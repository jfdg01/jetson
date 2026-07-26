"""Runs ON THE JETSON, driven over `ssh -T` stdin/stdout (NO port-forward -- the sandbox
blocks local port-binding, so `ssh -L` is out; a stdio pipe over the ssh channel is the
transport). The host `_SSHCarry` seam speaks this framing:

  host -> bridge : ("init", jpg_bytes, [x1,y1,x2,y2])  |  ("step", jpg_bytes)
  bridge -> host : {"ok": True}                         |  {"box": [..]|None, "ms": float}

Framing (both directions): 4-byte big-endian length + pickled payload, on the raw byte
streams. stdout carries ONLY framed replies; all logging goes to stderr. cwd must be
~/sam2-bench (imports stream_carry + the SAM2 weights the deployed service uses).

  cd ~/sam2-bench && ./.venv/bin/python -u carry_ssh_bridge.py
"""
import sys

# P6.7: the interpreter is alive HERE, before torch/sam2 are imported. Without this
# marker the host cannot separate "ssh + python startup" from "import torch" -- they
# arrive as one ~4 s lump with different fixes (ControlMaster vs process residency).
# stderr only: stdout carries the framed protocol and must not gain a message, or the
# live panel's first _recv would read this instead of the init ack.
print("[bridge] up", file=sys.stderr, flush=True)

import os  # noqa: E402

# stdout carries ONLY framed replies, so ANY library that writes to fd 1 desyncs the
# protocol: the host reads log text as a 4-byte frame length and then blocks forever on
# a read that can never be satisfied -- both ends idle at 0% CPU, no error anywhere.
# TensorRT does exactly this at the FIRST enqueueV3 ("[TRT] [W] Using default stream in
# enqueueV3() may lead to performance issues"), not at deserialize, so it only bites once
# real inference starts. It deadlocked EXP-9's G1 parity run (2026-07-26). Move the real
# stdout to a private fd and point fd 1 at stderr: the protocol writes to the saved fd and
# every stray print, from any library, lands in the log the host already captures.
_PROTO_OUT = os.fdopen(os.dup(1), "wb")
os.dup2(2, 1)

import argparse  # noqa: E402
import faulthandler  # noqa: E402
import hashlib  # noqa: E402
import pickle  # noqa: E402
import resource  # noqa: E402
import signal  # noqa: E402
import struct  # noqa: E402
import time  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from sam2.sam2_video_predictor import SAM2VideoPredictor  # noqa: E402

from stream_carry import MODEL, StreamCarry  # noqa: E402


def _readn(f, n):
    buf = b""
    while len(buf) < n:
        chunk = f.read(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def _recv(f):
    hdr = _readn(f, 4)
    if hdr is None:
        return None
    (n,) = struct.unpack(">I", hdr)
    data = _readn(f, n)
    return None if data is None else pickle.loads(data)


def _send(f, obj):
    data = pickle.dumps(obj)
    f.write(struct.pack(">I", len(data)))
    f.write(data)
    f.flush()


def _decode(jpg):
    # the host jpg-encodes the RGB array it feeds StreamCarry; decode preserves channel
    # order (JPEG is channel-agnostic), so pass straight through -- NO BGR<->RGB swap here.
    return cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)


def main():
    # Both ends of this protocol block on a read, so a hang here is invisible: the host
    # waits on a reply that is never coming and the bridge sits at 0% CPU. `kill -USR1
    # <pid>` dumps every thread's Python stack to stderr, which is the log file the host
    # already keeps. Costs nothing when nothing hangs. (EXP-9, and py-spy is not an
    # option -- attaching to a non-child needs root and only nvpmodel is NOPASSWD.)
    faulthandler.register(signal.SIGUSR1)
    ap = argparse.ArgumentParser()
    # Cites grounding.contract.CARRY_IMAGE_SIZE; cannot import it -- this file is copied
    # to ~/sam2-bench on the Orin, outside the repo. Was 1024 until R-46 (2026-07-26);
    # EXP-1 moved the deployed carry to the 640 elbow. The panel passes --image-size
    # explicitly, so this default only bites a manual invocation.
    ap.add_argument("--image-size", type=int, default=640)
    # EXP-8 memory-horizon levers. 0 = leave the model's own value (7 / 16 / StreamCarry's
    # PRUNE_AFTER), so every pre-EXP-8 caller is bit-identical.
    ap.add_argument("--num-maskmem", type=int, default=0,
                    help="K: mask-memory slots. Post-load ONLY and downward only -- "
                         "maskmem_tpos_enc is a trained Parameter sized 7, so a hydra "
                         "override fails the strict load_state_dict. Index-correct because "
                         "the tpos index is num_maskmem-t_pos-1 == t_rel-1, keyed to recency.")
    ap.add_argument("--max-obj-ptrs", type=int, default=0,
                    help="M: object pointers. >=2 -- t_diff_max = M-1 divides by zero at 1.")
    ap.add_argument("--prune-after", type=int, default=0, help="P: StreamCarry ring depth")
    ap.add_argument("--mask-hash", action="store_true",
                    help="sha1 the video-res mask per step (EXP-8 ring bit-identity)")
    # EXP-9 levers. Both default to the pre-EXP-9 behaviour (stream_carry.MODEL, eager
    # bf16 encoder), so every earlier caller -- the live CARLA panel, the EXP-1/2/6/8
    # replays -- is bit-identical. Same discipline EXP-8 used for its four flags.
    ap.add_argument("--model", default="",
                    help="HF model id; empty = stream_carry.MODEL (sam2.1-hiera-tiny)")
    ap.add_argument("--trt-encoder", default="",
                    help="path to an E1-style fp16 TensorRT image-encoder .plan; empty = "
                         "eager torch. Must have been built at THIS --image-size: the "
                         "engine's input shape is baked in and a mismatch is a hard fail, "
                         "not a silent resize.")
    args = ap.parse_args()
    inp, out = sys.stdin.buffer, _PROTO_OUT
    t0 = time.time()
    over = [f"++model.image_size={args.image_size}"] if args.image_size != 1024 else []
    predictor = SAM2VideoPredictor.from_pretrained(args.model or MODEL,
                                                   hydra_overrides_extra=over)
    if args.trt_encoder:
        from jetson_carry_bench import make_trt_forward_image
        predictor.forward_image = make_trt_forward_image(predictor, args.trt_encoder)
    if args.num_maskmem:
        assert 1 <= args.num_maskmem <= predictor.num_maskmem, "K is downward-only from 7"
        predictor.num_maskmem = args.num_maskmem
    if args.max_obj_ptrs:
        assert args.max_obj_ptrs >= 2, "M=1 divides by zero in the pointer sine embedding"
        predictor.max_obj_ptrs_in_encoder = args.max_obj_ptrs
    kw = {"prune_after": args.prune_after} if args.prune_after else {}
    print(f"[bridge] model loaded in {time.time()-t0:.1f}s, id={args.model or MODEL}, "
          f"image_size={args.image_size}, K={predictor.num_maskmem} "
          f"M={predictor.max_obj_ptrs_in_encoder} P={args.prune_after or 'stock'} "
          f"enc={args.trt_encoder or 'eager'}, ready", file=sys.stderr, flush=True)
    carry = None
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        while True:
            msg = _recv(inp)
            if msg is None:
                break
            if msg[0] == "init":
                _, jpg, box = msg
                torch.cuda.reset_peak_memory_stats()
                carry = StreamCarry(predictor, _decode(jpg), box, **kw)
                _send(out, {"ok": True})
            elif msg[0] == "step":
                ts = time.perf_counter()
                mask, box = carry.step(_decode(msg[1]))
                rep = {"box": list(box) if box is not None else None,
                       "ms": round(1000 * (time.perf_counter() - ts), 1),
                       "cuda_mb": round(torch.cuda.max_memory_allocated() / 2**20, 1),
                       "rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}
                if args.mask_hash:
                    rep["mh"] = hashlib.sha1(np.ascontiguousarray(mask)).hexdigest()
                _send(out, rep)
    print("[bridge] stdin closed, exiting", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
