#!/usr/bin/env python3
"""P5.19 proof figures — reproducible from runs/*/results.json.

  proof/paired_flip.png        per-scene pass/fail grid, P5.18 baseline vs
                               P5.19 patched, both legs; flipped cells get a
                               thick black outline. The paired-A/B claim.
  proof/dedup_census.png       discovery-call outcome census per arm: the
                               misaligned guard fired 0x in P5.18; this shows
                               whether the aligned guard is alive, plus how
                               often grace fired/was refused.
  proof/discovery_headline.png the headline wrong-seed cell (SWAP car18:150):
                               P5.18's accepted "black SUV" discovery ON the
                               red Mustang, next to what P5.19 did with the
                               same call (reject + retry / grace / honest
                               fail -- whichever PNG the run produced).

Usage:
    .venv-ft/bin/python experiments/2026-07-20-late-entry-rescue/make_proof.py \
        [--new-runs DIR] [--proof-dir DIR]
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
BASE_RUNS = P518 / "runs"
LEGS = ("WSEL", "SWAP")
GREEN, RED, GRAY = "#4a9d4f", "#d63b2f", "#b8b8b8"
HEADLINE = "DSC_SWAP_car18_150"


def load(runs, cid):
    p = runs / cid / "results.json"
    return json.loads(p.read_text()) if p.exists() else None


def fig_paired_flip(scenes, new_runs, out):
    cols = [("P5.18 WSEL", BASE_RUNS, "WSEL"), ("P5.19 WSEL", new_runs, "WSEL"),
            ("P5.18 SWAP", BASE_RUNS, "SWAP"), ("P5.19 SWAP", new_runs, "SWAP")]
    rows = [(f"{s['clip']}:{s['f0']}" + ("" if s.get("gating") else " (ctrl)"), s)
            for s in scenes]
    fig, ax = plt.subplots(figsize=(7.5, 0.34 * len(rows) + 1.6))
    for yi, (label, s) in enumerate(rows):
        for xi, (_, runs, leg) in enumerate(cols):
            cid = f"DSC_{leg}_{s['clip']}_{s['f0']}"
            r = load(runs, cid)
            ok = None if r is None else bool(r["pass"])
            c = GRAY if ok is None else (GREEN if ok else RED)
            # flip outline: compare the paired columns (0<->1, 2<->3)
            mate = load(BASE_RUNS if runs is new_runs else new_runs, cid)
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
    ax.tick_params(length=0); [s.set_visible(False) for s in ax.spines.values()]
    ax.set_title("P5.19 late-entry rescue vs frozen P5.18 baseline\n"
                 "green=pass red=fail gray=missing; black outline=flip; "
                 "G=grace delivery", fontsize=10)
    fig.tight_layout(); fig.savefig(out, dpi=160); plt.close(fig)


def census(runs, scenes):
    keys = ("accepted", "duplicate_reject", "invalid", "in_flight_at_prompt")
    n = dict.fromkeys(keys, 0)
    n["graced"] = n["grace_refused"] = 0
    for s in scenes:
        for leg in LEGS:
            r = load(runs, f"DSC_{leg}_{s['clip']}_{s['f0']}")
            if r is None:
                continue
            for e in r["meta"].get("discovery", []):
                if e.get("graced"):
                    n["graced"] += 1          # re-marked accepted by grace
                elif e.get("outcome") in n:
                    n[e["outcome"]] += 1
            gr = r["meta"].get("grace") or {}
            if gr.get("refused"):
                n["grace_refused"] += 1
    return n


def fig_dedup_census(scenes, new_runs, out):
    a = census(BASE_RUNS, scenes)
    b = census(new_runs, scenes)
    keys = ["accepted", "duplicate_reject", "invalid", "in_flight_at_prompt",
            "graced", "grace_refused"]
    x = np.arange(len(keys))
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(x - 0.2, [a[k] for k in keys], 0.4, label="P5.18 (misaligned guard)",
           color="#888888")
    ax.bar(x + 0.2, [b[k] for k in keys], 0.4, label="P5.19 (aligned + grace)",
           color="#2c6fbb")
    for xi, k in enumerate(keys):
        ax.text(xi - 0.2, a[k] + 0.6, str(a[k]), ha="center", fontsize=9)
        ax.text(xi + 0.2, b[k] + 0.6, str(b[k]), ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels([k.replace("_", "\n") for k in keys], fontsize=9)
    ax.set_ylabel("discovery calls (54 cells)")
    ax.set_title("Discovery-call outcomes: P5.18's distinctness guard fired 0x "
                 "(frame-misaligned);\nP5.19 dedups at the frame the VLM saw",
                 fontsize=10)
    ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(out, dpi=160); plt.close(fig)


def fig_headline(new_runs, out):
    left = BASE_RUNS / HEADLINE / "discovery_distractor.png"
    # whichever claim frame the patched run produced, in preference order
    cand = [new_runs / HEADLINE / n for n in
            ("discovery_distractor.png", "grace_deliver.png", "deliver.png")]
    right = next((p for p in cand if p.exists()), None)
    assert left.exists(), f"missing baseline PNG {left}"
    assert right is not None, f"no P5.19 PNG for {HEADLINE} in {new_runs}"
    li, ri = cv2.imread(str(left)), cv2.imread(str(right))
    h = min(li.shape[0], ri.shape[0])
    li = cv2.resize(li, (round(li.shape[1] * h / li.shape[0]), h))
    ri = cv2.resize(ri, (round(ri.shape[1] * h / ri.shape[0]), h))
    strip = np.full((44, li.shape[1] + ri.shape[1] + 8, 3), 30, np.uint8)
    img = np.full((h + 44, li.shape[1] + ri.shape[1] + 8, 3), 30, np.uint8)
    img[:44] = strip
    img[44:, :li.shape[1]] = li
    img[44:, li.shape[1] + 8:] = ri
    cv2.putText(img, f"P5.18 {HEADLINE}: 'black SUV' accepted ON the target",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 80, 255), 2)
    cv2.putText(img, f"P5.19: {right.name}",
                (li.shape[1] + 18, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (80, 255, 80), 2)
    cv2.imwrite(str(out), img)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new-runs", default=str(HERE / "runs"))
    ap.add_argument("--proof-dir", default=str(HERE / "proof"))
    args = ap.parse_args()
    new_runs = Path(args.new_runs)
    proof = Path(args.proof_dir)
    proof.mkdir(parents=True, exist_ok=True)
    scenes = json.loads((P518 / "scenes_p518.json").read_text())["scenes"]
    fig_paired_flip(scenes, new_runs, proof / "paired_flip.png")
    fig_dedup_census(scenes, new_runs, proof / "dedup_census.png")
    fig_headline(new_runs, proof / "discovery_headline.png")
    print(f"proof figures written to {proof}")


if __name__ == "__main__":
    main()
