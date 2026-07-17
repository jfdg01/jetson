"""P5.10 proof deliverables, reproducible from runs/*/results.json + overlays.

  proof/p510_pass_grid.png       12 clips x {DD,RG} x {white,blue} pass/fail grid
  proof/p510_failclass.png       fail-class histogram per contract
  proof/p510_headline_dd_vs_rg.png  DD vs RG delivery overlays, headline cell
                                    (mechanical pick: first cell in clip/leg
                                    order with DD PASS and RG FAIL; else first
                                    cell with any fail; else bank01_white)

    .venv-ft/bin/python experiments/2026-07-17-simbank-select/make_proof.py
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PROOF = HERE / "proof"
CLIPS = [f"bank{i:02d}" for i in range(1, 13)]
LEGS = ("white", "blue")
OKC, BADC, NAC = "#7fbf7f", "#d66", "#bbb"


def load():
    cells = {}
    for clip in CLIPS:
        for leg in LEGS:
            f = RUNS / f"{clip}_{leg}" / "results.json"
            cells[(clip, leg)] = json.loads(f.read_text()) if f.exists() else None
    return cells


def pass_grid(cells):
    fig, ax = plt.subplots(figsize=(9, 6.5))
    cols = [("DD", "white"), ("DD", "blue"), ("RG", "white"), ("RG", "blue")]
    for yi, clip in enumerate(CLIPS):
        for xi, (contract, leg) in enumerate(cols):
            r = cells[(clip, leg)]
            if r is None:
                c, txt = NAC, "n/a"
            else:
                d = r[contract.lower()]
                c = OKC if d["pass"] else BADC
                txt = "PASS" if d["pass"] else (d["fail_class"] or "FAIL")
            ax.add_patch(plt.Rectangle((xi, yi), 0.96, 0.96, color=c))
            ax.text(xi + 0.48, yi + 0.48, txt, ha="center", va="center",
                    fontsize=7.5)
    ax.set_xlim(0, 4)
    ax.set_ylim(12, 0)
    ax.set_xticks([i + 0.48 for i in range(4)])
    ax.set_xticklabels([f"{c} {l}" for c, l in cols])
    ax.set_yticks([i + 0.48 for i in range(12)])
    ax.set_yticklabels(CLIPS)
    ax.set_title("P5.10 select on the P5.9 scene bank: direct delivery (DD) "
                 "vs prompt-time re-ground (RG)")
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    fig.tight_layout()
    fig.savefig(PROOF / "p510_pass_grid.png", dpi=160)
    plt.close(fig)


def failclass(cells):
    counts = {"DD": {}, "RG": {}}
    for r in cells.values():
        if r is None:
            continue
        for k in counts:
            d = r[k.lower()]
            if not d["pass"]:
                cls = d["fail_class"] or "FAIL"
                counts[k][cls] = counts[k].get(cls, 0) + 1
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, k in zip(axes, counts):
        ks = sorted(counts[k], key=counts[k].get, reverse=True)
        ax.bar(ks, [counts[k][x] for x in ks],
               color=BADC if counts[k] else NAC)
        ax.set_title(f"{k} fail classes "
                     f"({sum(counts[k].values())}/24 cells fail)")
        ax.tick_params(axis="x", rotation=30)
        ax.set_ylim(0, 24)
    axes[0].set_ylabel("cells")
    fig.tight_layout()
    fig.savefig(PROOF / "p510_failclass.png", dpi=160)
    plt.close(fig)


def headline(cells):
    pick = None
    for clip in CLIPS:
        for leg in LEGS:
            r = cells[(clip, leg)]
            if r and r["dd"]["pass"] and not r["rg"]["pass"]:
                pick = (clip, leg)
                break
        if pick:
            break
    if pick is None:
        for clip in CLIPS:
            for leg in LEGS:
                r = cells[(clip, leg)]
                if r and not (r["dd"]["pass"] and r["rg"]["pass"]):
                    pick = (clip, leg)
                    break
            if pick:
                break
    pick = pick or ("bank01", "white")
    clip, leg = pick
    cell = RUNS / f"{clip}_{leg}"
    r = cells[pick]
    dd_img = cv2.imread(str(cell / f"overlay_dd_f{r['prompt_frame']:04d}.png"))
    rg_img = cv2.imread(str(cell / f"overlay_rg_f{r['rg']['deliver_frame']:04d}.png"))
    assert dd_img is not None and rg_img is not None, f"missing overlays in {cell}"
    combo = np.hstack([dd_img, rg_img])
    bar = np.full((44, combo.shape[1], 3), 24, np.uint8)
    cv2.putText(bar, f"P5.10 headline {clip}_{leg}: left DD "
                f"(pass={r['dd']['pass']}) | right RG (pass={r['rg']['pass']}, "
                f"{r['rg']['fail_class']})", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (240, 240, 240), 2)
    cv2.imwrite(str(PROOF / "p510_headline_dd_vs_rg.png"),
                np.vstack([bar, combo]))
    print(f"[make_proof] headline cell: {clip}_{leg}")


def main():
    PROOF.mkdir(exist_ok=True)
    cells = load()
    n = sum(v is not None for v in cells.values())
    print(f"[make_proof] {n}/24 cells loaded")
    pass_grid(cells)
    failclass(cells)
    headline(cells)
    print(f"[make_proof] wrote {PROOF}/p510_pass_grid.png, p510_failclass.png, "
          f"p510_headline_dd_vs_rg.png")


if __name__ == "__main__":
    main()
