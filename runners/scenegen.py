#!/usr/bin/env python3
"""
scenegen.py -- deterministic multi-candidate scene generator on Gazebo Harmonic (P5.7).

Drives an ALREADY RUNNING headless `gz sim -s` server (world: select_arena, started
paused) as a pure puppeteer: every entity pose (two colour-distinct hatchbacks + the
UAV camera) is computed in seeded numpy and pushed with set_pose_vector while the
world is PAUSED, then the world is stepped exactly one camera period
(`pause: true, multi_step: 40` = 40 x 1 ms = 1 frame @ 25 Hz). Nothing moves except
by command, so every rendered frame shows exactly the commanded state -- ground-truth
2D boxes are computed by projecting the commanded 3D boxes through the commanded
camera, no estimation anywhere.

Design facts this file encodes (empirically verified 2026-07-17, gz sim 8.14.0,
RTX 3090 headless EGL -- see experiments/2026-07-17-sim-scenegen/README.md):
  - plain `multi_step: N` LEAKS into free-running; `pause: true` must be in the same
    WorldControl request or the sim keeps running after the batch.
  - SDF camera pitch +90 deg looks straight DOWN (nadir).
  - Fuel hatchback textures do not load under this rig (map_Kd/map_Ka resolve to
    remote URLs / are dropped); a solid <material> override in the spawn SDF renders
    reliably, so vehicle colour comes from the SDF material, not the texture.
  - gz-transport pybind service *requests* CONCURRENT WITH an image-subscriber
    callback in the SAME process crash on the GIL (GAZEBO_LIVE_FEED.md). P5.7
    routed around this with per-call `gz service` CLI subprocesses (~0.29 s/call,
    ~480 ephemeral transport nodes per 240-frame run) and DIED for it: the server
    intermittently failed to route a reply back to an ephemeral node
    ("NodeShared::RecvSrvRequest() error sending response: Host unreachable"),
    ~one failure per ~236 calls, so no 240-frame run ever completed (P5.7 = NO
    [infra FAIL]). P5.8 fix: ONE persistent pybind requester Node living in a
    DEDICATED child process (`scenegen.py proxy`, JSON-lines over pipes) that has
    NO subscriptions -- the GIL crash condition (request overlapping a subscriber
    callback in one process) cannot occur, and there is no per-call node churn.
    The recorder process keeps its subscribe-only pybind node exactly as before.
  - retry policy on top (belt and braces): set_pose_vector is idempotent ->
    plain re-issue; a world-control step whose *reply* was lost may still have
    EXECUTED, so on request failure we first wait RESPONSE_LOST_WAIT_S for the
    frame to arrive and only re-issue if it does not. A double-step would show
    up mechanically as an 80 ms sim-stamp jump -> G1 catches it.

Usage (server must already be running -- see the experiment README for the exact
nohup launch line; scenegen never spawns `gz sim` itself):
    .venv-ft/bin/python runners/scenegen.py record --seed 101 --frames 240 \
        --out experiments/2026-07-17-scenegen-transport/runs/seed101_A
    .venv-ft/bin/python runners/scenegen.py selfcheck    # no gz / no GPU needed
    .venv-ft/bin/python runners/scenegen.py killserver   # kill select_arena servers by pgid
    (`scenegen.py proxy` is internal -- the persistent requester child process.)
"""
import argparse
import json
import math
import subprocess
import sys
import threading
import time
from pathlib import Path

import cv2  # venv cv2 BEFORE the dist-packages path append (ABI clash otherwise)
import numpy as np

sys.path.append("/usr/lib/python3/dist-packages")  # gz.transport13 / gz.msgs10 only

REPO = Path(__file__).resolve().parent.parent
WORLD = "select_arena"
CAM_TOPIC = f"/world/{WORLD}/model/uav_cam/link/cam_link/sensor/cam/image"
MESH = REPO / "runners" / "sitl" / "models" / "hatchback_white" / "meshes" / "hatchback.obj"

# Camera intrinsics -- MUST match select_arena.sdf (1280x720, hfov 1.2 rad).
W, H, HFOV = 1280, 720, 1.2
FX = (W / 2) / math.tan(HFOV / 2)
FY = FX
CX, CY = W / 2, H / 2

# Hatchback local AABB in MODEL frame, metres (obj bounds * 0.0254 scale, then the
# +90 deg visual yaw in the spawn SDF: model x = -obj_y, model y = obj_x).
# Recomputed from the mesh in `selfcheck`; update both if the asset changes.
CAR_AABB = {"x": (-1.657, 2.344), "y": (-1.070, 1.070), "z": (-0.011, 1.557)}

CAR_COLORS = {  # solid SDF material (r, g, b); phrase used by later select experiments
    "white": ((0.92, 0.92, 0.92), "the white car"),
    "blue": ((0.05, 0.12, 0.55), "the blue car"),
    "red": ((0.60, 0.05, 0.05), "the red car"),
}

CAM_PERIOD_STEPS = 40  # 40 x 1 ms = one 25 Hz camera frame per batch
STEP_TIMEOUT_S = 8.0
SETTLE_S = 0.08
SVC_TIMEOUT_MS = 5000
RESPONSE_LOST_WAIT_S = 3.0  # request failed: how long the step may still land
MAX_TRIES = 3               # per service call (first attempt included)

# ---------------------------------------------------------------- gz plumbing


class ProxyClient:
    """ONE persistent gz-transport requester Node, living in a dedicated child
    process (`scenegen.py proxy`) that never subscribes to anything -- so the
    pybind GIL crash (request overlapping a subscriber callback in the same
    process) cannot occur, and there is zero per-call transport-node churn
    (the P5.7 killer). Protocol: JSON lines over stdin/stdout."""

    def __init__(self):
        self.restarts = 0
        self._id = 0
        self._start()

    def _start(self):
        import queue
        self._p = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "proxy"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self._q = queue.Queue()

        def _reader(p, q):
            for line in p.stdout:
                q.put(line)
            q.put(None)  # EOF sentinel

        threading.Thread(target=_reader, args=(self._p, self._q), daemon=True).start()
        got, resp = self._roundtrip({"op": "ping"}, deadline_s=20.0)
        if not got or resp.get("op") != "pong":
            raise RuntimeError(f"gz proxy failed to start (no pong: {resp})")

    def _roundtrip(self, obj, deadline_s):
        import queue
        try:
            self._p.stdin.write(json.dumps(obj) + "\n")
            self._p.stdin.flush()
        except (BrokenPipeError, OSError):
            return False, None
        try:
            line = self._q.get(timeout=deadline_s)
        except queue.Empty:
            return False, None
        if line is None:
            return False, None
        try:
            return True, json.loads(line)
        except json.JSONDecodeError:
            return False, None

    def call(self, service, reqtype, req, timeout_ms=SVC_TIMEOUT_MS):
        """One service request through the persistent node -> (ok, err_text).
        A hung/dead proxy is restarted and reported as a failed call."""
        self._id += 1
        got, resp = self._roundtrip(
            {"op": "req", "id": self._id, "service": service, "reqtype": reqtype,
             "req": req, "timeout_ms": timeout_ms},
            deadline_s=timeout_ms / 1000 + 5.0)
        if not got or resp.get("id") != self._id:
            self.restarts += 1
            self._kill()
            self._start()
            return False, f"proxy dead/hung -- restarted (resp={resp})"
        return bool(resp.get("ok")), resp.get("err", "")

    def _kill(self):
        try:
            self._p.kill()
            self._p.wait(timeout=5)
        except Exception:
            pass

    def close(self):
        try:
            self._p.stdin.close()
            self._p.wait(timeout=5)
        except Exception:
            self._kill()


def proxy_main():
    """The dedicated requester process. No subscriptions, one Node, lives for
    the whole recording. Replies on stdout, one JSON line per request."""
    import gz.transport13 as transport
    from google.protobuf import text_format
    from gz.msgs10 import boolean_pb2, entity_factory_pb2, pose_v_pb2, world_control_pb2

    types = {
        "gz.msgs.Pose_V": pose_v_pb2.Pose_V,
        "gz.msgs.WorldControl": world_control_pb2.WorldControl,
        "gz.msgs.EntityFactory": entity_factory_pb2.EntityFactory,
    }
    node = transport.Node()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        if o.get("op") == "ping":
            print(json.dumps({"op": "pong"}), flush=True)
            continue
        try:
            cls = types[o["reqtype"]]
            msg = cls()
            text_format.Parse(o["req"], msg)
            result, rep = node.request(o["service"], msg, cls, boolean_pb2.Boolean,
                                       int(o["timeout_ms"]))
            ok = bool(result) and bool(getattr(rep, "data", False))
            err = "" if ok else f"result={result} rep_data={getattr(rep, 'data', None)}"
        except Exception as e:  # noqa: BLE001 -- proxy must never die on one request
            ok, err = False, repr(e)
        print(json.dumps({"id": o.get("id"), "ok": ok, "err": err[:300]}), flush=True)


class GzClient:
    """Image subscriber (pybind, subscribe-only: safe) + persistent-proxy caller."""

    def __init__(self):
        self._lock = threading.Lock()
        self._arr = None
        self._stamp_ns = -1
        self._count = 0
        self.retries_pose = 0     # failed set_pose_vector attempts that were re-issued
        self.retries_step = 0     # failed world-control attempts re-issued (no frame landed)
        self.response_lost = 0    # step executed but the service reply was lost
        self.spawn_warns = []
        import gz.transport13 as transport
        from gz.msgs10 import image_pb2

        self._node = transport.Node()  # keep ref or the subscription is GC'd

        def on_image(msg):
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
            with self._lock:
                self._arr = arr.copy()
                self._stamp_ns = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nsec
                self._count += 1

        ok = self._node.subscribe(image_pb2.Image, CAM_TOPIC, on_image)
        if not ok:
            raise RuntimeError(f"subscribe failed: {CAM_TOPIC}")
        self.proxy = ProxyClient()

    def latest(self):
        with self._lock:
            return (None if self._arr is None else self._arr.copy()), self._stamp_ns, self._count

    def set_poses(self, named_poses):
        """named_poses: list of (name, (x,y,z), (qw,qx,qy,qz)). One batched call.
        Idempotent -> plain retry on failure."""
        parts = []
        for name, p, q in named_poses:
            parts.append(
                f'pose: {{name: "{name}", position: {{x: {p[0]:.6f}, y: {p[1]:.6f}, z: {p[2]:.6f}}}, '
                f'orientation: {{w: {q[0]:.8f}, x: {q[1]:.8f}, y: {q[2]:.8f}, z: {q[3]:.8f}}}}}')
        req = ", ".join(parts)
        out = ""
        for _ in range(MAX_TRIES):
            ok, out = self.proxy.call(f"/world/{WORLD}/set_pose_vector", "gz.msgs.Pose_V", req)
            if ok:
                return
            self.retries_pose += 1
            time.sleep(0.2)
        raise RuntimeError(f"set_pose_vector failed after {MAX_TRIES} tries: {out[:300]}")

    def _wait_frame(self, stamp0, wait_s):
        t0 = time.time()
        while time.time() - t0 < wait_s:
            arr, stamp, _ = self.latest()
            if stamp > stamp0:
                time.sleep(SETTLE_S)  # let a same-batch straggler land, then re-read
                arr, stamp, _ = self.latest()
                return arr, stamp
            time.sleep(0.01)
        return None, None

    def step_one_frame(self):
        """Advance one camera period; return the frame rendered for the current
        state. NOT idempotent -> a failed request may still have executed with
        only the reply lost, so wait for the frame before re-issuing."""
        _, stamp0, _ = self.latest()
        out = ""
        for _ in range(MAX_TRIES):
            ok, out = self.proxy.call(f"/world/{WORLD}/control", "gz.msgs.WorldControl",
                                      f"pause: true, multi_step: {CAM_PERIOD_STEPS}")
            if ok:
                arr, stamp = self._wait_frame(stamp0, STEP_TIMEOUT_S)
                if arr is not None:
                    return arr, stamp
                raise RuntimeError(
                    f"step acked but no frame within {STEP_TIMEOUT_S}s (stamp0={stamp0}) "
                    "-- renderer stall; re-issuing would double-step")
            arr, stamp = self._wait_frame(stamp0, RESPONSE_LOST_WAIT_S)
            if arr is not None:
                self.response_lost += 1  # step executed, reply lost -> frame is valid
                return arr, stamp
            self.retries_step += 1  # genuinely not executed -> safe to re-issue
        raise RuntimeError(f"world control failed after {MAX_TRIES} tries: {out[:300]}")

    def spawn_car(self, name, color_rgb):
        sdf = car_sdf(name, color_rgb).replace('"', '\\"')
        req = f'sdf: "{sdf}", name: "{name}"'
        out = ""
        for _ in range(MAX_TRIES):
            ok, out = self.proxy.call(f"/world/{WORLD}/create", "gz.msgs.EntityFactory", req)
            if ok:
                return
            time.sleep(0.3)
        # A create whose reply was lost may have executed; the retry then fails
        # ("name already exists"), so a hard raise here could kill a healthy run.
        # Continue with a recorded warning -- a truly missing car fails G3 and V.
        self.spawn_warns.append(f"{name}: {out[:200]}")
        print(f"[scenegen] WARN spawn {name} unconfirmed: {out[:200]}", flush=True)


def car_sdf(name, rgb):
    c = f"{rgb[0]} {rgb[1]} {rgb[2]}"
    return (
        f'<sdf version="1.6"><model name="{name}"><static>true</static>'
        f'<link name="link"><visual name="visual">'
        f'<pose>0 0 0 0 0 1.57079632679</pose>'
        f'<geometry><mesh><scale>0.0254 0.0254 0.0254</scale><uri>{MESH}</uri></mesh></geometry>'
        f'<material><ambient>{c} 1</ambient><diffuse>{c} 1</diffuse>'
        f'<specular>0.3 0.3 0.3 1</specular></material>'
        f'</visual></link></model></sdf>')


# ---------------------------------------------------------------- math

def quat_yaw_pitch(yaw, pitch):
    """SDF ZYX (roll=0): q = qz(yaw) * qy(pitch) -> (w,x,y,z). pitch>0 looks down."""
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    return (cy * cp, -sy * sp, cy * sp, sy * cp)


def quat_to_R(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def look_at(cam_pos, target):
    """Yaw/pitch (roll 0) pointing the camera +X axis at target; returns quat."""
    f = np.asarray(target, float) - np.asarray(cam_pos, float)
    f = f / np.linalg.norm(f)
    yaw = math.atan2(f[1], f[0])
    pitch = -math.asin(f[2])  # f_z<0 (looking down) -> pitch>0 = down (verified)
    return quat_yaw_pitch(yaw, pitch), yaw, pitch


def project_box(cam_pos, cam_quat, car_pos, car_yaw):
    """Project the car's 3D AABB corners into the image. Returns (bbox or None, area).

    gz camera frame: +X forward (optical axis), +Y left, +Z up:
        u = CX - FX * Yc/Xc ; v = CY - FY * Zc/Xc.
    """
    xs, ys, zs = CAR_AABB["x"], CAR_AABB["y"], CAR_AABB["z"]
    corners = np.array([[x, y, z] for x in xs for y in ys for z in zs])
    cy, sy = math.cos(car_yaw), math.sin(car_yaw)
    Rcar = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    world = corners @ Rcar.T + np.asarray(car_pos)
    Rcam = quat_to_R(cam_quat)
    pc = (world - np.asarray(cam_pos)) @ Rcam  # R^T (p - t), row-vector form
    if (pc[:, 0] <= 0.2).any():  # any corner behind/at the near plane -> not scorable
        return None, 0.0
    u = CX - FX * pc[:, 1] / pc[:, 0]
    v = CY - FY * pc[:, 2] / pc[:, 0]
    x1, x2 = float(u.min()), float(u.max())
    y1, y2 = float(v.min()), float(v.max())
    x1c, y1c = max(0.0, x1), max(0.0, y1)
    x2c, y2c = min(float(W), x2), min(float(H), y2)
    if x2c - x1c < 2 or y2c - y1c < 2:
        return None, 0.0
    return [round(x1c, 1), round(y1c, 1), round(x2c, 1), round(y2c, 1)], \
        round((x2c - x1c) * (y2c - y1c), 1)


# ---------------------------------------------------------------- scenario

GRID = np.array([0.0, 0.0])       # start-grid origin on the Sonoma straight
ROAD_HEADING = math.radians(145)  # the start straight runs along ~145 deg (verified)
CAR_Z = 0.05

# P5.9 kerb-safe corridor -- calibrated, not guessed. Source:
# experiments/2026-07-17-kerbsafe-scenebank/probe_kerb.py sweep
# (curation/kerb_heatmap.png + kerb_sweep.json, 2026-07-17, gz 8.14.0):
# rendered-car integrity (pixel-count ratio >= 0.90 AND largest-connected-
# component fraction >= 0.98) holds for lat in [-5.5, +2.5] at EVERY station
# s in [0, 70]. The median kerb is NOT parallel to ROAD_HEADING: it converges
# from lat ~7.5 at s=10 to ~3.5 at s=70 (~4 deg skew), which is why P5.8's
# seed 101 distractor (lat 4.6-5.2) only clipped late in the clip. Scenarios
# must therefore respect BOTH a lat corridor and an s cap; author_scenario
# asserts them so a future band edit cannot silently reintroduce clipping.
LAT_SAFE = (-5.2, 2.0)  # sweep corridor [-5.5, +2.5] minus 0.3/0.5 m margin
S_SAFE_MAX = 70.0       # sweep's calibrated along-track extent


def author_scenario(seed, n_frames, fps=25.0, profile="v1"):
    """Seeded, fully precomputed poses for 2 cars + camera. Pure numpy, no gz.
    profile 'v1' = P5.9 bank (disjoint lanes, no crossings) -- byte-stable, do
    not touch. profile 'v2' = P5.11 crossing bank (designed occlusion).
    profile 'v3' = P5.17 lag-stress bank (crossing + post-prompt camera hold +
    z-order coin)."""
    if profile == "v2":
        return author_scenario_v2(seed, n_frames, fps)
    if profile == "v3":
        return author_scenario_v3(seed, n_frames, fps)
    assert profile == "v1", profile
    rng = np.random.default_rng(seed)
    h = ROAD_HEADING
    u = np.array([math.cos(h), math.sin(h)])   # along-track unit
    n = np.array([-math.sin(h), math.cos(h)])  # left-of-track unit
    t = np.arange(n_frames) / fps

    def car(lat_lo, lat_hi, s0, v):
        lat0 = rng.uniform(lat_lo, lat_hi)
        amp, per, ph = rng.uniform(0.2, 0.5), rng.uniform(4.0, 9.0), rng.uniform(0, 2 * math.pi)
        lat = lat0 + amp * np.sin(2 * math.pi * t / per + ph)
        s = s0 + v * t
        xy = GRID + np.outer(s, u) + np.outer(lat, n)
        dlat = np.gradient(lat, 1.0 / fps)
        yaw = h + np.arctan2(dlat, v)
        return xy, yaw, v

    # Bands are kerb-safe by construction (see LAT_SAFE above): worst case
    # target lat -4.5-0.5 = -5.0, distractor lat 1.3+0.5 = +1.8, both inside
    # LAT_SAFE; distractor s_max = 10 + 6.0*(239/25) = 67.4 <= S_SAFE_MAX.
    v_t = rng.uniform(3.0, 6.0)
    tgt_xy, tgt_yaw, v_t = car(-4.5, -2.2, rng.uniform(-4, 4), v_t)
    v_d = float(np.clip(v_t + rng.uniform(-1.5, 1.5), 2.5, 6.0))
    dis_xy, dis_yaw, v_d = car(0.5, 1.3, rng.uniform(4, 10), v_d)
    for xy in (tgt_xy, dis_xy):
        lat_v, s_v = xy @ n, xy @ u
        assert lat_v.min() >= LAT_SAFE[0] and lat_v.max() <= LAT_SAFE[1], \
            f"seed {seed}: lat [{lat_v.min():.2f},{lat_v.max():.2f}] outside kerb-safe {LAT_SAFE}"
        assert s_v.max() <= S_SAFE_MAX, \
            f"seed {seed}: s_max {s_v.max():.1f} beyond calibrated {S_SAFE_MAX}"

    mid = (tgt_xy + dis_xy) / 2
    standoff = rng.uniform(14, 22)
    alt = rng.uniform(16, 26)
    bob_a, bob_p = rng.uniform(0.5, 1.5), rng.uniform(5.0, 11.0)
    sway_a, sway_p = rng.uniform(1.0, 3.0), rng.uniform(6.0, 13.0)
    aim_err = rng.uniform(-1.5, 1.5, size=2)  # constant aim offset, metres at target
    cam_pos = np.zeros((n_frames, 3))
    cam_quat = np.zeros((n_frames, 4))
    for i in range(n_frames):
        p = np.array([*(mid[i] - u * standoff + n * (sway_a * math.sin(2 * math.pi * t[i] / sway_p))),
                      alt + bob_a * math.sin(2 * math.pi * t[i] / bob_p)])
        q, _, _ = look_at(p, [mid[i][0] + aim_err[0], mid[i][1] + aim_err[1], 0.0])
        cam_pos[i] = p
        cam_quat[i] = q
    return {
        "seed": seed, "n_frames": n_frames, "fps": fps,
        "target": {"name": "car_white", "color": "white", "xy": tgt_xy, "yaw": tgt_yaw, "v": v_t},
        "distractor": {"name": "car_blue", "color": "blue", "xy": dis_xy, "yaw": dis_yaw, "v": v_d},
        "cam_pos": cam_pos, "cam_quat": cam_quat,
        "params": {"standoff": standoff, "alt": alt, "aim_err": aim_err.tolist(),
                   "v_target": v_t, "v_distractor": v_d},
    }


# ------------------------------------------------- v2 crossing profile (P5.11)
# Bank v2 exists to manufacture the ID-ambiguity hazard bank v1 lacked (P5.10:
# max GT-GT image IoU 0.000 across all 12 v1 clips -> both select contracts at
# ceiling). Design: the blue distractor rides BEHIND the white target for the
# whole clip (smaller s = nearer to the trailing camera = always the OCCLUDER,
# never interpenetrating: |ds| >= 5.5 m by construction, asserted), and makes
# ONE smooth lane change that sweeps THROUGH the target's lat -- while the two
# are depth-stacked the blue body passes over the white body in image space: a
# DESIGNED occlusion with exact, precomputable geometry. Because poses are
# authored in pure numpy and GT is projected (project_box), the per-frame
# GT-GT IoU trace is computable OFFLINE (predicted_gtgt_iou) -- crossing
# screens are design-time facts, not run-time hopes.

V2_N_FRAMES = 300          # 12.0 s @ 25 Hz (s-corridor-safe at the v2 speeds)
V2_PROMPT_FRAME = 150      # t_p = 6.0 s -- documented here for the screens;
                           # the select harness owns the actual prompt timing
V2_MIN_GAP_S = 5.5         # min along-track separation, asserted (no contact)


def author_scenario_v2(seed, n_frames, fps=25.0):
    rng = np.random.default_rng(seed)
    h = ROAD_HEADING
    u = np.array([math.cos(h), math.sin(h)])
    n = np.array([-math.sin(h), math.cos(h)])
    t = np.arange(n_frames) / fps

    # white target: constant lane, small sway
    v_t = rng.uniform(2.2, 3.4)
    s0_t = rng.uniform(5.0, 12.0)
    lat_w0 = rng.uniform(-3.0, -2.4)
    amp_w = rng.uniform(0.10, 0.25)
    per_w, ph_w = rng.uniform(5.0, 9.0), rng.uniform(0, 2 * math.pi)
    lat_w = lat_w0 + amp_w * np.sin(2 * math.pi * t / per_w + ph_w)
    s_w = s0_t + v_t * t

    # blue distractor: behind for the whole clip, TWO-STAGE lane move (an
    # overtake prep): pull IN behind the target's lane, HOLD there ~1.5 s
    # (the sustained designed occlusion -- blue tailgates white along the
    # camera ray), then pull OUT to the far-left lane. A single fast
    # smoothstep sweep gave only a blink of overlap (peak IoU ~0.17, zero
    # sustained frames -- measured, see P5.11 README); the hold buys a
    # multi-frame occlusion window. All stages END before the prompt frame
    # (worst case 5.7 s < 6.0 s) so prompt-time delivery stays unambiguous.
    # Gap kept tight (|ds| in ~[5.9, 7.5] m): occlusion needs the depth
    # stack shallow (alt/standoff scan in the P5.11 README).
    ds0 = rng.uniform(-6.9, -5.9)
    dv = rng.uniform(-0.05, 0.0)           # keeps ds in [-7.5, -5.9] over 12 s
    v_d = v_t + dv
    lat_b_a = rng.uniform(0.7, 1.3)        # start: right lane
    lat_b_b = rng.uniform(-4.8, -4.3)      # end: far-left lane
    t_in0 = rng.uniform(0.7, 1.0)          # pull-in start (s)
    T_in = rng.uniform(0.9, 1.2)           # pull-in duration (s)
    T_hold = rng.uniform(1.3, 1.8)         # in-lane hold = occlusion window (s)
    T_out = rng.uniform(1.3, 1.7)          # pull-out duration (s)
    amp_b = rng.uniform(0.08, 0.20)
    per_b, ph_b = rng.uniform(5.0, 9.0), rng.uniform(0, 2 * math.pi)

    def sstep(t0, T):
        x = np.clip((t - t0) / T, 0.0, 1.0)
        return x * x * (3.0 - 2.0 * x)

    lat_hold = lat_w0                      # dead-centre of the target's lane
    lat_b = lat_b_a \
        + (lat_hold - lat_b_a) * sstep(t_in0, T_in) \
        + (lat_b_b - lat_hold) * sstep(t_in0 + T_in + T_hold, T_out) \
        + amp_b * np.sin(2 * math.pi * t / per_b + ph_b)
    s_b = s0_t + ds0 + v_d * t

    def track(s, lat, v):
        xy = GRID + np.outer(s, u) + np.outer(lat, n)
        dlat = np.gradient(lat, 1.0 / fps)
        yaw = h + np.arctan2(dlat, v)
        return xy, yaw

    tgt_xy, tgt_yaw = track(s_w, lat_w, v_t)
    dis_xy, dis_yaw = track(s_b, lat_b, v_d)

    # hard construction guarantees (a band edit cannot silently regress these)
    for xy in (tgt_xy, dis_xy):
        lat_v, s_v = xy @ n, xy @ u
        assert lat_v.min() >= LAT_SAFE[0] and lat_v.max() <= LAT_SAFE[1], \
            f"v2 seed {seed}: lat [{lat_v.min():.2f},{lat_v.max():.2f}] outside {LAT_SAFE}"
        assert s_v.max() <= S_SAFE_MAX, \
            f"v2 seed {seed}: s_max {s_v.max():.1f} beyond {S_SAFE_MAX}"
    gap = s_b - s_w
    assert gap.max() <= -V2_MIN_GAP_S, \
        f"v2 seed {seed}: min |ds| {-gap.max():.2f} < {V2_MIN_GAP_S} (contact risk)"

    # LOW, LONG camera: occlusion is a grazing-view phenomenon. The offline
    # scan (P5.11 README) shows the sightline from a v1-style camera
    # (alt 16-26) to the far car clears the near car's roof by metres; only
    # alt ~4-6 m with standoff 22-26 m puts the near body across the ray
    # (predicted lat-aligned GT-GT IoU 0.20-0.41). Sway/bob tightened so the
    # crossing window is not swept away by camera motion.
    mid = (tgt_xy + dis_xy) / 2
    standoff = rng.uniform(22, 26)
    alt = rng.uniform(4.0, 6.0)
    bob_a, bob_p = rng.uniform(0.2, 0.6), rng.uniform(5.0, 11.0)
    sway_a, sway_p = rng.uniform(0.5, 1.5), rng.uniform(6.0, 13.0)
    aim_err = rng.uniform(-1.5, 1.5, size=2)
    cam_pos = np.zeros((n_frames, 3))
    cam_quat = np.zeros((n_frames, 4))
    for i in range(n_frames):
        p = np.array([*(mid[i] - u * standoff
                        + n * (sway_a * math.sin(2 * math.pi * t[i] / sway_p))),
                      alt + bob_a * math.sin(2 * math.pi * t[i] / bob_p)])
        q, _, _ = look_at(p, [mid[i][0] + aim_err[0], mid[i][1] + aim_err[1], 0.0])
        cam_pos[i] = p
        cam_quat[i] = q
    return {
        "seed": seed, "n_frames": n_frames, "fps": fps, "profile": "v2",
        "target": {"name": "car_white", "color": "white", "xy": tgt_xy,
                   "yaw": tgt_yaw, "v": v_t},
        "distractor": {"name": "car_blue", "color": "blue", "xy": dis_xy,
                       "yaw": dis_yaw, "v": v_d},
        "cam_pos": cam_pos, "cam_quat": cam_quat,
        "params": {"standoff": standoff, "alt": alt, "aim_err": aim_err.tolist(),
                   "v_target": v_t, "v_distractor": v_d, "ds0": ds0,
                   "lat_b_a": lat_b_a, "lat_b_b": lat_b_b,
                   "t_in0": t_in0, "T_in": T_in,
                   "T_hold": T_hold, "T_out": T_out},
    }


# ------------------------------------------- v3 lag-stress profile (P5.17)
# Bank v2.1 could not separate the select contracts (P5.13 = NO branch 3):
# the camera tracks the two-car midpoint every frame, so after the prompt the
# target's IMAGE box barely moves (measured dcx 0.4-15.6 px over the 109-frame
# RG delivery lag) -- a stale delivered box scores as well as a fresh one, and
# the RG contract's ~4.4 s latency is free. The P5.13 audit pre-registered
# three mandatory properties for the next bank, implemented here:
#   1. post-prompt lag stress: the camera's tracking ANCHOR (midpoint + aim
#      point) freezes at the prompt frame (V3_HOLD_FRAME); bob/sway keep
#      oscillating so the feed stays alive, but the cars drive on and recede,
#      so a box delivered stale by the RG lag is genuinely wrong (gated:
#      predicted ZOH self-IoU over the lag <= 0.20 for BOTH cars, S8).
#   2. z-order variation: a seeded coin picks which car is the NEAR car
#      (smaller s = nearer to the trailing camera = the occluder). v2 had
#      blue nearer in 100% of frames of 12/12 clips (P5.12 audit).
#   3. crossing-peak diversity: stage timing is drawn against a randomized
#      pull-out END time t_end in U(4.2, 5.5) s (v2: t_in0 in U(0.7, 1.0)
#      with fixed-ish stages made every peak land f56-f94 with near-identical
#      geometry), plus wider camera bands (standoff 20-30, alt 3.5-7.0,
#      aim_err +-2.5). Gated at admission: >= peak_span_min frames between
#      earliest and latest admitted peak, exact 14/14 near-car mix (S9).
# Everything not named above copies v2 verbatim (lanes, speeds, sway, the
# two-stage lane change, corridor asserts).

V3_N_FRAMES = 300          # 12.0 s @ 25 Hz
V3_PROMPT_FRAME = 150      # t_p = 6.0 s, after every crossing completes
V3_HOLD_FRAME = 150        # camera anchor freeze = prompt frame
V3_LAG_FRAMES = 110        # RG delivery lag round(4.4 s * 25); P5.13 measured
                           # acquire_s 4.36-4.56 across 24 cells


def author_scenario_v3(seed, n_frames, fps=25.0):
    rng = np.random.default_rng(seed)
    h = ROAD_HEADING
    u = np.array([math.cos(h), math.sin(h)])
    n = np.array([-math.sin(h), math.cos(h)])
    t = np.arange(n_frames) / fps

    # white target: constant lane, small sway (v2 bands, verbatim)
    v_t = rng.uniform(2.2, 3.4)
    s0_t = rng.uniform(5.0, 12.0)
    lat_w0 = rng.uniform(-3.0, -2.4)
    amp_w = rng.uniform(0.10, 0.25)
    per_w, ph_w = rng.uniform(5.0, 9.0), rng.uniform(0, 2 * math.pi)
    lat_w = lat_w0 + amp_w * np.sin(2 * math.pi * t / per_w + ph_w)
    s_w = s0_t + v_t * t

    # z-order coin (mandate 2): near = smaller s (camera trails the convoy).
    # dv takes the SIGN of ds0 so |gap| can only GROW over the clip (v2's
    # dv < 0 with ds0 > 0 would shrink the gap below the contact floor).
    ds_mag = rng.uniform(5.9, 6.9)
    near_white = bool(rng.random() < 0.5)
    ds0 = ds_mag if near_white else -ds_mag
    dv = (1.0 if near_white else -1.0) * rng.uniform(0.0, 0.05)
    v_d = v_t + dv

    # blue lane change: same two-stage overtake-prep shape as v2, but timed
    # against a randomized END t_end (mandate 3). Worst-case end 5.5 s stays
    # >= 0.5 s clear of the prompt; t_in0 floor 0.3 s bounds the sum at 4.9 s.
    lat_b_a = rng.uniform(0.7, 1.3)        # start: right lane
    lat_b_b = rng.uniform(-4.8, -4.3)      # end: far-left lane
    t_end = rng.uniform(4.2, 5.5)          # pull-out completion (s)
    T_in = rng.uniform(0.9, 1.2)
    T_hold = rng.uniform(1.2, 1.8)
    T_out = rng.uniform(1.1, 1.6)
    t_in0 = max(0.3, t_end - T_in - T_hold - T_out)
    amp_b = rng.uniform(0.08, 0.20)
    per_b, ph_b = rng.uniform(5.0, 9.0), rng.uniform(0, 2 * math.pi)

    def sstep(t0, T):
        x = np.clip((t - t0) / T, 0.0, 1.0)
        return x * x * (3.0 - 2.0 * x)

    lat_hold = lat_w0
    lat_b = lat_b_a \
        + (lat_hold - lat_b_a) * sstep(t_in0, T_in) \
        + (lat_b_b - lat_hold) * sstep(t_in0 + T_in + T_hold, T_out) \
        + amp_b * np.sin(2 * math.pi * t / per_b + ph_b)
    s_b = s0_t + ds0 + v_d * t

    def track(s, lat, v):
        xy = GRID + np.outer(s, u) + np.outer(lat, n)
        dlat = np.gradient(lat, 1.0 / fps)
        yaw = h + np.arctan2(dlat, v)
        return xy, yaw

    tgt_xy, tgt_yaw = track(s_w, lat_w, v_t)
    dis_xy, dis_yaw = track(s_b, lat_b, v_d)

    for xy in (tgt_xy, dis_xy):
        lat_v, s_v = xy @ n, xy @ u
        assert lat_v.min() >= LAT_SAFE[0] and lat_v.max() <= LAT_SAFE[1], \
            f"v3 seed {seed}: lat [{lat_v.min():.2f},{lat_v.max():.2f}] outside {LAT_SAFE}"
        assert s_v.max() <= S_SAFE_MAX, \
            f"v3 seed {seed}: s_max {s_v.max():.1f} beyond {S_SAFE_MAX}"
    gap = s_b - s_w
    assert np.abs(gap).min() >= V2_MIN_GAP_S, \
        f"v3 seed {seed}: min |ds| {np.abs(gap).min():.2f} < {V2_MIN_GAP_S} (contact risk)"
    assert (np.sign(gap) == np.sign(gap[0])).all() and gap[0] != 0, \
        f"v3 seed {seed}: z-order flips mid-clip"

    # camera: v2's low grazing view, wider bands (mandate 3), and the
    # post-prompt anchor freeze (mandate 1): tracking index j clamps at
    # V3_HOLD_FRAME while bob/sway keep running on the true clock t[i].
    mid = (tgt_xy + dis_xy) / 2
    standoff = rng.uniform(20, 30)
    alt = rng.uniform(3.5, 7.0)
    bob_a, bob_p = rng.uniform(0.2, 0.6), rng.uniform(5.0, 11.0)
    sway_a, sway_p = rng.uniform(0.5, 1.5), rng.uniform(6.0, 13.0)
    aim_err = rng.uniform(-2.5, 2.5, size=2)
    cam_pos = np.zeros((n_frames, 3))
    cam_quat = np.zeros((n_frames, 4))
    for i in range(n_frames):
        j = min(i, V3_HOLD_FRAME)
        p = np.array([*(mid[j] - u * standoff
                        + n * (sway_a * math.sin(2 * math.pi * t[i] / sway_p))),
                      alt + bob_a * math.sin(2 * math.pi * t[i] / bob_p)])
        q, _, _ = look_at(p, [mid[j][0] + aim_err[0], mid[j][1] + aim_err[1], 0.0])
        cam_pos[i] = p
        cam_quat[i] = q
    return {
        "seed": seed, "n_frames": n_frames, "fps": fps, "profile": "v3",
        "target": {"name": "car_white", "color": "white", "xy": tgt_xy,
                   "yaw": tgt_yaw, "v": v_t},
        "distractor": {"name": "car_blue", "color": "blue", "xy": dis_xy,
                       "yaw": dis_yaw, "v": v_d},
        "cam_pos": cam_pos, "cam_quat": cam_quat,
        "params": {"standoff": standoff, "alt": alt, "aim_err": aim_err.tolist(),
                   "v_target": v_t, "v_distractor": v_d, "ds0": ds0,
                   "near": "white" if near_white else "blue",
                   "lat_b_a": lat_b_a, "lat_b_b": lat_b_b,
                   "t_in0": t_in0, "T_in": T_in,
                   "T_hold": T_hold, "T_out": T_out, "t_end": t_end},
    }


def _iou2d(a, b):
    if a is None or b is None:
        return 0.0
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    ar = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ar


def _overlap_frac(own, other):
    """Fraction of OWN box area covered by the other box (0 if either None)."""
    if own is None or other is None:
        return 0.0
    x1, y1 = max(own[0], other[0]), max(own[1], other[1])
    x2, y2 = min(own[2], other[2]), min(own[3], other[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return ((x2 - x1) * (y2 - y1)) / ((own[2] - own[0]) * (own[3] - own[1]))


def scenario_boxes(sc):
    """Predicted per-frame projected GT boxes for both cars. Pure numpy."""
    out = {"target": [], "distractor": []}
    for i in range(sc["n_frames"]):
        for role in ("target", "distractor"):
            c = sc[role]
            b, _ = project_box(sc["cam_pos"][i], sc["cam_quat"][i],
                               [float(c["xy"][i][0]), float(c["xy"][i][1]), CAR_Z],
                               float(c["yaw"][i]))
            out[role].append(b)
    return out


def predicted_gtgt_iou(sc, boxes=None):
    """Per-frame predicted GT-GT image IoU trace (the crossing signal)."""
    boxes = boxes or scenario_boxes(sc)
    return np.array([_iou2d(a, b) for a, b in
                     zip(boxes["target"], boxes["distractor"])])


# Pre-registered v2 crossing screen (P5.11): five design-time facts, all pure
# projection -- no gz, no render. Thresholds fixed from a 60-seed offline sweep
# (52/60 pass; see the P5.11 README) BEFORE any bank clip was recorded.
V2_SCREEN = {
    "peak_iou_min": 0.20,     # S1: the crossing really overlaps
    "run_iou15_min": 25,      # S2: >= 1.0 s consecutive frames IoU >= 0.15
    "run_occl50_min": 25,     # S3: >= 1.0 s with white >= 50% covered by blue
    "peak_before_f": V2_PROMPT_FRAME - 25,   # S4: peak >= 1 s pre-prompt
    "tail_iou_max": 0.15,     # S5: post-prompt GT-GT IoU stays unambiguous
}


def _max_run(trace, thr):
    c = best = 0
    for v in trace:
        c = c + 1 if v >= thr else 0
        best = max(best, c)
    return best


def v2_crossing_screen(sc):
    """Offline screen for one authored v2 scenario. Returns metrics + pass."""
    boxes = scenario_boxes(sc)
    iou = predicted_gtgt_iou(sc, boxes)
    occl_w = np.array([_overlap_frac(w, b) for w, b in
                       zip(boxes["target"], boxes["distractor"])])
    P = V2_PROMPT_FRAME
    m = {
        "peak_iou": round(float(iou.max()), 4),
        "peak_f": int(iou.argmax()),
        "run_iou15": _max_run(iou, 0.15),
        "peak_occl_white": round(float(occl_w.max()), 4),
        "run_occl50": _max_run(occl_w, 0.50),
        "tail_iou_max": round(float(iou[P:].max()), 4) if len(iou) > P else 0.0,
    }
    m["pass"] = bool(
        m["peak_iou"] >= V2_SCREEN["peak_iou_min"]
        and m["run_iou15"] >= V2_SCREEN["run_iou15_min"]
        and m["run_occl50"] >= V2_SCREEN["run_occl50_min"]
        and m["peak_f"] <= V2_SCREEN["peak_before_f"]
        and m["tail_iou_max"] <= V2_SCREEN["tail_iou_max"])
    return m


def screen_cmd(args):
    """Design-time preflight: sweep seeds through the offline crossing screen,
    print the per-seed table and the first --need passing seeds (the bank)."""
    passing = []
    print(f"{'seed':<6}{'pass':<6}{'peakIoU':<9}{'peak_f':<8}{'run15':<7}"
          f"{'occlPk':<8}{'run50':<7}{'tailIoU':<8}")
    for seed in range(args.lo, args.hi + 1):
        sc = author_scenario(seed, V2_N_FRAMES, profile="v2")
        m = v2_crossing_screen(sc)
        if m["pass"]:
            passing.append(seed)
        print(f"{seed:<6}{('PASS' if m['pass'] else 'fail'):<6}"
              f"{m['peak_iou']:<9.3f}{m['peak_f']:<8}{m['run_iou15']:<7}"
              f"{m['peak_occl_white']:<8.3f}{m['run_occl50']:<7}"
              f"{m['tail_iou_max']:<8.3f}")
    print(f"\npassing: {len(passing)}/{args.hi - args.lo + 1}")
    bank = passing[:args.need]
    print(f"bank (first {args.need}): {bank}")
    if len(bank) < args.need:
        print("SCREEN FAIL: not enough passing seeds")
        return 1
    return 0


# ------------------------------------------- v2.1 seed screen (P5.12 recal)
# P5.11 finding (NO [G4b; bank 3/12]): the S1-S5 screen admits seeds whose
# recorded clips then fail build gates for reasons that are fully PREDICTABLE
# offline -- record() realizes author_scenario byte-exactly (G4a mean|diff|
# 0.0), so predicted clear-frame counts matched recorded G6c n_clear 12/12
# EXACTLY on the P5.11 bank -- and the first-N-passing admission rule has no
# pairwise-diversity constraint, so near-duplicate seeds 9/14 slipped in and
# failed G4b at 0.77 m < 1.0. v2.1 adds two ADMISSION constraints (the
# generator profile itself is untouched; renders were defect-free 12/12):
#   S6 predicted CLEAR-frame floor: white occl <= 0.05 with box visible on
#      >= 45 frames (recalibrated gate G6c needs n_clear >= 40; 5-frame belt
#      over an exact prediction).
#   S7 pairwise diversity: greedy admission in ascending seed order; admit
#      iff whole-scenario divergence >= 1.1 m vs EVERY gate seed AND every
#      already-admitted seed (G4b floor is 1.0 m; 0.1 m margin -- the screen
#      uses the same author_scenario + same formula, so the guarantee is
#      exact, the margin is belt-and-braces).

V2_1_SCREEN = {"clear_min": 45, "div_min": 1.1, "lo": 1, "hi": 56,
               "gate_seeds": (101, 202, 303)}
# Pinned admission result of v2_1_bank() over the defaults above (computed
# offline 2026-07-17, pre-registered in the P5.12 README; selfcheck 6g pins it):
V2_1_BANK_PINNED = [1, 2, 3, 4, 6, 14, 17, 28, 29, 33, 40, 56]


def predicted_occl_white(sc, boxes=None):
    """Predicted per-frame occluded fraction of the white target (white is
    farther than blue on every v2 frame by construction, so blue is always
    the occluder -- same convention record() writes into gt.jsonl)."""
    boxes = boxes or scenario_boxes(sc)
    return np.array([_overlap_frac(w, b) for w, b in
                     zip(boxes["target"], boxes["distractor"])])


def predicted_clear_count(sc, boxes=None):
    """Predicted CLEAR-frame count for white (occl <= 0.05, box visible).
    Equals the recorded G6c white pool exactly under byte-determinism --
    verified 12/12 (pred==recorded) on the P5.11 bank before pre-registration."""
    boxes = boxes or scenario_boxes(sc)
    occ = predicted_occl_white(sc, boxes)
    vis = np.array([b is not None for b in boxes["target"]])
    return int(((occ <= 0.05) & vis).sum())


def scenario_divergence(A, B):
    """Whole-scenario divergence (m) between two authored scenarios: the G4b
    statistic (mean of target/distractor/camera mean point distances). Must
    stay formula-identical to verdict_p511/verdict_p512 g4b()."""
    dt = np.linalg.norm(A["target"]["xy"] - B["target"]["xy"], axis=1).mean()
    dd = np.linalg.norm(A["distractor"]["xy"] - B["distractor"]["xy"], axis=1).mean()
    dc = np.linalg.norm(A["cam_pos"] - B["cam_pos"], axis=1).mean()
    return float((dt + dd + dc) / 3)


def v2_1_bank(lo=None, hi=None, need=12):
    """v2.1 offline seed screen: S1-S5 (v2_crossing_screen, unchanged) + S6
    clear floor + S7 greedy pairwise diversity vs gate seeds + admitted set.
    Deterministic; returns (admitted, rows). No gz, no GPU."""
    cfg = V2_1_SCREEN
    lo = cfg["lo"] if lo is None else lo
    hi = cfg["hi"] if hi is None else hi
    gate_scs = [author_scenario(s, V2_N_FRAMES, profile="v2")
                for s in cfg["gate_seeds"]]
    admitted, adm_scs, rows = [], [], []
    for seed in range(lo, hi + 1):
        sc = author_scenario(seed, V2_N_FRAMES, profile="v2")
        boxes = scenario_boxes(sc)
        m = v2_crossing_screen(sc)
        clear = predicted_clear_count(sc, boxes)
        s6 = clear >= cfg["clear_min"]
        s7 = None
        if m["pass"] and s6 and len(admitted) < need:
            dmin = min([scenario_divergence(sc, g) for g in gate_scs]
                       + [scenario_divergence(sc, a) for a in adm_scs])
            s7 = dmin >= cfg["div_min"]
            if s7:
                admitted.append(seed)
                adm_scs.append(sc)
        rows.append({"seed": seed, "s15_pass": m["pass"], "clear": clear,
                     "s6": s6, "s7": s7, "admitted": seed in admitted, **m})
    return admitted, rows


def screen21_cmd(args):
    """Design-time preflight for the P5.12 bank: v2.1 screen table + bank."""
    admitted, rows = v2_1_bank(args.lo, args.hi, args.need)
    print(f"{'seed':<6}{'S1-5':<6}{'clear':<7}{'S6':<5}{'S7':<6}{'in':<4}"
          f"{'peakIoU':<9}{'run50':<7}{'tailIoU':<8}")
    for r in rows:
        print(f"{r['seed']:<6}{('PASS' if r['s15_pass'] else 'fail'):<6}"
              f"{r['clear']:<7}{('ok' if r['s6'] else 'LOW'):<5}"
              f"{('-' if r['s7'] is None else 'ok' if r['s7'] else 'DUP'):<6}"
              f"{('IN' if r['admitted'] else ''):<4}"
              f"{r['peak_iou']:<9.3f}{r['run_occl50']:<7}{r['tail_iou_max']:<8.3f}")
    print(f"\nadmitted bank ({len(admitted)}/{args.need}): {admitted}")
    if len(admitted) < args.need:
        print("SCREEN21 FAIL: not enough admissible seeds -- widen --hi")
        return 1
    return 0


# ------------------------------------------- v3 seed screen (P5.17)
# Per-seed rules S1-S5 keep the v2 thresholds but generalize "the occluded
# car" to the FAR car (z-order varies by design); S6 is the far-car clear
# floor; S8 is NEW (the lag-stress mandate): both cars' predicted ZOH
# self-IoU over the RG lag window must be <= stale_iou_max (a stale delivered
# box is genuinely wrong), and both cars must stay scoreable (area >=
# area_min) on every post-prompt frame. Admission adds S7 pairwise diversity
# (>= div_min vs every already-admitted seed, greedy ascending) and S9 set
# rules: exact need_per_class near-white/near-blue mix + crossing-peak span
# >= peak_span_min frames. All pure projection -- no gz, no GPU.

V3_SCREEN = {
    "peak_iou_min": 0.20, "run_iou15_min": 25, "run_occl50_min": 25,
    "peak_before_f": V3_PROMPT_FRAME - 25, "tail_iou_max": 0.15,
    "clear_min": 45, "stale_iou_max": 0.20, "area_min": 150.0,
    "div_min": 1.1, "need_per_class": 14, "lo": 1, "hi": 300,
    "peak_span_min": 30,
}
# Pinned admission result of v3_bank() over the defaults above (computed
# offline 2026-07-20, pre-registered in the P5.17 README; selfcheck 6h pins
# it): 28 seeds, exact 14/14 near-white/near-blue mix, peak_f span 62.
V3_BANK_PINNED = [2, 3, 6, 7, 8, 13, 17, 18, 21, 28, 32, 42, 48, 57, 68, 69,
                  70, 74, 89, 91, 92, 98, 101, 103, 104, 112, 116, 122]


def v3_roles(sc):
    """(near_role, far_role) of an authored v3 scenario: the near car (smaller
    s, closer to the trailing camera) is the occluder; the far car is the
    occluded one. Matches record()'s per-frame 'nearer' provenance."""
    if sc["params"]["near"] == "white":
        return "target", "distractor"
    return "distractor", "target"


def predicted_occl_far(sc, boxes=None):
    """Predicted per-frame occluded fraction of the FAR car (v3 analogue of
    predicted_occl_white; the occluded role varies with the z-order coin)."""
    boxes = boxes or scenario_boxes(sc)
    near, far = v3_roles(sc)
    return np.array([_overlap_frac(fb, nb) for fb, nb in
                     zip(boxes[far], boxes[near])])


def v3_crossing_screen(sc):
    """Offline per-seed screen for one authored v3 scenario (S1-S6 + S8)."""
    cfg = V3_SCREEN
    boxes = scenario_boxes(sc)
    iou = predicted_gtgt_iou(sc, boxes)
    occ = predicted_occl_far(sc, boxes)
    near, far = v3_roles(sc)
    P, L = V3_PROMPT_FRAME, V3_LAG_FRAMES
    vis_far = np.array([b is not None for b in boxes[far]])
    clear_far = int(((occ <= 0.05) & vis_far).sum())

    def _area(b):
        return 0.0 if b is None else (b[2] - b[0]) * (b[3] - b[1])

    stale = {}
    scoreable = True
    for role in ("target", "distractor"):
        b0, b1 = boxes[role][P], boxes[role][P + L]
        stale[role] = round(_iou2d(b0, b1), 4)
        scoreable &= all(_area(boxes[role][f]) >= cfg["area_min"]
                         for f in range(P, sc["n_frames"]))
    m = {
        "near": sc["params"]["near"],
        "peak_iou": round(float(iou.max()), 4),
        "peak_f": int(iou.argmax()),
        "run_iou15": _max_run(iou, 0.15),
        "peak_occl_far": round(float(occ.max()), 4),
        "run_occl50": _max_run(occ, 0.50),
        "tail_iou_max": round(float(iou[P:].max()), 4),
        "clear_far": clear_far,
        "stale_t": stale["target"], "stale_d": stale["distractor"],
        "scoreable": scoreable,
    }
    m["pass"] = bool(
        m["peak_iou"] >= cfg["peak_iou_min"]
        and m["run_iou15"] >= cfg["run_iou15_min"]
        and m["run_occl50"] >= cfg["run_occl50_min"]
        and m["peak_f"] <= cfg["peak_before_f"]
        and m["tail_iou_max"] <= cfg["tail_iou_max"]
        and m["clear_far"] >= cfg["clear_min"]
        and m["stale_t"] <= cfg["stale_iou_max"]
        and m["stale_d"] <= cfg["stale_iou_max"]
        and m["scoreable"])
    return m


def v3_bank(lo=None, hi=None, need_per_class=None):
    """v3 offline seed screen + greedy class-balanced admission. Ascending
    seed order; a passing seed is admitted iff its near-car class quota is
    open AND min divergence vs every admitted seed >= div_min. Stops when
    both quotas fill. Returns (admitted, rows). Deterministic, no gz."""
    cfg = V3_SCREEN
    lo = cfg["lo"] if lo is None else lo
    hi = cfg["hi"] if hi is None else hi
    need = cfg["need_per_class"] if need_per_class is None else need_per_class
    admitted, adm_scs, rows = [], [], []
    quota = {"white": need, "blue": need}
    for seed in range(lo, hi + 1):
        sc = author_scenario(seed, V3_N_FRAMES, profile="v3")
        m = v3_crossing_screen(sc)
        s7 = None
        if m["pass"] and quota[m["near"]] > 0:
            dmin = min([scenario_divergence(sc, a) for a in adm_scs],
                       default=float("inf"))
            s7 = dmin >= cfg["div_min"]
            if s7:
                admitted.append(seed)
                adm_scs.append(sc)
                quota[m["near"]] -= 1
        rows.append({"seed": seed, "s7": s7, "admitted": seed in admitted, **m})
        if quota["white"] == 0 and quota["blue"] == 0:
            break
    return admitted, rows


def v3_bank_peak_span(rows):
    """S9b: span (max-min) of admitted crossing-peak frames."""
    pk = [r["peak_f"] for r in rows if r["admitted"]]
    return (max(pk) - min(pk)) if pk else 0


def screen3_cmd(args):
    """Design-time preflight for the P5.17 bank: v3 screen table + admission."""
    admitted, rows = v3_bank(args.lo, args.hi, args.need_per_class)
    print(f"{'seed':<6}{'near':<7}{'S1-6':<6}{'S8st':<6}{'S7':<5}{'in':<4}"
          f"{'peakIoU':<9}{'peak_f':<8}{'run50':<7}{'clear':<7}"
          f"{'staleT':<8}{'staleD':<8}{'tail':<7}")
    for r in rows:
        s8 = "ok" if (r["stale_t"] <= V3_SCREEN["stale_iou_max"]
                      and r["stale_d"] <= V3_SCREEN["stale_iou_max"]
                      and r["scoreable"]) else "BAD"
        print(f"{r['seed']:<6}{r['near']:<7}"
              f"{('PASS' if r['pass'] else 'fail'):<6}{s8:<6}"
              f"{('-' if r['s7'] is None else 'ok' if r['s7'] else 'DUP'):<5}"
              f"{('IN' if r['admitted'] else ''):<4}"
              f"{r['peak_iou']:<9.3f}{r['peak_f']:<8}{r['run_occl50']:<7}"
              f"{r['clear_far']:<7}{r['stale_t']:<8.3f}{r['stale_d']:<8.3f}"
              f"{r['tail_iou_max']:<7.3f}")
    span = v3_bank_peak_span(rows)
    nw = sum(1 for r in rows if r["admitted"] and r["near"] == "white")
    nb = sum(1 for r in rows if r["admitted"] and r["near"] == "blue")
    print(f"\nadmitted bank ({len(admitted)}): {admitted}")
    print(f"near-white {nw}, near-blue {nb}, peak_f span {span} "
          f"(S9 needs {V3_SCREEN['need_per_class']}/{V3_SCREEN['need_per_class']}"
          f" and span >= {V3_SCREEN['peak_span_min']})")
    want = 2 * (args.need_per_class or V3_SCREEN["need_per_class"])
    if len(admitted) < want or span < V3_SCREEN["peak_span_min"]:
        print("SCREEN3 FAIL: not enough admissible seeds or peak span too "
              "narrow -- widen --hi or revisit bands")
        return 1
    return 0


# ---------------------------------------------------------------- validity metrics

def color_mask(bgr, color):
    b = bgr[:, :, 0].astype(int)
    g = bgr[:, :, 1].astype(int)
    r = bgr[:, :, 2].astype(int)
    if color == "blue":
        return (b - np.maximum(r, g)) > 20
    if color == "white":
        mx = np.maximum(np.maximum(b, g), r)
        mn = np.minimum(np.minimum(b, g), r)
        return (mn > 165) & ((mx - mn) < 45)
    if color == "red":
        return (r - np.maximum(b, g)) > 20
    raise ValueError(color)


def box_purity(bgr, bbox, color, shrink=0.12):
    x1, y1, x2, y2 = bbox
    dx, dy = (x2 - x1) * shrink, (y2 - y1) * shrink
    x1, y1, x2, y2 = int(x1 + dx), int(y1 + dy), int(x2 - dx), int(y2 - dy)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return 0.0
    m = color_mask(bgr[y1:y2, x1:x2], color)
    return float(m.mean())


FRAG_MIN_NPX = 30  # below this many car-colour pixels the split stat is noise


def frag_metric(bgr, bbox, color, pad=0.10):
    """Rendered-integrity stat (P5.9 gate G6): largest-connected-component
    fraction of car-colour pixels in the padded GT box. A healthy render is one
    blob (~1.0); kerb-clipping splits the body (P5.8 seed 101 blue car:
    min 0.504, p10 0.666 vs >= 0.992 on clean runs). Returns (frac|None, npx);
    None = too few pixels to score."""
    x1, y1, x2, y2 = bbox
    dx, dy = (x2 - x1) * pad, (y2 - y1) * pad
    x1, y1 = max(0, int(x1 - dx)), max(0, int(y1 - dy))
    x2, y2 = min(bgr.shape[1], int(x2 + dx)), min(bgr.shape[0], int(y2 + dy))
    m = color_mask(bgr[y1:y2, x1:x2], color).astype(np.uint8)
    npx = int(m.sum())
    if npx < FRAG_MIN_NPX:
        return None, npx
    n_lab, _lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    return float(stats[1:, 4].max() / npx), npx


def control_purity(bgr, bbox, color):
    """Same-size boxes offset +-1.6 widths laterally; mean purity (background level)."""
    x1, y1, x2, y2 = bbox
    w = x2 - x1
    vals = []
    for off in (-1.6 * w, 1.6 * w):
        a, b = x1 + off, x2 + off
        if a < 0 or b > W:
            continue
        vals.append(box_purity(bgr, [a, y1, b, y2], color, shrink=0.0))
    return float(np.mean(vals)) if vals else 0.0


# ---------------------------------------------------------------- record

def record(args):
    out = Path(args.out)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    sc = author_scenario(args.seed, args.frames, profile=args.profile)
    pred_boxes, xpeak_f, xpeak_iou = None, None, None
    if args.profile in ("v2", "v3"):
        # designed-occlusion provenance: the crossing peak is a design-time
        # fact (pure projection), so the LOOK-AT-IT overlay lands exactly on it
        pred_boxes = scenario_boxes(sc)
        pred_iou = predicted_gtgt_iou(sc, pred_boxes)
        xpeak_f = int(np.argmax(pred_iou))
        xpeak_iou = float(pred_iou[xpeak_f])
    gz = GzClient()
    time.sleep(0.7)

    # spawn cars at their f0 poses (queued while paused; applied on first step)
    for role in ("target", "distractor"):
        c = sc[role]
        gz.spawn_car(c["name"], CAR_COLORS[c["color"]][0])
    # warmup: first renders after spawn are routinely black/stale -- step a few
    # batches with f0 poses commanded, keep nothing.
    frame0_poses = frame_poses(sc, 0)
    gz.set_poses(frame0_poses)
    warm = None
    for _ in range(5):
        warm, _ = gz.step_one_frame()
    if warm is None or warm.std() <= 5:
        raise RuntimeError(f"warmup frame dead (std={None if warm is None else warm.std():.2f}) "
                           "-- black render: check EGL ICD env on the gz server")

    gt_path = out / "gt.jsonl"
    overlay_at = set(overlay_frames(args.frames))
    if xpeak_f is not None:
        overlay_at.add(xpeak_f)
    t_loop0 = time.time()
    prev = None
    stamps = []
    identical_consec = 0
    dead_frames = 0
    records = []
    gtf = open(gt_path, "w")  # incremental: a mid-run death still leaves GT on disk
    for i in range(args.frames):
        gz.set_poses(frame_poses(sc, i))
        arr, stamp = gz.step_one_frame()
        bgr = arr[:, :, ::-1]
        if arr.std() <= 5:
            dead_frames += 1
        if prev is not None and np.array_equal(arr, prev):
            identical_consec += 1
        prev = arr
        stamps.append(stamp)
        objs = []
        for tid, role in ((0, "target"), (1, "distractor")):
            c = sc[role]
            pos = [float(c["xy"][i][0]), float(c["xy"][i][1]), CAR_Z]
            yaw = float(c["yaw"][i])
            bbox, area = project_box(sc["cam_pos"][i], sc["cam_quat"][i], pos, yaw)
            rec = {"id": tid, "name": c["name"], "color": c["color"],
                   "phrase": CAR_COLORS[c["color"]][1],
                   "pos": [round(v, 4) for v in pos], "yaw": round(yaw, 4),
                   "bbox": bbox, "area": area, "visible": bbox is not None}
            if bbox is not None:
                rec["purity"] = round(box_purity(bgr, bbox, c["color"]), 4)
                rec["bg_purity"] = round(control_purity(bgr, bbox, c["color"]), 4)
                fr, _npx = frag_metric(bgr, bbox, c["color"])
                if fr is not None:
                    rec["frag"] = round(fr, 4)
                if args.profile in ("v2", "v3"):
                    rec["npx"] = _npx  # visible own-colour pixel count (gate G8)
            objs.append(rec)
        if args.profile in ("v2", "v3"):
            # occlusion provenance: 'nearer' = closer to the camera than the
            # other car; 'occl' = fraction of OWN GT box covered by the other
            # car's GT box IF the other car is nearer (else 0). This is what
            # lets the gates tell a DESIGNED occlusion from a render defect.
            cam = sc["cam_pos"][i]
            dcam = [float(np.linalg.norm(np.asarray(o["pos"]) - cam))
                    for o in objs]
            for a, b in ((0, 1), (1, 0)):
                objs[a]["nearer"] = bool(dcam[a] < dcam[b])
                objs[a]["occl"] = round(
                    _overlap_frac(objs[a]["bbox"], objs[b]["bbox"])
                    if dcam[b] < dcam[a] else 0.0, 4)
        frec = {
            "f": i, "t_sim_ns": stamp,
            "cam": {"pos": [round(float(v), 4) for v in sc["cam_pos"][i]],
                    "quat": [round(float(v), 6) for v in sc["cam_quat"][i]]},
            "objs": objs}
        records.append(frec)
        gtf.write(json.dumps(frec) + "\n")
        gtf.flush()
        cv2.imwrite(str(out / "frames" / f"{i:04d}.png"), bgr)
        if i in overlay_at:  # incremental: the visual gate stays computable mid-run
            cv2.imwrite(str(out / f"overlay_f{i:04d}.png"), draw_overlay(bgr, frec))
        if i % 40 == 0 or i == args.frames - 1:
            print(f"[scenegen] frame {i}/{args.frames} "
                  f"({(i + 1) / (time.time() - t_loop0):.2f} fps)", flush=True)
            with open(out / "progress.json", "w") as pf:
                json.dump({"frames_done": i + 1, "of": args.frames,
                           "fps_wall": round((i + 1) / (time.time() - t_loop0), 3),
                           "retries_pose": gz.retries_pose,
                           "retries_step": gz.retries_step,
                           "response_lost": gz.response_lost,
                           "proxy_restarts": gz.proxy.restarts}, pf)
    loop_s = time.time() - t_loop0
    gtf.close()

    # ---- per-run gate metrics
    fps_wall = args.frames / loop_s
    dstamps = np.diff(stamps)
    step_ns = CAM_PERIOD_STEPS * 1_000_000
    vis = {0: [], 1: []}
    pur = {0: [], 1: []}
    bgp = {0: [], 1: []}
    frg = {0: [], 1: []}
    both_vis = 0
    for r in records:
        ok_both = True
        for o in r["objs"]:
            v = o["visible"] and o["area"] >= 150
            vis[o["id"]].append(v)
            if v:
                pur[o["id"]].append(o["purity"])
                bgp[o["id"]].append(o["bg_purity"])
                if "frag" in o:
                    frg[o["id"]].append(o["frag"])
            ok_both &= v
        both_vis += ok_both
    v2_extra = {}
    if args.profile in ("v2", "v3"):
        # clear-frame partition (occl <= 0.05): the frames where v1-grade
        # integrity thresholds still apply. Occluded-frame fragmentation of the
        # farther car is DESIGNED, not a defect; verdict_p511 is the authority,
        # these aggregates are the at-a-glance copy. NOTE: for v2 the plain
        # g2_*/g6_* fields above/below mix designed-occlusion frames in and
        # are non-gating.
        frg_clear = {0: [], 1: []}
        pur_clear = {0: [], 1: []}
        for r in records:
            for o in r["objs"]:
                if o["bbox"] is not None and o.get("occl", 0.0) <= 0.05:
                    if "frag" in o:
                        frg_clear[o["id"]].append(o["frag"])
                    if "purity" in o:
                        pur_clear[o["id"]].append(o["purity"])
        screen_fn = v2_crossing_screen if args.profile == "v2" else v3_crossing_screen
        v2_extra = {
            "profile": args.profile,
            f"{args.profile}_screen": screen_fn(sc),
            f"{args.profile}_xpeak_pred_f": xpeak_f,
            f"{args.profile}_xpeak_pred_iou": round(xpeak_iou, 4),
            "g2_purity_median_clear": {
                str(k): round(float(np.median(v)), 4) if v else None
                for k, v in pur_clear.items()},
            "g6_frag_p10_clear": {
                str(k): round(float(np.percentile(v, 10)), 4) if v else None
                for k, v in frg_clear.items()},
            "g6_frag_below090_frac_clear": {
                str(k): round(float(np.mean(np.array(v) < 0.90)), 4) if v else None
                for k, v in frg_clear.items()},
            "g6_n_clear": {str(k): len(v) for k, v in frg_clear.items()},
        }
    results = {
        "seed": args.seed, "frames": args.frames, "out": str(out),
        **v2_extra,
        "wall_loop_s": round(loop_s, 1), "fps_wall": round(fps_wall, 3),
        "g1_dead_frames": dead_frames,
        "g1_identical_consecutive": identical_consec,
        "g1_stamp_steps_ok": bool((dstamps == step_ns).all()),
        "g2_purity_median": {str(k): round(float(np.median(v)), 4) if v else None
                             for k, v in pur.items()},
        "g2_bg_purity_median": {str(k): round(float(np.median(v)), 4) if v else None
                                for k, v in bgp.items()},
        "g3_both_visible_frac": round(both_vis / args.frames, 4),
        "g6_frag_p10": {str(k): round(float(np.percentile(v, 10)), 4) if v else None
                        for k, v in frg.items()},
        "g6_frag_min": {str(k): round(float(np.min(v)), 4) if v else None
                        for k, v in frg.items()},
        "g6_frag_below090_frac": {str(k): round(float(np.mean(np.array(v) < 0.90)), 4)
                                  if v else None for k, v in frg.items()},
        "g6_frag_n": {str(k): len(v) for k, v in frg.items()},
        "g0_retries_pose": gz.retries_pose,
        "g0_retries_step": gz.retries_step,
        "g0_response_lost": gz.response_lost,
        "g0_proxy_restarts": gz.proxy.restarts,
        "g0_spawn_warns": gz.spawn_warns,
        "params": sc["params"],
        "versions": {"gz": gz_version(), "python": sys.version.split()[0],
                     "numpy": np.__version__, "cv2": cv2.__version__},
        "cmd": " ".join(sys.argv),
    }
    with open(out / "results.json", "w") as f:
        json.dump(results, f, indent=2)

    write_videos(out, records, args.frames)
    gz.proxy.close()
    print(json.dumps(results, indent=2))
    print(f"[scenegen] DONE {out}")


def frame_poses(sc, i):
    poses = [("uav_cam", sc["cam_pos"][i], tuple(sc["cam_quat"][i]))]
    for role in ("target", "distractor"):
        c = sc[role]
        q = quat_yaw_pitch(float(c["yaw"][i]), 0.0)
        poses.append((c["name"], (float(c["xy"][i][0]), float(c["xy"][i][1]), CAR_Z), q))
    return poses


def overlay_frames(n):
    return [n // 4, n // 2, (3 * n) // 4]


BOX_BGR = {"white": (60, 220, 60), "blue": (60, 220, 60), "red": (60, 220, 60)}


def draw_overlay(bgr, rec):
    img = bgr.copy()
    for o in rec["objs"]:
        if o["bbox"] is None:
            continue
        x1, y1, x2, y2 = [int(v) for v in o["bbox"]]
        cv2.rectangle(img, (x1, y1), (x2, y2), BOX_BGR[o["color"]], 2)
        cv2.putText(img, f'id{o["id"]} {o["color"]}', (x1, max(14, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 230, 230), 2)
    cv2.putText(img, f'f={rec["f"]}', (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (255, 255, 255), 2)
    return img


def write_videos(out, records, n):
    vw = cv2.VideoWriter(str(out / "clip.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 25, (W, H))
    vo = cv2.VideoWriter(str(out / "overlay.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 25, (W, H))
    for i in range(n):
        bgr = cv2.imread(str(out / "frames" / f"{i:04d}.png"))
        vw.write(bgr)
        vo.write(draw_overlay(bgr, records[i]))
    vw.release()
    vo.release()


def gz_version():
    try:
        return subprocess.run(["gz", "sim", "--versions"], capture_output=True,
                              text=True, timeout=10).stdout.strip().splitlines()[0]
    except Exception:
        return "unknown"


# ---------------------------------------------------------------- killserver


def killserver():
    """Kill every gz-sim server running select_arena, by PROCESS GROUP.

    Replaces the P5.7 README teardown, which had two recorded defects:
    `kill $(cat pidfile)` killed only the nohup bash wrapper (`$!`) and orphaned
    the live ruby server -- silently faking the "fresh server session" that the
    G4a cross-session claim rests on -- and `pkill -f "gz sim"` self-matches the
    launching shell's own command line under this harness. This scans /proc for
    cmdlines containing the world file, excludes itself + its ancestors + its
    own process group, SIGTERMs the victims' process groups, escalates to
    SIGKILL, and verifies. Exit 0 iff nothing matching survives.
    """
    import os
    import signal

    needle = "select_arena.sdf"
    me = os.getpid()
    anc = set()
    p = me
    while p > 1:
        anc.add(p)
        try:
            stat = Path(f"/proc/{p}/stat").read_text()
            p = int(stat.rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break

    def victims():
        out = {}
        for d in Path("/proc").iterdir():
            if not d.name.isdigit():
                continue
            pid = int(d.name)
            if pid == me or pid in anc:
                continue
            try:
                cmd = (d / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            except OSError:
                continue
            if needle in cmd:
                try:
                    pgid = os.getpgid(pid)
                except OSError:
                    continue
                if pgid == os.getpgid(0):
                    continue  # never kill our own process group
                out.setdefault(pgid, []).append((pid, cmd.strip()[:120]))
        return out

    v = victims()
    for pgid, procs in v.items():
        print(f"[killserver] SIGTERM pgid {pgid}: {procs}")
        try:
            os.killpg(pgid, signal.SIGTERM)
        except OSError:
            pass
    if v:
        time.sleep(2.0)
        for pgid in victims():
            print(f"[killserver] SIGKILL pgid {pgid}")
            try:
                os.killpg(pgid, signal.SIGKILL)
            except OSError:
                pass
        time.sleep(0.5)
    left = victims()
    print(f"[killserver] remaining: {len(left)}")
    sys.exit(0 if not left else 1)


# ---------------------------------------------------------------- selfcheck (no gz)

def selfcheck():
    # 1. mesh AABB constants match the committed asset
    vs = []
    with open(MESH) as f:
        for line in f:
            if line.startswith("v "):
                vs.append([float(x) for x in line.split()[1:4]])
    v = np.array(vs) * 0.0254
    lo, hi = v.min(0), v.max(0)
    got = {"x": (-hi[1], -lo[1]), "y": (lo[0], hi[0]), "z": (lo[2], hi[2])}  # yaw+90
    for ax in "xyz":
        assert abs(got[ax][0] - CAR_AABB[ax][0]) < 0.01 and \
            abs(got[ax][1] - CAR_AABB[ax][1]) < 0.01, (ax, got[ax], CAR_AABB[ax])

    # 2. projection sanity: nadir camera 20 m above a car at origin -> box centred,
    #    car length axis along image vertical when car yaw points +x ... just check
    #    centre + plausible scale + known direction of a +y_world nudge.
    q = quat_yaw_pitch(0.0, math.pi / 2)  # nadir (pitch +90 = down, verified)
    bbox, area = project_box((0.35, 0, 20), q, (0, 0, 0), 0.0)
    assert bbox is not None
    cx = (bbox[0] + bbox[2]) / 2
    cyy = (bbox[1] + bbox[3]) / 2
    assert abs(cx - CX) < 60 and abs(cyy - CY) < 60, bbox
    # ~4 m at 20 m with fx 935 -> ~187 px long side
    long_side = max(bbox[2] - bbox[0], bbox[3] - bbox[1])
    assert 140 < long_side < 260, bbox
    b2, _ = project_box((0.35, 0, 20), q, (0, 2.0, 0), 0.0)
    assert b2 is not None and (b2[0] + b2[2]) / 2 != cx  # lateral nudge moves box in u

    # 3. look_at: forward vector reproduces the target direction
    p = np.array([0.0, 0.0, 20.0])
    tgt = np.array([10.0, 5.0, 0.0])
    q, yaw, pitch = look_at(p, tgt)
    fwd = quat_to_R(q) @ np.array([1.0, 0, 0])
    want = (tgt - p) / np.linalg.norm(tgt - p)
    assert np.allclose(fwd, want, atol=1e-6), (fwd, want)
    assert pitch > 0  # looking down => positive pitch (empirical SDF convention)

    # 4. scenario determinism: same seed identical; different seed differs
    a, b = author_scenario(7, 50), author_scenario(7, 50)
    assert np.array_equal(a["target"]["xy"], b["target"]["xy"])
    assert np.array_equal(a["cam_quat"], b["cam_quat"])
    c = author_scenario(8, 50)
    assert np.abs(a["target"]["xy"][0] - c["target"]["xy"][0]).max() > 0.5

    # 5. spawn SDF parses and text-format escaping keeps it single-line
    import xml.etree.ElementTree as ET
    s = car_sdf("t", (0.1, 0.2, 0.3))
    ET.fromstring(s)
    assert "\n" not in s

    # 6. colour classifiers on synthetic patches
    blue = np.zeros((8, 8, 3), np.uint8)
    blue[:] = (150, 40, 20)  # BGR
    white = np.zeros((8, 8, 3), np.uint8)
    white[:] = (230, 228, 226)
    grey = np.zeros((8, 8, 3), np.uint8)
    grey[:] = (120, 120, 120)
    assert color_mask(blue, "blue").all() and not color_mask(grey, "blue").any()
    assert color_mask(white, "white").all() and not color_mask(grey, "white").any()

    # 6b. frag_metric (gate G6): one solid blob ~= 1.0; a split body scores the
    #     largest piece's share; sub-threshold pixel counts return None.
    img = np.zeros((60, 120, 3), np.uint8)
    img[10:50, 10:50] = (150, 40, 20)    # blue blob A: 40x40 = 1600 px
    fr, npx = frag_metric(img, [0, 0, 120, 60], "blue", pad=0.0)
    assert fr == 1.0 and npx == 1600, (fr, npx)
    img[10:50, 80:100] = (150, 40, 20)   # blob B: 40x20 = 800 px -> largest 2/3
    fr, npx = frag_metric(img, [0, 0, 120, 60], "blue", pad=0.0)
    assert abs(fr - 2 / 3) < 1e-6 and npx == 2400, (fr, npx)
    tiny = np.zeros((20, 20, 3), np.uint8)
    tiny[0:2, 0:2] = (150, 40, 20)
    fr, npx = frag_metric(tiny, [0, 0, 20, 20], "blue", pad=0.0)
    assert fr is None and npx == 4, (fr, npx)

    # 6c. kerb-safe corridor (P5.9): every authored scenario stays inside
    #     LAT_SAFE x [0, S_SAFE_MAX] (author_scenario asserts internally; run a
    #     seed sweep so a band edit that breaks the corridor fails here, offline).
    h = ROAD_HEADING
    uu = np.array([math.cos(h), math.sin(h)])
    nn = np.array([-math.sin(h), math.cos(h)])
    for sd in range(1, 41):
        sc = author_scenario(sd, 240)
        for role in ("target", "distractor"):
            lat_v = sc[role]["xy"] @ nn
            s_v = sc[role]["xy"] @ uu
            assert LAT_SAFE[0] <= lat_v.min() and lat_v.max() <= LAT_SAFE[1]
            assert s_v.max() <= S_SAFE_MAX

    # 6d. v1 draw-order regression: the P5.9 bank must stay reproducible from
    #     this file. Exact params recorded in the P5.9 seed101_A results.json.
    sc101 = author_scenario(101, 240)
    assert abs(sc101["params"]["v_target"] - 5.830597516831662) < 1e-9
    assert abs(sc101["params"]["standoff"] - 17.7684841698056) < 1e-9
    assert abs(sc101["params"]["alt"] - 16.308054705510095) < 1e-9

    # 6e. v2 profile (P5.11): determinism, corridor + no-contact construction
    #     guarantees over a seed sweep (asserts fire inside author_scenario_v2),
    #     occluder invariant (blue strictly nearer every frame), lane change
    #     really crosses the target's lat, and helper unit tests.
    a2, b2 = author_scenario(7, 300, profile="v2"), author_scenario(7, 300, profile="v2")
    assert np.array_equal(a2["distractor"]["xy"], b2["distractor"]["xy"])
    assert np.array_equal(a2["cam_quat"], b2["cam_quat"])
    hh = ROAD_HEADING
    uu2 = np.array([math.cos(hh), math.sin(hh)])
    nn2 = np.array([-math.sin(hh), math.cos(hh)])
    for sd in range(1, 41):
        sc = author_scenario(sd, 300, profile="v2")  # internal asserts run here
        s_w2 = sc["target"]["xy"] @ uu2
        s_b2 = sc["distractor"]["xy"] @ uu2
        assert (s_b2 - s_w2).max() <= -V2_MIN_GAP_S  # blue behind = nearer, always
        lat_w2 = sc["target"]["xy"] @ nn2
        lat_b2 = sc["distractor"]["xy"] @ nn2
        d = lat_b2 - lat_w2
        assert d[0] > 0 and d[-1] < 0, sd  # starts right of target, ends left
    assert _iou2d((0, 0, 10, 10), (5, 0, 15, 10)) == 50 / 150
    assert _iou2d((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert _iou2d(None, (0, 0, 1, 1)) == 0.0
    assert _overlap_frac((0, 0, 10, 10), (5, 0, 15, 10)) == 0.5
    assert _overlap_frac((0, 0, 10, 10), None) == 0.0
    assert _max_run([0, 1, 1, 1, 0, 1], 0.5) == 3

    # 6f. v2 crossing screen: regression-pin the offline screen on two known
    #     seeds (measured 2026-07-17: seed 1 passes all five S-rules, seed 11
    #     fails S3 run_occl50=0 < 25). If either flips, the geometry or the
    #     screen changed -- both are pre-registered, so that is a real break.
    m1 = v2_crossing_screen(author_scenario(1, V2_N_FRAMES, profile="v2"))
    m11 = v2_crossing_screen(author_scenario(11, V2_N_FRAMES, profile="v2"))
    assert m1["pass"], m1
    assert not m11["pass"] and m11["run_occl50"] < 25, m11
    assert m1["peak_f"] <= V2_SCREEN["peak_before_f"]

    # 6g. v2.1 screen regression pins (P5.12): the greedy admission over the
    #     pre-registered pool must reproduce the pinned bank byte-for-byte;
    #     the P5.11 G4b-failing near-duplicate pair (9, 14) must be split
    #     (9 fails S6: predicted clear 32 < 45); seed 13 (P5.11 bank11,
    #     n_clear 23) must be excluded; and the full 15-seed set (3 gate + 12
    #     bank) must clear the G4b floor 1.0 m with the screen's 1.1 m margin.
    import itertools as _it
    admitted_21, _rows_21 = v2_1_bank()
    assert admitted_21 == V2_1_BANK_PINNED, admitted_21
    assert 9 not in admitted_21 and 13 not in admitted_21
    scs_21 = {s: author_scenario(s, V2_N_FRAMES, profile="v2")
              for s in list(V2_1_SCREEN["gate_seeds"]) + admitted_21}
    dmin_21 = min(scenario_divergence(scs_21[a], scs_21[b])
                  for a, b in _it.combinations(list(scs_21), 2))
    assert dmin_21 >= 1.0, dmin_21  # G4b floor; measured 1.106 at pair (2, 29)
    for s in admitted_21:
        assert predicted_clear_count(scs_21[s]) >= V2_1_SCREEN["clear_min"], s

    # 6h. v3 profile + screen regression pins (P5.17): determinism, corridor +
    #     no-contact + stable-z-order construction guarantees over a seed
    #     sweep, the post-prompt camera hold (anchor frozen from f150, bob/
    #     sway still alive), the z-order coin actually mixing, and the pinned
    #     bank admission byte-for-byte with its S9 set rules.
    a3, b3 = author_scenario(7, 300, profile="v3"), author_scenario(7, 300, profile="v3")
    assert np.array_equal(a3["distractor"]["xy"], b3["distractor"]["xy"])
    assert np.array_equal(a3["cam_quat"], b3["cam_quat"])
    nears = set()
    for sd in range(1, 41):
        sc = author_scenario(sd, 300, profile="v3")  # internal asserts run here
        nears.add(sc["params"]["near"])
        # camera anchor frozen from V3_HOLD_FRAME: the look-at direction at
        # f200/f299 must match a camera re-aimed at the f150 anchor, and the
        # xy anchor (pos minus sway) must equal the f150 anchor exactly
        assert not np.allclose(sc["target"]["xy"][299],
                               sc["target"]["xy"][150])  # cars still moving
        swy = sc["cam_pos"][:, :2]
        hh3 = ROAD_HEADING
        nn3 = np.array([-math.sin(hh3), math.cos(hh3)])
        uu3 = np.array([math.cos(hh3), math.sin(hh3)])
        anchor = swy - np.outer(swy @ nn3, nn3)  # remove lateral (sway) part
        assert np.allclose(anchor[150] @ uu3, anchor[299] @ uu3, atol=1e-9), sd
        assert not np.allclose(anchor[100] @ uu3, anchor[150] @ uu3, atol=1e-6), sd
    assert nears == {"white", "blue"}, nears  # coin mixes within 40 seeds
    m3 = v3_crossing_screen(author_scenario(2, V3_N_FRAMES, profile="v3"))
    assert m3["pass"] and m3["near"] == "white", m3
    m3f = v3_crossing_screen(author_scenario(1, V3_N_FRAMES, profile="v3"))
    assert not m3f["pass"] and m3f["clear_far"] < V3_SCREEN["clear_min"], m3f
    admitted_3, rows_3 = v3_bank()
    assert admitted_3 == V3_BANK_PINNED, admitted_3
    nw3 = sum(1 for r in rows_3 if r["admitted"] and r["near"] == "white")
    assert nw3 == 14 and len(admitted_3) == 28, (nw3, len(admitted_3))
    assert v3_bank_peak_span(rows_3) >= V3_SCREEN["peak_span_min"]
    scs_3 = [author_scenario(s, V3_N_FRAMES, profile="v3") for s in admitted_3]
    dmin_3 = min(scenario_divergence(x, y)
                 for k, x in enumerate(scs_3) for y in scs_3[k + 1:])
    assert dmin_3 >= 1.0, dmin_3  # G4b floor under the 1.1 screen margin
    for sc in scs_3:
        mm = v3_crossing_screen(sc)
        assert mm["stale_t"] <= V3_SCREEN["stale_iou_max"] \
            and mm["stale_d"] <= V3_SCREEN["stale_iou_max"] and mm["scoreable"]

    # 7. proxy protocol round-trip (needs the gz python libs but NO gz server):
    #    ping->pong, then a request to a nonexistent service must come back
    #    ok=False without crashing the proxy, and the proxy must still answer.
    px = ProxyClient()
    ok, err = px.call("/no/such/service", "gz.msgs.WorldControl", "pause: true",
                      timeout_ms=300)
    assert not ok and px.restarts == 0, (ok, err, px.restarts)
    got, resp = px._roundtrip({"op": "ping"}, 5.0)
    assert got and resp.get("op") == "pong", resp  # proxy alive after the failure
    px.close()

    # 8. killserver never matches its own process tree (run with no server up it
    #    must find nothing that is this process or an ancestor -- structural
    #    guard only; the full behaviour needs a live server).
    import os
    assert "select_arena.sdf" not in Path(f"/proc/{os.getpid()}/cmdline"
                                          ).read_bytes().decode(errors="replace")

    print("scenegen selfcheck OK")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--seed", type=int, required=True)
    r.add_argument("--frames", type=int, default=240)
    r.add_argument("--out", required=True)
    r.add_argument("--profile", choices=("v1", "v2", "v3"), default="v1",
                   help="v1 = P5.9 bank (frozen); v2 = P5.11 crossing bank; "
                        "v3 = P5.17 lag-stress bank")
    s = sub.add_parser("screen")  # offline v2 crossing screen (no gz needed)
    s.add_argument("--lo", type=int, default=1)
    s.add_argument("--hi", type=int, default=60)
    s.add_argument("--need", type=int, default=12)
    s21 = sub.add_parser("screen21")  # offline v2.1 screen: S1-S5 + S6 + S7 (P5.12)
    s21.add_argument("--lo", type=int, default=None)
    s21.add_argument("--hi", type=int, default=None)
    s21.add_argument("--need", type=int, default=12)
    s3 = sub.add_parser("screen3")  # offline v3 screen: S1-S6 + S8 + S7/S9 (P5.17)
    s3.add_argument("--lo", type=int, default=None)
    s3.add_argument("--hi", type=int, default=None)
    s3.add_argument("--need-per-class", type=int, default=None)
    sub.add_parser("selfcheck")
    sub.add_parser("proxy")       # internal: spawned by ProxyClient
    sub.add_parser("killserver")  # kill select_arena gz servers by process group
    args = ap.parse_args()
    if args.cmd == "selfcheck":
        selfcheck()
    elif args.cmd == "screen":
        sys.exit(screen_cmd(args))
    elif args.cmd == "screen21":
        sys.exit(screen21_cmd(args))
    elif args.cmd == "screen3":
        sys.exit(screen3_cmd(args))
    elif args.cmd == "proxy":
        proxy_main()
    elif args.cmd == "killserver":
        killserver()
    else:
        record(args)


if __name__ == "__main__":
    main()
