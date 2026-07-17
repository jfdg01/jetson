#!/usr/bin/env python
"""P5.9 proof deliverables (reproducible from runs/* + the P5.8 record).

  proof/p59_beforeafter_kerb.png  P5.8 seed101 f0180 (clipped) vs P5.9 seed101
                                  f0180 (kerb-safe bands) -- the fix, visually
  proof/p59_kerb_calibration.png  the (s, lat) integrity sweep behind the bands
  proof/p59_bank_grid.png         all 12 bank clips at f0180 with GT overlays
  proof/p59_g6_teeth.png          G6 frag p10 per car per run vs the P5.8
                                  clipped reference -- the gate has teeth
"""
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
P58 = HERE.parent / "2026-07-17-scenegen-transport"
PROOF = HERE / "proof"
PROOF.mkdir(exist_ok=True)


def img(path):
    im = plt.imread(str(path))
    return im


def main():
    # 1. before/after
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.6))
    axes[0].imshow(img(P58 / "runs" / "seed101_A" / "overlay_f0180.png"))
    axes[0].set_title("P5.8 seed101 f0180 -- distractor lat 4.6-5.2 m,\n"
                      "clips the median kerb: two disconnected blobs (frag p10 0.666)")
    axes[1].imshow(img(HERE / "runs" / "seed101_A" / "overlay_f0180.png"))
    axes[1].set_title("P5.9 seed101 f0180 -- calibrated kerb-safe bands\n"
                      "(lat in [-5.0, +1.8], s <= 67.4): intact body (frag p10 >= 0.95 gate)")
    for ax in axes:
        ax.axis("off")
    fig.suptitle("P5.9 kerb-clipping fix: same seed, same frame index, fixed spawn bands")
    fig.tight_layout()
    fig.savefig(PROOF / "p59_beforeafter_kerb.png", dpi=110)
    plt.close(fig)

    # 2. calibration heatmap (design-time sweep, copied into proof for the record)
    shutil.copy(HERE / "curation" / "kerb_heatmap.png", PROOF / "p59_kerb_calibration.png")

    # 3. bank grid
    fig, axes = plt.subplots(4, 3, figsize=(15, 11))
    for i, ax in enumerate(axes.flat, start=1):
        run = HERE / "runs" / f"bank{i:02d}"
        ov = run / "overlay_f0180.png"
        ax.axis("off")
        if ov.exists():
            ax.imshow(img(ov))
            r = json.load(open(run / "results.json"))
            ax.set_title(f"bank{i:02d} (seed {i})  frag p10 "
                         f"{r['g6_frag_p10']['0']:.3f}/{r['g6_frag_p10']['1']:.3f}",
                         fontsize=9)
        else:
            ax.set_title(f"bank{i:02d}: MISSING", fontsize=9)
    fig.suptitle("P5.9 scene bank: 12 seeded clips, f0180 GT overlays "
                 "(kerb-safe bands, G6-gated)")
    fig.tight_layout()
    fig.savefig(PROOF / "p59_bank_grid.png", dpi=100)
    plt.close(fig)

    # 4. G6 teeth
    runs = [("seed101_A", 101), ("seed202_B", 202), ("seed303_C", 303),
            ("seed101_D", 101)] + [(f"bank{i:02d}", i) for i in range(1, 13)]
    labels, p10_0, p10_1 = [], [], []
    for run, seed in runs:
        rj = HERE / "runs" / run / "results.json"
        if not rj.exists():
            continue
        r = json.load(open(rj))
        labels.append(run)
        p10_0.append(r["g6_frag_p10"]["0"])
        p10_1.append(r["g6_frag_p10"]["1"])
    x = range(len(labels))
    fig, ax = plt.subplots(figsize=(13, 4.2))
    ax.bar([i - 0.2 for i in x], p10_0, width=0.4, label="id0 white")
    ax.bar([i + 0.2 for i in x], p10_1, width=0.4, label="id1 blue")
    ax.axhline(0.95, color="r", ls="--", lw=1, label="G6 gate (p10 >= 0.95)")
    ax.axhline(0.666, color="k", ls=":", lw=1,
               label="P5.8 seed101 blue (clipped): 0.666")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("frag p10 (largest-component fraction)")
    ax.set_ylim(0.5, 1.02)
    ax.legend(fontsize=8)
    ax.set_title("P5.9 G6 rendered-integrity gate across all 16 runs")
    fig.tight_layout()
    fig.savefig(PROOF / "p59_g6_teeth.png", dpi=110)
    plt.close(fig)
    print("proof written:", sorted(p.name for p in PROOF.iterdir()))


if __name__ == "__main__":
    main()
