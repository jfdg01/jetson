"""EXP-9 G1 diagnostic: is the parity failure the ENGINE, or the INSTRUMENT?

G1 as pre-registered compares two 24-step recursive carries and asks for mean IoU >= 0.99.
That conflates two different things. A carry is stateful: step t's mask conditions step t+1's
memory, so ANY numerical difference compounds. The eager arm itself runs under
`torch.autocast(bfloat16)` -- fewer mantissa bits than the fp16 engine it is being compared
against -- so "eager" is not a precise reference, it is just a differently-rounded one.

The missing control is eager-vs-eager on the same clips. If two identical eager runs also
diverge, the 0.99 threshold was mis-specified and G1 measured carry chaos, not engine
fidelity. If eager-vs-eager is 1.0 and eager-vs-TRT is not, the engine is genuinely off and
the gate did its job.

The step-1 IoU separates the same two hypotheses from the other direction: an engine defect
shows up on the FIRST step, before any state has accumulated; chaos starts near 1.0 and decays.

    .venv-ft/bin/python diag_g1.py --out runs/exp9
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import run_exp9 as X  # noqa: E402

iou = X.iou

N_CLIPS, N_STEPS = 3, X.PARITY_STEPS


def run_arm(plan, model, trt, err_path: Path):
    """Return {clip: [box per step]} for one bridge invocation, or None if it died."""
    cmd = X.BRIDGE.format(size=X.SIZE, K=X.BASE_K, M=X.BASE_M, P=X.BASE_P, model=model,
                          trt=f" --trt-encoder {trt}" if trt else "", extra="")
    with open(err_path, "wb") as log:
        proc = subprocess.Popen(["ssh", "-T", "-q", "jetson", cmd], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=log)
        got = {}
        try:
            for e in plan:
                X._send(proc.stdin, ("init", X._rgb_jpg(e["clip"], e["seed"]), e["seed_box"]))
                assert (X._recv(proc.stdout) or {}).get("ok"), "init failed"
                boxes = []
                for st in e["steps"][:N_STEPS]:
                    X._send(proc.stdin, ("step", X._rgb_jpg(e["clip"], st["frame"])))
                    r = X._recv(proc.stdout)
                    assert r is not None, "bridge died"
                    boxes.append(r["box"])
                got[e["clip"]] = boxes
            proc.stdin.close()
            proc.wait()
        except (AssertionError, BrokenPipeError, OSError) as ex:
            proc.kill()
            print(f"  DIED: {ex} -- see {err_path.name}", flush=True)
            return None
    return got


def pair_iou(a, b):
    """Per-step IoU between two box sequences. Both-None counts as agreement."""
    return [1.0 if x is None and y is None else
            (iou(tuple(x), tuple(y)) if x and y else 0.0) for x, y in zip(a, b)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/exp9")
    a = ap.parse_args()
    out = Path(a.out)
    plan = json.loads((out / "plan.json").read_text())[:N_CLIPS]

    arms = {}
    for tag, model, trt in (("eagerA", X.TINY, ""), ("eagerB", X.TINY, ""),
                            ("trt", X.TINY, X.PLAN_T),
                            ("small_eagerA", X.SMALL, ""), ("small_eagerB", X.SMALL, ""),
                            ("small_trt", X.SMALL, X.PLAN_S)):
        print(f"[diag] {tag}", flush=True)
        arms[tag] = run_arm(plan, model, trt, out / f"diag_{tag}.err")

    rows = []
    for label, x, y in (("tiny  eager-vs-eager (CONTROL)", "eagerA", "eagerB"),
                        ("tiny  eager-vs-TRT", "eagerA", "trt"),
                        ("small eager-vs-eager (CONTROL)", "small_eagerA", "small_eagerB"),
                        ("small eager-vs-TRT", "small_eagerA", "small_trt")):
        if not arms[x] or not arms[y]:
            continue
        per_clip, step1, allious = {}, [], []
        for clip in arms[x]:
            ious = pair_iou(arms[x][clip], arms[y][clip])
            per_clip[clip] = [round(v, 3) for v in ious]
            step1.append(ious[0])
            allious += ious
        rows.append({"comparison": label, "mean_iou": round(float(np.mean(allious)), 4),
                     "min_iou": round(float(min(allious)), 4),
                     "mean_step1_iou": round(float(np.mean(step1)), 4),
                     "n_steps": len(allious), "per_clip": per_clip})
        r = rows[-1]
        print(f"  {label:34s} mean={r['mean_iou']:.4f} min={r['min_iou']:.4f} "
              f"step1={r['mean_step1_iou']:.4f}", flush=True)

    (out / "diag_g1.json").write_text(json.dumps(rows, indent=1))
    print(f"[diag] wrote {out/'diag_g1.json'}")


if __name__ == "__main__":
    main()
