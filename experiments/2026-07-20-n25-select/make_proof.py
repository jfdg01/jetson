#!/usr/bin/env python3
"""P5.18 proof deliverables (reproducible from runs/*/results.json):

  proof/pass_matrix.png       27 scenes x 2 legs outcome grid (the number
                              that gates: counts out of 26 in the title).
  proof/deliver_iou.png       per-cell delivery-quality metric vs the
                              0.25 / 0.10 floors, failing cells labelled.
  proof/deliver_headline.png  copy of the lowest-metric PASSING SWAP cell's
                              deliver.png (mechanical pick: worst pass, so
                              the headline is the least flattering success).

Usage: make_proof.py [--runs DIR]
"""
import json
import shutil
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
LEGS = ("WSEL", "SWAP")


def load(runs):
    scenes = json.loads((HERE / "scenes_p518.json").read_text())["scenes"]
    rows = []
    for sc in scenes:
        row = {"label": f"{sc['clip']}:{sc['f0']}", "gating": sc.get("gating")}
        for leg in LEGS:
            p = runs / f"DSC_{leg}_{sc['clip']}_{sc['f0']}" / "results.json"
            r = json.loads(p.read_text()) if p.exists() else None
            m = None
            if r:
                s = r["score"]
                m = (s.get("deliver_iou") if leg == "WSEL"
                     else s.get("deliver_iou_distractor"))
            row[leg] = {"ok": bool(r and r["pass"]), "metric": m,
                        "weak": r.get("swap_weak_pass") if r else None,
                        "reason": r["score"].get("reason") if r else "MISSING",
                        "dir": p.parent}
        rows.append(row)
    return rows


def fig_matrix(rows, out):
    fig, ax = plt.subplots(figsize=(6, 0.34 * len(rows) + 1.2))
    for y, row in enumerate(rows):
        for x, leg in enumerate(LEGS):
            c = row[leg]
            col = ("#2a9d2a" if c["ok"] else
                   "#e8a13a" if leg == "SWAP" and c["weak"] else "#c8382a")
            ax.add_patch(plt.Rectangle((x, y), 0.94, 0.94, color=col,
                                       alpha=1.0 if row["gating"] else 0.35))
        ax.text(-0.15, y + 0.5, row["label"] + ("" if row["gating"]
                else " (control)"), ha="right", va="center", fontsize=7)
    n = {leg: sum(r[leg]["ok"] for r in rows if r["gating"]) for leg in LEGS}
    ax.set_xlim(-3.2, 2.2)
    ax.set_ylim(len(rows), -0.3)
    ax.set_xticks([0.5, 1.5], LEGS)
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(f"P5.18 GT-free select, n=26 gating scenes/leg\n"
                 f"WSEL {n['WSEL']}/26   strengthened SWAP {n['SWAP']}/26"
                 f"   (bar 20/26; orange = weak-only SWAP)", fontsize=9)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig_iou(rows, out):
    fig, ax = plt.subplots(figsize=(9, 4))
    for x, leg in enumerate(LEGS):
        cells = [(r["label"], r[leg]) for r in rows if r["gating"]]
        for i, (lab, c) in enumerate(cells):
            m = -0.05 if c["metric"] is None else c["metric"]
            xx = x + (i - len(cells) / 2) * 0.028
            ax.scatter(xx, m, s=18,
                       c="#2a9d2a" if c["ok"] else "#c8382a", zorder=3)
            if not c["ok"]:
                ax.annotate(lab, (xx, m), fontsize=6, rotation=45,
                            textcoords="offset points", xytext=(2, 4))
    ax.axhline(0.25, ls="--", c="k", lw=0.8)
    ax.text(1.52, 0.255, "DIST_FLOOR 0.25", fontsize=7)
    ax.axhline(0.10, ls=":", c="gray", lw=0.8)
    ax.text(1.52, 0.105, "MATCH_FLOOR 0.10", fontsize=7)
    ax.set_xticks([0, 1], ["WSEL: deliver IoU vs target GT",
                           "SWAP: deliver IoU vs hand distractor GT"])
    ax.set_ylabel("IoU at delivery")
    ax.set_title("P5.18 delivery quality per gating cell "
                 "(red = leg FAIL; y=-0.05 = no delivery)", fontsize=9)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main():
    runs = Path(sys.argv[sys.argv.index("--runs") + 1]) \
        if "--runs" in sys.argv else HERE / "runs"
    proof = HERE / "proof"
    proof.mkdir(exist_ok=True)
    rows = load(runs)
    fig_matrix(rows, proof / "pass_matrix.png")
    fig_iou(rows, proof / "deliver_iou.png")
    # headline: worst passing SWAP cell's deliver.png
    passing = [(r["SWAP"]["metric"], r["SWAP"]["dir"]) for r in rows
               if r["gating"] and r["SWAP"]["ok"]
               and r["SWAP"]["metric"] is not None]
    if passing:
        src = min(passing)[1] / "deliver.png"
        if src.exists():
            shutil.copy(src, proof / "deliver_headline.png")
    for f in proof.glob("*.png"):
        assert f.stat().st_size > 20_000, f"{f} suspiciously small"
        print(f)


if __name__ == "__main__":
    main()
