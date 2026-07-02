"""Phase 3a: integrated end-to-end SITL follow -- real acquire, real carry (RQ-T.5).

Phase 1 injected the temporal design's costs; this closes the loop with the real
components: NadirCam renders the SITL world to 640x480 frames, ACQUIRE/REGROUND
is a live llama-server call to the Jetson ("the white car", deployed terse Q8_0),
CARRY is streaming SAM2 on the host 3090, and the occlusion is a drawn bridge the
car physically drives under -- nothing is masked or injected.

    .venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py

Phase 3b (--remote-carry): same loop, but CARRY runs on the Jetson itself --
jetson_carry_service.py is booted over ssh (co-resident with the llama-server
VLM) and frames stream to it as JPEG over an ssh-forwarded TCP port. The gate
gains the campaign criterion: control rate >= 5 Hz with everything on-device.

    .venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py \
        --remote-carry --image-size 640
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
from sitl_cam import NadirCam, world_to_px  # noqa: E402

CAPTION = "the white car"
LOSS_S = 3.0                     # seconds without a box before REGROUND (Phase 1 gate)
OCC_START, OCC_DUR = 30.0, 5.0   # full-occlusion window the bridge is sized for
SPEED = 0.25                     # m/s north; the pre-registered 3a gate speed
DURATION_S = 75.0
CONTROL_HZ = 20


def pursuit_vel(hist_last, v_est, t, copter_ne, kp=0.5, vmax=2.5):
    """E5 blind chase: command the estimated target velocity PLUS a
    proportional pull toward the target's dead-reckoned position, so an
    accrued deficit closes instead of freezing. Velocity-only DR (E2/E4)
    matches speed at best: the ~5 s first-acquire hover deficit (5 m at
    1.0 m/s) is carried forever and velocity-estimate errors compound
    unchecked (E4 ladder-1.0: 0.39 m/s lateral error -> 11 m off-road)."""
    tl, pn, pe = hist_last
    vn, ve = v_est
    en = pn + vn * (t - tl) - copter_ne[0]
    ee = pe + ve * (t - tl) - copter_ne[1]
    vn, ve = vn + kp * en, ve + kp * ee
    m = math.hypot(vn, ve)
    if m > vmax:
        vn, ve = vn * vmax / m, ve * vmax / m
    return vn, ve


def gate_box(box, score, mode: str, tau: float, motion_stale: bool):
    """E4 loss gate: demote a carry box to None when it can't be trusted, so the
    existing LossGate/DR/REGROUND machinery fires on a confident-but-wrong box
    (E2's occluder latch) exactly as it does on an honest loss.

    score: SAM2.1 object-score logit (None on the remote-carry path -> score
    mode is inert there). motion_stale: loop-computed 'estimated target has
    been static too long' flag (mode == motion)."""
    if box is None:
        return None
    if mode == "score" and score is not None and score < tau:
        return None
    if mode == "motion" and motion_stale:
        return None
    return box


class AcquireCarrySM:
    """ACQUIRE -> CARRY -> (loss gate) -> REGROUND over injected real components.

    submit(frame_bgr) -> Future[(box|None, wall_s)]; make_carry(submit_frame,
    box, t_submit) -> obj whose .step(frame_bgr) returns box|None (the frame is
    the one the box was computed on, E4); validate(box) -> bool rejects
    implausible acquire boxes (run 1: the VLM boxed a white road dash while the
    car was under the bridge). step() returns the box the controller may act on
    (None while blind).
    """

    def __init__(self, submit, make_carry, validate=None, loss_s: float = LOSS_S):
        self.submit, self.make_carry, self.validate = submit, make_carry, validate
        self.loss_s = loss_s
        self.state, self.fut, self.carry = "ACQUIRE", None, None
        self._submit_frame, self._submit_t = None, None
        self.last_seen: float | None = None
        self.n_attempts = self.n_regrounds = self.n_rejected = 0
        self.first_lock_t: float | None = None
        self.relock_walls: list[float] = []
        self._reground_t: float | None = None

    def step(self, t: float, frame_bgr):
        if self.state != "CARRY":
            if self.fut is None:
                self.fut = self.submit(frame_bgr)
                # keep the submitted frame: the VLM box is valid on THIS frame,
                # so carry must be initialized on it, not on the ~2.5-5s-later
                # frame where the box no longer overlaps a moving target (E4)
                self._submit_frame, self._submit_t = frame_bgr.copy(), t
                self.n_attempts += 1
            elif self.fut.done():
                box, _ = self.fut.result()
                self.fut = None
                if box is not None and self.validate and not self.validate(box):
                    self.n_rejected += 1
                    box = None  # implausible acquire -> treat as failed, relaunch
                if box is not None:
                    self.carry = self.make_carry(self._submit_frame, box,
                                                 self._submit_t)
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


def run_trial(pb, ctrl, be, predictor, raw_dir: Path, image_size: int,
              carry_conn=None, twin: str | None = None,
              loss_gate: str = "none", score_tau: float = 0.0,
              dr: str = "velocity") -> dict:
    """One 75 s follow trial at SPEED. Orchestration mirrors phase1_sitl.run_trial;
    the oracle box is kept for the in-FOV metric only -- control sees pixels.
    carry_conn set (3b): CARRY steps go to jetson_carry_service over the tunnel."""
    import torch

    from sitl.cascade_pid import CascadePID
    from sitl.oracle_bbox import (
        FOCAL_PX, IMG_H, IMG_W, TARGET_LEN_M, TARGET_WID_M,
        project as oracle_project)

    pid = CascadePID(kp_yaw=0.0)  # yaw disabled, per Phase B rationale
    executor = ThreadPoolExecutor(max_workers=1)
    rgb = lambda f: np.ascontiguousarray(f[:, :, ::-1])  # noqa: E731
    jpg = lambda f: cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()  # noqa: E731

    def _acquire(path: str):
        try:
            return vlm_acquire(be, path, CAPTION, IMG_W, IMG_H)
        finally:
            os.unlink(path)

    def submit(frame_bgr):
        path = f"/dev/shm/p3a_acq_{time.monotonic_ns()}.png"
        cv2.imwrite(path, frame_bgr)
        return executor.submit(_acquire, path)

    if carry_conn is not None:
        def _remote_step(f):
            carry_conn.send({"cmd": "step", "jpg": jpg(f)})
            return carry_conn.recv()["box"]

        def make_carry(frame_bgr, box, t_submit):
            # ponytail: no catch-up replay / score gate on the 3b remote path --
            # E4 runs the local rig; port both when 3b re-gates
            carry_conn.send({"cmd": "init", "jpg": jpg(frame_bgr), "box": list(box)})
            carry_conn.recv()
            return SimpleNamespace(step=_remote_step)
    else:
        from stream_carry import StreamCarry

        def make_carry(frame_bgr, box, t_submit):
            sc = StreamCarry(predictor, rgb(frame_bgr), box)
            # E4 catch-up: carry is initialized on the (stale) submit frame,
            # where the VLM box is true; replay the frames buffered since, so
            # the track is current when the loop resumes AND hist gets the
            # target's gap trajectory (seeds DR with a real velocity, so a
            # target that outran the FOV during acquire can be chased blind)
            for tb, fb, cn, yawb in [e for e in acq_buf if e[0] > t_submit]:
                b = sc.step(rgb(fb))[1]
                if b is not None:
                    hist.append((tb, *box_to_world(b, cn, yawb)))
            motion_stale[0] = False

            def step(f):
                b = sc.step(rgb(f))[1]
                score_cell[0] = sc.last_score
                return gate_box(b, sc.last_score, loss_gate, score_tau,
                                motion_stale[0])
            return SimpleNamespace(step=step)

    def validate(box):
        # size prior from known altitude: reject acquire boxes that can't be the
        # car (run 1: a white road dash, 3x too narrow, got locked while the car
        # was under the bridge)
        alt = max(1.0, -copter_ned[2])
        rw = (box[2] - box[0]) / (FOCAL_PX * TARGET_WID_M / alt)
        rh = (box[3] - box[1]) / (FOCAL_PX * TARGET_LEN_M / alt)
        return 0.5 <= rw <= 2.0 and 0.5 <= rh <= 2.0

    def box_to_world(box, cop_ned, yaw):
        # target world position from the box's SOUTH edge (car rear): it stays
        # visible during bridge ingress, so its velocity is the true car velocity
        # even while the visible sliver shrinks (run-1 lag fix)
        s = FOCAL_PX / max(1.0, -cop_ned[2])
        a = ((box[0] + box[2]) / 2 - IMG_W / 2) / s
        b = -(box[3] - IMG_H / 2) / s
        yc, ys = math.cos(yaw), math.sin(yaw)
        return cop_ned[0] + b * yc - a * ys, cop_ned[1] + a * yc + b * ys

    def hist_vel():
        if len(hist) < 2 or hist[-1][0] - hist[0][0] <= 0.5:
            return None
        dt = hist[-1][0] - hist[0][0]
        # was 1.5, saturated at the 1.5 m/s trial speed (E2); raised so DR
        # can track the top test speed instead of clamping exactly when needed
        vn = max(-2.5, min(2.5, (hist[-1][1] - hist[0][1]) / dt))
        ve = max(-2.5, min(2.5, (hist[-1][2] - hist[0][2]) / dt))
        return vn, ve

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

    # E3 twin distractor: an identical white car. crossing = 12 m ahead in the
    # +3 m lane driving south (opposing) at SPEED, passes ~t=24s; decoy = parked
    # 2 m past the bridge north edge in the same lane (the only car REGROUND sees
    # while the true car is occluded).
    if twin == "crossing":
        d0 = rover_home_n + pb.ROVER_START_N + 12.0
        distractor = lambda t: (d0 - SPEED * t, rover_home_e + 3.0, 0.0)  # noqa: E731
    elif twin == "decoy":
        dn = bridge[1] + 2.0
        distractor = lambda t: (dn, rover_home_e, 0.0)  # noqa: E731
    else:
        distractor = None
    twin_rows: list[tuple[float, float, float]] = []  # (t, d_true_px, d_dist_px) when boxed

    csv_path = raw_dir / f"trial-{SPEED}ms.csv"
    f = open(csv_path, "w", newline="")
    w = csv.writer(f)
    w.writerow(["t_s", "state", "copter_n", "copter_e", "copter_d",
                "rover_n", "rover_e", "in_fov", "occluded",
                "bbox_cx", "bbox_cy", "px_err", "vx_cmd", "vy_cmd", "loop_ms",
                "dist_n", "dist_e", "d_true_px", "d_dist_px", "carry_score"])
    vid = cv2.VideoWriter(str(raw_dir / f"trial-{SPEED}ms.mp4"),
                          cv2.VideoWriter_fourcc(*"mp4v"), CONTROL_HZ, (IMG_W, IMG_H))

    from collections import deque
    hist: deque = deque(maxlen=48)  # (t, target_n, target_e) over ~2-4 s
    acq_buf: deque = deque(maxlen=24)  # (t, frame, copter_ned, yaw) @0.5 s while not CARRY (E4 catch-up)
    score_cell = [None]      # SAM2 object-score logit of the last carry step (local path)
    motion_stale = [False]   # motion loss-gate latch; reset on each (re)lock
    stale_t0 = None
    n_frames = in_fov_frames = 0
    carry_errs: list[float] = []
    carry_step_s: list[float] = []
    hb_timer = t_start = time.monotonic()

    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        while time.monotonic() - t_start < DURATION_S:
            t_now = time.monotonic()
            t = t_now - t_start

            rover_ned = (c(t), rover_home_e, 0.0)
            dnd = distractor(t) if distractor else None
            copter_ned, attitude = pb._drain_telemetry(ctrl, copter_ned, attitude)
            frame = cam.render(copter_ned, attitude[2], rover_ned, dnd)
            if sm.state != "CARRY" and n_frames % 10 == 0:  # E4: catch-up buffer
                acq_buf.append((t, frame.copy(), copter_ned, attitude[2]))

            was_carry = sm.state == "CARRY"
            t_sm = time.monotonic()
            box = sm.step(t, frame)
            if was_carry:
                carry_step_s.append(time.monotonic() - t_sm)

            out = None
            if box is not None:
                out = {"cx": (box[0] + box[2]) / 2, "cy": (box[1] + box[3]) / 2,
                       "w": box[2] - box[0], "h": box[3] - box[1]}
                hist.append((t, *box_to_world(box, copter_ned, attitude[2])))
            if loss_gate == "motion" and sm.state == "CARRY" and out is not None:
                # E4 motion gate: we were tracking a mover; a box whose estimated
                # world position sits still > 2 s is an occluder latch -> distrust
                # it from the next step on (gate_box), LossGate/REGROUND take over.
                # ponytail: a target that legitimately parks also trips this;
                # REGROUND re-locks a visible parked car, cost = one reground
                v = hist_vel()
                if v is not None and math.hypot(*v) < 0.1:
                    stale_t0 = t if stale_t0 is None else stale_t0
                    if t - stale_t0 > 2.0:
                        motion_stale[0] = True
                else:
                    stale_t0 = None
            sp = pid.compute(out)
            v_blind = hist_vel() if out is None else None
            if v_blind is not None:
                # ponytail: blind -> dead-reckon at the last estimated target
                # velocity instead of hovering (Phase 1's identified lever)
                vn, ve = v_blind
                if dr == "pursuit":  # E5: also close the gap, don't just match speed
                    vn, ve = pursuit_vel(hist[-1], (vn, ve), t,
                                         (copter_ned[0], copter_ned[1]))
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

            # E3: box-center distance (px) to the true car vs the distractor
            d_true_px = d_dist_px = ""
            if dnd is not None:
                true_uv = world_to_px((rover_ned[0], rover_ned[1]), copter_ned, attitude[2])[0]
                dist_uv = world_to_px((dnd[0], dnd[1]), copter_ned, attitude[2])[0]
                if out is not None:
                    bc = np.array([out["cx"], out["cy"]])
                    d_true_px = round(float(np.hypot(*(bc - true_uv))), 1)
                    d_dist_px = round(float(np.hypot(*(bc - dist_uv))), 1)
                    twin_rows.append((t, d_true_px, d_dist_px))

            loop_ms = (time.monotonic() - t_now) * 1000
            w.writerow([round(t, 2), sm.state,
                        round(copter_ned[0], 2), round(copter_ned[1], 2), round(copter_ned[2], 2),
                        round(rover_ned[0], 2), round(rover_ned[1], 2),
                        int(bbox_geo is not None), int(occluded),
                        round(out["cx"], 1) if out else "", round(out["cy"], 1) if out else "",
                        round(px_err, 1) if px_err is not None else "",
                        round(sp["vx"], 3), round(sp["vy"], 3), round(loop_ms, 1),
                        round(dnd[0], 2) if dnd else "", round(dnd[1], 2) if dnd else "",
                        d_true_px, d_dist_px,
                        round(score_cell[0], 3)
                        if was_carry and score_cell[0] is not None else ""])
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
    if twin:
        # id_switch_s: longest continuous span the box sat closer to the distractor
        # than to the true car (S1 FAIL if > 1 s). final following distance decides
        # S2 wrong-lock, but only counts if a REGROUND actually fired (amendment).
        best = 0.0
        run_start = None
        for tt, dtrue, ddist in twin_rows:
            if ddist < dtrue:
                run_start = tt if run_start is None else run_start
                best = max(best, tt - run_start)
            else:
                run_start = None
        rov_end = (c(t), rover_home_e)
        d_end = distractor(t)
        fd_true = math.hypot(copter_ned[0] - rov_end[0], copter_ned[1] - rov_end[1])
        fd_dist = math.hypot(copter_ned[0] - d_end[0], copter_ned[1] - d_end[1])
        m["twin"] = {
            "mode": twin,
            "id_switch_s": round(best, 2),
            "frac_box_closer_distractor":
                round(sum(dd < dt for _, dt, dd in twin_rows) / len(twin_rows), 3)
                if twin_rows else None,
            "n_boxed_twin_frames": len(twin_rows),
            "final_d_true_m": round(fd_true, 2),
            "final_d_dist_m": round(fd_dist, 2),
            "closest_at_end": "distractor" if fd_dist < fd_true else "true",
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
    carried: list[int] = []  # pixel value of the frame handed to make_carry

    def make_carry(frame, _box, _t):
        lives["n"] = 5
        carried.append(int(frame[0, 0, 0]))
        return SimpleNamespace(step=lambda f: (100, 100, 200, 200)
                               if (lives.__setitem__("n", lives["n"] - 1) or lives["n"] >= 0)
                               else None)

    sm = AcquireCarrySM(submit, make_carry,
                        validate=lambda b: b[2] - b[0] > 5, loss_s=3.0)
    log = []
    for k in range(30):
        if pending and k in (2, 15, 20):      # acquire returns on these ticks
            box = (0, 0, 3, 3) if k == 15 else (0, 0, 10, 10)  # 15 = too small
            pending.pop(0).set_result((box, 2.5))
        frame = np.full((4, 4, 3), k, np.uint8)  # tick-stamped: E4 identity check
        box = sm.step(float(k), frame)
        log.append((k, sm.state, box is not None))
    states = [s for _, s, _ in log]
    assert states[0] == "ACQUIRE" and sm.first_lock_t == 2.0, log  # resolves@2
    assert states[10] == "REGROUND", log     # blind from 8, gate 3.0s fires @10
    assert sm.n_rejected == 1, log           # bad box @15 rejected, resubmit
    assert sm.relock_walls == [10.0], log    # fired@10, relocked@20
    assert sm.n_regrounds == 2 and states[-1] == "REGROUND", log  # re-lost @28
    # E4: carry must be initialized on the SUBMIT-tick frame (0, 16), not the
    # resolve-tick frame (2, 20) -- the VLM box is only true on the former
    assert carried == [0, 16], (carried, log)
    b = (0, 0, 10, 10)
    assert gate_box(b, -1.0, "score", 0.0, False) is None   # low score -> loss
    assert gate_box(b, 1.0, "score", 0.0, False) is b
    assert gate_box(b, None, "score", 0.0, False) is b      # remote path inert
    assert gate_box(b, 1.0, "motion", 0.0, True) is None    # stale flag -> loss
    assert gate_box(None, 5.0, "none", 0.0, False) is None
    # E5 pursuit_vel truth table: copter ON the predicted position -> pure
    # velocity match; 4 m deficit north -> vn = 1 + 0.5*4 = 3 -> clamped to
    # 2.5 total; lateral error pulls back with the correct sign
    assert pursuit_vel((10.0, 5.0, 0.0), (1.0, 0.0), 12.0, (7.0, 0.0)) == (1.0, 0.0)
    v = pursuit_vel((10.0, 5.0, 0.0), (1.0, 0.0), 12.0, (3.0, 0.0))
    assert v == (2.5, 0.0), v
    vn, ve = pursuit_vel((10.0, 5.0, 0.0), (1.0, 0.0), 12.0, (7.0, 2.0))
    assert vn == 1.0 and ve == -1.0, (vn, ve)
    print("selfcheck PASS  acquire->carry->gate->reground->relock + E4 submit-frame/gate_box"
          " + E5 pursuit_vel")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--image-size", type=int, default=1024)
    ap.add_argument("--remote-carry", action="store_true",
                    help="3b: run CARRY on the Jetson via jetson_carry_service")
    ap.add_argument("--trt-encoder", default=None,
                    help="3b: TensorRT .plan on the Jetson (e.g. enc768.plan); E1 speedup")
    ap.add_argument("--speed", type=float, default=0.25,
                    help="E2: rover north speed m/s (bridge auto-scales via the SPEED closure)")
    ap.add_argument("--twin", choices=["crossing", "decoy"], default=None,
                    help="E3: add an identical distractor car (crossing | decoy)")
    ap.add_argument("--loss-gate", choices=["none", "score", "motion"], default="none",
                    help="E4: demote untrusted carry boxes to loss so REGROUND "
                         "fires on a confident-but-wrong box (E2 occluder latch)")
    ap.add_argument("--score-tau", type=float, default=0.0,
                    help="E4: SAM2 object-score logit threshold (loss-gate=score)")
    ap.add_argument("--dr", choices=["velocity", "pursuit"], default="velocity",
                    help="E5: blind dead-reckoning mode -- velocity (E2/E4 "
                         "baseline: match estimated speed) or pursuit (also "
                         "close toward the dead-reckoned position, 2.5 m/s cap)")
    args = ap.parse_args()
    if args.selfcheck:
        selfcheck()
        return
    global SPEED
    SPEED = args.speed

    import run_phase_b as pb
    from sitl.offboard import OffboardController
    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend
    from grounding.manifest import capture, write as write_manifest

    from carry_eval import MODEL

    phase = "phase3b-sitl" if args.remote_carry else "phase3a-sitl"
    raw_dir = HERE / "raw" / phase
    raw_dir.mkdir(parents=True, exist_ok=True)
    pb.SITL_DIR.mkdir(parents=True, exist_ok=True)
    if not pb.ARDUCOPTER_BIN.exists():
        sys.exit(f"SITL binary missing: {pb.ARDUCOPTER_BIN}")

    print("[3] booting Jetson q8_0 server...", flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=1024)

    predictor = carry_conn = svc_pid = tunnel = None
    if args.remote_carry:
        import socket
        import subprocess
        from multiprocessing import AuthenticationError
        from multiprocessing.connection import Client

        print("[3b] booting Jetson carry service...", flush=True)
        out = subprocess.run(
            ["ssh", "jetson",
             # ponytail: ';' not '&&' -- with '&&' the '&' backgrounds a subshell that
             # still holds sshd's stdout pipe while waiting on python, so ssh never returns
             f"cd ~/sam2-bench; nohup .venv/bin/python jetson_carry_service.py "
             f"--image-size {args.image_size}"
             f"{f' --trt-encoder {args.trt_encoder}' if args.trt_encoder else ''}"
             f" > /tmp/carry_svc.log 2>&1 < /dev/null & echo $!"],
            capture_output=True, text=True, timeout=60)
        svc_pid = int(out.stdout.strip().split()[-1])
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            lport = s.getsockname()[1]
        tunnel = subprocess.Popen(["ssh", "-N", "-o", "ExitOnForwardFailure=yes",
                                   "-L", f"{lport}:127.0.0.1:18081", "jetson"])
        deadline = time.monotonic() + 120  # model load ~15 s; generous
        while True:
            try:
                carry_conn = Client(("127.0.0.1", lport), authkey=b"carry")
                break
            except (ConnectionError, OSError, EOFError, AuthenticationError):
                # tunnel accepts locally, then the remote refusal surfaces
                # mid-handshake as EOF/auth failure -> still "not up yet"
                if time.monotonic() > deadline:
                    raise RuntimeError("carry service not up after 120 s")
                time.sleep(2.0)
    else:
        from sam2.sam2_video_predictor import SAM2VideoPredictor
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
        trial = run_trial(pb, ctrl, be, predictor, raw_dir, args.image_size,
                          carry_conn=carry_conn, twin=args.twin,
                          loss_gate=args.loss_gate, score_tau=args.score_tau,
                          dr=args.dr)
        ctrl.land_and_disarm()
        ctrl.close()
    finally:
        be.close()
        if carry_conn is not None:
            carry_conn.close()
        if svc_pid:
            import subprocess
            subprocess.run(["ssh", "jetson", f"kill {svc_pid}"], timeout=30)
        if tunnel is not None:
            tunnel.terminate()
        if copter_proc and copter_proc.poll() is None:
            copter_proc.terminate()

    gate = trial["in_fov_frac"] >= 0.90 and trial["recovered_after_occlusion"]
    if args.remote_carry:  # campaign criterion: >=5 Hz control with carry on-device
        # ponytail: carry_fps, not achieved_hz -- whole-trial hz is inflated by the
        # blind ACQUIRE/REGROUND phases (no perception in the loop); the criterion
        # means the loop rate while actually tracking. The 2026-07-02 recorded run
        # predates this fix (its results.json PASS line used achieved_hz; README
        # records the honest per-leg verdict).
        gate = gate and trial["carry_fps"] >= 5.0
    summary = {"trial": trial, "gate_speed_ms": SPEED,
               "gate": "PASS" if gate else "FAIL"}
    cfg = {"caption": CAPTION, "loss_s": LOSS_S, "occ": [OCC_START, OCC_DUR],
           "speed": SPEED, "duration_s": DURATION_S, "hz": CONTROL_HZ,
           "image_size": args.image_size, "sam2": MODEL,
           "validate": "sizeprior-0.5-2.0", "deadreckon": True,
           "twin": args.twin,
           "loss_gate": args.loss_gate, "score_tau": args.score_tau,
           "dr": args.dr, "catchup_replay": True,
           "carry": "jetson-remote" if args.remote_carry else "host-3090"}
    out_dir = HERE / "runs" / phase
    write_manifest(capture(f"{phase}-integrated", cfg),
                   runs_dir=str(out_dir), results=summary)
    (out_dir / "results.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
