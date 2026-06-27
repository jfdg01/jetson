#!/usr/bin/env python3
"""Appearance-SNR vs range on VisDrone-MOT — validates the T2 permanence knob.

Measures the real appearance separation between an aerial target track and its
nearest same-class decoy, bucketed by crop area (range proxy). SNR = mean
decoy-distance / mean intra-target-distance. SNR >> 1 -> re-ID easy; SNR ~ 1 ->
the T2 collapse regime (reid_policy.py). See README.md for the pre-registration.

Descriptor: HSV 4x4x4 histogram (rung 1, ponytail: color before any model).
Distance: Hellinger (sqrt(1 - Bhattacharyya coefficient)), bounded [0,1].

Run:
  .venv-ft/bin/python score_appearance_snr.py                 # self-checks
  .venv-ft/bin/python score_appearance_snr.py --run val       # score a split
"""
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
MOT = os.path.join(HERE, "..", "..", "VisDrone", "MOT")
HB = 4  # hist bins per HSV channel -> 64-d descriptor
MIN_LEN = 20           # min visible frames for a usable target track
AREA_REF = 3000.0      # px^2 — pivot matching reid_policy.AREA_REF
AREA_EDGES = [0, 500, 1500, 3000, 8000, 1e9]  # crop-area buckets (px^2)


def descriptor(img, box):
    """HSV 4x4x4 L1-normalized histogram of the crop. box = (x,y,w,h)."""
    x, y, w, h = box
    crop = img.crop((x, y, x + w, y + h)).convert("HSV").resize((24, 24))
    a = np.asarray(crop, dtype=np.float64).reshape(-1, 3)
    hist, _ = np.histogramdd(a, bins=(HB, HB, HB),
                             range=((0, 256), (0, 256), (0, 256)))
    hist = hist.ravel()
    s = hist.sum()
    return hist / s if s > 0 else hist


def hellinger(p, q):
    """Bounded [0,1] distance between L1-normalized histograms."""
    return float(np.sqrt(max(0.0, 1.0 - np.sqrt(p * q).sum())))


def parse_mot(ann_path):
    """frame -> list of dicts {id, box=(x,y,w,h), cat, occ, area, cx, cy}."""
    frames = {}
    with open(ann_path) as f:
        for line in f:
            p = line.strip().split(",")
            if len(p) < 10:
                continue
            fr, tid, x, y, w, h = (int(float(v)) for v in p[:6])
            cat, occ = int(float(p[7])), int(float(p[9]))
            if cat == 0 or w <= 1 or h <= 1:        # ignored region / junk
                continue
            frames.setdefault(fr, []).append(
                dict(id=tid, box=(x, y, w, h), cat=cat, occ=occ,
                     area=float(w * h), cx=x + w / 2, cy=y + h / 2))
    return frames


def _img(seq_dir, fr):
    return Image.open(os.path.join(seq_dir, f"{fr:07d}.jpg")).convert("RGB")


def score_sequence(seq_dir, ann_path):
    """Return per-track SNR samples: list of (area, intra_d, decoy_d)."""
    frames = parse_mot(ann_path)
    # index detections by track id
    tracks = {}
    for fr, dets in frames.items():
        for d in dets:
            tracks.setdefault(d["id"], {})[fr] = d
    samples = []
    cache = {}  # fr -> PIL image (reload lazily; sequences are short)

    def img(fr):
        if fr not in cache:
            cache[fr] = _img(seq_dir, fr)
        return cache[fr]

    for tid, byfr in tracks.items():
        clear = sorted(fr for fr, d in byfr.items() if d["occ"] == 0)
        if len(clear) < MIN_LEN:
            continue
        # reference = mean descriptor over a sample of clear frames
        ref_frames = clear[:: max(1, len(clear) // 10)][:10]
        refs = [descriptor(img(fr), byfr[fr]["box"]) for fr in ref_frames]
        ref = np.mean(refs, axis=0)
        ref = ref / ref.sum() if ref.sum() > 0 else ref
        for fr in clear[:: max(1, len(clear) // 30)][:30]:
            d = byfr[fr]
            intra = hellinger(descriptor(img(fr), d["box"]), ref)
            # nearest same-category, un-occluded other track in this frame
            decoys = [o for o in frames[fr]
                      if o["cat"] == d["cat"] and o["id"] != tid and o["occ"] != 2]
            if not decoys:
                continue
            nd = min(decoys, key=lambda o: (o["cx"] - d["cx"]) ** 2
                     + (o["cy"] - d["cy"]) ** 2)
            decoy = hellinger(descriptor(img(fr), nd["box"]), ref)
            samples.append((d["area"], intra, decoy))
    return samples


def aggregate(samples):
    """SNR overall + per area bucket. SNR = mean(decoy) / mean(intra)."""
    def snr(rows):
        if not rows:
            return None
        intra = np.mean([r[1] for r in rows])
        decoy = np.mean([r[2] for r in rows])
        return dict(n=len(rows), intra=round(float(intra), 4),
                    decoy=round(float(decoy), 4),
                    snr=round(float(decoy / intra), 3) if intra > 0 else None)
    out = {"overall": snr(samples), "by_area": {}}
    for lo, hi in zip(AREA_EDGES[:-1], AREA_EDGES[1:]):
        rows = [r for r in samples if lo <= r[0] < hi]
        label = f"{lo:g}-{hi:g}" if hi < 1e9 else f"{lo:g}+"
        out["by_area"][label] = snr(rows)
    return out


def run_split(split):
    base = os.path.join(MOT, f"VisDrone2019-MOT-{split}")
    seqs = sorted(os.listdir(os.path.join(base, "sequences")))
    all_samples = []
    for s in seqs:
        ann = os.path.join(base, "annotations", f"{s}.txt")
        seq_dir = os.path.join(base, "sequences", s)
        if not os.path.exists(ann):
            continue
        sam = score_sequence(seq_dir, ann)
        all_samples += sam
        print(f"  {s}: {len(sam)} samples", file=sys.stderr)
    return aggregate(all_samples)


# ── self-check (ponytail: one runnable check) ─────────────────────────────────
def _test():
    # red target vs blue decoy must give SNR > 1; red vs slightly-noisy red ~ 1.
    red = Image.new("RGB", (64, 64), (200, 30, 30))
    blue = Image.new("RGB", (64, 64), (30, 30, 200))
    box = (0, 0, 64, 64)
    rd, bd = descriptor(red, box), descriptor(blue, box)
    assert hellinger(rd, rd) < 1e-9, "identical crops must have ~0 distance"
    assert hellinger(rd, bd) > 0.5, "red vs blue must be far"
    # synthetic SNR: intra (red vs red) tiny, decoy (red vs blue) large -> SNR huge
    agg = aggregate([(3000.0, hellinger(rd, rd) + 1e-3, hellinger(rd, bd))])
    assert agg["overall"]["snr"] > 1.0, "distinct decoy must yield SNR > 1"
    # area bucketing lands in the right bin
    assert agg["by_area"]["3000-8000"]["n"] == 1
    print("self-checks passed")


if __name__ == "__main__":
    if "--run" in sys.argv:
        split = sys.argv[sys.argv.index("--run") + 1]
        print(json.dumps(run_split(split), indent=2))
    else:
        _test()
