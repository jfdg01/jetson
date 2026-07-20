#!/usr/bin/env python3
"""P5.18 mechanical verdict — the SOLE authority on the RQ-P5.18 outcome.

Reads runs/DSC_<LEG>_<clip>_<f0>/results.json (written by the unchanged
P5.16 harness discover_p516.py) + scenes_p518.json + visual_downgrades.json,
prints the verdict branch, writes runs/verdict.json.

Pre-registered rules (frozen at design time, 2026-07-20):
  n        = 26 gating scenes per leg (car3:200 control excluded).
  BAR      = 20 of 26 per leg  (matches the P5.16 4/5 = 0.8 claim at real n).
  SAT      = 25 of 26 both legs -> saturation note (non-gating caveat).
  N_MIN    = 25 valid cells per leg, else INFRA [n-underflow].
  Missing/INVALID cell = FAIL for the count (conservative, no bar rescaling).
  Visual gate is DOWNGRADE-ONLY: a cell listed in visual_downgrades.json
  counts FAIL regardless of its results.json pass. Nothing can be upgraded.
  visual_downgrades.json MUST exist and its "audited" list MUST cover the
  mechanically-required audit set (computed below) or this script refuses.

Branches (exhaustive):
  INFRA [n-underflow]      valid < 25 in either leg (after Opus's one retry).
  1  YES                   WSEL >= 20/26 AND strengthened SWAP >= 20/26.
     (saturation note if both legs >= 25/26 — scene set may under-stress.)
  2  NO [SWAP-bound]       WSEL >= 20, SWAP < 20.
  3  NO [WSEL-bound]       WSEL < 20, SWAP >= 20.
  4  NO [select-broken]    both < 20.

Usage: verdict_p518.py [--runs DIR] | --selfcheck
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BAR, SAT, N_MIN, N_GATING = 20, 25, 25, 26
LEGS = ("WSEL", "SWAP")
ALWAYS_AUDIT_SCENES = {("person20", 1050)}   # borderline-overlap caveat cell
RANK_SAMPLE, FAIL_AUDIT_CAP = 5, 12


def _metric(leg, r):
    """Ranking metric for the audit sample (None sorts first)."""
    s = r["score"]
    v = s.get("deliver_iou") if leg == "WSEL" else s.get("deliver_iou_distractor")
    return -1.0 if v is None else v


def classify(leg, r):
    """Mechanical failure bucket, precedence order (P5.16 lesson:
    seed/discovery-correctness first)."""
    s = r["score"]
    reason = s.get("reason")
    if reason and str(reason).startswith("discovery-failed"):
        return "discovery"
    if reason is not None:
        return "carry-loss"                      # e.g. track lost during idle
    want = "target" if leg == "WSEL" else "distractor"
    if s.get("selection") != want:
        return "wrong-selection"
    if leg == "WSEL":
        return "carry-quality"                   # lock/coverage below floor
    if s.get("deliver_iou", 1.0) >= 0.25:
        return "on-target-not-distractor"
    return "off-distractor"                      # carry drift off the hand box


def required_audit(cells):
    """Deterministic audit set: every failing gating cell (cap 12, lowest
    metric first), 5 rank-sampled passing cells (metric-sorted indices
    0, n//4, n//2, 3n//4, n-1), plus the ALWAYS_AUDIT scenes, both legs."""
    req = set()
    fails = sorted([c for c in cells if c["gating"] and not c["final_pass"]],
                   key=lambda c: c["metric"])
    req |= {c["id"] for c in fails[:FAIL_AUDIT_CAP]}
    passes = sorted([c for c in cells if c["gating"] and c["final_pass"]],
                    key=lambda c: c["metric"])
    n = len(passes)
    if n:
        idx = sorted({0, n // 4, n // 2, (3 * n) // 4, n - 1})
        req |= {passes[i]["id"] for i in idx}
    for c in cells:
        if (c["clip"], c["f0"]) in ALWAYS_AUDIT_SCENES:
            req.add(c["id"])
    return req


def run(runs_dir: Path):
    scenes = json.loads((HERE / "scenes_p518.json").read_text())["scenes"]
    gating = [s for s in scenes if s.get("gating")]
    assert len(gating) == N_GATING, f"scene file drift: {len(gating)} gating"

    dg_path = HERE / "visual_downgrades.json"
    assert dg_path.exists(), (
        "visual_downgrades.json missing -- the visual audit is mandatory. "
        "Opus: open the required deliver.png files with the Read tool, then "
        'write {"audited": [...cell ids...], "downgrades": [{"cell": id, '
        '"seen": "..."}]} (downgrades may be empty, audited may not).')
    dg = json.loads(dg_path.read_text())
    audited = set(dg.get("audited", []))
    downgraded = {d["cell"]: d.get("seen", "") for d in dg.get("downgrades", [])}

    cells = []
    for sc in scenes:
        for leg in LEGS:
            cid = f"DSC_{leg}_{sc['clip']}_{sc['f0']}"
            p = runs_dir / cid / "results.json"
            if not p.exists():
                cells.append({"id": cid, "leg": leg, "clip": sc["clip"],
                              "f0": sc["f0"], "gating": bool(sc.get("gating")),
                              "invalid": True, "final_pass": False,
                              "metric": -1.0, "bucket": "INVALID"})
                continue
            r = json.loads(p.read_text())
            base = bool(r["pass"])
            final = base and cid not in downgraded
            cells.append({
                "id": cid, "leg": leg, "clip": sc["clip"], "f0": sc["f0"],
                "gating": bool(sc.get("gating")), "invalid": False,
                "base_pass": base, "final_pass": final,
                "downgraded": cid in downgraded,
                "metric": _metric(leg, r),
                "bucket": None if final else classify(leg, r),
                "weak": r.get("swap_weak_pass"),
                "selection": r["score"].get("selection"),
                "reason": r["score"].get("reason"),
                "shadow_sel": (r.get("meta", {}).get("shadow") or {}).get("selected"),
                "wall_s": r.get("wall_s")})

    req = required_audit(cells)
    missing_audit = req - audited
    assert not missing_audit, (
        f"visual audit incomplete -- these cells' deliver.png (and, for "
        f"'discovery' buckets, discovery_<cand>.png) must be opened with the "
        f"Read tool and listed in visual_downgrades.json audited: "
        f"{sorted(missing_audit)}")

    counts, valid_n = {}, {}
    for leg in LEGS:
        g = [c for c in cells if c["gating"] and c["leg"] == leg]
        counts[leg] = sum(c["final_pass"] for c in g)
        valid_n[leg] = sum(not c["invalid"] for c in g)

    if min(valid_n.values()) < N_MIN:
        branch, verdict = "INFRA", (f"INFRA [n-underflow]: valid cells "
                                    f"WSEL {valid_n['WSEL']}/26, SWAP "
                                    f"{valid_n['SWAP']}/26 (< {N_MIN})")
    elif counts["WSEL"] >= BAR and counts["SWAP"] >= BAR:
        sat = counts["WSEL"] >= SAT and counts["SWAP"] >= SAT
        branch = "1"
        verdict = (f"YES: WSEL {counts['WSEL']}/26, strengthened SWAP "
                   f"{counts['SWAP']}/26 (bar {BAR}/26)"
                   + (" [saturated >= 25/26 both legs -- scene set may "
                      "under-stress; non-gating caveat]" if sat else ""))
    elif counts["WSEL"] >= BAR:
        branch = "2"
        verdict = (f"NO [SWAP-bound]: WSEL {counts['WSEL']}/26 passes, "
                   f"SWAP {counts['SWAP']}/26 < {BAR}")
    elif counts["SWAP"] >= BAR:
        branch = "3"
        verdict = (f"NO [WSEL-bound]: SWAP {counts['SWAP']}/26 passes, "
                   f"WSEL {counts['WSEL']}/26 < {BAR}")
    else:
        branch = "4"
        verdict = (f"NO [select-broken]: WSEL {counts['WSEL']}/26, "
                   f"SWAP {counts['SWAP']}/26, both < {BAR}")

    ctrl = [c for c in cells if not c["gating"]]
    weak = sum(1 for c in cells
               if c["leg"] == "SWAP" and c["gating"] and c.get("weak"))
    fails = [c for c in cells if c["gating"] and not c["final_pass"]]
    out = {"branch": branch, "verdict": verdict, "counts": counts,
           "valid_n": valid_n, "bar": BAR, "weak_swap": weak,
           "control": [{k: c.get(k) for k in
                        ("id", "final_pass", "reason")} for c in ctrl],
           "failing": [{k: c.get(k) for k in
                        ("id", "bucket", "selection", "reason", "metric",
                         "downgraded")} for c in fails],
           "audited": sorted(audited), "downgrades": downgraded}
    (runs_dir / "verdict.json").write_text(json.dumps(out, indent=2))
    print(f"P5.18 VERDICT branch {branch}: {verdict}")
    print(f"  weak SWAP (non-gating): {weak}/26")
    for c in ctrl:
        print(f"  control {c['id']}: pass={c['final_pass']} "
              f"reason={c.get('reason')}")
    for c in fails:
        print(f"  FAIL {c['id']}: bucket={c['bucket']} sel={c.get('selection')} "
              f"reason={c.get('reason')} metric={c['metric']:.2f}"
              + (" [VISUAL DOWNGRADE]" if c.get("downgraded") else ""))
    return out


# --------------------------------------------------------------------------- #
def selfcheck():
    """Synthetic runs tree: bar arithmetic, downgrade flip, INFRA underflow,
    audit-set enforcement."""
    import shutil
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="p518_vd_"))
    scenes = json.loads((HERE / "scenes_p518.json").read_text())["scenes"]
    dg_path = HERE / "visual_downgrades.json"
    saved = dg_path.read_text() if dg_path.exists() else None

    def fake(cid, ok, *, reason=None, sel=None, iou=0.8, ioud=0.8, leg="WSEL"):
        d = tmp / cid
        d.mkdir(parents=True, exist_ok=True)
        (d / "results.json").write_text(json.dumps({
            "pass": ok, "swap_weak_pass": ok if leg == "SWAP" else None,
            "wall_s": 30.0,
            "score": {"reason": reason, "selection": sel or
                      ("target" if leg == "WSEL" else "distractor"),
                      "deliver_iou": iou, "deliver_iou_distractor": ioud,
                      "genuine_lock": ok, "coverage": 1.0 if ok else 0.0},
            "meta": {"shadow": {"selected": "target"}}}))

    def build(wsel_pass, swap_pass, *, skip=()):
        shutil.rmtree(tmp, ignore_errors=True)
        gi = 0
        for sc in scenes:
            for leg in LEGS:
                cid = f"DSC_{leg}_{sc['clip']}_{sc['f0']}"
                if cid in skip:
                    continue
                if not sc.get("gating"):
                    fake(cid, True, leg=leg)
                    continue
                k = gi if leg == "WSEL" else gi
                ok = k < (wsel_pass if leg == "WSEL" else swap_pass)
                fake(cid, ok, leg=leg,
                     reason=None if ok else "discovery-failed:target",
                     iou=0.8 if ok else 0.0, ioud=0.8 if ok else 0.0)
            gi += sc.get("gating", False)

    def audit_all():
        cells = []
        for sc in scenes:
            for leg in LEGS:
                cells.append(f"DSC_{leg}_{sc['clip']}_{sc['f0']}")
        dg_path.write_text(json.dumps({"audited": cells, "downgrades": []}))

    try:
        # (A) 20/20 -> branch 1 YES; 19 SWAP -> branch 2.
        build(20, 20); audit_all()
        assert run(tmp)["branch"] == "1"
        build(20, 19); audit_all()
        assert run(tmp)["branch"] == "2"
        build(19, 20); audit_all()
        assert run(tmp)["branch"] == "3"
        build(10, 10); audit_all()
        assert run(tmp)["branch"] == "4"
        # (B) saturation note fires at 26/26.
        build(26, 26); audit_all()
        r = run(tmp)
        assert r["branch"] == "1" and "saturated" in r["verdict"]
        # (C) downgrade-only visual gate flips 20 -> 19 -> branch 2.
        build(20, 20)
        cells = [f"DSC_{leg}_{sc['clip']}_{sc['f0']}"
                 for sc in scenes for leg in LEGS]
        victim = next(c for c in cells if c.startswith("DSC_SWAP_")
                      and "car3_200" not in c)
        dg_path.write_text(json.dumps(
            {"audited": cells,
             "downgrades": [{"cell": victim, "seen": "box on background"}]}))
        assert run(tmp)["branch"] == "2"
        # (D) INFRA: 2 missing WSEL cells -> valid 24 < 25.
        gat = [sc for sc in scenes if sc.get("gating")][:2]
        build(26, 26, skip={f"DSC_WSEL_{sc['clip']}_{sc['f0']}" for sc in gat})
        audit_all()
        assert run(tmp)["branch"] == "INFRA"
        # (E) audit enforcement: empty audited list refuses.
        build(20, 20)
        dg_path.write_text(json.dumps({"audited": [], "downgrades": []}))
        try:
            run(tmp)
            raise SystemExit("audit enforcement did not fire")
        except AssertionError:
            pass
        print("verdict_p518 selfcheck OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if saved is None:
            dg_path.unlink(missing_ok=True)
        else:
            dg_path.write_text(saved)


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        d = Path(sys.argv[sys.argv.index("--runs") + 1]) \
            if "--runs" in sys.argv else HERE / "runs"
        run(d)
