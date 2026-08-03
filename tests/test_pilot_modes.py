"""Pure-function guards for the demo UI's pilot + overlay additions.

Server-free by construction: everything here is a plain function in
runners/carla_debug_ui.py, so `make test` runs it with no CARLA, no SITL and no
Jetson. The stateful half (the catch-up gate, follow-mode cycling, AUTO refusing
to run without a copter) is asserted through the real widgets in the UI's own
`--selftest`, which needs a CARLA to build a client at all.

The DELIVER stage came out of the panel on 2026-08-03, and with it the two checks
that lived here: the `deliver` timing format and the amber maintained-vs-delivered
overlay. Their replacements below cover the same two mechanisms (a missing stage
must not print as 0.00; the overlay colour must track lock state).

The sign asserts are the point. A flipped key->NED mapping does not crash, it flies
the copter away from the target, and in a sim that reads as "the follow does not
work" rather than as a typo.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "runners"))

carla = pytest.importorskip("carla", reason="carla egg needed to import the UI module")
ui = pytest.importorskip("carla_debug_ui")
cr = pytest.importorskip("carla_render")


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
    # v is a SPEED: every key combination flies at |v|, so the slider reads true
    for keys in ({"w"}, {"w", "d"}, {"w", "d", "e"}, {"a", "q"}, {"s", "a"}):
        assert abs(math.hypot(*ui.manual_velocity(keys, v)) - v) < 1e-9, keys
    r = v / math.sqrt(2)
    assert ui.manual_velocity({"w", "d"}, v) == pytest.approx((r, r, 0.0))


def test_manual_velocity_is_relative_to_the_view():
    """w flies toward the TOP OF THE SCREEN at whatever yaw the view is rotated to.

    The nadir camera rotates (arrow keys yaw the gimbal), and a world-absolute wasd
    then steers sideways or backwards on screen -- which reads as the controls being
    broken, not as a frame mismatch. So the check is stated in screen terms and run
    through the real projection: push w, and the copter's velocity must move the
    scene DOWN the screen (the drone goes up-screen), at every yaw.
    """
    v = 5.0
    ground = carla.Location(cr.BASE_N, cr.BASE_E, 0.0)   # right under the start pose
    for yaw in (0.0, 90.0, 180.0, -90.0, 37.0):
        vn, ve, vd = ui.manual_velocity({"w"}, v, yaw)
        assert abs(vd) < 1e-9
        assert abs((vn ** 2 + ve ** 2) ** 0.5 - v) < 1e-9, "yaw must not change speed"
        # where that velocity puts the camera, one second on, in CARLA world axes
        here = cr.ned_to_carla(0.0, 0.0, -50.0, np.radians(yaw))
        there = cr.ned_to_carla(vn, ve, -50.0, np.radians(yaw))
        # a point on the ground under the start pose: it must slide toward the
        # bottom of the frame (screen y grows downward) and not sideways
        u0, w0 = ui.project(ground, here)
        u1, w1 = ui.project(ground, there)
        assert w1 > w0 + 1.0, f"yaw {yaw}: w must move the scene down-screen"
        assert abs(u1 - u0) < 1.0, f"yaw {yaw}: w must not slide the scene sideways"
    # and d is screen-right: the scene slides left
    vn, ve, _ = ui.manual_velocity({"d"}, v, 37.0)
    here = cr.ned_to_carla(0.0, 0.0, -50.0, np.radians(37.0))
    there = cr.ned_to_carla(vn, ve, -50.0, np.radians(37.0))
    assert ui.project(ground, there)[0] < ui.project(ground, here)[0]


def test_missing_stage_reads_as_missing():
    """A stage that has not run must not print as 0.00 -- one of those is a bug."""
    assert ui._f("catch-up {:.1f} s", 6.5) == "catch-up 6.5 s"
    assert ui._f("catch-up {:.1f} s", 0.0) == "catch-up 0.0 s"
    assert ui._f("catch-up {:.1f} s", None) == "catch-up --"
    assert ui._f("ground {:.0f} ms", None) == "ground --"


def _colours(img):
    return {tuple(int(c) for c in px) for px in img.reshape(-1, 3)} - {(0, 0, 0)}


def test_locked_and_adrift_boxes_are_drawn_differently():
    """The one overlay distinction left, checked in pixels rather than by reading code.

    Green = on target, red = adrift. It is the only thing on screen that says whether
    the carry still has the car, so a colour that stopped tracking `locked` would be
    invisible in review and load-bearing in the demo.
    """
    box = (20, 20, 60, 60)
    locked = ui.draw_overlay(np.zeros((100, 100, 3), np.uint8), box, "x", True)
    adrift = ui.draw_overlay(np.zeros((100, 100, 3), np.uint8), box, "x", False)
    assert (0, 255, 0) in _colours(locked), "an on-target box is green"
    assert (0, 255, 0) not in _colours(adrift), "an adrift box must not read as locked"
    assert (0, 0, 255) in _colours(adrift), "an adrift box is red"
    # at least 2 px thick: a 1 px box was invisible on the live feed once
    assert (locked == np.array([0, 255, 0])).all(2).sum() > 40, "too faint"


def test_no_box_draws_nothing():
    blank = np.zeros((10, 10, 3), np.uint8)
    assert not _colours(ui.draw_overlay(blank, None, "x", True))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
