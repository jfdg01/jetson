#!/usr/bin/env python3
"""P5.20 mechanical verdict -- the SOLE authority on the RQ-P5.20 outcome.

Reads runs/T/DSC_<LEG>_<clip>_<f0>/results.json and runs/S/... (written by
capacity_p520.py), plus the FROZEN committed P5.19 runs (replication
reference) and visual_downgrades.json. Prints the branch, writes
runs/verdict.json.

Pre-registered rules (frozen at design time, 2026-07-20):
  Scene set   = scenes_p518.json VERBATIM (referenced, not copied):
                26 gating scenes per leg, car3:200 control excluded.
  Arms        = T (facebook/sam2.1-hiera-tiny; the P5.19 config verbatim,
                fresh schedule re-roll = replication control) and
                S (facebook/sam2.1-hiera-small; equal stride, same harness).
  N_MIN       = 25 valid cells per leg per arm, else INFRA [n-underflow].
  N_PAIR_MIN  = 50 of 52 gating leg-cells valid in BOTH arms, else INFRA
                [pair-underflow].
  Missing/INVALID cell = FAIL for that arm's leg count (conservative).
  Gate a (RQ-P5.20a, capacity): paired_delta >= +3, where paired_delta =
      sum over gating leg-cells valid in BOTH arms of (S_pass - T_pass).
      MIN_SEP = +3 clears the observed schedule-noise band: between the
      P5.18 and P5.19 runs (same scenes, patch differences machine-
      attributed) exactly 1 SWAP cell flipped on pure timing noise and
      WSEL was pass-map-identical, so +-2 is the honest noise band and
      +3 is the smallest count above it.
  Gate b (RQ-P5.20b, replication): T_WSEL >= 20/26 AND T_SWAP >= 20/26 --
      the P5.19 bar, on a fresh schedule re-roll of the unchanged config.
  P519_REF    = committed P5.19 counts recomputed from
                ../2026-07-20-late-entry-rescue/runs and ASSERTED ==
                {WSEL: 22, SWAP: 20}; drift -> refuse to verdict.
  Marker guard: every valid cell must carry BOTH the p519 patch marker AND
      a p520 stamp whose arm/model match its tree, else refuse (stale or
      mixed-arm runs dir).
  Visual gate is DOWNGRADE-ONLY via visual_downgrades.json; ids are
      '<arm>/<cid>'. "audited" MUST cover the mechanically-required set or
      this script refuses. Required: per arm every failing gating cell
      (cap 12, lowest metric first) + 5 rank-sampled passing cells + the
      ALWAYS_AUDIT scenes both legs; PLUS both arms of every S-vs-T
      flipped gating cell; PLUS every grace-fired cell.

Branches (exhaustive):
  INFRA [n-underflow | pair-underflow]
  1  YES [capacity-lifts, p519-replicates]     a AND b
  2  YES [capacity-lifts, replication-failed]  a AND NOT b
  3  NO  [capacity-flat, p519-replicates]      NOT a AND b
  4  NO  [capacity-flat, replication-failed]   NOT a AND NOT b
  Sub-tag [capacity-hurts] appended to 3/4 when paired_delta <= -3.

Non-gating diagnostics (reported, never gate): carry-attribution of
recovered cells (T-side failure bucket), T-vs-P519-committed per-cell flip
list (the replication noise census), per-arm grace/dedup census, control
cells, weak-SWAP counts.

Usage: verdict_p520.py [--runs DIR] | --selfcheck
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
P519 = REPO / "experiments" / "2026-07-20-late-entry-rescue"
P518 = REPO / "experiments" / "2026-07-20-n25-select"
sys.path.insert(0, str(P519))
from verdict_p519 import _metric, classify                         # noqa: E402

SCENES_PATH = P518 / "scenes_p518.json"
P519_RUNS = P519 / "runs"
P519_REF = {"WSEL": 22, "SWAP": 20}
ARMS = {"T": "facebook/sam2.1-hiera-tiny",
        "S": "facebook/sam2.1-hiera-small"}
BAR, N_MIN, N_GATING, MIN_SEP, N_PAIR_MIN = 20, 25, 26, 3, 50
LEGS = ("WSEL", "SWAP")
ALWAYS_AUDIT_SCENES = {("person20", 1050), ("car3", 200)}
CARRY_BUCKETS = {"carry-loss", "carry-quality", "off-distractor",
                 "on-target-not-distractor"}
RANK_SAMPLE_N, FAIL_AUDIT_CAP = 5, 12


def ref_pass(scenes, ref_dir: Path):
    """Recompute the committed P5.19 per-cell pass map; assert no drift."""
    per_cell, counts = {}, {"WSEL": 0, "SWAP": 0}
    for sc in scenes:
        for leg in LEGS:
            cid = f"DSC_{leg}_{sc['clip']}_{sc['f0']}"
            p = ref_dir / cid / "results.json"
            ok = bool(json.loads(p.read_text())["pass"]) if p.exists() else False
            per_cell[cid] = ok
            if sc.get("gating"):
                counts[leg] += ok
    assert counts == P519_REF, (
        f"P519 REF DRIFT: recomputed counts {counts} != frozen {P519_REF} "
        f"-- the committed reference moved; refuse to verdict.")
    return per_cell


def _load_cells(runs_dir: Path, arm: str, scenes, downgraded):
    cells = []
    for sc in scenes:
        for leg in LEGS:
            cid = f"DSC_{leg}_{sc['clip']}_{sc['f0']}"
            aid = f"{arm}/{cid}"
            p = runs_dir / arm / cid / "results.json"
            if not p.exists():
                cells.append({"id": aid, "cid": cid, "arm": arm, "leg": leg,
                              "clip": sc["clip"], "f0": sc["f0"],
                              "gating": bool(sc.get("gating")),
                              "invalid": True, "final_pass": False,
                              "metric": -1.0, "bucket": "INVALID"})
                continue
            r = json.loads(p.read_text())
            # marker guard: stale-harness / mixed-arm protection
            assert r.get("p519", {}).get("patch") == "late-entry-rescue", (
                f"{aid}: missing/unexpected p519 patch marker -- stale "
                f"harness wrote this cell; delete the cell dir and re-run.")
            st = r.get("p520") or {}
            assert st.get("arm") == arm and st.get("sam2_model") == ARMS[arm], (
                f"{aid}: p520 stamp {st} does not match arm {arm} "
                f"({ARMS[arm]}) -- mixed-arm runs dir; refuse to verdict.")
            ok = bool(r["pass"])
            final = ok and aid not in downgraded
            disc = (r.get("meta", {}).get("discovery") or [])
            gr = (r.get("meta", {}).get("grace") or {})
            cells.append({
                "id": aid, "cid": cid, "arm": arm, "leg": leg,
                "clip": sc["clip"], "f0": sc["f0"],
                "gating": bool(sc.get("gating")), "invalid": False,
                "final_pass": final, "downgraded": aid in downgraded,
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
                "wall_s": r.get("wall_s")})
    return cells


def required_audit(cells_by_arm, flips):
    """Deterministic audit set over '<arm>/<cid>' ids."""
    req = set()
    for arm, cells in cells_by_arm.items():
        fails = sorted([c for c in cells if c["gating"] and not c["final_pass"]
                        and not c["invalid"]], key=lambda c: c["metric"])
        req |= {c["id"] for c in fails[:FAIL_AUDIT_CAP]}
        passes = sorted([c for c in cells if c["gating"] and c["final_pass"]],
                        key=lambda c: c["metric"])
        n = len(passes)
        if n:
            idx = sorted({0, n // 4, n // 2, (3 * n) // 4, n - 1})
            req |= {passes[i]["id"] for i in idx}
        for c in cells:
            if (c["clip"], c["f0"]) in ALWAYS_AUDIT_SCENES and not c["invalid"]:
                req.add(c["id"])
            if c.get("graced"):
                req.add(c["id"])
    for cid in flips:                      # both arms of every flipped cell
        req.add(f"T/{cid}")
        req.add(f"S/{cid}")
    return req


def run(runs_dir: Path, ref_dir: Path = P519_RUNS,
        scenes_path: Path = SCENES_PATH):
    scenes = json.loads(scenes_path.read_text())["scenes"]
    gating = [s for s in scenes if s.get("gating")]
    assert len(gating) == N_GATING, f"scene file drift: {len(gating)} gating"
    ref = ref_pass(scenes, ref_dir)

    dg_path = HERE / "visual_downgrades.json"
    assert dg_path.exists(), (
        "visual_downgrades.json missing -- the visual audit is mandatory. "
        "Opus: open the required deliver.png / grace_deliver.png / "
        "discovery_*.png files with the Read tool, then write "
        '{"audited": ["T/DSC_...", "S/DSC_...", ...], "downgrades": '
        '[{"cell": "<arm>/<cid>", "seen": "..."}]} (downgrades may be '
        "empty, audited may not).")
    dg = json.loads(dg_path.read_text())
    audited = set(dg.get("audited", []))
    downgraded = {d["cell"]: d.get("seen", "") for d in dg.get("downgrades", [])}

    cells_by_arm = {arm: _load_cells(runs_dir, arm, scenes, downgraded)
                    for arm in ARMS}
    by_cid = {arm: {c["cid"]: c for c in cells_by_arm[arm]} for arm in ARMS}

    # paired S-vs-T comparison on gating cells valid in both arms
    paired, flips, recovered, regressed = [], [], [], []
    for sc in gating:
        for leg in LEGS:
            cid = f"DSC_{leg}_{sc['clip']}_{sc['f0']}"
            t, s = by_cid["T"][cid], by_cid["S"][cid]
            if t["invalid"] or s["invalid"]:
                continue
            paired.append(cid)
            if s["final_pass"] != t["final_pass"]:
                flips.append(cid)
                if s["final_pass"]:
                    recovered.append({"cid": cid, "leg": leg,
                                      "t_bucket": t["bucket"],
                                      "s_graced": s["graced"],
                                      "s_dedup": s["dedup_fired"]})
                else:
                    regressed.append({"cid": cid, "leg": leg,
                                      "s_bucket": s["bucket"],
                                      "s_downgraded": s.get("downgraded")})
    paired_delta = len(recovered) - len(regressed)

    req = required_audit(cells_by_arm, flips)
    missing_audit = req - audited
    assert not missing_audit, (
        f"visual audit incomplete -- open these cells' deliver.png (plus "
        f"grace_deliver.png where grace fired, discovery_<cand>.png for "
        f"'discovery' buckets) with the Read tool and list them in "
        f"visual_downgrades.json audited: {sorted(missing_audit)}")

    counts, valid_n = {}, {}
    for arm in ARMS:
        counts[arm], valid_n[arm] = {}, {}
        for leg in LEGS:
            g = [c for c in cells_by_arm[arm]
                 if c["gating"] and c["leg"] == leg]
            counts[arm][leg] = sum(c["final_pass"] for c in g)
            valid_n[arm][leg] = sum(not c["invalid"] for c in g)
    totals = {arm: counts[arm]["WSEL"] + counts[arm]["SWAP"] for arm in ARMS}

    a = paired_delta >= MIN_SEP
    b = counts["T"]["WSEL"] >= BAR and counts["T"]["SWAP"] >= BAR
    hurts = paired_delta <= -MIN_SEP

    under = [f"{arm}/{leg} {valid_n[arm][leg]}/26" for arm in ARMS
             for leg in LEGS if valid_n[arm][leg] < N_MIN]
    if under:
        branch = "INFRA"
        verdict = f"INFRA [n-underflow]: valid cells {', '.join(under)} < {N_MIN}"
    elif len(paired) < N_PAIR_MIN:
        branch = "INFRA"
        verdict = (f"INFRA [pair-underflow]: only {len(paired)}/52 gating "
                   f"leg-cells valid in both arms (< {N_PAIR_MIN})")
    else:
        tag = " [capacity-hurts]" if hurts else ""
        tc = (f"T WSEL {counts['T']['WSEL']}/26 SWAP {counts['T']['SWAP']}/26, "
              f"S WSEL {counts['S']['WSEL']}/26 SWAP {counts['S']['SWAP']}/26, "
              f"paired delta {paired_delta:+d} (min_sep +{MIN_SEP}, "
              f"bar {BAR})")
        if a and b:
            branch, verdict = "1", f"YES [capacity-lifts, p519-replicates]: {tc}"
        elif a:
            branch, verdict = "2", f"YES [capacity-lifts, replication-failed]: {tc}"
        elif b:
            branch, verdict = "3", f"NO [capacity-flat, p519-replicates]{tag}: {tc}"
        else:
            branch, verdict = "4", (f"NO [capacity-flat, replication-failed]"
                                    f"{tag}: {tc}")

    # non-gating diagnostics
    carry_attr = sum(1 for r in recovered if r["t_bucket"] in CARRY_BUCKETS)
    t_vs_ref = []
    for sc in gating:
        for leg in LEGS:
            cid = f"DSC_{leg}_{sc['clip']}_{sc['f0']}"
            t = by_cid["T"][cid]
            if not t["invalid"] and ref.get(cid) is not None \
                    and t["final_pass"] != ref[cid]:
                t_vs_ref.append({"cid": cid,
                                 "dir": "p519_pass->T_fail" if ref[cid]
                                        else "p519_fail->T_pass"})
    graces = [{"id": c["id"], "acquire_s": c["acquire_s"],
               "pass": c["final_pass"]} for arm in ARMS
              for c in cells_by_arm[arm] if c.get("graced")]
    ctrl = [{"id": c["id"], "final_pass": c["final_pass"],
             "reason": c.get("reason")} for arm in ARMS
            for c in cells_by_arm[arm] if not c["gating"]]
    fails = [{"id": c["id"], "bucket": c["bucket"],
              "selection": c.get("selection"), "reason": c.get("reason"),
              "metric": c["metric"], "downgraded": c.get("downgraded")}
             for arm in ARMS for c in cells_by_arm[arm]
             if c["gating"] and not c["final_pass"]]
    weak = {arm: sum(1 for c in cells_by_arm[arm]
                     if c["leg"] == "SWAP" and c["gating"] and c.get("weak"))
            for arm in ARMS}
    dedup_n = {arm: sum(1 for c in cells_by_arm[arm]
                        if not c["invalid"] and c["dedup_fired"])
               for arm in ARMS}
    wall = {arm: round(sum(c.get("wall_s") or 0
                           for c in cells_by_arm[arm]) / 60, 1)
            for arm in ARMS}

    out = {"branch": branch, "verdict": verdict, "counts": counts,
           "totals": totals, "paired_delta": paired_delta,
           "paired_n": len(paired), "valid_n": valid_n,
           "gate_a_capacity": a, "gate_b_replication": b,
           "bar": BAR, "min_sep": MIN_SEP, "p519_ref": P519_REF,
           "recovered": recovered, "regressed": regressed,
           "carry_attributed_recoveries": carry_attr,
           "t_vs_p519_flips": t_vs_ref, "graces": graces,
           "control": ctrl, "failing": fails, "weak_swap": weak,
           "dedup_fired_cells": dedup_n, "arm_wall_min": wall,
           "audited": sorted(audited), "downgrades": downgraded}
    (runs_dir / "verdict.json").write_text(json.dumps(out, indent=2))
    print(f"P5.20 VERDICT branch {branch}: {verdict}")
    print(f"  gate a (capacity) {a}: paired delta {paired_delta:+d} on "
          f"{len(paired)} pairs; +{len(recovered)} recovered "
          f"({carry_attr} carry-attributed) / -{len(regressed)} regressed")
    print(f"  gate b (replication) {b}: T {counts['T']} vs P5.19 {P519_REF}; "
          f"T-vs-P5.19 flips {len(t_vs_ref)}")
    for r in recovered:
        print(f"  RECOVERED {r['cid']} (T bucket={r['t_bucket']})")
    for r in regressed:
        print(f"  REGRESSED {r['cid']} (S bucket={r['s_bucket']})")
    for g in graces:
        print(f"  grace {g['id']}: acquire_s={g['acquire_s']} pass={g['pass']}")
    for f in fails:
        print(f"  FAIL {f['id']}: bucket={f['bucket']} sel={f.get('selection')} "
              f"reason={f.get('reason')} metric={f['metric']:.2f}"
              + (" [VISUAL DOWNGRADE]" if f.get("downgraded") else ""))
    return out


# --------------------------------------------------------------------------- #
def selfcheck():
    """Synthetic runs/{T,S} + ref trees: branch arithmetic for all branches,
    paired-delta and capacity-hurts logic, INFRA underflows, marker guards,
    ref-drift refusal, downgrade demotion, audit enforcement (both arms of a
    flip required), carry attribution."""
    import shutil
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="p520_vd_"))
    runs_t, ref_t = root / "runs", root / "ref"
    scenes = json.loads(SCENES_PATH.read_text())["scenes"]
    gat = [s for s in scenes if s.get("gating")]
    dg_path = HERE / "visual_downgrades.json"
    saved = dg_path.read_text() if dg_path.exists() else None

    def cid_of(sc, leg):
        return f"DSC_{leg}_{sc['clip']}_{sc['f0']}"

    def fake(tree, cid, ok, *, leg, arm=None, reason=None, p519=True,
             p520=True, grace=None, bad_arm=None):
        d = tree / cid
        d.mkdir(parents=True, exist_ok=True)
        meta = {"discovery": [{"cand": "target", "outcome": "accepted"},
                              {"cand": "distractor", "outcome": "accepted"}],
                "shadow": {"selected": "target"}}
        if grace is not None:
            meta["grace"] = {"fired": True, "acquire_s": grace}
        r = {"pass": ok, "swap_weak_pass": ok if leg == "SWAP" else None,
             "wall_s": 30.0,
             "score": {"reason": reason, "selection":
                       ("target" if leg == "WSEL" else "distractor"),
                       "deliver_iou": 0.8 if leg == "WSEL" else 0.1,
                       "deliver_iou_distractor": 0.8 if ok else 0.0,
                       "acquire_s": grace or 0.0,
                       "genuine_lock": ok, "coverage": 1.0 if ok else 0.0},
             "meta": meta}
        if p519:
            r["p519"] = {"patch": "late-entry-rescue"}
        if p520 and arm:
            r["p520"] = {"arm": bad_arm or arm,
                         "sam2_model": ARMS[bad_arm or arm],
                         "equal_stride": True}
        (d / "results.json").write_text(json.dumps(r))

    def build_arm(arm, wsel_pass, swap_pass, *, skip=(), reason=None,
                  grace_ids=(), **fkw):
        tree = runs_t / arm
        shutil.rmtree(tree, ignore_errors=True)
        gi = 0
        for sc in scenes:
            for leg in LEGS:
                cid = cid_of(sc, leg)
                if cid in skip:
                    continue
                if not sc.get("gating"):
                    fake(tree, cid, True, leg=leg, arm=arm, **fkw)
                    continue
                ok = gi < (wsel_pass if leg == "WSEL" else swap_pass)
                fake(tree, cid, ok, leg=leg, arm=arm,
                     reason=None if ok else (reason or
                                             "discovery-failed:distractor"),
                     grace=0.8 if cid in grace_ids else None, **fkw)
            gi += bool(sc.get("gating"))

    def build_ref(wsel=22, swap=20):
        shutil.rmtree(ref_t, ignore_errors=True)
        gi = 0
        for sc in scenes:
            for leg in LEGS:
                if not sc.get("gating"):
                    fake(ref_t, cid_of(sc, leg), True, leg=leg)
                    continue
                ok = gi < (wsel if leg == "WSEL" else swap)
                fake(ref_t, cid_of(sc, leg), ok, leg=leg)
            gi += bool(sc.get("gating"))

    def audit_all():
        ids = [f"{arm}/{cid_of(sc, leg)}" for arm in ARMS
               for sc in scenes for leg in LEGS]
        dg_path.write_text(json.dumps({"audited": ids, "downgrades": []}))

    try:
        build_ref()
        kw = dict(ref_dir=ref_t)

        # (A) branch arithmetic. Prefix-pass builds make S a superset of T.
        build_arm("T", 22, 20); build_arm("S", 23, 22); audit_all()   # +3, b yes
        r = run(runs_t, **kw)
        assert r["branch"] == "1" and r["paired_delta"] == 3, r
        assert r["gate_a_capacity"] and r["gate_b_replication"], r
        build_arm("T", 22, 19); build_arm("S", 24, 20); audit_all()   # +3, b no
        assert run(runs_t, **kw)["branch"] == "2"
        build_arm("T", 22, 20); build_arm("S", 23, 21); audit_all()   # +2, b yes
        r = run(runs_t, **kw)
        assert r["branch"] == "3" and r["paired_delta"] == 2, r
        build_arm("T", 22, 19); build_arm("S", 22, 19); audit_all()   # 0, b no
        assert run(runs_t, **kw)["branch"] == "4"
        build_arm("T", 22, 20); build_arm("S", 20, 19); audit_all()   # -3, b yes
        r = run(runs_t, **kw)
        assert r["branch"] == "3" and "capacity-hurts" in r["verdict"], r

        # (B) carry attribution: T fails as carry-loss -> recovered cells
        #     are carry-attributed.
        build_arm("T", 22, 19, reason="lock-lost")
        build_arm("S", 23, 21); audit_all()
        r = run(runs_t, **kw)
        assert r["paired_delta"] == 3
        assert r["carry_attributed_recoveries"] == 3, r
        assert all(x["t_bucket"] == "carry-loss" for x in r["recovered"]), r

        # (C) INFRA n-underflow: 2 missing T WSEL cells -> valid 24.
        build_arm("T", 22, 20, skip={cid_of(sc, "WSEL") for sc in gat[:2]})
        build_arm("S", 23, 22); audit_all()
        assert run(runs_t, **kw)["branch"] == "INFRA"

        # (D) marker guards.
        build_arm("T", 22, 20, p520=False); build_arm("S", 23, 22); audit_all()
        try:
            run(runs_t, **kw)
            raise SystemExit("p520 marker guard did not refuse")
        except AssertionError as e:
            assert "p520 stamp" in str(e), e
        build_arm("T", 22, 20, bad_arm="S"); audit_all()
        try:
            run(runs_t, **kw)
            raise SystemExit("arm-mismatch guard did not refuse")
        except AssertionError as e:
            assert "p520 stamp" in str(e), e
        build_arm("T", 22, 20, p519=False); audit_all()
        try:
            run(runs_t, **kw)
            raise SystemExit("p519 marker guard did not refuse")
        except AssertionError as e:
            assert "p519 patch marker" in str(e), e

        # (E) ref drift refusal.
        build_arm("T", 22, 20); build_arm("S", 23, 22); audit_all()
        build_ref(21, 20)
        try:
            run(runs_t, **kw)
            raise SystemExit("ref drift did not refuse")
        except AssertionError as e:
            assert "P519 REF DRIFT" in str(e), e
        build_ref()

        # (F) downgrade-only visual gate: demoting one recovered S cell
        #     drops paired_delta 3 -> 2 => branch 1 -> 3.
        r = run(runs_t, **kw)
        assert r["branch"] == "1"
        victim = r["recovered"][0]["cid"]
        ids = [f"{arm}/{cid_of(sc, leg)}" for arm in ARMS
               for sc in scenes for leg in LEGS]
        dg_path.write_text(json.dumps(
            {"audited": ids,
             "downgrades": [{"cell": f"S/{victim}",
                             "seen": "box on background"}]}))
        r = run(runs_t, **kw)
        assert r["branch"] == "3" and r["paired_delta"] == 2, r

        # (G) audit enforcement: BOTH arms of a flipped cell are required;
        #     dropping the T side refuses even though T passed there... no:
        #     flipped cells are T-fail -> require T side too.
        audit_all()
        r = run(runs_t, **kw)
        flip_cid = r["recovered"][0]["cid"]
        dg_path.write_text(json.dumps(
            {"audited": [i for i in ids if i != f"T/{flip_cid}"],
             "downgrades": []}))
        try:
            run(runs_t, **kw)
            raise SystemExit("audit enforcement did not fire")
        except AssertionError as e:
            assert f"T/{flip_cid}" in str(e), e
        print("verdict_p520 selfcheck OK")
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
