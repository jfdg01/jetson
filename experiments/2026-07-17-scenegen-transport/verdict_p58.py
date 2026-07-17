#!/usr/bin/env python3
"""Mechanical verdict for P5.8 (scene-generator transport fix + capability gate).

Reads runs/{seed101_A,seed202_B,seed303_C,seed101_D}/ produced by
runners/scenegen.py (persistent-proxy transport) and prints the gate table +
overall verdict. No judgment calls live here -- thresholds are the
pre-registered ones from the README. G1-G5 thresholds are IDENTICAL to P5.7
(the capability claim is unchanged); G0 is new (run completion + bounded
retries, the gate P5.7 actually failed).

Usage: .venv-ft/bin/python experiments/2026-07-17-scenegen-transport/verdict_p58.py
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
GATING = ["seed101_A", "seed202_B", "seed303_C", "seed101_D"]
DET_PAIR = ("seed101_A", "seed101_D")
SEEDS_DIFFER = ("seed101_A", "seed202_B", "seed303_C")

# pre-registered thresholds (G1-G5 identical to P5.7)
FRAMES_REQUIRED = 240
G0_RETRIES_MAX = 12  # failed-then-recovered service calls per run (~2.5% of ~480)
PURITY_MIN = 0.30
BG_PURITY_RATIO = 4.0  # in-box purity must beat lateral control boxes by >= 4x
BOTH_VIS_MIN = 0.80
FPS_MIN = 0.5
FRAME_DIFF_MEAN_MAX = 2.0
FRAME_DIFF_FRAC8_MAX = 0.01
SEED_POS_DIFF_MIN = 1.0


def load(run):
    d = RUNS / run
    res = json.loads((d / "results.json").read_text())
    gt = [json.loads(line) for line in (d / "gt.jsonl").read_text().splitlines()]
    return res, gt


def canonical_gt(gt):
    out = []
    for r in gt:
        r = dict(r)
        r.pop("t_sim_ns", None)  # sim clock differs across server sessions by design
        out.append(r)
    return json.dumps(out, sort_keys=True)


def frame_diff(run_a, run_b, n):
    import cv2
    means, frac8 = [], []
    for i in range(n):
        a = cv2.imread(str(RUNS / run_a / "frames" / f"{i:04d}.png"))
        b = cv2.imread(str(RUNS / run_b / "frames" / f"{i:04d}.png"))
        if a is None or b is None:
            return None, None
        d = np.abs(a.astype(int) - b.astype(int))
        means.append(d.mean())
        frac8.append((d > 8).mean())
    return float(np.mean(means)), float(np.mean(frac8))


def main():
    missing = [r for r in GATING if not (RUNS / r / "results.json").exists()]
    if missing:
        print(f"INCOMPLETE: missing runs {missing} -- verdict not final")
        sys.exit(2)

    rows = []
    all_ok = True
    data = {r: load(r) for r in GATING}
    for r in GATING:
        res, gt = data[r]
        retries = res["g0_retries_pose"] + res["g0_retries_step"]
        g0 = (res["frames"] == FRAMES_REQUIRED and len(gt) == FRAMES_REQUIRED
              and retries <= G0_RETRIES_MAX)
        g1 = (res["g1_dead_frames"] == 0 and res["g1_identical_consecutive"] == 0
              and res["g1_stamp_steps_ok"])
        p = res["g2_purity_median"]
        bg = res["g2_bg_purity_median"]
        g2 = all(p[k] is not None and p[k] >= PURITY_MIN for k in ("0", "1")) and \
            all(bg[k] is not None and p[k] >= BG_PURITY_RATIO * bg[k]
                for k in ("0", "1"))
        g3 = res["g3_both_visible_frac"] >= BOTH_VIS_MIN
        g5 = res["fps_wall"] >= FPS_MIN
        ok = g0 and g1 and g2 and g3 and g5
        all_ok &= ok
        rows.append((r, res["seed"], g0, g1, g2, g3, g5, res["fps_wall"],
                     p["0"], p["1"], res["g3_both_visible_frac"], retries,
                     res["g0_response_lost"], res["g0_proxy_restarts"],
                     res.get("g0_spawn_warns", [])))

    # G4a: same-seed cross-session determinism
    a, b = DET_PAIR
    gt_same = canonical_gt(data[a][1]) == canonical_gt(data[b][1])
    n = data[a][0]["frames"]
    dmean, dfrac8 = frame_diff(a, b, n)
    g4a = gt_same and dmean is not None and dmean <= FRAME_DIFF_MEAN_MAX \
        and dfrac8 <= FRAME_DIFF_FRAC8_MAX
    # G4b: different seeds actually differ
    f0pos = {}
    for r in SEEDS_DIFFER:
        f0pos[r] = np.array(data[r][1][0]["objs"][0]["pos"])
    diffs = [np.linalg.norm(f0pos[x] - f0pos[y])
             for x in SEEDS_DIFFER for y in SEEDS_DIFFER if x < y]
    g4b = all(d > SEED_POS_DIFF_MIN for d in diffs)
    all_ok &= g4a and g4b

    print(f"{'run':<12} {'seed':<5} G0 G1 G2 G3 G5  fps    pur0   pur1   "
          f"bothvis retries lost restarts")
    for (r, s, g0, g1, g2, g3, g5, fps, p0, p1, bv, rt, lost, rst, warns) in rows:
        print(f"{r:<12} {s:<5} {int(g0)}  {int(g1)}  {int(g2)}  {int(g3)}  {int(g5)}  "
              f"{fps:<6.2f} {p0:<6.3f} {p1:<6.3f} {bv:<7.3f} {rt:<7d} {lost:<4d} {rst}")
        if warns:
            print(f"  spawn warns: {warns}")
    print(f"G4a determinism {a} vs {b}: gt_identical={gt_same} "
          f"frame_mean_absdiff={dmean if dmean is None else round(dmean, 3)} "
          f"(<= {FRAME_DIFF_MEAN_MAX}) frac_gt8={dfrac8 if dfrac8 is None else round(dfrac8, 5)} "
          f"(<= {FRAME_DIFF_FRAC8_MAX}) -> {'PASS' if g4a else 'FAIL'}")
    print(f"G4b seeds differ (f0 target pos, min pairwise dist "
          f"{round(min(diffs), 2)} m > {SEED_POS_DIFF_MIN}): {'PASS' if g4b else 'FAIL'}")
    print(f"RQ-P5.8 OVERALL: {'YES' if all_ok else 'NO'} "
          "(YES iff G0,G1,G2,G3,G5 on all 4 runs AND G4a AND G4b; "
          "visual gate V is checked by the operator on the overlay PNGs, "
          "and can only downgrade this to NO)")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
