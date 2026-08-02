#!/usr/bin/env python3
"""Where resolution stops paying: quality from a parity run, staleness from its own latency.

Raising resolution buys a better box AND a slower one. Under the paced protocol the second half
is not free, so the two curves cross somewhere and that crossing is per clip, because the cost of
being late is `motion * lag` -- the drift in object widths the consumer eats while it holds a
stale box. A clip whose target barely moves never crosses; `uav2` crosses almost immediately.

Model, two ingredients and no free parameter beyond `--k`:

    lag  = ms_p50 * fps / 1000 * k          frames the box is held (k=1: one latency)
    f    = motion * lag                     drift in object widths
    pred = parity_mIoU * (1 - f) / (1 + f)  two equal boxes offset by f of their side

`(1-f)/(1+f)` is the exact IoU of two identical squares translated along one axis. Real drift is
2-D and the box also rescales, so this is an upper bound on the surviving overlap; `--k` exists to
absorb the difference and is fitted, not assumed -- pass a paced run as `--check` to fit it.

    analysis/sweetspot.py raw/full-sweep-30 --fps 30
    analysis/sweetspot.py raw/full-sweep-30 --check raw/paced-smoke
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motion as mo  # noqa: E402
from aggregate import score_one  # noqa: E402


def decay(f: np.ndarray | float) -> np.ndarray | float:
    """Surviving IoU after drifting `f` object widths. Zero once the boxes stop touching."""
    return np.maximum(0.0, (1 - f) / (1 + f))


def load(run_dir: str) -> list[dict]:
    return [score_one(p) for p in sorted(Path(run_dir).glob("*.json")) if p.stem != "manifest"]


def predict(per: list[dict], fps: float, k: float, mot: dict) -> list[dict]:
    return [r | {"pred": r["mean_iou"] * decay(mot[r["seq"]] * r["ms_p50"] * fps / 1000 * k)}
            for r in per]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("parity", help="run dir measured WITHOUT --fps (quality + latency per arm)")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--k", type=float, default=1.0, help="lag multiplier; --check fits it")
    ap.add_argument("--check", help="paced run dir: fit k and report the residual")
    args = ap.parse_args()

    per = load(args.parity)
    assert not any(r["fps_stream"] for r in per), f"{args.parity} is already paced"
    mot = {s: mo.features(s)["motion"] for s in {r["seq"] for r in per}}
    k = args.k

    if args.check:
        obs = {(r["arm"], r["seq"]): r["mean_iou"] for r in load(args.check)}
        assert obs, f"nothing in {args.check}"
        have = [r for r in per if (r["arm"], r["seq"]) in obs]
        assert have, "no arm/seq pair in common with the parity run"
        # one-dimensional fit, so a grid is cheaper to read than an optimiser and cannot diverge
        grid = np.arange(0.5, 3.01, 0.05)
        err = [np.mean([(p["pred"] - obs[(p["arm"], p["seq"])]) ** 2
                        for p in predict(have, args.fps, g, mot)]) for g in grid]
        k = float(grid[int(np.argmin(err))])
        print(f"k ajustado = {k:.2f} sobre {len(have)} pares, RMSE {np.sqrt(min(err)):.3f}")
        print(f"{'arm':11s} {'seq':13s} {'anch/f':>7s} {'ms':>7s} {'pred':>7s} {'obs':>7s} {'d':>7s}")
        for p in sorted(predict(have, args.fps, k, mot), key=lambda r: (r["arm"], r["seq"])):
            o = obs[(p["arm"], p["seq"])]
            print(f"{p['arm']:11s} {p['seq']:13s} {mot[p['seq']]:7.4f} {p['ms_p50']:7.1f} "
                  f"{p['pred']:7.3f} {o:7.3f} {p['pred'] - o:+7.3f}")

    pred = predict(per, args.fps, k, mot)
    arms = sorted({r["arm"] for r in pred})
    print(f"\nfps {args.fps:g}, k {k:.2f}: mIoU de paridad contra mIoU predicho en stream")
    print(f"{'arm':11s} {'n':>3s} {'ms p50':>7s} {'retraso f':>10s} "
          f"{'paridad':>8s} {'predicho':>9s} {'coste':>7s}")
    for a in arms:
        g = [r for r in pred if r["arm"] == a]
        ms = float(np.median([r["ms_p50"] for r in g]))
        par, pr = np.median([r["mean_iou"] for r in g]), np.median([r["pred"] for r in g])
        print(f"{a:11s} {len(g):3d} {ms:7.1f} {ms * args.fps / 1000 * k:10.1f} "
              f"{par:8.3f} {pr:9.3f} {pr - par:+7.3f}")

    # the point of the whole file: the best arm is not the same arm for every clip
    print(f"\nmejor brazo por clip\n{'seq':13s}{'anch/f':>8s}  {'paridad':<17s}{'stream':<17s}")
    rows = sorted({r["seq"] for r in pred}, key=lambda s: -mot[s])
    for s in rows:
        g = [r for r in pred if r["seq"] == s]
        bp = max(g, key=lambda r: r["mean_iou"])
        bs = max(g, key=lambda r: r["pred"])
        print(f"{s:13s}{mot[s]:8.4f}  {bp['arm']:<11s}{bp['mean_iou']:5.3f} "
              f"{bs['arm']:<11s}{bs['pred']:5.3f}")
    won = [max((r for r in pred if r["seq"] == s), key=lambda r: r["pred"])["arm"] for s in rows]
    print("\nveces que gana cada brazo en stream: "
          + ", ".join(f"{a} {won.count(a)}" for a in arms if won.count(a)))


if __name__ == "__main__":
    main()
