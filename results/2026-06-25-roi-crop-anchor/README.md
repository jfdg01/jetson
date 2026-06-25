# ROI-crop anchor: cut prefill (and maybe beat the resolution ceiling) — Part II/III

**Status:** pre-registered, NOT started. Sibling of `../2026-06-25-terse-output-retrain/`.
**Date opened:** 2026-06-25 · **Branch:** `v3/object-permanence`.
**Phase:** Part III latency budget (lever #2, `IDEAS.md` §VLM speed). Inference-time only —
**no retraining**, unlike the terse-output experiment.

## Why this exists (context to start cold)

Sibling experiment (terse output) attacks **decode** (~24→~10 tok, ~1.1 s → ~0.6 s) by
re-LoRA. This one attacks **prefill** (the *other* half of the 2.27 s on-Orin anchor:
prefill 1113 ms + decode 1106 ms @ 15 W, 512 long-edge). Qwen2-VL prefill is dominated by
vision-token count, which scales with image **area**. Feed the VLM a crop around the
tracker's last box instead of the full 640×480 → fewer pixels → prefill collapses.

**The two effects are coupled through one knob — the crop's output resolution.** This is a
single continuous variable, not a menu of strategies; the endpoints frame what the sweep
spans:

| Crop 256px → fed at | Prefill | Object pixel size | What it isolates |
|---|---|---|---|
| 256px (native) | ~3× cheaper (area↓) | unchanged | pure latency, no zoom |
| 384px (intermediate) | partial | partial | the tradeoff middle |
| 512px (full budget) | ~unchanged | ~2× bigger | pure accuracy, no latency |

The full-budget end is the interesting one for the thesis: feeding a tight crop at 512
directly fights **Part II's binding constraint #2** (the resolution ceiling — tiny aerial
objects 5–30 px → 2–11 px after the 512 resize). A tight ROI crop is effective
super-resolution on the target → may *buy accuracy*, not just latency. But its prefill is
~unchanged, so it gives zero on the lever's actual goal. The deploy config is whatever point
on this curve is both faster *and* ≥ 62.6% — unknown until measured, so **we sweep the knob,
we don't pre-pick a point.**

**No retraining needed.** The model already grounds on variable-resolution inputs and
returns coords normalized 0–1000 *within the image it's given*. Crop → run → map back:
`full_x = roi_x0 + (coord/1000)*roi_w` (same for y). The metric stays box-invariant exactly
like the whole-image resize in `resolution.py` (just a different crop window).

## Methodology catch — there is no tracker prior in RefDrone

RefDrone is single-frame referring; there's no "previous tracker box" to define the ROI. So
**simulate the prior by inflating the GT box by a margin M** and cropping to that square.
M proxies how loose/stale the tracker's last box is. At **M → ∞ you recover the full-frame
baseline** (62.6% current deploy) — that's the control point, free in the same sweep.

- **Primary axis — margin M** ∈ {1.5×, 2×, 3×, 5×, full-frame}. (Box width/height × M,
  clamped to frame, made square.)
- **Secondary axis — output resolution** of the crop ∈ {native(≈crop size), 384, 512} →
  spans the latency↔accuracy knob (no-zoom → full-budget super-resolution).
- **Optional axis — prior perturbation** (shift the GT box by k·box_size, scale ±20%) to
  test robustness to *real* tracker drift, not an oracle prior. Run a small grid only if the
  M×out_res curve looks promising; mark clearly as "perturbed prior."

## Research questions (pre-registered)

- **RQ1 (latency)** — On-Orin prefill ms vs crop output-pixel-count, @ 15 W. Does a 256px
  crop fed at 256 drop prefill ~3× (1113 → ~370 ms) as the area model predicts? Decode held
  ~constant (same output format) — verify it doesn't move.
- **RQ2 (accuracy / the interesting one)** — Does a tight ROI crop fed at the **512 budget**
  *raise* RefDrone IoU@0.25 above 62.6% by beating the resolution ceiling? By
  how much, as a function of M? Where's the crossover where context loss hurts the referring
  phrase ("the car next to the building" needs the building)?
- **RQ3 (the tradeoff curve)** — Plot prefill-ms vs IoU@0.25 across (M, output-res). Is there
  a point that's both faster AND at-least-as-accurate as full-frame? That's the deploy config.
- **RQ4 (robustness)** — How fast does accuracy fall as the prior is perturbed (tracker drift)?
  At what drift does the object clip out of the crop → silent failure?

## Method / controlled variables

Change the crop window + output resolution **only**. Hold base model (deployed Qwen2-VL-2B
Q8_0, Part II Phase-3 LoRA — *as-is, no retrain*), contract/prompt/parser, data
(RefDrone val), quant identical so the delta is attributable to the crop.

Concrete edits to prepare (small — extends the existing resolution sweep):
1. **Crop+map helper** next to `grounding/resolution.py`: `(image, gt_box, M, out_res) →
   (cropped_resized_image, roi_window)`; and the inverse coord map applied to `parse_bbox`
   output before `iou`. Box-invariant, metric-safe (mirror the whole-image-resize note in
   `resolution.py:12`).
2. **Eval driver** — reuse `grounding/eval/harness.py` + `run.py`; add `--roi-margin` and
   `--roi-out-res` flags that route through the helper. No new backend.
3. **Accuracy sweep first (broad + cheap)** — full (M × out_res) grid (~15 configs) on the
   HF/GGUF harness. No Orin, no training. This is where the prefill-vs-IoU curve comes from.
4. **Gate, then time the survivors** — keep only configs within −2 pp of 62.6%, then measure
   prefill/decode on the Orin for *just those 2–3* (same `llama-bench`/completion path as the
   cadence harness; reuse the T0 timing block). Don't time a config that already lost on
   accuracy — the device is the expensive step.
5. The crossover (faster AND ≥ 62.6%) picks the one deploy config. Write a run manifest.

## Deployment shape (scope honesty — already in `IDEAS.md`)

ROI-crop is **re-anchor only**: a crop can't re-find an object that left the ROI — that's the
re-acquisition / occlusion case **T2** owns. So the deploy is **two-mode**: full-frame VLM
for cold-acquire and re-acquire (when the tracker has *no* confident box), ROI-crop for
periodic re-anchor *while the lock holds*. This lever does not sacrifice re-ID; it just
doesn't help it. Sub-1-sec anchor = this (prefill ↓) + terse output (decode ↓) together.

## Gate / decision

- **Adopt ROI re-anchor** if RQ3 finds a (M, out_res) that is **prefill-faster than
  full-frame AND IoU@0.25 ≥ 62.6%** (ideally Strategy B shows it's *higher*). Pre-commit the
  band: re-anchor crop must not drop below −2 pp of full-frame at its chosen latency.
- If the only fast configs lose accuracy (context-loss dominates the super-resolution gain),
  document the negative: "prefill −X%, IoU −Y pp on tight crops — re-anchor stays full-frame."
  Thesis content either way.
- Decision goes in `DECISIONS.md` (Part II/III) with the prefill-vs-IoU curve.

## Don't forget

- Already on `v3/object-permanence` (unlike the sibling experiment).
- Same gate rule: nothing ships without `results/` + `RESULTS.md` + `DECISIONS.md` same turn.
- Accuracy sweep under `.venv-ft` via the `Makefile`; Orin latency via the device path.
  llama.cpp stays pinned. No new dependency — this is crop + resize + a coordinate transform.
