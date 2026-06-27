"""ROI-crop anchor — cut prefill / beat the resolution ceiling (Part II/III lever).

Inference-time only, **no retrain** (sibling of the terse-output experiment, which
attacks decode by re-LoRA). Feed the VLM a crop around the tracker's box prior
instead of the full 640×480 frame:

* fewer pixels → fewer Qwen2-VL vision tokens → prefill collapses (~area model);
* feeding a *tight* crop **upscaled** to the budget is effective super-resolution on
  the target, which fights Part II binding constraint #2 (tiny aerial objects 5–30 px
  → 2–11 px after the 512 resize) — so a crop may *buy accuracy*, not just latency.

Both effects ride one knob: the crop's output resolution. Coords stay box-invariant
— the model returns 0–COORD_SCALE *within the crop it is given*; we map back to
full-image normalized coords with the crop window only (the whole-crop resize is
metric-safe exactly like the whole-image resize in `resolution.py`).

There is no tracker prior in single-frame RefDrone, so the prior is simulated by
inflating the GT box by margin M and squaring it. **M → ∞ recovers the full frame**
(the control point, free in the same sweep). Optional perturbation (shift + scale of
the prior) proxies real tracker drift.

Usage:
  source .venv-ft/bin/activate
  python -m grounding.roi --model ./runs/v2/phase3-refdrone-1024 \
      --split val --margins 1.5,2,3,5,inf --out-res native,384,512 --n 150

Self-check (no model load):  python -m grounding.roi --selfcheck
"""

from __future__ import annotations

import argparse
import math
import random
from dataclasses import asdict
from typing import List, Optional, Sequence, Tuple

from grounding import manifest
from grounding.contract import (COORD_SCALE, IOU_GATE_THRESHOLD, center_std, iou,
                                normalize_bbox, parse_bbox)
from grounding.data.schema import GroundingSample
from grounding.eval.harness import EvalReport

Window = Tuple[int, int, int, int]  # pixel XYXY crop window in the ORIGINAL image


def roi_window(bbox_norm: Sequence[int], img_w: int, img_h: int, margin: float,
               *, shift: float = 0.0, scale: float = 1.0, min_side: float = 0.0,
               rng: Optional[random.Random] = None) -> Window:
    """Square, inflated, clamped crop window (pixel XYXY) around a normalized box.

    `bbox_norm` is [x1,y1,x2,y2] in 0–COORD_SCALE of the original image. The square
    side is `margin · max(box_w, box_h)`; `margin=inf` (or any value covering the
    frame) returns the whole frame — the full-frame control point. Perturbation:
    `scale` multiplies the box size before inflation and `shift` offsets the center
    by `shift · box_size` in a random direction (proxy for a stale/drifted prior).

    `min_side` floors the square side (pixels). Without it, a re-anchor loop crops
    `margin · box` every pass, so a box that shrinks (small/drifted prediction) drives
    the next crop smaller, which zooms in past all context and shrinks again — a
    death spiral (observed: box 21px → crop 86px → fed at 64 tokens → garbage box).
    The floor makes the crop size constant once `margin · box < min_side`, breaking
    that positive feedback. Default 0 keeps the single-frame eval sweep unchanged.
    """
    x1, y1, x2, y2 = (c / COORD_SCALE for c in bbox_norm)
    bw = max(1.0, (x2 - x1) * img_w) * scale
    bh = max(1.0, (y2 - y1) * img_h) * scale
    cx = (x1 + x2) / 2 * img_w
    cy = (y1 + y2) / 2 * img_h
    if shift:
        r = rng or random
        ang = r.uniform(0, 2 * math.pi)
        d = shift * max(bw, bh)
        cx += d * math.cos(ang)
        cy += d * math.sin(ang)

    if not math.isfinite(margin):
        return (0, 0, img_w, img_h)
    half = max(margin * max(bw, bh), min_side) / 2.0
    x0 = int(round(cx - half)); y0 = int(round(cy - half))
    x3 = int(round(cx + half)); y3 = int(round(cy + half))
    # Clamp to frame (edges go non-square at the border — accepted, realistic).
    x0 = max(0, min(x0, img_w - 1)); y0 = max(0, min(y0, img_h - 1))
    x3 = max(x0 + 1, min(x3, img_w)); y3 = max(y0 + 1, min(y3, img_h))
    return (x0, y0, x3, y3)


def map_to_full(pred_norm: Sequence[int], win: Window,
                img_w: int, img_h: int) -> List[int]:
    """Map a pred box (0–COORD_SCALE within the crop) → 0–COORD_SCALE in full image."""
    x0, y0, x1, y1 = win
    rw = x1 - x0; rh = y1 - y0
    px = [x0 + pred_norm[0] / COORD_SCALE * rw,
          y0 + pred_norm[1] / COORD_SCALE * rh,
          x0 + pred_norm[2] / COORD_SCALE * rw,
          y0 + pred_norm[3] / COORD_SCALE * rh]
    return normalize_bbox(px, img_w, img_h)


def crop_resize(img, win: Window, out_res: Optional[int], *, upscale: bool = True):
    """Crop `win` and resize its long edge to `out_res` (up OR down).

    `out_res=None` → native (no resize). Unlike `resolution._resize_keep_aspect`
    (downscale-only), this **upscales** a small crop to the budget — that upscale is
    the super-resolution intervention RQ2 is about (keep `upscale=True` for the
    RefDrone sweep). With `upscale=False` the long edge is *capped* at `out_res` but
    never grown: the deploy re-anchor path uses this so the fed crop can't end up
    with MORE pixels (vision tokens) than the letterboxed full frame would — a square
    OUT_RES upscale of a small crop was actually making re-anchor prefill *slower*
    than the full-frame acquire.
    """
    from PIL import Image

    crop = img.crop(win)
    if not out_res:
        return crop
    w, h = crop.size
    s = out_res / max(w, h)
    if not upscale and s >= 1.0:
        return crop  # downscale-only: a crop already ≤ out_res is fed native
    return crop.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)


def evaluate_roi(backend, samples: Sequence[GroundingSample], margin: float,
                 out_res: Optional[int], *, progress_every: int = 0,
                 shift: float = 0.0, scale: float = 1.0,
                 seed: int = 0) -> EvalReport:
    """Crop-around-prior variant of `harness.evaluate`.

    Per sample: crop around the (inflated/perturbed) GT prior, resize to `out_res`,
    feed the backend the pre-resized crop (its own resize is disabled), parse, map
    the prediction back to full-image coords, score with the contract metrics. The
    crop is written to a temp PNG because backends take an image *path*.
    """
    import os
    import tempfile

    from PIL import Image

    saved = getattr(backend, "max_side", None)
    if saved is not None:
        backend.max_side = 10 ** 9  # crop is pre-resized; stop the backend re-resizing
    rng = random.Random(seed)

    n = len(samples)
    parsed = gate_hits = 0
    total_iou = 0.0
    pred_boxes: List[List[int]] = []
    try:
        for i, s in enumerate(samples):
            img = Image.open(s.image_path).convert("RGB")
            win = roi_window(s.bbox, s.img_w, s.img_h, margin,
                             shift=shift, scale=scale, rng=rng)
            crop = crop_resize(img, win, out_res)
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    crop.save(tmp.name)
                    tmp_path = tmp.name
                text = backend.generate(tmp_path, s.caption)
            finally:
                if tmp_path:
                    os.unlink(tmp_path)
            box = parse_bbox(text)
            if box is not None:
                parsed += 1
                full = map_to_full(box, win, s.img_w, s.img_h)
                pred_boxes.append(full)
                v = iou(full, s.bbox)
                total_iou += v
                if v >= IOU_GATE_THRESHOLD:
                    gate_hits += 1
            if progress_every and (i + 1) % progress_every == 0:
                print(f"  [roi M={margin} r={out_res}] {i+1}/{n}  "
                      f"parsed={parsed}  gate_hits={gate_hits}", flush=True)
    finally:
        if saved is not None:
            backend.max_side = saved

    return EvalReport(
        backend=getattr(backend, "name", "?"),
        n=n,
        parse_rate=parsed / n if n else 0.0,
        iou_gate_pass_rate=gate_hits / n if n else 0.0,
        mean_iou=total_iou / parsed if parsed else 0.0,
        center_std=center_std(pred_boxes),
    )


def _parse_margins(s: str) -> List[float]:
    return [float("inf") if t.strip().lower() in ("inf", "full") else float(t)
            for t in s.split(",") if t.strip()]


def _parse_resolutions(s: str) -> List[Optional[int]]:
    return [None if t.strip().lower() in ("native", "none", "0") else int(t)
            for t in s.split(",") if t.strip()]


def run_grid(model: str, split: str,
             combos: List[Tuple[float, Optional[int]]], *, n: int = 0,
             device: str = "cuda", dtype: str = "bfloat16",
             shift: float = 0.0, scale: float = 1.0, note: str = "") -> List[dict]:
    """Evaluate a list of (margin, out_res) combos on one model; manifest per combo.

    The model is loaded **once** and reused across combos (weights are crop-
    independent). `combos` is explicit so a survivor re-run hits the same path as the
    broad grid — the CLI builds the cross product, an orchestrator can pass a subset.
    """
    from grounding.data.refdrone import load_refdrone
    from grounding.eval.backends import HFBackend

    print(f"[roi] loading RefDrone '{split}' well-posed (n={n or 'all'})...", flush=True)
    samples = load_refdrone(split, max_samples=n)
    print(f"[roi] {len(samples)} samples; loading {model} (HF, {dtype})...", flush=True)
    backend = HFBackend(model, device=device, dtype=dtype)

    rows: List[dict] = []
    try:
        for margin, res in combos:
            tag = f"M={'inf' if math.isinf(margin) else margin} out_res={res or 'native'}"
            print(f"[roi] === {tag} ===", flush=True)
            rep = evaluate_roi(backend, samples, margin, res,
                               progress_every=max(1, len(samples) // 10),
                               shift=shift, scale=scale)
            print(f"[roi] {tag}  parse={rep.parse_rate:.1%}  "
                  f"iou@0.25={rep.iou_gate_pass_rate:.1%}  "
                  f"mean_iou={rep.mean_iou:.3f}  center_std={rep.center_std:.1f}",
                  flush=True)
            results = asdict(rep)
            cfg = {
                "phase": "II/III", "experiment": "roi-crop-anchor",
                "backend": "hf", "model": model, "dataset": "refdrone",
                "split": split, "n": len(samples),
                "roi_margin": "inf" if math.isinf(margin) else margin,
                "roi_out_res": res or "native",
                "perturb_shift": shift, "perturb_scale": scale,
                "device": device, "dtype": dtype, "note": note,
            }
            m = manifest.capture("eval", cfg)
            run_dir = manifest.write(m, results=results)
            rows.append({"margin": margin, "out_res": res, **results,
                         "run_dir": str(run_dir)})
    finally:
        close = getattr(backend, "close", None)
        if callable(close):
            close()
    return rows


def cross(margins: List[float],
          resolutions: List[Optional[int]]) -> List[Tuple[float, Optional[int]]]:
    """Full (margin × out_res) cross product, in sweep order."""
    return [(m, r) for m in margins for r in resolutions]


def _print_table(rows: List[dict]) -> None:
    print("\n[roi] (margin × out_res) — RefDrone well-posed val")
    print(f"{'M':>5} | {'out_res':>7} | {'parse':>6} | {'IoU@0.25':>8} | "
          f"{'mean_iou':>8} | {'center_std':>10}")
    print("-" * 64)
    for r in rows:
        M = "inf" if math.isinf(r["margin"]) else f"{r['margin']:g}"
        res = r["out_res"] or "native"
        print(f"{M:>5} | {str(res):>7} | {r['parse_rate']:>6.1%} | "
              f"{r['iou_gate_pass_rate']:>8.1%} | {r['mean_iou']:>8.3f} | "
              f"{r['center_std']:>10.1f}")


def _selfcheck() -> None:
    """Round-trip + window asserts — no model load (the lazy crop-math regression)."""
    # M→inf is the full frame.
    assert roi_window([400, 400, 600, 600], 640, 480, float("inf")) == (0, 0, 640, 480)
    # A predicted box equal to the GT (expressed in crop coords) must map back to ~GT.
    # Coords expressed as fractions of COORD_SCALE so the check is scale-agnostic
    # (the shared contract's COORD_SCALE may differ between sibling experiments).
    S = COORD_SCALE
    gt = [round(0.30 * S), round(0.20 * S), round(0.40 * S), round(0.28 * S)]
    for M in (1.5, 2.0, 3.0, 5.0):
        win = roi_window(gt, 640, 480, M)
        x0, y0, x1, y1 = win
        # GT in pixels, then expressed in crop-normalized coords:
        gpx = [gt[0] / COORD_SCALE * 640, gt[1] / COORD_SCALE * 480,
               gt[2] / COORD_SCALE * 640, gt[3] / COORD_SCALE * 480]
        pred_in_crop = [round((gpx[0] - x0) / (x1 - x0) * COORD_SCALE),
                        round((gpx[1] - y0) / (y1 - y0) * COORD_SCALE),
                        round((gpx[2] - x0) / (x1 - x0) * COORD_SCALE),
                        round((gpx[3] - y0) / (y1 - y0) * COORD_SCALE)]
        back = map_to_full(pred_in_crop, win, 640, 480)
        assert iou(back, gt) > 0.97, (M, back, gt, iou(back, gt))
    # Tight crop is upscaled (super-resolution): a 40-px crop fed at 512 grows.
    from PIL import Image
    img = Image.new("RGB", (640, 480))
    win = roi_window(gt, 640, 480, 1.5)
    assert max(crop_resize(img, win, 512).size) == 512
    assert crop_resize(img, win, None).size == (win[2] - win[0], win[3] - win[1])
    # A drifted prior shifts the window center away from the GT center.
    base = roi_window(gt, 640, 480, 2.0)
    drift = roi_window(gt, 640, 480, 2.0, shift=1.5, rng=random.Random(1))
    assert base != drift
    # min_side floors the crop: a tiny centered box that would crop small gets the floor.
    c = round(0.5 * S)
    tiny = [c - round(0.005 * S), c - round(0.005 * S),
            c + round(0.005 * S), c + round(0.005 * S)]  # ~1% box, crops tiny at margin 4
    uf = roi_window(tiny, 640, 480, 4.0)
    assert max(uf[2] - uf[0], uf[3] - uf[1]) < 256  # unfloored: collapses small
    fl = roi_window(tiny, 640, 480, 4.0, min_side=256)
    assert max(fl[2] - fl[0], fl[3] - fl[1]) >= 256, fl  # floored crop is ≥ min_side
    print("roi self-check passed")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--selfcheck", action="store_true", help="run crop-math asserts, exit")
    p.add_argument("--model", default="./runs/v2/phase3-refdrone-1024",
                   help="HF id or checkpoint path (default = Phase-3 merged deploy)")
    p.add_argument("--split", default="val")
    p.add_argument("--margins", default="1.5,2,3,5,inf",
                   help="comma-separated inflation margins; 'inf' = full frame")
    p.add_argument("--out-res", default="native,384,512",
                   help="comma-separated crop long-edge sizes; 'native' = no resize")
    p.add_argument("--n", type=int, default=0, help="cap on samples (0 = full)")
    p.add_argument("--shift", type=float, default=0.0,
                   help="perturb: offset prior center by shift·box_size (drift test)")
    p.add_argument("--scale", type=float, default=1.0,
                   help="perturb: scale the prior box size before inflation")
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", default="bfloat16")
    p.add_argument("--note", default="")
    args = p.parse_args()

    if args.selfcheck:
        _selfcheck()
        return

    combos = cross(_parse_margins(args.margins), _parse_resolutions(args.out_res))
    rows = run_grid(args.model, args.split, combos, n=args.n,
                    device=args.device, dtype=args.dtype,
                    shift=args.shift, scale=args.scale, note=args.note)
    _print_table(rows)


if __name__ == "__main__":
    main()
