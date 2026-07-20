#!/usr/bin/env python3
"""
carla_render.py -- CARLA as a pose-slaved renderer (P6.1 capability gate).

Replaces Gazebo in the Part VI rig. SITL stays the physics; this drives a free
camera to the pose the autopilot reports, exactly as run_phase_c.py drives the
Gazebo camera via set_pose. Nothing about the control loop changes.

    # terminal 1
    ~/carla/CARLA_0.9.16/CarlaUE4.sh -RenderOffScreen -quality-level=Epic
    # terminal 2
    .venv-ft/bin/python runners/carla_render.py --gate --out experiments/.../runs/

Gates G1-G5 (see experiments/2026-07-20-p61-carla-renderer/README.md). Pose comes
from a scripted sweep by default; --mavlink drains LOCAL_POSITION_NED from SITL
instead, which is what G3 actually claims.

COORDINATE MAPPING IS A HYPOTHESIS UNTIL A FRAME IS VIEWED. ArduPilot reports
right-handed NED metres; CARLA uses the left-handed Unreal frame (X North,
Y East, Z up, metres) with rotations in degrees. See ned_to_carla().
"""
import argparse
import json
import math
import random
import sys
import threading
import time
from pathlib import Path

import carla
import cv2
import numpy as np

TOWN = "Town10HD_Opt"        # ponytail: the release's default photoreal town. Swap via --town.
W, H, FOV = 640, 480, 90
FIXED_DT = 0.05              # 20 Hz, matches the P6.0 control loop
SEED = 20260720              # same traffic layout + TM decisions every run

# ponytail: async, not synchronous. Sync makes the CLIENT the clock master, but
# SITL already is one and runs in wall-clock real time -- and worse, sim time then
# only advances on world.tick(), so a 4.5 s VLM acquire costs ZERO sim seconds and
# the delivery lag that Parts IV/V exist to measure stops existing. Reproducibility
# comes from SEED + logged tracks + n>=25, not from tick determinism (bit-exact
# replay needs full lockstep, rejected in docs/decisions/part6-flight.md).

_latest = {"bgr": None, "n": 0}
_lock = threading.Lock()


def ned_to_carla(n, e, d, yaw_rad=0.0, pitch_deg=-90.0):
    """NED metres + yaw -> carla.Transform.

    N and E map straight through (CARLA Y is East-positive like NED). Down flips
    sign because CARLA Z is up. pitch_deg=-90 is intended to be nadir -- that sign
    is the one that aimed the Phase C camera at the sky for a month, so G3 confirms
    it against a viewed frame before any number is recorded.
    """
    return carla.Transform(
        carla.Location(x=float(n), y=float(e), z=float(-d)),
        carla.Rotation(pitch=float(pitch_deg), yaw=math.degrees(yaw_rad), roll=0.0),
    )


def _on_image(img):
    """carla.Image -> BGR ndarray. raw_data is BGRA."""
    buf = np.frombuffer(img.raw_data, np.uint8).reshape(img.height, img.width, 4)
    with _lock:
        _latest["bgr"] = np.ascontiguousarray(buf[:, :, :3])
        _latest["n"] += 1


def dominant_frac(frame):
    """Fraction of pixels that are the single most common colour.

    >0.99 means a blank render, not a night scene. Cheap mechanical version of the
    'look at it' rule -- it catches the failure without relying on anyone looking.
    """
    flat = frame.reshape(-1, frame.shape[2])
    return np.unique(flat, axis=0, return_counts=True)[1].max() / len(flat)


ALT = 100.0                  # scripted-sweep altitude, m AGL; --alt overrides


def scripted_pose(t):
    """Synthetic NED sweep: 60 m straight line at ALT, for G1/G2/G4/G5."""
    return (60.0 * t / 20.0, 0.0, -ALT, 0.0)


class MavlinkPose:
    """Drains LOCAL_POSITION_NED from SITL. Same source run_phase_c.py uses.

    Flies the copter on this same connection when `fly_alt` is set: SITL
    exposes one TCP client port, and without MAVProxy no second endpoint
    streams telemetry, so the commander and the renderer must share a link.
    """

    def __init__(self, url="tcp:127.0.0.1:5760", fly_alt=None, fly_north=8.0):
        import sitl_fly_leg as fly
        self.m = fly.connect(url)
        self.stop = None
        if fly_alt is not None:
            reached = fly.arm_and_takeoff(self.m, fly_alt)
            print(f"G3: airborne at {reached:.1f} m, holding {fly_north} m/s north")
            self.stop = fly.fly_in_background(self.m, fly_north)
        self.last = (0.0, 0.0, -(fly_alt or 100.0), 0.0)

    def __call__(self, _t):
        while True:  # drain to newest -- a stale pose is a lagging camera
            msg = self.m.recv_match(type="LOCAL_POSITION_NED", blocking=False)
            if msg is None:
                break
            self.last = (msg.x, msg.y, msg.z, self.last[3])
        att = self.m.recv_match(type="ATTITUDE", blocking=False)
        if att is not None:
            self.last = (*self.last[:3], att.yaw)
        return self.last


def setup_world(client, town, n_vehicles):
    world = client.load_world(town)
    settings = world.get_settings()
    settings.synchronous_mode = False
    settings.fixed_delta_seconds = FIXED_DT   # substep cap, not a pace
    world.apply_settings(settings)

    tm = client.get_trafficmanager(8000)
    tm.set_synchronous_mode(False)
    tm.set_random_device_seed(SEED)

    rng = random.Random(SEED)
    bp_lib = world.get_blueprint_library()
    car_bps = [b for b in bp_lib.filter("vehicle.*")
               if int(b.get_attribute("number_of_wheels")) == 4]
    spawns = world.get_map().get_spawn_points()
    rng.shuffle(spawns)

    vehicles = []
    for sp in spawns[:n_vehicles]:
        v = world.try_spawn_actor(rng.choice(car_bps), sp)
        if v is not None:
            v.set_autopilot(True, 8000)
            vehicles.append(v)

    cam_bp = bp_lib.find("sensor.camera.rgb")
    cam_bp.set_attribute("image_size_x", str(W))
    cam_bp.set_attribute("image_size_y", str(H))
    cam_bp.set_attribute("fov", str(FOV))
    cam_bp.set_attribute("sensor_tick", str(FIXED_DT))   # 20 Hz frame delivery
    cam = world.spawn_actor(cam_bp, ned_to_carla(*scripted_pose(0.0)))
    cam.listen(_on_image)
    return world, cam, vehicles


def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    client = carla.Client(args.host, args.port)
    client.set_timeout(60.0)          # map load on a cold shader cache is slow
    print(f"G1: connected, server {client.get_server_version()}, "
          f"client {client.get_client_version()}")

    world, cam, vehicles = setup_world(client, args.town, args.vehicles)
    print(f"G1: loaded {args.town}, spawned {len(vehicles)}/{args.vehicles} vehicles")

    pose_fn = (MavlinkPose(args.mavlink, fly_alt=args.alt, fly_north=args.north)
               if args.mavlink else scripted_pose)

    frames, stamps, poses, realised = {}, [], [], []
    t0 = time.time()
    n_ticks = int(args.seconds / FIXED_DT)
    for i in range(n_ticks):
        t = i * FIXED_DT
        ned = pose_fn(t)
        cam.set_transform(ned_to_carla(*ned, pitch_deg=args.pitch))
        # async: the server renders on its own clock, so pace to wall time instead
        # of driving it. Sim time == wall time == SITL time, one clock for all three.
        slack = (t0 + (i + 1) * FIXED_DT) - time.time()
        if slack > 0:
            time.sleep(slack)
        stamps.append(time.time())
        poses.append(ned)
        # what the SERVER actually placed the camera at -- asking CARLA rather than
        # assuming set_transform took is the whole point of the slaving proof
        loc = cam.get_transform().location
        realised.append((loc.x, loc.y, loc.z))
        with _lock:
            frame = _latest["bgr"]
        # keep a frame near the start, middle and end -- never frame 0, it is
        # routinely black before the first render completes
        if frame is not None and i in (n_ticks // 4, n_ticks // 2, n_ticks - 1):
            frames[i] = frame.copy()

    # --- teardown before asserting, so a failed gate still leaves a clean server ---
    if getattr(pose_fn, "stop", None) is not None:
        pose_fn.stop.set()
    cam.stop()
    cam.destroy()
    client.apply_batch([carla.command.DestroyActor(v) for v in vehicles])

    # --- gates ---
    res = {"town": args.town, "vehicles": len(vehicles), "ticks": n_ticks,
           "pitch_deg": args.pitch, "pose_source": "mavlink" if args.mavlink else "scripted"}

    assert frames, "G2 FAIL: no frames received from the camera sensor"
    for i, f in sorted(frames.items()):
        p = out / f"frame_{i:05d}.png"
        cv2.imwrite(str(p), f)
        print(f"  wrote {p}")
    mid = frames[sorted(frames)[len(frames) // 2]]
    res["dominant_frac"] = float(dominant_frac(mid))
    print(f"G2: dominant colour fraction {res['dominant_frac']:.3f}")
    assert res["dominant_frac"] < 0.99, "G2 FAIL: blank render"

    keys = sorted(frames)
    identical = np.array_equal(frames[keys[0]], frames[keys[-1]])
    res["frames_identical"] = bool(identical)
    assert not identical, "G4 FAIL: first and last frame byte-identical (dead feed)"

    dt = np.diff(stamps)
    res["mean_hz"] = float(1.0 / dt.mean())
    res["ticks_under_15hz"] = int((1.0 / dt < 15.0).sum())
    res["tick_dt"] = [float(x) for x in dt]
    print(f"G5: {res['mean_hz']:.2f} Hz mean, {res['ticks_under_15hz']} ticks under 15 Hz")

    res["frames_received"] = _latest["n"]
    res["pose_first"], res["pose_last"] = poses[0], poses[-1]
    res["pose_track"] = [list(p) for p in poses]
    res["camera_track"] = [list(c) for c in realised]
    # slaving error: commanded NED -> CARLA vs where the server put the camera
    err = [math.dist((n, e, -d), c) for (n, e, d, _), c in zip(poses, realised)]
    res["slave_err_max_m"] = float(max(err))
    res["slave_err_mean_m"] = float(sum(err) / len(err))
    print(f"G3: slaving error mean {res['slave_err_mean_m']:.3f} m, "
          f"max {res['slave_err_max_m']:.3f} m")
    (out / "results.json").write_text(json.dumps(res, indent=2))
    print(f"\nwrote {out/'results.json'}")
    print("G2/G3 are NOT satisfied until the written frames are opened and viewed.")
    return res


def main():
    global ALT
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--town", default=TOWN)
    ap.add_argument("--vehicles", type=int, default=30)
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--pitch", type=float, default=-90.0, help="camera pitch deg; -90 = nadir (CONFIRMED by viewed frame)")
    ap.add_argument("--alt", type=float, default=ALT, help="scripted-sweep altitude, m AGL")
    ap.add_argument("--mavlink", nargs="?", const="tcp:127.0.0.1:5760", default=None,
                    help="drain LOCAL_POSITION_NED from SITL instead of the scripted sweep")
    ap.add_argument("--north", type=float, default=8.0, help="--mavlink leg velocity, m/s")
    ap.add_argument("--out", default="runs/carla-gate")
    ap.add_argument("--gate", action="store_true", help="accepted for symmetry; gates always run")
    args = ap.parse_args()
    ALT = args.alt
    try:
        run(args)
    except AssertionError as e:
        print(f"\n{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
