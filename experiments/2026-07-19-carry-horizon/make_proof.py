"""P5.15 proof figures, reproducible from runs/*/results.json.

  proof/p515_decay.png      per-clip IoU-vs-time decay curves, PLAIN arm,
                            one panel per category, ALIVE_IOU floor drawn.
  proof/p515_alive_grid.png per-clip x per-horizon ALIVE/dead/N/A grid,
                            PLAIN and MAINT side by side.
  proof/p515_arms.png       alive-count bars per horizon, PLAIN vs MAINT.

    .venv-ft/bin/python experiments/2026-07-19-carry-horizon/make_proof.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402

HERE = Path(__file__).resolve().parent
HORIZONS = ("8", "16", "24")
ALIVE_IOU = 0.25
FPS = 30.0


def category(clip: str) -> str:
    for cat in ("car", "boat", "person", "bike", "wakeboard"):
        if clip.startswith(cat):
            return cat
    return "other"


def load() -> dict:
    cells = {}
    for rj in sorted((HERE / "runs").glob("*/results.json")):
        r = json.loads(rj.read_text())
        if "INVALID" not in r:
            cells[(r["arm"], r["clip"])] = r
    return cells


def fig_decay(cells) -> None:
    cats = sorted({category(c) for (a, c) in cells if a == "PLAIN"})
    fig, axes = plt.subplots(1, len(cats), figsize=(4 * len(cats), 3.5),
                             sharey=True)
    axes = np.atleast_1d(axes)
    for ax, cat in zip(axes, cats):
        for (a, c), r in sorted(cells.items()):
            if a != "PLAIN" or category(c) != cat:
                continue
            t = [f / FPS for f, _, iv in r["trace"] if iv is not None]
            v = [iv for _, _, iv in r["trace"] if iv is not None]
            ax.plot(t, v, lw=1, alpha=0.8, label=c)
        ax.axhline(ALIVE_IOU, color="r", ls="--", lw=1)
        for h in (8, 16, 24):
            ax.axvline(h, color="grey", ls=":", lw=0.7)
        ax.set_title(cat)
        ax.set_xlabel("time (s)")
        ax.set_ylim(0, 1)
        ax.legend(fontsize=6)
    axes[0].set_ylabel("carried-box IoU vs GT")
    fig.suptitle("P5.15 PLAIN carry decay (red = alive floor 0.25; "
                 "dotted = horizons 8/16/24 s)")
    fig.tight_layout()
    fig.savefig(HERE / "proof" / "p515_decay.png", dpi=130)
    plt.close(fig)


def fig_grid(cells) -> None:
    clips = sorted({c for (_, c) in cells})
    arms = ("PLAIN", "MAINT")
    fig, ax = plt.subplots(figsize=(7, 0.32 * len(clips) + 1.5))
    for yi, clip in enumerate(clips):
        for ai, arm in enumerate(arms):
            r = cells.get((arm, clip))
            for hi, h in enumerate(HORIZONS):
                x = ai * (len(HORIZONS) + 1) + hi
                if r is None:
                    col, txt = "lightgrey", "?"
                else:
                    rec = r["horizons"][h]
                    if rec["na"]:
                        col, txt = "lightgrey", "N/A"
                    elif rec["alive"]:
                        col, txt = "#7fc97f", f"{rec['iou']:.2f}"
                    else:
                        col, txt = "#f4a4a4", f"{rec['iou']:.2f}"
                ax.add_patch(plt.Rectangle((x, yi), 1, 1, color=col))
                ax.text(x + 0.5, yi + 0.5, txt, ha="center", va="center",
                        fontsize=6)
    for ai, arm in enumerate(arms):
        for hi, h in enumerate(HORIZONS):
            ax.text(ai * (len(HORIZONS) + 1) + hi + 0.5, -0.6,
                    f"{arm[0]}{h}s", ha="center", fontsize=7)
    ax.set_yticks([i + 0.5 for i in range(len(clips))])
    ax.set_yticklabels(clips, fontsize=7)
    ax.set_xlim(-0.2, 2 * (len(HORIZONS) + 1))
    ax.set_ylim(len(clips), -1.2)
    ax.set_xticks([])
    ax.set_title("P5.15 alive grid (green = IoU>=0.25 at horizon; "
                 "P=PLAIN, M=MAINT)")
    fig.tight_layout()
    fig.savefig(HERE / "proof" / "p515_alive_grid.png", dpi=130)
    plt.close(fig)


def fig_arms(cells) -> None:
    fig, ax = plt.subplots(figsize=(5, 3.2))
    w = 0.35
    for ai, arm in enumerate(("PLAIN", "MAINT")):
        counts = []
        for h in HORIZONS:
            counts.append(sum(1 for (a, _), r in cells.items()
                              if a == arm and not r["horizons"][h]["na"]
                              and r["horizons"][h]["alive"]))
        xs = np.arange(len(HORIZONS)) + (ai - 0.5) * w
        bars = ax.bar(xs, counts, w, label=arm)
        ax.bar_label(bars, fontsize=8)
    ax.set_xticks(range(len(HORIZONS)))
    ax.set_xticklabels([f"{h} s" for h in HORIZONS])
    ax.set_ylabel("clips alive (of 25)")
    ax.set_ylim(0, 26)
    ax.axhline(18, color="r", ls="--", lw=1)
    ax.text(2.4, 18.3, "RQ-a floor (16 s)", color="r", fontsize=7)
    ax.legend()
    ax.set_title("P5.15 carry survival by horizon")
    fig.tight_layout()
    fig.savefig(HERE / "proof" / "p515_arms.png", dpi=130)
    plt.close(fig)


def main() -> None:
    (HERE / "proof").mkdir(exist_ok=True)
    cells = load()
    assert cells, "no runs/*/results.json yet"
    fig_decay(cells)
    fig_grid(cells)
    fig_arms(cells)
    print("wrote proof/p515_decay.png p515_alive_grid.png p515_arms.png")


if __name__ == "__main__":
    main()
