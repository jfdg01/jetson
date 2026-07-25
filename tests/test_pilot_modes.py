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
    # diagonals compose, and nothing is normalised -- the cap is per-axis
    assert ui.manual_velocity({"w", "d"}, v) == (v, v, 0.0)


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
    # visible means AMBER and at least 2 px thick: it was grey and 1 px once and the
    # operator could not see it, which is the bug this assert exists to keep fixed
    assert (63, 160, 224) in _colours(maintained), "maintained is the amber 'not yours'"
    assert (maintained == np.array([63, 160, 224])).all(2).sum() > 40, "too faint"
    # brackets, not a closed rectangle: the middle of each edge stays background
    assert not _colours(maintained[40:41, 20:61]), "the box must not be closed"
    # and a delivered box that has drifted is red, not green (unchanged behaviour)
    adrift = ui.draw_overlay(np.zeros((100, 100, 3), np.uint8), box, "x", False)
    assert (0, 0, 255) in _colours(adrift)


def test_graph_draws_and_survives_holes():
    """The sparkline: right shape, no data is a message, and a None lane is skipped."""
    empty = ui.draw_graph([], 300)
    assert empty.shape == (ui.PLOT_H, 300, 3)
    assert _colours(empty), "empty must still SAY it is empty"
    hist = [(5.0 + i % 3, i, None if i < 5 else (i % 10) / 10.0,
             "maintaining" if i < 5 else "live") for i in range(40)]
    img = ui.draw_graph(hist, 300)
    assert img.shape == (ui.PLOT_H, 300, 3)
    # the three lane colours plus both ribbon states have to be on the canvas
    for c in ((95, 191, 63), (63, 160, 224), (224, 160, 63)):
        assert c in _colours(img), c


def test_no_box_draws_nothing():
    blank = np.zeros((10, 10, 3), np.uint8)
    assert not _colours(ui.draw_overlay(blank, None, "x", True))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
