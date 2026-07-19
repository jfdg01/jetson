"""P5.6 annotation-provenance renderer (design-time tool, run by Fable).

Regenerates the committed curation/prompt_<clip>_<frame>_z.jpg zoom renders
from scenes_p56.json: for each scene, the prompt frame (f0 + t_p*fps) is
cropped around the hand-annotated distractor_gt_prompt box, upscaled with a
10-px coordinate grid, and drawn with:

  red     = target GT at the prompt frame (from the UAV123 anno file)
  magenta = distractor_gt_prompt (the hand box the SWAP verdict checks against)

so every hand-set box in scenes_p56.json can be re-verified by eye.

Usage (repo root):
  .venv-ft/bin/python experiments/2026-07-14-direct-delivery-select/annotate_p56.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DATA = REPO / "experiments" / "2026-07-03-real-video-replay" / "data" / "UAV123"
OUT = HERE / "curation"
PAD = 90          # zoom margin around the hand box, full-frame px
FPS = 30.0


def load_gt(clip: str) -> list:
    rows = []
    for ln in (DATA / "anno" / "UAV123" / f"{clip}.txt").read_text().strip().splitlines():
        p = ln.replace(",", " ").split()
        try:
            x, y, w, h = (float(v) for v in p[:4])
            rows.append(None if math.isnan(x) else (x, y, x + w, y + h))
        except ValueError:
            rows.append(None)
    return rows


def render(scene: dict) -> Path:
    clip, f0 = scene["clip"], scene["f0"]
    prompt = f0 + round(scene["t_p"] * FPS)
    gt = load_gt(clip)
    img = cv2.imread(str(DATA / "data_seq" / "UAV123" / clip / f"{prompt + 1:06d}.jpg"))
    h, w = img.shape[:2]
    g = gt[prompt]
    if g is not None:
        cv2.rectangle(img, (int(g[0]), int(g[1])), (int(g[2]), int(g[3])),
                      (0, 0, 255), 1)
    d = scene["distractor_gt_prompt"]
    cv2.rectangle(img, (int(d[0]), int(d[1])), (int(d[2]), int(d[3])),
                  (255, 0, 255), 1)
    x0 = max(0, int(d[0]) - PAD); y0 = max(0, int(d[1]) - PAD)
    x1 = min(w, int(d[2]) + PAD); y1 = min(h, int(d[3]) + PAD)
    crop = img[y0:y1, x0:x1]
    s = max(2, 720 // max(x1 - x0, y1 - y0))
    crop = cv2.resize(crop, ((x1 - x0) * s, (y1 - y0) * s),
                      interpolation=cv2.INTER_NEAREST)
    for gx in range(x0 - x0 % 10, x1, 10):
        cv2.line(crop, ((gx - x0) * s, 0), ((gx - x0) * s, crop.shape[0]),
                 (60, 60, 60), 1)
        cv2.putText(crop, str(gx), ((gx - x0) * s + 1, 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 255), 1)
    for gy in range(y0 - y0 % 10, y1, 10):
        cv2.line(crop, (0, (gy - y0) * s), (crop.shape[1], (gy - y0) * s),
                 (60, 60, 60), 1)
        cv2.putText(crop, str(gy), (1, (gy - y0) * s + 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 255), 1)
    out = OUT / f"prompt_{clip}_{prompt}_z.jpg"
    cv2.imwrite(str(out), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    scenes = json.loads((HERE / "scenes_p56.json").read_text())["scenes"]
    for scene in scenes:
        print(render(scene))


if __name__ == "__main__":
    main()
