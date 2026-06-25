"""Overnight ROI-crop accuracy sweep orchestrator (run under .venv-ft, from repo root).

Self-contained so it can run unattended after the terse-output training frees the
GPU. Two stages, model loaded once per stage:

  1. BROAD grid (margin × out_res) on a 150-sample subset — cheap, finds the shape.
  2. SURVIVORS at full 439: every combo within −2 pp of the full-frame (M=inf, 512)
     baseline measured in stage 1, re-run on the whole well-posed val split.

Per-combo manifests are written by `run_grid`; this also dumps a single
`sweep_summary.json` next to the README for the write-up. No device work here — the
on-Orin prefill timing for survivors is a separate step (RQ1/RQ3).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from grounding.roi import cross, run_grid

MODEL = "./runs/v2/phase3-refdrone-1024"  # Phase-3 merged deploy checkpoint, as-is
SPLIT = "val"
MARGINS = [1.5, 2.0, 3.0, 5.0, float("inf")]
RESOLUTIONS = [None, 384, 512]   # None = native (no resize)
BROAD_N = 150
BAND_PP = 0.02                   # survivor band: within −2 pp of full-frame baseline
HERE = Path(__file__).resolve().parent


def _key(r):
    return ("inf" if math.isinf(r["margin"]) else r["margin"], r["out_res"] or "native")


def main():
    broad = run_grid(MODEL, SPLIT, cross(MARGINS, RESOLUTIONS), n=BROAD_N,
                     note="roi broad grid n=150")

    base = next(r for r in broad if math.isinf(r["margin"]) and r["out_res"] == 512)
    baseline = base["iou_gate_pass_rate"]
    cutoff = baseline - BAND_PP
    print(f"\n[sweep] full-frame@512 baseline (n={BROAD_N}) = {baseline:.1%}; "
          f"survivor cutoff = {cutoff:.1%}", flush=True)

    survivors = [(r["margin"], r["out_res"]) for r in broad
                 if r["iou_gate_pass_rate"] >= cutoff
                 and not (math.isinf(r["margin"]) and r["out_res"] == 512)]
    print(f"[sweep] survivors: {[_key({'margin': m, 'out_res': rr}) for m, rr in survivors]}",
          flush=True)

    # Always re-measure the full-frame baseline at full n too, as the honest anchor.
    full_combos = [(float("inf"), 512)] + survivors
    full = run_grid(MODEL, SPLIT, full_combos, n=0,
                    note="roi survivors + baseline, full val") if survivors else []

    summary = {
        "model": MODEL, "split": SPLIT, "broad_n": BROAD_N, "band_pp": BAND_PP,
        "baseline_iou25_broad": baseline,
        "broad": [{**{k: r[k] for k in ("parse_rate", "iou_gate_pass_rate",
                                        "mean_iou", "center_std", "n", "run_dir")},
                   "key": _key(r)} for r in broad],
        "survivors_full": [{**{k: r[k] for k in ("parse_rate", "iou_gate_pass_rate",
                                                 "mean_iou", "center_std", "n", "run_dir")},
                            "key": _key(r)} for r in full],
    }
    out = HERE / "sweep_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\n[sweep] DONE — summary -> {out}", flush=True)


if __name__ == "__main__":
    main()
