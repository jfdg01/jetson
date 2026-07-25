"""Runs ON THE JETSON. Times N grounding requests against the already-resident
`llama-server` over 127.0.0.1:18080 -- the RQ-P6.7d half that asks whether keeping a
SAM2 bridge resident taxes the VLM.

On-device on purpose: `JetsonBackend` boots its OWN llama-server and opens an
`ssh -N -L` tunnel, which would fight the deployed server that is already up (the one
the panel prewarms and this experiment must not disturb). Hitting 127.0.0.1 also takes
the ssh tunnel out of the measurement, so what is left is server queue + Orin compute --
which is exactly the contention G3 is about.

The request is the deployed shape: long-edge resize to --max-side, lossless PNG,
base64 data URL, the verbatim `GROUNDING_PROMPT`, greedy, `cache_prompt: false`.
cv2 does the resize+encode instead of PIL (PIL is not in ~/sam2-bench/.venv) -- that
can shift the absolute ms a little versus the panel, but G3 is a PAIRED test over the
same 25 images, so any encoder difference cancels.

  cd ~/sam2-bench && ./.venv/bin/python ground_probe.py --n 25 --tag baseline
"""
import argparse
import base64
import json
import time
import urllib.request
from pathlib import Path

import cv2

# Copied, not imported: this file runs on the Jetson where the `grounding` package is
# not installed. If the contract's prompt ever changes, this string must change with it.
GROUNDING_PROMPT = (
    'Locate "{target}". Return the bounding box as four space-separated integers '
    'x1 y1 x2 y2, normalized from 0 to 100.'
)
MAX_NEW_TOKENS = 32          # grounding/contract.py
BASE = "http://127.0.0.1:18080"


def mem_available_mb():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    return -1


def encode(path, max_side):
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    s = max_side / max(h, w)
    if s < 1.0:
        img = cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".png", img)
    assert ok, f"png encode failed for {path}"
    return base64.b64encode(buf.tobytes()).decode(), img.shape[1], img.shape[0]


def ground_once(b64, caption):
    payload = json.dumps({
        "model": "vlm",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": GROUNDING_PROMPT.format(target=caption)},
        ]}],
        "max_tokens": MAX_NEW_TOKENS,
        "temperature": 0.0,
        "cache_prompt": False,
    }).encode()
    req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=payload,
                                headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode())
    wall = (time.perf_counter() - t0) * 1000.0
    t = data.get("timings") or {}
    return {
        "wall_ms": round(wall, 1),
        "prompt_ms": round(float(t.get("prompt_ms", 0.0)), 1),
        "predicted_ms": round(float(t.get("predicted_ms", 0.0)), 1),
        "text": data["choices"][0]["message"]["content"].strip(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--max-side", type=int, default=1024)
    ap.add_argument("--caption", default="the white car")
    ap.add_argument("--clip", default=str(Path.home() / "sam2-bench" / "clip"))
    ap.add_argument("--tag", default="probe")
    args = ap.parse_args()

    frames = sorted(Path(args.clip).glob("*.jpg"))
    assert len(frames) >= args.n, f"need {args.n} frames, found {len(frames)} in {args.clip}"
    # Evenly spaced, not the first n: consecutive frames of one clip are near-identical
    # and would let any server-side reuse flatter the resident arm.
    picks = [frames[round(i * (len(frames) - 1) / max(1, args.n - 1))] for i in range(args.n)]

    # One untimed warm-up: the very first request after an idle gap pays a slot-alloc
    # cost that belongs to neither arm.
    b64, _, _ = encode(picks[0], args.max_side)
    ground_once(b64, args.caption)

    rows, mem = [], [mem_available_mb()]
    for i, p in enumerate(picks):
        b64, w, h = encode(p, args.max_side)
        r = ground_once(b64, args.caption)
        r.update({"i": i, "frame": p.name, "w": w, "h": h})
        rows.append(r)
        mem.append(mem_available_mb())

    walls = sorted(r["wall_ms"] for r in rows)
    out = {
        "tag": args.tag, "n": len(rows), "max_side": args.max_side, "caption": args.caption,
        "median_wall_ms": walls[len(walls) // 2],
        "min_wall_ms": walls[0], "max_wall_ms": walls[-1],
        "mem_available_mb_min": min(mem), "mem_available_mb_start": mem[0],
        "rows": rows,
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
