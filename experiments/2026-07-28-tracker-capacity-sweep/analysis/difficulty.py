"""A priori difficulty index for UAV123 clips: GT only, no tracker involved.

Ranking clips by how badly the trackers did would be circular -- you cannot then use the
ranking to judge the trackers. Everything here comes from the annotation file, so a clip can
be catalogued before it is ever run.

Three axes, each the continuous version of an attribute flag UAV123 already ships:

    size    median sqrt(w*h) in px          <- LR (low resolution), SOB (small object)
    motion  median centre step / sqrt(w*h)  <- FM (fast motion), CM (camera motion)
    gap     fraction of NaN frames          <- FOC/OV (full occlusion, out of view)

Combined by RANK SUM, not a weighted score: weights would need a justification we do not
have, ranks need none. Score is the mean of the three percentile ranks, 0 easy .. 1 hard.

    analysis/difficulty.py [--seqs raw/full-sweep-30] [--csv out.csv]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import uav123


def features(name: str) -> dict:
    gt = uav123.boxes(name)
    vis = [(i, b) for i, b in enumerate(gt) if b is not None]
    wh = np.array([[b[2] - b[0], b[3] - b[1]] for _, b in vis])
    diag = np.sqrt(wh[:, 0] * wh[:, 1])                       # size proxy, px
    cen = np.array([[(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] for _, b in vis])
    idx = np.array([i for i, _ in vis])
    # only consecutive visible frames: a step across a gap is not motion, it is a teleport
    ok = np.diff(idx) == 1
    step = np.linalg.norm(np.diff(cen, axis=0), axis=1)[ok]
    body = diag[:-1][ok]
    a = uav123.attrs(name)
    return {
        "seq": name, "frames": len(gt),
        "size_px": float(np.median(diag)),
        "motion": float(np.median(step / body)) if len(step) else 0.0,
        "gap": (len(gt) - len(vis)) / len(gt),
        "scale_range": float(diag.max() / diag.min()),
        "att": "".join(k for k in uav123.ATTRS if a[k]),
        "n_att": sum(a.values()),
    }


def rank01(v: np.ndarray) -> np.ndarray:
    """Percentile rank in [0,1], ties averaged. 1 = hardest."""
    order = v.argsort().argsort().astype(float)
    return order / max(len(v) - 1, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seqs", default="raw/full-sweep-30",
                    help="run dir (clips taken from its filenames) or comma list")
    ap.add_argument("--csv")
    args = ap.parse_args()

    p = Path(args.seqs)
    if p.is_dir():
        names = sorted({f.stem.split("__")[1] for f in p.glob("*__*.json")})
    else:
        names = args.seqs.split(",")

    rows = [features(n) for n in names]
    size = np.array([r["size_px"] for r in rows])
    mot = np.array([r["motion"] for r in rows])
    gap = np.array([r["gap"] for r in rows])
    # small is hard, so the size rank is inverted
    r_size, r_mot, r_gap = 1 - rank01(size), rank01(mot), rank01(gap)
    for r, a, b, c in zip(rows, r_size, r_mot, r_gap):
        r["score"] = float((a + b + c) / 3)

    rows.sort(key=lambda r: -r["score"])
    third = len(rows) / 3
    print(f"{'seq':13s}{'score':>6s}{'sizepx':>7s}{'motion':>7s}{'gap%':>6s}{'scale':>6s}  attrs")
    for i, r in enumerate(rows):
        band = "DIFICIL" if i < third else ("MEDIO" if i < 2 * third else "FACIL")
        print(f"{r['seq']:13s}{r['score']:6.2f}{r['size_px']:7.1f}{r['motion']:7.3f}"
              f"{r['gap'] * 100:5.0f}%{r['scale_range']:6.1f}  {band:7s} {r['att']}")

    if args.csv:
        keys = ["seq", "score", "size_px", "motion", "gap", "scale_range", "frames", "n_att", "att"]
        Path(args.csv).write_text(",".join(keys) + "\n"
                                  + "\n".join(",".join(str(r[k]) for k in keys) for r in rows) + "\n")
        print(f"\n-> {args.csv}")


if __name__ == "__main__":
    main()
