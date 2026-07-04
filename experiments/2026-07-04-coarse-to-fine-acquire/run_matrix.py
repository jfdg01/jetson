"""E21 matrix driver (13 runs): smoke (c2f car10 x1), then c2f (6 clips x n=2).

Each config is a fresh subprocess of replay_e21.py (per-run isolation + Jetson
self-boot, matching the E18/E19/E20 convention). Captions are frozen from E18 (D3);
the coarse-to-fine hint is COMPUTED at runtime by the coarse pass -- the matrix never
passes --scope-hint (that flag is E20-debug only). No buf legs (D2), no wrong probe
(E21's automated analogue is a naturally wrong coarse cell, measured post-hoc in
summarize.py).

    .venv-ft/bin/python experiments/2026-07-04-coarse-to-fine-acquire/run_matrix.py [--smoke-only]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PY = str(REPO / ".venv-ft" / "bin" / "python")
SCRIPT = str(HERE / "replay_e21.py")
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
DATA = E18 / "data" / "UAV123"

# frozen from E18 (D3) -- identical captions to E20
CAPTIONS = {
    "car3": "the red car", "car9": "the white car", "car14": "the red car",
    "car18": "the red car", "car7": "the silver car", "car10": "the red car",
}
CLIPS = ["car3", "car7", "car9", "car10", "car14", "car18"]


def run(clip, out_name):
    out = HERE / "runs" / out_name
    print(f"\n=== {out_name} (c2f clip={clip}) ===", flush=True)
    cmd = [PY, SCRIPT, "--mc", "none", "--c2f", "--clip", clip,
           "--caption", CAPTIONS[clip], "--out", str(out)]
    subprocess.run(cmd, check=True)


def main():
    smoke_only = "--smoke-only" in sys.argv
    run("car10", "smoke_c2f_car10")                              # plumbing smoke
    if smoke_only:
        return
    for clip in CLIPS:                                           # c2f arm
        for rep in (1, 2):
            run(clip, f"c2f_{clip}_r{rep}")


if __name__ == "__main__":
    main()
