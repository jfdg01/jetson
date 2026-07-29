"""Aggregate a whole run into per-sequence and per-arm tables.

Per-arm numbers are the MEDIAN over sequences, not the mean over frames: `bike1` has 3085 frames
and `uav2` has 133, so a frame-weighted mean would let one clip count 23 times another. `mean_iou`
inside a sequence is still over that sequence's scored frames, which is what a per-clip score is.

A frame the arm lost scores 0, not NaN. Scoring only the frames an arm answered flatters exactly
the arms that give up -- the `t512` row on wakeboard1 was 36 frames of free pass. Frames where GT
itself is absent (the target is out of shot) are excluded from both, since there is nothing to hit.

    analysis/aggregate.py raw/full-sweep-30 --csv out.csv
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import uav123  # noqa: E402
from render_overlay import iou  # noqa: E402


def score_one(path: Path) -> dict:
    res = json.loads(path.read_text())
    meta, rows = res["meta"], {r["i"]: r for r in res["rows"]}
    gt = uav123.boxes(meta["seq"])
    have = [(g, rows.get(i, {}).get("box")) for i, g in enumerate(gt) if g is not None]
    ious = np.array([0.0 if p is None else iou(g, p) for g, p in have])
    gap = len(gt) - len(have)
    # a gap frame the arm answered anyway is a false positive: nothing was there to find
    fp = sum(1 for i, g in enumerate(gt) if g is None and rows.get(i, {}).get("box"))
    return {
        "arm": meta["arm"], "seq": meta["seq"], "frames": meta["frames"],
        "gt_frames": len(have), "gap_frames": gap, "gap_false_pos": fp,
        "mean_iou": float(ious.mean()), "iou@0.25": float((ious >= 0.25).mean()),
        "iou@0.5": float((ious >= 0.5).mean()),
        "lost": meta["lost_frames"], "ms_p50": meta["ms_p50"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--csv")
    args = ap.parse_args()

    per = [score_one(p) for p in sorted(Path(args.run_dir).glob("*.json")) if p.stem != "manifest"]
    assert per, f"no results in {args.run_dir}"
    # sort by family letter then resolution: 'sam2_c640_coast' -> ('c', 640, '_coast')
    def key(a: str) -> tuple:
        m = re.match(r"sam2_([a-z]+)(\d+)(.*)", a)
        return (0, m[1], int(m[2]), m[3]) if m else (1, a, 0, "")

    arms = sorted({r["arm"] for r in per}, key=key)

    print(f"{len(per)} results, {len({r['seq'] for r in per})} sequences\n")
    print(f"{'arm':11s} {'n':>3s} {'p50':>8s} {'mIoU':>7s} {'@0.25':>7s} {'@0.5':>7s} "
          f"{'lost%':>7s} {'FP hueco':>9s}")
    for a in arms:
        g = [r for r in per if r["arm"] == a]
        m = lambda k: np.median([r[k] for r in g])  # noqa: E731
        lost = np.median([r["lost"] / r["frames"] for r in g])
        print(f"{a:11s} {len(g):3d} {m('ms_p50'):7.1f}m {m('mean_iou'):7.3f} {m('iou@0.25'):7.3f} "
              f"{m('iou@0.5'):7.3f} {lost * 100:6.1f}% {int(sum(r['gap_false_pos'] for r in g)):9d}")

    seqs = sorted({r["seq"] for r in per})
    print(f"\nmIoU por secuencia\n{'seq':13s}" + "".join(f"{a[5:]:>7s}" for a in arms))
    for s in seqs:
        row = {r["arm"]: r for r in per if r["seq"] == s}
        print(f"{s:13s}" + "".join(
            f"{row[a]['mean_iou']:7.3f}" if a in row else "      -" for a in arms))

    if args.csv:
        keys = list(per[0])
        Path(args.csv).write_text(
            ",".join(keys) + "\n" + "\n".join(",".join(str(r[k]) for k in keys) for r in per) + "\n")
        print(f"\n-> {args.csv}")


if __name__ == "__main__":
    main()
