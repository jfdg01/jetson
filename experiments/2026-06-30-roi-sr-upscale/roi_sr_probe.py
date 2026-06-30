"""ROI super-resolution probe — does a learned upscaler beat classical interpolation
for grounding tiny aerial targets, at equal fed resolution?

Branch `test/whole-frame-resolution`. The ROI-crop lever already upscales a crop around
the prior (currently LANCZOS) to fight binding-constraint #2 (tiny objects 5-30 px). This
asks: replace that interpolation with **Swin2SR** (learned, compressed-JPEG SR — matches
VisDrone's degradation) — do we get an *actual IoU lift*, or is classical already maxed?

Clean ablation, one variable (the upscale method):
  * Crop a fixed SIDE x SIDE (default 400) square centred on GT (ORACLE prior — removes
    ROI-placement error; deployment uses a *predicted* prior, so absolute IoU here is an
    upper bound, the *ranking* of methods is what transfers).
  * Keep only samples whose GT fits the crop (long edge <= SIDE*FIT_FRAC) — the tiny-object
    regime SR is supposed to help; a box bigger than the crop can't be localized from it.
  * Upscale the crop to FEED (default 1024) four ways and feed each to the same VLM:
      native   - fed at native crop size (no upscale): "does upscaling even help?" control
      bicubic  - classical
      lanczos  - classical (the 2 "best classical" arms)
      swin2sr  - learned (x4 then resized to FEED)
  * CRITICAL: Qwen2-VL's processor silently downscales >max_pixels inputs, which would wash
    out the comparison. We raise max_pixels to FEED^2 so the model ingests exactly the pixels
    each method produced — the upscaler is the only difference.

Coords are box-invariant: the model returns 0-COORD_SCALE within the crop; `roi.map_to_full`
maps back to full-image normalized coords (the crop window is all that's needed), then IoU
vs the original GT — same metric-safety the ROI lever relies on.

Runs on the dev CUDA GPU via HFBackend (bf16 fidelity reference), decoupled from the Jetson.
Use the terse100eos checkpoint: it emits 0-100 coords matching the current contract (the
older phase3-refdrone-1024 emits 0-1000 -> garbage IoU).

Usage:
  source .venv-ft/bin/activate
  python experiments/2026-06-30-whole-frame-resolution/roi_sr_probe.py \
      --model ./runners/runs/v2/phase3-terse100eos-1024 --n 150

Self-check (no model, no GPU):
  python experiments/2026-06-30-whole-frame-resolution/roi_sr_probe.py --selfcheck
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # repo root on path

from grounding.contract import COORD_SCALE, iou, parse_bbox
from grounding.roi import map_to_full

SR_ID = "caidas/swin2SR-realworld-sr-x4-64-bsrgan-psnr"
FIT_FRAC = 0.75   # keep samples whose GT long edge <= SIDE*FIT_FRAC (object + context)
SR_SCALE = 4      # Swin2SR realworld is x4
METHODS = ["native", "bicubic", "lanczos", "swin2sr"]

CSV_FIELDS = ["idx", "name", "caption", "method", "crop_w", "crop_h", "box_px",
              "feed", "parsed", "iou", "gate", "sr_ms", "vlm_ms", "raw"]


def _box_long_edge_px(s):
    """GT box long edge in original pixels."""
    x1, y1, x2, y2 = (c / COORD_SCALE for c in s.bbox)
    return max((x2 - x1) * s.img_w, (y2 - y1) * s.img_h)


def fixed_window(bbox_norm, img_w, img_h, side):
    """Square `side`-px window centred on the GT box, clamped inside the image.

    Returns pixel XYXY. If the image is smaller than `side` on an axis, that axis
    spans the whole image (degenerate; our val frames are all >= 540 px so it never
    triggers in practice, but the clamp keeps it safe)."""
    x1, y1, x2, y2 = (c / COORD_SCALE for c in bbox_norm)
    cx = (x1 + x2) / 2 * img_w
    cy = (y1 + y2) / 2 * img_h
    half = side / 2
    if img_w <= side:
        x0 = 0
    else:
        x0 = int(round(min(max(cx - half, 0), img_w - side)))
    if img_h <= side:
        y0 = 0
    else:
        y0 = int(round(min(max(cy - half, 0), img_h - side)))
    x3 = min(img_w, x0 + side)
    y3 = min(img_h, y0 + side)
    return (x0, y0, x3, y3)


def upscale_classical(crop, method, feed):
    """Resize the crop's long edge to `feed` with a classical filter (keeps aspect)."""
    from PIL import Image
    flt = {"bicubic": Image.BICUBIC, "lanczos": Image.LANCZOS}[method]
    w, h = crop.size
    s = feed / max(w, h)
    return crop.resize((max(1, round(w * s)), max(1, round(h * s))), flt)


class Swin2SR:
    """Lazy Swin2SR x4 wrapper. Loads weights once; upscales a PIL crop x4."""

    def __init__(self, device="cuda"):
        import torch
        from transformers import AutoImageProcessor, Swin2SRForImageSuperResolution
        self.device = device
        self.proc = AutoImageProcessor.from_pretrained(SR_ID)
        self.model = Swin2SRForImageSuperResolution.from_pretrained(SR_ID).to(device).eval()
        self._torch = torch

    def up(self, crop):
        import numpy as np
        from PIL import Image
        torch = self._torch
        inp = self.proc(crop, return_tensors="pt").to(self.device)
        with torch.no_grad():
            out = self.model(**inp)
        rec = out.reconstruction.data.squeeze(0).float().cpu().clamp_(0, 1).numpy()  # [3,H,W]
        rec = np.moveaxis(rec, 0, -1)  # HWC
        img = Image.fromarray((rec * 255).round().astype("uint8"))
        # Swin pads to the window multiple; trim to exactly SR_SCALE x the input.
        w, h = crop.size
        return img.crop((0, 0, w * SR_SCALE, h * SR_SCALE))


def make_fed(crop, method, feed, sr):
    """Produce the exact image fed to the VLM for `method`, + the SR time (ms)."""
    from PIL import Image
    if method == "native":
        return crop, 0.0
    if method in ("bicubic", "lanczos"):
        return upscale_classical(crop, method, feed), 0.0
    if method == "swin2sr":
        t0 = time.time()
        big = sr.up(crop)                       # x4 (native crop * 4)
        sr_ms = (time.time() - t0) * 1000
        if max(big.size) != feed:               # land on the common feed resolution
            s = feed / max(big.size)
            big = big.resize((round(big.width * s), round(big.height * s)), Image.LANCZOS)
        return big, sr_ms
    raise ValueError(method)


def run(backend, sr, samples, side, feed, out_dir):
    import os
    import tempfile
    from PIL import Image

    rows = []
    n = len(samples)
    for idx, s in enumerate(samples):
        img = Image.open(s.image_path).convert("RGB")
        win = fixed_window(s.bbox, s.img_w, s.img_h, side)
        crop = img.crop(win)
        name = Path(s.image_path).stem
        box_px = _box_long_edge_px(s)
        for method in METHODS:
            fed, sr_ms = make_fed(crop, method, feed, sr)
            tmp = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    fed.save(f.name); tmp = f.name
                t0 = time.time()
                text = backend.generate(tmp, s.caption)
                vlm_ms = (time.time() - t0) * 1000
            finally:
                if tmp:
                    os.unlink(tmp)
            pred = parse_bbox(text)
            iou_val = None
            if pred is not None:
                iou_val = iou(map_to_full(pred, win, s.img_w, s.img_h), s.bbox)
            rows.append({
                "idx": idx, "name": name, "caption": s.caption, "method": method,
                "crop_w": crop.width, "crop_h": crop.height, "box_px": round(box_px, 1),
                "feed": feed, "parsed": int(pred is not None),
                "iou": "" if iou_val is None else round(iou_val, 4),
                "gate": int(iou_val is not None and iou_val >= 0.25),
                "sr_ms": round(sr_ms, 1), "vlm_ms": round(vlm_ms, 1),
                "raw": text.strip()[:60],
            })
        if (idx + 1) % max(1, n // 20) == 0:
            print(f"  {idx+1}/{n}", flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "sr_per_sample.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader(); w.writerows(rows)
    print(f"\n[sr] {len(rows)} rows -> {csv_path}", flush=True)
    _summary(rows, out_dir, side, feed, len(samples))
    return rows


def _summary(rows, out_dir, side, feed, n_samples):
    """Per-method table: parse%, IoU@0.25, mean IoU(parsed), median SR+VLM ms."""
    def med(xs):
        xs = sorted(xs)
        if not xs:
            return float("nan")
        m = len(xs) // 2
        return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2

    lines = [f"# ROI super-resolution probe\n",
             f"crop {side}x{side} oracle · feed {feed} · n={n_samples} samples "
             f"(GT fits crop, long edge <= {side*FIT_FRAC:.0f}px)\n",
             "| method | parse% | IoU@0.25 | mean IoU | med SR ms | med VLM ms |",
             "|---|---|---|---|---|---|"]
    print("\n[sr] === per-method (crop {}, feed {}, n={}) ===".format(side, feed, n_samples))
    print(f"{'method':>9} | {'parse%':>6} | {'IoU@.25':>7} | {'meanIoU':>7} | "
          f"{'SR ms':>6} | {'VLM ms':>6}")
    for method in METHODS:
        rs = [r for r in rows if r["method"] == method]
        parsed = [r for r in rs if r["parsed"]]
        ious = [r["iou"] for r in parsed if r["iou"] != ""]
        hits = sum(1 for r in rs if r["gate"])
        parse_pct = 100 * len(parsed) / len(rs) if rs else 0
        iou25 = 100 * hits / len(rs) if rs else 0
        mean_iou = sum(ious) / len(ious) if ious else float("nan")
        sr_ms = med([r["sr_ms"] for r in rs])
        vlm_ms = med([r["vlm_ms"] for r in rs])
        print(f"{method:>9} | {parse_pct:>5.1f}% | {iou25:>6.1f}% | {mean_iou:>7.3f} | "
              f"{sr_ms:>6.0f} | {vlm_ms:>6.0f}")
        lines.append(f"| {method} | {parse_pct:.1f}% | {iou25:.1f}% | {mean_iou:.3f} | "
                     f"{sr_ms:.0f} | {vlm_ms:.0f} |")
    (out_dir / "sr_summary.md").write_text("\n".join(lines) + "\n")
    print(f"[sr] summary -> {out_dir/'sr_summary.md'}", flush=True)


def _selfcheck():
    """Geometry + arm asserts — no model, no GPU."""
    from PIL import Image

    class S:
        def __init__(s, bbox, w=1360, h=765):
            s.bbox = bbox; s.img_w = w; s.img_h = h
            s.image_path = "x"; s.caption = "c"

    # window is SIDE x SIDE and centred when interior
    s = S([45, 45, 55, 55])  # box at centre of a 1360x765 frame
    win = fixed_window(s.bbox, s.img_w, s.img_h, 400)
    assert (win[2] - win[0], win[3] - win[1]) == (400, 400), win
    cx = (win[0] + win[2]) / 2
    assert abs(cx - 0.5 * 1360) < 1.5, cx  # centred on the box centre

    # edge box: window clamps inside the image, still 400x400
    we = fixed_window([1, 1, 3, 3], 1360, 765, 400)
    assert we[0] == 0 and we[1] == 0 and (we[2], we[3]) == (400, 400), we

    # map_to_full round-trip: GT expressed in crop coords maps back to ~GT
    win = fixed_window(s.bbox, 1360, 765, 400)
    x0, y0, x1, y1 = win
    gpx = [s.bbox[0] / COORD_SCALE * 1360, s.bbox[1] / COORD_SCALE * 765,
           s.bbox[2] / COORD_SCALE * 1360, s.bbox[3] / COORD_SCALE * 765]
    pred_in_crop = [round((gpx[0] - x0) / (x1 - x0) * COORD_SCALE),
                    round((gpx[1] - y0) / (y1 - y0) * COORD_SCALE),
                    round((gpx[2] - x0) / (x1 - x0) * COORD_SCALE),
                    round((gpx[3] - y0) / (y1 - y0) * COORD_SCALE)]
    assert iou(map_to_full(pred_in_crop, win, 1360, 765), s.bbox) > 0.97

    # fit filter math
    assert abs(_box_long_edge_px(S([40, 40, 50, 45])) - max(0.10 * 1360, 0.05 * 765)) < 1e-6

    # classical upscale lands long edge on feed, keeps aspect
    up = upscale_classical(Image.new("RGB", (400, 400)), "lanczos", 1024)
    assert max(up.size) == 1024 and up.size == (1024, 1024), up.size
    up2 = upscale_classical(Image.new("RGB", (400, 300)), "bicubic", 1024)
    assert max(up2.size) == 1024 and up2.size == (1024, 768), up2.size

    # native arm is a pass-through (sr=None never touched)
    fed, ms = make_fed(Image.new("RGB", (400, 400)), "native", 1024, None)
    assert fed.size == (400, 400) and ms == 0.0
    print("roi_sr_probe self-check passed")


def build_backend(model, device, feed):
    from grounding.eval.backends import HFBackend
    b = HFBackend(model, device=device, max_side=10 ** 9)  # crop pre-sized; no re-resize
    # Stop Qwen2-VL's processor from downscaling our upscaled inputs back to its default
    # ~1MP budget — that would wash out the whole comparison. Ingest exactly `feed`^2.
    ip = b.processor.image_processor
    ip.max_pixels = feed * feed
    if getattr(ip, "size", None) and isinstance(ip.size, dict):
        ip.size["longest_edge"] = feed * feed  # newer processors gate on size dict
    return b


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--selfcheck", action="store_true")
    p.add_argument("--model", default="./runners/runs/v2/phase3-terse100eos-1024",
                   help="HF checkpoint emitting 0-100 coords (NOT phase3-refdrone-1024)")
    p.add_argument("--split", default="val")
    p.add_argument("--side", type=int, default=400, help="crop square side (px)")
    p.add_argument("--feed", type=int, default=1024, help="common fed long-edge resolution")
    p.add_argument("--n", type=int, default=0, help="cap on FITTING samples (0 = all)")
    p.add_argument("--device", default="cuda")
    p.add_argument("--out", default=str(HERE / "sr_probe_out"))
    args = p.parse_args()

    if args.selfcheck:
        _selfcheck()
        return

    from grounding.data.refdrone import load_refdrone
    allsamp = load_refdrone(args.split)
    fit = [s for s in allsamp if _box_long_edge_px(s) <= args.side * FIT_FRAC]
    if args.n:
        fit = fit[:args.n]
    print(f"[sr] {len(fit)}/{len(allsamp)} samples fit a {args.side}px crop "
          f"(<= {args.side*FIT_FRAC:.0f}px); feed={args.feed}", flush=True)

    backend = build_backend(args.model, args.device, args.feed)
    print(f"[sr] loading Swin2SR ({SR_ID})...", flush=True)
    sr = Swin2SR(device=args.device)
    try:
        run(backend, sr, fit, args.side, args.feed, Path(args.out))
    finally:
        close = getattr(backend, "close", None)
        if callable(close):
            close()


if __name__ == "__main__":
    main()
