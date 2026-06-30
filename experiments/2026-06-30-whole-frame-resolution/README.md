# Whole-frame resolution sweep — is more resolution worth the latency?

**Date:** 2026-06-30 · **Branch:** `test/whole-frame-resolution`
**Device:** Jetson Orin Nano 8 GB @ **15 W** (`nvpmodel -m 0` + `jetson_clocks`).
**Runtime:** llama.cpp `57fe1f0` CUDA sm_87, `llama-server`, Q8_0, ngl=99.
**Spine:** deployed terse Q8_0 (`phase3-terse100eos-1024`, 0–100 coords).
**Data:** RefDrone well-posed val, n=439. Provenance manifests in `runs/`
(git_sha `48c9cc1`, python 3.12.10, lockfile pinned).

## Question

The deployed model feeds the **whole frame** downscaled to a long edge of 512. Does
feeding it at higher resolution (less downscale) recover the tiny-aerial-target accuracy
the 512 baseline loses — and what does the prefill cost? This re-tests Part II's
max_side=1024 elbow (Phase 2) **on-device with the deployed Q8_0 terse model**, and sets
the baseline the ROI-crop lever is measured against.

Boxes are metric-safe (0–100 of the *original* frame), so whole-image resize keeps GT
invariant — the only variable is fed resolution.

## Method — `measure.py`

Run all 439 val samples through the Jetson `llama-server` at four long-edge resolutions
(`512, 1024, 1536, 1920`); record parse rate, IoU@0.25, mean IoU, and separated
prefill/decode/wall latency per arm.

```bash
source .venv-ft/bin/activate
python experiments/2026-06-30-whole-frame-resolution/measure.py \
    --sides 512,1024,1536,1920 --quant q8_0 --n 0
# self-check (geometry only, no Jetson): measure.py --selfcheck
```

`viewer.html` is a no-dep GUI for the per-sample CSV; `visualize.py` dumps the exact
fed pixels + GT/pred boxes for human eyeballing (`out/`, gitignored — regenerable, 31 MB).

**Key property baked into the sweep:** `_resize_keep_aspect` is **downscale-only**. Native
VisDrone val is ~1360px (≈70%), 960px (≈28%), 1920px (≈3%). So for ~70% of val the 1536
and 1920 arms **clamp to native** and are byte-identical — the upper arms are a built-in
duplicate/control, not new information.

## Result (Orin 15 W, Q8_0, n=439, parse 100% all arms)

| max_side | IoU@0.25 | mean IoU | prefill | decode | wall |
|---|---|---|---|---|---|
| 512  | 31.4% | 0.187 | 241 tok / 816 ms  | 12 tok / 543 ms | 1424 ms |
| **1024** | **63.1%** | 0.477 | 837 tok / 3712 ms | 12 tok / 547 ms | 4400 ms |
| 1536 | 65.4% | 0.519 | 1383 tok / 7929 ms | 12 tok / 550 ms | 8686 ms |
| 1920 | 65.1% | 0.514 | 1383 tok / 7938 ms | 12 tok / 550 ms | 8689 ms |

## Findings

1. **1024 is the knee.** 512 → 1024 **doubles** IoU@0.25 (+31.7pp) — the deployed 512
   baseline is leaving most of the model's grounding ability on the table by starving it
   of pixels on tiny targets.
2. **Beyond 1024, diminishing returns.** 1024 → 1536 buys only +2.3pp for ~2× the wall
   (4.4 s → 8.7 s). On-device, this re-confirms Part II's Phase-2 elbow.
3. **1536 ≈ 1920, a literal duplicate (negative result).** Identical prefill (1383 tok),
   identical wall (8.69 s), IoU within noise (65.4% vs 65.1%). The downscale-only clamp
   makes 1920 the same bytes as 1536 for ~70% of val — extra "resolution" beyond native
   is empty. Confirms the upper-arm control behaves as designed.
4. **Decode is flat (~12 tok, ~545 ms) across all arms** — the resolution cost is entirely
   prefill (vision tokens). This is what the ROI-crop lever attacks.

## Decision

Whole-frame **1024** is the accuracy/latency sweet spot if you must feed the whole frame,
but at **4.4 s wall it's too slow for the ~2 s anchor budget**, and pushing to 1536/1920
only adds latency. This is exactly why the deployed path uses the **ROI-crop lever**
instead (crop around the prior + upscale): it reaches **85.2% IoU@0.25 at ≈2.0 s** — beating
even the 1920 whole-frame arm (65.1% @ 8.7 s) at a fraction of the prefill. The whole-frame
sweep is the **baseline that justifies the crop**, not a deployment candidate.

**Given up:** whole-frame hi-res as a deployment mode — ruled out on latency. Kept as the
reference curve.

## Caveats / provenance notes

- **`per_sample.csv` + `summary.md` from the run itself were lost:** the `results/`→
  `experiments/` directory rename landed *mid-run*, so `measure.py`'s end-of-run CSV write
  hit a path that no longer existed and crashed (`EXIT 1`) **after** all four arms' aggregates
  were already flushed to `run.log`. `summary.md` here is regenerated from `run.log`; the
  per-sample CSV is re-runnable via the command above if needed. Lesson: don't rename a
  campaign dir while its job is running.

## Files

- `measure.py` — the sweep (+ `--selfcheck`). `visualize.py` — fed/annotated image dump.
- `viewer.html` — no-dep GUI for the per-sample CSV (needs `measure_out/per_sample.csv`,
  not present this run — see caveat).
- `measure_out/run.log` — full run trace (the authoritative numbers). `measure_out/summary.md`
  — regenerated table. `runs/` — per-arm provenance manifests.
- `out/` — visualize.py dumps (gitignored, regenerable).
