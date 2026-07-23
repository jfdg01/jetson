"""E18 arms at frame-0 onset, with CLEAN delivery-frame stamping.

Why a fork and not replay_e18 directly: the R-34 smoke run exposed a latent
artifact in replay_e18's oracle leg. It stamps the seed event at `video.t()`,
which fires AFTER the ~1 s SAM2 init on frame 0, so the GT[0] box is scored at
frame ~33 instead of frame 0. On E18's warmer GPU that init was 0.34 s (frame
~10, still overlapping); here it is 1.1 s and the oracle spuriously FAILS
genuine_lock on fast targets. That is init latency leaking into the timeline, not
a modeled delay. P5.2a's replay_e24 already fixed this (schedule-fixed deliver
frame + coverage_realtime zeroes the wall clock at delivery); this harness reuses
that exact machinery at a frame-0 onset.

  COLD  (E18 leg A): real Jetson VLM acquires on frame 0, takes acq_wall s
        (MEASURED), the correct-on-frame-0 box is delivered STALE at frame
        round(acq_wall*fps); SAM2 carry seeds there; REGROUND on (mask gate).
  ORACLE(E18 leg B): SAM2 carry seeded from GT[0] delivered FRESH at frame 0;
        no VLM; REGROUND off.

Scored with score_run (E18's metric, unchanged): genuine_lock AND coverage>=0.5.
Reuses coverage_realtime / MaskGate / vlm_acquire / _rgb / _valid from replay_e24
(validated by its selfcheck), and WallClockVideo / score_run / load_uav123_gt /
iou from replay_source.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
E24 = REPO / "experiments" / "2026-07-04-warm-start-acquire"
SRC = REPO / "experiments" / "2026-07-01-temporal-acquire-carry"
for p in (E24, E18, SRC, REPO):
    sys.path.insert(0, str(p))

from replay_source import load_uav123_gt, score_run  # noqa: E402
from replay_e24 import (CARRY_HZ, MaskGate, coverage_realtime, render_overlay,  # noqa: E402
                        vlm_acquire, _rgb, _valid)

MAX_SIDE = 1024


def run_clean(leg, seq_dir, anno, caption, out_dir, fps=30.0):
    """One clip, one leg (COLD|ORACLE), frame-0 onset, clean stamping."""
    import torch
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    from stream_carry import MODEL, StreamCarry

    gt = load_uav123_gt(anno)
    assert gt[0] is not None, f"{Path(seq_dir).name}: GT[0] absent, cannot seed"
    predictor = SAM2VideoPredictor.from_pretrained(MODEL)
    paths = sorted(Path(seq_dir).glob("*.jpg"))
    h0, w0 = cv2.imread(str(paths[0])).shape[:2]
    frame_shape = (h0, w0, 3)
    clip_len = len(gt)

    def frame_at(idx):
        return cv2.imread(str(paths[min(idx, len(paths) - 1)]))

    def make_carry(frame_rgb, box):
        return StreamCarry(predictor, frame_rgb, box)

    be = None
    if leg == "COLD":
        from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
        from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
        from grounding.eval.backends import JetsonBackend
        print(f"[clean COLD {Path(seq_dir).name}] booting Jetson q8_0...", flush=True)
        be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                           f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                           ssh_host="jetson", max_side=MAX_SIDE)

    def submit(frame_bgr):
        if be is None:
            return None
        path = f"/dev/shm/e18clean_{time.monotonic_ns()}.png"
        cv2.imwrite(path, frame_bgr)
        try:
            return vlm_acquire(be, path, caption, w0, h0)
        finally:
            Path(path).unlink(missing_ok=True)

    meta = {"leg": leg}
    wall0 = time.time()
    try:
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            if leg == "ORACLE":
                box = gt[0]
                deliver = 0
                carry = make_carry(_rgb(frame_at(0)), box)
                events = [(0.0, tuple(box))]
                events += coverage_realtime(
                    carry, str(seq_dir), frame_at, gt, fps, deliver, clip_len,
                    reground=False, gate=None, submit=submit, make_carry=make_carry)
                meta.update({"acquire_s": None, "seed": "gt[0]", "deliver_frame": 0})

            elif leg == "COLD":
                t0 = time.monotonic()
                box = submit(frame_at(0))         # acquire on frame 0 (blocks)
                acq_s = time.monotonic() - t0
                acq_frames = round(acq_s * fps)
                deliver = acq_frames
                if not _valid(box, frame_shape) or deliver >= clip_len:
                    events = []
                    reason = "no box" if not _valid(box, frame_shape) else "deliver past end"
                    meta.update({"acquire_s": round(acq_s, 2), "seed": "vlm[0]",
                                 "deliver_frame": deliver, "reason": reason})
                else:
                    carry = make_carry(_rgb(frame_at(deliver)), box)  # seed at ARRIVAL
                    gate = MaskGate(predictor)
                    gate.bind(frame_at(deliver), carry.init_mask)
                    events = [(deliver / fps, tuple(box))]            # stale box
                    events += coverage_realtime(
                        carry, str(seq_dir), frame_at, gt, fps, deliver, clip_len,
                        reground=True, gate=gate, submit=submit, make_carry=make_carry)
                    meta.update({"acquire_s": round(acq_s, 2), "seed": "vlm[0]",
                                 "deliver_frame": deliver, "acq_frames": acq_frames,
                                 "seed_box": [round(v, 1) for v in box],
                                 "n_gate_reject": gate.n_reject})
            else:
                raise ValueError(leg)
    finally:
        if be is not None:
            be.close()
    wall = time.time() - wall0

    s = score_run(events, gt, fps)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "leg": leg, "clip": Path(seq_dir).name, "caption": caption, "fps": fps,
        "n_frames_gt": clip_len, "wall_s": round(wall, 1), "cap_hz": CARRY_HZ,
        "n_events": len(events), "meta": meta, "score": s,
        "events": [(round(t, 3), None if b is None else [round(v, 1) for v in b])
                   for t, b in events],
    }
    (out_dir / "results.json").write_text(json.dumps(result, indent=2))
    render_overlay(seq_dir, events, gt, fps, out_dir / "overlay.mp4")
    print(f"[clean {leg} {Path(seq_dir).name}] genuine={s['genuine_lock']} "
          f"cov={s['coverage']} mean_iou={s['mean_iou']} t_lock={s.get('t_lock')} "
          f"deliver_f={meta['deliver_frame']} acq={meta.get('acquire_s')} "
          f"wall={wall:.0f}s", flush=True)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leg", choices=["COLD", "ORACLE"], required=True)
    ap.add_argument("--clip", required=True)
    ap.add_argument("--caption", default="the car")
    ap.add_argument("--out")
    ap.add_argument("--fps", type=float, default=30.0)
    args = ap.parse_args()
    data = E18 / "data" / "UAV123"
    seq_dir = data / "data_seq" / "UAV123" / args.clip
    anno = data / "anno" / "UAV123" / f"{args.clip}.txt"
    out = Path(args.out) if args.out else (HERE / "runs" / f"{args.leg}_{args.clip}")
    run_clean(args.leg, seq_dir, anno, args.caption, out, fps=args.fps)


if __name__ == "__main__":
    main()
