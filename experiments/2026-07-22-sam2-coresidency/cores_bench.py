#!/usr/bin/env python3
"""R-16 M3/M4 -- streaming SAM2 carry co-resident with the deployed VLM, on-device.

    .venv/bin/python cores_bench.py --frames clip --n 2 --server load

Two things this measures that the offline `carry_bench.py` cannot:

1. **The DEPLOYED carry.** `StreamCarry` (Part III phase 3.0) feeds one frame at a
   time and prunes the ring at PRUNE_AFTER=100 frames -- that is what the follow
   stack actually runs. `carry_bench.py` uses the stock offline `init_state(dir)`,
   which materialises the whole clip per state; at 1024 that is 12.58 MB/frame/
   candidate of float32 host RAM and it dominated the memory reading. Same compute,
   very different footprint, so the memory question has to be asked here.

2. **Co-residency under REAL load.** E1's "co-residency costs 0 FPS" was measured
   against an *idle* llama-server. `--server load` runs a grounding client in a
   background thread against the deployed Q8_0 checkpoint while the carry steps, so
   both sides are contended at once and both are recorded: the carry's per-tick ms
   AND the VLM's wall latency. An idle resident server tests memory only.

The load thread sends the same payload `grounding/eval/backends.py` builds -- same
prompt, same greedy sampling, same `cache_prompt: False` -- so the VLM latencies
here are comparable to every other VLM number in the thesis.
"""
from __future__ import annotations

import argparse
import base64
import json
import statistics
import sys
import threading
import time
import urllib.request
from pathlib import Path

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stream_carry import StreamCarry  # noqa: E402

MODEL = "facebook/sam2.1-hiera-tiny"
BOXES = [
    [496, 69, 577, 110],
    [604, 78, 672, 112],
    [400, 345, 555, 445],
]
# Verbatim from grounding/contract.py -- the deployed terse prompt. Copied rather
# than imported because the board has no repo checkout.
PROMPT = ("Locate the object described. Answer with only the bounding box "
          "as [x1, y1, x2, y2] with coordinates from 0 to 100.\nObject: {target}")


def meminfo_mb() -> dict:
    d = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        if k in ("MemAvailable", "SwapFree", "SwapTotal"):
            d[k] = int(v.split()[0]) // 1024
    d["SwapUsed"] = d.get("SwapTotal", 0) - d.get("SwapFree", 0)
    return d


class GroundingLoad(threading.Thread):
    """Hammer the deployed llama-server with real grounding calls until told to stop."""

    def __init__(self, url: str, image: Path, caption: str, max_side: int = 1024):
        super().__init__(daemon=True)
        self.url, self.caption, self.max_side = url, caption, max_side
        self.image = image
        self.walls: list[float] = []
        self.errors = 0
        self._done = threading.Event()  # NOT _stop: Thread.join() calls self._stop()

    def _payload(self) -> bytes:
        img = Image.open(self.image).convert("RGB")
        w, h = img.size
        s = self.max_side / max(w, h)
        if s < 1:
            img = img.resize((round(w * s), round(h * s)), Image.LANCZOS)
        buf = __import__("io").BytesIO()
        img.save(buf, format="JPEG", quality=95)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return json.dumps({
            "model": "vlm",
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": PROMPT.format(target=self.caption)},
            ]}],
            "max_tokens": 64, "temperature": 0.0, "cache_prompt": False,
        }).encode()

    def run(self) -> None:
        body = self._payload()  # built once; the cost under test is inference, not JPEG
        while not self._done.is_set():
            req = urllib.request.Request(
                f"{self.url}/v1/chat/completions", data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    resp.read()
                self.walls.append((time.perf_counter() - t0) * 1000)
            except Exception:
                self.errors += 1

    def stop(self) -> None:
        self._done.set()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--image-size", type=int, default=1024)
    ap.add_argument("--server", choices=["absent", "idle", "load"], default="absent")
    ap.add_argument("--url", default="http://127.0.0.1:18080")
    ap.add_argument("--caption", default="the dark car at the intersection")
    ap.add_argument("--prune-after", type=int, default=100,
                    help="StreamCarry ring length in frames; the deployed default is 100, "
                         "and it is sized in FRAMES -- so moving 768->1024 inflated it 1.78x "
                         "in bytes without anyone changing it")
    ap.add_argument("--out", default=None)
    ap.add_argument("--trace", default=None,
                    help="sidecar JSONL sampling MemAvailable/swap every 0.5s; survives an "
                         "OOM kill, which is the only way this cell reports anything when "
                         "it loses")
    a = ap.parse_args()

    paths = sorted(Path(a.frames).glob("*.jpg"))
    # Loaded one at a time inside the tick loop, NOT preloaded. A 100-frame
    # 1024x540 preload is ~166 MB of harness footprint charged to a measurement
    # whose whole subject is whether the deployed pair fits in 8 GB.
    mem0 = meminfo_mb()

    # This cell can be OOM-killed -- that is one of its possible outcomes, and a
    # kill leaves no stdout. Sample memory to a sidecar so the death has a
    # trajectory: which tick, how much was left, how much swap had been eaten.
    trace = open(a.trace, "w") if a.trace else None
    tick_no = [0]
    if trace:
        def sampler():
            t0 = time.perf_counter()
            while not stop_sampler.is_set():
                m = meminfo_mb()
                trace.write(json.dumps({"t": round(time.perf_counter() - t0, 2),
                                        "tick": tick_no[0],
                                        "avail": m["MemAvailable"],
                                        "swap": m["SwapUsed"]}) + "\n")
                trace.flush()
                time.sleep(0.5)
        stop_sampler = threading.Event()
        threading.Thread(target=sampler, daemon=True).start()

    from sam2.sam2_video_predictor import SAM2VideoPredictor
    pred = SAM2VideoPredictor.from_pretrained(
        MODEL, hydra_overrides_extra=[f"++model.image_size={a.image_size}"])
    mem_load = meminfo_mb()

    load = None
    if a.server == "load":
        load = GroundingLoad(a.url, paths[0], a.caption)
        load.start()
        time.sleep(8)  # let the first (cold) call land so the carry meets a warm server

    times: list[float] = []
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        carries = [StreamCarry(pred, str(paths[0]), BOXES[i], prune_after=a.prune_after)
                   for i in range(a.n)]
        mem_state = meminfo_mb()
        torch.cuda.synchronize()
        t_prev = time.perf_counter()
        for p in paths[1:]:
            f = np.asarray(Image.open(p).convert("RGB"))
            for c in carries:
                c.step(f)
            torch.cuda.synchronize()
            t = time.perf_counter()
            times.append(t - t_prev)
            t_prev = t
            tick_no[0] += 1
    mem_end = meminfo_mb()
    if trace:
        stop_sampler.set()

    vlm = None
    if load is not None:
        load.stop()
        load.join(timeout=200)
        w = sorted(load.walls)
        vlm = {"n_calls": len(w), "errors": load.errors,
               "wall_ms_p50": round(statistics.median(w)) if w else None,
               "wall_ms_max": round(w[-1]) if w else None,
               "wall_ms_min": round(w[0]) if w else None}

    per = times[5:] or times
    ms = sorted(1000 * v for v in per)
    p50 = ms[len(ms) // 2]
    res = {
        "tag": f"stream-n{a.n}-{a.image_size}-ring{a.prune_after}-server_{a.server}",
        "carry": "StreamCarry (deployed, prune_after=100)",
        "n_cand": a.n, "image_size": a.image_size, "server": a.server,
        "prune_after": a.prune_after,
        "n_ticks": len(times), "tick_ms_p50": round(p50, 1),
        "tick_ms_p90": round(ms[int(0.9 * len(ms))], 1), "tick_ms_max": round(ms[-1], 1),
        "per_cand_hz": round(1000.0 / p50, 3),
        "cuda_peak_mb": round(torch.cuda.max_memory_allocated() / 2**20),
        "mem_avail_mb": {"before": mem0["MemAvailable"], "after_load": mem_load["MemAvailable"],
                         "after_state": mem_state["MemAvailable"], "end": mem_end["MemAvailable"]},
        "swap_used_mb": {"before": mem0["SwapUsed"], "end": mem_end["SwapUsed"]},
        "vlm": vlm, "torch": torch.__version__,
    }
    line = json.dumps(res)
    print(line, flush=True)
    if a.out:
        with open(a.out, "a") as f:
            f.write(line + "\n")


if __name__ == "__main__":
    main()
