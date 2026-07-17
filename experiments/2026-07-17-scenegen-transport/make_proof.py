#!/usr/bin/env python3
"""Proof deliverables for P5.8 from runs/. Reproducible from the run artifacts.

Produces (into proof/):
  p58_overlay_grid.png    -- 4 runs x 3 mid-run GT-overlay frames (the visual gate V)
  p58_determinism.png     -- per-frame mean abs pixel diff, seed101_A vs seed101_D,
                             plus the worst frame pair side by side
  p58_transport_fix.png   -- the before/after of the campaign: P5.7 CLI transport
                             (died 127/240 and 108/240, 1.48 fps) vs P5.8 persistent
                             proxy (frames completed + fps + retries per run)
  p58_seed101_overlay.mp4 -- copied overlay clip of seed101_A (behaviour deliverable)

Usage: .venv-ft/bin/python experiments/2026-07-17-scenegen-transport/make_proof.py
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

# P5.7 baseline (cited from experiments/2026-07-17-sim-scenegen/README.md Results:
# both seed101_A attempts, ephemeral `gz service` CLI transport, fresh sessions).
P57_ATTEMPT_FRAMES = [127, 108]
P57_FPS = 1.48


def overlay_grid():
    tiles = []
    for r in GATING:
        pngs = sorted((RUNS / r).glob("overlay_f*.png"))
        row = [cv2.resize(cv2.imread(str(p)), (426, 240)) for p in pngs[:3]]
        if row:
            tiles.append(np.hstack(row))
    grid = np.vstack(tiles)
    y = 0
    for r in GATING:
        cv2.putText(grid, r, (8, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 255, 255), 2)
        y += 240
    cv2.imwrite(str(PROOF / "p58_overlay_grid.png"), grid)
    print("wrote proof/p58_overlay_grid.png")


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
    ax1.set_title(f"P5.8 cross-session determinism: {a} vs {b} (same seed, "
                  f"fresh server) -- worst frame {worst_i}: {worst:.3f}")
    ax1.legend()
    fa = cv2.imread(str(RUNS / a / "frames" / f"{worst_i:04d}.png"))[:, :, ::-1]
    fb = cv2.imread(str(RUNS / b / "frames" / f"{worst_i:04d}.png"))[:, :, ::-1]
    ax2.imshow(np.hstack([fa, fb]))
    ax2.set_title(f"worst frame pair f={worst_i} (left: {a}, right: {b})")
    ax2.axis("off")
    fig.tight_layout()
    fig.savefig(PROOF / "p58_determinism.png", dpi=110)
    print("wrote proof/p58_determinism.png")


def transport_fix_fig():
    labels, frames, fps, colors = [], [], [], []
    for j, f in enumerate(P57_ATTEMPT_FRAMES):
        labels.append(f"P5.7 CLI att.{j + 1}\n(ephemeral nodes)")
        frames.append(f)
        fps.append(P57_FPS)
        colors.append("#c0392b")
    retr_note = []
    for r in GATING:
        res = json.loads((RUNS / r / "results.json").read_text())
        labels.append(f"P5.8 {r}\n(persistent proxy)")
        frames.append(res["frames"])
        fps.append(res["fps_wall"])
        colors.append("#27ae60")
        retr_note.append(f"{r}: retries={res['g0_retries_pose'] + res['g0_retries_step']} "
                         f"lost={res['g0_response_lost']} restarts={res['g0_proxy_restarts']}")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    x = np.arange(len(labels))
    ax1.bar(x, frames, color=colors)
    ax1.axhline(240, color="k", ls="--", lw=1, label="240-frame clip")
    ax1.set_xticks(x, labels, rotation=30, ha="right", fontsize=8)
    ax1.set_ylabel("frames completed")
    ax1.set_title("run completion: CLI transport vs persistent proxy")
    ax1.legend()
    ax2.bar(x, fps, color=colors)
    ax2.set_xticks(x, labels, rotation=30, ha="right", fontsize=8)
    ax2.set_ylabel("frames/s wall")
    ax2.set_title("generation throughput")
    fig.suptitle("P5.8 transport fix -- " + "; ".join(retr_note), fontsize=8)
    fig.tight_layout()
    fig.savefig(PROOF / "p58_transport_fix.png", dpi=110)
    print("wrote proof/p58_transport_fix.png")


def main():
    PROOF.mkdir(exist_ok=True)
    overlay_grid()
    determinism_fig()
    transport_fix_fig()
    src = RUNS / "seed101_A" / "overlay.mp4"
    if src.exists():
        shutil.copy(src, PROOF / "p58_seed101_overlay.mp4")
        print("wrote proof/p58_seed101_overlay.mp4")
    else:
        print("WARN: seed101_A/overlay.mp4 missing -- clip deliverable not copied")


if __name__ == "__main__":
    main()
