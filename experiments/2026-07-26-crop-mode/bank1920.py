#!/usr/bin/env python3
"""bank1920.py -- Bank-1920-single: 25 single CARLA captures at 1920^2 with GT.

The only asset in this repo with headroom above the 960/512 feed sizes EXP-4 compares
(UAV123 is 1280x720, the CARLA GT bank is 640x480 -- both BELOW the feed). One frame
per designated target, nadir, `Town10HD_Opt`, FOV 90.

Stratified by native pixel footprint, 10 / 8 / 7:

    small  40-80 px    mid  80-160 px    large  >160 px

DEVIATION from the pre-registration, deliberate: the strata are realized by ALTITUDE,
not by "nadir 45 m + vehicle placement". At a fixed 45 m the footprint is set entirely
by vehicle length (21.3 px/m), and Town10's fleet cannot put 7 targets above 160 px --
that needs a 7.5 m body. Footprint is the stratification variable the RQ cares about;
altitude is only the means, and the deployed 45 m sits inside the mid tier either way.
Per target: alt = f*L/target_px, clamped to [20, 120] m, recorded in the manifest.

Independence (pre-registered deflation rule): two targets are non-independent if their
camera positions are within 30 m. Enforced at SELECTION time, so raw n = deflated n = 25.

    .venv-ft/bin/python experiments/2026-07-26-crop-mode/bank1920.py \
        --port 2100 --out experiments/2026-07-26-crop-mode/runs/bank1920
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runners"))
import carla_gt_bank as gb  # noqa: E402
from carla_debug_ui import CARLA_SH, ensure_carla, stop_carla  # noqa: E402

SIDE, FOV = 1920, 90
F_PX = (SIDE / 2.0) / math.tan(math.radians(FOV) / 2.0)   # 960
STRATA = (("small", 60, 10), ("mid", 120, 8), ("large", 200, 7))
ALT_RANGE = (20.0, 120.0)
MIN_SEP_M = 30.0          # the deflation rule, applied as a selection constraint
MARGIN_PX = 300           # a 512 window centred on the target must fit inside 1920
SETTLE = 6
N_VEHICLES = 80
SPREAD_TICKS = 200        # ~10 s of sim so traffic leaves the spawn ring
PASSES = 4                # re-scan attempts per stratum
REPOSITION_TICKS = 120    # ~6 s of driving between passes

# ponytail: 11 anchors, nearest-in-RGB. A colour name only has to be the one a human
# would say; a full CIE conversion buys nothing an operator phrase can use.
COLORS = {"black": (0, 0, 0), "white": (255, 255, 255), "grey": (128, 128, 128),
          "silver": (192, 192, 192), "red": (200, 0, 0), "dark red": (100, 0, 0),
          "blue": (0, 0, 200), "dark blue": (0, 0, 90), "green": (0, 130, 0),
          "yellow": (230, 200, 0), "orange": (230, 120, 0)}
CLASSES = {"bicycle": "bicycle", "motorcycle": "motorcycle", "harley": "motorcycle",
           "yamaha": "motorcycle", "kawasaki": "motorcycle", "vespa": "motorcycle",
           "gazelle": "bicycle", "diamondback": "bicycle", "crossbike": "bicycle",
           "firetruck": "fire truck", "ambulance": "ambulance", "carlacola": "truck",
           "cybertruck": "truck", "sprinter": "van", "t2": "van", "charger": "car",
           "police": "police car"}


def veh_pixels(bgr, tags, box):
    """(masked BGR pixel list, mask) for the vehicle-tagged pixels inside the GT box."""
    x1, y1 = max(0, int(box[0])), max(0, int(box[1]))
    x2, y2 = min(tags.shape[1], int(box[2])), min(tags.shape[0], int(box[3]))
    m = np.isin(tags[y1:y2, x1:x2], gb.VEH_TAGS)
    return bgr[y1:y2, x1:x2][m], m


def color_name(px):
    """Colour of the target AS RENDERED, from its vehicle-tagged pixels.

    NOT the blueprint `color` attribute: vans and trucks carry a fixed livery and
    ignore it, so the attribute said "dark red van" for a van the renderer drew white
    -- an operator phrase that is simply false, and false for every arm at once (found
    in the EXP-4 C-loss overlay, 2026-07-26).

    NOT the median RGB either: from nadir a car is mostly roof plus near-black glass
    and often sits in building shadow, so the median reads grey on a car that is
    plainly red (t11, 2026-07-26). Work in HSV instead: hue if the body is chromatic,
    lightness if it is not.

    Both gates are MEDIANS over the body, not percentiles. A percentile gate calls the
    colour from a minority of pixels, and on this bank that is always a livery detail
    rather than the body -- the white UBER lettering on a black car (t21) and a blue
    racing stripe on a white one (t24) both hijacked a 90th-percentile rule.
    """
    if px.size == 0:
        return ""
    hsv = cv2.cvtColor(px.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    h, s, v = hsv[:, 0].astype(float), hsv[:, 1].astype(float), hsv[:, 2].astype(float)
    s50 = float(np.median(s))
    if s50 < 60:                                   # achromatic body
        lit = float(np.median(v))
        return "black" if lit < 70 else ("grey" if lit < 150 else "white")
    hue = float(np.median(h[s >= s50])) * 2.0      # OpenCV packs hue into 0-179
    for lo, hi, name in ((0, 20, "red"), (20, 45, "orange"), (45, 70, "yellow"),
                         (70, 170, "green"), (170, 260, "blue"), (260, 320, "purple")):
        if lo <= hue < hi:
            return name
    return "red"                                   # 320-360 wraps back to red


def caption(type_id, px):
    """Operator phrase. Held CONSTANT across all four EXP-4 arms, so its quality is a
    constant of the experiment, not a confound."""
    tail = type_id.split(".")[-1]
    maker = type_id.split(".")[-2] if type_id.count(".") >= 2 else ""
    kind = next((v for k, v in CLASSES.items() if k in tail or k in maker), "car")
    col = color_name(px)
    return f"the {col} {kind}" if col else f"the {kind}"


def veh_len(v):
    e = v.bounding_box.extent
    return 2 * max(e.x, e.y)


def capture(world, cams, env, target, alt, out: Path, idx, stratum):
    loc = target.get_transform().location
    tf = gb.nadir(loc.x, loc.y, loc.z + alt)
    for c, _q in cams:
        c.set_transform(tf)
    for _ in range(SETTLE):
        bgr, tags, tick = gb.grab(world, cams)
    real_tf = cams[0][0].get_transform()

    row = next((r for r in gb.gt_rows(world, real_tf, env, tags, SIDE, SIDE, FOV)
                if r["id"] == target.id), None)
    if not row or not row["box_vis"] or row["partial"]:
        return None, "target not fully on screen"
    x1, y1, x2, y2 = row["box_vis"]
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    if not (MARGIN_PX <= cx <= SIDE - MARGIN_PX and MARGIN_PX <= cy <= SIDE - MARGIN_PX):
        return None, f"target drifted to ({cx:.0f},{cy:.0f}) during settle"
    # 0.30, not 0.5: an axis-aligned box around a car at 45 deg fills only ~0.41 even
    # unoccluded, so a 0.5 floor silently selects for axis-aligned traffic. 0.30 still
    # kills the real failure (occluded target, veh_fill 0.0).
    if (row["veh_fill"] or 0) < 0.30:
        return None, f"veh_fill {row['veh_fill']} -- box is mostly not vehicle"
    dom = gb.dominant_frac(bgr)
    if dom >= 0.99:
        return None, f"blank render (dominant {dom:.3f})"

    name = f"t{idx:02d}_{stratum}"
    cv2.imwrite(str(out / f"{name}.png"), bgr)
    px, mask = veh_pixels(bgr, tags, row["box_vis"])
    # the body mask, kept so the caption can be re-derived offline. It already cost one
    # full CARLA rebuild to fix a colour bug that only the pixels could reveal.
    cv2.imwrite(str(out / f"{name}_mask.png"), mask.astype(np.uint8) * 255)
    return {"name": name, "stratum": stratum, "alt_m": round(alt, 2),
            "cam_xy": [round(real_tf.location.x, 2), round(real_tf.location.y, 2)],
            "target_id": int(target.id), "type_id": target.type_id,
            "caption": caption(target.type_id, px),
            "box": [round(v, 2) for v in row["box_vis"]],
            "footprint_px": round(max(x2 - x1, y2 - y1), 1),
            "veh_fill": row["veh_fill"], "dominant_frac": round(dom, 4),
            "tick": tick, "png": f"{name}.png"}, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2100)
    ap.add_argument("--out", default="experiments/2026-07-26-crop-mode/runs/bank1920")
    ap.add_argument("--seed", type=int, default=gb.SEED)
    ap.add_argument("--stop-server", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    gb.W, gb.H, gb.FOV = SIDE, SIDE, FOV
    rng = random.Random(args.seed)

    print(f"free disk {gb.free_gb():.1f} GB, power limit {gb.reassert_power()} W")
    client, proc = ensure_carla(args.host, args.port, CARLA_SH)
    client.set_timeout(120.0)

    world = vehicles = None
    cams = []
    rows, rejects = [], []
    try:
        world, _tm, vehicles = gb.setup_world(client, gb.TOWN, N_VEHICLES, args.seed)
        env = gb.env_car_cache(world)
        # spread FIRST, then spawn: a 1920^2 sensor queues 14.7 MB per tick and
        # nothing drains it, so 200 ticks with cameras live is ~6 GB of listener queue.
        for _ in range(SPREAD_TICKS):
            world.tick()
        cams = gb.spawn_cams(world, gb.nadir(0.0, 0.0, 60.0))
        print(f"{len(vehicles)} vehicles spread over {SPREAD_TICKS} ticks", flush=True)

        pool = [v for v in world.get_actors().filter("vehicle.*")]
        rng.shuffle(pool)
        taken = []                      # camera XY of accepted captures
        idx = 0
        for stratum, target_px, want in STRATA:
            got = 0
            # traffic moves, so a vehicle blocked by the 30 m rule on pass 1 can be
            # free on pass 2. Re-scan rather than widen the pool and weaken the rule.
            for _pass in range(PASSES):
                if got >= want:
                    break
                if _pass:
                    for _ in range(REPOSITION_TICKS):
                        world.tick()
                for v in pool:
                    if got >= want:
                        break
                    if v.id in {r["target_id"] for r in rows}:
                        continue
                    loc = v.get_transform().location
                    if any(math.hypot(loc.x - tx, loc.y - ty) < MIN_SEP_M
                           for tx, ty in taken):
                        continue
                    alt = min(max(F_PX * veh_len(v) / target_px, ALT_RANGE[0]),
                              ALT_RANGE[1])
                    rec, why = capture(world, cams, env, v, alt, out, idx, stratum)
                    if rec is None:
                        rejects.append({"id": int(v.id), "stratum": stratum,
                                        "pass": _pass, "why": why})
                        continue
                    rows.append(rec)
                    taken.append(tuple(rec["cam_xy"]))
                    idx, got = idx + 1, got + 1
                    print(f"  [{len(rows):02d}/25] {rec['name']} "
                          f"{rec['footprint_px']:6.1f} px alt {alt:5.1f} m  "
                          f"\"{rec['caption']}\"", flush=True)
            if got < want:
                print(f"  WARNING: {stratum} short by {want - got}", flush=True)
    finally:
        if world is not None:
            gb.teardown(client, cams, vehicles or [])
        if proc is not None and args.stop_server:
            stop_carla(proc)

    fps = [r["footprint_px"] for r in rows]
    man = {"bank": "Bank-1920-single", "town": gb.TOWN, "seed": args.seed,
           "cam_wh_fov": [SIDE, SIDE, FOV], "f_px": F_PX,
           "strata": {s: sum(1 for r in rows if r["stratum"] == s) for s, _, _ in STRATA},
           "min_sep_m": MIN_SEP_M, "n": len(rows),
           "footprint_px": {"min": min(fps), "max": max(fps),
                            "median": round(float(np.median(fps)), 1)} if fps else {},
           "n_rejected": len(rejects), "rejects": rejects, "targets": rows}
    (out / "results.json").write_text(json.dumps(man, indent=1))
    print(f"bank: {len(rows)} targets, footprint {min(fps):.0f}-{max(fps):.0f} px, "
          f"{len(rejects)} rejected -> {out / 'results.json'}")


if __name__ == "__main__":
    main()
