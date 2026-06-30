"""On-Orin prefill/decode timing for ROI-crop survivors (RQ1/RQ3).

Reuses the T0a verbose-POST path: boots the deployed Qwen2-VL-2B Q8_0 on the Jetson
once, then for each config feeds the *actual image that would be sent* and reads the
server prompt_ms (prefill) / predicted_ms (decode) split. Configs:

  - full@1024   : full RefDrone frame, max_side=1024  → the accuracy baseline (62.6%)
  - crop@512 M2 : 512x512 ROI crop (M=2.0 around GT)  → the accuracy winner (85.2%)
  - crop@384 M2 : 384x384 ROI crop (M=2.0)            → cheaper, still 82.5%

Run from repo root under .venv-ft (needs grounding + PIL; talks to `ssh jetson`).
"""
from __future__ import annotations

import json
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "runners"))  # parsers, run_t0_cadence helpers

from PIL import Image

from grounding.data.refdrone import load_refdrone
from grounding.eval.backends import JetsonBackend
from grounding.roi import crop_resize, roi_window
from runners.run_t0_cadence import REMOTE_MMPROJ, REMOTE_MODEL, _timed_anchor_post
from parsers import parse_vlm_server_timings

N = 10
WARMUP = 2
MARGIN = 2.0
HERE = Path(__file__).resolve().parent


def _prep(sample, kind: str) -> tuple[str, int]:
    """Write the exact PNG that would be sent; return (path, feed_max_side)."""
    img = Image.open(sample.image_path).convert("RGB")
    if kind == "full":
        path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
        img.save(path)
        return path, 1024  # deploy accuracy operating point
    out_res = 512 if kind == "crop512" else 384
    win = roi_window(sample.bbox, img.width, img.height, MARGIN)
    crop = crop_resize(img, win, out_res)
    path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    crop.save(path)
    return path, 10**9  # already at target res — disable backend re-resize


if __name__ == "__main__":
    samples = load_refdrone("val", max_samples=N)
    print("[orin-timing] booting deploy backend (Q8_0, 15 W) ...", flush=True)
    backend = JetsonBackend(REMOTE_MODEL, REMOTE_MMPROJ, max_side=1024, startup_timeout_s=300)
    out = {}
    try:
        for kind in ("full", "crop512", "crop384"):
            print(f"[orin-timing] === {kind} (n={N}, {WARMUP} warmup) ===", flush=True)
            # per-sample caption: re-time inline so each uses its own phrase
            prompt_ms, predicted_ms, prompt_n, walls = [], [], [], []
            prepared = [(_prep(s, kind), s.caption) for s in samples]
            for (path, ms), cap in prepared[:WARMUP]:
                _timed_anchor_post(backend._base, path, cap, ms)
            for (path, ms), cap in prepared:
                wall, raw = _timed_anchor_post(backend._base, path, cap, ms)
                walls.append(wall)
                t = parse_vlm_server_timings(raw)
                if t is not None:
                    prompt_ms.append(t.prompt_ms)
                    predicted_ms.append(t.predicted_ms)
                    prompt_n.append(t.prompt_n)
            rec = {
                "kind": kind, "n": len(prompt_ms),
                "prefill_ms_median": statistics.median(prompt_ms) if prompt_ms else None,
                "decode_ms_median": statistics.median(predicted_ms) if predicted_ms else None,
                "wall_ms_median": statistics.median(walls),
                "prompt_toks_median": statistics.median(prompt_n) if prompt_n else None,
            }
            out[kind] = rec
            print(f"[orin-timing] {kind}: prefill={rec['prefill_ms_median']}ms "
                  f"decode={rec['decode_ms_median']}ms toks={rec['prompt_toks_median']} "
                  f"wall={rec['wall_ms_median']:.0f}ms", flush=True)
    finally:
        (HERE / "orin_timing.json").write_text(json.dumps(out, indent=2))
        print(f"[orin-timing] DONE → {HERE / 'orin_timing.json'}", flush=True)
