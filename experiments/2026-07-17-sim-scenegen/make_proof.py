#!/usr/bin/env python3
"""Proof deliverables for P5.7 from runs/. Reproducible from the run artifacts.

Produces (into proof/):
  p57_overlay_grid.png   -- 4 runs x 3 mid-run GT-overlay frames (the visual gate V)
  p57_determinism.png    -- per-frame mean abs pixel diff, seed101_A vs seed101_D,
                            plus the worst frame pair side by side
  p57_seed101_overlay.mp4-- copied overlay clip of seed101_A (behaviour deliverable)

Usage: .venv-ft/bin/python experiments/2026-07-17-sim-scenegen/make_proof.py
"""
import json
import shutil
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PROOF = HERE / "proof"
GATING = ["seed101_A", "seed202_B", "seed303_C", "seed101_D"]


def overlay_grid():
    tiles, labels = [], []
    for r in GATING:
        pngs = sorted((RUNS / r).glob("overlay_f*.png"))
        row = []
        for p in pngs[:3]:
            img = cv2.imread(str(p))
            row.append(cv2.resize(img, (426, 240)))
            labels.append(f"{r} {p.stem}")
        if row:
            tiles.append(np.hstack(row))
    grid = np.vstack(tiles)
    y = 0
    for i, r in enumerate(GATING):
        cv2.putText(grid, r, (8, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 255, 255), 2)
        y += 240
    cv2.imwrite(str(PROOF / "p57_overlay_grid.png"), grid)
    print("wrote proof/p57_overlay_grid.png")


def determinism_fig():
    a, b = "seed101_A", "seed101_D"
    n = json.loads((RUNS / a / "results.json").read_text())["frames"]
    means = []
    worst, worst_i = -1.0, 0
    for i in range(n):
        fa = cv2.imread(str(RUNS / a / "frames" / f"{i:04d}.png"))
        fb = cv2.imread(str(RUNS / b / "frames" / f"{i:04d}.png"))
        d = np.abs(fa.astype(int) - fb.astype(int)).mean()
        means.append(d)
        if d > worst:
            worst, worst_i = d, i
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8),
                                   gridspec_kw={"height_ratios": [1, 2]})
    ax1.plot(means, lw=1)
    ax1.axhline(2.0, color="r", ls="--", label="G4a gate (mean abs diff <= 2.0)")
    ax1.set_xlabel("frame")
    ax1.set_ylabel("mean |diff| (8-bit)")
    ax1.set_title(f"P5.7 cross-session determinism: {a} vs {b} (same seed, "
                  f"fresh server) -- worst frame {worst_i}: {worst:.3f}")
    ax1.legend()
    fa = cv2.imread(str(RUNS / a / "frames" / f"{worst_i:04d}.png"))[:, :, ::-1]
    fb = cv2.imread(str(RUNS / b / "frames" / f"{worst_i:04d}.png"))[:, :, ::-1]
    ax2.imshow(np.hstack([fa, fb]))
    ax2.set_title(f"worst frame pair f={worst_i} (left: {a}, right: {b})")
    ax2.axis("off")
    fig.tight_layout()
    fig.savefig(PROOF / "p57_determinism.png", dpi=110)
    print("wrote proof/p57_determinism.png")


def main():
    PROOF.mkdir(exist_ok=True)
    overlay_grid()
    determinism_fig()
    src = RUNS / "seed101_A" / "overlay.mp4"
    if src.exists():
        shutil.copy(src, PROOF / "p57_seed101_overlay.mp4")
        print("wrote proof/p57_seed101_overlay.mp4")
    else:
        print("WARN: seed101_A/overlay.mp4 missing -- clip deliverable not copied")


if __name__ == "__main__":
    main()
