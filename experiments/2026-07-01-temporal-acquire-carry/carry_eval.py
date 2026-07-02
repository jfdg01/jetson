"""Phase 0: SAM2 zero-shot memory-carry on AerialMind (RQ-T.1).

Prompt SAM2.1 video predictor with the first GT box of a track, propagate,
score the carried mask-box against GT per labeled frame. No fine-tuning.

    .venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/carry_eval.py \
        --smoke                      # 1 sequence, sanity
    .venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/carry_eval.py  # full 93-seq run

RAM note: SAM2 init_state decodes the whole frame dir (fp32 @1024^2 ~12.6 MB/frame;
max seq 1859 frames ~23 GB vs ~26 GB free), so each track gets a symlinked temp
window of <= --cap frames starting at the track's first labeled frame.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

from aerialmind import GAP_MIN_FRAMES, Box, Sequence, Track, load_sequences, pick_eval_tracks  # noqa: E402
from grounding.manifest import capture, write as write_manifest  # noqa: E402

MODEL = "facebook/sam2.1-hiera-tiny"
RECOVERY_WINDOW = 5  # labeled frames after a gap in which IoU>=0.25 counts as recovery


def iou(a: Box, b: Box) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def mask_to_box(mask: np.ndarray) -> Box | None:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return (float(xs.min()), float(ys.min()), float(xs.max()) + 1, float(ys.max()) + 1)


def run_track(predictor, seq: Sequence, track: Track, cap: int) -> dict:
    """Propagate SAM2 from the track's first GT box; score against GT labels."""
    frames = [n for n in seq.frame_nums if track.start <= n][:cap]
    with tempfile.TemporaryDirectory(dir="/dev/shm") as tmp:
        for i, n in enumerate(frames):
            (Path(tmp) / f"{i:07d}.jpg").symlink_to(seq.frame_path(n))
        t0 = time.time()
        state = predictor.init_state(
            tmp, offload_video_to_cpu=True, async_loading_frames=False
        )
        predictor.add_new_points_or_box(
            state, frame_idx=0, obj_id=1, box=np.array(track.boxes[track.start])
        )
        preds: dict[int, Box | None] = {}
        for fidx, _ids, logits in predictor.propagate_in_video(state):
            preds[frames[fidx]] = mask_to_box((logits[0, 0] > 0.0).cpu().numpy())
        wall = time.time() - t0
        predictor.reset_state(state)

    # score on labeled frames only (GT is sparse where the target is occluded)
    labeled = [n for n in frames if n in track.boxes]
    ious = [iou(preds[n], track.boxes[n]) if preds.get(n) else 0.0 for n in labeled]
    other = {tid: t for tid, t in seq.tracks().items() if tid != track.tid}

    # id consistency: on frames where the pred box overlaps SOME GT box (>0.1),
    # is the best-overlap track the target?
    matched = right = 0
    for n in labeled:
        p = preds.get(n)
        if not p:
            continue
        cands = {track.tid: track.boxes[n]}
        cands.update({tid: t.boxes[n] for tid, t in other.items() if n in t.boxes})
        best_tid = max(cands, key=lambda tid: iou(p, cands[tid]))
        if iou(p, cands[best_tid]) > 0.1:
            matched += 1
            right += best_tid == track.tid

    # occlusion recovery: after each gap, IoU>=0.25 within RECOVERY_WINDOW labeled frames
    gaps = [(g, ln) for g, ln in track.gaps() if g < frames[-1]]
    recovered = 0
    for gstart, glen in gaps:
        after = [n for n in labeled if n >= gstart + glen][:RECOVERY_WINDOW]
        if any(preds.get(n) and iou(preds[n], track.boxes[n]) >= 0.25 for n in after):
            recovered += 1

    return {
        "seq": seq.name,
        "tid": track.tid,
        "n_frames": len(frames),
        "n_labeled": len(labeled),
        "mean_iou": float(np.mean(ious)),
        "iou_at_25": float(np.mean([v >= 0.25 for v in ious])),
        "iou_at_50": float(np.mean([v >= 0.50 for v in ious])),
        "id_consistency": right / matched if matched else None,
        "pred_absent_frac": float(np.mean([preds.get(n) is None for n in labeled])),
        "n_gaps": len(gaps),
        "n_recovered": recovered,
        "wall_s": round(wall, 2),
        "fps": round(len(frames) / wall, 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=300, help="max frames per track window")
    ap.add_argument("--smoke", action="store_true", help="one sequence only")
    ap.add_argument("--out", default=str(HERE / "runs" / "phase0-zeroshot-carry"))
    ap.add_argument("--image-size", type=int, default=None,
                    help="override model.image_size (Phase 2 Jetson-FPS lever; default 1024)")
    args = ap.parse_args()

    from sam2.sam2_video_predictor import SAM2VideoPredictor

    over = [f"++model.image_size={args.image_size}"] if args.image_size else []
    predictor = SAM2VideoPredictor.from_pretrained(MODEL, hydra_overrides_extra=over)
    seqs = load_sequences(limit=1 if args.smoke else None)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    t_start = time.time()
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        for i, seq in enumerate(seqs):
            for track in pick_eval_tracks(seq):
                r = run_track(predictor, seq, track, args.cap)
                rows.append(r)
                print(
                    f"[{i + 1}/{len(seqs)}] {r['seq']} tid={r['tid']} "
                    f"iou25={r['iou_at_25']:.3f} mean={r['mean_iou']:.3f} "
                    f"gaps={r['n_gaps']} rec={r['n_recovered']} fps={r['fps']}",
                    flush=True,
                )

    with (out_dir / "per_track.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    n_gaps = sum(r["n_gaps"] for r in rows)
    idc = [r["id_consistency"] for r in rows if r["id_consistency"] is not None]
    summary = {
        "model": MODEL,
        "image_size": args.image_size or 1024,
        "cap": args.cap,
        "n_tracks": len(rows),
        "mean_iou": float(np.mean([r["mean_iou"] for r in rows])),
        "iou_at_25": float(np.mean([r["iou_at_25"] for r in rows])),
        "iou_at_50": float(np.mean([r["iou_at_50"] for r in rows])),
        "id_consistency": float(np.mean(idc)) if idc else None,
        "pred_absent_frac": float(np.mean([r["pred_absent_frac"] for r in rows])),
        "occlusion_recovery": (
            sum(r["n_recovered"] for r in rows) / n_gaps if n_gaps else None
        ),
        "n_gap_events": n_gaps,
        "mean_fps": float(np.mean([r["fps"] for r in rows])),
        "total_wall_min": round((time.time() - t_start) / 60, 1),
    }
    (out_dir / "results.json").write_text(json.dumps(summary, indent=2))
    m = capture(
        "sam2-zeroshot-carry",
        {"model": MODEL, "image_size": args.image_size or 1024,
         "cap": args.cap, "smoke": args.smoke,
         "gap_min_frames": GAP_MIN_FRAMES, "recovery_window": RECOVERY_WINDOW},
        dataset_path=str(HERE.parents[1] / "data" / "AerialMind"),
    )
    write_manifest(m, runs_dir=str(out_dir), results=summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
