# QUESTIONS — research-question index

> Thesis-writing reference. Catalog of every research question an experiment asked.
> Full verdict (headline number + pointer to the writeup) lives in the per-Part file —
> open only the one you're working on, so a session doesn't drag all three chapters into context.
> Companion docs: **`RESULTS.md`** (numbers tables) · **`DECISIONS.md`** (what was chosen & why) · `SOURCES.md` (citations).
>
> RQ ids preserved from each experiment's pre-registration where they exist; `Q-*` ids are
> questions formulated here for runs that didn't pre-register an explicit RQ. Last built 2026-06-30.

| Part | File | Scope |
|---|---|---|
| I | [`docs/questions/part1-exploratory.md`](docs/questions/part1-exploratory.md) | device benchmarks + grounding Stages 1–4 (24 RQs) |
| II | [`docs/questions/part2-rebuild.md`](docs/questions/part2-rebuild.md) | v2 single-frame grounding, Phases 0–4 (15 RQs) |
| III | [`docs/questions/part3-permanence.md`](docs/questions/part3-permanence.md) | v3 persistent tracking, T0–T4 + latency levers (24 RQs) |

---

## Part I — Exploratory → [`docs/questions/part1-exploratory.md`](docs/questions/part1-exploratory.md)

- **Q-ub-1** — upper-bound decode throughput & power at 15 W?
- **Q-ub-2** — is 25 W MAXN_SUPER available without a firmware flash?
- **RQ1** — does decode throughput scale inversely with weight size (bandwidth-bound)?
- **RQ2** — where is the 8 GB memory wall at n_ctx=4096, cliff or gradient?
- **RQ3** — is energy efficiency non-monotonic, peaking at 2–3B?
- **RQ4** — how does TTFT scale with model size for short prompts?
- **RQ5** — at fixed size, how sensitive is throughput to architecture?
- **RQ-G1** — does a newer Gemma generation give more capability per watt?
- **RQ-G2** — does vendor QAT `q4_0` cost throughput/memory vs `Q4_K_M`?
- **RQ-G3** — true on-device footprint of Gemma-4 PLE "effective-parameter" models?
- **RQ-G4** — where is the Gemma memory wall (12B), cliff or gradient?
- **RQ-G5** — does enabling vision (mmproj) change load footprint and TTFT?
- **RQ-S1.1** — does PaliGemma-2-3B load in pinned llama.cpp and emit `<locXXXX>`?
- **RQ-S1.2** — zero-shot grounding quality of SmolVLM-256M/500M on RefDrone?
- **RQ-S1.3** — does the modular pipeline hit ≥1 Hz with a stable track in SITL?
- **RQ-S1.4** — how much does tracking degrade with zero-shot VLM vs oracle?
- **Q-vlm-1** — can an on-Orin VLM meet both latency AND grounding for drone control?
- **Q-vlm-2** — end-to-end VLM or decomposed (grounding + LLM intent)?
- **Q-vlm-3** — what does Gemma-4 "thinking" mode cost in a command loop?
- **Q-toy-1** — do the end-to-end NL-command pipeline mechanics work?
- **Q-toy-2** — can zero-shot SmolVLM-500M ground objects in real aerial frames?
- **RQ-S2.1** — does LoRA fine-tune SmolVLM-500M reach IoU@0.25 ≥ 30%?
- **RQ-S2.2** — does the fine-tune emit a valid bbox in ≥ 50% of calls?
- **RQ-S2.3** — does the fine-tune survive GGUF Q8_0 (ΔIoU ≤ 5pp)?
- **RQ-S2.4** — does the fine-tune raise Phase-C valid_rate ≥ 30% AND px_err < 100?
- **RQ-S2.5** — does inference stay 0.5–2 Hz after fine-tuning?
- **RQ-S3.1** — does a well-posed RefCOCO objective avoid the Stage-2 collapse?
- **RQ-S3.2** — does the model emit valid JSON bbox in ≥ 90% of calls?
- **RQ-S3.3** — does the skill survive GGUF Q8_0 export (ΔIoU ≤ 5pp)?
- **RQ-S3.4** — how large is the COCO→aerial domain-shift penalty?
- **RQ-S3.5** — does the fine-tune change Phase-C Branch-2 valid_rate / px_err?
- **RQ-S4.1** — does one-box subset + curriculum reach IoU@0.25 ≥ 20% on aerial?
- **RQ-S4.2** — does the model emit valid JSON bbox in ≥ 90% of calls?
- **RQ-S4.3** — how much does curriculum init beat from-scratch?

## Part II — v2 Principled Rebuild → [`docs/questions/part2-rebuild.md`](docs/questions/part2-rebuild.md)

- **RQ-0.1** — does the v2 contract path reproduce the Part-I in-domain number?
- **RQ-0.2** — how large is HF↔GGUF gap; does preprocessing dominate quant?
- **RQ-0.3** — which model spine should v2 train on?
- **Q-phase0-1** — can each candidate spine be served on the Jetson at all?
- **RQ-1.1** — is the aerial target well-posed at one box/caption; how much survives?
- **RQ-1.2** — aerial object-size distribution before/after the 512 resize?
- **RQ-1.3** — is RefCOCO (warm-start corpus) well-posed by construction?
- **RQ-2.1** — does raising input long edge raise aerial accuracy with no training?
- **RQ-2.2** — does higher resolution stay well-formed and input-dependent?
- **RQ-2.3** — where does the resolution ladder plateau?
- **RQ-3.1** — does the v2 stack clear IoU@0.25 ≥ 20% after LoRA?
- **RQ-3.2** — is the fine-tuned output non-degenerate?
- **RQ-3.3** — how much is resolution vs the fine-tune on top?
- **RQ-4.1** — does the deployed GGUF land within the fidelity budget (≥ 57.5%)?
- **RQ-4.2** — runtime/preprocessing gap on the real fine-tune: −23pp or ≈−2pp?
- **RQ-4.3** — quantization gap (F16 − Q8_0); is Q8_0 a safe half-size artifact?
- **RQ-4.4** — is the exported projector bit-equivalent to the base mmproj?

## Part III — v3 Object Permanence → [`docs/questions/part3-permanence.md`](docs/questions/part3-permanence.md)

- **Q-charter-1** — what architecture does persistent tracking on 8 GB force?
- **Q-charter-2** — is Gemma 4 the right anchor model for this hardware?
- **RQ-T0a** — deployed Qwen2-VL-2B Q8_0 anchor rate, prefill vs decode?
- **RQ-T0b** — does the ByteTrack tracker fit the 20 Hz budget with re-ID headroom?
- **RQ-T0c** — how fast does an aerial target move per frame; does it break the tracker?
- **RQ-T0d** — is the crop large enough at follow altitude for appearance re-ID?
- **RQ-T1.1** — can the temporal metric suite be pure pytest-locked functions?
- **RQ-T1.2** — does the SITL clip recorder produce a deterministic scored dataset?
- **RQ-T1.3** — do clips contain the four stressors; does the baseline fail them?
- **Q-t2-1** — does appearance-memory re-ID beat memoryless ByteTrack, at what SNR?
- **Q-t3-1** — does appearance memory hold the target in closed loop?
- **Q-t4-1** — does the integrated two-tier loop fit the T0 budget on the Orin?
- **Q-demo-1** — can the two-tier architecture run live on real aerial video?
- **RQ1 (terse)** — does terse output cut decode tokens/wall-time as predicted?
- **RQ2 (terse)** — accuracy cost of the terse re-LoRA vs JSON deploy?
- **RQ3 (terse)** — does bracket-free terse hurt parse rate / cause silent corruption?
- **RQ1 (ROI-crop)** — does a native-size ROI crop drop prefill ~3×, decode unchanged?
- **RQ2 (ROI-crop)** — does a tight crop @512 raise IoU above 62.6% (beat the ceiling)?
- **RQ3 (ROI-crop)** — is there a config both prefill-faster AND ≥ as accurate?
- **RQ4 (ROI-crop)** — how fast does accuracy fall as the crop prior drifts?
- **RQ1 (appearance-SNR)** — real appearance SNR vs nearest same-class decoy? *(not yet measured)*
- **RQ2 (appearance-SNR)** — how does SNR vary with crop area; where crosses ~1.0? *(not yet measured)*
- **RQ3 (appearance-SNR)** — over the SITL crop-size range, is SNR above 1.0? *(not yet measured)*
- **RQ4 (appearance-SNR)** — does a stdlib HSV histogram already separate target/decoy? *(not yet measured)*
- **Q-demotab-1** — does the ROI-crop prefill lever transfer to live on-device Q8_0?
- **Q-spiral-1** — is ROI re-anchor stable when cadence is pushed fast?
- **Q-srupscale-1** — does learned super-resolution beat interpolation for tiny targets? *(preliminary)*
- **Q-wholeframe-1** — accuracy-vs-latency of whole frame at higher max_side? *(in progress)*
