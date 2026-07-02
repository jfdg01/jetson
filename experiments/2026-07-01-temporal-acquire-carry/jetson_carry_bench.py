"""Phase 2 Jetson bench: SAM2.1-tiny video-propagation FPS on the Orin Nano @ 15 W.

Self-contained -- runs on the Jetson with no repo imports (scp'd to ~/sam2-bench/).
Frames dir = integer-named JPEGs (an AerialMind window copied as-is). Accuracy is
NOT measured here (that's Phase 0); this gates RQ-T.2 (>=5 FPS) and feeds RQ-T.3.

  .venv/bin/python jetson_carry_bench.py --frames clip \
      --box X1,Y1,X2,Y2 [--image-size 512] --tag solo
"""

import argparse
import json
import time

import numpy as np
import torch
from sam2.sam2_video_predictor import SAM2VideoPredictor

MODEL = "facebook/sam2.1-hiera-tiny"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--box", required=True, help="x1,y1,x2,y2 pixels, prompt @ frame 0")
    ap.add_argument("--image-size", type=int, default=None, help="override model.image_size")
    ap.add_argument("--tag", default="solo")
    a = ap.parse_args()

    over = [f"++model.image_size={a.image_size}"] if a.image_size else []
    t0 = time.perf_counter()
    pred = SAM2VideoPredictor.from_pretrained(MODEL, hydra_overrides_extra=over)
    t_load = time.perf_counter() - t0
    box = np.array([float(v) for v in a.box.split(",")], dtype=np.float32)

    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        t0 = time.perf_counter()
        state = pred.init_state(a.frames, offload_video_to_cpu=True)
        t_init = time.perf_counter() - t0
        pred.add_new_points_or_box(state, frame_idx=0, obj_id=1, box=box)
        times, n_mask = [], 0
        t_prev = time.perf_counter()
        for _, _, logits in pred.propagate_in_video(state):
            torch.cuda.synchronize()
            t = time.perf_counter()
            times.append(t - t_prev)
            t_prev = t
            n_mask += int((logits[0, 0] > 0).any())  # sanity: masks are non-empty

    per = times[5:] or times  # ponytail: drop 5 warmup frames, no fancier stats needed
    out = dict(
        tag=a.tag,
        model=MODEL,
        image_size=a.image_size or 1024,
        n_frames=len(times),
        n_mask_present=n_mask,
        load_s=round(t_load, 2),
        init_s=round(t_init, 2),
        fps=round(len(per) / sum(per), 2),
        ms_p50=round(1000 * sorted(per)[len(per) // 2], 1),
        ms_max=round(1000 * max(per), 1),
        cuda_peak_mb=round(torch.cuda.max_memory_allocated() / 2**20),
        torch=torch.__version__,
    )
    print(json.dumps(out))


if __name__ == "__main__":
    main()
