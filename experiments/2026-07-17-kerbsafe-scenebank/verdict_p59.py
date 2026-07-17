#!/usr/bin/env python
"""P5.9 mechanical verdict: kerb-safe generator gate re-run + 12-clip scene bank.

Reads experiments/2026-07-17-kerbsafe-scenebank/runs/* and prints the full gate
table + overall verdict. No thresholds live anywhere else; Opus does not
deliberate. The visual gate V is done by the operator on the overlay PNGs and
can only DOWNGRADE the printed verdict.

Gates (per run unless noted; G1/G2/G3/G5 byte-for-byte from P5.7/P5.8):
  G0  completion: results.json present, 240 gt.jsonl lines, retries+lost <= 12
  G1  render-alive: 0 dead frames, 0 identical consecutive, stamps exact
  G2  GT-on-vehicle: median purity >= 0.30 per car AND >= 4x lateral control
  G3  co-visibility: both cars bbox area >= 150 px in >= 80% of frames
  G5  throughput: >= 0.5 generated frames/s wall
  G6  rendered integrity (NEW, calibrated on P5.8 data -- clean runs p10 >=
      0.996 / below-0.90 frac 0.0; the P5.8 kerb-clipped car p10 0.666 /
      frac 0.312): per car, frag p10 >= 0.95 AND frac(frag < 0.90) <= 0.02
      AND >= 200 scored frames
  G4a determinism (gate pair seed101_A vs seed101_D): canonical GT (sim-stamps
      excluded) byte-identical AND frames mean|diff| <= 2.0, frac(>8) <= 1%
  G4b seed diversity (REDEFINED this campaign -- see README ruling): min
      pairwise whole-scenario divergence over the 15 pre-registered seeds
      (mean over 240 frames of mean(|d target|, |d distractor|, |d cam|))
      >= 1.0 m, computed from author_scenario; PLUS recorded gt.jsonl frame-0
      positions of every completed run must reproduce author_scenario within
      1e-3 m (ties the offline number to what actually ran).

Overall YES iff:
  - all 4 gate runs pass G0,G1,G2,G3,G5,G6, and G4a and G4b pass, AND
  - >= 11 of 12 bank cells pass G0,G1,G2,G3,G5,G6, with any missing cell
    explicitly marked infra (runs/<cell>.INFRA file, per the partial-run rule)
    -- a present-but-gate-failing bank cell is a NO, only an infra-lost cell
    may be excused, and at most one.
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
BANK_RUNS = [(f"bank{i:02d}", i) for i in range(1, 13)]
ALL_SEEDS = [101, 202, 303] + list(range(1, 13))
N_FRAMES = 240


def grade_run(run, seed):
    d = HERE / "runs" / run
    rj = d / "results.json"
    if not rj.exists():
        return None
    r = json.load(open(rj))
    n_gt = sum(1 for _ in open(d / "gt.jsonl"))
    g0 = (n_gt == N_FRAMES and
          r["g0_retries_pose"] + r["g0_retries_step"] + r["g0_response_lost"] <= 12)
    g1 = (r["g1_dead_frames"] == 0 and r["g1_identical_consecutive"] == 0
          and r["g1_stamp_steps_ok"])
    g2 = all(r["g2_purity_median"][k] is not None
             and r["g2_purity_median"][k] >= 0.30
             and r["g2_purity_median"][k] >= 4 * (r["g2_bg_purity_median"][k] or 0.0)
             for k in ("0", "1"))
    g3 = r["g3_both_visible_frac"] >= 0.80
    g5 = r["fps_wall"] >= 0.5
    g6 = all(r["g6_frag_p10"][k] is not None
             and r["g6_frag_p10"][k] >= 0.95
             and r["g6_frag_below090_frac"][k] <= 0.02
             and r["g6_frag_n"][k] >= 200
             for k in ("0", "1"))
    return {"run": run, "seed": seed, "g0": g0, "g1": g1, "g2": g2, "g3": g3,
            "g5": g5, "g6": g6, "fps": r["fps_wall"],
            "pur": (r["g2_purity_median"]["0"], r["g2_purity_median"]["1"]),
            "frag_p10": (r["g6_frag_p10"]["0"], r["g6_frag_p10"]["1"]),
            "bothvis": r["g3_both_visible_frac"],
            "retries": r["g0_retries_pose"] + r["g0_retries_step"],
            "lost": r["g0_response_lost"], "restarts": r["g0_proxy_restarts"],
            "ok": g0 and g1 and g2 and g3 and g5 and g6}


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
    return ok, f"gt_identical={ident} frame_mean_absdiff={round(mean_abs, 4)} (<= 2.0) frac_gt8={round(frac8, 5)} (<= 0.01)"


def g4b():
    scs = {s: sg.author_scenario(s, N_FRAMES) for s in ALL_SEEDS}

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
    # faithfulness cross-check: recorded f0 must reproduce the authored scenario
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
    return ok, (f"min pairwise scenario divergence {dmin:.2f} m (>= 1.0) at pair {argmin}; "
                f"recorded-f0 faithful={faithful} over {checked} runs")


def main():
    hdr = (f"{'run':12s} {'seed':4s} G0 G1 G2 G3 G5 G6  fps    pur0   pur1   "
           f"fragp10        bothvis retries lost restarts")
    print(hdr)
    gate_rows, bank_rows, missing = [], [], []
    for run, seed in GATE_RUNS + BANK_RUNS:
        g = grade_run(run, seed)
        is_bank = run.startswith("bank")
        if g is None:
            infra = (HERE / "runs" / f"{run}.INFRA").exists()
            missing.append((run, "INFRA" if infra else "MISSING"))
            print(f"{run:12s} {seed:<4d} {'-- INFRA --' if infra else '-- MISSING results.json --'}")
            continue
        (bank_rows if is_bank else gate_rows).append(g)
        print(f"{g['run']:12s} {g['seed']:<4d} {int(g['g0'])}  {int(g['g1'])}  {int(g['g2'])}  "
              f"{int(g['g3'])}  {int(g['g5'])}  {int(g['g6'])}  {g['fps']:<6.2f} "
              f"{g['pur'][0]:<6.3f} {g['pur'][1]:<6.3f} "
              f"{g['frag_p10'][0]:.3f}/{g['frag_p10'][1]:.3f}  {g['bothvis']:<7.3f} "
              f"{g['retries']:<7d} {g['lost']:<4d} {g['restarts']}")

    a_ok, a_msg = g4a()
    print(f"G4a determinism seed101_A vs seed101_D: {a_msg} -> "
          f"{'PASS' if a_ok else 'FAIL' if a_ok is not None else 'INCOMPLETE'}")
    b_ok, b_msg = g4b()
    print(f"G4b seed diversity (redefined, 15 seeds): {b_msg} -> {'PASS' if b_ok else 'FAIL'}")

    gate_complete = len(gate_rows) == len(GATE_RUNS)
    gate_pass = gate_complete and all(g["ok"] for g in gate_rows)
    bank_gate_fail = any(not g["ok"] for g in bank_rows)
    bank_infra = [m for m in missing if m[0].startswith("bank") and m[1] == "INFRA"]
    bank_missing = [m for m in missing if m[0].startswith("bank") and m[1] == "MISSING"]
    gate_missing = [m for m in missing if not m[0].startswith("bank")]
    bank_pass = (not bank_gate_fail and not bank_missing
                 and len(bank_rows) >= 11 and len(bank_infra) <= 1)

    if gate_missing or bank_missing or a_ok is None:
        print(f"RQ-P5.9 OVERALL: INCOMPLETE (missing: {missing})")
        sys.exit(2)
    verdict = "YES" if (gate_pass and a_ok and b_ok and bank_pass) else "NO"
    why = []
    if not gate_pass:
        why.append("gate-run gates: " + ",".join(
            f"{g['run']}:{'/'.join(k for k in ('g0','g1','g2','g3','g5','g6') if not g[k])}"
            for g in gate_rows if not g["ok"]))
    if not a_ok:
        why.append("G4a")
    if not b_ok:
        why.append("G4b")
    if not bank_pass:
        why.append(f"bank ({sum(g['ok'] for g in bank_rows)}/12 pass, "
                   f"{len(bank_infra)} infra)")
    print(f"RQ-P5.9 OVERALL: {verdict}"
          + (f" [{'; '.join(why)}]" if why else "")
          + " (YES iff 4/4 gate runs pass G0,G1,G2,G3,G5,G6 AND G4a AND G4b AND"
            " >= 11/12 bank cells pass with <= 1 infra loss and 0 gate failures;"
            " the visual gate V is checked by the operator on the overlay PNGs"
            " and can only downgrade this to NO)")


if __name__ == "__main__":
    main()
