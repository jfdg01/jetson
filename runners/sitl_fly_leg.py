#!/usr/bin/env python3
"""
sitl_fly_leg.py -- arm, take off, fly one straight leg. Nothing else.

A pose source for renderer gates: something has to actually move so the
camera has a pose to follow. Importable so a renderer can fly the copter on
the SAME MAVLink connection it slaves to -- SITL exposes one TCP client port
and, without MAVProxy, no second endpoint streams telemetry.

    .venv-ft/bin/python runners/sitl_fly_leg.py --alt 60 --north 8 --seconds 40
"""
import argparse
import math
import threading
import time

from pymavlink import mavutil

GUIDED = 4  # copter custom mode


def wait_ack(m, command, timeout=5):
    """COMMAND_ACK for THIS command, skipping stale acks for earlier ones.

    Taking the first ACK off the wire reads the previous command's reply -- an
    arm ACK gets mistaken for a takeoff rejection, and the retry then really does
    fail because the copter is already climbing.
    """
    t0 = time.time()
    while time.time() - t0 < timeout:
        ack = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=timeout)
        if ack is None:
            return None
        if ack.command == command:
            return ack
    return None


def connect(url="tcp:127.0.0.1:5760", rate_hz=20):
    """Connect and ASK FOR the telemetry we need.

    ArduPilot streams almost nothing to a GCS that never requests it -- MAVProxy
    normally does this. Skip it and LOCAL_POSITION_NED simply never arrives, so a
    pose consumer reads its initial value forever and renders a frozen camera.
    """
    m = mavutil.mavlink_connection(url)
    m.wait_heartbeat()
    for msg_id in (mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED,
                   mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE):
        m.mav.command_long_send(m.target_system, m.target_component,
                                mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                                0, msg_id, int(1e6 / rate_hz), 0, 0, 0, 0, 0)
    return m


# Stock ArduCopter SITL is a conservative freighter: 30 deg of lean and 2.5 m/s^2 of
# nav acceleration, which behind a GUIDED velocity stick reads as sluggish and
# unresponsive -- the copter spends a second leaning before it goes anywhere, and
# another one stopping. These are sport-airframe limits. They change the AIRFRAME,
# not the control path the follow loop flies (still CascadePID -> LOCAL_NED velocity),
# and the interactive panel is a demo, so no P6 number is measured under them.
#
# What the operator feels is REVERSAL TIME: top speed one way to top speed the other.
# Everything below is what runners/sitl_reversal_check.py measured, at 45 m AGL:
#
#   path                                       15 m/s   10 m/s   6 m/s
#   GUIDED velocity setpoint (stock gains)      3.2 s    2.8 s    2.7 s
#   ... with PSC_VELXY_P raised 2 -> 9          2.6 s      -        -
#   ... velocity + accel feedforward            2.05 s   1.7 s    1.31 s
#   GUIDED attitude command, 65 deg lean          -      1.25 s   0.9 s
#
# Read the first row down, not across: the GUIDED velocity path costs ~2.7 s at ANY
# speed, so it is not accel authority, it is lag inside AC_PosControl -- the shaped
# target gets there in 0.4 s and the airframe is then dragged in behind it with a
# ~0.65 s time constant. Raising ANGLE_MAX / WPNAV_ACCEL / PSC_JERK_XY / PSC_VELXY_P
# barely touches it (all four were tried; the table is what came back). So the manual
# pilot does NOT fly velocity setpoints -- see send_manual_attitude, which commands
# lean directly and skips the position controller. These params still matter to it
# (ANGLE_MAX caps the attitude target, ATC_INPUT_TC is its slew) and still govern the
# follow loop, which stays on velocity.
#
# Ceilings, both measured, both airframe not param: 60 deg of lean settles at 13 m/s
# (SITL drag), and 15 m/s of cruise needs 46 deg of steady lean. Altitude held to
# 0.1 m through every reversal above -- the sag this comment used to warn about never
# appeared, because the copter's altitude limiter caps lean near 62 deg long before
# ANGLE_MAX's 75.
SPORT_PARAMS = {
    "ANGLE_MAX": 7500.0,      # cdeg lean limit (stock 3000) -- caps the attitude target
    "WPNAV_ACCEL": 3000.0,    # cm/s^2 horizontal (stock 250); follow loop only
    "WPNAV_ACCEL_Z": 2000.0,  # cm/s^2 vertical (stock 100)
    "WPNAV_SPEED": 1500.0,    # cm/s horizontal cruise (stock 1000)
    "WPNAV_SPEED_UP": 800.0,  # cm/s climb (stock 250). NOT higher: arm_and_takeoff
                              # climbs under SIM_SPEEDUP 10, and 1200 overshot 45 m
                              # by 68 m before the controller could stop it.
    "WPNAV_SPEED_DN": 600.0,  # cm/s descent (stock 150)
    "WPNAV_JERK": 200.0,      # m/s^3 (stock 5) -- otherwise jerk re-imposes the old ramp
    # WPNAV_JERK is the WAYPOINT jerk and a GUIDED velocity setpoint does not go
    # through waypoint nav -- PSC_JERK_* is the one that binds there.
    # Kept as a MEASURED NEGATIVE: stock 2 = "look at the next waypoint", so the
    # copter yaws to face wherever it is flying, and a reversal looked like it was
    # paying for a 180 deg heading slew (the trace showed roll climbing while pitch
    # fell). Setting 0 = hold heading moved the number 3.20 -> 3.25 s, i.e. not at
    # all; the tilt vector was rotating for some other reason. Left at 0 because a
    # camera rig should hold heading anyway -- the view is slaved to the GIMBAL's yaw
    # through ned_to_carla (R-10) -- but do not expect seconds from it.
    "WP_YAW_BEHAVIOR": 0.0,
    "PSC_JERK_XY": 200.0,     # m/s^3 horizontal (stock 30)
    "PSC_JERK_Z": 50.0,       # m/s^3 vertical (stock 5) -- q/e should bite immediately
    "ATC_INPUT_TC": 0.02,     # s of attitude smoothing (stock 0.15) -- this one IS the
                              # manual pilot's response time, it is the only filter left
                              # between the key and the lean
    # The attitude loop is what is left once the position controller is out of the
    # path, so it is worth the last 0.15 s: doubling both gains took the 6 m/s reversal
    # 1.05 -> 0.90 s. NOT higher -- 14.0/0.28 measured 1.00 s, i.e. it starts ringing
    # and the ring costs more than the slew rate buys.
    "ATC_ANG_RLL_P": 9.0,     # stock 4.5
    "ATC_ANG_PIT_P": 9.0,
    "ATC_RAT_RLL_P": 0.20,    # stock 0.135
    "ATC_RAT_PIT_P": 0.20,
    # q/e go out as the SET_ATTITUDE_TARGET thrust field, which Copter reads as a climb
    # rate scaled by these. 8 m/s each way (was 6); at PILOT_ACCEL_Z 500 that is ~1.6 s
    # of ramp, so short taps are accel-limited and get a fraction of what they asked.
    "PILOT_SPEED_UP": 800.0,  # cm/s (stock 250) -- MANUAL_CLIMB_MAX, so q/e fly the
    "PILOT_SPEED_DN": 800.0,  # slider like wasd does up to the airframe's own ceiling.
                              # MEASURED: asking for 13 m/s with these at 1300 peaked at
                              # 8.2 up / 8.0 down, i.e. the quad is THRUST-limited well
                              # below the param, and a param above what it can climb is
                              # just the old lie with a bigger number. 8 m/s down is
                              # 5.6 s from 45 m AGL to the road and there is no floor
                              # escape on the copter (that is the god camera's), so `q`
                              # held is the operator's own business.
    "PILOT_ACCEL_Z": 500.0,   # cm/s^2 (stock 250)
}

# --- manual pilot: lean, not velocity ---------------------------------------
# Why an angle and not a speed: see the table above. Everything here is measured on
# the SITL quad at 45 m AGL, and the three numbers trade against each other.
MANUAL_LEAN_DEG = 65.0   # commanded lean at full stick. 60 also works (13 m/s
                         # terminal); 70 measured no faster, the attitude slew and
                         # the drag dominate past ~65, and it costs altitude margin.
MANUAL_DRAG_K = 0.0066   # tan(lean) per (m/s)^2 -- the drag model, FIT AT THE SPEED
                         # THIS PILOT FLIES: holding 6 m/s takes 13.3 deg measured, and
                         # tan(13.3)/6^2 = 0.0066. A v^2 law fit at 15 m/s instead
                         # (46 deg -> 0.0046) undershoots down here and the copter
                         # cruises 5.74 for a demand of 6. Going the other way this
                         # runs ~10 deg hot at 15 m/s, where the P term trims it back;
                         # refit if MANUAL_V_MAX moves far.
                         # This is the FEEDFORWARD, and it is what stopped the pilot
                         # jittering: cruising at 6 m/s needs 9.4 deg, so a pure-P loop
                         # that commands 65 deg until the error is small and 0 deg once
                         # it is has no lean left to hold speed with. It overshot,
                         # braked, and slammed back in -- a limit cycle the operator
                         # felt as accelerate/brake on a held key.
MANUAL_LEAN_K = 15.0     # deg of EXTRA lean per m/s of velocity error, on top of the
                         # feedforward. Saturates ~3.7 m/s off, so a full reversal is
                         # still a step to max lean; near the setpoint the correction
                         # is proportional and small. P only -- the feedforward is
                         # doing the job an integrator would.
MANUAL_V_MAX = 6.0       # m/s. THE number that sets reversal time on this path:
                         # 6 -> 0.85 s, 7 -> ~1.0 s, 10 -> ~1.25 s. 6 is the fastest
                         # that keeps a full reversal inside 1 s. It is the REVERSAL
                         # SPEC and the default of sitl_reversal_check, not a limiter:
                         # the panel's slider is allowed up to V_CEIL, and the operator
                         # who sets 15 is choosing speed over a sub-second reversal.
V_CEIL = 13.0            # m/s the slider may demand of the copter. MEASURED terminal
                         # speed, not a preference: 60 deg of lean settles at 13 in
                         # SITL's drag, and the altitude limiter caps lean near 62 long
                         # before ANGLE_MAX's 75, so there is no more to have on this
                         # path -- `--v 15` was already recorded as never arriving.
                         # Demand past it and the lean just saturates, i.e. the slider
                         # goes back to lying, which is the thing this clamp is for.
MANUAL_CLIMB_MAX = 8.0   # m/s, must match PILOT_SPEED_UP/DN above. Same reason as
                         # V_CEIL and the same method: `e` at a slider of 13 climbing at
                         # 6 was the vertical axis lying, and 8.2 up / 8.0 down is what
                         # the airframe MEASURED when asked for 13. Vertical therefore
                         # saturates below V_CEIL -- thrust, not a choice.


def send_manual_attitude(m, vn, ve, vd, v_meas, yaw_rad):
    """One manual-pilot command: world-NED velocity demand -> a GUIDED lean.

    The panel's operator flies this; the follow loop still flies send_velocity. Both
    are GUIDED, and Copter switches submode on whichever message arrives, so letting
    go of the keys (send_velocity(0,0,0)) brakes and holds position with no mode change.

    `vn, ve, vd` is the demand in m/s (down-positive), `v_meas` the achieved
    (vx, vy, vz) straight off LOCAL_POSITION_NED, `yaw_rad` the AIRFRAME's heading --
    the lean has to be resolved in the body frame the autopilot is holding, which is
    not the gimbal yaw the keys were resolved in.
    """
    # Feedforward + P, in DEGREES. The feedforward is the lean that holds the demanded
    # speed against drag once there (v*|v| keeps the sign), so at steady state the P
    # term goes to ~0 instead of having to carry the cruise lean itself. The P term
    # still saturates the total on a reversal, which is what makes it a step input to
    # the attitude controller rather than a ramp out of the position controller.
    an = math.degrees(math.atan(MANUAL_DRAG_K * vn * abs(vn))) \
        + MANUAL_LEAN_K * (vn - v_meas[0])
    ae = math.degrees(math.atan(MANUAL_DRAG_K * ve * abs(ve))) \
        + MANUAL_LEAN_K * (ve - v_meas[1])
    # clamp the VECTOR, not each axis: clamping separately lets a diagonal demand ask
    # for 65 deg on both and fly a 84 deg resultant, which the altitude limiter then
    # quietly cuts back -- and the cut is not symmetric, so the copter turns.
    mag = math.hypot(an, ae)
    if mag > MANUAL_LEAN_DEG:
        an, ae = an * MANUAL_LEAN_DEG / mag, ae * MANUAL_LEAN_DEG / mag
    an, ae = math.radians(an), math.radians(ae)
    c, s = math.cos(yaw_rad), math.sin(yaw_rad)
    fwd, rgt = an * c + ae * s, -an * s + ae * c
    # thrust is a CLIMB RATE here (0.5 = hold), not a throttle: Copter reads the field
    # that way in guided angle control unless GUID_OPTIONS says otherwise.
    thrust = 0.5 - 0.5 * max(-1.0, min(1.0, vd / MANUAL_CLIMB_MAX))
    m.mav.set_attitude_target_send(
        0, m.target_system, m.target_component,
        0b00000111,                        # ignore body rates, use attitude + thrust
        _quat(rgt, -fwd, yaw_rad), 0, 0, 0, thrust)


def _quat(roll, pitch, yaw):
    """RPY -> [w, x, y, z]. mavlink wants a quaternion, the autopilot wants Euler."""
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return [cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy]


def set_params(m, params, timeout=2.0):
    """PARAM_SET each entry, read back what the autopilot actually kept.

    Returns {name: readback} with None for anything that never came back. The
    readback IS the check: ArduPilot silently ignores a param it does not have, so
    a typo'd or firmware-missing name is indistinguishable from an applied one
    unless you ask for the value.

    Set these BEFORE the mode is entered -- pos_control picks the WPNAV_* limits up
    at mode init, so a copter already flying GUIDED keeps the old ones until it
    re-enters.
    """
    out = {}
    for name, value in params.items():
        m.mav.param_set_send(m.target_system, m.target_component,
                             name.encode(), float(value),
                             mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        out[name] = None
        t0 = time.time()
        while time.time() - t0 < timeout:
            msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=timeout)
            if msg is None:
                break
            if msg.param_id.strip("\x00") == name:
                out[name] = msg.param_value
                break
    return out


def wait_alt(m, target, timeout=90, note=None):
    """Block until within 1 m of target altitude. Returns the altitude reached.

    `note` is an optional progress sink (a one-arg callable). A climb to 45 m takes
    ~20 s, and a caller with a screen has to be able to say so -- silence for 20 s
    reads as a hang, which is exactly how the panel's "arm + takeoff" was reported.
    """
    t0 = time.time()
    alt = 0.0
    said = None
    while time.time() - t0 < timeout:
        msg = m.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=5)
        if msg is None:
            continue
        alt = -msg.z
        # Only on a whole-metre change. The message interval is set in SIM time, so
        # under SIM_SPEEDUP (see arm_and_takeoff) this loop runs at speedup x 20 Hz
        # of wall clock, and an unthrottled sink is a Tk after() queue flooded with
        # ~200 identical strings a second.
        if note is not None and round(alt) != said:
            said = round(alt)
            note(f"climbing {alt:.0f}/{target:.0f} m")
        if abs(alt - target) < 1.0:
            return alt
    return alt


def set_guided(m, tries=60):
    """Request GUIDED and CONFIRM it from the heartbeat. Returns True if it stuck.

    Confirmation is not optional: arming succeeds in STABILIZE too, and the copter
    also drops back out of GUIDED on its own here (no MAVProxy, so the SITL RC mode
    switch sits on STABILIZE), after which NAV_TAKEOFF just returns FAILED.
    """
    for _ in range(tries):
        m.mav.set_mode_send(m.target_system,
                            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, GUIDED)
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
        if hb and hb.custom_mode == GUIDED:
            return True
        time.sleep(0.5)
    return False


def arm(m, tries=60):
    """Arm and CONFIRM from the heartbeat armed bit. Returns True if it stuck."""
    for _ in range(tries):
        m.mav.command_long_send(m.target_system, m.target_component,
                                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                                0, 1, 0, 0, 0, 0, 0, 0)
        ack = wait_ack(m, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, timeout=2)
        # The ACK says ACCEPTED before the motors are actually armed, so trust the
        # HEARTBEAT armed bit instead -- a takeoff sent on the ACK gets FAILED back.
        if ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
            hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=5)
            if hb and hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
                return True
        time.sleep(1)
    return False


def arm_and_takeoff(m, alt, note=None, speedup=1.0):
    """GUIDED -> armed -> at `alt`. Raises if any step does not actually happen.

    `note` is an optional progress sink, passed through to wait_alt (see there).

    Step order is load-bearing and was expensive to find. GUIDED must be set
    BEFORE arming and never re-asserted after: setting the mode on an armed,
    still-landed copter disarms it. And the whole sequence has to finish inside
    DISARM_DELAY (10 s) or the copter disarms itself while you are still retrying.

    `speedup` runs the CLIMB at SIM_SPEEDUP x wall clock and restores it after.
    SITL has no teleport -- an airborne copter is airborne because the physics flew
    it there -- so this is how "just put it at altitude" is bought: 45 m at
    WPNAV_SPEED_UP 5 m/s is ~9 s of physics, which at 10x is ~1 s of waiting.
    It is deliberately NOT applied to the arm/mode/retry block above: DISARM_DELAY
    is 10 s of SIM time, the retry sleeps are wall clock, and a sped-up clock eats
    that budget -- at 10x a single sleep(1) retry spends the whole of it.
    """
    # A copter left flying by a previous run rejects NAV_TAKEOFF (it is not
    # land_complete), which reads as a mysterious MAV_RESULT_FAILED. Reuse it.
    pos = m.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=5)
    if pos is not None and -pos.z > 5.0:
        return -pos.z

    if note is not None:
        note("GUIDED + arm")
    if not set_guided(m):
        raise SystemExit("never entered GUIDED")
    if not arm(m):
        raise SystemExit("never armed -- check SITL pre-arm state")

    # The motors need a beat to spin up after the armed bit sets; a takeoff sent
    # in that window comes back MAV_RESULT_FAILED. Retry, but do not touch the mode.
    for _ in range(6):
        time.sleep(1)
        m.mav.command_long_send(m.target_system, m.target_component,
                                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                                0, 0, 0, 0, 0, 0, 0, alt)
        ack = wait_ack(m, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, timeout=2)
        if ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
            break
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
        print(f"  takeoff not accepted (result={ack.result if ack else None}), "
              f"armed={bool(hb.base_mode & 128) if hb else None} "
              f"mode={hb.custom_mode if hb else None}")
    else:
        raise SystemExit("takeoff rejected -- see state above")
    if speedup > 1.0:
        set_params(m, {"SIM_SPEEDUP": float(speedup)})
    try:
        reached = wait_alt(m, alt, note=note)
    finally:
        if speedup > 1.0:
            # finally, not just the happy path: a SITL left at 10x makes every later
            # GUIDED setpoint (which are sent at a wall-clock 5 Hz) look like a 0.5 Hz
            # trickle to the autopilot, and the 3 s setpoint timeout starts firing.
            set_params(m, {"SIM_SPEEDUP": 1.0})
    if reached < alt - 2.0:
        raise SystemExit(f"never reached {alt} m (got {reached:.1f})")
    return reached


def hold_velocity(m, north, stop):
    """Resend a velocity setpoint at 5 Hz until `stop` is set.

    5 Hz because the autopilot times a GUIDED setpoint out after ~3 s of silence
    and falls back to loiter -- a one-shot send looks like it works, then stops.
    """
    while not stop.is_set():
        m.mav.set_position_target_local_ned_send(
            0, m.target_system, m.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b0000111111000111,  # use vx/vy/vz only
            0, 0, 0, north, 0, 0, 0, 0, 0, 0, 0)
        time.sleep(0.2)


def fly_in_background(m, north):
    """Start the velocity hold on a thread. Returns the stop event."""
    stop = threading.Event()
    threading.Thread(target=hold_velocity, args=(m, north, stop), daemon=True).start()
    return stop


def send_velocity(m, vn, ve, vd=0.0, yaw_rate=0.0):
    """One GUIDED velocity setpoint in LOCAL_NED (north, east, down; m/s + rad/s).

    Same mask as hold_velocity (vx/vy/vz/yaw_rate used, position ignored). The
    caller resends every control tick -- a GUIDED setpoint times out after ~3 s of
    silence and the copter falls back to loiter, so a one-shot send looks like it
    works then stops. Used by run_p62_flight's closed loop: PID output -> here.
    """
    m.mav.set_position_target_local_ned_send(
        0, m.target_system, m.target_component,
        mavutil.mavlink.MAV_FRAME_LOCAL_NED,
        0b0000111111000111,          # use vx/vy/vz + yaw_rate, ignore position/accel/yaw
        0, 0, 0, vn, ve, vd, 0, 0, 0, 0, yaw_rate)


def send_position(m, n, e, d):
    """One GUIDED position setpoint in LOCAL_NED (north, east, down; metres).

    The non-blocking half of reset_to_origin, for a caller that already runs its own
    control tick and already reads the pose -- the interactive panel, where a helper
    that blocks on recv_match would compete with the panel's own drain for the same
    socket and stall the camera it is slaving (see CARLA_DEBUG_UI_FINDINGS.md finding 15).
    Same resend rule as send_velocity: a GUIDED setpoint expires after ~3 s of silence.
    """
    m.mav.set_position_target_local_ned_send(
        0, m.target_system, m.target_component,
        mavutil.mavlink.MAV_FRAME_LOCAL_NED,
        0b0000110111111000,          # position-only (x,y,z); ignore vel/accel/yaw
        float(n), float(e), float(d), 0, 0, 0, 0, 0, 0, 0, 0)


def reset_to_origin(m, alt, tol=3.0, timeout=40):
    """Fly back to LOCAL_NED (0,0,-alt) and block until within `tol` m. Returns final dist.

    Between matrix flights the copter has chased a target away from origin; each seeded
    scenario must start from the same pose so the nadir camera reacquires near origin. A
    GUIDED *position* setpoint (not velocity), resent at 5 Hz -- a one-shot send times out
    after ~3 s and drops to loiter, same failure mode as send_velocity.
    """
    t0 = time.time()
    dist = float("inf")
    while time.time() - t0 < timeout:
        m.mav.set_position_target_local_ned_send(
            0, m.target_system, m.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b0000110111111000,          # position-only (x,y,z); ignore vel/accel/yaw
            0.0, 0.0, -alt, 0, 0, 0, 0, 0, 0, 0, 0)
        msg = m.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=1)
        if msg is None:
            continue
        dist = (msg.x ** 2 + msg.y ** 2 + ((-msg.z) - alt) ** 2) ** 0.5
        if dist < tol:
            return dist
        time.sleep(0.2)
    return dist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="tcp:127.0.0.1:5760")
    ap.add_argument("--alt", type=float, default=60.0)
    ap.add_argument("--north", type=float, default=8.0, help="north velocity, m/s")
    ap.add_argument("--seconds", type=float, default=40.0, help="how long to hold the leg")
    args = ap.parse_args()

    m = connect(args.url)
    print(f"heartbeat from sys {m.target_system}")
    print(f"takeoff: {arm_and_takeoff(m, args.alt):.1f} m")

    stop = fly_in_background(m, args.north)
    time.sleep(args.seconds)
    stop.set()
    print(f"leg done after {args.seconds:.0f} s")


if __name__ == "__main__":
    main()
