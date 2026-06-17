"""Resolution strategy (Phase 2) — confronting the tiny-object ceiling head-on.

Aerial targets are 5–30 px and shrink to ~6–16 px (median, Phase-1 RefDrone val)
after the 512 long-edge resize through the encoder — a hard cap on achievable IoU
that Part I never addressed explicitly. v2 makes the input transform a
pre-registered, measurable variable.

**The lever for the Qwen2-VL-2B spine is the input long-edge resize size.**
Qwen2-VL has *native dynamic resolution*: feeding more pixels gives the encoder
more to work with on tiny objects, with no architecture change. And because the
contract stores boxes normalized 0–`COORD_SCALE` relative to the *original* image,
a whole-image resize keeps the ground-truth box invariant (metric-safe, no box
remapping) — so the only thing that changes across the ladder is how much detail
the encoder sees. That makes the long-edge size a clean, single-variable sweep.

This module measures Qwen2-VL-2B **base, without training** across a resolution
ladder on the Phase-1 RefDrone well-posed val set, via the Phase-0 harness, and
writes one manifest per arm. The strategy is then chosen by the numbers.

Tiling / coarse-to-fine crops are *deliberately deferred* (see DECISIONS.md Part II,
Phase 2): grounding at inference has no known target location, so tiling needs a
multi-pass run + an ambiguous cross-tile merge; the native-dynamic-resolution lever
is the cheap, single-pass intervention to exhaust first. Revisit if the ladder
plateaus below the Phase-3 gate.

Usage:
  source .venv-ft/bin/activate
  python -m grounding.resolution --model Qwen/Qwen2-VL-2B-Instruct \
      --split val --sides 512,768,1024,1280
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from typing import List

from grounding import manifest
from grounding.contract import IMAGE_SIZE
from grounding.data.refdrone import load_refdrone
from grounding.eval.harness import evaluate

# Pre-registered resolution ladder (input long edge, px). 512 is the Phase-0/1
# baseline; higher arms progressively preserve more native VisDrone pixels
# (originals are ~2000×1500, so every arm here still *downscales* — no upscaling
# artifacts, just less information thrown away).
DEFAULT_LADDER = [512, 768, 1024, 1280]


def run_ladder(model: str, split: str, sides: List[int], *, n: int = 0,
               device: str = "cuda", dtype: str = "bfloat16",
               progress_every: int = 0, note: str = "") -> List[dict]:
    """Sweep the resolution ladder on one model over RefDrone well-posed `split`.

    Loads the HF backend **once** and mutates `backend.max_side` per arm (the model
    weights are resolution-independent), evaluates each arm on the Phase-0 harness,
    and writes one `kind="eval"` manifest per arm with `phase="2"` and the arm's
    `resolution_max_side`. Returns the list of per-arm result rows for the table.
    """
    from grounding.eval.backends import HFBackend

    print(f"[phase2] loading RefDrone '{split}' well-posed val "
          f"(n={n or 'all'})...", flush=True)
    samples = load_refdrone(split, max_samples=n)
    print(f"[phase2] {len(samples)} samples; loading {model} (HF, {dtype})...",
          flush=True)

    backend = HFBackend(model, device=device, dtype=dtype)
    rows: List[dict] = []
    try:
        for side in sides:
            backend.max_side = side
            print(f"[phase2] === resolution max_side={side} ===", flush=True)
            report = evaluate(
                backend, samples,
                progress_every=progress_every or max(1, len(samples) // 10),
            )
            print(f"[phase2] side={side}  parse={report.parse_rate:.1%}  "
                  f"iou@0.25={report.iou_gate_pass_rate:.1%}  "
                  f"mean_iou={report.mean_iou:.3f}  "
                  f"center_std={report.center_std:.1f}", flush=True)

            results = asdict(report)
            cfg = {
                "phase": "2",
                "backend": "hf",
                "model": model,
                "dataset": "refdrone",
                "split": split,
                "n": len(samples),
                "resolution_max_side": side,
                "device": device,
                "dtype": dtype,
                "note": note,
            }
            m = manifest.capture("eval", cfg)
            run_dir = manifest.write(m, results=results)
            print(f"[phase2] manifest -> {run_dir}", flush=True)
            rows.append({"side": side, **results, "run_dir": str(run_dir)})
    finally:
        close = getattr(backend, "close", None)
        if callable(close):
            close()

    return rows


def _print_table(rows: List[dict]) -> None:
    print("\n[phase2] resolution ladder — RefDrone well-posed val")
    print(f"{'max_side':>9} | {'parse':>6} | {'IoU@0.25':>8} | "
          f"{'mean_iou':>8} | {'center_std':>10}")
    print("-" * 56)
    for r in rows:
        print(f"{r['side']:>9} | {r['parse_rate']:>6.1%} | "
              f"{r['iou_gate_pass_rate']:>8.1%} | {r['mean_iou']:>8.3f} | "
              f"{r['center_std']:>10.1f}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="Qwen/Qwen2-VL-2B-Instruct",
                   help="HF id or checkpoint path of the spine")
    p.add_argument("--split", default="val", help="RefDrone split")
    p.add_argument("--sides", default=",".join(str(s) for s in DEFAULT_LADDER),
                   help="comma-separated long-edge sizes to sweep")
    p.add_argument("--n", type=int, default=0,
                   help="cap on samples (0 = full well-posed split)")
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", default="bfloat16")
    p.add_argument("--note", default="")
    args = p.parse_args()

    sides = [int(s) for s in args.sides.split(",") if s.strip()]
    rows = run_ladder(args.model, args.split, sides, n=args.n,
                      device=args.device, dtype=args.dtype, note=args.note)
    _print_table(rows)


# Kept for the contract docstring / type stubs: the baseline is just the default
# IMAGE_SIZE arm of the ladder above. Higher arms are the "upscale" intervention.
BASELINE_MAX_SIDE = IMAGE_SIZE


if __name__ == "__main__":
    main()
