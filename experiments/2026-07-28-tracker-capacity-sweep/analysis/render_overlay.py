"""Score a fetched result against GT and render the overlay video.

GT is green at 60% alpha; the tracker output is light blue. A mask arm fills its mask, a
box-only arm fills its box, and both get a solid outline plus the per-frame IoU burned in.

Scoring lives here, on the host, because the device is never given GT past frame 0.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import uav123  # noqa: E402

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
        h0, w0 = cv2.imread(str(uav123.frame_paths(name)[0])).shape[:2]
        meta = {"arm": "GT", "seq": name, "w": w0, "h": h0}
    else:
        assert args.result_json, "pass a result json or --seq"
        res = json.loads(Path(args.result_json).read_text())
        meta, rows = res["meta"], {r["i"]: r for r in res["rows"]}
        name = meta["seq"]
    gt = uav123.boxes(name)
    frames = uav123.frame_paths(name)
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

    if args.out:
        h, w = meta["h"], meta["w"]
        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
             "-s", f"{w}x{h}", "-r", "30", "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", "-crf", "28", args.out], stdin=subprocess.PIPE)
        mid = Path(args.out).with_suffix(".mid.png")
        crop = crop_box((w / 2, h / 2), args.crop, w, h) if args.crop else None
        for i, fp in enumerate(frames):
            img = cv2.imread(str(fp))
            g, r = gt[i], rows.get(i)
            # two separate blends: one shared layer would let whichever is drawn last hide the
            # other exactly when they agree, which is the case worth seeing.
            if g:
                over = img.copy()
                cv2.rectangle(over, (int(g[0]), int(g[1])), (int(g[2]), int(g[3])), GREEN, -1)
                cv2.addWeighted(over, ALPHA, img, 1 - ALPHA, 0, img)
            over = img.copy()
            if r and r.get("contours"):
                polys = [np.array(c, np.int32) for c in r["contours"] if len(c) >= 3]
                if polys:
                    cv2.fillPoly(over, polys, LIGHTBLUE)
            elif r and r.get("box"):
                b = [int(v) for v in r["box"]]  # SAM2 boxes come back as floats
                cv2.rectangle(over, (b[0], b[1]), (b[2], b[3]), LIGHTBLUE, -1)
            cv2.addWeighted(over, ALPHA, img, 1 - ALPHA, 0, img)
            if g:
                cv2.rectangle(img, (int(g[0]), int(g[1])), (int(g[2]), int(g[3])), GREEN, 2)
            if r and r.get("box"):
                b = [int(v) for v in r["box"]]
                cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), LIGHTBLUE, 2)
            if args.crop:
                if g:  # GT gap: hold the last window rather than snapping it back to the centre
                    crop = crop_box(((g[0] + g[2]) / 2, (g[1] + g[3]) / 2), args.crop, w, h)
                cv2.rectangle(img, (crop[0], crop[1]), (crop[2], crop[3]), ORANGE, 2)

            parts = [meta["arm"], f"{name} {i + 1}/{len(frames)}", "GT=verde"]
            if rows:
                parts += [f"{hz:.1f} Hz", "pred=azul",
                          "LOST" if not (r and r.get("box")) else f"IoU {ious[i]:.2f}"]
            if args.crop:
                parts.append(f"crop {crop[2] - crop[0]}px=naranja")
            cv2.putText(img, "  ".join(parts), (12, h - 16),
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
