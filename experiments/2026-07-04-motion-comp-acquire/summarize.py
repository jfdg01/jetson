"""Summarize E19 runs into a per-clip table + PASS rollup per arm.

PASS = genuine_lock AND coverage >= 0.50; clip PASS = better of n=2 reps.
Compares against E18's A legs (baseline) and B legs (ceiling).

    .venv-ft/bin/python experiments/2026-07-04-motion-comp-acquire/summarize.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
E18_RUNS = HERE.parents[0] / "2026-07-03-real-video-replay" / "runs"
CLIPS = ["car3", "car9", "car14", "car18", "car7", "car10"]


def load(p):
    d = json.load(open(p))
    s = d["score"]
    return s, d


def is_pass(s):
    return bool(s["genuine_lock"]) and s["coverage"] >= 0.50


def mc_detail(d):
    log = d.get("mc_log", [])
    if not log:
        return "-"
    parts = []
    for e in log:
        if d["mc"] == "flow":
            parts.append(f"{e['state'][:3]} ncc={e['ncc']:.2f} app={e['applied']} {e['gate']}")
        elif d["mc"] == "buf":
            if "catchup_frames" in e:
                parts.append(f"{e['state'][:3]} bl={e.get('backlog0','?')} "
                             f"cf={e['catchup_frames']} cs={e.get('catchup_s','?')}s gap={e.get('final_gap','?')}")
            else:
                parts.append(f"{e['state'][:3]} {e['gate']}")
    return " | ".join(parts)


def main():
    for mc in ("flow", "buf"):
        print(f"\n===== {mc.upper()} =====")
        n_pass = 0
        for clip in CLIPS:
            best = None
            for rep in (1, 2):
                p = HERE / "runs" / f"{mc}_{clip}_r{rep}" / "results.json"
                if not p.exists():
                    continue
                s, d = load(p)
                pas = is_pass(s)
                print(f"{clip:6} r{rep} t_lock={str(s['t_lock']):>5} "
                      f"gen={str(s['genuine_lock']):5} cov={s['coverage']:.3f} "
                      f"iou={s['mean_iou']:.3f} rej={d['n_gate_reject']} "
                      f"{'PASS' if pas else 'FAIL'} | {mc_detail(d)}")
                if best is None or (pas and not best[0]) or (pas == best[0] and s['coverage'] > best[1]['coverage']):
                    best = (pas, s)
            if best and best[0]:
                n_pass += 1
        print(f"  {mc} clip PASS = {n_pass}/6")


if __name__ == "__main__":
    main()
