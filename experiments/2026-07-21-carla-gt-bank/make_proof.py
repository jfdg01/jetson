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


def bank_overlay(clip="clip01", frame_idx=600):
    """GT drawn on a real captured bank frame -- the artifact itself, not the gate
    rig. Colour IS the finding: cyan/green boxes are static meshes and actors,
    yellow is the clip's anchor target, and RED marks veh_fill < 0.25, i.e. a
    geometrically-correct box sitting on pixels that are not a vehicle. Those are
    cars occluded behind buildings (hazard 2.3c), which corner-projected GT cannot
    see and this column makes filterable.
    """
    d = RUNS / "bank" / clip
    if not (d / "manifest.json").exists():
        return None
    man = json.loads((d / "manifest.json").read_text())
    lines = (d / "gt.jsonl").read_text().splitlines()
    rec = json.loads(lines[min(frame_idx, len(lines) - 1)])
    im = cv2.imread(str(d / "frames" / f"{rec['i']:05d}.jpg"))
    if im is None:
        return None
    for g in rec["gt"]:
        if not g["box_vis"]:
            continue
        x1, y1, x2, y2 = (int(v) for v in g["box_vis"])
        f = g["veh_fill"]
        col = (0, 255, 0) if g["kind"] == "vehicle" else (255, 180, 0)
        if f is not None and f < 0.25:
            col = (0, 0, 255)
        if g["id"] == man.get("target_id"):
            col = (0, 255, 255)
        cv2.rectangle(im, (x1, y1), (x2, y2), col, 2)
        cv2.putText(im, f"{f:.2f}" if f is not None else "-", (x1, y1 - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, col, 1)
    on = sum(1 for g in rec["gt"] if g["box_vis"])
    cv2.putText(im, f"{clip} alt {man['alt']:.0f}m gain {man['track_gain']} "
                    f"frame {rec['i']} on-screen {on}", (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    out = PROOF / "bank-gt-overlay.png"
    cv2.imwrite(str(out), im)
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

    # sample GT areas: every 40th frame is plenty and keeps this script quick.
    # Only fully-in-frame boxes count. A box clipped by the frame edge reports a
    # smaller area than it projects to, and low altitude clips the most, so mixing
    # them in flattens the curve and hides whether the projection obeys 1/z^2.
    by_alt = {}
    for p in mans:
        alt = json.loads(p.read_text())["alt"]
        for i, line in enumerate(open(p.parent / "gt.jsonl")):
            if i % 40:
                continue
            for g in json.loads(line)["gt"]:
                whole = (g["n_proj"] == 8
                         and g.get("area_vis_px", 0) >= g["area_px"] - 0.5)
                if whole and g["area_px"] > 1.0:
                    by_alt.setdefault(alt, []).append(g["area_px"])
    alts = sorted(by_alt)
    if alts:
        ax[1].boxplot([by_alt[a] for a in alts], tick_labels=[f"{int(a)}" for a in alts],
                      showfliers=False)
        # 1/z^2 anchored on the lowest altitude's median: the projection is analytic,
        # so this is a check the bank has to pass, not a trend line fitted to it
        med0 = float(np.median(by_alt[alts[0]]))
        ax[1].plot(range(1, len(alts) + 1),
                   [med0 * (alts[0] / a) ** 2 for a in alts],
                   "o--", color="crimson", ms=4,
                   label=f"1/z^2 from {int(alts[0])} m median")
        ax[1].set_yscale("log")
        ax[1].set(xlabel="camera altitude (m)",
                  ylabel="projected GT box area (px^2), fully in frame",
                  title="Target pixel size vs altitude")
        ax[1].legend(fontsize=8)
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
    vals = [r["same_config_meanabsdiff"], r["toggle_restore_meanabsdiff"]]
    ax.bar(["same config\n(repeat)", "layer toggle\n+ restore"], vals,
           color=["#3b6ea5", "#c05640"])
    ax.axhline(r["floor"], color="grey", ls=":", label=f"floor {r['floor']}")
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
    made = [f for f in (gate_a_montage(), bank_overlay(), bank_figure(),
                        gate_c_figure()) if f]
    for f in made:
        print(f"wrote {f}")
    if not made:
        print("nothing to build -- runs/ is empty", file=sys.stderr)
        sys.exit(1)
