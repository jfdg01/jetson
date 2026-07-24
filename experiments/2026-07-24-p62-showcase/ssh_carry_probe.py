"""De-risk the flight's _SSHCarry transport WITHOUT CARLA: launch the Jetson carry bridge
over `ssh -T`, init with the staged car9 seed, step the staged frames, print boxes + timing,
and cross-check against the socket-service run (runs/p62_showcase/ondevice/boxes.json) -- same
frames, same weights, so the ssh-stdio path should reproduce it. Validates framing + latency
before wiring _SSHCarry into run_p62_flight.py.

  .venv-ft/bin/python experiments/2026-07-24-p62-showcase/ssh_carry_probe.py
"""
import json
import pickle
import struct
import subprocess
import sys
import time
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
STAGE = HERE.parents[1] / "runs" / "p62_showcase" / "ondevice"
SSH_CMD = ["ssh", "-T", "-q", "jetson", "cd ~/sam2-bench && ./.venv/bin/python -u carry_ssh_bridge.py"]


def _send(f, obj):
    data = pickle.dumps(obj)
    f.write(struct.pack(">I", len(data))); f.write(data); f.flush()


def _readn(f, n):
    buf = b""
    while len(buf) < n:
        c = f.read(n - len(buf))
        if not c:
            return None
        buf += c
    return buf


def _recv(f):
    hdr = _readn(f, 4)
    if hdr is None:
        return None
    (n,) = struct.unpack(">I", hdr)
    return pickle.loads(_readn(f, n))


def _jpg_rgb(path):
    """Staged frames are BGR (cv2.imwrite). Convert to RGB then jpg -- the bridge feeds the
    decoded array straight to StreamCarry, so the host must send RGB (the flight sends _rgb(f))."""
    bgr = cv2.imread(str(path))
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return cv2.imencode(".jpg", rgb)[1].tobytes()


def main():
    meta = json.loads((STAGE / "meta.json").read_text())
    ref = json.loads((STAGE / "boxes.json").read_text())["boxes"]
    frames = STAGE / "frames"
    print("[probe] launching ssh bridge (model load ~sec)...", flush=True)
    proc = subprocess.Popen(SSH_CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=sys.stderr, bufsize=0)
    t0 = time.time()
    _send(proc.stdin, ("init", _jpg_rgb(frames / "seed.jpg"),
                       [int(v) for v in meta["seed_box"]]))
    ack = _recv(proc.stdout)
    print(f"[probe] init ack={ack} after {time.time()-t0:.1f}s (incl. model load)", flush=True)
    ious, rtts = [], []
    for st in meta["steps"]:
        j = st["j"]
        ta = time.time()
        _send(proc.stdin, ("step", _jpg_rgb(frames / f"s{j:03d}.jpg")))
        r = _recv(proc.stdout)
        rtt = (time.time() - ta) * 1000
        rtts.append(rtt)
        box = r["box"]
        rb = ref[j]
        # IoU vs the socket-service run (should be ~1.0: identical frames+weights)
        if box and rb:
            iw = max(0, min(box[2], rb[2]) - max(box[0], rb[0]))
            ih = max(0, min(box[3], rb[3]) - max(box[1], rb[1]))
            inter = iw * ih
            ua = ((box[2]-box[0])*(box[3]-box[1]) + (rb[2]-rb[0])*(rb[3]-rb[1]) - inter)
            ious.append(inter / ua if ua > 0 else 0.0)
        print(f"[probe] step {j:2d} box={box} compute_ms={r['ms']} rtt_ms={rtt:.1f} "
              f"iou_vs_socket={ious[-1]:.3f}", flush=True)
    proc.stdin.close()
    proc.wait(timeout=10)
    import statistics as stx
    print(f"\n[probe] {len(ious)} steps | median IoU vs socket-run {stx.median(ious):.3f} "
          f"(min {min(ious):.3f}) | median rtt {stx.median(rtts):.1f} ms "
          f"| transport = rtt - compute", flush=True)
    assert stx.median(ious) >= 0.95, f"ssh-bridge carry diverges from socket run: {stx.median(ious):.3f}"
    print("[probe] PASS: ssh-stdio carry reproduces the on-device socket run", flush=True)


if __name__ == "__main__":
    main()
