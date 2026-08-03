#!/usr/bin/env python3
"""Measure what an operator actually feels: full-speed reversal time.

The panel's copter is flown by hand with wasd, so the number that decides whether it
reads as "responsive" or "sluggish" is the time from top speed one way to top speed
the other. This is the runnable check behind sitl_fly_leg's manual-pilot tuning
(MANUAL_LEAN_DEG / MANUAL_LEAN_K / MANUAL_V_MAX and SPORT_PARAMS): change one, run
this, read the seconds. It flies the SAME send_manual_attitude the panel does.

    .venv-ft/bin/python runners/sitl_reversal_check.py [--v 6] [--budget 1.0]
    .venv-ft/bin/python runners/sitl_reversal_check.py --velocity   # the old path

`--velocity` reverses via send_velocity instead, which is what the follow loop flies
and what the manual pilot used to: it is ~2.7 s at any speed and is here so the
regression is one flag away rather than a claim in a comment.

Boots SITL if 5760 is dead (~20 s), reuses an airborne copter, and leaves it flying.
Also prints altitude sag -- the copter is supposed to hold height through the turn,
and a lean tuning that trades altitude for the seconds would pass on time and look
wrong on screen.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import boot_sim                                                   # noqa: E402
import sitl_fly_leg as fly                                        # noqa: E402

ALT = 45.0
SETTLE_S = 25.0          # generous: the spin-up is not the thing under test
CMD_HZ = 20.0            # same resend rate the panel flies at


def hold(m, vn, ve, until, timeout, trace=False, velocity=False):
    """Resend (vn, ve, 0) until until(vy) is true. Returns (seconds, sag_m).

    Sag is measured against the altitude at the FIRST sample, not against a nominal
    target: this reuses an airborne copter, so where it starts is wherever the last
    run left it, and assuming ALT reported a -45 m "sag" the first time it ran.
    """
    t0, sent, alt0, low = time.time(), 0.0, None, None
    v_meas, yaw = (0.0, 0.0, 0.0), 0.0
    while time.time() - t0 < timeout:
        now = time.time()
        if now - sent >= 1.0 / CMD_HZ:
            sent = now
            if velocity:
                fly.send_velocity(m, vn, ve, 0.0)
            else:
                fly.send_manual_attitude(m, vn, ve, 0.0, v_meas, yaw)
        msg = m.recv_match(type=["LOCAL_POSITION_NED", "ATTITUDE"],
                           blocking=True, timeout=1)
        if msg is None:
            continue
        if msg.get_type() == "ATTITUDE":
            yaw = msg.yaw
            continue
        alt, v_meas = -msg.z, (msg.vx, msg.vy, msg.vz)
        alt0 = alt if alt0 is None else alt0
        low = alt if low is None else min(low, alt)
        if trace:
            print(f"    t={now - t0:5.2f}  alt={alt:6.1f}  vn={msg.vx:6.2f} "
                  f"ve={msg.vy:6.2f} vd={msg.vz:6.2f}")
        if until(msg.vy):
            return time.time() - t0, alt0 - low
    return None, (alt0 - low) if alt0 is not None else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v", type=float, default=fly.MANUAL_V_MAX,
                    help="top speed to reverse, m/s")
    ap.add_argument("--budget", type=float, default=1.0, help="seconds allowed")
    ap.add_argument("--url", default="tcp:127.0.0.1:5760")
    ap.add_argument("--trace", action="store_true", help="print every pose sample")
    ap.add_argument("--velocity", action="store_true",
                    help="fly send_velocity instead (the follow loop's path)")
    args = ap.parse_args()

    port = int(args.url.rsplit(":", 1)[1])
    if not boot_sim.up(port):
        print(f"nothing on {port}: launching ArduCopter SITL (~20 s)")
        boot_sim.launch_sitl()
        if not boot_sim.wait(port, "SITL", 180):
            raise SystemExit("SITL did not come up -- see runs/sim/sitl.log")
    m = fly.connect(args.url)

    missed = [k for k, v in fly.set_params(m, fly.SPORT_PARAMS).items() if v is None]
    if missed:
        # a param the firmware silently dropped is indistinguishable from an applied
        # one unless you say so -- and it is exactly what a "why is it still slow" run
        # looks like from the outside
        print(f"WARNING: params not applied: {','.join(missed)}")
    print(f"params: {fly.SPORT_PARAMS}")
    print(f"takeoff to {ALT} m")
    reached = fly.arm_and_takeoff(m, ALT, note=lambda s: None, speedup=10.0)
    print(f"  takeoff settled at {reached:.1f} m")

    v, vel = args.v, args.velocity
    print(f"east at {v} m/s on the {'velocity' if vel else 'attitude'} path, settling...")
    t_up, _ = hold(m, 0.0, v, lambda vy: vy >= 0.95 * v, SETTLE_S, args.trace, vel)
    if t_up is None:
        raise SystemExit(f"never reached {v} m/s east in {SETTLE_S} s -- the airframe "
                         f"tops out at 13 m/s on lean alone, WPNAV_SPEED caps the "
                         f"velocity path")
    print(f"  reached {v} m/s in {t_up:.2f} s from hover")

    print(f"reversing to west at {v} m/s...")
    t_rev, sag = hold(m, 0.0, -v, lambda vy: vy <= -0.95 * v, SETTLE_S, args.trace, vel)
    fly.send_velocity(m, 0.0, 0.0, 0.0)
    if t_rev is None:
        raise SystemExit(f"never reversed in {SETTLE_S} s")
    print(f"\nREVERSAL {t_rev:.2f} s  (budget {args.budget:.2f})   "
          f"altitude sag {sag:.1f} m")
    if vel:
        print("(velocity path -- expected ~2.7 s at any speed, not the panel's pilot)")
        return
    assert t_rev <= args.budget, (
        f"reversal {t_rev:.2f} s over the {args.budget:.2f} s budget -- "
        f"lower sitl_fly_leg.MANUAL_V_MAX (6 -> 0.9 s, 7 -> 1.05 s, 10 -> 1.25 s); "
        f"more lean does not help, 70 deg measured no faster than 65")
    print("OK")


if __name__ == "__main__":
    main()
