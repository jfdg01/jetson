"""Summarize E20 runs into a per-clip table + PASS rollup per arm, apply the frozen
verdict rules, and report scoped acquire_s vs E18's ~4.85 s baseline.

PASS = genuine_lock AND coverage >= 0.50; clip PASS = better of n=2 reps. Primary
arm = cell. YES cell>=4/6, PARTIAL 2-3/6, NO <=1/6. Regression guard: no cell clip's
coverage may fall >0.10 below its E18 A-leg best. [hint-fragile] if the wrong probe
produces an accepted wrong-cell lock (cov<0.25 on either rep).

    .venv-ft/bin/python experiments/2026-07-04-prompt-scoped-acquire/summarize.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
E18_RUNS = HERE.parents[0] / "2026-07-03-real-video-replay" / "runs"
CLIPS = ["car3", "car7", "car9", "car10", "car14", "car18"]


def load(p):
    d = json.load(open(p))
    return d["score"], d


def is_pass(s):
    return bool(s["genuine_lock"]) and s["coverage"] >= 0.50


def acq_of(d):
    """Scoped ACQUIRE acquire_s values in a run (usually one)."""
    return [e["acquire_s"] for e in d.get("mc_log", [])
            if e.get("state") == "ACQUIRE" and e.get("scoped")]


def e18_a_best(clip):
    """Best (by coverage among PASS-first) E18 A-leg reps for the clip."""
    best = None
    for rep in (1, 2):
        p = E18_RUNS / f"A_{clip}_r{rep}" / "results.json"
        if not p.exists():
            continue
        s, _ = load(p)
        pas = is_pass(s)
        if best is None or (pas and not best[0]) or (pas == best[0] and s["coverage"] > best[1]["coverage"]):
            best = (pas, s)
    return best[1] if best else None


def arm(name, arm_key):
    print(f"\n===== {name} =====")
    n_pass = 0
    rows = {}
    all_acq = []
    for clip in CLIPS:
        best = None
        for rep in (1, 2):
            p = HERE / "runs" / f"{arm_key}_{clip}_r{rep}" / "results.json"
            if not p.exists():
                continue
            s, d = load(p)
            pas = is_pass(s)
            acq = acq_of(d)
            all_acq += acq
            print(f"{clip:6} r{rep} t_lock={str(s['t_lock']):>5} "
                  f"gen={str(s['genuine_lock']):5} cov={s['coverage']:.3f} "
                  f"iou={s['mean_iou']:.3f} rej={d['n_gate_reject']} acq={acq} "
                  f"{'PASS' if pas else 'FAIL'}")
            if best is None or (pas and not best[0]) or (pas == best[0] and s["coverage"] > best[1]["coverage"]):
                best = (pas, s)
        rows[clip] = best
        if best and best[0]:
            n_pass += 1
    print(f"  {name} clip PASS = {n_pass}/6")
    if all_acq:
        print(f"  {name} mean scoped acquire_s = {sum(all_acq)/len(all_acq):.2f} "
              f"(n={len(all_acq)}, min={min(all_acq)} max={max(all_acq)})")
    return n_pass, rows, all_acq


def main():
    cell_pass, cell_rows, cell_acq = arm("CELL", "cell")
    cellbuf_pass, _, _ = arm("CELLBUF", "cellbuf")

    # regression guard vs E18 A-leg coverage
    print("\n===== REGRESSION GUARD (cell cov vs E18 A best) =====")
    breach = False
    for clip in CLIPS:
        b = cell_rows.get(clip)
        e = e18_a_best(clip)
        if b is None or e is None:
            print(f"{clip:6} MISSING"); continue
        cov, ecov = b[1]["coverage"], e["coverage"]
        flag = "BREACH" if cov < ecov - 0.10 else "ok"
        if flag == "BREACH":
            breach = True
        print(f"{clip:6} cell_cov={cov:.3f} E18A_cov={ecov:.3f} d={cov-ecov:+.3f} {flag}")

    # wrong probe
    print("\n===== WRONG PROBE (car10, 'top left') =====")
    wrong_fragile = False
    for rep in (1, 2):
        p = HERE / "runs" / f"wrong_car10_r{rep}" / "results.json"
        if not p.exists():
            print(f"r{rep} MISSING"); continue
        s, d = load(p)
        cov = s["coverage"]
        accepted = bool(d.get("mc_log")) and any(e.get("gate") == "accept" for e in d["mc_log"])
        frag = accepted and cov < 0.25
        if frag:
            wrong_fragile = True
        print(f"r{rep} gen={s['genuine_lock']} cov={cov:.3f} accepted_lock={accepted} "
              f"acq={acq_of(d)} {'HINT-FRAGILE' if frag else ''}")

    # verdict
    print("\n===== VERDICT =====")
    verdict = "YES" if cell_pass >= 4 else ("PARTIAL" if cell_pass >= 2 else "NO")
    if breach:
        verdict += " (REGRESSIVE)"
    if wrong_fragile:
        verdict += " [hint-fragile]"
    print(f"cell PASS = {cell_pass}/6, cellbuf PASS = {cellbuf_pass}/6 -> RQ-E20 {verdict}")
    if cell_acq:
        print(f"mean scoped acquire_s (cell) = {sum(cell_acq)/len(cell_acq):.2f} s "
              f"vs E18 full-frame ~4.85 s")


if __name__ == "__main__":
    main()
