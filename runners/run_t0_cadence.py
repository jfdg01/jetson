#!/usr/bin/env python3
"""run_t0_cadence.py — Part III · T0 cadence & dynamics harness (measure-before-design).

Pre-registration: experiments/2026-06-18-t0-cadence/README.md
Branch: v3/object-permanence

Four sub-experiments, selectable with --phase {a,b,c,d,all}:

  T0a — Anchor cadence.  Boot the deployed Qwen2-VL-2B Q8_0 on the Orin via the real
        deploy path (grounding.eval.backends.JetsonBackend), then issue a *custom*
        /v1/chat/completions POST carrying "__verbose": true so the server echoes its
        prompt_ms/predicted_ms split (the stock backend.generate() discards timings).
        Sweep max_side ∈ {512, 768, 1024}; wall-clock + server timings + tegrastats.
  T0b — Tracker cost.    Profile bytetrack.ByteTracker.update() over a realistic 20 Hz
        single-target stream; report mean/median/p99 ms, implied max Hz, headroom under
        the 50 ms (20 Hz) budget for an added appearance/re-ID model.
  T0c — Target dynamics. Step oracle_bbox.project() at 20 Hz over altitude × ground
        speed; report pixel velocity, time-in-frame, and scale-change rate (descent).
  T0d — Re-ID feasibility (geometry half). Target crop size in px at follow altitudes
        — how much appearance signal a re-locked target carries (constraint #2 check).

RUN UNDER .venv-ft  (needs PIL + numpy + scipy + the grounding package).
GPU/eval discipline per CLAUDE.md; device reached via `ssh jetson` (15 W mode).
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))                       # grounding package
sys.path.insert(0, str(Path(__file__).resolve().parent))  # sitl/, parsers

# ── constants ────────────────────────────────────────────────────────────────
FRAME_W, FRAME_H = 640, 480          # SITL downward-cam native (oracle intrinsics)
# Anchor source rendered larger than the camera so the 512/768/1024 long-edge
# sweep is a genuine downscale at every point (max_side >= long-edge is a no-op
# in _resize_keep_aspect). 1024×768 keeps the 4:3 camera aspect.
SRC_W, SRC_H = 1024, 768
CONTROL_HZ = 20
BUDGET_MS = 1000.0 / CONTROL_HZ                     # 50 ms per-frame budget

RESULTS_RAW = ROOT / "results" / "raw"

# Anchor artifacts already deployed on the device (verified present — no re-push).
REMOTE_MODEL = "/home/jfdg/grounding/phase3-refdrone-1024-q8_0.gguf"
REMOTE_MMPROJ = "/home/jfdg/grounding/mmproj-phase3-refdrone-1024-f16.gguf"
SSH_HOST = "jetson"

RESOLUTIONS = [512, 768, 1024]                      # long-edge max_side, Part-II grid
CAPTION = "the white van"
N_WARMUP = 2
N_REPS = 8

ALTITUDES_M = [10, 20, 30]
SPEEDS_MS = [1, 3, 5, 10]


def _utc_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _stats(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0, "mean": 0.0, "median": 0.0, "p99": 0.0, "min": 0.0, "max": 0.0}
    s = sorted(xs)
    p99 = s[min(len(s) - 1, int(math.ceil(0.99 * len(s)) - 1))]
    return {
        "n": len(xs),
        "mean": statistics.mean(xs),
        "median": statistics.median(xs),
        "p99": p99,
        "min": s[0],
        "max": s[-1],
    }


# ── synthetic anchor frame (deterministic; textured ground, no pure-color) ─────

def _make_synthetic_frame(seed: int = 42):
    """1024×768 RGB: noisy/gradient ground + a white-ish van and distractor cars.

    Deterministic (fixed seed). The ground is textured (not flat) and vehicles are
    not pure primaries, honouring the Part III no-pure-color fidelity constraint —
    this frame only drives the anchor *timing* sweep, not accuracy, but we keep it
    representative so the prefill token count is realistic. Rendered at SRC_W×SRC_H
    (> camera native) so the 512/768/1024 long-edge sweep is a real downscale at
    every point. Vehicle rectangles are placed in 640×480 coords then scaled.
    """
    import numpy as np
    from PIL import Image, ImageDraw

    sx, sy = SRC_W / FRAME_W, SRC_H / FRAME_H
    rng = np.random.default_rng(seed)
    base = rng.integers(55, 105, size=(SRC_H, SRC_W, 3), dtype=np.int16)
    grad = np.linspace(0, 35, SRC_H).astype(np.int16)[:, None, None]
    arr = np.clip(base + grad, 0, 255).astype("uint8")
    img = Image.fromarray(arr, "RGB")
    d = ImageDraw.Draw(img)

    def _box(x1, y1, x2, y2, fill):
        d.rectangle([x1 * sx, y1 * sy, x2 * sx, y2 * sy], fill=fill)

    _box(300, 210, 362, 252, (222, 224, 218))   # white van (target)
    _box(118, 100, 166, 132, (74, 92, 138))     # blue-grey car
    _box(458, 318, 506, 350, (140, 70, 66))     # dull-red car
    _box(220, 360, 280, 392, (208, 210, 205))   # 2nd light vehicle
    return img


# ── T0a: on-Orin anchor cadence ───────────────────────────────────────────────

def _timed_anchor_post(base_url: str, image_path: str, caption: str,
                       max_side: int, timeout: int = 300):
    """One timed /v1/chat/completions POST with server timings requested.

    Mirrors grounding.eval.backends._llama_server_chat byte-for-byte (verbatim
    GROUNDING_PROMPT, lossless PNG, greedy, cache_prompt=False) but adds
    "__verbose": true so the response carries the prompt_ms/predicted_ms split,
    and returns the raw JSON text + wall-clock ms (the rate the real loop sees).
    """
    import base64
    import tempfile
    import urllib.request

    from PIL import Image

    from grounding.contract import GROUNDING_PROMPT, MAX_NEW_TOKENS
    from grounding.eval.backends import _resize_keep_aspect

    img = Image.open(image_path).convert("RGB")
    img = _resize_keep_aspect(img, max_side)
    prompt = GROUNDING_PROMPT.format(target=caption)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
        img.save(tmp.name)
        b64 = base64.b64encode(open(tmp.name, "rb").read()).decode()

    payload = json.dumps({
        "model": "vlm",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": prompt},
        ]}],
        "max_tokens": MAX_NEW_TOKENS,
        "temperature": 0.0,
        "cache_prompt": False,
        "__verbose": True,
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
    wall_ms = (time.perf_counter() - t0) * 1000.0
    return wall_ms, raw


def _start_tegrastats(remote_log: str) -> int | None:
    cmd = (f"nohup tegrastats --interval 1000 --logfile {remote_log} "
           f"> /dev/null 2>&1 & echo $!")
    out = subprocess.run(["ssh", SSH_HOST, cmd], capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        print(f"[T0a] WARN: tegrastats start failed: {out.stderr.strip()}")
        return None
    try:
        return int(out.stdout.strip().split()[-1])
    except (ValueError, IndexError):
        print(f"[T0a] WARN: could not parse tegrastats PID from {out.stdout!r}")
        return None


def _stop_tegrastats(pid: int | None, remote_log: str, local_path: Path) -> None:
    kill = f"kill {pid} 2>/dev/null; " if pid else ""
    subprocess.run(["ssh", SSH_HOST, f"{kill}pkill -f tegrastats 2>/dev/null; true"], timeout=30)
    subprocess.run(["scp", f"{SSH_HOST}:{remote_log}", str(local_path)], timeout=60)


def _jetson_clocks_state() -> str:
    """Best-effort read of whether jetson_clocks is engaged (recorded next to numbers)."""
    out = subprocess.run(
        ["ssh", SSH_HOST, "sudo -n jetson_clocks --show 2>/dev/null | head -1 || echo unknown"],
        capture_output=True, text=True, timeout=30,
    )
    return out.stdout.strip() or "unknown"


def run_t0a() -> dict:
    from grounding.contract import parse_bbox
    from grounding.eval.backends import JetsonBackend
    from parsers import parse_tegrastats, parse_vlm_server_timings

    RESULTS_RAW.mkdir(parents=True, exist_ok=True)
    tag = _utc_tag()
    frame_path = RESULTS_RAW / f"t0a-synthetic-frame-{tag}.png"
    _make_synthetic_frame().save(frame_path)
    print(f"[T0a] synthetic frame → {frame_path}")

    clocks = _jetson_clocks_state()
    print(f"[T0a] jetson_clocks: {clocks}")

    remote_log = f"/tmp/t0a_tegra_{tag}.log"
    local_log = RESULTS_RAW / f"t0a-tegrastats-{tag}.log"

    print("[T0a] booting JetsonBackend (Qwen2-VL-2B Q8_0, -ngl 99, 15 W) ...")
    backend = JetsonBackend(REMOTE_MODEL, REMOTE_MMPROJ, max_side=1024, startup_timeout_s=300)
    per_res: dict = {}
    tegra_pid = None
    try:
        tegra_pid = _start_tegrastats(remote_log)
        time.sleep(6)  # capture a short idle baseline before the first inference
        for res in RESOLUTIONS:
            print(f"[T0a] max_side={res}: {N_WARMUP} warmup + {N_REPS} timed reps ...")
            for _ in range(N_WARMUP):
                _timed_anchor_post(backend._base, str(frame_path), CAPTION, res)
            walls: list[float] = []
            prompt_ms: list[float] = []
            predicted_ms: list[float] = []
            predicted_n: list[int] = []
            prompt_n: list[int] = []
            parse_ok = 0
            for _ in range(N_REPS):
                wall, raw = _timed_anchor_post(backend._base, str(frame_path), CAPTION, res)
                walls.append(wall)
                t = parse_vlm_server_timings(raw)
                if t is not None:
                    prompt_ms.append(t.prompt_ms)
                    predicted_ms.append(t.predicted_ms)
                    predicted_n.append(t.predicted_n)
                    prompt_n.append(t.prompt_n)
                try:
                    content = json.loads(raw)["choices"][0]["message"].get("content") or ""
                except Exception:
                    content = ""
                if parse_bbox(content) is not None:
                    parse_ok += 1
            wall_stats = _stats(walls)
            entry = {
                "max_side": res,
                "wall_ms": wall_stats,
                "wall_hz_median": 1000.0 / wall_stats["median"] if wall_stats["median"] else 0.0,
                "parse_rate": parse_ok / N_REPS,
                "server_timings_present": bool(prompt_ms),
            }
            if prompt_ms:
                entry["prompt_ms_mean"] = statistics.mean(prompt_ms)
                entry["predicted_ms_mean"] = statistics.mean(predicted_ms)
                entry["per_frame_ms_mean"] = statistics.mean(prompt_ms) + statistics.mean(predicted_ms)
                entry["server_hz"] = 1000.0 / entry["per_frame_ms_mean"] if entry["per_frame_ms_mean"] else 0.0
                entry["predicted_n_mean"] = statistics.mean(predicted_n)
                entry["prompt_n_mean"] = statistics.mean(prompt_n)
            per_res[res] = entry
            print(f"[T0a]   wall median={wall_stats['median']:.0f} ms "
                  f"({entry['wall_hz_median']:.2f} Hz), parse_rate={entry['parse_rate']:.0%}")
            if prompt_ms:
                print(f"[T0a]   server prompt={entry['prompt_ms_mean']:.0f} ms "
                      f"decode={entry['predicted_ms_mean']:.0f} ms "
                      f"({entry['predicted_n_mean']:.0f} tok)")
    finally:
        _stop_tegrastats(tegra_pid, remote_log, local_log)
        backend.close()

    power = {}
    try:
        summary = parse_tegrastats(local_log.read_text())
        power = {
            "idle_w": summary.idle_w,
            "mean_w": summary.mean_w,
            "peak_w": summary.peak_w,
            "peak_temp_c": summary.peak_temp_c,
            "peak_ram_mb": summary.peak_ram_mb,
            "swap_growth_mb": summary.swap_growth_mb,
            "swap_hit": summary.swap_hit,
            "log": str(local_log),
        }
        print(f"[T0a] power: idle={power['idle_w']:.1f} W mean={power['mean_w']:.1f} W "
              f"peak={power['peak_w']:.1f} W, peak_temp={power['peak_temp_c']:.0f} C, "
              f"peak_ram={power['peak_ram_mb']:.0f} MB")
    except Exception as e:
        print(f"[T0a] WARN: could not parse tegrastats log: {e}")

    return {
        "phase": "T0a",
        "device": "Orin Nano 8GB, nvpmodel -m 0 (15 W)",
        "jetson_clocks": clocks,
        "model": "phase3-refdrone-1024-q8_0.gguf",
        "n_warmup": N_WARMUP,
        "n_reps": N_REPS,
        "resolutions": per_res,
        "power": power,
    }


# ── T0b: per-frame tracker cost @ 20 Hz ───────────────────────────────────────

def run_t0b() -> dict:
    from sitl.bytetrack import ByteTracker, MAX_LOST_FRAMES

    tracker = ByteTracker()
    n_frames = 1200  # 60 s @ 20 Hz
    durations: list[float] = []
    cx, cy = 320.0, 240.0
    for i in range(n_frames):
        # realistic single-target wander + a crossing distractor every so often
        cx = 320.0 + 120.0 * math.sin(i * 0.04)
        cy = 240.0 + 70.0 * math.cos(i * 0.03)
        dets = [{"cx": cx, "cy": cy, "w": 52.0, "h": 30.0, "score": 0.92}]
        if (i // 40) % 5 == 0:  # intermittent distractor (two-track association cost)
            dets.append({"cx": 600.0 - (i % 40) * 12.0, "cy": 240.0,
                         "w": 48.0, "h": 28.0, "score": 0.55})
        t0 = time.perf_counter()
        tracker.update(dets)
        durations.append((time.perf_counter() - t0) * 1000.0)

    warm = durations[20:]  # drop JIT/warmup frames
    st = _stats(warm)
    headroom_ms = BUDGET_MS - st["median"]
    result = {
        "phase": "T0b",
        "host": f"{platform.node()} ({platform.processor() or platform.machine()})",
        "n_frames": len(warm),
        "budget_ms": BUDGET_MS,
        "update_ms": st,
        "implied_max_hz": 1000.0 / st["median"] if st["median"] else 0.0,
        "headroom_ms_median": headroom_ms,
        "headroom_frac": headroom_ms / BUDGET_MS,
        "max_lost_frames": MAX_LOST_FRAMES,
        "coast_horizon_s": MAX_LOST_FRAMES / CONTROL_HZ,
    }
    print(f"[T0b] update median={st['median']:.3f} ms p99={st['p99']:.3f} ms "
          f"→ max {result['implied_max_hz']:.0f} Hz; headroom {headroom_ms:.1f} ms "
          f"({result['headroom_frac']:.0%} of 50 ms budget)")
    return result


# ── T0c: target dynamics (px velocity, time-in-frame, scale-change) ───────────

def run_t0c() -> dict:
    from sitl.oracle_bbox import project_unclipped

    dt = 1.0 / CONTROL_HZ
    cells: list[dict] = []
    for h in ALTITUDES_M:
        copter = (0.0, 0.0, -float(h))   # NED: altitude h above ground, nadir hover
        for v in SPEEDS_MS:
            # target crosses through nadir along +north at ground speed v.
            # project_unclipped gives the TRUE centre (clipping a large box at an
            # edge would otherwise dampen the apparent velocity — see oracle_bbox).
            T = 30.0
            n = int(T / dt)
            x0 = -v * T / 2.0
            prev = None
            pxvels: list[float] = []
            in_frame = 0
            for i in range(n):
                x = x0 + v * i * dt
                box = project_unclipped(copter, (x, 0.0, 0.0), 0.0, 0.0, 0.0)
                if box is None or not box["visible"]:
                    prev = None
                    continue
                in_frame += 1
                c = (box["cx"], box["cy"])
                if prev is not None:
                    pxvels.append(math.hypot(c[0] - prev[0], c[1] - prev[1]))
                prev = c
            v_st = _stats(pxvels)
            cells.append({
                "altitude_m": h,
                "speed_ms": v,
                "px_per_frame_median": v_st["median"],
                "px_per_s_median": v_st["median"] * CONTROL_HZ,
                "time_in_frame_s": in_frame * dt,
            })

    # scale-change: stationary target under a descending camera (30→10 m @ 2 m/s)
    descend_vh = 2.0
    h = 30.0
    prev_area = None
    scale_pct_per_frame: list[float] = []
    while h > 10.0:
        box = project_unclipped((0.0, 0.0, -h), (0.0, 0.0, 0.0), 0.0, 0.0, 0.0)
        if box is not None:
            area = box["w"] * box["h"]
            if prev_area:
                scale_pct_per_frame.append(100.0 * (area - prev_area) / prev_area)
            prev_area = area
        h -= descend_vh * dt
    scale_st = _stats(scale_pct_per_frame)

    result = {
        "phase": "T0c",
        "control_hz": CONTROL_HZ,
        "cells": cells,
        "scale_change_descent": {
            "descent_rate_ms": descend_vh,
            "area_pct_per_frame_median": scale_st["median"],
            "area_pct_per_frame_max": scale_st["max"],
        },
    }
    print("[T0c] px/frame by (alt, speed):")
    for c in cells:
        print(f"[T0c]   {c['altitude_m']:>2} m × {c['speed_ms']:>2} m/s → "
              f"{c['px_per_frame_median']:6.2f} px/frame "
              f"({c['px_per_s_median']:6.1f} px/s), in-frame {c['time_in_frame_s']:.1f} s")
    print(f"[T0c] scale change (2 m/s descent): "
          f"median {scale_st['median']:.2f}% / frame, max {scale_st['max']:.2f}% / frame")
    return result


# ── T0d: re-ID feasibility (crop-size geometry) ───────────────────────────────

def run_t0d() -> dict:
    from sitl.oracle_bbox import project_unclipped

    crops: list[dict] = []
    for h in ALTITUDES_M:
        box = project_unclipped((0.0, 0.0, -float(h)), (0.0, 0.0, 0.0), 0.0, 0.0, 0.0)
        if box is None:
            crops.append({"altitude_m": h, "crop_w_px": 0, "crop_h_px": 0, "crop_area_px": 0})
            continue
        crops.append({
            "altitude_m": h,
            "crop_w_px": round(box["w"], 1),
            "crop_h_px": round(box["h"], 1),
            "crop_area_px": round(box["w"] * box["h"], 0),
        })
    result = {
        "phase": "T0d",
        "note": ("Geometry half only. Crop = projected target bbox at nadir for a 4×2 m "
                 "vehicle. Embedding-separability half deferred to T1 (needs rendered pixels)."),
        "crops": crops,
    }
    print("[T0d] target crop size (px) at follow altitude:")
    for c in crops:
        print(f"[T0d]   {c['altitude_m']:>2} m → {c['crop_w_px']}×{c['crop_h_px']} px "
              f"(area {c['crop_area_px']:.0f} px²)")
    return result


# ── driver ─────────────────────────────────────────────────────────────────--

def main() -> None:
    ap = argparse.ArgumentParser(description="Part III T0 cadence & dynamics harness")
    ap.add_argument("--phase", choices=["a", "b", "c", "d", "all"], default="all")
    ap.add_argument("--out", default=None, help="write combined JSON results here")
    args = ap.parse_args()

    RESULTS_RAW.mkdir(parents=True, exist_ok=True)
    results: dict = {"started": datetime.now(timezone.utc).isoformat()}
    want = {"a", "b", "c", "d"} if args.phase == "all" else {args.phase}

    # locally-feasible phases first (b, c, d), then the on-Orin sweep (a)
    if "b" in want:
        results["T0b"] = run_t0b()
    if "c" in want:
        results["T0c"] = run_t0c()
    if "d" in want:
        results["T0d"] = run_t0d()
    if "a" in want:
        results["T0a"] = run_t0a()

    out = Path(args.out) if args.out else RESULTS_RAW / f"t0-results-{_utc_tag()}.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\n[T0] combined results → {out}")


if __name__ == "__main__":
    main()
