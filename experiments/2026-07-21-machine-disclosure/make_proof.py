"""Proof figures for the R-1 machine-disclosure audit.

    .venv-ft/bin/python experiments/2026-07-21-machine-disclosure/make_proof.py

Two stacked bars over the same 76 campaigns:
  disclosure-by-part.png  - how well each Part says where it ran (the defect)
  vlm-host-by-part.png    - where grounding actually ran (the answer to claim B)
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
PARTS = ["I", "II", "II/III", "III", "IV", "V", "VI"]

SERIES = {
    "disclosure": (
        "confidence",
        [("stated", "#2e7d32"), ("inferred", "#ef6c00"), ("unknown", "#c62828")],
        "Disclosure quality of the machine that ran each campaign",
        "disclosure-by-part.png",
    ),
    "vlm_host": (
        "vlm_machine",
        [("jetson-orin-nano-8gb", "#2e7d32"), ("both", "#66bb6a"),
         ("rtx-3090", "#ef6c00"), ("n/a", "#90a4ae"), ("unclear", "#c62828")],
        "Machine that ran the VLM, per campaign",
        "vlm-host-by-part.png",
    ),
}


def plot(campaigns: list[dict], field: str, levels, title: str, out: Path) -> None:
    counts = {p: Counter(c[field] for c in campaigns if c["part"] == p) for p in PARTS}
    fig, ax = plt.subplots(figsize=(9, 4.6))
    bottom = [0] * len(PARTS)
    for level, colour in levels:
        vals = [counts[p].get(level, 0) for p in PARTS]
        if not any(vals):
            continue
        ax.bar(PARTS, vals, bottom=bottom, label=level, color=colour, edgecolor="white")
        for i, (v, b) in enumerate(zip(vals, bottom)):
            if v:
                ax.text(i, b + v / 2, str(v), ha="center", va="center",
                        color="white", fontsize=9, fontweight="bold")
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xlabel("Part")
    ax.set_ylabel("campaigns")
    ax.set_title(f"{title}\n(n = {len(campaigns)} campaigns, audit 2026-07-21)", fontsize=11)
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


def main() -> None:
    campaigns = json.loads((HERE / "raw" / "machine-audit.json").read_text())
    assert len(campaigns) == 76, f"expected 76 campaigns, got {len(campaigns)}"
    # A bar whose segments do not sum to the Part's campaign count means a level
    # is missing from the palette and vanished from the figure silently.
    for name, (field, levels, title, fname) in SERIES.items():
        known = {lv for lv, _ in levels}
        stray = {c[field] for c in campaigns} - known
        assert not stray, f"{name}: unpalettedvalues would be dropped: {stray}"
        plot(campaigns, field, levels, title, HERE / "proof" / fname)


if __name__ == "__main__":
    main()
