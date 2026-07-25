"""Pure-function guards for the demo UI's pilot + delivery additions.

Server-free by construction: everything here is a plain function in
runners/carla_debug_ui.py, so `make test` runs it with no CARLA, no SITL and no
Jetson. The stateful half (WARM/COLD delivery, follow-mode cycling, AUTO refusing
to run without a copter) is asserted through the real widgets in the UI's own
`--selftest`, which needs a CARLA to build a client at all.

The sign asserts are the point. A flipped key->NED mapping does not crash, it flies
the copter away from the target, and in a sim that reads as "the follow does not
work" rather than as a typo.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "runners"))

carla = pytest.importorskip("carla", reason="carla egg needed to import the UI module")
ui = pytest.importorskip("carla_debug_ui")


def test_manual_velocity_signs():
    """North-up nadir: w is north, d is east, e is UP (vd is down-positive)."""
    v = 5.0
    assert ui.manual_velocity({"w"}, v) == (v, 0.0, 0.0)
    assert ui.manual_velocity({"s"}, v) == (-v, 0.0, 0.0)
    assert ui.manual_velocity({"d"}, v) == (0.0, v, 0.0)
    assert ui.manual_velocity({"a"}, v) == (0.0, -v, 0.0)
    assert ui.manual_velocity({"q"}, v) == (0.0, 0.0, v)     # down
    assert ui.manual_velocity({"e"}, v) == (0.0, 0.0, -v)    # up
    assert ui.manual_velocity(set(), v) == (0.0, 0.0, 0.0)
    # opposites cancel rather than latching whichever was pressed last
    assert ui.manual_velocity({"w", "s"}, v) == (0.0, 0.0, 0.0)
    # diagonals compose, and nothing is normalised -- the cap is per-axis
    assert ui.manual_velocity({"w", "d"}, v) == (v, v, 0.0)


def test_missing_stage_reads_as_missing():
    """A stage that has not run must not print as 0.00 -- one of those is a bug."""
    assert ui._f("deliver {:.2f} s", 0.04) == "deliver 0.04 s"
    assert ui._f("deliver {:.2f} s", 0.0) == "deliver 0.00 s"
    assert ui._f("deliver {:.2f} s", None) == "deliver --"
    assert ui._f("ground {:.0f} ms", None) == "ground --"


def _colours(img):
    return {tuple(int(c) for c in px) for px in img.reshape(-1, 3)} - {(0, 0, 0)}


def test_maintained_box_is_drawn_differently_from_a_delivered_one():
    """The WARM overlay distinction, checked in pixels rather than by reading code.

    A maintained box (nobody has asked for it yet) must not be paintable as the
    green "this is your target" box -- that is the one thing an operator watching a
    warm-start demo has to be able to tell apart.
    """
    box = (20, 20, 60, 60)
    delivered = ui.draw_overlay(np.zeros((100, 100, 3), np.uint8), box, "x", True)
    maintained = ui.draw_overlay(np.zeros((100, 100, 3), np.uint8), box, "x", True,
                                 delivered=False)
    assert (0, 255, 0) in _colours(delivered), "a delivered on-target box is green"
    assert (0, 255, 0) not in _colours(maintained), "maintained must not read as locked"
    assert _colours(maintained), "maintained still has to be visible"
    # and a delivered box that has drifted is red, not green (unchanged behaviour)
    adrift = ui.draw_overlay(np.zeros((100, 100, 3), np.uint8), box, "x", False)
    assert (0, 0, 255) in _colours(adrift)


def test_no_box_draws_nothing():
    blank = np.zeros((10, 10, 3), np.uint8)
    assert not _colours(ui.draw_overlay(blank, None, "x", True))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
