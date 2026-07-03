"""E12 late-command run matrix. All design patches are already committed
(do NOT re-patch). 4 legs, the full E11 lever stack plus --acquire-delay 3.0
(no VLM draw before t=3.0 s -- removes the t=0 gift frame, so the winning
submit frame must be chase-produced): d3.0 (control -- chase is already
validated at 3.0, the delay only removes an always-rejected early draw),
d3.5 x3 (decision -- does chase itself deliver first-acquire at 3.5?).
Snapshot-per-run (phase3_sitl clobbers raw/phase3a-sitl/trial-<v>ms.{csv,mp4}
+ runs/phase3a-sitl/results.json every run; the csv/mp4 name depends on
--speed).

Per-leg gate and the FAIL binding-mode classification are mechanical --
printed by this script, no deliberation. Abort rule: a leg is killed at 20 min
(INVALID, continue); the second INVALID stops the matrix (INVALID-RUN).

    .venv-ft/bin/python experiments/2026-07-03-late-command/run_e12.py
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

LEGS = [  # (label, speed, vmax) -- run in this order; the control leg first
    ("d3.0", "3.0", "4.0"),
    ("d3.5a", "3.5", "5.0"), ("d3.5b", "3.5", "5.0"), ("d3.5c", "3.5", "5.0"),
]
COMMON = ["--loss-gate", "motion", "--dr", "pursuit",
          "--acquire-hold", "chase", "--acquire-delay", "3.0"]


def classify_fail(trial: dict, csv_path: Path) -> str:
    """Mechanical binding-mode label for a FAIL leg (verbatim from run_e10.py).

    never-locked        first_lock_s is null (first-acquire binds)
    else: first >=1.0 s contiguous in_fov==0 run after first_lock ->
      state at run start: ACQUIRE -> first-acquire; REGROUND/RETARGET ->
      relock; CARRY -> tracking-trail.
    E12 addition: no such post-lock run -> the gate fell on the PRE-lock
      escape window (first-acquire) or on recovered_after_occlusion.
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
    if not trial.get("recovered_after_occlusion"):
        return ("occlusion-relock (recovered_after_occlusion=False, "
                "no >=1s post-lock out-of-FOV run)")
    return ("first-acquire (pre-lock escape window -- in_fov budget spent "
            "before first lock; post-lock track clean)")


def chase_runaway(csv_path: Path) -> bool:
    """E11's pre-registered failure signature: a garbage early blob seeds a
    bad velocity and the copter chases off north at vmax with no pre-lock
    timeout. Mechanical test: while in ACQUIRE, copter_n ever exceeds
    rover_n + 15 m (the copter has overrun the car by more than a footprint
    and a half -- it is chasing a phantom)."""
    if not csv_path.exists():
        return False
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            if row["state"] == "ACQUIRE" and row["copter_n"] and row["rover_n"]:
                if float(row["copter_n"]) > float(row["rover_n"]) + 15.0:
                    return True
    return False


def run_leg(label: str, speed: str, vmax: str) -> str:
    """Run one leg, snapshot, print+return verdict: PASS / FAIL / INVALID."""
    print(f"=========== E12 {label}  --speed {speed} --vmax {vmax} "
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
        if chase_runaway(dst / "trial.csv"):
            line += "  [CHASE-RUNAWAY: pre-lock copter overran the car by >15 m]"
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
    print("=========== E12 MATRIX DONE ===========", flush=True)
    d30 = verdicts.get("d3.0")
    d35 = [verdicts.get(f"d3.5{c}") for c in "abc"]
    print(f"  d3.0 (control): {d30}", flush=True)
    print(f"  d3.5: {d35.count('PASS')}/3 PASS  {d35}", flush=True)
    if d30 != "PASS":
        rq = ("NO (CONTROL-FAIL: d3.0 failed -- the 3-s late command breaks "
              "even the chase-validated speed; d3.5 results are not "
              "attributable to the 3.5 rung)")
        ceiling = ("late-command first-acquire binds at <= 3.0 m/s; "
                   "easy-spawn ceiling >= 3.5 (E11) stands but is draw-1-"
                   "conditioned")
    elif d35.count("PASS") >= 2:
        rq = "YES"
        ceiling = "3.5 m/s ceiling now CHASE-VALIDATED under a hard spawn"
    else:
        rq = "NO"
        ceiling = ("chase-validated ceiling = 3.0 m/s; E11's 3.5 passes were "
                   "draw-1 easy-spawn artifacts (3.5 holds only when the "
                   "first draw wins)")
    print(f"  RQ-E12: {rq}", flush=True)
    print(f"  ceiling statement: {ceiling}", flush=True)
    print("  (verdict rules: README 'Verdict rules' -- these lines ARE the "
          "mechanical application)", flush=True)
    sys.exit(0 if n_invalid < 2 else 1)


if __name__ == "__main__":
    main()
