"""Whole-frame grounding eyeball dump — feed RefDrone/VisDrone frames at a chosen
long-edge resolution and render what the VLM actually sees + what it predicts.

Branch `test/whole-frame-resolution`. The question this answers: with NO downscale
(or a high max_side), how much better does the deployed Q8_0 spine ground tiny aerial
targets vs the 512 baseline? Numbers come from the manifest sweep; this script is the
visual layer so a human can judge the boxes, not just the IoU column.

Per sample it writes two files into <out>/:
  fed/<rank>_<iou>_<name>.png        — the exact pixels sent to the model (long-edge
                                        resized to --max-side; this IS the VLM input)
  annotated/<rank>_<iou>_<name>.png  — same image, GT box (green) + prediction (red),
                                        caption + IoU in the header strip

Coords are box-invariant: pred and GT are both 0-COORD_SCALE of the ORIGINAL frame,
and a whole-image resize keeps that normalization, so both draw correctly on the fed
(resized) image using its own w/h — same metric-safety the resolution lever relies on.

Sample pick is a difficulty SPREAD (sorted by GT box long-edge px): the tiniest, the
median, and the largest, interleaved — so the dump covers the hard tiny-object cases
the whole experiment is about, not just easy big boxes.

Usage (Jetson Q8_0, whole frame):
  source .venv-ft/bin/activate
  python results/2026-06-30-whole-frame-resolution/visualize.py \
      --backend jetson --quant q8_0 --max-side 1920 --n 12

Self-check (no model, no Jetson):
  python results/2026-06-30-whole-frame-resolution/visualize.py --selfcheck
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root on path

from grounding.contract import COORD_SCALE, iou, parse_bbox
from grounding.eval.backends import _resize_keep_aspect


def _box_px(bbox, w, h):
    """0-COORD_SCALE box -> pixel XYXY in a w x h image."""
    return [bbox[0] / COORD_SCALE * w, bbox[1] / COORD_SCALE * h,
            bbox[2] / COORD_SCALE * w, bbox[3] / COORD_SCALE * h]


def _long_edge_px(s):
    px = _box_px(s.bbox, s.img_w, s.img_h)
    return max(px[2] - px[0], px[3] - px[1])


def pick_spread(samples, n):
    """n samples spread evenly across the GT-box-size distribution (small->large)."""
    ordered = sorted(samples, key=_long_edge_px)
    if n >= len(ordered):
        return ordered
    idx = [round(i * (len(ordered) - 1) / (n - 1)) for i in range(n)] if n > 1 else [0]
    return [ordered[i] for i in idx]


def annotate(fed_img, gt_px, pred_px, caption, iou_val):
    """Return a copy of fed_img with a header strip + GT (green) and pred (red) boxes."""
    from PIL import Image, ImageDraw

    pad = 46
    canvas = Image.new("RGB", (fed_img.width, fed_img.height + pad), (20, 20, 20))
    canvas.paste(fed_img, (0, pad))
    d = ImageDraw.Draw(canvas)
    iou_txt = "no parse" if iou_val is None else f"IoU {iou_val:.2f}"
    d.text((6, 4), f"{iou_txt}  green=GT red=pred", fill=(255, 255, 255))
    d.text((6, 24), caption[:90], fill=(180, 180, 180))

    def rect(px, color):
        if px is None:
            return
        x1, y1, x2, y2 = (px[0], px[1] + pad, px[2], px[3] + pad)
        d.rectangle([x1, y1, x2, y2], outline=color, width=3)

    rect(gt_px, (0, 230, 0))
    rect(pred_px, (255, 40, 40))
    return canvas


def run(backend, samples, max_side, out_dir):
    from PIL import Image

    fed_dir = out_dir / "fed"; ann_dir = out_dir / "annotated"
    fed_dir.mkdir(parents=True, exist_ok=True)
    ann_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for rank, s in enumerate(samples):
        img = Image.open(s.image_path).convert("RGB")
        fed = _resize_keep_aspect(img, max_side)  # exact pixels the backend will send
        text = backend.generate(s.image_path, s.caption)
        pred = parse_bbox(text)
        iou_val = iou(pred, s.bbox) if pred is not None else None

        gt_px = _box_px(s.bbox, fed.width, fed.height)
        pred_px = _box_px(pred, fed.width, fed.height) if pred is not None else None
        name = Path(s.image_path).stem
        tag = "xx" if iou_val is None else f"{int(round(iou_val * 100)):02d}"
        stem = f"{rank:02d}_{tag}_{name}"

        fed.save(fed_dir / f"{stem}.png")
        annotate(fed, gt_px, pred_px, s.caption, iou_val).save(ann_dir / f"{stem}.png")
        print(f"  [{rank:02d}] {_long_edge_px(s):4.0f}px GT  fed={fed.width}x{fed.height}"
              f"  IoU={'  - ' if iou_val is None else f'{iou_val:.2f}'}  {name}"
              f"  | raw={text.strip()[:40]!r}", flush=True)
        rows.append(iou_val)

    parsed = [v for v in rows if v is not None]
    hits = sum(1 for v in parsed if v >= 0.25)
    n = len(rows)
    print(f"\n[viz] n={n}  parsed={len(parsed)}/{n}  IoU@0.25={hits}/{n} ({hits/n:.0%})"
          f"  mean_iou(parsed)={(sum(parsed)/len(parsed) if parsed else 0):.3f}", flush=True)
    print(f"[viz] images -> {out_dir}", flush=True)


def build_backend(args):
    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    if args.backend == "jetson":
        from grounding.eval.backends import JetsonBackend
        d = args.remote_dir
        return JetsonBackend(f"{d}/{_REMOTE_MODELS[args.quant]}",
                             f"{d}/{_REMOTE_MMPROJ}",
                             max_side=args.max_side, startup_timeout_s=300)
    if args.backend == "hf":
        from grounding.eval.backends import HFBackend
        return HFBackend(args.model, max_side=args.max_side)
    raise SystemExit(f"backend {args.backend} not wired")


def _selfcheck():
    """Geometry asserts — no model, no Jetson (the lazy regression on the math)."""
    from PIL import Image
    # box-px round trip
    assert _box_px([0, 0, COORD_SCALE, COORD_SCALE], 640, 480) == [0, 0, 640, 480]
    assert _box_px([50, 50, 50, 50], 100, 100) == [50, 50, 50, 50] or COORD_SCALE != 100
    # annotate produces a taller canvas and doesn't crash on a None pred / None iou
    img = Image.new("RGB", (200, 100))
    out = annotate(img, [10, 10, 50, 50], None, "a caption", None)
    assert out.size == (200, 146), out.size
    # spread pick returns n, smallest first
    class S:  # minimal sample stub
        def __init__(s, side): s.bbox = [0, 0, side, side]; s.img_w = 100; s.img_h = 100
    pool = [S(s) for s in (5, 1, 9, 3, 7)]
    got = pick_spread(pool, 3)
    assert [_long_edge_px(x) for x in got] == [1, 5, 9], [_long_edge_px(x) for x in got]
    print("visualize self-check passed")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--selfcheck", action="store_true")
    p.add_argument("--backend", default="jetson", choices=["jetson", "hf"])
    p.add_argument("--quant", default="q8_0", choices=["q8_0", "f16"])
    p.add_argument("--remote-dir", default="/home/jfdg/grounding")
    p.add_argument("--model", default="./experiments/runs/v2/phase3-refdrone-1024",
                   help="HF checkpoint (hf backend only)")
    p.add_argument("--split", default="val")
    p.add_argument("--max-side", type=int, default=1920,
                   help="long-edge resize; native VisDrone is <=1920 so 1920 ~= whole frame")
    p.add_argument("--n", type=int, default=12)
    p.add_argument("--out", default="results/2026-06-30-whole-frame-resolution/out")
    args = p.parse_args()

    if args.selfcheck:
        _selfcheck()
        return

    from grounding.data.refdrone import load_refdrone
    samples = pick_spread(load_refdrone(args.split), args.n)
    out_dir = Path(args.out) / f"max_side_{args.max_side}"
    print(f"[viz] {len(samples)} samples (size-spread) | {args.backend} "
          f"{args.quant if args.backend=='jetson' else ''} max_side={args.max_side}",
          flush=True)

    backend = build_backend(args)
    try:
        run(backend, samples, args.max_side, out_dir)
    finally:
        close = getattr(backend, "close", None)
        if callable(close):
            close()


if __name__ == "__main__":
    main()
