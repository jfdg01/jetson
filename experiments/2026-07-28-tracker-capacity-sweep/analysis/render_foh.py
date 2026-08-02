#!/usr/bin/env python3
"""ZOH against FOH on the same frame: what the consumer holds, and what coasting it would give.

Notes 19 and 20 close the FOH result on JSON alone. This is the missing look at the pixels. Three
boxes on every frame of a paced run:

    verde     GT
    rojo      ZOH -- the last answer, frozen until the next one lands
    azul      FOH -- the same answer coasted along its own velocity

They coincide exactly on the frames where an answer lands, and separate in between. That gap IS the
+0.069, so the clip either shows it or the number is not about what we think it is.

    analysis/render_foh.py raw/paced-sweep-30/sam2_c512__truck2.json --out proof/foh__truck2.mp4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data  # noqa: E402
from aggregate import extrapolate, held  # noqa: E402
from render_overlay import iou  # noqa: E402

GREEN, RED, BLUE = (60, 220, 60), (60, 60, 235), (235, 160, 60)
ALPHA = 0.35


def draw(img, box, colour) -> None:
    if not box:
        return
    b = [int(v) for v in box]
    over = img.copy()
    cv2.rectangle(over, (b[0], b[1]), (b[2], b[3]), colour, -1)
    cv2.addWeighted(over, ALPHA, img, 1 - ALPHA, 0, img)
    cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), colour, 2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("result_json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", metavar="A:B", help="1-based inclusive range")
    ap.add_argument("--scale", type=int, default=960, metavar="W")
    ap.add_argument("--zoom", type=int, metavar="N",
                    help="crop an NxN window tracking GT instead of the full frame. A 40 px truck "
                         "in a 1280 frame is 30 px on screen and the three boxes just overlap")
    args = ap.parse_args()

    res = json.loads(Path(args.result_json).read_text())
    meta = res["meta"]
    assert meta.get("fps_stream"), "not a paced run -- ZOH and FOH are the same thing without one"
    gt, frames = data.boxes(meta["seq"]), data.frame_paths(meta["seq"])
    zoh = held(res["rows"], meta["fps_stream"], len(gt))
    foh = extrapolate(zoh)
    landed = {r["i"] for r in res["rows"]}

    a, b = (int(v) for v in args.frames.split(":")) if args.frames else (1, len(frames))
    keep = list(range(a - 1, min(b, len(frames))))
    assert keep, f"empty range over {len(frames)} frames"

    h0, w0 = cv2.imread(str(frames[keep[0]])).shape[:2]
    if args.zoom:
        # the window is smoothed over GT so it does not jitter frame to frame -- it is furniture,
        # not a measurement, and a shaking crop makes the box separation unreadable
        c = np.array([[(g[0] + g[2]) / 2, (g[1] + g[3]) / 2] if g else [np.nan, np.nan] for g in gt])
        for k in (0, 1):
            v = c[:, k]
            ok = ~np.isnan(v)
            v[:] = np.interp(np.arange(len(v)), np.flatnonzero(ok), v[ok])
            c[:, k] = np.convolve(v, np.ones(31) / 31, "same")
        h0 = w0 = args.zoom
    w, h = args.scale, int(round(h0 * args.scale / w0)) // 2 * 2
    out = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), 30, (w, h))
    mid, sums, hashes = keep[len(keep) // 2], [0.0, 0.0], []

    for j in keep:
        img = cv2.imread(str(frames[j]))
        g, z, f = gt[j], zoh.get(j, {}).get("box"), foh.get(j, {}).get("box")
        if args.zoom:
            fh, fw = img.shape[:2]
            x = int(np.clip(c[j, 0] - args.zoom / 2, 0, fw - args.zoom))
            y = int(np.clip(c[j, 1] - args.zoom / 2, 0, fh - args.zoom))
            img = img[y:y + args.zoom, x:x + args.zoom].copy()
            sh = lambda b: [b[0] - x, b[1] - y, b[2] - x, b[3] - y] if b else b  # noqa: E731
            draw(img, sh(g), GREEN), draw(img, sh(z), RED), draw(img, sh(f), BLUE)
        else:
            draw(img, g, GREEN), draw(img, z, RED), draw(img, f, BLUE)
        if g:
            sums[0] += iou(g, z) if z else 0.0
            sums[1] += iou(g, f) if f else 0.0
        fresh = "RESPUESTA" if j in landed else "retenido"
        img = cv2.resize(img, (w, h))
        cv2.putText(img, f"f{j + 1}  {fresh}  ZOH rojo {iou(g, z) if g and z else 0:.2f}"
                        f"  FOH azul {iou(g, f) if g and f else 0:.2f}",
                    (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2)
        out.write(img)
        hashes.append(hash(img.tobytes()))
        if j == mid:
            cv2.imwrite(args.out.replace(".mp4", ".mid.png"), img)
    out.release()

    # the render either shows motion or it is a dead feed dressed up as 900 frames -- assert both
    assert len(set(hashes)) > len(hashes) * 0.5, "fotogramas identicos: el render esta muerto"
    n = sum(1 for j in keep if gt[j])
    print(f"{meta['seq']}  {len(keep)} fotogramas, {n} con GT, {len(landed & set(keep))} respuestas")
    print(f"  ZOH {sums[0] / n:.3f}   FOH {sums[1] / n:.3f}   delta {(sums[1] - sums[0]) / n:+.3f}")
    print(f"  {args.out}  +  {args.out.replace('.mp4', '.mid.png')}")


if __name__ == "__main__":
    main()
