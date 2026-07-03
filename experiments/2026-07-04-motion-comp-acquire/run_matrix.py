"""E19 matrix driver: smoke, then A-flow (6 clips x n=2), then A-buf (6 x n=2).

Each config is a fresh subprocess of replay_e19.py (per-run isolation + Jetson
self-boot, matching the E18 convention). Captions are frozen from E18 (D3).

    .venv-ft/bin/python experiments/2026-07-04-motion-comp-acquire/run_matrix.py [--smoke-only]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PY = str(REPO / ".venv-ft" / "bin" / "python")
SCRIPT = str(HERE / "replay_e19.py")

CAPTIONS = {
    "car3": "the red car", "car9": "the white car", "car14": "the red car",
    "car18": "the red car", "car7": "the silver car", "car10": "the red car",
}
CLIPS = ["car3", "car9", "car14", "car18", "car7", "car10"]


def run(mc: str, clip: str, out_name: str) -> None:
    out = HERE / "runs" / out_name
    print(f"\n=== {out_name} (mc={mc} clip={clip}) ===", flush=True)
    subprocess.run([PY, SCRIPT, "--mc", mc, "--clip", clip,
                    "--caption", CAPTIONS[clip], "--out", str(out)], check=True)


def main() -> None:
    smoke_only = "--smoke-only" in sys.argv
    run("flow", "car10", "smoke_flow_car10")          # plumbing smoke
    if smoke_only:
        return
    for mc in ("flow", "buf"):
        for clip in CLIPS:
            for rep in (1, 2):
                run(mc, clip, f"{mc}_{clip}_r{rep}")


if __name__ == "__main__":
    main()
