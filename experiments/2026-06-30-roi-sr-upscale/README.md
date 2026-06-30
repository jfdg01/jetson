# ROI super-resolution probe — does learned SR beat classical upscale?

**Date:** 2026-06-30 · **Branch:** `test/whole-frame-resolution`
**Hardware:** dev RTX 3090 (HF bf16 backend — off the Jetson, no contention with the
resolution sweep running there in parallel).
**Software:** transformers 4.57.6, torch 2.6.0+cu124, `.venv-ft`.
**Spine:** `./runners/runs/v2/phase3-terse100eos-1024` (0–100 coords, matches the
deployed contract). **SR model:** `caidas/swin2SR-realworld-sr-x4-64-bsrgan-psnr` (x4).

## Question

The deployed ROI lever crops a window around the prior and upscales it (currently
LANCZOS) before feeding the VLM — effective super-resolution on the target. Does a
*learned* upscaler (Swin2SR, chosen for compressed-JPEG + PSNR-weight; see SOURCES.md)
actually lift grounding IoU over the best classical interpolation? If not, it's a
1.3 s/crop torch dependency for nothing.

## Method — `roi_sr_probe.py`

For each RefDrone val sample whose GT fits a 400px window: crop a fixed 400×400 oracle
window centred on GT, then bring it to the same fed resolution (**1024**) by four
methods — `native` (no upscale), `bicubic`, `lanczos`, `swin2sr` (x4 then LANCZOS-down
to 1024). **Equal fed pixels → the upscale method is the only variable.** Boxes are
metric-safe; pred is mapped crop→full via `grounding.roi.map_to_full`.

- **Confound defused:** Qwen2-VL's default `max_pixels` (~1 MP) would silently downscale
  the 1024² feed and erase the difference between methods. We bump
  `image_processor.max_pixels = feed²` so every method's pixels actually reach the model.
- **Oracle crop, not predicted:** this isolates the upscaler. It measures the *ceiling*
  the SR step can offer the lever, not end-to-end anchor accuracy.
- **n = 429/439:** 10 samples dropped because GT long edge > 300px doesn't fit a 400 crop.

```bash
source .venv-ft/bin/activate
python experiments/2026-06-30-roi-sr-upscale/roi_sr_probe.py \
    --model ./runners/runs/v2/phase3-terse100eos-1024 --side 400 --feed 1024 --n 0
# self-check (geometry only, no model): roi_sr_probe.py --selfcheck
```

## Result (crop 400, feed 1024, n=429)

| method  | parse% | IoU@0.25 | mean IoU | med SR ms | med VLM ms |
|---------|--------|----------|----------|-----------|------------|
| native  | 100.0% | 78.8%    | 0.651    | 0         | 306        |
| bicubic | 100.0% | **80.9%**| **0.695**| 0         | 635        |
| lanczos | 100.0% | 80.2%    | 0.690    | 0         | 634        |
| swin2sr | 100.0% | 78.6%    | 0.682    | **1331**  | 635        |

## Findings

1. **Upscaling the crop helps box tightness, modestly.** Going from native 400px to a
   1024 feed lifts mean IoU 0.651 → ~0.69 (tighter boxes), but IoU@0.25 barely moves
   (78.8% → ~80%). The win is sub-threshold precision, and it costs ~2× VLM time
   (306 → 635 ms) because the model ingests ~6× the pixels.
2. **Learned SR does NOT beat classical.** Swin2SR is the **worst** of the three
   upscalers on both IoU@0.25 (78.6%, *below* even native) and mean IoU (0.682 <
   bicubic 0.695), while adding **1331 ms/crop**. Its PSNR-conservative reconstruction
   buys nothing the VLM can use; if anything its smoothing slightly hurts the threshold
   hit-rate.
3. **Bicubic ≈ lanczos**, within run-to-run noise. No reason to switch the deployed
   LANCZOS to bicubic.

## Decision

**Reject Swin2SR for the ROI lever.** A learned SR upscaler costs ~1.3 s/crop — most of
the ~2 s anchor budget — and loses to free classical interpolation. Keep the deployed
**LANCZOS** upscale. What *learned* SR was supposed to add (recover real high-frequency
detail) doesn't survive contact with a 2B VLM grounding tiny targets: the model is
limited by where the box is, not by texture the SR model hallucinates back.

**Given up:** the chance that a faster/quantized SR (ONNX on Jetson) could win — but
since even the full-precision model loses on *accuracy* here, speed wouldn't rescue it.
Closed unless a sharper, detail-preserving SR (GAN/diffusion) is shown to help, which
the latency budget already rules out for deployment (see EDiffSR note in SOURCES.md).

## Files

- `roi_sr_probe.py` — the probe (+ `--selfcheck` geometry regression).
- `sr_probe_out/sr_summary.md` — the table above. `sr_probe_out/sr_per_sample.csv` —
  per-sample raw (idx, name, caption, method, crop_w/h, box_px, feed, parsed, iou, gate,
  sr_ms, vlm_ms, raw). `sr_probe_out/run.log` — full run trace.
- `sr_probe_smoke/` — n=5 smoke output from bring-up.
