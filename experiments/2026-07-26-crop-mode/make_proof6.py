#!/usr/bin/env python3
"""make_proof6.py -- EXP-6 thesis deliverables, rebuilt from runs/exp6/.

    exp6-arms.png       per-clip median IoU, 38 clips, 3 arms, held-out vs pilot stratum
    exp6-win.png        the largest TREATMENT win over CONTROL, frame by frame
    exp6-loss.png       the largest TREATMENT loss to CONTROL -- the failure mode, shown

    .venv-ft/bin/python experiments/2026-07-26-crop-mode/make_proof6.py
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
from run_exp5 import CLIPS as PILOT  # noqa: E402
from run_exp5 import iou  # noqa: E402

RUN = HERE / "runs" / "exp6"
OUT = HERE / "proof"
COLOR = {"CONTROL": "tab:gray", "TREATMENT": "tab:orange", "CONTROL2": "tab:blue"}
LABEL = {"CONTROL": "CONTROL plain@640", "TREATMENT": "TREATMENT crop512@640",
         "CONTROL2": "CONTROL-2 plain@1024"}


def figure(res):
    per, summ, arms = res["per_clip"], res["summary"], res["arms"]
    # sorted by the deployed arm, so the resolution-gated tail collects on the left
    clips = sorted(res["clips"], key=lambda c: per[c]["CONTROL"]["median_iou"])
    held = set(res["strata"]["held_out_26"])

    fig, (ax, bx) = plt.subplots(1, 2, figsize=(15, 5.0), width_ratios=[2.6, 1])

    w = 0.27
    for k, a in enumerate(arms):
        ax.bar([i + (k - 1) * w for i in range(len(clips))],
               [per[c][a]["median_iou"] for c in clips], w, label=LABEL[a], color=COLOR[a])
    ax.axhline(0.25, color="k", ls=":", lw=1)
    ax.set_xticks(range(len(clips)))
    ax.set_xticklabels([c if c in held else f"{c}*" for c in clips],
                       rotation=60, ha="right", fontsize=7)
    ax.set_ylabel("per-clip median IoU vs GT")
    t = res["tests"]["held_out_26"]["treatment_vs_control"]
    ax.set_title(f"EXP-6 carry crop at gate scale, n={res['n_clips']} UAV123 clips, SAM2 on "
                 f"the Orin  |  * = EXP-5 pilot clip (not the primary stratum)\n"
                 f"held-out 26: TREATMENT {t['median_iou_a']} vs CONTROL {t['median_iou_b']}, "
                 f"Wilcoxon deflated p={t['wilcoxon_deflated']['p_value']:.3g} "
                 f"(n_eff={t['n_effective']})", fontsize=10)
    ax.legend(fontsize=8, loc="upper left")
    ax.set_ylim(0, 1.05)
    ax.grid(alpha=0.3, axis="y")

    x = range(len(arms))
    bx.bar([i - 0.22 for i in x], [summ[a]["median_of_median_iou"] for a in arms], 0.2,
           label="median-of-median IoU", color="tab:purple")
    bx.bar([i for i in x], [summ[a]["pass"] / res["n_clips"] for a in arms], 0.2,
           label=f"delivered PASS (of {res['n_clips']})", color="tab:green")
    bx.bar([i + 0.22 for i in x], [summ[a]["hz_median"] / 8.0 for a in arms], 0.2,
           label="on-device Hz / 8", color="tab:red")
    for i, a in enumerate(arms):
        bx.text(i - 0.22, summ[a]["median_of_median_iou"] + .02,
                f"{summ[a]['median_of_median_iou']:.3f}", ha="center", fontsize=7)
        bx.text(i, summ[a]["pass"] / res["n_clips"] + .02,
                f"{summ[a]['pass']}/{res['n_clips']}", ha="center", fontsize=7)
        bx.text(i + 0.22, summ[a]["hz_median"] / 8.0 + .02, f"{summ[a]['hz_median']:.1f}",
                ha="center", fontsize=7)
    g = res["gates"]["throughput_matched_parity"]
    bx.set_xticks(list(x))
    bx.set_xticklabels([LABEL[a].replace(" ", "\n", 1) for a in arms], fontsize=7)
    bx.set_ylim(0, 1.18)
    bx.legend(fontsize=7, loc="lower left")
    bx.set_title(f"throughput-matched parity gate: {'PASS' if g['pass'] else 'FAIL'}\n"
                 f"{g['rate_x']}x rate, d_IoU {g['d_median_iou_vs_control2']:+.3f}, "
                 f"d_PASS {g['d_pass_vs_control2']:+d} vs CONTROL-2", fontsize=10)
    bx.grid(alpha=0.3, axis="y")

    fig.tight_layout()
    p = OUT / "exp6-arms.png"
    fig.savefig(p, dpi=150)
    print(p)


def _draw(img, box, color, label):
    if box is None:
        return
    x0, y0, x1, y1 = (int(v) for v in box)
    cv2.rectangle(img, (x0, y0), (x1, y1), color, 2)
    cv2.putText(img, label, (x0, max(14, y0 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)


def montage(clip, name, plan, per):
    """Two rows (CONTROL, TREATMENT), four steps: crop window (orange), GT (green),
    carried box (yellow)."""
    entry = plan[clip]
    n = len(entry["steps"])
    rows = []
    for a in ("CONTROL", "TREATMENT"):
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
            _draw(img, cr["boxes"][j], (255, 255, 0),
                  f"{a} {iou(cr['boxes'][j], st['gt']):.2f}")
            cv2.putText(img, f"{clip} {a} step {j}  (clip median "
                        f"{per[clip][a]['median_iou']:.2f})", (6, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
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
    per = res["per_clip"]
    figure(res)
    delta = sorted(res["clips"], key=lambda c: per[c]["TREATMENT"]["median_iou"]
                   - per[c]["CONTROL"]["median_iou"])
    montage(delta[-1], "exp6-win.png", plan, per)
    montage(delta[0], "exp6-loss.png", plan, per)
    assert set(PILOT) <= set(res["clips"])


if __name__ == "__main__":
    main()
