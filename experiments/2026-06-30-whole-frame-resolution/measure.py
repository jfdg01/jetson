"""Whole-frame resolution sweep — measure EVERYTHING, per sample, on the Jetson.

Branch `test/whole-frame-resolution`. Companion to `visualize.py` (the eyeball layer);
this is the numbers layer. For each `--max-side` arm it runs the deployed Q8_0 spine
over the RefDrone well-posed val set on the Orin Nano and records, per sample:

  accuracy : parsed?, IoU, IoU@0.25 gate hit
  geometry : original img WxH, GT box long-edge px (orig AND after resize), box area %
  cost     : fed WxH / megapixels, payload KB over the tunnel,
             prefill tokens + ms, decode tokens + ms, wall ms, transfer ms

The point is the accuracy-vs-latency tradeoff of feeding the whole frame: vision tokens
(=> prefill ms) scale ~with fed megapixels, so a bigger max_side buys detail on tiny
targets at a prefill cost this table makes explicit. Box size is logged because IoU is
expected to track the *post-resize* target size, not the arm alone.

Outputs (under <out>/):
  per_sample.csv   — one row per (max_side, sample); the raw measurement record
  summary.md       — per-arm medians + accuracy, the table for the writeup
plus one grounding manifest per arm (git sha + lock + config) for provenance.

Config is fixed at: Orin Nano, 15 W, Q8_0 + f16 mmproj, greedy, ctx 4096, ssh transfer
included in wall (the real deploy wall). Power mode is logged, not assumed — pass --note.

Usage:
  source .venv-ft/bin/activate
  python results/2026-06-30-whole-frame-resolution/measure.py \
      --sides 512,1024,1536,1920 --n 0        # 0 = full val set

Self-check (no model, no Jetson):
  python results/2026-06-30-whole-frame-resolution/measure.py --selfcheck
"""

from __future__ import annotations

import argparse
import csv
import statistics as st
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root on path

from grounding import manifest
from grounding.contract import COORD_SCALE, IOU_GATE_THRESHOLD, iou, parse_bbox

HERE = Path(__file__).resolve().parent

CSV_FIELDS = [
    "max_side", "idx", "name", "caption",
    "img_w", "img_h", "box_px_orig", "box_px_fed", "box_area_pct",
    "parsed", "iou", "gate",
    "fed_w", "fed_h", "fed_mpx", "payload_kb",
    "prompt_n", "prompt_ms", "predicted_n", "predicted_ms",
    "wall_ms", "transfer_ms", "raw",
]


def _box_long_edge_px(bbox, w, h):
    """GT box (0-COORD_SCALE) long edge in pixels of a w x h image."""
    bw = (bbox[2] - bbox[0]) / COORD_SCALE * w
    bh = (bbox[3] - bbox[1]) / COORD_SCALE * h
    return max(bw, bh)


def _box_area_pct(bbox):
    """GT box area as % of the frame (resolution-independent)."""
    return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) / (COORD_SCALE ** 2) * 100.0


def measure_sample(backend, s, max_side, idx):
    """One (sample, arm) measurement row as a dict over CSV_FIELDS."""
    stats: dict = {}
    text = backend.generate_stats(s.image_path, s.caption, stats)
    pred = parse_bbox(text)
    iou_val = iou(pred, s.bbox) if pred is not None else None
    fed_w = stats.get("fed_w") or 0
    fed_h = stats.get("fed_h") or 0
    fed_long = max(fed_w, fed_h) or max(s.img_w, s.img_h)
    box_orig = _box_long_edge_px(s.bbox, s.img_w, s.img_h)
    return {
        "max_side": max_side, "idx": idx, "name": Path(s.image_path).stem,
        "caption": s.caption,
        "img_w": s.img_w, "img_h": s.img_h,
        "box_px_orig": round(box_orig, 1),
        "box_px_fed": round(box_orig * fed_long / max(s.img_w, s.img_h), 1),
        "box_area_pct": round(_box_area_pct(s.bbox), 3),
        "parsed": int(pred is not None),
        "iou": round(iou_val, 4) if iou_val is not None else "",
        "gate": int(iou_val is not None and iou_val >= IOU_GATE_THRESHOLD),
        "fed_w": fed_w, "fed_h": fed_h, "fed_mpx": stats.get("fed_mpx"),
        "payload_kb": stats.get("payload_kb"),
        "prompt_n": stats.get("prompt_n"), "prompt_ms": stats.get("prompt_ms"),
        "predicted_n": stats.get("predicted_n"), "predicted_ms": stats.get("predicted_ms"),
        "wall_ms": stats.get("wall_ms"), "transfer_ms": stats.get("transfer_ms"),
        "raw": text.strip().replace("\n", " ")[:60],
    }


def _med(rows, key):
    vals = [r[key] for r in rows if isinstance(r[key], (int, float))]
    return st.median(vals) if vals else 0


def arm_summary(rows, max_side):
    """Per-arm aggregate dict (accuracy + median costs)."""
    n = len(rows)
    parsed = [r for r in rows if r["parsed"]]
    ious = [r["iou"] for r in parsed if isinstance(r["iou"], (int, float))]
    hits = sum(r["gate"] for r in rows)
    return {
        "max_side": max_side, "n": n,
        "parse_pct": round(100 * len(parsed) / n, 1) if n else 0,
        "iou25_pct": round(100 * hits / n, 1) if n else 0,
        "mean_iou": round(sum(ious) / len(ious), 3) if ious else 0,
        "med_box_px_fed": round(_med(rows, "box_px_fed"), 1),
        "med_fed_mpx": round(_med(rows, "fed_mpx"), 2),
        "med_prompt_n": int(_med(rows, "prompt_n")),
        "med_prompt_ms": int(_med(rows, "prompt_ms")),
        "med_predicted_n": int(_med(rows, "predicted_n")),
        "med_predicted_ms": int(_med(rows, "predicted_ms")),
        "med_wall_ms": int(_med(rows, "wall_ms")),
        "med_transfer_ms": int(_med(rows, "transfer_ms")),
    }


def write_summary_md(summaries, out_path, note):
    cols = [("max_side", "max_side"), ("n", "n"), ("parse_pct", "parse%"),
            ("iou25_pct", "IoU@.25%"), ("mean_iou", "mean_iou"),
            ("med_box_px_fed", "box_px(fed)"), ("med_fed_mpx", "fed_mpx"),
            ("med_prompt_n", "prefill_tok"), ("med_prompt_ms", "prefill_ms"),
            ("med_predicted_n", "decode_tok"), ("med_predicted_ms", "decode_ms"),
            ("med_wall_ms", "wall_ms"), ("med_transfer_ms", "xfer_ms")]
    lines = ["# Whole-frame resolution sweep — Orin Nano, 15 W, Q8_0 (medians)", "",
             f"_{note}_", "",
             "| " + " | ".join(h for _, h in cols) + " |",
             "|" + "|".join("---" for _ in cols) + "|"]
    for s in summaries:
        lines.append("| " + " | ".join(str(s[k]) for k, _ in cols) + " |")
    out_path.write_text("\n".join(lines) + "\n")


def run(sides, n, quant, remote_dir, out_dir, note):
    from grounding.data.refdrone import load_refdrone
    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR  # noqa: F401  (kept import parity)
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend

    out_dir.mkdir(parents=True, exist_ok=True)
    samples = load_refdrone("val", max_samples=n)
    print(f"[measure] {len(samples)} val samples; sides={sides}; quant={quant}", flush=True)

    backend = JetsonBackend(f"{remote_dir}/{_REMOTE_MODELS[quant]}",
                            f"{remote_dir}/{_REMOTE_MMPROJ}",
                            max_side=max(sides), startup_timeout_s=300)
    all_rows = []
    summaries = []
    try:
        for side in sides:
            backend.max_side = side
            print(f"[measure] === max_side={side} ===", flush=True)
            t0 = time.time()
            rows = []
            for idx, s in enumerate(samples):
                rows.append(measure_sample(backend, s, side, idx))
                if (idx + 1) % max(1, len(samples) // 10) == 0:
                    print(f"  {idx+1}/{len(samples)}", flush=True)
            all_rows.extend(rows)
            summ = arm_summary(rows, side)
            summaries.append(summ)
            print(f"[measure] side={side}  parse={summ['parse_pct']}%  "
                  f"IoU@.25={summ['iou25_pct']}%  mean_iou={summ['mean_iou']}  "
                  f"prefill={summ['med_prompt_n']}tok/{summ['med_prompt_ms']}ms  "
                  f"decode={summ['med_predicted_n']}tok/{summ['med_predicted_ms']}ms  "
                  f"wall={summ['med_wall_ms']}ms  ({time.time()-t0:.0f}s)", flush=True)
            cfg = {"phase": "whole-frame", "experiment": "resolution-sweep",
                   "backend": "jetson", "quant": quant, "dataset": "refdrone",
                   "split": "val", "n": len(samples), "resolution_max_side": side,
                   "power_mode": "15W", "note": note}
            manifest.write(manifest.capture("eval", cfg), results=summ)
    finally:
        backend.close()

    with (out_dir / "per_sample.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(all_rows)
    write_summary_md(summaries, out_dir / "summary.md", note or "RefDrone well-posed val")
    print(f"\n[measure] {len(all_rows)} rows -> {out_dir/'per_sample.csv'}", flush=True)
    print(f"[measure] summary -> {out_dir/'summary.md'}", flush=True)
    for s in summaries:
        print("  ", s, flush=True)


def _selfcheck():
    """Pure-math asserts on the per-row + summary builders — no model, no Jetson."""
    # box geometry
    assert _box_long_edge_px([0, 0, COORD_SCALE, COORD_SCALE], 640, 480) == 640
    assert abs(_box_area_pct([0, 0, COORD_SCALE, COORD_SCALE]) - 100.0) < 1e-6
    half = _box_area_pct([0, 0, COORD_SCALE, COORD_SCALE // 2])
    assert abs(half - 50.0) < 1.0, half
    # summary over two fake rows (one hit, one miss, one of them unparsed)
    rows = [
        {"parsed": 1, "iou": 0.80, "gate": 1, "box_px_fed": 40, "fed_mpx": 1.0,
         "prompt_n": 800, "prompt_ms": 500, "predicted_n": 8, "predicted_ms": 100,
         "wall_ms": 700, "transfer_ms": 100},
        {"parsed": 0, "iou": "", "gate": 0, "box_px_fed": 20, "fed_mpx": 1.0,
         "prompt_n": 800, "prompt_ms": 500, "predicted_n": 8, "predicted_ms": 100,
         "wall_ms": 700, "transfer_ms": 100},
    ]
    s = arm_summary(rows, 1024)
    assert s["n"] == 2 and s["parse_pct"] == 50.0, s
    assert s["iou25_pct"] == 50.0, s          # 1 gate hit / 2 total
    assert s["mean_iou"] == 0.8, s            # mean over PARSED only
    assert s["med_prompt_n"] == 800 and s["med_wall_ms"] == 700, s
    print("measure self-check passed")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--selfcheck", action="store_true")
    p.add_argument("--sides", default="512,1024,1536,1920",
                   help="comma-separated long-edge arms (1920 ~= native VisDrone)")
    p.add_argument("--n", type=int, default=0, help="val samples (0 = full well-posed split)")
    p.add_argument("--quant", default="q8_0", choices=["q8_0", "f16"])
    p.add_argument("--remote-dir", default="/home/jfdg/grounding")
    p.add_argument("--out", default=str(HERE / "measure_out"))
    p.add_argument("--note", default="")
    args = p.parse_args()

    if args.selfcheck:
        _selfcheck()
        return

    sides = [int(x) for x in args.sides.split(",") if x.strip()]
    run(sides, args.n, args.quant, args.remote_dir, Path(args.out), args.note)


if __name__ == "__main__":
    main()
