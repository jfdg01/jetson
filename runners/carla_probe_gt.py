#!/usr/bin/env python3
"""carla_probe_gt.py -- answer the API questions the GT bank design cannot settle from source.

Read-only against a live server. Writes JSON to stdout and a probe frame to --out.
The one that matters: is an EnvironmentObject's bounding_box in WORLD space or in
the object's LOCAL space? Actors carry a local box that get_world_vertices(transform)
resolves; environment objects have no actor transform to pass, and guessing wrong
puts all 29 parked-car GT boxes somewhere plausible but wrong -- with nothing
downstream that would notice.

    .venv-ft/bin/python runners/carla_probe_gt.py --port 2100
"""
import argparse
import json
import math
import queue
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


def probe_env_objects(world):
    """World-space or local-space? Decide it by magnitude, not by faith.

    A local box sits near its own origin (|location| is metres). A world box sits
    at a map coordinate (|location| is tens-to-hundreds of metres, and matches the
    object's own transform.location). Town10 is ~400 m across, so the two are not
    close enough to confuse.
    """
    objs = world.get_environment_objects(carla.CityObjectLabel.Car)
    rows = []
    for o in objs[:8]:
        bb, tf = o.bounding_box, o.transform
        rows.append({
            "name": o.name,
            "id": int(o.id),
            "transform_loc": [tf.location.x, tf.location.y, tf.location.z],
            "bbox_loc": [bb.location.x, bb.location.y, bb.location.z],
            "bbox_extent": [bb.extent.x, bb.extent.y, bb.extent.z],
            "bbox_rot": [bb.rotation.pitch, bb.rotation.yaw, bb.rotation.roll],
            "dist_bbox_to_tf": math.dist(
                (bb.location.x, bb.location.y, bb.location.z),
                (tf.location.x, tf.location.y, tf.location.z)),
            "bbox_loc_norm": math.dist((bb.location.x, bb.location.y, bb.location.z),
                                       (0, 0, 0)),
        })
    # a world-space box has its location AT the object; a local one has it near zero
    near_obj = sum(r["dist_bbox_to_tf"] < 2.0 for r in rows)
    near_zero = sum(r["bbox_loc_norm"] < 2.0 for r in rows)
    verdict = ("WORLD" if near_obj >= max(1, len(rows) - 1)
               else "LOCAL" if near_zero >= max(1, len(rows) - 1)
               else "AMBIGUOUS")

    # get_world_vertices needs a transform. If the box is already world-space, the
    # identity transform is the correct one to pass; if local, the object's own.
    vert = {}
    if rows:
        o = objs[0]
        for label, tf in (("identity", carla.Transform()), ("own", o.transform)):
            try:
                v = o.bounding_box.get_world_vertices(tf)
                vert[label] = {
                    "n": len(v),
                    "first": [v[0].x, v[0].y, v[0].z],
                    "spread_m": max(math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))
                                    for a in v for b in v),
                    "centroid": [sum(p.x for p in v) / len(v),
                                 sum(p.y for p in v) / len(v),
                                 sum(p.z for p in v) / len(v)],
                }
            except Exception as e:                      # noqa: BLE001
                vert[label] = {"error": repr(e)}
    return {"n_env_cars": len(objs), "verdict": verdict, "samples": rows,
            "get_world_vertices": vert}


def probe_actor_box(world):
    """Same question for a real vehicle, as the control case."""
    vs = list(world.get_actors().filter("vehicle.*"))
    if not vs:
        return {"n_vehicles": 0}
    v = vs[0]
    bb, tf = v.bounding_box, v.get_transform()
    verts = bb.get_world_vertices(tf)
    return {
        "n_vehicles": len(vs),
        "type_id": v.type_id,
        "actor_loc": [tf.location.x, tf.location.y, tf.location.z],
        "bbox_loc": [bb.location.x, bb.location.y, bb.location.z],
        "bbox_extent": [bb.extent.x, bb.extent.y, bb.extent.z],
        "world_vert_centroid": [sum(p.x for p in verts) / 8,
                                sum(p.y for p in verts) / 8,
                                sum(p.z for p in verts) / 8],
        "vert_spread_m": max(math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))
                             for a in verts for b in verts),
    }


def probe_sync(client, world, args):
    """Sync-mode capture: does the image delivered for a tick carry that tick's frame id?

    An off-by-one here means every GT box is one frame stale -- the exact defect
    P5.13 was charged with, and invisible in any log.
    """
    settings = world.get_settings()
    old = (settings.synchronous_mode, settings.fixed_delta_seconds)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.05
    world.apply_settings(settings)
    tm = client.get_trafficmanager(8000)
    tm.set_synchronous_mode(True)

    bp = world.get_blueprint_library().find("sensor.camera.rgb")
    bp.set_attribute("image_size_x", str(W))
    bp.set_attribute("image_size_y", str(H))
    bp.set_attribute("fov", str(FOV))
    cam = world.spawn_actor(bp, carla.Transform(
        carla.Location(x=0.0, y=0.0, z=60.0), carla.Rotation(pitch=-90.0)))
    q = queue.Queue()
    cam.listen(q.put)

    rows, t0 = [], time.time()
    frame = None
    for _ in range(40):
        snap_frame = world.tick()
        img = q.get(timeout=10.0)
        rows.append({"tick": int(snap_frame), "img": int(img.frame),
                     "delta": int(img.frame) - int(snap_frame)})
        buf = np.frombuffer(img.raw_data, np.uint8).reshape(img.height, img.width, 4)
        frame = np.ascontiguousarray(buf[:, :, :3])
    hz = 40.0 / (time.time() - t0)

    cam.stop()
    cam.destroy()
    settings.synchronous_mode, settings.fixed_delta_seconds = old
    world.apply_settings(settings)
    tm.set_synchronous_mode(False)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    png = out / "probe_sync.png"
    cv2.imwrite(str(png), frame)
    flat = frame.reshape(-1, 3)
    dom = np.unique(flat, axis=0, return_counts=True)[1].max() / len(flat)
    return {"deltas": sorted({r["delta"] for r in rows}), "rows": rows[:5],
            "sync_hz_at_200W": hz, "frame_png": str(png),
            "dominant_frac": float(dom)}


def probe_raycast(world):
    """Is there anything in 0.9.16 for an occlusion test? (slate 2.3c)"""
    have = {n: hasattr(world, n) for n in
            ("cast_ray", "project_point", "ground_projection")}
    sample = None
    if have.get("cast_ray"):
        try:
            hits = world.cast_ray(carla.Location(0, 0, 60), carla.Location(0, 0, 0))
            sample = [{"label": str(h.label), "z": h.location.z} for h in hits[:5]]
        except Exception as e:                          # noqa: BLE001
            sample = repr(e)
    return {"api": have, "sample": sample}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2100)
    ap.add_argument("--town", default=TOWN)
    ap.add_argument("--vehicles", type=int, default=10)
    ap.add_argument("--out", default="runs/carla-probe")
    ap.add_argument("--keep", action="store_true", help="leave the server up")
    args = ap.parse_args()

    client, proc = ensure_carla(args.host, args.port, CARLA_SH)
    client.set_timeout(120.0)
    res = {"server": client.get_server_version(), "client": client.get_client_version(),
           "adopted": proc is None}
    try:
        world = client.load_world(args.town)
        time.sleep(3.0)
        # a few vehicles so probe_actor_box has a control case
        bp_lib = world.get_blueprint_library()
        cars = [b for b in bp_lib.filter("vehicle.*")
                if int(b.get_attribute("number_of_wheels")) == 4]
        spawns = world.get_map().get_spawn_points()[:args.vehicles]
        spawned = [v for v in (world.try_spawn_actor(cars[i % len(cars)], sp)
                               for i, sp in enumerate(spawns)) if v is not None]
        res["spawned"] = len(spawned)
        res["env_objects"] = probe_env_objects(world)
        res["actor_box"] = probe_actor_box(world)
        res["raycast"] = probe_raycast(world)
        res["sync"] = probe_sync(client, world, args)
        res["map_layers"] = [m for m in dir(carla.MapLayer) if not m.startswith("_")]
        res["city_labels"] = [m for m in dir(carla.CityObjectLabel) if not m.startswith("_")]
    finally:
        print(json.dumps(res, indent=2, default=str))
        Path(args.out).mkdir(parents=True, exist_ok=True)
        (Path(args.out) / "probe.json").write_text(json.dumps(res, indent=2, default=str))
        if proc is not None and not args.keep:
            stop_carla(proc)


if __name__ == "__main__":
    main()
