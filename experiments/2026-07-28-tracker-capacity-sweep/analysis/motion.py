#!/usr/bin/env python3
"""Per-clip target motion in OBJECT WIDTHS per frame, and what it becomes over a stale hold.

`motion` is the same quantity `difficulty.py` already scores -- median centre step over
sqrt(w*h) -- lifted out so it also runs on TLP, and multiplied by a hold length. Under the
paced protocol the tracker's box is held for `lag` frames, so the drift the consumer actually
eats is `motion * lag`; at ~0.35 widths the boxes stop overlapping and IoU collapses.

    analysis/motion.py                    # every dataset on disk
    analysis/motion.py --lag 5 --csv m.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data  # noqa: E402


def features(name: str) -> dict:
    gt = data.boxes(name)
    vis = [(i, b) for i, b in enumerate(gt) if b is not None]
    idx = np.array([i for i, _ in vis])
    wh = np.array([[b[2] - b[0], b[3] - b[1]] for _, b in vis])
    body = np.sqrt(wh[:, 0] * wh[:, 1])
    cen = np.array([[(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] for _, b in vis])
    # only consecutive visible frames: a step across a gap is a teleport, not motion
    ok = np.diff(idx) == 1
    step = np.linalg.norm(np.diff(cen, axis=0), axis=1)[ok]
    rel = step / body[:-1][ok]
    return {
        "seq": name, "frames": len(gt), "size_px": float(np.median(body)),
        "px": float(np.median(step)) if len(step) else 0.0,
        "motion": float(np.median(rel)) if len(rel) else 0.0,
        "p90": float(np.percentile(rel, 90)) if len(rel) else 0.0,
        "gap": (len(gt) - len(vis)) / len(gt),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lag", type=int, default=5,
                    help="frames the box is held; 5 = sam2_c640 at 159 ms over a 30 fps stream")
    ap.add_argument("--ds", nargs="+", default=[d.name for d in data.DATASETS])
    ap.add_argument("--csv")
    args = ap.parse_args()

    for ds in args.ds:
        rows = sorted((features(n) for n in data.sequences(ds)), key=lambda r: -r["motion"])
        if not rows:
            continue
        print(f"\n{ds}: {len(rows)} clips, deriva sobre {args.lag} fotogramas de retencion")
        print(f"{'seq':14s}{'frames':>7s}{'tam px':>7s}{'px/f':>6s}{'anch/f':>8s}"
              f"{'p90':>7s}{'x' + str(args.lag):>7s}{'hueco%':>7s}")
        for r in rows:
            print(f"{r['seq']:14s}{r['frames']:7d}{r['size_px']:7.0f}{r['px']:6.1f}"
                  f"{r['motion']:8.4f}{r['p90']:7.3f}{r['motion'] * args.lag:7.3f}"
                  f"{r['gap'] * 100:6.1f}%")
        m = np.array([r["motion"] for r in rows])
        print(f"{'MEDIANA':14s}{'':7s}{np.median([r['size_px'] for r in rows]):7.0f}"
              f"{np.median([r['px'] for r in rows]):6.1f}{np.median(m):8.4f}"
              f"{'':7s}{np.median(m) * args.lag:7.3f}")

    if args.csv:
        rows = [r | {"ds": ds} for ds in args.ds for r in map(features, data.sequences(ds))]
        keys = list(rows[0])
        Path(args.csv).write_text(",".join(keys) + "\n"
                                  + "\n".join(",".join(str(r[k]) for k in keys) for r in rows) + "\n")
        print(f"\n-> {args.csv}")


if __name__ == "__main__":
    main()
