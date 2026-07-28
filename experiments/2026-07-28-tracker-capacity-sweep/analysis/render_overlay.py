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
ALPHA = 0.6


def iou(a, b) -> float:
    if a is None or b is None:
        return float("nan")
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("result_json")
    ap.add_argument("--out", help="mp4 path; omit to score without rendering")
    args = ap.parse_args()

    res = json.loads(Path(args.result_json).read_text())
    meta, rows = res["meta"], {r["i"]: r for r in res["rows"]}
    name = meta["seq"]
    gt = uav123.boxes(name)
    frames = uav123.frame_paths(name)
    assert len(gt) == len(frames), f"{name}: {len(gt)} anno vs {len(frames)} frames"

    ious = np.array([iou(gt[i], rows.get(i, {}).get("box")) for i in range(len(frames))])
    ok = ~np.isnan(ious)
    score = {
        "arm": meta["arm"], "seq": name, "frames": len(frames),
        "scored_frames": int(ok.sum()),
        "mean_iou": float(ious[ok].mean()),
        "iou@0.25": float((ious[ok] >= 0.25).mean()),
        "iou@0.5": float((ious[ok] >= 0.5).mean()),
        "lost_frames": meta["lost_frames"],
        "ms_p50": meta["ms_p50"], "fps": meta["fps"],
    }

    if args.out:
        h, w = meta["h"], meta["w"]
        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
             "-s", f"{w}x{h}", "-r", "30", "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", "-crf", "28", args.out], stdin=subprocess.PIPE)
        mid = Path(args.out).with_suffix(".mid.png")
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
            tag = "LOST" if not (r and r.get("box")) else f"IoU {ious[i]:.2f}"
            cv2.putText(img, f"{meta['arm']}  {name} {i + 1}/{len(frames)}  GT=verde  pred=azul  {tag}",
                        (12, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            if i == len(frames) // 2:  # mid-run still for visual verification, never frame 0
                cv2.imwrite(str(mid), img)
            ff.stdin.write(img.tobytes())
        ff.stdin.close()
        assert ff.wait() == 0, "ffmpeg failed"
        score["mp4"], score["mid_png"] = args.out, str(mid)

    print(json.dumps(score, indent=1))


if __name__ == "__main__":
    main()
