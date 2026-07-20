"""ASSIST aim law, headless. No CARLA, no Tk -- pure geometry."""
import importlib.util
import math
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "carla_debug_ui", Path(__file__).resolve().parents[1] / "runners/carla_debug_ui.py")
ui = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ui)

W, H = ui.CAM_W, ui.CAM_H
DT = 1 / 60
F = W / (2 * math.tan(math.radians(ui.CAM_FOV) / 2))


def box_at(cx, cy, s=40):
    return [cx - s, cy - s, cx + s, cy + s]


def test_centred_box_asks_for_nothing():
    dyaw, dpitch = ui.center_delta(box_at(W / 2, H / 2))
    assert abs(dyaw) < 1e-9 and abs(dpitch) < 1e-9


def test_turns_toward_the_target():
    # +yaw is right, +pitch is up, image y grows downward
    assert ui.center_delta(box_at(W * 0.9, H / 2))[0] > 0
    assert ui.center_delta(box_at(W * 0.1, H / 2))[0] < 0
    assert ui.center_delta(box_at(W / 2, H * 0.9))[1] < 0
    assert ui.center_delta(box_at(W / 2, H * 0.1))[1] > 0


def test_center_delta_is_the_full_angle():
    """It returns the whole correction, not a step -- ease() does the pacing."""
    assert ui.center_delta(box_at(W * 0.9, H / 2))[0] == math.degrees(
        math.atan2(W * 0.4, F))


def test_ease_is_a_pan_not_a_snap():
    want = ui.center_delta(box_at(W * 0.9, H / 2))
    assert 0 < ui.ease(want, DT)[0] < want[0] * 0.2


def test_ease_never_overshoots_however_long_the_tick():
    """min(1.0, rate*dt): a 10 s stall spends the remainder exactly, no swing past."""
    want = ui.center_delta(box_at(W * 0.9, H / 2))
    assert want[0] == max(ui.ease(want, dt)[0] for dt in (DT, 0.5, 10.0, 1e9))


def _spend(box, ticks, dt=DT):
    """Charge the budget from one box, then spend it -- what fly() does per tick."""
    rem, moved = list(ui.center_delta(box)), 0.0
    for _ in range(ticks):
        dyaw, dpitch = ui.ease(rem, dt)
        moved += dyaw
        rem[0] -= dyaw
        rem[1] -= dpitch
    return moved


def test_a_frozen_box_is_worth_one_correction():
    """The occlusion bug. The box is in PIXELS: turning the camera does not change
    it, so a per-tick law integrates a constant error and sweeps the view away
    until the target is out of frame and can never be re-found. Charging the budget
    once per new box bounds the whole occlusion at the one measured angle."""
    want = ui.center_delta(box_at(W * 0.9, H / 2))[0]
    for seconds in (1, 3, 10, 60):        # target stays occluded this long
        moved = _spend(box_at(W * 0.9, H / 2), int(seconds * 60))
        assert moved <= want + 1e-9, f"{seconds}s of a frozen box moved {moved:.1f} deg"


def test_the_correction_does_get_spent():
    """The other half: bounded must not mean inert -- one box centres the target."""
    want = ui.center_delta(box_at(W * 0.9, H / 2))[0]
    assert _spend(box_at(W * 0.9, H / 2), 120) > want * 0.95   # 2 s at ASSIST_RATE


def test_converges_on_a_static_target():
    """Iterate charge-and-spend against a target that keeps being re-measured."""
    yaw, target = 0.0, 20.0
    for _ in range(600):                  # 10 s at 60 Hz, re-measured every tick
        px = W / 2 + F * math.tan(math.radians(target - yaw))
        yaw += ui.ease(ui.center_delta(box_at(px, H / 2)), DT)[0]
    assert abs(target - yaw) < 0.1


FRAME = W * H
WANT = ui.CHASE_TARGET_FRAC * FRAME       # the area the loop is holding


def _hist(area):
    """A full history sitting at one area -- what a settled track looks like."""
    return [area] * (ui.CHASE_HIST + 1)


def test_no_chase_until_there_is_history():
    """CHASE_HIST+1 measurements or nothing -- a fresh lock must not lurch."""
    for n in range(ui.CHASE_HIST + 1):
        assert ui.chase_speed([WANT / 4] * n) == 0.0


def test_small_target_closes_and_big_one_backs_off():
    assert ui.chase_speed(_hist(WANT / 4)) > 0
    assert ui.chase_speed(_hist(WANT * 4)) < 0


def test_at_the_setpoint_it_holds():
    assert ui.chase_speed(_hist(WANT)) == 0.0


def test_deadband_swallows_mask_jitter():
    """A few percent of wobble is the mask breathing, not a range error."""
    assert ui.chase_speed(_hist(WANT * math.exp(ui.CHASE_DEADBAND / 2))) == 0.0
    assert ui.chase_speed(_hist(WANT / math.exp(ui.CHASE_DEADBAND / 2))) == 0.0


def test_speed_is_capped_both_ways():
    """A target 100x off setpoint must not command an unflyable lunge."""
    assert ui.chase_speed(_hist(WANT / 100)) == ui.CHASE_SPEED
    assert ui.chase_speed(_hist(WANT * 100)) == -ui.CHASE_SPEED


def test_one_blown_up_mask_does_not_move_the_drone():
    """The median is the whole reason this is not the latest reading: a single
    mask that swallows half the frame would otherwise command a full-speed
    retreat."""
    settled = _hist(WANT)
    settled[-1] = FRAME * 0.5
    assert ui.chase_speed(settled) == 0.0


def test_it_converges_on_a_static_target():
    """The loop closed: area ~ 1/d^2, so fly the commanded speed against a real
    range and check the range settles instead of hunting or diverging."""
    d = 120.0                                  # metres, way too far
    ref = WANT * 60.0 ** 2                     # area*d^2 is the invariant: 60 m = setpoint
    areas = []
    for _ in range(1800):                      # 30 s at 60 Hz -- 60 m of it is
                                               # spent at the CHASE_SPEED cap
        areas.append(ref / d ** 2)
        d -= ui.chase_speed(areas[-(ui.CHASE_HIST + 1):] if len(areas) > ui.CHASE_HIST
                            else areas) * (1 / 60)
        assert d > 1.0, "flew through the target"
    assert abs(d - 60.0) < 60.0 * 0.15, f"settled at {d:.1f} m, wanted ~60"


def test_chase_holds_altitude_whatever_the_camera_pitch():
    """The whole point of the ground frame: aiming down must not fly the copter
    into the road. ground_forward only ever knows the yaw."""
    for yaw in (0.0, 37.0, -90.0, 180.0):
        v = ui.ground_forward(yaw)
        assert v.z == 0.0
        assert abs(math.hypot(v.x, v.y) - 1.0) < 1e-6   # Location is float32


def test_chase_heading_follows_yaw():
    assert ui.ground_forward(0.0).x > 0.99          # +x at yaw 0
    assert ui.ground_forward(90.0).y > 0.99         # +y is right in CARLA


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
