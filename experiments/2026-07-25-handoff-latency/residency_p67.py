"""RQ-P6.7d, the kill condition: does keeping SAM2 resident on the Orin cost the VLM?

G3 has two halves and this script owns one of them.

  memory  -- 25 consecutive designations against ONE resident bridge, zero `rc=-9`.
             Already paid for by `handoff_p67.py`: its WARM pass puts 50 init+carry
             designations through a single bridge with `llama-server` up. Scored from
             the matrix's `results.json`, not re-run here (`--score-matrix`).
  latency -- `ground_ms` over 25 paired grounding calls must not regress by more than
             15% with SAM2 resident.

The latency half is the pass structure below: probe with no SAM2 on the board, then
probe again with an IDLE resident bridge. Idle, not stepping, on purpose -- in the
panel's caption path the operator's phrase is grounded BEFORE the carry starts, so the
contention the deployed system actually meets is a resident-but-quiet tracker. A
stepping bridge is a different (and easier to make look bad) question.

  .venv-ft/bin/python experiments/2026-07-25-handoff-latency/residency_p67.py \
      --out runs/p67/residency
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from handoff_p67 import BANK, CARRY_SIZE, Bridge, Clip  # noqa: E402

PROBE = Path(__file__).resolve().parent / "ground_probe.py"
REMOTE_PROBE = "~/sam2-bench/ground_probe.py"
PROBE_CMD = ("cd ~/sam2-bench && ./.venv/bin/python ground_probe.py "
             "--n {n} --max-side {max_side} --tag {tag}")
REGRESS_LIMIT = 0.15   # G3


def probe(n, max_side, tag):
    """Run the on-device probe; return its parsed JSON (stdout is JSON only)."""
    r = subprocess.run(["ssh", "-T", "-q", "jetson",
                        PROBE_CMD.format(n=n, max_side=max_side, tag=tag)],
                       capture_output=True, timeout=1800)
    if r.returncode != 0:
        raise SystemExit(f"probe {tag} rc={r.returncode}: {r.stderr.decode()[-800:]}")
    return json.loads(r.stdout.decode())


def score_matrix(path: Path) -> dict:
    """The memory half, read out of the matrix: one bridge, every WARM designation."""
    cells = json.loads(path.read_text())["cells"]
    warm = [c for c in cells if c["arm"] == "WARM"]
    killed = [c for c in warm if c.get("rc") == -9]
    return {"warm_designations": len(warm), "rc_minus9": len(killed),
            "nonzero_rc": [c["rc"] for c in warm if c.get("rc") not in (None, 0)],
            "pass": len(warm) >= 25 and not killed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--max-side", type=int, default=1024)
    ap.add_argument("--matrix", type=Path, default=Path("runs/p67/matrix/results.json"))
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()

    if args.selfcheck:
        assert PROBE.exists(), PROBE
        assert "--tag baseline" in PROBE_CMD.format(n=1, max_side=1, tag="baseline")
        fake = {"cells": [{"arm": "WARM", "rc": None} for _ in range(50)]}
        p = Path("/tmp/_p67_sc.json")
        p.write_text(json.dumps(fake))
        assert score_matrix(p)["pass"] is True
        fake["cells"][3]["rc"] = -9
        p.write_text(json.dumps(fake))
        s = score_matrix(p)
        assert s["pass"] is False and s["rc_minus9"] == 1, s
        p.unlink()
        print("selfcheck OK")
        return
    if not args.out:
        ap.error("--out is required unless --selfcheck")
    args.out.mkdir(parents=True, exist_ok=True)

    subprocess.run(["scp", "-q", str(PROBE), f"jetson:{REMOTE_PROBE}"], check=True)

    print("[1/3] baseline: no SAM2 on the board")
    base = probe(args.n, args.max_side, "baseline")
    print(f"    median {base['median_wall_ms']} ms, MemAvailable floor "
          f"{base['mem_available_mb_min']} MB")

    print("[2/3] starting a resident bridge and leaving it idle")
    br = Bridge(errlog=args.out / "bridge.err")
    br.wait_ready()
    clip = Clip("clip00", 0, 8)              # any frame: the bridge just has to hold state
    br.init(clip.frames[0], clip.target_box(0) or [100, 100, 200, 200])
    br.step(clip.frames[4])                  # one forward, then quiet -- the panel's shape
    time.sleep(2.0)
    print(f"    bridge up in {br.t_ready - br.t_spawn:.2f}s (load {br.load_s}s), idle")

    print("[3/3] resident: same 25 images, SAM2 holding its context")
    res = probe(args.n, args.max_side, "resident")
    br.close()
    print(f"    median {res['median_wall_ms']} ms, MemAvailable floor "
          f"{res['mem_available_mb_min']} MB")

    a = np.array([r["wall_ms"] for r in base["rows"]])
    b = np.array([r["wall_ms"] for r in res["rows"]])
    ratio = float(np.median(b) / np.median(a))
    mem = score_matrix(args.matrix) if args.matrix.exists() else {"pass": None,
                                                                 "note": "matrix missing"}
    out = {
        "baseline": base, "resident": res,
        "median_baseline_ms": float(np.median(a)), "median_resident_ms": float(np.median(b)),
        "ratio": round(ratio, 4), "regress_limit": REGRESS_LIMIT,
        "latency_pass": ratio <= 1.0 + REGRESS_LIMIT,
        "memory": mem,
        "G3_pass": bool(ratio <= 1.0 + REGRESS_LIMIT and mem.get("pass")),
    }
    (args.out / "results.json").write_text(json.dumps(out, indent=1))
    print(f"\nground_ms {out['median_baseline_ms']:.0f} -> {out['median_resident_ms']:.0f} "
          f"(x{ratio:.3f}, limit x{1 + REGRESS_LIMIT:.2f}) "
          f"latency_pass={out['latency_pass']}")
    print(f"memory: {mem}")
    print(f"G3 = {'PASS' if out['G3_pass'] else 'FAIL'}")


if __name__ == "__main__":
    main()
