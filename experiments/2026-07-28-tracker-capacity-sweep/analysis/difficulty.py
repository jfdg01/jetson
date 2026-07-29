"""A priori difficulty index for UAV123 clips: GT only, no tracker involved.

Ranking clips by how badly the trackers did would be circular -- you cannot then use the
ranking to judge the trackers. Everything here comes from the annotation file, so a clip can
be catalogued before it is ever run.

Four axes, the first three each the continuous version of an attribute flag UAV123 ships:

    size    median sqrt(w*h) in px          <- LR (low resolution), SOB (small object)
    motion  median centre step / sqrt(w*h)  <- FM (fast motion), CM (camera motion)
    gap     fraction of NaN frames          <- FOC/OV (full occlusion, out of view)
    roam    RMS distance of the GT centre from its own mean, / frame diagonal

`roam` has no attribute flag and is not a slower `motion`: motion is per-frame jitter relative
to the target's own body, roam is how much of the frame the target ends up covering over the
whole clip. A UAV123 camera chases its target, so a target pinned near frame centre means the
camera kept up and a crop window would too; a high roam means it did not. RMS about the mean
rather than the bounding box of the track, so one stray frame cannot set the value.

Combined by RANK SUM, not a weighted score: weights would need a justification we do not
have, ranks need none. Score is the mean of the four percentile ranks, 0 easy .. 1 hard.

    analysis/difficulty.py [--seqs raw/full-sweep-30] [--csv out.csv]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

import uav123


def frame_size(name: str) -> tuple[int, int]:
    """(w, h) of the clip. PIL reads the JPEG header only, so this does not decode 123 images."""
    with Image.open(uav123.frame_paths(name)[0]) as im:
        return im.size


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
    fw, fh = frame_size(name)
    roam = float(np.sqrt(((cen - cen.mean(0)) ** 2).sum(1).mean()) / np.hypot(fw, fh))
    a = uav123.attrs(name)
    return {
        "seq": name, "frames": len(gt),
        "size_px": float(np.median(diag)),
        "motion": float(np.median(step / body)) if len(step) else 0.0,
        "gap": (len(gt) - len(vis)) / len(gt),
        "roam": roam,
        "scale_range": float(diag.max() / diag.min()),
        "att": "".join(k for k in uav123.ATTRS if a[k]),
        "n_att": sum(a.values()),
    }


def rank01(v: np.ndarray) -> np.ndarray:
    """Percentile rank in [0,1], ties averaged. 1 = hardest."""
    order = v.argsort().argsort().astype(float)
    return order / max(len(v) - 1, 1)


# size is the only axis where small means hard. `roam` is computed and reported but deliberately
# NOT scored: adding it drops the validation from rho=-0.707 to -0.642 against the cross-arm
# median mIoU (n=24). Alone it is rho=-0.291, p=0.17 -- no signal -- and it correlates +0.50 with
# `motion`, so it mostly re-spends a rank the index already has. Revisit at n=49.
AXES = ["size_px", "motion", "gap"]


def score(rows: list[dict], axes: list[str] = AXES) -> list[dict]:
    """Add `score` and `rank` in place, then return `rows` sorted hardest first.

    Ranks are relative to the set passed in, so scoring 30 clips and scoring all 123 give
    different numbers for the same clip. That is the intended behaviour -- "hard" only means
    anything against a reference population -- but it is why the same clip is 0.92 among 30
    and 0.97 among 123, and why bands must never be compared across two different calls.
    """
    for k in axes:
        r01 = rank01(np.array([r[k] for r in rows]))
        if k == "size_px":
            r01 = 1 - r01
        for r, v in zip(rows, r01):
            r.setdefault("_r", []).append(v)
    for r in rows:
        r["score"] = float(np.mean(r.pop("_r")))
    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


def load(spec: str) -> list[str]:
    """`all`, a run dir whose filenames carry the clip names, or a comma list."""
    if spec == "all":
        return sorted(uav123.config())
    p = Path(spec)
    if p.is_dir():
        return sorted({f.stem.split("__")[1] for f in p.glob("*__*.json")})
    return spec.split(",")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seqs", default="all",
                    help="'all', a run dir (clips taken from its filenames), or a comma list")
    ap.add_argument("--csv")
    args = ap.parse_args()

    rows = score([features(n) for n in load(args.seqs)])
    third = len(rows) / 3
    print(f"{'seq':13s}{'score':>6s}{'sizepx':>7s}{'motion':>7s}{'gap%':>6s}{'roam':>6s}  attrs")
    for i, r in enumerate(rows):
        band = "DIFICIL" if i < third else ("MEDIO" if i < 2 * third else "FACIL")
        print(f"{r['seq']:13s}{r['score']:6.2f}{r['size_px']:7.1f}{r['motion']:7.3f}"
              f"{r['gap'] * 100:5.0f}%{r['roam']:6.3f}  {band:7s} {r['att']}")

    if args.csv:
        keys = ["seq", "score", "size_px", "motion", "gap", "scale_range", "frames", "n_att", "att"]
        Path(args.csv).write_text(",".join(keys) + "\n"
                                  + "\n".join(",".join(str(r[k]) for k in keys) for r in rows) + "\n")
        print(f"\n-> {args.csv}")


if __name__ == "__main__":
    main()
