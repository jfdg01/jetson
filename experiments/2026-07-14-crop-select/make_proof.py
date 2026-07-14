"""P5.4 proof figures (DoD-7). Reproducible from runs/*/results.json plus the
frozen P5.3 runs (the before side of the before/after).

  proof/p54_pass_grid.png     : per-scene PASS grid, P5.3 (WSEL/SWAP, full-frame
                                VLM) vs P5.4 (VSEL/VSWP, ROI-constrained VLM);
                                NO_MATCH cells hatched — the failure family the
                                ROI window is meant to kill.
  proof/p54_acquire_match.png : left, measured acquire latency per run (P5.3
                                full-frame vs P5.4 ROI crop); right, winning
                                match IoU per run (floor line at 0.10).

    .venv-ft/bin/python experiments/2026-07-14-crop-select/make_proof.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
P53_RUNS = REPO / "experiments" / "2026-07-14-multi-candidate-select" / "runs"
P54_RUNS = HERE / "runs"
PROOF = HERE / "proof"

SCENES = [("car10", 240), ("car10", 615), ("car9", 300), ("car7", 460),
          ("car3", 200)]
PAIRS = [("WSEL", "VSEL"), ("SWAP", "VSWP")]  # (P5.3 leg, P5.4 leg)


def load(runs: Path, leg: str, clip: str, f0: int) -> dict | None:
    p = runs / f"{leg}_{clip}_{f0}" / "results.json"
    return json.loads(p.read_text()) if p.exists() else None


def cell(r: dict | None) -> tuple[float, str]:
    """(value for the colormap, annotation)."""
    if r is None:
        return np.nan, "—"
    reason = r["score"].get("reason") or ""
    if r["pass"]:
        return 1.0, "PASS"
    if "NO_MATCH" in reason or "no box" in reason:
        return 0.0, "NO\nMATCH"
    return 0.35, "FAIL"


def fig_pass_grid() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
    labels = [f"{c}:{f}" for c, f in SCENES]
    for ax, (leg3, leg4) in zip(axes, PAIRS):
        grid, ann = np.full((2, 5), np.nan), [[""] * 5 for _ in range(2)]
        for j, (clip, f0) in enumerate(SCENES):
            for i, (runs, leg) in enumerate(((P53_RUNS, leg3), (P54_RUNS, leg4))):
                grid[i, j], ann[i][j] = cell(load(runs, leg, clip, f0))
        ax.imshow(grid, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
        for i in range(2):
            for j in range(5):
                ax.text(j, i, ann[i][j], ha="center", va="center", fontsize=9,
                        fontweight="bold" if ann[i][j] == "PASS" else "normal")
        ax.set_xticks(range(5), labels, fontsize=8)
        ax.set_yticks([0, 1], [f"P5.3 {leg3}\n(full frame)",
                               f"P5.4 {leg4}\n(ROI crop)"], fontsize=9)
        n3 = sum(1 for j in range(5) if ann[0][j] == "PASS")
        n4 = sum(1 for j in range(5) if ann[1][j] == "PASS")
        ax.set_title(f"{leg3} {n3}/5  ->  {leg4} {n4}/5", fontsize=11)
    fig.suptitle("P5.4 ROI-constrained select vs P5.3 full-frame select "
                 "(same 5 frozen scenes, same match rule)", fontsize=11)
    fig.tight_layout()
    fig.savefig(PROOF / "p54_pass_grid.png", dpi=150)
    print("wrote", PROOF / "p54_pass_grid.png")


def fig_acquire_match() -> None:
    rows = []  # (label, acq53, acq54, miou53, miou54) per (pair, scene)
    for leg3, leg4 in PAIRS:
        for clip, f0 in SCENES:
            r3, r4 = load(P53_RUNS, leg3, clip, f0), load(P54_RUNS, leg4, clip, f0)

            def get(r, key, src):
                if r is None:
                    return np.nan
                if key == "acq":
                    return r["meta"].get("acquire_s") or np.nan
                mi = r["meta"].get("match_ious")
                return max(mi.values()) if mi else np.nan

            rows.append((f"{leg4[0]}{leg4[1]}* {clip}:{f0}",
                         get(r3, "acq", leg3), get(r4, "acq", leg4),
                         get(r3, "miou", leg3), get(r4, "miou", leg4)))
    labels = [r[0] for r in rows]
    x = np.arange(len(rows))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4))
    a1.bar(x - 0.2, [r[1] for r in rows], 0.4, label="P5.3 full-frame")
    a1.bar(x + 0.2, [r[2] for r in rows], 0.4, label="P5.4 ROI crop")
    a1.set_ylabel("measured acquire (s)")
    a1.set_title("VLM acquire latency per run")
    a1.legend(fontsize=8)
    a2.bar(x - 0.2, [r[3] for r in rows], 0.4, label="P5.3")
    a2.bar(x + 0.2, [r[4] for r in rows], 0.4, label="P5.4")
    a2.axhline(0.10, color="k", ls="--", lw=1, label="match floor 0.10")
    a2.set_ylabel("winning match IoU (vlm box vs carried candidates)")
    a2.set_title("Match strength per run")
    a2.legend(fontsize=8)
    for a in (a1, a2):
        a.set_xticks(x, labels, rotation=45, ha="right", fontsize=7)
    fig.tight_layout()
    fig.savefig(PROOF / "p54_acquire_match.png", dpi=150)
    print("wrote", PROOF / "p54_acquire_match.png")


if __name__ == "__main__":
    PROOF.mkdir(exist_ok=True)
    fig_pass_grid()
    fig_acquire_match()
