"""E14 mask-identity run matrix. All design patches are already committed
(do NOT re-patch). Order: mask smoke first -- it is a PRECONDITION GATE
(decoy-capture >= 7/10 AND real-latch descriptor separability AND all blend
probes rejected AND the true-strip probe accepted, else print
PRECONDITION-FAIL and skip the legs); then 7 SITL legs, snapshot-per-run
(phase3_sitl clobbers raw/phase3a-sitl/trial-<v>ms.{csv,mp4} +
runs/phase3a-sitl/results.json every run, the E2-E13 gotcha). Per-leg verdicts
are computed mechanically here; the README's verdict rules are the same rules.
ctl-decoy uses END-STATE attribution (E13's relock_on[0] rule broke on a
transient early reground that caught the still-visible true car).

    .venv-ft/bin/python experiments/2026-07-03-mask-identity/run_e14.py
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
LEG_TIMEOUT_S = 1500  # 150 s legs + boots; E10-E13 actuals ~3-5 min/leg

GATE = ["--reground-gate", "mask"]
DECOY = ["--speed", "0.25", "--twin", "decoy", "--decoy-shade", "215",
         "--duration-s", "150",
         "--loss-gate", "motion", "--dr", "pursuit", "--acquire-hold", "motion"]
LEGS = [  # (label, flags)
    ("ctl-decoy",  DECOY),
    ("mk-decoy-a", DECOY + GATE),
    ("mk-decoy-b", DECOY + GATE),
    ("mk-decoy-c", DECOY + GATE),
    ("mk-reg-0.5", ["--speed", "0.5", "--loss-gate", "motion", "--dr",
                    "pursuit", "--acquire-hold", "motion"] + GATE),
    ("mk-reg-3.0", ["--speed", "3.0", "--vmax", "4.0", "--loss-gate", "motion",
                    "--dr", "pursuit", "--acquire-hold", "chase",
                    "--acquire-delay", "3.0"] + GATE),
    ("mk-rt",      ["--speed", "0.5", "--twin", "escort", "--loss-gate",
                    "motion", "--dr", "pursuit", "--acquire-hold", "motion",
                    "--retarget-t", "50"] + GATE),
]


def verdict(label: str, tr: dict) -> str:
    """Mechanical per-leg verdict; mirror of the README rules."""
    if label == "ctl-decoy":
        # end-state attribution: the wrong-lock reproduces iff a reground
        # fired and the flight ENDED on the decoy, far from the escaped true
        # car (E13 ctl: final_d_true 21.5 m). relock_on[0] is NOT consulted --
        # a transient early reground may legitimately catch the still-visible
        # true car (the E13 rule-edge).
        tw = tr["twin"]
        repro = (tr["n_regrounds"] >= 1 and tw["closest_at_end"] == "distractor"
                 and tw["final_d_true_m"] >= 10.0)
        return ("REPRODUCES" if repro else "NOT-REPRODUCED") + (
            f" (n_regrounds={tr['n_regrounds']} closest={tw['closest_at_end']} "
            f"final_d_true={tw['final_d_true_m']} relock_on={tw['relock_on']})")
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
    if label == "mk-rt":
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
    print(f"=========== E14 {label}  {' '.join(flags)} ===========", flush=True)
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
    print("=========== E14 mask smoke (precondition) ===========", flush=True)
    subprocess.run([str(PY), str(CAMP / "e14_mask_smoke.py")],
                   cwd=REPO, check=True)
    smoke = json.loads((CAMP / "runs/mask-smoke/results.json").read_text())
    if not smoke["pass"]:
        print(f"PRECONDITION-FAIL: decoy_hits={smoke['decoy_hits_of_10']}/10 "
              f"true_dists={smoke['true_dists']} "
              f"decoy_dists={smoke['decoy_dists']} "
              f"blend_probes={smoke['blend_probes']} -- SITL legs skipped, "
              "verdict per README", flush=True)
        sys.exit(1)
    print(f"smoke PASS (decoy_hits={smoke['decoy_hits_of_10']}/10) "
          "-- running legs", flush=True)
    for label, flags in LEGS:
        run_leg(label, flags)
    print("=========== E14 MATRIX DONE ===========", flush=True)


if __name__ == "__main__":
    main()
