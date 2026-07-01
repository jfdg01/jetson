"""Per-arm driver for the VLM backbone bake-off (README is the source of truth).

Thin wrapper over the Phase-3 entry points: it loads an arm's `TrainConfig` from
`configs/<arm>.py`, runs the per-arm lr sweep through `grounding.train.trainer`,
and re-scores the best merged checkpoint with the same `grounding.eval` harness.

Stages:
  train   FT the arm for each lr in the sweep; in-loop eval picks the best epoch.
  eval    local HF whole-frame accuracy re-score of a merged checkpoint.
  all     train then eval.

Export to GGUF/TensorRT + Jetson latency are device stages — run on `ssh jetson`
via grounding/deploy (see README "Method" step 2/4); not driven from here.

Usage:
  source .venv-ft/bin/activate
  python experiments/2026-06-30-vlm-backbone-bakeoff/run_arm.py --arm internvl3-2b --stage all
  python experiments/2026-06-30-vlm-backbone-bakeoff/run_arm.py --arm internvl3-2b --stage train --lr 2e-4
  python experiments/2026-06-30-vlm-backbone-bakeoff/run_arm.py --arm internvl3-2b --dry-run
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))   # repo root, so `grounding` imports

from grounding.train import trainer  # noqa: E402

# PaliGemma's processor emits a per-call "passing both text and images" notice; over a
# multi-hour sweep that's tens of thousands of lines burying real errors. Silence it on
# both channels (transformers logger + Python warnings); our own [train]/step prints stay.
import transformers  # noqa: E402
transformers.logging.set_verbosity_error()
import warnings  # noqa: E402
warnings.filterwarnings("ignore", message=".*special image tokens.*")

LR_SWEEP = (1e-4, 2e-4, 4e-4)   # README: lr is the only swept knob


def load_arm_config(arm: str):
    path = HERE / "configs" / f"{arm}.py"
    if not path.exists():
        raise SystemExit(f"no config for arm {arm!r}: {path} missing")
    spec = importlib.util.spec_from_file_location(f"arm_{arm}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.config


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arm", required=True, help="arm name -> configs/<arm>.py")
    p.add_argument("--stage", choices=["train", "eval", "all"], default="all")
    p.add_argument("--lr", type=float, default=None,
                   help="single lr (default: sweep {1e-4,2e-4,4e-4})")
    p.add_argument("--dry-run", action="store_true",
                   help="load + 1 forward pass at the lowest lr; no training")
    p.add_argument("--eval-ckpt", default=None,
                   help="merged checkpoint to score (default: best from the sweep)")
    args = p.parse_args()

    base = load_arm_config(args.arm)
    lrs = [args.lr] if args.lr is not None else list(LR_SWEEP)

    if args.dry_run:
        trainer.train(replace(base, lr=lrs[0]), dry_run=True)
        return

    best = None  # (iou@0.25, lr, merged_path)
    if args.stage in ("train", "all"):
        for lr in lrs:
            cfg = replace(base, lr=lr,
                          output_dir=f"{base.output_dir}/lr{lr:g}")
            out = Path(cfg.output_dir)
            if (out / "DONE").exists():
                # crash-resume: this lr already finished; reuse it, don't retrain
                iou = _best_epoch_iou(out / "eval_iou.csv")
                print(f"[run_arm] lr={lr:g} already DONE ({out}); "
                      f"skip, IoU@0.25={iou:.1%}", flush=True)
                if best is None or iou > best[0]:
                    best = (iou, lr, str(out))
                continue
            print(f"\n===== arm {args.arm}  lr={lr:g}  ->  {cfg.output_dir} =====",
                  flush=True)
            merged = trainer.train(cfg)
            # in-loop per-epoch IoU is in <output_dir>/eval_iou.csv; the manifest
            # also holds eval_history. Pick the run with the best final-epoch IoU.
            iou = _best_epoch_iou(Path(cfg.output_dir) / "eval_iou.csv")
            print(f"[run_arm] lr={lr:g}  best in-loop IoU@0.25={iou:.1%}", flush=True)
            if best is None or iou > best[0]:
                best = (iou, lr, merged)
        print(f"\n[run_arm] sweep winner: lr={best[1]:g}  "
              f"IoU@0.25={best[0]:.1%}  ckpt={best[2]}", flush=True)

    if args.stage in ("eval", "all"):
        ckpt = args.eval_ckpt or (best[2] if best else None)
        if not ckpt:
            raise SystemExit("eval stage needs --eval-ckpt (no sweep result in this run)")
        print(f"\n[run_arm] whole-frame accuracy re-score: {ckpt}", flush=True)
        trainer.evaluate_only(ckpt, replace(base, eval_n=base.eval_n))


def _best_epoch_iou(csv_path: Path) -> float:
    """Best IoU@0.25 across epochs from the in-loop eval csv (early-stop pick)."""
    if not csv_path.exists():
        return 0.0
    import csv as _csv
    with open(csv_path) as f:
        rows = list(_csv.DictReader(f))
    return max((float(r["iou@0.25"]) for r in rows), default=0.0)


if __name__ == "__main__":
    main()
