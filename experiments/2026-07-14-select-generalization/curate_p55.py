"""P5.5 scene-curation helpers (design-time tool, run by Fable while curating).

Three subcommands:

  sheet   -- contact sheets (3x3, every --stride frames) with the target GT box
             drawn (red) so co-visible same-class distractors can be spotted.
  frame   -- one full-res frame with a 40-px coordinate grid + GT box, used to
             hand-annotate distractor boxes by reading the image.
  check   -- validate a scenes json against the P5.4 rig's assumptions:
             GT present at f0, f0 + t_p*fps + acquire-slack + cover*fps inside
             the clip, distractor box inside the frame, boxes non-degenerate.

Usage (from repo root, .venv-ft):
  .venv-ft/bin/python experiments/2026-07-14-select-generalization/curate_p55.py \
      sheet car14 --start 0 --stride 100
  .venv-ft/bin/python .../curate_p55.py frame car14 300
  .venv-ft/bin/python .../curate_p55.py frame car14 300 --zoom 400,200,900,600
  .venv-ft/bin/python .../curate_p55.py check scenes_p55.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DATA = REPO / "experiments" / "2026-07-03-real-video-replay" / "data" / "UAV123"
OUT = HERE / "curation"


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


def frame_path(clip: str, f0: int) -> Path:
    return DATA / "data_seq" / "UAV123" / clip / f"{f0 + 1:06d}.jpg"


def draw_gt(img, box, color=(0, 0, 255)):
    if box is not None:
        x1, y1, x2, y2 = (int(v) for v in box)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)


def cmd_sheet(a):
    gt = load_gt(a.clip)
    idxs = list(range(a.start, min(a.start + 9 * a.stride, len(gt)), a.stride))[:9]
    tiles = []
    for i in idxs:
        img = cv2.imread(str(frame_path(a.clip, i)))
        draw_gt(img, gt[i] if i < len(gt) else None)
        cv2.putText(img, f"f0={i}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 2.0,
                    (0, 255, 255), 4)
        tiles.append(cv2.resize(img, (640, 360)))
    while len(tiles) < 9:
        tiles.append(np.zeros((360, 640, 3), np.uint8))
    rows = [np.hstack(tiles[r * 3:(r + 1) * 3]) for r in range(3)]
    OUT.mkdir(exist_ok=True)
    out = OUT / f"sheet_{a.clip}_{a.start}.jpg"
    cv2.imwrite(str(out), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(out)


def cmd_frame(a):
    gt = load_gt(a.clip)
    img = cv2.imread(str(frame_path(a.clip, a.f0)))
    draw_gt(img, gt[a.f0] if a.f0 < len(gt) else None)
    h, w = img.shape[:2]
    for x in range(0, w, 40):
        cv2.line(img, (x, 0), (x, h), (80, 80, 80), 1)
        cv2.putText(img, str(x), (x + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                    (255, 255, 0), 1)
    for y in range(0, h, 40):
        cv2.line(img, (0, y), (w, y), (80, 80, 80), 1)
        cv2.putText(img, str(y), (2, y + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                    (255, 255, 0), 1)
    if a.zoom:
        x1, y1, x2, y2 = (int(v) for v in a.zoom.split(","))
        img = img[y1:y2, x1:x2]
        img = cv2.resize(img, (img.shape[1] * 2, img.shape[0] * 2),
                         interpolation=cv2.INTER_NEAREST)
    if a.box:
        # draw a candidate distractor box (green) to verify a hand annotation
        bx = [int(v) for v in a.box.split(",")]
        draw_gt(img, bx, color=(0, 255, 0))
    OUT.mkdir(exist_ok=True)
    tag = "z" if a.zoom else "g"
    out = OUT / f"frame_{a.clip}_{a.f0}_{tag}.jpg"
    cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(out)


def cmd_check(a):
    doc = json.loads((HERE / a.scenes).read_text() if not Path(a.scenes).is_absolute()
                     else Path(a.scenes).read_text())
    fps, ok = 30.0, True
    for s in doc["scenes"]:
        gt = load_gt(s["clip"])
        f0, tp = s["f0"], s["t_p"]
        # Rig-aligned bounds: the harness hard-fails only if deliver >= clip_len
        # (deliver = prompt + acquire; 180 frames = 6 s acquire slack, measured
        # full-frame acquire is ~4.5 s). Coverage past clip end is CLAMPED by
        # window() and handled by the scorer (P5.3 ran car7:460 exactly so),
        # so a truncated coverage window is a warning, not a failure.
        deliver_max = f0 + int(tp * fps) + 180
        full_cover = deliver_max + int(10.0 * fps)
        msgs, warns = [], []
        if gt[f0] is None:
            msgs.append("GT NaN at f0")
        if deliver_max >= len(gt):
            msgs.append(f"clip too short: deliver bound f{deliver_max}, "
                        f"have {len(gt) - 1}")
        elif full_cover >= len(gt):
            warns.append(f"coverage truncated at clip end (full 10 s wants "
                         f"f{full_cover}, have {len(gt) - 1})")
        x1, y1, x2, y2 = s["distractor_box"]
        if not (0 <= x1 < x2 <= 1280 and 0 <= y1 < y2 <= 720):
            msgs.append("distractor box out of frame / degenerate")
        if gt[f0] is not None:
            gx1, gy1, gx2, gy2 = gt[f0]
            ix = max(0, min(x2, gx2) - max(x1, gx1))
            iy = max(0, min(y2, gy2) - max(y1, gy1))
            if ix * iy > 0.3 * (x2 - x1) * (y2 - y1):
                msgs.append("distractor box overlaps target GT > 30%")
        for k in ("target_caption", "distractor_caption", "note"):
            if not s.get(k):
                msgs.append(f"missing {k}")
        status = "OK" if not msgs else "FAIL: " + "; ".join(msgs)
        if warns:
            status += "  [warn: " + "; ".join(warns) + "]"
        ok &= not msgs
        print(f"{s['clip']}:{f0}  gt[f0]={gt[f0]}  {status}")
    print("ALL OK" if ok else "CHECK FAILED")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("sheet"); p.add_argument("clip")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--stride", type=int, default=100)
    p = sub.add_parser("frame"); p.add_argument("clip"); p.add_argument("f0", type=int)
    p.add_argument("--zoom"); p.add_argument("--box")
    p = sub.add_parser("check"); p.add_argument("scenes")
    a = ap.parse_args()
    {"sheet": cmd_sheet, "frame": cmd_frame, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    main()
