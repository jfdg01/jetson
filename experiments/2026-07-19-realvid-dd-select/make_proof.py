"""P5.6 proof figures (reproducible from runs/*/results.json).

  proof/p56_pass_grid.png -- per cell x leg: P5.3 baseline vs P5.5 MC vs
                             P5.6 DD (direct delivery). The headline
                             did-the-contract-change-flip-the-cells picture,
                             reading the sibling P5.3/P5.5 runs dirs.
  proof/p56_contract.png  -- per cell: delivered-box IoU vs the correct
                             object's GT at the prompt (target GT for WSEL,
                             hand distractor GT for SWAP) with the 0.25
                             floor, plus the acquire-latency comparison
                             (DD 0.0 s vs the recorded shadow re-ground) and
                             the shadow-selection agreement markers.

Usage:
  .venv-ft/bin/python experiments/2026-07-14-direct-delivery-select/make_proof.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
P53_RUNS = HERE.parent / "2026-07-14-multi-candidate-select" / "runs"
P55_RUNS = HERE.parent / "2026-07-14-select-generalization" / "runs"
RUNS = HERE / "runs"
PROOF = HERE / "proof"
CELLS = [("car10", 240), ("car10", 615), ("car9", 300), ("car7", 460),
         ("car9", 560), ("car3", 200)]           # car3:200 non-gating control


def load(runs_dir: Path, prefix: str, leg: str, clip: str, f0: int):
    p = runs_dir / f"{prefix}{leg}_{clip}_{f0}" / "results.json"
    return json.loads(p.read_text()) if p.exists() else None


def fig_pass_grid():
    arms = [("P5.3", P53_RUNS, ""), ("P5.5 MC", P55_RUNS, "MC_"),
            ("P5.6 DD", RUNS, "DD_")]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2))
    for ax, leg in zip(axes, ("WSEL", "SWAP")):
        for yi, (label, rd, pre) in enumerate(arms):
            for xi, (clip, f0) in enumerate(CELLS):
                r = load(rd, pre, leg, clip, f0)
                if r is None:
                    ax.text(xi, yi, "-", ha="center", va="center", color="0.6")
                    continue
                ok = r["pass"]
                ax.add_patch(plt.Rectangle((xi - .45, yi - .45), .9, .9,
                                           color="#2a9d4e" if ok else "#c0392b",
                                           alpha=.85))
                ax.text(xi, yi, "PASS" if ok else "FAIL", ha="center",
                        va="center", color="w", fontsize=9, weight="bold")
        ax.set_xticks(range(len(CELLS)))
        ax.set_xticklabels([f"{c}:{f}" + ("\n(non-gating)" if c == "car3" else "")
                            for c, f in CELLS], fontsize=8)
        ax.set_yticks(range(len(arms)))
        ax.set_yticklabels([a[0] for a in arms], fontsize=9)
        ax.set_xlim(-.5, len(CELLS) - .5); ax.set_ylim(-.5, len(arms) - .5)
        ax.invert_yaxis()
        ax.set_title(f"{leg} per cell")
    fig.suptitle("P5.6 direct-delivery contract vs the P5.3/P5.5 re-ground "
                 "contracts (gating = first 5 cells; note: P5.6 SWAP is the "
                 "STRENGTHENED rule, see README)")
    fig.tight_layout()
    out = PROOF / "p56_pass_grid.png"
    fig.savefig(out, dpi=150)
    print(out)


def fig_contract():
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))

    # left: delivered-box IoU vs the correct object's GT at the prompt
    ax = axes[0]
    xs = range(len(CELLS))
    for leg, color, dy in (("WSEL", "tab:blue", -0.12),
                           ("SWAP", "tab:orange", 0.12)):
        vals, marks = [], []
        for clip, f0 in CELLS:
            r = load(RUNS, "DD_", leg, clip, f0)
            if r is None:
                vals.append(None); marks.append(None)
                continue
            sc = r["score"]
            v = (sc.get("deliver_iou") if leg == "WSEL"
                 else sc.get("deliver_iou_distractor"))
            vals.append(v)
            sh = (r["meta"].get("shadow") or {}).get("selected")
            marks.append(sh == ("target" if leg == "WSEL" else "distractor"))
        for xi, (v, m) in enumerate(zip(vals, marks)):
            if v is None:
                continue
            ax.bar(xi + dy, v, width=0.22, color=color,
                   label=leg if xi == 0 else None)
            ax.text(xi + dy, v + 0.02, "s" if m else "S!", ha="center",
                    fontsize=7, color="0.3")
    ax.axhline(0.25, color="r", ls="--", lw=1, label="0.25 floor")
    ax.set_xticks(list(xs))
    ax.set_xticklabels([f"{c}:{f}" for c, f in CELLS], fontsize=8)
    ax.set_ylabel("delivered-box IoU vs correct-object GT at prompt")
    ax.set_title("Direct delivery: is the carried box on the named object?\n"
                 "(s = shadow re-ground agrees, S! = shadow disagrees)")
    ax.legend(fontsize=8)

    # right: acquire latency, DD (0.0 by construction) vs shadow re-ground
    ax = axes[1]
    labels, dd, sh = [], [], []
    for clip, f0 in CELLS:
        for leg in ("WSEL", "SWAP"):
            r = load(RUNS, "DD_", leg, clip, f0)
            if r is None:
                continue
            labels.append(f"{clip}:{f0}\n{leg}")
            dd.append(r["score"].get("acquire_s") or 0.0)
            sh.append((r["meta"].get("shadow") or {}).get("acquire_s"))
    x = range(len(labels))
    ax.bar([i - 0.18 for i in x], dd, width=0.36, color="tab:green",
           label="P5.6 direct delivery")
    ax.bar([i + 0.18 for i in x], [v or 0.0 for v in sh], width=0.36,
           color="tab:gray", label="shadow full-frame re-ground")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=6)
    ax.set_ylabel("acquire_s (s)")
    ax.set_title("Select latency: contract change removes the prompt-time "
                 "VLM call entirely")
    ax.legend(fontsize=8)

    fig.tight_layout()
    out = PROOF / "p56_contract.png"
    fig.savefig(out, dpi=150)
    print(out)


def main():
    PROOF.mkdir(exist_ok=True)
    fig_pass_grid()
    fig_contract()
    print("Also copy 1-2 headline overlay MP4s into proof/ per the README "
          "deliverables section (e.g. runs/DD_SWAP_car10_240/overlay.mp4).")


if __name__ == "__main__":
    main()
