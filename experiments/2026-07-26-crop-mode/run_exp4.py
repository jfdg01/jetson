#!/usr/bin/env python3
"""run_exp4.py -- EXP-4: native source vs zoom, disentangled (lever a').

Four arms over Bank-1920-single, ALL FED AT 512 so feed size is not a confound:

    arm  source  window  FOV of frame  feed
    A    960     512     53.3%         512 1:1     <- CONTROL, today's roi_reanchor
    B    1920    1024    53.3%         512 2:1 down
    C    1920    512     26.7%         512 1:1 native   <- MODE 2
    D    960     256     26.7%         512 2x LANCZOS up  <- zoom, NO new detail

Primary contrast C vs D (native detail at matched zoom). Secondary A vs D (zoom alone),
A vs B (downscale-chain loss; a non-null there means the chain itself is lossy).

The window is centred on the GT centre -- the perfect operator click, which is MODE 2's
premise ("we know where the object is thanks to the user input"). Same centre in all four
arms, so the centring is a constant of the experiment, not a lever.

    .venv-ft/bin/python experiments/2026-07-26-crop-mode/run_exp4.py --check   # no VLM
    .venv-ft/bin/python experiments/2026-07-26-crop-mode/run_exp4.py
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import cv2
import numpy as np
from PIL import Image
from scipy.stats import binomtest, wilcoxon

from grounding.contract import COORD_SCALE, iou, normalize_bbox, parse_bbox
from grounding.roi import crop_resize, map_to_full, roi_window

FEED = 512
HIT = 0.5
# (source side, window side). Source 960 = the INTER_AREA downscale carla_debug_ui.py
# does in on_image(); 1920 = the raw sensor frame.
ARMS = {"A": (960, 512), "B": (1920, 1024), "C": (1920, 512), "D": (960, 256)}
BANK = "experiments/2026-07-26-crop-mode/runs/bank1920"


def sources(png: Path):
    """The 1920 native frame and its 960 INTER_AREA downscale, as PIL RGB."""
    bgr = cv2.imread(str(png))
    assert bgr is not None and bgr.shape[0] == 1920, f"{png}: not a 1920 frame"
    small = cv2.resize(bgr, (960, 960), interpolation=cv2.INTER_AREA)
    return {1920: Image.fromarray(bgr[:, :, ::-1]),
            960: Image.fromarray(small[:, :, ::-1])}


def feed_for(arm, src_img, box1920):
    """(PIL 512x512 feed, window in source pixels, source side)."""
    side, win_px = ARMS[arm]
    k = side / 1920.0
    gt_norm = normalize_bbox([v * k for v in box1920], side, side)
    win = roi_window(gt_norm, side, side, margin=0.0, min_side=win_px)
    img = crop_resize(src_img[side], win, FEED, upscale=win_px < FEED)
    assert img.size == (FEED, FEED), f"{arm}: feed {img.size}, window {win}"
    return img, win, side


def ground(be, img, caption, tmp: Path):
    """One VLM pass on a 512 feed -> (box normalized 0-COORD_SCALE in the CROP, wall_s)."""
    img.save(tmp)
    t0 = time.time()
    raw = be.generate(str(tmp), caption)
    wall = time.time() - t0
    tmp.unlink(missing_ok=True)
    return parse_bbox(raw), wall, raw


def overlay(img, gt_norm_crop, pred_norm_crop, path: Path, title):
    """GT red, prediction green, on the real 512 feed. The verdict is the pixels."""
    a = np.array(img)[:, :, ::-1].copy()
    for norm, col in ((gt_norm_crop, (0, 0, 255)), (pred_norm_crop, (0, 255, 0))):
        if norm is None:
            continue
        x1, y1, x2, y2 = (int(v / COORD_SCALE * FEED) for v in norm)
        cv2.rectangle(a, (x1, y1), (x2, y2), col, 2)
    cv2.putText(a, title, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1,
                cv2.LINE_AA)
    cv2.imwrite(str(path), a)
    assert float((a == a[0, 0]).all(axis=2).mean()) < 0.99, f"{path}: blank overlay"


def to_crop_norm(box1920, win, side):
    """GT box -> normalized coords WITHIN the crop window (for the overlay only)."""
    k = side / 1920.0
    x0, y0, x1, y1 = win
    px = [box1920[0] * k - x0, box1920[1] * k - y0,
          box1920[2] * k - x0, box1920[3] * k - y0]
    return normalize_bbox(px, x1 - x0, y1 - y0)


def mcnemar(a, b):
    """Exact McNemar on two paired binary vectors. b = a-wins, c = b-wins."""
    nb = sum(1 for x, y in zip(a, b) if x and not y)
    nc = sum(1 for x, y in zip(a, b) if y and not x)
    p = binomtest(nb, nb + nc, 0.5).pvalue if nb + nc else 1.0
    return nb, nc, float(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default=BANK)
    ap.add_argument("--out", default="experiments/2026-07-26-crop-mode/runs/exp4")
    ap.add_argument("--check", action="store_true",
                    help="build feeds + overlays only, no VLM (bank sanity)")
    args = ap.parse_args()

    bank = Path(args.bank)
    man = json.loads((bank / "results.json").read_text())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(f"/dev/shm/exp4_{os.getpid()}.png")

    be = None
    if not args.check:
        from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
        from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
        from grounding.eval.backends import JetsonBackend
        be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                           f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                           ssh_host="jetson", max_side=FEED)

    per = []
    try:
        for t in man["targets"]:
            src = sources(bank / t["png"])
            gt_full = normalize_bbox(t["box"], 1920, 1920)
            row = {"name": t["name"], "caption": t["caption"],
                   "footprint_px": t["footprint_px"], "alt_m": t["alt_m"], "arms": {}}
            for arm in ARMS:
                img, win, side = feed_for(arm, src, t["box"])
                if args.check:
                    if t["name"] in ("t00_small", "t10_mid", "t18_large"):
                        overlay(img, to_crop_norm(t["box"], win, side), None,
                                out / f"check_{t['name']}_{arm}.png",
                                f"{arm} src{side} win{win[2]-win[0]} "
                                f"{t['footprint_px']:.0f}px")
                    continue
                pred, wall, raw = ground(be, img, t["caption"], tmp)
                full = map_to_full(pred, win, side, side) if pred else None
                val = float(iou(gt_full, full)) if full else 0.0
                row["arms"][arm] = {"iou": round(val, 4), "hit": val >= HIT,
                                    "wall_s": round(wall, 2), "win": list(win),
                                    "pred_crop": list(pred) if pred else None,
                                    "raw": raw[:120] if pred is None else None}
                # keep the C feed around: the pre-registered visual is a C-win and a
                # C-loss overlaid on the real crop, and re-grounding to draw it would
                # be a different sample.
                if arm == "C":
                    row["_c"] = (img, to_crop_norm(t["box"], win, side), pred)
            per.append(row)
            if not args.check:
                print(f"  {row['name']:12s} {t['footprint_px']:6.1f}px  " +
                      "  ".join(f"{a} {row['arms'][a]['iou']:.2f}" for a in ARMS),
                      flush=True)
    finally:
        if be is not None:
            be.close()
        tmp.unlink(missing_ok=True)

    if args.check:
        print(f"feeds built for {len(man['targets'])} targets, overlays in {out}")
        return

    summ = {a: {"hit_rate": round(np.mean([r["arms"][a]["hit"] for r in per]), 4),
                "mean_iou": round(float(np.mean([r["arms"][a]["iou"] for r in per])), 4),
                "median_iou": round(float(np.median([r["arms"][a]["iou"] for r in per])), 4),
                "median_wall_s": round(float(np.median([r["arms"][a]["wall_s"]
                                                        for r in per])), 2)}
            for a in ARMS}
    tests = {}
    for lo, hi in (("C", "D"), ("A", "D"), ("A", "B"), ("C", "A")):
        h1 = [r["arms"][lo]["hit"] for r in per]
        h2 = [r["arms"][hi]["hit"] for r in per]
        nb, nc, p = mcnemar(h1, h2)
        d = [r["arms"][lo]["iou"] - r["arms"][hi]["iou"] for r in per]
        w = wilcoxon(d).pvalue if any(v != 0 for v in d) else 1.0
        tests[f"{lo}_vs_{hi}"] = {"b": nb, "c": nc, "p_mcnemar": round(p, 5),
                                  "p_wilcoxon": round(float(w), 5),
                                  "median_iou_diff": round(float(np.median(d)), 4)}
    best = max(per, key=lambda r: r["arms"]["C"]["iou"] - r["arms"]["D"]["iou"])
    worst = min(per, key=lambda r: r["arms"]["C"]["iou"])
    for tag, r in (("win", best), ("loss", worst)):
        img, gtc, pc = r["_c"]
        overlay(img, gtc, pc, out / f"C_{tag}_{r['name']}.png",
                f"C {r['name']} {r['footprint_px']:.0f}px IoU {r['arms']['C']['iou']:.2f}"
                f" (D {r['arms']['D']['iou']:.2f}) \"{r['caption']}\"")
    for r in per:
        r.pop("_c", None)

    cd = tests["C_vs_D"]
    verdict = ("PASS" if (cd["b"] > cd["c"] and cd["b"] + cd["c"] >= 6
                          and cd["p_mcnemar"] < 0.05) else "MISS")
    res = {"exp": "EXP-4", "bank": man["bank"], "n": len(per), "n_deflated": len(per),
           "deflation": f"min pairwise camera sep enforced at {man['min_sep_m']} m",
           "feed": FEED, "hit_gate": HIT, "arms": {k: list(v) for k, v in ARMS.items()},
           "summary": summ, "tests": tests, "verdict": verdict, "per": per}
    (out / "results.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({"summary": summ, "tests": tests, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    main()
