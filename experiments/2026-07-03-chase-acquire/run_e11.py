"""E11 chase-acquire run matrix. All design patches are already committed
(do NOT re-patch). 6 legs, the full lever stack with --acquire-hold chase:
reg-2.5 (regression guard at the E10 ceiling), s3.0 x3 (primary RQ),
s3.5 x2 (stretch, --vmax 5.0). Snapshot-per-run (phase3_sitl clobbers
raw/phase3a-sitl/trial-<v>ms.{csv,mp4} + runs/phase3a-sitl/results.json every
run, the E2-E10 gotcha; the csv/mp4 name depends on --speed).

Per-leg gate and the FAIL binding-mode classification are mechanical --
printed by this script, no deliberation. Abort rule: a leg is killed at 20 min
(INVALID, continue); the second INVALID stops the matrix (INVALID-RUN).

    .venv-ft/bin/python experiments/2026-07-03-chase-acquire/run_e11.py
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

LEGS = [  # (label, speed, vmax) -- run in this order; reg-2.5 first
    ("reg-2.5", "2.5", "4.0"),
    ("s3.0a", "3.0", "4.0"), ("s3.0b", "3.0", "4.0"), ("s3.0c", "3.0", "4.0"),
    ("s3.5a", "3.5", "5.0"), ("s3.5b", "3.5", "5.0"),
]
COMMON = ["--loss-gate", "motion", "--dr", "pursuit",
          "--acquire-hold", "chase"]


def classify_fail(trial: dict, csv_path: Path) -> str:
    """Mechanical binding-mode label for a FAIL leg (verbatim from run_e10.py).

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


def run_leg(label: str, speed: str, vmax: str) -> str:
    """Run one leg, snapshot, print+return verdict: PASS / FAIL / INVALID."""
    print(f"=========== E11 {label}  --speed {speed} --vmax {vmax} "
          f"{' '.join(COMMON)} ===========", flush=True)
    try:
        subprocess.run([str(PY), str(SRC / "phase3_sitl.py"),
                        "--speed", speed, "--vmax", vmax, *COMMON],
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
    for label, speed, vmax in LEGS:
        verdicts[label] = run_leg(label, speed, vmax)
        if verdicts[label] == "INVALID":
            n_invalid += 1
            if n_invalid >= 2:
                print("=========== 2 INVALID LEGS -- STOPPING: INVALID-RUN "
                      "===========", flush=True)
                break
    print("=========== E11 MATRIX DONE ===========", flush=True)
    by_speed: dict[str, list[str]] = {}
    for label, speed, _ in LEGS:
        if label in verdicts:
            by_speed.setdefault(speed, []).append(verdicts[label])
    for speed, vs in by_speed.items():
        print(f"  {speed} m/s: {vs.count('PASS')}/{len(vs)} PASS  {vs}", flush=True)
    reg_ok = verdicts.get("reg-2.5") == "PASS"
    s30 = [verdicts.get(f"s3.0{c}") for c in "abc"]
    rq = "YES" if reg_ok and s30.count("PASS") >= 2 else "NO"
    if not reg_ok:
        rq += (" (CHASE-REGRESSION: reg-2.5 failed -- chase-hold broke the E10"
               " ceiling speed; the 3.0+ results are not comparable)")
    ceiling = "2.5 m/s (E10, unchanged)"
    need = {"2.5": 1, "3.0": 2, "3.5": 2}
    for speed in ["3.0", "3.5"]:
        vs = by_speed.get(speed, [])
        if reg_ok and vs.count("PASS") >= need[speed]:
            ceiling = f"{speed} m/s"
        else:
            break  # a lower speed failing blocks a higher "ceiling" claim
    print(f"  RQ-E11: {rq}   measured ceiling: {ceiling}", flush=True)
    print("  (verdict rules: README 'Verdict rules' -- these lines ARE the "
          "mechanical application)", flush=True)
    sys.exit(0 if n_invalid < 2 else 1)


if __name__ == "__main__":
    main()
