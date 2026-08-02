"""Score a fetched result against GT and render the overlay video.

GT is green at 60% alpha; the tracker output is light blue. A mask arm fills its mask, a
box-only arm fills its box, and both get a solid outline plus the per-frame IoU burned in.

Scoring lives here, on the host, because the device is never given GT past frame 0.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data  # noqa: E402

GREEN = (0, 200, 0)
LIGHTBLUE = (255, 200, 100)  # BGR
ORANGE = (0, 160, 255)  # crop window; nothing else in these renders is warm-coloured
ALPHA = 0.6


def iou(a, b) -> float:
    if a is None or b is None:
        return float("nan")
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def crop_box(center: tuple[float, float], size: int, w: int, h: int) -> list[int]:
    """A `size`x`size` window centred on `center`, slid (not shrunk) to stay inside the frame.

    Sliding rather than clipping keeps every crop the same shape, so the model always sees the
    same input geometry -- a target hugging the border would otherwise silently change the
    effective resolution. Only a frame smaller than `size` forces a smaller box.
    """
    s = min(size, w, h)
    x = int(round(min(max(center[0] - s / 2, 0), w - s)))
    y = int(round(min(max(center[1] - s / 2, 0), h - s)))
    return [x, y, x + s, y + s]


def search_box(box, factor: float) -> list[int]:
    """Mirror of `device/trackers.py:search_window`, as (x, y, side).

    Duplicated for the same reason as `crop_box`: host and device do not import from each other.
    Both must change together or the overlay stops being evidence about what the arm did.
    """
    x1, y1, x2, y2 = box
    w, h = max(x2 - x1, 1.0), max(y2 - y1, 1.0)
    s = max(math.ceil(math.sqrt(w * h) * factor), 1)
    return [int(round(x1 + w / 2 - s / 2)), int(round(y1 + h / 2 - s / 2)), s]


def arm_factor(arm: str) -> float:
    """Search factor of an arm, from its name. 0 means a fixed window or no window at all."""
    m = re.match(r"sam2_f(\d+)$", arm)
    return float(m[1]) if m else (4.0 if arm.startswith("asym_") else 0.0)


def annotate(img, g, r, off=(0, 0)) -> None:
    """GT fill + outline, then prediction fill + outline. `off` shifts full-frame coords into a crop.

    Two separate blends: one shared layer would let whichever is drawn last hide the other exactly
    when they agree, which is the case worth seeing.
    """
    dx, dy = off
    if g:
        over = img.copy()
        cv2.rectangle(over, (int(g[0]) - dx, int(g[1]) - dy),
                      (int(g[2]) - dx, int(g[3]) - dy), GREEN, -1)
        cv2.addWeighted(over, ALPHA, img, 1 - ALPHA, 0, img)
    over = img.copy()
    if r and r.get("contours"):
        polys = [np.array(c, np.int32) - (dx, dy) for c in r["contours"] if len(c) >= 3]
        if polys:
            cv2.fillPoly(over, polys, LIGHTBLUE)
    elif r and r.get("box"):
        b = [int(v) for v in r["box"]]  # SAM2 boxes come back as floats
        cv2.rectangle(over, (b[0] - dx, b[1] - dy), (b[2] - dx, b[3] - dy), LIGHTBLUE, -1)
    cv2.addWeighted(over, ALPHA, img, 1 - ALPHA, 0, img)
    if g:
        cv2.rectangle(img, (int(g[0]) - dx, int(g[1]) - dy),
                      (int(g[2]) - dx, int(g[3]) - dy), GREEN, 2)
    if r and r.get("box"):
        b = [int(v) for v in r["box"]]
        cv2.rectangle(img, (b[0] - dx, b[1] - dy), (b[2] - dx, b[3] - dy), LIGHTBLUE, 2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("result_json", nargs="?", help="omit when using --seq")
    ap.add_argument("--seq", help="render GT only for this sequence, with no tracker result")
    ap.add_argument("--out", help="mp4 path; omit to score without rendering")
    ap.add_argument("--crop", type=int, metavar="N",
                    help="also draw the NxN crop window centred on GT (crop mode preview)")
    args = ap.parse_args()

    if args.seq:
        name, rows = args.seq, {}
        h0, w0 = cv2.imread(str(data.frame_paths(name)[0])).shape[:2]
        meta = {"arm": "GT", "seq": name, "w": w0, "h": h0}
    else:
        assert args.result_json, "pass a result json or --seq"
        res = json.loads(Path(args.result_json).read_text())
        meta, rows = res["meta"], {r["i"]: r for r in res["rows"]}
        name = meta["seq"]
    gt = data.boxes(name)
    frames = data.frame_paths(name)
    assert len(gt) == len(frames), f"{name}: {len(gt)} anno vs {len(frames)} frames"

    ious = np.array([iou(gt[i], rows.get(i, {}).get("box")) for i in range(len(frames))])
    ok = ~np.isnan(ious)
    score = {"arm": meta["arm"], "seq": name, "frames": len(frames), "scored_frames": int(ok.sum())}
    if ok.any():
        score |= {
            "mean_iou": float(ious[ok].mean()),
            "iou@0.25": float((ious[ok] >= 0.25).mean()),
            "iou@0.5": float((ious[ok] >= 0.5).mean()),
            "lost_frames": meta["lost_frames"],
            "ms_p50": meta["ms_p50"], "fps": meta["fps"],
        }

    # mean, not median: the burned-in rate should include the slow frames, since a tail stall is
    # exactly what a follow loop feels. meta["fps"] stays median-based so the tables do not move.
    if rows:
        lat = [r["ms"] for r in rows.values() if not r.get("init")][meta["warmup_frames"]:]
        hz = 1000 / (sum(lat) / len(lat))
        score["mean_hz"] = hz

    # Provenance check for crop arms: every window the device recorded must be the one this file's
    # own geometry derives from the previous frame's box. If the two ever disagree, the panel would
    # be showing something the model never saw, which is the one lie this render must not tell.
    #
    # Only frames whose PREVIOUS frame was a hit are derivable. After a loss the recovery arms
    # (`_coast` slides the window, `_edge` drops to the full frame and records win=None) move it
    # from state this file cannot see, so those frames are skipped rather than asserted -- the panel
    # is still drawn from the recorded window either way, so it is never a lie, just unverified.
    #
    # Both window geometries are re-derivable, so both are asserted rather than trusted. A fixed
    # arm slides a constant NxN inside the frame; a target-scaled arm rebuilds the window every
    # frame as `factor * sqrt(w*h)` around the previous box, which is just as checkable once the
    # factor is known -- and checking it is what caught the round-vs-ceil drift in `AsymArm`.
    fac = arm_factor(meta["arm"])
    if rows and rows.get(1, {}).get("win") and (fac or meta["arm"].startswith("sam2_")):
        n, checked = rows[1]["win"][2], 0
        for i in range(2, len(frames)):
            b, win = rows[i - 1]["box"], rows[i].get("win")
            if win is None:  # arm fed the full frame this step
                continue
            if b is None:
                # Plain SAM2 crop arm: a lost frame holds the window where it was. Not true of
                # `asym_lt`, whose whole point is that a lost frame MOVES the window -- that is the
                # re-detection sweep.
                if meta["arm"].startswith("sam2_") and "_" not in meta["arm"][5:]:
                    assert win == rows[i - 1]["win"], (i, win)
                continue
            if fac:
                e = search_box(b, fac)
            elif meta["arm"].endswith("_pad"):
                # The pad arm does NOT slide: the window stays centred on the target and hangs off
                # the frame, so its origin is routinely negative. Re-deriving it with `crop_box`
                # checks the wrong geometry -- that is the whole treatment under test.
                cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                e = [round(cx - n / 2), round(cy - n / 2), n]
            else:
                c = crop_box(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), n, meta["w"], meta["h"])
                e = [c[0], c[1], c[2] - c[0]]
            if meta["arm"].startswith("asym_"):
                # The side is not checkable for these arms. The device builds the window from the
                # tracker's float `state`, the row records the box int-truncated, and the side is
                # `ceil(factor * sqrt(w*h))` -- on a car12-sized target (~19 px) losing a fraction
                # of a pixel on w and h moves the side by 3. What IS checkable, and what this
                # assert is really for, is that the window is centred on the box it claims to
                # follow: a window built from the wrong box is off by tens of pixels.
                assert all(abs((win[k] + win[2] / 2) - (b[k] + b[k + 2]) / 2) <= 2
                           for k in (0, 1)), (i, win, b)
            else:
                assert win == e, (i, win, e)
            checked += 1
        score["win_checked"] = checked

    if args.out:
        h, w = meta["h"], meta["w"]
        # A crop arm records the window it sliced; the panel is drawn from that recorded value, not
        # re-derived here, so what the video shows cannot silently disagree with what the arm did.
        win = rows.get(1, {}).get("win") if rows else None
        # A fixed-window arm needs a column as wide as its one window; a target-scaled arm needs
        # the widest window it ever asked for, and each frame's panel is pasted top-left inside it.
        cw = max((r["win"][2] for r in rows.values() if r.get("win")), default=0) if win else 0
        cw += cw % 2
        # A crop arm gets its own caption strip below the frame: at 704 the text baseline lands
        # inside the window, and the caption must not paint over the pixels it claims are the input.
        bar = 28 if win else 0
        cvw, cvh = w + cw, max(h, cw) + bar
        assert cvw % 2 == 0 and cvh % 2 == 0, f"yuv420p needs even dims, got {cvw}x{cvh}"
        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
             "-s", f"{cvw}x{cvh}", "-r", "30", "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", "-crf", "28", args.out], stdin=subprocess.PIPE)
        mid = Path(args.out).with_suffix(".mid.png")
        crop = crop_box((w / 2, h / 2), args.crop, w, h) if args.crop else None
        for i, fp in enumerate(frames):
            raw = cv2.imread(str(fp))
            img = raw.copy()
            g, r = gt[i], rows.get(i)
            annotate(img, g, r)
            if args.crop:
                if g:  # GT gap: hold the last window rather than snapping it back to the centre
                    crop = crop_box(((g[0] + g[2]) / 2, (g[1] + g[3]) / 2), args.crop, w, h)
                cv2.rectangle(img, (crop[0], crop[1]), (crop[2], crop[3]), ORANGE, 2)

            if win and r is not None and r.get("win") is None:
                # `edge` arm dropped to the whole frame this step. Outlining the old crop here would
                # claim an input the model was not given, so outline the frame and letterbox it.
                s = win[2]
                cv2.rectangle(img, (1, 1), (w - 2, h - 2), ORANGE, 2)
                shot = raw.copy()
                annotate(shot, g, r)
                sc = min(s / w, s / h)
                rz = cv2.resize(shot, (int(w * sc), int(h * sc)))
                canvas = np.zeros((cvh, cvw, 3), np.uint8)
                canvas[:h, :w] = img
                canvas[:rz.shape[0], w:w + rz.shape[1]] = rz
                img = canvas
            elif win:
                x, y, s = r["win"] if r and r.get("win") else win
                # A target-scaled window can hang off the frame; the arm's own crop pads there, so
                # the panel shows only the part that exists rather than wrapping a negative slice.
                cx, cy = max(x, 0), max(y, 0)
                x2, y2 = min(x + s, w), min(y + s, h)
                # the model's input, byte for byte: the same decoded jpeg sliced with the same
                # integers the arm used. Annotations go on this copy, never on `raw`.
                panel = raw[cy:y2, cx:x2].copy()
                # restore the window interior on the left panel so it stays literally the model
                # input, then outline it from outside -- a 2 px line centred on the border would
                # paint into the region it is claiming is untouched.
                img[cy:y2, cx:x2] = raw[cy:y2, cx:x2]
                cv2.rectangle(img, (x - 2, y - 2), (x + s + 1, y + s + 1), ORANGE, 2)
                annotate(panel, g, r, off=(cx, cy))
                canvas = np.zeros((cvh, cvw, 3), np.uint8)
                canvas[:h, :w] = img
                ph, pw = panel.shape[:2]
                canvas[:ph, w:w + pw] = panel  # no border: it would paint over the input itself
                img = canvas

            parts = [meta["arm"], f"{name} {i + 1}/{len(frames)}", "GT=verde"]
            if rows:
                parts += [f"{hz:.1f} Hz", "pred=azul",
                          "LOST" if not (r and r.get("box")) else f"IoU {ious[i]:.2f}"]
            if win:
                # the CURRENT frame's window, not frame 1's: on a target-scaled arm they differ
                parts.append(f"entrada {(r['win'] if r and r.get('win') else win)[2]}px=naranja "
                             f"(derecha)")
            elif args.crop:
                parts.append(f"crop {crop[2] - crop[0]}px=naranja")
            cv2.putText(img, "  ".join(parts), (12, cvh - 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            if i == len(frames) // 2:  # mid-run still for visual verification, never frame 0
                cv2.imwrite(str(mid), img)
            ff.stdin.write(img.tobytes())
        ff.stdin.close()
        assert ff.wait() == 0, "ffmpeg failed"
        score["mp4"], score["mid_png"] = args.out, str(mid)

    print(json.dumps(score, indent=1))


def _check() -> None:
    assert crop_box((640, 360), 512, 1280, 720) == [384, 104, 896, 616]  # centred, fits
    assert crop_box((10, 10), 512, 1280, 720) == [0, 0, 512, 512]  # slid off the top-left corner
    assert crop_box((1270, 710), 512, 1280, 720) == [768, 208, 1280, 720]  # bottom-right
    for c in [crop_box((x, y), 512, 1280, 720) for x in (0, 640, 1279) for y in (0, 360, 719)]:
        assert c[2] - c[0] == c[3] - c[1] == 512, c  # never shrinks while it fits
    assert crop_box((640, 360), 1024, 1280, 720) == [280, 0, 1000, 720]  # capped by frame height


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        _check()
        print("crop_box ok")
    else:
        main()
