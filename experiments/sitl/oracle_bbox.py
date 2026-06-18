"""
Oracle bounding-box source for Phase B.

Converts SITL world-state (copter NED + attitude, rover NED) into pixel
bounding boxes via a pinhole camera model.  No vision involved — this is the
perfect-perception upper bound that Phase C replaces with the VLM.

Camera convention (downward-facing, body-mounted):
    cam_x = body_y  (right  → pixel right / +u)
    cam_y = -body_x (aft    → pixel down  / +v;  "forward" appears at top)
    cam_z = body_z  (down   → optical axis; must be > 0 for point to be visible)

ArduPilot body frame: x=forward, y=right, z=down.
NED→body rotation: Rx(roll) @ Ry(pitch) @ Rz(yaw).

Unit test (run with: python experiments/sitl/oracle_bbox.py):
    Rover directly below hovering copter → box centred at (W/2, H/2).
"""

import math
import numpy as np

# Camera intrinsics (fixed for all Phase B/C runs — record next to results)
IMG_W = 640
IMG_H = 480
FOV_H_DEG = 60.0
FOCAL_PX = (IMG_W / 2) / math.tan(math.radians(FOV_H_DEG / 2))  # ≈ 554 px

# Simulated target physical size (ArduRover default vehicle ≈ car)
TARGET_LEN_M = 4.0   # body length (maps to cam_y axis)
TARGET_WID_M = 2.0   # body width  (maps to cam_x axis)

# Minimum depth to avoid division-by-zero
MIN_DEPTH_M = 0.5


def _ned2body(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """3×3 rotation matrix: NED vector → body vector (ZYX Euler, intrinsic)."""
    cr, sr = math.cos(roll),  math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw),   math.sin(yaw)
    # R = Rx(roll) @ Ry(pitch) @ Rz(yaw)
    return np.array([
        [ cp*cy,          cp*sy,         -sp     ],
        [ sr*sp*cy-cr*sy, sr*sp*sy+cr*cy, sr*cp  ],
        [ cr*sp*cy+sr*sy, cr*sp*sy-sr*cy, cr*cp  ],
    ])


def project(
    copter_ned: tuple,
    rover_ned: tuple,
    roll: float,
    pitch: float,
    yaw: float,
) -> dict | None:
    """
    Project rover world position into copter's downward camera.

    Args:
        copter_ned: (N, E, D) metres, copter position in NED
        rover_ned:  (N, E, D) metres, rover  position in NED
        roll, pitch, yaw: copter attitude in radians (ArduPilot convention)

    Returns:
        dict(cx, cy, w, h) in pixel coordinates, or None if out-of-frame.
    """
    rel = np.array(rover_ned) - np.array(copter_ned)   # NED offset
    body = _ned2body(roll, pitch, yaw) @ rel             # body frame

    # cam_x=body_y, cam_y=-body_x, cam_z=body_z
    cam_x = body[1]
    cam_y = -body[0]
    cam_z = body[2]   # positive = below copter = in front of downward camera

    if cam_z < MIN_DEPTH_M:
        return None  # rover above or too close to the lens

    u = FOCAL_PX * cam_x / cam_z + IMG_W / 2
    v = FOCAL_PX * cam_y / cam_z + IMG_H / 2

    half_w = FOCAL_PX * (TARGET_WID_M / 2) / cam_z
    half_h = FOCAL_PX * (TARGET_LEN_M / 2) / cam_z

    x1, y1 = u - half_w, v - half_h
    x2, y2 = u + half_w, v + half_h

    # Clip to image bounds
    x1c, y1c = max(0.0, x1), max(0.0, y1)
    x2c, y2c = min(float(IMG_W), x2), min(float(IMG_H), y2)

    if x2c <= x1c or y2c <= y1c:
        return None  # fully outside frame

    return {
        "cx": (x1c + x2c) / 2,
        "cy": (y1c + y2c) / 2,
        "w":  x2c - x1c,
        "h":  y2c - y1c,
    }


def project_unclipped(
    copter_ned: tuple,
    rover_ned: tuple,
    roll: float,
    pitch: float,
    yaw: float,
) -> dict | None:
    """Unclipped pinhole projection: TRUE target centre + full box size in px.

    Identical optics to project(), but the centre/size are NOT clipped to the
    frame, so the returned centre is the target's true pixel position even when
    the box runs off-screen. project() returns the clipped-box centre, which
    underestimates pixel motion for a large (low-altitude) box straddling an
    edge — use this one for the T0c cadence-vs-dynamics budget.

    Returns dict(cx, cy, w, h, visible) or None if behind / too close to lens.
    `visible` is True when the unclipped box overlaps the image rectangle.
    """
    rel = np.array(rover_ned) - np.array(copter_ned)
    body = _ned2body(roll, pitch, yaw) @ rel

    cam_x = body[1]
    cam_y = -body[0]
    cam_z = body[2]

    if cam_z < MIN_DEPTH_M:
        return None

    u = FOCAL_PX * cam_x / cam_z + IMG_W / 2
    v = FOCAL_PX * cam_y / cam_z + IMG_H / 2
    half_w = FOCAL_PX * (TARGET_WID_M / 2) / cam_z
    half_h = FOCAL_PX * (TARGET_LEN_M / 2) / cam_z

    visible = (u + half_w > 0) and (u - half_w < IMG_W) and \
              (v + half_h > 0) and (v - half_h < IMG_H)
    return {"cx": u, "cy": v, "w": 2 * half_w, "h": 2 * half_h, "visible": visible}


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def _test_center():
    """Rover directly below hovering copter → box at image centre."""
    bbox = project(
        copter_ned=(0.0, 0.0, -10.0),   # 10 m above origin
        rover_ned=(0.0, 0.0,   0.0),    # on the ground at origin
        roll=0.0, pitch=0.0, yaw=0.0,
    )
    assert bbox is not None, "Expected visible bbox, got None"
    tol = 1.0  # pixel
    assert abs(bbox["cx"] - IMG_W / 2) < tol, f"cx={bbox['cx']:.1f}, expected {IMG_W/2}"
    assert abs(bbox["cy"] - IMG_H / 2) < tol, f"cy={bbox['cy']:.1f}, expected {IMG_H/2}"
    print(f"  center test PASS  cx={bbox['cx']:.1f}  cy={bbox['cy']:.1f}  "
          f"w={bbox['w']:.1f}  h={bbox['h']:.1f}")


def _test_offset_north():
    """Rover 5 m north of nadir → box shifts toward top of image."""
    bbox_ctr = project((0,0,-10), (0,0,0),  0,0,0)
    bbox_off = project((0,0,-10), (5,0,0),  0,0,0)
    assert bbox_off is not None
    # north offset: body_x>0 → cam_y = -body_x < 0 → v < H/2 (toward top)
    assert bbox_off["cy"] < bbox_ctr["cy"], \
        f"Expected cy to decrease with north offset, got {bbox_off['cy']:.1f} vs {bbox_ctr['cy']:.1f}"
    print(f"  north-offset test PASS  cy_ctr={bbox_ctr['cy']:.1f}  cy_off={bbox_off['cy']:.1f}")


def _test_above_copter():
    """Rover above copter → None (cam_z < 0)."""
    bbox = project((0,0,-10), (0,0,-20), 0,0,0)
    assert bbox is None, f"Expected None for rover above copter, got {bbox}"
    print("  above-copter test PASS  (returns None)")


def _test_altitude_scaling():
    """Box area scales as 1/altitude²."""
    b10 = project((0,0,-10), (0,0,0), 0,0,0)
    b20 = project((0,0,-20), (0,0,0), 0,0,0)
    assert b10 is not None and b20 is not None
    ratio = (b10["w"] * b10["h"]) / (b20["w"] * b20["h"])
    assert abs(ratio - 4.0) < 0.1, f"Expected area ratio 4.0, got {ratio:.3f}"
    print(f"  altitude-scaling test PASS  area ratio = {ratio:.3f} (expected 4.0)")


def _test_yaw():
    """90° yaw rotates but does not shift a centred target."""
    b0  = project((0,0,-10), (0,0,0), 0, 0, 0)
    b90 = project((0,0,-10), (0,0,0), 0, 0, math.pi/2)
    tol = 1.0
    assert abs(b0["cx"]  - b90["cx"])  < tol, "cx shifted with yaw (no lateral offset)"
    assert abs(b0["cy"]  - b90["cy"])  < tol, "cy shifted with yaw (no lateral offset)"
    print(f"  yaw test PASS  cx unchanged={b90['cx']:.1f}  cy unchanged={b90['cy']:.1f}")


if __name__ == "__main__":
    print("oracle_bbox unit tests:")
    _test_center()
    _test_offset_north()
    _test_above_copter()
    _test_altitude_scaling()
    _test_yaw()
    print("all oracle_bbox tests passed")
