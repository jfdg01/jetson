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


class TRTEncoder:
    """Run the fp16 TensorRT image-encoder engine, binding torch cuda tensors directly.

    No pycuda, no host copies: input/output stay as torch device tensors (data_ptr).
    Engine I/O is fp32 (--fp16 keeps declared I/O dtypes, fp16 only internal). Outputs the
    6 raw encoder tensors (fpn0/1/2 + pos0/1/2); the caller re-applies conv_s0/conv_s1.
    """

    def __init__(self, plan_path):
        import tensorrt as trt

        logger = trt.Logger(trt.Logger.WARNING)
        with open(plan_path, "rb") as f:
            self.engine = trt.Runtime(logger).deserialize_cuda_engine(f.read())
        self.ctx = self.engine.create_execution_context()
        self.in_name, self.out_names = None, []
        for i in range(self.engine.num_io_tensors):
            n = self.engine.get_tensor_name(i)
            if self.engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT:
                self.in_name = n
            else:
                self.out_names.append(n)

    def __call__(self, x):  # x: (1,3,S,S) cuda tensor
        x = x.contiguous().float()
        self.ctx.set_input_shape(self.in_name, tuple(x.shape))
        self.ctx.set_tensor_address(self.in_name, x.data_ptr())
        outs = {}
        for n in self.out_names:
            t = torch.empty(tuple(self.ctx.get_tensor_shape(n)),
                            dtype=torch.float32, device=x.device)
            outs[n] = t
            self.ctx.set_tensor_address(n, t.data_ptr())
        self.ctx.execute_async_v3(torch.cuda.current_stream().cuda_stream)
        torch.cuda.current_stream().synchronize()
        return outs


def make_trt_forward_image(pred, plan_path):
    """Drop-in for pred.forward_image: encoder via TensorRT, high-res 1x1 convs in torch."""
    enc = TRTEncoder(plan_path)

    def fwd(img_batch):
        o = enc(img_batch)
        fpn = [o["fpn0"], o["fpn1"], o["fpn2"]]
        bb = {"vision_features": fpn[2], "vision_pos_enc": [o["pos0"], o["pos1"], o["pos2"]],
              "backbone_fpn": fpn}
        bb["backbone_fpn"][0] = pred.sam_mask_decoder.conv_s0(bb["backbone_fpn"][0])
        bb["backbone_fpn"][1] = pred.sam_mask_decoder.conv_s1(bb["backbone_fpn"][1])
        return bb

    return fwd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--box", required=True, help="x1,y1,x2,y2 pixels, prompt @ frame 0")
    ap.add_argument("--image-size", type=int, default=None, help="override model.image_size")
    ap.add_argument("--tag", default="solo")
    ap.add_argument("--trt-encoder", default=None, help="path to enc<S>.plan; monkeypatch encoder")
    a = ap.parse_args()

    over = [f"++model.image_size={a.image_size}"] if a.image_size else []
    t0 = time.perf_counter()
    pred = SAM2VideoPredictor.from_pretrained(MODEL, hydra_overrides_extra=over)
    if a.trt_encoder:
        pred.forward_image = make_trt_forward_image(pred, a.trt_encoder)
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
        trt_encoder=a.trt_encoder,
    )
    print(json.dumps(out))


if __name__ == "__main__":
    main()
