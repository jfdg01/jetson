#!/usr/bin/env python3
"""R-36 verdict: paired maintain-vs-select McNemar over the SWAP-hard bank.

verdict_p518.py is a per-LEG bar counter (WSEL>=20/26 AND SWAP>=20/26) hardcoded
to P5.18's 26-cell bank; R-36 asks a different, PAIRED question -- is delivering a
named DISTRACTOR (SWAP) separable from delivering the maintained TARGET (WSEL) on
the SAME clip -- so it needs an exact McNemar on the discordant pairs, not two bars.

One scene per distinct UAV123 capture => n_effective == n_rows (no pseudo-replication
to deflate). b = WSEL pass & SWAP fail; c = WSEL fail & SWAP pass. Frozen gate
(README): reject H0 at two-sided exact McNemar p<0.05, reachable only at b+c>=6
one-directional, directional expectation b>c (select is the harder arm). Miss branch
is pre-registered: b+c<6 or a two-directional split -> "select fails but is not
separable-from-maintain at this n".

MANDATORY visual audit (CLAUDE.md "look at it"): the cells that MOVE the McNemar are
the discordant pairs and every SWAP pass (the strengthened-but-still-fakeable outcome).
This refuses to emit a verdict until a hand `visual_downgrades.json` covers them.
Downgrade-only: the audit can turn a mechanical PASS into a FAIL, never the reverse.

    python verdict_r36.py runs/r36 bank/scenes_r36.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from grounding.stats import mcnemar, min_discordant_for_significance  # noqa: E402

AUDIT_CAP = 12


def load_cell(runs: Path, leg: str, clip: str, f0: int) -> dict:
    p = runs / f"DSC_{leg}_{clip}_{f0}" / "results.json"
    if not p.exists():
        raise SystemExit(f"INFRA: missing run {p} -- matrix incomplete for {leg} {clip}:{f0}")
    return json.loads(p.read_text())


def required_audit(pairs: list[dict]) -> list[tuple[str, str, int]]:
    """(leg, clip, f0) cells whose correctness determines b/c. Discordant cells
    plus every SWAP pass; capped, discordants first (they move the test directly)."""
    disc, swap_pass = [], []
    for pr in pairs:
        clip, f0 = pr["clip"], pr["f0"]
        if pr["wsel_pass"] != pr["swap_pass"]:
            disc.append(("WSEL", clip, f0))
            disc.append(("SWAP", clip, f0))
        elif pr["swap_pass"]:
            swap_pass.append(("SWAP", clip, f0))
    return (disc + swap_pass)[:AUDIT_CAP]


def apply_downgrades(pairs: list[dict], downgrades: dict) -> None:
    """visual_downgrades.json: {"WSEL_clip_f0": {"pass": false|"confirmed":true|"exclude":true, "why": ...}}.
    Downgrade-only: a downgrade may set pass True->False; "exclude":true drops the
    whole pair (a cell whose GT is defective -- removes evidence, never manufactures
    it); "confirmed":true attests the cell was viewed with no change."""
    for pr in pairs:
        for leg in ("wsel", "swap"):
            key = f"{leg.upper()}_{pr['clip']}_{pr['f0']}"
            d = downgrades.get(key)
            if d is None:
                continue
            if d.get("pass") is True:
                raise SystemExit(f"AUDIT REFUSED: {key} tries to UPGRADE; audit is downgrade-only")
            if d.get("exclude") is True:
                pr["excluded"] = f"{leg}: {d.get('why', '')}"
            if pr[f"{leg}_pass"] and d.get("pass") is False:
                pr[f"{leg}_pass"] = False
                pr.setdefault("downgraded", []).append(f"{leg}: {d.get('why', '')}")


def main() -> None:
    runs = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/r36")
    scenes = json.loads(Path(sys.argv[2] if len(sys.argv) > 2
                             else "bank/scenes_r36.json").read_text())["scenes"]
    pairs = []
    for sc in scenes:
        clip, f0 = sc["clip"], sc["f0"]
        w = load_cell(runs, "WSEL", clip, f0)
        s = load_cell(runs, "SWAP", clip, f0)
        pairs.append({"clip": clip, "f0": f0,
                      "wsel_pass": bool(w["pass"]), "swap_pass": bool(s["pass"]),
                      "wsel_reason": w["score"].get("reason"),
                      "swap_sel": s["score"].get("selection"),
                      "swap_iou_dist": s["score"].get("deliver_iou_distractor")})

    # --- mandatory visual audit gate -------------------------------------
    need = required_audit(pairs)
    dgpath = runs / "visual_downgrades.json"
    if not dgpath.exists():
        print("VERDICT REFUSED: no visual_downgrades.json.")
        print(f"Open the overlay.mp4 / prompt frame for each cell below, then write "
              f"{dgpath} (may be empty {{}} if all confirmed):")
        for leg, clip, f0 in need:
            print(f"  audit {leg} {clip}:{f0}  -> {runs}/DD_{leg}_{clip}_{f0}/overlay.mp4")
        raise SystemExit(2)
    downgrades = json.loads(dgpath.read_text())
    covered = {f"{leg}_{clip}_{f0}" for leg, clip, f0 in need}
    missing = covered - set(downgrades)   # every required cell must appear (even {"confirmed":true})
    if missing:
        raise SystemExit(f"AUDIT INCOMPLETE: required cells not in visual_downgrades.json: "
                         f"{sorted(missing)}")
    apply_downgrades(pairs, downgrades)
    excluded = [p for p in pairs if p.get("excluded")]
    pairs = [p for p in pairs if not p.get("excluded")]

    # --- paired McNemar (audit-clean pairs only) --------------------------
    b = sum(1 for p in pairs if p["wsel_pass"] and not p["swap_pass"])
    c = sum(1 for p in pairs if not p["wsel_pass"] and p["swap_pass"])
    n = len(pairs)
    p = mcnemar(b, c, "two-sided")
    floor = min_discordant_for_significance(n)
    reachable = floor is not None and (b + c) >= floor
    if b + c == 0:
        branch = "MISS [0 discordant -- arms indistinguishable, not equivalent]"
    elif not reachable:
        branch = (f"MISS [b+c={b+c} < reachable floor {floor}; select not separable "
                  f"from maintain at n={n}]")
    elif p <= 0.05 and b > c:
        branch = f"REJECT H0 [select < maintain, McNemar p={p:.4g}, b={b} c={c}]"
    elif p <= 0.05:
        branch = f"REJECT H0 but WRONG DIRECTION [c>b, p={p:.4g}]"
    else:
        branch = f"MISS [b+c={b+c} reachable but p={p:.4g} > 0.05]"

    for ex in excluded:
        print(f"  EXCLUDED (defective GT, audit): {ex['clip']}@{ex['f0']} -- {ex['excluded']}")
    print(f"R-36 maintain-vs-select  n={n}  b(WSEL+/SWAP-)={b}  c(WSEL-/SWAP+)={c}")
    print(f"  WSEL pass rate {sum(p['wsel_pass'] for p in pairs)}/{n}   "
          f"SWAP pass rate {sum(p['swap_pass'] for p in pairs)}/{n}")
    print(f"  reachable floor (n={n}): {floor} discordant one-way")
    print(f"  McNemar two-sided p = {p:.4g}")
    print(f"  VERDICT: {branch}")
    for pr in pairs:
        flag = "  <-- discordant" if pr["wsel_pass"] != pr["swap_pass"] else ""
        dg = f"  DOWNGRADED({';'.join(pr['downgraded'])})" if pr.get("downgraded") else ""
        print(f"    {pr['clip']:12s}@{pr['f0']:<5d} WSEL={'P' if pr['wsel_pass'] else 'F'} "
              f"SWAP={'P' if pr['swap_pass'] else 'F'}{flag}{dg}")
    (runs / "verdict_r36.json").write_text(json.dumps(
        {"n": n, "b": b, "c": c, "p_two_sided": p, "reachable_floor": floor,
         "reachable": reachable, "branch": branch,
         "excluded": [{"clip": e["clip"], "f0": e["f0"], "why": e["excluded"]} for e in excluded],
         "pairs": pairs}, indent=2))


if __name__ == "__main__":
    main()
