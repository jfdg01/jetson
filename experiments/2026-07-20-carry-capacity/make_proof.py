#!/usr/bin/env python3
"""P5.20 proof figures -- reproducible from runs/{T,S}/*/results.json +
runs/verdict.json.

  proof/ab_counts.png       per-leg pass counts, arm T (hiera-tiny) vs arm S
                            (hiera-small), with the 20/26 bar and the
                            committed P5.19 reference counts. The headline
                            capacity + replication numbers.
  proof/paired_grid_ts.png  per-scene pass/fail grid, T vs S, both legs;
                            S-vs-T flipped cells get a thick black outline,
                            G = grace delivery. The paired-A/B claim.
  proof/flip_evidence.png   side-by-side deliver.png (T | S) for up to 4
                            S-vs-T flipped gating cells (recovered first) --
                            the qualitative what-changed frames. Skipped
                            with a notice if there are no flips.

Usage:
    .venv-ft/bin/python experiments/2026-07-20-carry-capacity/make_proof.py \
        [--runs DIR] [--proof-dir DIR]
"""
import argparse
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402

HERE = Path(__file__).resolve().parent
P518 = HERE.parent / "2026-07-20-n25-select"
LEGS = ("WSEL", "SWAP")
GREEN, RED, GRAY = "#4a9d4f", "#d63b2f", "#b8b8b8"
BAR, P519_REF = 20, {"WSEL": 22, "SWAP": 20}
ARM_LABEL = {"T": "T hiera-tiny", "S": "S hiera-small"}


def load(runs, arm, cid):
    p = runs / arm / cid / "results.json"
    return json.loads(p.read_text()) if p.exists() else None


def fig_ab_counts(scenes, runs, verdict, out):
    counts = verdict["counts"]
    x = np.arange(len(LEGS))
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.bar(x - 0.2, [counts["T"][l] for l in LEGS], 0.4,
           label=ARM_LABEL["T"], color="#888888")
    ax.bar(x + 0.2, [counts["S"][l] for l in LEGS], 0.4,
           label=ARM_LABEL["S"], color="#2c6fbb")
    for xi, l in enumerate(LEGS):
        ax.text(xi - 0.2, counts["T"][l] + 0.3, str(counts["T"][l]),
                ha="center", fontsize=10)
        ax.text(xi + 0.2, counts["S"][l] + 0.3, str(counts["S"][l]),
                ha="center", fontsize=10)
        ax.plot([xi - 0.45, xi + 0.45], [P519_REF[l]] * 2, ls=":",
                color="#111111", lw=1.4)
    ax.axhline(BAR, color="#d63b2f", ls="--", lw=1.4,
               label=f"bar {BAR}/26")
    ax.plot([], [], ls=":", color="#111111", label="P5.19 committed ref")
    ax.set_xticks(x); ax.set_xticklabels(LEGS)
    ax.set_ylim(0, 27); ax.set_ylabel("passing gating cells (of 26)")
    ax.set_title(f"P5.20 carry-capacity A/B -- branch {verdict['branch']}, "
                 f"paired delta {verdict['paired_delta']:+d} "
                 f"(min_sep +{verdict['min_sep']})", fontsize=10)
    ax.legend(fontsize=9, loc="lower right")
    fig.tight_layout(); fig.savefig(out, dpi=160); plt.close(fig)


def fig_paired_grid(scenes, runs, out):
    cols = [("T WSEL", "T", "WSEL"), ("S WSEL", "S", "WSEL"),
            ("T SWAP", "T", "SWAP"), ("S SWAP", "S", "SWAP")]
    rows = [(f"{s['clip']}:{s['f0']}" + ("" if s.get("gating") else " (ctrl)"), s)
            for s in scenes]
    fig, ax = plt.subplots(figsize=(7.5, 0.34 * len(rows) + 1.6))
    for yi, (label, s) in enumerate(rows):
        for xi, (_, arm, leg) in enumerate(cols):
            cid = f"DSC_{leg}_{s['clip']}_{s['f0']}"
            r = load(runs, arm, cid)
            ok = None if r is None else bool(r["pass"])
            c = GRAY if ok is None else (GREEN if ok else RED)
            mate = load(runs, "S" if arm == "T" else "T", cid)
            flipped = (ok is not None and mate is not None
                       and bool(mate["pass"]) != ok)
            ax.add_patch(plt.Rectangle(
                (xi, yi), 0.94, 0.9, facecolor=c,
                edgecolor="black" if flipped else "none",
                linewidth=2.2 if flipped else 0))
            if r is not None and (r["meta"].get("grace") or {}).get("fired"):
                ax.text(xi + 0.47, yi + 0.45, "G", ha="center", va="center",
                        fontsize=8, fontweight="bold", color="white")
    ax.set_xlim(0, len(cols)); ax.set_ylim(len(rows), 0)
    ax.set_xticks([i + 0.47 for i in range(len(cols))])
    ax.set_xticklabels([c[0] for c in cols], fontsize=9)
    ax.set_yticks([i + 0.45 for i in range(len(rows))])
    ax.set_yticklabels([r[0] for r in rows], fontsize=7)
    ax.tick_params(length=0); [sp.set_visible(False) for sp in ax.spines.values()]
    ax.set_title("P5.20 carry capacity: hiera-tiny (T) vs hiera-small (S), "
                 "same harness/scenes\ngreen=pass red=fail gray=missing; "
                 "black outline=S-vs-T flip; G=grace", fontsize=10)
    fig.tight_layout(); fig.savefig(out, dpi=160); plt.close(fig)


def fig_flip_evidence(runs, verdict, out, cap=4):
    """Stack up to `cap` flipped gating cells as (T deliver | S deliver)
    rows. Recovered cells first, then regressed."""
    flips = ([("recovered", f["cid"]) for f in verdict["recovered"]]
             + [("regressed", f["cid"]) for f in verdict["regressed"]])[:cap]
    if not flips:
        print("no S-vs-T flips -- flip_evidence.png skipped")
        return
    rows = []
    for kind, cid in flips:
        pair = []
        for arm in ("T", "S"):
            d = runs / arm / cid
            p = next((d / n for n in ("grace_deliver.png", "deliver.png")
                      if (d / n).exists()), None)
            assert p is not None, f"no claim PNG for {arm}/{cid}"
            pair.append(cv2.imread(str(p)))
        h = min(i.shape[0] for i in pair)
        pair = [cv2.resize(i, (round(i.shape[1] * h / i.shape[0]), h))
                for i in pair]
        w = pair[0].shape[1] + pair[1].shape[1] + 8
        row = np.full((h + 40, w, 3), 30, np.uint8)
        row[40:, :pair[0].shape[1]] = pair[0]
        row[40:, pair[0].shape[1] + 8:] = pair[1]
        cv2.putText(row, f"{cid} [{kind}]  left=T hiera-tiny  "
                         "right=S hiera-small",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (80, 255, 80) if kind == "recovered" else (80, 80, 255), 2)
        rows.append(row)
    w = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, w - r.shape[1]), (0, 0)),
                   constant_values=30) for r in rows]
    cv2.imwrite(str(out), np.vstack(rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(HERE / "runs"))
    ap.add_argument("--proof-dir", default=str(HERE / "proof"))
    args = ap.parse_args()
    runs = Path(args.runs)
    proof = Path(args.proof_dir)
    proof.mkdir(parents=True, exist_ok=True)
    scenes = json.loads((P518 / "scenes_p518.json").read_text())["scenes"]
    vp = runs / "verdict.json"
    assert vp.exists(), "run verdict_p520.py before make_proof.py"
    verdict = json.loads(vp.read_text())
    fig_ab_counts(scenes, runs, verdict, proof / "ab_counts.png")
    fig_paired_grid(scenes, runs, proof / "paired_grid_ts.png")
    fig_flip_evidence(runs, verdict, proof / "flip_evidence.png")
    print(f"proof figures written to {proof}")


if __name__ == "__main__":
    main()
