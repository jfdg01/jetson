"""E1 step 5 accuracy proxy (Jetson): dump eager vs fp16-TRT carry boxes for host GT scoring.

Runs the same 100-frame carry twice -- eager bf16, then TRT-fp16-encoder patched -- and dumps
per-clip-index mask boxes for both to JSON. The engine .plan is Jetson-only, so we score
IoU@0.25 vs AerialMind GT back on the host (score_trt_acc.py): the E1 gate is fp16 within 1 pp
of eager on the M0205 window, not mask-for-mask parity. Self-contained (scp'd to ~/sam2-bench/).

  .venv/bin/python jetson_trt_acc.py --frames clip --box 496,69,577,110 \
      --image-size 768 --trt-encoder enc768.plan --out boxes_trt.json
"""

import argparse
import json

import numpy as np
import torch
from jetson_carry_bench import MODEL, make_trt_forward_image
from sam2.sam2_video_predictor import SAM2VideoPredictor


def mask_to_box(m):
    ys, xs = np.where(m)
    if xs.size == 0:
        return None
    return [float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())]


def run(pred, frames, box):
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        state = pred.init_state(frames, offload_video_to_cpu=True)
        pred.add_new_points_or_box(state, frame_idx=0, obj_id=1, box=box)
        boxes = {}
        for fidx, _ids, logits in pred.propagate_in_video(state):
            boxes[fidx] = mask_to_box((logits[0, 0] > 0.0).cpu().numpy())
        pred.reset_state(state)
    return boxes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--box", required=True)
    ap.add_argument("--image-size", type=int, default=768)
    ap.add_argument("--trt-encoder", required=True)
    ap.add_argument("--out", default="boxes_trt.json")
    a = ap.parse_args()

    over = [f"++model.image_size={a.image_size}"]
    box = np.array([float(v) for v in a.box.split(",")], dtype=np.float32)

    pred = SAM2VideoPredictor.from_pretrained(MODEL, hydra_overrides_extra=over)
    ref = run(pred, a.frames, box)
    pred.forward_image = make_trt_forward_image(pred, a.trt_encoder)
    test = run(pred, a.frames, box)

    json.dump({"eager": ref, "trt": test}, open(a.out, "w"))
    print(f"dumped {len(ref)} eager + {len(test)} trt boxes -> {a.out}")


if __name__ == "__main__":
    main()
