# QUESTIONS — Part I (Exploratory)

> Device benchmark campaigns + grounding Stages 1–4. Index: [`../../QUESTIONS.md`](../../QUESTIONS.md).
> Companion docs: `RESULTS.md` (numbers) · `DECISIONS.md` (choices) · `SOURCES.md` (citations).
> RQ ids preserved from each experiment's pre-registration; `Q-*` ids formulated here for runs with no explicit RQ.

---

### Q-ub-1 — What is the upper-bound decode throughput and power draw for a useful general-purpose LLM on the Orin Nano at the 15 W ceiling?   [Part I · llama.cpp upper-bound]
- **Answer:** Llama-3.2-3B Q4_K_M sustains ~14.5 tok/s decode (570 tok/s prefill) at ~13.6 W, ~0.94 J/tok, peak 66.9 °C with no throttling — faster than human reading inside the thermal budget.
- **Why it matters:** Establishes the device ceiling against which every later constrained/optimized run is measured; confirms decode bandwidth (not prefill) is the binding edge constraint.
- **More:** `experiments/2026-06-13-llamacpp-upper-bound/`

### Q-ub-2 — Is the 25 W MAXN_SUPER power mode available on this Orin Nano 8 GB without a firmware flash?   [Part I · llama.cpp upper-bound]
- **Answer:** No — the active nvpmodel config exposes only 15 W (ID=0) and 7 W (ID=1); true 25 W Super needs a bootloader/firmware update, deferred for lack of physical access, so the "upper bound" is the 15 W-locked ceiling, not the silicon ceiling.
- **Why it matters:** Bounds every throughput/power number in the thesis to 15 W and flags that absolute-silicon claims require the deferred firmware run.
- **More:** `experiments/2026-06-13-llamacpp-upper-bound/`

### RQ1 — Does decode throughput scale inversely with model weight size (is decode bandwidth-bound)?   [Part I · 10-model capability sweep]
- **Answer:** Yes (H1 confirmed) — tg128 spans 9× from 0.5B→8B (71.52→7.75 tok/s), tracking the ~12× weight ratio; minor deviation only at the 7–8B memory-bound extreme.
- **Why it matters:** Lets model decode speed be predicted from weight bytes alone, framing all edge model-selection as a bandwidth budget.
- **More:** `experiments/2026-06-13-model-capability-sweep/`

### RQ2 — Where is the 8 GB memory wall under n_ctx=4096, and is it a cliff or a gradient?   [Part I · 10-model capability sweep]
- **Answer:** No OOM at n_ctx=4096 across all 10 models; thinnest margin Llama-3.1-8B at 5953 MB (1654 MB headroom). The actual OOM threshold (a context-scaling sub-sweep) remains open.
- **Why it matters:** Confirms 8B-class Q4_K_M models fit at moderate context, bounding deployable model size on the device.
- **More:** `experiments/2026-06-13-model-capability-sweep/`

### RQ3 — Is energy efficiency non-monotonic, peaking at the 2–3B tier?   [Part I · 10-model capability sweep]
- **Answer:** No (H4 falsified) — efficiency decreases monotonically with size; best raw efficiency is the 0.5B (11.77 tok/s·W⁻¹ net), since the ~5.2 W platform floor is too small to create the predicted peak.
- **Why it matters:** Refutes a "sweet-spot" energy argument; the real tradeoff is task-capability vs cost, not a Pareto knee.
- **More:** `experiments/2026-06-13-model-capability-sweep/`

### RQ4 — How does time-to-first-token scale with model size for short prompts?   [Part I · 10-model capability sweep]
- **Answer:** TTFT rises 38 ms (0.5B) → 204 ms (8B); all models respond under 250 ms on short prompts — within the interactive threshold.
- **Why it matters:** Shows prefill latency is not a barrier to interactive use even at 8B, isolating decode as the bottleneck.
- **More:** `experiments/2026-06-13-model-capability-sweep/`

### RQ5 — At a fixed size class, how sensitive is throughput to model architecture?   [Part I · 10-model capability sweep]
- **Answer:** Weak — weight size dominates; at 3B Qwen2.5 (14.91) ≈ Llama (14.60) within 2%, and 7–8B Mistral/Qwen/Llama fall within 8% of each other.
- **Why it matters:** Justifies choosing models by size/quality rather than architecture for throughput, simplifying the deployment search.
- **More:** `experiments/2026-06-13-model-capability-sweep/`

### RQ-G1 — At comparable footprint, does a newer Gemma generation deliver more capability per watt/joule than Gemma 2?   [Part I · Gemma-family sweep]
- **Answer:** Yes — Gemma-4 E2B is the campaign's best edge operating point: fastest decode (20.44 tg), lowest J/tok among the multi-B models (0.584), no swap, with text+vision+audio, because PLE keeps active params (~2.3B) low.
- **Why it matters:** Identifies the generational+architectural win the campaign sought and a concrete best-edge VLM candidate.
- **More:** `experiments/2026-06-14-gemma-family-sweep/`

### RQ-G2 — Does vendor QAT `q4_0` cost throughput/memory versus community `Q4_K_M` on the Orin?   [Part I · Gemma-family sweep]
- **Answer:** Not cleanly testable here — no same-model Q4_K_M-vs-QAT pair was run (HG2 deferred to a quant-sensitivity sub-study).
- **Why it matters:** Leaves cross-campaign Gemma-vs-other-family comparisons explicitly approximate (different block format, ~same bits/weight).
- **More:** `experiments/2026-06-14-gemma-family-sweep/`

### RQ-G3 — What is the true on-device footprint of Gemma-4 PLE "effective-parameter" models (spec sheets disagree ~2×)?   [Part I · Gemma-family sweep]
- **Answer:** Above the optimistic mobile spec (HG3 supported) — E2B authoritative resident = 3677 MiB (27% over Google's 2.9 GB VRAM-table figure, far above the 1.1 GB mobile claim); E4B couldn't load with `--no-mmap` (mmap essential), tegrastats lower bound 4374 MB.
- **Why it matters:** Resolves on device which spec to trust and warns the thesis not to quote the optimistic PLE numbers.
- **More:** `experiments/2026-06-14-gemma-family-sweep/`

### RQ-G4 — Where is the Gemma memory wall, and is the 12B failure a cliff or gradient?   [Part I · Gemma-family sweep]
- **Answer:** A clean cliff — Gemma-3-12B Q4 hard-OOMs at load (`cudaMalloc` 7694 MiB at -ngl 99; still fails 5168 MiB at -ngl 28); no partial-offload operating point keeps it on the Orin at reasonable quality.
- **Why it matters:** Sets the hard upper size limit for the device and documents a clean negative (thesis content) for the family.
- **More:** `experiments/2026-06-14-gemma-family-sweep/`

### RQ-G5 — Does enabling vision (mmproj) materially change load footprint and TTFT vs text-only?   [Part I · Gemma-family sweep]
- **Answer:** Deferred — text-only path was run as primary; the vision/audio modality-cost sub-run was marked secondary and not reported.
- **Why it matters:** Leaves modality overhead unquantified for the Gemma family (the VLM-feasibility campaign measures vision cost separately).
- **More:** `experiments/2026-06-14-gemma-family-sweep/`

### RQ-S1.1 — Does PaliGemma-2-3B Q4_K_M load in llama.cpp `57fe1f0` on the Orin and emit `<locXXXX>` tokens, and at what Hz/RAM?   [Part I · Stage 1 baseline]
- **Answer:** No — PaliGemma was excluded because multimodal PR #7553 is unmerged in the baseline commit `57fe1f0` (no GGUF); Hz/RAM never measured, path collapsed to SmolVLM-only.
- **Why it matters:** Removed the strongest grounding candidate, forcing the zero-shot baseline onto the weaker SmolVLM models.
- **More:** `experiments/2026-06-14-stage1-baseline/`

### RQ-S1.2 — What is the zero-shot grounding quality (parse rate, IoU) of SmolVLM-256M/500M on a 50-image RefDrone single-target sample?   [Part I · Stage 1 baseline]
- **Answer:** Near-zero — SmolVLM-256M 0% parse / 0% IoU@0.25; SmolVLM-500M 4% parse / 0% IoU@0.25 (mean IoU 0.001). Zero-shot SmolVLM cannot localize aerial targets at all.
- **Why it matters:** Triggers the "fine-tune is load-bearing" branch — Stages 2–4 become the thesis contribution, not an incremental polish.
- **More:** `experiments/2026-06-14-stage1-baseline/`

### RQ-S1.3 — Does the modular pipeline (oracle bbox → ByteTrack → cascade PID → MAVLink) hit ≥1 Hz with a stable track in SITL?   [Part I · Stage 1 baseline]
- **Answer:** Yes (PASS) — 19.99 Hz loop, 12.9 px mean error, 100% oracle coverage, 0 track losses across 3×60 s runs (well above the ≥1 Hz / <50 px bar).
- **Why it matters:** Validates the control/tracking stack independently of grounding, so any closed-loop failure can be attributed to perception.
- **More:** `experiments/2026-06-14-stage1-baseline/`

### RQ-S1.4 — Replacing the oracle with the best zero-shot VLM, how much does tracking degrade?   [Part I · Stage 1 baseline]
- **Answer:** Catastrophically (pre-registered negative) — live SmolVLM-500M gives 12.5% valid-box rate, 190.5 px mean error (vs 12.9 px oracle, +1380%), 20.7% track coverage, 19 track losses; no run completes without loss.
- **Why it matters:** Quantifies the closed-loop cost of zero-shot perception and confirms Stage 2 fine-tuning is mandatory, not optional.
- **More:** `experiments/2026-06-14-stage1-baseline/`

### Q-vlm-1 — Can a VLM running entirely on the Orin Nano meet the 0.5–2 Hz latency AND grounding quality needed for a drone command loop?   [Part I · VLM feasibility]
- **Answer:** Only borderline — SmolVLM hits 3 Hz but grounds poorly; Gemma-3-4B grounds well (correct class+colour) but is unusable at 0.10 Hz; Gemma-4-E2B is the best trade-off at 0.49 Hz / 4616 MB with only partial grounding.
- **Why it matters:** No on-device VLM cleanly satisfies both axes, motivating Part II's decomposed approach and/or fine-tuning a small VLM for structured output.
- **More:** `experiments/2026-06-14-vlm-feasibility/`

### Q-vlm-2 — End-to-end VLM (camera→VLM→command) or decomposed (grounding model + LLM intent)?   [Part I · VLM feasibility]
- **Answer:** End-to-end is viable only with Gemma-4-E2B (reasoning off) at the 0.49 Hz boundary; the marginal result motivates the Part II decomposed / fine-tuned-VLM direction.
- **Why it matters:** This architecture fork sets the entire downstream direction of the thesis (Parts II/III).
- **More:** `experiments/2026-06-14-vlm-feasibility/`

### Q-vlm-3 — What does Gemma-4's "thinking" mode cost in a VLM command loop?   [Part I · VLM feasibility]
- **Answer:** Prohibitive (negative result) — with thinking on, all 50 tokens are consumed by `reasoning_content` and no JSON is produced (E2B 0.30 Hz, E4B 0.19 Hz); `--reasoning off` is required for deployable latency.
- **Why it matters:** Documents a deployment gotcha — thinking models must be run with reasoning disabled for real-time control.
- **More:** `experiments/2026-06-14-vlm-feasibility/`

### Q-toy-1 — Do the end-to-end NL-command pipeline mechanics (parse → VLM/heuristic → drone action) actually work?   [Part I · Toy demo]
- **Answer:** Yes — TURN commands work unconditionally (<1 ms heuristic yaw lookup, no VLM); FOLLOW/ZOOM reach the Jetson, start the server, and return a response, so orchestration is sound.
- **Why it matters:** Provides a runnable thesis demo and proves the integration layer before fine-tuned grounding is available.
- **More:** `experiments/2026-06-15-toy-demo/`

### Q-toy-2 — Can zero-shot SmolVLM-500M ground specific objects in real nadir/aerial drone frames in a live demo?   [Part I · Toy demo]
- **Answer:** No (expected) — on VisDrone frames both FOLLOW and ZOOM returned `parse_ok=false` (echoed template / degenerate whole-image box), consistent with Phase A's 0% IoU@0.25.
- **Why it matters:** Honestly demonstrates the zero-shot grounding gap on the target domain — the exact motivation for Stage-2 fine-tuning.
- **More:** `experiments/2026-06-15-toy-demo/`

### RQ-S2.1 — Does LoRA fine-tuning SmolVLM-500M on RefDrone+VisDrone reach IoU@0.25 ≥ 30% on the Phase A probe?   [Part I · Stage 2 fine-tune]
- **Answer:** No (FAIL) — IoU@0.25 = 1.0% (mean IoU 0.008) via mode collapse: the model emits a near-constant center box (~[223,111,229,120]) regardless of image/caption.
- **Why it matters:** A diagnosed negative (ill-posed one-caption→many-boxes target + frozen vision + tiny objects) that reframes the Stage-3 methodological fix.
- **More:** `experiments/2026-06-15-stage2-finetune/`

### RQ-S2.2 — Does the fine-tuned model emit a valid bounding box in ≥ 50% of calls?   [Part I · Stage 2 fine-tune]
- **Answer:** Yes — parse rate 100.0%; the text backbone learned the output format perfectly, so the failure is spatial, not syntactic.
- **Why it matters:** Isolates the Stage 2 failure to localization (not the pipeline/format), pinpointing the fix needed in Stage 3.
- **More:** `experiments/2026-06-15-stage2-finetune/`

### RQ-S2.3 — Does the fine-tune survive GGUF Q8_0 quantization (ΔIoU@0.25 ≤ 5pp)?   [Part I · Stage 2 fine-tune]
- **Answer:** Not measured — deferred because gate G2 (IoU) failed; quantization parity was instead measured in Stage 3.
- **Why it matters:** Parity testing is only meaningful on a model with real skill, which Stage 2 lacked.
- **More:** `experiments/2026-06-15-stage2-finetune/`

### RQ-S2.4 — Does the fine-tuned model raise Phase C valid_rate to ≥ 30% AND px_err < 100?   [Part I · Stage 2 fine-tune]
- **Answer:** Not measured — deferred (G2 failed before closed-loop re-run).
- **Why it matters:** No usable grounding meant no point re-flying the closed loop.
- **More:** `experiments/2026-06-15-stage2-finetune/`

### RQ-S2.5 — Does inference stay within 0.5–2 Hz on the Jetson after fine-tuning?   [Part I · Stage 2 fine-tune]
- **Answer:** Not measured — deferred (G2 failed); LoRA only adds an adapter, so speed was not in question.
- **Why it matters:** Throughput was never the Stage 2 risk; accuracy was.
- **More:** `experiments/2026-06-15-stage2-finetune/`

### RQ-S3.1 — Does a well-posed objective (RefCOCO + normalized 0–1000 coords + attn+MLP LoRA) avoid the Stage 2 mode collapse?   [Part I · Stage 3 RefCOCO]
- **Answer:** Yes (PASS) — RefCOCO val IoU@0.25 = 82.5% (2.75× the 30% bar) with non-degenerate center_std = 200.5; boxes vary with input.
- **Why it matters:** Proves the machinery and objective are sound and the Stage 2 collapse was an ill-posed-target artifact, not a model-capacity wall.
- **More:** `experiments/2026-06-16-stage3-refcoco-finetune/`

### RQ-S3.2 — Does the fine-tuned model emit a valid JSON bbox in ≥ 90% of calls?   [Part I · Stage 3 RefCOCO]
- **Answer:** Yes — parse rate 100.0% on RefCOCO val.
- **Why it matters:** Confirms reliable structured output, a prerequisite for the deployment contract shared with the probe and Phase C.
- **More:** `experiments/2026-06-16-stage3-refcoco-finetune/`

### RQ-S3.3 — Does the grounding skill survive GGUF Q8_0 export (ΔIoU@0.25 ≤ 5pp)?   [Part I · Stage 3 RefCOCO]
- **Answer:** Functionally yes but gate FAIL — in-domain RefCOCO IoU@0.25 drops 85.0% (HF bf16) → 55.0% (GGUF Q8_0), a 30 pp penalty; an F16 arm attributes ~23 pp to the llama.cpp Idefics3 image-preprocessing path and only ~7 pp to Q8_0 quantization.
- **Why it matters:** The dominant edge-deployment cost for an Idefics3-family grounding VLM is runtime preprocessing divergence, not weight quantization — a key thesis finding that drives the Part-II spine reselection.
- **More:** `experiments/2026-06-16-stage3-refcoco-finetune/`

### RQ-S3.4 — How large is the COCO→aerial domain-shift penalty?   [Part I · Stage 3 RefCOCO]
- **Answer:** Large (expected negative) — IoU@0.25 collapses from 82.5% in-domain (RefCOCO) to 2.0% on aerial VisDrone (at the random-guess floor), with parse rate still 100%.
- **Why it matters:** Quantifies the domain gap that mandates aerial-specific data and sets the 2.0% floor that Stage 4 must beat.
- **More:** `experiments/2026-06-16-stage3-refcoco-finetune/`

### RQ-S3.5 — Does the fine-tuned model change Phase C Branch-2 valid_rate / px_err vs the zero-shot baseline?   [Part I · Stage 3 RefCOCO]
- **Answer:** Blocked (honest defer) — Gazebo Harmonic + ardupilot_gazebo SITL is not installed on the Jetson; also mooted because the aerial domain sits at the 2.0% floor (RQ-S3.4).
- **Why it matters:** A documented blocked result rather than a silent skip; closed-loop gains await an aerial-trained model plus an on-device SITL stack.
- **More:** `experiments/2026-06-16-stage3-refcoco-finetune/`

### RQ-S4.1 — Does a well-posed one-box subset + curriculum warm-start avoid mode collapse and reach IoU@0.25 ≥ 20% on aerial RefDrone?   [Part I · Stage 4 curriculum]
- **Answer:** Narrow miss — IoU@0.25 = 19.5% (−0.5pp), but a ~10× lift over the 2.0% RefCOCO-init floor and ~20× over Stage 2's ~1%, still rising monotonically at epoch 3 with center_std 211.5 (no collapse).
- **Why it matters:** Shows the Stage 2 root cause is eliminated and real aerial grounding skill exists on a 500M model with frozen SigLIP; the miss is a training-budget/capacity boundary — the motivation for Part II.
- **More:** `experiments/2026-06-17-stage4-refdrone-curriculum/`

### RQ-S4.2 — Does the model emit a valid JSON bbox in ≥ 90% of calls?   [Part I · Stage 4 curriculum]
- **Answer:** Yes — parse rate 100.0% on the RefDrone well-posed val set across all 3 epochs.
- **Why it matters:** Confirms format competence holds in the aerial domain, isolating the remaining gap to localization accuracy.
- **More:** `experiments/2026-06-17-stage4-refdrone-curriculum/`

### RQ-S4.3 — How much does curriculum init (from Stage 3 ft3) beat from-scratch on the same subset?   [Part I · Stage 4 curriculum]
- **Answer:** Not separately reported — the optional from-scratch control arm was gated to run only if the primary clearly passed; the primary curriculum arm reached 19.5% IoU@0.25.
- **Why it matters:** Leaves the precise warm-start contribution unquantified, though the 19.5% vs 2.0% RefCOCO-init floor strongly implies positive transfer.
- **More:** `experiments/2026-06-17-stage4-refdrone-curriculum/`
</content>
