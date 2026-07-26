#!/usr/bin/env python3
"""make_proof5.py -- EXP-5 thesis deliverables, rebuilt from runs/exp5/.

Three artefacts, because EXP-5 has one quantitative claim and two behavioural ones:

    exp5-arms.png              per-clip median IoU across the six arms + tail/throughput
    exp5-guard-latches.png     bike3, A4 vs A5 -- the guard turns one burst into total loss
    exp5-scaled-strands.png    car18, A4 vs A6 -- the box-scaled window shrinks and strands

    .venv-ft/bin/python experiments/2026-07-26-crop-mode/make_proof5.py
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments" / "2026-07-20-n25-select"))
sys.path.insert(0, str(HERE))
from curate_p518 import frame  # noqa: E402
from run_exp5 import CLIPS, EASY, TAIL, iou  # noqa: E402

RUN = HERE / "runs" / "exp5"
OUT = HERE / "proof"
LABEL = {"A1": "A1 plain 640\n(deployed)", "A2": "A2 plain 1024\n(config flag)",
         "A3": "A3 plain+guard", "A4": "A4 crop 512", "A5": "A5 crop+guard",
         "A6": "A6 scaled+guard"}


def figure(res):
    per, summ, arms = res["per_clip"], res["summary"], res["arms"]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(14, 4.8), width_ratios=[2, 1])

    w = 0.14
    for k, a in enumerate(arms):
        ax.bar([i + (k - 2.5) * w for i in range(len(CLIPS))],
               [per[c][a]["median_iou"] for c in CLIPS], w, label=a)
    ax.axhline(0.25, color="k", ls=":", lw=1)
    ax.axvline(len(TAIL) - 0.5, color="k", lw=1)
    ax.text(len(TAIL) / 2 - .5, 1.02, "resolution-gated tail", ha="center", fontsize=8)
    ax.text(len(TAIL) + len(EASY) / 2 - .5, 1.02, "easy controls", ha="center", fontsize=8)
    ax.set_xticks(range(len(CLIPS)))
    ax.set_xticklabels(CLIPS, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("per-clip median IoU vs GT")
    ax.set_title(f"EXP-5 carry-crop pilot, n={res['n_clips']} UAV123 clips, "
                 f"SAM2 on the Orin  |  D_MAX={res['dmax'].get('d_max')}", fontsize=10)
    ax.legend(fontsize=7, ncol=6, loc="lower left")
    ax.set_ylim(0, 1.08)
    ax.grid(alpha=0.3, axis="y")

    x = range(len(arms))
    bx.bar([i - 0.2 for i in x], [summ[a]["tail_recovered"] / len(TAIL) for a in arms],
           0.4, label=f"tail clips >= 0.25 (of {len(TAIL)})", color="tab:blue")
    bx.bar([i + 0.2 for i in x], [summ[a]["hz_median"] / 8.0 for a in arms],
           0.4, label="on-device Hz / 8", color="tab:green")
    for i, a in enumerate(arms):
        bx.text(i - 0.2, summ[a]["tail_recovered"] / len(TAIL) + .02,
                f"{summ[a]['tail_recovered']}/{len(TAIL)}", ha="center", fontsize=7)
        bx.text(i + 0.2, summ[a]["hz_median"] / 8.0 + .02, f"{summ[a]['hz_median']:.1f}",
                ha="center", fontsize=7)
    bx.set_xticks(list(x))
    bx.set_xticklabels([LABEL[a] for a in arms], fontsize=7, rotation=30, ha="right")
    bx.set_ylim(0, 1.15)
    bx.legend(fontsize=7)
    bx.set_title("tail recovery and throughput", fontsize=10)
    bx.grid(alpha=0.3, axis="y")

    fig.tight_layout()
    p = OUT / "exp5-arms.png"
    fig.savefig(p, dpi=150)
    print(p)


def _draw(img, box, color, label):
    if box is None:
        return
    x0, y0, x1, y1 = (int(v) for v in box)
    cv2.rectangle(img, (x0, y0), (x1, y1), color, 2)
    cv2.putText(img, label, (x0, max(14, y0 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)


def montage(clip, arms, name, plan):
    """Two rows, four steps: the crop window (orange), GT (green), the carried box (yellow)."""
    entry = plan[clip]
    n = len(entry["steps"])
    rows = []
    for a in arms:
        cr = json.loads((RUN / f"carry_{a}.json").read_text())[clip]
        tiles = []
        for f in (0.0, 0.33, 0.66, 1.0):
            j = min(n - 1, int(round(f * (n - 1))))
            st = entry["steps"][j]
            img = frame(clip, st["frame"])
            win = cr["wins"][j]
            if win[2] - win[0] < img.shape[1]:
                _draw(img, win, (0, 140, 255), "crop")
            _draw(img, st["gt"], (0, 200, 0), "GT")
            v = cr["veto"][j]
            _draw(img, cr["boxes"][j], (255, 255, 0),
                  f"{a}{'/' + v if v else ''} {iou(cr['boxes'][j], st['gt']):.2f}")
            cv2.putText(img, f"{clip} {a} step {j}", (6, 24), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (255, 255, 255), 2)
            assert float((img == img[0, 0]).all(axis=2).mean()) < 0.99, "failed render"
            tiles.append(cv2.resize(img, (480, 270)))
        rows.append(np.hstack(tiles))
    p = OUT / name
    cv2.imwrite(str(p), np.vstack(rows))
    print(p)


def main():
    OUT.mkdir(exist_ok=True)
    res = json.loads((RUN / "results.json").read_text())
    plan = {e["clip"]: e for e in json.loads((RUN / "plan.json").read_text())}
    figure(res)
    montage("bike3", ("A4", "A5"), "exp5-guard-latches.png", plan)
    montage("car18", ("A4", "A6"), "exp5-scaled-strands.png", plan)


if __name__ == "__main__":
    main()
