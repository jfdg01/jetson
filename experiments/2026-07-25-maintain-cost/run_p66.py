"""P6.6 host orchestrator: what does MAINTAINING cost, in watts?

Runs the arm matrix over ssh, logs `tegrastats` on the device for the whole session,
and slices the power trace by each arm's device-clock window.

  .venv-ft/bin/python experiments/2026-07-25-maintain-cost/run_p66.py --smoke
  .venv-ft/bin/python experiments/2026-07-25-maintain-cost/run_p66.py \
      --arms A0,A1,B,C,D --seconds 300 --repeats 3 --out runs/p66_maintain_cost

Pre-registration, arms, gate G1 and the estimates are in this directory's README.
Every pure function here (tegrastats parsing, energy integration, arm scheduling, the
G1 rate split) is covered offline by `test_p66.py` -- this file has never been run
against the device.
"""
import argparse
import json
import random
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DEV_DIR = "~/sam2-bench"
DEV_PY = f"{DEV_DIR}/.venv/bin/python"
TS_LOG = "/tmp/p66_tegrastats.log"
TS_FMT = "%m-%d-%Y %H:%M:%S"
GROUND_CAPTION = "the white car"

# arm -> (needs llama-server, dev-script args or None for the host-driven ground arm)
ARMS = {
    "A0": (False, ["--arm", "idle"]),
    "A1": (True, ["--arm", "idle"]),
    "B": (False, ["--arm", "carry", "--image-size", "640"]),
    "C": (False, ["--arm", "carry", "--image-size", "512"]),
    "D": (True, None),
}


# --------------------------------------------------------------------------- pure

def parse_tegrastats(text, anchor_str, anchor_unix):
    """tegrastats lines -> [{t, vdd_in_mw, cpu_gpu_cv_mw, soc_mw, tj_c, ram_mb, gr3d}].

    `t` is device unix time, derived by parsing each line's local timestamp against
    `anchor_str` (the same format, captured next to `anchor_unix` on the device) and
    adding the difference -- so the host's timezone never enters.
    Takes the INSTANT mW (`5348mW/5348mW` -> 5348), not the running average: the
    average is over tegrastats' whole lifetime and would smear the arm boundaries.
    """
    # ponytail: naive local-time subtraction. A DST jump mid-run would shift an hour;
    # a 1.5 h matrix at 15 W is not going to be scheduled across 03:00.
    base = datetime.strptime(anchor_str.strip(), TS_FMT)
    out = []
    for line in text.splitlines():
        f = line.split()
        if len(f) < 4 or "VDD_IN" not in line:
            continue
        try:
            t = anchor_unix + (datetime.strptime(" ".join(f[:2]), TS_FMT) - base).total_seconds()
        except ValueError:
            continue
        rec = {"t": round(t, 3)}
        for i, tok in enumerate(f):
            nxt = f[i + 1] if i + 1 < len(f) else ""
            if tok in ("VDD_IN", "VDD_CPU_GPU_CV", "VDD_SOC") and "mW" in nxt:
                rec[tok.lower() + "_mw"] = float(nxt.split("/")[0].replace("mW", ""))
            elif tok == "RAM":
                rec["ram_mb"] = float(nxt.split("/")[0].replace("MB", ""))
            elif tok == "GR3D_FREQ":
                rec["gr3d_pct"] = float(nxt.rstrip("%"))
            elif tok.startswith("tj@"):
                rec["tj_c"] = float(tok[3:].rstrip("C"))
        if "vdd_in_mw" in rec:
            out.append(rec)
    return out


def window(samples, t0, t1):
    return [s for s in samples if t0 <= s["t"] <= t1]


def integrate(samples, key="vdd_in_mw"):
    """Trapezoid over the instant-power samples -> (mean W, joules, seconds spanned).

    Mean is energy/duration, not the sample mean, so an irregular tegrastats cadence
    (it drifts under load) does not bias it toward the densely-sampled stretches.
    """
    pts = [(s["t"], s[key]) for s in samples if key in s]
    if len(pts) < 2:
        return (pts[0][1] / 1000.0, 0.0, 0.0) if pts else (float("nan"), 0.0, 0.0)
    joules = sum((b[0] - a[0]) * (a[1] + b[1]) / 2 / 1000.0 for a, b in zip(pts, pts[1:]))
    span = pts[-1][0] - pts[0][0]
    return joules / span, joules, span


def rate_in(steps, t0, t1):
    """Achieved Hz over [t0, t1) of a carry arm, from the driver's (offset_s, ms) list."""
    n = sum(1 for off, _ in steps if t0 <= off < t1)
    return n / (t1 - t0)


def g1_split(steps, seconds, edge=60.0):
    """G1: last-60 s rate within 10% of first-60 s. Returns (first, last, delta_frac)."""
    first = rate_in(steps, 0.0, edge)
    last = rate_in(steps, seconds - edge, seconds)
    return first, last, (abs(last - first) / first if first else float("nan"))


def schedule(arms, repeats, seed=666):
    """Arm order: shuffled inside each repeat so a monotone thermal soak cannot be
    read as an arm effect. Seeded, so the run order is in the record and replayable."""
    rng = random.Random(seed)
    plan = []
    for r in range(repeats):
        block = list(arms)
        rng.shuffle(block)
        plan += [(r, a) for a in block]
    return plan


# ------------------------------------------------------------------------- device

def ssh(cmd, check=True, timeout=None):
    p = subprocess.run(["ssh", "jetson", cmd], capture_output=True, text=True,
                       timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f"ssh failed ({p.returncode}): {cmd}\n{p.stderr.strip()}")
    return p.stdout


def backend():
    """The deployed grounding runtime: q8_0 + mmproj on the Orin, served by llama-server.

    max_side is left at the backend default (`contract.IMAGE_SIZE` = 512), which is also
    what the panel runs (`carla_debug_ui.py:ORIN_GROUND_RES = 512`) -- arm D must cost the
    deployed acquire, not a hypothetical one. Same construction the rest of the repo uses
    (`run_exp4.py`, `discover_p516.py`); the no-arg call this replaced never ran.
    """
    sys.path.insert(0, str(REPO))
    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend
    return JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                         f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}", ssh_host="jetson")


def dev_now():
    return float(ssh("date +%s.%N").strip())


def dev_tj():
    """Junction temp from the last line of the live tegrastats log -- a second
    tegrastats instance would be refused while the session logger holds the device."""
    line = ssh(f"tail -1 {TS_LOG}", check=False)
    for tok in line.split():
        if tok.startswith("tj@"):
            return float(tok[3:].rstrip("C"))
    return None


def stop_llama():
    # bracket trick: a plain `pkill -f llama-server` matches the remote shell running it
    ssh("pkill -f 'llama-serv[e]r' || true", check=False)
    time.sleep(2)


def ps_snapshot():
    return ssh("ps -eo pid,pcpu,rss,comm --sort=-rss | head -6", check=False)


def cooldown(target_tj, tol=2.0, max_s=300.0):
    if target_tj is None:
        return {"skipped": "no baseline tj"}
    t0 = time.time()
    while time.time() - t0 < max_s:
        tj = dev_tj()
        if tj is None or tj <= target_tj + tol:
            return {"waited_s": round(time.time() - t0, 1), "tj_c": tj,
                    "target_c": target_tj}
        time.sleep(10)
    return {"waited_s": round(time.time() - t0, 1), "tj_c": dev_tj(),
            "target_c": target_tj, "timed_out": True}


def run_dev_arm(arm_args, seconds, tag):
    """Run maintain_cost_dev.py on the device; returns its json record."""
    out = f"/tmp/p66_{tag}.json"
    cmd = (f"cd {DEV_DIR} && {DEV_PY} -u maintain_cost_dev.py "
           + " ".join(shlex.quote(a) for a in arm_args)
           + f" --seconds {seconds} --out {out}")
    ssh(cmd, timeout=seconds + 600)
    return json.loads(ssh(f"cat {out}"))


def run_ground_arm(seconds, image, tag):
    """Arm D: repeated deployed q8_0 grounds. Host-driven via JetsonBackend (which
    boots llama-server over ssh); the compute is on the device, the image ships over
    the tunnel -- that transport is part of the cost and is noted as such in the README."""
    be = backend()
    t_start = dev_now()
    n, lat = 0, []
    try:
        end = time.time() + seconds
        while time.time() < end:
            t = time.time()
            be.generate(str(image), GROUND_CAPTION)
            lat.append(round((time.time() - t) * 1000, 1))
            n += 1
    finally:
        be.close()
    return {"arm": "ground", "n_grounds": n, "latencies_ms": lat, "steps": [],
            "n_steps": 0, "t_start_unix": t_start, "t_end_unix": dev_now(),
            "seconds": seconds}


# ---------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="A0,A1,B,C,D")
    ap.add_argument("--seconds", type=float, default=300.0)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--seed", type=int, default=666)
    ap.add_argument("--out", default="runs/p66_maintain_cost")
    ap.add_argument("--smoke", action="store_true",
                    help="A1 + B at 20 s, one repeat -- confirms the parser sees a delta")
    args = ap.parse_args()
    if args.smoke:
        args.arms, args.seconds, args.repeats = "A1,B", 20.0, 1
        args.out = "runs/p66_smoke"

    arms = args.arms.split(",")
    assert all(a in ARMS for a in arms), f"unknown arm in {arms}"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(ssh("nvpmodel -q").strip())
    print(ps_snapshot().strip())

    # one image on the host for arm D, taken from the device's own clip
    image = out / "ground_frame.jpg"
    if "D" in arms and not image.exists():
        name = ssh(f"ls {DEV_DIR}/clip/*.jpg | head -1").strip()
        subprocess.run(["scp", f"jetson:{name}", str(image)], check=True)

    ssh(f"tegrastats --stop; rm -f {TS_LOG}", check=False)
    ssh(f"nohup tegrastats --interval 500 --logfile {TS_LOG} >/dev/null 2>&1 &")
    time.sleep(3)
    anchor = ssh(f"date '+{TS_FMT}'").strip()
    anchor_unix = dev_now()
    baseline_tj = dev_tj()
    print(f"[host] tegrastats up, anchor={anchor!r} tj={baseline_tj}")

    records = []
    try:
        for rep, arm in schedule(arms, args.repeats, args.seed):
            needs_llama, dev_args = ARMS[arm]
            tag = f"{arm}_r{rep}"
            if not needs_llama:
                stop_llama()
            cool = cooldown(baseline_tj)
            ps_before = ps_snapshot()
            print(f"[host] {tag}: cooldown {cool}")
            t0 = time.time()
            if dev_args is None:
                rec = run_ground_arm(args.seconds, image, tag)
            else:
                if needs_llama:      # A1: server resident and idle, no requests
                    be = backend()
                    try:
                        rec = run_dev_arm(dev_args, args.seconds, tag)
                    finally:
                        be.close()
                else:
                    rec = run_dev_arm(dev_args, args.seconds, tag)
            rec.update(arm_id=arm, repeat=rep, tag=tag, cooldown=cool,
                       ps_before=ps_before, ps_after=ps_snapshot(),
                       host_wall_s=round(time.time() - t0, 1))
            records.append(rec)
            print(f"[host] {tag} done in {rec['host_wall_s']}s")
            if arm == "A0":
                # A0 ends idle, so its end temp IS the floor the README says to cool
                # back to within 2 C. Pre-flight tj only seeds it for the first arms.
                baseline_tj = dev_tj() or baseline_tj
    finally:
        ssh("tegrastats --stop", check=False)

    trace = ssh(f"cat {TS_LOG}")
    (out / "tegrastats.log").write_text(trace)
    samples = parse_tegrastats(trace, anchor, anchor_unix)
    print(f"[host] {len(samples)} tegrastats samples")

    for rec in records:
        # steady window: skips the carry arms' SAM2 load transient (see maintain_cost_dev
        # `t_steady_unix`). Idle arms and the ground arm set it equal to t_start_unix.
        w = window(samples, rec.get("t_steady_unix", rec["t_start_unix"]),
                   rec["t_end_unix"])
        mean_w, joules, span = integrate(w)
        rec["power"] = {
            "n_samples": len(w), "span_s": round(span, 1),
            "vdd_in_mean_w": round(mean_w, 3), "vdd_in_joules": round(joules, 1),
            "cpu_gpu_cv_mean_w": round(integrate(w, "vdd_cpu_gpu_cv_mw")[0], 3),
            "soc_mean_w": round(integrate(w, "vdd_soc_mw")[0], 3),
            "tj_start_c": w[0].get("tj_c") if w else None,
            "tj_end_c": w[-1].get("tj_c") if w else None,
            "gr3d_max_pct": max((s.get("gr3d_pct", 0) for s in w), default=None),
            "ram_max_mb": max((s.get("ram_mb", 0) for s in w), default=None),
        }
        if rec.get("steps"):
            first, last, delta = g1_split(rec["steps"], rec["seconds"])
            rec["g1"] = {"hz_first_60s": round(first, 3), "hz_last_60s": round(last, 3),
                         "delta_frac": round(delta, 4), "pass": delta <= 0.10}

    res = {"experiment": "P6.6", "arms": arms, "seconds": args.seconds,
           "repeats": args.repeats, "seed": args.seed, "anchor": anchor,
           "anchor_unix": anchor_unix, "records": records}
    (out / "results.json").write_text(json.dumps(res, indent=1) + "\n")

    for arm in arms:
        ws = [r["power"]["vdd_in_mean_w"] for r in records if r["arm_id"] == arm]
        hz = [r["n_steps"] / (r["t_end_unix"] - r.get("t_steady_unix", r["t_start_unix"]))
              for r in records if r["arm_id"] == arm and r.get("n_steps")]
        print(f"  {arm}: VDD_IN {median(ws):.2f} W (n={len(ws)})"
              + (f"  {median(hz):.2f} Hz" if hz else ""))
    print(f"[host] wrote {out / 'results.json'}")


if __name__ == "__main__":
    main()
