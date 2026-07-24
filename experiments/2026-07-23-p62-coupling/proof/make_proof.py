#!/usr/bin/env python3
"""P6.2-COUPLING proof figure — reproducible from runs/p62_coupling/coupling.json.

Numbers are the point here (per-seed follow-error, coupled vs decoupled), so this
is a figure, not a clip (CLAUDE.md DoD-7). Run from repo root:

    .venv-ft/bin/python experiments/2026-07-23-p62-coupling/proof/make_proof.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
COUPLING = ROOT / "runs/p62_coupling/coupling.json"
OUT = Path(__file__).resolve().parent / "p62_coupling_paired.png"

# The WARM schedule-noise band (P6.2-DELIVERY, warm arm, 3 seeds x 2 flights).
# Both coupling arms feed WARM perception, so the warm-arm rep spread is the
# relevant floor; cold's 69 px rep-noise is a different (off-target) regime.
BAND_PX = 6.70  # max |rep diff|, warm arm; mean 2.58


def main() -> None:
    d = json.loads(COUPLING.read_text())
    ps = d["per_seed"]
    x = [p["coupled"] for p in ps]      # coupled follow-error (px)
    y = [p["decoupled"] for p in ps]    # decoupled follow-error (px)
    diff = [c - dd for c, dd in zip(x, y)]  # coupled - decoupled; >0 = coupled worse
    med = d["median_paired_diff_px"]
    lo, hi = d["ci95_median_diff_px"]
    p = d["wilcoxon_p"]

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12, 5))

    # LEFT: paired scatter, log-log (outliers to 760 px), y=x = no difference.
    axL.scatter(x, y, s=40, c="#2c6fbb", zorder=3)
    lim = [1, 1000]
    axL.plot(lim, lim, "k--", lw=1, alpha=0.6, label="y = x (no difference)")
    for p_ in ps:
        if max(p_["coupled"], p_["decoupled"]) > 60:  # label the carry-drift outliers
            axL.annotate(f"seed{int(p_['scenario']):02d}",
                         (p_["coupled"], p_["decoupled"]),
                         fontsize=7, xytext=(4, 4), textcoords="offset points")
    axL.set_xscale("log"); axL.set_yscale("log")
    axL.set_xlim(lim); axL.set_ylim(lim)
    axL.set_xlabel("COUPLED follow-error (px, log)")
    axL.set_ylabel("DECOUPLED follow-error (px, log)")
    axL.set_title("Per-seed paired follow-error (n=25)")
    axL.legend(loc="upper left", fontsize=8)
    axL.grid(True, which="both", alpha=0.2)

    # RIGHT: signed paired diff, sorted, with median, CI, and noise band.
    order = sorted(range(len(diff)), key=lambda i: diff[i])
    ds = [diff[i] for i in order]
    axR.axhspan(-BAND_PX, BAND_PX, color="#bbbbbb", alpha=0.35,
                label=f"schedule-noise band (+/-{BAND_PX:.1f} px)")
    axR.axhline(0, color="k", lw=0.8)
    axR.axhline(med, color="#d1495b", lw=1.4, label=f"median diff {med:+.2f} px")
    axR.axhspan(lo, hi, color="#d1495b", alpha=0.18,
                label=f"95% CI [{lo:+.2f}, {hi:+.2f}]")
    axR.scatter(range(len(ds)), ds, s=28, c="#2c6fbb", zorder=3)
    axR.set_ylim(-20, 20)  # clip the 3 carry-drift outliers so the band is legible
    axR.set_xlabel("seed (sorted by diff)")
    axR.set_ylabel("COUPLED - DECOUPLED follow-error (px)")
    axR.set_title(f"Paired difference within noise floor\nWilcoxon p={p:.3f} (n.s.) -> bounded null")
    axR.legend(loc="upper left", fontsize=8)
    axR.grid(True, alpha=0.2)
    n_clipped = sum(1 for v in diff if abs(v) > 20)
    if n_clipped:
        axR.text(0.98, 0.02, f"{n_clipped} carry-drift outliers off-scale",
                 transform=axR.transAxes, ha="right", va="bottom",
                 fontsize=7, style="italic", color="#666")

    fig.suptitle("P6.2-COUPLING: closing the control loop does not degrade the warm track "
                 "(bounded null, gate ii)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT, dpi=130)
    print(f"wrote {OUT}  (p={p:.4f}, median {med:+.3f} px, CI [{lo:+.2f},{hi:+.2f}], "
          f"{n_clipped} outliers off-scale)")


if __name__ == "__main__":
    main()
