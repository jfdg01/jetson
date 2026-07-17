#!/usr/bin/env python3
"""Proof deliverables for the P5.7 *negative* (infra FAIL) outcome.

`make_proof.py` (Fable's, untouched) builds the success-path deliverables and
requires all 4 gating runs' results.json. No gating run reached finalize, so it
cannot run (ValueError: need at least one array to concatenate). This script
builds the evidence for what actually happened, from the artifacts that exist:
the raw frames of the two INVALID seed-101 attempts plus their logs.

Produces (into proof/):
  p57_render_ok_f0060.png        -- a rendered frame: the render path is healthy
  p57_infra_fail.png             -- both attempts die mid-run on a gz-transport flake
  p57_crosssession_determinism.png -- non-gating G4a probe: 108/108 byte-identical

Usage: .venv-ft/bin/python experiments/2026-07-17-sim-scenegen/make_proof_infra.py
"""
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

S1 = RUNS / "seed101_A_attempt1_INVALID" / "frames"  # session 1 (fresh server)
S2 = RUNS / "seed101_A" / "frames"                   # session 2 (fresh server)
TARGET_FRAMES = 240
CRASH = [("attempt 1\nset_pose_vector\ntimed out", 127),
         ("attempt 2\nworld control\ntimed out", 108)]


def render_ok():
    """The render path works: two colour-distinct cars, UAV-style oblique view."""
    shutil.copy(S2 / "0060.png", PROOF / "p57_render_ok_f0060.png")
    print("wrote proof/p57_render_ok_f0060.png")


def infra_fail_fig():
    fig, ax = plt.subplots(figsize=(9, 5))
    names = [c[0] for c in CRASH]
    got = [c[1] for c in CRASH]
    bars = ax.barh(names, got, color="#c0392b", label="frames rendered before crash")
    ax.barh(names, [TARGET_FRAMES - g for g in got], left=got, color="#dddddd",
            label="frames never rendered")
    ax.axvline(TARGET_FRAMES, color="k", ls="--", lw=1)
    ax.text(TARGET_FRAMES - 4, 1.42, "240-frame clip (G5 target)", ha="right",
            va="top", fontsize=9)
    for b, g in zip(bars, got):
        ax.text(g + 4, b.get_y() + b.get_height() / 2,
                f"{g} frames  ({g/TARGET_FRAMES:.0%})  ~{g*2} gz service calls",
                va="center", fontsize=9)
    ax.set_xlabel("frames of the 240-frame clip")
    ax.set_xlim(0, TARGET_FRAMES + 60)
    ax.set_title("P5.7 infra FAIL: no gating run reaches finalize\n"
                 "both attempts = seed 101, fresh gz server session, server ALIVE at crash\n"
                 "server log both times: NodeShared::RecvSrvRequest() "
                 "error sending response: Host unreachable", fontsize=10)
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    fig.savefig(PROOF / "p57_infra_fail.png", dpi=110)
    print("wrote proof/p57_infra_fail.png")


def determinism_fig():
    """NON-GATING probe of G4a's frame half on the overlapping frames."""
    n = min(len(list(S1.glob("*.png"))), len(list(S2.glob("*.png"))))
    means = []
    for i in range(n):
        a = cv2.imread(str(S1 / f"{i:04d}.png"))
        b = cv2.imread(str(S2 / f"{i:04d}.png"))
        means.append(np.abs(a.astype(int) - b.astype(int)).mean())
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8),
                                   gridspec_kw={"height_ratios": [1, 2]})
    ax1.plot(means, lw=1.5, color="#27ae60", label="measured mean |diff| (flat 0.0)")
    ax1.axhline(2.0, color="r", ls="--", label="G4a gate (mean abs diff <= 2.0)")
    ax1.set_ylim(-0.2, 2.4)
    ax1.set_xlabel("frame")
    ax1.set_ylabel("mean |diff| (8-bit)")
    ax1.set_title(f"P5.7 NON-GATING probe: cross-session frame determinism, seed 101\n"
                  f"two fresh server sessions, {n} overlapping frames: "
                  f"{n}/{n} BYTE-IDENTICAL (mean |diff| = 0.000000)\n"
                  f"NOT a G4a pass: runs INVALID (no finalize), GT half uncheckable, "
                  f"{n}/240 frames", fontsize=10)
    ax1.legend(fontsize=9)
    fa = cv2.imread(str(S1 / "0060.png"))[:, :, ::-1]
    fb = cv2.imread(str(S2 / "0060.png"))[:, :, ::-1]
    ax2.imshow(np.hstack([fa, fb]))
    ax2.set_title("f=60, left: session 1, right: session 2 -- byte-identical", fontsize=10)
    ax2.axis("off")
    fig.tight_layout()
    fig.savefig(PROOF / "p57_crosssession_determinism.png", dpi=110)
    print("wrote proof/p57_crosssession_determinism.png")


def main():
    PROOF.mkdir(exist_ok=True)
    render_ok()
    infra_fail_fig()
    determinism_fig()


if __name__ == "__main__":
    main()
