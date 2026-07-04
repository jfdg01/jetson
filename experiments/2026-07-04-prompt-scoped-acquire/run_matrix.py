"""E20 matrix driver (27 runs): smoke, then cell (6 clips x n=2), cellbuf (6 x n=2),
wrong (car10 x n=2).

Each config is a fresh subprocess of replay_e20.py (per-run isolation + Jetson
self-boot, matching the E18/E19 convention). Captions + per-clip hints are frozen
from E18/scope.hint_for (D1, D3); the wrong probe deliberately mis-hints car10.

    .venv-ft/bin/python experiments/2026-07-04-prompt-scoped-acquire/run_matrix.py [--smoke-only]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PY = str(REPO / ".venv-ft" / "bin" / "python")
SCRIPT = str(HERE / "replay_e20.py")
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
DATA = E18 / "data" / "UAV123"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(E18))
import scope                                                          # noqa: E402
from replay_source import load_uav123_gt                             # noqa: E402

# frozen from E18 (D3)
CAPTIONS = {
    "car3": "the red car", "car9": "the white car", "car14": "the red car",
    "car18": "the red car", "car7": "the silver car", "car10": "the red car",
}
# frozen from scope.hint_for on the frame-0 GT (asserted below)
HINTS = {
    "car3": "bottom left", "car7": "top center", "car9": "bottom center",
    "car10": "center", "car14": "center", "car18": "middle left",
}
CLIPS = ["car3", "car7", "car9", "car10", "car14", "car18"]
WRONG_HINT = "top left"   # car10 is actually "center"; deliberate mis-hint (D5)


def seq_dir(clip):
    return DATA / "data_seq" / "UAV123" / clip


def anno(clip):
    return DATA / "anno" / "UAV123" / f"{clip}.txt"


def assert_hints():
    """Guard: the hardcoded HINTS table must equal scope.hint_for on frame-0 GT."""
    for clip in CLIPS:
        gt = load_uav123_gt(anno(clip))
        box = gt[0]
        paths = sorted(seq_dir(clip).glob("*.jpg"))
        h, w = cv2.imread(str(paths[0])).shape[:2]
        got = scope.hint_for(box, w, h)
        assert got == HINTS[clip], (clip, got, HINTS[clip])
    print("[matrix] hint table verified against scope.hint_for", flush=True)


def run(mc, clip, hint, out_name):
    out = HERE / "runs" / out_name
    print(f"\n=== {out_name} (mc={mc} clip={clip} hint={hint!r}) ===", flush=True)
    cmd = [PY, SCRIPT, "--mc", mc, "--clip", clip,
           "--caption", CAPTIONS[clip], "--scope-hint", hint, "--out", str(out)]
    subprocess.run(cmd, check=True)


def main():
    assert_hints()
    smoke_only = "--smoke-only" in sys.argv
    run("none", "car10", HINTS["car10"], "smoke_cell_car10")     # plumbing smoke
    if smoke_only:
        return
    for clip in CLIPS:                                            # cell arm
        for rep in (1, 2):
            run("none", clip, HINTS[clip], f"cell_{clip}_r{rep}")
    for clip in CLIPS:                                            # cellbuf arm
        for rep in (1, 2):
            run("buf", clip, HINTS[clip], f"cellbuf_{clip}_r{rep}")
    for rep in (1, 2):                                            # wrong probe
        run("none", "car10", WRONG_HINT, f"wrong_car10_r{rep}")


if __name__ == "__main__":
    main()
