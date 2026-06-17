"""Dataset audit gate (Phase 1).

Computes box-per-caption and object-size distributions and decides well-posedness
*before* any GPU run. Had this existed in Part I, the Stage 2 ill-posed RefDrone
target (many boxes per caption → marginal-mean collapse) would have been caught
for free. The gate result is captured as `AuditStats` and written to a per-run
manifest (kind="audit") so the distribution is a committed, reproducible artifact.

The audit consumes the *pre-filter* `RawRecord` view (one caption + ALL of its
real boxes), because the box-per-caption distribution — the Stage-2 sentinel — is
only visible before the one-box collapse the canonical `GroundingSample` performs.

Object size is √(w·h) in pixels per real box; the post-resize column multiplies by
`IMAGE_SIZE / max(img_w, img_h)` (the long-edge resize the frozen encoder sees), so
binding constraint #2 (aerial objects → 2–11 px after 512 resize) is quantified
exactly rather than recalled.

CPU-only, no model, no torch. Reproducible from the committed annotation JSON.
"""

from __future__ import annotations

import argparse
import math
from collections import Counter
from typing import Dict, List, Sequence

from grounding.contract import IMAGE_SIZE
from grounding.data.schema import AuditStats, RawRecord

_PERCENTILES = [5, 10, 25, 50, 75, 90, 95]


def _percentiles(values: Sequence[float], pcts: Sequence[int] = _PERCENTILES) -> Dict[str, float]:
    """Linear-interpolated percentiles, keyed 'p5','p10',… ; {} for empty input."""
    if not values:
        return {}
    xs = sorted(values)
    n = len(xs)
    out: Dict[str, float] = {}
    for p in pcts:
        if n == 1:
            out[f"p{p}"] = round(xs[0], 2)
            continue
        rank = (p / 100.0) * (n - 1)
        lo = int(math.floor(rank))
        hi = int(math.ceil(rank))
        frac = rank - lo
        out[f"p{p}"] = round(xs[lo] + (xs[hi] - xs[lo]) * frac, 2)
    return out


def audit(records: Sequence[RawRecord], *, split: str = "") -> AuditStats:
    """Compute the distribution summary for a set of pre-filter `RawRecord`s.

    - box-per-caption histogram + mean (the Part-I "3.80" sentinel)
    - well-posed fraction = share of captions with exactly one real box
    - √area object-size percentiles, pre- and post-`IMAGE_SIZE` long-edge resize
    """
    if not records:
        raise ValueError("audit() received zero records")

    source = records[0].source
    n_records = len(records)
    hist: Counter[int] = Counter()
    sizes_px: List[float] = []
    sizes_resized: List[float] = []
    n_real_boxes = 0
    n_well_posed = 0

    for r in records:
        k = len(r.boxes_xyxy)
        hist[k] += 1
        n_real_boxes += k
        if k == 1:
            n_well_posed += 1
        scale = IMAGE_SIZE / max(r.img_w, r.img_h)
        for (x1, y1, x2, y2) in r.boxes_xyxy:
            w = max(0.0, x2 - x1)
            h = max(0.0, y2 - y1)
            s = math.sqrt(w * h)
            sizes_px.append(s)
            sizes_resized.append(s * scale)

    return AuditStats(
        source=source,
        split=split,
        n_records=n_records,
        n_real_boxes=n_real_boxes,
        boxes_per_caption={str(k): hist[k] for k in sorted(hist)},
        boxes_per_caption_mean=round(n_real_boxes / n_records, 4),
        n_well_posed=n_well_posed,
        well_posed_fraction=round(n_well_posed / n_records, 4),
        obj_size_px_percentiles=_percentiles(sizes_px),
        obj_size_px_after_resize=_percentiles(sizes_resized),
        image_size=IMAGE_SIZE,
    )


def assert_well_posed(stats: AuditStats, *, min_well_posed_fraction: float = 0.95) -> None:
    """Phase-1 gate: raise if the split is not predominantly one-box-per-caption.

    Applied to the *trainable* (already well-posed-filtered) corpus, where the
    fraction must be ~1.0 by construction. The raw aerial corpus is expected to
    FAIL this (that failure is the documented finding) — call it on the filtered
    samples, not the raw records, to assert the trainer is fed a clean target.
    """
    if stats.well_posed_fraction < min_well_posed_fraction:
        raise AssertionError(
            f"{stats.source}/{stats.split}: well-posed fraction "
            f"{stats.well_posed_fraction:.3f} < {min_well_posed_fraction:.3f} "
            f"(mean {stats.boxes_per_caption_mean} boxes/caption; "
            f"histogram {stats.boxes_per_caption}) — ill-posed target, the Stage-2 "
            f"failure mode. Filter to the one-box subset before training."
        )


# --- CLI ------------------------------------------------------------------------

def _records_for(dataset: str, split: str, max_samples: int) -> List[RawRecord]:
    """Build the pre-filter RawRecord view for a dataset/split."""
    if dataset == "refdrone":
        from grounding.data.refdrone import load_refdrone_raw
        recs = load_refdrone_raw(split)
        if max_samples:
            recs = recs[:max_samples]
        return recs
    if dataset == "refcoco":
        # RefCOCO is one-box-by-construction: each canonical sample is its own
        # RawRecord with a single box. This is the control arm (expected wp≈1.0).
        from grounding.data.refcoco import load_refcoco
        samples = load_refcoco(split, max_samples=max_samples)
        return [
            RawRecord(
                caption=s.caption,
                # canonical bbox is already normalized 0–COORD_SCALE; for the
                # size audit we want pixels, so de-normalize back to img_w/img_h.
                boxes_xyxy=[[
                    s.bbox[0] / 1000.0 * s.img_w, s.bbox[1] / 1000.0 * s.img_h,
                    s.bbox[2] / 1000.0 * s.img_w, s.bbox[3] / 1000.0 * s.img_h,
                ]],
                img_w=s.img_w,
                img_h=s.img_h,
                source="refcoco",
            )
            for s in samples
        ]
    raise SystemExit(f"unknown --dataset {dataset!r} (refdrone|refcoco)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase-1 dataset audit gate.")
    ap.add_argument("--dataset", required=True, choices=["refdrone", "refcoco"])
    ap.add_argument("--split", required=True)
    ap.add_argument("--max-samples", type=int, default=0)
    ap.add_argument("--runs-dir", default="runs")
    args = ap.parse_args()

    from dataclasses import asdict

    from grounding import manifest as M

    records = _records_for(args.dataset, args.split, args.max_samples)
    stats = audit(records, split=args.split)
    results = asdict(stats)

    cfg = {
        "dataset": args.dataset,
        "split": args.split,
        "max_samples": args.max_samples,
    }
    # Make the run_id self-describing AND collision-free: several audits run in the
    # same wall-clock second (train+val), so a bare UTC timestamp overwrites.
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{ts}-audit-{args.dataset}-{args.split}"
    man = M.capture("audit", cfg, run_id=run_id)
    run_dir = M.write(man, runs_dir=args.runs_dir, results=results)

    # Human-readable echo
    print(f"[audit] {stats.source}/{stats.split}: {stats.n_records} captions, "
          f"{stats.n_real_boxes} real boxes")
    print(f"[audit] boxes/caption mean = {stats.boxes_per_caption_mean}  "
          f"histogram = {stats.boxes_per_caption}")
    print(f"[audit] well-posed (1 box) = {stats.n_well_posed} "
          f"({stats.well_posed_fraction:.1%})")
    print(f"[audit] √area px   percentiles = {stats.obj_size_px_percentiles}")
    print(f"[audit] √area px@{stats.image_size} resize = {stats.obj_size_px_after_resize}")
    print(f"[audit] manifest → {run_dir}")


if __name__ == "__main__":
    main()
