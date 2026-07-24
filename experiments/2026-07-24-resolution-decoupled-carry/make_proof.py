"""EXP-1 proof figures from runs/exp1/results.json (reproducible; DoD-7).

  proof/elbow_iou_hz.png   : the carry-res ELBOW -- median IoU (left) + on-device Hz (right)
                             vs SAM2 image_size. Where accuracy stops paying for the slowdown.
  proof/per_clip_iou.png   : per-clip median IoU vs image_size (faint spaghetti). Shows the tail
                             clips that collapse at low res while the bulk is flat.
  proof/hz_ondevice.png    : on-device carry Hz bar across the swept sizes.

    .venv-ft/bin/python make_proof.py --out runs/exp1
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "runs" / "exp1"))
    a = ap.parse_args()
    out = Path(a.out)
    r = json.loads((out / "results.json").read_text())
    proof = HERE / "proof"
    proof.mkdir(exist_ok=True)

    sizes = sorted(int(s) for s in r["arms"])
    iou = [r["arms"][str(s)]["median_of_median_iou"] for s in sizes]
    hz = [r["arms"][str(s)]["ondevice_hz_median"] for s in sizes]
    n = r["n_clips"]

    # --- elbow: IoU + Hz vs image_size (twin axes) -----------------------
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    ax.plot(sizes, iou, "o-", color="#1f77b4", lw=2, label="median-of-median IoU")
    ax.set_xlabel("SAM2 carry image_size (px)")
    ax.set_ylabel("median-of-median carry IoU", color="#1f77b4")
    ax.tick_params(axis="y", labelcolor="#1f77b4")
    ax.set_ylim(0, 1); ax.grid(alpha=0.25)
    ax.set_xticks(sizes)
    ax2 = ax.twinx()
    ax2.plot(sizes, hz, "s--", color="#d62728", lw=2, label="on-device Hz")
    ax2.set_ylabel("on-device carry throughput (Hz)", color="#d62728")
    ax2.tick_params(axis="y", labelcolor="#d62728")
    ax2.set_ylim(0, max(hz) * 1.2)
    ax.axvline(768, color="gray", ls=":", lw=1)
    ax.set_title(f"EXP-1 carry-res elbow on the Orin (n={n} clips, 15W+clocks)\n"
                 "IoU flat down to the knee, Hz rises as res falls")
    fig.tight_layout(); fig.savefig(proof / "elbow_iou_hz.png", dpi=130)
    plt.close(fig)

    # --- per-clip spaghetti: exposes the tail clips ----------------------
    per = r["per_clip"]
    clips = list(per[str(sizes[-1])].keys())
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    for c in clips:
        ys = [per[str(s)][c]["median_iou"] if c in per[str(s)] else None for s in sizes]
        collapses = min(y for y in ys if y is not None) < 0.25 <= max(y for y in ys if y is not None)
        ax.plot(sizes, ys, "-", lw=1.6 if collapses else 0.6,
                color="#d62728" if collapses else "#888",
                alpha=0.9 if collapses else 0.4,
                label=c if collapses else None)
    ax.set_xlabel("SAM2 carry image_size (px)"); ax.set_ylabel("per-clip median IoU")
    ax.set_xticks(sizes); ax.set_ylim(0, 1); ax.grid(alpha=0.25)
    ax.set_title(f"EXP-1 per-clip carry IoU vs image_size (n={n})\n"
                 "red = target lost at low res (resolution-sensitive tail)")
    if any(ax.get_legend_handles_labels()[1]):
        ax.legend(fontsize=7, loc="lower right", title="collapsing clips")
    fig.tight_layout(); fig.savefig(proof / "per_clip_iou.png", dpi=130)
    plt.close(fig)

    # --- Hz bar ----------------------------------------------------------
    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    bars = ax.bar([str(s) for s in sizes], hz, color="#1f77b4", edgecolor="k")
    for b, h in zip(bars, hz):
        ax.text(b.get_x() + b.get_width() / 2, h + 0.05, f"{h:.2f}", ha="center", fontsize=9)
    ax.set_xlabel("SAM2 carry image_size (px)")
    ax.set_ylabel("on-device carry throughput (Hz)")
    ax.set_title("EXP-1 SAM2 carry Hz on the Orin (15W + jetson_clocks)")
    ax.set_ylim(0, max(hz) * 1.25); ax.grid(axis="y", alpha=0.25)
    fig.tight_layout(); fig.savefig(proof / "hz_ondevice.png", dpi=130)
    plt.close(fig)

    print(f"wrote elbow_iou_hz.png, per_clip_iou.png, hz_ondevice.png for sizes {sizes}")
    print("  IoU:", dict(zip(sizes, iou)))
    print("  Hz :", dict(zip(sizes, hz)))


if __name__ == "__main__":
    main()
