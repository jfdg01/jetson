#!/usr/bin/env python3
"""Self-check for `Sam2CropArm(lead=True)`: does the window actually get ahead of the target?

Geometry only -- the inner SAM2 is stubbed with an oracle that returns the true box, so what is
under test is where the window is placed, not what the model finds in it. Run it:

    analysis/test_lead.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "device"))
import trackers  # noqa: E402

STEP = 40   # px per step; a fast target under a 4-frame drop, well inside the 512 window
START = 400  # far enough from the left border that `crop_window` is not clamping the window


class Oracle:
    """Stands in for SAM2: always finds the target, wherever the window happens to be."""

    def __init__(self, *a, **k):
        self.conf, self.i, self.owner = 1.0, 0, None

    def _box(self):
        # truth in FULL-FRAME coords; the arm hands us a crop, so subtract the window origin
        return [START + STEP * self.i, 300.0, START + STEP * self.i + 20, 320.0]

    def init(self, sub, box):
        return box, []

    def step(self, sub):
        self.i += 1
        # read the window the arm placed for THIS frame, not the previous one -- `_crop` rewrites
        # `arm.win` inside `step`, and using the stale value was what made this test lie
        b, (x, y, _) = self._box(), self.owner.win
        return [b[0] - x, b[1] - y, b[2] - x, b[3] - y], []


def run(lead: bool) -> list[float]:
    """Signed miss of the window centre against the target centre, per step."""
    trackers.Sam2Arm = Oracle
    arm = trackers.Sam2CropArm("stub", 512, lead=lead)
    arm.inner.owner = arm
    frame = np.zeros((720, 1280, 3), np.uint8)
    arm.init(frame, [float(START), 300.0, START + 20.0, 320.0])
    out = []
    for _ in range(8):
        arm.step(frame)
        cx = arm.win[0] + arm.win[2] / 2
        out.append(cx - (arm.last[0] + arm.last[2]) / 2)
    return out


def main() -> None:
    real = trackers.Sam2Arm
    try:
        off, on = run(False), run(True)
    finally:
        trackers.Sam2Arm = real

    # Zero-order: the window is always one step BEHIND the target it then finds. `crop_window`
    # slides the window to stay inside the frame, so only check while it is not clamped -- at 512
    # wide in a 1280 frame that holds until the centre passes 1024, i.e. 6 steps from START.
    assert all(o < -STEP / 2 for o in off[:6]), off
    # First-order: with a constant velocity the prediction is exact, so the window is CENTRED --
    # from the SECOND step on, because two hits are needed before there is a velocity at all
    assert abs(on[0] - off[0]) < 1e-6, (on[0], off[0])
    assert all(abs(o) < 1e-6 for o in on[1:6]), on

    print("ok")


if __name__ == "__main__":
    main()
