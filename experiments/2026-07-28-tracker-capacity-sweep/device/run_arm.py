"""One arm over one sequence, in its own process. Writes <arm>__<seq>.json.

Streams frames from disk. Decode is timed separately and excluded from the tracker latency, so
`ms` is the model and nothing else. No ground truth here beyond the frame-0 init box: scoring is
the host's job, which makes it structurally impossible for an arm to peek at GT it should not see.

`--fps` turns the loop from frame-parity into a live stream. Without it every arm sees every
frame no matter how long it took, which quietly hands a 431 ms arm the same input as a 30 ms one
and hides the cost of being slow. With it, the arm gets whatever frame is live when it finishes
the previous one -- everything captured in between is dropped, as a camera does. Pacing runs on
the recorded wall clock, not on `sleep`, so a slow arm is CHEAPER here than in parity mode.

Caveat to declare with any number from this mode: the clock only advances by tracker latency.
Decode is excluded, so real end-to-end staleness is `decode_ms_p50` worse than what this measures.
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


def next_frame(i: int, t: float, fps: float) -> tuple[int, float]:
    """Which frame is live at `t` seconds, given `i` was the last one consumed, and when it lands.

    Drop-to-latest, as a camera does: everything captured while the arm was busy is gone except the
    newest. `max(i + 1, ...)` covers the arm that outruns the stream -- it cannot consume a frame
    twice, so it waits, and the clock jumps forward to that frame's capture time.
    """
    if not fps:
        return i + 1, t
    nxt = max(i + 1, int(t * fps))
    return nxt, max(t, nxt / fps)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--seq-dir", required=True, help="dir holding spec.json + frames/")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=0.0,
                    help="stream rate: consume the frame that is live when the previous step ends, "
                         "dropping what went past. 0 = every frame (unbounded-compute upper bound)")
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
    # `t` is the stream clock in seconds: when this row's ANSWER lands, not when its frame was
    # captured. The host scores by holding each box from its `t` until the next one, which is what
    # a follow loop actually consumes. In parity mode it is just a running total and nobody reads it.
    rows = [{"i": 0, "ms": init_s * 1000, "t": 0.0, "box": b, "contours": cnts, "init": True,
             "win": getattr(tr, "win", None), "conf": getattr(tr, "conf", None),
             "conf_cos": getattr(tr, "conf_cos", None)}]
    decode_ms = []
    # The stream clock starts at 0, NOT at init_s: measured init is ~5.1 s on `sam2_c640`, which is
    # CUDA context + first-kernel warmup (the same thing WARMUP=5 exists to exclude), and charging it
    # to the stream would model a system that loads the model at designation time. The deployment
    # keeps the tracker resident and warm. init_ms is recorded, so it can be added back on purpose.
    t_wall = 0.0
    i = 0
    t_start = time.monotonic()
    while True:
        nxt, t_wall = next_frame(i, t_wall, args.fps)
        if nxt >= len(files):
            break
        i = nxt
        if i % 50 == 0:  # a 27-arm sweep is unwatchable without this
            el = time.monotonic() - t_start
            print(f"  {i}/{len(files)}  {el:.0f}s  {i / el:.2f} fps  "
                  f"eta {(len(files) - i) / (i / el):.0f}s", flush=True)
        t = time.monotonic()
        frame = cv2.imread(str(files[i]))
        d = time.monotonic()
        b, cnts = tr.step(frame)
        e = time.monotonic()
        decode_ms.append((d - t) * 1000)
        t_wall += e - d
        rows.append({"i": i, "ms": (e - d) * 1000, "t": t_wall, "box": b, "contours": cnts,
                     "win": getattr(tr, "win", None), "conf": getattr(tr, "conf", None),
                     "conf_cos": getattr(tr, "conf_cos", None)})

    lat = np.array([r["ms"] for r in rows[1 + WARMUP:]])
    assert len(lat) > 0, "sequence too short to have any post-warmup frames"
    meta = {
        "arm": args.arm, "seq": spec["name"], "frames": len(rows), "w": w, "h": h,
        # in paced mode `frames` is what the arm PROCESSED; the stream had `stream_frames`
        "fps_stream": args.fps or None, "stream_frames": len(files),
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
