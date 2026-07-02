"""E3 AerialMind leg: does distractor density degrade Phase 0 zero-shot carry?

Per track, distractor density = mean number of *same-size* (box area within +-50%)
GT boxes whose center is within 3x the target's box diagonal, per labeled frame.
Split tracks at the top-quartile density; compare IoU@0.25 and ID-consistency of
the distractor-heavy quartile vs the rest. Pure analysis, no tracking runs.

GT labels are `class tid x y w h`, NORMALIZED and TOP-LEFT encoded (the documented
Phase 0 gotcha -- x,y is the top-left corner, not the center). Distances are in
normalized coords (x by width, y by height): a density proxy, not metric meters.

    .venv-ft/bin/python experiments/2026-07-02-twin-distractor/distractor_density.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
PER_TRACK = REPO / "experiments/2026-07-01-temporal-acquire-carry/runs/phase0-zeroshot-carry/per_track.csv"
LABELS = REPO / "data/AerialMind/labels_with_ids"


def load_seq(seq: str) -> dict[str, np.ndarray]:
    """frame stem -> (N,5) array of [tid, cx, cy, w, h] (center from top-left)."""
    out = {}
    for txt in (LABELS / seq).glob("*.txt"):
        rows = []
        for line in txt.read_text().splitlines():
            p = line.split()
            if len(p) < 6:
                continue
            tid, x, y, w, h = float(p[1]), *map(float, p[2:6])
            rows.append((tid, x + w / 2, y + h / 2, w, h))  # top-left -> center
        if rows:
            out[txt.stem] = np.array(rows)
    return out


def track_density(frames: dict, tid: float) -> float:
    """mean # same-size boxes within 3x target diagonal, over frames holding tid."""
    per_frame = []
    for arr in frames.values():
        tgt = arr[arr[:, 0] == tid]
        if len(tgt) == 0:
            continue
        cx, cy, w, h = tgt[0, 1:]
        diag = np.hypot(w, h)
        others = arr[arr[:, 0] != tid]
        if len(others) == 0:
            per_frame.append(0)
            continue
        area_o = others[:, 3] * others[:, 4]
        area_t = w * h
        same_size = (area_o >= 0.5 * area_t) & (area_o <= 1.5 * area_t)
        near = np.hypot(others[:, 1] - cx, others[:, 2] - cy) <= 3 * diag
        per_frame.append(int((same_size & near).sum()))
    return float(np.mean(per_frame)) if per_frame else 0.0


def main() -> None:
    pt = pd.read_csv(PER_TRACK)
    cache: dict[str, dict] = {}
    dens = []
    for _, r in pt.iterrows():
        seq = str(r["seq"])
        if seq not in cache:
            cache[seq] = load_seq(seq)
        dens.append(track_density(cache[seq], float(r["tid"])))
    pt["density"] = dens

    q75 = pt["density"].quantile(0.75)
    heavy = pt[pt["density"] >= q75]
    rest = pt[pt["density"] < q75]
    print(f"top-quartile density threshold (>= {q75:.3f}):\n")
    print(f"{'quartile':<16}{'n':>4}{'density':>9}{'IoU@0.25':>10}{'ID-consist':>12}")
    for name, g in [("distractor-heavy", heavy), ("rest", rest)]:
        print(f"{name:<16}{len(g):>4}{g['density'].mean():>9.2f}"
              f"{g['iou_at_25'].mean():>10.3f}{g['id_consistency'].mean():>12.3f}")
    d_iou = rest["iou_at_25"].mean() - heavy["iou_at_25"].mean()
    d_id = rest["id_consistency"].mean() - heavy["id_consistency"].mean()
    print(f"\nheavy quartile delta vs rest: IoU@0.25 {-d_iou:+.3f}, "
          f"ID-consistency {-d_id:+.3f} (negative = heavy is worse)")


if __name__ == "__main__":
    main()
