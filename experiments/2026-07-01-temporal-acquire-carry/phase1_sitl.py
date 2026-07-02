"""Phase 1: SITL oracle-follow slice with injected VLM acquire cost (RQ-T.5 skeleton).

Perception is perfect (oracle box @ 20 Hz); what's injected is what the temporal
design *costs*: ACQUIRE/REGROUND latency U(4.1, 4.6) s (measured Jetson Q8_0
acquire walls), parse-fail p=0.007 (deployed terse parse rate, worst case), a 5 s
synthetic occlusion, and a 60-frame LossGate (3 s @ 20 Hz ~= demo's 75 @ 25 fps).
During ACQUIRE/REGROUND the copter hovers blind while the rover keeps driving --
the speed sweep asks where that blind window breaks the follow loop.

    .venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/phase1_sitl.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/phase1_sitl.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[1] / "runners"))

LAT_LO, LAT_HI = 4.1, 4.6   # s, measured Jetson acquire walls (campaign README)
P_PARSEFAIL = 0.007         # deployed terse config parses 99.3% worst case (part3 ledger)
LOSS_N = 60                 # no-box frames before REGROUND: 3 s @ 20 Hz
OCC_START, OCC_DUR = 30.0, 5.0   # synthetic occlusion window (s into trial)
SPEEDS = (0.25, 0.5, 1.0)   # rover m/s north; 0.25 = Phase B baseline
DURATION_S = 75.0
CONTROL_HZ = 20


class TemporalSM:
    """ACQUIRE -> CARRY -> (LossGate) -> REGROUND with injected acquire latency.

    step(t, bbox) takes the oracle's current box (None = not visible) and returns
    the box the controller may act on (None while blind). An acquire in flight
    returns at t >= done_t; it succeeds only if the target is visible then and
    the parse didn't fail, else it relaunches.
    """

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.state = "ACQUIRE"
        self.done_t: float | None = None
        self.loss_streak = 0
        self.n_attempts = 0
        self.n_regrounds = 0
        self.first_lock_t: float | None = None
        self.reground_t: float | None = None
        self.relock_walls: list[float] = []

    def _launch(self, t: float) -> None:
        self.done_t = t + self.rng.uniform(LAT_LO, LAT_HI)

    def step(self, t: float, bbox: dict | None) -> dict | None:
        if self.state in ("ACQUIRE", "REGROUND"):
            if self.done_t is None:
                self._launch(t)
            if t >= self.done_t:
                self.n_attempts += 1
                if bbox is None or self.rng.random() < P_PARSEFAIL:
                    self._launch(t)  # target out of frame or parse fail: retry
                else:
                    if self.first_lock_t is None:
                        self.first_lock_t = t
                    if self.state == "REGROUND":
                        self.relock_walls.append(round(t - self.reground_t, 2))
                    self.state, self.loss_streak, self.done_t = "CARRY", 0, None
                    return bbox
            return None  # blind while acquiring
        # CARRY
        if bbox is None:
            self.loss_streak += 1
            if self.loss_streak >= LOSS_N:
                self.state, self.reground_t = "REGROUND", t
                self.n_regrounds += 1
                self._launch(t)
            return None
        self.loss_streak = 0
        return bbox


def run_trial(pb, speed: float, ctrl, csv_path: Path, seed: int) -> dict:
    """One 75 s follow trial at the given rover speed. Adapted from pb.run_trial:
    same telemetry drain / programmatic rover / pacing; ByteTrack replaced by
    TemporalSM, gimbal-level oracle as in Phase B."""
    from sitl.cascade_pid import CascadePID
    from sitl.oracle_bbox import project as oracle_project, IMG_W, IMG_H

    sm = TemporalSM(random.Random(seed))
    pid = CascadePID(kp_yaw=0.0)  # yaw disabled, per Phase B rationale

    copter_ned = (0.0, 0.0, -pb.TAKEOFF_ALT_M)
    attitude = (0.0, 0.0, 0.0)

    # anchor rover to a fresh copter position (Phase B's stale-backlog fix)
    if ctrl.mav is not None:
        while ctrl.mav.recv_match(blocking=False) is not None:
            pass
        pos = ctrl.mav.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=5.0)
        if pos is not None:
            copter_ned = (pos.x, pos.y, pos.z)
        else:
            print(f"[{speed} m/s] WARNING: no fresh LOCAL_POSITION_NED; using {copter_ned}")
    rover_home_n, rover_home_e = copter_ned[0], copter_ned[1]

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(csv_path, "w", newline="")
    w = csv.writer(f)
    w.writerow(["t_s", "state", "copter_n", "copter_e", "copter_d",
                "rover_n", "rover_e", "in_fov", "occluded",
                "bbox_cx", "bbox_cy", "px_err", "vx_cmd", "vy_cmd"])

    n_frames = in_fov_frames = 0
    carry_errs: list[float] = []
    hb_timer = t_start = time.monotonic()

    while time.monotonic() - t_start < DURATION_S:
        t_now = time.monotonic()
        t = t_now - t_start

        rover_ned = (rover_home_n + pb.ROVER_START_N + speed * t, rover_home_e, 0.0)
        copter_ned, attitude = pb._drain_telemetry(ctrl, copter_ned, attitude)

        # gimbal-stabilized nadir camera: LEVEL roll/pitch, real yaw (Phase B model)
        bbox_geo = oracle_project(copter_ned, rover_ned, 0.0, 0.0, attitude[2])
        occluded = OCC_START <= t < OCC_START + OCC_DUR
        out = sm.step(t, None if occluded else bbox_geo)

        sp = pid.compute(out)
        if ctrl.mav:
            ctrl.send_velocity_body(sp["vx"], sp["vy"], sp["vz"], sp["yaw_rate"])
            if t_now - hb_timer >= 1.0:
                ctrl.send_heartbeat()
                hb_timer = t_now

        n_frames += 1
        in_fov_frames += bbox_geo is not None
        px_err = None
        if out is not None:
            px_err = math.hypot(out["cx"] - IMG_W / 2, out["cy"] - IMG_H / 2)
            carry_errs.append(px_err)

        w.writerow([round(t, 2), sm.state,
                    round(copter_ned[0], 2), round(copter_ned[1], 2), round(copter_ned[2], 2),
                    round(rover_ned[0], 2), round(rover_ned[1], 2),
                    int(bbox_geo is not None), int(occluded),
                    round(out["cx"], 1) if out else "", round(out["cy"], 1) if out else "",
                    round(px_err, 1) if px_err is not None else "",
                    round(sp["vx"], 3), round(sp["vy"], 3)])

        sleep_t = 1.0 / CONTROL_HZ - (time.monotonic() - t_now)
        if sleep_t > 0:
            time.sleep(sleep_t)
    f.close()

    m = {
        "speed_ms": speed,
        "n_frames": n_frames,
        "in_fov_frac": round(in_fov_frames / n_frames, 4),
        "first_lock_s": round(sm.first_lock_t, 2) if sm.first_lock_t else None,
        "n_acquire_attempts": sm.n_attempts,
        "n_regrounds": sm.n_regrounds,
        "relock_walls_s": sm.relock_walls,
        "carry_px_err_mean": round(sum(carry_errs) / len(carry_errs), 1) if carry_errs else None,
        "carry_frames": len(carry_errs),
        "recovered_after_occlusion": len(sm.relock_walls) >= 1,
    }
    print(f"[{speed} m/s] in_fov={m['in_fov_frac']:.3f} lock@{m['first_lock_s']}s "
          f"attempts={m['n_acquire_attempts']} regrounds={m['n_regrounds']} "
          f"relock={m['relock_walls_s']} px_err={m['carry_px_err_mean']}")
    return m


def selfcheck() -> None:
    """Drive the state machine kinematics-free: fixed 4.3 s latency via seeded rng."""
    rng = random.Random(0)
    sm = TemporalSM(rng)
    box = {"cx": 320.0, "cy": 240.0, "w": 20.0, "h": 20.0}
    dt = 1.0 / CONTROL_HZ
    occ = lambda t: OCC_START <= t < OCC_START + OCC_DUR
    lock_t = gate_t = relock_t = None
    for i in range(int(DURATION_S / dt)):
        t = i * dt
        prev = sm.state
        out = sm.step(t, None if occ(t) else box)
        if prev != "CARRY" and sm.state == "CARRY" and lock_t is None:
            lock_t = t
        if prev == "CARRY" and sm.state == "REGROUND":
            gate_t = t
        if prev == "REGROUND" and sm.state == "CARRY":
            relock_t = t
        if sm.state == "CARRY" and not occ(t):
            assert out is not None
        if occ(t):
            assert out is None, "must be blind during occlusion"
    assert lock_t is not None and LAT_LO <= lock_t <= LAT_HI + dt, f"first lock {lock_t}"
    assert gate_t is not None and abs(gate_t - (OCC_START + LOSS_N * dt)) <= 2 * dt, \
        f"LossGate fired at {gate_t}, expected ~{OCC_START + LOSS_N * dt}"
    assert relock_t is not None and relock_t >= OCC_START + OCC_DUR, f"relock {relock_t}"
    assert sm.n_regrounds == 1 and len(sm.relock_walls) == 1
    print(f"selfcheck PASS  lock@{lock_t:.2f}s gate@{gate_t:.2f}s relock@{relock_t:.2f}s "
          f"wall={sm.relock_walls[0]}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true", help="state machine only, no SITL")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    if args.selfcheck:
        selfcheck()
        return

    import run_phase_b as pb
    from sitl.offboard import OffboardController
    from grounding.manifest import capture, write as write_manifest

    raw_dir = HERE / "raw" / "phase1-sitl"
    raw_dir.mkdir(parents=True, exist_ok=True)
    pb.SITL_DIR.mkdir(parents=True, exist_ok=True)
    if not pb.ARDUCOPTER_BIN.exists():
        sys.exit(f"SITL binary missing: {pb.ARDUCOPTER_BIN}")

    copter_proc = None
    try:
        copter_proc = pb._start_sitl(pb.ARDUCOPTER_BIN, pb.COPTER_PORT, pb.COPTER_PARM,
                                     0, raw_dir / "copter-sitl.log")
        time.sleep(5.0)  # let SITL bind; ctrl is the sole client on 5760
        ctrl = OffboardController(f"tcp:127.0.0.1:{pb.COPTER_PORT}")
        ctrl.connect_and_takeoff(target_alt_m=pb.TAKEOFF_ALT_M)

        trials = []
        for i, speed in enumerate(SPEEDS):
            if i > 0:
                print("[pause] 10 s hover between trials")
                t0 = time.monotonic()
                while time.monotonic() - t0 < 10.0:  # keep offboard link alive
                    ctrl.hover()
                    ctrl.send_heartbeat()
                    time.sleep(0.5)
            trials.append(run_trial(pb, speed, ctrl,
                                    raw_dir / f"trial-{speed}ms.csv", args.seed + i))
        ctrl.land_and_disarm()
        ctrl.close()
    finally:
        if copter_proc and copter_proc.poll() is None:
            copter_proc.terminate()

    base = trials[0]
    gate = base["in_fov_frac"] >= 0.90 and base["recovered_after_occlusion"]
    summary = {"trials": trials, "gate_speed_ms": SPEEDS[0],
               "gate": "PASS" if gate else "FAIL"}
    cfg = {"lat_s": [LAT_LO, LAT_HI], "p_parsefail": P_PARSEFAIL, "loss_n": LOSS_N,
           "occ": [OCC_START, OCC_DUR], "speeds": list(SPEEDS),
           "duration_s": DURATION_S, "hz": CONTROL_HZ, "seed": args.seed}
    out_dir = HERE / "runs" / "phase1-sitl"
    write_manifest(capture("phase1-sitl-oracle", cfg), runs_dir=str(out_dir), results=summary)
    (out_dir / "results.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
