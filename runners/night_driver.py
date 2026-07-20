#!/usr/bin/env python3
"""night_driver.py -- run a fixed sequence of unattended steps, retrying each.

Exists because the operator is away and the agent that launched this is not
guaranteed to be alive when it finishes. Every step is resumable by design
(carla_gt_bank skips clips with a complete manifest), so a retry is a resume,
not a restart -- the point is that a CARLA segfault at clip 19 costs one clip
instead of the night.

    setsid nohup .venv-ft/bin/python runners/night_driver.py \
        > experiments/2026-07-21-carla-gt-bank/runs/night.log 2>&1 &

The server is deliberately NOT stopped between steps: ensure_carla adopts a
live server on the port, and relaunches only if nothing answers.
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv-ft" / "bin" / "python")
OUT = ROOT / "experiments" / "2026-07-21-carla-gt-bank" / "runs"
BANK = str(OUT / "bank")

# (name, argv, attempts). Order matters: the bank is the long pole and the
# gates are cheap, so the bank goes first -- a night that dies early should
# still have most of the artifact.
STEPS = [
    ("bank", ["--clips", "25", "--seconds", "60", "--out", BANK], 8),
    ("gate_c", ["--gate-c"], 3),
    ("gate_a", ["--gate-a"], 2),
]


def stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def run(name, extra, attempts):
    for k in range(1, attempts + 1):
        cmd = [PY, str(ROOT / "runners" / "carla_gt_bank.py"), "--port", "2100", *extra]
        print(f"[{stamp()}] {name} attempt {k}/{attempts}: {' '.join(cmd)}", flush=True)
        t0 = time.time()
        rc = subprocess.call(cmd, cwd=ROOT)
        dt = time.time() - t0
        print(f"[{stamp()}] {name} rc={rc} after {dt/60:.1f} min", flush=True)
        if rc == 0:
            return {"step": name, "ok": True, "attempts": k, "minutes": round(dt / 60, 1)}
        # a crashed server leaves the port dead; give it time to release before
        # ensure_carla tries to relaunch on top of a half-exited process
        time.sleep(30)
    return {"step": name, "ok": False, "attempts": attempts}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / "night_driver.json"
    results = []
    for name, extra, attempts in STEPS:
        results.append(run(name, extra, attempts))
        log.write_text(json.dumps(
            {"started": stamp(), "results": results}, indent=2))
    ok = all(r["ok"] for r in results)
    print(f"[{stamp()}] done, all_ok={ok}", flush=True)
    print(json.dumps(results, indent=2), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
