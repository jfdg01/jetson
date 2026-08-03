"""Any sweep arm behind the live panel's carry socket. Runs ON THE JETSON over `ssh -T`.

Same framing and the same replies as `carry_ssh_bridge.py`, so the panel's `_SSHCarry`
seam does not know which of the two it is talking to:

  host -> bridge : ("init", jpg_bytes, [x1,y1,x2,y2])  |  ("step", jpg_bytes)
  bridge -> host : {"ok": True}                         |  {"box": [..]|None, "ms": float, ...}

Why a SECOND bridge instead of a `--tracker` flag on the first one: DAM4SAM and SAMURAI
each vendor their own modified `sam2` fork, which collides with the `sam2 1.1.0` in
~/sam2-bench/.venv. The sweep already solved this by giving each family its own
interpreter (`.venv-dam4sam`, `.venv-samurai`), so the family lives in the command line,
not in an import that cannot coexist. The published SAM2 carry path stays bit-identical
because that file is not touched.

  cd ~/tracker-sweep/code && ../.venv-dam4sam/bin/python -u arm_ssh_bridge.py \
      --family dam4sam --size 640

Frames arrive RGB-encoded (the host jpg-encodes the RGB array). `trackers.py` declares
BGR, so this bridge swaps -- `carry_ssh_bridge.py` does not, because StreamCarry feeds
SAM2 directly and SAM2 wants RGB.
"""
import sys

print("[bridge] up", file=sys.stderr, flush=True)

import os  # noqa: E402

# stdout carries ONLY framed replies; any library print on fd 1 desyncs the protocol and
# both ends idle forever on a read. Same guard as carry_ssh_bridge.py, same reason.
_PROTO_OUT = os.fdopen(os.dup(1), "wb")
os.dup2(2, 1)

import argparse  # noqa: E402
import faulthandler  # noqa: E402
import pickle  # noqa: E402
import resource  # noqa: E402
import signal  # noqa: E402
import struct  # noqa: E402
import time  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import trackers  # noqa: E402

# ponytail: three lambdas, not a registry lookup, because the panel's carry dropdown
# offers sizes (896) that no `*_t<size>` arm is registered at, and snapping the operator's
# choice to the nearest registered arm would be a silent lie about what ran. `--arm` is
# the escape hatch for anything already in the registry.
FAMILIES = {
    "sam2": lambda n: trackers.Sam2Arm("facebook/sam2.1-hiera-tiny", n),
    "dam4sam": lambda n: trackers.Dam4SamArm(size=n),
    # fp16 default = published SAMURAI. nota 16: DAM4SAM runs bf16, so a SAMURAI-vs-DAM4SAM
    # delta seen in this panel is precision plus policy. `--amp bf16` prices the halves apart.
    "samurai": lambda n: trackers.SamuraiArm(size=n),
}


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
    # host sends RGB; trackers.py takes BGR (`self._pil` in Dam4SamArm undoes exactly this)
    return cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)[:, :, ::-1].copy()


def _cuda_mb():
    try:
        import torch
        if torch.cuda.is_available():
            return round(torch.cuda.max_memory_allocated() / 2**20, 1)
    except Exception:
        pass
    return None


def main():
    faulthandler.register(signal.SIGUSR1)   # `kill -USR1 <pid>` dumps stacks to the log
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", choices=sorted(FAMILIES), default="sam2")
    ap.add_argument("--size", type=int, default=640)
    ap.add_argument("--amp", default="", help="samurai only: fp16 (published) | bf16 (parity)")
    ap.add_argument("--arm", default="", help="registry arm name; overrides --family/--size")
    args = ap.parse_args()
    inp, out = sys.stdin.buffer, _PROTO_OUT
    t0 = time.time()
    if args.arm:
        tr = trackers.build(args.arm)
    elif args.family == "samurai" and args.amp:
        tr = trackers.SamuraiArm(size=args.size, amp=args.amp)
    else:
        tr = FAMILIES[args.family](args.size)
    # The weights load on `init`, not here (every arm builds its model lazily so the sweep
    # can fork a process per sequence), so this line only prices the imports.
    print(f"[bridge] {args.arm or args.family} size={args.size} imports in "
          f"{time.time()-t0:.1f}s, ready", file=sys.stderr, flush=True)
    while True:
        msg = _recv(inp)
        if msg is None:
            break
        if msg[0] == "init":
            _, jpg, box = msg
            ts = time.perf_counter()
            tr.init(_decode(jpg), [float(v) for v in box])
            print(f"[bridge] init (model load included) "
                  f"{time.perf_counter()-ts:.1f}s", file=sys.stderr, flush=True)
            _send(out, {"ok": True})
        elif msg[0] == "step":
            ts = time.perf_counter()
            box, _ = tr.step(_decode(msg[1]))
            _send(out, {"box": list(box) if box is not None else None,
                        "ms": round(1000 * (time.perf_counter() - ts), 1),
                        "cuda_mb": _cuda_mb(),
                        "rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)})
    print("[bridge] stdin closed, exiting", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
