#!/usr/bin/env python3
"""run_t4.py — Part III · T4 on-Orin deployment + sim-to-device characterisation.

T0 measured the two tiers *in isolation and off-device*: anchor cadence on the Orin
via llama-server (T0a), but the tracker cost (T0b) on the RTX-3090 workstation. T4
runs the **integrated two-tier loop on the actual Orin Nano** and reconciles the
measured device timings against the T0 cadence budget — the deployment gate.

Phases (run with --phase {a,b,c,all}):
  T4a — Fast tier ON THE ORIN CPU. Push bytetrack.py to the device, time
        ByteTracker.update() over the *same* T0b 1200-frame stream on aarch64 @ 15 W.
        The new sim-to-device number for the 20 Hz tier (T0b was the dev box).
  T4b — Slow tier on the Orin, REAL in-loop anchor. Boot the deployed Qwen2-VL-2B
        Q8_0 via JetsonBackend and fire real grounding anchors @512 through the
        verbatim contract path; measure end-to-end wall latency (the rate the real
        loop sees). Confirms / re-measures T0a on the metal.
  T4c — Integrated budget + sim-to-device verdict. Reconcile both tiers against the
        50 ms (20 Hz) budget and the 1.5 s coast horizon; emit the dev-box→Orin
        table and the deployment verdict. Writes results JSON.

Reuses the T0 harness wholesale (helpers imported from run_t0_cadence) — only the
on-device tracker push and the budget reconciliation are new.

Self-check (no device): `.venv-ft/bin/python runners/run_t4.py` runs the
deterministic asserts. Device run: `.venv-ft/bin/python runners/run_t4.py --phase all`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_t0_cadence as t0  # noqa: E402  reuse the whole T0 harness

RESULTS_DIR = ROOT / "results" / "2026-06-24-t4-deployment"
SITL = Path(__file__).resolve().parent / "sitl"

# Dev-box (RTX 3090) baselines recorded in experiments/2026-06-18-t0-cadence/README.md,
# so the sim-to-device gap is a side-by-side, not a re-derivation.
DEVBOX_TRACKER_MEDIAN_MS = 0.051
DEVBOX_TRACKER_P99_MS = 0.103
T0A_512_WALL_MS = 2265.0          # T0a @512 wall median (0.44 Hz)
COAST_HORIZON_S = 30 / t0.CONTROL_HZ   # MAX_LOST_FRAMES / 20 Hz = 1.5 s


# ── T4a: fast tier on the Orin CPU ────────────────────────────────────────────

# The remote driver replays the *exact* T0b workload (same wander + intermittent
# distractor) so dev-box vs Orin is one-variable. Kept as a heredoc so the only
# artifact pushed is bytetrack.py — _observe()/PID are scalar arithmetic, dwarfed
# by the Kalman predict + Hungarian match this measures.
# ponytail: heredoc over a packaged remote module — one file pushed, no install;
# promote to a real remote package if T4 ever needs the full reid+PID step timed.
_REMOTE_TRACKER_DRIVER = r'''
import json, math, statistics, sys, time
sys.path.insert(0, "/tmp/t4_sitl")
from bytetrack import ByteTracker, MAX_LOST_FRAMES

tracker = ByteTracker()
durations = []
for i in range(1200):                      # 60 s @ 20 Hz, identical to T0b
    cx = 320.0 + 120.0 * math.sin(i * 0.04)
    cy = 240.0 + 70.0 * math.cos(i * 0.03)
    dets = [{"cx": cx, "cy": cy, "w": 52.0, "h": 30.0, "score": 0.92}]
    if (i // 40) % 5 == 0:
        dets.append({"cx": 600.0 - (i % 40) * 12.0, "cy": 240.0,
                     "w": 48.0, "h": 28.0, "score": 0.55})
    t = time.perf_counter()
    tracker.update(dets)
    durations.append((time.perf_counter() - t) * 1000.0)

warm = sorted(durations[20:])
p99 = warm[min(len(warm) - 1, int(math.ceil(0.99 * len(warm)) - 1))]
print(json.dumps({
    "n": len(warm),
    "median": statistics.median(warm),
    "mean": statistics.mean(warm),
    "p99": p99,
    "max": warm[-1],
    "max_lost_frames": MAX_LOST_FRAMES,
}))
'''


def run_t4a() -> dict:
    print("[T4a] pushing bytetrack.py → jetson:/tmp/t4_sitl/ ...")
    subprocess.run(["ssh", t0.SSH_HOST, "mkdir -p /tmp/t4_sitl"], check=True, timeout=30)
    subprocess.run(["scp", str(SITL / "bytetrack.py"),
                    f"{t0.SSH_HOST}:/tmp/t4_sitl/bytetrack.py"], check=True, timeout=60)
    print("[T4a] timing ByteTracker.update over 1200 frames on the Orin (aarch64, 15 W) ...")
    out = subprocess.run(
        ["ssh", t0.SSH_HOST, "python3 -u -"], input=_REMOTE_TRACKER_DRIVER,
        capture_output=True, text=True, timeout=120,
    )
    if out.returncode != 0:
        raise RuntimeError(f"remote tracker driver failed:\n{out.stderr}")
    st = json.loads(out.stdout.strip().splitlines()[-1])
    headroom_ms = t0.BUDGET_MS - st["median"]
    slowdown = st["median"] / DEVBOX_TRACKER_MEDIAN_MS if DEVBOX_TRACKER_MEDIAN_MS else 0.0
    res = {
        "phase": "T4a", "host": "Orin Nano 8GB (aarch64, 15 W)",
        "update_ms": st, "budget_ms": t0.BUDGET_MS,
        "implied_max_hz": 1000.0 / st["median"] if st["median"] else 0.0,
        "headroom_ms_median": headroom_ms, "headroom_frac": headroom_ms / t0.BUDGET_MS,
        "devbox_median_ms": DEVBOX_TRACKER_MEDIAN_MS, "sim_to_device_slowdown": slowdown,
    }
    print(f"[T4a] Orin update median={st['median']:.3f} ms p99={st['p99']:.3f} ms "
          f"→ max {res['implied_max_hz']:.0f} Hz; headroom {headroom_ms:.2f} ms "
          f"({res['headroom_frac']:.1%}); {slowdown:.1f}× the dev box")
    return res


# ── T4b: slow tier on the Orin, real in-loop anchor ───────────────────────────

def run_t4b(n_reps: int = 8) -> dict:
    from grounding.contract import parse_bbox
    from grounding.eval.backends import JetsonBackend

    t0.RESULTS_RAW.mkdir(parents=True, exist_ok=True)
    frame = t0.RESULTS_RAW / f"t4b-anchor-frame-{t0._utc_tag()}.png"
    t0._make_synthetic_frame().save(frame)
    print(f"[T4b] booting JetsonBackend (deployed Qwen2-VL-2B Q8_0, 15 W) ...")
    backend = JetsonBackend(t0.REMOTE_MODEL, t0.REMOTE_MMPROJ, max_side=1024, startup_timeout_s=300)
    walls, parse_ok = [], 0
    try:
        for _ in range(2):  # warmup
            t0._timed_anchor_post(backend._base, str(frame), t0.CAPTION, 512)
        for _ in range(n_reps):
            wall, raw = t0._timed_anchor_post(backend._base, str(frame), t0.CAPTION, 512)
            walls.append(wall)
            try:
                content = json.loads(raw)["choices"][0]["message"].get("content") or ""
            except Exception:
                content = ""
            parse_ok += int(parse_bbox(content) is not None)
    finally:
        if getattr(backend, "_proc", None):
            backend._proc.terminate()
    st = t0._stats(walls)
    anchor_period_s = st["median"] / 1000.0
    res = {
        "phase": "T4b", "host": "Orin Nano 8GB (15 W)", "max_side": 512,
        "wall_ms": st, "anchor_hz_median": 1000.0 / st["median"] if st["median"] else 0.0,
        "anchor_period_s": anchor_period_s, "parse_rate": parse_ok / n_reps if n_reps else 0.0,
        "t0a_512_wall_ms": T0A_512_WALL_MS,
        "drift_vs_t0a_pct": 100.0 * (st["median"] - T0A_512_WALL_MS) / T0A_512_WALL_MS,
    }
    print(f"[T4b] Orin anchor wall median={st['median']:.0f} ms "
          f"({res['anchor_hz_median']:.2f} Hz), parse_rate={res['parse_rate']:.0%}, "
          f"drift vs T0a {res['drift_vs_t0a_pct']:+.1f}%")
    return res


# ── T4c: integrated budget + sim-to-device verdict ────────────────────────────

def run_t4c(a: dict, b: dict) -> dict:
    """Reconcile both measured tiers against the T0 cadence budget on the metal."""
    tracker_ok = a["update_ms"]["p99"] < t0.BUDGET_MS       # fast tier fits 20 Hz?
    anchor_period = b["anchor_period_s"]
    event_triggered_required = anchor_period > COAST_HORIZON_S  # re-acq can't be timer-only
    res = {
        "phase": "T4c",
        "tracker_p99_ms": a["update_ms"]["p99"], "budget_ms": t0.BUDGET_MS,
        "fast_tier_fits_20hz": tracker_ok,
        "anchor_period_s": anchor_period, "coast_horizon_s": COAST_HORIZON_S,
        "event_triggered_reacq_required": event_triggered_required,
        "sim_to_device": {
            "tracker_devbox_median_ms": DEVBOX_TRACKER_MEDIAN_MS,
            "tracker_orin_median_ms": a["update_ms"]["median"],
            "tracker_slowdown": a["sim_to_device_slowdown"],
            "anchor_t0a_wall_ms": T0A_512_WALL_MS,
            "anchor_orin_wall_ms": b["wall_ms"]["median"],
        },
        # The deployment verdict: both tiers fit their roles, and the on-Orin numbers
        # reproduce the T0 design budget that the whole two-tier architecture rests on.
        "deploys_within_t0_budget": tracker_ok and event_triggered_required,
    }
    print(f"[T4c] fast tier fits 20 Hz: {tracker_ok} (p99 {res['tracker_p99_ms']:.3f} "
          f"ms < {t0.BUDGET_MS:.0f} ms)")
    print(f"[T4c] anchor period {anchor_period:.2f} s vs coast {COAST_HORIZON_S:.1f} s "
          f"→ event-triggered re-acq required: {event_triggered_required}")
    print(f"[T4c] DEPLOYS within T0 cadence budget: {res['deploys_within_t0_budget']}")
    return res


# ── self-check (no device) ────────────────────────────────────────────────────

def _test_budget_logic():
    """T4c verdict must be monotone in the measured timings (the gate's own logic)."""
    a = {"update_ms": {"median": 0.4, "p99": 0.9}, "sim_to_device_slowdown": 7.8}
    b = {"anchor_period_s": 2.27, "wall_ms": {"median": 2270.0}}
    r = run_t4c(a, b)
    assert r["fast_tier_fits_20hz"] is True, "0.9 ms p99 must fit the 50 ms budget"
    assert r["event_triggered_reacq_required"] is True, "2.27 s > 1.5 s coast must force event re-acq"
    assert r["deploys_within_t0_budget"] is True
    # a tracker that blows the budget must fail the gate
    a_bad = {"update_ms": {"median": 60.0, "p99": 80.0}, "sim_to_device_slowdown": 1e3}
    assert run_t4c(a_bad, b)["deploys_within_t0_budget"] is False, "80 ms p99 must fail 20 Hz"
    print("[selftest] T4c budget logic OK")


def main():
    ap = argparse.ArgumentParser(description="Part III T4 on-Orin deployment harness")
    ap.add_argument("--phase", choices=["a", "b", "c", "all"], default=None,
                    help="device phase to run; omit for the no-device self-check")
    args = ap.parse_args()

    if args.phase is None:
        _test_budget_logic()
        print("\nself-check passed — pass --phase all to run on the Orin (ssh jetson).")
        return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out: dict = {"generated_utc": t0._utc_tag()}
    a = run_t4a() if args.phase in ("a", "all") else None
    b = run_t4b() if args.phase in ("b", "all") else None
    if args.phase in ("c", "all") and a and b:
        out["t4c"] = run_t4c(a, b)
    if a:
        out["t4a"] = a
    if b:
        out["t4b"] = b
    dest = RESULTS_DIR / f"t4-results-{out['generated_utc']}.json"
    dest.write_text(json.dumps(out, indent=2))
    print(f"\n[T4] results → {dest}")


if __name__ == "__main__":
    main()
