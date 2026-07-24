#!/usr/bin/env python3
"""P5.21 proof deliverables. Reproducible from runs/p521/*/results.json.

Two figures:
  proof/p521_drift_reinforcement.png  -- the negative, viewed: plain HOLDS car10 while the ROI
                                         re-anchor cropped a drifted box and lost the track (0.0);
                                         + the single b-side win (car14, ROI recovers a plain-lost car).
  proof/p521_per_seq_iou.png          -- per-seq final-IoU plain-vs-ROI scatter (y=x = tie), the 4
                                         discordants labelled, PASS threshold 0.25. The numbers.

Run: .venv-ft/bin/python make_proof.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

HERE = Path(__file__).parent
RUNS = HERE / "runs" / "p521"
PROOF = HERE / "proof"
PROOF.mkdir(exist_ok=True)


def _load():
    plain, roi = {}, {}
    for p in sorted(RUNS.glob("*/results.json")):
        if p.parent.name.startswith("pilot"):
            continue
        r = json.loads(p.read_text())
        (plain if r["arm"] == "plain" else roi)[r["seq"]] = r
    return plain, roi


def fig_drift():
    panels = [
        ("plain_car10", "Arm A plain: HOLDS the car (IoU 0.86)"),
        ("roi_car10", "Arm B ROI: drift-reinforced -> track LOST (IoU 0.0)\n"
                      "re-anchor cropped a drifted box, grounded off-target"),
        ("roi_car14", "Arm B ROI: the one win -- recovers a car\nArm A lost (IoU 0.71 vs 0.0)"),
    ]
    fig, axs = plt.subplots(1, 3, figsize=(19, 4.3))
    for ax, (cell, cap) in zip(axs, panels):
        ax.imshow(mpimg.imread(RUNS / cell / "final_overlay.png"))
        ax.axis("off")
        ax.set_title(cap, fontsize=10.5, fontweight="bold")
    fig.suptitle("P5.21  ROI re-anchor carry vs plain SAM2 carry  -  green = GT, red = predicted "
                 "(absent red = track lost)\n"
                 "the pre-registered drift-reinforcement failure fired: ROI-carry is net-negative "
                 "(c=3 > b=1), it does NOT beat plain carry",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    out = PROOF / "p521_drift_reinforcement.png"
    fig.savefig(out, dpi=115)
    plt.close(fig)
    print("wrote", out)


def fig_per_seq():
    plain, roi = _load()
    verd = json.loads((RUNS / "verdict.json").read_text())
    seqs = sorted(set(plain) & set(roi))
    fig, ax = plt.subplots(figsize=(9.2, 8.4))
    ax.plot([0, 1], [0, 1], "--", color="#888", lw=1, label="tie (y = x)")
    ax.axhline(0.25, color="#c44", lw=0.8, ls=":", alpha=0.6)
    ax.axvline(0.25, color="#c44", lw=0.8, ls=":", alpha=0.6)
    drop_k = 0                                     # stagger the c-side labels (all at y=0)
    for s in seqs:
        px, ry = plain[s]["final_iou"], roi[s]["final_iou"]
        pp, rr = plain[s]["pass"], roi[s]["pass"]
        disc = pp != rr
        color = ("#2a9d8f" if (rr and not pp) else "#c1121f" if (pp and not rr)
                 else "#bbb" if px == ry else "#4a6fa5")
        ax.scatter(px, ry, s=90 if disc else 45, color=color,
                   edgecolor="black" if disc else "none", zorder=3, lw=1.1)
        if disc:
            tag = s + ("  (drift-reinf)" if roi[s]["drift_reinforced"] else "")
            if pp and not rr:                      # c-side, sits at y=0 -> stack labels upward
                ax.annotate(tag, (px, ry), fontsize=8.5, fontweight="bold", color="#c1121f",
                            xytext=(-4, 22 + 20 * drop_k), textcoords="offset points",
                            ha="right", arrowprops=dict(arrowstyle="-", color="#c1121f", lw=0.7))
                drop_k += 1
            else:                                  # b-side win
                ax.annotate(tag, (px, ry), fontsize=8.5, fontweight="bold", color="#2a9d8f",
                            xytext=(8, 6), textcoords="offset points")
    ax.set_xlabel("Arm A plain-carry final-frame IoU vs GT", fontsize=11)
    ax.set_ylabel("Arm B ROI-carry final-frame IoU vs GT", fontsize=11)
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.03, 1.03)
    ax.set_title(f"P5.21 per-sequence carry outcome (n={verd['n_pairs']}, "
                 f"n_eff={verd['n_effective']} distinct sources)\n"
                 f"plain {verd['plain_pass']}/{verd['n_pairs']}  vs  "
                 f"ROI {verd['roi_pass']}/{verd['n_pairs']}    "
                 f"b={verd['b']} c={verd['c']}  p={verd['p_deflated']:.3g}  -> TIE "
                 f"(ROI net-negative)", fontsize=11.5, fontweight="bold")
    ax.legend(loc="upper center", fontsize=9)
    ax.text(0.02, 0.97, "above y=x: ROI better\nbelow: ROI worse (drift)",
            transform=ax.transAxes, fontsize=9, va="top", style="italic", color="#555")
    fig.tight_layout()
    out = PROOF / "p521_per_seq_iou.png"
    fig.savefig(out, dpi=125)
    plt.close(fig)
    # ponytail: cheap sanity -- the figure headline must match the registry counts
    assert (verd["b"], verd["c"]) == (1, 3), "verdict b/c drifted"
    assert verd["plain_pass"] == 28 and verd["roi_pass"] == 26, "pass counts drifted"
    print("wrote", out)


if __name__ == "__main__":
    fig_drift()
    fig_per_seq()
