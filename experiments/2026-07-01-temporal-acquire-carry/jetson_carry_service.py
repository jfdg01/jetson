"""Phase 3b: SAM2 carry service on the Jetson (scp'd to ~/sam2-bench/ with stream_carry.py).

The host loop streams JPEG frames over an ssh-forwarded TCP port; this service runs
StreamCarry on-device and returns the tracked box per frame. One client, one target
(matched to the "follow the white car" loop; no multi-object protocol).

Protocol (multiprocessing.connection dicts, authkey b"carry"):
  {"cmd": "init", "jpg": <bytes>, "box": [x1,y1,x2,y2]} -> {"ok": True}
  {"cmd": "step", "jpg": <bytes>}                       -> {"box": [..] | None, "ms": float}
  connection close -> drop carry state, wait for next client

  ~/sam2-bench/.venv/bin/python jetson_carry_service.py --image-size 640
"""

import argparse
import time
from multiprocessing.connection import Listener

import cv2
import numpy as np
import torch
from sam2.sam2_video_predictor import SAM2VideoPredictor

from stream_carry import MODEL, StreamCarry


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image-size", type=int, default=640)
    ap.add_argument("--port", type=int, default=18081)
    ap.add_argument("--trt-encoder", default=None,
                    help="path to TensorRT .plan; swaps forward_image (E1, 768 op)")
    args = ap.parse_args()

    over = [f"++model.image_size={args.image_size}"] if args.image_size != 1024 else []
    predictor = SAM2VideoPredictor.from_pretrained(MODEL, hydra_overrides_extra=over)
    if args.trt_encoder:
        from jetson_carry_bench import make_trt_forward_image
        predictor.forward_image = make_trt_forward_image(predictor, args.trt_encoder)
    print(f"[carry-svc] ready 127.0.0.1:{args.port} image_size={args.image_size}"
          f" trt={bool(args.trt_encoder)}", flush=True)

    with Listener(("127.0.0.1", args.port), authkey=b"carry") as srv:
        while True:
            conn = srv.accept()
            print("[carry-svc] client connected", flush=True)
            carry = None
            try:
                with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                    while True:
                        msg = conn.recv()
                        rgb = cv2.cvtColor(
                            cv2.imdecode(np.frombuffer(msg["jpg"], np.uint8),
                                         cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
                        t0 = time.perf_counter()
                        if msg["cmd"] == "init":
                            carry = StreamCarry(predictor, rgb, msg["box"])
                            conn.send({"ok": True})
                        else:
                            _, box = carry.step(rgb)
                            conn.send({"box": box,
                                       "ms": round(1000 * (time.perf_counter() - t0), 1)})
            except EOFError:
                print("[carry-svc] client gone, resetting", flush=True)
            finally:
                conn.close()
                carry = None


if __name__ == "__main__":
    main()
