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
RETARGET_CAPTION = "the blue car"   # E9: mid-follow NL switch command
ESCORT_COLOR = (230, 90, 40)        # E9: escort car body, BGR (vivid blue)
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


def blob_chase_box(blob):
    """E11 chase-hold: blob dict -> a box whose SOUTH edge is the sweep CENTER
    row, for box_to_world. The sweep spans rear-at-base .. nose-at-now, so its
    center trails the true car center by only ~v*lag/2 (~0.9 m at 3 m/s);
    anchoring on the sweep's own south edge (rear at base, a full v*lag behind)
    would park the copter far enough back to clip the nose out of the 4.33 m
    half-footprint at 3 m/s -- exactly the high/clipped frames Stage 0 (E6)
    showed the VLM grounds onto road dashes. The residual lag is near-constant
    at a fixed diff baseline, so it differentiates out of hist_vel."""
    return (blob["cx"] - blob["w"] / 2, blob["cy"] - blob["h"] / 2,
            blob["cx"] + blob["w"] / 2, blob["cy"])


def _ground_affine(prev_ned, prev_yaw, cur_ned, cur_yaw):
    """Pixel map prev frame -> cur frame for GROUND points. The nadir camera is
    an affine map of the ground plane (sitl_cam), so three world anchors pin it
    exactly; real hardware substitutes the EKF pose delta the same way."""
    anchors = np.array([[cur_ned[0], cur_ned[1]],
                        [cur_ned[0] + 5.0, cur_ned[1]],
                        [cur_ned[0], cur_ned[1] + 5.0]])
    src = world_to_px(anchors, prev_ned, prev_yaw).astype(np.float32)
    dst = world_to_px(anchors, cur_ned, cur_yaw).astype(np.float32)
    return cv2.getAffineTransform(src, dst)


def motion_blob(cur_bgr, prev_bgr, M, min_area: int = 800):
    """E6 motion-hold: ego-motion-compensated frame diff -> {cx,cy,w,h}|None.
    The car is the scene's only mover, so after warping prev onto cur's pose
    the diff is the car's swept region (ground texture cancels); the union
    bbox of the diff components is a pixel target the PID can hold in FOV.
    min_area 800 px^2: the 0.5 m/s / 0.35 s worst case sweeps ~4000 px^2
    pre-morph -- 800 rejects warp-seam noise without rejecting the car."""
    h, w = cur_bgr.shape[:2]
    warped = cv2.warpAffine(prev_bgr, M, (w, h))
    valid = cv2.warpAffine(np.full((h, w), 255, np.uint8), M, (w, h))
    diff = cv2.absdiff(cv2.cvtColor(cur_bgr, cv2.COLOR_BGR2GRAY),
                       cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY))
    diff[valid < 255] = 0  # ponytail: drop partially-interpolated warp border
    mask = cv2.morphologyEx((diff > 40).astype(np.uint8), cv2.MORPH_OPEN,
                            np.ones((5, 5), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    keep = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= min_area // 4]
    if not keep or sum(int(stats[i, cv2.CC_STAT_AREA]) for i in keep) < min_area:
        return None
    x0 = min(stats[i, cv2.CC_STAT_LEFT] for i in keep)
    y0 = min(stats[i, cv2.CC_STAT_TOP] for i in keep)
    x1 = max(stats[i, cv2.CC_STAT_LEFT] + stats[i, cv2.CC_STAT_WIDTH] for i in keep)
    y1 = max(stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT] for i in keep)
    return {"cx": (x0 + x1) / 2.0, "cy": (y0 + y1) / 2.0,
            "w": float(x1 - x0), "h": float(y1 - y0)}


def reground_motion_ok(box, cur_bgr, base_bgr, M, pad: float = 60.0):
    """E7 reground gate: accept a REGROUND box only if it sits on the scene's
    mover. The size prior is identity-blind (E3-S2: a parked pixel-identical
    decoy captured the reground 3/3), but motion is not -- the true target
    moves, the decoy is parked. box is in base-frame pixels (the VLM drew it
    on the submit frame; base is the buffered frame nearest the submit time),
    M maps base -> cur ground pixels, so the ego-compensated diff sweep
    contains the box center by construction when the box is on the mover.
    blob None (nothing moves: target still occluded, or decoy-only scene)
    -> reject and keep drawing. pad 60 px ~= 1 m at F/alt ~63 px/m: covers
    the <=0.25 s base-vs-submit pose slack (<=0.6 m ~= 39 px at the 2.5 m/s
    cap) + warp error, still well under the decoy's >=2 m offset."""
    blob = motion_blob(cur_bgr, base_bgr, M)
    if blob is None:
        return False
    cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    u = M[0, 0] * cx + M[0, 1] * cy + M[0, 2]
    v = M[1, 0] * cx + M[1, 1] * cy + M[1, 2]
    return (abs(u - blob["cx"]) <= blob["w"] / 2 + pad
            and abs(v - blob["cy"]) <= blob["h"] / 2 + pad)


def appearance_descriptor(frame_bgr, box):
    """E13 identity gate: a body-color descriptor for a box crop -- mean BGR of
    the crop's brightest quartile, ranked by max-channel value. The bright
    quartile is the car-body pixels (the body outshines road/grass, and the
    dark windshield drops out), so the descriptor survives loose boxes and
    partially-emerged cars; ranking by max-channel rather than grey luminance
    keeps it working for saturated bodies (the blue escort's B=230 outranks
    grass, whose green would beat it in luminance). E3's byte-identical twin is
    out of reach for ANY appearance cue by construction; --decoy-shade renders
    the discriminable same-class case this gate exists for (true 245 vs decoy
    215 -> L-inf gap 30). Returns a float BGR triple, or None on a degenerate
    crop."""
    h, w = frame_bgr.shape[:2]
    x0, y0 = max(0, int(box[0])), max(0, int(box[1]))
    x1, y1 = min(w, int(box[2])), min(h, int(box[3]))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    crop = frame_bgr[y0:y1, x0:x1].reshape(-1, 3).astype(np.float64)
    sel = crop.max(axis=1) >= np.percentile(crop.max(axis=1), 75)
    return crop[sel].mean(axis=0)


def mask_descriptor(frame_bgr, mask):
    """E14 mask-bound identity: per-channel MEDIAN BGR over a SAM2 mask's
    pixels. E13's crop statistic asked "is the template color PRESENT in this
    box?" -- a two-car blend box answers yes via the emerging true car's
    pixels while SAM2 latches the decoy the box centres on (ap-decoy 0/3).
    The mask is what SAM2 actually latched, and the median is a MAJORITY vote
    over it: a latch that is mostly decoy reads the decoy's body shade even
    when true-car pixels are inside the mask (design probe 2026-07-03: blend
    inits at 0.5-4.0 m emergence all read exactly 215.0 while containing up
    to 65% true-region pixels), and the ~16% dark windshield never outvotes
    the body. None on a degenerate (<16 px) mask."""
    if mask is None or int(mask.sum()) < 16:
        return None
    return np.median(frame_bgr[mask.astype(bool)].astype(np.float64), axis=0)


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

    def __init__(self, submit, make_carry, validate=None, loss_s: float = LOSS_S,
                 reground_gate=None, acquire_delay: float = 0.0):
        self.submit, self.make_carry, self.validate = submit, make_carry, validate
        self.loss_s = loss_s
        # E12: sim time before which no VLM draw may submit (a late NL command
        # -- "follow that white car" said after the car is already moving away).
        # Removes the t=0 gift frame, so the winning submit frame must be one
        # the pre-lock hold/chase produced. Pre-FIRST-lock only: the guard in
        # step() tests first_lock_t, so REGROUND/RETARGET draws are never
        # delayed. Default 0.0 = E2-E11 behavior, bit-identical.
        self.acquire_delay = acquire_delay
        # E7: reground_gate(box, frame, t, t_submit) -> bool; consulted ONLY in
        # REGROUND (first ACQUIRE has no prior mover to confirm against)
        self.reground_gate = reground_gate
        self.state, self.fut, self.carry = "ACQUIRE", None, None
        self._submit_frame, self._submit_t = None, None
        self.last_seen: float | None = None
        self.n_attempts = self.n_regrounds = self.n_rejected = 0
        self.n_gate_rejected = 0
        # E5 blind spot: rejected acquires were counted but never logged, so
        # the lottery mechanism was invisible. (t, raw box, accepted, reason)
        # per resolve; reason in {"", "size", "gate"} ("gate" = the E7/E13
        # reground gate; E7's recorded artifacts spell it "motion").
        self.acquire_log: list = []
        self.first_lock_t: float | None = None
        self.relock_walls: list[float] = []
        self._reground_t: float | None = None
        self.retarget_fired_t: float | None = None

    def retarget(self, submit, t: float):
        """E9: point the SM at a new NL target. Swap the acquire closure (it
        carries the new caption) and drop the current carry -- the loop goes
        blind (DR owns it) until the new target locks. Reuses the whole
        not-CARRY acquire path: size prior validates, relock_walls records the
        switch wall. RETARGET (not REGROUND) so the E7 motion gate -- a claim
        of continuity with the OLD target -- is not consulted."""
        self.submit = submit
        if self.fut is not None:          # stale draw carries the old caption
            self.fut.cancel()
            self.fut = None
        self.state, self.carry = "RETARGET", None
        self._reground_t = t
        self.retarget_fired_t = t

    def step(self, t: float, frame_bgr):
        if self.state != "CARRY":
            if self.fut is None:
                if self.first_lock_t is None and t < self.acquire_delay:
                    return None  # E12: NL command not yet given; hold/chase still run
                self.fut = self.submit(frame_bgr)
                # keep the submitted frame: the VLM box is valid on THIS frame,
                # so carry must be initialized on it, not on the ~2.5-5s-later
                # frame where the box no longer overlaps a moving target (E4)
                self._submit_frame, self._submit_t = frame_bgr.copy(), t
                self.n_attempts += 1
            elif self.fut.done():
                box, _ = self.fut.result()
                self.fut = None
                raw, reason = box, ""
                if box is not None and self.validate and not self.validate(box):
                    self.n_rejected += 1
                    reason, box = "size", None  # implausible acquire -> failed, relaunch
                if (box is not None and self.reground_gate is not None
                        and self.state == "REGROUND"
                        and not self.reground_gate(box, frame_bgr, t,
                                                   self._submit_t)):
                    # E7/E13: size prior passed but the gate says the box is
                    # not the target (not on the scene's mover / wrong body
                    # color) -> keep drawing
                    self.n_gate_rejected += 1
                    reason, box = "gate", None
                self.acquire_log.append(
                    (round(t, 2),
                     [round(v, 1) for v in raw] if raw is not None else None,
                     box is not None, reason))
                if box is not None:
                    self.carry = self.make_carry(self._submit_frame, box,
                                                 self._submit_t)
                    self.last_seen = t
                    if self.first_lock_t is None:
                        self.first_lock_t = t
                    if self.state in ("REGROUND", "RETARGET"):
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
              dr: str = "velocity", acquire_hold: str = "none",
              reground_gate: str = "none", duration_s: float = DURATION_S,
              retarget_t: float | None = None, vmax: float = 2.5,
              acquire_delay: float = 0.0, app_tau: float = 12.0,
              decoy_shade: int = 245) -> dict:
    """One `duration_s` s follow trial at SPEED (default 75 s). Orchestration mirrors phase1_sitl.run_trial;
    the oracle box is kept for the in-FOV metric only -- control sees pixels.
    carry_conn set (3b): CARRY steps go to jetson_carry_service over the tunnel."""
    import torch

    from sitl.cascade_pid import CascadePID
    from sitl.oracle_bbox import (
        FOCAL_PX, IMG_H, IMG_W, TARGET_LEN_M, TARGET_WID_M,
        project as oracle_project)

    # yaw disabled, per Phase B rationale. E10: PID velocity limit follows
    # --vmax (never below the historical 3.0, so default runs are bit-identical)
    pid = CascadePID(kp_yaw=0.0, max_vx=max(3.0, vmax), max_vy=max(3.0, vmax))
    executor = ThreadPoolExecutor(max_workers=1)
    rgb = lambda f: np.ascontiguousarray(f[:, :, ::-1])  # noqa: E731
    jpg = lambda f: cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()  # noqa: E731

    def _acquire(path: str, caption: str):
        try:
            return vlm_acquire(be, path, caption, IMG_W, IMG_H)
        finally:
            os.unlink(path)

    def submit(frame_bgr, caption: str = CAPTION):
        path = f"/dev/shm/p3a_acq_{time.monotonic_ns()}.png"
        cv2.imwrite(path, frame_bgr)
        return executor.submit(_acquire, path, caption)

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
            # E14: expose the frame-0 mask so the mask template can be bound
            # from the instance the carry actually latched at NL grounding
            return SimpleNamespace(step=step, init_mask=sc.init_mask)

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
        # was 1.5, saturated at the 1.5 m/s trial speed (E2); raised to 2.5,
        # then parameterized as vmax (E10) so DR can track the top test speed
        # instead of clamping exactly when needed
        vn = max(-vmax, min(vmax, (hist[-1][1] - hist[0][1]) / dt))
        ve = max(-vmax, min(vmax, (hist[-1][2] - hist[0][2]) / dt))
        return vn, ve

    template = [None]  # E13: appearance template, bound at NL grounding time
    rg_gate = None
    if reground_gate == "motion":
        def rg_gate(box, frame_bgr, t, t_submit):
            # E7: baseline = buffered frame NEAREST the submit time (the box is
            # only valid on the submit frame), so the ego-compensated diff
            # sweeps submit->now; acq_buf steps 0.5 s -> base within 0.25 s of
            # submit, covered by reground_motion_ok's pad
            base = min(acq_buf, key=lambda e: abs(e[0] - t_submit)) if acq_buf else None
            if base is None or t - base[0] < 0.35:
                return False  # no usable baseline -> cannot confirm a mover
            return reground_motion_ok(box, frame_bgr, base[1], _ground_affine(
                base[2], base[3], copter_ned, attitude[2]))
    elif reground_gate == "appearance":
        def rg_gate(box, frame_bgr, t, t_submit):
            # E13: the box is only valid on the frame the VLM drew it on, so
            # crop the SM's kept submit frame (sm._submit_frame -- exact, no
            # base-vs-submit pose slack), not the current frame. No template
            # yet (first capture degenerate) -> fail-open: with no bound
            # identity there is no identity claim to enforce.
            if template[0] is None:
                return True
            d = appearance_descriptor(sm._submit_frame, box)
            return (d is not None
                    and float(np.abs(d - template[0]).max()) <= app_tau)
    elif reground_gate == "mask":
        assert carry_conn is None, "--reground-gate mask needs the local carry"

        def rg_gate(box, frame_bgr, t, t_submit):
            # E14: judge the INSTANCE, not the crop. Run the exact StreamCarry
            # init the SM would run on accept (same submit-frame bytes via the
            # q=95 jpg path, same box, same weights -> the same latch) and take
            # the majority body color of its frame-0 mask. E13's blend boxes
            # (crop stat within tau while SAM2 latched the decoy) read the
            # decoy's 215 here and are rejected. ~40 ms per consult on the 3090
            # (design probe), once per size-passing REGROUND resolve -- noise
            # against the ~2.3 s VLM draw cadence. Fail-open with no template,
            # as in appearance mode: no bound identity, no claim to enforce.
            if template[0] is None:
                return True
            sc = StreamCarry(predictor, rgb(sm._submit_frame), box)
            d = mask_descriptor(sm._submit_frame, sc.init_mask)
            del sc  # throwaway verifier state; accept re-inits identically
            return (d is not None
                    and float(np.abs(d - template[0]).max()) <= app_tau)

    sm = AcquireCarrySM(submit, make_carry, validate, reground_gate=rg_gate,
                        acquire_delay=acquire_delay)

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
    # E10: extend the world texture north when the trial's reach needs it;
    # max() keeps every <=1.5 m/s run on the exact E2-E9 world (n_max=140)
    cam = NadirCam(bridge_n=bridge, road_e=rover_home_e,
                   n_max=max(140.0, c(duration_s) + 20.0))

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
    elif twin == "escort":
        # E9: BLUE companion in the +3 m lane, 2.5 m behind, same velocity --
        # the RETARGET target. Co-moving, so it sits at a fixed offset inside
        # the ~8.7 x 11.6 m footprint whichever car the copter centers on.
        distractor = lambda t: (rover_home_n + pb.ROVER_START_N + SPEED * t - 2.5,  # noqa: E731
                                rover_home_e + 3.0, 0.0)
    else:
        distractor = None
    # E13: non-escort distractor body shade (default 245 = E3's byte-identical
    # twin; 215 = the discriminable same-class "white-ish car" case)
    dist_color = ESCORT_COLOR if twin == "escort" else (decoy_shade,) * 3
    twin_rows: list[tuple[float, float, float]] = []  # (t, d_true_px, d_dist_px) when boxed
    relock_on: list[str] = []  # E7 verdict metric: per relock, first boxed twin
    # frame is closer to "true" or "distractor" (aligned with relock_walls)

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
    rt_wall_idx = None          # E9: relock_walls index where switch walls start
    rt_frames = rt_dist_fov = 0  # E9: post-switch frames / escort-in-FOV frames
    carry_errs: list[float] = []
    carry_step_s: list[float] = []
    hb_timer = t_start = time.monotonic()

    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        while time.monotonic() - t_start < duration_s:
            t_now = time.monotonic()
            t = t_now - t_start

            rover_ned = (c(t), rover_home_e, 0.0)
            dnd = distractor(t) if distractor else None
            copter_ned, attitude = pb._drain_telemetry(ctrl, copter_ned, attitude)
            frame = cam.render(copter_ned, attitude[2], rover_ned, dnd,
                               distractor_color=dist_color)
            if sm.state != "CARRY" and n_frames % 10 == 0:  # E4: catch-up buffer
                acq_buf.append((t, frame.copy(), copter_ned, attitude[2]))

            if (retarget_t is not None and sm.retarget_fired_t is None
                    and t >= retarget_t and sm.state == "CARRY"):
                # E9: the NL switch command fires at the first CARRY tick at/after
                # retarget_t (never mid-REGROUND: a switch during a blind phase
                # would conflate relock and retarget in the walls metric)
                sm.retarget(lambda f: submit(f, RETARGET_CAPTION), t)
                rt_wall_idx = len(sm.relock_walls)
                template[0] = None  # E13: new NL target -> old template void

            was_carry = sm.state == "CARRY"
            t_sm = time.monotonic()
            box = sm.step(t, frame)
            if was_carry:
                carry_step_s.append(time.monotonic() - t_sm)
            if (reground_gate in ("appearance", "mask") and template[0] is None
                    and sm.state == "CARRY" and sm.acquire_log
                    and sm.acquire_log[-1][2]):
                # E13: bind the template at NL grounding time -- the tick the
                # first ACQUIRE (or RETARGET) accept lands, from the accepted
                # box on its own submit frame. REGROUND accepts never rebind
                # (template already set): reground identity is the very thing
                # the gate judges. E14 mask mode binds from the frame-0 mask of
                # the carry the accept just created -- the instance actually
                # latched, not the box crop.
                if reground_gate == "mask":
                    template[0] = mask_descriptor(sm._submit_frame,
                                                  sm.carry.init_mask)
                else:
                    template[0] = appearance_descriptor(sm._submit_frame,
                                                        sm.acquire_log[-1][1])

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
            hold = None
            if (acquire_hold in ("motion", "chase") and out is None
                    and sm.first_lock_t is None and acq_buf):
                # E6 motion-hold: pre-first-lock the copter hovers while the VLM
                # draws (~2.3 s/attempt) and a >=1.0 m/s car exits the FOV between
                # draws (E5 acquire lottery: 31/32 rejects at 1.0). Servo on the
                # frame-diff blob to keep the car in frame until a draw accepts;
                # after first lock, replay/DR/pursuit own every blind phase.
                base = next((e for e in reversed(acq_buf) if t - e[0] >= 0.35), None)
                if base is not None:
                    hold = motion_blob(frame, base[1], _ground_affine(
                        base[2], base[3], copter_ned, attitude[2]))
                    if hold is not None and acquire_hold == "chase":
                        # E11 chase-hold: feed the blob's world track into hist
                        # so the existing hist_vel -> pursuit DR (a) closes on
                        # the mover with velocity feed-forward while the blob is
                        # visible and (b) keeps chasing the last estimate when
                        # the mover outruns the FOV. E10 s3.0: the positional
                        # hold hovered on blob loss (compute(None)) and the car
                        # never re-entered -- 73 s of road-dash draws. Pre-lock
                        # entries mix with the E4 replay's box entries for
                        # <=2.4 s after first lock (hist maxlen 48 @20 Hz); the
                        # anchor offset between the two conventions is ~1 m, a
                        # <~0.5 m/s transient in hist_vel that pursuit's
                        # position term absorbs.
                        hist.append((t, *box_to_world(
                            blob_chase_box(hold), copter_ned, attitude[2])))
            sp = pid.compute(out if out is not None else hold)
            v_blind = hist_vel() if out is None else None
            if v_blind is not None:
                # ponytail: blind -> dead-reckon at the last estimated target
                # velocity instead of hovering (Phase 1's identified lever)
                vn, ve = v_blind
                if dr == "pursuit":  # E5: also close the gap, don't just match speed
                    vn, ve = pursuit_vel(hist[-1], (vn, ve), t,
                                         (copter_ned[0], copter_ned[1]),
                                         vmax=vmax)
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
            if sm.retarget_fired_t is not None and dnd is not None:
                # E9: post-switch the escort IS the commanded target -- its
                # in-FOV fraction is the follow-quality metric that matters
                rt_frames += 1
                rt_dist_fov += oracle_project(copter_ned, dnd, 0.0, 0.0,
                                              attitude[2]) is not None
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
                    if len(sm.relock_walls) > len(relock_on):
                        # a relock happened since the last boxed frame: classify
                        # it by this (first) box; pad "?" keeps alignment if a
                        # relock somehow produced no boxed frame at all
                        relock_on += ["?"] * (len(sm.relock_walls) - len(relock_on) - 1)
                        relock_on.append("distractor" if d_dist_px < d_true_px
                                         else "true")

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
        "duration_s": duration_s,
        "achieved_hz": round(n_frames / duration_s, 1),
        "carry_fps": round(1.0 / (sum(carry_step_s) / len(carry_step_s)), 1)
                     if carry_step_s else None,
        "in_fov_frac": round(in_fov_frames / n_frames, 4),
        "first_lock_s": round(sm.first_lock_t, 2) if sm.first_lock_t else None,
        "n_acquire_attempts": sm.n_attempts,
        "n_rejected_acquires": sm.n_rejected,
        "n_reground_gate_rejects": sm.n_gate_rejected,
        "app_template": [round(float(x), 1) for x in template[0]]
                        if template[0] is not None else None,
        "acquire_log": sm.acquire_log,
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
            "relock_on": relock_on,
        }
    if retarget_t is not None:
        # E9: post-switch, twin_rows' "distractor" is the COMMANDED target, so
        # closer-to-distractor is the PASS direction (sign flip vs E3/E7/E8)
        post = ([(dt, dd) for tt, dt, dd in twin_rows if tt > sm.retarget_fired_t]
                if sm.retarget_fired_t is not None else [])
        m["retarget"] = {
            "commanded_t_s": retarget_t,
            "fired_t_s": round(sm.retarget_fired_t, 2)
                         if sm.retarget_fired_t is not None else None,
            "caption": RETARGET_CAPTION,
            "switch_walls_s": sm.relock_walls[rt_wall_idx:]
                              if rt_wall_idx is not None else [],
            "switch_on": relock_on[rt_wall_idx:] if rt_wall_idx is not None else [],
            "n_post_boxed_frames": len(post),
            "frac_box_closer_dist_post":
                round(sum(dd < dt for dt, dd in post) / len(post), 3)
                if post else None,
            "dist_in_fov_frac_post": round(rt_dist_fov / rt_frames, 4)
                                     if rt_frames else None,
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
    # E10: raised vmax lifts the clamp -- same 4 m deficit now yields 3.0
    assert pursuit_vel((10.0, 5.0, 0.0), (1.0, 0.0), 12.0, (3.0, 0.0),
                       vmax=4.0) == (3.0, 0.0)
    # E6: every resolved acquire attempt is logged (t, raw box, accepted,
    # reason) -- ticks 2 (accept), 15 (too-small box, reject), 20 (accept)
    assert [(tt, ok, rs) for tt, _, ok, rs in sm.acquire_log] == \
        [(2.0, True, ""), (15.0, False, "size"), (20.0, True, "")], sm.acquire_log
    assert sm.acquire_log[1][1] == [0.0, 0.0, 3.0, 3.0], sm.acquire_log
    # E7 SM wiring: gate consulted ONLY on REGROUND resolves (never on the
    # first ACQUIRE), reject keeps drawing, accept relocks. Same stub timeline
    # plus a resolve @24: 20 gate-rejected, 24 gate-accepted.
    pending.clear()
    calls: list[float] = []

    def rgate(box, frame, t, t_submit):
        calls.append(t)
        return len(calls) > 1  # reject first consult, accept after

    sm2 = AcquireCarrySM(submit, make_carry,
                         validate=lambda b: b[2] - b[0] > 5, loss_s=3.0,
                         reground_gate=rgate)
    for k in range(30):
        if pending and k in (2, 15, 20, 24):
            box = (0, 0, 3, 3) if k == 15 else (0, 0, 10, 10)
            pending.pop(0).set_result((box, 2.5))
        sm2.step(float(k), np.full((4, 4, 3), k, np.uint8))
    assert sm2.first_lock_t == 2.0, sm2.acquire_log  # ACQUIRE: gate not consulted
    assert calls == [20.0, 24.0], calls              # REGROUND resolves only
    assert sm2.n_gate_rejected == 1 and sm2.n_rejected == 1, sm2.acquire_log
    assert [rs for _, _, _, rs in sm2.acquire_log] == ["", "size", "gate", ""], \
        sm2.acquire_log
    assert sm2.relock_walls == [14.0], sm2.relock_walls  # fired@10, relocked@24
    # E9 retarget: lock @2, retarget mid-CARRY @4 -> carry dropped, state
    # RETARGET, the NEW submit closure draws, accept @6 -> relock_walls entry
    # (wall = 6-4) + back to CARRY; E7 gate must NOT be consulted on RETARGET
    pending.clear()
    rt_pending: list[Future] = []

    def rt_submit(_frame):
        fut = Future()
        rt_pending.append(fut)
        return fut

    gate_calls: list[float] = []
    sm3 = AcquireCarrySM(submit, make_carry,
                         validate=lambda b: b[2] - b[0] > 5, loss_s=3.0,
                         reground_gate=lambda *a: gate_calls.append(a[2]) or True)
    for k in range(8):
        if pending and k == 2:
            pending.pop(0).set_result(((0, 0, 10, 10), 2.5))
        if rt_pending and k == 6:
            rt_pending.pop(0).set_result(((0, 0, 10, 10), 2.5))
        if k == 4:
            assert sm3.state == "CARRY", sm3.state
            sm3.retarget(rt_submit, float(k))
            assert sm3.state == "RETARGET" and sm3.carry is None
        sm3.step(float(k), np.full((4, 4, 3), k, np.uint8))
    assert not pending, "old-caption closure drew after retarget"
    assert sm3.state == "CARRY" and sm3.retarget_fired_t == 4.0, sm3.state
    assert sm3.relock_walls == [2.0], sm3.relock_walls  # fired@4, relocked@6
    assert gate_calls == [], gate_calls  # E7 gate skipped on RETARGET resolves
    # E12 acquire-delay: no draw may submit before t=acquire_delay (late NL
    # command); the first submit fires at the first tick >= delay and carry
    # still inits on the delayed SUBMIT frame (E4). Post-first-lock the guard
    # is inert by construction (first_lock_t is not None), so REGROUND draws
    # are never delayed.
    pending.clear()
    sm4 = AcquireCarrySM(submit, make_carry,
                         validate=lambda b: b[2] - b[0] > 5, loss_s=3.0,
                         acquire_delay=3.0)
    for k in range(3):
        assert sm4.step(float(k), np.full((4, 4, 3), k, np.uint8)) is None
        assert sm4.n_attempts == 0 and sm4.fut is None, (k, sm4.n_attempts)
    sm4.step(3.0, np.full((4, 4, 3), 3, np.uint8))
    assert sm4.n_attempts == 1 and pending, sm4.n_attempts
    pending.pop(0).set_result(((0, 0, 10, 10), 2.5))
    sm4.step(4.0, np.full((4, 4, 3), 4, np.uint8))
    assert sm4.first_lock_t == 4.0 and sm4.state == "CARRY", sm4.first_lock_t
    assert carried[-1] == 3, carried  # E4 under delay: submit frame, not resolve
    # E6 motion_blob: two rendered poses (copter moved + yawed, car 0.5->1.5 m N)
    # -> blob centered on the car's swept span; identical frames -> None
    cam = NadirCam()
    cop0, cop1 = (0.0, 0.0, -8.8), (0.3, 0.1, -8.8)
    f0 = cam.render(cop0, 0.0, (0.5, 0.0, 0.0))
    f1 = cam.render(cop1, 0.05, (1.5, 0.0, 0.0))
    blob = motion_blob(f1, f0, _ground_affine(cop0, 0.0, cop1, 0.05))
    assert blob is not None, "motion_blob missed a 1 m car displacement"
    u, v = world_to_px((1.0, 0.0), cop1, 0.05)[0]  # swept-span midpoint
    d = math.hypot(blob["cx"] - u, blob["cy"] - v)
    assert d < 40, (blob, (u, v), d)
    ident = np.float32([[1, 0, 0], [0, 1, 0]])
    assert motion_blob(f1, f1, ident) is None, "static scene must yield no blob"
    # E11 chase-hold: blob_chase_box anchors box_to_world on the sweep CENTER
    # row. On the rendered pair that row must lie strictly inside the true
    # sweep span [rear at base (N=0.5-2.0) .. nose at cur (N=1.5+2.0)] -- i.e.
    # the chase target trails the true car by less than the sweep length, a
    # near-constant lag at fixed baseline (north = smaller image v)
    from sitl.oracle_bbox import TARGET_LEN_M as _TL
    cb = blob_chase_box(blob)
    assert cb[3] == blob["cy"] and cb[2] - cb[0] == blob["w"], cb
    v_nose = world_to_px((1.5 + _TL / 2, 0.0), cop1, 0.05)[0][1]
    v_rear = world_to_px((0.5 - _TL / 2, 0.0), cop1, 0.05)[0][1]
    assert v_nose < cb[3] < v_rear, (cb[3], v_nose, v_rear)
    # E7 reground_motion_ok on the same rendered pair: a box on the car (base-
    # frame coords) sits on the sweep -> accept; a box on a static ground point
    # 3.5 m south of the sweep (the decoy analog, decoy offset is >=2 m)
    # -> reject; a static scene (no mover at all) -> blob None -> reject
    M = _ground_affine(cop0, 0.0, cop1, 0.05)
    u0, v0 = world_to_px((0.5, 0.0), cop0, 0.0)[0]   # car center in f0
    car_box = (u0 - 20, v0 - 20, u0 + 20, v0 + 20)
    assert reground_motion_ok(car_box, f1, f0, M), "box on the mover must pass"
    ud, vd = world_to_px((-5.0, 0.0), cop0, 0.0)[0]  # static point off the sweep
    assert not reground_motion_ok((ud - 20, vd - 20, ud + 20, vd + 20), f1, f0, M), \
        "box on a static point must be rejected"
    assert not reground_motion_ok(car_box, f1, f1, ident), \
        "no mover in scene -> reject"
    # E13 appearance_descriptor on rendered frames: white car -> ~245 grey; a
    # 215-shaded decoy -> ~215 (L-inf gap ~30, > 2x the default tau 12); the
    # blue escort -> B-dominant (max-channel ranking picks the 230-blue body
    # over grass, which would out-rank it in grey luminance); degenerate box
    # -> None. Boxes are exact car rects from the known geometry.
    from sitl.oracle_bbox import FOCAL_PX as _F
    cop = (0.0, 0.0, -8.8)
    px_m = _F / 8.8

    def _car_box(n, e):
        u, v = world_to_px((n, e), cop, 0.0)[0]
        return (u - px_m, v - 2 * px_m, u + px_m, v + 2 * px_m)  # 2 x 4 m body

    fw = cam.render(cop, 0.0, (0.5, 0.0, 0.0))
    dw = appearance_descriptor(fw, _car_box(0.5, 0.0))
    assert dw is not None and np.abs(dw - 245.0).max() <= 6.0, dw
    fd = cam.render(cop, 0.0, (60.0, 0.0, 0.0),  # true car far out of FOV
                    distractor_ned=(0.5, 0.0, 0.0), distractor_color=(215,) * 3)
    dd = appearance_descriptor(fd, _car_box(0.5, 0.0))
    assert np.abs(dd - 215.0).max() <= 6.0, dd
    assert np.abs(dd - dw).max() >= 25.0, (dd, dw)  # gap comfortably > tau 12
    fb = cam.render(cop, 0.0, (60.0, 0.0, 0.0),
                    distractor_ned=(0.5, 3.0, 0.0), distractor_color=(230, 90, 40))
    db = appearance_descriptor(fb, _car_box(0.5, 3.0))
    assert db[0] > 200.0 and db[0] - db[2] > 100.0, db  # B-dominant = blue body
    assert appearance_descriptor(fw, (0.0, 0.0, 1.0, 1.0)) is None
    # E14 mask_descriptor + the exact E13 hole it closes, on one rendered
    # two-car scene: true 245 car at N=0.5, 215 decoy at N=4.7, cop between
    # them at 12 m. A wide REGROUND box spanning both cars + road background
    # PASSES the E13 crop stat (its brightest quartile IS the true car's 245
    # body -> dist 0 <= tau 12), while the median over the two-car latch
    # region -- what SAM2 latches from such a box per the 2026-07-03 design
    # probe -- reads the decoy's 215 (dark windshields keep 245 above the
    # 50th percentile only when 245 is the outright majority) -> REJECTED.
    from sitl.oracle_bbox import TARGET_WID_M as _TW
    cop2 = (2.6, 0.0, -12.0)
    f2 = cam.render(cop2, 0.0, (0.5, 0.0, 0.0),
                    distractor_ned=(4.7, 0.0, 0.0), distractor_color=(215,) * 3)

    def _region(frame, cop_, n0, n1, e0, e1):
        (u0, v0), (u1, v1) = world_to_px([(n1, e0), (n0, e1)], cop_, 0.0)
        m = np.zeros(frame.shape[:2], bool)
        m[int(min(v0, v1)):int(max(v0, v1)), int(min(u0, u1)):int(max(u0, u1))] = True
        return m

    hl2, hw2 = _TL / 2, _TW / 2
    m_true = _region(f2, cop2, 0.5 - hl2, 0.5 + hl2, -hw2, hw2)
    m_dec = _region(f2, cop2, 4.7 - hl2, 4.7 + hl2, -hw2, hw2)
    assert np.abs(mask_descriptor(f2, m_true) - 245.0).max() <= 6.0
    assert np.abs(mask_descriptor(f2, m_dec) - 215.0).max() <= 6.0  # L-inf ~30 > tau
    (bu0, bv0), (bu1, bv1) = world_to_px([(6.7, -1.5), (-1.5, 1.5)], cop2, 0.0)
    blend_box = (min(bu0, bu1), min(bv0, bv1), max(bu0, bu1), max(bv0, bv1))
    da_blend = appearance_descriptor(f2, blend_box)
    assert np.abs(da_blend - 245.0).max() <= 12.0, da_blend  # E13 gate: ACCEPT (the hole)
    dm_blend = mask_descriptor(f2, m_true | m_dec)
    assert np.abs(dm_blend - 215.0).max() <= 6.0, dm_blend   # E14 gate: REJECT
    assert mask_descriptor(f2, np.zeros(f2.shape[:2], bool)) is None
    dm_blue = mask_descriptor(fb, _region(fb, cop, 0.5 - hl2, 0.5 + hl2,
                                          3.0 - hw2, 3.0 + hw2))
    assert dm_blue[0] > 200.0 and dm_blue[0] - dm_blue[2] > 100.0, dm_blue
    print("selfcheck PASS  acquire->carry->gate->reground->relock + E4 submit-frame/gate_box"
          " + E5 pursuit_vel + E6 acquire_log/motion_blob + E7 reground gate"
          " + E9 retarget + E11 chase box + E12 acquire-delay"
          " + E13 appearance descriptor + E14 mask descriptor")


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
    ap.add_argument("--twin", choices=["crossing", "decoy", "escort"], default=None,
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
    ap.add_argument("--acquire-hold", choices=["none", "motion", "chase"],
                    default="none",
                    help="E6: pre-first-lock FOV hold -- servo on the ego-motion-"
                         "compensated frame-diff blob so the target stays in "
                         "frame across VLM draws (E5 acquire lottery). E11 "
                         "chase: additionally feed the blob track into hist so "
                         "pursuit DR chases the mover pre-lock (motion is a "
                         "positional servo only and hovers on blob loss -- at "
                         "3 m/s the car outruns the FOV and never returns)")
    ap.add_argument("--reground-gate",
                    choices=["none", "motion", "appearance", "mask"],
                    default="none",
                    help="extra REGROUND acceptance check -- the size prior is "
                         "identity-blind (E3 decoy wrong-lock 3/3). motion "
                         "(E7): box must sit on the ego-motion-compensated "
                         "frame-diff blob (a parked decoy is not a mover; "
                         "defeated by drive-through co-location). appearance "
                         "(E13): box crop must match the body-color template "
                         "bound at NL grounding time within --app-tau "
                         "(defeated by two-car blend boxes). mask (E14): the "
                         "median body color of the SAM2 frame-0 mask the box "
                         "would latch must match the template -- judges the "
                         "instance, not the crop. Local carry only.")
    ap.add_argument("--app-tau", type=float, default=12.0,
                    help="E13/E14: L-inf BGR tolerance for reground-gate="
                         "appearance and mask (true car ~0, 215-shade decoy "
                         "~30; E13's crop stat let two-car blend boxes land "
                         "inside tau -- mask mode's median reads the latched "
                         "majority instance instead)")
    ap.add_argument("--decoy-shade", type=int, default=245,
                    help="E13: grey body shade of the non-escort distractor "
                         "car. Default 245 = E3's byte-identical twin, "
                         "bit-identical to E2-E12; 215 = a discriminable "
                         "same-class 'white-ish car'. Keep >200 (road-dash "
                         "grey / sitl_cam selfcheck blob threshold).")
    ap.add_argument("--retarget-t", type=float, default=None,
                    help="E9: at this sim time (first CARRY tick at/after it), "
                         "swap the NL target to RETARGET_CAPTION and drop the "
                         "carry -- mid-follow 'switch to the blue car'")
    ap.add_argument("--acquire-delay", type=float, default=0.0,
                    help="E12: sim seconds before the first VLM acquire may "
                         "submit (a late NL command -- removes the t=0 gift "
                         "frame; E11 s3.5 locked on draw 1 without stressing "
                         "chase). Hold/chase run from t=0; REGROUND draws are "
                         "unaffected. Default 0.0 = E2-E11, bit-identical.")
    ap.add_argument("--vmax", type=float, default=2.5,
                    help="E10: DR/pursuit speed cap (m/s); also raises the PID "
                         "velocity limit to max(3.0, vmax). Default 2.5 = the "
                         "E2-E9 behavior, bit-identical.")
    ap.add_argument("--duration-s", type=float, default=DURATION_S,
                    help="E8: trial length -- default 75s truncated the E7 decoy "
                         "legs before the E4 motion loss-gate (2s stillness + 3s "
                         "LOSS_S) could complete a post-wrong-lock reground retry")
    args = ap.parse_args()
    if args.selfcheck:
        selfcheck()
        return
    if args.reground_gate == "mask" and args.remote_carry:
        # E14 gate verifies with the HOST predictor (StreamCarry init mask);
        # the 3b remote path has no local predictor -- port when 3b re-gates
        sys.exit("--reground-gate mask is local-carry only (drop --remote-carry)")
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
                          retarget_t=args.retarget_t,
                          loss_gate=args.loss_gate, score_tau=args.score_tau,
                          dr=args.dr, acquire_hold=args.acquire_hold,
                          reground_gate=args.reground_gate,
                          duration_s=args.duration_s, vmax=args.vmax,
                          acquire_delay=args.acquire_delay,
                          app_tau=args.app_tau, decoy_shade=args.decoy_shade)
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
           "speed": SPEED, "duration_s": args.duration_s, "hz": CONTROL_HZ,
           "image_size": args.image_size, "sam2": MODEL,
           "validate": "sizeprior-0.5-2.0", "deadreckon": True,
           "twin": args.twin, "retarget_t": args.retarget_t,
           "loss_gate": args.loss_gate, "score_tau": args.score_tau,
           "dr": args.dr, "acquire_hold": args.acquire_hold,
           "reground_gate": args.reground_gate, "vmax": args.vmax,
           "acquire_delay": args.acquire_delay,
           "app_tau": args.app_tau, "decoy_shade": args.decoy_shade,
           "catchup_replay": True,
           "carry": "jetson-remote" if args.remote_carry else "host-3090"}
    out_dir = HERE / "runs" / phase
    write_manifest(capture(f"{phase}-integrated", cfg),
                   runs_dir=str(out_dir), results=summary)
    (out_dir / "results.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
