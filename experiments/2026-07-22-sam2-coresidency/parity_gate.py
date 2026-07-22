#!/usr/bin/env python3
"""R-16 G0 -- does a batched N-obj_id SAM2 state track the same masks as N separate states?

    .venv/bin/python parity_gate.py --frames clip --n 2 --image-size 1024

Runs the same clip twice at the same image_size: once as N independent states
(what every Part IV/V campaign does, one StreamCarry per candidate) and once as
one state carrying N obj_ids (the untested speedup). Then compares the masks
frame by frame, object by object.

This gates the whole campaign. SAM2 has two cross-object mechanisms --
`non_overlap_masks` and `non_overlap_masks_for_mem_enc` -- that exist precisely
because objects sharing a state can interact. Both default False and the 2.1-tiny
config overrides neither, so the masks *should* match. That is a reading of the
source, not a measurement, which is what this script is for: if they diverge, a
batched carry tracks something different from what the campaigns tracked and the
speedup is not comparable.

Emits one JSON line. Nothing here is timed -- G0 is about identity, not speed.
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import torch
from sam2.sam2_video_predictor import SAM2VideoPredictor

MODEL = "facebook/sam2.1-hiera-tiny"

# Picked in the prior bench session by LOOKING at clip/0000400.jpg (1024x540 aerial
# night intersection): 1 = dark car (the E1 box), 2 = blue car right of it,
# 3 = black SUV lower centre. Re-rendered as this campaign's first proof figure.
BOXES = [
    [496, 69, 577, 110],
    [604, 78, 672, 112],
    [400, 345, 555, 445],
]


def mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    """IoU of two boolean masks. Both empty counts as agreement, not as 0/0."""
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return 1.0 if union == 0 else float(inter) / float(union)


def run_separate(pred, frames: str, boxes: list) -> dict[int, list[np.ndarray]]:
    """N independent states, obj_id=1 in each -- the harness configuration."""
    out: dict[int, list[np.ndarray]] = {}
    for i, box in enumerate(boxes):
        st = pred.init_state(frames, offload_video_to_cpu=True)
        pred.add_new_points_or_box(st, frame_idx=0, obj_id=1, box=box)
        masks = []
        for _, _, logits in pred.propagate_in_video(st):
            masks.append((logits[0] > 0).cpu().numpy().squeeze())
        out[i] = masks
        del st
        torch.cuda.empty_cache()
    return out


def run_batched(pred, frames: str, boxes: list) -> dict[int, list[np.ndarray]]:
    """One state, N obj_ids -- encoder runs once per frame."""
    st = pred.init_state(frames, offload_video_to_cpu=True)
    for i, box in enumerate(boxes):
        pred.add_new_points_or_box(st, frame_idx=0, obj_id=i + 1, box=box)
    out: dict[int, list[np.ndarray]] = {i: [] for i in range(len(boxes))}
    for _, obj_ids, logits in pred.propagate_in_video(st):
        for j, oid in enumerate(obj_ids):
            out[oid - 1].append((logits[j] > 0).cpu().numpy().squeeze())
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--n", type=int, default=2)
    ap.add_argument("--image-size", type=int, default=1024)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    boxes = [np.array(b, dtype=np.float32) for b in BOXES[: a.n]]
    pred = SAM2VideoPredictor.from_pretrained(
        MODEL, hydra_overrides_extra=[f"++model.image_size={a.image_size}"])

    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        sep = run_separate(pred, a.frames, boxes)
        bat = run_batched(pred, a.frames, boxes)

    per_obj = []
    for i in range(a.n):
        n_f = min(len(sep[i]), len(bat[i]))
        ious = [mask_iou(sep[i][f], bat[i][f]) for f in range(n_f)]
        # a mask that vanishes in one arm and not the other is the failure this
        # gate exists to catch, so record presence separately from IoU
        per_obj.append({
            "obj": i + 1,
            "n_frames": n_f,
            "iou_median": round(float(np.median(ious)), 6),
            "iou_min": round(float(np.min(ious)), 6),
            "iou_mean": round(float(np.mean(ious)), 6),
            "n_below_0.95": int(sum(1 for v in ious if v < 0.95)),
            "px_sep_median": int(np.median([m.sum() for m in sep[i][:n_f]])),
            "px_bat_median": int(np.median([m.sum() for m in bat[i][:n_f]])),
            "empty_sep": int(sum(1 for m in sep[i][:n_f] if m.sum() == 0)),
            "empty_bat": int(sum(1 for m in bat[i][:n_f] if m.sum() == 0)),
        })

    ok = all(o["iou_median"] >= 0.99 and o["iou_min"] >= 0.95 for o in per_obj)
    res = {"gate": "G0-batched-separate-parity", "model": MODEL,
           "image_size": a.image_size, "n_cand": a.n,
           "verdict": "PASS" if ok else "FAIL",
           "criterion": "median mask IoU >= 0.99 and min >= 0.95, every object",
           "per_object": per_obj, "torch": torch.__version__}
    line = json.dumps(res)
    print(line, flush=True)
    if a.out:
        with open(a.out, "a") as f:
            f.write(line + "\n")


if __name__ == "__main__":
    main()
