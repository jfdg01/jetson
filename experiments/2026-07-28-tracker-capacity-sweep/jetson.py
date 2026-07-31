#!/usr/bin/env python3
"""Host-side entry point for the tracker capacity sweep. The only thing that talks to the device.

Contract
--------
The repo is the source of truth; ``~/tracker-sweep`` on the Jetson is a mirror that is never
hand-edited. ``sync`` pushes ``device/`` with ``rsync --delete``, so anything created on the
device outside ``runs/`` and ``data/`` is transient by construction.

Frames are staged once (``stage``) and never re-sent. Runs are detached with ``setsid`` so a
dropped ssh connection cannot kill a multi-hour sweep; ``status`` polls and ``fetch`` pulls
results into ``raw/<run-id>/``, which is append-only.

The device never sees ground truth beyond the frame-0 init box. Scoring happens on the host,
so an arm cannot accidentally consult GT it should not have.

    ./jetson.py setup                      # build the device venv from device/requirements.txt
    ./jetson.py stage truck3 car9 ...      # push frames + spec.json
    ./jetson.py run --arms sam2_tiny --seqs truck3
    ./jetson.py status <run-id>
    ./jetson.py fetch <run-id>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "analysis"))
import uav123  # noqa: E402

HOST = "jetson"
ROOT = "/home/jfdg/tracker-sweep"
PY = f"{ROOT}/.venv/bin/python"
UV = "/home/jfdg/.local/bin/uv"
INDEX = "https://pypi.jetson-ai-lab.io/jp6/cu126"  # torch 2.8.0+cu126 aarch64 lives only here
HERE = Path(__file__).resolve().parent


def sh(cmd: str, check: bool = True, quiet: bool = False) -> str:
    """Run a command on the device. Returns stdout."""
    p = subprocess.run(["ssh", HOST, cmd], capture_output=True, text=True)
    if not quiet and p.stderr.strip():
        print(p.stderr.strip(), file=sys.stderr)
    if check and p.returncode:
        raise SystemExit(f"remote failed ({p.returncode}): {cmd}")
    return p.stdout


def rsync(src: str, dst: str, delete: bool = False) -> None:
    cmd = ["rsync", "-a", "--info=stats1"] + (["--delete"] if delete else []) + [src, dst]
    subprocess.run(cmd, check=True)


# --------------------------------------------------------------------------- commands

def cmd_setup(args) -> None:
    """Build a fresh device venv. Deliberately not shared with ~/sam2-bench."""
    sh(f"mkdir -p {ROOT}/data {ROOT}/runs")
    rsync(f"{HERE}/device/", f"{HOST}:{ROOT}/code/", delete=True)
    sh(f"{UV} venv --python 3.10 {ROOT}/.venv")
    print(sh(f"{UV} pip install --python {PY} --index-strategy unsafe-best-match "
             f"--extra-index-url {INDEX} -r {ROOT}/code/requirements.txt"))
    print(sh(f"{PY} -c \"import torch,sam2,cv2;"
             f"print('torch',torch.__version__,'cuda',torch.cuda.is_available());"
             f"print('sam2 ok, cv2',cv2.__version__)\""))


def cmd_sync(args) -> None:
    rsync(f"{HERE}/device/", f"{HOST}:{ROOT}/code/", delete=True)


def cmd_stage(args) -> None:
    """Push frames + spec.json for each sequence. Idempotent: skips what already matches."""
    cfg = uav123.config()
    for name in args.seqs:
        folder, start, end, nz, ext = cfg[name]
        files = [f"{i:0{nz}d}.{ext}" for i in range(start, end + 1)]
        box = uav123.init_box(name)
        assert box is not None, f"{name}: frame 0 has no GT, cannot initialise"
        remote = f"{ROOT}/data/{name}"
        have = sh(f"ls {remote}/frames 2>/dev/null | wc -l", check=False).strip()
        if have == str(len(files)):
            print(f"skip {name}: {have} frames already staged")
        else:
            sh(f"mkdir -p {remote}/frames")
            listing = "\n".join(files)
            subprocess.run(
                ["rsync", "-a", "--files-from=-", str(uav123.SEQ / folder), f"{HOST}:{remote}/frames/"],
                input=listing, text=True, check=True,
            )
            print(f"staged {name}: {len(files)} frames")
        spec = {"name": name, "files": files, "init_box_xyxy": box, "frames": len(files)}
        sh(f"cat > {remote}/spec.json << 'EOF'\n{json.dumps(spec)}\nEOF")


def cmd_run(args) -> None:
    run_id = args.id or time.strftime("%Y%m%dT%H%M%S")
    cmd_sync(args)
    rd = f"{ROOT}/runs/{run_id}"
    # two drivers on one run dir write the same result files and produce concatenated JSON that only
    # shows up much later, at `json.load`. It happened on `sam2-t768-control`; refuse instead.
    if sh(f"pgrep -f '[d]river.py --run-dir {rd}' > /dev/null && echo BUSY || true").strip():
        raise SystemExit(f"run {run_id} already has a driver alive; pick another --id")
    sh(f"mkdir -p {rd}")
    arms, seqs = ",".join(args.arms), ",".join(args.seqs)
    launch = (f"cd {ROOT} && setsid nohup {PY} code/driver.py --run-dir {rd} "
              f"--arms {arms} --seqs {seqs} --data {ROOT}/data "
              f"> {rd}/driver.log 2>&1 < /dev/null &")
    sh(launch)
    print(f"run-id {run_id}\n  ./jetson.py status {run_id}\n  ./jetson.py fetch {run_id}")


def cmd_status(args) -> None:
    rd = f"{ROOT}/runs/{args.id}"
    # the [d] bracket stops pgrep matching the ssh command line that carries this very pattern
    print(sh(f"tail -n {args.lines} {rd}/driver.log 2>/dev/null; echo '--- results ---'; "
             f"ls {rd}/*.json 2>/dev/null | wc -l; "
             f"pgrep -f '[d]river.py --run-dir {rd}' > /dev/null && echo RUNNING || echo NOT-RUNNING"))


def cmd_fetch(args) -> None:
    dst = HERE / "raw" / args.id
    dst.mkdir(parents=True, exist_ok=True)
    rsync(f"{HOST}:{ROOT}/runs/{args.id}/", f"{dst}/")
    print(f"-> {dst}")
    for f in sorted(dst.glob("*.json")):
        if f.name != "manifest.json":
            m = json.loads(f.read_text())["meta"]
            print(f"  {f.stem:28s} {m['frames']:5d} fr  p50 {m['ms_p50']:6.1f} ms  "
                  f"{m['fps']:5.1f} fps  lost {m['lost_frames']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup").set_defaults(fn=cmd_setup)
    sub.add_parser("sync").set_defaults(fn=cmd_sync)
    p = sub.add_parser("stage"); p.add_argument("seqs", nargs="+"); p.set_defaults(fn=cmd_stage)
    p = sub.add_parser("run")
    p.add_argument("--arms", nargs="+", required=True)
    p.add_argument("--seqs", nargs="+", required=True)
    p.add_argument("--id")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("status"); p.add_argument("id"); p.add_argument("--lines", type=int, default=15)
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("fetch"); p.add_argument("id"); p.set_defaults(fn=cmd_fetch)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
