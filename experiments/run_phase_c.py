"""
Phase C — VLM in the loop (Stage 1 closed-loop baseline).

Starts ArduCopter SITL, runs a 20 Hz ByteTrack→PID→MAVLink control loop with
the oracle bbox kept as GT-only for scoring, while an async thread provides
detections from either (a) oracle injection for the Branch-1 mechanics gate,
or (b) a Jetson VLM over Gazebo-rendered frames.

Usage (Branch-1 gate — no Gazebo needed):
    python experiments/run_phase_c.py --inject-oracle [--dry-run] [--runs N]

Usage (live VLM + Gazebo — requires Gazebo Harmonic installed):
    python experiments/run_phase_c.py --expression "the vehicle" [--dry-run]

Outputs:
    results/2026-06-14-stage1-baseline/phase-c-vlm.md  (metrics filled in)
    results/raw/phase-c-<timestamp>-run<N>.csv

CLI flags:
    --inject-oracle       Branch-1 gate: inject oracle bbox at 1 Hz, no VLM/Gazebo
    --expression "<NL>"  Target expression for VLM grounding (default: "the vehicle")
    --vlm-model <path>   Override VLM model path on Jetson (for Stage 2 re-run)
    --skip-server        Assume llama-server already running on port 8080
    --dry-run            Print commands without executing MAVLink or VLM calls
    --runs N             Number of 60-second trials (default 3)
    --duration S         Seconds per trial (default 60)

Pre-registration: results/2026-06-14-stage1-baseline/phase-c-vlm.md
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from sitl.oracle_bbox import project as oracle_project, IMG_W, IMG_H
from sitl.bytetrack import ByteTracker, MAX_LOST_FRAMES
from sitl.cascade_pid import CascadePID
from sitl.offboard import OffboardController
from pymavlink import mavutil

# Import VLM server + HTTP client from Phase A grounding probe (reuse, don't reinvent)
import run_grounding_probe as _probe

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ARDUPILOT_DIR  = Path.home() / "ardupilot"
ARDUCOPTER_BIN = ARDUPILOT_DIR / "build/sitl/bin/arducopter"
COPTER_PARM    = ARDUPILOT_DIR / "Tools/autotest/default_params/copter.parm"
SITL_DIR       = Path("/tmp/sitl-phase-c")

COPTER_PORT    = 5760

TAKEOFF_ALT_M  = 10.0
ROVER_SPEED_MS = 0.25      # m/s north (same as Phase B)
ROVER_START_N  = 0.5       # m ahead of copter at trial start
CONTROL_HZ     = 20        # control loop rate

# Pre-registered Phase C constants
LOST_TIMEOUT_S  = 3.0      # s of no valid detection → declare track-loss event
INJECT_RATE_HZ  = 1.0      # oracle-inject / VLM call rate
GAP_INJECT_RUN  = 3        # which run (1-indexed) forces the re-seed gap (Branch-1)
GAP_AT_S        = 30.0     # gap starts at this elapsed time within the run
GAP_DURATION_S  = LOST_TIMEOUT_S + 1.0   # 4 s; > LOST_TIMEOUT_S to guarantee loss

# Frame size (matches Phase C design doc §5.2)
FRAME_W = 640
FRAME_H = 480

# Gazebo world / topics
GZ_WORLD_SDF    = Path(__file__).parent / "sitl/worlds/phase_c.sdf"
GZ_WORLD_NAME   = "phase_c"
GZ_CAM_TOPIC    = (f"/world/{GZ_WORLD_NAME}/model/downward_cam"
                   f"/link/cam_link/sensor/downward_cam/image")
GZ_SET_POSE_SVC = f"/world/{GZ_WORLD_NAME}/set_pose"
ARDUPILOT_GZ_BUILD = Path.home() / "ardupilot_gazebo/build"

# VLM prompt format (Phase A Format A; higher parse rate for S2)
DEFAULT_EXPRESSION = "the vehicle"
DEFAULT_VLM_MODEL  = "~/models/SmolVLM-500M-Instruct-Q8_0.gguf"
DEFAULT_MMPROJ     = "~/models/mmproj-SmolVLM-500M-Instruct-f16.gguf"

_SITL_HOME = "-35.363262,149.165237,584,353"   # CMAC, Canberra

RESULTS_DIR = Path(__file__).parent.parent / "results/2026-06-14-stage1-baseline"
RAW_DIR     = Path(__file__).parent.parent / "results/raw"
PHASE_C_MD  = RESULTS_DIR / "phase-c-vlm.md"
RESULTS_MD  = Path(__file__).parent.parent / "RESULTS.md"


# ---------------------------------------------------------------------------
# Async latest-detection slot (thread-safe, stale-rejection)
# ---------------------------------------------------------------------------

@dataclass
class Detection:
    """Snapshot of one VLM or oracle-inject result."""
    capture_ts: float = 0.0       # monotonic; reject if <= last seen
    bbox: Optional[dict] = None   # {cx,cy,w,h} for ByteTrack, or None
    vlm_ms: float = 0.0           # VLM compute time (0.0 for oracle-inject)
    raw_text: str = ""


class LatestDetectionSlot:
    """
    Lock-protected slot for the most recent detection.

    The VLM grounding thread (or oracle-inject thread) writes here; the 20 Hz
    control thread reads.  Stale-rejection: a write is silently dropped if
    capture_ts <= the stored timestamp (monotonic, so this is rare but safe).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._det = Detection()

    def write(self, capture_ts: float, bbox: Optional[dict],
              vlm_ms: float = 0.0, raw_text: str = "") -> bool:
        """Write a new detection.  Returns True if written, False if stale."""
        with self._lock:
            if capture_ts <= self._det.capture_ts:
                return False
            self._det = Detection(
                capture_ts=capture_ts,
                bbox=dict(bbox) if bbox is not None else None,
                vlm_ms=vlm_ms,
                raw_text=raw_text,
            )
            return True

    def read(self) -> Detection:
        """Return a copy of the current detection."""
        with self._lock:
            d = self._det
            return Detection(
                capture_ts=d.capture_ts,
                bbox=dict(d.bbox) if d.bbox is not None else None,
                vlm_ms=d.vlm_ms,
                raw_text=d.raw_text,
            )


def _test_slot() -> None:
    """Unit tests for LatestDetectionSlot."""
    slot = LatestDetectionSlot()

    # write + read
    ok = slot.write(1.0, {"cx": 10, "cy": 20, "w": 5, "h": 8}, vlm_ms=100.0)
    assert ok, "write should succeed"
    d = slot.read()
    assert d.bbox == {"cx": 10, "cy": 20, "w": 5, "h": 8}
    assert d.vlm_ms == 100.0

    # stale-rejection: same timestamp should be rejected
    ok2 = slot.write(1.0, {"cx": 99, "cy": 99, "w": 1, "h": 1})
    assert not ok2, "same-ts write should be rejected"
    assert slot.read().bbox["cx"] == 10, "slot should not have changed"

    # older timestamp rejected
    ok3 = slot.write(0.5, {"cx": 50, "cy": 50, "w": 2, "h": 2})
    assert not ok3, "older-ts write should be rejected"

    # newer timestamp accepted
    ok4 = slot.write(2.0, {"cx": 77, "cy": 88, "w": 3, "h": 6})
    assert ok4
    assert slot.read().bbox["cx"] == 77

    # None bbox
    ok5 = slot.write(3.0, None)
    assert ok5
    assert slot.read().bbox is None

    # read returns a copy (not the internal reference)
    d1 = slot.read()
    slot.write(4.0, {"cx": 1, "cy": 2, "w": 3, "h": 4})
    # d1 should be unchanged (was a snapshot)
    assert d1.capture_ts == 3.0

    print("  ✓ LatestDetectionSlot tests passed")


# ---------------------------------------------------------------------------
# Bbox xyxy→cxcywh adapter (VLM output → ByteTrack format)
# ---------------------------------------------------------------------------

def xyxy_to_cxcywh(x1: float, y1: float, x2: float, y2: float) -> dict:
    """Convert xyxy (VLM Format-A output) to {cx,cy,w,h} (ByteTrack input)."""
    return {
        "cx": (x1 + x2) / 2.0,
        "cy": (y1 + y2) / 2.0,
        "w":  x2 - x1,
        "h":  y2 - y1,
    }


def _test_adapter() -> None:
    """Unit tests for xyxy_to_cxcywh."""
    b = xyxy_to_cxcywh(10.0, 20.0, 50.0, 80.0)
    assert b["cx"] == 30.0,  f"cx={b['cx']}"
    assert b["cy"] == 50.0,  f"cy={b['cy']}"
    assert b["w"]  == 40.0,  f"w={b['w']}"
    assert b["h"]  == 60.0,  f"h={b['h']}"

    # zero-size box (degenerate; should be rejected downstream by Bbox.is_valid)
    b2 = xyxy_to_cxcywh(5.0, 5.0, 5.0, 5.0)
    assert b2["w"] == 0.0 and b2["h"] == 0.0

    print("  ✓ xyxy_to_cxcywh adapter tests passed")


# ---------------------------------------------------------------------------
# Shared copter state (read by injection thread, written by drain loop)
# ---------------------------------------------------------------------------

@dataclass
class CopterState:
    ned: tuple = (0.0, 0.0, -TAKEOFF_ALT_M)   # (N, E, D)
    attitude: tuple = (0.0, 0.0, 0.0)           # (roll, pitch, yaw) rad
    lock: threading.Lock = field(default_factory=threading.Lock)


# ---------------------------------------------------------------------------
# Oracle-injection thread (Branch-1 mechanics gate)
# ---------------------------------------------------------------------------

def _oracle_inject_thread(
    slot: LatestDetectionSlot,
    stop_event: threading.Event,
    copter_state: CopterState,
    rover_fn,                          # callable(elapsed_s) → (N, E, D)
    run_idx: int,                      # 0-indexed
    dry_run: bool,
    call_log: list,                    # shared list; append (capture_ts, bbox_or_None)
) -> None:
    """
    Inject oracle bboxes at 1 Hz into the detection slot.

    In run GAP_INJECT_RUN (1-indexed), forces a GAP_DURATION_S gap at GAP_AT_S
    elapsed seconds to validate re-seed mechanics (Branch-1 criterion 3).
    """
    t_start = time.monotonic()
    gap_active = False

    while not stop_event.is_set():
        t_now = time.monotonic()
        elapsed = t_now - t_start

        # Forced gap (run 3 only, at GAP_AT_S mark)
        is_gap_run = (run_idx + 1) == GAP_INJECT_RUN
        if is_gap_run:
            in_gap = GAP_AT_S <= elapsed < (GAP_AT_S + GAP_DURATION_S)
            if in_gap:
                if not gap_active:
                    print(f"[inject] forced gap started at t={elapsed:.1f}s "
                          f"(duration={GAP_DURATION_S:.1f}s, re-seed test)")
                    gap_active = True
                time.sleep(0.1)
                continue
            elif gap_active:
                print(f"[inject] forced gap ended at t={elapsed:.1f}s — "
                      f"resuming injection (re-seed expected within 2s)")
                gap_active = False

        # Get current copter state
        with copter_state.lock:
            copter_ned = copter_state.ned
            attitude   = copter_state.attitude

        rover_ned = rover_fn(elapsed)

        if dry_run:
            bbox = {"cx": IMG_W / 2, "cy": IMG_H / 2, "w": 100.0, "h": 50.0}
        else:
            bbox = oracle_project(copter_ned, rover_ned, 0.0, 0.0, attitude[2])

        capture_ts = time.monotonic()
        slot.write(capture_ts, bbox, vlm_ms=0.0, raw_text="[oracle-inject]")
        call_log.append((capture_ts, dict(bbox) if bbox else None, 0.0, "[oracle-inject]"))

        time.sleep(1.0 / INJECT_RATE_HZ)


# ---------------------------------------------------------------------------
# Gazebo state (module-level; initialised in _setup_gz_node)
# ---------------------------------------------------------------------------

_gz_node         = None
_gz_latest_frame: dict = {"data": None, "w": 0, "h": 0}
_gz_frame_lock   = threading.Lock()
_gz_frame_event  = threading.Event()


def _euler_to_quat(roll: float, pitch: float, yaw: float) -> tuple:
    """Return (w, x, y, z) quaternion from intrinsic ZYX Euler angles."""
    cr = math.cos(roll  / 2); sr = math.sin(roll  / 2)
    cp = math.cos(pitch / 2); sp = math.sin(pitch / 2)
    cy = math.cos(yaw   / 2); sy = math.sin(yaw   / 2)
    w =  cr*cp*cy + sr*sp*sy
    x =  sr*cp*cy - cr*sp*sy
    y =  cr*sp*cy + sr*cp*sy
    z =  cr*cp*sy - sr*sp*cy
    return (w, x, y, z)


def _start_gazebo(log_path: Path) -> subprocess.Popen:
    """Start gz sim headless (server-only, real-time) with the phase_c world."""
    env = os.environ.copy()
    env["GZ_SIM_SYSTEM_PLUGIN_PATH"] = str(ARDUPILOT_GZ_BUILD)
    env["GZ_SIM_RESOURCE_PATH"] = str(ARDUPILOT_GZ_BUILD.parent)
    cmd = ["gz", "sim", "-s", "-r", str(GZ_WORLD_SDF)]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w")
    return subprocess.Popen(cmd, stdout=log_file, stderr=log_file, env=env)


def _setup_gz_node() -> None:
    """Create the gz transport Node and subscribe to the downward camera topic."""
    global _gz_node
    sys.path.insert(0, "/usr/lib/python3/dist-packages")
    import gz.transport13 as transport  # noqa: PLC0415
    from gz.msgs10 import image_pb2     # noqa: PLC0415

    _gz_node = transport.Node()

    def _on_image(msg):
        with _gz_frame_lock:
            _gz_latest_frame["data"] = bytes(msg.data)
            _gz_latest_frame["w"]    = msg.width
            _gz_latest_frame["h"]    = msg.height
        _gz_frame_event.set()

    _gz_node.subscribe(image_pb2.Image, GZ_CAM_TOPIC, _on_image)
    print(f"[gazebo] subscribed to {GZ_CAM_TOPIC}")


def _wait_gazebo(timeout: float = 30.0) -> bool:
    """Block until the first camera frame arrives (or timeout). Returns True on success."""
    return _gz_frame_event.wait(timeout=timeout)


# ---------------------------------------------------------------------------
# VLM grounding thread (requires Gazebo Harmonic; placeholder until installed)
# ---------------------------------------------------------------------------

def _grab_gazebo_frame():
    """
    Return the latest Gazebo camera frame as JPEG bytes, or None if no frame yet.

    Uses the module-level _gz_latest_frame buffer filled by the gz transport
    callback registered in _setup_gz_node().  Converts raw R8G8B8 bytes to JPEG
    via Pillow (installed in the project venv).
    """
    with _gz_frame_lock:
        data = _gz_latest_frame["data"]
        w    = _gz_latest_frame["w"]
        h    = _gz_latest_frame["h"]
    if data is None:
        return None
    from PIL import Image as PILImage  # noqa: PLC0415
    import io                          # noqa: PLC0415
    img = PILImage.frombytes("RGB", (w, h), data)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _update_gz_pose(model_name: str,
                    x: float, y: float, z: float,
                    roll: float, pitch: float, yaw: float) -> None:
    """
    Move a Gazebo model via the /world/phase_c/set_pose service.

    Coordinates are Gazebo ENU (x=East, y=North, z=Up).
    Orientation is roll/pitch/yaw in radians (intrinsic ZYX).
    Silently returns if the gz node is not yet initialised.
    """
    if _gz_node is None:
        return
    from gz.msgs10 import pose_pb2, boolean_pb2  # noqa: PLC0415
    p = pose_pb2.Pose()
    p.name = model_name
    p.position.x = x
    p.position.y = y
    p.position.z = z
    qw, qx, qy, qz = _euler_to_quat(roll, pitch, yaw)
    p.orientation.w = qw
    p.orientation.x = qx
    p.orientation.y = qy
    p.orientation.z = qz
    # 50 ms timeout; non-blocking relative to control loop pace
    _gz_node.request(GZ_SET_POSE_SVC, p, pose_pb2.Pose, boolean_pb2.Boolean, 50)


def _vlm_grounding_thread(
    slot: LatestDetectionSlot,
    stop_event: threading.Event,
    expression: str,
    call_log: list,   # append (capture_ts, bbox_or_None, vlm_ms, raw_text)
    dry_run: bool,
) -> None:
    """
    VLM grounding thread: Gazebo frame → Jetson VLM → parse → write slot.

    Runs as fast as the VLM allows (~1 Hz for SmolVLM-500M).
    Never blocks the control thread.

    REQUIRES: Gazebo Harmonic running and llama-server healthy on localhost:8080.
    """
    prompt_fn = _probe.prompt_format_a

    while not stop_event.is_set():
        t_grab = time.monotonic()

        # Grab frame from Gazebo camera (returns None if no frame yet)
        frame_jpeg = _grab_gazebo_frame()
        if frame_jpeg is None:
            time.sleep(0.05)   # wait for first Gazebo frame
            continue

        if dry_run:
            # Simulate a successful grounding call
            bbox_cxcywh = {"cx": IMG_W / 2, "cy": IMG_H / 2, "w": 80.0, "h": 40.0}
            slot.write(t_grab, bbox_cxcywh, vlm_ms=500.0, raw_text="[dry-run]")
            call_log.append((t_grab, dict(bbox_cxcywh), 500.0, "[dry-run]"))
            time.sleep(1.0 / INJECT_RATE_HZ)
            continue

        # Build VLM request
        import base64, json as _json
        img_b64  = base64.b64encode(frame_jpeg).decode()
        prompt   = prompt_fn(expression, FRAME_W, FRAME_H)
        payload  = _probe._build_payload(img_b64, "image/jpeg", prompt, max_tokens=80)

        try:
            raw = _probe._post(payload, timeout=10)
            vlm_ms  = _probe._response_ms(raw)
            text    = _probe._response_text(raw)
            parsed  = _probe.parse_response_a(text, FRAME_W, FRAME_H)

            if parsed is not None and parsed.is_valid(FRAME_W, FRAME_H):
                bbox_cxcywh = xyxy_to_cxcywh(parsed.x1, parsed.y1, parsed.x2, parsed.y2)
                slot.write(t_grab, bbox_cxcywh, vlm_ms=vlm_ms, raw_text=text)
                call_log.append((t_grab, dict(bbox_cxcywh), vlm_ms, text))
            else:
                slot.write(t_grab, None, vlm_ms=vlm_ms, raw_text=text)
                call_log.append((t_grab, None, vlm_ms, text))

        except Exception as e:
            print(f"[vlm-thread] request error: {e}")
            call_log.append((t_grab, None, 0.0, f"error: {e}"))


# ---------------------------------------------------------------------------
# SITL process management (same as Phase B)
# ---------------------------------------------------------------------------

def _start_copter(log_path: Path) -> subprocess.Popen:
    instance_dir = SITL_DIR / "instance0"
    instance_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(ARDUCOPTER_BIN),
        "--model", "quad",
        "--speedup", "1",
        "--defaults", str(COPTER_PARM),
        f"--uartA=tcp:{COPTER_PORT}",
        "--instance", "0",
        f"--home={_SITL_HOME}",
    ]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w")
    return subprocess.Popen(cmd, stdout=log_file, stderr=log_file,
                            cwd=str(instance_dir))


def _wait_for_copter(timeout: float = 30.0) -> OffboardController:
    conn_str = f"tcp:127.0.0.1:{COPTER_PORT}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            m = mavutil.mavlink_connection(conn_str, source_system=255)
            hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=5.0)
            if hb:
                print(f"[sitl] copter port {COPTER_PORT} ready")
                m.mav.heartbeat_send(
                    mavutil.mavlink.MAV_TYPE_GCS,
                    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                    0, 0, mavutil.mavlink.MAV_STATE_ACTIVE,
                )
                m.mav.request_data_stream_send(
                    m.target_system, m.target_component,
                    mavutil.mavlink.MAV_DATA_STREAM_ALL, 5, 1,
                )
                m.close()
                break
        except Exception:
            pass
        time.sleep(0.5)
    time.sleep(2.0)
    return OffboardController(conn_str)


# ---------------------------------------------------------------------------
# Telemetry drain (same pattern as Phase B)
# ---------------------------------------------------------------------------

def _drain_telemetry(ctrl: OffboardController,
                     copter_ned: tuple, attitude: tuple,
                     copter_state: CopterState) -> tuple:
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
            ctrl._yaw_rad = msg.yaw
    # Update shared state for the injection thread
    with copter_state.lock:
        copter_state.ned      = copter_ned
        copter_state.attitude = attitude
    return copter_ned, attitude


# ---------------------------------------------------------------------------
# Phase C control step
# ---------------------------------------------------------------------------

def _control_step_c(
    tracker: ByteTracker,
    pid: CascadePID,
    slot: LatestDetectionSlot,
    copter_ned: tuple,
    rover_ned: tuple,
    attitude: tuple,
    last_det_ts: float,
) -> tuple:
    """
    One Phase C perception→control step.

    Oracle runs for GT scoring only — it does NOT drive control.
    Detections come from the async slot (VLM or oracle-inject).

    Returns:
        (oracle_bbox_gt, det, is_new_det, track, bbox_out, sp,
         pix_err_vs_oracle, new_det_ts)
    """
    # GT-only oracle (gimbal-stabilised nadir, same as Phase B)
    oracle_bbox_gt = oracle_project(copter_ned, rover_ned, 0.0, 0.0, attitude[2])

    # Read latest detection from the async slot
    det = slot.read()
    is_new_det = det.capture_ts > last_det_ts and det.bbox is not None
    new_det_ts = det.capture_ts if is_new_det else last_det_ts

    # Feed to ByteTrack only when a genuinely new detection arrived
    if is_new_det:
        dets = [{**det.bbox, "score": 1.0}]
    else:
        dets = []   # ByteTrack coasts its Kalman estimate

    tracks   = tracker.update(dets)
    track    = tracks[0] if tracks else None
    bbox_out = track.bbox if track else None
    sp       = pid.compute(bbox_out)

    # Following error vs oracle GT (pre-registered metric §5.3)
    pix_err_vs_oracle = None
    if oracle_bbox_gt is not None and bbox_out is not None:
        pix_err_vs_oracle = math.hypot(
            bbox_out["cx"] - oracle_bbox_gt["cx"],
            bbox_out["cy"] - oracle_bbox_gt["cy"],
        )

    return (oracle_bbox_gt, det, is_new_det, track,
            bbox_out, sp, pix_err_vs_oracle, new_det_ts)


# ---------------------------------------------------------------------------
# Trial runner
# ---------------------------------------------------------------------------

def run_trial(
    run_idx: int,
    duration_s: float,
    ctrl: OffboardController,
    slot: LatestDetectionSlot,
    dry_run: bool,
    csv_path: Path,
    inject_oracle: bool,
) -> dict:
    """Execute one trial.  Returns a metrics dict."""
    tracker = ByteTracker()
    pid     = CascadePID(kp_yaw=0.0)

    metrics = {
        "run": run_idx + 1,
        "mode": "inject-oracle" if inject_oracle else "vlm",
        "n_frames": 0,

        # Oracle GT coverage
        "oracle_frames": 0,
        "oracle_coverage_pct": 0.0,

        # Detection slot stats (VLM calls or oracle injections)
        "n_det_calls": 0,
        "n_det_valid": 0,
        "vlm_latency_ms": [],

        # Track coverage (coasted) and loss
        "n_track_frames": 0,          # frames with a live ByteTrack track
        "track_coverage_pct": 0.0,
        "track_loss_events": 0,

        # Coasting: consecutive frames with no NEW detection
        "coasting_max_consecutive": 0,

        # Re-seed (filled after a forced gap)
        "reseed_time_s": None,        # time from gap-end to first new track

        # Following error vs oracle
        "pix_errors_vs_oracle": [],
        "pixel_error_mean_px": 0.0,

        # Loop rate
        "loop_hz_mean": 0.0,
        "loop_dts": [],

        "notes": f"{'inject-oracle' if inject_oracle else 'vlm-grounding'} "
                 f"rover 0.25m/s north anchored to copter",
    }

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_file = open(csv_path, "w", newline="")
    writer   = csv.writer(csv_file)
    writer.writerow([
        "t_s",
        "copter_n", "copter_e", "copter_d",
        "rover_n", "rover_e", "rover_d",
        "oracle_cx", "oracle_cy", "oracle_w", "oracle_h",
        "det_bbox_cx", "det_bbox_cy", "det_new",
        "track_cx", "track_cy", "track_w", "track_h",
        "track_id",
        "pix_err_vs_oracle",
        "vx_cmd", "vy_cmd", "yaw_rate_cmd",
        "loop_dt_ms",
    ])

    copter_ned    = (0.0, 0.0, -TAKEOFF_ALT_M)
    attitude      = (0.0, 0.0, 0.0)
    copter_state  = CopterState(ned=copter_ned, attitude=attitude)

    # Anchor rover to copter's actual position at trial start
    if ctrl.mav is not None:
        while ctrl.mav.recv_match(blocking=False) is not None:
            pass  # flush stale backlog
        pos = ctrl.mav.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=5.0)
        if pos is not None:
            copter_ned = (pos.x, pos.y, pos.z)
            with copter_state.lock:
                copter_state.ned = copter_ned
        else:
            print(f"[run {run_idx+1}] WARNING: no fresh position; anchoring to {copter_ned}")

    rover_home_n = copter_ned[0]
    rover_home_e = copter_ned[1]

    def rover_fn(elapsed: float) -> tuple:
        return (
            rover_home_n + ROVER_START_N + ROVER_SPEED_MS * elapsed,
            rover_home_e,
            0.0,
        )

    # Start async detection thread
    stop_event     = threading.Event()
    call_log: list = []

    if inject_oracle:
        det_thread = threading.Thread(
            target=_oracle_inject_thread,
            args=(slot, stop_event, copter_state, rover_fn, run_idx, dry_run, call_log),
            daemon=True,
        )
    else:
        det_thread = threading.Thread(
            target=_vlm_grounding_thread,
            args=(slot, stop_event, _expression, call_log, dry_run),
            daemon=True,
        )

    det_thread.start()

    prev_track_id  = None
    last_det_ts    = 0.0
    coasting_count = 0   # consecutive frames without a new detection
    gap_ended_t    = None
    reseed_found   = False

    t_start  = time.monotonic()
    t_prev   = t_start
    hb_timer = t_start

    # Detect when the forced gap ends (run 3, inject-oracle mode)
    is_gap_run = inject_oracle and (run_idx + 1) == GAP_INJECT_RUN
    gap_end_elapsed = GAP_AT_S + GAP_DURATION_S

    print(f"\n[run {run_idx+1}] starting ({duration_s}s) "
          f"mode={'inject-oracle' if inject_oracle else 'vlm'} "
          f"{'DRY-RUN' if dry_run else ''}")

    while time.monotonic() - t_start < duration_s:
        t_now     = time.monotonic()
        dt        = t_now - t_prev
        t_prev    = t_now
        t_elapsed = t_now - t_start

        rover_ned = rover_fn(t_elapsed)

        # Drain telemetry → update shared copter state
        copter_ned, attitude = _drain_telemetry(
            ctrl, copter_ned, attitude, copter_state)

        # Phase C control step
        (oracle_bbox_gt, det, is_new_det, track, bbox_out, sp,
         pix_err, new_det_ts) = _control_step_c(
            tracker, pid, slot, copter_ned, rover_ned, attitude, last_det_ts)

        last_det_ts = new_det_ts

        # --- Update Gazebo model poses (NED → ENU: x=E, y=N, z=Up) ---
        # Camera always nadir (gimbal-stabilised); rover sits on ground (z=0.5=box half-h).
        if _gz_node is not None:
            _update_gz_pose(
                "downward_cam",
                copter_ned[1], copter_ned[0], -copter_ned[2],
                0.0, -math.pi / 2, 0.0,
            )
            _update_gz_pose(
                "target_rover",
                rover_ned[1], rover_ned[0], 0.5,
                0.0, 0.0, 0.0,
            )

        # --- Coasting counter ---
        if is_new_det:
            metrics["coasting_max_consecutive"] = max(
                metrics["coasting_max_consecutive"], coasting_count)
            coasting_count = 0
        else:
            coasting_count += 1

        # --- Re-seed detection (run 3 only) ---
        if is_gap_run and not reseed_found and gap_ended_t is None:
            if t_elapsed >= gap_end_elapsed:
                gap_ended_t = t_now
        if is_gap_run and gap_ended_t is not None and not reseed_found:
            if track is not None:
                metrics["reseed_time_s"] = round(t_now - gap_ended_t, 3)
                reseed_found = True
                print(f"[run {run_idx+1}] re-seed at t={t_elapsed:.1f}s  "
                      f"reseed_time={metrics['reseed_time_s']:.3f}s")

        # --- Track-loss events ---
        # Count only when the track disappears entirely (ByteTracker returns nothing).
        # ID changes between injections are NOT counted — at 1 Hz with score=1.0,
        # each new high-conf detection seeds a fresh track (pre-registered §3.4 limitation).
        if track is None and prev_track_id is not None:
            metrics["track_loss_events"] += 1
        prev_track_id = track.id if track else None

        # --- Coverage + error accumulation ---
        if oracle_bbox_gt is not None:
            metrics["oracle_frames"] += 1
        if track is not None:
            metrics["n_track_frames"] += 1
        if pix_err is not None:
            metrics["pix_errors_vs_oracle"].append(pix_err)

        # --- Send setpoint ---
        if not dry_run and ctrl.mav:
            ctrl.send_velocity_body(sp["vx"], sp["vy"], sp["vz"], sp["yaw_rate"])

        # Heartbeat at ~1 Hz
        if t_now - hb_timer >= 1.0:
            if not dry_run and ctrl.mav:
                ctrl.send_heartbeat()
            hb_timer = t_now

        # --- CSV log ---
        writer.writerow([
            f"{t_elapsed:.3f}",
            f"{copter_ned[0]:.2f}", f"{copter_ned[1]:.2f}", f"{copter_ned[2]:.2f}",
            f"{rover_ned[0]:.2f}",  f"{rover_ned[1]:.2f}",  f"{rover_ned[2]:.2f}",
            f"{oracle_bbox_gt['cx']:.1f}" if oracle_bbox_gt else "",
            f"{oracle_bbox_gt['cy']:.1f}" if oracle_bbox_gt else "",
            f"{oracle_bbox_gt['w']:.1f}"  if oracle_bbox_gt else "",
            f"{oracle_bbox_gt['h']:.1f}"  if oracle_bbox_gt else "",
            f"{det.bbox['cx']:.1f}"  if det.bbox else "",
            f"{det.bbox['cy']:.1f}"  if det.bbox else "",
            "1" if is_new_det else "0",
            f"{bbox_out['cx']:.1f}" if bbox_out else "",
            f"{bbox_out['cy']:.1f}" if bbox_out else "",
            f"{bbox_out['w']:.1f}"  if bbox_out else "",
            f"{bbox_out['h']:.1f}"  if bbox_out else "",
            track.id if track else "",
            f"{pix_err:.1f}" if pix_err is not None else "",
            f"{sp['vx']:.3f}", f"{sp['vy']:.3f}", f"{sp['yaw_rate']:.4f}",
            f"{dt*1000:.1f}",
        ])

        metrics["n_frames"] += 1
        if dt > 0:
            metrics["loop_dts"].append(dt)

        # Pace the loop at CONTROL_HZ
        target_dt = 1.0 / CONTROL_HZ
        sleep_t   = target_dt - (time.monotonic() - t_now)
        if sleep_t > 0:
            time.sleep(sleep_t)

    csv_file.close()
    stop_event.set()
    det_thread.join(timeout=3.0)

    # Finalise coasting counter
    metrics["coasting_max_consecutive"] = max(
        metrics["coasting_max_consecutive"], coasting_count)

    # Aggregate call_log
    metrics["n_det_calls"]  = len(call_log)
    metrics["n_det_valid"]  = sum(1 for _, b, *_ in call_log if b is not None)
    metrics["vlm_latency_ms"] = [ms for _, _, ms, *_ in call_log if ms > 0]

    # Aggregate loop stats
    if metrics["loop_dts"]:
        metrics["loop_hz_mean"] = round(
            1.0 / (sum(metrics["loop_dts"]) / len(metrics["loop_dts"])), 2)
    if metrics["pix_errors_vs_oracle"]:
        metrics["pixel_error_mean_px"] = round(
            sum(metrics["pix_errors_vs_oracle"]) / len(metrics["pix_errors_vs_oracle"]), 1)
    if metrics["n_frames"] > 0:
        metrics["oracle_coverage_pct"] = round(
            100.0 * metrics["oracle_frames"] / metrics["n_frames"], 1)
        metrics["track_coverage_pct"] = round(
            100.0 * metrics["n_track_frames"] / metrics["n_frames"], 1)

    print(
        f"[run {run_idx+1}] done  "
        f"hz={metrics['loop_hz_mean']:.1f}  "
        f"track_cov={metrics['track_coverage_pct']:.1f}%  "
        f"px_err={metrics['pixel_error_mean_px']:.1f}px  "
        f"track_losses={metrics['track_loss_events']}  "
        f"coasting_max={metrics['coasting_max_consecutive']}  "
        f"det_calls={metrics['n_det_calls']} valid={metrics['n_det_valid']}"
        + (f"  reseed={metrics['reseed_time_s']:.3f}s" if metrics['reseed_time_s'] else "")
    )
    return metrics


# ---------------------------------------------------------------------------
# Branch-1 pass/fail evaluation
# ---------------------------------------------------------------------------

def _eval_branch1(all_metrics: list[dict]) -> tuple[bool, str]:
    """
    Branch-1 criteria (pre-registered §6):
      1. Mean control Hz >= 15 across all runs.
      2. Max coasting run >= 15 consecutive frames without a new detection.
      3. Re-seed after forced gap < 2 s (run GAP_INJECT_RUN).
    Returns (pass, reason).
    """
    hz_mean = sum(r["loop_hz_mean"] for r in all_metrics) / len(all_metrics)

    coasting_max = max(r["coasting_max_consecutive"] for r in all_metrics)

    reseed_run = next(
        (r for r in all_metrics if r.get("reseed_time_s") is not None), None)
    reseed_ok = reseed_run is not None and reseed_run["reseed_time_s"] < 2.0
    reseed_val = reseed_run["reseed_time_s"] if reseed_run else None

    crit1 = hz_mean >= 15.0
    crit2 = coasting_max >= 15
    crit3 = reseed_ok

    ok = crit1 and crit2 and crit3
    reason = (
        f"hz={hz_mean:.2f} ({'✓' if crit1 else '✗'}≥15)  "
        f"coasting_max={coasting_max} ({'✓' if crit2 else '✗'}≥15)  "
        f"reseed={'%.3f' % reseed_val if reseed_val is not None else 'N/A'} "
        f"({'✓' if crit3 else '✗'}<2s)"
    )
    return ok, reason


# ---------------------------------------------------------------------------
# Results writing
# ---------------------------------------------------------------------------

def _std(xs: list) -> float:
    if len(xs) < 2:
        return 0.0
    mean = sum(xs) / len(xs)
    return math.sqrt(sum((x - mean) ** 2 for x in xs) / (len(xs) - 1))


def _format_branch1_table(runs: list[dict], b1_pass: bool, b1_reason: str) -> str:
    header = ("| Run | Loop Hz | Track cov (coasted) | Oracle cov | "
              "Px err vs oracle | Track losses | Coasting max | Re-seed s | Notes |")
    sep    = "|---|---|---|---|---|---|---|---|---|"
    rows   = []
    for r in runs:
        rs = r.get("reseed_time_s")
        rows.append(
            f"| {r['run']} "
            f"| {r['loop_hz_mean']} "
            f"| {r['track_coverage_pct']}% "
            f"| {r['oracle_coverage_pct']}% "
            f"| {r['pixel_error_mean_px']} "
            f"| {r['track_loss_events']} "
            f"| {r['coasting_max_consecutive']} "
            f"| {'%.3f' % rs if rs else '—'} "
            f"| {r['notes']} |"
        )
    hz_list  = [r["loop_hz_mean"] for r in runs]
    cov_list = [r["track_coverage_pct"] for r in runs]
    px_list  = [r["pixel_error_mean_px"] for r in runs]
    tl_total = sum(r["track_loss_events"] for r in runs)
    rows.append(
        f"| **Mean±std** "
        f"| {sum(hz_list)/len(hz_list):.2f}±{_std(hz_list):.2f} "
        f"| {sum(cov_list)/len(cov_list):.1f}% "
        f"| — | {sum(px_list)/len(px_list):.1f} "
        f"| {tl_total} total | — | — | — |"
    )
    status = "**Branch-1 PASS**" if b1_pass else "**Branch-1 FAIL**"
    return (
        "\n".join([header, sep] + rows)
        + f"\n\n{status} — {b1_reason}"
    )


def _patch_phase_c_md(table: str, date: str, mode: str) -> None:
    if not PHASE_C_MD.exists():
        print(f"[results] WARNING: {PHASE_C_MD} not found — skipping patch")
        return
    text = PHASE_C_MD.read_text()
    tag  = f"## Results — Branch-1 ({mode})"
    block = f"\n{tag}\n\nRun: {date}\n\n{table}\n"
    if tag in text:
        start = text.index(tag)
        # Find the next ## heading after our tag
        next_h = text.find("\n## ", start + len(tag))
        end = next_h if next_h != -1 else len(text)
        text = text[:start] + block.lstrip("\n") + text[end:]
    else:
        text = text.rstrip("\n") + "\n\n" + block
    PHASE_C_MD.write_text(text)
    print(f"[results] {PHASE_C_MD.relative_to(PHASE_C_MD.parent.parent.parent)} updated")


def _append_results_md(runs: list[dict], date: str, mode: str,
                       b1_pass: bool) -> None:
    hz_list = [r["loop_hz_mean"] for r in runs]
    hz_mean = sum(hz_list) / len(hz_list)
    px_list = [r["pixel_error_mean_px"] for r in runs]
    px_mean = sum(px_list) / len(px_list)
    row = (
        f"| {date[:10]} | Phase C {mode} | SmolVLM-500M Q8_0 | 15W locked "
        f"| hz={hz_mean:.2f} px_err={px_mean:.1f} "
        f"b1={'PASS' if b1_pass else 'FAIL'} |"
    )
    with RESULTS_MD.open("a") as f:
        f.write(row + "\n")
    print(f"[results] RESULTS.md row appended")


# ---------------------------------------------------------------------------
# Global expression (set in main, used by the VLM thread closure)
# ---------------------------------------------------------------------------
_expression = DEFAULT_EXPRESSION


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    global _expression

    parser = argparse.ArgumentParser(description="Phase C — VLM in the loop runner")
    parser.add_argument("--inject-oracle", action="store_true",
                        help="Branch-1 gate: inject oracle bbox, no VLM/Gazebo needed")
    parser.add_argument("--expression", default=DEFAULT_EXPRESSION,
                        help="NL expression for VLM grounding")
    parser.add_argument("--vlm-model",  default=DEFAULT_VLM_MODEL,
                        help="Override VLM GGUF path on Jetson")
    parser.add_argument("--skip-server", action="store_true",
                        help="Assume llama-server already running on Jetson")
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--runs",        type=int, default=3)
    parser.add_argument("--duration",    type=float, default=60.0)
    args = parser.parse_args()

    _expression = args.expression
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M UTC")
    ts       = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    mode     = "inject-oracle" if args.inject_oracle else "vlm"

    if not args.inject_oracle and not args.dry_run:
        print("WARNING: live VLM mode requires Gazebo Harmonic. "
              "Use --inject-oracle for the Branch-1 gate without Gazebo.")
        if not args.skip_server:
            print("Attempting to start VLM server on Jetson (will fail if Gazebo blocks).")

    SITL_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if not ARDUCOPTER_BIN.exists():
        sys.exit(f"ERROR: ArduCopter SITL binary not found: {ARDUCOPTER_BIN}\n"
                 f"Run: cd ~/ardupilot && python3 waf copter")

    print("=" * 65)
    print(f"Phase C — VLM in the loop  [{mode}]")
    print(f"Runs: {args.runs} × {args.duration}s  |  DRY-RUN={args.dry_run}")
    if args.inject_oracle:
        print(f"Branch-1 gate: forced re-seed gap in run {GAP_INJECT_RUN} "
              f"at t={GAP_AT_S}s (duration={GAP_DURATION_S}s)")
    print("=" * 65)

    copter_proc  = None
    gz_proc      = None
    pf_server    = None
    slot         = LatestDetectionSlot()

    try:
        # ---- Gazebo (live VLM mode only) ----
        if not args.inject_oracle and not args.dry_run:
            if not GZ_WORLD_SDF.exists():
                sys.exit(f"ERROR: Gazebo world not found: {GZ_WORLD_SDF}")
            gz_log = RAW_DIR / f"phase-c-{ts}-gz.log"
            print(f"[gazebo] starting gz sim headless (world={GZ_WORLD_SDF.name}) …")
            gz_proc = _start_gazebo(gz_log)
            time.sleep(3.0)          # let gz sim initialise before subscribing
            _setup_gz_node()
            print("[gazebo] waiting for first camera frame (up to 30 s) …")
            if not _wait_gazebo(timeout=30.0):
                sys.exit("ERROR: Gazebo camera topic produced no frame within 30 s. "
                         "Check gz sim log: " + str(gz_log))
            print("[gazebo] camera active — first frame received")

        # ---- VLM server (live mode only) ----
        if not args.inject_oracle and not args.skip_server and not args.dry_run:
            spec = _probe.MODELS[1]  # S2: SmolVLM-500M
            text_path   = args.vlm_model
            mmproj_path = DEFAULT_MMPROJ
            pf_server, load_failed, _ = _probe.start_server(
                spec, text_path, mmproj_path, args.dry_run)
            if load_failed:
                sys.exit("ERROR: VLM server failed to start")
            print("[vlm-server] healthy on localhost:8080")

        # ---- Start ArduCopter SITL ----
        copter_log = RAW_DIR / f"phase-c-{ts}-copter-sitl.log"
        print("[sitl] starting ArduCopter …")
        copter_proc = _start_copter(copter_log)

        ctrl = _wait_for_copter(timeout=30.0)

        if not args.dry_run:
            ctrl.connect_and_takeoff(target_alt_m=TAKEOFF_ALT_M)
        else:
            print("[dry-run] skipping connect/arm/takeoff")
            ctrl.mav = None

        # ---- Trials ----
        all_metrics = []
        for i in range(args.runs):
            csv_path = RAW_DIR / f"phase-c-{ts}-run{i+1}.csv"
            m = run_trial(
                run_idx=i,
                duration_s=args.duration,
                ctrl=ctrl,
                slot=slot,
                dry_run=args.dry_run,
                csv_path=csv_path,
                inject_oracle=args.inject_oracle,
            )
            all_metrics.append(m)
            if i < args.runs - 1 and not args.dry_run:
                print("[run] pausing 10s between runs …")
                time.sleep(10.0)

        # ---- Land ----
        if not args.dry_run and ctrl.mav:
            ctrl.land_and_disarm()
        ctrl.close()

        # ---- Evaluate Branch-1 ----
        b1_pass, b1_reason = _eval_branch1(all_metrics)
        print(f"\n{'=' * 65}")
        print(f"Branch-1 {'PASS ✓' if b1_pass else 'FAIL ✗'}  {b1_reason}")
        print(f"{'=' * 65}")

        # ---- Write results ----
        table = _format_branch1_table(all_metrics, b1_pass, b1_reason)
        print("\n" + table)
        _patch_phase_c_md(table, date_str, mode)
        _append_results_md(all_metrics, date_str, mode, b1_pass)

        print(f"\nPhase C [{mode}] complete.")
        print(f"Raw CSVs: {RAW_DIR}/phase-c-{ts}-run*.csv")

    finally:
        if copter_proc and copter_proc.poll() is None:
            copter_proc.terminate()
            try:
                copter_proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                copter_proc.kill()
        if gz_proc and gz_proc.poll() is None:
            gz_proc.terminate()
            try:
                gz_proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                gz_proc.kill()
        if pf_server:
            try:
                _probe.stop_server(pf_server)
            except Exception:
                pass


def run_unit_tests():
    print("run_phase_c.py unit tests:")
    _test_slot()
    _test_adapter()
    print("All unit tests passed.")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    if "--test" in sys.argv:
        run_unit_tests()
    else:
        main()
