#!/usr/bin/env python3
"""T3 — closed-loop permanence integration in SITL.

Phase-C's negative: sparse-cadence perception + memoryless coasting could not hold a
moving lock. Branch-1 (1 Hz oracle inject + 20 Hz Kalman coast) showed the *mechanics*
follow a SINGLE moving rover. T3 adds the hard part the charter is about — a same-class
**distractor** that crosses and briefly **occludes** the target — and closes the loop so
a *wrong* lock steers the camera off the true target (the failure compounds).

Two policies share one harness (apples-to-apples, both at 1 Hz detect / 20 Hz coast):
  • baseline — memoryless re-acq (nearest track to last lock position) → swaps to the
    distractor at the crossing, follows the wrong vehicle, true-target coverage collapses.
  • reid     — the T2 appearance-memory gate re-locks the true target after the occlusion
    and refuses the distractor in between → holds coverage.

Headline metric: true-target oracle-coverage % (frames the lock IoU vs the TRUE target's
oracle box ≥ 0.25). Phase-C negative ≈ 0% on a moving target; T3 PASS = reid ≫ 0% and
beats baseline.

  .venv-ft/bin/python experiments/run_t3.py            # deterministic kinematic self-checks
  .venv/bin/python    experiments/run_t3.py --live     # real ArduCopter SITL (pymavlink)

Dry-run uses .venv-ft (numpy); --live needs pymavlink → .venv.
"""
import argparse
import math
import os
import sys
import time

here = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(here, ".."))
sys.path.insert(0, os.path.join(here, "sitl"))

from sitl.oracle_bbox import project as oracle_project  # noqa: E402
from sitl.bytetrack import ByteTracker, _iou  # noqa: E402
from sitl.cascade_pid import CascadePID  # noqa: E402
from sitl.reid_policy import _observe, SIGMA0, GATE  # noqa: E402  (appearance model + knob)

# --- scenario ---------------------------------------------------------------
ALT_M = 10.0
CONTROL_HZ = 20
DETECT_HZ = 1.0                 # sparse anchor cadence (Phase-C regime)
DURATION_S = 60.0
TGT_START_N = 0.5               # m ahead of copter at t0
TGT_SPEED_MS = 0.25             # north (Phase-B/C)
# Persistent same-class distractor: rides ~2.2 m east of the target (a clear confuser,
# both on-screen), then VEERS east after the occlusion. A lock that grabs it gets steered
# off — the true target drifts out of frame (Phase-C "lost the moving lock", now identity).
DIS_E_OFF = 2.2                 # m east of the target, pre-veer
DIS_VEER = 0.30                 # m/s east, applied after VEER_T
VEER_T = 31.0
# Scripted occlusion of the target (motion blur / passes behind the distractor), brief.
OCC_START, OCC_END = 29.0, 31.0
IOU_GATE = 0.25                 # lock-correct / re-acq gate

DESC = {"target": 1.0, "distractor": 0.0}   # two distinct vehicles (T2 _desc_map: 0 and 1)


def _box_to_det(b):
    return {"cx": b["cx"], "cy": b["cy"], "w": b["w"], "h": b["h"]}


def _track_xyxy(tr):
    bb = tr.bbox
    return bb  # bytetrack tracks already expose cx,cy,w,h dict


def project_objs(copter_ned, anchor, yaw, elapsed):
    """World → image boxes for both vehicles, projected through the LIVE copter pose.
    Rovers live in the WORLD (anchored to the copter's START), so the copter must
    actually chase them. A persistent same-class distractor rides east of the target
    and veers off after a brief scripted occlusion — the permanence challenge.
    Returns {id: box|None}, (true_target_box, dist_world, tgt_world)."""
    tgt = (anchor[0] + TGT_START_N + TGT_SPEED_MS * elapsed, anchor[1], 0.0)
    veer = DIS_VEER * max(0.0, elapsed - VEER_T)
    dis = (tgt[0], anchor[1] + DIS_E_OFF + veer, 0.0)
    bt = oracle_project(copter_ned, tgt, 0.0, 0.0, yaw)
    bd = oracle_project(copter_ned, dis, 0.0, 0.0, yaw)
    occluded = OCC_START <= elapsed < OCC_END          # scripted target blackout
    return {"target": (None if occluded else bt), "distractor": bd}, (bt, dis, tgt)


def _obs(tracks, tid, objs, fi, snr):
    """Observe the appearance of whichever object track `tid` best covers (T2 obs)."""
    tb = tracks[tid].bbox
    oid = max((k for k, v in objs.items() if v),
              key=lambda k: _iou(tb, objs[k]), default=None)
    if oid is None or _iou(tb, objs[oid]) <= 0:
        return None
    ob = objs[oid]
    return _observe(DESC[oid], oid, ob["w"] * ob["h"], fi, snr)


def run_loop(policy, snr=8.0, ctrl=None, dry_run=True):
    """One closed-loop trial. policy ∈ {baseline, reid}. Returns metrics dict.
    dry_run integrates the velocity setpoints kinematically (no SITL); else ctrl flies it."""
    tracker = ByteTracker()
    pid = CascadePID(kp_yaw=0.0)
    copter_ned = [0.0, 0.0, -ALT_M]
    anchor = tuple(copter_ned)      # rovers are pinned to the copter's START pose
    yaw = 0.0
    locked, mem = None, None
    n, cover, occ_frames = 0, 0, 0
    last_lock_xy = None
    det_period = 1.0 / DETECT_HZ
    last_det_t = -1e9

    t_start = time.monotonic() if not dry_run else 0.0
    fi = 0
    while True:
        elapsed = (time.monotonic() - t_start) if not dry_run else fi / CONTROL_HZ
        if elapsed >= DURATION_S:
            break

        if not dry_run and ctrl is not None:
            pos = None                                   # drain to the FRESHEST pose
            while (m := ctrl.mav.recv_match(type="LOCAL_POSITION_NED", blocking=False)):
                pos = m
            if pos is not None:
                copter_ned = [pos.x, pos.y, pos.z]
                if fi == 0:
                    anchor = tuple(copter_ned)

        objs, (tgt_box, _dis_ned, _tgt_ned) = project_objs(copter_ned, anchor, yaw, elapsed)
        if objs["target"] is None and tgt_box is not None:
            occ_frames += 1  # target on-screen but suppressed by the distractor (occluded)

        # sparse detector: feed visible boxes only on anchor ticks; coast otherwise
        new_det = elapsed - last_det_t >= det_period
        dets = [_box_to_det(b) for b in objs.values() if b] if new_det else []
        if new_det:
            last_det_t = elapsed
        tracks = {t.id: t for t in tracker.update(dets)}

        # seed appearance memory the first time the target is locked at acquisition
        if mem is None and objs["target"] and tracks:
            a = objs["target"]
            cand = min(tracks, key=lambda i: (tracks[i].bbox["cx"] - a["cx"]) ** 2
                       + (tracks[i].bbox["cy"] - a["cy"]) ** 2)
            if _iou(tracks[cand].bbox, a) >= IOU_GATE:
                locked = cand
                mem = _obs(tracks, cand, objs, fi, snr)

        if locked not in tracks and mem is not None:        # re-acquire
            if policy == "baseline" and last_lock_xy is not None:
                # memoryless: nearest track to last lock position
                locked = min(tracks, key=lambda i: (tracks[i].bbox["cx"] - last_lock_xy[0]) ** 2
                             + (tracks[i].bbox["cy"] - last_lock_xy[1]) ** 2, default=None)
            else:                                            # reid: descriptor gate
                best, best_d = None, GATE
                for tid in tracks:
                    o = _obs(tracks, tid, objs, fi, snr)
                    if o is not None and abs(o - mem) < best_d:
                        best, best_d = tid, abs(o - mem)
                locked = best                                # None ⇒ refuse, keep waiting

        lock_box = tracks[locked].bbox if locked in tracks else None
        if lock_box is not None:
            last_lock_xy = (lock_box["cx"], lock_box["cy"])
            # refine memory only while genuinely on the true target
            if objs["target"] and _iou(lock_box, objs["target"]) >= IOU_GATE:
                o = _obs(tracks, locked, objs, fi, snr)
                if o is not None:
                    mem = 0.9 * mem + 0.1 * o

        # coverage = lock is on the TRUE target's (unsuppressed) box
        if tgt_box is not None and lock_box is not None and _iou(lock_box, tgt_box) >= IOU_GATE:
            cover += 1

        sp = pid.compute(lock_box)
        if dry_run:
            # integrate body velocity (yaw=0 ⇒ vx_b→N, vy_b→E)
            copter_ned[0] += sp["vx"] / CONTROL_HZ
            copter_ned[1] += sp["vy"] / CONTROL_HZ
        elif ctrl is not None:
            ctrl.send_velocity_body(sp["vx"], sp["vy"], sp["vz"], sp["yaw_rate"])
            if fi % CONTROL_HZ == 0:
                ctrl.send_heartbeat()

        n += 1
        fi += 1
        if not dry_run:
            sleep = (fi / CONTROL_HZ) - (time.monotonic() - t_start)
            if sleep > 0:
                time.sleep(sleep)

    return {"policy": policy, "snr": snr, "frames": n,
            "occlusion_frames": occ_frames,
            "true_target_coverage_pct": round(100.0 * cover / n, 1) if n else 0.0}


# ---- self-checks (deterministic kinematic dry-run) -------------------------
def _test_occlusion_actually_happens():
    """The scenario must exercise permanence: the distractor must occlude the target."""
    m = run_loop("reid", snr=8.0, dry_run=True)
    assert m["occlusion_frames"] >= 10, m   # a real crossing window, not a vacuous test
    print(f"  occlusion test PASS  ({m['occlusion_frames']} occluded frames)")


def _test_reid_beats_baseline():
    """Closed loop: memoryless swaps to the distractor at the crossing; reid holds."""
    base = run_loop("baseline", snr=8.0, dry_run=True)
    reid = run_loop("reid", snr=8.0, dry_run=True)
    assert reid["true_target_coverage_pct"] > base["true_target_coverage_pct"], (base, reid)
    assert reid["true_target_coverage_pct"] >= 80.0, reid   # holds the moving target
    print(f"  beats-baseline test PASS  (baseline={base['true_target_coverage_pct']}% "
          f"→ reid={reid['true_target_coverage_pct']}%)")


def _test_reproducible():
    assert run_loop("reid", snr=2.0, dry_run=True) == run_loop("reid", snr=2.0, dry_run=True)
    print("  reproducibility test PASS")


def _fly_one(policy):
    """One INDEPENDENT live flight (fresh boot+takeoff) for a single policy, so both
    policies see identical initial conditions — the back-to-back apples-to-apples the
    dry-run gives for free but a single shared flight cannot (the first policy leaves the
    copter chased-off and reid then starts from a degraded state)."""
    import subprocess
    from pathlib import Path
    from sitl.offboard import OffboardController

    BIN = Path.home() / "ardupilot/build/sitl/bin/arducopter"
    PARM = Path.home() / "ardupilot/Tools/autotest/default_params/copter.parm"
    workdir = Path("/tmp/sitl-t3")
    workdir.mkdir(exist_ok=True)
    subprocess.run(["pkill", "-9", "-f", "[a]rducopter"])   # clear stale SITL (frees 5760)
    time.sleep(2)
    log = open(workdir / f"sitl-{policy}.log", "w")
    proc = subprocess.Popen(
        [str(BIN), "--model", "quad", "--speedup", "1", "--defaults", str(PARM),
         "--uartA=tcp:5760", "--instance", "0",   # explicit SERIAL0 (Phase-C parity)
         "--home", "-35.363262,149.165237,584,353"],
        cwd=str(workdir), stdout=log, stderr=subprocess.STDOUT)
    try:
        time.sleep(15)
        ctrl = OffboardController("tcp:127.0.0.1:5760")
        ctrl.connect()
        ctrl.set_mode("GUIDED")          # NAV_TAKEOFF is rejected outside GUIDED
        ctrl.arm()
        ctrl.takeoff(ALT_M)
        print(f"\n[t3] live SITL — policy={policy}")
        m = run_loop(policy, snr=8.0, ctrl=ctrl, dry_run=False)
        print(f"     {m}")
        ctrl.land_and_disarm()
    finally:
        proc.kill()           # hard reap so 5760 is free before the next flight
        proc.wait()
        log.close()
    return m


def _run_live():
    """Real ArduCopter SITL, one fresh flight per policy (independent, apples-to-apples)."""
    return [_fly_one(p) for p in ("baseline", "reid")]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="run real ArduCopter SITL")
    args = ap.parse_args()
    if args.live:
        rs = _run_live()
        import json
        print(json.dumps(rs, indent=2))
    else:
        print("run_t3 self-checks (kinematic dry-run):")
        _test_reproducible()
        _test_occlusion_actually_happens()
        _test_reid_beats_baseline()
        print("all run_t3 tests passed")
