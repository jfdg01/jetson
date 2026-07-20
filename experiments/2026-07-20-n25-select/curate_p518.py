"""P5.18 scene-curation tooling (design-time, run by Fable; committed for
reproducibility of the scene set's provenance).

The P5.14/P5.16 select results gate on n=5 scenes; the standing sample-size
rule (2026-07-20) requires n >= 25 per gating condition. This tool is how the
expanded scene set was authored, with every step leaving a committed render
so the curation can be re-verified by eye:

  montage --clip C          tile candidate prompt-frames (stride over the
                            usable f0 range) with target GT drawn -> the
                            shortlisting view (curation/montage_<clip>.png)
  scene --clip C --f0 N     full-res 2-up: discovery-start frame (f0-150)
                            and prompt frame (f0+t_p*30), target GT drawn ->
                            the caption-authoring view
  zoom --clip C --frame F --center X,Y [--pad P]
                            upscaled crop with a 10-px grid -> the
                            distractor hand-annotation view
  verify                    mechanical asserts over scenes_p518.json
                            (bounds, GT validity, spacing, caption
                            distinctness) + a tiled per-scene zoom of every
                            hand distractor box (verify_grid_*.png) -> the
                            final look-at-every-box view

Usage (repo root):
  .venv-ft/bin/python experiments/2026-07-20-n25-select/curate_p518.py montage --clip car9
  .venv-ft/bin/python experiments/2026-07-20-n25-select/curate_p518.py scene --clip car9 --f0 800
  .venv-ft/bin/python experiments/2026-07-20-n25-select/curate_p518.py zoom --clip car9 --frame 1040 --center 640,300
  .venv-ft/bin/python experiments/2026-07-20-n25-select/curate_p518.py verify
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DATA = REPO / "experiments" / "2026-07-03-real-video-replay" / "data" / "UAV123"
OUT = HERE / "curation"
FPS = 30.0
DS_OFFSET = 150          # matches discover_p516.DS_OFFSET
COVER_F = 300            # 10 s coverage window after the prompt


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


def frame(clip: str, idx: int):
    img = cv2.imread(str(DATA / "data_seq" / "UAV123" / clip / f"{idx + 1:06d}.jpg"))
    assert img is not None, f"{clip} frame {idx} missing"
    return img


def clip_len(clip: str) -> int:
    return len(list((DATA / "data_seq" / "UAV123" / clip).glob("*.jpg")))


def draw_gt(img, g, color=(0, 0, 255), t=2):
    if g is not None:
        cv2.rectangle(img, (int(g[0]), int(g[1])), (int(g[2]), int(g[3])), color, t)


def montage(clip: str, stride: int, tile_w: int) -> Path:
    n, gt = clip_len(clip), load_gt(clip)
    lo, hi = DS_OFFSET, n - (240 + COVER_F + 5)
    assert hi > lo, f"{clip} too short ({n} frames)"
    f0s = list(range(lo, hi + 1, stride))
    tiles = []
    for f0 in f0s:
        p = f0 + 240                      # prompt frame at t_p = 8 s
        img = frame(clip, p).copy()
        draw_gt(img, gt[p] if p < len(gt) else None, t=3)
        s = tile_w / img.shape[1]
        img = cv2.resize(img, (tile_w, int(img.shape[0] * s)))
        cv2.putText(img, f"f0={f0} prompt={p}", (6, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        tiles.append(img)
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    th, tw = tiles[0].shape[:2]
    canvas = np.zeros((rows * th, cols * tw, 3), np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        canvas[r * th:r * th + t.shape[0], c * tw:c * tw + t.shape[1]] = t
    out = OUT / f"montage_{clip}.png"
    cv2.imwrite(str(out), canvas)
    print(f"{out}  ({len(tiles)} tiles, f0 range {lo}..{hi})")
    return out


def scene_view(clip: str, f0: int, t_p: float) -> Path:
    gt = load_gt(clip)
    ds, prompt = f0 - DS_OFFSET, f0 + round(t_p * FPS)
    top, bot = frame(clip, ds).copy(), frame(clip, prompt).copy()
    draw_gt(top, gt[ds] if ds < len(gt) else None)
    draw_gt(bot, gt[prompt] if prompt < len(gt) else None)
    cv2.putText(top, f"{clip} ds={ds} (discovery start) red=targetGT",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    cv2.putText(bot, f"{clip} prompt={prompt} (f0={f0}+{round(t_p*FPS)})",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    out = OUT / f"scene_{clip}_{f0}.png"
    cv2.imwrite(str(out), np.vstack([top, bot]))
    print(out)
    return out


def zoom(clip: str, fr: int, cx: int, cy: int, pad: int) -> Path:
    gt = load_gt(clip)
    img = frame(clip, fr).copy()
    draw_gt(img, gt[fr] if fr < len(gt) else None, t=1)
    h, w = img.shape[:2]
    x0, y0 = max(0, cx - pad), max(0, cy - pad)
    x1, y1 = min(w, cx + pad), min(h, cy + pad)
    crop = img[y0:y1, x0:x1]
    s = max(2, 720 // max(x1 - x0, y1 - y0))
    crop = cv2.resize(crop, ((x1 - x0) * s, (y1 - y0) * s),
                      interpolation=cv2.INTER_NEAREST)
    for gx in range(x0 - x0 % 10 + 10, x1, 10):        # 10-px grid
        cv2.line(crop, ((gx - x0) * s, 0), ((gx - x0) * s, crop.shape[0]),
                 (80, 80, 80), 1)
        if gx % 50 == 0:
            cv2.putText(crop, str(gx), ((gx - x0) * s + 2, 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    for gy in range(y0 - y0 % 10 + 10, y1, 10):
        cv2.line(crop, (0, (gy - y0) * s), (crop.shape[1], (gy - y0) * s),
                 (80, 80, 80), 1)
        if gy % 50 == 0:
            cv2.putText(crop, str(gy), (2, (gy - y0) * s + 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    out = OUT / f"zoom_{clip}_{fr}.png"
    cv2.imwrite(str(out), crop)
    print(f"{out}  (crop [{x0},{y0},{x1},{y1}], x{s})")
    return out


def verify() -> None:
    scenes = json.loads((HERE / "scenes_p518.json").read_text())["scenes"]
    by_clip: dict = {}
    tiles = []
    for sc in scenes:
        clip, f0, t_p = sc["clip"], sc["f0"], sc["t_p"]
        n, gt = clip_len(clip), load_gt(clip)
        prompt = f0 + round(t_p * FPS)
        ds = f0 - DS_OFFSET
        assert ds >= 0, (clip, f0, "no discovery pre-roll")
        assert prompt + COVER_F <= n + 60, (clip, f0, "coverage past clip end")
        assert gt[ds] is not None, (clip, f0, "target GT NaN at ds")
        assert gt[prompt] is not None, (clip, f0, "target GT NaN at prompt")
        nan_cover = sum(1 for g in gt[prompt:min(prompt + COVER_F, n)]
                        if g is None)
        assert nan_cover <= 60, (clip, f0, f"{nan_cover} NaN GT frames in cover")
        assert sc["target_caption"] != sc["distractor_caption"], (clip, f0)
        d = sc["distractor_gt_prompt"]
        assert 0 <= d[0] < d[2] <= 1280 and 0 <= d[1] < d[3] <= 720, (clip, f0, d)
        g = gt[prompt]
        ix0, iy0 = max(d[0], g[0]), max(d[1], g[1])
        ix1, iy1 = min(d[2], g[2]), min(d[3], g[3])
        inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
        a_d = (d[2] - d[0]) * (d[3] - d[1])
        a_g = (g[2] - g[0]) * (g[3] - g[1])
        iou_dg = inter / (a_d + a_g - inter)
        assert iou_dg < 0.25, (clip, f0, f"distractor GT overlaps target GT {iou_dg:.2f}")
        by_clip.setdefault(clip, []).append(f0)

        img = frame(clip, prompt).copy()
        draw_gt(img, g, (0, 0, 255), 1)
        draw_gt(img, d, (255, 0, 255), 1)
        cx = int((d[0] + d[2]) / 2)
        cy = int((d[1] + d[3]) / 2)
        pad = max(70, int(max(d[2] - d[0], d[3] - d[1])))
        h, w = img.shape[:2]
        x0, y0 = max(0, cx - pad), max(0, cy - pad)
        x1, y1 = min(w, cx + pad), min(h, cy + pad)
        crop = cv2.resize(img[y0:y1, x0:x1], (260, 260),
                          interpolation=cv2.INTER_NEAREST)
        cv2.putText(crop, f"{clip}:{f0}", (4, 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        cv2.putText(crop, sc["distractor_caption"][:34], (4, 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 0, 255), 1)
        tiles.append(crop)
    for clip, f0s in by_clip.items():
        f0s = sorted(f0s)
        for a, b in zip(f0s, f0s[1:]):
            assert b - a >= 200, (clip, a, b, "scenes closer than 200 frames")
    cols, per = 5, 25
    for pg in range((len(tiles) + per - 1) // per):
        chunk = tiles[pg * per:(pg + 1) * per]
        rows = (len(chunk) + cols - 1) // cols
        canvas = np.zeros((rows * 260, cols * 260, 3), np.uint8)
        for i, t in enumerate(chunk):
            r, c = divmod(i, cols)
            canvas[r * 260:(r + 1) * 260, c * 260:(c + 1) * 260] = t
        out = OUT / f"verify_grid_{pg}.png"
        cv2.imwrite(str(out), canvas)
        print(out)
    ng = sum(1 for s in scenes if s.get("gating", True))
    print(f"verify OK: {len(scenes)} scenes ({ng} gating), "
          f"{len(by_clip)} clips: "
          + ", ".join(f"{c}x{len(v)}" for c, v in sorted(by_clip.items())))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("montage")
    m.add_argument("--clip", required=True)
    m.add_argument("--stride", type=int, default=100)
    m.add_argument("--tile-w", type=int, default=426)
    s = sub.add_parser("scene")
    s.add_argument("--clip", required=True)
    s.add_argument("--f0", type=int, required=True)
    s.add_argument("--tp", type=float, default=8.0)
    z = sub.add_parser("zoom")
    z.add_argument("--clip", required=True)
    z.add_argument("--frame", type=int, required=True)
    z.add_argument("--center", required=True, help="cx,cy full-frame px")
    z.add_argument("--pad", type=int, default=80)
    sub.add_parser("verify")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    if args.cmd == "montage":
        montage(args.clip, args.stride, args.tile_w)
    elif args.cmd == "scene":
        scene_view(args.clip, args.f0, args.tp)
    elif args.cmd == "zoom":
        cx, cy = (int(v) for v in args.center.split(","))
        zoom(args.clip, args.frame, cx, cy, args.pad)
    elif args.cmd == "verify":
        verify()


if __name__ == "__main__":
    main()
