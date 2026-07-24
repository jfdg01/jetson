"""REG proof deliverables (reproducible from runs/reg/results.json).

fig_landing  : 4 panels -- one concordant clip + the 3 discordants -- each showing
               the target-phrase box + distractor-phrase box drawn on the ONE prompt
               frame, against their own hand GTs. This is the "look at it" evidence:
               distractor phrase lands on the distractor object (not collapsed to the
               salient target), and the discordants are near-misses at the IoU floor.
fig_outcome  : per-clip target-vs-distractor grounding outcome (14 gating clips x 2
               arms, pass/fail), with the frozen b/c/p verdict annotated.

Colours: target GT = green, target box = cyan; distractor GT = yellow, distractor
box = magenta. Run: .venv-ft/bin/python .../make_proof.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments" / "2026-07-20-n25-select"))
sys.path.insert(0, str(REPO / "experiments" / "2026-07-03-real-video-replay"))
from curate_p518 import frame            # noqa: E402  (1-indexed frame reader)
from replay_source import iou            # noqa: E402

RESULTS = REPO / "runs" / "reg" / "results.json"
PROOF = HERE / "proof"
LANDING = [c for c in ("car9", "car10", "person13", "wakeboard8")]   # concordant + b,b,c


def _draw(ax, clip, row):
    img = cv2.cvtColor(frame(clip, row["prompt_frame"]), cv2.COLOR_BGR2RGB)
    ax.imshow(img)
    specs = [("target_gt", "lime", "-"), ("target_box", "cyan", "--"),
             ("distractor_gt", "yellow", "-"), ("distractor_box", "magenta", "--")]
    for key, col, ls in specs:
        b = row.get(key)
        if not b:
            continue
        x0, y0, x1, y1 = b
        ax.add_patch(mpatches.Rectangle((x0, y0), x1 - x0, y1 - y0,
                     fill=False, edgecolor=col, lw=2.2, linestyle=ls))
    ti = iou(row["target_box"], row["target_gt"]) if row.get("target_box") and row.get("target_gt") else 0.0
    di = iou(row["distractor_box"], row["distractor_gt"]) if row.get("distractor_box") and row.get("distractor_gt") else 0.0
    tok = "OK" if row["target_correct"] else "MISS"
    dok = "OK" if row["distractor_correct"] else "MISS"
    ax.set_title(f"{clip}  target IoU={ti:.2f} [{tok}]   distractor IoU={di:.2f} [{dok}]",
                 fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])


def fig_landing(rows_by_clip):
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    for ax, clip in zip(axes.ravel(), LANDING):
        _draw(ax, clip, rows_by_clip[clip])
    handles = [mpatches.Patch(color="lime", label="target GT"),
               mpatches.Patch(color="cyan", label="target-phrase box"),
               mpatches.Patch(color="yellow", label="distractor GT"),
               mpatches.Patch(color="magenta", label="distractor-phrase box")]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=10,
               bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("REG grounding isolation -- distractor phrase resolves the distractor object "
                 "(not the salient target); discordants are IoU-floor near-misses",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    out = PROOF / "reg_landing.png"
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out


def fig_outcome(rows, verdict):
    g = [r for r in rows if r.get("gating", True)]
    g = sorted(g, key=lambda r: (not r["target_correct"], not r["distractor_correct"], r["clip"]))
    n = len(g)
    fig, ax = plt.subplots(figsize=(8, 0.42 * n + 2))
    green, red = "#2ca02c", "#d62728"
    for i, r in enumerate(g):
        y = n - 1 - i
        ax.add_patch(mpatches.Rectangle((0, y - 0.4), 0.9, 0.8,
                     color=green if r["target_correct"] else red))
        ax.add_patch(mpatches.Rectangle((1.0, y - 0.4), 0.9, 0.8,
                     color=green if r["distractor_correct"] else red))
        ax.text(-0.1, y, r["clip"], ha="right", va="center", fontsize=9)
    ax.text(0.45, n + 0.1, "target\nphrase", ha="center", va="bottom", fontsize=9)
    ax.text(1.45, n + 0.1, "distractor\nphrase", ha="center", va="bottom", fontsize=9)
    ax.set_xlim(-2.2, 2.4); ax.set_ylim(-0.8, n + 1.2)
    ax.axis("off")
    cap = (f"paired McNemar (same frame): b={verdict['b_obs']} (target-ok, distractor-miss)  "
           f"c={verdict['c_obs']} (target-miss, distractor-ok)\n"
           f"n={verdict['n_rows']} (n_eff={verdict['n_eff']}), p={verdict['p_deflated']:.3g}  "
           f"-> SYMMETRIC branch: grounding is not the bottleneck")
    ax.text(0.1, -0.7, cap, ha="left", va="top", fontsize=9,
            bbox=dict(boxstyle="round", fc="#f0f0f0", ec="0.6"))
    ax.set_title("REG -- per-clip target-vs-distractor grounding outcome (green=IoU>=0.25)",
                 fontsize=11)
    fig.tight_layout()
    out = PROOF / "reg_per_clip_outcome.png"
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out


def main():
    PROOF.mkdir(exist_ok=True)
    r = json.loads(RESULTS.read_text())
    rows = r["rows"]
    by_clip = {row["clip"]: row for row in rows}
    sys.path.insert(0, str(HERE))
    from reg_isolate import verdict as compute_verdict
    v = compute_verdict(rows)
    # sanity: the frozen result this proof documents
    assert (v["b_obs"], v["c_obs"], v["n_rows"], v["n_eff"]) == (2, 1, 14, 14), (v["b_obs"], v["c_obs"], v["n_rows"], v["n_eff"])
    assert v["branch"] == "symmetric" and not v["gate_pass"]
    p1 = fig_landing(by_clip)
    p2 = fig_outcome(rows, v)
    print("wrote", p1)
    print("wrote", p2)


if __name__ == "__main__":
    main()
