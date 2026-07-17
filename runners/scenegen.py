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


def author_scenario(seed, n_frames, fps=25.0):
    """Seeded, fully precomputed poses for 2 cars + camera. Pure numpy, no gz."""
    rng = np.random.default_rng(seed)
    h = ROAD_HEADING
    u = np.array([math.cos(h), math.sin(h)])   # along-track unit
    n = np.array([-math.sin(h), math.cos(h)])  # left-of-track unit
    t = np.arange(n_frames) / fps

    def car(lat_lo, lat_hi, s0, v):
        lat0 = rng.uniform(lat_lo, lat_hi)
        amp, per, ph = rng.uniform(0.2, 0.7), rng.uniform(4.0, 9.0), rng.uniform(0, 2 * math.pi)
        lat = lat0 + amp * np.sin(2 * math.pi * t / per + ph)
        s = s0 + v * t
        xy = GRID + np.outer(s, u) + np.outer(lat, n)
        dlat = np.gradient(lat, 1.0 / fps)
        yaw = h + np.arctan2(dlat, v)
        return xy, yaw, v

    v_t = rng.uniform(3.0, 6.0)
    tgt_xy, tgt_yaw, v_t = car(-5.0, -1.5, rng.uniform(-4, 4), v_t)
    v_d = float(np.clip(v_t + rng.uniform(-1.5, 1.5), 2.5, 6.5))
    dis_xy, dis_yaw, v_d = car(1.5, 5.0, rng.uniform(4, 14), v_d)

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
    sc = author_scenario(args.seed, args.frames)
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
            objs.append(rec)
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
    both_vis = 0
    for r in records:
        ok_both = True
        for o in r["objs"]:
            v = o["visible"] and o["area"] >= 150
            vis[o["id"]].append(v)
            if v:
                pur[o["id"]].append(o["purity"])
                bgp[o["id"]].append(o["bg_purity"])
            ok_both &= v
        both_vis += ok_both
    results = {
        "seed": args.seed, "frames": args.frames, "out": str(out),
        "wall_loop_s": round(loop_s, 1), "fps_wall": round(fps_wall, 3),
        "g1_dead_frames": dead_frames,
        "g1_identical_consecutive": identical_consec,
        "g1_stamp_steps_ok": bool((dstamps == step_ns).all()),
        "g2_purity_median": {str(k): round(float(np.median(v)), 4) if v else None
                             for k, v in pur.items()},
        "g2_bg_purity_median": {str(k): round(float(np.median(v)), 4) if v else None
                                for k, v in bgp.items()},
        "g3_both_visible_frac": round(both_vis / args.frames, 4),
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
    sub.add_parser("selfcheck")
    sub.add_parser("proxy")       # internal: spawned by ProxyClient
    sub.add_parser("killserver")  # kill select_arena gz servers by process group
    args = ap.parse_args()
    if args.cmd == "selfcheck":
        selfcheck()
    elif args.cmd == "proxy":
        proxy_main()
    elif args.cmd == "killserver":
        killserver()
    else:
        record(args)


if __name__ == "__main__":
    main()
