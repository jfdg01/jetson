#!/usr/bin/env python3
"""make_proof.py -- EXP-4 thesis figure, rebuilt from runs/exp4/results.json.

One figure, two panels, because the interesting thing is that the two panels disagree:

    left  per-target IoU, C (MODE 2 native crop) vs A (deployed 960 control)
    right hit@0.5 and mean IoU per arm

    .venv-ft/bin/python experiments/2026-07-26-crop-mode/make_proof.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RUN = Path("experiments/2026-07-26-crop-mode/runs/exp4/results.json")
OUT = Path("experiments/2026-07-26-crop-mode/proof/exp4-arms.png")
LABEL = {"A": "A 960/512\n(deployed)", "B": "B 1920/1024",
         "C": "C 1920/512\n(MODE 2)", "D": "D 960/256\n(upscaled)"}


def main():
    res = json.loads(RUN.read_text())
    per, summ, tests = res["per"], res["summary"], res["tests"]
    order = sorted(per, key=lambda r: r["footprint_px"])
    x = range(len(order))

    fig, (ax, bx) = plt.subplots(1, 2, figsize=(13, 4.6), width_ratios=[1.7, 1])
    for arm, col, mk in (("A", "tab:red", "o"), ("C", "tab:blue", "s")):
        ax.plot(x, [r["arms"][arm]["iou"] for r in order], mk + "-", color=col,
                label=f"{arm} {'deployed 960 crop' if arm == 'A' else 'MODE 2 native crop'}",
                ms=5, lw=1.2)
    ax.axhline(0.5, color="k", ls=":", lw=1, label="hit@0.5")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{r['footprint_px']:.0f}" for r in order], fontsize=6,
                       rotation=90)
    ax.set_xlabel("target footprint in the 1920 frame (px), sorted")
    ax.set_ylabel("IoU vs GT")
    cva = tests["C_vs_A"]
    ax.set_title(f"per-target IoU, n={res['n']}  |  C vs A: b={cva['b']} c={cva['c']} "
                 f"p={cva['p_mcnemar']:.4g}")
    ax.legend(fontsize=8, loc="lower right")
    ax.set_ylim(-0.03, 1.03)
    ax.grid(alpha=0.3)

    arms = list(LABEL)
    w = 0.38
    bx.bar([i - w / 2 for i in range(len(arms))], [summ[a]["hit_rate"] for a in arms],
           w, label="hit@0.5", color="tab:blue")
    bx.bar([i + w / 2 for i in range(len(arms))], [summ[a]["mean_iou"] for a in arms],
           w, label="mean IoU", color="tab:orange")
    for i, a in enumerate(arms):
        bx.text(i - w / 2, summ[a]["hit_rate"] + .02, f"{summ[a]['hit_rate']:.2f}",
                ha="center", fontsize=7)
        bx.text(i + w / 2, summ[a]["mean_iou"] + .02, f"{summ[a]['mean_iou']:.2f}",
                ha="center", fontsize=7)
    bx.set_xticks(range(len(arms)))
    bx.set_xticklabels([LABEL[a] for a in arms], fontsize=7)
    cd = tests["C_vs_D"]
    bx.set_title(f"fed at {res['feed']}  |  C vs D: b={cd['b']} c={cd['c']} "
                 f"{res['verdict']}", fontsize=10)
    bx.set_ylim(0, 1.08)
    bx.legend(fontsize=8)
    bx.grid(alpha=0.3, axis="y")

    fig.tight_layout()
    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=150)
    print(OUT)


if __name__ == "__main__":
    main()
