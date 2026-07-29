"""Search for a better a priori difficulty index: candidate GT-only axes, then subset selection.

`difficulty.py` scores rank-sum over size/motion/gap and validates at rho=-0.707. This asks whether
a different set of axes does better, over a wider pool of candidates that are still GT-only (no
tracker output, no pixels beyond the frame header) so the index stays a priori.

The target is the cross-arm MEDIAN mean_iou per clip: median over arms, so one bad arm does not
define a clip, and the score is not tied to the arm we happen to deploy.

Selection on 30 points overfits -- with 14 candidates the best subset is partly noise. Two guards:

  * LOO   leave-one-clip-out. Re-select the best subset on the other n-1 clips, predict the held-out
          one, correlate the held-out predictions. This is the honest number; the in-sample `rho`
          column is the optimistic one. A big LOO/rho gap means the subset is fitted to noise.
  * ranks are always computed over all 123 sequences, never over the scored subset, so the axis
          values themselves carry no information from the labels.

    analysis/index_search.py raw/full-sweep-30 [--max-axes 4]
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import difficulty  # noqa: E402
import uav123  # noqa: E402
from aggregate import score_one  # noqa: E402

# name -> (higher value means harder?)
CANDIDATES = {
    "size_px": False, "size_min": False, "size_p10": False,
    "motion": True, "motion_p90": True, "speed_px": True,
    "gap": True, "gap_runs": True, "gap_max": True,
    "roam": True, "scale_range": True, "scale_jitter": True, "aspect_jitter": True,
    "edge_frac": True,
}


def features(name: str) -> dict:
    """Everything `difficulty.features` has, plus the candidates being auditioned."""
    f = difficulty.features(name)
    gt = uav123.boxes(name)
    vis = [(i, b) for i, b in enumerate(gt) if b is not None]
    idx = np.array([i for i, _ in vis])
    wh = np.array([[b[2] - b[0], b[3] - b[1]] for _, b in vis], float)
    diag = np.sqrt(wh[:, 0] * wh[:, 1])
    cen = np.array([[(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] for _, b in vis])
    ok = np.diff(idx) == 1  # a step across a gap is a teleport, not motion
    step = np.linalg.norm(np.diff(cen, axis=0), axis=1)[ok]
    fw, fh = difficulty.frame_size(name)

    # NaN runs: 20 one-frame blinks and one 20-frame blackout are the same `gap` but not the same
    # problem -- the second is the one that loses a tracker for good.
    runs, cur = [], 0
    for i in range(len(gt)):
        if gt[i] is None:
            cur += 1
        elif cur:
            runs.append(cur); cur = 0
    if cur:
        runs.append(cur)

    # how often GT sits within one target-size of the frame border: the target is leaving the shot,
    # which is the case a crop window handles worst
    m = diag
    at_edge = ((wh[:, 0] * 0 + cen[:, 0] - m / 2 < m) | (cen[:, 1] - m / 2 < m)
               | (cen[:, 0] + m / 2 > fw - m) | (cen[:, 1] + m / 2 > fh - m))

    lg = np.log(diag)
    ar = np.log(wh[:, 0] / np.maximum(wh[:, 1], 1e-6))
    f.update({
        "size_min": float(diag.min()),
        "size_p10": float(np.percentile(diag, 10)),
        "motion_p90": float(np.percentile(step / diag[:-1][ok], 90)) if len(step) else 0.0,
        "speed_px": float(np.median(step)) if len(step) else 0.0,
        "gap_runs": len(runs) / len(gt),
        "gap_max": (max(runs) if runs else 0) / len(gt),
        "scale_jitter": float(np.median(np.abs(np.diff(lg)[ok]))) if ok.any() else 0.0,
        "aspect_jitter": float(np.median(np.abs(np.diff(ar)[ok]))) if ok.any() else 0.0,
        "edge_frac": float(at_edge.mean()),
    })
    return f


def build_ranks(feats: list[dict]) -> dict[str, np.ndarray]:
    """Percentile rank per candidate over the FULL population, oriented so 1 = hard."""
    out = {}
    for k, hard_is_high in CANDIDATES.items():
        r = difficulty.rank01(np.array([f[k] for f in feats]))
        out[k] = r if hard_is_high else 1 - r
    return out


def best_subset(axes: list[str], R: np.ndarray, y: np.ndarray, k: int) -> tuple[float, tuple]:
    """Exhaustive over subsets up to size k. 14 candidates, so this is ~1500 combinations."""
    best = (-2.0, ())
    for n in range(1, k + 1):
        for c in itertools.combinations(range(len(axes)), n):
            rho = spearmanr(R[:, list(c)].mean(1), y).statistic
            if -rho > best[0]:  # hard index vs mIoU: more negative is better
                best = (-rho, c)
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--max-axes", type=int, default=4)
    ap.add_argument("--min-arms", type=int, default=5)
    args = ap.parse_args()

    per = [score_one(p) for p in sorted(Path(args.run_dir).glob("*.json")) if p.stem != "manifest"]
    by_seq: dict[str, list[float]] = {}
    for r in per:
        by_seq.setdefault(r["seq"], []).append(r["mean_iou"])
    scored = {s: float(np.median(v)) for s, v in by_seq.items() if len(v) >= args.min_arms}

    names = sorted(uav123.config())
    feats = [features(n) for n in names]
    ranks = build_ranks(feats)
    axes = list(CANDIDATES)

    sel = [i for i, n in enumerate(names) if n in scored]
    y = np.array([scored[names[i]] for i in sel])
    R = np.column_stack([ranks[a] for a in axes])[sel]
    n = len(sel)
    print(f"{n} clips con >={args.min_arms} brazos, {len(axes)} ejes candidatos\n")

    print(f"{'eje':14s}{'rho':>8s}{'p':>10s}")
    for j, a in enumerate(axes):
        r = spearmanr(R[:, j], y)
        print(f"{a:14s}{r.statistic:8.3f}{r.pvalue:10.4f}")

    cur = [axes.index(a) for a in difficulty.AXES]
    base = spearmanr(R[:, cur].mean(1), y)
    print(f"\nactual {'+'.join(difficulty.AXES):34s} rho={base.statistic:6.3f} p={base.pvalue:.2g}")

    print(f"\nmejores subconjuntos (<= {args.max_axes} ejes, en muestra)")
    scores = []
    for k in range(1, args.max_axes + 1):
        for c in itertools.combinations(range(len(axes)), k):
            scores.append((-spearmanr(R[:, list(c)].mean(1), y).statistic, c))
    scores.sort(reverse=True)
    for s, c in scores[:8]:
        print(f"  rho={-s:6.3f}  {'+'.join(axes[i] for i in c)}")

    # LOO: re-select on n-1, predict the held-out clip. Guards against picking a fitted subset.
    pred, picks = [], []
    for h in range(n):
        keep = [i for i in range(n) if i != h]
        _, c = best_subset(axes, R[keep], y[keep], args.max_axes)
        picks.append(c)
        pred.append(R[h, list(c)].mean())
    loo = spearmanr(pred, y)
    top = max(set(picks), key=picks.count)
    print(f"\nLOO rho={loo.statistic:6.3f} p={loo.pvalue:.2g}   "
          f"subconjunto elegido en {picks.count(top)}/{n} pliegues: {'+'.join(axes[i] for i in top)}")
    loo_cur = spearmanr(R[:, cur].mean(1), y)  # the current index is not selected, so LOO == rho
    print(f"    frente al indice actual, rho={loo_cur.statistic:6.3f} (sin seleccion, no hay que "
          f"validarlo cruzado)")


if __name__ == "__main__":
    main()
