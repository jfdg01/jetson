"""Jetson deploy + dual-path latency/accuracy bench for one bake-off arm.

Pushes an arm's GGUF (+ mmproj) to the Jetson, serves it via the stack-native
`llama-server` (pinned llama.cpp 57fe1f0, CUDA sm_87, ngl=99), and scores it over
RefDrone-val on BOTH deployed paths the README compares (README "Method" step 4):

  whole-frame 1024  — cold-acquire path; the incumbent's 63.1% WF / 4400 ms row.
  ROI re-anchor     — crop M=2.0 @512 around the prior; the deployed 85.2% / ~2000 ms row.

Unlike `harness.evaluate` / `roi.evaluate_roi` (which call `backend.generate`), this
loops on `generate_stats` so IoU and the separated prefill/decode/wall timings come
from the SAME pass — one serve, both numbers. Fills the Results-table shape:
parse / IoU@0.25 / mean IoU / center_std / prefill(tok,ms) / decode(tok,ms) / wall.

  source .venv-ft/bin/activate
  python experiments/2026-06-30-vlm-backbone-bakeoff/jetson_bench.py \
      --arm-label qwen2.5-vl-3b \
      --gguf   .../runs/qwen2.5-vl-3b/lr0.0002/gguf/lr0.0002-q8_0.gguf \
      --mmproj .../runs/qwen2.5-vl-3b/lr0.0002/gguf/mmproj-lr0.0002-f16.gguf

ponytail: single-file driver, no new abstraction — the arm loop is a for-loop in bash.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))  # repo root

from PIL import Image

from grounding import contract
from grounding.data.refdrone import load_refdrone
from grounding.deploy.serve import push
from grounding.eval.backends import JetsonBackend
from grounding.roi import crop_resize, map_to_full, roi_window


def _median(xs):
    return round(statistics.median(xs)) if xs else None


def _run_path(backend, samples, *, roi_margin, roi_res, progress_every):
    """One scoring pass. roi_margin=None -> whole-frame; else crop each sample first."""
    parsed = gate_hits = 0
    total_iou = 0.0
    pred_boxes = []
    prompt_n, prompt_ms, pred_n_toks, pred_ms, wall_ms = [], [], [], [], []

    # ROI feeds a pre-resized crop; stop the backend re-resizing it (mirrors evaluate_roi).
    saved_side = backend.max_side
    if roi_margin is not None:
        backend.max_side = 10 ** 9

    try:
        for i, s in enumerate(samples):
            stats: dict = {}
            if roi_margin is None:
                text = backend.generate_stats(s.image_path, s.caption, stats)
                box = contract.parse_bbox(text)
                full = box
            else:
                img = Image.open(s.image_path).convert("RGB")
                win = roi_window(s.bbox, s.img_w, s.img_h, roi_margin)
                crop = crop_resize(img, win, roi_res)
                tmp = None
                try:
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                        crop.save(f.name)
                        tmp = f.name
                    text = backend.generate_stats(tmp, s.caption, stats)
                finally:
                    if tmp:
                        os.unlink(tmp)
                box = contract.parse_bbox(text)
                full = map_to_full(box, win, s.img_w, s.img_h) if box is not None else None

            if stats.get("prompt_n") is not None:
                prompt_n.append(stats["prompt_n"]); prompt_ms.append(stats["prompt_ms"])
            if stats.get("predicted_n") is not None:
                pred_n_toks.append(stats["predicted_n"]); pred_ms.append(stats["predicted_ms"])
            if stats.get("wall_ms") is not None:
                wall_ms.append(stats["wall_ms"])

            if full is not None:
                parsed += 1
                pred_boxes.append(full)
                v = contract.iou(full, s.bbox)
                total_iou += v
                if v >= contract.IOU_GATE_THRESHOLD:
                    gate_hits += 1
            if progress_every and (i + 1) % progress_every == 0:
                print(f"  [{i+1}/{len(samples)}] parsed={parsed} gate_hits={gate_hits} "
                      f"wall_med={_median(wall_ms)}ms", flush=True)
    finally:
        backend.max_side = saved_side

    n = len(samples)
    return {
        "n": n,
        "parse_rate": round(parsed / n, 4) if n else 0.0,
        "iou@0.25": round(gate_hits / n, 4) if n else 0.0,
        "mean_iou": round(total_iou / parsed, 4) if parsed else 0.0,
        "center_std": round(contract.center_std(pred_boxes), 2),
        "prefill_tok": _median(prompt_n), "prefill_ms": _median(prompt_ms),
        "decode_tok": _median(pred_n_toks), "decode_ms": _median(pred_ms),
        "wall_ms": _median(wall_ms),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm-label", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--mmproj", required=True)
    ap.add_argument("--split", default="val")
    ap.add_argument("--limit", type=int, default=0, help="0 = full split")
    ap.add_argument("--max-side", type=int, default=1024)
    ap.add_argument("--n-ctx", type=int, default=4096)
    ap.add_argument("--roi-margin", type=float, default=2.0)
    ap.add_argument("--roi-res", type=int, default=512)
    ap.add_argument("--paths", default="wf,roi", help="comma list: wf,roi")
    ap.add_argument("--out", default=None, help="JSON results path (default: raw/<label>-jetson.json)")
    args = ap.parse_args()

    samples = load_refdrone(args.split, max_samples=args.limit)
    print(f"[bench] {args.arm_label}: RefDrone '{args.split}' n={len(samples)} "
          f"max_side={args.max_side} n_ctx={args.n_ctx}", flush=True)

    remote_gguf = push(args.gguf)
    remote_mmproj = push(args.mmproj)
    backend = JetsonBackend(remote_gguf, remote_mmproj, n_ctx=args.n_ctx,
                            max_side=args.max_side, startup_timeout_s=300)
    print(f"[bench] served {os.path.basename(args.gguf)} on Jetson (ngl=99)", flush=True)

    results = {"arm": args.arm_label, "gguf": os.path.basename(args.gguf),
               "max_side": args.max_side, "n_ctx": args.n_ctx}
    prog = max(1, len(samples) // 10)
    try:
        wanted = [p.strip() for p in args.paths.split(",")]
        if "wf" in wanted:
            print("[bench] === whole-frame path ===", flush=True)
            results["whole_frame"] = _run_path(backend, samples, roi_margin=None,
                                               roi_res=None, progress_every=prog)
            print("[bench] WF:", json.dumps(results["whole_frame"]), flush=True)
        if "roi" in wanted:
            print(f"[bench] === ROI re-anchor path (M={args.roi_margin} @{args.roi_res}) ===",
                  flush=True)
            results["roi"] = _run_path(backend, samples, roi_margin=args.roi_margin,
                                       roi_res=args.roi_res, progress_every=prog)
            results["roi"]["margin"] = args.roi_margin
            results["roi"]["res"] = args.roi_res
            print("[bench] ROI:", json.dumps(results["roi"]), flush=True)
    finally:
        backend.close()

    out = args.out or f"experiments/2026-06-30-vlm-backbone-bakeoff/raw/{args.arm_label}-jetson.json"
    Path(out).write_text(json.dumps(results, indent=2))
    print(f"[bench] wrote {out}", flush=True)


if __name__ == "__main__":
    main()
