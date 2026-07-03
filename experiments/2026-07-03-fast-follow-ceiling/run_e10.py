"""E10 fast-follow-ceiling run matrix. All design patches are already
committed (do NOT re-patch). 9 legs, a speed ladder at the full lever stack
with --vmax 4.0: reg-1.5 (regression guard), s2.0 x3 (primary RQ),
s2.5 x3, s3.0 x2 (ceiling probes). Snapshot-per-run (phase3_sitl clobbers
raw/phase3a-sitl/trial-<v>ms.{csv,mp4} + runs/phase3a-sitl/results.json every
run, the E2-E9 gotcha; NOTE the csv/mp4 name depends on --speed here).

Per-leg gate and the FAIL binding-mode classification are mechanical --
printed by this script, no deliberation. Abort rule: a leg is killed at 20 min
(INVALID, continue); the second INVALID stops the matrix (INVALID-RUN).

    .venv-ft/bin/python experiments/2026-07-03-fast-follow-ceiling/run_e10.py
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAMP = Path(__file__).resolve().parent
SRC = REPO / "experiments" / "2026-07-01-temporal-acquire-carry"
PY = REPO / ".venv-ft" / "bin" / "python"
LEG_TIMEOUT_S = 20 * 60

LEGS = [  # (label, speed) -- run in this order; reg-1.5 first (regression guard)
    ("reg-1.5", "1.5"),
    ("s2.0a", "2.0"), ("s2.0b", "2.0"), ("s2.0c", "2.0"),
    ("s2.5a", "2.5"), ("s2.5b", "2.5"), ("s2.5c", "2.5"),
    ("s3.0a", "3.0"), ("s3.0b", "3.0"),
]
COMMON = ["--vmax", "4.0", "--loss-gate", "motion", "--dr", "pursuit",
          "--acquire-hold", "motion"]


def classify_fail(trial: dict, csv_path: Path) -> str:
    """Mechanical binding-mode label for a FAIL leg (per README verdict rules).

    never-locked        first_lock_s is null (first-acquire binds)
    else: first >=1.0 s contiguous in_fov==0 run after first_lock ->
      state at run start: ACQUIRE -> first-acquire; REGROUND/RETARGET ->
      relock; CARRY -> tracking-trail.
    """
    if trial.get("first_lock_s") is None:
        return "never-locked (first-acquire)"
    if not csv_path.exists():
        return "no CSV -- classify by hand"
    t0 = trial["first_lock_s"]
    run_start, run_state = None, None
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            t = float(row["t_s"])
            if t < t0:
                continue
            if row["in_fov"] == "0":
                if run_start is None:
                    run_start, run_state = t, row["state"]
                elif t - run_start >= 1.0:
                    mode = {"ACQUIRE": "first-acquire",
                            "REGROUND": "relock", "RETARGET": "relock",
                            "CARRY": "tracking-trail"}.get(run_state, run_state)
                    return f"{mode} (out-of-FOV from t={run_start:.1f}s in {run_state})"
            else:
                run_start, run_state = None, None
    return "no >=1s out-of-FOV run found -- gate failed on recovered_after_occlusion?"


def run_leg(label: str, speed: str) -> str:
    """Run one leg, snapshot, print+return verdict: PASS / FAIL / INVALID."""
    print(f"=========== E10 {label}  --speed {speed} {' '.join(COMMON)} "
          f"===========", flush=True)
    try:
        subprocess.run([str(PY), str(SRC / "phase3_sitl.py"),
                        "--speed", speed, *COMMON],
                       cwd=REPO, timeout=LEG_TIMEOUT_S)
        timed_out = False
    except subprocess.TimeoutExpired:
        print(f"LEG TIMEOUT ({LEG_TIMEOUT_S}s) -- INVALID, snapshotting "
              f"whatever exists", flush=True)
        timed_out = True
    dst = CAMP / "runs" / label
    dst.mkdir(parents=True, exist_ok=True)
    for src, name in [(SRC / "runs/phase3a-sitl/results.json", "results.json"),
                      (SRC / f"raw/phase3a-sitl/trial-{speed}ms.csv", "trial.csv"),
                      (SRC / f"raw/phase3a-sitl/trial-{speed}ms.mp4", "trial.mp4")]:
        if src.exists():
            shutil.copy2(src, dst / name)
        else:
            print(f"MISSING: {src}", flush=True)
    if timed_out or not (dst / "results.json").exists():
        print(f"--- {label}: INVALID ---", flush=True)
        return "INVALID"
    trial = json.loads((dst / "results.json").read_text())["trial"]
    gate = trial["in_fov_frac"] >= 0.90 and trial["recovered_after_occlusion"]
    verdict = "PASS" if gate else "FAIL"
    line = (f"--- {label}: {verdict}  in_fov={trial['in_fov_frac']:.3f} "
            f"recovered={trial['recovered_after_occlusion']} "
            f"first_lock={trial['first_lock_s']}")
    if not gate:
        line += f"  binding-mode: {classify_fail(trial, dst / 'trial.csv')}"
    print(line + " ---", flush=True)
    return verdict


def main() -> None:
    verdicts: dict[str, str] = {}
    n_invalid = 0
    for label, speed in LEGS:
        verdicts[label] = run_leg(label, speed)
        if verdicts[label] == "INVALID":
            n_invalid += 1
            if n_invalid >= 2:
                print("=========== 2 INVALID LEGS -- STOPPING: INVALID-RUN "
                      "===========", flush=True)
                break
    print("=========== E10 MATRIX DONE ===========", flush=True)
    by_speed: dict[str, list[str]] = {}
    for (label, speed) in LEGS:
        if label in verdicts:
            by_speed.setdefault(speed, []).append(verdicts[label])
    for speed, vs in by_speed.items():
        print(f"  {speed} m/s: {vs.count('PASS')}/{len(vs)} PASS  {vs}", flush=True)
    reg_ok = verdicts.get("reg-1.5") == "PASS"
    s20 = [verdicts.get(f"s2.0{c}") for c in "abc"]
    rq = "YES" if reg_ok and s20.count("PASS") >= 2 else "NO"
    if not reg_ok:
        rq += " (RIG-REGRESSION: reg-1.5 failed -- 2.0+ results not comparable)"
    ceiling = "none measured"
    need = {"1.5": 1, "2.0": 2, "2.5": 2, "3.0": 2}
    for speed in ["1.5", "2.0", "2.5", "3.0"]:
        vs = by_speed.get(speed, [])
        if vs.count("PASS") >= need[speed]:
            ceiling = f"{speed} m/s"
    print(f"  RQ-E10: {rq}   measured ceiling: {ceiling}", flush=True)
    print("  (verdict rules: README 'Verdict rules' -- these lines ARE the "
          "mechanical application)", flush=True)
    sys.exit(0 if n_invalid < 2 else 1)


if __name__ == "__main__":
    main()
