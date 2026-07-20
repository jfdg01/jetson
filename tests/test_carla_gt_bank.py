"""Pure-function checks for the CARLA GT bank. No server, no GPU, no display.

The decisive one is test_projected_area_matches_analytic: it is the assert that
would have caught the EnvironmentObject world-vs-local transform bug, which
produces a perfectly well-formed box in the wrong place.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

carla = pytest.importorskip("carla")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runners"))

from carla_gt_bank import (  # noqa: E402
    W, H, FOV, analytic_area, box_area, clip_to_frame, dominant_frac,
    mean_absdiff, nadir, veh_fill, verts_to_box,
)


def _box_verts(cx, cy, cz, ex, ey, ez):
    """The 8 world-space corners of an axis-aligned box, CARLA extent convention
    (extent is the HALF-size)."""
    return [carla.Location(x=cx + sx * ex, y=cy + sy * ey, z=cz + sz * ez)
            for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def test_projected_area_matches_analytic():
    """A nadir camera at altitude z over a box of known footprint projects a
    predictable pixel area. This is the check that distinguishes a correctly
    placed box from a plausible-looking one built from the wrong transform."""
    ex, ey, ez = 2.50, 1.05, 0.77          # a real SM_ChargerParked extent
    for alt in (25.0, 40.0, 60.0, 85.0, 120.0):
        verts = _box_verts(0.0, 0.0, ez, ex, ey, ez)
        box, n = verts_to_box(verts, nadir(0.0, 0.0, alt))
        assert n == 8, f"all 8 corners should project at {alt} m, got {n}"
        pred = analytic_area((ex, ey), alt - ez)
        got = box_area(box)
        assert 0.75 <= got / pred <= 1.35, (
            f"alt {alt}: projected {got:.0f} px^2 vs analytic {pred:.0f} px^2")


def test_wrong_transform_is_caught():
    """The actual bug: an EnvironmentObject box is world-space, so passing the
    object's own transform doubles its coordinates. The box still forms, still
    shrinks monotonically with altitude -- and lands somewhere else entirely.
    Monotonicity alone would pass it; the analytic check must not."""
    ex, ey, ez = 2.50, 1.05, 0.77
    cx, cy = -51.0, 166.5                   # a real parked-car location
    cam = nadir(cx, cy, 60.0)
    right = verts_to_box(_box_verts(cx, cy, ez, ex, ey, ez), cam)[0]
    doubled = verts_to_box(_box_verts(2 * cx, 2 * cy, ez, ex, ey, ez), cam)[0]
    assert clip_to_frame(right) is not None, "correct box should be in frame"
    assert clip_to_frame(doubled) is None, (
        "doubled-coordinate box should fall outside the frame -- if it does not, "
        "this test no longer guards the bug it was written for")


def test_monotonic_shrink_alone_is_weak():
    """Why the analytic check exists: the WRONG box shrinks monotonically too."""
    ex, ey, ez = 2.50, 1.05, 0.77
    areas = []
    for alt in (25.0, 40.0, 60.0, 85.0, 120.0):
        # a box at twice the true offset from the camera axis still shrinks
        b, _ = verts_to_box(_box_verts(4.0, 4.0, ez, ex, ey, ez), nadir(0, 0, alt))
        areas.append(box_area(b))
    assert all(a > b for a, b in zip(areas, areas[1:])), (
        "a misplaced box still shrinks with altitude, which is exactly why "
        "monotonicity is not sufficient")


def test_partial_projection_is_kept_not_dropped():
    """Hazard 2.3f: a target close enough to put vertices behind the camera plane
    must still produce a box for CAPTURE, with n_proj recording the truncation.
    carla_debug_ui.actor_box returns None here on purpose; this must not."""
    # camera at 2 m, box straddling the camera plane
    verts = _box_verts(0.0, 0.0, 2.0, 2.5, 1.05, 3.0)
    box, n = verts_to_box(verts, nadir(0.0, 0.0, 2.0))
    assert box is not None, "a partly-behind-camera box must still be captured"
    assert n < 8, f"expected a truncated projection, got all {n}"


def test_clip_to_frame():
    assert clip_to_frame((10, 10, 20, 20)) == (10, 10, 20, 20)
    assert clip_to_frame((-50, -50, -10, -10)) is None
    assert clip_to_frame((W - 5, H - 5, W + 50, H + 50)) == (W - 5, H - 5, W, H)
    assert clip_to_frame((-10, -10, 30, 30)) == (0, 0, 30, 30)


def test_veh_fill():
    tags = np.zeros((H, W), np.uint8)
    car = int(carla.CityObjectLabel.Car)
    tags[100:140, 200:260] = car
    assert veh_fill(tags, (200, 100, 260, 140)) == pytest.approx(1.0)
    assert veh_fill(tags, (0, 0, 60, 40)) == pytest.approx(0.0)
    # half the box on the car, half off -- the occlusion proxy must read partial
    assert veh_fill(tags, (200, 100, 320, 140)) == pytest.approx(0.5, abs=0.02)
    assert veh_fill(tags, (-100, -100, -50, -50)) is None


def test_blank_render_detector():
    assert dominant_frac(np.zeros((H, W, 3), np.uint8)) == 1.0
    rng = np.random.default_rng(0)
    assert dominant_frac(rng.integers(0, 255, (H, W, 3), dtype=np.uint8)) < 0.99


def test_mean_absdiff_is_signless():
    a = np.zeros((4, 4, 3), np.uint8)
    b = np.full((4, 4, 3), 10, np.uint8)
    assert mean_absdiff(a, b) == 10.0
    assert mean_absdiff(b, a) == 10.0          # must not cancel via uint8 wraparound
    assert mean_absdiff(a, a) == 0.0


def test_nadir_points_down():
    """The sign that aimed Phase C at the sky for a month."""
    assert nadir(0, 0, 60).rotation.pitch == -90.0
