#!/usr/bin/env python
"""P5.12 mechanical verdict: bank v2.1 (recalibrated designed-crossing bank).

Forward copy of P5.11's verdict_p511.py (byte-frozen there; do not edit that
file) with exactly THREE pre-registered changes, everything else identical:

  1. BANK_SEEDS = the v2.1 screen's pinned admission [1, 2, 3, 4, 6, 14, 17,
     28, 29, 33, 40, 56] (scenegen.v2_1_bank: S1-S5 unchanged + S6 predicted
     CLEAR floor 45 + S7 greedy pairwise diversity >= 1.1 m incl. gate seeds).
  2. G6c white n_clear floor 60 -> 40. Recalibration provenance
     (curation/p511_population.json): the old floor came from the single
     seed-1 probe (n_clear 80); the 12-cell recorded population of visually
     defect-free clips spans 23..119, so 60 rejected 7 valid cells. 40 keeps
     statistical teeth (p10 = 4th-lowest of >= 40; frac(<0.90) <= 0.02 allows
     0 bad frames below n=50) and is guaranteed by screen S6 (>= 45 predicted
     == recorded, byte-determinism verified 12/12 in P5.11).
  3. G8b blue-dominance floor 0.55 -> 0.40. Same provenance: the old floor
     came from the probe median 0.687; the recorded population of confirmed
     genuine occlusions spans 0.487..0.700, while the defect this gate exists
     to catch (wrong z-order: white drawn in front) drives the statistic
     toward ~0. 0.40 sits below the observed-correct minimum and far above
     the defect signature. G8a/G8c unchanged.

New cross-run gate G7 (screen pin): sg.v2_1_bank() re-run at verdict time
must reproduce BANK_SEEDS byte-for-byte -- if the generator or screen drifted
since pre-registration, the verdict refuses to pass.

All other gates byte-identical to P5.11: G0 completion (300 frames,
retries+lost <= 15), G1 render-alive, G2c occlusion-aware GT-on-vehicle,
G3 co-visibility >= 0.80, G5 >= 0.5 fps, G6c blue side (all frames, n >= 250,
p10 >= 0.95, frac(<0.90) <= 0.02), G4a determinism (seed101_A vs seed101_D),
G4b seed diversity (min pairwise whole-scenario divergence over the 15 seeds
>= 1.0 m + recorded-f0 faithfulness), G8a >= 25 occluded frames, G8c occluder
intact, G9 crossing-as-designed.

Overall YES iff:
  - all 4 gate runs pass G0,G1,G2c,G3,G5,G6c, and G4a, G4b, G7 pass, AND
  - >= 11 of 12 bank cells pass G0,G1,G2c,G3,G5,G6c,G8,G9, with any missing
    cell explicitly marked infra (runs/<cell>.INFRA), at most one, and no
    present-but-gate-failing cell.
The visual gate V (operator opens the named overlay PNGs) can only DOWNGRADE.
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
BANK_SEEDS = [1, 2, 3, 4, 6, 14, 17, 28, 29, 33, 40, 56]   # v2.1 screen pinned admission
BANK_RUNS = [(f"bank{i + 1:02d}", s) for i, s in enumerate(BANK_SEEDS)]
ALL_SEEDS = [101, 202, 303] + BANK_SEEDS
N_FRAMES = 300
PROMPT_F = 150
N_CLEAR_FLOOR = 40   # recalibrated (was 60) -- see module docstring
BDOM_FLOOR = 0.40    # recalibrated (was 0.55) -- see module docstring


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
    g6c = (len(wf) >= N_CLEAR_FLOOR and float(np.percentile(wf, 10)) >= 0.95
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
        g8b = len(doms) == len(occ_frames) > 0 and float(np.median(doms)) >= BDOM_FLOOR
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


def g7():
    admitted, _ = sg.v2_1_bank()
    ok = admitted == BANK_SEEDS
    return ok, (f"v2.1 screen admission {'reproduces' if ok else 'DIVERGES from'} "
                f"the pinned bank: {admitted}")


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
    print(f"G4b seed diversity (15 seeds, v2): {b_msg} -> {'PASS' if b_ok else 'FAIL'}")
    s_ok, s_msg = g7()
    print(f"G7 screen pin: {s_msg} -> {'PASS' if s_ok else 'FAIL'}")

    gate_complete = len(gate_rows) == len(GATE_RUNS)
    gate_pass = gate_complete and all(g["ok"] for g in gate_rows)
    bank_gate_fail = any(not g["ok"] for g in bank_rows)
    bank_infra = [m for m in missing if m[0].startswith("bank") and m[1] == "INFRA"]
    bank_missing = [m for m in missing if m[0].startswith("bank") and m[1] == "MISSING"]
    gate_missing = [m for m in missing if not m[0].startswith("bank")]
    bank_pass = (not bank_gate_fail and not bank_missing
                 and len(bank_rows) >= 11 and len(bank_infra) <= 1)

    if gate_missing or bank_missing or a_ok is None:
        print(f"RQ-P5.12 OVERALL: INCOMPLETE (missing: {missing})")
        sys.exit(2)
    verdict = "YES" if (gate_pass and a_ok and b_ok and s_ok and bank_pass) else "NO"
    why = []
    if not gate_pass:
        why.append("gate-run gates: " + ",".join(
            f"{g['run']}:{'/'.join(k for k in ('g0', 'g1', 'g2c', 'g3', 'g5', 'g6c') if not g[k])}"
            for g in gate_rows if not g["ok"]))
    if not a_ok:
        why.append("G4a")
    if not b_ok:
        why.append("G4b")
    if not s_ok:
        why.append("G7")
    if not bank_pass:
        why.append(f"bank ({sum(g['ok'] for g in bank_rows)}/12 pass, "
                   f"{len(bank_infra)} infra)")
    print(f"RQ-P5.12 OVERALL: {verdict}"
          + (f" [{'; '.join(why)}]" if why else "")
          + " (YES iff 4/4 gate runs pass G0,G1,G2c,G3,G5,G6c AND G4a AND G4b"
            " AND G7 AND >= 11/12 bank cells also pass G8,G9 with <= 1 infra"
            " loss and 0 gate failures; the visual gate V -- operator opens"
            " the named overlay PNGs, including every bank cell's"
            " crossing-peak overlay -- can only downgrade this to NO)")


def selfcheck():
    """Offline: grades the committed P5.11 probe_seed1 calibration clip as if
    it were a bank cell (must pass every gate its on-disk data allows, incl.
    the RECALIBRATED floors), then doctors copies to prove the negative paths
    fire -- including a new G6c-teeth negative under the lowered n_clear
    floor. No gz, no GPU."""
    import shutil
    import tempfile

    probe = HERE.parent / "2026-07-17-bankv2-crossing" / "curation" / "probe_seed1"
    assert (probe / "results.json").exists(), "P5.11 probe_seed1 fixture missing"
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
        assert g["n_clear"] >= N_CLEAR_FLOOR, g   # 80 >= 40
        if have_frames:
            assert g["g8"] and g["bdom"] is not None and g["bdom"] >= BDOM_FLOOR, g
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

        # negative 3 (NEW, proves the recalibrated G6c keeps teeth): doctor
        # white frag to 0.5 on 10 CLEAR frames -> frac(<0.90) = 10/80 = 0.125
        # > 0.02 and p10 < 0.95 -> G6c must fail even at the lowered floor.
        t4 = Path(td) / "neg3"
        d4 = t4 / "runs" / "bank01"
        d4.mkdir(parents=True)
        shutil.copy(probe / "results.json", d4 / "results.json")
        recs = [json.loads(l) for l in open(probe / "gt.jsonl")]
        doctored = 0
        for rec in recs:
            w = rec["objs"][0]
            if doctored < 10 and w["bbox"] is not None \
                    and w.get("occl", 0.0) <= 0.05 and "frag" in w:
                w["frag"] = 0.5
                doctored += 1
        assert doctored == 10
        (d4 / "gt.jsonl").write_text(
            "".join(json.dumps(rec) + "\n" for rec in recs))
        if have_frames:
            (d4 / "frames").symlink_to(probe / "frames")
        globals()["HERE"] = t4
        g4_ = grade_run("bank01", 1, is_bank=True)
        globals()["HERE"] = real_here
        assert g4_ is not None and not g4_["g6c"] and not g4_["ok"], \
            "fragmented clear frames must fail recalibrated G6c"
        print("--- selfcheck: doctored clear-frame frag fails G6c at floor 40")

    # screen pin must hold offline too
    s_ok, s_msg = g7()
    assert s_ok, s_msg
    print(f"--- selfcheck: {s_msg}")
    print("verdict_p512 selfcheck OK")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        main()
