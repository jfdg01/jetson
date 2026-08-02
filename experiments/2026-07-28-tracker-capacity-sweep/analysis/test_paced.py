#!/usr/bin/env python3
"""Self-check for the paced-stream protocol: the drop schedule and the zero-order-hold scoring.

The two halves have to agree or the mode measures nothing: `next_frame` decides WHICH frames the
arm sees, `held` decides what the consumer holds in between. Run it:

    analysis/test_paced.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "device")]
# run_arm imports the tracker registry, which needs sam2 and only exists on the device
sys.modules.setdefault("trackers", types.ModuleType("trackers"))

from aggregate import held  # noqa: E402
from run_arm import next_frame  # noqa: E402


def schedule(fps: float, ms: float, n: int) -> list[tuple[int, float]]:
    """Replay a constant-latency arm: the (frame, answer time) pairs a run would record."""
    rows, i, t = [(0, 0.0)], 0, 0.0
    while True:
        i, t = next_frame(i, t, fps)
        if i >= n:
            return rows
        t += ms / 1000
        rows.append((i, t))


def main() -> None:
    # fps=0 is the old parity mode: every frame, clock ignored
    assert [i for i, _ in schedule(0, 431, 6)] == [0, 1, 2, 3, 4, 5]

    # 30 fps, 431 ms: 12.93 frames per step, so it lands on 12 or 13 and never on both extremes
    fast = [i for i, _ in schedule(30, 431, 400)]
    # the first step is 1: init cost is not modelled here, so at t=0 the live frame is still 1
    step = {b - a for a, b in zip(fast[1:], fast[2:])}
    assert step == {12, 13} and fast[:2] == [0, 1], (step, fast[:3])
    assert 390 / 13 < len(fast) < 390 / 12 + 3, len(fast)

    # an arm faster than the stream sees every frame and idles: 20 ms at 30 fps (33.3 ms)
    every = schedule(30, 20, 50)
    assert [i for i, _ in every] == list(range(50))
    # ... and its answers land 20 ms after capture, not 33.3 -- the clock follows the stream
    assert abs(every[10][1] - (10 / 30 + 0.020)) < 1e-9, every[10]

    # zero-order hold. The answer for frame 1 lands at 1/30 + 0.431 = 0.4643 s = stream frame 13.9,
    # so frames 0..13 hold the frame-0 box and only frame 14 onwards sees the frame-1 one. That
    # 13-frame lag on top of the 13-frame drop is the whole point of the mode.
    rows = [{"i": i, "t": t, "box": [i, 0, 1, 1]} for i, t in schedule(30, 431, 60)]
    h = held(rows, 30, 60)
    assert [h[j]["i"] for j in (0, 13, 14, 26, 27)] == [0, 0, 1, 1, 13], [h[j]["i"] for j in range(30)]
    assert len(h) == 60 and all(h[j] for j in range(60)), "every stream frame must hold something"

    # a late first answer leaves the head of the stream holding NOTHING, and that has to score as a
    # loss rather than silently vanish -- an arm with a 2 s init is blind for 60 frames
    h = held([{"i": 0, "t": 2.0, "box": [0, 0, 1, 1]}], 30, 90)
    assert h[59] == {} and h[60]["box"], "hold must start at the answer, not at frame 0"

    print("ok")


if __name__ == "__main__":
    main()
