"""
Cascade PID controller for drone-follows-target.

Outer loop (runs at tracker/oracle rate, ~25 Hz Phase B / ~1.2 Hz Phase C):
    Inputs:  bbox centre (cx, cy) and area from tracker
    Outputs: velocity setpoints (vx, vy, yaw_rate) in body frame

Inner loop: autopilot attitude controller (ArduPilot, ~400 Hz).

All gains are P-only for Phase B validation.  Integral and derivative terms
are stub slots for Stage 2 tuning — do not add them here until Phase B
establishes a working baseline.

Coordinate convention (body frame, ArduPilot NED-derived):
    vx > 0  →  fly forward  (closes range to target ahead)
    vy > 0  →  fly right
    vz > 0  →  fly down  (not used here — altitude held by autopilot)
    yaw_rate > 0 → yaw right (CW from above)

Error definitions:
    error_yaw   = cx − W/2   (px, positive → target right of centre)
    error_lat   = cy − H/2   (px, positive → target below centre = forward)
    error_range = A_ref − A_bbox  (px², positive → too far from target)

Unit test: python experiments/sitl/cascade_pid.py
"""

import math

# Image dimensions (must match oracle_bbox.py)
IMG_W = 640
IMG_H = 480

# Reference bbox area at desired standoff (4m × 2m car at 10 m AGL ≈ 6600 px²)
# Derived: w≈111px, h≈222px → area≈24642 px².  Use as-measured after first run.
# Placeholder value — calibrate from Phase B run 1 telemetry.
A_REF_PX2 = 24000.0

# Velocity limits (m/s and rad/s) — conservative for Phase B
MAX_VX      =  3.0   # m/s forward/backward
MAX_VY      =  3.0   # m/s lateral
MAX_YAW     =  1.0   # rad/s
MAX_VZ      =  0.0   # m/s (altitude control disabled, held by autopilot)

# P gains — tuned for SITL; adjust after Phase B run 1
KP_YAW   = 0.003   # rad/s per pixel
KP_LAT   = 0.02    # m/s per pixel
KP_RANGE = 0.0001  # m/s per px²  (area error → forward speed)


class CascadePID:
    """
    Stateless P controller (one instance per trial run).

    Call compute() once per tracker update to get velocity setpoints.
    """

    def __init__(
        self,
        kp_yaw:   float = KP_YAW,
        kp_lat:   float = KP_LAT,
        kp_range: float = KP_RANGE,
        a_ref:    float = A_REF_PX2,
        img_w:    int   = IMG_W,
        img_h:    int   = IMG_H,
    ):
        self.kp_yaw   = kp_yaw
        self.kp_lat   = kp_lat
        self.kp_range = kp_range
        self.a_ref    = a_ref
        self.img_w    = img_w
        self.img_h    = img_h

    def compute(self, bbox: dict | None) -> dict:
        """
        Args:
            bbox: dict with keys cx, cy, w, h (pixel coords), or None if no track.

        Returns:
            dict(vx, vy, vz, yaw_rate) in m/s and rad/s, body frame.
            All zeros if bbox is None (hover in place).
        """
        if bbox is None:
            return {"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_rate": 0.0}

        cx, cy = bbox["cx"], bbox["cy"]
        area   = bbox["w"] * bbox["h"]

        error_yaw   = cx - self.img_w / 2   # +ve → target right of centre
        error_lat   = cy - self.img_h / 2   # +ve → target below centre

        # Camera convention (downward-facing, body-mounted):
        #   body_y → cam_x → image u (right)  : error_yaw drives vy
        #   body_x → cam_y = -body_x → image v: error_lat < 0 means target is NORTH
        #     → fly north (vx > 0) to centre it → vx = -Kp * error_lat
        vy       = _clamp(self.kp_lat * error_yaw,   -MAX_VY,  MAX_VY)
        vx       = _clamp(-self.kp_lat * error_lat,  -MAX_VX,  MAX_VX)
        yaw_rate = _clamp(self.kp_yaw * error_yaw,   -MAX_YAW, MAX_YAW)

        return {"vx": vx, "vy": vy, "vz": 0.0, "yaw_rate": yaw_rate}

    def pixel_errors(self, bbox: dict | None) -> dict:
        """Return raw pixel errors for logging (not the velocity outputs)."""
        if bbox is None:
            return {"error_yaw_px": None, "error_lat_px": None, "error_range_px2": None}
        return {
            "error_yaw_px":    bbox["cx"] - self.img_w / 2,
            "error_lat_px":    bbox["cy"] - self.img_h / 2,
            "error_range_px2": self.a_ref - bbox["w"] * bbox["h"],
        }


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def _test_zero_error():
    pid = CascadePID()
    bbox = {"cx": IMG_W / 2, "cy": IMG_H / 2, "w": 110.0, "h": 224.0}
    sp = pid.compute(bbox)
    assert abs(sp["yaw_rate"]) < 1e-9
    assert abs(sp["vy"]) < 1e-9
    # range error will be non-zero (area != A_REF_PX2), vx may be non-zero
    print(f"  zero-error test PASS  vx={sp['vx']:.3f}  vy={sp['vy']:.3f}  "
          f"yaw_rate={sp['yaw_rate']:.4f}")


def _test_target_right():
    pid = CascadePID()
    bbox = {"cx": IMG_W / 2 + 100, "cy": IMG_H / 2, "w": 110.0, "h": 224.0}
    sp = pid.compute(bbox)
    assert sp["yaw_rate"] > 0, "yaw_rate should be positive when target is right"
    assert sp["vy"] > 0,       "vy should be positive when target is right"
    assert abs(sp["vx"]) < 1e-9, "vx should be 0 when target is centred vertically"
    print(f"  target-right test PASS  yaw_rate={sp['yaw_rate']:.4f}  vy={sp['vy']:.3f}  vx={sp['vx']:.3f}")


def _test_target_above():
    """Target at top of image (north of copter) → vx > 0 (fly forward/north)."""
    pid = CascadePID()
    bbox = {"cx": IMG_W / 2, "cy": IMG_H / 2 - 100, "w": 110.0, "h": 224.0}
    sp = pid.compute(bbox)
    assert sp["vx"] > 0, f"vx should be positive (fly north) when target is above centre, got {sp['vx']}"
    assert abs(sp["vy"]) < 1e-9, "vy should be 0 when target is horizontally centred"
    print(f"  target-above test PASS  vx={sp['vx']:.3f} (fly north)")


def _test_none_bbox():
    pid = CascadePID()
    sp = pid.compute(None)
    assert all(v == 0.0 for v in sp.values()), "all setpoints should be 0 when no track"
    print("  none-bbox test PASS")


def _test_clamp():
    pid = CascadePID()
    # Push error_yaw to 10000 px — should clamp to MAX_YAW
    bbox = {"cx": IMG_W / 2 + 10000, "cy": IMG_H / 2, "w": 100.0, "h": 100.0}
    sp = pid.compute(bbox)
    assert abs(sp["yaw_rate"]) <= MAX_YAW + 1e-9, f"yaw_rate not clamped: {sp['yaw_rate']}"
    print(f"  clamp test PASS  yaw_rate clamped to {sp['yaw_rate']:.4f} (max={MAX_YAW})")


if __name__ == "__main__":
    print("cascade_pid unit tests:")
    _test_zero_error()
    _test_target_right()
    _test_target_above()
    _test_none_bbox()
    _test_clamp()
    print("all cascade_pid tests passed")
