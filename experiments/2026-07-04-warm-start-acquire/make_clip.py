"""E24 secondary proof clip: WARM (fresh) vs COLD (stale) side by side on one clip
where WARM passes and COLD fails. Windowed around the delivery + coverage window
and downscaled so it stays committable. Reproducible from runs/*/results.json.

    .venv-ft/bin/python experiments/2026-07-04-warm-start-acquire/make_clip.py --clip car10
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
E18 = HERE.parents[1] / "experiments" / "2026-07-03-real-video-replay"
sys.path.insert(0, str(E18))
from replay_source import load_uav123_gt  # noqa: E402

PANEL_W = 440           # downscaled panel width (px); keeps the mp4 small
OUT_FPS = 15            # every 2nd native frame -> ~half the file size


def held_at(events, t):
    held = None
    for te, b in events:
        if te <= t:
            held = b
        else:
            break
    return held


def draw(frame, gt_box, held, label):
    if gt_box is not None:
        g = [int(v) for v in gt_box]
        cv2.rectangle(frame, (g[0], g[1]), (g[2], g[3]), (0, 0, 220), 3)
    if held is not None:
        b = [int(v) for v in held]
        cv2.rectangle(frame, (b[0], b[1]), (b[2], b[3]), (40, 200, 80), 3)
    tag = "LOST (no box yet)" if held is None else "TRACK"
    cv2.putText(frame, label, (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                (255, 255, 255), 3)
    cv2.putText(frame, tag, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (40, 200, 80) if held is not None else (60, 60, 230), 2)
    return frame


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", default="car10")
    ap.add_argument("--start", type=int, default=200)
    ap.add_argument("--end", type=int, default=560)
    args = ap.parse_args()

    runs = HERE / "runs"
    warm = json.load(open(runs / f"WARM_{args.clip}_r1/results.json"))
    cold = json.load(open(runs / f"COLD_{args.clip}_r1/results.json"))
    we = [(t, tuple(b) if b else None) for t, b in warm["events"]]
    ce = [(t, tuple(b) if b else None) for t, b in cold["events"]]
    fps = warm["fps"]
    wd = warm["warm"]["deliver_frame"]
    cd = cold["warm"]["deliver_frame"]

    seq = E18 / "data" / "UAV123" / "data_seq" / "UAV123" / args.clip
    anno = E18 / "data" / "UAV123" / "anno" / "UAV123" / f"{args.clip}.txt"
    gt = load_uav123_gt(anno)
    paths = sorted(seq.glob("*.jpg"))
    h0, w0 = cv2.imread(str(paths[0])).shape[:2]
    scale = PANEL_W / w0
    ph = int(h0 * scale)

    out = HERE / "proof" / f"{args.clip}_warm_vs_cold.mp4"
    vw = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), OUT_FPS,
                         (PANEL_W * 2 + 8, ph + 40))
    for i in range(args.start, min(args.end, len(paths)), 2):
        t = i / fps
        base = cv2.imread(str(paths[i]))
        gtb = gt[i] if i < len(gt) else None
        left = draw(base.copy(), gtb, held_at(we, t),
                    f"WARM  f={i}  (delivered @ {wd})")
        right = draw(base.copy(), gtb, held_at(ce, t),
                     f"COLD  f={i}  (delivered @ {cd})")
        left = cv2.resize(left, (PANEL_W, ph))
        right = cv2.resize(right, (PANEL_W, ph))
        sep = 255 * (0 * left[:, :8])  # black separator
        row = cv2.hconcat([left, sep[:, :8] if sep.shape[1] >= 8 else left[:, :8],
                           right])
        canvas = cv2.copyMakeBorder(row, 40, 0, 0, 0, cv2.BORDER_CONSTANT, value=(20, 20, 20))
        cv2.putText(canvas, "green=held box  red=GT   |   WARM locks fresh at prompt(240); "
                    "COLD waits, delivers stale (~375)", (10, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (235, 235, 235), 1)
        vw.write(canvas)
    vw.release()
    # re-encode mp4v -> h264 (much smaller, committable). ffmpeg is a repo tool.
    import shutil
    import subprocess
    if shutil.which("ffmpeg"):
        tmp = out.with_suffix(".h264.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out),
                        "-c:v", "libx264", "-crf", "30", "-preset", "slow",
                        "-pix_fmt", "yuv420p", str(tmp)], check=True)
        tmp.replace(out)
    print("wrote", out, f"({out.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
