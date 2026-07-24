#!/usr/bin/env python3
"""R-36 proof deliverables. Reproducible from runs/r36/.

Two figures:
  proof/r36_scarcity.png                   -- headline: 8/10 curated candidates single-target;
                                              the paired WSEL/SWAP outcome grid; the 3 McNemar reads.
  proof/r36_person13_swap_delivers_target.png -- the SWAP select failure viewed, with the
                                              mis-placed distractor GT the "look at it" audit caught.

Run: uv run --python ../../.venv-ft/bin/python make_proof.py   (or: .venv-ft/bin/python make_proof.py)
"""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrow
import matplotlib.image as mpimg

HERE = Path(__file__).parent
RUNS = HERE / "runs" / "r36"
PROOF = HERE / "proof"
PROOF.mkdir(exist_ok=True)


def fig_scarcity():
    cur = json.loads((RUNS / "bank" / "curation_r36_findings.json").read_text())
    verd = json.loads((RUNS / "verdict_r36.json").read_text())
    cands = cur["candidates"]
    usable = [c for c in cands if c.get("usable")]
    unusable = [c for c in cands if not c.get("usable")]

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(16, 7), gridspec_kw={"width_ratios": [1.15, 1]})

    # LEFT: curation outcome -- the headline scarcity, as a labelled color grid (imshow-robust)
    rows = [(c["clip"], False, str(c.get("reason", ""))) for c in unusable] + \
           [(c["clip"], True, str(c.get("reason", ""))) for c in usable]
    grid = np.array([[0.78, 0.27, 0.27] if not use else [0.91, 0.64, 0.24] for _, use, _ in rows])
    axL.imshow(grid[:, None, :], aspect="auto", extent=(0, 1, len(rows), 0))
    for i, (clip, use, reason) in enumerate(rows):
        tag = "USABLE-WEAK: " if use else "single-target: "
        axL.text(0.02, i + 0.5, f"{clip}  -  {tag}{reason[:40]}",
                 va="center", ha="left", fontsize=8.5, color="white" if not use else "black")
    axL.set_xlim(0, 1); axL.set_ylim(len(rows), 0)
    axL.set_xticks([]); axL.set_yticks([])
    axL.set_title(f"Curation of 10 fresh UAV123 candidates\n"
                  f"{cur['unusable_count']}/10 single-target (red)   |   "
                  f"{cur['usable_count']}/10 usable-weak (amber)",
                  fontsize=12, fontweight="bold")
    axL.set_xlabel("UAV123 follows one target -> two co-visible same-class candidates barely exist\n"
                   "the gating variable is scenes, not n", fontsize=9.5, style="italic")

    # RIGHT: paired WSEL/SWAP grid via imshow (green pass / red fail)
    pairs = verd["pairs"]
    cells = np.zeros((len(pairs), 2, 3))
    for i, p in enumerate(pairs):
        for j, ok in enumerate([p["wsel_pass"], p["swap_pass"]]):
            cells[i, j] = (0.16, 0.60, 0.53) if ok else (0.80, 0.27, 0.27)
    axR.imshow(cells, aspect="auto")
    for i, p in enumerate(pairs):
        for j, ok in enumerate([p["wsel_pass"], p["swap_pass"]]):
            axR.text(j, i, "P" if ok else "F", ha="center", va="center",
                     color="white", fontweight="bold", fontsize=10)
        if p["wsel_pass"] and not p["swap_pass"]:      # a discordant (b)
            axR.text(1.62, i, "* discordant (b)", va="center", ha="left", fontsize=8.5, color="#c44")
    axR.set_xticks([0, 1]); axR.set_xticklabels(["WSEL\n(maintain)", "SWAP\n(select)"], fontsize=10)
    axR.set_yticks(range(len(pairs)))
    axR.set_yticklabels([p["clip"] for p in pairs], fontsize=8.5)
    axR.set_xlim(-0.5, 2.6)
    axR.set_title(f"Paired maintain vs select per clip\n"
                  f"b={verd['b']} (maintain wins), c={verd['c']} (select wins) -> select never wins a pair",
                  fontsize=12, fontweight="bold")
    axR.set_xlabel("3 reads, all miss or fragile:\n"
                   "clean n=13 b=4 p=0.125  |  audit-clean n=14 b=5 p=0.0625 (registered)  |  "
                   "full n=15 b=6 p=0.031 (WITHDRAWN)", fontsize=8.5, style="italic")

    fig.suptitle("R-36  maintain-and-deliver vs select-among-candidates  -  "
                 "NO [underpowered, scene-starved]", fontsize=13.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = PROOF / "r36_scarcity.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    # ponytail: cheap sanity -- the figure's headline count must match the registry
    assert cur["usable_count"] == 2 and cur["unusable_count"] == 8, "scarcity counts drifted"
    assert verd["b"] == 5 and verd["c"] == 0, "verdict b/c drifted"
    print("wrote", out)


def fig_person13():
    cell = RUNS / "DSC_SWAP_person13_244"
    img = mpimg.imread(cell / "deliver.png")
    res = json.loads((cell / "results.json").read_text())
    dist_gt = res["scene"]["distractor_gt_prompt"]  # [360,300,408,412] -- mis-placed

    fig, ax = plt.subplots(figsize=(13, 7.3))
    ax.imshow(img)
    ax.axis("off")
    # the actual green-shirt person (the intended distractor) stands far-left ~x200,y=300
    ax.add_patch(FancyArrow(150, 250, 40, 55, width=4, head_width=16, color="yellow",
                            length_includes_head=True))
    ax.text(60, 235, "actual green-shirt person\n(the intended distractor)",
            color="yellow", fontsize=10, fontweight="bold", va="bottom")
    # the mis-placed distractor GT box (blue in the render) sits on empty bushes
    bx0, by0, bx1, by1 = dist_gt
    ax.text(bx1 + 8, (by0 + by1) / 2,
            f"distractor GT {dist_gt}\nsits on EMPTY GROUND (iou_d=0.0)\n-> excluded on the audit",
            color="deepskyblue", fontsize=10, fontweight="bold", va="center")
    ax.set_title("R-36 person13 SWAP: asked for the distractor, the system DELIVERED THE TARGET "
                 "(green box on striped shirt)\n"
                 "-- a real select failure, but the distractor GT is mis-placed, so this cell "
                 "cannot serve as a clean gating discordant",
                 fontsize=11, fontweight="bold")
    fig.tight_layout()
    out = PROOF / "r36_person13_swap_delivers_target.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    fig_scarcity()
    fig_person13()
