# DR-11 — Re-adjudicating a closed VLM grounding bake-off: fundamental limit or premature closure?

**Task:** For a UAV natural-language grounding thesis on a Jetson Orin Nano 8 GB, the incumbent grounding model — **Qwen2-VL-2B-Instruct (Q8_0)** — was selected via an **early-stopped** fine-tuning bake-off. The regime under which competitors were judged: referring-expression grounding on drone imagery,
coordinates emitted as **plain-text "terse int" strings**, **LoRA of the language subtree with the vision
tower frozen**, and a **ROI-crop + LANCZOS-upscale-to-512 px** preprocessing step. Metric: IoU@0.25.
This report asks, per competitor, whether the rejection was a *fundamental* limit or a *recipe/format
artifact*.

---

## TL;DR verdict table

| Model | Bake-off outcome | Verdict | Dominant cause | Retest priority |
|---|---|---|---|---|
| **Qwen2.5-VL-3B** | "collapsed to ~33% IoU@0.25" | **Likely premature** | **Coordinate-format mismatch** — Qwen2.5-VL emits *absolute pixels of the smart-resized image*, not the normalized 0–1000 the incumbent harness assumes | **#1 (highest value)** |
| **InternVL3-2B** | loser arm, blocked | **Likely premature** | Never fairly evaluated; format is *most* compatible with the incumbent's 0–1000 text contract, so a format killer is *unlikely* → it deserves a real run | #2 |
| **Florence-2-large** | never run (0 data) | **Premature by definition** | Strongest referring-grounding pedigree of the field, but needs a *bespoke* harness (loc-tokens, task prompts, full FT) — the shared contract cannot host it | #3 (separate arm) |
| **PaliGemma2-3B** | "ran, lost" | **Premature *if* run in the shared text-int contract; otherwise a fair loss with caveats** | `<locNNNN>` token format + fixed 224/448/896 square resize both fight the regime | #4 (verify harness first) |
| **SmolVLM2-500M** | LoRA capacity-collapse (near-constant boxes) | **Mostly fairly beaten (partly fundamental)** | Aggressive pixel-shuffle token compression + not grounding-pretrained + 500M capacity; under-tuned LoRA is a *secondary* contributor | Low (one cheap sanity retest, expect it to stay weak) |

**The single highest-value retest:** re-run **Qwen2.5-VL-3B** with coordinates expressed as **absolute
pixel values in the model's post-`smart_resize` (processed) image space**, both in the LoRA training
targets and in the decode/parse step — not normalized 0–1000. This is the cleanest, most likely artifact,
and the retest is closest architecturally to the incumbent (both are dynamic-resolution, LoRA-LM-friendly).

---

## The central diagnostic: coordinate format is *per-model* and non-interchangeable

The bake-off used **one shared output contract** — plain-text integer coordinates — for models that were
each pre-trained to speak a *different* coordinate language. Reusing the incumbent's decoder/target format
across arms is the single most likely source of unfair collapse. Here is what each model actually expects,
from primary docs:

| Model | Native grounding coordinate format | Source |
|---|---|---|
| **Qwen2-VL** (incumbent) | Plain-text ints **normalized to [0, 1000)** | Qwen2-VL paper / issue #866 [1][2] |
| **Qwen2.5-VL** | Plain-text ints as **absolute pixels of the *processed* image** (after `smart_resize` to a multiple of 28, bounded by min/max_pixels) — *not* normalized. Rescale back with `image_grid_thw`. | Qwen2.5-VL issue #866 [1]; HF discussion #13 [3]; DeepWiki grounding page [4] |
| **PaliGemma / PaliGemma2** | Special tokens `<loc0000>…<loc1023>` (1024 added vocab tokens), **order (y_min, x_min, y_max, x_max)**, normalized to 1024 bins; image force-resized to a fixed **224/448/896** square | HF PaliGemma blog [5]; PaliGemma paper [6]; ai.google.dev [7] |
| **Florence-2** | Special location tokens `<loc_0>…<loc_999>` (quantized to [0,1000], 0.1% resolution); task-specific prompts (`<CAPTION_TO_PHRASE_GROUNDING>`, `<REFERRING_EXPRESSION_SEGMENTATION>`); encoder-decoder, no plain-text ints | Florence-2 CVPR paper [8]; HF finetune-florence2 [9] |
| **InternVL 2.5 / 3.x** | `<box>[[x1, y1, x2, y2]]</box>` with coords **normalized to [0, 1000]** (modes: `real` / `norm_1000` / `norm_1`; default `norm_1000`) | InternVL docs / ms-swift best-practice [10][11] |

**Why this matters for the "33% collapse".** A coordinate-format mismatch produces *exactly* the pathology
observed: boxes land in the right ballpark for large, centered objects (so IoU@0.25 is not zero) but are
systematically mis-scaled/mis-placed, dragging the pass rate down to a third. DeepWiki's Qwen2.5-VL page
states the failure explicitly: *"If you mistakenly treat pixel coordinates as normalized values (0–1000
range), your bounding boxes would be positioned incorrectly — likely appearing far too small or in the
wrong location."* [4] That is the collapse signature.

---

## Per-model adjudication

### 1. Qwen2.5-VL-3B — **LIKELY PREMATURE.** Retest first.

**What the evidence says.** Qwen2.5-VL deliberately *changed the coordinate convention* from Qwen2-VL.
Qwen2-VL normalized boxes to [0, 1000); Qwen2.5-VL "directly uses coordinate values based on the actual
dimensions of the input images" — i.e. **absolute pixels of the processed image**, obtained from
`image_grid_thw`/`smart_resize` [1][3][4]. The incumbent is Qwen2-VL-2B, so the harness's "terse int"
target/decoder was almost certainly built for the **0–1000 normalized** convention. Feeding that same
contract to Qwen2.5-VL means:

- **At training:** the LoRA targets are 0–1000 numbers, but the model's pretrained prior emits pixels in
  the ~[0, 512]-ish processed range. The adapter must *fight* the pretrained coordinate head instead of
  refining it — slow, unstable, and prone to a mediocre compromise. Practitioners report precisely this
  when the resize/scaling contract is left implicit in LLaMA-Factory-style fine-tunes [12][13][14].
- **At inference:** even a correctly-predicting model is mis-decoded if the parser divides by 1000 (or by
  the *original* rather than *processed* dimensions). A well-documented cause of low grounding IoU on
  Qwen2.5-VL [1][3].

**This is not a weak model.** A correctly-run Qwen2.5-VL-3B is one of the strongest small grounding models
in existence: the technical report lists **RefCOCO val ≈ 89.1, RefCOCOg val ≈ 85.2** for the 3B [15]. A
model that scores ~89 on RefCOCO does not "have ~33% IoU@0.25" as a capability ceiling — the 33% is a
harness artifact with very high probability.

**The ROI-crop-to-512 interaction (extra confound).** After you LANCZOS-upscale a crop to 512, Qwen2.5-VL
still runs its own `smart_resize` (round to a multiple of 28, clamp to min/max_pixels) [16]. So the model's
output coordinates live in *that* final processed space, which is neither 512 nor the crop's pixel size nor
0–1000. If the training labels were computed in crop-pixel or normalized space, they are wrong by a
scale factor. The upscale itself is harmless-to-mildly-helpful for Qwen (dynamic resolution tolerates it),
but the **coordinate bookkeeping across crop → 512 → smart_resize must be exact**.

**The fix to retest.**
1. Express bounding-box **targets in absolute pixels of the final processed image** (the tensor Qwen
   actually sees), computed by running the *same* `smart_resize` the processor uses, then mapping GT boxes
   through crop → 512 → processed. Decode symmetrically and map back via `image_grid_thw`.
2. Keep the ROI-crop but verify the label transform end-to-end on a handful of examples (overlay predicted
   vs GT on the *original* frame) before trusting the metric.
3. Optional: also try the un-cropped native-resolution path as a control, to separate "crop helps" from
   "crop breaks my coordinate math".

**Confidence:** high that this recovers most of the gap.

### 2. InternVL3-2B — **LIKELY PREMATURE.** Never given a fair run.

It was "blocked / a loser arm" — i.e. it never received a real evaluation, so *by construction* the
rejection is not evidence of a limit. Notably, InternVL's native format — `<box>[[x1,y1,x2,y2]]</box>`
with coords **normalized to [0, 1000]** — is the **most compatible** of the field with the incumbent's
0–1000 text convention [10][11]. That cuts both ways for adjudication:

- A pure coordinate-format killer (as hypothesized for Qwen2.5-VL) is *less* likely here, because 0–1000
  matches. So if it genuinely lost after a real run, that would be closer to a fair loss.
- But it was *blocked*, not run to completion, so there is no such result. InternVL 2.5/3 are competitive
  grounding models; the model should get one honest run with (a) its `<box>…</box>` template, (b)
  `norm_1000` mode, and (c) the crop-label transform verified. Watch for the known "only predicts one box"
  quirk and multi-object prompting issues reported upstream [10] — for single-target referring grounding
  that quirk is harmless.

**The fix to retest.** Use the native `<box>[[x1,y1,x2,y2]]</box>` template in `norm_1000` mode; confirm
the crop→resize label mapping; single-target prompt. **Confidence:** medium — it may still lose, but the
current "loss" carries zero information.

### 3. Florence-2-large — **PREMATURE BY DEFINITION** (zero data). Worth running as a *separate* arm.

Florence-2 has the strongest referring-grounding pedigree of the whole field: it set zero-shot records on
RefCOCO/RefCOCO+/RefCOCOg (≈+4/+8/+8 pts over Kosmos-2) and reports RES mIoU on RefCOCO, at only **0.23B /
0.77B params** — purpose-built for grounding and demonstrably Jetson-deployable (community reports ~45 ms
inference on Orin with INT4/pruning) [8][9][17]. On the localization-first metric this thesis targets, it
is arguably the *most* on-brief competitor, so cancelling it at early-stop is the least defensible cut.

**The catch — it cannot live in the shared contract.** Florence-2 is an **encoder-decoder** that speaks
**location tokens** under **task-specific prompts**, is typically **fully fine-tuned** (not LM-only LoRA),
and does not emit plain-text ints [8][9]. So the "why it was skipped" is understandable (it doesn't fit the
Qwen-shaped harness), but that is a statement about the *harness*, not the model. It needs its own driver:
`<CAPTION_TO_PHRASE_GROUNDING>` / `<OPEN_VOCABULARY_DETECTION>` prompts, loc-token targets, full or
DoRA/LoRA-on-decoder fine-tune per the HF recipe [9].

**The fix to retest.** Build the bespoke Florence-2 arm (native loc-token format, task prompts, full FT on
0.77B — fits a single GPU). Feed it the ROI crop at its native 768 input; do *not* force plain-text ints.
**Confidence:** medium-high that it is competitive; it is the arm most likely to rival or beat the
incumbent on pure localization.

### 4. PaliGemma2-3B — **PREMATURE *if* run in the shared text-int contract; a fair (caveated) loss otherwise.**

Two independent ways the regime disadvantages PaliGemma2:

- **Format.** PaliGemma grounds *only* via `<loc0000>…<loc1023>` tokens in **(y,x,y,x)** order, normalized
  to 1024 bins, and expects the `detect {classes}` / `segment {entity}` prompt prefixes [5][6][7]. If the
  bake-off forced it into the shared **plain-text-int, (x,y,x,y)** contract, it was grounding with its
  hands tied — a fatal artifact, verdict *premature*. **First action: check what format the PaliGemma arm
  actually emitted.**
- **Resolution.** PaliGemma force-resizes every image to a **fixed 224/448/896 square** [5][7]. The
  regime's LANCZOS-upscale-to-512 is then immediately re-resized by the model (512 → 448 or → 224),
  wasting the upscale and, at the 224 checkpoint, destroying the small-target detail the crop was meant to
  preserve. PaliGemma detection quality is strongly resolution-dependent; the 448/896 checkpoints are the
  ones used for detection. So the regime is *quietly biased* against PaliGemma unless the 448/896 variant
  is used and the crop is fed at (or below) that native size.

**The fix to retest.** Use the **native `<locNNNN>` (y,x,y,x) format** + the `detect` prompt + the **448
(or 896) checkpoint**; feed the ROI crop and let PaliGemma's own resize handle it (skip the 512 upscale).
Note the deployability tension: 896 is heavy for 8 GB, so 448 is the pragmatic retest. **Confidence:**
medium — with the native format it becomes a *fair* comparison, but PaliGemma's fixed-square resize is a
genuine (not artifactual) headwind for a small-target-crop regime, so a fair loss here would be *credible*.

### 5. SmolVLM2-500M — **MOSTLY FAIRLY BEATEN** (partly fundamental, secondary recipe contribution).

The observed pathology — loss trains fine, but boxes collapse to near-constant centers (tiny `center_std`)
— has both a fundamental and a recipe reading, and here the fundamental reading dominates:

- **Architectural (fundamental).** SmolVLM uses **aggressive pixel-shuffle token compression** (its design
  motif is compressing spatial regions into very few tokens; cf. the "a bounding box is worth one token"
  discussion) [18][19][20]. Higher pixel-shuffle ratios *collapse larger spatial regions into single
  tokens, impairing tasks requiring precise localization* [21]. SmolVLM is optimized for VQA/OCR-style
  understanding, **not grounding-pretrained**, so there is no strong pretrained coordinate prior for a LoRA
  to refine. At **500M**, capacity to learn a precise coordinate regressor from a small drone dataset is
  genuinely limited.
- **Recipe (secondary).** The constant-box collapse is *also* the classic signature of an under-tuned
  adapter: rank too low, LR too low/high, too few steps, connector/vision frozen so the only trainable path
  can't move the spatial representation. A grounding LoRA on a non-grounding base often needs the
  vision-language **connector unfrozen** (not just LM), higher rank, and enough steps [22].

**Calibrated call:** the rejection of **500M** for a localization-first task is **probably correct**, and
should be recorded as *fairly beaten* — but one cheap confirmatory retest is warranted to convert "we think
it's too small" into "we showed it": unfreeze the connector, raise LoRA rank/LR, use the lowest available
pixel-shuffle / highest feed resolution, native output format, more steps. If it still collapses, the
fundamental reading is confirmed. If capacity is the true bottleneck, the **2.2B SmolVLM2** — not the
500M — would be the fair stand-in, though that erodes the 8 GB deployability edge. **Confidence:** high that
500M stays weak; the value of the retest is *evidentiary closure*, not a likely reversal.

---

## Minimal fair bake-off protocol (to settle the incumbent choice with confidence)

The failure mode of the original bake-off was a **single shared output contract** applied across models
with incompatible coordinate languages, plus a preprocessing step (crop→512) tuned to the incumbent. A
fair re-run must make each arm speak its *native* format and must verify the label transform. Minimum
spec:

1. **Per-model native coordinate contract — non-negotiable.**
   - Qwen2.5-VL: absolute pixels of the processed image (via `smart_resize`/`image_grid_thw`).
   - InternVL3: `<box>[[x1,y1,x2,y2]]</box>`, `norm_1000`.
   - PaliGemma2: `<locNNNN>` (y,x,y,x), 1024 bins, `detect` prompt, 448/896 checkpoint.
   - Florence-2: loc-tokens under `<CAPTION_TO_PHRASE_GROUNDING>` / detection prompts (bespoke driver).
   - Incumbent Qwen2-VL: 0–1000 normalized (unchanged).
2. **Label-transform verification gate.** For every arm, overlay predicted-vs-GT boxes on the *original*
   frame for ~10 samples *before* trusting any metric. A single scale/axis/order bug is exactly the
   ~33%-collapse trap. This one check would have caught the Qwen2.5-VL result.
3. **Preprocessing parity, not incumbent-tuned.** Report each model **both** with and without the ROI-crop
   (native-resolution control). For fixed-resolution models (PaliGemma) feed the crop at the model's native
   square; do not pre-upscale to a size the model will only re-resize. This exposes whether the crop→512
   step is a general win or an incumbent-specific one.
4. **Matched LoRA/compute budget, per-model tuned.** Give each arm an *equal* hyperparameter search budget
   (rank ∈ {16,32,64}, a small LR sweep, connector-frozen vs connector-unfrozen), rather than the
   incumbent's single fixed recipe — unequal tuning budget is a known model-comparison confound [23][24].
   Fix a step/epoch budget in advance and disclose it.
5. **Single metric, single threshold, single held-out drone split.** IoU@0.25 on the same frames; report
   center-error and `center_std` too (they diagnose capacity-collapse vs mis-scaling).
6. **No early-stop before the format gate.** An arm may be dropped only *after* it has passed step 2 (proven
   correct decoding) and received its step-4 budget. Dropping before that bakes in the confound (§below).

Deployability (8 GB Orin, quantized, latency) is a **second-stage tiebreaker** applied *after* fair
accuracy ranking — not a reason to skip an arm's fair-accuracy run.

---

## Methodological note: when is early-stopping a bake-off safe?

Early-stopping a comparison is safe **only once each arm has reached its own correct, converged recipe** —
i.e. you are stopping on a *fair* estimate. Stopping earlier bakes in a confound: a competitor killed before
its correct coordinate format / resolution / LoRA scope was found is indistinguishable from a bad model,
and the "loss" is uninformative [23][25]. The literature on fine-tuning variance shows outcomes swing widely
with seeds, data order, and stopping criteria, so a single under-tuned run is a weak basis for elimination
[23]; reproducibility audits repeatedly find "state-of-the-art" losers that were simply under-tuned
relative to the favored method [24]. Practical rule for this thesis: **an arm may be eliminated at
early-stop only if it (a) demonstrably decoded coordinates correctly and (b) had an equal tuning budget.**
By that rule, four of the five rejections (Qwen2.5-VL-3B, InternVL3-2B, Florence-2, PaliGemma2) do **not**
qualify as safe eliminations; only SmolVLM2-500M is close, and even it deserves the one cheap confirmatory
run.

---

## Bottom line

- **Fairly beaten:** SmolVLM2-500M (record as *fairly beaten, one confirmatory retest pending*) — partly a
  fundamental capacity/architecture limit for precise localization.
- **Likely premature — retest:** Qwen2.5-VL-3B (coordinate-format fix), InternVL3-2B (never fairly run),
  Florence-2-large (never run; needs bespoke loc-token arm), PaliGemma2-3B (verify it used native
  `<loc>` format + 448 resolution before accepting the loss).
- **Do this first:** Qwen2.5-VL-3B with absolute-pixel-of-processed-image coordinates. A model that scores
  ~89 RefCOCO does not top out at 33% IoU@0.25 — the collapse is almost certainly the format mismatch, and
  it is the arm most architecturally aligned with the incumbent, making it the cheapest high-value fix.

---

## Sources

1. Qwen2.5-VL Issue #866 — "Problem about Visual Grounding in Qwen2 and Qwen2.5" (Qwen2-VL normalized [0,1000); Qwen2.5-VL uses `smart_resize`-based absolute coords): https://github.com/QwenLM/Qwen2.5-VL/issues/866
2. Qwen2-VL paper (coordinate normalization [0,1000)): https://arxiv.org/pdf/2409.12191
3. HuggingFace — Qwen2.5-VL-7B discussion #13, "Bounding boxes coordinates" (absolute pixels relative to resized image; convert via scaling ratio): https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct/discussions/13
4. DeepWiki — Qwen2.5-VL Object Detection and Grounding (pixel space relative to processed dims via `image_grid_thw`; consequences of treating as 0–1000): https://deepwiki.com/jzh15/Qwen2.5-VL/8.2-object-detection-and-grounding
5. HuggingFace blog — PaliGemma (`<locNNNN>` tokens, 1024 bins, y,x,y,x order; fixed square resize): https://huggingface.co/blog/paligemma
6. PaliGemma paper — "A versatile 3B VLM for transfer": https://arxiv.org/html/2407.07726v1
7. Google AI for Developers — PaliGemma docs (224/448/896 fixed resolutions; detection format): https://ai.google.dev/gemma/docs/paligemma
8. Florence-2 (CVPR 2024) — loc tokens quantized to [0,1000]; RefCOCO/RefCOCO+/RefCOCOg zero-shot records: https://openaccess.thecvf.com/content/CVPR2024/papers/Xiao_Florence-2_Advancing_a_Unified_Representation_for_a_Variety_of_Vision_Tasks_CVPR_2024_paper.pdf
9. HuggingFace blog — Fine-tuning Florence-2 (task prompts, loc-token format, full fine-tune recipe): https://huggingface.co/blog/finetune-florence2
10. InternVL Issue #1103 — Visual Grounding Results (grounding behavior, single-box quirk): https://github.com/OpenGVLab/InternVL/issues/1103
11. ms-swift InternVL best-practice (bbox modes `real` / `norm_1000` / `norm_1`; `<box>[[x1,y1,x2,y2]]</box>`): https://github.com/xuyongfu/ms-swift-2.5.0.post1-241017/blob/main/docs/source_en/Multi-Modal/internvl-best-practice.md
12. Datature — How to Fine-Tune Qwen2.5-VL (coordinate/resize handling): https://datature.io/blog/how-to-fine-tune-qwen2-5-vl
13. QwenLM/Qwen3-VL Issue #1616 — grounding fine-tuning bbox scaling with LLaMA-Factory: https://github.com/QwenLM/Qwen3-VL/issues/1616
14. QwenLM/Qwen3-VL Issue #721 — grounding bias (boxes shift) after fine-tuning: https://github.com/QwenLM/Qwen3-VL/issues/721
15. Qwen2.5-VL Technical Report (arXiv 2502.13923) — RefCOCO val ≈89.1 / RefCOCOg ≈85.2 for 3B; absolute-space coordinates: https://arxiv.org/abs/2502.13923
16. DeepWiki / Qwen2.5-VL model architecture — `smart_resize`, min_pixels/max_pixels dynamic resolution: https://deepwiki.com/QwenLM/Qwen2.5-VL/2-model-architecture
17. HuggingFace — Qwen2.5-VL-3B-Instruct model card (grounding via bbox/points, JSON output): https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct
18. SmolVLM paper — "Redefining small and efficient multimodal models" (pixel-shuffle token compression, VQA focus): https://arxiv.org/html/2504.05299v1
19. HuggingFace blog — SmolVLM (architecture, fine-tuning support): https://huggingface.co/blog/smolvlm
20. HuggingFace — SmolVLM-Instruct discussion #24, "A Bounding Box is Worth One Token": https://huggingface.co/HuggingFaceTB/SmolVLM-Instruct/discussions/24
21. Pixel-shuffle localization trade-off — high shuffle ratios collapse spatial regions into single tokens, impairing precise localization (SmolVLM analysis): https://ritvik19.medium.com/papers-explained-346-smolvlm-9b4e208fa66b
22. "Empower Vision Applications with LoRA LMM" (LoRA scope/connector tuning for vision tasks): https://arxiv.org/pdf/2411.00915
23. "Fine-Tuning Pretrained Language Models: Weight Initializations, Data Orders, and Early Stopping" (variance across seeds/stopping; early-stop confounds): https://arxiv.org/pdf/2002.06305
24. "A Troubling Analysis of Reproducibility and Progress in Recommender Systems Research" (under-tuned baselines masquerading as losers): https://arxiv.org/pdf/1911.07698
25. VLM-R1 Issue #6 — baseline Qwen2.5-VL grounding performance (recipe-sensitivity of grounding numbers): https://github.com/om-ai-lab/VLM-R1/issues/6
