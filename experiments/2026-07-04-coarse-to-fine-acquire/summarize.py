"""Summarize E21 c2f runs: per-clip table (with E20-cell + E18-A baselines), the
coarse-hint hit table (logged coarse cell vs GT cell at the submit frame), and the
latency table (coarse_s + total acquire_s vs E20's 1.57-2.07 s and E18's ~4.85 s).
Applies the FROZEN E21 verdict rules mechanically.

PASS = genuine_lock AND coverage >= 0.50; clip PASS = better of n=2 reps. Primary
arm = c2f. YES c2f>=4/6, PARTIAL 2-3/6, NO <=1/6. Suffix [prior-wrong] if the coarse
hint mismatches the GT submit cell on >=2 clips (either rep counts). Regression guard:
no clip's c2f coverage may fall >0.10 below its E18 A-leg best.

    .venv-ft/bin/python experiments/2026-07-04-coarse-to-fine-acquire/summarize.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E18_RUNS = REPO / "experiments" / "2026-07-03-real-video-replay" / "runs"
E20_RUNS = REPO / "experiments" / "2026-07-04-prompt-scoped-acquire" / "runs"
CLIPS = ["car3", "car7", "car9", "car10", "car14", "car18"]

# E18 A-leg best coverage per clip (from HANDOFF / E18 README), for the regression guard
E18_A_COV = {"car3": 0.976, "car7": 0.285, "car9": 0.993,
             "car10": 1.000, "car14": 0.903, "car18": 0.711}


def load(p):
    d = json.load(open(p))
    return d["score"], d


def is_pass(s):
    return bool(s["genuine_lock"]) and s["coverage"] >= 0.50


def acq0(d):
    """First ACQUIRE mc_log entry of a run (the coarse-to-fine acquire)."""
    return next((e for e in d.get("mc_log", []) if e.get("state") == "ACQUIRE"), None)


def best_of(clip, arm_key, runs_dir):
    """Better of n=2 reps (PASS-first, then coverage). Returns (pas, s, d)|None."""
    best = None
    for rep in (1, 2):
        p = runs_dir / f"{arm_key}_{clip}_r{rep}" / "results.json"
        if not p.exists():
            continue
        s, d = load(p)
        pas = is_pass(s)
        if best is None or (pas and not best[0]) or (pas == best[0] and s["coverage"] > best[1]["coverage"]):
            best = (pas, s, d)
    return best


def main():
    print("===== C2F PER-CLIP (PASS = genuine_lock AND cov>=0.50; best of n=2) =====")
    n_pass = 0
    c2f_rows = {}
    all_coarse_s, all_acq_s = [], []
    for clip in CLIPS:
        for rep in (1, 2):
            p = HERE / "runs" / f"c2f_{clip}_r{rep}" / "results.json"
            if not p.exists():
                print(f"{clip:6} r{rep} MISSING")
                continue
            s, d = load(p)
            e = acq0(d)
            cs = e.get("coarse_s") if e else None
            as_ = e.get("acquire_s") if e else None
            if cs is not None:
                all_coarse_s.append(cs)
            if as_ is not None:
                all_acq_s.append(as_)
            print(f"{clip:6} r{rep} t_lock={str(s['t_lock']):>5} "
                  f"gen={str(s['genuine_lock']):5} cov={s['coverage']:.3f} "
                  f"iou={s['mean_iou']:.3f} rej={d['n_gate_reject']} "
                  f"coarse_hint={str(e['coarse_hint']) if e else None} "
                  f"gt_hint={d.get('gt_hint')} coarse_s={cs} acquire_s={as_} "
                  f"{'PASS' if is_pass(s) else 'FAIL'}")
        b = best_of(clip, "c2f", HERE / "runs")
        c2f_rows[clip] = b
        if b and b[0]:
            n_pass += 1
    print(f"  c2f clip PASS = {n_pass}/6")

    # coarse-hint hit table (logged coarse cell vs GT cell at submit frame, either rep)
    print("\n===== COARSE-HINT HIT (logged coarse cell vs GT submit-frame cell) =====")
    n_wrong_clips = 0
    for clip in CLIPS:
        reps = []
        for rep in (1, 2):
            p = HERE / "runs" / f"c2f_{clip}_r{rep}" / "results.json"
            if not p.exists():
                continue
            _, d = load(p)
            e = acq0(d)
            ch = e.get("coarse_hint") if e else None
            gh = d.get("gt_hint")
            reps.append((rep, ch, gh, ch == gh))
        any_wrong = any(not ok for _, _, _, ok in reps)
        if any_wrong:
            n_wrong_clips += 1
        for rep, ch, gh, ok in reps:
            print(f"{clip:6} r{rep} coarse={str(ch):>14} gt={str(gh):>14} "
                  f"{'HIT' if ok else 'MISS'}")
    hits = 0
    total = 0
    for clip in CLIPS:
        for rep in (1, 2):
            p = HERE / "runs" / f"c2f_{clip}_r{rep}" / "results.json"
            if not p.exists():
                continue
            _, d = load(p)
            e = acq0(d)
            if e is None:
                continue
            total += 1
            if e.get("coarse_hint") == d.get("gt_hint"):
                hits += 1
    print(f"  coarse-hint hit rate = {hits}/{total} reps; "
          f"clips with >=1 wrong rep = {n_wrong_clips}/6")

    # latency
    print("\n===== LATENCY =====")
    if all_coarse_s:
        print(f"  coarse_s: mean={sum(all_coarse_s)/len(all_coarse_s):.2f} "
              f"min={min(all_coarse_s)} max={max(all_coarse_s)} (n={len(all_coarse_s)})")
    if all_acq_s:
        print(f"  total acquire_s: mean={sum(all_acq_s)/len(all_acq_s):.2f} "
              f"min={min(all_acq_s)} max={max(all_acq_s)} (n={len(all_acq_s)}) "
              f"| E20 cell 1.57-2.07, E18 full-frame ~4.85")

    # regression guard vs E18 A-leg coverage
    print("\n===== REGRESSION GUARD (c2f cov vs E18 A best) =====")
    breach = False
    for clip in CLIPS:
        b = c2f_rows.get(clip)
        if b is None:
            print(f"{clip:6} MISSING")
            continue
        cov, ecov = b[1]["coverage"], E18_A_COV[clip]
        flag = "BREACH" if cov < ecov - 0.10 else "ok"
        if flag == "BREACH":
            breach = True
        print(f"{clip:6} c2f_cov={cov:.3f} E18A_cov={ecov:.3f} d={cov-ecov:+.3f} {flag}")

    # verdict
    print("\n===== VERDICT =====")
    verdict = "YES" if n_pass >= 4 else ("PARTIAL" if n_pass >= 2 else "NO")
    if breach:
        verdict += " (REGRESSIVE)"
    if n_wrong_clips >= 2:
        verdict += " [prior-wrong]"
    print(f"c2f PASS = {n_pass}/6 -> RQ-E21 {verdict}")
    if all_acq_s:
        print(f"mean coarse_s = {sum(all_coarse_s)/len(all_coarse_s):.2f} s, "
              f"mean total acquire_s = {sum(all_acq_s)/len(all_acq_s):.2f} s")


if __name__ == "__main__":
    main()
