#!/usr/bin/env python3
"""Tk debug panel for a running CarlaUE4.sh. Buttons only, no state of its own.

    .venv-ft/bin/python runners/carla_debug_ui.py
"""
import argparse
import collections
import math
import random
import signal
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
import traceback
from pathlib import Path

import carla
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grounding.contract import COORD_SCALE, parse_bbox

# What the operator flies IS the drone camera: the frame on screen and the frame
# the VLM grounds come from this one sensor, so they cannot disagree. FOV used to
# have to match CarlaUE4's viewport default, back when the operator watched the
# viewport; headless removed that constraint, so 90 is inherited rather than
# chosen and is an untested lever on lock rate.
CAM_W, CAM_H, CAM_FOV = 960, 540, 90
# 5 Hz feed. The catch-up only converges if the tracker outruns the camera:
# SAM2.1-hiera-tiny is 14.4 FPS @1024 on the 3090, so at 5 Hz a ~20-frame backlog
# (one ~3.9 s VLM call) drains in ~2.1 s at stride 1. At 20 Hz it never converges.
CAM_HZ = 5.0
# One camera, two rates: the operator sees 30 Hz, the Jetson every 6th
# frame. Two sensors would double the render cost to show the same pixels.
LIVE_HZ = 30.0
FEED_EVERY = round(LIVE_HZ / CAM_HZ)
# Replaying every buffered frame drains at (carry_fps - CAM_HZ), which measured
# 4.9 frames/s -> 7.5 s to catch up, by which time the target had left frame.
# Stride S consumes S*carry_fps, so S=3 drains ~25 frames/s instead. The cost is
# a 0.6 s gap between replayed frames -- if the carry drops fast targets during
# catch-up, this is the knob. P5.1's idle_catchup does the same thing.
CARRY_STRIDE = 3
CARRY_DIR = "experiments/2026-07-01-temporal-acquire-carry"   # StreamCarry lives here
# 1080p30 cap: a 2144x1206 sensor rendered every frame is more than the 3090
# has spare once SAM2 is co-resident on it.
MAX_CAM_W = 1920
THUMB_W = 300          # what the Jetson sees stays a thumbnail at any window size
CARLA_SH = "/home/gara/carla/CARLA_0.9.16/CarlaUE4.sh"
REMOTE_DIR = "/home/jfdg/grounding"
REMOTE_GGUF = f"{REMOTE_DIR}/phase3-terse100eos-1024-q8_0.gguf"
REMOTE_MMPROJ = f"{REMOTE_DIR}/mmproj-phase3-terse100eos-1024-f16.gguf"


def project(world_loc, cam_tf, w=CAM_W, h=CAM_H, fov=CAM_FOV):
    """CARLA world point -> image pixel. Standard pinhole + the UE axis swap."""
    f = w / (2.0 * math.tan(math.radians(fov) / 2.0))
    pt = np.array([world_loc.x, world_loc.y, world_loc.z, 1.0])
    c = np.dot(np.array(cam_tf.get_inverse_matrix()), pt)
    # UE is x-forward/y-right/z-up; the pinhole wants x-right/y-down/z-forward
    x, y, z = c[1], -c[2], c[0]
    if z <= 0.1:
        return None                      # behind the camera
    return (f * x / z + w / 2.0, f * y / z + h / 2.0)


def match_actor(world, cam_tf, box):
    """Which vehicle, if any, sits inside the tracker's box. None means drifted.

    The correctness check the throughput asserts could not give -- and it only
    reads the world, it draws nothing. Overlays go on the frames we receive, not
    into the engine, so the render stays the render.
    """
    best, best_d = None, 1e9
    cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    for v in world.get_actors().filter("vehicle.*"):
        p = project(v.get_location(), cam_tf)
        if p is None or not (box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]):
            continue
        d = math.hypot(p[0] - cx, p[1] - cy)
        if d < best_d:
            best, best_d = v, d
    return best


def draw_overlay(frame, box, label, locked, scale=1.0):
    """Box + caption onto a copy of the received frame. Green locked, red adrift."""
    if box is None:
        return frame
    c = (0, 255, 0) if locked else (0, 0, 255)
    p = [int(v * scale) for v in box]
    cv2.rectangle(frame, (p[0], p[1]), (p[2], p[3]), c, max(1, int(2 * scale)))
    cv2.putText(frame, label, (p[0], max(14, p[1] - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5 * scale, c, 1)
    return frame


def ensure_carla(host, port, sh, wait=300):
    """Connect, or start a headless CARLA and wait for its RPC to answer.

    Headless is the right default here: the UI never reads the viewport, it reads
    an attached RGB sensor, so the on-screen window was pure GPU cost.
    """
    # a fresh Client per attempt: one that has already timed out stays unhappy,
    # which is what made a CARLA that WAS coming up look like one that never did
    def try_connect(t):
        c = carla.Client(host, port)
        c.set_timeout(t)
        try:
            c.get_server_version()
            return c
        except RuntimeError:
            return None

    got = try_connect(2.0)
    if got is not None:
        return got
    if not Path(sh).exists():
        raise SystemExit(f"nothing on {host}:{port} and no CarlaUE4.sh at {sh}")
    print(f"starting headless CARLA: {sh}", flush=True)
    subprocess.Popen([sh, "-RenderOffScreen", "-quality-level=Epic",
                      f"-carla-rpc-port={port}", "-ExecCmds=t.MaxFPS 30"],
                     cwd=str(Path(sh).parent),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + wait
    while time.time() < deadline:
        got = try_connect(5.0)
        if got is not None:
            print("CARLA up", flush=True)
            return got
        time.sleep(2.0)
    raise SystemExit(f"CARLA did not answer on {port} within {wait}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--out", default="runs/carla-ui",
                    help="where grounded overlays are written")
    ap.add_argument("--carla", default=CARLA_SH,
                    help="CarlaUE4.sh to launch if nothing answers on the port")
    ap.add_argument("--selftest", action="store_true",
                    help="spawn, check they move, clear, exit")
    args = ap.parse_args()

    client = ensure_carla(args.host, args.port, args.carla)
    client.set_timeout(60.0)  # load_world blocks for ~10-30s
    # basename only: get_available_maps returns /Game/Carla/Maps/Town10HD_Opt
    maps = sorted(m.split("/")[-1] for m in client.get_available_maps())

    root = tk.Tk()
    root.title("CARLA debug")
    # Start maximised so the sensor picks the full-screen resolution on the first
    # attach. mutter ignores -zoomed when it is set before the window is mapped,
    # so an explicit screen-sized geometry is the one that actually takes.
    root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight() - 60}+0+0")
    try:
        root.attributes("-zoomed", True)
    except tk.TclError:
        pass

    # Tk must own the main thread, so the CARLA RPCs move off it instead -- a
    # load_world blocks 10-30 s and every spawn is a round-trip, which froze the
    # whole panel. Widgets are only touched back on the main thread via after().
    # ponytail: one flag, not a queue -- these are all whole-world operations
    # that have no business overlapping anyway.
    busy = {"on": False}

    def bg(target, fn, *a):
        if busy["on"]:
            status.config(text="busy, wait")
            return
        busy["on"] = True
        target.config(text="working...")

        def work():
            try:
                msg = fn(*a)
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
            busy["on"] = False
            root.after(0, lambda: target.config(text=msg))

        threading.Thread(target=work, daemon=True).start()
    # One control strip along the top; everything below it is picture. The map
    # list was a 22-row Listbox that pushed the feeds off the bottom of a 1440p
    # screen -- a Combobox is the same choice in one line.
    bar = tk.Frame(root)
    bar.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)

    label = tk.Label(bar, text="map")
    label.pack(side=tk.LEFT)
    picked = tk.StringVar(value=client.get_world().get_map().name.split("/")[-1])
    listbox = ttk.Combobox(bar, textvariable=picked, values=maps,
                           state="readonly", width=22)
    listbox.pack(side=tk.LEFT, padx=(4, 4))

    def load_world(nxt):
        # a non-drivable entry (e.g. AnnotationColorLandscape) raises here
        try:
            client.load_world(nxt)
            out = nxt
        except RuntimeError as e:
            out = f"{nxt}: {e}"
        # new world: the old spectator handle and our actor ids are all stale
        cam["spec"], cam["t"], cam["sensor"] = (
            client.get_world().get_spectator(), None, None)
        attach_camera()
        spawned.clear()
        return out

    def load_selected(_event=None):
        bg(status, load_world, picked.get())

    tk.Button(bar, text="load", command=load_selected).pack(side=tk.LEFT)

    spawned = []  # everything we made, so "clear" only kills our own actors
    row = tk.Frame(bar)
    row.pack(side=tk.LEFT, padx=(16, 0))
    tk.Label(row, text="count").pack(side=tk.LEFT)
    count = tk.Spinbox(row, from_=1, to=300, width=4)
    count.delete(0, tk.END)
    count.insert(0, "30")
    count.pack(side=tk.LEFT, padx=(4, 6))
    status = tk.Label(bar, text="", anchor=tk.W)

    def spawn_vehicles(n):
        world = client.get_world()
        bps = world.get_blueprint_library().filter("vehicle.*")
        points = world.get_map().get_spawn_points()
        random.shuffle(points)
        n = min(n, len(points))
        tm_port = client.get_trafficmanager().get_port()
        batch = [carla.command.SpawnActor(random.choice(bps), p).then(
                     carla.command.SetAutopilot(carla.command.FutureActor,
                                                True, tm_port))
                 for p in points[:n]]
        ids = [r.actor_id for r in client.apply_batch_sync(batch, True)
               if not r.error]
        spawned.extend(ids)
        # short of n means the spawn points were already occupied
        return f"+{len(ids)}/{n} vehicles ({len(spawned)} total)"

    def spawn_walkers(n):
        world = client.get_world()
        bps = world.get_blueprint_library().filter("walker.pedestrian.*")
        if world.get_random_location_from_navigation() is None:
            return "no pedestrian navmesh on this map"
        # random navmesh points land on top of each other often enough that a
        # single batch only places a third of them -- retry the misses.
        walkers = []
        for _ in range(5):
            if len(walkers) >= n:
                break
            batch = []
            for _ in range(n - len(walkers)):
                bp = random.choice(bps)
                if bp.has_attribute("is_invincible"):
                    bp.set_attribute("is_invincible", "false")
                spot = carla.Transform(world.get_random_location_from_navigation())
                batch.append(carla.command.SpawnActor(bp, spot))
            walkers += [r.actor_id for r in client.apply_batch_sync(batch, True)
                        if not r.error]
        # a walker without an AI controller just stands there
        ctrl_bp = world.get_blueprint_library().find("controller.ai.walker")
        batch = [carla.command.SpawnActor(ctrl_bp, carla.Transform(), w)
                 for w in walkers]
        ctrls = [r.actor_id for r in client.apply_batch_sync(batch, True)
                 if not r.error]
        world.wait_for_tick()  # controllers must exist server-side before start()
        for c in world.get_actors(ctrls):
            c.start()
            c.go_to_location(world.get_random_location_from_navigation())
            c.set_max_speed(1.4)  # without this the controller sits at 0 m/s
        spawned.extend(walkers + ctrls)
        return f"+{len(walkers)}/{n} walkers ({len(spawned)} total)"

    def clear():
        world = client.get_world()
        for a in world.get_actors(spawned):
            if a.type_id.startswith("controller"):
                a.stop()  # stop before destroy or the walker keeps its command
        res = client.apply_batch_sync(
            [carla.command.DestroyActor(x) for x in spawned], True)
        failed = [r.error for r in res if r.error]
        world.wait_for_tick()  # actors stay in the registry until the next tick
        msg = (f"cleared {len(spawned) - len(failed)}"
               + (f", {len(failed)} failed" if failed else ""))
        spawned.clear()
        return msg

    tk.Button(row, text="cars",
              command=lambda: bg(status, spawn_vehicles, int(count.get()))
              ).pack(side=tk.LEFT)
    tk.Button(row, text="walkers",
              command=lambda: bg(status, spawn_walkers, int(count.get()))
              ).pack(side=tk.LEFT, padx=4)
    tk.Button(row, text="clear",
              command=lambda: bg(status, clear)).pack(side=tk.LEFT)

    # Pause = flip the server into synchronous mode and never tick it. Nothing
    # advances: traffic, physics and the camera all stop, so the last frame just
    # sits there. Resume puts it back to async, which is how the rig normally runs
    # (the sim must free-run at its own pace -- that is the whole point of the
    # separate 5 Hz feed).
    paused = {"on": False}

    def toggle_pause():
        world = client.get_world()
        settings = world.get_settings()
        tm = client.get_trafficmanager()
        want = not paused["on"]
        settings.synchronous_mode = want
        # a sync world with no fixed step warns on every apply; 20 Hz is only what
        # the step WOULD be, nothing ticks while paused anyway
        settings.fixed_delta_seconds = 0.05 if want else None
        world.apply_settings(settings)
        tm.set_synchronous_mode(want)
        paused["on"] = want
        held.clear()          # drop anything mid-press, or it resumes still held
        pause_btn.config(text="resume" if want else "pause")
        status.config(text="PAUSED" if want else "running")

    pause_btn = tk.Button(row, text="pause", command=toggle_pause)
    pause_btn.pack(side=tk.LEFT, padx=(6, 0))

    def unpause_on_exit():
        # a server left in sync mode with no ticker hangs the next client that
        # connects -- never leave it that way, even on a crash
        if paused["on"]:
            try:
                toggle_pause()
            except RuntimeError:
                pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", unpause_on_exit)

    # CarlaUE4's own WASD fly speed is a UE4 viewport setting with no RPC, so
    # instead we drive the spectator ourselves. Keys work while THIS window has
    # focus; the CARLA window still shows the result.
    held = set()
    pending = {}  # keysym -> after-id of a not-yet-applied release

    # The keys go to whichever widget has focus, and the thing you want to fly is
    # the picture -- so the image labels ARE the focus target (wired below, once
    # they exist). Focusing there also keeps wasd out of the Spinbox and Combobox.
    tk.Label(bar, text="click the view to fly:  wasd/qe, arrows look").pack(
        side=tk.LEFT, padx=(16, 0))
    speed = tk.Scale(bar, from_=1, to=300, orient=tk.HORIZONTAL, length=140,
                     showvalue=True, label=None, sliderlength=16)
    speed.set(45)
    speed.pack(side=tk.LEFT, padx=(8, 0))
    status.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(16, 0))

    # --- "follow that car": ground the frame the operator is looking at ---
    out_dir = Path(args.out)
    backend = {"be": None}   # lazy: booting llama-server on the Jetson costs ~1 min

    # box is in PIXELS of the live frame, kept current by the follow thread; tick()
    # only ever reads it, so no lock -- a dict assign is atomic under the GIL.
    track = {"box": None, "msg": "", "lag": 0, "stop": None, "actor": None,
             "hits": 0, "steps": 0}
    resize = {"job": None}

    def _pixels(box, w, h):
        """contract coords are 0-COORD_SCALE normalised, not pixels"""
        return [int(box[0] / COORD_SCALE * w), int(box[1] / COORD_SCALE * h),
                int(box[2] / COORD_SCALE * w), int(box[3] / COORD_SCALE * h)]

    def follow(caption, stop):
        with frame_lock:
            if latest["bgr"] is None:
                track["msg"] = "no frame yet -- is the camera attached?"
                return
            seed_n, seed = latest["n"], latest["bgr"].copy()

        if backend["be"] is None:
            track["msg"] = "booting Jetson llama-server..."
            from grounding.eval.backends import JetsonBackend
            backend["be"] = JetsonBackend(REMOTE_GGUF, REMOTE_MMPROJ,
                                          max_side=1024).__enter__()
        out_dir.mkdir(parents=True, exist_ok=True)
        shot = out_dir / "frame.png"
        cv2.imwrite(str(shot), seed)
        track["msg"] = f"grounding {caption!r}..."
        t0 = time.time()
        raw = backend["be"].generate(str(shot), caption)
        vlm_s = time.time() - t0
        box = parse_bbox(raw)
        if box is None:
            track["msg"] = f"NO_MATCH in {vlm_s:.1f}s (raw {raw!r:.40})"
            return

        h, w = seed.shape[:2]
        seed_box = _pixels(box, w, h)
        track["box"] = seed_box            # stale, but shows immediately
        track["msg"] = f"grounded in {vlm_s:.1f}s, catching up..."

        # The box describes frame seed_n; the world is already ~vlm_s*CAM_HZ frames
        # past it. Replay the backlog to drag the track into the present, THEN go
        # live on the same carry object (P5.1 idle_catchup -> coverage_realtime).
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / CARRY_DIR))
        import torch
        from sam2.sam2_video_predictor import SAM2VideoPredictor
        from stream_carry import MODEL, StreamCarry

        if backend.get("pred") is None:
            backend["pred"] = SAM2VideoPredictor.from_pretrained(MODEL)
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            carry = StreamCarry(backend["pred"], seed[:, :, ::-1], seed_box)
            cursor, caught_at = seed_n, None
            while not stop.is_set():
                with frame_lock:
                    pending = [(n, f) for n, f in backlog if n > cursor]
                    live_n = latest["n"]
                if not pending:
                    time.sleep(0.01)
                    continue
                # behind: skip ahead by the stride. caught up: take every frame.
                n, frame = pending[min(len(pending), CARRY_STRIDE) - 1]
                _, b = carry.step(frame[:, :, ::-1])
                cursor = n
                track["lag"] = live_n - cursor
                if b is not None and cam["sensor"] is not None:
                    track["box"] = [int(v) for v in b]
                    track["actor"] = match_actor(client.get_world(),
                                                 cam["sensor"].get_transform(),
                                                 track["box"])
                    track["hits"] += track["actor"] is not None
                    track["steps"] += 1
                if caught_at is None and track["lag"] <= 1:
                    caught_at = time.time() - t0
                    track["msg"] = (f"vlm {vlm_s:.1f}s + catchup "
                                    f"{caught_at - vlm_s:.1f}s, now live")
                elif caught_at is not None:
                    # lock% is the honest signal: box on a real car, or drifted
                    track["msg"] = (f"tracking, lag {track['lag']}, lock "
                                    f"{track['hits']}/{track['steps']}")
        track["msg"] = "stopped"

    grow = tk.Frame(root)
    grow.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 6))
    tk.Label(grow, text="follow").pack(side=tk.LEFT)
    caption_entry = tk.Entry(grow, width=28)
    caption_entry.insert(0, "the red car")
    caption_entry.pack(side=tk.LEFT, padx=(4, 0))
    gstatus = tk.Label(grow, text="", anchor=tk.W)

    def do_follow(_event=None):
        if track["stop"] is not None:
            track["stop"].set()          # one target at a time
        track["stop"] = threading.Event()
        track["box"] = None
        threading.Thread(target=follow, daemon=True,
                         args=(caption_entry.get(), track["stop"])).start()

    def do_drop():
        if track["stop"] is not None:
            track["stop"].set()
        track["box"], track["msg"] = None, "dropped"

    caption_entry.bind("<Return>", do_follow)
    tk.Button(grow, text="follow", command=do_follow).pack(side=tk.LEFT, padx=(4, 0))
    tk.Button(grow, text="drop", command=do_drop).pack(side=tk.LEFT, padx=(4, 0))
    gstatus.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(16, 0))

    # Live feed with the track drawn on it. In-memory PPM into PhotoImage runs at
    # ~115 FPS (no PIL, no disk); a PNG-per-frame round-trip does not. The image
    # MUST stay referenced in `preview` -- a local gets collected and the label
    # renders blank with no error, the silent failure this repo keeps hitting.
    preview = {"live": None, "feed": None, "ln": -1, "fn": -1,
               "t": time.time(), "n0": 0, "fps": 0.0}
    # grid, not pack: the weights are what make a resize redistribute the space.
    # 3:1 keeps the flown view dominant and the Jetson feed a thumbnail at any size.
    views = tk.Frame(root, bg="#1e1e1e")
    views.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    # the thumbnail is a FIXED width, not a fraction: a 3:1 weight handed it 500 px
    # on a 2000 px window, which is not a thumbnail. Big view takes all the slack.
    views.columnconfigure(0, weight=1)
    views.columnconfigure(1, weight=0, minsize=THUMB_W + 12)
    views.rowconfigure(0, weight=1)
    big = tk.Label(views, bg="#1e1e1e")
    big.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
    col = tk.Frame(views, bg="#1e1e1e")
    col.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)
    tk.Label(col, text=f"what the Jetson sees -- {CAM_HZ:.0f} Hz, VLM + tracker",
             bg="#1e1e1e", fg="#dddddd").pack(anchor=tk.W)
    small_lbl = tk.Label(col, bg="#1e1e1e")
    small_lbl.pack(fill=tk.BOTH, expand=True, anchor=tk.N)

    def _photo(bgr, widget, drop=0, fixed_w=None):
        """Fit the frame to the widget's current size, keep aspect. Grows AND shrinks.

        Shrink-only left the 960x540 frame floating in the middle of a maximised
        window -- on a big screen the whole point is that the picture gets bigger.
        """
        h, w = bgr.shape[:2]
        if fixed_w is not None:
            s = fixed_w / w
        else:
            s = min(max(widget.winfo_width() - 8, 120) / w,
                    max(widget.winfo_height() - drop, 80) / h)
        if abs(s - 1.0) > 0.01:
            # AREA is the right kernel down, LINEAR up; AREA upscaling is blocky
            bgr = cv2.resize(bgr, (max(int(w * s), 1), max(int(h * s), 1)),
                             interpolation=cv2.INTER_AREA if s < 1
                             else cv2.INTER_LINEAR)
        rgb = np.ascontiguousarray(bgr[:, :, ::-1])
        h, w = rgb.shape[:2]
        return tk.PhotoImage(data=b"P6\n%d %d\n255\n" % (w, h) + rgb.tobytes(),
                             format="PPM")

    def show_preview():
        with frame_lock:
            lf = None if live["n"] == preview["ln"] else live["bgr"]
            ff = None if latest["n"] == preview["fn"] else latest["bgr"]
            if lf is not None:
                lf, preview["ln"] = lf.copy(), live["n"]
            if ff is not None:
                ff, preview["fn"] = ff.copy(), latest["n"]
        box, locked = track["box"], track["actor"] is not None
        if lf is not None:
            # the box is up to one feed period stale here -- it was measured on
            # the 5 Hz frame, drawn on the 60 Hz one. Same camera, so it lines up.
            draw_overlay(lf, box, caption_entry.get(), locked,
                         scale=lf.shape[1] / CAM_W)
            preview["live"] = _photo(lf, big)
            big.config(image=preview["live"])
        if ff is not None:
            draw_overlay(ff, box, "", locked)
            preview["feed"] = _photo(ff, col, fixed_w=THUMB_W)
            small_lbl.config(image=preview["feed"])
        # measured delivery rate, not the requested one -- headless or not, a
        # GPU-contended sensor quietly ships fewer frames than sensor_tick asks for
        dt = time.time() - preview["t"]
        if dt >= 1.0:
            with frame_lock:
                n = live["n"]
            preview["fps"] = (n - preview["n0"]) / dt
            preview["t"], preview["n0"] = time.time(), n
        gstatus.config(text=f"{preview['fps']:.0f} Hz live  {track['msg']}")

    def on_press(e):
        # paused means paused: the spectator still accepts set_transform while the
        # world is frozen, so keys held now would fly it blind and the view would
        # jump on resume
        if paused["on"]:
            return
        k = e.keysym.lower()
        if k in pending:  # autorepeat, not a real release
            root.after_cancel(pending.pop(k))
        held.add(k)

    def on_release(e):
        # X11 autorepeat fires release/press pairs ~30 ms apart, so a release
        # only counts if no repeat press follows it. Without this the key set
        # empties between repeats and the motion stutters.
        k = e.keysym.lower()
        pending[k] = root.after(50, lambda: (held.discard(k), pending.pop(k, None)))

    # click either view to take the stick; the green border is the only "am I
    # flying?" signal, so losing focus must also drop every held key or the
    # spectator keeps drifting after you click away.
    for w in (big, small_lbl):
        w.config(takefocus=True, highlightthickness=3,
                 highlightbackground="#1e1e1e", highlightcolor="#3fbf5f")
        w.bind("<Button-1>", lambda e, w=w: w.focus_set())
        w.bind("<FocusOut>", lambda e: held.clear())
        w.bind("<KeyPress>", on_press)
        w.bind("<KeyRelease>", on_release)

    DT = 1 / 60
    MOVE = {"w": (1, 0, 0), "s": (-1, 0, 0), "a": (0, -1, 0), "d": (0, 1, 0),
            "e": (0, 0, 1), "q": (0, 0, -1)}
    LOOK = {"left": (-1, 0), "right": (1, 0), "up": (0, 1), "down": (0, -1)}
    cam = {"spec": client.get_world().get_spectator(), "t": None, "sensor": None,
           "res": (CAM_W, CAM_H)}

    # The spectator is a pose, not a sensor -- it has no pixels to grab. Attaching
    # an RGB camera to it makes the flown view readable, and attach_to means the
    # pose follows for free, including when CarlaUE4's own viewport WASD moves it.
    live = {"bgr": None, "n": 0}       # 60 Hz, what the operator flies
    latest = {"bgr": None, "n": 0}     # 5 Hz, what the Jetson is handed
    frame_lock = threading.Lock()
    # Backlog for the catch-up: the VLM grounds frame N but the world is at N+20 by
    # the time the box lands, so the tracker replays N..now instead of starting
    # stale. 120 frames @5 Hz = 24 s of history, ~190 MB.
    backlog = collections.deque(maxlen=120)

    def on_image(img):
        buf = np.frombuffer(img.raw_data, np.uint8).reshape(img.height, img.width, 4)
        bgr = np.ascontiguousarray(buf[:, :, :3])
        with frame_lock:
            live["bgr"] = bgr
            live["n"] += 1
            # the Jetson only gets every FEED_EVERY-th frame -- one camera, two
            # rates -- and always at CAM_W x CAM_H, so VLM/tracker cost and the
            # pixel coords of every box stay put when the window is resized
            if live["n"] % FEED_EVERY == 0:
                latest["bgr"] = (bgr if bgr.shape[1] == CAM_W else
                                 cv2.resize(bgr, (CAM_W, CAM_H),
                                            interpolation=cv2.INTER_AREA))
                bgr = latest["bgr"]
                latest["n"] += 1
                backlog.append((latest["n"], latest["bgr"]))

    def attach_camera():
        world = client.get_world()
        if cam["sensor"] is not None:
            cam["sensor"].stop()
            cam["sensor"].destroy()
        w, h = cam["res"]
        bp = world.get_blueprint_library().find("sensor.camera.rgb")
        bp.set_attribute("image_size_x", str(w))
        bp.set_attribute("image_size_y", str(h))
        bp.set_attribute("fov", str(CAM_FOV))
        bp.set_attribute("sensor_tick", str(1.0 / LIVE_HZ))
        cam["sensor"] = world.spawn_actor(bp, carla.Transform(),
                                          attach_to=cam["spec"])
        cam["sensor"].listen(on_image)

    attach_camera()

    def retarget_res():
        """Render at the size we display at. Upscaling a 960x540 sensor into a
        maximised window is what looked like a stuck resolution -- it was just
        blur. Snapped to 16:9 and to 32 px steps so a slow drag is not 40 respawns.
        """
        resize["job"] = None
        if big.winfo_width() < 100:
            return                       # not laid out yet, winfo_width is 1
        want_w = max(int(big.winfo_width() / 32) * 32, 640)
        want_w = min(want_w, MAX_CAM_W)
        want = (want_w, int(want_w * 9 / 16) // 2 * 2)
        if want == cam["res"] or busy["on"]:
            return
        cam["res"] = want
        try:
            attach_camera()
            status.config(text=f"render {want[0]}x{want[1]}")
        except RuntimeError as e:
            status.config(text=f"resize failed: {e}")

    def on_resize(_e=None):
        # debounce: <Configure> fires per pixel of a drag, and each respawn is an
        # actor destroy + spawn round-trip
        if resize["job"] is not None:
            root.after_cancel(resize["job"])
        resize["job"] = root.after(400, retarget_res)

    root.bind("<Configure>", on_resize)

    def fly():
        if busy["on"]:
            return  # mid-load the spectator handle is stale, set_transform raises
        if not held:
            cam["t"] = None  # resync next time, the view may have moved elsewhere
            return
        # keep the pose local: get_world()/get_transform() are RPC round-trips
        # and doing them per frame is what made this choppy. Only push.
        if cam["t"] is None:
            cam["t"] = cam["spec"].get_transform()
        t = cam["t"]
        fwd, right, up = (t.get_forward_vector(), t.get_right_vector(),
                          t.get_up_vector())
        step = speed.get() * DT
        for k in held & MOVE.keys():
            f, r, u = MOVE[k]
            t.location += (fwd * f + right * r + up * u) * step
        for k in held & LOOK.keys():
            dyaw, dpitch = LOOK[k]
            t.rotation.yaw += dyaw * 90 * DT
            t.rotation.pitch = max(-89, min(89, t.rotation.pitch + dpitch * 90 * DT))
        cam["spec"].set_transform(t)

    # Tk blocks in C, so SIGINT only lands while Python bytecode runs -- the
    # tick gives the interpreter that chance, and flies the spectator.
    # ponytail: no cleanup to do, the client holds no world state.
    # SIGTERM too: a kill while paused would leave the server in sync mode with
    # nothing ticking it, which hangs the next client that connects
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: unpause_on_exit())
    def tick():
        fly()
        show_preview()
        root.after(int(DT * 1000), tick)
    tick()

    if args.selftest:
        root.withdraw()  # runs the real widgets, shows no window
        root.after(100, lambda: selftest(root, client, spawned, bg,
                                         spawn_vehicles, spawn_walkers, clear))

    try:
        root.mainloop()
    except KeyboardInterrupt:
        root.destroy()


def selftest(*a):
    # a failing assert inside a Tk callback only prints, the loop keeps running
    try:
        _selftest(*a)
    except Exception:
        traceback.print_exc()
        a[0].destroy()
        raise SystemExit(1)


def _selftest(root, client, spawned, bg, spawn_vehicles, spawn_walkers, clear):
    """Spawn through the real buttons, assert the actors exist and move."""
    # the worker-thread hop is the one bit the button path adds, so prove a
    # result actually lands back on the widget instead of dying in the thread
    probe = tk.Label(root)
    bg(probe, lambda: "probe ok")
    for _ in range(50):
        root.update()
        if probe.cget("text") == "probe ok":
            break
        time.sleep(0.05)
    assert probe.cget("text") == "probe ok", f"bg lost it: {probe.cget('text')!r}"

    world = client.get_world()
    spawn_vehicles(10)
    spawn_walkers(10)
    ids = list(spawned)
    cars = [a for a in world.get_actors(ids) if a.type_id.startswith("vehicle")]
    peds = [a for a in world.get_actors(ids) if a.type_id.startswith("walker.")]
    assert len(cars) >= 5, f"only {len(cars)} vehicles spawned"
    assert len(peds) >= 5, f"only {len(peds)} walkers spawned"

    before = {a.id: a.get_location() for a in cars + peds}
    time.sleep(4.0)
    def movers(group):
        return sum(1 for a in group if before[a.id].distance(a.get_location()) > 0.5)
    drove, walked = movers(cars), movers(peds)
    print(f"spawned {len(cars)} cars ({drove} drove), "
          f"{len(peds)} walkers ({walked} walked) in 4 s")
    # counted separately: a passing total can hide one whole class standing still
    assert drove >= 3, f"only {drove} cars moved -- autopilot not running"
    assert walked >= 3, f"only {walked} walkers moved -- AI controllers not running"

    clear()
    # get_actors() keeps listing destroyed actors and Actor.is_alive is a stale
    # client-side cache -- the world snapshot is the only server truth here.
    snap = world.get_snapshot()
    left = [a for a in world.get_actors(ids)
            if a.type_id.startswith(("vehicle", "walker")) and snap.find(a.id)]
    assert not left, f"{len(left)} actors survived clear"
    print("ok")
    root.destroy()


if __name__ == "__main__":
    main()
