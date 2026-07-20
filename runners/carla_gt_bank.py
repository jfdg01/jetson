#!/usr/bin/env python3
"""carla_gt_bank.py -- deterministic CARLA ground-truth capture bank.

Capture, not flight (PART6-SLATE 4.1): no controller consumes a delivery lag here,
so this runs SYNCHRONOUS and buys determinism. carla_render.py stays async for the
flight rig, where sim time must advance on its own or the lag Parts IV/V exist to
measure would stop existing. Every manifest this writes carries mode="sync".

Unnumbered infrastructure. P6.2 keeps its committed meaning (closed-loop
select-and-follow vs oracle-driven control) -- see the campaign README.

Emits per clip:
    <out>/<clip>/frames/<i:05d>.jpg    the render
    <out>/<clip>/gt.jsonl              one row per frame, every GT box (committed)
    <out>/<clip>/manifest.json         config + seed + gate numbers (committed)

    .venv-ft/bin/python runners/carla_gt_bank.py --port 2100 --gate-a
    .venv-ft/bin/python runners/carla_gt_bank.py --port 2100 --clips 25
"""
import argparse
import json
import math
import queue
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

import carla
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from carla_debug_ui import CARLA_SH, ensure_carla, project, stop_carla  # noqa: E402

TOWN = "Town10HD_Opt"
W, H, FOV = 640, 480, 90
FIXED_DT = 0.05                  # 20 Hz, matches the P6.0 control loop
SEED = 20260721
MIN_FREE_GB = 10.0               # measured 2.8 GB/h following, ~19 GB/h worst case
POWER_W = 200                    # user-set 3090 cap; re-asserted per clip

# Derived from the enum rather than hardcoded: the semantic palette was renumbered
# when Car/Truck/Bus/Motorcycle split out of a single "Vehicles" tag, and a stale
# integer here would silently score every occlusion check as zero fill.
VEH_TAGS = [int(getattr(carla.CityObjectLabel, n))
            for n in ("Car", "Truck", "Bus", "Motorcycle", "Bicycle", "Rider")
            if hasattr(carla.CityObjectLabel, n)]


# ---------------------------------------------------------------- pure helpers

def verts_to_box(verts, cam_tf, w=W, h=H, fov=FOV):
    """World-space vertices -> axis-aligned pixel box + how many vertices projected.

    Deliberately NOT the all-8-or-None rule carla_debug_ui.actor_box uses. That
    rule keeps a tracker from matching a half-visible actor, which is right for
    MATCHING and wrong for CAPTURE: a target close enough to put one vertex behind
    the camera plane is exactly the interesting case, and dropping it silently
    scores as drift (PART6-SLATE 2.3f). Keep the box, record n_proj, let the
    consumer decide.
    """
    pts = [project(p, cam_tf, w, h, fov) for p in verts]
    ok = [p for p in pts if p is not None]
    if not ok:
        return None, 0
    xs, ys = [p[0] for p in ok], [p[1] for p in ok]
    return (min(xs), min(ys), max(xs), max(ys)), len(ok)


def box_area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def clip_to_frame(b, w=W, h=H):
    """Intersection with the image rect, or None when fully outside."""
    x1, y1 = max(0.0, b[0]), max(0.0, b[1])
    x2, y2 = min(float(w), b[2]), min(float(h), b[3])
    return (x1, y1, x2, y2) if x2 > x1 and y2 > y1 else None


def veh_fill(tags, box, w=W, h=H):
    """Fraction of a GT box covered by vehicle-class pixels, or None if off-frame.

    The occlusion proxy. Corner-projected GT has no depth test (PART6-SLATE 2.3c),
    so a car parked behind a building still projects a clean box. This measures how
    much of the box is actually vehicle pixels, which is the cheapest thing that
    tells the two apart. Tag-level, not instance-level: it cannot say WHICH vehicle
    fills the box, so two overlapping cars both read high. Documented limitation.
    # ponytail: tag-level fill. Instance-level needs an instance-segmentation
    # camera and a per-actor id map; add it only if an audit actually confuses
    # two adjacent vehicles.
    """
    x1, y1 = max(0, int(box[0])), max(0, int(box[1]))
    x2, y2 = min(w, int(box[2])), min(h, int(box[3]))
    if x2 <= x1 or y2 <= y1:
        return None
    return float(np.isin(tags[y1:y2, x1:x2], VEH_TAGS).mean())


def analytic_area(extent_xy, z, w=W, fov=FOV):
    """Predicted pixel area of a nadir-viewed box of known world footprint.

    px_per_m = (W/2)/tan(fov/2)/z. A box in the wrong place, at the wrong scale, or
    built from the wrong transform misses this badly -- which is the point: the
    EnvironmentObject box is world-space, and passing its own transform instead of
    the identity doubles its coordinates. Monotonic shrink alone would NOT catch
    that; this does.
    """
    f = (w / 2.0) / math.tan(math.radians(fov) / 2.0)
    return (2 * extent_xy[0]) * (2 * extent_xy[1]) * (f / z) ** 2


def dominant_frac(frame):
    """>0.99 is a blank render, not a night scene."""
    flat = frame.reshape(-1, frame.shape[2])
    return float(np.unique(flat, axis=0, return_counts=True)[1].max() / len(flat))


def mean_absdiff(a, b):
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))


def free_gb(path="."):
    return shutil.disk_usage(path).free / 1e9


# ---------------------------------------------------------------- carla plumbing

def nadir(n, e, alt, yaw=0.0, pitch=-90.0):
    """Metres -> carla.Transform. pitch -90 = nadir, CONFIRMED by a viewed frame
    (proof/probe-nadir-town10.png). The opposite sign aimed the Phase C camera at
    the sky for a month, so this is never asserted from a log."""
    return carla.Transform(carla.Location(x=float(n), y=float(e), z=float(alt)),
                           carla.Rotation(pitch=float(pitch), yaw=float(yaw), roll=0.0))


def reassert_power(w=POWER_W):
    """The 3090 cap is not persistent (nvidia-smi -pm needs an interactive
    password), so a driver reload would restore 350 W and every rate number after
    that point would be a different config. Cheap to re-assert per clip."""
    try:
        subprocess.run(["sudo", "-n", "nvidia-smi", "-pl", str(w)],
                       capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=power.limit",
                              "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20).stdout
        return float(out.strip().split("\n")[0])
    except (OSError, subprocess.SubprocessError, ValueError):
        return -1.0


def env_car_cache(world):
    """Static parked cars, pre-resolved to world vertices (they never move).

    identity transform: an EnvironmentObject's bounding_box is ALREADY world-space.
    Passing o.transform doubles its coordinates (-51,166 -> -102,333) and lands 29
    boxes somewhere plausible but wrong. Verified live, runs/probe/results.json.
    """
    return [{"id": int(o.id), "name": o.name, "loc": o.transform.location,
             "extent": (o.bounding_box.extent.x, o.bounding_box.extent.y,
                        o.bounding_box.extent.z),
             "verts": list(o.bounding_box.get_world_vertices(carla.Transform()))}
            for o in world.get_environment_objects(carla.CityObjectLabel.Car)]


def _round_opt(v, nd):
    return None if v is None else round(v, nd)


def _row(kind, oid, name, b, n_proj, loc, cam_loc, tags, w, h):
    vis = clip_to_frame(b, w, h)
    return {
        "kind": kind, "id": int(oid), "name": name,
        "box": [round(v, 2) for v in b],
        "box_vis": [round(v, 2) for v in vis] if vis else None,
        "area_px": round(box_area(b), 1),
        "area_vis_px": round(box_area(vis), 1) if vis else 0.0,
        "n_proj": n_proj,                     # <8 means partly behind the camera
        "partial": n_proj < 8,
        # a clipped box can still be sub-pixel after int truncation, and veh_fill
        # says None for that -- so ask it, do not infer it from `vis`
        "veh_fill": _round_opt(veh_fill(tags, vis, w, h)
                               if (tags is not None and vis) else None, 4),
        "range_m": round(math.dist((loc.x, loc.y, loc.z),
                                   (cam_loc.x, cam_loc.y, cam_loc.z)), 2),
    }


def gt_rows(world, cam_tf, env, tags=None, w=W, h=H, fov=FOV):
    """Every GT box for this frame: moving vehicles AND static parked meshes.

    The two buckets need DIFFERENT calls -- an actor's bounding_box is local and
    takes its transform; an EnvironmentObject's is world-space and takes the
    identity. This asymmetry is the whole reason for the live probe.
    """
    rows, cam_loc = [], cam_tf.location
    for v in world.get_actors().filter("vehicle.*"):
        tf = v.get_transform()
        b, n = verts_to_box(v.bounding_box.get_world_vertices(tf), cam_tf, w, h, fov)
        if b is not None:
            rows.append(_row("vehicle", v.id, v.type_id, b, n, tf.location,
                             cam_loc, tags, w, h))
    for o in env:
        b, n = verts_to_box(o["verts"], cam_tf, w, h, fov)
        if b is not None:
            rows.append(_row("static", o["id"], o["name"], b, n, o["loc"],
                             cam_loc, tags, w, h))
    return rows


def _cam_bp(world, sensor):
    bp = world.get_blueprint_library().find(sensor)
    bp.set_attribute("image_size_x", str(W))
    bp.set_attribute("image_size_y", str(H))
    bp.set_attribute("fov", str(FOV))
    return bp


def spawn_cams(world, tf):
    """RGB + semantic segmentation at the SAME pose (seg feeds veh_fill)."""
    out = []
    for name in ("sensor.camera.rgb", "sensor.camera.semantic_segmentation"):
        c = world.spawn_actor(_cam_bp(world, name), tf)
        q = queue.Queue()
        c.listen(q.put)
        out.append((c, q))
    return out


def _drain_to(q, fid, timeout=20.0):
    img = q.get(timeout=timeout)
    while img.frame < fid:
        img = q.get(timeout=timeout)
    if img.frame != fid:
        raise AssertionError(f"sensor frame {img.frame} != tick {fid} (stale GT)")
    return img


def grab(world, cams):
    """One synchronous step -> (bgr, tags, tick).

    Asserts both sensors belong to THIS tick. The probe measured delta 0 on 40/40,
    but an off-by-one makes every GT box one frame stale -- the exact defect P5.13
    was charged with, invisible in any log -- so it is asserted every frame.
    """
    tick = world.tick()
    (rgb_c, rgb_q), (seg_c, seg_q) = cams
    rgb = _drain_to(rgb_q, tick)
    seg = _drain_to(seg_q, tick)
    bgr = np.ascontiguousarray(
        np.frombuffer(rgb.raw_data, np.uint8).reshape(rgb.height, rgb.width, 4)[:, :, :3])
    tags = np.frombuffer(seg.raw_data, np.uint8).reshape(
        seg.height, seg.width, 4)[:, :, 2]        # BGRA: red channel carries the tag
    return bgr, tags, int(tick)


def setup_world(client, town, n_vehicles, seed, dt=FIXED_DT):
    """Fresh world, seeded traffic, synchronous. Returns (world, tm, vehicles).

    Spawn drops are SILENT server-side when a point is occupied, and a bank with a
    different actor count than its pair is not a paired comparison, so the caller
    asserts the count rather than trusting it.
    """
    world = client.load_world(town)
    s = world.get_settings()
    s.synchronous_mode = True
    s.fixed_delta_seconds = dt
    world.apply_settings(s)

    tm = client.get_trafficmanager(8000)
    tm.set_synchronous_mode(True)
    tm.set_random_device_seed(seed)

    rng = random.Random(seed)
    cars = [b for b in world.get_blueprint_library().filter("vehicle.*")
            if int(b.get_attribute("number_of_wheels")) == 4]
    cars.sort(key=lambda b: b.id)            # blueprint order is not guaranteed
    spawns = world.get_map().get_spawn_points()
    rng.shuffle(spawns)

    vehicles = []
    for sp in spawns[:n_vehicles]:
        v = world.try_spawn_actor(rng.choice(cars), sp)
        if v is not None:
            v.set_autopilot(True, 8000)
            vehicles.append(v)
    for _ in range(20):                      # settle traffic deterministically
        world.tick()
    return world, tm, vehicles


def teardown(client, cams, vehicles):
    for c, _ in cams:
        c.stop()
        c.destroy()
    if vehicles:
        client.apply_batch([carla.command.DestroyActor(v) for v in vehicles])


# ---------------------------------------------------------------- clip capture

def clip_plan(i, seed=SEED):
    """Deterministic per-clip camera flight. Altitude is swept on purpose: the
    range/size envelope downstream needs targets at a spread of pixel sizes, and a
    bank captured at one altitude cannot answer it."""
    rng = random.Random(seed + i * 7919)
    return {
        "clip": f"clip{i:02d}",
        "alt": [40.0, 60.0, 80.0, 100.0, 120.0][i % 5],
        "n0": rng.uniform(-60, 60), "e0": rng.uniform(-60, 60),
        "heading": rng.uniform(0, 360),
        "speed": rng.choice([0.0, 4.0, 8.0, 12.0]),
        "yaw": rng.uniform(0, 360),
        "vehicles": 40,
        "seed": seed + i,
    }


def capture_clip(client, plan, out, seconds, dt=FIXED_DT, max_frames=None):
    """One clip. Resumable: a complete manifest means skip.

    Resumability is not a nicety -- CARLA segfaults, and a night that loses 24
    good clips because the 25th died is a night wasted.
    """
    d = out / plan["clip"]
    man_p = d / "manifest.json"
    if man_p.exists():
        try:
            man = json.loads(man_p.read_text())
            if man.get("complete"):
                print(f"  {plan['clip']}: complete, skipping")
                return man
        except (json.JSONDecodeError, OSError):
            pass
    (d / "frames").mkdir(parents=True, exist_ok=True)

    if free_gb() < MIN_FREE_GB:
        raise AssertionError(f"free disk {free_gb():.1f} GB < {MIN_FREE_GB} GB, aborting")
    pl = reassert_power()

    world, _tm, vehicles = setup_world(client, TOWN, plan["vehicles"], plan["seed"])
    assert len(vehicles) >= int(0.8 * plan["vehicles"]), (
        f"only {len(vehicles)}/{plan['vehicles']} vehicles spawned -- occupied spawn "
        f"points are dropped silently and a short world is not a paired world")
    env = env_car_cache(world)
    assert env, "no static Car meshes found -- ParkedVehicles layer missing?"

    n_ticks = min(int(seconds / dt), max_frames or 10 ** 9)
    hdg = math.radians(plan["heading"])
    cams = spawn_cams(world, nadir(plan["n0"], plan["e0"], plan["alt"], plan["yaw"]))

    n, mid, last, t0 = 0, None, None, time.time()
    try:
        with (d / "gt.jsonl").open("w") as fh:
            for i in range(n_ticks):
                t = i * dt
                cn = plan["n0"] + plan["speed"] * t * math.cos(hdg)
                ce = plan["e0"] + plan["speed"] * t * math.sin(hdg)
                cams[0][0].set_transform(nadir(cn, ce, plan["alt"], plan["yaw"]))
                cams[1][0].set_transform(nadir(cn, ce, plan["alt"], plan["yaw"]))
                bgr, tags, tick = grab(world, cams)
                # the pose the SERVER used, not the one we asked for: GT projected
                # from the commanded pose would be subtly and invisibly wrong
                real_tf = cams[0][0].get_transform()
                rows = gt_rows(world, real_tf, env, tags)
                cv2.imwrite(str(d / "frames" / f"{i:05d}.jpg"), bgr,
                            [cv2.IMWRITE_JPEG_QUALITY, 92])
                fh.write(json.dumps({
                    "i": i, "tick": tick, "t": round(t, 3),
                    "cam": [round(real_tf.location.x, 3), round(real_tf.location.y, 3),
                            round(real_tf.location.z, 3)],
                    "cam_rot": [round(real_tf.rotation.pitch, 2),
                                round(real_tf.rotation.yaw, 2),
                                round(real_tf.rotation.roll, 2)],
                    "gt": rows}) + "\n")
                n += 1
                if i == n_ticks // 2:
                    mid = bgr.copy()
                    cv2.imwrite(str(d / "mid.png"), bgr)
                last = bgr
                if i % 200 == 0 and free_gb() < MIN_FREE_GB:
                    raise AssertionError(f"free disk {free_gb():.1f} GB mid-clip, aborting")
    finally:
        teardown(client, cams, vehicles)

    hz = n / max(1e-6, time.time() - t0)
    dom = dominant_frac(mid if mid is not None else last)
    identical = bool(np.array_equal(mid, last)) if mid is not None else True
    man = {**plan, "mode": "sync", "town": TOWN, "dt": dt, "frames": n,
           "spawned": len(vehicles), "n_static_cars": len(env),
           "capture_hz": round(hz, 2), "power_limit_w": pl,
           "dominant_frac": round(dom, 4), "mid_last_identical": identical,
           "cam_wh_fov": [W, H, FOV], "complete": True}
    assert dom < 0.99, f"{plan['clip']}: blank render (dominant {dom:.3f})"
    assert not identical, f"{plan['clip']}: mid and last frame identical (dead feed)"
    man_p.write_text(json.dumps(man, indent=2))
    print(f"  {plan['clip']}: {n} frames, {hz:.1f} Hz, {len(vehicles)} veh, "
          f"{len(env)} static, dom {dom:.3f}")
    return man


# ---------------------------------------------------------------- G-A

def gate_a(client, out, alts=(25.0, 40.0, 60.0, 85.0, 120.0)):
    """GT projection verified by looking AND by an assert that can fail.

    Monotonic shrink alone is weak: a receding camera shrinks almost any box,
    including one built from the wrong transform. So the sharp check is ANALYTIC
    (see analytic_area) and monotonicity is the cheap second. The lowest altitude
    exercises hazard 2.3f -- close enough that vertices fall behind the camera
    plane -- and the seg-camera fill says whether the box is on vehicle pixels at
    all rather than merely somewhere plausible.
    """
    d = out / "gate_a"
    d.mkdir(parents=True, exist_ok=True)
    world, _tm, vehicles = setup_world(client, TOWN, 12, SEED)
    env = env_car_cache(world)
    ref = min(env, key=lambda o: math.hypot(o["loc"].x, o["loc"].y))
    print(f"G-A reference: {ref['name']} at ({ref['loc'].x:.1f},{ref['loc'].y:.1f}) "
          f"extent {tuple(round(v, 2) for v in ref['extent'])}")

    recs, cams = [], spawn_cams(world, nadir(ref["loc"].x, ref["loc"].y, alts[0]))
    try:
        for alt in alts:
            tf = nadir(ref["loc"].x, ref["loc"].y, alt)
            for c, _ in cams:
                c.set_transform(tf)
            for _ in range(6):                 # settle TAA + auto-exposure
                bgr, tags, _ = grab(world, cams)
            real_tf = cams[0][0].get_transform()
            rows = gt_rows(world, real_tf, env, tags)
            me = next((r for r in rows if r["id"] == ref["id"]), None)
            z = real_tf.location.z - ref["loc"].z
            pred = analytic_area(ref["extent"], z)

            ov = bgr.copy()
            for r in rows:
                if r["box_vis"] is None:
                    continue
                x1, y1, x2, y2 = [int(v) for v in r["box_vis"]]
                c = (0, 255, 0) if r["kind"] == "vehicle" else (255, 160, 0)
                if me and r["id"] == me["id"]:
                    c = (0, 0, 255)
                cv2.rectangle(ov, (x1, y1), (x2, y2), c, 2)
            cv2.putText(ov, f"alt {alt:.0f}m pred {pred:.0f} meas "
                        f"{me['area_px'] if me else -1:.0f} fill "
                        f"{me['veh_fill'] if me else None}",
                        (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            p = d / f"gt_alt{int(alt):03d}.png"
            cv2.imwrite(str(p), ov)
            recs.append({"alt": alt, "z": round(z, 2),
                         "area": me["area_px"] if me else None,
                         "n_proj": me["n_proj"] if me else None,
                         "veh_fill": me["veh_fill"] if me else None,
                         "pred_area": round(pred, 1),
                         "ratio": round(me["area_px"] / pred, 3) if me else None,
                         "n_gt": len(rows), "png": str(p)})
            print(f"  alt {alt:6.1f}  meas {recs[-1]['area']}  pred {pred:8.1f}  "
                  f"ratio {recs[-1]['ratio']}  n_proj {recs[-1]['n_proj']}  "
                  f"fill {recs[-1]['veh_fill']}")
    finally:
        teardown(client, cams, vehicles)

    got = [r for r in recs if r["area"] is not None]
    areas = [r["area"] for r in got]
    ratios = [r["ratio"] for r in got]
    mono = all(a > b for a, b in zip(areas, areas[1:])) and len(areas) >= 5
    scale_ok = bool(ratios) and all(0.75 <= r <= 1.35 for r in ratios)
    res = {"gate": "G-A", "ref": ref["name"],
           "ref_extent": [round(v, 3) for v in ref["extent"]],
           "records": recs, "monotonic_decreasing": mono, "ratios": ratios,
           "analytic_scale_ok": scale_ok,
           "verdict": "PASS" if (mono and scale_ok) else "FAIL",
           "note": "NOT satisfied until the overlays are opened and viewed"}
    (d / "results.json").write_text(json.dumps(res, indent=2))
    print(f"G-A: monotonic={mono} analytic_scale_ok={scale_ok} -> {res['verdict']}")
    return res


# ---------------------------------------------------------------- G-C

def gate_c(client, out, n_frames=40, n_vehicles=40):
    """Does pairing hold across an environment-object toggle?

    Byte-identity is the wrong bar: TAA, motion blur and auto-exposure carry state
    across frames, so it fails for reasons unrelated to the toggle and then gets
    softened until it stops gating. So: measure the SAME-CONFIG repeat difference
    first, require the toggle-restore difference to be no worse, and separately
    require the traffic-manager actor positions at frame N to be identical -- which
    is what pairing actually needs. The same-config floor is checked too, because a
    baseline that is itself huge would make the comparison pass trivially.
    """
    d = out / "gate_c"
    d.mkdir(parents=True, exist_ok=True)

    def run_once(tag, toggle=False):
        world, _tm, vehicles = setup_world(client, TOWN, n_vehicles, SEED)
        env = env_car_cache(world)
        if toggle:
            ids = {o["id"] for o in env[:5]}
            world.enable_environment_objects(ids, False)
            for _ in range(4):
                world.tick()
            world.enable_environment_objects(ids, True)      # restore
            for _ in range(4):
                world.tick()
        cams = spawn_cams(world, nadir(0.0, 0.0, 70.0))
        bgr = None
        try:
            for _ in range(n_frames):
                bgr, _tags, _ = grab(world, cams)
            pos = sorted((v.id, round(v.get_location().x, 3),
                          round(v.get_location().y, 3)) for v in vehicles)
        finally:
            teardown(client, cams, vehicles)
        cv2.imwrite(str(d / f"{tag}.png"), bgr)
        return bgr, pos

    a, pos_a = run_once("baseline_a")
    b, pos_b = run_once("baseline_b")                # same config, repeat
    c, pos_c = run_once("toggled", toggle=True)      # toggle then restore

    same_cfg, toggled = mean_absdiff(a, b), mean_absdiff(a, c)
    pos_same, pos_toggle = (pos_a == pos_b), (pos_a == pos_c)
    floor_ok = same_cfg < 8.0
    res = {"gate": "G-C", "same_config_meanabsdiff": round(same_cfg, 4),
           "toggle_restore_meanabsdiff": round(toggled, 4),
           "pixel_rule_ok": toggled <= max(same_cfg, 1e-9),
           "same_config_floor_ok": floor_ok,
           "tm_positions_identical_same_config": pos_same,
           "tm_positions_identical_after_toggle": pos_toggle,
           "n_vehicles_compared": len(pos_a),
           "verdict": "PASS" if (toggled <= max(same_cfg, 1e-9) and floor_ok
                                 and pos_same and pos_toggle) else "FAIL"}
    (d / "results.json").write_text(json.dumps(res, indent=2))
    print(f"G-C: same-config {same_cfg:.3f}, toggle-restore {toggled:.3f}, "
          f"TM identical same={pos_same} toggled={pos_toggle} -> {res['verdict']}")
    return res


# ---------------------------------------------------------------- driver

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2100)
    ap.add_argument("--out", default="experiments/2026-07-21-carla-gt-bank/runs/bank")
    ap.add_argument("--clips", type=int, default=25)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--gate-a", action="store_true")
    ap.add_argument("--gate-c", action="store_true")
    ap.add_argument("--stop-server", action="store_true",
                    help="kill the server on exit (only one we started ourselves)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"free disk {free_gb():.1f} GB, power limit {reassert_power()} W")

    client, proc = ensure_carla(args.host, args.port, CARLA_SH)
    client.set_timeout(120.0)
    print(f"server {client.get_server_version()} (adopted={proc is None})")
    try:
        if args.gate_a:
            gate_a(client, out.parent)
        elif args.gate_c:
            gate_c(client, out.parent)
        else:
            mans = [capture_clip(client, clip_plan(i), out, args.seconds,
                                 max_frames=args.max_frames)
                    for i in range(args.clips)]
            summ = {"clips": len(mans), "mode": "sync", "seed": SEED,
                    "town": TOWN, "dt": FIXED_DT,
                    "total_frames": sum(m["frames"] for m in mans),
                    "mean_capture_hz": round(
                        sum(m["capture_hz"] for m in mans) / len(mans), 2),
                    "power_limit_w": mans[0]["power_limit_w"] if mans else None}
            (out / "results.json").write_text(json.dumps(summ, indent=2))
            print(json.dumps(summ, indent=2))
    finally:
        if proc is not None and args.stop_server:
            stop_carla(proc)


if __name__ == "__main__":
    main()
