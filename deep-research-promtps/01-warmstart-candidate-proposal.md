# DR-01 — High-recall always-on candidate proposal for warm-start acquisition on an 8 GB edge device

## Context (assume no prior knowledge)
I run a natural-language-driven target-acquisition pipeline for a UAV on an **NVIDIA Jetson
Orin Nano 8 GB** (Ampere, ~1024 CUDA cores, unified 8 GB shared CPU/GPU RAM, power capped at
15 W with `jetson_clocks`; there is no MAXN mode on this board). The pipeline:
operator natural-language phrase → visual grounding (a 2B vision-language model,
Qwen2-VL-2B-Instruct, Q8_0 GGUF via llama.cpp, ROI-crop + LANCZOS upscale to 512 px,
~1.4 s prefill) → memory-carry tracking (SAM2.1-hiera-tiny, TensorRT fp16 encoder, ~6 Hz,
box-prompt → per-frame mask propagation) → follow controller (MAVLink / ArduPilot).

**The new architecture ("warm-start"):** the operator's command arrives *mid-flight*, seconds
after video starts streaming — the pre-prompt window is free compute. So instead of a cold
grounding pass under time pressure, I continuously propose boxes+labels of salient objects
during the idle window, hand each to SAM2 as a live track, and at command time I just *select*
the track that matches the phrase. This works: on a 25-clip UAV123 replay, warm-start lands
21/25 vs 5/25 for cold acquire.

**The binder now:** the warm-start seed is **detection-bound** — my idle-window proposer
(currently the same VLM asked for salient boxes) misses small or deformable targets, so those
tracks never exist to be selected. I need a *high-recall*, class-agnostic or open-vocabulary
**candidate proposer** that runs continuously and cheaply, co-resident with the VLM + SAM2, and
whose recall (not precision — the VLM selects later) is the figure of merit.

## Research question
What are the best-available (2024–2026) **class-agnostic / open-vocabulary object *proposal***
methods that could run continuously on a Jetson Orin Nano 8 GB **co-resident** with a 2B VLM and
SAM2, prioritising recall of *all* salient objects (including small/distant/deformable ones) in
aerial video, at a few Hz within a ~2–3 GB memory / few-watt slice?

## Sub-questions to cover
- Open-vocabulary detectors (e.g. YOLO-World, Grounding DINO / DINO-X, OWLv2, T-Rex, MM-Grounding-DINO)
  and **class-agnostic proposal** nets — measured latency/memory when quantized (INT8/fp16) and
  deployed via TensorRT on Orin-class hardware. Which have real edge deployments?
- Recall-oriented operating points: how to tune for high recall at acceptable false-positive load
  when a downstream VLM does the final selection.
- "Salient object" / objectness proposal as an alternative to full detection — is a cheap
  objectness/segment-everything pass (e.g. FastSAM, MobileSAM, EfficientSAM, a lightweight RPN)
  a better always-on proposer than a detector?
- Anything purpose-built for **aerial / small-object** proposal that is edge-deployable.
- How each composes with SAM2 (box or mask prompts feeding SAM2's memory).

## Constraints / priorities
- Edge-deployable on 8 GB Orin Nano, co-resident (leave room for a 2B Q8 VLM ≈ 2.5–3 GB + SAM2-tiny).
- Recency: prioritise 2024–2026 methods with reported edge/Jetson numbers or TensorRT/ONNX paths.
- Recall and continuous (streaming) operation matter more than mAP or SOTA precision.

## Explicitly out of scope (already ruled out — do not re-propose)
- Learned super-resolution of crops (Swin2SR tested, rejected — buys a 2B VLM nothing).
- Prose/text scene descriptions as the candidate representation (throws away geometry).
- Replacing SAM2 with EdgeTAM (already compared; SAM2 kept).

## Desired output
A ranked shortlist (comparison table: method · params · quantized latency & memory on Orin-class
HW if known · recall characteristics · aerial/small-object suitability · TensorRT/ONNX path ·
license) with 3–5 concrete candidates to prototype, each with a citation and a one-line
"why it fits the 8 GB co-resident slice."
