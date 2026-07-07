# DR-07 — Frontier refresh: small grounding-capable VLMs and quantization effect on box accuracy

## Context (assume no prior knowledge)
My UAV grounding stack uses **Qwen2-VL-2B-Instruct at Q8_0 (GGUF, llama.cpp)** on a **Jetson Orin
Nano 8 GB** (15 W). I picked it via a backbone bake-off (~mid-2025) against InternVL3-2B,
Qwen2.5-VL-3B, PaliGemma2-3B, and SmolVLM2-500M — Qwen2-VL-2B won; the others either lost on
grounding accuracy or collapsed on my ROI-crop regime. Deployed grounding is 85.2 % IoU@0.25 on a
drone referring benchmark with ROI cropping. The field moves fast, so I want a periodic scan of
whether a *newer/smaller/faster* grounding-capable VLM would beat my incumbent, and — separately —
hard evidence on how aggressive **quantization affects spatial-grounding (box) accuracy**, since
box accuracy is my metric and it may degrade differently from text quality.

## Research question
As of 2025–2026, what small (≤3 B) **grounding-capable** VLMs are candidates to beat Qwen2-VL-2B on
edge referring/grounding, and how does **quantization (Q8 / INT4 / AWQ / GPTQ / SmoothQuant)**
affect *bounding-box* accuracy specifically (as opposed to captioning/VQA quality) for such models?

## Sub-questions to cover
- New/updated small grounding VLMs (Qwen3-VL / Qwen2.5-VL updates, Moondream2/3, Florence-2,
  PaliGemma2, InternVL 2.5/3.x, MiniCPM-V, SmolVLM2, and any 2025–2026 grounding-specialised small
  models) — which report strong **referring-expression / grounding** numbers, not just VQA.
- Which of these have **GGUF / llama.cpp / TensorRT-LLM / MLC** paths that actually run on Orin
  Nano 8 GB, with reported tokens/s or latency.
- **Quantization vs grounding accuracy**: published evidence that spatial/coordinate outputs
  degrade (or don't) under INT4/AWQ vs Q8/fp16 — coordinate-regression is numerically sensitive, so
  I want data, not vibes. Any studies isolating localization from language quality.
- Prompt/output-format effects on small-VLM grounding (coordinate encodings, "terse" outputs,
  special-token vs text coordinates) that materially change accuracy or latency.
- Whether a grounding-*specialised* small model (open-vocab detector-VLM hybrids) would beat a
  general small VLM for *pure localization* at my scale.

## Constraints / priorities
- Runs on 8 GB Orin Nano co-resident with SAM2; ≤3 B; quantizable to fit ~3 GB.
- Metric of record is **localization** (IoU@0.25 on referring), not caption/VQA scores.
- Prioritise 2025–2026 releases and reproducible edge deployment reports.

## Explicitly out of scope (already ruled out)
- The specific arms already bake-off-tested and beaten (InternVL3-2B, Qwen2.5-VL-3B, PaliGemma2-3B,
  SmolVLM2-500M) — unless a *materially newer* checkpoint or a grounding-specific finding changes
  the verdict.
- Learned super-resolution as a preprocessing lever (separately tested and rejected).

## Desired output
A table of ≤3 B grounding-VLM candidates (grounding benchmark score · size · edge runtime path ·
reported Orin/edge latency · license) with a clear "worth a bake-off vs Qwen2-VL-2B or not" call
per model, plus a focused summary of **quantization → box-accuracy** evidence with a recommended
quant level for coordinate outputs. Citations throughout.
