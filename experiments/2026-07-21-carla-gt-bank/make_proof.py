#!/usr/bin/env python3
"""Rebuild the proof deliverables from runs/. Reproducible, no live server.

    .venv-ft/bin/python experiments/2026-07-21-carla-gt-bank/make_proof.py

Reads only manifests, gt.jsonl and the gate PNGs already on disk, so it can be
re-run after the fact to regenerate a figure without re-capturing anything.
"""
import json
import sys
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402

HERE = Path(__file__).resolve().parent
RUNS, PROOF = HERE / "runs", HERE / "proof"


def gate_a_montage():
    """The overlays, side by side. GT boxes on real pixels at five altitudes --
    the deliverable for a gate whose whole point is that someone looked."""
    src = sorted((RUNS / "gate_a").glob("gt_alt*.png"))
    if not src:
        return None
    ims = [cv2.imread(str(p)) for p in src]
    h = min(i.shape[0] for i in ims)
    strip = np.hstack([cv2.resize(i, (int(i.shape[1] * h / i.shape[0]), h)) for i in ims])
    out = PROOF / "gate-a-gt-overlay-altitudes.png"
    cv2.imwrite(str(out), strip)
    return out


def bank_figure():
    """The numbers are the point here, so this is a figure and not a clip.

    Left: per-clip capture rate at the 200 W cap -- the honest sustained number,
    since the 86.1 Hz probe was measured with 10 vehicles and no JPG encoding.
    Right: on-screen GT box area against altitude. That spread is the reason the
    bank sweeps altitude at all; a bank captured at one height cannot answer what
    the range/size envelope does to a tracker.
    """
    mans = sorted(RUNS.glob("bank/clip*/manifest.json"))
    if not mans:
        return None
    m = [json.loads(p.read_text()) for p in mans]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))

    ax[0].bar(range(len(m)), [x["capture_hz"] for x in m], color="#3b6ea5")
    mean = float(np.mean([x["capture_hz"] for x in m]))
    ax[0].axhline(mean, color="crimson", ls="--",
                  label=f"mean {mean:.1f} Hz")
    ax[0].axhline(20.0, color="grey", ls=":", label="20 Hz sim real-time (dt=0.05)")
    ax[0].set(xlabel="clip", ylabel="sustained capture Hz",
              title=f"Capture rate, {len(m)} clips @ 200 W cap")
    ax[0].legend(fontsize=8)

    # sample GT areas: every 40th frame is plenty and keeps this script quick
    by_alt = {}
    for p in mans:
        alt = json.loads(p.read_text())["alt"]
        for i, line in enumerate(open(p.parent / "gt.jsonl")):
            if i % 40:
                continue
            for g in json.loads(line)["gt"]:
                if g.get("area_vis_px", 0) > 1.0:
                    by_alt.setdefault(alt, []).append(g["area_vis_px"])
    alts = sorted(by_alt)
    if alts:
        ax[1].boxplot([by_alt[a] for a in alts], tick_labels=[f"{int(a)}" for a in alts],
                      showfliers=False)
        ax[1].set_yscale("log")
        ax[1].set(xlabel="camera altitude (m)", ylabel="on-screen GT box area (px^2)",
                  title="Target pixel size vs altitude")
        ax[1].grid(alpha=0.3, axis="y")

    fig.tight_layout()
    out = PROOF / "bank-capture-and-target-size.png"
    fig.savefig(out, dpi=140)
    return out


def gate_c_figure():
    """G-C: byte-identical is the wrong bar (TAA and auto-exposure carry state), so
    the gate compares a layer-toggle repeat against a same-config repeat baseline."""
    p = RUNS / "gate_c" / "results.json"
    if not p.exists():
        return None
    r = json.loads(p.read_text())
    fig, ax = plt.subplots(figsize=(5.5, 4))
    keys = ["same_config_diff", "toggled_diff"]
    vals = [r.get(k, 0.0) for k in keys]
    ax.bar(["same config\n(repeat)", "layer toggle\n+ restore"], vals,
           color=["#3b6ea5", "#c05640"])
    ax.axhline(r.get("floor", 8.0), color="grey", ls=":",
               label=f"noise floor {r.get('floor', 8.0)}")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.3f}", ha="center", va="bottom", fontsize=9)
    ax.set(ylabel="mean |frame difference| (8-bit levels)",
           title=f"G-C repeatability -- {r.get('verdict', '?')}")
    ax.legend(fontsize=8)
    fig.tight_layout()
    out = PROOF / "gate-c-repeatability.png"
    fig.savefig(out, dpi=140)
    return out


if __name__ == "__main__":
    PROOF.mkdir(exist_ok=True)
    made = [f for f in (gate_a_montage(), bank_figure(), gate_c_figure()) if f]
    for f in made:
        print(f"wrote {f}")
    if not made:
        print("nothing to build -- runs/ is empty", file=sys.stderr)
        sys.exit(1)
