"""P5.3 proof figures from runs/*/results.json (reproducible, DoD-7).

    .venv-ft/bin/python experiments/2026-07-14-multi-candidate-select/make_proof.py

Writes proof/p53_pass_grid.png (leg x scene outcome grid, selection labelled)
and proof/p53_deliver_iou.png (delivered-box IoU vs target GT, WSEL vs CSEL --
the late-binding-vs-stale comparison at the SAME delivery frame).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
LEGS = ["WSEL", "SWAP", "CSEL"]


def load():
    runs = {}
    for p in sorted((HERE / "runs").glob("*/results.json")):
        r = json.loads(p.read_text())
        sid = f"{r['scene']['clip']}:{r['scene']['f0']}"
        runs[(r["leg"], sid)] = r
    scenes = sorted({s for (_, s) in runs})
    return runs, scenes


def pass_grid(runs, scenes, out):
    fig, ax = plt.subplots(figsize=(1.8 * len(scenes) + 2, 3.2))
    for i, leg in enumerate(LEGS):
        for j, sid in enumerate(scenes):
            r = runs.get((leg, sid))
            if r is None:
                ax.text(j, i, "--", ha="center", va="center")
                continue
            ok = r["pass"]
            ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1,
                                       color="#7fc97f" if ok else "#f4a582"))
            sel = r["score"].get("selection")
            lab = "PASS" if ok else "FAIL"
            if leg != "CSEL":
                lab += f"\nsel={sel or 'NO_MATCH'}"
            lab += f"\niou={r['score'].get('deliver_iou', 0):.2f}"
            ax.text(j, i, lab, ha="center", va="center", fontsize=8)
    ax.set_xticks(range(len(scenes)), scenes)
    ax.set_yticks(range(len(LEGS)), LEGS)
    ax.set_xlim(-.5, len(scenes) - .5)
    ax.set_ylim(len(LEGS) - .5, -.5)
    ax.set_title("P5.3 outcome grid (deliver_iou = delivered box vs target GT)")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print("wrote", out)


def deliver_iou(runs, scenes, out):
    x = np.arange(len(scenes))
    fig, ax = plt.subplots(figsize=(1.6 * len(scenes) + 2, 3.4))
    for k, (leg, off, c) in enumerate([("WSEL", -.18, "#2b8cbe"),
                                       ("CSEL", .18, "#969696")]):
        v = [runs.get((leg, s), {}).get("score", {}).get("deliver_iou", 0.0)
             for s in scenes]
        ax.bar(x + off, v, .34, label=leg, color=c)
    ax.axhline(0.25, ls="--", c="k", lw=1, label="lock threshold 0.25")
    ax.set_xticks(x, scenes)
    ax.set_ylabel("IoU at delivery vs target GT")
    ax.set_title("Late-binding select (WSEL) vs stale raw box (CSEL), same deliver frame")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print("wrote", out)


if __name__ == "__main__":
    runs, scenes = load()
    assert runs, "no runs/*/results.json yet"
    (HERE / "proof").mkdir(exist_ok=True)
    pass_grid(runs, scenes, HERE / "proof" / "p53_pass_grid.png")
    deliver_iou(runs, scenes, HERE / "proof" / "p53_deliver_iou.png")
