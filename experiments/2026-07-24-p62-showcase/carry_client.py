"""Runs ON THE JETSON. Connects to the local jetson_carry_service.py socket
(127.0.0.1:18081, authkey=b"carry"), seeds the deployed SAM2 carry with the
oracle GT box, steps it over the staged frames, writes boxes.json.

Sandbox note: no SSH port-forward is used -- the client runs on the Orin and
talks to the service over 127.0.0.1, so nothing binds a local host port. This
is the exact carry compute path the showcase FLIGHT's _SSHCarry seam exercises;
here we drive it directly instead of through the flight rig.

  python3 carry_client.py <staging_dir>   # reads meta.json + frames/, writes boxes.json
"""
import json
import sys
import time
from multiprocessing.connection import Client
from pathlib import Path

PORT = 18081
AUTH = b"carry"


def main(stage: Path):
    meta = json.loads((stage / "meta.json").read_text())
    frames = stage / "frames"
    conn = Client(("127.0.0.1", PORT), authkey=AUTH)
    seed_jpg = (frames / "seed.jpg").read_bytes()
    conn.send({"cmd": "init", "jpg": seed_jpg, "box": [int(v) for v in meta["seed_box"]]})
    ack = conn.recv()
    assert ack.get("ok"), f"init failed: {ack}"
    boxes, mss = [], []
    for st in meta["steps"]:
        j = st["j"]
        jpg = (frames / f"s{j:03d}.jpg").read_bytes()
        t0 = time.time()
        conn.send({"cmd": "step", "jpg": jpg})
        r = conn.recv()
        wall = (time.time() - t0) * 1000.0
        boxes.append(r.get("box"))
        mss.append(r.get("ms"))
        print(f"[client] step {j:2d} box={r.get('box')} compute_ms={r.get('ms')} "
              f"wall_ms={wall:.1f}", flush=True)
    conn.close()   # service treats the EOF as "client gone, resetting" (no close cmd exists)
    (stage / "boxes.json").write_text(json.dumps({"boxes": boxes, "ms": mss}, indent=1))
    print(f"[client] wrote {len(boxes)} boxes -> {stage/'boxes.json'}", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
