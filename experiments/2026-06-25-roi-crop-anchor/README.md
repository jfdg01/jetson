# ROI-crop anchor: cut prefill (and maybe beat the resolution ceiling) — Part II/III

**Status:** ✅ COMPLETE — GATE PASS (2026-06-26). Sibling of `../2026-06-25-terse-output-retrain/`.
**Date opened:** 2026-06-25 · **Closed:** 2026-06-26 · **Branch:** `v3/object-permanence`.
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
- Same gate rule: nothing ships without `experiments/` + `RESULTS.md` + `DECISIONS.md` same turn.
- Accuracy sweep under `.venv-ft` via the `Makefile`; Orin latency via the device path.
  llama.cpp stays pinned. No new dependency — this is crop + resize + a coordinate transform.

---

# RESULTS (2026-06-26) — GATE PASS

**TL;DR.** A tight ROI crop fed at the 512 budget is **both ~2.7× cheaper on prefill AND
+22.6 pp more accurate** than the full-frame anchor — the resolution ceiling (Part II
constraint #2) was the dominant accuracy lever all along, and cropping+upscaling around the
tracker's box beats it for free (no retraining). Robust to realistic tracker drift.
**Deploy config: M=2.0, out_res=512** (re-anchor mode).

Code: `grounding/roi.py` (`--selfcheck` for the crop-math regression). Orchestrators:
`run_sweep.py` (accuracy), `time_orin.py` (device latency), `perturb.py` (drift). Machine
results: `sweep_summary.json`, `orin_timing.json`, `perturb_summary.json`. Per-combo
manifests under `runs/<id>/`.

## RQ2 — accuracy (HF bf16, 3090, RefDrone val n=439, IoU@0.25)

| margin M ↓ \ out_res → | native (no zoom) | 384 | **512** |
|---|---|---|---|
| **1.5×** | 26.0% | 79.5% | **83.8%** |
| **2.0×** | 39.4% | 82.5% | **85.2%** |
| **3.0×** | 54.4% | 78.1% | 82.7% |
| **5.0×** | 67.0% | 67.2% | 78.6% |
| **∞ (full-frame)** | **64.0%** | 10.0%¹ | 15.9% |

¹broad n=150 (dropped from the full re-run as a non-survivor). Deployed baseline (Qwen2-VL-2B
**Q8_0** @ max_side=1024, on Jetson) = **62.6%**; the HF **full-frame-native** control here
(no resize cap) = **64.0%** — they agree, so the control is sound.

**Two findings, one mechanism (the resolution ceiling):**
- **The ceiling, laid bare.** Downscaling the *full frame* to 512 long-edge collapses accuracy
  **64.0% → 15.9%** — the 1024-trained anchor's tiny aerial objects (RefDrone natives are
  1360×765 / 960×540 / 1920×1080) disintegrate at 512. This *is* Part II constraint #2, measured
  directly here for the first time.
- **Cropping reverses and beats it.** A tight crop **upscaled** to 512 is super-resolution on
  the target: **M=2.0 → 85.2%** (+22.6 pp over deploy), M=1.5 → 83.8%. The win is large and
  monotone in tightness up to M≈2 (then context loss for the referring phrase starts to bite:
  M=5 @512 = 78.6%). Native crops (no upscale) lose — confirming it's the *upscale*, not the
  crop, that buys the accuracy.

## RQ1 / RQ3 — on-Orin latency & the tradeoff (Jetson, Q8_0, 15 W, n=10 median, M=2.0)

| config | prefill ms | decode ms | prompt toks | wall ms | accuracy | prefill speedup |
|---|---|---|---|---|---|---|
| **full-frame @1024** (baseline) | 3691 | 966 | 836 | 4630 | 62.6% | 1.0× |
| **crop @512** | **1374** | 964 | 383 | 2327 | **85.2%** | **2.7×** |
| **crop @384** | **885** | 964 | 255 | 1870 | 82.5% | **4.2×** |

Prefill ≈ linear in prompt tokens (≈ image area), as predicted; decode is **unchanged**
(~964 ms — same output format, RQ1 verified). There is a point that is **both faster AND more
accurate** than full-frame — RQ3 answered, and emphatically: crop@512 wins on *both* axes
simultaneously, not a tradeoff. (full@1024 prefill is 3691 ms here vs 5111 ms in T0a because
RefDrone is 16:9 → 836 toks vs T0a's 4:3 1024×768 → 1063 toks; same linear regime.)

## RQ4 — robustness to a drifted (non-oracle) prior (HF, n=439, @512, IoU@0.25)

The sweep used a GT-centered crop. Real re-anchor uses the tracker's last box, which drifts.
Offsetting the crop center by `shift · box_size` (random direction, seeded):

| shift (·box) | M=2.0 @512 | M=3.0 @512 |
|---|---|---|
| 0 (oracle) | 85.2% | 82.7% |
| 0.25 | 82.5% | 83.1% |
| 0.5 | 83.6% | 83.6% |
| 1.0 | 74.3% | 79.7% |

**Flat (82–85%) up to half-a-box drift; even a full-box drift stays well above the 62.6%
baseline** (M=2.0 → 74.3%, the looser M=3.0 → 79.7%). The win is genuine localization, not a
center-bias artifact (a center-predicting model would collapse under shift — it doesn't). The
looser M=3.0 trades ~2 pp of peak accuracy for materially better extreme-drift tolerance.

## Gate / decision

**GATE PASS.** Adopt ROI-crop re-anchor. **Deploy config = M=2.0, out_res=512**: +22.6 pp
accuracy and 2.7× cheaper prefill vs full-frame, robust to ≤0.5·box tracker drift. For a
tighter latency budget, **M=2.0 @384** gives 4.2× prefill at 82.5% (+19.9 pp). If the tracker
is expected to drift hard, **M=3.0** is the safer margin. Deploy shape is unchanged from
pre-registration: two-mode (full-frame for cold/re-acquire, ROI-crop for re-anchor while the
lock holds). Combined with the terse-output decode lever, the sub-1s anchor is now in reach.

## Caveats / honesty

- **Accuracy is HF bf16 (3090); latency is Q8_0 (Orin).** Part II measured the HF↔Q8_0
  fidelity gap at ≈±3 pp (Q8_0 was *slightly higher*: 59.5% HF vs 62.6% Q8_0 @1024). The +20 pp
  ROI headroom dwarfs that, so the conclusion is robust — but an on-device **Q8_0 ROI accuracy**
  confirmation is the one open follow-up before flipping the deploy default.
- **Cross-experiment contamination caught.** The sibling terse experiment edited the *shared*
  `grounding/contract.py` (COORD_SCALE 1000→100, prompt "0 to 1000"→"0 to 100") after the
  accuracy sweep ran. The first RQ4 run picked up COORD_SCALE=100 and the 0–1000-emitting
  phase3 model → `/100` mapping → bogus **0.0%**. Diagnosed (the model emits 0–1000 regardless
  of the prompt), proved the sweep itself ran at 1000 (its 00:05 inf/native=64.0% is impossible
  under 100), borrowed the contract back to 1000 only for these evals (control reproduced
  84.7%), and restored the terse working copy. Exactly the shared-working-tree collision risk
  flagged at setup — logged so it doesn't recur.
