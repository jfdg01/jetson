#!/usr/bin/env python3
"""Stage 4 — closed-loop following visualiser: memoryless baseline vs T2 re-ID, in the loop.

Replays the T3 closed-loop A/B (same harness, same scenario) through BOTH lock policies
and renders a side-by-side image-plane animation, so a viewer SEES the T3 result instead
of reading a coverage table: a same-class distractor crosses + briefly occludes the
moving target, the camera (cascade-PID) steers to centre whatever it is locked on. The
memoryless baseline grabs the distractor at the crossing and is steered off the true
target (lock box turns red, true target drifts to frame edge); the appearance re-ID gate
refuses the decoy and re-locks the true target after the blackout (stays green, centred).

No new control/perception code: it drives `run_t3.run_loop` with its `on_frame` hook to
capture the per-frame {true-target box, distractor box, lock box, covered} stream the
existing closed loop already produces, then draws them. Deterministic — same GIF on the
dev box or the Orin.

    .venv-ft/bin/python experiments/sitl/closedloop_viz.py            # self-check + GIF
    .venv-ft/bin/python experiments/sitl/closedloop_viz.py --out /tmp/closedloop.gif
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

here = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(here, ".."))        # experiments/ (run_t3)
sys.path.insert(0, here)                             # sitl/

import run_t3  # noqa: E402

IMG_W, IMG_H = 640, 480  # oracle_bbox pinhole image size
GREEN, RED, ORANGE, GRAY = (40, 190, 70), (220, 50, 50), (240, 150, 40), (130, 130, 135)


def _capture(policy, snr=8.0):
    """Run one closed-loop trial, grabbing the per-frame trace via the on_frame hook."""
    frames = []
    metrics = run_t3.run_loop(policy, snr=snr, dry_run=True, on_frame=frames.append)
    return frames, metrics


def _font(sz):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", sz)
    except OSError:
        return ImageFont.load_default()


def _box(d, b, col, w, scale, bar, label=None):
    x1, y1, x2, y2 = (b["cx"] - b["w"] / 2) * scale, (b["cy"] - b["h"] / 2) * scale + bar, \
                     (b["cx"] + b["w"] / 2) * scale, (b["cy"] + b["h"] / 2) * scale + bar
    d.rectangle([x1, y1, x2, y2], outline=col, width=w)
    if label:
        d.text((x1 + 2, max(bar, y1 - 13)), label, fill=col, font=_font(12))


def _panel(fr, title, metrics, scale):
    """One policy's frame: true target + distractor faint, the lock box coloured by hit."""
    pw, ph, bar = round(IMG_W * scale), round(IMG_H * scale), 54
    img = Image.new("RGB", (pw, ph + bar), (28, 28, 32))
    d = ImageDraw.Draw(img)

    # crosshair: the camera centres whatever it's locked on (cascade-PID image-plane error)
    d.line([(pw / 2, bar), (pw / 2, ph + bar)], fill=(60, 60, 66), width=1)
    d.line([(0, bar + ph / 2), (pw, bar + ph / 2)], fill=(60, 60, 66), width=1)

    objs = fr["objs"]
    # true target (use unsuppressed tgt_box so it's visible even while occluded)
    if fr["tgt_box"] is not None:
        occ = objs["target"] is None
        _box(d, fr["tgt_box"], (90, 130, 95) if occ else GRAY, 1, scale, bar,
             "target (occluded)" if occ else "target")
    if objs["distractor"]:
        _box(d, objs["distractor"], GRAY, 1, scale, bar, "distractor")

    lb = fr["lock_box"]
    if lb is None:
        d.text((pw / 2 - 44, ph / 2 + bar), "SEARCHING…", fill=ORANGE, font=_font(15))
    else:
        col = GREEN if fr["covered"] else RED
        _box(d, lb, col, 3, scale, bar, "LOCK" + ("" if fr["covered"] else "  WRONG"))

    d.text((8, 6), title, fill=(235, 235, 235), font=_font(15))
    d.text((8, 26), f"true-target coverage {metrics['true_target_coverage_pct']:.0f}%  "
                    f"t={fr['elapsed']:.0f}s", fill=(170, 170, 175), font=_font(12))
    return img, bar


def render(out_path, snr=8.0, stride=4, duration=70):
    base_fr, base_m = _capture("baseline", snr)
    reid_fr, reid_m = _capture("reid", snr)
    scale, gap = 0.62, 10

    frames = []
    for i in range(0, min(len(base_fr), len(reid_fr)), stride):
        lp, _ = _panel(base_fr[i], "Memoryless baseline", base_m, scale)
        rp, _ = _panel(reid_fr[i], f"Appearance re-ID (snr {snr:g})", reid_m, scale)
        W = lp.width + gap + rp.width
        canvas = Image.new("RGB", (W, lp.height + 22), (15, 15, 18))
        canvas.paste(lp, (0, 0))
        canvas.paste(rp, (lp.width + gap, 0))
        d = ImageDraw.Draw(canvas)
        d.text((8, lp.height + 4), "closed-loop SITL — cascade-PID centres the lock; "
               "distractor crosses+occludes the moving target → memoryless follows the "
               "WRONG vehicle, re-ID holds   green=on-target  red=wrong",
               fill=(150, 150, 155), font=_font(12))
        frames.append(canvas)

    frames[0].save(out_path, save_all=True, append_images=frames[1:],
                   duration=duration, loop=0, optimize=True)
    return out_path, base_m, reid_m


def out_default():
    return os.path.join(here, "..", "..", "results", "2026-06-24-t3-closed-loop",
                        "closedloop.gif")


def _selfcheck():
    """The viz must reproduce the T3 story: memoryless is steered off (coverage collapses),
    re-ID holds the moving target. If this fails, the demo would lie."""
    out = os.path.join(os.path.dirname(out_default()), "closedloop_selfcheck.gif")
    _, base_m, reid_m = render(out, snr=8.0, stride=8)
    bc, rc = base_m["true_target_coverage_pct"], reid_m["true_target_coverage_pct"]
    assert rc > bc and rc >= 80.0, (base_m, reid_m)
    assert os.path.getsize(out) > 0
    print(f"  selfcheck PASS  baseline coverage={bc}%  vs  re-ID coverage={rc}%  → {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=out_default())
    ap.add_argument("--snr", type=float, default=8.0)
    ap.add_argument("--stride", type=int, default=4)
    ap.add_argument("--duration", type=int, default=70, help="ms per GIF frame")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        print("closedloop_viz self-check:")
        _selfcheck()
    else:
        path, base_m, reid_m = render(args.out, args.snr, args.stride, args.duration)
        print(f"wrote {path}")
        print(f"  baseline: coverage {base_m['true_target_coverage_pct']}%")
        print(f"  re-ID   : coverage {reid_m['true_target_coverage_pct']}%")
