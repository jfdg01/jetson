#!/usr/bin/env python
"""P5.12 proof deliverables (reproducible from runs/*). Writes proof/*.png:

  p511_crossing_traces.png   per-bank-cell recorded GT-GT IoU trace, occlusion
                             window shaded, prompt frame marked (numbers proof)
  p511_gate_grid.png         gate x cell PASS grid from the same grader the
                             verdict uses (numbers proof)
  p511_occlusion_montage.png crossing-peak overlay crop per bank cell (visual
                             proof the designed occlusion rendered)

Skips missing cells; needs >= 1 recorded bank cell.
"""
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("verdict_p512", HERE / "verdict_p512.py")
vd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vd)
sg = vd.sg

PROOF = HERE / "proof"
PROOF.mkdir(exist_ok=True)


def load_cells():
    cells = []
    for run, seed in vd.BANK_RUNS:
        d = HERE / "runs" / run
        if not (d / "results.json").exists():
            continue
        recs = [json.loads(l) for l in open(d / "gt.jsonl")]
        cells.append((run, seed, d, recs))
    return cells


def fig_traces(cells):
    fig, axes = plt.subplots(3, 4, figsize=(16, 9), sharex=True, sharey=True)
    for ax, (run, seed, d, recs) in zip(axes.flat, cells):
        iou = [sg._iou2d(r["objs"][0]["bbox"], r["objs"][1]["bbox"]) for r in recs]
        occ = [r["objs"][0].get("occl", 0.0) for r in recs]
        f = np.arange(len(iou))
        ax.fill_between(f, 0, 1, where=np.array(occ) >= 0.50,
                        color="tab:orange", alpha=0.25, label="occl >= 0.5")
        ax.plot(f, iou, lw=1.2, color="tab:blue", label="GT-GT IoU")
        ax.axvline(vd.PROMPT_F, color="k", ls="--", lw=0.8)
        ax.axhline(0.20, color="tab:green", ls=":", lw=0.8)
        ax.axhline(0.15, color="tab:red", ls=":", lw=0.8)
        ax.set_ylim(0, 0.6)
        ax.set_title(f"{run} (seed {seed})", fontsize=9)
    for ax in axes.flat[len(cells):]:
        ax.axis("off")
    axes.flat[0].legend(fontsize=7, loc="upper right")
    fig.suptitle("P5.12 bank v2.1: recorded GT-GT IoU per clip "
                 "(shaded = white occluded >= 50%; dashed = prompt f150; "
                 "dotted green/red = peak floor 0.20 / tail cap 0.15)")
    fig.tight_layout()
    fig.savefig(PROOF / "p511_crossing_traces.png", dpi=120)
    plt.close(fig)


def fig_gates(cells):
    gates = ["g0", "g1", "g2c", "g3", "g5", "g6c", "g8", "g9"]
    rows, names = [], []
    for run, seed, d, recs in cells:
        g = vd.grade_run(run, seed, is_bank=True)
        rows.append([1 if g[k] else 0 for k in gates])
        names.append(f"{run}/{seed}")
    m = np.array(rows)
    fig, ax = plt.subplots(figsize=(7, 0.5 * len(rows) + 2))
    ax.imshow(m, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(gates)), [g.upper() for g in gates])
    ax.set_yticks(range(len(names)), names, fontsize=8)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            ax.text(j, i, "P" if m[i, j] else "F", ha="center", va="center",
                    fontsize=8)
    ax.set_title(f"P5.12 gate grid ({int(m.all(axis=1).sum())}/{len(rows)} "
                 "cells pass all)")
    fig.tight_layout()
    fig.savefig(PROOF / "p511_gate_grid.png", dpi=120)
    plt.close(fig)


def fig_montage(cells):
    fig, axes = plt.subplots(3, 4, figsize=(16, 9))
    for ax, (run, seed, d, recs) in zip(axes.flat, cells):
        r = json.load(open(d / "results.json"))
        xf = r["v2_xpeak_pred_f"]
        img = cv2.imread(str(d / f"overlay_f{xf:04d}.png"))
        assert img is not None, f"{run}: missing crossing-peak overlay f{xf}"
        # crop around the two boxes with margin
        boxes = [o["bbox"] for o in recs[xf]["objs"] if o["bbox"]]
        x1 = int(min(b[0] for b in boxes)) - 120
        y1 = int(min(b[1] for b in boxes)) - 90
        x2 = int(max(b[2] for b in boxes)) + 120
        y2 = int(max(b[3] for b in boxes)) + 90
        h, w = img.shape[:2]
        crop = img[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
        ax.imshow(crop[:, :, ::-1])
        ax.set_title(f"{run} seed {seed} f{xf} "
                     f"IoU {r['v2_xpeak_pred_iou']:.2f}", fontsize=9)
        ax.axis("off")
    for ax in axes.flat[len(cells):]:
        ax.axis("off")
    fig.suptitle("P5.12 bank v2.1: crossing-peak overlay per clip "
                 "(blue occluder in front of white target = designed occlusion)")
    fig.tight_layout()
    fig.savefig(PROOF / "p511_occlusion_montage.png", dpi=120)
    plt.close(fig)


def main():
    cells = load_cells()
    if not cells:
        print("no recorded bank cells under runs/ -- nothing to plot")
        sys.exit(1)
    fig_traces(cells)
    fig_gates(cells)
    fig_montage(cells)
    print(f"wrote 3 figures to {PROOF} from {len(cells)} cells")


if __name__ == "__main__":
    main()
