"""Pick the sweep's sequence subset from UAV123, maximising heterogeneity.

Greedy max-min (farthest-point) over z-scored per-sequence features: start from the most extreme
sequence, then repeatedly add whichever is farthest from everything already picked. That spreads
the subset over the feature space instead of clustering it near the mean, which is what a random
or a "longest N" draw would do.

Features beyond the obvious four (length, size, GT gaps, scale trend):
  scale_ratio  p90/p10 of area -- dynamic range, orthogonal to the trend (a target can oscillate
               without any net drift)
  absent_events  number of gaps, not their length: one 200-frame occlusion and twenty 10-frame
               ones are different failures (re-identification vs a single loss)
  speed_norm   per-frame displacement RELATIVE to target size -- this, not pixel speed, is what
               breaks IoU-based association
  edge_frac    fraction of frames touching the border (partial out-of-view)
  ar_cv        aspect-ratio variation: viewpoint change and deformation
  ar_med       base shape (upright pedestrian vs wide boat)
  category, resolution  balanced explicitly; the uav* clips are the only 720x480 group
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import uav123

# log where spread is multiplicative, sqrt to stop a single 45%-occluded clip dominating
AXES = {
    "len": lambda r: np.log(r["frames"]),
    "area": lambda r: np.log(max(r["area_med"], 1)),
    "scale_range": lambda r: np.log(max(r["scale_ratio"], 1.01)),
    "scale_trend": lambda r: r["scale_trend"],
    "absent": lambda r: np.sqrt(r["absent_frac"]),
    "absent_evt": lambda r: np.log1p(r["absent_events"]),
    "speed": lambda r: np.log1p(r["speed_norm"]),
    "edge": lambda r: r["edge_frac"],
    "ar_cv": lambda r: r["ar_cv"],
    "ar_med": lambda r: np.log(r["ar_med"]),
}
ATTR_WEIGHT = 0.5  # 12 binary flags would otherwise swamp 10 continuous axes


def runs(mask) -> list[int]:
    """Lengths of consecutive True runs."""
    out, n = [], 0
    for v in mask:
        if v:
            n += 1
        elif n:
            out.append(n)
            n = 0
    return out + ([n] if n else [])


def features(name: str) -> dict:
    import cv2

    gt = np.array([[np.nan] * 4 if b is None else b for b in uav123.boxes(name)], float)
    h, w = cv2.imread(str(uav123.frame_paths(name)[0])).shape[:2]

    absent = np.isnan(gt[:, 0])
    v = gt[~absent]
    bw, bh = v[:, 2] - v[:, 0], v[:, 3] - v[:, 1]
    area = bw * bh
    cx, cy = v[:, 0] + bw / 2, v[:, 1] + bh / 2
    step = np.hypot(np.diff(cx), np.diff(cy))
    lo, hi = np.percentile(area, [10, 90])
    trend = np.corrcoef(np.arange(len(area)), area)[0, 1] if len(area) > 2 and area.std() > 0 else 0.0
    edge = (v[:, 0] <= 1) | (v[:, 1] <= 1) | (v[:, 2] >= w - 1) | (v[:, 3] >= h - 1)
    ar = bw / bh
    gaps = runs(absent)

    return {
        "name": name,
        "cat": next(c for c in uav123.CATS if name.startswith(c)),
        "frames": len(gt), "w": w, "h": h,
        "area_med": float(np.median(area)),
        "scale_ratio": float(np.sqrt(hi / max(lo, 1))),
        "scale_trend": float(trend),
        "absent_frac": float(absent.mean()),
        "absent_events": len(gaps),
        "absent_longest": max(gaps, default=0),
        "speed_norm": float(np.median(step) / max(np.sqrt(np.median(area)), 1)) if len(step) else 0.0,
        "edge_frac": float(edge.mean()),
        "ar_med": float(np.median(ar)),
        "ar_cv": float(ar.std() / ar.mean()),
        **uav123.attrs(name),
    }


def select(rows: list[dict], k: int, cat_cap: int) -> list[int]:
    X = np.array([[f(r) for f in AXES.values()] for r in rows])
    X = (X - X.mean(0)) / X.std(0)
    A = np.array([[r[a] for a in uav123.ATTRS] for r in rows], float) * ATTR_WEIGHT
    X = np.hstack([X, A])
    cats = [r["cat"] for r in rows]

    picked = [int(np.linalg.norm(X - X.mean(0), axis=1).argmax())]  # most extreme sequence
    dist = np.linalg.norm(X - X[picked[0]], axis=1)
    while len(picked) < k:
        used = {c: sum(cats[i] == c for i in picked) for c in set(cats)}
        ok = np.array([i not in picked and used[cats[i]] < cat_cap for i in range(len(rows))])
        assert ok.any(), "category caps too tight for k"
        i = int(np.where(ok, dist, -1).argmax())
        picked.append(i)
        dist = np.minimum(dist, np.linalg.norm(X - X[i], axis=1))
    return picked


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", type=int, default=30)
    ap.add_argument("--cat-cap", type=int, default=5)
    ap.add_argument("--json", help="write the full feature table here")
    args = ap.parse_args()

    rows = [features(n) for n in sorted(uav123.config())]
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1))
    sel = sorted((rows[i] for i in select(rows, args.k, args.cat_cap)),
                 key=lambda r: (r["cat"], r["name"]))

    print(f"{'name':14s} {'cat':10s} {'frames':>6s} {'area':>7s} {'scaleR':>6s} "
          f"{'trend':>6s} {'noGT%':>6s} {'spd':>5s} {'res':>9s}  attrs")
    for r in sel:
        on = ",".join(a for a in uav123.ATTRS if r[a])
        print(f"{r['name']:14s} {r['cat']:10s} {r['frames']:6d} {r['area_med']:7.0f} "
              f"{r['scale_ratio']:6.2f} {r['scale_trend']:+6.2f} {100 * r['absent_frac']:6.1f} "
              f"{r['speed_norm']:5.2f} {r['w']}x{r['h']:<4d}  {on}")

    tot = sum(r["frames"] for r in sel)
    print(f"\nn={len(sel)} frames={tot} mean={tot / len(sel):.0f} "
          f"pop_mean={sum(r['frames'] for r in rows) / len(rows):.0f}")
    print("cats:", {c: sum(r["cat"] == c for r in sel) for c in sorted({r["cat"] for r in sel})})
    print("attrs:", {a: f"{sum(r[a] for r in sel)}/{sum(r[a] for r in rows)}" for a in uav123.ATTRS})
    print("names:", " ".join(r["name"] for r in sel))


if __name__ == "__main__":
    main()
