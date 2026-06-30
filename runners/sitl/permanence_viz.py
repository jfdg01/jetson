#!/usr/bin/env python3
"""Demo 2 — object-permanence visualiser: memoryless ByteTrack vs appearance re-ID.

Replays a T1 kinematic clip through BOTH lock policies and renders a side-by-side
top-down (image-plane) animation, so a viewer SEES the T2 result instead of reading a
metrics table: when the same-class distractor crosses + briefly occludes the target,
the memoryless baseline steals the lock onto the decoy (box turns red), while the
appearance re-ID policy refuses the wrong object and re-locks the true target (green).

No new perception code: it monkeypatches `assemble_scores` to capture the per-frame
`preds` / `locked_gt` streams the two existing scorers already build
(`clip_recorder.score_clip` = memoryless, `reid_policy.score_clip_reid` = T2), then
draws them. Deterministic — same GIF on the dev box or on the Orin.

    .venv-ft/bin/python runners/sitl/permanence_viz.py            # self-check + GIF
    .venv-ft/bin/python runners/sitl/permanence_viz.py \
        --clip experiments/2026-06-18-t1-temporal-contract/clips/crossing_occlusion \
        --snr 8 --stride 2 --out /tmp/permanence.gif

Output is an animated GIF (PIL only, no ffmpeg). For an mp4:
    ffmpeg -i permanence.gif permanence.mp4
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

here = os.path.dirname(__file__)
sys.path.insert(0, here)
sys.path.insert(0, os.path.join(here, "..", ".."))

import clip_recorder  # noqa: E402
import reid_policy  # noqa: E402
from clip_recorder import load_clip  # noqa: E402

IMG_W, IMG_H = 640, 480
GREEN, RED, ORANGE, GRAY = (40, 190, 70), (220, 50, 50), (240, 150, 40), (150, 150, 150)


def _capture(scorer, *args, **kw):
    """Run a scorer, intercepting the per-frame streams it hands to assemble_scores."""
    grabbed = {}
    real = clip_recorder.assemble_scores

    def spy(name, tgt_id, preds, gts, vis, locked_gt, correct, timeout=30):
        grabbed.update(preds=preds, locked_gt=locked_gt, tgt_id=tgt_id)
        return real(name, tgt_id, preds, gts, vis, locked_gt, correct, timeout)

    # both modules look up assemble_scores in their own namespace — patch both
    clip_recorder.assemble_scores = spy
    reid_policy.assemble_scores = spy
    try:
        scores = scorer(*args, **kw)
    finally:
        clip_recorder.assemble_scores = real
        reid_policy.assemble_scores = real
    return grabbed, scores


def _font(sz):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", sz)
    except OSError:
        return ImageFont.load_default()


def _panel(recs, fi, pred, locked_gt, tgt_id, title, scores, scale):
    """One policy's frame: GT objects faint, the locked box coloured by what it's on."""
    pw, ph, bar = round(IMG_W * scale), round(IMG_H * scale), 56
    img = Image.new("RGB", (pw, ph + bar), (28, 28, 32))
    d = ImageDraw.Draw(img)
    f, fs = _font(15), _font(12)

    for o in recs[fi]["objects"]:
        if not o["box"] or not o["visible"]:
            continue
        x1, y1, x2, y2 = (c * scale for c in o["box"])
        y1, y2 = y1 + bar, y2 + bar
        d.rectangle([x1, y1, x2, y2], outline=GRAY, width=1)
        d.text((x1 + 2, y1 + 1), o["id"], fill=GRAY, font=fs)

    if pred is None:
        d.text((pw / 2 - 48, ph / 2 + bar), "SEARCHING…", fill=ORANGE, font=f)
    else:
        col = GREEN if locked_gt == tgt_id else RED
        x1, y1, x2, y2 = (c * scale for c in pred)
        d.rectangle([x1, y1 + bar, x2, y2 + bar], outline=col, width=3)
        tag = f"LOCK → {locked_gt}" + ("" if locked_gt == tgt_id else "  WRONG")
        tw = d.textlength(tag, font=fs)
        tx = min(x1 + 2, pw - tw - 3)  # keep the whole label inside the panel
        d.text((max(2, tx), y1 + bar - 14), tag, fill=col, font=fs)

    d.text((8, 6), title, fill=(235, 235, 235), font=f)
    d.text((8, 26), f"purity {scores['identity_purity']:.2f}  "
                    f"ID-sw {scores['id_switches']}  cov {scores['oracle_coverage']:.2f}",
           fill=(170, 170, 175), font=fs)
    return img, bar


def render(clip_dir, out_path, snr=8.0, stride=2, duration=80):
    _, recs = load_clip(clip_dir)
    ml, ml_s = _capture(clip_recorder.score_clip, clip_dir)
    rid, rid_s = _capture(reid_policy.score_clip_reid, clip_dir, snr=snr)
    tgt = ml["tgt_id"]
    scale = 0.62
    gap = 10

    frames = []
    for fi in range(0, len(recs), stride):
        lp, lbar = _panel(recs, fi, ml["preds"][fi], ml["locked_gt"][fi], tgt,
                          "Memoryless ByteTrack", ml_s, scale)
        rp, _ = _panel(recs, fi, rid["preds"][fi], rid["locked_gt"][fi], tgt,
                       f"Appearance re-ID (snr {snr:g})", rid_s, scale)
        W = lp.width + gap + rp.width
        canvas = Image.new("RGB", (W, lp.height + 22), (15, 15, 18))
        canvas.paste(lp, (0, 0))
        canvas.paste(rp, (lp.width + gap, 0))
        d = ImageDraw.Draw(canvas)
        d.text((8, lp.height + 4), f"crossing_occlusion  frame {fi}/{len(recs)}   "
               "target crosses the distractor then leaves frame → on re-acq memoryless "
               "grabs the wrong object   green=on-target  red=wrong",
               fill=(150, 150, 155), font=_font(12))
        frames.append(canvas)

    frames[0].save(out_path, save_all=True, append_images=frames[1:],
                   duration=duration, loop=0, optimize=True)
    return out_path, ml_s, rid_s


def _selfcheck():
    """The viz must reproduce the T2 story: memoryless mis-locks (purity<1, an ID switch),
    re-ID holds identity (purity 1, no switch). If this fails, the demo would lie."""
    clip = os.path.join(here, "..", "..", "results", "2026-06-18-t1-temporal-contract",
                        "clips", "crossing_occlusion")
    out = os.path.join(os.path.dirname(out_default()), "permanence_selfcheck.gif")
    _, ml_s, rid_s = render(clip, out, snr=8.0, stride=4)
    assert ml_s["identity_purity"] < 1.0 and ml_s["id_switches"] >= 1, ml_s
    assert rid_s["identity_purity"] == 1.0 and rid_s["id_switches"] == 0, rid_s
    assert os.path.getsize(out) > 0
    print(f"  selfcheck PASS  memoryless purity={ml_s['identity_purity']} "
          f"(id-sw {ml_s['id_switches']})  vs  re-ID purity={rid_s['identity_purity']} "
          f"(id-sw {rid_s['id_switches']})  → {out}")


def out_default():
    return os.path.join(here, "..", "..", "results", "2026-06-24-t2-permanence",
                        "permanence.gif")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clip", default=os.path.join(
        here, "..", "..", "results", "2026-06-18-t1-temporal-contract",
        "clips", "crossing_occlusion"))
    ap.add_argument("--out", default=out_default())
    ap.add_argument("--snr", type=float, default=8.0)
    ap.add_argument("--stride", type=int, default=2)
    ap.add_argument("--duration", type=int, default=80, help="ms per GIF frame")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        print("permanence_viz self-check:")
        _selfcheck()
    else:
        path, ml_s, rid_s = render(args.clip, args.out, args.snr, args.stride, args.duration)
        print(f"wrote {path}")
        print(f"  memoryless: purity {ml_s['identity_purity']}  id-sw {ml_s['id_switches']}"
              f"  cov {ml_s['oracle_coverage']:.3f}")
        print(f"  re-ID     : purity {rid_s['identity_purity']}  id-sw {rid_s['id_switches']}"
              f"  cov {rid_s['oracle_coverage']:.3f}")
