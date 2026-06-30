"""
Phase B — SITL pipeline integration runner.

Starts ArduCopter + ArduRover SITL, runs the oracle→ByteTrack→PID→MAVLink
loop for 3 × 60-second trials, and records metrics to the Phase B results file.

Usage:
    source .venv/bin/activate
    python runners/run_phase_b.py [--dry-run] [--runs N] [--duration S]

Outputs:
    experiments/2026-06-14-stage1-baseline/phase-b-sitl.md  (metrics table filled in)
    experiments/raw/phase-b-<timestamp>-run<N>.csv          (per-frame telemetry)

SITL processes launched:
    ArduCopter SITL  — TCP 5760 (copter control + telemetry)
    ArduRover SITL   — TCP 5770 (rover position telemetry only)

Rover trajectory: straight line at 0.5 m/s heading North, starting ROVER_START_N m
ahead of the copter at each trial's start.  Programmatic (no SITL rover telemetry).

Requires:  pymavlink, scipy, numpy  (all in project .venv)
"""

import argparse
import csv
import math
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure runners/ package is importable regardless of cwd
sys.path.insert(0, str(Path(__file__).parent))

from sitl.oracle_bbox import project as oracle_project, IMG_W, IMG_H
from sitl.bytetrack import ByteTracker
from sitl.cascade_pid import CascadePID
from sitl.offboard import OffboardController
from pymavlink import mavutil

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ARDUPILOT_DIR  = Path.home() / "ardupilot"
ARDUCOPTER_BIN = ARDUPILOT_DIR / "build/sitl/bin/arducopter"
ARDUROVER_BIN  = ARDUPILOT_DIR / "build/sitl/bin/ardurover"
COPTER_PARM    = ARDUPILOT_DIR / "Tools/autotest/default_params/copter.parm"
ROVER_PARM     = ARDUPILOT_DIR / "Tools/autotest/default_params/rover.parm"
SITL_DIR       = Path("/tmp/sitl-phase-b")

COPTER_PORT    = 5760
ROVER_PORT     = 5770

TAKEOFF_ALT_M  = 10.0
ROVER_SPEED_MS = 0.25      # m/s north — slow enough for copter to track with untuned P gains
ROVER_START_N  = 0.5       # m north of copter at trial-start (just ahead, well within FOV)
CONTROL_HZ     = 20        # MAVLink setpoint rate
ORACLE_HZ      = 25        # oracle bbox generation rate

RESULTS_DIR = Path(__file__).parent.parent / "experiments/2026-06-14-stage1-baseline"
RAW_DIR     = Path(__file__).parent.parent / "experiments/raw"


# ---------------------------------------------------------------------------
# SITL process management
# ---------------------------------------------------------------------------

_SITL_HOME = "-35.363262,149.165237,584,353"   # ArduPilot SITL default (CMAC, Canberra)

def _start_sitl(binary: Path, port: int, parm: Path, instance: int,
                log_path: Path) -> subprocess.Popen:
    """Launch an ArduPilot SITL binary on a specific TCP port."""
    instance_dir = SITL_DIR / f"instance{instance}"
    instance_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(binary),
        "--model", "quad" if "copter" in binary.name else "rover",
        "--speedup", "1",
        "--defaults", str(parm),
        f"--uartA=tcp:{port}",
        "--instance", str(instance),
        f"--home={_SITL_HOME}",   # GPS origin — required for EKF position estimate
    ]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
        cwd=str(instance_dir),
    )
    return proc


def _wait_for_sitl(port: int, timeout: float = 30.0):
    """Block until SITL is accepting connections on port, return live mavlink connection."""
    conn_str = f"tcp:127.0.0.1:{port}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            m = mavutil.mavlink_connection(conn_str, source_system=255)
            hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=5.0)
            if hb:
                print(f"[sitl] port {port} ready  type={hb.type}")
                # Prime GCS link and request streams
                m.mav.heartbeat_send(
                    mavutil.mavlink.MAV_TYPE_GCS,
                    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                    0, 0, mavutil.mavlink.MAV_STATE_ACTIVE,
                )
                m.mav.request_data_stream_send(
                    m.target_system, m.target_component,
                    mavutil.mavlink.MAV_DATA_STREAM_ALL, 5, 1,
                )
                return m
            m.close()
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"SITL on port {port} did not respond within {timeout}s")


# ---------------------------------------------------------------------------
# Rover scripting
# ---------------------------------------------------------------------------

def _script_rover(rover_mav, speed_ms: float = ROVER_SPEED_MS) -> None:
    """Set rover ARMING_CHECK=0, arm it, switch to GUIDED, send waypoint north."""
    # Disable arming checks (rover also needs GPS/EKF in 4.6)
    rover_mav.mav.param_set_send(
        rover_mav.target_system, rover_mav.target_component,
        b"ARMING_CHECK", 0.0, mavutil.mavlink.MAV_PARAM_TYPE_INT32,
    )
    time.sleep(0.5)

    # Set GUIDED mode
    mode_id = rover_mav.mode_mapping().get("GUIDED")
    if mode_id is None:
        print("[rover] WARNING: cannot find GUIDED mode id, rover won't move")
        return
    for _ in range(3):
        rover_mav.mav.command_long_send(
            rover_mav.target_system, rover_mav.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE, 0,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, mode_id,
            0, 0, 0, 0, 0,
        )
        time.sleep(0.5)

    # Arm rover (force-arm)
    rover_mav.mav.command_long_send(
        rover_mav.target_system, rover_mav.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 21196, 0, 0, 0, 0, 0,
    )
    time.sleep(1.0)

    # Send target waypoint 200 m north (local NED)
    rover_mav.mav.set_position_target_local_ned_send(
        0,
        rover_mav.target_system, rover_mav.target_component,
        mavutil.mavlink.MAV_FRAME_LOCAL_NED,
        0b110111111000,   # position only
        ROVER_START_N + 200.0, 0.0, 0.0,
        0, 0, 0, 0, 0, 0, 0, 0,
    )
    print(f"[rover] scripted to drive north at ~{speed_ms} m/s")


# ---------------------------------------------------------------------------
# Telemetry reader helpers
# ---------------------------------------------------------------------------

def _get_position_ned(mav) -> tuple | None:
    """Return (N, E, D) from the most recent LOCAL_POSITION_NED message."""
    msg = mav.recv_match(type="LOCAL_POSITION_NED", blocking=False)
    if msg:
        return (msg.x, msg.y, msg.z)
    return None


def _get_attitude(mav) -> tuple | None:
    """Return (roll, pitch, yaw) radians from latest ATTITUDE message."""
    msg = mav.recv_match(type="ATTITUDE", blocking=False)
    if msg:
        return (msg.roll, msg.pitch, msg.yaw)
    return None


# ---------------------------------------------------------------------------
# Single trial
# ---------------------------------------------------------------------------

def _drain_telemetry(ctrl, copter_ned: tuple, attitude: tuple) -> tuple:
    """
    Non-blocking drain of the copter MAVLink backlog.  Returns updated
    (copter_ned, attitude); also keeps ctrl._yaw_rad in sync so the body→NED
    velocity transform uses the latest heading.

    Drained in one loop here (not via ctrl.poll_attitude()) because that helper
    consumes and discards LOCAL_POSITION_NED before the control loop sees it.
    """
    if ctrl.mav is None:
        return copter_ned, attitude
    while True:
        msg = ctrl.mav.recv_match(blocking=False)
        if msg is None:
            break
        mt = msg.get_type()
        if mt == "LOCAL_POSITION_NED":
            copter_ned = (msg.x, msg.y, msg.z)
        elif mt == "ATTITUDE":
            attitude = (msg.roll, msg.pitch, msg.yaw)
            ctrl._yaw_rad = msg.yaw  # keep body→NED rotation in sync
    return copter_ned, attitude


def _control_step(tracker, pid, copter_ned: tuple, rover_ned: tuple,
                  attitude: tuple) -> tuple:
    """
    One perception→control step.  Returns (bbox_raw, track, bbox_out, sp,
    pix_err): the oracle bbox (ground truth, None if unseen), the ByteTrack
    track, the tracked bbox fed to the PID, the velocity setpoint, and the
    honest pixel error (from bbox_raw, None when the oracle didn't see target).

    Gimbal-stabilized (nadir) camera: LEVEL roll/pitch passed to the oracle, yaw
    kept.  A body-fixed downward camera tilts with the airframe — ArduPilot's
    nose-down accel pitch shifts the target up in frame by FOCAL_PX·tan(pitch)
    (~130px at 13°), swamping the real offset and forming a positive-feedback
    loop (vx → pitch → more apparent error → more vx → saturation).  A 2-axis
    gimbal removes this coupling; we model it by zeroing roll/pitch.
    """
    bbox_raw = oracle_project(copter_ned, rover_ned, 0.0, 0.0, attitude[2])
    det = [{**bbox_raw, "score": 1.0}] if bbox_raw else []

    tracks = tracker.update(det)
    track  = tracks[0] if tracks else None

    bbox_out = track.bbox if track else None
    sp = pid.compute(bbox_out)

    # Pixel error is gated on the ORACLE seeing the target (bbox_raw not None),
    # NOT on ByteTrack having a track — ByteTrack coasts a Kalman estimate for a
    # few frames after the oracle returns None; counting those would inflate
    # coverage with frames perfect-perception never saw.  Error is from bbox_raw.
    pix_err = None
    if bbox_raw is not None:
        pix_err = math.hypot(bbox_raw["cx"] - IMG_W / 2,
                             bbox_raw["cy"] - IMG_H / 2)
    return bbox_raw, track, bbox_out, sp, pix_err


def _log_frame(writer, t_elapsed: float, copter_ned: tuple, rover_ned: tuple,
               bbox_out, track, pix_err, sp: dict, dt: float) -> None:
    """Append one per-frame telemetry row to the open CSV writer."""
    writer.writerow([
        f"{t_elapsed:.3f}",
        f"{copter_ned[0]:.2f}", f"{copter_ned[1]:.2f}", f"{copter_ned[2]:.2f}",
        f"{rover_ned[0]:.2f}",  f"{rover_ned[1]:.2f}",  f"{rover_ned[2]:.2f}",
        f"{bbox_out['cx']:.1f}" if bbox_out else "",
        f"{bbox_out['cy']:.1f}" if bbox_out else "",
        f"{bbox_out['w']:.1f}"  if bbox_out else "",
        f"{bbox_out['h']:.1f}"  if bbox_out else "",
        track.id if track else "",
        f"{pix_err:.1f}" if pix_err is not None else "",
        f"{sp['vx']:.3f}", f"{sp['vy']:.3f}", f"{sp['yaw_rate']:.4f}",
        f"{dt*1000:.1f}",
    ])


def run_trial(
    run_idx: int,
    duration_s: float,
    ctrl: OffboardController,
    rover_mav,
    dry_run: bool,
    csv_path: Path,
) -> dict:
    """
    Execute one 60-second trial.  Returns a metrics dict.

    The control loop:
        1. Drain copter telemetry (LOCAL_POSITION_NED, ATTITUDE)
        2. Compute oracle rover position from PROGRAMMATIC trajectory
           (avoids SITL NED-frame mismatch between two SITL instances)
        3. Compute oracle bbox from world positions
        4. Feed bbox to ByteTrack
        5. Compute PID setpoints from tracker output
        6. Send setpoints via pymavlink
        7. Log frame telemetry to CSV

    Rover trajectory: constant-velocity linear, ROVER_SPEED_MS north, starting
    ROVER_START_N m north of copter home.  Programmatic rather than SITL-telemetry
    because separate ArduRover SITL instance uses a different NED altitude origin
    (instance offset causes ~584m D discrepancy at CMAC home).
    """
    tracker = ByteTracker()
    # kp_yaw=0.0: at low altitude with a near-nadir target, yaw-rate commands add
    # body-rotation noise to pixel centring without improving it.  Yaw is disabled
    # for Phase B validation; re-enable and tune in Phase C.
    pid     = CascadePID(kp_yaw=0.0)
    metrics = {
        "run": run_idx + 1,
        "n_frames": 0,
        "oracle_detection_frames": 0,
        "oracle_coverage_pct": 0.0,
        "loop_hz_mean": 0.0,
        "pixel_error_mean_px": 0.0,
        "track_loss_events": 0,
        "notes": f"rover: programmatic {ROVER_SPEED_MS} m/s north, anchored to copter (N,E)",
    }

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_file = open(csv_path, "w", newline="")
    writer = csv.writer(csv_file)
    writer.writerow([
        "t_s", "copter_n", "copter_e", "copter_d",
        "rover_n", "rover_e", "rover_d",
        "bbox_cx", "bbox_cy", "bbox_w", "bbox_h",
        "track_id", "pixel_err_px",
        "vx_cmd", "vy_cmd", "yaw_rate_cmd",
        "loop_dt_ms",
    ])

    # Cached copter position/attitude (updated from SITL telemetry)
    copter_ned = (0.0, 0.0, -TAKEOFF_ALT_M)
    attitude   = (0.0, 0.0, 0.0)  # roll, pitch, yaw

    # Capture the copter's real position before the trial starts so the rover
    # trajectory can be anchored to it (both N and E).  The old code drained a
    # fixed 20 messages and frequently never saw a LOCAL_POSITION_NED in that
    # window (it sits deep in the backlog), leaving rover_home_n=0 and the rover
    # misaligned relative to a drifted copter — the cause of the run-2/3 vacuous
    # PASS.  Fix: flush the entire backlog non-blocking, then block for exactly
    # one *fresh* LOCAL_POSITION_NED.
    if ctrl.mav is not None:
        while ctrl.mav.recv_match(blocking=False) is not None:
            pass  # discard stale backlog
        pos = ctrl.mav.recv_match(type="LOCAL_POSITION_NED",
                                  blocking=True, timeout=5.0)
        if pos is not None:
            copter_ned = (pos.x, pos.y, pos.z)
        else:
            print(f"[run {run_idx+1}] WARNING: no fresh LOCAL_POSITION_NED "
                  f"in 5s; anchoring rover to last-known copter pos {copter_ned}")

    # Rover trajectory anchored to copter's actual (N, E) position at trial start
    # (prevents inter-run drift from misaligning rover relative to copter)
    rover_home_n = copter_ned[0]
    rover_home_e = copter_ned[1]

    prev_track_id = None
    pixel_errors  = []
    loop_dts      = []

    t_start  = time.monotonic()
    t_prev   = t_start
    hb_timer = t_start

    print(f"\n[run {run_idx+1}] starting trial ({duration_s}s) "
          f"{'DRY-RUN' if dry_run else ''}")

    while time.monotonic() - t_start < duration_s:
        t_now = time.monotonic()
        dt    = t_now - t_prev
        t_prev = t_now
        t_elapsed = t_now - t_start

        # --- Programmatic rover trajectory (avoids SITL NED mismatch) ---
        # Anchored to copter position at trial start so each run is independent
        rover_ned = (
            rover_home_n + ROVER_START_N + ROVER_SPEED_MS * t_elapsed,
            rover_home_e,
            0.0,   # ground level = D=0 in copter NED frame
        )

        # --- Drain copter telemetry ---
        copter_ned, attitude = _drain_telemetry(ctrl, copter_ned, attitude)

        # --- Perception → control step (oracle → ByteTrack → PID) ---
        bbox_raw, track, bbox_out, sp, pix_err = _control_step(
            tracker, pid, copter_ned, rover_ned, attitude)

        # Detect track-loss events (ID change or no track)
        if track:
            if prev_track_id is not None and track.id != prev_track_id:
                metrics["track_loss_events"] += 1
        elif prev_track_id is not None:
            metrics["track_loss_events"] += 1
        prev_track_id = track.id if track else None

        # Coverage + pixel-error accumulation (honest: oracle-seen frames only)
        if bbox_raw is not None:
            metrics["oracle_detection_frames"] += 1
            pixel_errors.append(pix_err)
        if dt > 0:
            loop_dts.append(dt)

        # --- Send setpoint ---
        if not dry_run and ctrl.mav:
            ctrl.send_velocity_body(sp["vx"], sp["vy"], sp["vz"], sp["yaw_rate"])

        # Heartbeat at ~1 Hz
        if t_now - hb_timer >= 1.0:
            if not dry_run and ctrl.mav:
                ctrl.send_heartbeat()
            hb_timer = t_now

        # --- CSV log ---
        _log_frame(writer, t_now - t_start, copter_ned, rover_ned,
                   bbox_out, track, pix_err, sp, dt)

        metrics["n_frames"] += 1

        # Sleep to pace the loop at ~CONTROL_HZ
        target_dt = 1.0 / CONTROL_HZ
        sleep_t   = target_dt - (time.monotonic() - t_now)
        if sleep_t > 0:
            time.sleep(sleep_t)

    csv_file.close()

    if loop_dts:
        metrics["loop_hz_mean"] = round(1.0 / (sum(loop_dts) / len(loop_dts)), 2)
    if pixel_errors:
        metrics["pixel_error_mean_px"] = round(
            sum(pixel_errors) / len(pixel_errors), 1)
    if metrics["n_frames"] > 0:
        metrics["oracle_coverage_pct"] = round(
            100.0 * metrics["oracle_detection_frames"] / metrics["n_frames"], 1)
    print(f"[run {run_idx+1}] done  "
          f"hz={metrics['loop_hz_mean']:.1f}  "
          f"px_err={metrics['pixel_error_mean_px']:.1f}px  "
          f"coverage={metrics['oracle_coverage_pct']:.1f}%  "
          f"track_losses={metrics['track_loss_events']}  "
          f"frames={metrics['n_frames']}")
    return metrics


# ---------------------------------------------------------------------------
# Results writing
# ---------------------------------------------------------------------------

def _format_metrics_table(runs: list[dict]) -> str:
    header = ("| Run | Loop Hz | Mean pixel error (px) | Oracle coverage (%) | "
              "Track-loss events | Notes |")
    sep    = "|---|---|---|---|---|---|"
    rows   = []
    for r in runs:
        rows.append(
            f"| {r['run']} "
            f"| {r['loop_hz_mean']} "
            f"| {r['pixel_error_mean_px']} "
            f"| {r.get('oracle_coverage_pct', 0.0)} "
            f"| {r['track_loss_events']} "
            f"| {r['notes']} |"
        )
    # Summary row
    hz_mean  = round(sum(r["loop_hz_mean"] for r in runs) / len(runs), 2)
    px_mean  = round(sum(r["pixel_error_mean_px"] for r in runs) / len(runs), 1)
    cov_mean = round(sum(r.get("oracle_coverage_pct", 0.0) for r in runs) / len(runs), 1)
    hz_std   = round(_std([r["loop_hz_mean"]  for r in runs]), 2)
    px_std   = round(_std([r["pixel_error_mean_px"] for r in runs]), 1)
    tl_total = sum(r["track_loss_events"] for r in runs)
    rows.append(f"| **Mean ± std** | {hz_mean} ± {hz_std} "
                f"| {px_mean} ± {px_std} | {cov_mean} | {tl_total} total | — |")
    # PASS requires: real-time loop, centred target, AND high oracle coverage.
    # The coverage gate is what makes the PASS non-vacuous: a low-coverage run
    # can show a tiny mean px_err over a handful of frames the oracle barely saw.
    pass_fail = ("PASS" if hz_mean >= 1.0 and px_mean < 50.0 and cov_mean >= 80.0
                 else "FAIL")
    return "\n".join([header, sep] + rows) + f"\n\n**Phase B result: {pass_fail}**"


def _std(xs: list) -> float:
    if len(xs) < 2:
        return 0.0
    mean = sum(xs) / len(xs)
    return math.sqrt(sum((x - mean) ** 2 for x in xs) / (len(xs) - 1))


def _patch_results_file(table: str, date: str) -> None:
    """Replace the placeholder metrics table in phase-b-sitl.md with real data."""
    results_file = RESULTS_DIR / "phase-b-sitl.md"
    text = results_file.read_text()
    # Find and replace the table between "## Metrics" and the next "---"
    marker_start = "| Run | Loop Hz | Mean pixel error (px) |"
    marker_end   = "\n\n**Success threshold:**"
    idx_s = text.find(marker_start)
    idx_e = text.find(marker_end, idx_s)
    if idx_s == -1 or idx_e == -1:
        print("[results] WARNING: could not locate metrics table in phase-b-sitl.md")
        return
    new_text = text[:idx_s] + table + text[idx_e:]
    # Add completion date header
    new_text = new_text.replace(
        "**Status:** SETUP PENDING — prerequisites not yet installed",
        f"**Status:** COMPLETE ({date})",
    )
    results_file.write_text(new_text)
    print(f"[results] phase-b-sitl.md updated")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Phase B SITL pipeline runner")
    parser.add_argument("--dry-run",  action="store_true",
                        help="skip arming/takeoff and MAVLink setpoints")
    parser.add_argument("--runs",     type=int, default=3)
    parser.add_argument("--duration", type=float, default=60.0,
                        help="seconds per run (default 60)")
    args = parser.parse_args()

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M UTC")
    ts       = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    SITL_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Verify binaries ----
    for b in (ARDUCOPTER_BIN, ARDUROVER_BIN):
        if not b.exists():
            sys.exit(f"ERROR: SITL binary not found: {b}\n"
                     f"Run: cd ~/ardupilot && python3 waf copter rover")

    print("=" * 60)
    print("Phase B — SITL pipeline integration")
    print(f"Runs: {args.runs} × {args.duration}s  |  DRY-RUN={args.dry_run}")
    print("=" * 60)

    copter_proc = rover_proc = None
    rover_mav_conn = None

    try:
        # ---- Start SITL processes ----
        copter_log = RAW_DIR / f"phase-b-{ts}-copter-sitl.log"
        rover_log  = RAW_DIR / f"phase-b-{ts}-rover-sitl.log"
        RAW_DIR.mkdir(parents=True, exist_ok=True)

        print("[sitl] starting ArduCopter SITL ...")
        copter_proc = _start_sitl(ARDUCOPTER_BIN, COPTER_PORT, COPTER_PARM, 0, copter_log)
        print("[sitl] starting ArduRover SITL ...")
        rover_proc  = _start_sitl(ARDUROVER_BIN,  ROVER_PORT,  ROVER_PARM,  1, rover_log)

        # ---- Wait for rover SITL; ctrl connects to copter itself ----
        # Only one TCP connection per SITL port — do NOT open a separate
        # handshake connection to port 5760; ctrl is the sole client.
        rover_mav_conn = _wait_for_sitl(ROVER_PORT, timeout=30.0)
        # Brief delay so copter SITL finishes binding before ctrl connects
        time.sleep(2.0)

        # ---- Set up offboard controller ----
        ctrl = OffboardController(f"tcp:127.0.0.1:{COPTER_PORT}")

        if not args.dry_run:
            ctrl.connect_and_takeoff(target_alt_m=TAKEOFF_ALT_M)
            _script_rover(rover_mav_conn)
            time.sleep(2.0)  # let rover start moving
        else:
            print("[dry-run] skipping connect/arm/takeoff/rover-script")
            ctrl.mav = None  # suppress MAVLink sends in dry-run

        # ---- Trials ----
        all_metrics = []
        for i in range(args.runs):
            csv_path = RAW_DIR / f"phase-b-{ts}-run{i+1}.csv"
            # Reset rover trajectory each run: re-issue GUIDED waypoint
            if not args.dry_run and rover_mav_conn and i > 0:
                _script_rover(rover_mav_conn)
                time.sleep(1.0)
            m = run_trial(i, args.duration, ctrl, rover_mav_conn, args.dry_run, csv_path)
            all_metrics.append(m)
            if i < args.runs - 1 and not args.dry_run:
                print("[run] pausing 10s between runs ...")
                time.sleep(10.0)

        # ---- Land ----
        if not args.dry_run and ctrl.mav:
            ctrl.land_and_disarm()
        ctrl.close()

        # ---- Write results ----
        table = _format_metrics_table(all_metrics)
        print("\n" + table)
        _patch_results_file(table, date_str)

        print("\nPhase B complete.")
        print(f"Raw CSVs: {RAW_DIR}/phase-b-{ts}-run*.csv")

    finally:
        for proc in (copter_proc, rover_proc):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
        if rover_mav_conn:
            try:
                rover_mav_conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    main()
