"""E13 identity-gate run matrix. All design patches are already committed
(do NOT re-patch). Order: appearance smoke first -- it is a PRECONDITION GATE
(decoy-capture >= 7/10 AND descriptor separability at tau, else print
PRECONDITION-FAIL and skip the legs); then 7 SITL legs, snapshot-per-run
(phase3_sitl clobbers raw/phase3a-sitl/trial-<v>ms.{csv,mp4} +
runs/phase3a-sitl/results.json every run, the E2-E12 gotcha). Per-leg verdicts
are computed mechanically here; the README's verdict rules are the same rules.

    .venv-ft/bin/python experiments/2026-07-03-identity-gate/run_e13.py
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
LEG_TIMEOUT_S = 1500  # 150 s legs + boots; E10-E12 actuals ~3-5 min/leg

GATE = ["--reground-gate", "appearance"]
DECOY = ["--speed", "0.25", "--twin", "decoy", "--decoy-shade", "215",
         "--duration-s", "150",
         "--loss-gate", "motion", "--dr", "pursuit", "--acquire-hold", "motion"]
LEGS = [  # (label, flags)
    ("ctl-decoy",  DECOY),
    ("ap-decoy-a", DECOY + GATE),
    ("ap-decoy-b", DECOY + GATE),
    ("ap-decoy-c", DECOY + GATE),
    ("ap-reg-0.5", ["--speed", "0.5", "--loss-gate", "motion", "--dr",
                    "pursuit", "--acquire-hold", "motion"] + GATE),
    ("ap-reg-3.0", ["--speed", "3.0", "--vmax", "4.0", "--loss-gate", "motion",
                    "--dr", "pursuit", "--acquire-hold", "chase",
                    "--acquire-delay", "3.0"] + GATE),
    ("ap-rt",      ["--speed", "0.5", "--twin", "escort", "--loss-gate",
                    "motion", "--dr", "pursuit", "--acquire-hold", "motion",
                    "--retarget-t", "50"] + GATE),
]


def verdict(label: str, tr: dict) -> str:
    """Mechanical per-leg verdict; mirror of the README rules."""
    if "decoy" in label:
        if tr["n_regrounds"] == 0:
            return "NOT-MEASURABLE (confident-latch: no REGROUND fired)"
        tw = tr["twin"]
        if not tw["relock_on"]:
            return (f"FAIL (no relock: {tr['n_regrounds']} regrounds, "
                    f"{tr['n_reground_gate_rejects']} gate rejects -- "
                    "identity-preserving no-relock)")
        ok = (tw["relock_on"][-1] == "true" and tw["closest_at_end"] == "true"
              and tw["final_d_true_m"] <= 2.0 and tr["in_fov_frac"] >= 0.90)
        return ("PASS" if ok else "FAIL") + (
            f" (relock_on={tw['relock_on']} closest={tw['closest_at_end']} "
            f"final_d_true={tw['final_d_true_m']} in_fov={tr['in_fov_frac']})")
    if label == "ap-rt":
        rt, tw = tr["retarget"], tr["twin"]
        checks = [bool(rt["switch_walls_s"]) and rt["switch_walls_s"][0] <= 15.0,
                  bool(rt["switch_on"]) and rt["switch_on"][-1] == "distractor",
                  tw["closest_at_end"] == "distractor",
                  tw["final_d_dist_m"] <= 2.0,
                  (rt["frac_box_closer_dist_post"] or 0) >= 0.80,
                  (rt["dist_in_fov_frac_post"] or 0) >= 0.90,
                  tr["in_fov_frac"] >= 0.90]
        return ("PASS" if all(checks) else "FAIL") + f" (E9 checks={checks})"
    ok = tr["in_fov_frac"] >= 0.90 and tr["recovered_after_occlusion"]
    return ("PASS" if ok else "FAIL") + (
        f" (in_fov={tr['in_fov_frac']} recovered={tr['recovered_after_occlusion']})")


def run_leg(label: str, flags: list[str]) -> None:
    print(f"=========== E13 {label}  {' '.join(flags)} ===========", flush=True)
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
    print("=========== E13 appearance smoke (precondition) ===========",
          flush=True)
    subprocess.run([str(PY), str(CAMP / "e13_appearance_smoke.py")],
                   cwd=REPO, check=True)
    smoke = json.loads((CAMP / "runs/appearance-smoke/results.json").read_text())
    if not smoke["pass"]:
        print(f"PRECONDITION-FAIL: decoy_hits={smoke['decoy_hits_of_10']}/10 "
              f"true_dists={smoke['true_dists']} "
              f"decoy_dists={smoke['decoy_dists']} -- SITL legs skipped, "
              "verdict per README", flush=True)
        sys.exit(1)
    print(f"smoke PASS (decoy_hits={smoke['decoy_hits_of_10']}/10, "
          f"pref_true={smoke['pref_true_of_10']}/10) -- running legs",
          flush=True)
    for label, flags in LEGS:
        run_leg(label, flags)
    print("=========== E13 MATRIX DONE ===========", flush=True)


if __name__ == "__main__":
    main()
