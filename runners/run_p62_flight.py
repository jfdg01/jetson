#!/usr/bin/env python3
"""
run_p62_flight.py -- R-35 closed-loop CARLA harness (P6.2), increment 1: the merge.

Merges the two disjoint CARLA scripts into one async loop:
  - carla_render.py  : async flight + pose-slaved free camera  (flies, no GT/target)
  - carla_gt_bank.py : per-frame identity GT for a moving target (GT, no flight)
into run_phase_c.py's source-agnostic detection seam (LatestDetectionSlot).

Increment 1 (THIS file) verifies the PLUMBING end to end:
  CARLA image source -> pose-slave -> target designation -> per-frame GT projection
  -> a stub detection producer through the LatestDetectionSlot -> genuine_lock/coverage
  scoring vs the target's actor_box -> mid-run overlay PNG (look-at-it).

Increment 2 (THIS file, added): --pose mavlink closes the loop. The delivered bbox
drives CascadePID -> send_velocity -> SITL, the camera slaves to the copter's own
NED, so the pixels are a consequence of the control output. verdict_allowed=True.
Still an OracleStubProducer for the detection -- incr.2 isolates the PID plumbing.

Deferred to increment 3 (see experiments/PART6-PROGRAM-...md sec.4):
  real WARM (idle-window VLM seed + StreamCarry live ring, prune_after=32) and
  COLD (blocking ~4.85 s Jetson vlm_acquire) producers replacing the stub.

    # boot the server first (separate terminal / background):
    ~/carla/CARLA_0.9.16/CarlaUE4.sh -RenderOffScreen -quality-level=Epic -carla-rpc-port=2000
    # server-free logic check (no CARLA/SITL needed):
    .venv-ft/bin/python runners/run_p62_flight.py --selftest
    # live plumbing smoke (CARLA up; GT-driven camera, NO P6.2 verdict):
    .venv-ft/bin/python runners/run_p62_flight.py --pose target_nadir --alt 60 \
        --seconds 12 --out runs/p62_smoke
    # closed-loop smoke (CARLA + ArduCopter SITL up; copter-slaved camera, PID follow):
    .venv-ft/bin/python runners/run_p62_flight.py --pose mavlink --alt 60 \
        --seconds 40 --out runs/p62_coupling_smoke

HONESTY: --pose target_nadir slaves the camera to the TARGET's own position (GT-driven
ego-motion). It is a plumbing smoke ONLY -- it verifies GT projection + scoring, and the
harness refuses to emit a FOLLOW-PASS verdict in this mode. A real P6.2 number needs
--pose mavlink (copter-slaved) + the PID coupling of increment 2.
"""
import argparse
import json
import math
import pickle
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# carla_render is import-safe (carla/cv2/numpy only). Reuse its renderer verbatim.
import carla_render as cr

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))                          # grounding.*
sys.path.insert(0, str(Path(__file__).resolve().parent))  # p62_producers, sitl_fly_leg


# --- copied, not imported --------------------------------------------------
# ponytail: LatestDetectionSlot + Detection are copied from run_phase_c.py
# (identical semantics). Importing that 1200-line module drags in the whole
# Gazebo/pymavlink/grounding-probe rig for 40 lines. project/actor_box/match_actor
# are copied from carla_debug_ui.py, which imports tkinter+PIL at module top.

@dataclass
class Detection:
    capture_ts: float = 0.0
    bbox: Optional[dict] = None    # {cx,cy,w,h} or None
    vlm_ms: float = 0.0
    raw_text: str = ""


class LatestDetectionSlot:
    """Lock-protected newest-detection slot. Producer writes, control loop reads.
    Stale write (capture_ts <= stored) is dropped (monotonic)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._det = Detection()

    def write(self, capture_ts, bbox, vlm_ms=0.0, raw_text="") -> bool:
        with self._lock:
            if capture_ts <= self._det.capture_ts:
                return False
            self._det = Detection(capture_ts, dict(bbox) if bbox else None, vlm_ms, raw_text)
            return True

    def read(self) -> Detection:
        with self._lock:
            d = self._det
            return Detection(d.capture_ts, dict(d.bbox) if d.bbox else None, d.vlm_ms, d.raw_text)


MATCH_OVERLAP = 0.30   # carla_debug_ui: min overlap (of smaller box) to call it the same vehicle


def project(world_loc, cam_tf, w, h, fov):
    """CARLA world point -> image pixel. Pinhole + the UE axis swap. None if behind."""
    f = w / (2.0 * math.tan(math.radians(fov) / 2.0))
    pt = np.array([world_loc.x, world_loc.y, world_loc.z, 1.0])
    c = np.dot(np.array(cam_tf.get_inverse_matrix()), pt)
    x, y, z = c[1], -c[2], c[0]    # UE x-fwd/y-right/z-up -> pinhole x-right/y-down/z-fwd
    if z <= 0.1:
        return None
    return (f * x / z + w / 2.0, f * y / z + h / 2.0)


def actor_box(bbox3d, tf, cam_tf, w, h, fov):
    """Actor 3D bbox -> axis-aligned pixel box (x0,y0,x1,y1). None if any vertex behind cam.

    `bbox3d` is the actor's (static) carla.BoundingBox, cached once before the loop:
    reading `actor.bounding_box` is a ~17 ms RPC each time, so match_actor's
    20-vehicle scan cost ~346 ms/tick. `tf` is the transform from a world snapshot.
    With both passed in, the whole tick makes ONE RPC (get_snapshot). Pure math here.
    """
    pts = [project(p, cam_tf, w, h, fov)
           for p in bbox3d.get_world_vertices(tf)]
    pts = [p for p in pts if p is not None]
    if len(pts) < 8:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def match_actor(vehicles, bb, snap, cam_tf, box, w, h, fov):
    """Which vehicle the box is on (overlap of smaller box >= MATCH_OVERLAP), or None.

    Reads transforms from `snap` (one world.get_snapshot() for the whole tick) and
    bounding boxes from `bb` (id -> carla.BoundingBox, cached before the loop), so
    the scan makes zero RPCs. `vehicles` is the spawn list captured once.
    """
    best, best_o = None, MATCH_OVERLAP
    for v in vehicles:
        s = snap.find(v.id)
        if s is None:
            continue
        a = actor_box(bb[v.id], s.get_transform(), cam_tf, w, h, fov)
        if a is None:
            continue
        iw = min(a[2], box[2]) - max(a[0], box[0])
        ih = min(a[3], box[3]) - max(a[1], box[1])
        if iw <= 0 or ih <= 0:
            continue
        smaller = min((a[2] - a[0]) * (a[3] - a[1]), (box[2] - box[0]) * (box[3] - box[1]))
        o = iw * ih / max(1.0, smaller)
        if o > best_o:
            best, best_o = v, o
    return best


# --- pure helpers ----------------------------------------------------------

def iou(a, b):
    """IoU of two (x0,y0,x1,y1) boxes. 0.0 if either is None or disjoint."""
    if a is None or b is None:
        return 0.0
    iw = min(a[2], b[2]) - max(a[0], b[0])
    ih = min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def box_to_bbox(box):
    """(x0,y0,x1,y1) -> {cx,cy,w,h} (the ByteTrack/PID convention). None-safe."""
    if box is None:
        return None
    return {"cx": (box[0] + box[2]) / 2, "cy": (box[1] + box[3]) / 2,
            "w": box[2] - box[0], "h": box[3] - box[1]}


def bbox_to_box(bbox):
    """{cx,cy,w,h} -> (x0,y0,x1,y1). None-safe."""
    if bbox is None:
        return None
    return (bbox["cx"] - bbox["w"] / 2, bbox["cy"] - bbox["h"] / 2,
            bbox["cx"] + bbox["w"] / 2, bbox["cy"] + bbox["h"] / 2)


# --- detection producer seam ----------------------------------------------
# The one seam WARM/COLD replace in increment 3. .step is called every control
# tick with the live frame + the current GT + the wall clock; it decides when a
# detection lands in the slot. The stub lands the true GT box delayed by a fixed
# latency -- the simplest producer that closes the loop and exercises scoring.

class OracleStubProducer:
    """Lands the true target box in the slot, delayed by `latency_s`.

    ponytail: a stand-in for the real perception. It is NOT a WARM or COLD arm --
    it has no VLM, no carry, no miss. It exists to prove the slot/scoring plumbing
    end to end so incr.3 can drop in the real producers behind the same interface.
    """

    def __init__(self, slot: LatestDetectionSlot, latency_s: float = 0.0):
        self.slot = slot
        self.latency_s = latency_s
        self._pending = []   # (deliver_ts, capture_ts, bbox)

    info = {"mode": "oracle-stub"}   # seam-compat with WarmColdProducer.info

    def step(self, frame_bgr, gt_box, now_ts):
        # frame_bgr ignored: the oracle reads GT, not pixels (seam-compat with WARM/COLD)
        if gt_box is not None:
            self._pending.append((now_ts + self.latency_s, now_ts, box_to_bbox(gt_box)))
        while self._pending and self._pending[0][0] <= now_ts:
            _, cap, bbox = self._pending.pop(0)
            self.slot.write(cap, bbox, vlm_ms=self.latency_s * 1000.0, raw_text="oracle-stub")

    def close(self):
        pass


# --- ssh-stdio carry framing (mirrors carry_ssh_bridge.py + ssh_carry_probe.py) ------
# 4-byte big-endian length + pickled payload, both directions, on the raw ssh pipe.
# The sandbox blocks local port-binding, so ssh -L is out; a stdio pipe is the transport.
def _ssh_send(f, obj):
    data = pickle.dumps(obj)
    f.write(struct.pack(">I", len(data))); f.write(data); f.flush()


def _ssh_readn(f, n):
    buf = b""
    while len(buf) < n:
        c = f.read(n - len(buf))
        if not c:
            return None
        buf += c
    return buf


def _ssh_recv(f):
    hdr = _ssh_readn(f, 4)
    if hdr is None:
        return None
    (n,) = struct.unpack(">I", hdr)
    return pickle.loads(_ssh_readn(f, n))


def build_grounding_carry(caption, prune_after, ssh_host, out_dir, carry_only=False,
                          showcase_ssh=False):
    """Boot the EXPENSIVE, reusable backends ONCE: Jetson q8_0 grounding + 3090 SAM2 carry.

    Returns (backend, acquire_fn, carry_factory, close). Split from the per-flight producer
    so the matrix boots the Jetson server + loads SAM2 a single time and reuses them across
    50 flights. Heavy imports are lazy so --selftest / oracle never touch torch/sam2/Jetson.
    Grounding ALWAYS on-device (quantization moves the box); carry on the 3090
    (E1 parity -> device-identical boxes, D-part6), prune_after=32 ring (R-16 OOM).

    carry_only=True skips the Jetson boot entirely (backend=None, acquire raises): the
    P6.2-COUPLING decoupled re-fly seeds from the operator's GT designation (oracle_gt),
    so grounding is never in the loop -- booting an unused llama-server would only add a
    pointless Jetson dependency the arm can fail on.
    """
    import torch
    sys.path.insert(0, str(REPO / "experiments" / "2026-07-04-warm-start-acquire"))
    sys.path.insert(0, str(REPO / "experiments" / "2026-07-01-temporal-acquire-carry"))
    from replay_e24 import vlm_acquire
    from stream_carry import MODEL, StreamCarry
    from sam2.sam2_video_predictor import SAM2VideoPredictor

    backend = None
    if not carry_only:
        from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
        from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
        from grounding.eval.backends import JetsonBackend
        backend = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                                f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                                ssh_host=ssh_host, max_side=1024)
    predictor = SAM2VideoPredictor.from_pretrained(MODEL)   # loads once on the 3090
    tmp = Path(out_dir); tmp.mkdir(parents=True, exist_ok=True)
    ctr = [0]

    # showcase: route the carry LITERALLY to the Jetson over ssh-stdio (P6.2-SHOWCASE
    # flight half). Launch the bridge ONCE here so its ~7 s model load overlaps CARLA
    # world setup, not the idle window -- then _SSHCarry.__init__ only sends the seed
    # frame. A 3090 _HostCarry twin runs in lockstep for the in-rig parity gate
    # (median IoU >= 0.95 => the ssh-stdio path reproduces the parity-checked carry).
    ssh_proc = None
    parity = []      # per-step {jetson, host, iou, compute_ms, rtt_ms}
    if showcase_ssh:
        ssh_proc = subprocess.Popen(
            ["ssh", "-T", "-q", ssh_host,
             "cd ~/sam2-bench && ./.venv/bin/python -u carry_ssh_bridge.py"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, bufsize=0)

    def acquire(frame_bgr, w, h):
        if backend is None:
            raise RuntimeError("carry_only backend has no grounding (oracle designation only)")
        ctr[0] += 1
        p = tmp / f"acq_{ctr[0]:04d}.png"
        cv2.imwrite(str(p), frame_bgr)
        return vlm_acquire(backend, str(p), caption, w, h)   # -> (x1,y1,x2,y2)|None

    class _HostCarry:
        """StreamCarry on the 3090, box-only, autocast-wrapped (the parity-checked path)."""
        def __init__(self, frame_rgb, box):
            with torch.autocast("cuda", dtype=torch.bfloat16):
                self.sc = StreamCarry(predictor, frame_rgb, box, prune_after=prune_after)
        def step(self, frame_rgb):
            with torch.autocast("cuda", dtype=torch.bfloat16):
                _, box = self.sc.step(frame_rgb)
            return box

    class _SSHCarry:
        """Carry stepped ON THE JETSON over ssh-stdio; a 3090 _HostCarry twin runs in
        lockstep for the in-rig parity gate. step() returns the JETSON box (the on-device
        deliverable); the twin box is only scored, never delivered. One bridge = one carry
        state, so only ONE _SSHCarry may exist per build (showcase = one warm flight)."""
        _live = [0]

        def __init__(self, frame_rgb, box):
            assert self._live[0] == 0, "ssh bridge holds one carry state; only one _SSHCarry"
            self._live[0] = 1
            self.twin = _HostCarry(frame_rgb, box)
            jpg = cv2.imencode(".jpg", frame_rgb)[1].tobytes()   # RGB in, bridge sends RGB through
            _ssh_send(ssh_proc.stdin, ("init", jpg, [int(v) for v in box]))
            ack = _ssh_recv(ssh_proc.stdout)
            assert ack and ack.get("ok"), f"ssh bridge init failed: {ack}"

        def step(self, frame_rgb):
            jpg = cv2.imencode(".jpg", frame_rgb)[1].tobytes()
            ta = time.time()
            _ssh_send(ssh_proc.stdin, ("step", jpg))
            r = _ssh_recv(ssh_proc.stdout)
            rtt_ms = (time.time() - ta) * 1000.0
            jbox = tuple(r["box"]) if r and r["box"] is not None else None
            hbox = self.twin.step(frame_rgb)                     # 3090 twin, scored not delivered
            parity.append({"jetson": list(jbox) if jbox else None,
                           "host": list(hbox) if hbox else None,
                           "iou": round(iou(list(jbox) if jbox else None,
                                            list(hbox) if hbox else None), 3),
                           "compute_ms": r.get("ms") if r else None,
                           "rtt_ms": round(rtt_ms, 1)})
            return jbox

    def carry_factory(rgb, box):
        return _SSHCarry(rgb, box) if showcase_ssh else _HostCarry(rgb, box)

    def close():
        if backend is not None:
            backend.close()
        if ssh_proc is not None:
            try:
                ssh_proc.stdin.close()
                ssh_proc.wait(timeout=10)
            except Exception:
                ssh_proc.kill()
            (tmp / "parity.json").write_text(json.dumps(parity, indent=1))
    return backend, acquire, carry_factory, close


def build_real_producer(args, slot, W, H):
    """Single-flight WARM/COLD producer (run() path): boot backends + one producer.

    Returns (producer, close_fn). The matrix uses build_grounding_carry directly so it
    boots the backends once; this convenience keeps run()'s single-flight path one call.
    """
    from p62_producers import WarmColdProducer
    showcase = getattr(args, "showcase_ssh_carry", False)
    _, acquire, carry_factory, close_backends = build_grounding_carry(
        args.caption, args.prune_after, args.ssh_host, args.out,
        showcase_ssh=showcase)
    # showcase carry lives on the Jetson (oracle designation only -- P6's novelty is the
    # loop, not grounding; the Jetson q8_0 nadir grounding is non-discriminative, G6).
    prod = WarmColdProducer(slot, acquire, carry_factory,
                            mode=args.arm, t_prompt=args.t_prompt, w=W, h=H,
                            oracle_gt=showcase)

    def close():
        prod.close()
        close_backends()
    return prod, close


# --- flight seam: pose in, delivered-bbox out ------------------------------
# Two real implementations, so a small seam keeps the tick loop single:
#   GtDrivenPose  -- camera slaved to a GT-scripted pose, no copter (plumbing smoke)
#   MavlinkFlight -- camera slaved to the SITL copter, PID drives it from the bbox
# The loop calls flight.pose(t) to aim the camera and flight.send(bbox) to act.

def pid_to_ned(vel):
    """CascadePID body-frame velocity -> LOCAL_NED (north, east) m/s.

    The rig holds yaw~0 (R-10: yaw never arrives; camera hard-nadir, north-up),
    so body-forward == north and body-right == east, one-to-one. yaw_rate is
    dropped: rotating a nadir camera reframes nothing. THIS is the sign-calibration
    knob -- if a live smoke shows the copter fleeing the target, negate here.
    """
    return (vel["vx"], vel["vy"])


def pose_scripted(target, alt, t):
    """Straight 60 m north sweep at alt (ego-motion independent of the target)."""
    return (60.0 * t / 20.0, 0.0, -alt, 0.0)


def pose_target_nadir(target, alt, t):
    """Hover nadir over the target. GT-DRIVEN camera -- plumbing smoke only.

    target.location is CARLA world; ned_to_carla re-adds the render base, so subtract
    it here or the camera lands base-offset away from the target.
    """
    loc = target.get_transform().location
    return (loc.x - cr.BASE_N, loc.y - cr.BASE_E, -alt, 0.0)


class GtDrivenPose:
    """Camera slaved to a GT-scripted NED pose. No copter, no verdict (plumbing)."""
    verdict_allowed = False

    def __init__(self, pose_fn, target, alt):
        self.pose_fn, self.target, self.alt = pose_fn, target, alt

    def pose(self, t):
        return self.pose_fn(self.target, self.alt, t)

    def send(self, bbox):
        pass

    def close(self):
        pass


class MavlinkFlight:
    """Camera slaved to the SITL copter; the delivered bbox drives it via CascadePID.

    This is the closed loop -- the pixels are a consequence of the copter's own
    control output, which is what Part VI exists to test. verdict_allowed=True.
    """
    verdict_allowed = True

    def __init__(self, url, alt, m=None, kp_lat=0.02, max_v=3.0):
        import sitl_fly_leg as fly
        from sitl.cascade_pid import CascadePID
        self.fly = fly
        self.alt = alt
        self._PID = CascadePID
        # kp_lat/max_v are the follow-authority knobs. The default 0.02 holds a target only under
        # dense (20 Hz oracle) delivery; at the device 2.69 Hz carry rate the P-lag lets a moving
        # target walk off-frame (steady-state offset = v/kp). Raise both so warm-start can HOLD the
        # maintained track at the real carry rate -- the CARRY rate stays device-faithful; the
        # controller gains are ours to tune (cascade_pid: "calibrate from Phase B run 1").
        self.kp_lat, self.max_v = kp_lat, max_v
        self.m = m if m is not None else fly.connect(url)   # matrix connects once, reuses
        reached = fly.arm_and_takeoff(self.m, alt)           # reuses copter if already airborne
        print(f"airborne at {reached:.1f} m; PID follow engaged (kp_lat={kp_lat}, max_v={max_v})")
        self.pid = CascadePID(img_w=cr.W, img_h=cr.H, kp_lat=kp_lat, max_vx=max_v, max_vy=max_v)
        self.last = (0.0, 0.0, -alt, 0.0)

    def reset(self):
        """Fly to origin and re-zero the PID -- start each matrix flight from one pose."""
        dist = self.fly.reset_to_origin(self.m, self.alt)
        self.pid = self._PID(img_w=cr.W, img_h=cr.H, kp_lat=self.kp_lat,
                             max_vx=self.max_v, max_vy=self.max_v)
        self.last = (0.0, 0.0, -self.alt, 0.0)
        return dist

    def pose(self, t):
        while True:                       # drain to newest -- stale NED = lagging camera
            msg = self.m.recv_match(type="LOCAL_POSITION_NED", blocking=False)
            if msg is None:
                break
            self.last = (msg.x, msg.y, msg.z, 0.0)   # yaw 0: nadir camera, north-up
        return self.last

    def send(self, bbox):
        vel = self.pid.compute(bbox)      # bbox None -> hover (all zeros)
        vn, ve = pid_to_ned(vel)
        self.fly.send_velocity(self.m, vn, ve)

    def close(self):
        self.fly.send_velocity(self.m, 0.0, 0.0)      # stop; leave it hovering in GUIDED


# --- self-test (server-free) ----------------------------------------------

def selftest():
    # iou
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert iou(None, (0, 0, 1, 1)) == 0.0
    assert abs(iou((0, 0, 10, 10), (5, 0, 15, 10)) - (50 / 150)) < 1e-9

    # box<->bbox round trip
    b = (10, 20, 30, 50)
    assert bbox_to_box(box_to_bbox(b)) == b
    assert box_to_bbox(None) is None and bbox_to_box(None) is None

    # slot: stale rejection is monotonic
    s = LatestDetectionSlot()
    assert s.write(1.0, {"cx": 1, "cy": 1, "w": 2, "h": 2}) is True
    assert s.write(0.5, {"cx": 9, "cy": 9, "w": 2, "h": 2}) is False   # stale, dropped
    assert s.read().bbox["cx"] == 1
    assert s.write(2.0, None) is True and s.read().bbox is None

    # producer latency: a box captured at t is NOT delivered until t+latency
    s2 = LatestDetectionSlot()
    p = OracleStubProducer(s2, latency_s=0.5)
    p.step(None, (0, 0, 10, 10), now_ts=100.0)
    assert s2.read().bbox is None, "delivered before latency elapsed"
    p.step(None, (0, 0, 10, 10), now_ts=100.4)
    assert s2.read().bbox is None, "delivered 0.1 s early"
    p.step(None, (0, 0, 10, 10), now_ts=100.6)
    assert s2.read().bbox is not None, "not delivered after latency"
    assert abs(iou(bbox_to_box(s2.read().bbox), (0, 0, 10, 10)) - 1.0) < 1e-9

    # ned_to_carla: Down flips to +Z, N/E pass through (guards the Phase-C sign scar)
    tf = cr.ned_to_carla(5.0, 3.0, -60.0)   # 60 m up
    assert abs(tf.location.z - 60.0) < 1e-6 and tf.location.x == 5.0 and tf.location.y == 3.0
    assert tf.rotation.pitch == -90.0

    # PID->NED coupling sign (increment 2): the closed-loop chase direction. In a
    # north-up nadir frame, target right-of-centre must drive +east, target above
    # centre (= north) must drive +north, and no bbox must hover. If a live smoke
    # shows the copter fleeing instead of chasing, the fix goes in pid_to_ned.
    from sitl.cascade_pid import CascadePID
    pid = CascadePID(img_w=cr.W, img_h=cr.H)
    vn, ve = pid_to_ned(pid.compute({"cx": cr.W / 2 + 100, "cy": cr.H / 2, "w": 30, "h": 30}))
    assert ve > 0 and abs(vn) < 1e-9, "target right-of-centre should drive +east only"
    vn, ve = pid_to_ned(pid.compute({"cx": cr.W / 2, "cy": cr.H / 2 - 100, "w": 30, "h": 30}))
    assert vn > 0 and abs(ve) < 1e-9, "target above-centre (north) should drive +north only"
    vn, ve = pid_to_ned(pid.compute(None))
    assert vn == 0.0 and ve == 0.0, "no bbox should hover"
    print("selftest OK")


# --- live plumbing smoke ---------------------------------------------------

def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    W, H, FOV = cr.W, cr.H, cr.FOV
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(60.0)
    print(f"connected: server {client.get_server_version()} client {client.get_client_version()}")
    world, cam, vehicles = cr.setup_world(client, args.town, args.vehicles)
    assert vehicles, "no vehicles spawned"
    # target: explicit index, else the vehicle nearest the copter's takeoff origin
    # (0,0) so a nadir camera can acquire it without a scripted goto.
    if args.target_index < 0:
        origin = carla.Location(0, 0, 0)
        target = min(vehicles, key=lambda v: v.get_transform().location.distance(origin))
    else:
        target = vehicles[args.target_index % len(vehicles)]
    print(f"loaded {args.town}, {len(vehicles)} vehicles, target=id{target.id} {target.type_id}")
    bboxes = {v.id: v.bounding_box for v in vehicles}   # static geometry; cache the ~17ms RPC once

    slot = LatestDetectionSlot()
    if args.arm in ("warm", "cold"):
        producer, producer_close = build_real_producer(args, slot, W, H)
        print(f"arm={args.arm}: Jetson grounding + 3090 carry (prune_after={args.prune_after}), "
              f"t_prompt={args.t_prompt}s caption={args.caption!r}")
    else:
        producer = OracleStubProducer(slot, latency_s=args.latency)
        producer_close = producer.close
    if args.pose == "mavlink":
        flight = MavlinkFlight(args.mavlink_url, args.alt)
    else:
        pose_fn = {"scripted": pose_scripted, "target_nadir": pose_target_nadir}[args.pose]
        flight = GtDrivenPose(pose_fn, target, args.alt)
    res = fly_once(world, cam, vehicles, target, bboxes, slot, producer, flight, args, out)
    producer_close()
    cam.stop(); cam.destroy()
    client.apply_batch([carla.command.DestroyActor(v) for v in vehicles])
    return res


def fly_once(world, cam, vehicles, target, bboxes, slot, producer, flight, args, out):
    """One flight: drive the loop, score, write rows/results/overlays, look-at-it guards.

    Owns NEITHER teardown NOR producer/flight lifecycle -- the caller (run() or the matrix)
    builds and disposes those, so the matrix can reuse the persistent cam/world/copter/backend
    across flights. Returns the results dict; also written to out/results.json.
    """
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    W, H, FOV = cr.W, cr.H, cr.FOV
    verdict_allowed = flight.verdict_allowed

    # analytic nadir GT-area prediction, for the Gate-A style plumbing check
    f = W / (2.0 * math.tan(math.radians(FOV) / 2.0))
    ppm = f / args.alt                      # px per metre at nadir, altitude args.alt
    bb = target.bounding_box.extent
    pred_area = (2 * bb.x * ppm) * (2 * bb.y * ppm)

    rows, frames, cframes = [], {}, {}
    t0 = time.time()
    n = int(args.seconds / cr.FIXED_DT)
    for i in range(n):
        t = i * cr.FIXED_DT
        ned = flight.pose(t)                          # copter NED (mavlink) or scripted
        cam.set_transform(cr.ned_to_carla(*ned, pitch_deg=args.pitch))
        slack = (t0 + (i + 1) * cr.FIXED_DT) - time.time()
        if slack > 0:
            time.sleep(slack)
        now = time.time()
        cam_tf = cam.get_transform()
        snap = world.get_snapshot()                  # ONE RPC/tick; transforms read locally
        ts = snap.find(target.id)
        gt = actor_box(bboxes[target.id], ts.get_transform(), cam_tf, W, H, FOV) if ts else None
        with cr._lock:
            fr = cr._latest["bgr"]
        fr = fr.copy() if fr is not None else None
        producer.step(fr, gt, now - t0)               # loop-relative time (t_prompt is relative)
        det = slot.read()                            # control loop reads newest
        # oracle_drive (DECOUPLED arm, P6.2-COUPLING): the oracle actor_box steers the PID
        # while the warm track is still scored but never touches control -- cuts the
        # perception->control feedback path to isolate self-induced ego-motion (C1).
        drive_bbox = box_to_bbox(gt) if getattr(args, "oracle_drive", False) else det.bbox
        flight.send(drive_bbox)                       # driven bbox -> copter (PID, mavlink)
        deliver_box = bbox_to_box(det.bbox)          # warm track ALWAYS scored (never steers under oracle_drive)
        lock_iou = iou(deliver_box, gt)
        if i % 50 == 0:
            print(f"  tick {i}/{n} t={now - t0:.1f}s iou={lock_iou:.2f} gt={bool(gt)} bbox={bool(deliver_box)}", flush=True)
        on = match_actor(vehicles, bboxes, snap, cam_tf, deliver_box, W, H, FOV) if deliver_box else None
        rows.append({"i": i, "t": round(now - t0, 3),
                     "post_prompt": bool((now - t0) >= args.t_prompt),  # frozen gate scores this window
                     "gt": [round(x, 1) for x in gt] if gt else None,
                     "deliver": [round(x, 1) for x in deliver_box] if deliver_box else None,
                     "lock_iou": round(lock_iou, 3),
                     "on_target": bool(on and on.id == target.id),
                     "on_other": bool(on and on.id != target.id),
                     "gt_area": round((gt[2] - gt[0]) * (gt[3] - gt[1]), 1) if gt else None})
        if fr is not None and i in (n // 4, n // 2, n - 1):
            cframes[i] = fr.copy()                     # clean frame (no boxes) -- G6 grounds this
            ov = fr.copy()
            if gt:
                p = [int(v) for v in gt]
                cv2.rectangle(ov, (p[0], p[1]), (p[2], p[3]), (0, 255, 0), 2)  # GT green
            if deliver_box:
                q = [int(v) for v in deliver_box]
                col = (0, 255, 0) if lock_iou >= 0.25 else (0, 0, 255)
                cv2.rectangle(ov, (q[0], q[1]), (q[2], q[3]), col, 1)          # delivered
            cv2.putText(ov, f"i{i} iou{lock_iou:.2f} on_tgt={bool(on and on.id==target.id)}",
                        (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            frames[i] = ov

    print(f"  loop done: {len(rows)} ticks in {time.time() - t0:.1f}s (target {n * cr.FIXED_DT:.1f}s)", flush=True)
    flight.close()          # stop the copter (hovers; reusable across matrix flights)

    # --- plumbing scoring ---
    gt_frames = [r for r in rows if r["gt"] is not None]
    locks = [r for r in gt_frames if r["lock_iou"] >= 0.25]
    # post-prompt window: WARM/COLD deliver only after t_prompt; oracle has no prompt.
    if args.arm in ("warm", "cold", "decoupled"):
        post = [r for r in gt_frames if r["t"] >= args.t_prompt]
    else:
        post = gt_frames[len(gt_frames) // 4:]        # crude proxy for the oracle stub
    coverage = (sum(r["lock_iou"] >= 0.25 for r in post) / len(post)) if post else 0.0
    res = {
        "mode": "plumbing_smoke" if not verdict_allowed else "flight",
        "arm": args.arm, "oracle_drive": bool(getattr(args, "oracle_drive", False)),
        "producer": producer.info,
        "pose": args.pose, "verdict_allowed": verdict_allowed,
        "town": args.town, "vehicles": len(vehicles), "target_id": target.id,
        "target_type": target.type_id, "alt": args.alt, "latency_s": args.latency,
        "t_prompt": args.t_prompt, "caption": args.caption,
        "ticks": n, "gt_frames": len(gt_frames), "post_prompt_frames": len(post),
        "genuine_lock_frames": len(locks),
        "coverage": round(coverage, 3),
        "pred_nadir_area_px": round(pred_area, 1),
        "median_gt_area_px": float(np.median([r["gt_area"] for r in gt_frames])) if gt_frames else None,
    }
    (out / "rows.json").write_text(json.dumps(rows, indent=1))
    for i, fr in sorted(frames.items()):
        cv2.imwrite(str(out / f"overlay_{i:05d}.png"), fr)
        print(f"  wrote {out / f'overlay_{i:05d}.png'}")
    for i, cf in sorted(cframes.items()):                 # clean frames for G6 grounding
        cv2.imwrite(str(out / f"frame_{i:05d}.png"), cf)

    # look-at-it mechanical guards
    mid = frames[sorted(frames)[len(frames) // 2]]
    res["dominant_frac"] = float(cr.dominant_frac(mid))
    assert res["dominant_frac"] < 0.99, "blank render"
    keys = sorted(frames)
    assert not np.array_equal(frames[keys[0]], frames[keys[-1]]), "dead feed (identical frames)"
    assert len(gt_frames) > 0, "target never projected into frame"
    # nadir GT-area sanity (only meaningful for target_nadir): axis-aligned box over a
    # rotated car + model variance => a loose 0.3-3.0x band, same spirit as gt_bank Gate-A
    if args.pose == "target_nadir" and res["median_gt_area_px"]:
        ratio = res["median_gt_area_px"] / pred_area
        res["gt_area_ratio"] = round(ratio, 2)
        assert 0.3 < ratio < 3.0, f"GT area {ratio:.2f}x prediction -- projection likely wrong"

    (out / "results.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    print("NOT verified until the written overlays are opened and viewed.")
    if not verdict_allowed:
        print("mode=plumbing_smoke: NO P6.2 follow verdict (GT-driven camera).")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="server-free logic check")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--town", default=cr.TOWN)
    ap.add_argument("--vehicles", type=int, default=40)
    ap.add_argument("--target-index", type=int, default=-1,
                    help="vehicle index; <0 = nearest to takeoff origin")
    ap.add_argument("--mavlink-url", default="tcp:127.0.0.1:5760")
    ap.add_argument("--pose", default="target_nadir", choices=["scripted", "target_nadir", "mavlink"])
    ap.add_argument("--alt", type=float, default=60.0)
    ap.add_argument("--pitch", type=float, default=-90.0)
    ap.add_argument("--latency", type=float, default=0.0, help="stub producer delivery latency, s")
    ap.add_argument("--oracle-drive", action="store_true",
                    help="DECOUPLED arm (P6.2-COUPLING): oracle actor_box steers the PID; the "
                         "warm track is scored but never steers (cuts the perception->control loop)")
    ap.add_argument("--arm", default="oracle", choices=["oracle", "warm", "cold", "decoupled"],
                    help="detection producer: oracle stub, or real WARM/COLD (Jetson+3090)")
    ap.add_argument("--t-prompt", type=float, default=8.0,
                    help="operator command time (s into loop); idle window before it")
    ap.add_argument("--caption", default="the car in the center",
                    help="grounding phrase (G6: needs a discriminative spatial ref)")
    ap.add_argument("--prune-after", type=int, default=32,
                    help="SAM2 carry ring length (R-16: 32 co-resident, 100 OOMs)")
    ap.add_argument("--ssh-host", default="jetson")
    ap.add_argument("--showcase-ssh-carry", action="store_true",
                    help="P6.2-SHOWCASE: route SAM2 carry LITERALLY to the Jetson over "
                         "ssh-stdio + score a 3090 twin for parity (oracle designation)")
    ap.add_argument("--seconds", type=float, default=12.0)
    ap.add_argument("--out", default="runs/p62_smoke")
    args = ap.parse_args()
    if args.selftest:
        selftest(); return
    try:
        run(args)
    except AssertionError as e:
        print(f"\nFAIL: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
