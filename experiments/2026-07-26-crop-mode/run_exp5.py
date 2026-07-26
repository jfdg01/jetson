"""EXP-5 -- carry-crop mechanism pilot (levers b, c, e), ON THE ORIN.

Exploratory: no test, no PASS claim. Six carry arms over 12 frozen UAV123 clips, seeded
from EXP-1's own plan (same seed frame, same seed box, same stride), so the only thing
that moves between arms is what SAM2 is fed and whether its output is vetoed.

    A1 CONTROL      plain whole frame @640           (deployed)
    A2 CONTROL-2    plain whole frame @1024          (deployed fallback -- costs nothing but a flag)
    A3 GUARD-ONLY   plain whole frame @640 + guard   (is the guard the whole effect?)
    A4 CROP-FIXED   512-px dead-band window @640
    A5 CROP+GUARD   512-px dead-band window @640 + guard
    A6 CROP-SCALED  roi_window(margin=2.0, min_side=256) @640 + guard

Carry runs on the Jetson via the ssh-stdio bridge; this host script holds UAV123 + GT,
crops, streams JPEGs, remaps and guards the returned box, scores IoU vs GT. NO torch/SAM2
here, NO 3090. machine=jetson.

D_MAX (the displacement veto's threshold) is NOT a guess and NOT a constant of this file:
the guard-free arms run first, `dmax` reads the 99th percentile of A1's per-step normalized
displacement and freezes it to dmax.json, and the guard arms refuse to start without it.

    .venv-ft/bin/python run_exp5.py carry --out runs/exp5 --arms A1,A2,A4
    .venv-ft/bin/python run_exp5.py dmax  --out runs/exp5
    .venv-ft/bin/python run_exp5.py carry --out runs/exp5 --arms A3,A5,A6
    .venv-ft/bin/python run_exp5.py score --out runs/exp5
"""
from __future__ import annotations

import argparse
import json
import math
import pickle
import struct
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments" / "2026-07-20-n25-select"))
sys.path.insert(0, str(REPO))
from curate_p518 import frame  # noqa: E402
from grounding.contract import COORD_SCALE  # noqa: E402
from grounding.roi import roi_window  # noqa: E402

EXP1 = REPO / "experiments" / "2026-07-24-resolution-decoupled-carry" / "runs" / "exp1"

# The EXP-1 resolution-gated tail: median IoU at 640 far below the same clip at 1024.
# car11 excluded by pre-registered rule (0.000 at every size except 896 -- anomalous,
# not resolution-gated); uav8 likewise 0.000 at BOTH sizes, so it gates on nothing.
TAIL = ["bike3", "car15", "uav3", "person21", "building3", "car13", "truck2", "truck3"]
# 4 easy controls, one per object category, each the best clip of its category at 640
# (all >0.8). Category spread rather than the top-4 outright, which would have been
# three boats and a car -- a regression check wants the range, not the ceiling.
EASY = ["boat3", "car18", "person10", "wakeboard6"]
CLIPS = TAIL + EASY

CROP_SIDE = 512          # lever b, fixed window
SCALED_MARGIN = 2.0      # lever c, box-scaled window
SCALED_MIN_SIDE = 256
DEAD_BAND = 0.5          # window re-centres only when the box centre leaves the central 50%
AREA_LO, AREA_HI = 0.4, 2.5   # P5.21's own constants (carry_p521.py:96); new call site
VETO_RUN_MAX = 5         # consecutive vetoes before falling through to lost

ARMS = {
    "A1": {"size": 640, "crop": None, "guard": False},
    "A2": {"size": 1024, "crop": None, "guard": False},
    "A3": {"size": 640, "crop": None, "guard": True},
    "A4": {"size": 640, "crop": "fixed", "guard": False},
    "A5": {"size": 640, "crop": "fixed", "guard": True},
    "A6": {"size": 640, "crop": "scaled", "guard": True},
}
BRIDGE = "cd ~/sam2-bench && ./.venv/bin/python -u carry_ssh_bridge.py --image-size {size}"


# ---- geometry ------------------------------------------------------------------
def iou(a, b) -> float:
    if a is None or b is None:
        return 0.0
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def area(b) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def centre(b):
    return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)


def disp_norm(new, prev) -> float:
    """Centre travel in units of the previous box's long side -- scale-free, so one D_MAX
    covers a 20-px person and a 200-px truck."""
    cx, cy = centre(new)
    px, py = centre(prev)
    ref = max(1.0, prev[2] - prev[0], prev[3] - prev[1])
    return math.hypot(cx - px, cy - py) / ref


def window(box, w, h, kind):
    """Crop window (pixel XYXY) around `box` for this arm. None -> the whole frame."""
    if kind is None:
        return (0, 0, w, h)
    if kind == "scaled":
        norm = [round(box[0] / w * COORD_SCALE), round(box[1] / h * COORD_SCALE),
                round(box[2] / w * COORD_SCALE), round(box[3] / h * COORD_SCALE)]
        return roi_window(norm, w, h, SCALED_MARGIN, min_side=SCALED_MIN_SIDE)
    cx, cy = centre(box)
    half = min(CROP_SIDE, w, h) / 2.0
    x0 = int(round(min(max(cx - half, 0), w - 2 * half)))
    y0 = int(round(min(max(cy - half, 0), h - 2 * half)))
    return (x0, y0, x0 + int(2 * half), y0 + int(2 * half))


def outside_dead_band(box, win) -> bool:
    cx, cy = centre(box)
    x0, y0, x1, y1 = win
    mx, my = (x1 - x0) * (1 - DEAD_BAND) / 2.0, (y1 - y0) * (1 - DEAD_BAND) / 2.0
    return not (x0 + mx <= cx <= x1 - mx and y0 + my <= cy <= y1 - my)


# ---- ssh bridge framing (host side of carry_ssh_bridge.py) ---------------------
def _send(f, obj):
    data = pickle.dumps(obj)
    f.write(struct.pack(">I", len(data)))
    f.write(data)
    f.flush()


def _recv(f):
    hdr = b""
    while len(hdr) < 4:
        more = f.read(4 - len(hdr))
        if not more:
            return None
        hdr += more
    (n,) = struct.unpack(">I", hdr)
    buf = b""
    while len(buf) < n:
        more = f.read(n - len(buf))
        if not more:
            return None
        buf += more
    return pickle.loads(buf)


def _jpg(bgr, win):
    """Crop -> RGB JPEG. The crop is sent at its NATIVE pixel size: the bridge's _prep
    resizes it to image_size internally, and that resize IS the magnification under test."""
    x0, y0, x1, y1 = win
    rgb = cv2.cvtColor(bgr[y0:y1, x0:x1], cv2.COLOR_BGR2RGB)
    ok, buf = cv2.imencode(".jpg", rgb, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    return buf.tobytes()


# ---- carry ---------------------------------------------------------------------
def _plan(out: Path):
    """The 12 clips of EXP-1's frozen plan -- same seed frame, same seed box, same steps."""
    full = json.loads((EXP1 / "plan.json").read_text())
    by = {p["clip"]: p for p in full}
    missing = [c for c in CLIPS if c not in by]
    assert not missing, f"clips absent from the EXP-1 plan: {missing}"
    plan = [by[c] for c in CLIPS]
    (out / "plan.json").write_text(json.dumps(plan, indent=1))
    return plan


def _run_clip(proc, entry, cfg, d_max):
    """One clip through one arm. Returns per-step boxes (FULL-frame coords), ms, windows,
    guard traces."""
    clip, seed = entry["clip"], entry["seed"]
    img = frame(clip, seed)
    h, w = img.shape[:2]
    prev = [float(v) for v in entry["seed_box"]]
    win = window(prev, w, h, cfg["crop"])
    seed_in_crop = [prev[0] - win[0], prev[1] - win[1], prev[2] - win[0], prev[3] - win[1]]
    _send(proc.stdin, ("init", _jpg(img, win), seed_in_crop))
    ack = _recv(proc.stdout)
    assert ack and ack.get("ok"), f"init failed {clip}: {ack}"

    boxes, mss, wins, ratios, disps, vetoes = [], [], [], [], [], []
    veto_run = 0
    for st in entry["steps"]:
        img = frame(clip, st["frame"])
        _send(proc.stdin, ("step", _jpg(img, win)))
        r = _recv(proc.stdout)
        assert r is not None, f"bridge died {clip} step={st['j']}"
        mss.append(r["ms"])
        wins.append(list(win))
        raw = r["box"]
        box = None if raw is None else [raw[0] + win[0], raw[1] + win[1],
                                        raw[2] + win[0], raw[3] + win[1]]
        ratio = area(box) / area(prev) if box and area(prev) > 0 else None
        d = disp_norm(box, prev) if box else None
        ratios.append(None if ratio is None else round(ratio, 4))
        disps.append(None if d is None else round(d, 4))

        veto = ""
        if cfg["guard"] and box is not None:
            if ratio is not None and not (AREA_LO <= ratio <= AREA_HI):
                veto = "area"
            elif d is not None and d > d_max:
                veto = "disp"
        vetoes.append(veto)
        if veto:
            veto_run += 1
            # hold the previous box and do NOT re-centre: a window recentred on a box the
            # guard just rejected is exactly the drift reinforcement P5.21 measured.
            box = None if veto_run >= VETO_RUN_MAX else list(prev)
        else:
            veto_run = 0
            if box is not None and cfg["crop"] and outside_dead_band(box, win):
                win = window(box, w, h, cfg["crop"])
        boxes.append(box)
        if box is not None:
            prev = box
    return {"boxes": boxes, "ms": mss, "wins": wins, "area_ratio": ratios,
            "disp": disps, "veto": vetoes}


def carry(out: Path, arms: list[str]) -> None:
    plan = _plan(out)
    d_max = None
    if any(ARMS[a]["guard"] for a in arms):
        p = out / "dmax.json"
        assert p.exists(), ("guard arms need dmax.json -- run the guard-free arms then "
                            "`run_exp5.py dmax` first (pre-registered ordering)")
        d_max = json.loads(p.read_text())["d_max"]
        print(f"[carry] D_MAX={d_max} (frozen from A1)", flush=True)

    for size in sorted({ARMS[a]["size"] for a in arms}):
        todo = [a for a in arms if ARMS[a]["size"] == size
                and not (out / f"carry_{a}.json").exists()]
        if not todo:
            continue
        log = open(out / f"bridge_{size}.err", "ab")
        proc = subprocess.Popen(["ssh", "-T", "-q", "jetson", BRIDGE.format(size=size)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        try:
            for arm in todo:
                cfg, res, t0 = ARMS[arm], {}, time.time()
                for i, entry in enumerate(plan):
                    res[entry["clip"]] = _run_clip(proc, entry, cfg, d_max)
                    ms = [m for m in res[entry["clip"]]["ms"] if m]
                    print(f"[carry] {arm} [{i + 1}/{len(plan)}] {entry['clip']} "
                          f"median_ms={np.median(ms):.0f}", flush=True)
                (out / f"carry_{arm}.json").write_text(json.dumps(res, indent=1))
                print(f"[carry] {arm} done in {time.time() - t0:.0f}s", flush=True)
        finally:
            proc.stdin.close()
            proc.wait()
            log.close()


def dmax(out: Path) -> None:
    """Freeze the displacement veto threshold from the CONTROL arm, before any guard arm
    runs. Pre-registered as a RULE (99th percentile, one decimal), not as a number."""
    res = json.loads((out / "carry_A1.json").read_text())
    plan = json.loads((out / "plan.json").read_text())
    ds = []
    for entry in plan:
        prev = [float(v) for v in entry["seed_box"]]
        for box in res[entry["clip"]]["boxes"]:
            if box is None:
                continue
            ds.append(disp_norm(box, prev))
            prev = box
    q = float(np.percentile(ds, 99))
    d_max = round(q, 1)
    (out / "dmax.json").write_text(json.dumps(
        {"d_max": d_max, "p99_raw": round(q, 4), "n_steps": len(ds),
         "p50": round(float(np.percentile(ds, 50)), 4),
         "p95": round(float(np.percentile(ds, 95)), 4),
         "source": "A1 CONTROL plain@640", "rule": "99th pct, rounded to 1 decimal"},
        indent=1))
    print(f"[dmax] n={len(ds)} p50={np.percentile(ds, 50):.3f} "
          f"p95={np.percentile(ds, 95):.3f} p99={q:.3f} -> D_MAX={d_max}", flush=True)


# ---- score ---------------------------------------------------------------------
def _draw(img, box, color, label):
    if box is None:
        return
    x0, y0, x1, y1 = (int(v) for v in box)
    cv2.rectangle(img, (x0, y0), (x1, y1), color, 2)
    cv2.putText(img, label, (x0, max(14, y0 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


def _overlays(out: Path, plan, by_arm, clips, arms):
    """Frames 0 / 25% / 50% / 100% with GT, the carried box and the crop window drawn.
    A carry claim is a claim about pixels; these are the pixels."""
    ovr = out / "overlays"
    ovr.mkdir(exist_ok=True)
    by_clip = {e["clip"]: e for e in plan}
    for clip in clips:
        entry = by_clip[clip]
        n = len(entry["steps"])
        for arm in arms:
            cr = by_arm[arm][clip]
            for frac in (0.0, 0.25, 0.5, 1.0):
                j = min(n - 1, int(round(frac * (n - 1))))
                st = entry["steps"][j]
                img = frame(clip, st["frame"])
                _draw(img, st["gt"], (0, 200, 0), "GT")
                w = cr["wins"][j]
                if (w[2] - w[0]) < img.shape[1]:
                    _draw(img, w, (0, 140, 255), "crop")
                v = cr["veto"][j]
                _draw(img, cr["boxes"][j], (255, 255, 0),
                      f"{arm}{'/' + v if v else ''} IoU={iou(cr['boxes'][j], st['gt']):.2f}")
                p = ovr / f"{clip}_{arm}_{int(frac * 100):03d}.jpg"
                cv2.imwrite(str(p), img)
                assert float((img == img[0, 0]).all(axis=2).mean()) < 0.99, \
                    f"{p} is >99% one colour -- failed render"
    print(f"[score] overlays for {clips} x {arms} -> {ovr}", flush=True)


def score(out: Path) -> None:
    plan = json.loads((out / "plan.json").read_text())
    arms = [a for a in ARMS if (out / f"carry_{a}.json").exists()]
    by_arm = {a: json.loads((out / f"carry_{a}.json").read_text()) for a in arms}
    d_max = json.loads((out / "dmax.json").read_text()) if (out / "dmax.json").exists() else {}

    per = {}
    for entry in plan:
        clip = entry["clip"]
        row = {}
        for a in arms:
            cr = by_arm[a][clip]
            ious = [iou(b, st["gt"]) for b, st in zip(cr["boxes"], entry["steps"])]
            ms = [m for m in cr["ms"] if m]
            rat = [r for r in cr["area_ratio"] if r]
            row[a] = {
                "median_iou": round(float(np.median(ious)), 3),
                "final_iou": round(ious[-1], 3),
                "held_frac": round(float(np.mean([i >= 0.25 for i in ious])), 3),
                "hz": round(1000.0 / float(np.median(ms)), 2) if ms else None,
                "n_lost": int(sum(b is None for b in cr["boxes"])),
                "veto_area": cr["veto"].count("area"),
                "veto_disp": cr["veto"].count("disp"),
                # a spiral is a box that only ever shrinks: no step grows it back.
                "monotone_shrink": bool(rat) and all(r < 1.0 for r in rat),
                "ious": [round(i, 3) for i in ious],
            }
        per[clip] = row

    summ = {}
    for a in arms:
        tail = [per[c][a]["median_iou"] for c in TAIL]
        easy = [per[c][a]["median_iou"] for c in EASY]
        summ[a] = {
            "tail_recovered": int(sum(v >= 0.25 for v in tail)),
            "tail_median_iou": round(float(np.median(tail)), 3),
            "easy_median_iou": round(float(np.median(easy)), 3),
            "spiral_clips": [c for c in TAIL if per[c][a]["monotone_shrink"]],
            "vetoes": sum(per[c][a]["veto_area"] + per[c][a]["veto_disp"] for c in CLIPS),
            "hz_median": round(float(np.median([per[c][a]["hz"] for c in CLIPS
                                                if per[c][a]["hz"]])), 2),
        }

    res = {"n_clips": len(plan), "tail": TAIL, "easy": EASY, "arms": arms,
           "dmax": d_max, "per_clip": per, "summary": summ}
    (out / "results.json").write_text(json.dumps(res, indent=1))

    # The clips the arms disagree about most -- one tail, one easy -- across every arm.
    # Data-driven so the pictures are chosen by the numbers, not by what reads well.
    def spread(c):
        v = [per[c][a]["median_iou"] for a in arms]
        return max(v) - min(v)
    _overlays(out, plan, by_arm,
              [max(TAIL, key=spread), max(EASY, key=spread)], arms)

    print(f"\n[score] tail={len(TAIL)} easy={len(EASY)}  D_MAX={d_max.get('d_max')}")
    print(f"{'arm':>4} | {'tail>=0.25':>10} | {'tail med':>8} | {'easy med':>8} | "
          f"{'spirals':>7} | {'vetoes':>6} | {'Hz':>5}")
    for a in arms:
        s = summ[a]
        print(f"{a:>4} | {s['tail_recovered']:>4}/{len(TAIL):<5} | "
              f"{s['tail_median_iou']:>8} | {s['easy_median_iou']:>8} | "
              f"{len(s['spiral_clips']):>7} | {s['vetoes']:>6} | {s['hz_median']:>5}")
    print("\nper-clip median IoU")
    print(f"{'clip':>11} | " + " | ".join(f"{a:>5}" for a in arms))
    for c in CLIPS:
        print(f"{c:>11} | " + " | ".join(f"{per[c][a]['median_iou']:>5.3f}" for a in arms))


def selfcheck() -> None:
    """Crop math, dead band, guard arithmetic -- the parts that silently produce a
    plausible-but-wrong box. No bridge, no device."""
    W, H = 1280, 720
    box = [600.0, 300.0, 640.0, 340.0]
    win = window(box, W, H, "fixed")
    assert win[2] - win[0] == CROP_SIDE and win[3] - win[1] == CROP_SIDE, win
    assert win[0] <= box[0] and win[2] >= box[2] and win[1] <= box[1] and win[3] >= box[3]
    # round trip: a box expressed in crop coords maps back to itself
    in_crop = [box[0] - win[0], box[1] - win[1], box[2] - win[0], box[3] - win[1]]
    back = [in_crop[0] + win[0], in_crop[1] + win[1], in_crop[2] + win[0], in_crop[3] + win[1]]
    assert iou(back, box) > 0.999, back
    # a box at the frame corner still yields a full-side window inside the frame
    edge = window([0.0, 0.0, 20.0, 20.0], W, H, "fixed")
    assert edge[0] >= 0 and edge[1] >= 0 and edge[2] <= W and edge[3] <= H, edge
    assert edge[2] - edge[0] == CROP_SIDE
    # whole-frame arm is a no-op window
    assert window(box, W, H, None) == (0, 0, W, H)
    # scaled window honours the min_side floor on a tiny box
    sc = window([600.0, 300.0, 610.0, 310.0], W, H, "scaled")
    assert max(sc[2] - sc[0], sc[3] - sc[1]) >= SCALED_MIN_SIDE, sc
    # dead band: centred box holds the window, a box near the edge moves it
    assert not outside_dead_band(box, win)
    assert outside_dead_band([win[0] + 4.0, win[1] + 4.0, win[0] + 20.0, win[1] + 20.0], win)
    # guard arithmetic: 2.5x AREA (1.58x linear), not 2.5x side
    grown = [600.0, 300.0, 600.0 + 40 * 1.58, 300.0 + 40 * 1.58]
    assert AREA_LO <= area(grown) / area(box) <= AREA_HI
    burst = [600.0, 300.0, 700.0, 400.0]
    assert area(burst) / area(box) > AREA_HI
    # displacement is in units of the previous box's long side
    assert abs(disp_norm([640.0, 300.0, 680.0, 340.0], box) - 1.0) < 1e-9
    print("exp5 self-check passed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["carry", "dmax", "score", "selfcheck"])
    ap.add_argument("--out", default=str(HERE / "runs" / "exp5"))
    ap.add_argument("--arms", default="A1,A2,A4")
    a = ap.parse_args()
    if a.mode == "selfcheck":
        selfcheck()
        return
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.mode == "carry":
        arms = [x.strip() for x in a.arms.split(",") if x.strip()]
        assert all(x in ARMS for x in arms), f"unknown arm in {arms}"
        carry(out, arms)
    elif a.mode == "dmax":
        dmax(out)
    else:
        score(out)


if __name__ == "__main__":
    main()
