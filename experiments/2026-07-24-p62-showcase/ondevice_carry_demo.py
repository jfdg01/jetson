"""On-Jetson end-to-end carry demonstration (GPU-independent half of P6.2-SHOWCASE).

Proves the deployed SAM2 carry runs literally on the Orin, seeded by an oracle-designation
GT box (the showcase's designation model), stepped over real UAV123 frames through the
`jetson_carry_service.py` socket protocol (the exact path the showcase FLIGHT's `_SSHCarry`
factory will use) -- with no 3090 and no CARLA. The CARLA closed loop is a separate, GPU-blocked
step; this de-risks the carry seam and demonstrates the on-device capability on real imagery.

  stage : pick a local UAV123 clip, dump the seed frame + N stepped frames as JPEGs + meta.json
          (seed box = GT at the seed frame; per-step GT for scoring). Runs on the host.
  score : overlay the Jetson-carried boxes (from the on-device client's boxes.json) on the real
          frames, compute IoU vs GT, assert the look-at-it mechanical checks, save + summarise.

Carry itself runs on the Orin via carry_client.py (this file never imports torch/SAM2).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments" / "2026-07-20-n25-select"))
sys.path.insert(0, str(REPO / "experiments" / "2026-07-03-real-video-replay"))
from curate_p518 import frame, load_gt        # noqa: E402  1-indexed frame + GT rows
from replay_source import iou                  # noqa: E402

STRIDE = 11          # 2.69 Hz carry over 30 fps video (R-16; matches P5.21 CARRY_STRIDE)
N_STEPS = 24         # ~264 video frames ~= 8.8 s of on-device carry
CANDIDATES = ["car1", "car9", "car6", "car16", "car4", "car10", "truck2"]


def _contiguous_gt(clip: str, seed: int, last: int):
    """Return the GT rows for seed..last if all present (non-None), else None."""
    gt = load_gt(clip)
    if last >= len(gt):
        return None
    rows = [gt[i] for i in range(seed, last + 1)]
    return rows if all(r is not None for r in rows) else None


def stage(out: Path) -> dict:
    seed = 1
    last = seed + N_STEPS * STRIDE
    for clip in CANDIDATES:
        try:
            rows = _contiguous_gt(clip, seed, last)
        except Exception:
            rows = None
        if rows is None:
            continue
        stepdir = out / "frames"
        stepdir.mkdir(parents=True, exist_ok=True)
        steps = [seed + k * STRIDE for k in range(1, N_STEPS + 1)]
        meta = {"clip": clip, "seed_frame": seed, "stride": STRIDE,
                "seed_box": list(load_gt(clip)[seed]), "steps": [],
                "image_wh": None}
        img = frame(clip, seed)
        h, w = img.shape[:2]
        meta["image_wh"] = [w, h]
        cv2.imwrite(str(stepdir / "seed.jpg"), img)
        gt = load_gt(clip)
        for j, fi in enumerate(steps):
            cv2.imwrite(str(stepdir / f"s{j:03d}.jpg"), frame(clip, fi))
            meta["steps"].append({"j": j, "frame": fi, "gt": list(gt[fi])})
        (out / "meta.json").write_text(json.dumps(meta, indent=1))
        print(f"[stage] clip={clip} seed={seed} steps={len(steps)} "
              f"stride={STRIDE} -> {out}", flush=True)
        return meta
    raise SystemExit(f"no candidate clip has contiguous GT for {N_STEPS} steps @ stride {STRIDE}")


def _draw(img, box, color, label=None):
    if box is None:
        return
    x0, y0, x1, y1 = [int(v) for v in box]
    cv2.rectangle(img, (x0, y0), (x1, y1), color, 2)
    if label:
        cv2.putText(img, label, (x0, max(0, y0 - 6)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, color, 2)


def score(out: Path) -> dict:
    meta = json.loads((out / "meta.json").read_text())
    boxes = json.loads((out / "boxes.json").read_text())   # from carry_client.py on the Orin
    ovr = out / "overlays"
    ovr.mkdir(exist_ok=True)
    clip = meta["clip"]
    ious, mss, held = [], [], 0
    carried = boxes["boxes"]           # list of [x1,y1,x2,y2]|None, per step
    mss = [m for m in boxes["ms"] if m is not None]
    prev_saved = None
    for st in meta["steps"]:
        j, fi, gt = st["j"], st["frame"], tuple(st["gt"])
        cb = carried[j]
        i = iou(tuple(cb), gt) if cb else 0.0
        ious.append(i)
        if i >= 0.25:
            held += 1
        img = frame(clip, fi)
        _draw(img, gt, (0, 200, 0), "GT")                 # green
        _draw(img, cb, (255, 255, 0), f"carry j{j} IoU{i:.2f}")   # cyan
        p = ovr / f"s{j:03d}.jpg"
        cv2.imwrite(str(p), img)
        prev_saved = img
    # look-at-it mechanical asserts on a mid-run overlay
    mid = cv2.imread(str(ovr / f"s{len(meta['steps'])//2:03d}.jpg"))
    frac = (mid == mid[0, 0]).all(axis=2).mean()
    assert frac < 0.99, f"mid overlay is {frac:.2%} one colour -- failed render"
    import numpy as np
    med_iou = float(np.median(ious))
    hz = round(1000.0 / (sum(mss) / len(mss)), 3) if mss else None
    summ = {"clip": clip, "n_steps": len(ious), "held_frac": round(held / len(ious), 3),
            "median_iou": round(med_iou, 3), "min_iou": round(min(ious), 3),
            "final_iou": round(ious[-1], 3), "carry_hz_ondevice": hz,
            "median_ms_ondevice": round(float(np.median(mss)), 1) if mss else None,
            "ious": [round(x, 3) for x in ious]}
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    print(f"[score] {clip}: held {held}/{len(ious)} (median IoU {med_iou:.2f}), "
          f"on-device carry {hz} Hz ({summ['median_ms_ondevice']} ms/step)", flush=True)
    return summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["stage", "score"])
    ap.add_argument("--out", default="runs/p62_showcase/ondevice")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (stage if a.mode == "stage" else score)(out)


if __name__ == "__main__":
    main()
