"""E15 mask-hardening run matrix. All design patches are already committed
(do NOT re-patch). Order: both selfchecks first -- they are a PRECONDITION
GATE (phase3_sitl --selfcheck AND sitl_cam.py must both print PASS, else
print PRECONDITION-FAIL and skip the legs; no Jetson mask smoke is needed --
E15 uses E14's exact shade/descriptor, and the no-gate controls are the
behavioral precondition); then 9 SITL legs, snapshot-per-run (phase3_sitl
clobbers raw/phase3a-sitl/trial-<v>ms.{csv,mp4} + runs/phase3a-sitl/
results.json every run, the E2-E14 gotcha). Per-leg verdicts are computed
mechanically here; the README's verdict rules are the same rules. All
attribution is END-STATE (closest_at_end / final_d_true_m, E14's fix) --
relock_on[0] is never consulted.

    .venv-ft/bin/python experiments/2026-07-03-mask-hardening/run_e15.py
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
LEG_TIMEOUT_S = 1500  # 150 s legs + boots; E10-E14 actuals ~3-5 min/leg

GATE = ["--reground-gate", "mask"]
DECOY = ["--speed", "0.25", "--twin", "decoy", "--decoy-shade", "215",
         "--duration-s", "150",
         "--loss-gate", "motion", "--dr", "pursuit", "--acquire-hold", "motion"]
DD = ["--decoy2", "7.0"]      # second parked 215-decoy 7 m north of the first
RO = ["--occ2", "82", "10"]   # second bridge: car fully hidden t in [82, 92]
LEGS = [  # (label, flags)
    ("reg-e14", DECOY + GATE),         # exact E14 mk-decoy config, n=1
    ("ctl-dd",  DECOY + DD),           # no gate: does dd wrong-lock?
    ("dd-a",    DECOY + DD + GATE),
    ("dd-b",    DECOY + DD + GATE),
    ("dd-c",    DECOY + DD + GATE),
    ("ctl-ro",  DECOY + RO),           # no gate: does ro wrong-lock?
    ("ro-a",    DECOY + RO + GATE),
    ("ro-b",    DECOY + RO + GATE),
    ("ro-c",    DECOY + RO + GATE),
]


def verdict(label: str, tr: dict) -> str:
    """Mechanical per-leg verdict; mirror of the README rules."""
    tw = tr["twin"]
    if label.startswith("ctl-"):
        # end-state attribution: the wrong-lock reproduces iff a reground
        # fired and the flight ENDED on a decoy (either one), far from the
        # escaped true car. relock_on[0] is NOT consulted (E14's rule fix).
        repro = (tr["n_regrounds"] >= 1 and tw["closest_at_end"] != "true"
                 and tw["final_d_true_m"] >= 10.0)
        return ("REPRODUCES" if repro else "NOT-REPRODUCED") + (
            f" (n_regrounds={tr['n_regrounds']} closest={tw['closest_at_end']} "
            f"final_d_true={tw['final_d_true_m']} relock_on={tw['relock_on']})")
    # reg-e14 and the six gated stress legs share one rule; only the in_fov
    # bar differs (reg-e14 keeps E14's 0.90; stress legs get 0.80 because
    # --occ2 adds ~10 s of pre-registered blindness and dd extends the
    # reject window -- a relaxation declared before the run, not after).
    if tr["n_regrounds"] == 0:
        return "NOT-MEASURABLE (confident-latch: no REGROUND fired)"
    if not tw["relock_on"]:
        return (f"FAIL (no relock: {tr['n_regrounds']} regrounds, "
                f"{tr['n_reground_gate_rejects']} gate rejects -- "
                "identity-preserving no-relock)")
    fov_bar = 0.90 if label == "reg-e14" else 0.80
    ok = (tw["relock_on"][-1] == "true" and tw["closest_at_end"] == "true"
          and tw["final_d_true_m"] <= 2.0 and tr["in_fov_frac"] >= fov_bar)
    note = (" [degraded-fov]" if ok and label != "reg-e14"
            and tr["in_fov_frac"] < 0.90 else "")
    return ("PASS" if ok else "FAIL") + note + (
        f" (relock_on={tw['relock_on']} closest={tw['closest_at_end']} "
        f"final_d_true={tw['final_d_true_m']} "
        f"final_d_dist2={tw.get('final_d_dist2_m')} "
        f"in_fov={tr['in_fov_frac']} "
        f"gate_rejects={tr['n_reground_gate_rejects']})")


def run_leg(label: str, flags: list[str]) -> None:
    print(f"=========== E15 {label}  {' '.join(flags)} ===========", flush=True)
    try:
        subprocess.run([str(PY), str(SRC / "phase3_sitl.py"), *flags],
                       cwd=REPO, timeout=LEG_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        print(f"LEG TIMEOUT >{LEG_TIMEOUT_S}s -- kill, snapshot, leg INVALID",
              flush=True)
    speed = float(flags[flags.index("--speed") + 1])
    dst = CAMP / "runs" / label
    dst.mkdir(parents=True, exist_ok=True)
    for src, name in [(SRC / "runs/phase3a-sitl/results.json", "results.json"),
                      (SRC / f"raw/phase3a-sitl/trial-{speed}ms.csv", "trial.csv"),
                      (SRC / f"raw/phase3a-sitl/trial-{speed}ms.mp4", "trial.mp4")]:
        if src.exists():
            shutil.copy2(src, dst / name)
        else:
            print(f"MISSING (leg INVALID?): {src}", flush=True)
    try:
        tr = json.loads((dst / "results.json").read_text())["trial"]
        print(f"--- {label}: {verdict(label, tr)} ---", flush=True)
    except (FileNotFoundError, KeyError) as e:
        print(f"--- {label}: INVALID (no readable results: {e}) ---", flush=True)
    print(f"--- snapshot -> {dst} ---", flush=True)


def main() -> None:
    print("=========== E15 selfchecks (precondition) ===========", flush=True)
    for script in [SRC / "phase3_sitl.py", SRC / "sitl_cam.py"]:
        args = ["--selfcheck"] if script.name == "phase3_sitl.py" else []
        r = subprocess.run([str(PY), str(script), *args], cwd=REPO)
        if r.returncode != 0:
            print(f"PRECONDITION-FAIL: {script.name} selfcheck failed -- "
                  "SITL legs skipped, verdict per README", flush=True)
            sys.exit(1)
    print("selfchecks PASS -- running legs", flush=True)
    for label, flags in LEGS:
        run_leg(label, flags)
    print("=========== E15 MATRIX DONE ===========", flush=True)


if __name__ == "__main__":
    main()
