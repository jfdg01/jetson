"""E9 retarget-switch run matrix. All design patches are already committed
(do NOT re-patch). Order: color smoke first -- it is a PRECONDITION GATE
(both captions >= 7/10 hits, else print PRECONDITION-FAIL and skip the legs);
then 4 SITL legs, snapshot-per-run (phase3_sitl clobbers raw/phase3a-sitl/
trial-<v>ms.{csv,mp4} + runs/phase3a-sitl/results.json every run, the E2-E8
gotcha).

    .venv-ft/bin/python experiments/2026-07-03-retarget-switch/run_e9.py
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
SMOKE_MIN = 7  # per caption, of 10

LEGS = [  # (label, extra flags beyond the common set)
    ("ctl", []),
    ("rt-a", ["--retarget-t", "50"]),
    ("rt-b", ["--retarget-t", "50"]),
    ("rt-c", ["--retarget-t", "50"]),
]
COMMON = ["--speed", "0.5", "--twin", "escort",
          "--loss-gate", "motion", "--dr", "pursuit", "--acquire-hold", "motion"]


def run_leg(label: str, extra: list[str]) -> None:
    print(f"=========== E9 {label}  {' '.join(COMMON + extra)} ===========",
          flush=True)
    subprocess.run([str(PY), str(SRC / "phase3_sitl.py"), *COMMON, *extra],
                   cwd=REPO)  # leg failure still snapshots whatever exists
    dst = CAMP / "runs" / label
    dst.mkdir(parents=True, exist_ok=True)
    for src, name in [(SRC / "runs/phase3a-sitl/results.json", "results.json"),
                      (SRC / "raw/phase3a-sitl/trial-0.5ms.csv", "trial.csv"),
                      (SRC / "raw/phase3a-sitl/trial-0.5ms.mp4", "trial.mp4")]:
        if src.exists():
            shutil.copy2(src, dst / name)
        else:
            print(f"MISSING (leg INVALID?): {src}", flush=True)
    print(f"--- snapshot -> {dst} ---", flush=True)


def main() -> None:
    print("=========== E9 color smoke (precondition) ===========", flush=True)
    subprocess.run([str(PY), str(CAMP / "e9_color_smoke.py")], cwd=REPO, check=True)
    hits = json.loads((CAMP / "runs/color-smoke/results.json")
                      .read_text())["hits_of_10"]
    if min(hits.values()) < SMOKE_MIN:
        print(f"PRECONDITION-FAIL: color smoke {hits} (need >= {SMOKE_MIN}/10 "
              f"per caption) -- SITL legs skipped, verdict per README", flush=True)
        sys.exit(1)
    print(f"smoke PASS {hits} -- running legs", flush=True)
    for label, extra in LEGS:
        run_leg(label, extra)
    print("=========== E9 MATRIX DONE ===========", flush=True)


if __name__ == "__main__":
    main()
