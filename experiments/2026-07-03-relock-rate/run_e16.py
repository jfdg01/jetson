"""E16 relock-rate run matrix. NO harness patches this cycle (the config is
E14's exact mk-decoy flag set on current main); this runner is the only new
file. Order: both selfchecks (PRECONDITION GATE -- phase3_sitl --selfcheck AND
sitl_cam.py must both exit 0, else PRECONDITION-FAIL and no legs run); then
ctl (no-gate control, halt-on-fail with one retry); then rep-1..rep-8 (E14's
exact mask-gate config, 8 independent replicates). Snapshot-per-leg
(phase3_sitl clobbers raw/phase3a-sitl/trial-0.25ms.{csv,mp4} +
runs/phase3a-sitl/results.json every run -- the E2-E15 gotcha). Per-leg
verdicts and the final RQ-E16 rate verdict are computed mechanically here;
the README's verdict rules are the same rules.

    .venv-ft/bin/python experiments/2026-07-03-relock-rate/run_e16.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAMP = Path(__file__).resolve().parent
SRC = REPO / "experiments" / "2026-07-01-temporal-acquire-carry"
PY = REPO / ".venv-ft" / "bin" / "python"
LEG_TIMEOUT_S = 1500  # 150 s legs + boots; E14/E15 actuals ~12-15 min/leg
MAX_RETRIES = 2       # rep retries (NOT-MEASURABLE / INVALID legs only)

GATE = ["--reground-gate", "mask"]
DECOY = ["--speed", "0.25", "--twin", "decoy", "--decoy-shade", "215",
         "--duration-s", "150",
         "--loss-gate", "motion", "--dr", "pursuit", "--acquire-hold", "motion"]

REPS = [f"rep-{i}" for i in range(1, 9)]


def accept_times(tr: dict) -> list[float]:
    """Relock accept times: every accepted acquire AFTER the initial lock."""
    acc = [e[0] for e in tr.get("acquire_log", []) if e[2]]
    return acc[1:]  # acc[0] is the initial ACQUIRE at first_lock


def size_rejects(tr: dict) -> int:
    return sum(1 for e in tr.get("acquire_log", []) if not e[2] and e[3] == "size")


def verdict(label: str, tr: dict | None) -> str:
    """Mechanical per-leg verdict; mirror of the README rules."""
    if tr is None:
        return "INVALID (no readable results)"
    tw = tr["twin"]
    if label.startswith("ctl"):
        repro = (tr["n_regrounds"] >= 1 and tw["closest_at_end"] == "distractor"
                 and tw["final_d_true_m"] >= 10.0)
        return ("REPRODUCES" if repro else "NOT-REPRODUCED") + (
            f" (n_regrounds={tr['n_regrounds']} closest={tw['closest_at_end']} "
            f"final_d_true={tw['final_d_true_m']} relock_on={tw['relock_on']})")
    detail = (f" (relock_on={tw['relock_on']} closest={tw['closest_at_end']} "
              f"final_d_true={tw['final_d_true_m']} in_fov={tr['in_fov_frac']} "
              f"gate_rejects={tr['n_reground_gate_rejects']} "
              f"size_rejects={size_rejects(tr)} accepts_t={accept_times(tr)})")
    breach = " [GATE-BREACH]" if "distractor" in tw["relock_on"] else ""
    if tr["n_regrounds"] == 0:
        return "NOT-MEASURABLE (confident-latch: no REGROUND fired)" + detail
    if not tw["relock_on"]:
        return "FAIL no-relock" + breach + detail
    ok = (tw["relock_on"][-1] == "true" and tw["closest_at_end"] == "true"
          and tw["final_d_true_m"] <= 2.0 and tr["in_fov_frac"] >= 0.90)
    if ok:
        return "PASS" + breach + detail
    if tw["relock_on"][-1] != "true":
        return "FAIL wrong-lock" + breach + detail
    if tw["closest_at_end"] != "true":
        return "FAIL wrong-end" + breach + detail
    return "FAIL verified-but-lost" + breach + detail


def run_leg(label: str, flags: list[str]) -> tuple[str, dict | None]:
    print(f"=========== E16 {label}  {' '.join(flags)} ===========", flush=True)
    try:
        subprocess.run([str(PY), str(SRC / "phase3_sitl.py"), *flags],
                       cwd=REPO, timeout=LEG_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        print(f"LEG TIMEOUT >{LEG_TIMEOUT_S}s -- kill, snapshot, leg INVALID",
              flush=True)
    dst = CAMP / "runs" / label
    dst.mkdir(parents=True, exist_ok=True)
    for src, name in [(SRC / "runs/phase3a-sitl/results.json", "results.json"),
                      (SRC / "raw/phase3a-sitl/trial-0.25ms.csv", "trial.csv"),
                      (SRC / "raw/phase3a-sitl/trial-0.25ms.mp4", "trial.mp4")]:
        if src.exists():
            shutil.copy2(src, dst / name)
        else:
            print(f"MISSING (leg INVALID?): {src}", flush=True)
    try:
        tr = json.loads((dst / "results.json").read_text())["trial"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        print(f"--- {label}: INVALID (no readable results: {e}) ---", flush=True)
        return "INVALID (no readable results)", None
    v = verdict(label, tr)
    print(f"--- {label}: {v} ---", flush=True)
    print(f"--- snapshot -> {dst} ---", flush=True)
    return v, tr


def main() -> None:
    print("=========== E16 selfchecks (precondition) ===========", flush=True)
    for script in [SRC / "phase3_sitl.py", SRC / "sitl_cam.py"]:
        args = ["--selfcheck"] if script.name == "phase3_sitl.py" else []
        r = subprocess.run([str(PY), str(script), *args], cwd=REPO)
        if r.returncode != 0:
            print(f"PRECONDITION-FAIL: {script.name} selfcheck failed -- "
                  "no legs run; RQ-E16 = NOT-MEASURABLE", flush=True)
            sys.exit(1)
    print("selfchecks PASS", flush=True)

    # Control first: halt-on-fail (one retry) before spending 8 reps.
    v, _ = run_leg("ctl", DECOY)
    if not v.startswith("REPRODUCES"):
        v, _ = run_leg("ctl-retry", DECOY)
        if not v.startswith("REPRODUCES"):
            print("CTL NOT-REPRODUCED twice -- HALT, RQ-E16 = NOT-MEASURABLE "
                  "(upstream rig/VLM drift; rates not comparable to E14)",
                  flush=True)
            sys.exit(1)

    results: dict[str, str] = {}
    for label in REPS:
        results[label], _ = run_leg(label, DECOY + GATE)

    # Retry NOT-MEASURABLE / INVALID reps once each, max MAX_RETRIES total.
    retryable = [l for l in REPS
                 if results[l].startswith(("NOT-MEASURABLE", "INVALID"))]
    if len(retryable) > MAX_RETRIES:
        print(f"WARNING: {len(retryable)} reps need retry, cap is "
              f"{MAX_RETRIES} -- rig likely sick, retrying first "
              f"{MAX_RETRIES} only", flush=True)
    for label in retryable[:MAX_RETRIES]:
        results[label], _ = run_leg(f"{label}-retry", DECOY + GATE)

    print("=========== E16 SUMMARY ===========", flush=True)
    for label in REPS:
        print(f"{label}: {results[label]}", flush=True)
    valid = [l for l in REPS
             if results[l].startswith(("PASS", "FAIL"))]
    r = sum(1 for l in valid if results[l].startswith("PASS"))
    denom = len(valid)
    breach = any("[GATE-BREACH]" in results[l] for l in REPS)
    print(f"relock rate r = {r}/{denom} valid reps "
          f"(8 attempted; excluded: {8 - denom})", flush=True)
    if denom < 6:
        rq = "NOT-MEASURABLE (fewer than 6 valid reps)"
    elif denom - r <= 1:
        rq = f"RELIABLE ({r}/{denom}, at most one FAIL)"
    elif 2 * r <= denom:
        rq = f"FRAGILE ({r}/{denom}, at or below half)"
    else:
        rq = f"QUALIFIED ({r}/{denom})"
    if breach:
        rq += " [identity-breach observed]"
    print(f"RQ-E16 verdict: {rq}", flush=True)
    print("=========== E16 MATRIX DONE ===========", flush=True)


if __name__ == "__main__":
    main()
