#!/usr/bin/env python3
"""Design-time stress probe for P5.8: does the persistent-requester transport
survive well past a full run's call count?

P5.7 died at ~254 and ~216 ephemeral `gz service` CLI calls (mean ~236), i.e.
inside a single 240-frame run (~480 calls). This probe drives the REAL P5.8
code path (scenegen.ProxyClient -> `scenegen.py proxy` child -> one persistent
pybind Node) against a live select_arena server with the same two services the
recorder uses, alternating set_pose_vector and world-control step, for N pairs
(default 1200 pairs = 2400 calls, 5x the per-run count and 10x the P5.7 MTTF).

Usage (server already running, see README):
    .venv-ft/bin/python experiments/2026-07-17-scenegen-transport/probe_stress.py \
        --pairs 1200 --out experiments/2026-07-17-scenegen-transport/curation/probe_stress.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runners"))
from scenegen import CAM_PERIOD_STEPS, WORLD, ProxyClient  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=1200)
    ap.add_argument("--out", default=str(Path(__file__).parent / "curation" / "probe_stress.json"))
    args = ap.parse_args()

    px = ProxyClient()
    fails = []
    lat_pose, lat_step = [], []
    t0 = time.time()
    for i in range(args.pairs):
        x = 5.0 + (i % 50) * 0.1
        req = (f'pose: {{name: "uav_cam", position: {{x: {x:.3f}, y: 0.0, z: 20.0}}, '
               f'orientation: {{w: 1.0, x: 0.0, y: 0.0, z: 0.0}}}}')
        t = time.time()
        ok, err = px.call(f"/world/{WORLD}/set_pose_vector", "gz.msgs.Pose_V", req)
        lat_pose.append(time.time() - t)
        if not ok:
            fails.append({"i": i, "svc": "set_pose_vector", "err": err[:200]})
        t = time.time()
        ok, err = px.call(f"/world/{WORLD}/control", "gz.msgs.WorldControl",
                          f"pause: true, multi_step: {CAM_PERIOD_STEPS}")
        lat_step.append(time.time() - t)
        if not ok:
            fails.append({"i": i, "svc": "control", "err": err[:200]})
        if i % 100 == 0:
            print(f"[probe] pair {i}/{args.pairs} fails={len(fails)} "
                  f"restarts={px.restarts}", flush=True)
    wall = time.time() - t0
    px.close()

    def stats(v):
        v = sorted(v)
        return {"mean_ms": round(1000 * sum(v) / len(v), 2),
                "p50_ms": round(1000 * v[len(v) // 2], 2),
                "p99_ms": round(1000 * v[int(len(v) * 0.99)], 2),
                "max_ms": round(1000 * v[-1], 2)}

    res = {"pairs": args.pairs, "calls": 2 * args.pairs, "wall_s": round(wall, 1),
           "failed_calls": len(fails), "proxy_restarts": px.restarts,
           "lat_pose": stats(lat_pose), "lat_step": stats(lat_step),
           "fails": fails[:20]}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    print(f"[probe] {'CLEAN' if not fails and not px.restarts else 'FAILURES SEEN'}")


if __name__ == "__main__":
    main()
