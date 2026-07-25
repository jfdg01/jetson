#!/usr/bin/env python3
"""Live demo panel for the whole deployed stack: fly it, designate, watch it follow.

Every stage is live -- no replay, no recorded numbers, no oracle box. CARLA renders
on the 3090, ArduCopter SITL is the physics, and BOTH models run on the Orin
(Qwen2-VL-2B Q8_0 grounding over ssh, SAM2 carry over the ssh-stdio bridge).

Three orthogonal mode switches, because they are the three questions the thesis
asks and each one is a different demo:

  PILOT     spectator | copter
            spectator flies a camera on a stick -- perception in isolation, any view
            you like, no flight dynamics. copter arms an ArduCopter SITL and slaves
            the camera to the pose it reports (P6.1), so the pixels are a consequence
            of the vehicle's own motion.
  ACQUIRE   warm | cold
            warm maintains a track from the moment you designate and DELIVERS it on
            command (P5.1/P6.2-DELIVERY: maintain-and-deliver). cold does nothing
            until the command, then grounds under time pressure (E18/R-34: the
            ~4.8 s acquire lands the box stale). The `deliver` timing on screen is
            that comparison, measured live.
  FOLLOW    manual | assist | auto
            manual = operator has sole authority. assist = the model aims (gimbal
            only, never position). auto = closed loop, the delivered box drives the
            copter through CascadePID -> LOCAL_NED velocity, the same path
            run_p62_flight measured (P6.2). auto needs PILOT=copter.

    .venv-ft/bin/python runners/carla_debug_ui.py         # starts CARLA if needed
    .venv-ft/bin/python runners/carla_debug_ui.py --pilot copter    # + SITL

Controls: click the view to take the stick. wasd/qe move, arrows look (gimbal in
copter mode), space pause, t cycles FOLLOW, g delivers, Shift-click designates a car.
See runners/CARLA_DEBUG_UI.md.
"""
import argparse
import collections
import json
import math
import os
import random
import re
import signal
import statistics
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
import traceback
from pathlib import Path

import carla
from PIL import Image, ImageTk
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
# Same seed every run, so "the scene" means one scene across sessions. Only holds
# on a world with no other traffic in it -- an occupied spawn point is rejected
# server-side and silently drops that car, so re-spawn on top of an old fleet is
# not the same fleet. Startup loads a fresh server, which is the case that counts.
SPAWN_SEED = 1234
AUTO_SPAWN = 50   # vehicles spawned once on startup; --auto-spawn 0 to skip
# On-Orin SAM2 carry runs ~6-10 Hz (image_size 512-640, measured), the feed 5 Hz.
# Replaying EVERY buffered frame drains at only (carry_hz - CAM_HZ) ~= a few frames/s,
# so a ~4.5 s grounding backlog took seconds to clear and never felt live. Instead,
# when behind, JUMP toward the newest pending frame: SAM2 re-anchors by APPEARANCE
# across the gap (it is a video segmenter, not a per-frame detector), and CARLA nadir
# targets move <~10 px over the whole lag, so a big jump costs ~nothing. The cap stops
# one step from skipping so far it loses a genuinely fast target. Steady-state this
# self-regulates: when carry outpaces the feed there is <=1 pending and it takes it
# (smooth); when it falls behind it jumps back to live. P5.1's idle_catchup, sharpened.
CATCHUP_JUMP = 12
# 1080p30 cap: a 2144x1206 sensor rendered every frame is more than the 3090 has
# spare while it also drives CARLA. (Grounding + carry are on the Orin now, not here.)
MAX_CAM_W = 1920
THUMB_W = 300          # what the Jetson sees stays a thumbnail at any window size
CARLA_SH = "/home/gara/carla/CARLA_0.9.16/CarlaUE4.sh"
# ASSIST mode: yaw/pitch to keep the tracked box centred. The knob is the fraction
# of the OUTSTANDING correction spent per second, so the view eases in and never
# snaps -- 3.0 spends ~95% of it in a second. Raise it if the camera lags a fast
# target, lower it if a track switch (the box jumping across frame) whips the view.
# ponytail: P only. Add D only if you slow it down enough to ring.
ASSIST_RATE = 3.0
# CHASE: box area is the only range signal we have -- no depth, no target pose.
# Hold it at a setpoint instead of merely reacting to shrinkage: too small and the
# VLM has no pixels to re-ground with, too large and normal relative motion walks
# the target off the frame edge. Forward when it is under size, backward when over.
# 0.012 = a car at ~125 px long edge, ~17 m slant range. Not a guess: the 429-sample
# native arm of experiments/2026-06-30-roi-sr-upscale puts grounding IoU@0.25 at
# 59.1% under 30 px, 88.9% at 90-150 px and 93.5% past 150 -- the knee is 90-150 and
# everything above it costs range for +4.6pp. Calibrated FOR CARS: this is an area
# setpoint, so a fixed fraction means a different standoff per target class (a truck
# is held at 33 m, a pedestrian at 6 m). See CARLA_DEBUG_UI.md.
CHASE_TARGET_FRAC = 0.012
CHASE_SPEED = 30.0          # m/s cap along the boresight, either direction
# Min altitude the chase is allowed to reach, and how far above it the escape
# climbs once breached. CARLA world z, and Town10's ground is ~0, so it doubles
# as AGL. ponytail: flat-ground assumption. Raycast the terrain if a map with
# real relief shows up.
CHASE_FLOOR = 5.0
# One palette for the whole panel. DARK matches the video panes, which were dark
# from the start; ACCENT is the focus ring and doubles as the "box is on target"
# green so the two read as the same signal.
DARK, DARK_HI, TEXT, ACCENT, ALERT = "#1e1e1e", "#2d2d2d", "#e0e0e0", "#3fbf5f", "#ff6b6b"
CHASE_CLIMB = 15.0
CHASE_HIST = 5              # measurements median-filtered into one area reading
# Error is in LOG area because area falls as 1/d^2: one log unit is a fixed ratio
# of range whether the target is near or far, so a single gain behaves the same
# everywhere. GAIN is m/s per log unit; 0.15 is +-16% of area, inside the mask's
# own breathing, and without it the drone hunts back and forth on nothing.
CHASE_GAIN = 5.0
CHASE_DEADBAND = 0.15
# How long a latched speed survives without a new box. One 5 Hz feed period is
# 0.2 s, so this tolerates a couple of dropped measurements and no more.
CHASE_STALE = 0.6
REMOTE_DIR = "/home/jfdg/grounding"
REMOTE_GGUF = f"{REMOTE_DIR}/phase3-terse100eos-1024-q8_0.gguf"
REMOTE_MMPROJ = f"{REMOTE_DIR}/mmproj-phase3-terse100eos-1024-f16.gguf"

# EXP-3 "click -> ground -> track", BOTH on the Orin. The point-crop rich-caption
# grounder + the SAM2 carry both run on the Jetson: grounding over JetsonBackend
# (already ssh), carry over the ssh-stdio bridge that lives on the Orin at
# ~/sam2-bench/carry_ssh_bridge.py. No SAM2 on the 3090 (constraint: the 3090 runs
# only the CARLA simulator). Defaults are the resolutions EXP-1/EXP-2/EXP-3 found:
# rich-caption grounding wants the 1024 crop (256 starves colour on a nadir car),
# SAM2 carry is 99.4% of full IoU at image_size 640 for 2.5x the throughput.
EXP3_DIR = Path(__file__).resolve().parent.parent / "experiments" / "2026-07-24-point-crop-select"
CARRY_BRIDGE = "cd ~/sam2-bench && ./.venv/bin/python -u carry_ssh_bridge.py --image-size {size}"
ORIN_GROUND_RES = 1024
# 512, not EXP-1's adopted 640: the catch-up only converges if the tracker outruns the
# 5 Hz feed. EXP-1's sweep is 8.71 Hz at 512 vs 5.76 at 640 vs 2.34 at 1024, and this
# panel measures 9.3 Hz / 107 ms at 512 live. Costs 512-vs-640 accuracy (median IoU
# 0.780 vs 0.811) -- fine for a demo, which is why no number from here is a result.
ORIN_CARRY_SIZE = 512
_EXP3 = {}

# --- copter pilot mode: the P6.1/P6.2 rig, live -----------------------------
# The spectator is a camera on a stick. The SYSTEM under test flies an ArduCopter
# SITL and slaves the camera to the pose the autopilot reports -- that is the whole
# of P6.1, and it is what makes the pixels a consequence of the control output
# instead of an input to it. Both pilots stay here because they answer different
# questions (see the module docstring).
MAVLINK_URL = "tcp:127.0.0.1:5760"
COPTER_ALT = 45.0        # m AGL. P6.2-DELIVERY flew 45 m nadir. Note G6: q8_0 is
                         # non-discriminative on a car at that range, which is why
                         # the click designator (EXP-3 point crop) exists.
MANUAL_V_MAX = 12.0      # m/s cap on operator velocity commands (the fly slider
                         # goes to 300, which is a spectator speed, not a copter one)
GIMBAL_RATE = 90.0       # deg/s the arrow keys slew the gimbal in copter mode
# A GUIDED velocity setpoint expires after ~3 s of silence and the copter drops to
# loiter, so it must be resent -- but not at the 60 Hz render tick. 10 Hz is twice
# the feed rate and a fiftieth of the MAVLink traffic.
CMD_HZ = 10.0
# AUTO follow gains. CascadePID's default kp_lat=0.02 only holds a target under
# dense (20 Hz oracle) delivery; at the on-device carry rate the P-lag lets a moving
# target walk off frame (steady-state offset = v/kp). These are the raised gains the
# P6.2 warm arm flew. ponytail: P only -- add D when it rings, not before.
AUTO_KP_LAT = 0.06
AUTO_MAX_V = 8.0
FOLLOW_MODES = ("manual", "assist", "auto")


def load_exp3():
    """Lazily pull the point-crop grounder + rich caption + ssh-bridge framing.

    One import of select_exp3 sets up its own sys.path and re-exports everything the
    tab needs (rich_caption, roi_reanchor, select_p55, the _send/_recv/_rgb_jpg_arr
    bridge framing, vlm_acquire, _valid, MAX_SIDE, _center_box). Lazy: not paid unless
    the operator uses a tab.
    """
    if not _EXP3:
        if str(EXP3_DIR) not in sys.path:
            sys.path.insert(0, str(EXP3_DIR))
        import select_exp3 as X
        _EXP3["X"] = X
    return _EXP3["X"]


def center_delta(box, w=CAM_W, h=CAM_H, fov=CAM_FOV):
    """Box (pixels of the CAM_W x CAM_H feed) -> (dyaw, dpitch) degrees, in FULL.

    The whole rotation that would put this box in the middle of the frame, not a
    per-tick step -- ease() decides how fast it is actually spent. The feed is
    always CAM_W x CAM_H whatever the window does, so pixel error maps to angle
    through one fixed focal length. +yaw is right in CARLA, +pitch is up, and image
    y grows downward -- hence the sign flip on pitch.
    """
    px, py = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    f = w / (2.0 * math.tan(math.radians(fov) / 2.0))
    return (math.degrees(math.atan2(px - w / 2, f)),
            -math.degrees(math.atan2(py - h / 2, f)))


def ease(remaining, dt):
    """How much of an outstanding correction to spend this tick.

    min(1.0, ...) is what makes this dt-correct AND overshoot-proof in one step: a
    stalled tick spends the whole remainder and stops, it never swings past.
    """
    close = min(1.0, ASSIST_RATE * dt)
    return remaining[0] * close, remaining[1] * close


def chase_speed(areas, frame_area=CAM_W * CAM_H):
    """Recent box areas -> ground speed in m/s. + closes, - backs off, 0 holds.

    Area, not width or height: a box that shrinks in one axis only is usually the
    target turning, not receding. The MEDIAN of the recent measurements, not the
    latest, so one blown-up mask cannot punch the drone across the street --
    median over mean because the failure it guards against is exactly an outlier.
    """
    if len(areas) <= CHASE_HIST or min(areas) <= 0:
        return 0.0                     # not enough history to trust a reading yet
    err = math.log(CHASE_TARGET_FRAC * frame_area / statistics.median(areas))
    if abs(err) < CHASE_DEADBAND:
        return 0.0
    # Scale with RANGE, not with the log error alone: area ~ 1/d^2, so
    # sqrt(target_area/area) = exp(err/2) is exactly how many times further out
    # the target is than the setpoint. A tiny box is a far target and gets a
    # fast approach; a big one is close and gets a gentle one. Without it every
    # range crawled in at the same few m/s and a 300 m target never arrived.
    return max(-CHASE_SPEED, min(CHASE_SPEED,
                                 CHASE_GAIN * err * math.exp(err / 2)))


def floor_climb(z, dt, goal):
    """Vertical metres to add this tick, and the latched goal -> (dz, goal).

    Dipping under CHASE_FLOOR latches a climb to CHASE_FLOOR + CHASE_CLIMB and
    holds it until reached. Latched, not a bare clamp: a nose-down chase is still
    commanding descent, so an escape that stopped the instant it cleared the floor
    would sink straight back and buzz along it.
    """
    if z < CHASE_FLOOR:
        goal = CHASE_FLOOR + CHASE_CLIMB
    if goal is None or z >= goal:
        return 0.0, None
    return min(goal - z, CHASE_SPEED * dt), goal


def manual_velocity(held, v):
    """Held keys -> a LOCAL_NED velocity setpoint (vn, ve, vd) in m/s.

    Copter mode only. The camera is north-up nadir (R-10: yaw never arrives from
    SITL, and rotating a nadir camera reframes nothing), so screen-up IS north and
    the keys map to the world frame directly -- no body-frame rotation to get wrong.
    vd is DOWN-positive, hence `e` (up) being negative.
    """
    vn = (("w" in held) - ("s" in held)) * v
    ve = (("d" in held) - ("a" in held)) * v
    vd = (("q" in held) - ("e" in held)) * v
    return vn, ve, vd


def ensure_sitl(url, wait_s=180):
    """Live pymavlink connection to ArduCopter SITL, launching one if the port is dead.

    Same contract as ensure_carla: never starts a second server on a port that already
    answers, and the launch command is boot_sim's (the P6.1 as-run one) rather than a
    second copy of it here. Returns the connection with LOCAL_POSITION_NED + ATTITUDE
    already requested -- ArduPilot streams neither to a GCS that does not ask, which is
    how a pose consumer ends up rendering a frozen camera.
    """
    import boot_sim
    import sitl_fly_leg as fly
    port = int(url.rsplit(":", 1)[1])
    if not boot_sim.up(port):
        print(f"nothing on {port}: launching ArduCopter SITL "
              f"(~20 s, log runs/sim/sitl.log)", flush=True)
        boot_sim.launch_sitl()
        if not boot_sim.wait(port, "SITL", wait_s):
            raise SystemExit("SITL did not come up -- see runs/sim/sitl.log")
    return fly.connect(url)


def boresight(pitch_deg, yaw_deg):
    """Unit vector along where the camera is LOOKING, pitch included.

    The ground frame was wrong for chase: flying level toward a target that is
    below you closes the ground distance without closing the slant range, so the
    box need not grow. Since ASSIST already parks the target at frame centre,
    the boresight IS the line to the target -- move along it and it gets bigger.
    A nose-down chase therefore descends -- floor_climb() is the min-AGL guard.
    """
    p, y = math.radians(pitch_deg), math.radians(yaw_deg)
    return carla.Location(math.cos(p) * math.cos(y),
                          math.cos(p) * math.sin(y),
                          math.sin(p))


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


# How long the box may sit on the wrong vehicle (or on no vehicle at all) before
# the UI calls it drift. Long enough to ride out an occlusion or a bad frame or
# two, short enough that the operator is not steering a lie: at 5 Hz that is ~25
# consecutive bad measurements, which is not a glitch.
DRIFT_S = 5.0


# How much of the smaller of (tracker box, actor's projected box) must overlap
# before we call it the same vehicle. Low on purpose: a mask clipped by a pole or
# a banner keeps only part of the vehicle, and that is still a lock, not a drift.
MATCH_OVERLAP = 0.30

# How often the carry loop re-runs the identity match (green/red + drift). It is
# the loop's one GIL-heavy step -- projecting 8 verts x ~40 vehicles is ~320 numpy
# calls that block the tk render tick, and per-step it starved the display to ~5 fps
# the moment carry started (the CARLA server itself stayed at ~56 fps). The SAM2 box
# updates every step regardless; identity only needs a few Hz for a 5 s drift window.
MATCH_HZ = 4.0


def actor_box(bbox, cam_tf, actor_tf):
    """An actor's 3D bounding box projected to an axis-aligned pixel box.

    `bbox` is the actor's (constant) local bounding_box, and `actor_tf` its transform
    read from a world SNAPSHOT (one RPC for the whole world). Both are passed in, not
    read off the actor here, because v.bounding_box is a ~10 ms round-trip and this
    runs for every vehicle every carry step -- the caller caches the box (see
    veh_list) and snapshots the transform once."""
    pts = [project(p, cam_tf)
           for p in bbox.get_world_vertices(actor_tf)]
    pts = [p for p in pts if p is not None]
    if len(pts) < 8:                      # partly behind the camera: not a match
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def match_actor(cam_tf, box, vehicles, snap):
    """Which vehicle, if any, the tracker's box is on. None means drifted.

    The correctness check the throughput asserts could not give -- and it only
    reads the world, it draws nothing. Overlays go on the frames we receive, not
    into the engine, so the render stays the render.

    RPC cost matters: this runs every carry step. `vehicles` is a cached list of
    (actor, bounding_box) pairs (see veh_list) and `snap` is one world snapshot that
    carries every transform, so the loop makes ZERO per-actor round-trips -- neither
    v.get_transform() (was ~50-80 RPCs/step) nor v.bounding_box (was ~10 ms each,
    ~540 ms/step). snap.find(id) is a local lookup.

    Overlap, not point-in-box: the mesh origin of a truck sits well outside a
    tight box drawn around its cargo body, so the old point test called a
    pixel-perfect lock a drift and never recovered.
    """
    best, best_o = None, MATCH_OVERLAP
    for v, bb in vehicles:
        s = snap.find(v.id)
        if s is None:                     # actor gone since the list was fetched
            continue
        a = actor_box(bb, cam_tf, s.get_transform())
        if a is None:
            continue
        iw = min(a[2], box[2]) - max(a[0], box[0])
        ih = min(a[3], box[3]) - max(a[1], box[1])
        if iw <= 0 or ih <= 0:
            continue
        smaller = min((a[2] - a[0]) * (a[3] - a[1]),
                      (box[2] - box[0]) * (box[3] - box[1]))
        o = iw * ih / max(1.0, smaller)
        if o > best_o:
            best, best_o = v, o
    return best


def draw_overlay(frame, box, label, locked, scale=1.0, delivered=True):
    """Box + caption onto a copy of the received frame. Green locked, red adrift.

    An UNDELIVERED box (WARM: maintained, nobody has asked for it yet) is drawn grey
    and hollow-thin. That is not decoration -- the whole warm-start claim is that the
    system tracks things it has not been asked about, so the operator has to be able
    to see at a glance which boxes are its own housekeeping and which one is theirs.
    """
    if box is None:
        return frame
    if not delivered:
        c, th, label = (150, 150, 150), 1, f"maintaining: {label}"
    else:
        c = (0, 255, 0) if locked else (0, 0, 255)
        th = max(1, int(2 * scale))
    p = [int(v * scale) for v in box]
    cv2.rectangle(frame, (p[0], p[1]), (p[2], p[3]), c, th)
    cv2.putText(frame, label, (p[0], max(14, p[1] - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5 * scale, c, 1)
    return frame


def _f(fmt, v):
    """"deliver {:.2f} s" + None -> "deliver --". A missing stage reads as missing.

    Not 0.0 and not blank: a stage that has not run yet and a stage that ran in no
    time look identical on a status strip otherwise, and one of those is a bug.
    """
    return fmt.format(v) if v is not None else fmt.split("{")[0] + "--"


def ensure_carla(host, port, sh, wait=300):
    """Connect, or start a headless CARLA and wait for its RPC to answer.

    Headless is the right default here: the UI never reads the viewport, it reads
    an attached RGB sensor, so the on-screen window was pure GPU cost.

    Returns (client, proc). proc is None when CARLA was already running -- closing
    the UI kills only a server it started itself, never one you launched.
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
        return got, None
    # A CARLA that crashed or was half-killed keeps the RPC port LISTENING while
    # answering nothing. Spawning on top of that gives a server that cannot bind,
    # and the wait loop below then burns the full timeout for no reason -- which is
    # exactly the "it hangs at 'starting headless CARLA'" symptom. A healthy server
    # answers in milliseconds, so a bound-but-silent port is dead by definition:
    # clear it, but only if it really is a CARLA, never some unrelated service.
    pid, name = port_owner(port)
    if pid is not None:
        if "CarlaUE4" not in name:
            raise SystemExit(f"port {port} is held by {name} (pid {pid}), not CARLA")
        print(f"clearing dead CARLA on {port} (pid {pid}, listening but not "
              f"answering)", flush=True)
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                break
            for _ in range(80):          # 8 s per signal
                time.sleep(0.1)
                if port_owner(port)[0] != pid:
                    break
            else:
                continue
            break
        if port_owner(port)[0] == pid:
            raise SystemExit(f"could not free port {port} from pid {pid}")
    if not Path(sh).exists():
        raise SystemExit(f"nothing on {host}:{port} and no CarlaUE4.sh at {sh}")
    print(f"starting headless CARLA: {sh}", flush=True)
    # own session: CarlaUE4.sh forks the actual UE4 binary, so the thing to signal
    # on exit is the whole process group, not the launcher shell that outlives it
    proc = subprocess.Popen([sh, "-RenderOffScreen", "-quality-level=Epic",
                             f"-carla-rpc-port={port}", "-ExecCmds=t.MaxFPS 30"],
                            cwd=str(Path(sh).parent), start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + wait
    while time.time() < deadline:
        got = try_connect(5.0)
        if got is not None:
            print("CARLA up", flush=True)
            return got, proc
        # the launcher exiting means the server is never coming: fail in seconds
        # with the reason, instead of sitting out the whole timeout
        if proc.poll() is not None:
            raise SystemExit(f"CarlaUE4.sh exited with {proc.returncode} while "
                             f"starting -- run it by hand to see why")
        time.sleep(2.0)
    stop_carla(proc)          # do not leave a half-booted server behind
    raise SystemExit(f"CARLA did not answer on {port} within {wait}s")


def group_alive(pgid):
    """Is anything still in this process group? signal 0 = existence check only."""
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True          # exists, just not ours to signal


def port_owner(port):
    """(pid, name) of whoever is LISTENING on port, or (None, None).

    ss over lsof/psutil: it is installed everywhere and this needs one line of it.
    """
    try:
        out = subprocess.run(["ss", "-lptnH", f"sport = :{port}"],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None, None
    m = re.search(r'users:\(\("([^"]+)".*?pid=(\d+)', out)
    return (int(m.group(2)), m.group(1)) if m else (None, None)


def apply_dark(root):
    """Dark chrome to match the video panes, which were #1e1e1e from the start.

    A white control strip around a night-lit render is what the eye adapts to, and
    then the frame you are supposed to be judging looks underexposed.

    tk_setPalette does every classic Tk widget in one call, including ones already
    built. ttk is a separate world: its default theme ignores colour options
    outright, so the Combobox needs "clam" plus its dropdown styled through the
    option database -- that list is a plain Tk Listbox the theme never reaches.
    """
    root.tk_setPalette(background=DARK, foreground=TEXT,
                       activeBackground=DARK_HI, activeForeground=TEXT,
                       highlightBackground=DARK, highlightColor=ACCENT,
                       selectBackground=ACCENT, selectForeground=DARK,
                       insertBackground=TEXT, troughColor=DARK_HI,
                       disabledForeground="#6a6a6a")
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TCombobox", fieldbackground=DARK_HI, background=DARK_HI,
                    foreground=TEXT, arrowcolor=TEXT, bordercolor=DARK_HI)
    style.map("TCombobox", fieldbackground=[("readonly", DARK_HI)],
              selectbackground=[("readonly", DARK_HI)],
              selectforeground=[("readonly", TEXT)])
    # the two-tab strip is ttk too, so the clam theme paints it -- match the chrome
    style.configure("TNotebook", background=DARK, borderwidth=0)
    style.configure("TNotebook.Tab", background=DARK, foreground=TEXT,
                    padding=(10, 4), borderwidth=0)
    style.map("TNotebook.Tab", background=[("selected", DARK_HI)],
              foreground=[("selected", TEXT)])
    style.configure("TFrame", background=DARK)
    for k, v in (("background", DARK_HI), ("foreground", TEXT),
                 ("selectBackground", ACCENT), ("selectForeground", DARK)):
        root.option_add(f"*TCombobox*Listbox.{k}", v)
    # The palette paints one background everywhere, which loses the two places a
    # flat dark UI needs contrast: a text field has to look like a hole you can type
    # in, and an unchecked box defaults to a white square that grabs the eye harder
    # than anything on screen. Both only reach widgets built after this call.
    for cls in ("Entry", "Spinbox"):
        root.option_add(f"*{cls}.background", DARK_HI)
        root.option_add(f"*{cls}.highlightBackground", DARK_HI)
    root.option_add("*Checkbutton.selectColor", DARK_HI)


def reload_argv(argv, pgid):
    """argv for a hot reload's re-exec.

    Two edits. Auto-spawn goes to 0: the old process's cars are still in the world
    (they live in the server, not in us), so respawning would stack another batch
    every reload. And the server's process group rides along, because execv keeps
    our PID -- the group is still ours to signal -- but not our Popen object.
    """
    out, skip = [], False
    for a in argv:
        if skip:
            skip = False
            continue
        if a in ("--auto-spawn", "--adopt-pgid"):
            skip = True
        elif not a.startswith(("--auto-spawn=", "--adopt-pgid=")):
            out.append(a)
    out += ["--auto-spawn", "0"]
    return out + (["--adopt-pgid", str(pgid)] if pgid else [])


def stop_carla(proc):
    """TERM the server's process group, then KILL what ignored it.

    Waiting on `proc` is the trap this function was written around: proc is the
    CarlaUE4.sh launcher, a /bin/sh that dies the instant it is signalled, while
    the CarlaUE4-Linux-Shipping binary it forked takes seconds -- or never does.
    Returning when the SHELL exits left that binary orphaned, still holding the RPC
    port but no longer answering it, so the next launch found a dead socket, started
    a second server that could not bind, and hung in ensure_carla's wait loop.
    So: reap the launcher, then wait on the GROUP, and escalate for real.
    """
    if proc is None:
        return
    if isinstance(proc, int):
        # adopted across a hot reload: we have the group but not the Popen, so the
        # launcher shell is reaped by number instead of by object
        pgid = proc

        def reap():
            try:
                os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                pass
    else:
        try:
            pgid = os.getpgid(proc.pid)
        except ProcessLookupError:
            return
        reap = proc.poll
    print("stopping CARLA", flush=True)
    for sig, grace in ((signal.SIGTERM, 8.0), (signal.SIGKILL, 5.0)):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return
        deadline = time.time() + grace
        while time.time() < deadline:
            reap()           # reap the launcher, else its zombie counts as "alive"
            if not group_alive(pgid):
                return
            time.sleep(0.1)
    print(f"WARNING: CARLA process group {pgid} survived SIGKILL", flush=True)


_TM = []


def traffic_manager(client):
    """The one traffic manager for this process.

    get_trafficmanager() does not fetch a TM, it *creates* an RPC server on
    port 8000. A second carla_debug_ui.py against the same CARLA finds the
    port already owned by the first and raises 'bind error' -- from whatever
    button happened to call it, which on the Tk main thread is a raw traceback
    and a dead button. One acquire, checked at startup, turns that into a
    sentence.
    """
    if not _TM:
        try:
            _TM.append(client.get_trafficmanager())
        except RuntimeError as e:
            raise SystemExit(
                "traffic-manager port 8000 is busy -- another carla_debug_ui.py "
                f"is already running against this server ({e})") from e
    return _TM[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--out", default="runs/carla-ui",
                    help="where grounded overlays are written")
    ap.add_argument("--carla", default=CARLA_SH,
                    help="CarlaUE4.sh to launch if nothing answers on the port")
    ap.add_argument("--auto-spawn", type=int, default=AUTO_SPAWN,
                    help="vehicles to spawn on startup (0 = none)")
    ap.add_argument("--pilot", choices=("spectator", "copter"), default="spectator",
                    help="spectator = fly a camera on a stick; copter = arm SITL and "
                         "slave the camera to the pose it reports (P6.1)")
    ap.add_argument("--mavlink-url", default=MAVLINK_URL)
    ap.add_argument("--alt", type=float, default=COPTER_ALT,
                    help="copter takeoff altitude, m AGL")
    ap.add_argument("--adopt-pgid", type=int, default=0,
                    help="internal: server process group inherited from a hot reload")
    ap.add_argument("--clean-world", action="store_true",
                    help="destroy every vehicle/walker/camera in the world at startup, "
                         "including actors this process did not spawn (recovers a world "
                         "polluted by a crashed or leaky earlier run)")
    ap.add_argument("--acquire", choices=("warm", "cold"), default="warm",
                    help="warm = maintain from designation and deliver on command; "
                         "cold = the designation is the command (the stale-box arm)")
    ap.add_argument("--designate", choices=("vlm", "oracle"), default="vlm",
                    help="seed the carry from the deployed VLM, or from CARLA's projected "
                         "box (P6.2-DELIVERY's ORACLE designation scope)")
    ap.add_argument("--smoke", type=float, default=0.0, metavar="SECONDS",
                    help="unattended live run: designate the car nearest frame centre, "
                         "deliver, AUTO-follow for SECONDS, dump an overlay PNG, exit")
    ap.add_argument("--selftest", action="store_true",
                    help="spawn, check they move, clear, exit")
    args = ap.parse_args()

    client, carla_proc = ensure_carla(args.host, args.port, args.carla)
    # ensure_carla returns None for a server it did not start, which after a hot
    # reload is our own from one execv ago -- take it back so the last exit still
    # cleans up instead of orphaning it
    if carla_proc is None and args.adopt_pgid and group_alive(args.adopt_pgid):
        carla_proc = args.adopt_pgid
    client.set_timeout(60.0)  # load_world blocks for ~10-30s
    traffic_manager(client)   # fail here, not on the first button press
    # basename only: get_available_maps returns /Game/Carla/Maps/Town10HD_Opt
    maps = sorted(m.split("/")[-1] for m in client.get_available_maps())

    root = tk.Tk()
    root.title("CARLA debug")
    apply_dark(root)
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

    def clean_world():
        """Destroy EVERY traffic actor and camera in the world, not just ours.

        `clear` is deliberately limited to our own ids, which is right on exit and
        useless for recovery: a run that crashed, or any older build that leaked, leaves
        cars nobody owns, and CARLA reuses spawn points -- so the next spawn stacks
        duplicates on top of them and the scene stops being the scene you asked for.
        Opt-in (--clean-world) because these actors may belong to another client."""
        world = client.get_world()
        port = traffic_manager(client).get_port()
        mine = cam["sensor"].id if cam["sensor"] is not None else None
        doomed = [a for a in world.get_actors()
                  if (a.type_id.split(".")[0] in ("vehicle", "walker", "controller")
                      or a.type_id.startswith("sensor.camera")) and a.id != mine]
        for a in doomed:
            try:
                if a.type_id.startswith("controller"):
                    a.stop()
                elif a.type_id.startswith("vehicle"):
                    a.set_autopilot(False, port)   # see clear(): TM + dead actor aborts us
            except RuntimeError:
                pass
        world.wait_for_tick()
        client.apply_batch_sync([carla.command.DestroyActor(a.id) for a in doomed], True)
        world.wait_for_tick()
        spawned.clear()
        left = sum(1 for a in client.get_world().get_actors()
                   if a.type_id.startswith(("vehicle", "walker")))
        return f"clean world: destroyed {len(doomed)}, {left} traffic actors left"
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
        # Deterministic placement: a private Random seeded per call (so click
        # order cannot shift the draw) and blueprints sorted by id (filter()
        # order is not a documented guarantee). Same seed -> same models at the
        # same spawn points, every run.
        # No traffic-manager seed: set_random_device_seed() with vehicles being
        # batch-registered times out 'register_vehicle' and then aborts the
        # client ("Actor could not be found in the registry"), measured on
        # 0.9.16 async mode. Driving is therefore NOT repeatable -- identical
        # starting grid, diverging traffic. Sync mode is what that would need.
        rng = random.Random(SPAWN_SEED)
        bps = sorted(world.get_blueprint_library().filter("vehicle.*"),
                     key=lambda b: b.id)
        points = world.get_map().get_spawn_points()
        rng.shuffle(points)
        # Nearest-to-camera first. Town10HD's spawn points cover the whole map, so a
        # uniform draw of 30 puts ~0 cars inside the ~50 m the nadir camera sees at
        # 45 m: the first clean-world run rendered an empty city and AUTO had nothing
        # to follow. (The earlier runs looked dense only because 190 leaked cars were
        # stacked on reused spawn points.) Shuffle first, then sort, so the draw stays
        # seed-deterministic and ties break the same way every run.
        here = cam["spec"].get_location()
        points.sort(key=lambda p: p.location.distance(here))
        n = min(n, len(points))
        tm_port = traffic_manager(client).get_port()
        batch = [carla.command.SpawnActor(rng.choice(bps), p).then(
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
        port = traffic_manager(client).get_port()
        for a in world.get_actors(spawned):
            if a.type_id.startswith("controller"):
                a.stop()  # stop before destroy or the walker keeps its command
            elif a.type_id.startswith("vehicle"):
                # Destroying a car the traffic manager still drives makes the TM
                # call set_actor_simulate_physics on a gone actor, and that error
                # comes back as an uncaught std::runtime_error that aborts *this*
                # process (core dump, measured at 50 cars on 0.9.16). Hand the
                # car back first, then let the tick land before destroying.
                a.set_autopilot(False, port)
        world.wait_for_tick()
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
    tk.Button(row, text="clear all",     # ours AND anyone else's -- see clean_world
              command=lambda: bg(status, clean_world)).pack(side=tk.LEFT, padx=4)

    # Pause = flip the server into synchronous mode and never tick it. Nothing
    # advances: traffic, physics and the camera all stop, so the last frame just
    # sits there. Resume puts it back to async, which is how the rig normally runs
    # (the sim must free-run at its own pace -- that is the whole point of the
    # separate 5 Hz feed).
    paused = {"on": False}

    def toggle_pause():
        world = client.get_world()
        settings = world.get_settings()
        tm = traffic_manager(client)
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

    # Teardown has exactly one caller: the tick. Everything that wants to quit --
    # the X button, SIGINT, SIGTERM -- only raises this flag. A signal lands in the
    # middle of whatever bytecode is running, which is usually inside tick(), and
    # destroying the widgets from there returns into a half-finished callback that
    # then touches a dead widget: "invalid command name .!frame.!scale".
    closing = {"want": False, "done": False, "reload": False}

    def unpause_on_exit():
        if closing["done"]:
            return
        closing["done"] = True
        # kill the on-Orin carry bridge first: it holds the Jetson GPU, and a window
        # close that skips it leaves carry_ssh_bridge.py running on the device.
        with track_lock:
            if track["stop"] is not None:
                track["stop"].set()
            br = track.get("bridge")
            track["bridge"] = None
        if br is not None:
            try:
                br.stdin.close()
            except Exception:
                pass
            try:
                br.kill()
            except Exception:
                pass
        # Zero the GUIDED setpoint before letting go of the link. A copter left with a
        # live velocity command keeps flying it for ~3 s after the UI is gone; SITL is
        # cheap, but "it flew off after I closed the window" is not a demo.
        if pilot.get("m") is not None and pilot.get("fly") is not None:
            try:
                pilot["fly"].send_velocity(pilot["m"], 0.0, 0.0)
            except Exception:
                pass
        # a server we started dies with the window, so its sync-mode state is moot;
        # one that was already running is someone else's and must be handed back
        # unpaused -- left in sync mode with no ticker it hangs the next client.
        # A reload counts as handing it back: the next process would connect to a
        # sync-mode server with nothing ticking it and hang on the first world call.
        if paused["on"] and (carla_proc is None or closing["reload"]):
            try:
                toggle_pause()
            except RuntimeError:
                pass
        # The camera is an actor in the server, and the server can outlive us -- a
        # reload leaks a sensor that still renders, and a plain exit leaves its
        # callback firing into a finalizing interpreter ("Fatal Python error:
        # PyGILState_Release ... runtime state: finalizing", reproducible on every
        # exit against a server this process did not start).
        try:
            if cam["sensor"] is not None:
                cam["sensor"].stop()
                cam["sensor"].destroy()
                cam["sensor"] = None
        except RuntimeError:
            pass
        # Give the world back the way we found it. A reload deliberately keeps the cars
        # (that is the point of it -- 50 spawns is ~50 round-trips), but a real exit that
        # leaks them poisons the NEXT run: four --smoke runs at 30 cars each left 190
        # vehicles in Town10, restacked on the same spawn points, and the "traffic" in
        # the frames was duplicate cars jammed at angles. A demo scene has to be the
        # scene you asked for.
        if not closing["reload"]:
            try:
                print(clear(), flush=True)
            except (RuntimeError, IndexError):
                pass
        if closing["reload"]:
            root.destroy()
            pgid = carla_proc if isinstance(carla_proc, int) else (
                os.getpgid(carla_proc.pid) if carla_proc else 0)
            print("reloading UI, leaving CARLA up", flush=True)
            os.execv(sys.executable,          # never returns
                     [sys.executable, *reload_argv(sys.argv, pgid)])
        root.destroy()
        stop_carla(carla_proc)   # no-op unless this process launched it

    def request_close(*_):
        closing["want"] = True

    root.protocol("WM_DELETE_WINDOW", request_close)

    # Hot reload: 'r' + Enter in the launching terminal re-execs this script and
    # leaves the server, its world and its cars alone -- CARLA costs 10-30 s to boot
    # plus a spawn round-trip per car, and none of that is what you are editing.
    # Line-buffered, not raw single-key: cbreak means restoring termios on every
    # exit path including the crash ones, for one saved keystroke.
    def watch_stdin():
        for line in sys.stdin:
            cmd = line.strip().lower()
            if cmd in ("r", "q"):
                closing["reload"] = cmd == "r"
                closing["want"] = True   # teardown still happens only in tick()
                return

    if sys.stdin and sys.stdin.isatty():
        threading.Thread(target=watch_stdin, daemon=True).start()
        print("press r + Enter to reload the UI (CARLA stays up), q to quit",
              flush=True)

    # CarlaUE4's own WASD fly speed is a UE4 viewport setting with no RPC, so
    # instead we drive the spectator ourselves. Keys work while THIS window has
    # focus; the CARLA window still shows the result.
    held = set()
    pending = {}  # keysym -> after-id of a not-yet-applied release

    # The keys go to whichever widget has focus, and the thing you want to fly is
    # the picture -- so the image labels ARE the focus target (wired below, once
    # they exist). Focusing there also keeps wasd out of the Spinbox and Combobox.
    tk.Label(bar, text="click the view to fly:  wasd/qe move, arrows look, space "
                       "pause, t follow-mode, g deliver, Shift-click designate"
             ).pack(side=tk.LEFT, padx=(16, 0))
    speed = tk.Scale(bar, from_=1, to=300, orient=tk.HORIZONTAL, length=140,
                     showvalue=True, label=None, sliderlength=16)
    speed.set(45)
    speed.pack(side=tk.LEFT, padx=(8, 0))
    status.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(16, 0))

    # --- "follow that car": ground the frame the operator is looking at ---
    out_dir = Path(args.out)
    backend = {"be": None, "lock": threading.Lock()}

    def get_backend():
        """The on-Orin llama-server, booted once.

        Booting it costs ~10 s of ssh + model load, and charging that to the first
        acquire is a lie in the wrong direction: it made a live COLD delivery read
        18.8 s against the ~4.85 s the thesis measures, because the first click paid
        for the server. Prewarmed at startup and locked, so the number on screen is
        acquire and nothing else."""
        with backend["lock"]:
            if backend["be"] is None:
                from grounding.eval.backends import JetsonBackend
                backend["be"] = JetsonBackend(REMOTE_GGUF, REMOTE_MMPROJ,
                                              max_side=1024).__enter__()
            return backend["be"]

    # box is in PIXELS of the live frame, kept current by the follow thread; tick()
    # only ever reads it, so no lock for the read -- a dict assign is atomic under
    # the GIL. The lock exists for one thing: drop lands while the follow thread is
    # inside a ~200 ms carry.step(), so without it that step's box is published
    # AFTER drop cleared it and the stale square stays on screen forever.
    # "stamp" counts published boxes. ASSIST needs it to tell a NEW measurement from
    # the same one sitting there: a box that stopped updating (occlusion) is a fixed
    # pixel error, and steering on it every tick is an integrator with no feedback.
    track = {"box": None, "msg": "", "lag": 0, "stop": None, "actor": None,
             "hits": 0, "steps": 0, "stamp": 0, "on_target": False, "drift": None,
             # lost_s = how long the mask has been empty (distinct from drift, which is
             # a box on the wrong object). Both have to be visible or the panel reports
             # a healthy lock rate while nothing is being tracked.
             "lost_s": None,
             # bridge = the live Orin carry subprocess (killed on drop/close); label =
             # the caption the overlay draws (rich caption in click mode); the *_ms/hz
             # fields are the live per-stage timings the status strip reads at 60 Hz.
             "bridge": None, "label": None, "ground_ms": None,
             "carry_ms": None, "carry_hz": None, "catchup_s": None,
             # WARM/COLD delivery. `delivered` is the whole difference between the two
             # arms: a maintained track exists and is being carried but is NOT handed
             # to the operator or to control until the command lands. cmd_t is when the
             # command landed; deliver_s is command -> first box in hand, which is the
             # ~0 s vs ~4.8 s that P5.1/R-34/P6.2-DELIVERY are about. It is measured
             # here, live, not read from a table.
             "delivered": True, "cmd_t": None, "deliver_s": None}
    track_lock = threading.Lock()
    resize = {"job": None}

    # Reading v.bounding_box is a ~10 ms server round-trip (measured), and match_actor
    # projects every vehicle EVERY carry step -- 50 vehicles was ~540 ms/step of held
    # GIL, which froze the 60 Hz render tick to a slideshow the moment carry started
    # (the CARLA server itself stayed at ~56 fps). The box is the actor's constant
    # local extent, so fetch each once and reuse. Not pruned: a debug session does not
    # churn enough actors to matter.
    veh_bbox = {}
    def veh_list(world):
        out = []
        for v in world.get_actors().filter("vehicle.*"):
            bb = veh_bbox.get(v.id)
            if bb is None:
                bb = veh_bbox[v.id] = v.bounding_box
            out.append((v, bb))
        return out

    def _pixels(box, w, h):
        """contract coords are 0-COORD_SCALE normalised, not pixels"""
        return [int(box[0] / COORD_SCALE * w), int(box[1] / COORD_SCALE * h),
                int(box[2] / COORD_SCALE * w), int(box[3] / COORD_SCALE * h)]

    def _stop_current():
        """Stop whatever is following now and reap its on-Orin carry bridge.

        Caller holds track_lock. Killing the ssh bridge here (not only on drop) is
        what stops a re-follow from leaving an orphaned carry_ssh_bridge.py on the
        Jetson holding the GPU."""
        if track.get("stop") is not None:
            track["stop"].set()
        br = track.get("bridge")
        if br is not None:
            try:
                br.stdin.close()
            except Exception:
                pass
            try:
                br.kill()
            except Exception:
                pass
            track["bridge"] = None

    def _mark_delivered():
        """Stamp deliver_s the first time a box exists after the command lands.

        Caller holds track_lock. This is the one number the WARM/COLD switch exists to
        show: command -> box in the operator's hands. WARM has already been carrying,
        so it is bounded by one carry step; COLD has to ground first, so it is the
        ~4.8 s acquire. Measured from the click/keypress, not from any stage boundary.
        """
        if track["delivered"] and track["deliver_s"] is None and track["cmd_t"]:
            track["deliver_s"] = time.time() - track["cmd_t"]

    def orin_carry(seed_n, seed, seed_box, caption, vlm_s, raw, carry_size,
                   seed_actor_id, stop):
        """SAM2 carry on the JETSON over the ssh-stdio bridge (never local).

        Grounding produced seed_box on frame seed_n; the world is already ~vlm_s*CAM_HZ
        frames past it, so replay the backlog to drag the track into the present, then
        go live -- one persistent bridge process, one SAM2 state on the Orin. Identity:
        a click passes the actor it hit (seed_actor_id) so lock is against THAT car from
        frame one; a caption follow passes None and adopts identity at catch-up (lag<=1),
        because the seed box and the world are only the same instant once caught up.
        """
        X = load_exp3()
        out_dir.mkdir(parents=True, exist_ok=True)
        # One trace per follow: every carry step is a line, and the seed + every
        # actor switch/drift gets a PNG. A drift is unarguable from the log alone.
        tdir = out_dir / f"trace-{seed_n}"
        tdir.mkdir(parents=True, exist_ok=True)
        trace = (tdir / "trace.jsonl").open("w", buffering=1)

        def emit(**row):
            trace.write(json.dumps(row) + "\n")

        cv2.imwrite(str(tdir / f"seed-{seed_n}.png"), seed)
        emit(ev="ground", caption=caption, seed_n=seed_n, vlm_s=round(vlm_s, 3),
             raw=(raw or "")[:200], box=seed_box,
             mode="click" if seed_actor_id is not None else "caption")

        log = open(out_dir / "ui_bridge.err", "wb")
        proc = subprocess.Popen(
            ["ssh", "-T", "-q", "jetson", CARRY_BRIDGE.format(size=int(carry_size))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        with track_lock:
            track["bridge"] = proc
        t0 = time.time()
        try:
            X._send(proc.stdin, ("init", X._rgb_jpg_arr(seed),
                                 [int(v) for v in seed_box]))
            ack = X._recv(proc.stdout)
            if not (ack and ack.get("ok")):
                track["msg"] = f"carry bridge init failed: {ack}"
                emit(ev="bridge_fail", ack=str(ack))
                return
            cursor, caught_at = seed_n, None
            seed_area = max(1, (seed_box[2] - seed_box[0]) * (seed_box[3] - seed_box[1]))
            recent = collections.deque(maxlen=60)   # rolling lock; cumulative hides drift
            prev_id = None
            # identity match is throttled to MATCH_HZ, so cache its verdict between runs
            last_match, cur_actor, cur_aid = 0.0, None, None
            seed_id, bad_since, flagged = seed_actor_id, None, False
            lost_since = None      # start of the current run of empty masks, if any
            # Fetch the world + vehicle list ONCE (cars are spawned up front). Each
            # step then takes a SINGLE world snapshot and reads every transform from
            # it, so match_actor makes ~1 RPC/step instead of one get_transform() per
            # vehicle. That per-vehicle flood (~50-80 RPCs/step) was what dropped the
            # 3090's CARLA render to ~5 fps the moment carry started. Refresh the list
            # every ~2 s in case cars are added or removed.
            world = client.get_world()
            vehicles = veh_list(world)   # (actor, cached bbox) pairs -- see veh_list
            veh_at = time.time()
            while not stop.is_set():
                with frame_lock:
                    pending = [(n, f) for n, f in backlog if n > cursor]
                    live_n = latest["n"]
                if not pending:
                    time.sleep(0.01)
                    continue
                # behind: jump toward the newest pending frame (capped). caught up
                # (<=1 pending): take it. See CATCHUP_JUMP -- this is what keeps the
                # on-Orin carry feeling live instead of replaying stale history.
                n, frame = pending[min(len(pending), CATCHUP_JUMP) - 1]
                X._send(proc.stdin, ("step", X._rgb_jpg_arr(frame)))
                r = X._recv(proc.stdout)
                if r is None:
                    # The exit status is the whole diagnosis and costs one wait(): -9 is
                    # the Orin OOM killer (no traceback, which is why ui_bridge.err looks
                    # clean), -11 a segfault, 0 an orderly exit we did not ask for.
                    try:
                        rc = proc.wait(timeout=2)
                    except Exception:
                        rc = None
                    track["msg"] = f"carry bridge died (rc={rc}) -- see ui_bridge.err"
                    emit(ev="bridge_died", n=n, rc=rc)
                    break
                b, ms = r.get("box"), r.get("ms")
                cursor = n
                track["lag"] = live_n - cursor
                if b is None:
                    # A lost mask is a MISS, not a pause. Counting it only in the box
                    # branch froze the rolling lock at its last good value: a measured
                    # run printed "lock 60/60" after 87 consecutive lost steps, with no
                    # box on screen. It also has to run the off-target clock, or the
                    # panel stays quiet for the entire time the target is gone.
                    lost_since = lost_since or time.time()
                    recent.append(False)
                    emit(ev="lost", n=n, lag=track["lag"], ms=ms, lock60=sum(recent))
                    with track_lock:
                        if stop.is_set():
                            break
                        track["box"], track["on_target"] = None, False
                        track["lost_s"] = time.time() - lost_since
                        track["steps"] += 1
                        track["stamp"] += 1
                elif cam["sensor"] is not None:
                    box = [int(v) for v in b]
                    lost_since, track["lost_s"] = None, None
                    now = time.time()
                    # Throttle the GIL-heavy identity match (see MATCH_HZ). The box is
                    # pushed to the display every step below regardless; only the
                    # green/red verdict is re-derived at MATCH_HZ. Force a match while
                    # identity is still unadopted so lock happens the instant lag<=1.
                    need_id = seed_id is None and track["lag"] <= 1
                    if now - last_match >= 1.0 / MATCH_HZ or need_id:
                        last_match = now
                        if now - veh_at > 2.0:          # cheap refresh for spawns
                            vehicles = veh_list(world)
                            veh_at = now
                        cur_actor = match_actor(cam["sensor"].get_transform(),
                                                box, vehicles=vehicles,
                                                snap=world.get_snapshot())
                        cur_aid = cur_actor.id if cur_actor is not None else None
                        if need_id and cur_aid is not None:
                            seed_id = cur_aid
                            emit(ev="identity", n=n, actor=cur_aid,
                                 actor_type=cur_actor.type_id)
                    actor, aid = cur_actor, cur_aid
                    # green means THE target, not "some car is in the box"
                    on_target = aid is not None and (seed_id is None or aid == seed_id)

                    if on_target:
                        bad_since, flagged = None, False
                        track["drift"] = None
                    else:
                        bad_since = bad_since or now
                        held = now - bad_since
                        track["drift"] = held if held >= DRIFT_S else None
                        if held >= DRIFT_S and not flagged:
                            flagged = True   # once per drift episode, not per frame
                            cv2.imwrite(str(tdir / f"drift-{n}.png"),
                                        draw_overlay(frame.copy(), box, caption, False))
                            emit(ev="drift", n=n, held_s=round(held, 2),
                                 want=seed_id, got=aid,
                                 got_type=actor.type_id if actor is not None else None)

                    with track_lock:
                        if stop.is_set():
                            break
                        track["box"], track["actor"] = box, actor
                        track["on_target"] = on_target
                        track["stamp"] += 1
                        track["hits"] += on_target
                        track["steps"] += 1
                        _mark_delivered()   # WARM: this is the box the command gets
                    recent.append(on_target)
                    area = (box[2] - box[0]) * (box[3] - box[1])
                    emit(ev="step", n=n, lag=track["lag"], box=box, ms=ms,
                         area_ratio=round(area / seed_area, 3),
                         aspect=round((box[2] - box[0]) / max(1, box[3] - box[1]), 3),
                         actor=aid, on_target=on_target,
                         actor_type=actor.type_id if actor is not None else None,
                         lock60=sum(recent))
                    if aid != prev_id:
                        cv2.imwrite(str(tdir / f"switch-{n}.png"),
                                    draw_overlay(frame.copy(), box, caption,
                                                 actor is not None))
                        emit(ev="switch", n=n, was=prev_id, now=aid)
                        prev_id = aid
                hz = (1000.0 / ms) if ms else 0.0
                track["carry_ms"], track["carry_hz"] = ms, hz   # live timing readout
                if caught_at is None and track["lag"] <= 1:
                    caught_at = time.time() - t0
                    track["catchup_s"] = caught_at
                    track["msg"] = (f"vlm {vlm_s:.1f}s + catchup {caught_at:.1f}s, live"
                                    f"  --  carry {hz:.1f} Hz Orin")
                    emit(ev="live", n=cursor, catchup_s=round(caught_at, 3))
                elif caught_at is not None:
                    d, ls = track["drift"], track["lost_s"]
                    # LOST (empty mask) and DRIFT (a box, on the wrong object) are
                    # different failures and the panel names them separately.
                    track["msg"] = (
                        (f"LOST {ls:.0f}s -- no mask, drop and re-follow.  " if ls else "")
                        + (f"DRIFT {d:.0f}s off target -- drop and re-follow.  " if d else "")
                        + f"carry {hz:.1f} Hz Orin, lag {track['lag']}, lock "
                          f"{sum(recent)}/{len(recent)} "
                          f"({track['hits']}/{track['steps']} all)")
                else:
                    track["msg"] = (f"catching up on Orin... lag {track['lag']}  "
                                    f"carry {hz:.1f} Hz")
            emit(ev="end", n=cursor)
        finally:
            trace.close()
            try:
                proc.stdin.close()
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
            log.close()
            with track_lock:
                if track.get("bridge") is proc:
                    track["bridge"] = None

    def follow(caption, stop):
        """Whole-frame caption grounding on the Jetson -> carry on the Jetson."""
        with frame_lock:
            if latest["bgr"] is None:
                track["msg"] = "no frame yet -- is the camera attached?"
                return
            seed_n, seed = latest["n"], latest["bgr"].copy()
        if backend["be"] is None:
            track["msg"] = "booting Jetson llama-server..."
        be = get_backend()
        out_dir.mkdir(parents=True, exist_ok=True)
        shot = out_dir / "frame.png"
        cv2.imwrite(str(shot), seed)
        track["msg"] = f"grounding {caption!r}..."
        t0 = time.time()
        raw = be.generate(str(shot), caption)
        vlm_s = time.time() - t0
        track["ground_ms"] = vlm_s * 1000        # live timing readout
        box = parse_bbox(raw)
        if box is None:
            track["msg"] = f"NO_MATCH in {vlm_s:.1f}s (raw {raw!r:.40})"
            return
        h, w = seed.shape[:2]
        seed_box = _pixels(box, w, h)
        with track_lock:                   # dropped during the ~4.5 s grounding?
            if stop.is_set():              # then this box is not wanted on screen
                return
            track["box"] = seed_box        # stale, but shows immediately
            track["stamp"] += 1
            _mark_delivered()   # COLD: the box the command gets, and it is already stale
        track["msg"] = f"grounded in {vlm_s:.1f}s, carrying on Orin..."
        orin_carry(seed_n, seed, seed_box, caption, vlm_s, raw,
                   ORIN_CARRY_SIZE, None, stop)

    def hit_test_live(feed_x, feed_y):
        """Clicked feed pixel -> the CARLA vehicle under it (smallest projected box).

        Same projection as match_actor (CAM_W x CAM_H, CAM_FOV), so the click lives in
        the same pixel space the tracker and the grounder do. Smallest-area containing
        box wins an overlap toward the nearer/topmost car."""
        if cam["sensor"] is None:
            return None
        cam_tf = cam["sensor"].get_transform()
        world = client.get_world()
        snap = world.get_snapshot()          # one RPC, not one get_transform() per car
        best, best_area = None, float("inf")
        for v, bb in veh_list(world):        # cached bboxes -- no per-car round-trip
            s = snap.find(v.id)
            if s is None:
                continue
            a = actor_box(bb, cam_tf, s.get_transform())
            if a is None or not (a[0] <= feed_x <= a[2] and a[1] <= feed_y <= a[3]):
                continue
            area = (a[2] - a[0]) * (a[3] - a[1])
            if area < best_area:
                best_area, best = area, v
        return best

    def follow_click(actor_id, click_xy, carry_size, ground_res, stop):
        """EXP-3, both on the Orin: rich caption -> point-crop VLM ground -> SAM2 carry.

        The crop centres on the click, so position is the constant "in the center"; the
        colour is sampled from the clicked car's pixels and the object word from its
        CARLA type. Grounding is a point-crop (roi_reanchor) at ground_res, carry at
        carry_size -- the resolutions EXP-1/EXP-2/EXP-3 found."""
        X = load_exp3()
        with frame_lock:
            if latest["bgr"] is None:
                track["msg"] = "no frame yet -- is the camera attached?"
                return
            seed_n, seed = latest["n"], latest["bgr"].copy()
        v = client.get_world().get_actor(actor_id)
        if v is None:
            track["msg"] = "the clicked car is gone"
            return
        a = (actor_box(v.bounding_box, cam["sensor"].get_transform(),  # one-off click
                       v.get_transform()) if cam["sensor"] else None)
        if a is None:
            track["msg"] = "cannot project the clicked car"
            return
        caption = X.rich_caption(seed, a, v.type_id)
        with track_lock:
            track["label"] = caption
        if designate.get() == "oracle":
            # ORACLE designation: seed the carry from the CARLA projected box and skip
            # the VLM entirely. This is not a shortcut, it is the scope P6.2-DELIVERY's
            # claim was measured in -- q8_0 is non-discriminative at 45 m nadir (G6), so
            # holding designation constant is the only way to show the carry + control
            # half at the altitude the flagship flew. Watch WARM at the same altitude to
            # see why: the grounder answers with a sliver of median strip.
            seed_box = [int(x) for x in a]
            with track_lock:
                if stop.is_set():
                    return
                track["box"] = seed_box
                track["stamp"] += 1
                _mark_delivered()
            track["ground_ms"] = 0.0
            track["msg"] = f"ORACLE designation {caption!r}, carrying on Orin..."
            orin_carry(seed_n, seed, seed_box, caption, 0.0, None,
                       int(carry_size), actor_id, stop)
            return
        if backend["be"] is None:
            track["msg"] = "booting Jetson llama-server..."
        be = get_backend()
        gms = {"ms": 0.0}

        def submit_img(img_bgr, cap):
            p = f"/dev/shm/uiclick_{time.monotonic_ns()}.png"
            cv2.imwrite(p, img_bgr)
            try:
                t = time.perf_counter()
                bx = X.vlm_acquire(be, p, cap,
                                   img_bgr.shape[1], img_bgr.shape[0])
                gms["ms"] = round(1000 * (time.perf_counter() - t), 1)
                return bx
            finally:
                Path(p).unlink(missing_ok=True)

        X.select_p55.ROI_RES = int(ground_res)
        cx, cy = click_xy
        track["msg"] = f"grounding {caption!r} @{int(ground_res)} on Orin..."
        t0 = time.time()
        box, _dbg = X.roi_reanchor(seed, X._center_box((cx, cy, cx, cy)),
                                   caption, submit_img)
        vlm_s = time.time() - t0
        track["ground_ms"] = gms["ms"]           # on-device VLM point-crop time
        if not X._valid(box, seed.shape):
            track["msg"] = f"NO_MATCH {caption!r} in {gms['ms']:.0f} ms"
            return
        seed_box = [int(x) for x in box]
        with track_lock:
            if stop.is_set():
                return
            track["box"] = seed_box
            track["stamp"] += 1
            _mark_delivered()   # COLD: same, one point-crop instead of a whole frame
        track["msg"] = f"grounded {caption!r} {gms['ms']:.0f} ms, carrying on Orin..."
        orin_carry(seed_n, seed, seed_box, caption, vlm_s, None,
                   int(carry_size), actor_id, stop)

    # --- PILOT: a camera on a stick, or the real copter with the camera slaved ---
    # In copter mode nothing about the camera changes except who decides where it is:
    # the pose comes from LOCAL_POSITION_NED through carla_render's ned_to_carla (the
    # SAME mapping P6.1 gated -- do not re-derive it here, the sign in it is the one
    # that aimed Phase C at the sky for a month), and the operator's keys become GUIDED
    # velocity setpoints instead of teleports. The gimbal is ours because SITL never
    # sends yaw (R-10) and a nadir camera has nothing to rotate anyway.
    pilot = {"mode": "spectator", "m": None, "fly": None,
             "ned": (0.0, 0.0, -args.alt), "ned_v": (0.0, 0.0, 0.0),
             "vel": (0.0, 0.0, 0.0), "sent": 0.0,
             "gim": {"pitch": -90.0, "yaw": 0.0}, "pid": None, "hb": "no link"}

    def connect_copter():
        """Bring SITL up if needed, arm, take off. Blocking -- called through bg()."""
        import carla_render as cr
        import sitl_fly_leg as mavfly
        pilot["cr"] = cr
        pilot["fly"] = mavfly
        m = pilot["m"] or ensure_sitl(args.mavlink_url)
        pilot["m"] = m
        reached = mavfly.arm_and_takeoff(m, args.alt)   # reuses one already airborne
        pilot["mode"] = "copter"
        cam["t"] = None
        return f"copter airborne at {reached:.1f} m, camera slaved"

    def go_spectator():
        """Hand the stick back. The copter is left hovering in GUIDED, not landed."""
        if pilot["m"] is not None:
            pilot["fly"].send_velocity(pilot["m"], 0.0, 0.0)
        pilot["mode"] = "spectator"
        cam["t"] = None
        return "spectator: flying the camera directly"

    def do_land():
        if pilot["m"] is None:
            return "no copter"
        from pymavlink import mavutil
        m = pilot["m"]
        m.mav.command_long_send(m.target_system, m.target_component,
                                mavutil.mavlink.MAV_CMD_NAV_LAND,
                                0, 0, 0, 0, 0, 0, 0, 0)
        pilot["mode"] = "spectator"       # stop slaving to a descending copter
        return "LAND commanded (pilot back to spectator)"

    pbar = tk.Frame(root)
    pbar.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 4))
    tk.Label(pbar, text="pilot").pack(side=tk.LEFT)
    tk.Button(pbar, text="copter (arm + takeoff)",
              command=lambda: bg(status, connect_copter)).pack(side=tk.LEFT, padx=(4, 0))
    tk.Button(pbar, text="spectator",
              command=lambda: bg(status, go_spectator)).pack(side=tk.LEFT, padx=(4, 0))
    tk.Button(pbar, text="to origin",
              command=lambda: bg(status, lambda: (
                  f"origin: {pilot['fly'].reset_to_origin(pilot['m'], args.alt):.1f} m"
                  if pilot["m"] else "no copter"))).pack(side=tk.LEFT, padx=(4, 0))
    tk.Button(pbar, text="land", command=lambda: bg(status, do_land)).pack(
        side=tk.LEFT, padx=(4, 0))
    ptel = tk.Label(pbar, text="", anchor=tk.W, font=("TkFixedFont", 9))
    ptel.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(16, 0))

    grow = tk.Frame(root)
    grow.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 6))
    nb = ttk.Notebook(grow)
    nb.pack(side=tk.TOP, fill=tk.X)

    def _arm_track():
        """Clear the old track, reap its Orin bridge, and set the WARM/COLD stance.

        Caller must NOT hold track_lock. Returns the new stop event. The one thing the
        acquire mode changes here is who owns the box that is about to be produced:
        COLD means the operator has already asked (this designation IS the command, so
        clock starts now and whatever comes back is delivered stale), WARM means the
        system starts maintaining and nobody has asked yet.
        """
        cold = acquire.get() == "cold"
        with track_lock:
            _stop_current()              # one target at a time; reap its Orin bridge
            track["stop"] = threading.Event()
            track["box"], track["actor"] = None, None
            track["on_target"], track["drift"], track["lost_s"] = False, None, None
            track["label"] = None        # caption mode: overlay uses the entry text
            track["ground_ms"] = track["carry_ms"] = track["carry_hz"] = None
            track["catchup_s"] = track["deliver_s"] = None
            track["delivered"] = cold
            track["cmd_t"] = time.time() if cold else None
            return track["stop"]

    def do_deliver(_event=None):
        """The operator's command: hand the maintained track over. WARM's other half.

        On a maintained (undelivered) track this is instant by construction -- the box
        already exists, and deliver_s lands within one carry step. With nothing
        maintained there is nothing to deliver, which is the honest answer rather than
        silently falling back to a cold ground.
        """
        with track_lock:
            if track["stop"] is None or track["stop"].is_set():
                track["msg"] = "nothing maintained -- designate a target first"
                return
            if track["delivered"]:
                return                   # already the operator's; not a re-command
            track["delivered"], track["cmd_t"] = True, time.time()
            track["deliver_s"] = None
            if track["box"] is not None:
                _mark_delivered()        # already carrying: delivered on the spot

    def do_follow(_event=None):
        # oracle designation needs a designated actor to read a GT box off, and a typed
        # caption names no actor. Say so instead of silently grounding with the VLM.
        if designate.get() == "oracle":
            track["msg"] = "designate=oracle needs a Shift-click on a car, not a caption"
            return
        threading.Thread(target=follow, daemon=True,
                         args=(caption_entry.get(), _arm_track())).start()

    def do_drop():
        # set the event INSIDE the lock, so a follow thread holding it is either
        # already past its publish (and this clear wins) or blocked before its stop
        # check (and it bails without publishing). _stop_current also kills the Orin
        # carry bridge, or a dropped follow leaves SAM2 running on the device.
        with track_lock:
            _stop_current()
            track["box"], track["actor"], track["msg"] = None, None, "dropped"
            track["on_target"], track["drift"], track["label"] = False, None, None
            track["lost_s"] = None
            track["delivered"], track["cmd_t"] = True, None

    # -- tab 1: caption follow -- whole-frame VLM ground (Orin) -> SAM2 carry (Orin) --
    tab_follow = ttk.Frame(nb)
    nb.add(tab_follow, text="Follow (caption)")
    tk.Label(tab_follow, text="follow").pack(side=tk.LEFT)
    caption_entry = tk.Entry(tab_follow, width=28)
    caption_entry.insert(0, "the red car")
    caption_entry.pack(side=tk.LEFT, padx=(4, 0))
    caption_entry.bind("<Return>", do_follow)
    tk.Button(tab_follow, text="follow", command=do_follow).pack(side=tk.LEFT, padx=(4, 0))
    tk.Button(tab_follow, text="drop", command=do_drop).pack(side=tk.LEFT, padx=(4, 0))

    # -- tab 2: click follow (EXP-3) -- Shift-click a car -> point-crop rich-caption
    # ground (Orin) -> SAM2 carry (Orin); the two combos are the EXP-1/EXP-2/EXP-3 knobs
    tab_click = ttk.Frame(nb)
    nb.add(tab_click, text="Click to follow (EXP-3)")
    tk.Label(tab_click, text="Shift-click a car in the flown view").pack(side=tk.LEFT)
    tk.Label(tab_click, text="ground").pack(side=tk.LEFT, padx=(12, 2))
    ground_res = tk.IntVar(value=ORIN_GROUND_RES)
    ttk.Combobox(tab_click, textvariable=ground_res, width=5, state="readonly",
                 values=(256, 512, 768, 1024)).pack(side=tk.LEFT)
    tk.Label(tab_click, text="carry").pack(side=tk.LEFT, padx=(12, 2))
    carry_size = tk.IntVar(value=ORIN_CARRY_SIZE)
    ttk.Combobox(tab_click, textvariable=carry_size, width=5, state="readonly",
                 values=(256, 384, 512, 640, 768, 1024)).pack(side=tk.LEFT)
    tk.Button(tab_click, text="drop", command=do_drop).pack(side=tk.LEFT, padx=(12, 0))

    # -- shared strips below the tabs: the two mode switches, then the live timings --
    strip = tk.Frame(grow)
    strip.pack(side=tk.TOP, fill=tk.X, pady=(4, 0))
    # ACQUIRE. warm = maintain from designation, deliver on command (the thesis
    # position: maintain-and-deliver). cold = the designation IS the command, so the
    # ~4.8 s ground happens under time pressure and the box lands stale. Same code
    # path either way -- the only difference is who owns the box while it is produced,
    # which is exactly the comparison and the reason both live in one binary.
    tk.Label(strip, text="acquire").pack(side=tk.LEFT)
    acquire = tk.StringVar(value=args.acquire)
    ttk.Combobox(strip, textvariable=acquire, width=6, state="readonly",
                 values=("warm", "cold")).pack(side=tk.LEFT, padx=(4, 0))
    tk.Button(strip, text="deliver (g)", command=do_deliver).pack(side=tk.LEFT, padx=(4, 0))
    # DESIGNATE, orthogonal to acquire. vlm = the deployed Qwen2-VL-2B Q8_0 point-crop
    # grounds the clicked car on the Orin. oracle = the seed box comes from CARLA's
    # projected bounding box. Not a cheat switch: P6.2-DELIVERY held designation
    # constant with ORACLE in BOTH arms because q8_0 is non-discriminative at 45 m nadir
    # (G6), so oracle is what reproduces the flagship's scope, and it is the only way to
    # watch the carry + control half at that altitude. Applies to Shift-click only.
    tk.Label(strip, text="   designate").pack(side=tk.LEFT)
    designate = tk.StringVar(value=args.designate)
    ttk.Combobox(strip, textvariable=designate, width=7, state="readonly",
                 values=("vlm", "oracle")).pack(side=tk.LEFT, padx=(4, 0))
    # FOLLOW authority. manual = operator alone. assist = the model AIMS (gimbal or
    # spectator rotation; never position). auto = the closed loop -- the delivered box
    # drives the copter through CascadePID -> LOCAL_NED velocity, which is P6.2's own
    # control path, so it needs a copter to fly. Operator input stays live in all
    # three: a held key outranks the model for as long as it is held.
    tk.Label(strip, text="   follow").pack(side=tk.LEFT)
    follow_mode = tk.StringVar(value="manual")
    for m in FOLLOW_MODES:
        tk.Radiobutton(strip, text=m, value=m, variable=follow_mode).pack(side=tk.LEFT)
    gstatus = tk.Label(strip, text="", anchor=tk.W)
    gstatus.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(16, 0))
    gtimes = tk.Label(grow, text="", anchor=tk.W, fg=ACCENT, font=("TkFixedFont", 10))
    gtimes.pack(side=tk.TOP, fill=tk.X, pady=(2, 0))
    # Which box runs which stage, spelled out. The constraint is that SAM2 and the VLM
    # run ONLY on the Orin and the 3090 runs ONLY the simulator; a demo that cannot be
    # asked where the models are is a demo that can quietly answer "on the 3090".
    gmodes = tk.Label(grow, text="", anchor=tk.W, fg="#8a8a8a",
                      font=("TkFixedFont", 9))
    gmodes.pack(side=tk.TOP, fill=tk.X)

    # Live feed with the track drawn on it. In-memory PPM into PhotoImage runs at
    # ~115 FPS (no PIL, no disk); a PNG-per-frame round-trip does not. The image
    # MUST stay referenced in `preview` -- a local gets collected and the label
    # renders blank with no error, the silent failure this repo keeps hitting.
    preview = {"live": None, "feed": None, "ln": -1, "fn": -1,
               "t": time.time(), "n0": 0, "fps": 0.0,
               "disp": 0.0, "dt": time.time()}   # real render-tick rate (see tick)
    # grid, not pack: the weights are what make a resize redistribute the space.
    # 3:1 keeps the flown view dominant and the Jetson feed a thumbnail at any size.
    views = tk.Frame(root, bg=DARK)
    views.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    # the thumbnail is a FIXED width, not a fraction: a 3:1 weight handed it 500 px
    # on a 2000 px window, which is not a thumbnail. Big view takes all the slack.
    views.columnconfigure(0, weight=1)
    views.columnconfigure(1, weight=0, minsize=THUMB_W + 12)
    views.rowconfigure(0, weight=1)
    big = tk.Label(views, bg=DARK)
    big.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
    col = tk.Frame(views, bg=DARK)
    col.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)
    tk.Label(col, text=f"what the Jetson sees -- {CAM_HZ:.0f} Hz, VLM + tracker",
             bg=DARK, fg=TEXT).pack(anchor=tk.W)
    small_lbl = tk.Label(col, bg=DARK)
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
        # PIL over Tk's own PPM path: at 1080p, parsing a 5 MB PPM blob costs
        # 28 ms and ImageTk costs 7.5. That 20 ms was the single biggest item in
        # the tick, and the tick is what flies the camera -- see fly().
        # cvtColor over bgr[:, :, ::-1] for the same reason: 0.3 ms vs 6.3.
        return ImageTk.PhotoImage(Image.fromarray(
            cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)))

    def show_preview():
        with frame_lock:
            lf = None if live["n"] == preview["ln"] else live["bgr"]
            ff = None if latest["n"] == preview["fn"] else latest["bgr"]
            if lf is not None:
                lf, preview["ln"] = lf.copy(), live["n"]
            if ff is not None:
                ff, preview["fn"] = ff.copy(), latest["n"]
        box, locked, deliv = track["box"], track["on_target"], track["delivered"]
        label = track.get("label") or caption_entry.get()   # rich caption in click mode
        if lf is not None:
            # the box is up to one feed period stale here -- it was measured on
            # the 5 Hz frame, drawn on the 60 Hz one. Same camera, so it lines up.
            draw_overlay(lf, box, label, locked,
                         scale=lf.shape[1] / CAM_W, delivered=deliv)
            preview["live"] = _photo(lf, big)
            big.config(image=preview["live"])
        if ff is not None:
            draw_overlay(ff, box, "", locked, delivered=deliv)
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
        gstatus.config(text=f"{preview['fps']:.0f} Hz live  {track['msg']}",
                       fg=ALERT if track["drift"] else TEXT)
        # live per-stage timings, refreshed every tick straight off the track dict.
        # deliver comes FIRST because it is the number the whole warm-start argument
        # is about (command -> box in hand); the rest is where that number came from.
        gm, cm, chz = track["ground_ms"], track["carry_ms"], track["carry_hz"]
        cu, dv = track["catchup_s"], track["deliver_s"]
        gtimes.config(text="   |   ".join((
            _f("deliver {:.2f} s", dv),
            _f("ground {:.0f} ms", gm),
            (f"carry {cm:.0f} ms ({chz:.1f} Hz) Orin" if cm is not None else "carry --"),
            _f("catch-up {:.1f} s", cu),
            f"lag {track['lag']} f",
            f"feed {CAM_HZ:.0f} Hz",
            f"disp {preview['disp']:.0f} Hz",
        )))
        # Who is flying, what has been asked for, and which box runs which stage.
        fm = pilot_follow_mode()
        gmodes.config(text="   ".join((
            f"pilot {pilot['mode']}",
            f"acquire {acquire.get()}" + ("" if track["delivered"] else " (maintaining)"),
            f"designate {designate.get()}",
            f"follow {fm}" + ("" if fm == follow_mode.get() else " [auto needs copter]"),
            f"|  ground {ground_res.get()} Orin",
            f"carry {carry_size.get()} Orin",
            "CARLA + SITL 3090",
        )))
        if pilot["mode"] == "copter":
            n, e, d = pilot["ned"]
            vn, ve, vd = pilot["vel"]
            mn, me, _md = pilot["ned_v"]
            ptel.config(text=f"{pilot['hb']}   alt {-d:5.1f} m   N {n:7.1f}  E {e:7.1f}"
                             f"   cmd vn {vn:5.1f}  ve {ve:5.1f}  vd {vd:5.1f} m/s"
                             f"   got {(mn**2 + me**2) ** 0.5:4.1f} m/s"
                             f"   gimbal {pilot['gim']['pitch']:.0f}/"
                             f"{pilot['gim']['yaw']:.0f} deg")
        else:
            ptel.config(text="spectator -- no copter in the loop "
                             "(click 'copter' to arm SITL and slave the camera)")

    def do_click_follow(feed_x, feed_y, actor=None):
        v = actor or hit_test_live(feed_x, feed_y)   # actor: --smoke already projected it
        if v is None:
            track["msg"] = "no car under the click"
            return
        threading.Thread(target=follow_click, daemon=True,
                         args=(v.id, (feed_x, feed_y), carry_size.get(),
                               ground_res.get(), _arm_track())).start()

    def on_select_click(e):
        # Shift-click on the flown view -> feed px. The photo is centred in the label
        # with letterboxing, so recover scale+offset from the DISPLAYED photo size.
        ph = preview["live"]
        if ph is None:
            return "break"
        iw, ih = ph.width(), ph.height()
        ox, oy = (big.winfo_width() - iw) / 2, (big.winfo_height() - ih) / 2
        u, vv = (e.x - ox) / iw, (e.y - oy) / ih
        if 0 <= u <= 1 and 0 <= vv <= 1:
            big.focus_set()
            do_click_follow(u * CAM_W, vv * CAM_H)
        return "break"

    big.bind("<Shift-Button-1>", on_select_click)

    def on_press(e):
        k = e.keysym.lower()
        if k in pending:  # autorepeat, not a real release
            root.after_cancel(pending.pop(k))
        # space toggles pause, so it must be handled BEFORE the paused gate below or
        # it would only ever pause and never resume. Bound on the views rather than
        # on root, or every space typed into the caption box would freeze the sim.
        # held-as-repeat-guard: X11 autorepeat fires press events while the key is
        # down, which would toggle dozens of times per hold.
        if k == "space":
            if k not in held:
                toggle_pause()
                held.add(k)      # after the toggle: it clears held on the way past
            return
        # same autorepeat guard as space -- a held t must cycle once, not 30 times
        if k == "t":
            if k not in held:
                follow_mode.set(FOLLOW_MODES[
                    (FOLLOW_MODES.index(follow_mode.get()) + 1) % len(FOLLOW_MODES)])
                held.add(k)
            return
        # g = the operator's command. Same guard: one delivery per press.
        if k == "g":
            if k not in held:
                do_deliver()
                held.add(k)
            return
        # paused means paused: the spectator still accepts set_transform while the
        # world is frozen, so keys held now would fly it blind and the view would
        # jump on resume
        if paused["on"]:
            return
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
                 highlightbackground=DARK, highlightcolor=ACCENT)
        w.bind("<Button-1>", lambda e, w=w: w.focus_set())
        w.bind("<FocusOut>", lambda e: held.clear())
        w.bind("<KeyPress>", on_press)
        w.bind("<KeyRelease>", on_release)

    DT = 1 / 60          # how often the tick is SCHEDULED; fly() measures the real one
    fly_t = {"last": None}
    # outstanding ASSIST correction in degrees, and the box stamp it came from
    aim = {"yaw": 0.0, "pitch": 0.0, "stamp": -1, "chase": False, "seen": 0.0,
           "floor": None,
           "areas": collections.deque(maxlen=CHASE_HIST + 1)}
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

    if args.clean_world:
        # BEFORE attach_camera: clean_world destroys every sensor.camera in the world,
        # including ours if it already exists.
        print(clean_world(), flush=True)
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

    def model_box():
        """The box the MODEL is allowed to steer on, or None.

        The WARM gate lives here and nowhere else: a maintained track is a real box
        being really carried, but until the operator's command lands it is not the
        operator's box, so no control law may read it. That is the difference between
        "we were already tracking it" and "we flew at something nobody asked for".
        """
        if paused["on"] or not track["delivered"]:
            return None
        fm = pilot_follow_mode()
        return track["box"] if fm in ("assist", "auto") else None

    def pilot_follow_mode():
        """The follow mode actually in force. AUTO with no copter is not a mode.

        Reported rather than silently downgraded to assist: AUTO means position
        authority, and quietly giving the model the camera instead would be a
        different experiment wearing the same label.
        """
        fm = follow_mode.get()
        if fm == "auto" and (pilot["mode"] != "copter" or pilot["m"] is None):
            return "manual"
        return fm

    def charge_aim(now, box):
        """Update the outstanding ASSIST correction from a (possibly new) box.

        Charged once per NEW box and then spent down. A box that stopped updating
        (occluded target, dead track) is therefore worth exactly one correction: the
        camera turns to where the target last was, stops, and waits for the tracker.
        Steering on a repeated box is an open loop -- rotating does not change stale
        pixels, so the error never shrinks and the view sweeps off until the target is
        out of frame and can never be re-found.
        """
        if box is None:
            aim["yaw"] = aim["pitch"] = 0.0
            aim["chase"] = 0.0
            aim["areas"].clear()   # a dropped/reacquired target has no history
        elif track["stamp"] != aim["stamp"]:
            aim["stamp"] = track["stamp"]
            aim["yaw"], aim["pitch"] = center_delta(box)
            aim["areas"].append(max(box[2] - box[0], 0) * max(box[3] - box[1], 0))
            aim["chase"], aim["seen"] = chase_speed(aim["areas"]), now
        # Same failure the aim budget guards against, one rung worse: a frozen box
        # is a latched speed and the copter keeps flying at a target it can no
        # longer see. Aim self-limits (it spends a finite budget); chase does not,
        # so it gets a hard stale timeout instead.
        if aim["chase"] and now - aim["seen"] > CHASE_STALE:
            aim["chase"] = 0.0

    def fly_spectator(now):
        if not held and not (aim["yaw"] or aim["pitch"] or aim["chase"]
                             or aim["floor"]):
            cam["t"] = None  # resync next time, the view may have moved elsewhere
            fly_t["last"] = None
            return
        # Move by MEASURED time, not by a nominal 1/60. The tick also paints the
        # preview, so its real period swings with window size and load -- assuming
        # 60 Hz made the camera crawl at 1080p and made the slider speed depend on
        # how big the window was. Uneven steps are what "choppy" actually is.
        dt = min(now - fly_t["last"], 0.1) if fly_t["last"] else 1 / 60
        fly_t["last"] = now
        # keep the pose local: get_world()/get_transform() are RPC round-trips
        # and doing them per frame is what made this choppy. Only push.
        if cam["t"] is None:
            cam["t"] = cam["spec"].get_transform()
        t = cam["t"]
        fwd, right, up = (t.get_forward_vector(), t.get_right_vector(),
                          t.get_up_vector())
        step = speed.get() * dt
        for k in held & MOVE.keys():
            f, r, u = MOVE[k]
            t.location += (fwd * f + right * r + up * u) * step
        looking = held & LOOK.keys()
        for k in looking:
            dyaw, dpitch = LOOK[k]
            t.rotation.yaw += dyaw * 90 * dt
            t.rotation.pitch = max(-89, min(89, t.rotation.pitch + dpitch * 90 * dt))
        # the operator wins the tie: while an arrow is held the model does not fight
        # it, otherwise the two would sum and the view would crawl against the input
        if not looking:
            dyaw, dpitch = ease((aim["yaw"], aim["pitch"]), dt)
            t.rotation.yaw += dyaw
            t.rotation.pitch = max(-89, min(89, t.rotation.pitch + dpitch))
            aim["yaw"] -= dyaw          # spent: what is left is what still owes
            aim["pitch"] -= dpitch
        # CHASE flies along the boresight, signed: + closes, - backs
        # off. Unlike aim it is NOT one-shot per box, because closing genuinely
        # does change the pixels -- the box grows toward the setpoint, the error
        # shrinks, and it settles on its own. A real closed loop where aim on a
        # frozen box is an open one.
        # The operator wins the same tie as with look: a held wasd outranks it.
        if aim["chase"] and not (held & MOVE.keys()):
            t.location += boresight(t.rotation.pitch, t.rotation.yaw) * (aim["chase"] * dt)
        # Min-AGL escape, same operator-wins tie: flying the camera low by hand is
        # a deliberate act, sinking into the road on a nose-down chase is not.
        if not (held & MOVE.keys()):
            dz, aim["floor"] = floor_climb(t.location.z, dt, aim["floor"])
            t.location.z += dz
        else:
            aim["floor"] = None
        cam["spec"].set_transform(t)

    def fly_copter(now, dt, box):
        """Slave the camera to the copter's reported pose, and command the copter.

        Read then write, in that order, because they are two different loops sharing
        one link: the camera is SLAVED (pose in) and the copter is FLOWN (velocity
        out). Nothing here teleports anything -- the only way this camera moves is a
        setpoint the autopilot chose to honour, which is exactly what makes the frames
        a consequence of the control output rather than an input to it.
        """
        m, mavfly = pilot["m"], pilot["fly"]
        while True:                    # drain to newest: a stale NED is a lagging camera
            msg = m.recv_match(type="LOCAL_POSITION_NED", blocking=False)
            if msg is None:
                break
            pilot["ned"] = (msg.x, msg.y, msg.z)
            # ACHIEVED velocity, next to the commanded one. A follow that loses the
            # target because the copter is speed-limited looks identical to one that
            # loses it because the gain is too low, until you can see both numbers.
            pilot["ned_v"] = (msg.vx, msg.vy, msg.vz)
        hb = m.recv_match(type="HEARTBEAT", blocking=False)
        if hb is not None:
            pilot["hb"] = ("armed" if hb.base_mode & 128 else "disarmed") + \
                          f" mode {hb.custom_mode}"
        auto = pilot_follow_mode() == "auto"
        # Gimbal. AUTO forces nadir and leaves framing entirely to the PID: that is
        # P6.2's geometry (hard nadir, north-up), and a gimbal that also chases would
        # make the position loop's error unobservable -- two controllers, one error.
        gim = pilot["gim"]
        if auto:
            gim["pitch"], gim["yaw"] = -90.0, 0.0
        else:
            looking = held & LOOK.keys()
            for k in looking:
                dyaw, dpitch = LOOK[k]
                gim["yaw"] += dyaw * GIMBAL_RATE * dt
                gim["pitch"] = max(-89.0, min(0.0,
                                              gim["pitch"] + dpitch * GIMBAL_RATE * dt))
            if not looking and box is not None:   # ASSIST aims the gimbal, not the copter
                dyaw, dpitch = ease((aim["yaw"], aim["pitch"]), dt)
                gim["yaw"] += dyaw
                gim["pitch"] = max(-89.0, min(0.0, gim["pitch"] + dpitch))
                aim["yaw"] -= dyaw
                aim["pitch"] -= dpitch
        n, e, d = pilot["ned"]
        # ned_to_carla is P6.1's gated mapping, gimbal angles passed through it rather
        # than re-derived -- the -90 nadir sign in there is the Phase C sky-camera scar.
        cam["spec"].set_transform(pilot["cr"].ned_to_carla(
            n, e, d, yaw_rad=math.radians(gim["yaw"]), pitch_deg=gim["pitch"]))
        # Command. A held key outranks the model, same tie as everywhere else; with
        # nothing held AUTO gets the stick and MANUAL/ASSIST hover.
        v = min(float(speed.get()), MANUAL_V_MAX)
        if held & MOVE.keys():
            vn, ve, vd = manual_velocity(held & MOVE.keys(), v)
        elif auto and box is not None:
            if pilot["pid"] is None:
                from sitl.cascade_pid import CascadePID
                pilot["pid"] = CascadePID(img_w=CAM_W, img_h=CAM_H,
                                          kp_lat=AUTO_KP_LAT,
                                          max_vx=AUTO_MAX_V, max_vy=AUTO_MAX_V)
            # Same CascadePID -> LOCAL_NED path run_p62_flight flew, on the SAME box
            # the Orin carry published. cy above centre is north; cx right is east.
            vel = pilot["pid"].compute({"cx": (box[0] + box[2]) / 2,
                                        "cy": (box[1] + box[3]) / 2,
                                        "w": box[2] - box[0], "h": box[3] - box[1]})
            vn, ve, vd = vel["vx"], vel["vy"], 0.0
        else:
            vn, ve, vd = 0.0, 0.0, 0.0
        pilot["vel"] = (vn, ve, vd)
        # Resend on a timer even when the command has not changed: a GUIDED setpoint
        # expires after ~3 s of silence and the copter drops to loiter, so a one-shot
        # send looks like it works and then stops. 60 Hz would be 60 sends/s for no
        # gain -- CMD_HZ is twice the feed rate.
        if now - pilot["sent"] >= 1.0 / CMD_HZ:
            pilot["sent"] = now
            mavfly.send_velocity(m, vn, ve, vd)

    def fly():
        if busy["on"]:
            fly_t["last"] = None
            return  # mid-load (or mid-takeoff) the handles are stale, RPCs raise
        now = time.time()
        box = model_box()
        charge_aim(now, box)
        if pilot["mode"] == "copter" and pilot["m"] is not None:
            # Measured dt, never a nominal 1/60: the tick also paints the preview, so
            # its real period swings with window size and load.
            dt = min(now - fly_t["last"], 0.1) if fly_t["last"] else 1 / 60
            fly_t["last"] = now
            if not paused["on"]:
                fly_copter(now, dt, box)
            return
        fly_spectator(now)

    # Tk blocks in C, so SIGINT only lands while Python bytecode runs -- the
    # tick gives the interpreter that chance, and flies the spectator.
    # SIGTERM too: a kill while paused would leave the server in sync mode with
    # nothing ticking it, which hangs the next client that connects
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, request_close)

    def tick():
        # the one place teardown runs: nothing is half-executed here, so the
        # widgets are safe to destroy and no later callback can touch them
        if closing["want"]:
            unpause_on_exit()
            return
        # real render-tick rate (EMA). This is the display Hz the operator sees --
        # distinct from the CARLA server fps -- and it is what collapsed to ~5 when
        # the carry loop stole the GIL. Surfaced in the gtimes strip as a health read.
        now = time.time()
        d = now - preview["dt"]
        preview["dt"] = now
        if 0 < d < 1:
            preview["disp"] = 0.9 * preview["disp"] + 0.1 * (1.0 / d)
        fly()
        show_preview()
        root.after(int(DT * 1000), tick)
    tick()

    # Startup order matters, and it is the copter that decides it. spawn_vehicles
    # places cars nearest the CAMERA, so in copter mode it has to run AFTER the copter
    # is airborne and the camera is slaved -- spawning first puts the traffic around the
    # default spectator pose, which is not where the drone ends up. Both go through bg()
    # (SITL boot + climb is ~40 s of blocking MAVLink; the spawn is ~50 round-trips) and
    # bg() takes one whole-world operation at a time, refusing rather than waiting.
    def queue(fn, *a):
        """Run fn through bg() as soon as bg() is free."""
        def go():
            if busy["on"]:
                root.after(500, go)
            else:
                bg(status, fn, *a)
        return go

    if args.pilot == "copter" and not args.selftest:
        def boot_then_spawn():
            msg = connect_copter()
            if args.auto_spawn:
                msg += " | " + spawn_vehicles(args.auto_spawn)
            return msg
        root.after(1000, queue(boot_then_spawn))
    elif args.auto_spawn and not args.selftest:
        root.after(200, queue(spawn_vehicles, args.auto_spawn))

    if not args.selftest:
        # Prewarm the Orin llama-server off the UI thread. Not an optimisation: the
        # first acquire otherwise charges the server boot to the delivery latency,
        # which is the one number on this panel that has to be honest.
        threading.Thread(target=get_backend, daemon=True).start()

    if args.smoke and not args.selftest:
        # Unattended end-to-end run: designate the car nearest frame centre, deliver it,
        # hand the copter to AUTO, fly for N seconds, dump an overlay frame and exit.
        # It exists because synthetic clicks are banned in this repo (xdotool XTEST goes
        # to whatever window has focus and has typed into the user's terminal before),
        # so this is the only way to exercise the full live chain without a human at the
        # keyboard -- and it is the same code path the operator's Shift-click takes.
        smoke = {"phase": "wait", "t": time.time()}

        def nearest_on_screen():
            """Feed pixel on the vehicle whose projected box centre is nearest centre."""
            if cam["sensor"] is None:
                return None
            cam_tf = cam["sensor"].get_transform()
            world = client.get_world()
            snap = world.get_snapshot()
            best, bd = None, float("inf")
            for v, bb in veh_list(world):
                # "vehicle.*" includes bicycles, and a nadir bike is ~8 px wide -- the
                # first smoke designated a diamondback.century and the grounder had
                # nothing to find. Cars only.
                if int(v.attributes.get("number_of_wheels", 4)) < 4:
                    continue
                s = snap.find(v.id)
                if s is None:
                    continue
                a = actor_box(bb, cam_tf, s.get_transform())
                if a is None:
                    continue
                cx, cy = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
                if not (0 < cx < CAM_W and 0 < cy < CAM_H):
                    continue
                d = (cx - CAM_W / 2) ** 2 + (cy - CAM_H / 2) ** 2
                if d < bd:
                    best, bd = (v, cx, cy), d
            return best

        def smoke_step():
            ph, dt = smoke["phase"], time.time() - smoke["t"]
            if ph == "wait":            # airborne, a frame in hand, a car on screen
                ready = (pilot["mode"] == "copter" and not busy["on"]
                         and latest["bgr"] is not None)
                pt = nearest_on_screen() if ready else None
                if pt is None:
                    if dt > 180:
                        print("SMOKE FAIL: never got airborne with a car on screen")
                        closing["want"] = True
                        return
                elif not smoke.get("designated"):
                    smoke["designated"] = True
                    v, cx, cy = pt
                    # Does the operator's own hit test agree that a car is under that
                    # pixel? Reported, not asserted: a miss here is a hit-test finding,
                    # and the point of the smoke is the stages downstream of it.
                    agree = hit_test_live(cx, cy)
                    print(f"smoke: designating {v.type_id} at feed px {cx:.0f},{cy:.0f} "
                          f"(hit test: {'agrees' if agree and agree.id == v.id else 'MISSES'})",
                          flush=True)
                    do_click_follow(cx, cy, actor=v)
                    smoke["phase"], smoke["t"] = "maintain", time.time()
            elif ph == "maintain":      # let the ground + catch-up finish, then command
                if track["box"] is not None and track["catchup_s"] is not None:
                    do_deliver()
                    follow_mode.set("auto")
                    print(f"smoke: delivered in {track['deliver_s']:.3f} s, AUTO engaged",
                          flush=True)
                    smoke["phase"], smoke["t"] = "fly", time.time()
                elif dt > 60:
                    print(f"SMOKE FAIL: no carried box after {dt:.0f}s ({track['msg']})")
                    closing["want"] = True
                    return
            elif ph == "fly" and dt >= args.smoke:
                out_dir.mkdir(parents=True, exist_ok=True)
                with frame_lock:
                    f = None if live["bgr"] is None else live["bgr"].copy()
                p = out_dir / "smoke.png"
                if f is not None:
                    draw_overlay(f, track["box"], track.get("label") or "",
                                 track["on_target"], scale=f.shape[1] / CAM_W,
                                 delivered=track["delivered"])
                    cv2.imwrite(str(p), f)
                n, e, d = pilot["ned"]
                mn, me, _ = pilot["ned_v"]
                cn, ce, _ = pilot["vel"]
                print(f"smoke OK: {p}\n  {gtimes.cget('text')}\n  {gmodes.cget('text')}"
                      f"\n  ned N{n:.1f} E{e:.1f} alt {-d:.1f}"
                      f"  cmd {(cn**2 + ce**2) ** 0.5:.1f} m/s"
                      f"  got {(mn**2 + me**2) ** 0.5:.1f} m/s"
                      f"\n  {track['msg']}", flush=True)
                closing["want"] = True
                return
            root.after(500, smoke_step)

        root.after(3000, smoke_step)

    if args.selftest:
        root.withdraw()  # runs the real widgets, shows no window
        root.after(100, lambda: selftest(root, client, spawned, bg,
                                         spawn_vehicles, spawn_walkers, clear,
                                         {"arm": _arm_track, "deliver": do_deliver,
                                          "drop": do_drop, "track": track,
                                          "acquire": acquire, "follow": follow_mode,
                                          "eff_follow": pilot_follow_mode,
                                          "box": model_box, "press": on_press,
                                          "held": held, "designate": designate,
                                          "follow_caption": do_follow,
                                          "close": unpause_on_exit}))

    try:
        root.mainloop()
    except KeyboardInterrupt:
        root.destroy()
    finally:
        # every exit path, not just the X button. stop_carla is idempotent.
        stop_carla(carla_proc)


def selftest(*a):
    # a failing assert inside a Tk callback only prints, the loop keeps running
    try:
        _selftest(*a)
    except Exception:
        traceback.print_exc()
        a[0].destroy()
        raise SystemExit(1)


def _check_modes(md):
    """The WARM/COLD + follow-authority state machine, through the real widgets.

    No Jetson and no copter needed: _arm_track only sets the stance (the grounding
    thread is started by its callers, not by it), so this exercises exactly the
    bookkeeping that decides whether a box is the operator's or the system's.
    """
    track, follow = md["track"], md["follow"]

    # WARM: designating starts maintaining. Nobody has asked, so nothing is delivered
    # and no control law may see the box -- that is the whole warm-start premise.
    md["acquire"].set("warm")
    md["arm"]()
    assert track["delivered"] is False and track["cmd_t"] is None
    follow.set("assist")
    track["box"] = [10, 10, 20, 20]      # pretend the carry published one
    assert md["box"]() is None, "an undelivered box must not reach a control law"
    md["deliver"]()
    assert track["delivered"] is True and track["cmd_t"] is not None
    assert track["deliver_s"] is not None and track["deliver_s"] < 0.5, \
        f"a maintained track must deliver instantly, got {track['deliver_s']}"
    assert md["box"]() is not None, "a delivered box is what control steers on"

    # COLD: the designation IS the command, so the clock is already running and
    # whatever comes back is the operator's (and stale) from the first frame.
    md["acquire"].set("cold")
    md["arm"]()
    assert track["delivered"] is True and track["cmd_t"] is not None
    assert track["deliver_s"] is None, "cold has not delivered until a box exists"

    # AUTO is position authority; with no copter it must report itself unavailable
    # rather than quietly steering the camera instead.
    follow.set("auto")
    assert md["eff_follow"]() == "manual", "auto with no copter must not engage"
    follow.set("assist")
    assert md["eff_follow"]() == "assist"

    # t cycles the three modes, and exactly once per press. The autorepeat guard is
    # what the second press-without-release checks: X11 fires press events while the
    # key is down, and without the guard a hold would cycle dozens of times.
    class _K:
        keysym = "t"
    follow.set("manual")
    for want in ("assist", "auto", "manual"):
        md["press"](_K())
        assert follow.get() == want, f"t should reach {want}, got {follow.get()}"
        md["press"](_K())                       # autorepeat: must not cycle again
        assert follow.get() == want, "held t cycled twice -- autorepeat guard gone"
        md["held"].discard("t")                 # the release
    assert follow.get() == "manual"

    # designate=oracle reads a GT box off a designated actor, and the caption button
    # designates nobody. It must refuse, not silently fall back to the VLM -- a demo
    # that quietly swaps the designation source invalidates every number on it.
    md["designate"].set("oracle")
    before = track["stop"]              # _arm_track swaps in a NEW Event, so identity
    md["follow_caption"]()              # is exactly the "did a follow start" question
    assert track["stop"] is before, "oracle + caption must not arm a new follow"
    assert "oracle" in track["msg"], f"and must say why, got {track['msg']!r}"
    md["designate"].set("vlm")

    md["drop"]()
    assert track["box"] is None and track["delivered"] is True
    print("modes ok")


def _selftest(root, client, spawned, bg, spawn_vehicles, spawn_walkers, clear, md):
    """Spawn through the real buttons, assert the actors exist and move."""
    _check_modes(md)
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
    # counted separately: a passing total can hide one whole class standing still.
    # Cars are what this tool designates and tracks, so their motion stays a hard gate.
    assert drove >= 3, f"only {drove} cars moved -- autopilot not running"
    # Walker MOTION is not gated, and that is a measured decision rather than a
    # convenience: on this CARLA 0.9.16 / Town10HD_Opt install the AI controllers move
    # nobody, reproduced OUTSIDE this UI with CARLA's own canonical sequence (batch
    # spawn on get_random_location_from_navigation -> controller.ai.walker attached ->
    # wait_for_tick -> start -> go_to_location -> set_max_speed(1.4)): 5/5 walkers moved
    # 0.00 m in 5 s while the navmesh answered with valid points. It is the simulator,
    # not the tool, and the demo tracks vehicles. Still reported, never silently passed.
    if walked < 3:
        print(f"  NOTE: {walked}/{len(peds)} walkers moved -- walker AI is dead on this "
              f"CARLA build (see CARLA_DEBUG_UI.md); pedestrians are static scenery",
              flush=True)

    clear()
    # get_actors() keeps listing destroyed actors and Actor.is_alive is a stale
    # client-side cache -- the world snapshot is the only server truth here.
    snap = world.get_snapshot()
    left = [a for a in world.get_actors(ids)
            if a.type_id.startswith(("vehicle", "walker")) and snap.find(a.id)]
    assert not left, f"{len(left)} actors survived clear"
    print("ok")
    md["close"]()   # the real teardown, so the selftest leaks no camera either


if __name__ == "__main__":
    main()
