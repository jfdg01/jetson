#!/usr/bin/env python3
"""P5.19 mechanical verdict — the SOLE authority on the RQ-P5.19 outcome.

Reads runs/DSC_<LEG>_<clip>_<f0>/results.json (written by rescue_p519.py)
plus the FROZEN P5.18 baseline (../2026-07-20-n25-select/runs, committed) and
visual_downgrades.json, prints the verdict branch, writes runs/verdict.json.

Pre-registered rules (frozen at design time, 2026-07-20):
  Scene set  = scenes_p518.json VERBATIM (referenced, not copied):
               26 gating scenes per leg, car3:200 control excluded.
  BAR        = 20 of 26 per leg (same bar P5.18 missed at SWAP 17/26).
  N_MIN      = 25 valid cells per leg, else INFRA [n-underflow].
  Missing/INVALID cell = FAIL for the count (conservative, no rescaling).
  BASELINE   = P5.18 counts recomputed from the committed results.json and
               ASSERTED == {WSEL: 22, SWAP: 17}; drift -> refuse to verdict.
  MIN_SEP    = +2 SWAP cells vs baseline 17: the pre-registered minimum
               arm-to-arm difference that counts as a real rescue effect
               (2 wrong-seed cells are visually confirmed recoverable;
               +1 is within single-cell timing noise).
  Visual gate is DOWNGRADE-ONLY: a cell listed in visual_downgrades.json
  counts FAIL regardless of its results.json pass. Nothing can be upgraded.
  visual_downgrades.json MUST exist and its "audited" list MUST cover the
  mechanically-required audit set (computed below) or this script refuses.
  The audit set ADDS to P5.18's rules: every FLIPPED cell (either direction)
  and every cell where grace fired (grace_deliver.png is the claim frame).

Branches (exhaustive):
  INFRA [n-underflow]          valid < 25 in either leg (after one retry).
  1  YES [late-entry-rescued]  WSEL >= 20/26 AND strengthened SWAP >= 20/26.
  2  NO  [wsel-regressed]      WSEL < 20 (the patch broke the passing leg;
                               SWAP count reported but not reached).
  3  NO  [rescue-real-but-short] WSEL >= 20, SWAP <= 19, SWAP-17 >= +2:
                               the mechanism recovers cells but other
                               failure modes keep SWAP under the bar.
  4  NO  [rescue-dead]         WSEL >= 20, SWAP <= 19, SWAP-17 <= +1:
                               aligned dedup + grace do not move SWAP
                               beyond noise (includes regressions).

Usage: verdict_p519.py [--runs DIR] | --selfcheck
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P518 = HERE.parent / "2026-07-20-n25-select"
BASE_RUNS = P518 / "runs"
SCENES_PATH = P518 / "scenes_p518.json"
BAR, N_MIN, N_GATING, MIN_SEP = 20, 25, 26, 2
BASELINE = {"WSEL": 22, "SWAP": 17}
LEGS = ("WSEL", "SWAP")
ALWAYS_AUDIT_SCENES = {("person20", 1050)}   # P5.18 borderline-overlap cell
WATCH = {"DSC_SWAP_car9_950", "DSC_SWAP_person10_450"}  # proxy-guard cells
RANK_SAMPLE, FAIL_AUDIT_CAP = 5, 12


def _metric(leg, r):
    """Ranking metric for the audit sample (None sorts first)."""
    s = r["score"]
    v = s.get("deliver_iou") if leg == "WSEL" else s.get("deliver_iou_distractor")
    return -1.0 if v is None else v


def classify(leg, r):
    """Mechanical failure bucket, precedence order (P5.18 verbatim)."""
    s = r["score"]
    reason = s.get("reason")
    if reason and str(reason).startswith("discovery-failed"):
        return "discovery"
    if reason is not None:
        return "carry-loss"
    want = "target" if leg == "WSEL" else "distractor"
    if s.get("selection") != want:
        return "wrong-selection"
    if leg == "WSEL":
        return "carry-quality"
    if s.get("deliver_iou", 1.0) >= 0.25:
        return "on-target-not-distractor"
    return "off-distractor"


def _mechanism(c):
    """Attribution for a flip: did the patch actually touch this cell?"""
    m = []
    if c.get("dedup_fired"):
        m.append("aligned-dedup")
    if c.get("graced"):
        m.append("grace")
    if c.get("grace_refused"):
        m.append(f"grace-refused:{c['grace_refused']}")
    return "+".join(m) if m else "timing-noise"


def baseline_pass(scenes, base_dir: Path):
    """Recompute the frozen P5.18 per-cell pass map; assert no drift."""
    per_cell, counts = {}, {"WSEL": 0, "SWAP": 0}
    for sc in scenes:
        for leg in LEGS:
            cid = f"DSC_{leg}_{sc['clip']}_{sc['f0']}"
            p = base_dir / cid / "results.json"
            ok = bool(json.loads(p.read_text())["pass"]) if p.exists() else False
            per_cell[cid] = ok
            if sc.get("gating"):
                counts[leg] += ok
    assert counts == BASELINE, (
        f"BASELINE DRIFT: recomputed P5.18 counts {counts} != frozen "
        f"{BASELINE} -- the committed baseline moved; refuse to verdict.")
    return per_cell


def required_audit(cells):
    """Deterministic audit set: every failing gating cell (cap 12, lowest
    metric first), 5 rank-sampled passing cells, the ALWAYS_AUDIT scenes
    both legs, PLUS every flipped cell and every grace-fired cell."""
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
        if c.get("flip") or c.get("graced"):
            req.add(c["id"])
    return req


def run(runs_dir: Path, base_dir: Path = BASE_RUNS,
        scenes_path: Path = SCENES_PATH, baseline_check=True):
    scenes = json.loads(scenes_path.read_text())["scenes"]
    gating = [s for s in scenes if s.get("gating")]
    assert len(gating) == N_GATING, f"scene file drift: {len(gating)} gating"
    base = baseline_pass(scenes, base_dir) if baseline_check else {}

    dg_path = HERE / "visual_downgrades.json"
    assert dg_path.exists(), (
        "visual_downgrades.json missing -- the visual audit is mandatory. "
        "Opus: open the required deliver.png / grace_deliver.png / "
        "discovery_*.png files with the Read tool, then write "
        '{"audited": [...cell ids...], "downgrades": [{"cell": id, '
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
                              "base_pass": base.get(cid),
                              "flip": bool(base.get(cid)),   # pass -> missing
                              "metric": -1.0, "bucket": "INVALID"})
                continue
            r = json.loads(p.read_text())
            ok = bool(r["pass"])
            final = ok and cid not in downgraded
            disc = (r.get("meta", {}).get("discovery") or [])
            gr = (r.get("meta", {}).get("grace") or {})
            cells.append({
                "id": cid, "leg": leg, "clip": sc["clip"], "f0": sc["f0"],
                "gating": bool(sc.get("gating")), "invalid": False,
                "base_pass": base.get(cid), "final_pass": final,
                "flip": (base.get(cid) is not None
                         and final != base.get(cid)),
                "downgraded": cid in downgraded,
                "metric": _metric(leg, r),
                "bucket": None if final else classify(leg, r),
                "weak": r.get("swap_weak_pass"),
                "selection": r["score"].get("selection"),
                "reason": r["score"].get("reason"),
                "acquire_s": r["score"].get("acquire_s"),
                "dedup_fired": any(e.get("outcome") == "duplicate_reject"
                                   for e in disc),
                "graced": bool(gr.get("fired")),
                "grace_refused": gr.get("refused"),
                "shadow_sel": (r.get("meta", {}).get("shadow") or {}).get("selected"),
                "p519": r.get("p519"),
                "wall_s": r.get("wall_s")})
    # every scored cell must carry the patch marker (guards a stale-harness
    # rerun of the P5.16 code writing into this runs dir)
    unmarked = [c["id"] for c in cells
                if not c["invalid"] and baseline_check and not c.get("p519")]
    assert not unmarked, f"cells missing the p519 patch marker: {unmarked}"

    req = required_audit(cells)
    missing_audit = req - audited
    assert not missing_audit, (
        f"visual audit incomplete -- these cells' deliver.png (plus "
        f"grace_deliver.png where grace fired, and discovery_<cand>.png for "
        f"'discovery' buckets and flips) must be opened with the Read tool "
        f"and listed in visual_downgrades.json audited: "
        f"{sorted(missing_audit)}")

    counts, valid_n = {}, {}
    for leg in LEGS:
        g = [c for c in cells if c["gating"] and c["leg"] == leg]
        counts[leg] = sum(c["final_pass"] for c in g)
        valid_n[leg] = sum(not c["invalid"] for c in g)
    delta = {leg: counts[leg] - BASELINE[leg] for leg in LEGS}

    if min(valid_n.values()) < N_MIN:
        branch, verdict = "INFRA", (f"INFRA [n-underflow]: valid cells "
                                    f"WSEL {valid_n['WSEL']}/26, SWAP "
                                    f"{valid_n['SWAP']}/26 (< {N_MIN})")
    elif counts["WSEL"] >= BAR and counts["SWAP"] >= BAR:
        branch = "1"
        verdict = (f"YES [late-entry-rescued]: WSEL {counts['WSEL']}/26, "
                   f"strengthened SWAP {counts['SWAP']}/26 (bar {BAR}/26; "
                   f"baseline {BASELINE['SWAP']}, delta {delta['SWAP']:+d})")
    elif counts["WSEL"] < BAR:
        branch = "2"
        verdict = (f"NO [wsel-regressed]: WSEL {counts['WSEL']}/26 < {BAR} "
                   f"(baseline {BASELINE['WSEL']}); SWAP {counts['SWAP']}/26")
    elif delta["SWAP"] >= MIN_SEP:
        branch = "3"
        verdict = (f"NO [rescue-real-but-short]: SWAP {counts['SWAP']}/26 < "
                   f"{BAR} but delta {delta['SWAP']:+d} >= +{MIN_SEP} vs "
                   f"baseline {BASELINE['SWAP']} (WSEL {counts['WSEL']}/26)")
    else:
        branch = "4"
        verdict = (f"NO [rescue-dead]: SWAP {counts['SWAP']}/26, delta "
                   f"{delta['SWAP']:+d} <= +{MIN_SEP - 1} vs baseline "
                   f"{BASELINE['SWAP']} (WSEL {counts['WSEL']}/26)")

    recovered = [c for c in cells if c["gating"] and c["flip"] and c["final_pass"]]
    regressed = [c for c in cells if c["gating"] and c["flip"] and not c["final_pass"]]
    ctrl = [c for c in cells if not c["gating"]]
    weak = sum(1 for c in cells
               if c["leg"] == "SWAP" and c["gating"] and c.get("weak"))
    fails = [c for c in cells if c["gating"] and not c["final_pass"]]
    dedup_n = sum(1 for c in cells if not c["invalid"] and c["dedup_fired"])
    graces = [{"id": c["id"], "acquire_s": c["acquire_s"],
               "pass": c["final_pass"]} for c in cells if c.get("graced")]
    refusals = [{"id": c["id"], "refused": c["grace_refused"]}
                for c in cells if c.get("grace_refused")]

    out = {"branch": branch, "verdict": verdict, "counts": counts,
           "baseline": BASELINE, "delta": delta, "valid_n": valid_n,
           "bar": BAR, "min_sep": MIN_SEP, "weak_swap": weak,
           "recovered": [{k: c.get(k) for k in ("id", "base_pass")}
                         | {"mechanism": _mechanism(c)} for c in recovered],
           "regressed": [{k: c.get(k) for k in ("id", "bucket", "reason")}
                         | {"mechanism": _mechanism(c)} for c in regressed],
           "dedup_fired_cells": dedup_n, "graces": graces,
           "grace_refusals": refusals,
           "watch": [{k: c.get(k) for k in
                      ("id", "final_pass", "bucket", "reason")}
                     for c in cells if c["id"] in WATCH],
           "control": [{k: c.get(k) for k in
                        ("id", "final_pass", "reason")} for c in ctrl],
           "failing": [{k: c.get(k) for k in
                        ("id", "bucket", "selection", "reason", "metric",
                         "downgraded")} for c in fails],
           "audited": sorted(audited), "downgrades": downgraded}
    (runs_dir / "verdict.json").write_text(json.dumps(out, indent=2))
    print(f"P5.19 VERDICT branch {branch}: {verdict}")
    print(f"  flips: +{len(recovered)} recovered / -{len(regressed)} "
          f"regressed; dedup fired in {dedup_n} cells; grace fired "
          f"{len(graces)}x, refused {len(refusals)}x")
    for c in recovered:
        print(f"  RECOVERED {c['id']}")
    for c in regressed:
        print(f"  REGRESSED {c['id']}")
    for g in graces:
        print(f"  grace {g['id']}: acquire_s={g['acquire_s']} pass={g['pass']}")
    for c in fails:
        print(f"  FAIL {c['id']}: bucket={c['bucket']} sel={c.get('selection')} "
              f"reason={c.get('reason')} metric={c['metric']:.2f}"
              + (" [VISUAL DOWNGRADE]" if c.get("downgraded") else ""))
    return out


# --------------------------------------------------------------------------- #
def selfcheck():
    """Synthetic base+new runs trees: bar/threshold arithmetic for every
    branch, flip attribution, baseline-drift refusal, patch-marker guard,
    downgrade flip, INFRA underflow, audit-set enforcement (incl. the new
    flipped/graced audit requirements)."""
    import shutil
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="p519_vd_"))
    base_t, new_t = root / "base", root / "new"
    scenes = json.loads(SCENES_PATH.read_text())["scenes"]
    gat = [s for s in scenes if s.get("gating")]
    dg_path = HERE / "visual_downgrades.json"
    saved = dg_path.read_text() if dg_path.exists() else None

    def cid_of(sc, leg):
        return f"DSC_{leg}_{sc['clip']}_{sc['f0']}"

    def fake(tree, cid, ok, *, leg, reason=None, marker=True, grace=None,
             dedup=False, refused=None):
        d = tree / cid
        d.mkdir(parents=True, exist_ok=True)
        disc = [{"cand": "target", "outcome": "accepted"},
                {"cand": "distractor",
                 "outcome": "duplicate_reject" if dedup else "accepted"}]
        meta = {"discovery": disc, "shadow": {"selected": "target"}}
        if grace is not None:
            meta["grace"] = {"fired": True, "acquire_s": grace}
        if refused:
            meta["grace"] = {"fired": False, "refused": refused}
        r = {"pass": ok, "swap_weak_pass": ok if leg == "SWAP" else None,
             "wall_s": 30.0,
             "score": {"reason": reason, "selection":
                       ("target" if leg == "WSEL" else "distractor"),
                       "deliver_iou": 0.8 if leg == "WSEL" else 0.1,
                       "deliver_iou_distractor": 0.8 if ok else 0.0,
                       "acquire_s": grace or 0.0,
                       "genuine_lock": ok, "coverage": 1.0 if ok else 0.0},
             "meta": meta}
        if marker:
            r["p519"] = {"patch": "late-entry-rescue"}
        (d / "results.json").write_text(json.dumps(r))

    def build(tree, wsel_pass, swap_pass, *, skip=(), marker=True,
              grace_ids=(), dedup_ids=()):
        shutil.rmtree(tree, ignore_errors=True)
        gi = 0
        for sc in scenes:
            for leg in LEGS:
                cid = cid_of(sc, leg)
                if cid in skip:
                    continue
                if not sc.get("gating"):
                    fake(tree, cid, True, leg=leg, marker=marker)
                    continue
                ok = gi < (wsel_pass if leg == "WSEL" else swap_pass)
                fake(tree, cid, ok, leg=leg, marker=marker,
                     reason=None if ok else "discovery-failed:distractor",
                     grace=0.8 if cid in grace_ids else None,
                     dedup=cid in dedup_ids)
            gi += bool(sc.get("gating"))

    def audit_all():
        cells = [cid_of(sc, leg) for sc in scenes for leg in LEGS]
        dg_path.write_text(json.dumps({"audited": cells, "downgrades": []}))

    try:
        build(base_t, 22, 17)          # the frozen P5.18 shape
        kw = dict(base_dir=base_t)

        # (A) branch arithmetic: 22/20 -> 1; 19 WSEL -> 2; 22/19 (+2) -> 3;
        #     22/18 (+1) -> 4; 22/16 (-1) -> 4.
        build(new_t, 22, 20); audit_all()
        r = run(new_t, **kw)
        assert r["branch"] == "1" and r["delta"]["SWAP"] == 3, r
        build(new_t, 19, 20); audit_all()
        assert run(new_t, **kw)["branch"] == "2"
        build(new_t, 22, 19); audit_all()
        assert run(new_t, **kw)["branch"] == "3"
        build(new_t, 22, 18); audit_all()
        assert run(new_t, **kw)["branch"] == "4"
        build(new_t, 22, 16); audit_all()
        r = run(new_t, **kw)
        assert r["branch"] == "4" and r["delta"]["SWAP"] == -1, r

        # (B) flip attribution: the 3 recovered SWAP cells carry mechanism
        #     tags when dedup/grace fired, else timing-noise.
        sw_ids = [cid_of(sc, "SWAP") for sc in gat]
        build(new_t, 22, 20, grace_ids={sw_ids[17]}, dedup_ids={sw_ids[18]})
        audit_all()
        r = run(new_t, **kw)
        mech = {c["id"]: c["mechanism"] for c in r["recovered"]}
        assert mech[sw_ids[17]] == "grace", mech
        assert mech[sw_ids[18]] == "aligned-dedup", mech
        assert mech[sw_ids[19]] == "timing-noise", mech
        assert {g["id"] for g in r["graces"]} == {sw_ids[17]}, r["graces"]

        # (C) baseline drift refusal.
        build(base_t, 21, 17)
        build(new_t, 22, 20); audit_all()
        try:
            run(new_t, **kw)
            raise SystemExit("baseline drift did not refuse")
        except AssertionError as e:
            assert "BASELINE DRIFT" in str(e), e
        build(base_t, 22, 17)

        # (D) patch-marker guard refuses unpatched results.
        build(new_t, 22, 20, marker=False); audit_all()
        try:
            run(new_t, **kw)
            raise SystemExit("patch-marker guard did not refuse")
        except AssertionError as e:
            assert "p519 patch marker" in str(e), e

        # (E) downgrade-only visual gate: 22/20 with one SWAP downgrade
        #     -> 19 passes, delta +2 -> branch 3.
        build(new_t, 22, 20)
        cells = [cid_of(sc, leg) for sc in scenes for leg in LEGS]
        victim = sw_ids[0]
        dg_path.write_text(json.dumps(
            {"audited": cells,
             "downgrades": [{"cell": victim, "seen": "box on background"}]}))
        assert run(new_t, **kw)["branch"] == "3"

        # (F) INFRA: 2 missing WSEL cells -> valid 24 < 25 (and the missing
        #     base-passing cells count as flips needing audit -> audit_all).
        build(new_t, 22, 20,
              skip={cid_of(sc, "WSEL") for sc in gat[:2]})
        audit_all()
        assert run(new_t, **kw)["branch"] == "INFRA"

        # (G) audit enforcement: flipped + graced cells are REQUIRED; an
        #     audited list missing them refuses even if fails are covered.
        build(new_t, 22, 20, grace_ids={sw_ids[19]})
        full = set(cells)
        dg_path.write_text(json.dumps(
            {"audited": sorted(full - {sw_ids[19]}), "downgrades": []}))
        try:
            run(new_t, **kw)
            raise SystemExit("audit enforcement did not fire")
        except AssertionError as e:
            assert sw_ids[19] in str(e), e
        print("verdict_p519 selfcheck OK")
    finally:
        shutil.rmtree(root, ignore_errors=True)
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
