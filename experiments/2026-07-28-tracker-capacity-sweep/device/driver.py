"""Device-side driver: writes the manifest, then runs each (arm, sequence) in a fresh process.

A fresh process per arm is the only way the "no allocator / cuDNN cache contamination" row in the
README is actually true rather than aspirational. Arm order is shuffled so thermal drift over a
long sweep does not correlate with arm identity.

No manifest, no run: the environment is captured before anything is measured, so a result can
never be reported as "probably at 15 W".
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
PY = sys.executable

sys.path.insert(0, str(HERE))
import trackers  # noqa: E402


def frame_size(seq_dir: str) -> tuple[int, int]:
    """(w, h) of the staged clip, from the first jpeg's header. No decode, no cv2 import here."""
    sd = Path(seq_dir)
    first = json.loads((sd / "spec.json").read_text())["files"][0]
    with Image.open(sd / "frames" / first) as im:
        return im.size


def sh(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()


def thermals() -> dict[str, float]:
    out = {}
    for z in sorted(Path("/sys/devices/virtual/thermal").glob("thermal_zone*")):
        try:  # a zone can return EAGAIN or an empty read; it is telemetry, never fatal
            out[(z / "type").read_text().strip()] = int((z / "temp").read_text()) / 1000
        except Exception:
            pass
    return out


def rails() -> dict[str, float]:
    """INA3221 instantaneous power per rail, in watts."""
    out = {}
    for ch in sorted(Path("/sys/bus/i2c/devices/1-0040/hwmon").glob("hwmon*/in*_label")):
        try:
            name = ch.read_text().strip()
            volt = int((ch.parent / ch.name.replace("_label", "_input")).read_text())
            cur = int((ch.parent / ch.name.replace("in", "curr").replace("_label", "_input")).read_text())
            out[name] = volt * cur / 1e6
        except Exception:
            pass
    return out


def manifest(run_dir: Path, arms: list[str], seqs: list[str], seed: int, fps: float) -> dict:
    m = {
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "arms": arms, "seqs": seqs, "seed": seed, "fps_stream": fps or None,
        "nvpmodel": sh("nvpmodel -q"),
        "governor": sh("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"),
        "nproc": sh("nproc"),
        "l4t": sh("cat /etc/nv_tegra_release"),
        "meminfo": {k: v for k, v in
                    (ln.split(":", 1) for ln in Path("/proc/meminfo").read_text().splitlines())
                    if k in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")},
        "thermals_start": thermals(),
        "rails_start": rails(),
        "code_sha256": sh(f"cat {HERE}/*.py | sha256sum | cut -d' ' -f1"),
        # one freeze per interpreter actually used: a run mixing SAM2 and AsymTrack arms spans two
        # venvs, and "which packages produced this number" has to be answerable for both.
        "freeze": {py: sh(f"{py} -m pip freeze 2>/dev/null")
                        or sh(f"/home/jfdg/.local/bin/uv pip freeze --python {py} 2>/dev/null")
                   for py in sorted({trackers.REGISTRY[a].get("venv_python", PY) for a in arms})},
        "big_procs": sh("ps -eo rss,comm --sort=-rss | awk 'NR>1 && $1>102400'"),
    }
    (run_dir / "manifest.json").write_text(json.dumps(m, indent=1))
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--arms", required=True)
    ap.add_argument("--seqs", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fps", type=float, default=0.0, help="stream rate, see run_arm.py --fps")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    arms, seqs = args.arms.split(","), args.seqs.split(",")

    m = manifest(run_dir, arms, seqs, args.seed, args.fps)
    print("manifest written;", m["nvpmodel"].replace("\n", " "), "| governor", m["governor"], flush=True)
    if m["big_procs"]:
        print(f"WARNING: processes >100 MB resident:\n{m['big_procs']}", flush=True)

    # Drop the arm x clip pairs the source resolution cannot support. Recorded in the manifest so a
    # missing cell in the tables is a documented skip, not an unexplained hole.
    size = {s: frame_size(f"{args.data}/{s}") for s in seqs}
    jobs = [(a, s) for a in arms for s in seqs if not trackers.upscales(a, *size[s])]
    gated = [f"{a}__{s}" for a in arms for s in seqs if trackers.upscales(a, *size[s])]
    if gated:
        print(f"gated {len(gated)} jobs (arm larger than source): {' '.join(gated)}", flush=True)
    m = {**m, "frame_size": {s: list(v) for s, v in size.items()}, "gated": gated}
    (run_dir / "manifest.json").write_text(json.dumps(m, indent=1))

    random.Random(args.seed).shuffle(jobs)  # decorrelate thermal drift from arm identity

    for n, (a, s) in enumerate(jobs, 1):
        out = run_dir / f"{a}__{s}.json"
        if out.exists():
            print(f"[{n}/{len(jobs)}] skip {a} x {s} (done)", flush=True)
            continue
        t = time.monotonic()
        print(f"[{n}/{len(jobs)}] {a} x {s} ...", flush=True)
        # inherit stdout/stderr: capturing them hides the child's progress lines until it exits,
        # which makes a multi-hour sweep unwatchable. Everything lands in driver.log.
        # arms can declare their own interpreter: AsymTrack needs deps that would perturb the venv
        # every committed result was measured in. Default is this process's.
        p = subprocess.run(
            [trackers.REGISTRY[a].get("venv_python", PY), str(HERE / "run_arm.py"), "--arm", a,
             "--seq-dir", f"{args.data}/{s}", "--out", str(out), "--fps", str(args.fps)],
        )
        if p.returncode:
            (run_dir / f"{a}__{s}.FAIL").write_text(f"rc={p.returncode}; traceback in driver.log\n")
            print(f"  FAIL rc={p.returncode}", flush=True)
        print(f"  {time.monotonic() - t:.1f}s wall, temps {thermals().get('CPU-therm')}C", flush=True)

    (run_dir / "manifest.json").write_text(json.dumps(
        {**m, "thermals_end": thermals(), "rails_end": rails(),
         "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
