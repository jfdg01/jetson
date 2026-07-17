#!/usr/bin/env python
"""P5.11 mechanical verdict: bank v2 (designed-crossing scene bank) build gate.

Reads experiments/2026-07-17-bankv2-crossing/runs/* and prints the full gate
table + overall verdict. No thresholds live anywhere else; Opus does not
deliberate. The visual gate V is done by the operator on the overlay PNGs
(including the crossing-peak overlay_f<xpeak>.png of every bank cell) and can
only DOWNGRADE the printed verdict.

The core design tension this file resolves mechanically: bank v2 INTENDS
occlusion (the P5.9 G6 gate existed to kill exactly this look when it was a
render DEFECT). The partition is the per-frame `occl` field in gt.jsonl (pure
GT geometry: fraction of a car's box covered by the OTHER car's box when the
other car is nearer the camera):
  - CLEAR frames (occl <= 0.05): v1-grade integrity applies unchanged. A
    fragmented or impure car body here is a render DEFECT -> gate fails.
  - OCCLUDED frames (occl >= 0.50): the farther (white) car is EXPECTED to
    fragment -- that is the designed occlusion; its integrity is NOT graded.
    Instead the OCCLUDER (blue, nearer by construction every frame) must
    render intact (G8c) and must actually be drawn IN FRONT (G8b).
Blue is never occluded (white is farther the whole clip by construction), so
blue is graded v1-style on ALL frames.

Gates (G1/G3/G5 byte-for-byte from P5.9; G0 scaled 240->300 frames):
  G0  completion: results.json present, 300 gt.jsonl lines, retries+lost <= 15
  G1  render-alive: 0 dead frames, 0 identical consecutive, stamps exact
  G2c GT-on-vehicle, occlusion-aware: median purity >= 0.30 AND >= 4x the
      whole-clip lateral bg control -- white over CLEAR frames only, blue over
      all frames
  G3  co-visibility: both cars bbox area >= 150 px in >= 80% of frames
  G5  throughput: >= 0.5 generated frames/s wall
  G6c rendered integrity, occlusion-aware: white over CLEAR frames only
      (frag p10 >= 0.95, frac(frag < 0.90) <= 0.02, n_clear >= 60 -- the
      probe_seed1 calibration clip measured n_clear = 80, p10 = 0.995);
      blue over ALL frames (same thresholds, n >= 250)
  G4a determinism (seed101_A vs seed101_D): canonical GT (sim stamps
      excluded) byte-identical AND frames mean|diff| <= 2.0, frac(>8) <= 1%
  G4b seed diversity: min pairwise whole-scenario divergence over the 16
      pre-registered seeds >= 1.0 m (author_scenario profile=v2), PLUS
      recorded gt.jsonl f0 positions reproduce the authored scenario
      within 1e-3 m for every completed run

Bank-only gates (the crossing itself; gate runs 101/202/303 are generator
sanity checks and are NOT screened for crossing quality -- seed 303's
predicted occlusion window is 24 frames, one short of the screen, which is
why the screen is a bank-cell property, not a generator property):
  G8  realized occlusion (from recorded gt.jsonl + frames):
      G8a >= 25 recorded frames with white occl >= 0.50
      G8b blue-dominance: median over those frames of
          n_blue/(n_blue+n_white) inside the box-intersection >= 0.55
          (probe_seed1 measured 0.687; a wrong z-order would put white
          pixels in front and drive this toward 0)
      G8c occluder intact: blue frag over those frames median >= 0.95 AND
          frac(frag < 0.90) <= 0.10 (probe: 1.0 / 0.0)
  G9  crossing-as-designed: results.json v2_screen.pass is true AND the
      recorded-box GT-GT IoU trace reproduces it: peak >= 0.20, peak at
      frame <= 125, max over frames 150..299 <= 0.15

Overall YES iff:
  - all 4 gate runs pass G0,G1,G2c,G3,G5,G6c, and G4a and G4b pass, AND
  - >= 11 of 12 bank cells pass G0,G1,G2c,G3,G5,G6c,G8,G9, with any missing
    cell explicitly marked infra (runs/<cell>.INFRA), at most one, and no
    present-but-gate-failing cell.
"""
import importlib.util
import itertools
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
spec = importlib.util.spec_from_file_location("scenegen", REPO / "runners" / "scenegen.py")
sg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sg)
import cv2

GATE_RUNS = [("seed101_A", 101), ("seed202_B", 202), ("seed303_C", 303), ("seed101_D", 101)]
BANK_SEEDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 14]   # first 12 passing the offline screen (52/60 sweep)
BANK_RUNS = [(f"bank{i + 1:02d}", s) for i, s in enumerate(BANK_SEEDS)]
ALL_SEEDS = [101, 202, 303] + BANK_SEEDS
N_FRAMES = 300
PROMPT_F = 150


def _load(d):
    rj = d / "results.json"
    if not rj.exists():
        return None, None
    recs = [json.loads(l) for l in open(d / "gt.jsonl")]
    return json.load(open(rj)), recs


def grade_run(run, seed, is_bank):
    d = HERE / "runs" / run
    r, recs = _load(d)
    if r is None:
        return None
    g0 = (len(recs) == N_FRAMES and
          r["g0_retries_pose"] + r["g0_retries_step"] + r["g0_response_lost"] <= 15)
    g1 = (r["g1_dead_frames"] == 0 and r["g1_identical_consecutive"] == 0
          and r["g1_stamp_steps_ok"])
    g3 = r["g3_both_visible_frac"] >= 0.80
    g5 = r["fps_wall"] >= 0.5

    # occlusion-aware per-frame pools from gt.jsonl
    w_pur_clear, w_frag_clear = [], []
    b_pur_all, b_frag_all = [], []
    occ_frames = []          # (f, white_bbox, blue_bbox) with occl >= 0.50
    b_frag_occ = []
    for rec in recs:
        w, b = rec["objs"][0], rec["objs"][1]
        occ = w.get("occl", 0.0)
        if w["bbox"] is not None and occ <= 0.05:
            if "purity" in w:
                w_pur_clear.append(w["purity"])
            if "frag" in w:
                w_frag_clear.append(w["frag"])
        if b["bbox"] is not None:
            if "purity" in b:
                b_pur_all.append(b["purity"])
            if "frag" in b:
                b_frag_all.append(b["frag"])
        if occ >= 0.50 and w["bbox"] is not None and b["bbox"] is not None:
            occ_frames.append((rec["f"], w["bbox"], b["bbox"]))
            if "frag" in b:
                b_frag_occ.append(b["frag"])

    bg = r["g2_bg_purity_median"]
    w_pur = float(np.median(w_pur_clear)) if w_pur_clear else None
    b_pur = float(np.median(b_pur_all)) if b_pur_all else None
    g2c = (w_pur is not None and w_pur >= 0.30 and w_pur >= 4 * (bg["0"] or 0.0)
           and b_pur is not None and b_pur >= 0.30 and b_pur >= 4 * (bg["1"] or 0.0))
    wf, bf = np.array(w_frag_clear), np.array(b_frag_all)
    g6c = (len(wf) >= 60 and float(np.percentile(wf, 10)) >= 0.95
           and float(np.mean(wf < 0.90)) <= 0.02
           and len(bf) >= 250 and float(np.percentile(bf, 10)) >= 0.95
           and float(np.mean(bf < 0.90)) <= 0.02)

    g8 = g9 = None
    bdom = None
    if is_bank:
        g8a = len(occ_frames) >= 25
        doms = []
        for f, wb, bb in occ_frames:
            img = cv2.imread(str(d / "frames" / f"{f:04d}.png"))
            if img is None:
                break
            x1, y1 = int(max(wb[0], bb[0])), int(max(wb[1], bb[1]))
            x2, y2 = int(min(wb[2], bb[2])), int(min(wb[3], bb[3]))
            if x2 <= x1 or y2 <= y1:
                continue
            roi = img[y1:y2, x1:x2]
            nb = int(sg.color_mask(roi, "blue").sum())
            nw = int(sg.color_mask(roi, "white").sum())
            doms.append(nb / max(nb + nw, 1))
        g8b = len(doms) == len(occ_frames) > 0 and float(np.median(doms)) >= 0.55
        bfo = np.array(b_frag_occ)
        g8c = (len(bfo) > 0 and float(np.median(bfo)) >= 0.95
               and float(np.mean(bfo < 0.90)) <= 0.10)
        g8 = g8a and g8b and g8c
        bdom = round(float(np.median(doms)), 3) if doms else None

        iou_rec = np.array([sg._iou2d(rec["objs"][0]["bbox"], rec["objs"][1]["bbox"])
                            for rec in recs])
        g9 = (bool(r.get("v2_screen", {}).get("pass"))
              and float(iou_rec.max()) >= 0.20
              and int(iou_rec.argmax()) <= PROMPT_F - 25
              and float(iou_rec[PROMPT_F:].max()) <= 0.15)

    gates = [g0, g1, g2c, g3, g5, g6c] + ([g8, g9] if is_bank else [])
    return {"run": run, "seed": seed, "g0": g0, "g1": g1, "g2c": g2c, "g3": g3,
            "g5": g5, "g6c": g6c, "g8": g8, "g9": g9,
            "fps": r["fps_wall"], "pur": (w_pur, b_pur),
            "wfrag_p10": round(float(np.percentile(wf, 10)), 3) if len(wf) else None,
            "n_clear": len(wf), "n_occ": len(occ_frames), "bdom": bdom,
            "xpeak_f": r.get("v2_xpeak_pred_f"),
            "ok": all(gates)}


def canonical_gt(path):
    out = []
    for line in open(path):
        r = json.loads(line)
        r.pop("t_sim_ns", None)
        out.append(json.dumps(r, sort_keys=True))
    return "\n".join(out)


def g4a():
    a, d = HERE / "runs" / "seed101_A", HERE / "runs" / "seed101_D"
    if not (a / "results.json").exists() or not (d / "results.json").exists():
        return None, "missing runs"
    ident = canonical_gt(a / "gt.jsonl") == canonical_gt(d / "gt.jsonl")
    diffs = []
    for i in range(N_FRAMES):
        fa = cv2.imread(str(a / "frames" / f"{i:04d}.png"))
        fd = cv2.imread(str(d / "frames" / f"{i:04d}.png"))
        if fa is None or fd is None:
            return None, f"missing frame {i}"
        diffs.append(np.abs(fa.astype(np.int16) - fd.astype(np.int16)))
    mean_abs = float(np.mean([x.mean() for x in diffs]))
    frac8 = float(np.mean([(x > 8).mean() for x in diffs]))
    ok = ident and mean_abs <= 2.0 and frac8 <= 0.01
    return ok, (f"gt_identical={ident} frame_mean_absdiff={round(mean_abs, 4)}"
                f" (<= 2.0) frac_gt8={round(frac8, 5)} (<= 0.01)")


def g4b():
    scs = {s: sg.author_scenario(s, N_FRAMES, profile="v2") for s in ALL_SEEDS}

    def div(A, B):
        dt = np.linalg.norm(A["target"]["xy"] - B["target"]["xy"], axis=1).mean()
        dd = np.linalg.norm(A["distractor"]["xy"] - B["distractor"]["xy"], axis=1).mean()
        dc = np.linalg.norm(A["cam_pos"] - B["cam_pos"], axis=1).mean()
        return (dt + dd + dc) / 3

    dmin, argmin = 1e9, None
    for a, b in itertools.combinations(ALL_SEEDS, 2):
        v = div(scs[a], scs[b])
        if v < dmin:
            dmin, argmin = v, (a, b)
    faithful, checked = True, 0
    for run, seed in GATE_RUNS + BANK_RUNS:
        gt = HERE / "runs" / run / "gt.jsonl"
        if not gt.exists():
            continue
        r0 = json.loads(open(gt).readline())
        for oid, role in ((0, "target"), (1, "distractor")):
            want = scs[seed][role]["xy"][0]
            got = np.array(r0["objs"][oid]["pos"][:2])
            if np.abs(want - got).max() > 1e-3:
                faithful = False
        checked += 1
    ok = dmin >= 1.0 and faithful and checked > 0
    return ok, (f"min pairwise scenario divergence {dmin:.2f} m (>= 1.0) at "
                f"pair {argmin}; recorded-f0 faithful={faithful} over {checked} runs")


def main():
    print(f"{'run':12s} {'seed':4s} G0 G1 G2c G3 G5 G6c G8 G9  fps    "
          f"purW/B        wfragp10 nclr nocc bdom   xpeak")
    gate_rows, bank_rows, missing = [], [], []
    for run, seed in GATE_RUNS + BANK_RUNS:
        is_bank = run.startswith("bank")
        g = grade_run(run, seed, is_bank)
        if g is None:
            infra = (HERE / "runs" / f"{run}.INFRA").exists()
            missing.append((run, "INFRA" if infra else "MISSING"))
            print(f"{run:12s} {seed:<4d} "
                  f"{'-- INFRA --' if infra else '-- MISSING results.json --'}")
            continue
        (bank_rows if is_bank else gate_rows).append(g)
        i8 = "-" if g["g8"] is None else int(g["g8"])
        i9 = "-" if g["g9"] is None else int(g["g9"])
        print(f"{g['run']:12s} {g['seed']:<4d} {int(g['g0'])}  {int(g['g1'])}  "
              f"{int(g['g2c'])}   {int(g['g3'])}  {int(g['g5'])}  "
              f"{int(g['g6c'])}   {i8}  {i9}   {g['fps']:<6.2f} "
              f"{(g['pur'][0] or 0):.3f}/{(g['pur'][1] or 0):.3f}   "
              f"{g['wfrag_p10']}    {g['n_clear']:<4d} {g['n_occ']:<4d} "
              f"{str(g['bdom']):<6s} {g['xpeak_f']}")

    a_ok, a_msg = g4a()
    print(f"G4a determinism seed101_A vs seed101_D: {a_msg} -> "
          f"{'PASS' if a_ok else 'FAIL' if a_ok is not None else 'INCOMPLETE'}")
    b_ok, b_msg = g4b()
    print(f"G4b seed diversity (16 seeds, v2): {b_msg} -> {'PASS' if b_ok else 'FAIL'}")

    gate_complete = len(gate_rows) == len(GATE_RUNS)
    gate_pass = gate_complete and all(g["ok"] for g in gate_rows)
    bank_gate_fail = any(not g["ok"] for g in bank_rows)
    bank_infra = [m for m in missing if m[0].startswith("bank") and m[1] == "INFRA"]
    bank_missing = [m for m in missing if m[0].startswith("bank") and m[1] == "MISSING"]
    gate_missing = [m for m in missing if not m[0].startswith("bank")]
    bank_pass = (not bank_gate_fail and not bank_missing
                 and len(bank_rows) >= 11 and len(bank_infra) <= 1)

    if gate_missing or bank_missing or a_ok is None:
        print(f"RQ-P5.11 OVERALL: INCOMPLETE (missing: {missing})")
        sys.exit(2)
    verdict = "YES" if (gate_pass and a_ok and b_ok and bank_pass) else "NO"
    why = []
    if not gate_pass:
        why.append("gate-run gates: " + ",".join(
            f"{g['run']}:{'/'.join(k for k in ('g0', 'g1', 'g2c', 'g3', 'g5', 'g6c') if not g[k])}"
            for g in gate_rows if not g["ok"]))
    if not a_ok:
        why.append("G4a")
    if not b_ok:
        why.append("G4b")
    if not bank_pass:
        why.append(f"bank ({sum(g['ok'] for g in bank_rows)}/12 pass, "
                   f"{len(bank_infra)} infra)")
    print(f"RQ-P5.11 OVERALL: {verdict}"
          + (f" [{'; '.join(why)}]" if why else "")
          + " (YES iff 4/4 gate runs pass G0,G1,G2c,G3,G5,G6c AND G4a AND G4b"
            " AND >= 11/12 bank cells also pass G8,G9 with <= 1 infra loss and"
            " 0 gate failures; the visual gate V -- operator opens the named"
            " overlay PNGs, including every bank cell's crossing-peak overlay"
            " -- can only downgrade this to NO)")


def selfcheck():
    """Offline: grades the committed probe_seed1 calibration clip as if it
    were a bank cell (it must pass every gate its on-disk data allows), then
    doctors copies to prove the negative paths fire. No gz, no GPU."""
    import shutil
    import tempfile

    probe = HERE / "curation" / "probe_seed1"
    assert (probe / "results.json").exists(), "probe_seed1 fixture missing"
    have_frames = (probe / "frames" / "0000.png").exists()

    real_here = HERE
    with tempfile.TemporaryDirectory() as td:
        # grade the probe through the real grader by symlinking it in as bank01
        tmp_runs = Path(td) / "runs"
        tmp_runs.mkdir()
        (tmp_runs / "bank01").symlink_to(probe)
        globals()["HERE"] = Path(td)
        g = grade_run("bank01", 1, is_bank=True)
        globals()["HERE"] = real_here
        assert g is not None
        assert g["g0"] and g["g1"] and g["g2c"] and g["g3"] and g["g5"] and g["g6c"], g
        assert g["g9"], g
        assert g["n_occ"] >= 25, g
        if have_frames:
            assert g["g8"] and g["bdom"] is not None and g["bdom"] >= 0.55, g
            print(f"--- selfcheck: probe passes all bank gates (bdom={g['bdom']})")
        else:
            print("--- selfcheck: probe passes gates (frames absent: G8b skipped)")

        # negative 1: truncated gt.jsonl -> G0 fails
        t2 = Path(td) / "neg1"
        d2 = t2 / "runs" / "bank01"
        d2.mkdir(parents=True)
        shutil.copy(probe / "results.json", d2 / "results.json")
        lines = open(probe / "gt.jsonl").readlines()
        (d2 / "gt.jsonl").write_text("".join(lines[:200]))
        if have_frames:
            (d2 / "frames").symlink_to(probe / "frames")
        globals()["HERE"] = t2
        g2 = grade_run("bank01", 1, is_bank=True)
        globals()["HERE"] = real_here
        assert g2 is not None and not g2["g0"] and not g2["ok"], "truncated gt must fail G0"
        print("--- selfcheck: truncated gt.jsonl fails G0")

        # negative 2: doctored v2_screen.pass=false -> G9 fails
        t3 = Path(td) / "neg2"
        d3 = t3 / "runs" / "bank01"
        d3.mkdir(parents=True)
        r = json.load(open(probe / "results.json"))
        r["v2_screen"]["pass"] = False
        (d3 / "results.json").write_text(json.dumps(r))
        shutil.copy(probe / "gt.jsonl", d3 / "gt.jsonl")
        if have_frames:
            (d3 / "frames").symlink_to(probe / "frames")
        globals()["HERE"] = t3
        g3_ = grade_run("bank01", 1, is_bank=True)
        globals()["HERE"] = real_here
        assert g3_ is not None and not g3_["g9"] and not g3_["ok"], "doctored screen must fail G9"
        print("--- selfcheck: doctored v2_screen fails G9")

    print("verdict_p511 selfcheck OK")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        main()
