"""P5.16 proof figures (reproducible from runs/DSC_*/results.json).

  proof/p516_pass_grid.png -- per cell x leg: P5.14 DD (oracle seeds,
                              hardcoded frozen row) vs P5.16 DSC (VLM
                              discovery). The headline what-did-removing-
                              the-oracle-cost picture.
  proof/p516_discovery.png -- per cell: the discovery timeline (call frames,
                              outcomes, accept frames) against the idle
                              window [ds, prompt], plus target seed IoU vs
                              GT at the accept frame (diagnostic).

Usage:
  .venv-ft/bin/python experiments/2026-07-19-autodisc-select/make_proof.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PROOF = HERE / "proof"
CELLS = [("car10", 240), ("car10", 615), ("car9", 300), ("car7", 460),
         ("car9", 560), ("car3", 200)]           # car3:200 non-gating control

# Frozen P5.14 oracle-seeded outcomes (committed record; runs/** gitignored).
P514 = {
    ("WSEL", "car10", 240): True,  ("SWAP", "car10", 240): True,
    ("WSEL", "car10", 615): True,  ("SWAP", "car10", 615): True,
    ("WSEL", "car9", 300):  True,  ("SWAP", "car9", 300):  True,
    ("WSEL", "car7", 460):  True,  ("SWAP", "car7", 460):  False,
    ("WSEL", "car9", 560):  True,  ("SWAP", "car9", 560):  True,
    ("WSEL", "car3", 200):  True,  ("SWAP", "car3", 200):  True,
}


def load(leg: str, clip: str, f0: int):
    p = RUNS / f"DSC_{leg}_{clip}_{f0}" / "results.json"
    return json.loads(p.read_text()) if p.exists() else None


def fig_pass_grid():
    fig, axes = plt.subplots(1, 2, figsize=(13, 3.6))
    for ax, leg in zip(axes, ("WSEL", "SWAP")):
        for xi, (clip, f0) in enumerate(CELLS):
            # row 0: P5.14 oracle
            old = P514.get((leg, clip, f0))
            ax.add_patch(plt.Rectangle((xi - .45, -.45), .9, .9,
                                       color="#2a9d4e" if old else "#c0392b",
                                       alpha=.85))
            ax.text(xi, 0, "PASS" if old else "FAIL", ha="center",
                    va="center", color="w", fontsize=9, weight="bold")
            # row 1: P5.16 discovery
            r = load(leg, clip, f0)
            if r is None:
                ax.text(xi, 1, "-", ha="center", va="center", color="0.6")
                continue
            ok = r["pass"]
            ax.add_patch(plt.Rectangle((xi - .45, .55), .9, .9,
                                       color="#2a9d4e" if ok else "#c0392b",
                                       alpha=.85))
            fc = "" if ok else "\n" + (r["score"].get("reason") or "")[:16]
            ax.text(xi, 1, ("PASS" if ok else "FAIL") + fc, ha="center",
                    va="center", color="w", fontsize=8, weight="bold")
        ax.set_xticks(range(len(CELLS)))
        ax.set_xticklabels([f"{c}:{f}" + ("\n(non-gating)" if c == "car3"
                                          else "") for c, f in CELLS],
                           fontsize=8)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["P5.14 DD\n(oracle seeds)",
                            "P5.16 DSC\n(VLM discovery)"], fontsize=8)
        ax.set_xlim(-.5, len(CELLS) - .5); ax.set_ylim(-.5, 1.5)
        ax.invert_yaxis()
        ax.set_title(f"{leg} per cell")
    fig.suptitle("P5.16: same direct-delivery contract, oracle seeds replaced "
                 "by idle-window VLM discovery (gating = first 5 cells)")
    fig.tight_layout()
    out = PROOF / "p516_pass_grid.png"
    fig.savefig(out, dpi=150)
    print(out)


def fig_discovery():
    cells = []
    for clip, f0 in CELLS:
        for leg in ("WSEL", "SWAP"):
            r = load(leg, clip, f0)
            if r is not None:
                cells.append((f"{clip}:{f0} {leg}", r))
    if not cells:
        print("no runs yet -- skip p516_discovery.png")
        return
    fig, ax = plt.subplots(figsize=(13, 0.55 * len(cells) + 2))
    colors = {"accepted": "#2a9d4e", "invalid": "#c0392b",
              "duplicate_reject": "#e67e22", "in_flight_at_prompt": "0.5"}
    for yi, (label, r) in enumerate(cells):
        f0 = r["scene"]["f0"]
        ds = r["meta"]["ds"]
        prompt = r["meta"]["prompt_frame"]
        ax.plot([ds - f0, prompt - f0], [yi, yi], color="0.85", lw=6,
                zorder=1, solid_capstyle="butt")
        ax.axvline(0, color="0.6", lw=0.5, zorder=0)
        for e in r["meta"].get("discovery", []):
            x0, x1 = e["call_frame"] - f0, e["return_frame"] - f0
            c = colors.get(e["outcome"], "k")
            ax.plot([x0, min(x1, prompt - f0)], [yi, yi], color=c, lw=6,
                    zorder=2, solid_capstyle="butt")
            ax.text(x0, yi - 0.32, e["cand"][0].upper(), fontsize=7,
                    ha="left", color=c)
        for ra in r["meta"].get("reanchor", []):
            m = ("x" if ra.get("skipped") else
                 ("^" if ra.get("accepted") else "v"))
            ax.plot(ra["frame"] - f0, yi, m, color="tab:blue", ms=5, zorder=3)
    ax.set_yticks(range(len(cells)))
    ax.set_yticklabels([c[0] for c in cells], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("frames relative to f0 (0 = scene f0; prompt at right end "
                  "of grey bar)")
    ax.set_title("P5.16 discovery timeline per cell -- bar = idle window, "
                 "colored = VLM discovery calls (green accepted / red "
                 "invalid / orange duplicate / grey in-flight-at-prompt), "
                 "T/D = caption, blue marks = re-anchor boundaries "
                 "(x skipped, ^ accepted, v rejected)")
    fig.tight_layout()
    out = PROOF / "p516_discovery.png"
    fig.savefig(out, dpi=150)
    print(out)


def main():
    PROOF.mkdir(exist_ok=True)
    fig_pass_grid()
    fig_discovery()
    print("Also copy the headline per-cell PNGs named in the README "
          "deliverables section into proof/ (deliver.png + discovery PNGs "
          "of the decisive cells).")


if __name__ == "__main__":
    main()
