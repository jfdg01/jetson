"""
pymavlink offboard control module for Phase B/C.

State machine:
    CONNECT → HEARTBEAT_LOOP → SET_PARAM → SET_GUIDED → ARM → TAKEOFF → OFFBOARD → LAND

Sends SET_POSITION_TARGET_LOCAL_NED (velocity-only + yaw_rate) at ~20 Hz.
All velocity setpoints are in the NED frame as required by MAVLink; the
cascade_pid output is body-frame, so a yaw rotation is applied before sending.

Key ArduPilot SITL quirks addressed here:
- SITL TCP port 5760 is single-client; use ONE connection throughout.
- ArduPilot ignores mode/param commands until the GCS has sent at least one
  HEARTBEAT.  We send several before issuing any command.
- GUIDED mode requires ARMING_CHECK=0 for headless SITL (no GPS lock).
- Force-arm (param2=21196) bypasses any remaining pre-arm check.

Requires: pymavlink >= 2.4.49  (installed in project .venv)
"""

import math
import time
from pymavlink import mavutil


# MAVLink type_mask: use velocity + yaw_rate; ignore pos, acc, yaw
_VELOCITY_YAW_RATE_MASK = (
    mavutil.mavlink.POSITION_TARGET_TYPEMASK_X_IGNORE |
    mavutil.mavlink.POSITION_TARGET_TYPEMASK_Y_IGNORE |
    mavutil.mavlink.POSITION_TARGET_TYPEMASK_Z_IGNORE |
    mavutil.mavlink.POSITION_TARGET_TYPEMASK_AX_IGNORE |
    mavutil.mavlink.POSITION_TARGET_TYPEMASK_AY_IGNORE |
    mavutil.mavlink.POSITION_TARGET_TYPEMASK_AZ_IGNORE |
    mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_IGNORE
)

_HEARTBEAT_TIMEOUT_S = 15.0
_ARM_TIMEOUT_S       = 15.0
_TAKEOFF_TIMEOUT_S   = 40.0
_GCS_HB_INTERVAL_S  = 1.0   # send GCS heartbeat at 1 Hz


class OffboardController:
    """
    Thin stateful wrapper around a pymavlink connection for ArduPilot SITL.

    Single-threaded.  Caller drives the control loop.
    """

    def __init__(self, connection_string: str = "tcp:127.0.0.1:5760"):
        self._conn_str = connection_string
        self.mav = None
        self._yaw_rad = 0.0
        self._last_hb_sent = 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_gcs_hb(self) -> None:
        """Send one GCS heartbeat (ArduPilot needs this to trust the GCS)."""
        self.mav.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0, 0, mavutil.mavlink.MAV_STATE_ACTIVE,
        )

    def _drain(self, timeout: float = 0.05) -> list:
        """Non-blocking drain; return list of received messages."""
        msgs = []
        while True:
            msg = self.mav.recv_match(blocking=True, timeout=timeout)
            if msg is None:
                break
            msgs.append(msg)
        return msgs

    def _wait_msg(self, msg_type: str, timeout: float, pred=None):
        """Wait for a specific message type, optionally matching pred(msg)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # Send periodic GCS heartbeat while waiting
            if time.monotonic() - self._last_hb_sent >= _GCS_HB_INTERVAL_S:
                self._send_gcs_hb()
                self._last_hb_sent = time.monotonic()
            msg = self.mav.recv_match(type=msg_type, blocking=True, timeout=0.5)
            if msg is None:
                continue
            if pred is None or pred(msg):
                return msg
        return None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open TCP connection, wait for autopilot heartbeat, prime GCS link."""
        print(f"[offboard] connecting to {self._conn_str} ...")
        self.mav = mavutil.mavlink_connection(self._conn_str, source_system=255)

        # Wait for first autopilot heartbeat
        hb = self.mav.recv_match(type="HEARTBEAT", blocking=True,
                                  timeout=_HEARTBEAT_TIMEOUT_S)
        if hb is None:
            raise RuntimeError("No heartbeat from SITL")
        print(f"[offboard] heartbeat  type={hb.type}  autopilot={hb.autopilot}  "
              f"target_sys={self.mav.target_system}")

        # Send several GCS heartbeats so ArduPilot recognises us as a GCS
        print("[offboard] priming GCS link (3 heartbeats) ...")
        for _ in range(3):
            self._send_gcs_hb()
            time.sleep(0.5)
        self._last_hb_sent = time.monotonic()

        # Request all data streams at 10 Hz — SITL won't send telemetry otherwise
        self.mav.mav.request_data_stream_send(
            self.mav.target_system, self.mav.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1,
        )
        print("[offboard] data stream requested")

        # Drain any backlog
        self._drain()

    def _set_param(self, name: str, value: float) -> bool:
        """
        Set parameter and wait for PARAM_VALUE ack.  Returns True on success.
        Retries up to 3 times.
        """
        for attempt in range(3):
            self.mav.mav.param_set_send(
                self.mav.target_system,
                self.mav.target_component,
                name.encode("utf-8"),
                value,
                mavutil.mavlink.MAV_PARAM_TYPE_INT32,
            )
            msg = self._wait_msg(
                "PARAM_VALUE", timeout=3.0,
                pred=lambda m: m.param_id.rstrip("\x00") == name,
            )
            if msg:
                print(f"[offboard] param {name} = {msg.param_value:.0f}")
                return True
            print(f"[offboard] param {name} retry {attempt+1}")
        print(f"[offboard] WARNING: param {name} set failed")
        return False

    def set_mode(self, mode_name: str) -> bool:
        """
        Request flight mode by name.  Returns True on confirmation.
        Uses COMMAND_LONG (MAV_CMD_DO_SET_MODE) which is more reliable
        than SET_MODE in recent ArduPilot builds.
        """
        mode_map = self.mav.mode_mapping()
        mode_id  = mode_map.get(mode_name)
        if mode_id is None:
            raise ValueError(f"Unknown mode '{mode_name}'.  Available: {list(mode_map)}")
        print(f"[offboard] requesting mode {mode_name} (id={mode_id}) ...")
        for attempt in range(5):
            self.mav.mav.command_long_send(
                self.mav.target_system,
                self.mav.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                0,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                mode_id,
                0, 0, 0, 0, 0,
            )
            msg = self._wait_msg(
                "HEARTBEAT", timeout=2.0,
                pred=lambda m, mid=mode_id: m.custom_mode == mid,
            )
            if msg:
                print(f"[offboard] mode {mode_name} confirmed")
                return True
        print(f"[offboard] WARNING: mode {mode_name} not confirmed after 5 attempts")
        return False

    def _wait_for_ekf_ready(self, timeout: float = 60.0) -> None:
        """
        Wait until EKF has a valid position estimate (required for arming in
        ArduPilot 4.6 even when ARMING_CHECK=0).

        EKF_STATUS_REPORT flags bit-field:
            0x01 velocity_horiz  0x02 velocity_vert
            0x04 pos_horiz_rel   0x08 pos_horiz_abs
            0x10 pos_vert_abs    0x20 pos_vert_agl
        We require at minimum pos_horiz_abs (0x08) + pos_vert_abs (0x10).
        """
        print("[offboard] waiting for EKF position estimate ...")
        REQUIRED = 0x08 | 0x10   # horiz_abs + vert_abs
        msg = self._wait_msg(
            "EKF_STATUS_REPORT", timeout=timeout,
            pred=lambda m: (m.flags & REQUIRED) == REQUIRED,
        )
        if msg:
            print(f"[offboard] EKF ready  flags=0x{msg.flags:02X}  "
                  f"vel_horiz={msg.velocity_variance:.2f}  "
                  f"pos_horiz={msg.pos_horiz_variance:.2f}")
        else:
            print("[offboard] WARNING: EKF status timeout — trying anyway")

    def arm(self) -> None:
        """Wait for EKF convergence, disable pre-arm checks, arm the vehicle."""
        self._set_param("ARMING_CHECK", 0.0)
        time.sleep(0.3)
        self._wait_for_ekf_ready(timeout=60.0)
        time.sleep(1.0)   # extra settling after EKF flags up

        print("[offboard] arming ...")
        for attempt in range(4):
            self.mav.mav.command_long_send(
                self.mav.target_system,
                self.mav.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                1,     # arm
                0,     # param2=0: normal arm (ARMING_CHECK already disabled)
                0, 0, 0, 0, 0,
            )
            # Check COMMAND_ACK first to get the result code
            ack = self._wait_msg("COMMAND_ACK", timeout=2.0,
                pred=lambda m: m.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM)
            if ack:
                print(f"[offboard] arm ACK result={ack.result}")
                if ack.result == 0:   # MAV_RESULT_ACCEPTED
                    # Confirm via HEARTBEAT armed bit
                    hb = self._wait_msg(
                        "HEARTBEAT", timeout=3.0,
                        pred=lambda m: bool(m.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED),
                    )
                    if hb:
                        print("[offboard] armed")
                        return
            # Check STATUSTEXT for rejection reason
            stxt = self.mav.recv_match(type="STATUSTEXT", blocking=True, timeout=0.5)
            if stxt:
                print(f"[offboard] STATUSTEXT: {stxt.text.rstrip()}")
            time.sleep(0.5)
        raise RuntimeError("Arm confirmation timeout")

    def takeoff(self, alt_m: float = 10.0) -> None:
        """Command takeoff and wait until altitude is reached."""
        self.mav.mav.command_long_send(
            self.mav.target_system,
            self.mav.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0, 0, 0, 0, 0, 0, 0, alt_m,
        )
        print(f"[offboard] climbing to {alt_m} m ...")
        msg = self._wait_msg(
            "LOCAL_POSITION_NED", timeout=_TAKEOFF_TIMEOUT_S,
            pred=lambda m, a=alt_m: m.z < -(a - 1.5),
        )
        if msg:
            print(f"[offboard] at altitude  z={msg.z:.1f} m NED")
        else:
            print("[offboard] WARNING: takeoff altitude timeout, proceeding")

    def connect_and_takeoff(self, target_alt_m: float = 10.0) -> None:
        """Full connect → GUIDED → arm → takeoff sequence."""
        self.connect()
        self.set_mode("GUIDED")
        self.arm()
        self.takeoff(target_alt_m)

    # ------------------------------------------------------------------
    # Control loop
    # ------------------------------------------------------------------

    def poll_attitude(self) -> None:
        """Non-blocking message drain; updates self._yaw_rad."""
        if self.mav is None:
            return
        while True:
            msg = self.mav.recv_match(blocking=False)
            if msg is None:
                break
            if msg.get_type() == "ATTITUDE":
                self._yaw_rad = msg.yaw

    def send_velocity_body(self, vx_b: float, vy_b: float, vz_b: float,
                            yaw_rate: float) -> None:
        """Body-frame velocity → NED setpoint via SET_POSITION_TARGET_LOCAL_NED."""
        cy, sy = math.cos(self._yaw_rad), math.sin(self._yaw_rad)
        vx_ned =  cy * vx_b - sy * vy_b
        vy_ned =  sy * vx_b + cy * vy_b
        self.mav.mav.set_position_target_local_ned_send(
            int(time.monotonic() * 1000) & 0xFFFFFFFF,
            self.mav.target_system,
            self.mav.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            _VELOCITY_YAW_RATE_MASK,
            0, 0, 0,
            vx_ned, vy_ned, vz_b,
            0, 0, 0,
            0.0, yaw_rate,
        )

    def send_heartbeat(self) -> None:
        """Send GCS heartbeat (keeps ArduPilot in GUIDED)."""
        self._send_gcs_hb()
        self._last_hb_sent = time.monotonic()

    def hover(self) -> None:
        self.send_velocity_body(0.0, 0.0, 0.0, 0.0)

    def land_and_disarm(self) -> None:
        """Command LAND mode and wait for disarm."""
        print("[offboard] landing ...")
        self.set_mode("LAND")
        msg = self._wait_msg(
            "HEARTBEAT", timeout=30.0,
            pred=lambda m: not bool(m.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED),
        )
        if msg:
            print("[offboard] disarmed — landed")
        else:
            print("[offboard] WARNING: disarm timeout")

    def close(self) -> None:
        if self.mav:
            self.mav.close()
            self.mav = None
