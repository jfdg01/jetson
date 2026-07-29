"""One arm over one sequence, in its own process. Writes <arm>__<seq>.json.

Streams frames from disk. Decode is timed separately and excluded from the tracker latency, so
`ms` is the model and nothing else. No ground truth here beyond the frame-0 init box: scoring is
the host's job, which makes it structurally impossible for an arm to peek at GT it should not see.
"""
from __future__ import annotations

import argparse
import json
import resource
import time
from pathlib import Path

import cv2
import numpy as np

import trackers

WARMUP = 5  # frames excluded from the latency summary (JIT, cuDNN autotune, first kernel)


def gpu_peak_mb() -> float | None:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.max_memory_allocated() / 2**20
    except Exception:
        pass
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--seq-dir", required=True, help="dir holding spec.json + frames/")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    sd = Path(args.seq_dir)
    spec = json.loads((sd / "spec.json").read_text())
    files = [sd / "frames" / f for f in spec["files"]]
    box0 = spec["init_box_xyxy"]

    first = cv2.imread(str(files[0]))
    assert first is not None, f"cannot decode {files[0]}"
    h, w = first.shape[:2]

    tr = trackers.build(args.arm)
    t0 = time.monotonic()
    b, cnts = tr.init(first, box0)
    init_s = time.monotonic() - t0

    # `win` is the exact (x, y, s) the arm sliced out of this frame, recorded so the host draws the
    # window the model really saw instead of re-deriving it and hoping the two agree.
    # `conf` is the arm's presence score: SAM2's trained occlusion head, AsymTrack's corner-peak
    # surrogate, None for arms that have neither. Recorded raw and uncalibrated -- both the VOT-LT
    # F-score and MaxGM sweep the threshold themselves, so only the ORDER has to mean anything.
    rows = [{"i": 0, "ms": init_s * 1000, "box": b, "contours": cnts, "init": True,
             "win": getattr(tr, "win", None), "conf": getattr(tr, "conf", None)}]
    decode_ms = []
    t_start = time.monotonic()
    for i, fp in enumerate(files[1:], start=1):
        if i % 50 == 0:  # a 27-arm sweep is unwatchable without this
            el = time.monotonic() - t_start
            print(f"  {i}/{len(files)}  {el:.0f}s  {i / el:.2f} fps  "
                  f"eta {(len(files) - i) / (i / el):.0f}s", flush=True)
        t = time.monotonic()
        frame = cv2.imread(str(fp))
        d = time.monotonic()
        b, cnts = tr.step(frame)
        e = time.monotonic()
        decode_ms.append((d - t) * 1000)
        rows.append({"i": i, "ms": (e - d) * 1000, "box": b, "contours": cnts,
                     "win": getattr(tr, "win", None), "conf": getattr(tr, "conf", None)})

    lat = np.array([r["ms"] for r in rows[1 + WARMUP:]])
    assert len(lat) > 0, "sequence too short to have any post-warmup frames"
    meta = {
        "arm": args.arm, "seq": spec["name"], "frames": len(rows), "w": w, "h": h,
        "init_ms": init_s * 1000, "warmup_frames": WARMUP,
        "ms_p50": float(np.percentile(lat, 50)), "ms_p95": float(np.percentile(lat, 95)),
        "ms_p99": float(np.percentile(lat, 99)), "ms_max": float(lat.max()),
        "fps": float(1000 / np.median(lat)),
        "decode_ms_p50": float(np.median(decode_ms)),
        "lost_frames": sum(1 for r in rows if r["box"] is None),
        # 0 here means the arm has no presence signal at all, which is a different thing from a
        # useless one -- and it is the failure that would otherwise show up as an empty analysis
        "conf_frames": sum(1 for r in rows if r["conf"] is not None),
        "rss_peak_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "gpu_peak_mb": gpu_peak_mb(),
    }
    Path(args.out).write_text(json.dumps({"meta": meta, "rows": rows}))
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
