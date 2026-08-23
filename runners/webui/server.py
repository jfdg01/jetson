#!/usr/bin/env python3
"""Barebones CARLA camera -> browser. One camera, one MJPEG stream, nothing else.

    /home/gara/carla/CARLA_0.9.16/CarlaUE4.sh -RenderOffScreen -quality-level=Epic &  # once
    .venv-ft/bin/python runners/webui/server.py                                         # then
    open http://<this host>:8080

Rebuilt from scratch on 2026-08-23 to replace the Tk panel (runners/carla_debug_ui.py);
nothing is imported from it. The camera hangs off the spectator, so a later "fly" only
has to call `world.get_spectator().set_transform(...)`. Each frame is JPEG-encoded once,
in CARLA's callback thread (cv2 releases the GIL); every browser client takes the latest
frame and a slow client simply skips some.

    --smoke S   serve for S seconds, fetch one frame over HTTP, assert it is a picture
                (not one colour, feed still moving), write it as JPG, exit. Look at the
                JPG before claiming the stream shows anything.
"""
import argparse
import collections
import json
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import carla
import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
CARLA_SH = "/home/gara/carla/CARLA_0.9.16/CarlaUE4.sh"


class Latest:
    """The newest JPEG and its sequence number; readers wait for a number above theirs."""

    def __init__(self):
        self.cv = threading.Condition()
        self.jpg, self.n, self.w, self.h = None, 0, 0, 0
        self.stamps = collections.deque(maxlen=120)

    def put(self, jpg, w, h):
        with self.cv:
            self.jpg, self.n, self.w, self.h = jpg, self.n + 1, w, h
            self.stamps.append(time.time())
            self.cv.notify_all()

    def after(self, n, timeout=2.0):
        with self.cv:
            self.cv.wait_for(lambda: self.n > n, timeout)
            return self.jpg, self.n

    def fps(self):
        s = list(self.stamps)
        return (len(s) - 1) / (s[-1] - s[0]) if len(s) > 1 and s[-1] > s[0] else 0.0


LATEST = Latest()


def attach_camera(world, side, fov, hz, alt, quality):
    spec = world.get_spectator()
    sp = world.get_map().get_spawn_points()[0]
    spec.set_transform(carla.Transform(sp.location + carla.Location(z=alt),
                                       carla.Rotation(pitch=-90.0, yaw=sp.rotation.yaw)))
    bp = world.get_blueprint_library().find("sensor.camera.rgb")
    for k, v in (("image_size_x", side), ("image_size_y", side), ("fov", fov),
                 ("sensor_tick", 1.0 / hz)):
        bp.set_attribute(k, str(v))
    cam = world.spawn_actor(bp, carla.Transform(), attach_to=spec)

    def on_image(img):
        bgr = np.frombuffer(img.raw_data, np.uint8).reshape(img.height, img.width, 4)[:, :, :3]
        ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if ok:
            LATEST.put(buf.tobytes(), img.width, img.height)

    cam.listen(on_image)
    return cam


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):          # one line per frame otherwise
        pass

    def _send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self._send((HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/frame.jpg":
            jpg, _ = LATEST.after(0)
            if jpg is None:
                self.send_error(503, "no frame yet")
            else:
                self._send(jpg, "image/jpeg")
        elif self.path == "/stats":
            body = json.dumps({"n": LATEST.n, "fps": LATEST.fps(),
                               "w": LATEST.w, "h": LATEST.h}).encode()
            self._send(body, "application/json")
        elif self.path == "/stream":
            self.stream()
        else:
            self.send_error(404)

    def stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=f")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        n = LATEST.n
        try:
            while True:
                jpg, n2 = LATEST.after(n)
                if n2 == n:
                    continue            # 2 s without a frame: keep the socket, keep waiting
                n = n2
                self.wfile.write(b"--f\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n"
                                 % len(jpg))
                self.wfile.write(jpg)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


def smoke(http_port, seconds, out):
    """Assert the stream is a live picture: two sequence reads move, one frame is not flat."""
    base = f"http://127.0.0.1:{http_port}"
    get = lambda p: urllib.request.urlopen(base + p, timeout=10).read()
    time.sleep(seconds / 2)
    n0 = json.loads(get("/stats"))["n"]
    time.sleep(seconds / 2)
    st = json.loads(get("/stats"))
    assert st["n"] > n0 + 5, f"feed dead: frame counter {n0} -> {st['n']} in {seconds / 2:.0f} s"
    img = cv2.imdecode(np.frombuffer(get("/frame.jpg"), np.uint8), cv2.IMREAD_COLOR)
    assert img is not None and img.shape[:2] == (st["h"], st["w"]), f"bad frame {img and img.shape}"
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    flat = np.bincount(grey.ravel(), minlength=256).max() / grey.size
    assert flat < 0.99, f"frame is {flat:.1%} one shade: failed render"
    out.mkdir(parents=True, exist_ok=True)
    jpg = out / f"webui-smoke-{time.strftime('%Y%m%dT%H%M')}.jpg"
    cv2.imwrite(str(jpg), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"SMOKE OK  {st['w']}x{st['h']}  sensor {st['fps']:.1f} Hz  dominant shade "
          f"{flat:.1%}  frame -> {jpg}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="127.0.0.1", help="CARLA rpc host")
    ap.add_argument("--port", type=int, default=2000, help="CARLA rpc port")
    ap.add_argument("--bind", default="0.0.0.0", help="HTTP bind address")
    ap.add_argument("--http", type=int, default=8080, help="HTTP port")
    ap.add_argument("--side", type=int, default=960, help="square camera size, px")
    ap.add_argument("--fov", type=float, default=90.0)
    ap.add_argument("--hz", type=float, default=30.0, help="sensor_tick, the frame-rate ceiling")
    ap.add_argument("--alt", type=float, default=45.0, help="camera height above spawn 0, m, nadir")
    ap.add_argument("--quality", type=int, default=80, help="JPEG quality 1-100")
    ap.add_argument("--smoke", type=float, metavar="S", help="self-check for S seconds, then exit")
    ap.add_argument("--out", type=Path, default=Path("experiments/raw/webui"),
                    help="where --smoke writes its frame")
    args = ap.parse_args()

    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)
    try:
        world = client.get_world()
    except RuntimeError as e:
        raise SystemExit(f"no CARLA on {args.host}:{args.port} ({e}). Start it first:\n"
                         f"  {CARLA_SH} -RenderOffScreen -quality-level=Epic &")
    cam = attach_camera(world, args.side, args.fov, args.hz, args.alt, args.quality)
    srv = ThreadingHTTPServer((args.bind, args.http), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"CARLA {client.get_server_version()} map {world.get_map().name}  "
          f"camera {args.side}x{args.side} fov {args.fov:.0f} @ {args.hz:.0f} Hz  "
          f"-> http://{args.bind}:{args.http}/", flush=True)
    try:
        if args.smoke:
            smoke(args.http, args.smoke, args.out)
        else:
            while True:
                time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        srv.shutdown()
        cam.stop()
        cam.destroy()


if __name__ == "__main__":
    main()
