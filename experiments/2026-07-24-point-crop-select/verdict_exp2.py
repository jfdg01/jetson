#!/usr/bin/env python3
"""EXP-2 verdict: paired point-crop (PT) vs natural-language (NL) McNemar, per leg.

Pairs NL-pass vs PT-pass on the SAME scene, per leg (WSEL control, SWAP the acquisition
test). b = NL pass & PT fail; c = NL fail & PT pass. Pre-registered expectation: PT removes
referring-expression ambiguity, so if anything moves it is c>b (PT wins). 26 cells over 13
UAV123 clips => deflate the discordants to the clip scale (invariant I2: cite the deflated p).

Frozen branches (README):
  REJECT H0 [PT>NL] : two-sided exact McNemar p<0.05 AND c>b (reachable only at b+c>=6).
  REJECT H0 WRONG-DIR: p<0.05 AND b>c (NL beat PT -- would contradict the premise).
  MISS [not separable]: b+c below the reachable floor, or reachable but p>=0.05.
This is the predicted outcome (R-38: grounding symmetric) -> the residual is carry/delivery.

MANDATORY visual audit (CLAUDE.md "look at it"): the cells that move the McNemar are the
discordant pairs and every SWAP pass (a delivered box that overlaps the distractor GT by
coincidence still counts mechanically). Refuses a verdict until a hand `visual_downgrades.json`
covers them (open runs/overlays/<key>.jpg with the Read tool first). Downgrade-only.

    python verdict_exp2.py runs/exp2 .../scenes_p518.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from grounding.stats import (deflate_to_effective, mcnemar,          # noqa: E402
                             min_discordant_for_significance)

LEGS = ("WSEL", "SWAP")
AUDIT_CAP = 14


def _key(arm, leg, clip, f0):
    return f"{arm}_{leg}_{clip}_{f0}"


def required_audit(per, scenes):
    """(arm, leg, clip, f0) cells whose correctness moves a McNemar: every discordant
    pair (both arms) + every SWAP pass. Discordants first; capped."""
    disc, swap_pass = [], []
    for s in scenes:
        clip, f0 = s["clip"], s["f0"]
        for leg in LEGS:
            nl = per.get(_key("NL", leg, clip, f0), {}).get("pass", False)
            pt = per.get(_key("PT", leg, clip, f0), {}).get("pass", False)
            if nl != pt:
                disc.append(("NL", leg, clip, f0))
                disc.append(("PT", leg, clip, f0))
            if leg == "SWAP":
                for arm, p in (("NL", nl), ("PT", pt)):
                    if p and (arm, leg, clip, f0) not in disc:
                        swap_pass.append((arm, leg, clip, f0))
    return (disc + swap_pass)[:AUDIT_CAP]


def apply_downgrades(per, downgrades):
    """{"PT_SWAP_clip_f0": {"pass": false, "why": ...}} | {"exclude": true} | {"confirmed": true}.
    Downgrade-only: pass True->False, or drop the cell (exclude). Never upgrades."""
    excluded = set()
    for key, d in downgrades.items():
        if d.get("pass") is True:
            raise SystemExit(f"AUDIT REFUSED: {key} tries to UPGRADE; audit is downgrade-only")
        if d.get("exclude") is True:
            excluded.add(key)
        if key in per and per[key].get("pass") and d.get("pass") is False:
            per[key]["pass"] = False
            per[key].setdefault("downgraded", d.get("why", ""))
    return excluded


def leg_bc(per, scenes, leg, excluded):
    b = c = n = 0
    rows = []
    for s in scenes:
        clip, f0 = s["clip"], s["f0"]
        kn, kp = _key("NL", leg, clip, f0), _key("PT", leg, clip, f0)
        if kn in excluded or kp in excluded:
            continue
        nl = bool(per.get(kn, {}).get("pass", False))
        pt = bool(per.get(kp, {}).get("pass", False))
        n += 1
        b += nl and not pt
        c += (not nl) and pt
        rows.append((clip, f0, nl, pt))
    return b, c, n, rows


def branch_for(b, c, n, n_clips):
    bd, _ = deflate_to_effective(b, n, n_clips)
    cd, _ = deflate_to_effective(c, n, n_clips)
    p_raw = mcnemar(b, c, "two-sided")
    p_def = mcnemar(bd, cd, "two-sided")
    floor_cells = min_discordant_for_significance(n)
    floor_clips = min_discordant_for_significance(n_clips)
    reachable = floor_cells is not None and (b + c) >= floor_cells
    if b + c == 0:
        br = "MISS [0 discordant -- arms indistinguishable, not equivalent]"
    elif not reachable:
        br = f"MISS [b+c={b + c} < reachable floor {floor_cells}; not separable at n={n}]"
    elif p_raw <= 0.05 and c > b:
        br = f"REJECT H0 [PT>NL, McNemar p={p_raw:.4g} raw / {p_def:.4g} clip-deflated, b={b} c={c}]"
    elif p_raw <= 0.05 and b > c:
        br = f"REJECT H0 WRONG-DIR [NL>PT, p={p_raw:.4g}, b={b} c={c}]"
    else:
        br = f"MISS [b+c={b + c} reachable but p={p_raw:.4g} > 0.05]"
    return {"b": b, "c": c, "n": n, "b_def": bd, "c_def": cd, "n_clips": n_clips,
            "p_raw": p_raw, "p_deflated": p_def, "floor_cells": floor_cells,
            "floor_clips": floor_clips, "reachable": reachable, "branch": br}


def main() -> None:
    runs = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/exp2")
    mpath = sys.argv[2] if len(sys.argv) > 2 else str(
        Path(__file__).resolve().parents[1] / "2026-07-20-n25-select" / "scenes_p518.json")
    md = json.loads(Path(mpath).read_text())
    scenes = [s for s in (md["scenes"] if isinstance(md, dict) else md) if s.get("gating", True)]
    per = json.loads((runs / "results.json").read_text())["per_cell"]

    # --- mandatory visual audit gate -------------------------------------
    need = required_audit(per, scenes)
    dgpath = runs / "visual_downgrades.json"
    if not dgpath.exists():
        print("VERDICT REFUSED: no visual_downgrades.json.")
        print(f"Open each overlay below with the Read tool, then write {dgpath} "
              f"(may be empty {{}} if all confirmed):")
        for arm, leg, clip, f0 in need:
            print(f"  audit {arm} {leg} {clip}:{f0}  -> {runs}/overlays/{_key(arm, leg, clip, f0)}.jpg")
        raise SystemExit(2)
    downgrades = json.loads(dgpath.read_text())
    covered = {_key(a, l, c, f) for a, l, c, f in need}
    missing = covered - set(downgrades)
    if missing:
        raise SystemExit(f"AUDIT INCOMPLETE: required cells not in visual_downgrades.json: "
                         f"{sorted(missing)}")
    excluded = apply_downgrades(per, downgrades)

    n_clips = len({s["clip"] for s in scenes})
    out = {"n_clips": n_clips, "legs": {}}
    for leg in LEGS:
        b, c, n, rows = leg_bc(per, scenes, leg, excluded)
        res = branch_for(b, c, n, n_clips)
        nlp = sum(r[2] for r in rows)
        ptp = sum(r[3] for r in rows)
        out["legs"][leg] = {**res, "nl_pass": nlp, "pt_pass": ptp}
        print(f"\n[{leg}]  NL {nlp}/{n}   PT {ptp}/{n}   b(NLonly)={b} c(PTonly)={c}")
        print(f"  reachable floor: {res['floor_cells']} (cells) / {res['floor_clips']} (clips)")
        print(f"  McNemar p = {res['p_raw']:.4g} raw, {res['p_deflated']:.4g} deflated to {n_clips} clips")
        print(f"  VERDICT: {res['branch']}")
        for clip, f0, nl, pt in rows:
            flag = "  <-- discordant" if nl != pt else ""
            print(f"    {clip:12s}@{f0:<5d} NL={'P' if nl else 'F'} PT={'P' if pt else 'F'}{flag}")
    (runs / "verdict_exp2.json").write_text(json.dumps(out, indent=2))
    print(f"\n-> {runs / 'verdict_exp2.json'}")


if __name__ == "__main__":
    main()
