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
import pickle
import struct
import sys
import time

import cv2
import numpy as np
import torch
from sam2.sam2_video_predictor import SAM2VideoPredictor

from stream_carry import MODEL, StreamCarry


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
    inp, out = sys.stdin.buffer, sys.stdout.buffer
    t0 = time.time()
    predictor = SAM2VideoPredictor.from_pretrained(MODEL)   # image_size 1024 (deployed default)
    print(f"[bridge] model loaded in {time.time()-t0:.1f}s, ready", file=sys.stderr, flush=True)
    carry = None
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        while True:
            msg = _recv(inp)
            if msg is None:
                break
            if msg[0] == "init":
                _, jpg, box = msg
                carry = StreamCarry(predictor, _decode(jpg), box)
                _send(out, {"ok": True})
            elif msg[0] == "step":
                ts = time.perf_counter()
                _, box = carry.step(_decode(msg[1]))
                _send(out, {"box": list(box) if box is not None else None,
                            "ms": round(1000 * (time.perf_counter() - ts), 1)})
    print("[bridge] stdin closed, exiting", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
