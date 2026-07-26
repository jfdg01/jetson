"""EXP-9 thesis deliverables: rebuild every figure in proof/ from runs/exp9/*.json.

Numbers only -- the behavioural evidence is the overlay JPEG that `run_exp9.py score` writes
under runs/exp9/overlays/ (the look-at-it rule), copied into proof/ by hand with a caption.

    .venv-ft/bin/python make_proof.py --run runs/exp9 --out proof
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

BOARD_MB = 7607          # Orin Nano 8 GB, as `free -m` reports total
STYLE = {"base": ("#444444", "o"), "trt": ("#1f77b4", "s"),
         "small": ("#d62728", "^"), "small_trt": ("#2ca02c", "D")}


def fig_rate_vs_iou(res: dict, out: Path) -> Path:
    """The trade the campaign exists to price: carry rate against carry accuracy."""
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    arms = res["arms"]
    n = res["n_clips"]
    for a, r in arms.items():
        c, m = STYLE.get(a, ("#888888", "o"))
        ax.scatter(r["hz"], r["median_of_median_iou"], s=190, c=c, marker=m,
                   edgecolors="black", linewidths=0.8, zorder=3,
                   label=f"{a}  ({r['median_ms']} ms, {r['n_pass']}/{n} PASS)")
        ax.annotate(a, (r["hz"], r["median_of_median_iou"]), textcoords="offset points",
                    xytext=(9, 6), fontsize=9.5, color=c, weight="bold")
    b = arms["base"]
    # ponytail: margins BEFORE reading the limits -- matplotlib autoscale is lazy, and the
    # first draw clipped the trt marker into the corner and put the floor label under the legend.
    ax.margins(0.16)
    ax.axhline(b["median_of_median_iou"], color="#444444", ls=":", lw=1, zorder=1)
    ax.axhline(b["median_of_median_iou"] - 0.05, color="#aa0000", ls="--", lw=1, zorder=1)
    ax.text(ax.get_xlim()[0], b["median_of_median_iou"] - 0.05,
            "  G2 non-inferiority floor (-0.05)",
            va="bottom", ha="left", fontsize=8, color="#aa0000")
    ax.axvline(5.0, color="#0066aa", ls="--", lw=1, zorder=1)
    ax.text(5.0, ax.get_ylim()[1], " E1 co-resident gate: 5 Hz", rotation=90,
            va="top", ha="right", fontsize=8, color="#0066aa")
    ax.set_xlabel("carry rate on the Orin, median of per-clip medians (Hz)")
    ax.set_ylabel("carry accuracy, median of per-clip median IoU")
    ax.set_title(f"EXP-9: encoder runtime x capacity, {n} UAV123 clips, 24 steps @ stride 11\n"
                 f"image_size={res['size']}, K={res['K']}, M={res['M']}, "
                 f"Jetson Orin Nano 8 GB @ 15 W + jetson_clocks", fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right", fontsize=8.5, framealpha=0.95)
    fig.tight_layout()
    p = out / "rate-vs-iou.png"
    fig.savefig(p, dpi=160)
    plt.close(fig)
    return p


def fig_memory(census: list, res: dict, out: Path) -> Path:
    """H3: what actually fits next to the deployed VLM on 8 GB of unified memory."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.0, 4.6))
    ok = [r for r in census if r.get("status") == "ok"]
    dead = [r for r in census if r.get("status") != "ok"]

    tags = [r["tag"] for r in ok]
    x = range(len(tags))
    ax1.bar([i - 0.2 for i in x], [r["peak_cuda_mb"] for r in ok], 0.4,
            label="peak CUDA allocated", color="#1f77b4")
    ax1.bar([i + 0.2 for i in x], [r["peak_rss_mb"] for r in ok], 0.4,
            label="peak host RSS", color="#ff7f0e")
    for i, r in enumerate(ok):
        ax1.text(i - 0.2, r["peak_cuda_mb"], f"{r['peak_cuda_mb']:.0f}", ha="center",
                 va="bottom", fontsize=8)
        ax1.text(i + 0.2, r["peak_rss_mb"], f"{r['peak_rss_mb']:.0f}", ha="center",
                 va="bottom", fontsize=8)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(tags)
    ax1.set_ylabel("MB")
    ax1.set_title("SAM2 footprint per model @ 640, co-resident with llama-server", fontsize=10)
    ax1.set_ylim(top=max(r["peak_rss_mb"] for r in ok) * 1.22)   # headroom for the bar labels
    ax1.legend(fontsize=8.5, loc="upper left")
    ax1.grid(alpha=0.3, axis="y")
    if dead:
        ax1.text(0.5, 0.9, "did not load: " + ", ".join(r["tag"] for r in dead),
                 transform=ax1.transAxes, ha="center", fontsize=9, color="#aa0000")

    # board-level: what the run left free, measured by `free -m` on the Orin mid-carry
    labels = [r["tag"] for r in ok]
    used = [BOARD_MB - r["during"]["available_mb"] for r in ok]
    ax2.barh(labels, used, color="#2ca02c")
    ax2.axvline(BOARD_MB, color="black", lw=1.5)
    ax2.text(BOARD_MB, -0.45, f" board total {BOARD_MB} MB", fontsize=8, va="bottom")
    for i, r in enumerate(ok):
        ax2.text(used[i], i, f"  {r['during']['available_mb']} MB still available", va="center",
                 fontsize=8)
    ax2.set_xlim(0, BOARD_MB * 1.28)
    ax2.set_xlabel("board memory committed during the carry (MB, unified)")
    ax2.set_title("Orin Nano 8 GB occupancy, VLM + SAM2 together", fontsize=10)
    ax2.grid(alpha=0.3, axis="x")

    fig.suptitle("EXP-9 Stage 0 memory census -- Jetson Orin Nano 8 GB @ 15 W + jetson_clocks",
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    p = out / "memory-census.png"
    fig.savefig(p, dpi=160)
    plt.close(fig)
    return p


def fig_per_clip(res: dict, out: Path) -> Path:
    """Per-clip paired deltas: the medians in fig 1 can hide a minority of clips collapsing."""
    per = res["per_clip"]
    clips = sorted(per["base"], key=lambda c: per["base"][c]["median_iou"])
    others = [a for a in res["arms_run"] if a != "base"]
    fig, ax = plt.subplots(figsize=(11.0, 4.8))
    for a in others:
        c, m = STYLE.get(a, ("#888888", "o"))
        ax.plot(range(len(clips)), [per[a][c_]["median_iou"] - per["base"][c_]["median_iou"]
                                    for c_ in clips], marker=m, ms=4.5, lw=1.1, color=c, label=a)
    ax.axhline(0, color="black", lw=1)
    ax.axhline(-0.05, color="#aa0000", ls="--", lw=1)
    ax.set_xticks(range(len(clips)))
    ax.set_xticklabels(clips, rotation=90, fontsize=7)
    ax.set_ylabel("median IoU, arm minus base")
    ax.set_title(f"EXP-9 per-clip paired delta vs base ({len(clips)} clips, sorted by base IoU); "
                 f"PASS flips: {res.get('pass_flip_clips') or 'none'}", fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9)
    fig.tight_layout()
    p = out / "per-clip-delta.png"
    fig.savefig(p, dpi=160)
    plt.close(fig)
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="runs/exp9")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "proof"))
    a = ap.parse_args()
    run, out = Path(a.run), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = json.loads((run / "results.json").read_text())
    made = [fig_rate_vs_iou(res, out), fig_per_clip(res, out)]
    cf = run / "census.json"
    if cf.exists():
        made.append(fig_memory(json.loads(cf.read_text()), res, out))
    else:
        print("[proof] no census.json -- skipping the memory figure")
    for p in made:
        print(f"[proof] {p}  ({p.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
