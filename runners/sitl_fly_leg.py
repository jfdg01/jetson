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


def wait_alt(m, target, timeout=90, note=None):
    """Block until within 1 m of target altitude. Returns the altitude reached.

    `note` is an optional progress sink (a one-arg callable). A climb to 45 m takes
    ~20 s, and a caller with a screen has to be able to say so -- silence for 20 s
    reads as a hang, which is exactly how the panel's "arm + takeoff" was reported.
    """
    t0 = time.time()
    alt = 0.0
    while time.time() - t0 < timeout:
        msg = m.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=5)
        if msg is None:
            continue
        alt = -msg.z
        if note is not None:
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


def arm_and_takeoff(m, alt, note=None):
    """GUIDED -> armed -> at `alt`. Raises if any step does not actually happen.

    `note` is an optional progress sink, passed through to wait_alt (see there).

    Step order is load-bearing and was expensive to find. GUIDED must be set
    BEFORE arming and never re-asserted after: setting the mode on an armed,
    still-landed copter disarms it. And the whole sequence has to finish inside
    DISARM_DELAY (10 s) or the copter disarms itself while you are still retrying.
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
    reached = wait_alt(m, alt, note=note)
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
    socket and stall the camera it is slaving (see CARLA_DEBUG_UI.md finding 15).
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
