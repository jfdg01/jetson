"""Summarize E23 tol runs into a per-clip table, apply the frozen verdict rules, and
report mean acquire_s vs E20 (1.85 s) / E18 (4.85 s).

PASS = genuine_lock AND coverage >= 0.50; clip PASS = better of n=2 reps. The frozen
verdict is about PRESERVING E20's PASS set {car9, car10, car14} under a FUZZED hint at
HW*, not beating it (E20's residual fails car3/car7/car18 are target-size bound):
  YES     = tol PASS set SUPERSET of {car9,car10,car14} AND mean acquire_s < 3.0 s.
  PARTIAL = preserves >=2 of the three but drops one, OR mean acquire_s in [3.0,4.0).
  NO      = drops >=2 of the three, OR mean acquire_s >= 4.0 s.
Suffix [already-tolerant] if Phase-0 found E20's HW already 6/6 (it did NOT: 2/6).
Regression guard: no clip's tol coverage may fall > 0.10 below its E18 A-leg best.

    .venv-ft/bin/python experiments/2026-07-04-tolerant-cells/summarize.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
E18_RUNS = HERE.parents[0] / "2026-07-03-real-video-replay" / "runs"
CLIPS = ["car3", "car7", "car9", "car10", "car14", "car18"]
E20_PASS = {"car9", "car10", "car14"}
# E18 A-leg best coverage per clip (frozen from E18/E20 records, regression floor)
E18_A_COV = {"car3": 0.976, "car7": 0.285, "car9": 0.993, "car10": 1.000,
             "car14": 0.903, "car18": 0.711}


def load(p):
    d = json.load(open(p))
    return d["score"], d


def is_pass(s):
    return bool(s["genuine_lock"]) and s["coverage"] >= 0.50


def acq_of(d):
    return [e["acquire_s"] for e in d.get("mc_log", [])
            if e.get("state") == "ACQUIRE" and e.get("scoped")]


def main():
    print("===== E23 tol arm (HW*=0.38, worst-case fuzzed hints) =====")
    n_pass = 0
    rows, all_acq = {}, []
    passset = set()
    for clip in CLIPS:
        best = None
        for rep in (1, 2):
            p = HERE / "runs" / f"tol_{clip}_r{rep}" / "results.json"
            if not p.exists():
                continue
            s, d = load(p)
            pas = is_pass(s)
            acq = acq_of(d)
            all_acq += acq
            print(f"{clip:6} r{rep} true={d.get('true_hint'):>13} "
                  f"fuzzed={d.get('fuzzed_hint'):>13} t_lock={str(s['t_lock']):>5} "
                  f"gen={str(s['genuine_lock']):5} cov={s['coverage']:.3f} "
                  f"iou={s['mean_iou']:.3f} rej={d['n_gate_reject']} acq={acq} "
                  f"{'PASS' if pas else 'FAIL'}")
            if best is None or (pas and not best[0]) or (pas == best[0] and s["coverage"] > best[1]["coverage"]):
                best = (pas, s, d)
        rows[clip] = best
        if best and best[0]:
            n_pass += 1
            passset.add(clip)
    print(f"  tol clip PASS = {n_pass}/6, PASS set = {sorted(passset)}")

    mean_acq = sum(all_acq) / len(all_acq) if all_acq else float("nan")
    if all_acq:
        print(f"  mean scoped acquire_s = {mean_acq:.2f} (n={len(all_acq)}, "
              f"min={min(all_acq)} max={max(all_acq)}) vs E20 1.85 / E18 4.85")

    # regression guard vs E18 A-leg coverage
    print("\n===== REGRESSION GUARD (tol cov vs E18 A best) =====")
    breach = False
    for clip in CLIPS:
        b = rows.get(clip)
        if b is None:
            print(f"{clip:6} MISSING"); continue
        cov, ecov = b[1]["coverage"], E18_A_COV[clip]
        flag = "BREACH" if cov < ecov - 0.10 else "ok"
        if flag == "BREACH":
            breach = True
        print(f"{clip:6} tol_cov={cov:.3f} E18A_cov={ecov:.3f} d={cov-ecov:+.3f} {flag}")

    # verdict (frozen rules; [already-tolerant] N/A since Phase-0 E20 HW = 2/6)
    print("\n===== VERDICT (frozen rules) =====")
    superset = E20_PASS <= passset
    kept = len(E20_PASS & passset)
    if superset and mean_acq < 3.0:
        verdict = "YES"
    elif kept >= 2 or (3.0 <= mean_acq < 4.0):
        verdict = "PARTIAL"
    else:
        verdict = "NO"
    if breach:
        verdict += " (REGRESSIVE)"
    print(f"E20 PASS set {sorted(E20_PASS)} preserved: kept {kept}/3, "
          f"superset={superset}; mean_acq={mean_acq:.2f}")
    print(f"tol PASS = {n_pass}/6, PASS set {sorted(passset)} -> RQ-E23 {verdict}")
    print("(Phase-0: E20 HW=0.2667 worst-case containment 2/6 -> NOT [already-tolerant])")


if __name__ == "__main__":
    main()
