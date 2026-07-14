"""P5.5 proof figures (reproducible from runs/*/results.json).

  proof/p55_pass_grid.png     -- per gating cell x leg: P5.3 baseline vs
                                 P5.5 MC (and M where run). The headline
                                 did-the-levers-flip-the-cells picture.
  proof/p55_reanchor_traj.png -- distractor-box trajectory on the two P5.3
                                 drift cells (car10:615 SWAP, car7:460 SWAP):
                                 seed -> accepted re-anchor boxes ->
                                 candidate box at the prompt, with the P5.3
                                 drifted end-state for contrast.

Usage:
  .venv-ft/bin/python experiments/2026-07-14-select-generalization/make_proof.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
P53_RUNS = HERE.parent / "2026-07-14-multi-candidate-select" / "runs"
RUNS = HERE / "runs"
PROOF = HERE / "proof"
CELLS = [("car10", 240), ("car10", 615), ("car9", 300), ("car7", 460),
         ("car9", 560), ("car3", 200)]           # car3:200 non-gating control
DRIFT_CELLS = [("car10", 615), ("car7", 460)]    # audit-confirmed P5.3 drift


def load(runs_dir: Path, prefix: str, leg: str, clip: str, f0: int):
    p = runs_dir / f"{prefix}{leg}_{clip}_{f0}" / "results.json"
    return json.loads(p.read_text()) if p.exists() else None


def fig_pass_grid():
    arms = [("P5.3", P53_RUNS, ""), ("P5.5 MC", RUNS, "MC_"),
            ("P5.5 M", RUNS, "M_")]
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
    fig.suptitle("P5.5 maintained-candidate select vs the P5.3 baseline "
                 "(gating = first 5 cells; verdict thresholds in README)")
    fig.tight_layout()
    out = PROOF / "p55_pass_grid.png"
    fig.savefig(out, dpi=150)
    print(out)


def fig_reanchor_traj():
    fig, axes = plt.subplots(1, len(DRIFT_CELLS), figsize=(11, 4.6))
    for ax, (clip, f0) in zip(axes, DRIFT_CELLS):
        r = load(RUNS, "MC_", "SWAP", clip, f0)
        r53 = load(P53_RUNS, "", "SWAP", clip, f0)
        if r is None:
            ax.set_title(f"{clip}:{f0} (no MC run yet)")
            continue
        seed = r["scene"]["distractor_box"]
        pts = [("seed f0", seed, "tab:blue")]
        for ra in r["meta"].get("reanchor", []):
            if ra.get("accepted"):
                pts.append((f"re-anchor f{ra['frame']}", ra["new_box"],
                            "tab:green"))
            else:
                pts.append((f"rejected f{ra['frame']}", ra["prior"],
                            "tab:orange"))
        cap = (r["meta"].get("cand_at_prompt") or {}).get("distractor")
        if cap:
            pts.append(("at prompt (P5.5)", cap, "tab:purple"))
        if r53:
            c53 = (r53["meta"].get("cand_at_prompt") or {}).get("distractor")
            if c53:
                pts.append(("at prompt (P5.3, drifted)", c53, "tab:red"))
        for label, b, color in pts:
            x1, y1, x2, y2 = b
            ax.add_patch(plt.Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False,
                                       edgecolor=color, lw=2, label=label))
        ax.set_xlim(0, 1280); ax.set_ylim(720, 0)
        ax.set_title(f"{clip}:{f0} SWAP distractor box")
        ax.legend(fontsize=7, loc="upper left")
        ax.set_aspect("equal")
    fig.suptitle("Idle-window ROI re-anchor vs P5.3 unmaintained drift "
                 "(frame coords, 1280x720)")
    fig.tight_layout()
    out = PROOF / "p55_reanchor_traj.png"
    fig.savefig(out, dpi=150)
    print(out)


def main():
    PROOF.mkdir(exist_ok=True)
    fig_pass_grid()
    fig_reanchor_traj()
    print("Also copy 1-2 headline overlay MP4s into proof/ per the README "
          "deliverables section (e.g. runs/MC_SWAP_car7_460/overlay.mp4).")


if __name__ == "__main__":
    main()
