#!/usr/bin/env python3
"""probe_s0.py -- S0 detail-headroom gate for the MODE 2 crop campaign.

Question: does a CARLA 1920^2 render carry high-frequency detail that its own 960
INTER_AREA downscale destroys, at the SMALL-target footprint this campaign is about?

If it does not, lever (a') -- "cut the crop from the native sensor frame instead of
the 960 display frame" -- is dead before any bank is built, and MODE 2's crop simply
comes off the 960 frame like `roi_reanchor` already does.

Method. One nadir camera over a STATIC parked car (deterministic, stationary --
the same reference `carla_gt_bank.gate_a` uses). The footprint knob is ALTITUDE, not
ground offset: at nadir footprint_px = f*L/z, so a lateral offset barely moves it.
Per altitude, two SxS images of the same physical region:

    A native  -- SxS window cut from the 1920 frame, no resize.
    B down    -- 1920 -> 960 with INTER_AREA (byte-for-byte what carla_debug_ui.py:2467
                 does), the same region cut as (S/2)^2, LANCZOS-upscaled back to SxS.

Both are SxS, so the comparison is at native scale and the upscale is the thing under
test. Metric: Laplacian-variance ratio A/B, plus a side-by-side PNG per target.

GATE: ratio >= 1.30 on >= 4 of 6 targets INCLUDING BOTH SMALLEST, and the difference
visible in the PNGs. The JSON is not the verdict -- the pixels are. Read every
pair_*.png before writing anything down.

    .venv-ft/bin/python experiments/2026-07-26-crop-mode/probe_s0.py \
        --port 2100 --out experiments/2026-07-26-crop-mode/runs/s0
"""
import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runners"))
import carla_gt_bank as gb  # noqa: E402
from carla_debug_ui import CARLA_SH, ensure_carla, stop_carla  # noqa: E402

SIDE, FOV = 1920, 90                 # the live sensor: LIVE_CAM_SIDE, CAM_FOV
DISPLAY = 960                        # CAM_W/CAM_H -- what on_image() downscales to
FOOTPRINTS = (40, 60, 100, 140, 200, 230)   # nominal native px, small first
ALT_FLOOR = 20.0                     # gate_a has flown 25 m clean; below this we risk
                                     # clipping into Town10 geometry
GATE_RATIO = 1.30
SETTLE = 6                           # TAA + auto-exposure, same as gate_a


def lapvar(img):
    """Laplacian variance -- the standard cheap sharpness proxy."""
    return float(cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY),
                               cv2.CV_64F).var())


def even(v):
    return int(v) - (int(v) % 2)


def window(cx, cy, s, side=SIDE):
    """SxS window centred on (cx,cy), SHIFTED (not shrunk) to stay in frame.

    Shrinking at the border would make A and B cover different areas at different
    sizes, and the whole measurement is a same-region comparison. The target sits
    under a nadir camera so this only ever bites at the largest S.
    """
    s = min(even(s), even(side))
    x0 = even(max(0, min(round(cx - s / 2), side - s)))
    y0 = even(max(0, min(round(cy - s / 2), side - s)))
    return x0, y0, s


def probe_alt(world, cams, env, ref, alt, out: Path):
    """One altitude -> one record + one pair PNG. Returns the record dict."""
    tf = gb.nadir(ref["loc"].x, ref["loc"].y, ref["loc"].z + alt)
    for c, _q in cams:                    # rgb and seg must share the pose
        c.set_transform(tf)
    for _ in range(SETTLE):
        bgr, tags, _ = gb.grab(world, cams)
    real_tf = cams[0][0].get_transform()

    rows = gb.gt_rows(world, real_tf, env, tags, SIDE, SIDE, FOV)
    me = next((r for r in rows if r["id"] == ref["id"]), None)
    assert me and me["box_vis"], f"alt {alt}: reference car not on screen"
    dom = gb.dominant_frac(bgr)
    assert dom < 0.99, f"alt {alt}: blank render (dominant {dom:.3f})"

    x1, y1, x2, y2 = me["box_vis"]
    px = max(x2 - x1, y2 - y1)
    x0, y0, s = window((x1 + x2) / 2, (y1 + y2) / 2, max(96, 1.5 * px))

    a = bgr[y0:y0 + s, x0:x0 + s]
    down = cv2.resize(bgr, (DISPLAY, DISPLAY), interpolation=cv2.INTER_AREA)
    k = SIDE // DISPLAY
    b_small = down[y0 // k:y0 // k + s // k, x0 // k:x0 // k + s // k]
    b = cv2.resize(b_small, (s, s), interpolation=cv2.INTER_LANCZOS4)
    assert not np.array_equal(a, b), f"alt {alt}: native and downscaled crop identical"

    la, lb = lapvar(a), lapvar(b)
    pair = np.hstack([a, np.full((s, 4, 3), 255, np.uint8), b])
    for txt, ox in ((f"native 1920  lapvar {la:.1f}", 0),
                    (f"via 960 +LANCZOS  lapvar {lb:.1f}", s + 4)):
        cv2.putText(pair, txt, (ox + 6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (0, 255, 255), 1, cv2.LINE_AA)
    p = out / f"pair_{round(px):03d}px.png"
    cv2.imwrite(str(p), pair)
    # viewing aid: NEAREST magnification, identical on both arms, adds no information.
    # A 96x96 pair is unreadable at 1:1 and the verdict has to be made by eye.
    k = max(1, int(700 / pair.shape[1]))
    cv2.imwrite(str(out / f"view_{round(px):03d}px.png"),
                cv2.resize(pair, None, fx=k, fy=k, interpolation=cv2.INTER_NEAREST)
                if k > 1 else pair)
    cv2.imwrite(str(out / f"full_alt{round(alt):03d}.png"), bgr)

    rec = {"alt_m": round(alt, 2), "measured_px": round(px, 1),
           "analytic_px_area": round(gb.analytic_area(ref["extent"], alt, SIDE, FOV), 1),
           "box_area_px": me["area_px"], "veh_fill": me["veh_fill"],
           "crop_side": s, "win": [x0, y0],
           "lapvar_native": round(la, 2), "lapvar_down": round(lb, 2),
           "ratio": round(la / lb, 3) if lb else None,
           "mean_absdiff": round(gb.mean_absdiff(a, b), 3),
           "dominant_frac": round(dom, 4), "png": str(p)}
    print(f"  alt {alt:6.1f} m  {px:5.1f} px  crop {s:4d}  "
          f"lapvar {la:8.1f} / {lb:8.1f}  ratio {rec['ratio']}", flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2100)
    ap.add_argument("--out", default="experiments/2026-07-26-crop-mode/runs/s0")
    ap.add_argument("--vehicles", type=int, default=8,
                    help="traffic is scenery here; the reference is a static car")
    ap.add_argument("--stop-server", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # carla_gt_bank builds its camera blueprints from module globals -- point them at
    # the live sensor size instead of the 640x480 bank size.
    gb.W, gb.H, gb.FOV = SIDE, SIDE, FOV

    print(f"free disk {gb.free_gb():.1f} GB, power limit {gb.reassert_power()} W")
    client, proc = ensure_carla(args.host, args.port, CARLA_SH)
    client.set_timeout(120.0)
    print(f"server {client.get_server_version()} (adopted={proc is None})")

    world = vehicles = None
    cams = []
    try:
        world, _tm, vehicles = gb.setup_world(client, gb.TOWN, args.vehicles, gb.SEED)
        env = gb.env_car_cache(world)
        assert env, "no static Car meshes -- ParkedVehicles layer missing?"
        ref = min(env, key=lambda o: math.hypot(o["loc"].x, o["loc"].y))
        f = (SIDE / 2.0) / math.tan(math.radians(FOV) / 2.0)
        length = 2 * ref["extent"][0]
        print(f"reference {ref['name']} at ({ref['loc'].x:.1f},{ref['loc'].y:.1f},"
              f"{ref['loc'].z:.1f}) length {length:.2f} m, f={f:.0f} px")

        cams = gb.spawn_cams(world, gb.nadir(ref["loc"].x, ref["loc"].y,
                                             ref["loc"].z + 60.0))
        recs = []
        for target_px in FOOTPRINTS:
            alt = max(ALT_FLOOR, f * length / target_px)
            recs.append({"nominal_px": target_px,
                         **probe_alt(world, cams, env, ref, alt, out)})
    finally:
        if world is not None:
            gb.teardown(client, cams, vehicles or [])
        if proc is not None and args.stop_server:
            stop_carla(proc)

    ok = [r for r in recs if (r["ratio"] or 0) >= GATE_RATIO]
    smallest = sorted(recs, key=lambda r: r["measured_px"])[:2]
    small_ok = all((r["ratio"] or 0) >= GATE_RATIO for r in smallest)
    res = {"probe": "S0", "gate_ratio": GATE_RATIO,
           "sensor": [SIDE, SIDE, FOV], "display": DISPLAY,
           "ref": ref["name"], "ref_extent": [round(v, 3) for v in ref["extent"]],
           "records": recs,
           "n_pass": len(ok), "smallest_two_pass": small_ok,
           "verdict": "PASS" if (len(ok) >= 4 and small_ok) else "FAIL",
           "note": "NOT satisfied until every pair_*.png is opened and viewed"}
    (out / "results.json").write_text(json.dumps(res, indent=2))
    print(f"S0: {len(ok)}/6 >= {GATE_RATIO}, smallest-two {small_ok} "
          f"-> {res['verdict']} (pending the eyes)")


if __name__ == "__main__":
    main()
