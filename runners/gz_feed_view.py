#!/usr/bin/env python3
"""
gz_feed_view.py -- see the real Gazebo camera feed over SSH.

Starts `gz sim` headless (NVIDIA EGL) with the Sonoma Raceway world (chase_cam
mounted over the start grid), subscribes to the camera topic, and serves the
live frames as MJPEG on 127.0.0.1:8088. The camera tilt is a runtime knob:
--pitch -90 = nadir (straight down), ~-10 = near-horizon / mostly sky (default).

This is what the grounding model will see (follow-loop / VLM come later).

View it over SSH:
    ssh -L 8088:localhost:8088 <box>          # on your laptop
    .venv-ft/bin/python runners/gz_feed_view.py   # on the box
    # open http://localhost:8088 in your browser

One-frame smoke check / still capture (no server):
    .venv-ft/bin/python runners/gz_feed_view.py --snapshot /tmp/feed.png --pitch -30

Run with the venv python (.venv-ft) -- it has cv2 AND (via the path insert
below) the system gz-transport bindings.
"""
import argparse
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2  # from the venv -- import BEFORE touching sys.path
import numpy as np

sys.path.append("/usr/lib/python3/dist-packages")  # APPEND: gz-transport13 / gz-msgs10 only;
# must not front-shadow the venv's numpy/cv2 (different ABI -> native crash, no traceback)

REPO = Path(__file__).resolve().parent.parent
WORLD_SDF = REPO / "runners" / "sitl" / "worlds" / "sonoma_follow.sdf"
WORLD = "raceway"
CAM = "chase_cam"
CAM_TOPIC = f"/world/{WORLD}/model/{CAM}/link/cam_link/sensor/{CAM}/image"
SET_POSE_SVC = f"/world/{WORLD}/set_pose"
HOST, PORT = "127.0.0.1", 8088

# gz sim -s renders the camera sensor offscreen via EGL (it ignores DISPLAY). By
# default glvnd's EGL loader picks mesa on this box and fails ("dri2 screen") -> BLACK
# frames. Force NVIDIA's EGL vendor so it renders on the 3090.
GZ_EGL_ICD = os.environ.get("GZ_FEED_EGL_ICD", "/usr/share/glvnd/egl_vendor.d/10_nvidia.json")
# Sonoma world uses model:// includes from the vendored SITL_Models tree.
_SITL = REPO / "runners" / "sitl" / "external" / "SITL_Models" / "Gazebo"
_RES = f"{_SITL/'models'}:{_SITL/'worlds'}"
GZ_ENV = {**os.environ, "__EGL_VENDOR_LIBRARY_FILENAMES": GZ_EGL_ICD,
          "GZ_SIM_RESOURCE_PATH": _RES + os.pathsep + os.environ.get("GZ_SIM_RESOURCE_PATH", "")}

_latest = {"rgb": None}  # HxWx3 uint8
_lock = threading.Lock()
_first = threading.Event()

# Live camera pose (world). Driven by the control loop from currently-held keys.
_cam = {"x": 0.0, "y": 0.0, "z": 3.0, "pitch": -10.0, "yaw": 145.0}
_held = set()          # movement keys currently down in the browser
_cam_lock = threading.Lock()


def _start_gz(log_path: Path) -> subprocess.Popen:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["gz", "sim", "-s", "-r", str(WORLD_SDF)]  # offscreen EGL render (NVIDIA vendor forced via GZ_ENV)
    return subprocess.Popen(cmd, stdout=open(log_path, "w"), stderr=subprocess.STDOUT, env=GZ_ENV)


def _subscribe():
    print("[gz_feed] importing gz.transport13...", flush=True)
    import gz.transport13 as transport
    from gz.msgs10 import image_pb2
    print("[gz_feed] creating Node()...", flush=True)
    node = transport.Node()
    print("[gz_feed] subscribing...", flush=True)

    def on_image(msg):
        arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
        with _lock:
            _latest["rgb"] = arr
        if arr.std() > 5:  # ponytail: skip the ~8 uniform-gray warmup frames before the scene settles
            _first.set()

    node.subscribe(image_pb2.Image, CAM_TOPIC, on_image)
    return node  # keep a ref alive or the subscription is GC'd


def _quat_zyx(pitch, yaw, roll=0.0):
    """Euler (rad) -> (w,x,y,z). ZYX intrinsic, matching SDF <pose> roll pitch yaw."""
    cy, sy = np.cos(yaw / 2), np.sin(yaw / 2)
    cp, sp = np.cos(pitch / 2), np.sin(pitch / 2)
    cr, sr = np.cos(roll / 2), np.sin(roll / 2)
    return (cr * cp * cy + sr * sp * sy,
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy)


MOVE, LIFT, ROT = 6.0, 3.0, 60.0  # m/s, m/s, deg/s -- fly speeds while a key is held


def _step(cam, keys, dt):
    """Integrate one control tick: apply held movement keys to the pose dict (WASD/RF/arrows)."""
    yaw = np.radians(cam["yaw"])
    fx, fy = np.cos(yaw), np.sin(yaw)         # forward (heading) unit vector
    if "w" in keys: cam["x"] += MOVE * dt * fx; cam["y"] += MOVE * dt * fy
    if "s" in keys: cam["x"] -= MOVE * dt * fx; cam["y"] -= MOVE * dt * fy
    if "a" in keys: cam["x"] -= MOVE * dt * fy; cam["y"] += MOVE * dt * fx   # strafe left (+90 of fwd)
    if "d" in keys: cam["x"] += MOVE * dt * fy; cam["y"] -= MOVE * dt * fx   # strafe right
    if "r" in keys: cam["z"] += LIFT * dt
    if "f" in keys: cam["z"] = max(0.2, cam["z"] - LIFT * dt)                # don't sink below ground
    if "up" in keys:    cam["pitch"] = min(30.0, cam["pitch"] + ROT * dt)
    if "down" in keys:  cam["pitch"] = max(-90.0, cam["pitch"] - ROT * dt)
    if "left" in keys:  cam["yaw"] += ROT * dt
    if "right" in keys: cam["yaw"] -= ROT * dt
    return cam


def _apply_pose():
    """Push the current _cam to gz via the set_pose service (CLI, not the pybind node).

    ponytail: subprocess `gz service` costs ~290ms/call (ruby launcher), so held-key
    control updates at ~3-4 Hz -- fine for placing the camera, not AAA-smooth. It's
    used instead of node.request() because concurrent pybind requests race the image
    subscription callback and crash on a GIL assertion. Upgrade path if smoothness
    matters: a small persistent C++/gz-transport helper, or fixing the pybind GIL.
    """
    with _cam_lock:
        c = dict(_cam)
    # SDF <pose> convention here: negative pitch = look down (phase_c nadir = -1.5708).
    # The plain ZYX quaternion has the opposite sign, so negate to match the knob.
    w, x, y, z = _quat_zyx(np.radians(-c["pitch"]), np.radians(c["yaw"]))
    req = (f'name: "{CAM}", position: {{x: {c["x"]}, y: {c["y"]}, z: {c["z"]}}}, '
           f'orientation: {{w: {w}, x: {x}, y: {y}, z: {z}}}')
    subprocess.run(["gz", "service", "-s", SET_POSE_SVC,
                    "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
                    "--timeout", "500", "--req", req],
                   env=GZ_ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)


def _control_loop(stop):
    """While keys are held, integrate the pose (real elapsed dt) and push it. Idle otherwise."""
    last = time.time()
    while not stop.wait(0.02):
        now = time.time()
        dt, last = now - last, now
        with _cam_lock:
            keys = set(_held)
            if keys:
                _step(_cam, keys, min(dt, 0.25))  # clamp dt so a stalled call can't teleport
        if keys:
            _apply_pose()


# --- feed colour grade ------------------------------------------------------
# The Sonoma OBJ mesh renders effectively unlit in gz/ogre2: world lights don't
# reach its flat baked-texture surfaces (verified -- ambient 1->0.35, sun recolour
# and a low raking sun all left the track pixel-identical). So the scene "look" is a
# post-process grade on the egress frame, not in-world lighting. ~0.3 ms at 640x480.
# Tune GRADE live; set on=False for the raw render.
GRADE = {"on": True, "gamma": 0.90, "contrast": 1.14, "sat": 1.28,
         "warm": 1.07, "cool": 0.95, "vignette": 0.35}


def _grade_lut():
    x = np.arange(256, dtype=np.float32) / 255.0
    x = np.clip((x - 0.5) * GRADE["contrast"] + 0.5, 0, 1)   # contrast about mid-grey
    x = np.power(x, GRADE["gamma"])                           # gamma lift
    return np.clip(x * 255, 0, 255).astype(np.uint8)


_LUT = _grade_lut()
_vig_cache = {}


def _vignette(shape):
    v = _vig_cache.get(shape)
    if v is None:
        h, w = shape
        yy, xx = np.ogrid[0:h, 0:w]
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        # flat in the centre, darkens past r=0.4 out to the corners
        v = (1 - GRADE["vignette"] * np.clip(r - 0.4, 0, 1) / 0.6).astype(np.float32)
        v = _vig_cache[shape] = v[..., None]
    return v


def _grade(bgr):
    if not GRADE["on"]:
        return bgr
    out = cv2.LUT(bgr, _LUT).astype(np.float32)               # contrast+gamma
    out[..., 0] *= GRADE["cool"]                              # BGR: pull blue
    out[..., 2] *= GRADE["warm"]                              # push red = warm
    out *= _vignette(bgr.shape[:2])
    out = np.clip(out, 0, 255).astype(np.uint8)
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * GRADE["sat"], 0, 255)  # saturation
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def _bgr(rgb):
    """RGB frame -> graded BGR, ready for imencode/imwrite."""
    return _grade(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def _jpeg(rgb):
    ok, buf = cv2.imencode(".jpg", _bgr(rgb), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buf.tobytes() if ok else None


PAGE = b"""<!doctype html><meta charset=utf-8><title>Gazebo feed -- fly the camera</title>
<style>body{margin:0;background:#111;color:#ccc;font:14px system-ui;text-align:center}
.wrap{position:relative;display:inline-block;margin-top:8px}
img{max-width:100%;height:auto;display:block;image-rendering:auto}
#hud{position:absolute;top:6px;left:6px;background:rgba(0,0,0,.55);padding:4px 8px;
  font:12px/1.4 monospace;text-align:left;border-radius:4px;pointer-events:none}
p{margin:6px}</style>
<p>Sonoma Raceway &middot; fly the camera: <b>WASD</b> move &middot; <b>R/F</b> up/down &middot;
   <b>arrows</b> look &middot; click the image first</p>
<div class=wrap tabindex=0 id=stage><img src="/stream"><div id=hud></div></div>
<script>
const MAP={w:'w',a:'a',s:'s',d:'d',r:'r',f:'f',
  ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right'};
const held=new Set();
function send(){fetch('/move',{method:'POST',body:[...held].join(',')});}
const stage=document.getElementById('stage');
stage.focus();
stage.addEventListener('keydown',e=>{const k=MAP[e.key];if(!k)return;e.preventDefault();
  if(!held.has(k)){held.add(k);send();}});
stage.addEventListener('keyup',e=>{const k=MAP[e.key];if(!k)return;e.preventDefault();
  held.delete(k);send();});
stage.addEventListener('blur',()=>{if(held.size){held.clear();send();}});  // stop on focus loss
const hud=document.getElementById('hud');
setInterval(async()=>{const p=await(await fetch('/pose')).json();
  hud.textContent=`x ${p.x.toFixed(1)}  y ${p.y.toFixed(1)}  z ${p.z.toFixed(1)}\\n`+
    `pitch ${p.pitch.toFixed(0)}  yaw ${p.yaw.toFixed(0)}`;},200);
</script>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _json(self, obj):
        body = __import__("json").dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/move":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n).decode() if n else ""
        keys = {k for k in raw.split(",") if k}
        with _cam_lock:
            _held.clear()
            _held.update(keys)
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(PAGE)))
            self.end_headers()
            self.wfile.write(PAGE)
            return
        if self.path == "/pose":
            with _cam_lock:
                self._json(dict(_cam))
            return
        if self.path != "/stream":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        try:
            while True:
                with _lock:
                    rgb = _latest["rgb"]
                if rgb is not None:
                    jpg = _jpeg(rgb)
                    if jpg:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                         b"Content-Length: %d\r\n\r\n" % len(jpg))
                        self.wfile.write(jpg)
                        self.wfile.write(b"\r\n")
                time.sleep(1 / 15)
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", metavar="PNG", help="grab one settled frame, save PNG, exit")
    ap.add_argument("--dump", metavar="DIR", help="save --n frames at the topic rate (~5 fps) to DIR, exit")
    ap.add_argument("--n", type=int, default=25, help="frames for --dump (default 25 = 5 s @ 5 fps)")
    ap.add_argument("--attach", action="store_true",
                    help="attach to an already-running gz sim (do not spawn/kill it). "
                         "Needed because the harness reaps gz when python spawns it.")
    ap.add_argument("--pitch", type=float, default=-10.0,
                    help="camera tilt deg: -90 = nadir (straight down), ~-10 = near-horizon/mostly-sky (default)")
    ap.add_argument("--height", type=float, default=3.0, help="camera height above start grid (m)")
    ap.add_argument("--yaw", type=float, default=145.0, help="camera heading deg (145 = down the start straight)")
    ap.add_argument("--selftest", action="store_true", help="check movement math (no gz), exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    with _cam_lock:
        _cam.update(x=0.0, y=0.0, z=args.height, pitch=args.pitch, yaw=args.yaw)

    log = REPO / "runners" / "_gz_feed.log"
    gz = None if args.attach else _start_gz(log)
    stop = threading.Event()
    try:
        node = _subscribe()
        _apply_pose()  # aim before the first frame settles
        if not _first.wait(timeout=30):
            print(f"[gz_feed] no frame in 30s; see {log}", file=sys.stderr)
            return 1
        _apply_pose()  # re-apply once gz is fully up
        threading.Thread(target=_control_loop, args=(stop,), daemon=True).start()

        if args.snapshot:
            time.sleep(0.5)
            with _lock:
                rgb = _latest["rgb"].copy()
            cv2.imwrite(args.snapshot, _bgr(rgb))
            assert rgb.std() > 5, f"frame looks blank (std={rgb.std():.1f})"  # egress smoke check
            print(f"[gz_feed] saved {args.snapshot}  ({rgb.shape[1]}x{rgb.shape[0]}, std={rgb.std():.1f})")
            return 0

        if args.dump:
            out = Path(args.dump)
            out.mkdir(parents=True, exist_ok=True)
            prev = None
            i, t0 = 0, time.time()
            while i < args.n and time.time() - t0 < 20:  # cap: static scene -> dedup would spin forever
                with _lock:
                    rgb = _latest["rgb"]
                if rgb is not None and (prev is None or not np.array_equal(rgb, prev)):
                    cv2.imwrite(str(out / f"frame_{i:03d}.png"), _bgr(rgb))
                    prev = rgb
                    i += 1
                time.sleep(0.05)  # poll faster than 5 Hz; dedup by array equality catches each new frame
            print(f"[gz_feed] wrote {i} frames to {out}")
            return 0

        srv = ThreadingHTTPServer((HOST, PORT), Handler)
        print(f"[gz_feed] live feed at http://{HOST}:{PORT}  (ssh -L {PORT}:localhost:{PORT})  Ctrl-C to stop")
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if gz is not None:
            gz.terminate()
            try:
                gz.wait(timeout=5)
            except subprocess.TimeoutExpired:
                gz.kill()
    return 0


def _selftest():
    c = lambda: {"x": 0.0, "y": 0.0, "z": 3.0, "pitch": -10.0, "yaw": 0.0}  # heading +x
    m = _step(c(), {"w"}, 1.0); assert m["x"] > 0 and abs(m["y"]) < 1e-9, m       # forward = +x
    m = _step(c(), {"s"}, 1.0); assert m["x"] < 0, m                              # back = -x
    m = _step(c(), {"a"}, 1.0); assert m["y"] > 0 and abs(m["x"]) < 1e-9, m       # left = +y
    m = _step(c(), {"d"}, 1.0); assert m["y"] < 0, m                              # right = -y
    m = _step(c(), {"r"}, 1.0); assert m["z"] > 3.0, m                            # up
    m = _step(c(), {"f"}, 100.0); assert m["z"] == 0.2, m                         # down, floored
    m = _step(c(), {"down"}, 100.0); assert m["pitch"] == -90.0, m               # clamp nadir
    m = _step(c(), {"up"}, 100.0); assert m["pitch"] == 30.0, m                  # clamp up
    # grade: warms (R>B on grey), stays in-bounds, vignette darkens corner vs centre
    grey = np.full((64, 64, 3), 128, np.uint8)
    g = _grade(grey.copy())
    assert 0 <= g.min() and g.max() <= 255, (g.min(), g.max())
    assert int(g[32, 32, 2]) > int(g[32, 32, 0]), g[32, 32]                       # centre R > B
    assert g[0, 0].mean() < g[32, 32].mean(), (g[0, 0], g[32, 32])                # corner darker
    GRADE["on"] = False
    assert np.array_equal(_grade(grey.copy()), grey), "off should pass through"
    GRADE["on"] = True
    print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
