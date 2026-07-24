"""EXP-2 grounding-res elbow: how low can the VLM feed resolution go before the box
stops landing on the target -- swept for BOTH acquisition arms, ON THE ORIN.

The acquisition arms differ in WHICH resolution knob they expose:
  NL : whole-frame grounding  -> knob = JetsonBackend.max_side (long-edge feed px).
  PT : point-crop grounding   -> knob = select_p55.ROI_RES (crop upscaled to this, LANCZOS).
Both are client-side resizes fed to the SAME deployed q8_0 server (max_side is per-call,
_llama_server_chat(..., self.max_side); the crop is <= 1024 so it passes through un-downsized).

Metric is grounding accuracy only -- IoU(grounded box, TARGET GT at the command frame) on the
WSEL leg -- so no SAM2 carry is needed and the elbow isolates the feed-resolution knob. hit =
IoU >= 0.5. machine=jetson. Run AFTER the on-device SAM2 sweeps free the GPU (VLM+SAM2 contend).

    .venv-ft/bin/python ground_sweep.py --matrix .../scenes_p518.json --out runs/exp2
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
N25 = REPO / "experiments" / "2026-07-20-n25-select"
P55 = REPO / "experiments" / "2026-07-14-select-generalization"
E24 = REPO / "experiments" / "2026-07-04-warm-start-acquire"
for p in (HERE, N25, P55, E24, REPO, REPO / "grounding"):
    sys.path.insert(0, str(p))

from curate_p518 import frame, load_gt                 # noqa: E402
from replay_e24 import MAX_SIDE, _valid, vlm_acquire    # noqa: E402
from replay_source import iou                           # noqa: E402
import select_p55                                        # noqa: E402  (mutate ROI_RES)
from select_p55 import roi_reanchor                      # noqa: E402
from select_exp2 import FPS, _center_box, _gating        # noqa: E402

NL_SIZES = [512, 640, 768, 896, 1024]        # whole-frame long-edge feed px (deployed = 1024)
PT_SIZES = [192, 256, 384, 512, 768]         # ROI crop upscale px (deployed = 512)
HIT = 0.5                                     # IoU floor for "grounded on the target"


def _submit(be):
    def submit_img(img_bgr, caption):
        h, w = img_bgr.shape[:2]
        path = f"/dev/shm/exp2_gs_{time.monotonic_ns()}.png"
        cv2.imwrite(path, img_bgr)
        try:
            return vlm_acquire(be, path, caption, w, h)
        finally:
            Path(path).unlink(missing_ok=True)
    return submit_img


def _agg(per):
    ious = list(per.values())
    return {"n": len(ious), "hit_rate": round(float(np.mean([i >= HIT for i in ious])), 3),
            "median_iou": round(float(np.median(ious)), 4),
            "mean_iou": round(float(np.mean(ious)), 4), "per": {k: round(v, 4) for k, v in per.items()}}


def sweep(out: Path, matrix: str) -> None:
    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend

    scenes = _gating(matrix)
    # WSEL cells only: ground the TARGET at the command frame, score vs target GT.
    cells = []
    for s in scenes:
        cmd = s["f0"] + round(s["t_p"] * FPS)
        gt = load_gt(s["clip"])
        if cmd < len(gt) and gt[cmd] is not None:
            cells.append((s, cmd, tuple(gt[cmd])))
    print(f"[gsweep] {len(cells)} WSEL target-grounding cells", flush=True)

    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=1024)
    submit_img = _submit(be)
    res = {"nl": {}, "pt": {}, "n_cells": len(cells), "hit_floor": HIT,
           "nl_sizes": NL_SIZES, "pt_sizes": PT_SIZES}
    ovr = out / "gsweep_overlays"
    ovr.mkdir(exist_ok=True)
    try:
        # --- NL: whole-frame feed at each max_side -----------------------
        for ms in NL_SIZES:
            be.max_side = ms
            per = {}
            for s, cmd, tgt in cells:
                fr = frame(s["clip"], cmd)
                box = submit_img(fr, s["target_caption"])
                per[f"{s['clip']}_{s['f0']}"] = iou(tuple(box), tgt) if _valid(box, fr.shape) else 0.0
                if ms == NL_SIZES[0] and len(per) <= 3:  # look-at-it at the low end
                    _draw(ovr / f"NL_{ms}_{s['clip']}_{s['f0']}.jpg", fr, box, tgt)
            res["nl"][ms] = _agg(per)
            print(f"[gsweep] NL max_side={ms}: hit {res['nl'][ms]['hit_rate']} "
                  f"medIoU {res['nl'][ms]['median_iou']}", flush=True)
        be.max_side = 1024   # crop feed never downsized

        # --- PT: point-crop upscaled to each ROI_RES ---------------------
        for rr in PT_SIZES:
            select_p55.ROI_RES = rr
            per = {}
            for s, cmd, tgt in cells:
                fr = frame(s["clip"], cmd)
                box, _ = roi_reanchor(fr, _center_box(tgt), s["target_caption"], submit_img)
                per[f"{s['clip']}_{s['f0']}"] = iou(tuple(box), tgt) if _valid(box, fr.shape) else 0.0
                if rr == PT_SIZES[0] and len(per) <= 3:
                    _draw(ovr / f"PT_{rr}_{s['clip']}_{s['f0']}.jpg", fr, box, tgt)
            res["pt"][rr] = _agg(per)
            print(f"[gsweep] PT ROI_RES={rr}: hit {res['pt'][rr]['hit_rate']} "
                  f"medIoU {res['pt'][rr]['median_iou']}", flush=True)
    finally:
        be.close()
    (out / "ground_sweep.json").write_text(json.dumps(res, indent=1))
    print(f"[gsweep] -> {out / 'ground_sweep.json'}", flush=True)


def _draw(path, fr, box, tgt):
    img = fr.copy()
    cv2.rectangle(img, (int(tgt[0]), int(tgt[1])), (int(tgt[2]), int(tgt[3])), (0, 0, 220), 2)
    if box is not None and _valid(box, fr.shape):
        b = [int(v) for v in box]
        cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), (0, 220, 0), 2)
    cv2.putText(img, f"{path.stem} green=grounded red=tgtGT", (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    assert float((img == img[0, 0]).all(axis=2).mean()) < 0.99, f"{path} one-colour"
    cv2.imwrite(str(path), img)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--matrix", default=str(N25 / "scenes_p518.json"))
    ap.add_argument("--out", default="runs/exp2")
    a = ap.parse_args()
    o = Path(a.out); o.mkdir(parents=True, exist_ok=True)
    sweep(o, a.matrix)
