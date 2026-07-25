#!/usr/bin/env python3
"""
boot_sim.py -- bring up CARLA (renderer) and ArduCopter SITL (physics), detached.

The P6.x closed loop needs both servers listening: CARLA on 2000, SITL on 5760.
Launches each in its OWN session (start_new_session) so it OUTLIVES this process,
polls both ports, and exits 0 the moment both are up (or 1 on timeout). Run it in
the background: it notifies on exit, so the caller proceeds without a blocking sleep.

    .venv-ft/bin/python runners/boot_sim.py                 # both
    .venv-ft/bin/python runners/boot_sim.py --carla-only
    .venv-ft/bin/python runners/boot_sim.py --status        # just report, launch nothing

Idempotent: a server already listening is left alone. Logs to runs/sim/*.log.
Exact commands are the P6.1 as-run ones (experiments/2026-07-20-p61-carla-renderer
/README.md) -- --no-mavproxy SITL, venv-mavproxy on PATH for the waf build.
"""
import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
CARLA_DIR = HOME / "carla" / "CARLA_0.9.16"
ARDU_DIR = HOME / "ardupilot"
LOGDIR = Path("runs/sim")


def up(port, host="127.0.0.1"):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def launch(cmd, log, cwd, env=None):
    """Detached: new session so it survives this process, output to a log file."""
    LOGDIR.mkdir(parents=True, exist_ok=True)
    f = open(LOGDIR / log, "wb")
    subprocess.Popen(cmd, cwd=str(cwd), stdout=f, stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, start_new_session=True, env=env)


def launch_sitl():
    """Detached ArduCopter SITL on 5760 -- the exact P6.1 as-run command.

    Factored out of main() so a live tool (carla_debug_ui's copter pilot mode) can
    bring the physics up itself instead of re-spelling the command and drifting
    from it.
    """
    env = dict(os.environ, PATH=f"{HOME}/.venv-mavproxy/bin:{os.environ['PATH']}")
    launch([str(ARDU_DIR / "Tools/autotest/sim_vehicle.py"), "-v", "ArduCopter",
            "--no-rebuild", "--no-mavproxy", "-l", "40.4168,-3.7038,0,0"],
           "sitl.log", ARDU_DIR, env)


def wait(port, name, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if up(port):
            print(f"  {name} up on {port} ({time.time()-t0:.0f}s)")
            return True
        time.sleep(2)
    print(f"  {name} NOT up on {port} after {timeout}s", file=sys.stderr)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--carla-only", action="store_true")
    ap.add_argument("--sitl-only", action="store_true")
    ap.add_argument("--status", action="store_true", help="report only, launch nothing")
    ap.add_argument("--timeout", type=float, default=180.0)
    args = ap.parse_args()

    if args.status:
        print(f"CARLA(2000)={'up' if up(2000) else 'down'}  SITL(5760)={'up' if up(5760) else 'down'}")
        return

    want_carla = not args.sitl_only
    want_sitl = not args.carla_only

    if want_carla and not up(2000):
        print("launching CARLA...")
        launch([str(CARLA_DIR / "CarlaUE4.sh"), "-RenderOffScreen",
                "-quality-level=Epic", "-carla-rpc-port=2000"], "carla.log", CARLA_DIR)
    elif want_carla:
        print("CARLA already up on 2000")

    if want_sitl and not up(5760):
        print("launching SITL (ArduCopter, --no-mavproxy)...")
        launch_sitl()
    elif want_sitl:
        print("SITL already up on 5760")

    ok = True
    if want_carla:
        ok &= wait(2000, "CARLA", args.timeout)
    if want_sitl:
        ok &= wait(5760, "SITL", args.timeout)
    if not ok:
        print("boot FAILED -- see runs/sim/*.log", file=sys.stderr)
        sys.exit(1)
    print("both servers ready")


if __name__ == "__main__":
    main()
