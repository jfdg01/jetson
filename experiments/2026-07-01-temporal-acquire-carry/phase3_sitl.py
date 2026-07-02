"""Phase 3a: integrated end-to-end SITL follow -- real acquire, real carry (RQ-T.5).

Phase 1 injected the temporal design's costs; this closes the loop with the real
components: NadirCam renders the SITL world to 640x480 frames, ACQUIRE/REGROUND
is a live llama-server call to the Jetson ("the white car", deployed terse Q8_0),
CARRY is streaming SAM2 on the host 3090, and the occlusion is a drawn bridge the
car physically drives under -- nothing is masked or injected.

    .venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[1] / "runners"))

from follow_demo import vlm_acquire  # noqa: E402
from sitl_cam import NadirCam  # noqa: E402

CAPTION = "the white car"
LOSS_S = 3.0                     # seconds without a box before REGROUND (Phase 1 gate)
OCC_START, OCC_DUR = 30.0, 5.0   # full-occlusion window the bridge is sized for
SPEED = 0.25                     # m/s north; the pre-registered 3a gate speed
DURATION_S = 75.0
CONTROL_HZ = 20


class AcquireCarrySM:
    """ACQUIRE -> CARRY -> (loss gate) -> REGROUND over injected real components.

    submit(frame_bgr) -> Future[(box|None, wall_s)]; make_carry(frame_bgr, box)
    -> obj whose .step(frame_bgr) returns box|None; validate(box) -> bool rejects
    implausible acquire boxes (run 1: the VLM boxed a white road dash while the
    car was under the bridge). step() returns the box the controller may act on
    (None while blind).
    """

    def __init__(self, submit, make_carry, validate=None, loss_s: float = LOSS_S):
        self.submit, self.make_carry, self.validate = submit, make_carry, validate
        self.loss_s = loss_s
        self.state, self.fut, self.carry = "ACQUIRE", None, None
        self.last_seen: float | None = None
        self.n_attempts = self.n_regrounds = self.n_rejected = 0
        self.first_lock_t: float | None = None
        self.relock_walls: list[float] = []
        self._reground_t: float | None = None

    def step(self, t: float, frame_bgr):
        if self.state != "CARRY":
            if self.fut is None:
                self.fut = self.submit(frame_bgr)
                self.n_attempts += 1
            elif self.fut.done():
                box, _ = self.fut.result()
                self.fut = None
                if box is not None and self.validate and not self.validate(box):
                    self.n_rejected += 1
                    box = None  # implausible acquire -> treat as failed, relaunch
                if box is not None:
                    # ponytail: prompt SAM2 on the CURRENT frame with the ~2.5s-stale
                    # acquire box (~35 px drift at 0.25 m/s); velocity-extrapolate the
                    # box if faster gate speeds ever matter
                    self.carry = self.make_carry(frame_bgr, box)
                    self.last_seen = t
                    if self.first_lock_t is None:
                        self.first_lock_t = t
                    if self.state == "REGROUND":
                        self.relock_walls.append(round(t - self._reground_t, 2))
                    self.state = "CARRY"
            return None
        box = self.carry.step(frame_bgr)
        if box is not None:
            self.last_seen = t
        elif t - self.last_seen >= self.loss_s:
            self.state, self.carry = "REGROUND", None
            self.n_regrounds += 1
            self._reground_t = t
        return box


def run_trial(pb, ctrl, be, predictor, raw_dir: Path, image_size: int) -> dict:
    """One 75 s follow trial at SPEED. Orchestration mirrors phase1_sitl.run_trial;
    the oracle box is kept for the in-FOV metric only -- control sees pixels."""
    import torch

    from stream_carry import StreamCarry
    from sitl.cascade_pid import CascadePID
    from sitl.oracle_bbox import (
        FOCAL_PX, IMG_H, IMG_W, TARGET_LEN_M, TARGET_WID_M,
        project as oracle_project)

    pid = CascadePID(kp_yaw=0.0)  # yaw disabled, per Phase B rationale
    executor = ThreadPoolExecutor(max_workers=1)
    rgb = lambda f: np.ascontiguousarray(f[:, :, ::-1])  # noqa: E731

    def _acquire(path: str):
        try:
            return vlm_acquire(be, path, CAPTION, IMG_W, IMG_H)
        finally:
            os.unlink(path)

    def submit(frame_bgr):
        path = f"/dev/shm/p3a_acq_{time.monotonic_ns()}.png"
        cv2.imwrite(path, frame_bgr)
        return executor.submit(_acquire, path)

    def make_carry(frame_bgr, box):
        sc = StreamCarry(predictor, rgb(frame_bgr), box)
        return SimpleNamespace(step=lambda f: sc.step(rgb(f))[1])

    def validate(box):
        # size prior from known altitude: reject acquire boxes that can't be the
        # car (run 1: a white road dash, 3x too narrow, got locked while the car
        # was under the bridge)
        alt = max(1.0, -copter_ned[2])
        rw = (box[2] - box[0]) / (FOCAL_PX * TARGET_WID_M / alt)
        rh = (box[3] - box[1]) / (FOCAL_PX * TARGET_LEN_M / alt)
        return 0.5 <= rw <= 2.0 and 0.5 <= rh <= 2.0

    sm = AcquireCarrySM(submit, make_carry, validate)

    copter_ned = (0.0, 0.0, -pb.TAKEOFF_ALT_M)
    attitude = (0.0, 0.0, 0.0)
    if ctrl.mav is not None:  # fresh-position anchor (Phase B's stale-backlog fix)
        while ctrl.mav.recv_match(blocking=False) is not None:
            pass
        pos = ctrl.mav.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=5.0)
        if pos is not None:
            copter_ned = (pos.x, pos.y, pos.z)
        else:
            print(f"WARNING: no fresh LOCAL_POSITION_NED; using {copter_ned}")
    rover_home_n, rover_home_e = copter_ned[0], copter_ned[1]

    # bridge sized so the car is FULLY hidden exactly for t in [OCC_START, +DUR]
    hl = TARGET_LEN_M / 2
    c = lambda t: rover_home_n + pb.ROVER_START_N + SPEED * t  # noqa: E731
    bridge = (c(OCC_START) - hl, c(OCC_START + OCC_DUR) + hl)
    cam = NadirCam(bridge_n=bridge, road_e=rover_home_e)

    csv_path = raw_dir / f"trial-{SPEED}ms.csv"
    f = open(csv_path, "w", newline="")
    w = csv.writer(f)
    w.writerow(["t_s", "state", "copter_n", "copter_e", "copter_d",
                "rover_n", "rover_e", "in_fov", "occluded",
                "bbox_cx", "bbox_cy", "px_err", "vx_cmd", "vy_cmd", "loop_ms"])
    vid = cv2.VideoWriter(str(raw_dir / f"trial-{SPEED}ms.mp4"),
                          cv2.VideoWriter_fourcc(*"mp4v"), CONTROL_HZ, (IMG_W, IMG_H))

    from collections import deque
    hist: deque = deque(maxlen=48)  # (t, target_n, target_e) over ~2-4 s
    n_frames = in_fov_frames = 0
    carry_errs: list[float] = []
    carry_step_s: list[float] = []
    hb_timer = t_start = time.monotonic()

    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        while time.monotonic() - t_start < DURATION_S:
            t_now = time.monotonic()
            t = t_now - t_start

            rover_ned = (c(t), rover_home_e, 0.0)
            copter_ned, attitude = pb._drain_telemetry(ctrl, copter_ned, attitude)
            frame = cam.render(copter_ned, attitude[2], rover_ned)

            was_carry = sm.state == "CARRY"
            t_sm = time.monotonic()
            box = sm.step(t, frame)
            if was_carry:
                carry_step_s.append(time.monotonic() - t_sm)

            out = None
            if box is not None:
                out = {"cx": (box[0] + box[2]) / 2, "cy": (box[1] + box[3]) / 2,
                       "w": box[2] - box[0], "h": box[3] - box[1]}
                # target world position from the box's SOUTH edge (car rear): it
                # stays visible during bridge ingress, so its velocity is the true
                # car velocity even while the visible sliver shrinks (run-1 lag fix)
                s = FOCAL_PX / max(1.0, -copter_ned[2])
                a = (out["cx"] - IMG_W / 2) / s
                b = -(box[3] - IMG_H / 2) / s
                yc, ys = math.cos(attitude[2]), math.sin(attitude[2])
                hist.append((t, copter_ned[0] + b * yc - a * ys,
                             copter_ned[1] + a * yc + b * ys))
            sp = pid.compute(out)
            if out is None and len(hist) >= 2 and hist[-1][0] - hist[0][0] > 0.5:
                # ponytail: blind -> dead-reckon at the last estimated target
                # velocity instead of hovering (Phase 1's identified lever)
                dt = hist[-1][0] - hist[0][0]
                vn = max(-1.5, min(1.5, (hist[-1][1] - hist[0][1]) / dt))
                ve = max(-1.5, min(1.5, (hist[-1][2] - hist[0][2]) / dt))
                yc, ys = math.cos(attitude[2]), math.sin(attitude[2])
                sp = {"vx": vn * yc + ve * ys, "vy": -vn * ys + ve * yc,
                      "vz": 0.0, "yaw_rate": 0.0}
            if ctrl.mav:
                ctrl.send_velocity_body(sp["vx"], sp["vy"], sp["vz"], sp["yaw_rate"])
                if t_now - hb_timer >= 1.0:
                    ctrl.send_heartbeat()
                    hb_timer = t_now

            # metrics: in-FOV is pure geometry (ignores the bridge), as in Phase 1
            bbox_geo = oracle_project(copter_ned, rover_ned, 0.0, 0.0, attitude[2])
            occluded = bridge[0] <= rover_ned[0] - hl and rover_ned[0] + hl <= bridge[1]
            n_frames += 1
            in_fov_frames += bbox_geo is not None
            px_err = None
            if out is not None:
                px_err = math.hypot(out["cx"] - IMG_W / 2, out["cy"] - IMG_H / 2)
                carry_errs.append(px_err)

            loop_ms = (time.monotonic() - t_now) * 1000
            w.writerow([round(t, 2), sm.state,
                        round(copter_ned[0], 2), round(copter_ned[1], 2), round(copter_ned[2], 2),
                        round(rover_ned[0], 2), round(rover_ned[1], 2),
                        int(bbox_geo is not None), int(occluded),
                        round(out["cx"], 1) if out else "", round(out["cy"], 1) if out else "",
                        round(px_err, 1) if px_err is not None else "",
                        round(sp["vx"], 3), round(sp["vy"], 3), round(loop_ms, 1)])
            if box is not None:
                cv2.rectangle(frame, (int(box[0]), int(box[1])),
                              (int(box[2]), int(box[3])), (40, 200, 80), 2)
            cv2.putText(frame, f"{sm.state} t={t:.1f}s", (8, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (245, 245, 245), 2)
            vid.write(frame)

            sleep_t = 1.0 / CONTROL_HZ - (time.monotonic() - t_now)
            if sleep_t > 0:
                time.sleep(sleep_t)

    f.close()
    vid.release()
    executor.shutdown(wait=False, cancel_futures=True)

    m = {
        "speed_ms": SPEED,
        "image_size": image_size,
        "n_frames": n_frames,
        "achieved_hz": round(n_frames / DURATION_S, 1),
        "carry_fps": round(1.0 / (sum(carry_step_s) / len(carry_step_s)), 1)
                     if carry_step_s else None,
        "in_fov_frac": round(in_fov_frames / n_frames, 4),
        "first_lock_s": round(sm.first_lock_t, 2) if sm.first_lock_t else None,
        "n_acquire_attempts": sm.n_attempts,
        "n_rejected_acquires": sm.n_rejected,
        "n_regrounds": sm.n_regrounds,
        "relock_walls_s": sm.relock_walls,
        "carry_px_err_mean": round(sum(carry_errs) / len(carry_errs), 1) if carry_errs else None,
        "carry_frames": len(carry_errs),
        "recovered_after_occlusion": len(sm.relock_walls) >= 1,
    }
    print(f"[{SPEED} m/s] in_fov={m['in_fov_frac']:.3f} lock@{m['first_lock_s']}s "
          f"attempts={m['n_acquire_attempts']} regrounds={m['n_regrounds']} "
          f"relock={m['relock_walls_s']} px_err={m['carry_px_err_mean']} "
          f"hz={m['achieved_hz']} carry_fps={m['carry_fps']}")
    return m


def selfcheck() -> None:
    """Drive the SM with stub components: acquire resolves after 2 ticks; the
    carry holds for 5 frames then goes blind -> gate fires -> relock."""
    from concurrent.futures import Future

    pending: list[Future] = []

    def submit(_frame):
        fut = Future()
        pending.append(fut)
        return fut

    lives = {"n": 0}

    def make_carry(_frame, _box):
        lives["n"] = 5
        return SimpleNamespace(step=lambda f: (100, 100, 200, 200)
                               if (lives.__setitem__("n", lives["n"] - 1) or lives["n"] >= 0)
                               else None)

    sm = AcquireCarrySM(submit, make_carry,
                        validate=lambda b: b[2] - b[0] > 5, loss_s=3.0)
    frame = np.zeros((4, 4, 3), np.uint8)
    log = []
    for k in range(30):
        if pending and k in (2, 15, 20):      # acquire returns on these ticks
            box = (0, 0, 3, 3) if k == 15 else (0, 0, 10, 10)  # 15 = too small
            pending.pop(0).set_result((box, 2.5))
        box = sm.step(float(k), frame)
        log.append((k, sm.state, box is not None))
    states = [s for _, s, _ in log]
    assert states[0] == "ACQUIRE" and sm.first_lock_t == 2.0, log  # resolves@2
    assert states[10] == "REGROUND", log     # blind from 8, gate 3.0s fires @10
    assert sm.n_rejected == 1, log           # bad box @15 rejected, resubmit
    assert sm.relock_walls == [10.0], log    # fired@10, relocked@20
    assert sm.n_regrounds == 2 and states[-1] == "REGROUND", log  # re-lost @28
    print("selfcheck PASS  acquire->carry->gate->reground->relock")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--image-size", type=int, default=1024)
    args = ap.parse_args()
    if args.selfcheck:
        selfcheck()
        return

    import run_phase_b as pb
    from sitl.offboard import OffboardController
    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend
    from grounding.manifest import capture, write as write_manifest
    from sam2.sam2_video_predictor import SAM2VideoPredictor

    from carry_eval import MODEL

    raw_dir = HERE / "raw" / "phase3a-sitl"
    raw_dir.mkdir(parents=True, exist_ok=True)
    pb.SITL_DIR.mkdir(parents=True, exist_ok=True)
    if not pb.ARDUCOPTER_BIN.exists():
        sys.exit(f"SITL binary missing: {pb.ARDUCOPTER_BIN}")

    print("[3a] booting Jetson q8_0 server...", flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=1024)
    over = ([f"++model.image_size={args.image_size}"]
            if args.image_size != 1024 else [])
    predictor = SAM2VideoPredictor.from_pretrained(MODEL, hydra_overrides_extra=over)

    copter_proc = None
    try:
        copter_proc = pb._start_sitl(pb.ARDUCOPTER_BIN, pb.COPTER_PORT, pb.COPTER_PARM,
                                     0, raw_dir / "copter-sitl.log")
        time.sleep(5.0)
        ctrl = OffboardController(f"tcp:127.0.0.1:{pb.COPTER_PORT}")
        ctrl.connect_and_takeoff(target_alt_m=pb.TAKEOFF_ALT_M)
        trial = run_trial(pb, ctrl, be, predictor, raw_dir, args.image_size)
        ctrl.land_and_disarm()
        ctrl.close()
    finally:
        be.close()
        if copter_proc and copter_proc.poll() is None:
            copter_proc.terminate()

    gate = trial["in_fov_frac"] >= 0.90 and trial["recovered_after_occlusion"]
    summary = {"trial": trial, "gate_speed_ms": SPEED,
               "gate": "PASS" if gate else "FAIL"}
    cfg = {"caption": CAPTION, "loss_s": LOSS_S, "occ": [OCC_START, OCC_DUR],
           "speed": SPEED, "duration_s": DURATION_S, "hz": CONTROL_HZ,
           "image_size": args.image_size, "sam2": MODEL,
           "validate": "sizeprior-0.5-2.0", "deadreckon": True}
    out_dir = HERE / "runs" / "phase3a-sitl"
    write_manifest(capture("phase3a-sitl-integrated", cfg),
                   runs_dir=str(out_dir), results=summary)
    (out_dir / "results.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
