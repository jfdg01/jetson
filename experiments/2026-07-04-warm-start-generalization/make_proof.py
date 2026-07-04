"""P5.2 proof figures from runs/*/results.json + the frozen profiles.

  fig1 gap_vs_speed.png  : per-clip (WARM-COLD) coverage gap vs on-screen speed,
                           coloured by category, with Spearman rho + per-bin means
                           -> the RQ-P5.2b thesis figure (payoff grows with speed).
  fig2 generalization_grid.png : WARM/COLD/ORACLE PASS per clip, grouped by category
                           -> RQ-P5.2a (does the win hold beyond cars).

    python make_proof.py            # writes proof/*.png, prints the summary table
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PROOF = HERE / "proof"
DATA = HERE.parent / "2026-07-03-real-video-replay" / "data" / "UAV123"
LEGS = ("WARM", "COLD", "ORACLE")
CAT_COLOR = {"car": "#1f77b4", "person": "#d62728", "boat": "#2ca02c",
             "wakeboard": "#9467bd", "bike": "#ff7f0e"}


def spearman(x, y):
    """rank-correlation without scipy: Pearson of the ranks."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    rx, ry = x.argsort().argsort().astype(float), y.argsort().argsort().astype(float)
    return float(np.corrcoef(rx, ry)[0, 1]) if len(x) > 1 else 0.0


def load() -> list[dict]:
    prof = {p["seq"]: p for p in json.loads((DATA / "anno" / "profiles.json").read_text())}
    clips = json.loads((HERE / "clips.json").read_text())
    rows = []
    for c in clips:
        s = c["clip"]
        r = {"clip": s, "category": prof[s]["category"],
             "speed": prof[s]["speed_pct_s"], "bin": prof[s]["speed_bin"]}
        for leg in LEGS:
            f = RUNS / f"{leg}_{s}" / "results.json"
            d = json.loads(f.read_text()).get("warm", {}) if f.exists() else {}
            r[f"{leg}_cov"] = d.get("coverage", 0.0)
            r[f"{leg}_gl"] = bool(d.get("genuine_lock", False))
            r[f"{leg}_pass"] = bool(d.get("genuine_lock", False)) and d.get("coverage", 0.0) >= 0.50
            r[f"{leg}_occ"] = f.exists() and d.get("deliver_frame") is not None and \
                d.get("deliver_iou", 0.0) == 0.0 and d.get("coverage", 0.0) >= 0.50  # deliver-occluded flag
        rows.append(r)
    return rows


def fig_gap_vs_speed(rows):
    xs = [r["speed"] for r in rows]
    gaps = [r["WARM_cov"] - r["COLD_cov"] for r in rows]
    rho = spearman(xs, gaps)
    fig, ax = plt.subplots(figsize=(8, 5))
    for cat, col in CAT_COLOR.items():
        pts = [(r["speed"], r["WARM_cov"] - r["COLD_cov"]) for r in rows if r["category"] == cat]
        if pts:
            ax.scatter(*zip(*pts), c=col, label=cat, s=70, edgecolor="k", linewidth=0.5, zorder=3)
    # per-bin mean gap
    for b, cut in [("slow", 2.3 / 2), ("med", (2.3 + 4.5) / 2), ("fast", 4.5 + (max(xs) - 4.5) / 2)]:
        g = [r["WARM_cov"] - r["COLD_cov"] for r in rows if r["bin"] == b]
        if g:
            ax.hlines(np.mean(g), *({"slow": (0, 2.3), "med": (2.3, 4.5), "fast": (4.5, max(xs))}[b]),
                      color="gray", linestyle="--", linewidth=1.5, zorder=2)
            ax.text(cut, np.mean(g) + 0.02, f"{b}\n{np.mean(g):+.2f}", ha="center", fontsize=8, color="gray")
    ax.axhline(0, color="k", linewidth=0.8)
    for c in (2.3, 4.5):
        ax.axvline(c, color="lightgray", linewidth=0.8, zorder=1)
    ax.set_xlabel("on-screen target speed (%frame-diagonal / s)")
    ax.set_ylabel("WARM - COLD coverage gap")
    ax.set_title(f"P5.2: warm-start payoff vs on-screen speed  (Spearman rho = {rho:+.2f}, n={len(rows)})")
    ax.legend(title="category", fontsize=8)
    fig.tight_layout()
    PROOF.mkdir(exist_ok=True)
    fig.savefig(PROOF / "gap_vs_speed.png", dpi=140)
    plt.close(fig)
    return rho


def fig_grid(rows):
    rows = sorted(rows, key=lambda r: (r["category"], r["speed"]))
    labels = [f"{r['clip']} ({r['speed']:.1f})" for r in rows]
    y = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(9, 8))
    for j, leg in enumerate(LEGS):
        offs = (j - 1) * 0.25
        ax.barh(y + offs, [1 if r[f"{leg}_pass"] else 0 for r in rows], height=0.22,
                color=["#2ca02c" if r[f"{leg}_pass"] else "#eeeeee" for r in rows],
                edgecolor="k", linewidth=0.3)
        ax.text(1.05, y[0] + offs, leg[0], fontsize=8, va="center")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlim(0, 1.3)
    ax.set_xticks([])
    ax.set_title("P5.2 PASS by clip (green) — bars per clip = WARM / COLD / ORACLE (top->bottom)")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(PROOF / "generalization_grid.png", dpi=140)
    plt.close(fig)


def main():
    rows = load()
    W = sum(r["WARM_pass"] for r in rows)
    C = sum(r["COLD_pass"] for r in rows)
    O = sum(r["ORACLE_pass"] for r in rows)
    rho = fig_gap_vs_speed(rows)
    fig_grid(rows)
    print(f"{'clip':12} {'cat':10} {'spd':>5} {'bin':>4}  W  C  O   gap")
    for r in sorted(rows, key=lambda r: r["speed"]):
        gap = r["WARM_cov"] - r["COLD_cov"]
        print(f"{r['clip']:12} {r['category']:10} {r['speed']:5.1f} {r['bin']:>4}  "
              f"{int(r['WARM_pass'])}  {int(r['COLD_pass'])}  {int(r['ORACLE_pass'])}  {gap:+.2f}")
    print(f"\nW={W}/{len(rows)}  C={C}/{len(rows)}  O={O}/{len(rows)}   Spearman rho(gap,speed)={rho:+.2f}")
    cats = sorted({r["category"] for r in rows if r["WARM_pass"]})
    print(f"WARM passes in categories: {cats} ({len(cats)})")
    for b in ("slow", "med", "fast"):
        g = [r["WARM_cov"] - r["COLD_cov"] for r in rows if r["bin"] == b]
        print(f"  {b:5} bin mean WARM-COLD gap = {np.mean(g):+.2f} (n={len(g)})")


if __name__ == "__main__":
    main()
