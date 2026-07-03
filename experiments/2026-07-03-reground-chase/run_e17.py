"""E17 reground-chase run matrix. One harness patch this cycle (already
committed by Fable on this branch -- Opus: do NOT edit phase3_sitl.py):
`--reground-hold {none,chase}`, default none = E2-E16 bit-identical; "chase"
extends the E11 pre-lock chase-hold to REGROUND blind phases (control law
only, accept path untouched).

Order: both selfchecks (PRECONDITION GATE -- phase3_sitl --selfcheck AND
sitl_cam.py must both exit 0, else PRECONDITION-FAIL and no legs run); then
ctl (no-gate no-hold control, halt-on-fail with one retry); then guard-a/b
(E14 mk-reg-3.0 config + the lever, 3.0 m/s honest-ceiling regression;
guard-c only if exactly one of a/b PASSes); then rh-1..rh-10 (E16's exact
mask-gate config + --reground-hold chase, 10 independent replicates).
Snapshot-per-leg (phase3_sitl clobbers raw/phase3a-sitl/trial-<speed>ms.{csv,
mp4} + runs/phase3a-sitl/results.json every run -- the E2-E16 gotcha; the
csv/mp4 basename depends on --speed). Per-leg verdicts, the mechanism metric
rg_fov (in-FOV fraction over REGROUND-state csv rows), and the final RQ-E17
verdict are computed mechanically here; the README's verdict rules are the
same rules.

    .venv-ft/bin/python experiments/2026-07-03-reground-chase/run_e17.py
"""

from __future__ import annotations

import csv as csvmod
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAMP = Path(__file__).resolve().parent
SRC = REPO / "experiments" / "2026-07-01-temporal-acquire-carry"
PY = REPO / ".venv-ft" / "bin" / "python"
LEG_TIMEOUT_S = 1500  # 150 s legs + boots; E16 actuals ~13-14 min/leg
MAX_RETRIES = 2       # rh-rep retries (NOT-MEASURABLE / INVALID legs only)

GATE = ["--reground-gate", "mask"]
HOLD = ["--reground-hold", "chase"]
DECOY = ["--speed", "0.25", "--twin", "decoy", "--decoy-shade", "215",
         "--duration-s", "150",
         "--loss-gate", "motion", "--dr", "pursuit", "--acquire-hold", "motion"]
# E14 mk-reg-3.0 (the E12 honest-ceiling config + mask gate) + the lever:
GUARD = ["--speed", "3.0", "--vmax", "4.0",
         "--loss-gate", "motion", "--dr", "pursuit",
         "--acquire-hold", "chase", "--acquire-delay", "3.0"] + GATE + HOLD

REPS = [f"rh-{i}" for i in range(1, 11)]


def accept_times(tr: dict) -> list[float]:
    """Relock accept times: every accepted acquire AFTER the initial lock."""
    acc = [e[0] for e in tr.get("acquire_log", []) if e[2]]
    return acc[1:]  # acc[0] is the initial ACQUIRE at first_lock


def size_rejects(tr: dict) -> int:
    return sum(1 for e in tr.get("acquire_log", []) if not e[2] and e[3] == "size")


def rg_fov(csv_path: Path) -> float | None:
    """Mechanism metric: in-FOV fraction over REGROUND-state control rows.
    E16 comparators: PASS reps all 1.000; FAIL reps 0.507 (rep-1) and 0.203
    (rep-5); ctl 0.255. None if the leg never entered REGROUND."""
    try:
        rows = [r for r in csvmod.DictReader(open(csv_path))
                if r["state"] == "REGROUND"]
    except FileNotFoundError:
        return None
    if not rows:
        return None
    return round(sum(int(r["in_fov"]) for r in rows) / len(rows), 3)


def verdict(label: str, tr: dict | None, fov: float | None) -> str:
    """Mechanical per-leg verdict; mirror of the README rules."""
    if tr is None:
        return "INVALID (no readable results)"
    if label.startswith("guard"):
        ok = tr["in_fov_frac"] >= 0.90 and tr["recovered_after_occlusion"]
        return ("PASS" if ok else "FAIL") + (
            f" (in_fov={tr['in_fov_frac']} "
            f"recovered={tr['recovered_after_occlusion']} "
            f"first_lock={tr['first_lock_s']} n_regrounds={tr['n_regrounds']} "
            f"rg_fov={fov})")
    tw = tr["twin"]
    if label.startswith("ctl"):
        repro = (tr["n_regrounds"] >= 1 and tw["closest_at_end"] == "distractor"
                 and tw["final_d_true_m"] >= 10.0)
        return ("REPRODUCES" if repro else "NOT-REPRODUCED") + (
            f" (n_regrounds={tr['n_regrounds']} closest={tw['closest_at_end']} "
            f"final_d_true={tw['final_d_true_m']} relock_on={tw['relock_on']})")
    detail = (f" (relock_on={tw['relock_on']} closest={tw['closest_at_end']} "
              f"final_d_true={tw['final_d_true_m']} in_fov={tr['in_fov_frac']} "
              f"rg_fov={fov} gate_rejects={tr['n_reground_gate_rejects']} "
              f"size_rejects={size_rejects(tr)} accepts_t={accept_times(tr)})")
    breach = " [GATE-BREACH]" if "distractor" in tw["relock_on"] else ""
    if tr["n_regrounds"] == 0:
        return "NOT-MEASURABLE (confident-latch: no REGROUND fired)" + detail
    # FAIL sub-attribution: HOLD-MISS = the lever failed its proximal job
    # (car left FOV during REGROUND anyway); PROPOSAL-MISS = the lever did its
    # job (car held in FOV) but the VLM/accept path still missed.
    mode = ("HOLD-MISS" if fov is not None and fov < 0.90 else "PROPOSAL-MISS")
    if not tw["relock_on"]:
        return f"FAIL no-relock [{mode}]" + breach + detail
    ok = (tw["relock_on"][-1] == "true" and tw["closest_at_end"] == "true"
          and tw["final_d_true_m"] <= 2.0 and tr["in_fov_frac"] >= 0.90)
    if ok:
        return "PASS" + breach + detail
    if tw["relock_on"][-1] != "true":
        return f"FAIL wrong-lock [{mode}]" + breach + detail
    if tw["closest_at_end"] != "true":
        return f"FAIL wrong-end [{mode}]" + breach + detail
    return f"FAIL verified-but-lost [{mode}]" + breach + detail


def run_leg(label: str, flags: list[str], speed: str) -> tuple[str, dict | None]:
    print(f"=========== E17 {label}  {' '.join(flags)} ===========", flush=True)
    try:
        subprocess.run([str(PY), str(SRC / "phase3_sitl.py"), *flags],
                       cwd=REPO, timeout=LEG_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        print(f"LEG TIMEOUT >{LEG_TIMEOUT_S}s -- kill, snapshot, leg INVALID",
              flush=True)
    dst = CAMP / "runs" / label
    dst.mkdir(parents=True, exist_ok=True)
    for src, name in [
            (SRC / "runs/phase3a-sitl/results.json", "results.json"),
            (SRC / f"raw/phase3a-sitl/trial-{speed}ms.csv", "trial.csv"),
            (SRC / f"raw/phase3a-sitl/trial-{speed}ms.mp4", "trial.mp4")]:
        if src.exists():
            shutil.copy2(src, dst / name)
        else:
            print(f"MISSING (leg INVALID?): {src}", flush=True)
    try:
        tr = json.loads((dst / "results.json").read_text())["trial"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        print(f"--- {label}: INVALID (no readable results: {e}) ---", flush=True)
        return "INVALID (no readable results)", None
    v = verdict(label, tr, rg_fov(dst / "trial.csv"))
    print(f"--- {label}: {v} ---", flush=True)
    print(f"--- snapshot -> {dst} ---", flush=True)
    return v, tr


def main() -> None:
    print("=========== E17 selfchecks (precondition) ===========", flush=True)
    for script in [SRC / "phase3_sitl.py", SRC / "sitl_cam.py"]:
        args = ["--selfcheck"] if script.name == "phase3_sitl.py" else []
        r = subprocess.run([str(PY), str(script), *args], cwd=REPO)
        if r.returncode != 0:
            print(f"PRECONDITION-FAIL: {script.name} selfcheck failed -- "
                  "no legs run; RQ-E17 = NOT-MEASURABLE", flush=True)
            sys.exit(1)
    print("selfchecks PASS", flush=True)

    # Control first: halt-on-fail (one retry) before spending the reps.
    v, _ = run_leg("ctl", DECOY, "0.25")
    if not v.startswith("REPRODUCES"):
        v, _ = run_leg("ctl-retry", DECOY, "0.25")
        if not v.startswith("REPRODUCES"):
            print("CTL NOT-REPRODUCED twice -- HALT, RQ-E17 = NOT-MEASURABLE "
                  "(upstream rig/VLM drift; rate not comparable to E16)",
                  flush=True)
            sys.exit(1)

    # Ceiling guards next (cheap, 75 s legs): a REGRESSED early warning.
    # Whatever they say, the reps still run (the rate stands on its own).
    guards: dict[str, str] = {}
    for g in ["guard-a", "guard-b"]:
        guards[g], _ = run_leg(g, GUARD, "3.0")
    for g in list(guards):  # INVALID guards get one retry each
        if guards[g].startswith("INVALID"):
            guards[g], _ = run_leg(f"{g}-retry", GUARD, "3.0")
    gvalid = [g for g in guards if guards[g].startswith(("PASS", "FAIL"))]
    if len(gvalid) == 2 and sum(
            guards[g].startswith("PASS") for g in gvalid) == 1:
        guards["guard-c"], _ = run_leg("guard-c", GUARD, "3.0")
        if guards["guard-c"].startswith("INVALID"):
            guards["guard-c"], _ = run_leg("guard-c-retry", GUARD, "3.0")
        gvalid = [g for g in guards if guards[g].startswith(("PASS", "FAIL"))]
    gpass = sum(guards[g].startswith("PASS") for g in gvalid)
    if len(gvalid) < 2:
        greg = "GUARD-INCOMPLETE"      # <2 valid guard legs after retries
    elif gpass >= 2:
        greg = "NO-REGRESSION"
    else:
        greg = "REGRESSED"
    print(f"--- guards: {gpass}/{len(gvalid)} PASS -> {greg} ---", flush=True)

    results: dict[str, str] = {}
    for label in REPS:
        results[label], _ = run_leg(label, DECOY + GATE + HOLD, "0.25")

    # Retry NOT-MEASURABLE / INVALID reps once each, max MAX_RETRIES total.
    retryable = [l for l in REPS
                 if results[l].startswith(("NOT-MEASURABLE", "INVALID"))]
    if len(retryable) > MAX_RETRIES:
        print(f"WARNING: {len(retryable)} reps need retry, cap is "
              f"{MAX_RETRIES} -- rig likely sick, retrying first "
              f"{MAX_RETRIES} only", flush=True)
    for label in retryable[:MAX_RETRIES]:
        results[label], _ = run_leg(f"{label}-retry", DECOY + GATE + HOLD,
                                    "0.25")

    print("=========== E17 SUMMARY ===========", flush=True)
    for g in guards:
        print(f"{g}: {guards[g]}", flush=True)
    for label in REPS:
        print(f"{label}: {results[label]}", flush=True)
    valid = [l for l in REPS if results[l].startswith(("PASS", "FAIL"))]
    r = sum(1 for l in valid if results[l].startswith("PASS"))
    denom = len(valid)
    fails = denom - r
    breach = any("[GATE-BREACH]" in results[l] for l in REPS)
    print(f"relock rate r = {r}/{denom} valid reps "
          f"(10 attempted; excluded: {10 - denom}); E16 baseline 6/8",
          flush=True)
    if denom < 8:
        rq = "NOT-MEASURABLE (fewer than 8 valid reps)"
    elif fails == 0:
        band = "LIFTS"
        rq = f"YES ({r}/{denom}, zero FAILs; baseline 6/8)"
    elif fails == 1:
        band = "PARTIAL"
        rq = f"QUALIFIED ({r}/{denom}, one FAIL; baseline 6/8)"
    else:
        band = "NO-LIFT"
        rq = f"NO ({r}/{denom}, >=2 FAILs -- indistinguishable from the 0.75 baseline)"
    if denom >= 8:
        print(f"rate band: {band}", flush=True)
        if breach:
            rq = f"NO [identity-breach observed] (rate was {r}/{denom})"
        if greg == "REGRESSED":
            rq += " [REGRESSED at 3.0 m/s -- lever rejected for the follow stack]"
        elif greg == "GUARD-INCOMPLETE":
            if rq.startswith("YES"):
                rq = "QUALIFIED" + rq[3:] + " [guard-incomplete: capped, cannot be YES]"
            else:
                rq += " [guard-incomplete]"
    print(f"RQ-E17 verdict: {rq}", flush=True)
    print("=========== E17 MATRIX DONE ===========", flush=True)


if __name__ == "__main__":
    main()
