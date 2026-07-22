#!/usr/bin/env python3
"""R-16 M3 driver -- run the co-residency matrix with a CLEAN start per cell.

    .venv/bin/python run_m3.py --out m3-clean.jsonl

The first pass at M3 ran its cells back to back and the readings were not
comparable: a cell that OOM-kills leaves swap occupied, so the next cell starts
with ~800 MB less room than the one before it. That is fatal for the specific
question M3 asks -- "does the ring-size lever remove the swap thrash?" -- because
the answer is itself a swap number. So each cell here restarts the llama-server
and waits for it to report healthy, which returns the board to the same state
(server resident, weights paged in, carry process gone) before anything is timed.

Cells are (n_candidates, image_size, prune_after). Run order does not matter once
the state is reset, so it is written in the order the README's table reads.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path.home()
SERVER = [
    str(HOME / "llama.cpp/build/bin/llama-server"),
    "-m", "phase3-terse100eos-1024-q8_0.gguf",
    "--mmproj", "mmproj-phase3-terse100eos-1024-f16.gguf",
    "-ngl", "99", "-c", "4096", "-np", "1",
    "--cache-ram", "0", "--no-cache-idle-slots",
    "--host", "127.0.0.1", "--port", "18080",
]
CELLS = [(1, 1024, 100), (1, 1024, 32), (1, 768, 100), (2, 1024, 100), (2, 1024, 32)]


def meminfo() -> dict:
    d = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        if k in ("MemAvailable", "SwapFree", "SwapTotal"):
            d[k] = int(v.split()[0]) // 1024
    return {"avail": d["MemAvailable"], "swap_used": d["SwapTotal"] - d["SwapFree"]}


def healthy() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:18080/health", timeout=5) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def restart_server() -> subprocess.Popen:
    subprocess.run(["pkill", "-f", "llama-server"], check=False)
    # the weights are ~4.6 GB; give the kernel time to actually release them or the
    # next cell inherits the footprint it was supposed to be measured without
    for _ in range(30):
        if not healthy():
            break
        time.sleep(1)
    time.sleep(5)
    proc = subprocess.Popen(SERVER, cwd=str(HOME / "grounding"),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(90):
        if healthy():
            return proc
        time.sleep(2)
    raise RuntimeError("llama-server did not become healthy in 180 s")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="m3-clean.jsonl")
    ap.add_argument("--frames", default="clip")
    a = ap.parse_args()

    for n, size, ring in CELLS:
        tag = f"stream-n{n}-{size}-ring{ring}-server_load"
        restart_server()
        pre = meminfo()
        cmd = [".venv/bin/python", "cores_bench.py", "--frames", a.frames,
               "--n", str(n), "--image-size", str(size), "--prune-after", str(ring),
               "--server", "load", "--trace", f"tr-clean-n{n}-{size}-r{ring}.jsonl"]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           env={"TQDM_DISABLE": "1", "PATH": "/usr/bin:/bin",
                                "HOME": str(HOME)})
        if r.returncode == 0 and r.stdout.strip():
            rec = json.loads(r.stdout.strip().splitlines()[-1])
            rec["clean_start"] = pre
        else:
            # exit 137 = SIGKILL = the OOM killer. That is a RESULT for this
            # campaign, not an error, so it is recorded with the same fields the
            # surviving cells carry.
            rec = {"tag": tag, "n_cand": n, "image_size": size, "prune_after": ring,
                   "server": "load", "verdict": "OOM-KILLED" if r.returncode == -9
                   or r.returncode == 137 else f"DIED-{r.returncode}",
                   "clean_start": pre, "post": meminfo()}
        print(json.dumps(rec), flush=True)
        with open(a.out, "a") as f:
            f.write(json.dumps(rec) + "\n")

    subprocess.run(["pkill", "-f", "llama-server"], check=False)


if __name__ == "__main__":
    main()
