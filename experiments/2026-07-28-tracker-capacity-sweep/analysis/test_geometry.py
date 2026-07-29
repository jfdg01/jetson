"""Self-check for the search-window geometry. Run it: `python analysis/test_geometry.py`.

Exists because the geometry is written twice on purpose -- `device/trackers.py` for the arms and
`analysis/render_overlay.py` for the overlay that verifies them -- and a silent divergence between
the two would make the overlay agree with itself while disagreeing with the model. It also pins
the arithmetic to AsymTrack's `sample_target`, which is the only reason `sam2_f*` and `asym_b` are
comparable at all.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "device")]

from render_overlay import arm_factor, search_box  # noqa: E402
from trackers import crop_pad, search_window  # noqa: E402


def sample_target_window(xywh, factor):
    """`lib/train/data/processing_utils.py:30-39` transcribed, as the reference to match."""
    x, y, w, h = xywh
    crop_sz = math.ceil(math.sqrt(w * h) * factor)
    return round(x + 0.5 * w - crop_sz * 0.5), round(y + 0.5 * h - crop_sz * 0.5), crop_sz


def main() -> None:
    rng = np.random.default_rng(0)
    for _ in range(2000):
        x, y = rng.integers(-50, 1300, 2)
        w, h = rng.integers(1, 400, 2)
        f = float(rng.choice([2.0, 4.0, 5.0, 6.0]))
        ours = search_window([x, y, x + w, y + h], f)
        assert ours == sample_target_window((x, y, w, h), f), (x, y, w, h, f, ours)
        # host copy must agree with the device copy, or the overlay is not evidence
        assert search_box([x, y, x + w, y + h], f) == list(ours), (x, y, w, h, f)

    # the factor holds the target/window ratio constant, which is the whole point of the design
    for side in (10, 28, 100):
        _, _, s = search_window([0, 0, side, side], 5.0)
        assert s == side * 5, (side, s)

    # padding: what falls outside the frame is filled, what is inside is the frame, unshifted
    frame = rng.integers(0, 255, (720, 1280, 3), dtype=np.uint8)
    for win in [(-30, -30, 100), (1250, 700, 100), (600, 300, 200), (-500, -500, 64)]:
        out = crop_pad(frame, win)
        x, y, s = win
        assert out.shape == (s, s, 3), (win, out.shape)
        for (px, py) in [(0, 0), (s // 2, s // 2), (s - 1, s - 1)]:
            fx, fy = x + px, y + py
            want = frame[fy, fx] if (0 <= fx < 1280 and 0 <= fy < 720) else np.zeros(3, np.uint8)
            assert (out[py, px] == want).all(), (win, px, py, out[py, px], want)

    # a fully-outside window is all padding, not a wrapped or empty slice
    assert crop_pad(frame, (-500, -500, 64)).max() == 0

    assert arm_factor("sam2_f5") == 5.0 and arm_factor("asym_b") == 4.0
    assert arm_factor("sam2_c640") == 0.0 and arm_factor("sam2_t640") == 0.0
    print("geometry OK")


if __name__ == "__main__":
    main()
