"""P5.17 proof deliverables: 3 PNGs under proof/, reproducible from
runs/bank/*/ + runs/*_*/results.json + the authored scenarios (deterministic).

    .venv-ft/bin/python experiments/2026-07-20-bankv3-select/make_proof.py

  p517_peak_montage.png   crossing-peak GT overlay of every recorded bank clip,
                          labelled seed / near-car / peak frame -- the P5.13
                          audit's "every peak is the same picture" claim,
                          answered (or not) in one image. Red-framed tile =
                          clip NOT in bank_valid.json.
  p517_staleness.png      predicted ZOH staleness IoU(box@f150, box@f) decay,
                          bank v3 vs the P5.12 bank v2.1 -- the mechanism this
                          bank exists to add (no recorded data needed; byte-
                          deterministic from author_scenario).
  p517_dd_vs_rg_cells.png per-cell paired DD vs RG outcome grid from the
                          select matrix (skipped with a message if the select
                          runs are not there yet).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
spec = importlib.util.spec_from_file_location("scenegen", REPO / "runners" / "scenegen.py")
sg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sg)

BANK = HERE / "runs" / "bank"
PROOF = HERE / "proof"
SEEDS = list(sg.V3_BANK_PINNED)
N, P, D = 300, 150, 150 + sg.V3_LAG_FRAMES   # frames, prompt, deliver estimate


def peak_montage() -> None:
    bv_f = HERE / "runs" / "bank_valid.json"
    valid = set(json.loads(bv_f.read_text())["valid"]) if bv_f.exists() else set()
    tiles, tw, th = [], 320, 180
    for s in SEEDS:
        run = f"s{s:03d}"
        d = BANK / run
        rj = d / "results.json"
        tile = np.full((th, tw, 3), 30, np.uint8)
        label = f"{run} ?"
        if rj.exists():
            r = json.loads(rj.read_text())
            pk = r["v3_xpeak_pred_f"]
            img = cv2.imread(str(d / f"overlay_f{pk:04d}.png"))
            if img is not None:
                tile = cv2.resize(img, (tw, th))
            label = f"{run} near={r['v3_screen']['near']} pk={pk}"
        cv2.putText(tile, label, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (0, 255, 255), 1, cv2.LINE_AA)
        if run not in valid:
            cv2.rectangle(tile, (0, 0), (tw - 1, th - 1), (0, 0, 255), 3)
        tiles.append(tile)
    rows = [np.hstack(tiles[i:i + 4]) for i in range(0, 28, 4)]
    cv2.imwrite(str(PROOF / "p517_peak_montage.png"), np.vstack(rows))
    print("proof/p517_peak_montage.png")


def staleness_fig() -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    for seeds, profile, color, lbl in (
            (SEEDS, "v3", "tab:blue", "bank v3 (28 seeds, this run)"),
            (sg.V2_1_BANK_PINNED, "v2", "tab:red", "bank v2.1 (P5.12/P5.13)")):
        curves = []
        for s in seeds:
            sc = sg.author_scenario(s, N, profile=profile)
            boxes = sg.scenario_boxes(sc)
            for role in ("target", "distractor"):
                b0 = boxes[role][P]
                c = [sg._iou2d(b0, boxes[role][f]) for f in range(P, N)]
                curves.append(c)
                ax.plot(range(P, N), c, color=color, alpha=0.12, lw=0.8)
        med = np.median(np.array(curves), axis=0)
        ax.plot(range(P, N), med, color=color, lw=2.5, label=lbl + " (median)")
    ax.axvline(D, color="k", ls="--", lw=1,
               label=f"RG deliver estimate f{D} (prompt + 4.4 s)")
    ax.axhline(0.20, color="grey", ls=":", lw=1, label="S8/G10 staleness cap 0.20")
    ax.set_xlabel("frame (prompt = f150)")
    ax.set_ylabel("IoU(GT box @ f150, GT box @ f)  [ZOH staleness]")
    ax.set_title("P5.17: why bank v3 makes the re-ground lag cost real\n"
                 "(predicted from authored scenarios; both cars per seed)")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_ylim(-0.02, 1.02)
    fig.tight_layout()
    fig.savefig(PROOF / "p517_staleness.png", dpi=130)
    print("proof/p517_staleness.png")


def cells_fig() -> None:
    bv_f = HERE / "runs" / "bank_valid.json"
    if not bv_f.exists():
        print("cells figure SKIPPED: runs/bank_valid.json not there yet")
        return
    clips = json.loads(bv_f.read_text())["valid"]
    cols = [("DD", "white"), ("RG", "white"), ("DD", "blue"), ("RG", "blue")]
    grid = np.full((len(clips), 4), np.nan)
    have = False
    for i, clip in enumerate(clips):
        for j, (con, leg) in enumerate(cols):
            f = HERE / "runs" / f"{clip}_{leg}" / "results.json"
            if f.exists():
                r = json.loads(f.read_text())
                grid[i, j] = float(bool(r[con.lower()]["pass"]))
                have = True
            elif (HERE / "runs" / f"{clip}_{leg}.INFRA").exists():
                grid[i, j] = 0.5
    if not have:
        print("cells figure SKIPPED: no select cells recorded yet")
        return
    fig, ax = plt.subplots(figsize=(5, 0.34 * len(clips) + 1.6))
    cmap = matplotlib.colors.ListedColormap(["#c0392b", "#95a5a6", "#27ae60"])
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(4), [f"{c} {l}" for c, l in cols])
    ax.set_yticks(range(len(clips)), clips, fontsize=7)
    n_cells = 2 * len(clips)
    dd = int(np.nansum(grid[:, [0, 2]] == 1.0))
    rg = int(np.nansum(grid[:, [1, 3]] == 1.0))
    ax.set_title(f"P5.17 paired select outcomes -- DD {dd}/{n_cells} vs "
                 f"RG {rg}/{n_cells}\n(green PASS, red FAIL, grey INFRA; "
                 f"SEP_MARGIN {7})")
    fig.tight_layout()
    fig.savefig(PROOF / "p517_dd_vs_rg_cells.png", dpi=130)
    print("proof/p517_dd_vs_rg_cells.png")


if __name__ == "__main__":
    PROOF.mkdir(exist_ok=True)
    peak_montage()
    staleness_fig()
    cells_fig()
