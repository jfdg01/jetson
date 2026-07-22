#!/usr/bin/env python3
"""R-14 proof figures, reproducible from raw/items-{full,roi}.jsonl.

    PYTHONPATH=. .venv-ft/bin/python experiments/2026-07-21-roi-ondevice/make_proof.py

Three figures: the paired per-item IoU, a handful of discordant crops drawn on
the real frames (the "look at it" rule -- a +22 pp claim should be visibly true
on individual images), and on-device prefill vs prompt tokens for both arms.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
PROOF = HERE / "proof"
GATE = 0.25


def load(name: str) -> dict[str, dict]:
    rows = [json.loads(l) for l in (RAW / name).read_text().splitlines() if l.strip()]
    return {f"{r['image_path']}||{r['caption']}": r for r in rows}


def paired_iou(full: dict, roi: dict) -> None:
    keys = [k for k in full if k in roi]
    fx = [full[k]["iou"] for k in keys]
    rx = [roi[k]["iou"] for k in keys]
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(fx, rx, s=10, alpha=0.4, color="#1f77b4")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8, alpha=0.5)
    ax.axvline(GATE, color="crimson", lw=0.8, alpha=0.6)
    ax.axhline(GATE, color="crimson", lw=0.8, alpha=0.6)
    ax.set_xlabel("full-frame @1024 IoU (Orin Q8_0)")
    ax.set_ylabel("ROI M=2.0 @512 IoU (Orin Q8_0)")
    ax.set_title("R-14 paired per-item IoU, n=439\nROI 85.2% vs full-frame 63.1%, McNemar p=2.5e-14")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_aspect("equal")
    fig.tight_layout(); fig.savefig(PROOF / "paired-iou.png", dpi=130); plt.close(fig)


def prefill_vs_tokens() -> None:
    cf = [json.loads(l) for l in (RAW / "calls-full.jsonl").read_text().splitlines() if l.strip()]
    cr = [json.loads(l) for l in (RAW / "calls-roi.jsonl").read_text().splitlines() if l.strip()]
    fig, ax = plt.subplots(figsize=(7, 5))
    for calls, color, label in [(cf, "#1f77b4", "full @1024"), (cr, "#ff7f0e", "ROI @512")]:
        x = [c.get("prompt_n") for c in calls if c.get("prompt_n") and c.get("prompt_ms")]
        y = [c["prompt_ms"] for c in calls if c.get("prompt_n") and c.get("prompt_ms")]
        ax.scatter(x, y, s=9, alpha=0.35, color=color, label=label)
    ax.set_xlabel("prompt tokens"); ax.set_ylabel("on-device prefill ms (Orin Q8_0)")
    ax.set_title("R-14 prefill is linear in prompt tokens, both arms, n=878\nROI cuts median prefill 3680 -> 1371 ms (2.68x)")
    ax.legend(); fig.tight_layout()
    fig.savefig(PROOF / "prefill-vs-tokens.png", dpi=130); plt.close(fig)


def discordant_examples(full: dict, roi: dict, n: int = 6) -> None:
    """b-cells: ROI passes the gate, full frame does not. Draw GT + both preds.

    RefDrone targets are tiny aerial objects (single-digit-percent of frame
    width), so each panel zooms to the union of GT+preds with padding -- a
    full-frame view renders the boxes as invisible dots and defeats the point.
    """
    disc = [(k, full[k], roi[k]) for k in full if k in roi
            and roi[k]["gate_pass"] and not full[k]["gate_pass"]]
    disc.sort(key=lambda t: t[2]["iou"] - t[1]["iou"], reverse=True)
    picks = disc[:n]
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    shown = 0
    for (k, f, r), ax in zip(picks, axes.flat):
        img = cv2.imread(f["image_path"])
        if img is None:
            ax.set_title("image not found"); ax.axis("off"); continue
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        H, W = img.shape[:2]
        boxes = [b for b in (f["gt"], f["pred"], r["pred"]) if b]
        xs = [c for b in boxes for c in (b[0], b[2])]
        ys = [c for b in boxes for c in (b[1], b[3])]
        pad = max(40, (max(xs) - min(xs)), (max(ys) - min(ys)))
        cx0, cy0 = max(0, min(xs) - pad), max(0, min(ys) - pad)
        cx1, cy1 = min(W, max(xs) + pad), min(H, max(ys) + pad)
        for box, col in [(f["gt"], (0, 200, 0)),
                         (f["pred"], (220, 0, 0)),
                         (r["pred"], (0, 90, 255))]:
            if box:
                x0, y0, x1, y1 = map(int, box)
                cv2.rectangle(img, (x0, y0), (x1, y1), col, 2)
        ax.imshow(img[cy0:cy1, cx0:cx1]); ax.axis("off")
        ax.set_title(f"{f['caption'][:44]}\nfull {f['iou']:.2f}  ROI {r['iou']:.2f}", fontsize=8)
        shown += 1
    for ax in axes.flat[shown:]:
        ax.axis("off")
    fig.suptitle("R-14 discordant cells (zoomed): green=GT, red=full-frame pred, blue=ROI pred",
                 fontsize=11)
    fig.tight_layout(); fig.savefig(PROOF / "discordant-examples.png", dpi=110); plt.close(fig)


def main() -> None:
    PROOF.mkdir(exist_ok=True)
    full, roi = load("items-full.jsonl"), load("items-roi.jsonl")
    assert len(full) == 439 and len(roi) == 439, f"{len(full)}/{len(roi)} rows, expected 439"
    paired_iou(full, roi)
    prefill_vs_tokens()
    discordant_examples(full, roi)
    print(f"[proof] wrote 3 figures to {PROOF}")


if __name__ == "__main__":
    main()
