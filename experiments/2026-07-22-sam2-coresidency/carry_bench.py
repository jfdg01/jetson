#!/usr/bin/env python3
"""R-16 device-side carry bench -- one config per process, JSON on stdout.

    .venv/bin/python carry_bench.py --frames clip --n 2 --mode sep --image-size 1024

One process per cell on purpose: `torch.cuda.max_memory_allocated` and the
`MemAvailable` deltas are only meaningful against a clean start, and R-16's claim
that MEMORY is the binding constraint stands or falls on those numbers.

A *tick* is one round in which every candidate advances one frame -- that is what
the Part IV/V harness models as `CAND_HZ`, so `per_cand_hz` here is directly the
number `select_p53.py:84` assumed. Modes:

  sep  N independent SAM2 states stepped round-robin, obj_id=1 in each. What the
       harness actually does (one StreamCarry per candidate).
  bat  ONE state with N obj_ids: the encoder runs once per frame and only memory
       attention + the mask decoder repeat per object. G0 proved this tracks
       IDENTICAL masks (IoU 1.000 on every frame at n=2 and n=3), so it is a pure
       speed lever, not a different tracker.

The TRT encoder path reuses `make_trt_forward_image` from the E1 bench already on
the board; `enc768.plan` is built for 768 and cannot serve 1024.
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
import torch
from sam2.sam2_video_predictor import SAM2VideoPredictor

MODEL = "facebook/sam2.1-hiera-tiny"

# Same three boxes as the G0 gate and the E1 bench, picked by looking at
# clip/0000400.jpg. Rendered in proof/boxes-on-frame.png.
BOXES = [
    [496, 69, 577, 110],
    [604, 78, 672, 112],
    [400, 345, 555, 445],
]


def meminfo_mb() -> dict:
    d = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        if k in ("MemAvailable", "MemFree", "SwapFree", "SwapTotal"):
            d[k] = int(v.split()[0]) // 1024
    d["SwapUsed"] = d.get("SwapTotal", 0) - d.get("SwapFree", 0)
    return d


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--mode", choices=["sep", "bat"], default="sep")
    ap.add_argument("--image-size", type=int, default=1024)
    ap.add_argument("--trt", default=None, help="path to enc<S>.plan")
    ap.add_argument("--tag", default="")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    mem0 = meminfo_mb()
    t0 = time.time()
    pred = SAM2VideoPredictor.from_pretrained(
        MODEL, hydra_overrides_extra=[f"++model.image_size={a.image_size}"])
    if a.trt:
        from jetson_carry_bench import make_trt_forward_image
        pred.forward_image = make_trt_forward_image(pred, a.trt)
    load_s = round(time.time() - t0, 2)
    mem_load = meminfo_mb()

    boxes = [np.array(b, dtype=np.float32) for b in BOXES[: a.n]]
    times: list[float] = []

    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        if a.mode == "sep":
            states = []
            for box in boxes:
                st = pred.init_state(a.frames, offload_video_to_cpu=True)
                pred.add_new_points_or_box(st, frame_idx=0, obj_id=1, box=box)
                states.append(st)
            mem_state = meminfo_mb()
            gens = [pred.propagate_in_video(st) for st in states]
            torch.cuda.synchronize()
            t_prev = time.perf_counter()
            while True:
                try:
                    for g in gens:
                        next(g)
                except StopIteration:
                    break
                torch.cuda.synchronize()
                t = time.perf_counter()
                times.append(t - t_prev)
                t_prev = t
        else:
            st = pred.init_state(a.frames, offload_video_to_cpu=True)
            for i, box in enumerate(boxes):
                pred.add_new_points_or_box(st, frame_idx=0, obj_id=i + 1, box=box)
            mem_state = meminfo_mb()
            torch.cuda.synchronize()
            t_prev = time.perf_counter()
            for _ in pred.propagate_in_video(st):
                torch.cuda.synchronize()
                t = time.perf_counter()
                times.append(t - t_prev)
                t_prev = t

    per = times[5:] or times  # drop warm-up
    ms = sorted(1000 * v for v in per)
    p50 = ms[len(ms) // 2]
    res = {
        "tag": a.tag or f"{a.mode}-n{a.n}-{a.image_size}-{'trt' if a.trt else 'eager'}",
        "mode": a.mode, "n_cand": a.n, "image_size": a.image_size, "trt": bool(a.trt),
        "n_ticks": len(times), "n_timed": len(per),
        "tick_ms_p50": round(p50, 1),
        "tick_ms_p90": round(ms[int(0.9 * len(ms))], 1),
        "tick_ms_max": round(ms[-1], 1),
        "per_cand_hz": round(1000.0 / p50, 3),
        "load_s": load_s,
        "cuda_peak_mb": round(torch.cuda.max_memory_allocated() / 2**20),
        "mem_avail_mb": {"before": mem0["MemAvailable"], "after_load": mem_load["MemAvailable"],
                         "after_state": mem_state["MemAvailable"],
                         "end": meminfo_mb()["MemAvailable"]},
        "swap_used_mb": {"before": mem0["SwapUsed"], "end": meminfo_mb()["SwapUsed"]},
        "torch": torch.__version__,
    }
    line = json.dumps(res)
    print(line, flush=True)
    if a.out:
        with open(a.out, "a") as f:
            f.write(line + "\n")


if __name__ == "__main__":
    main()
