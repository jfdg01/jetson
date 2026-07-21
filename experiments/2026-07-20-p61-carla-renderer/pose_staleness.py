#!/usr/bin/env python3
"""Replacement for the vacuous `slave_err_*` metric (R-10).

`slave_err_*` compares `cam.get_transform()` against the transform handed to
`cam.set_transform()` one line earlier. The camera is an unattached
`sensor.camera.rgb` -- a kinematic actor with no dynamics -- so the read-back is
the write, and the residual (1.8e-06 m mean) is float32 round-trip noise. It
cannot be nonzero. It measures the assignment.

Where real slaving error *does* live is upstream: `MavlinkPose.__call__` drains
`LOCAL_POSITION_NED` non-blocking and silently returns `self.last` when no new
sample has arrived. Every render tick that reuses a stale pose puts the camera
where the aircraft *was*. That is recoverable from the committed artifact --
consecutive identical rows in `pose_track` are exactly the reused samples -- so
this needs no re-run.

What it does NOT measure: the SITL-side sensor-to-wire latency. `pose_track`
stores (n, e, d, yaw) with no `time_boot_ms`, so only the client-side reuse
interval is on disk. The number below is therefore a lower bound on total lag.

    .venv-ft/bin/python experiments/2026-07-20-p61-carla-renderer/pose_staleness.py
"""
from __future__ import annotations

import json
import math
import statistics as st
from pathlib import Path

RUN = Path(__file__).parent / "runs" / "g3-mavlink" / "results.json"
FIXED_DT = 0.05  # carla_render.py, as run at d925c74


def analyse(path: Path = RUN) -> dict:
    r = json.loads(path.read_text())
    pose, dt = r["pose_track"], r["tick_dt"]

    fresh_gaps, speeds, acc = [], [], 0.0
    stale = 0
    for i in range(1, len(pose)):
        acc += dt[i - 1]
        if pose[i] == pose[i - 1]:
            stale += 1
            continue
        fresh_gaps.append(acc)
        speeds.append(math.dist(pose[i][:3], pose[i - 1][:3]) / acc)
        acc = 0.0

    wall = sum(dt)
    return {
        "ticks": len(pose),
        "stale_ticks": stale,
        "stale_frac": stale / (len(pose) - 1),
        "fresh_samples": len(fresh_gaps),
        "fresh_hz": len(fresh_gaps) / wall,
        "gap_mean_s": st.mean(fresh_gaps),
        "gap_max_s": max(fresh_gaps),
        "speed_median_ms": st.median(speeds),
        # worst observed drought x the speed the aircraft was actually making
        "lag_worst_m": max(fresh_gaps) * st.median(speeds),
        "lag_typical_m": st.mean(fresh_gaps) * st.median(speeds),
        # the sim clock outran the flight clock; see R-10 metric 3
        "wall_s": wall,
        "sim_s": len(pose) * FIXED_DT,
        "sim_over_wall": len(pose) * FIXED_DT / wall,
        # yaw was never slaved: MavlinkPose only fills it from an ATTITUDE poll
        # that never delivered, and slave_err reads .location so nobody noticed
        "yaw_unique_values": len({p[3] for p in pose}),
        "slave_err_mean_m": r["slave_err_mean_m"],
    }


def _selfcheck() -> None:
    """The two properties that make the old metric vacuous and the new one not."""
    m = analyse()
    assert m["slave_err_mean_m"] < 1e-4, "slave_err is supposed to be float noise"
    assert m["lag_worst_m"] > 1.0, "a lag metric that cannot exceed a metre is not one"
    assert m["yaw_unique_values"] == 1, "yaw was constant in this run; recheck if not"


if __name__ == "__main__":
    _selfcheck()
    for k, v in analyse().items():
        print(f"{k:20s} {v:.4g}" if isinstance(v, float) else f"{k:20s} {v}")
