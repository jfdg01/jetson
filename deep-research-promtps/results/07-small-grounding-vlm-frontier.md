# DR-07 — Frontier refresh: small grounding-capable VLMs and the effect of quantization on box accuracy

**Date:** 2026-07-07 · **Scope:** ≤3 B grounding-capable VLMs as candidates to beat the incumbent **Qwen2-VL-2B-Instruct @ Q8_0 (GGUF, llama.cpp)** on Jetson Orin Nano 8 GB (15 W), plus hard evidence on how quantization affects *bounding-box* (spatial) accuracy specifically.

> **Bottom line up front.** The one candidate that is genuinely *worth a bake-off* is **Qwen3-VL-2B-Instruct** — same vendor, Apache-2.0, a higher grounding-average than the incumbent on paper, and (as of Oct 2025) a *merged* llama.cpp vision path. But it comes with two caveats that mean the incumbent may still win in practice: (1) llama.cpp Qwen3-VL grounding has documented **coordinate-scaling quirks** that must be validated on your own IoU@0.25, and (2) it is **slower on the 8 GB board** (≈0.53 QPS prefill via llama.cpp vs the incumbent's already-tuned pipeline), with vLLM OOM-ing on 8 GB. Everything else is either over the memory budget (Moondream 3 = 9 B MoE), license-restricted (LocateAnything-3B = NVIDIA non-commercial), lacks an edge path (Rex-Omni), or is a pure detector that can't parse referring phrases (Grounding DINO). On the **quantization** question: the flagship VLM-quantization papers do **not** test grounding at all, but the referring-segmentation and VLA literature confirms your hypothesis — **spatial/coordinate output is far more quantization-fragile than text**, and the fault line is **activation** bit-width, not weight bit-width. Because llama.cpp GGUF is *weight-only* (activations stay fp16), you largely dodge that fault line; **Q8_0 remains the safe reference, Q6_K/Q5_K_M is the aggressive-but-safe floor, and anything at or below Q4 should be validated on your own box metric, never assumed from VQA scores.**

---

## 1. The incumbent baseline (for calibration)

Qwen2-VL-2B-Instruct, referring-expression comprehension (REC), from the Qwen2-VL technical report, Table 6 ([ar5iv 2409.12191](https://ar5iv.labs.arxiv.org/html/2409.12191)):

| Split | val | testA | testB |
|---|---|---|---|
| RefCOCO | 87.6 | 90.6 | 82.3 |
| RefCOCO+ | 79.0 | 84.9 | 71.0 |
| RefCOCOg | 81.2 | 80.3 (test) | — |

- **8-split mean ≈ 82.1** (this is the number to compare against Qwen3-VL's collapsed "RefCOCO-avg").
- License: **Apache 2.0**. Deployed on-device at **Q8_0 GGUF**, 85.2 % IoU@0.25 on your drone referring benchmark with ROI cropping (project record).

---

## 2. Candidate table (≤3 B grounding-capable VLMs, 2025–2026)

Scores are the primary-source numbers I could verify; where a per-model grounding number is **not published**, I say so rather than invent one. "RefCOCO-avg" for the Qwen3-VL rows is the collapsed RefCOCO/+/g average reported in the Qwen3-VL tech report (Table 4) — **not** the same basis as the incumbent's per-split table, so read the comparison as directional.

| Model | Params | Grounding score (source) | Edge runtime path | Reported Orin/edge latency | License | Worth a bake-off vs Qwen2-VL-2B? |
|---|---|---|---|---|---|---|
| **Qwen2-VL-2B** (incumbent) | 2 B | RefCOCO/+/g 8-split mean **≈82.1**; deployed **85.2 % IoU@0.25** w/ ROI | llama.cpp GGUF **Q8_0** (deployed) | tuned pipeline, anchor ≈2.0 s | Apache-2.0 | — (reference) |
| **Qwen3-VL-2B-Instruct** | 2 B | **RefCOCO-avg 85.6**; ODinW-13 **43.4** mAP; CountBench **88.4** ([tech report T4](https://arxiv.org/pdf/2511.21631)) | llama.cpp GGUF **+ vision** (PR [#16780](https://github.com/ggml-org/llama.cpp/pull/16780), b6887+); vLLM ≥0.11; TRT-LLM | Orin Nano Super: **0.53 QPS** (llama.cpp b7641) / **0.89 QPS** (transformers); 2-QPS target missed; vLLM **OOM** on 8 GB ([forum](https://forums.developer.nvidia.com/t/performance-inquiry-optimizing-qwen3-vl-2b-inference-for-2-qps-target-on-orin-nano-super/359639)) | **Apache-2.0** ([HF card](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)) | **YES — top candidate**, with coord-scaling validation + expect slower than incumbent |
| **Qwen3-VL-4B-Instruct** | 4 B | **RefCOCO-avg 89.0**; ODinW-13 **48.2** mAP ([tech report T4](https://arxiv.org/pdf/2511.21631)) | same llama.cpp/vLLM path; official GGUF | no Orin number published; how-to-run issue [#1847](https://github.com/QwenLM/Qwen3-VL/issues/1847) unanswered | Apache-2.0 | **MAYBE** — best grounding, but **>3 B** (~2.5–2.8 GB @Q4) is tight co-resident with SAM2; bake off only if 2B underwhelms |
| **Moondream 3 (preview)** | **9 B MoE / 2 B active** | COCO det **51.2 mAP**; RefCOCO+ **79.1 mIoU** (seg); CountBenchQA 86.4; ScreenSpot 80.4 ([models page](https://moondream.ai/p/models)) | Moondream "Photon" runtime (Jetson→B200); **no GGUF** (MoE) | inference "not optimized yet" ([blog](https://moondream.ai/blog/moondream-3-preview)) | permissive (personal/research/most commercial) | **WATCH** — strong grounding but **9 B weights** ≈ too heavy for 8 GB co-resident; non-llama.cpp runtime; not a clean drop-in |
| **Moondream 2** | 2 B dense | native detect/point/segment; no strong published RefCOCO REC number | **GGUF int4/int8**, llama.cpp; runs Orin/RPi | runs on RPi5 8 GB @ int4 (1.2 GB) ([HF GGUF](https://huggingface.co/moondream/moondream2-gguf)) | permissive | **MAYBE (low priority)** — true edge fit + native grounding, but detection/point-oriented, likely **below** incumbent on referring accuracy |
| **LocateAnything-3B** | 3 B (Qwen2.5-3B + MoonViT) | grounding specialist, **parallel box decoding**; quant coord-delta table (see §3) | **GGUF** via fork branch `mtmd-grounders`, needs `--special` ([HF](https://huggingface.co/yuuko-eth/LocateAnything-3B-GGUF)) | fast (single-step box decode); no Orin number | **NVIDIA — non-commercial/research only** | **MAYBE (research)** — excellent pure-localization + quant datapoint for the thesis; **license blocks productization**; needs fork build |
| **Rex-Omni** | 3 B (Qwen2.5-VL-3B base) | next-point-prediction; RefCOCOg + COCO/LVIS zero-shot rivaling Grounding DINO ([2510.12798](https://arxiv.org/html/2510.12798v1)) | no GGUF / llama.cpp path published | none | IDEA-Research (check terms) | **WATCH** — strong pure localizer, **no edge path yet** |
| **InternVL3.5-2B** | 2 B | InternVL3-2B RefCOCO-avg **86.7**; 3.5 improves ([2508.18265](https://arxiv.org/html/2508.18265v1)) | limited llama.cpp vision support | none published | MIT/Apache (per card) | **WATCH** — materially newer than the beaten InternVL3-2B, but prior **ROI-crop collapse** in your bake-off + deployment friction |
| **Florence-2 (base/large)** | 0.23 / 0.77 B | fine-tuned SOTA-small on RefCOCO/+/g (large ≈93 REC); base 51.5 % RefCOCO+ val ([CVPR'24](https://openaccess.thecvf.com/content/CVPR2024/papers/Xiao_Florence-2_Advancing_a_Unified_Representation_for_a_Variety_of_Vision_Tasks_CVPR_2024_paper.pdf)) | transformers / ONNX; **no llama.cpp** | very light (0.2–0.8 B) | MIT | **MAYBE (pure-localization specialist)** — tiny & fast, but seq2seq/no-chat, dated (2024), needs its own runtime |
| **Grounding DINO 1.5 Edge / YOLO-World** | ~<1 B det | open-vocab detector; Edge 36.2 AP LVIS-mini @ **75 FPS TensorRT** ([2405.10300](https://arxiv.org/html/2405.10300v1)) | TensorRT (native edge) | **75.2 FPS** (Orin-class, TRT) | Apache-2.0 (varies) | **Complementary, not a replacement** — takes class phrases, **not** relational referring expressions; useful as a detector+VLM-selector hybrid |

### Reading the table

- **Qwen3-VL-2B vs the incumbent, same basis.** The incumbent's *RefCOCO-only* average is ≈86.8, but its full RefCOCO/+/g 8-split average is **≈82.1** (folding in the harder RefCOCO+/g splits). Qwen3-VL-2B's **85.6** is a comparable collapsed average, so on the same basis Qwen3-VL-2B is **roughly +3.5 higher on grounding-average** — a real but modest gain, and **not** the regression that a naive "85.6 < 87.6" glance suggests. The Qwen3-VL report never publishes per-split RefCOCO/+/g for any size, so an apples-to-apples comparison **requires re-running the splits yourself** ([tech report](https://arxiv.org/pdf/2511.21631)). Treat the +3.5 as directional.
- **Qwen3-VL also adds open-vocab detection (ODinW-13 43.4 mAP) and counting** as first-class, which the incumbent lacks — potentially useful for the UAV multi-target regime.
- **Moondream 3's headline grounding is strong** (COCO 51.2 mAP, RefCOCO+ seg 79.1 mIoU) but it is a **9 B-total MoE**: all 9 B of weights must be resident even though only 2 B activate, so at 4-bit it is ≈4.5 GB *before* SAM2 + KV cache — the opposite of what your 8 GB co-residency budget wants. It also has no GGUF and its own runtime admits inference is unoptimized. This is the single biggest "looks great on the leaderboard, wrong shape for the board" trap in this scan.
- **The grounding specialists (LocateAnything-3B, Rex-Omni, Florence-2)** genuinely beat general small VLMs at *pure localization*, but each carries a deployment tax: LocateAnything is non-commercial-licensed and needs a llama.cpp fork; Rex-Omni has no edge path; Florence-2 is a dated seq2seq model with no chat interface and no llama.cpp. For a UAV pipeline that needs to parse *relational* operator phrases ("the car that just turned left"), a specialist tuned on short RefCOCO phrases is not obviously better than a general VLM you already trust — the referring-language understanding matters as much as the box regression.

---

## 3. Quantization → box-accuracy: the evidence

### 3.1 The headline gap
The three most-cited VLM-quantization papers **do not evaluate grounding at all** — they test VQA/OCR/reasoning only:
- **MBQ (Modality-Balanced Quantization)** — benchmarks MMMU, SEED, OCRBench, VizWiz, ScienceQA, TextVQA; **no RefCOCO/detection** ([2412.19509](https://arxiv.org/html/2412.19509v1)).
- **VLMQ** — ChartQA, DocVQA, OCRBench, TextVQA, etc.; **no grounding** ([2508.03351](https://arxiv.org/html/2508.03351v1)).
- **"Evaluating PTQ Impact on Reliable VQA"** — VQAv2/AdVQA/VizWiz only ([2602.13289](https://arxiv.org/html/2602.13289)).

So the common claim "INT4 is basically free" is a **VQA/text** claim and does **not** transfer to boxes without evidence. This gap is itself a citable finding — and a possible thesis contribution (a clean Q4-vs-Q8 GGUF sweep on your IoU@0.25 does not appear to exist publicly).

### 3.2 What the VQA/text numbers actually say (for context)
From the Reliable-VQA PTQ study ([2602.13289](https://arxiv.org/html/2602.13289)): **INT8 ≈ lossless; INT4 within ~1–2 pp of bf16; INT3 collapses** and, notably, calibration (ECE) degrades *before* raw accuracy does.

| Model | bf16 | int4 (data-aware MBQ) | int4 (data-free HQQ) | int3 (HQQ) |
|---|---|---|---|---|
| Qwen2-VL-7B | 83.0 % | **82.5 % (−0.5)** | 82.2 % (−0.8) | 80.1 % (−2.9) |
| Idefics3-8B | 79.3 % | **78.1 % (−1.2)** | 77.2 % (−2.1) | **64.0 % (−15.3)** |

### 3.3 The direct localization evidence (this is the load-bearing part)
**PTQ4RIS** applies post-training quantization to a *referring image segmentation* VLM — a spatial task scored in mIoU/oIoU ([2409.17020](https://arxiv.org/html/2409.17020v1)). Full-precision baseline: 74.31 mIoU (RefCOCO val). Under quantization:

| Bit-width | Δ mIoU (RefCOCO+ val, purpose-built method) |
|---|---|
| **W8A8** | near-lossless (−0.25 on testB) |
| **W6A6** | −1.46 |
| **W4A8** | −2.40 |
| **W4A4** | −5.44 |

And the decisive contrast: **naive PTQ methods that cost only ~2 pp on classification lose 20–34 mIoU on this localization task at W4A8** (RTN −22.68, PTQ4ViT −34.32). This is direct, quantitative confirmation that **spatial/coordinate output is roughly an order of magnitude more quantization-fragile than text/classification**, and that **activation bit-width is the fault line** — W4A8 survives, W4A4 breaks. The mechanism is corroborated from the robotics side by **DA-PTQ** ([2604.11572](https://arxiv.org/abs/2604.11572)): continuous coordinate/action regression is more numerically sensitive to low-bit rounding than discrete text tokens, because coordinates need precision across narrow ranges and accumulate error over sequential predictions.

### 3.4 The reassuring counter-evidence for *your* stack
Two facts pull the other way for GGUF/llama.cpp specifically:

1. **llama.cpp GGUF quantization is weight-only.** Activations run in fp16/fp32 during compute, so Q4_K_M is effectively **W4A16-ish**, not the W4A4 that collapses in PTQ4RIS. You largely **avoid the activation fault line** that breaks spatial tasks. This is the key nuance: the scary INT4 grounding-collapse numbers come from *activation* quantization, which GGUF does not do.
2. **A grounding-specialist GGUF shows sub-pixel coordinate stability down to Q4.** LocateAnything-3B-GGUF publishes mean absolute coordinate delta vs its own BF16 (0–1000 normalized space) ([HF card](https://huggingface.co/yuuko-eth/LocateAnything-3B-GGUF)):

| GGUF variant | Size | Coord delta vs BF16 |
|---|---|---|
| Q8_0 | 3.6 GB | ≤ 0.5 norm-units |
| Q6_K | 2.8 GB | sub-pixel |
| Q5_K_M | 2.4 GB | sub-pixel |
| Q4_K_M | 2.1 GB | sub-pixel (**author-recommended**) |

Caveat: this delta is measured against the model's *own* BF16 on a narrow 5-landmark GUI-screenshot suite, so it demonstrates *quantization stability*, not absolute REC/UAV accuracy — but it is the cleanest public "Q4 GGUF preserves coordinates" datapoint that exists.

### 3.5 A trap to avoid: "bad bbox in llama.cpp" is usually **not** quantization
The widely-cited llama.cpp reports of wrong Qwen-VL boxes are a **preprocessing/coordinate-scaling artifact, independent of quantization**:
- **#16880** — Qwen3-VL emits wrong boxes for non-1000×1000 / non-square images (needs ~1.25× rescale); the bug appears **identically in F16 and Q4_K_XL** ([issue](https://github.com/ggml-org/llama.cpp/issues/16880)).
- **#17131** — Qwen3-VL-4B produces *no* coordinates and 8B localizes poorly, **even at FP16**, and *not* reproduced in HF transformers at 4-bit; suspected GGUF conversion dropping vision-tower layers; **closed as stale, unresolved** ([issue](https://github.com/ggml-org/llama.cpp/issues/17131)).

Do not attribute these to Q4. They are, however, a **real deployment risk for Qwen3-VL grounding on llama.cpp** and the single biggest reason a Qwen3-VL-2B bake-off must validate raw box coordinates before trusting the metric.

### 3.6 Recommended quant level for coordinate outputs
- **Keep Q8_0 as the box-accuracy reference.** It is near-indistinguishable from full precision across every source here, and it is what you already deploy.
- **Q6_K / Q5_K_M is the aggressive-but-safe floor** to reclaim ~1–1.5 GB for SAM2 co-residency: weight-only, sub-pixel in the LocateAnything data, and it stays clear of the activation fault line.
- **Q4_K_M is defensible on GGUF** (weight-only ≈ W4A16, and sub-pixel in the specialist data) — but the localization literature says spatial output is 10× more fragile than text, so **validate Q4 on your own IoU@0.25 rather than assuming it from VQA parity**, especially for small/distant UAV targets where a few normalized units of coordinate drift crosses your 0.25 threshold.
- **Avoid activation quantization** (SmoothQuant, AWQ/GPTQ variants that quantize activations to ≤8-bit, and anything INT3/W4A4). That is precisely where boxes collapse.
- **Keep the vision encoder / mmproj at fp16.** Vision-token precision is where MBQ's modality-imbalance argument and PTQ4RIS's activation sensitivity both concentrate.

---

## 4. Verdict

1. **Bake off Qwen3-VL-2B-Instruct** against the incumbent. It is the only candidate that is simultaneously (a) ≤3 B, (b) Apache-2.0, (c) higher on grounding-average (~+3.5 on the same basis), and (d) already merged into llama.cpp with vision. **Gate the bake-off on two things the incumbent already passes:** raw box-coordinate correctness (given #16880/#17131) and on-device latency at 15 W (given the 0.53 QPS Orin-Super prefill and vLLM OOM). If Qwen3-VL-2B can't clear the coordinate-scaling quirks or is materially slower without a matching IoU gain, **the incumbent wins and you keep Qwen2-VL-2B @ Q8_0.**
2. **Hold Qwen3-VL-4B in reserve** — best grounding numbers, but over the 3 B budget and unproven co-resident with SAM2 on 8 GB.
3. **Do not chase Moondream 3** on this board (9 B MoE ≠ 8 GB co-residency), and treat Moondream 2 / Florence-2 / LocateAnything-3B / Rex-Omni as **pure-localization specialists** to sample only if a general VLM keeps losing on the box metric — each has a license or runtime tax, and none clearly parses relational operator phrases better than a Qwen VLM.
4. **Quantization:** the incumbent's Q8_0 is well-chosen. Weight-only GGUF lets you likely drop to Q6_K/Q5_K_M safely; treat Q4 as "validate, don't assume." There is a genuine **published gap** on Q4-vs-Q8 GGUF box accuracy — measuring it on your IoU@0.25 would be a citable thesis contribution.

---

## Sources

- Qwen2-VL technical report (incumbent REC numbers, Table 6): https://ar5iv.labs.arxiv.org/html/2409.12191 · https://arxiv.org/pdf/2409.12191
- Qwen3-VL technical report (small-model grounding, Table 4; family sizes; RefCOCO-avg/ODinW-13/CountBench): https://arxiv.org/abs/2511.21631 · https://arxiv.org/pdf/2511.21631
- Qwen3-VL-2B-Instruct model card (Apache-2.0, params, "stronger 2D grounding"): https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct
- Qwen3-VL-4B-Instruct model card / GGUF: https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct
- Qwen3-VL GitHub (runtime support: vLLM ≥0.11, TRT-LLM): https://github.com/QwenLM/Qwen3-VL · run-on-Orin issue #1847: https://github.com/QwenLM/Qwen3-VL/issues/1847
- llama.cpp Qwen3-VL vision support (PR #16780, merged 2025-10-30): https://github.com/ggml-org/llama.cpp/pull/16780 · feature request #16207: https://github.com/ggml-org/llama.cpp/issues/16207
- llama.cpp Qwen3-VL grounding/bbox bugs: #16880 (non-square scaling): https://github.com/ggml-org/llama.cpp/issues/16880 · #17131 (4B no coords / 8B poor, FP16 too, closed stale): https://github.com/ggml-org/llama.cpp/issues/17131
- Jetson Orin Nano Super Qwen3-VL-2B QPS benchmark (0.53 llama.cpp / 0.89 transformers; vLLM OOM): https://forums.developer.nvidia.com/t/performance-inquiry-optimizing-qwen3-vl-2b-inference-for-2-qps-target-on-orin-nano-super/359639
- Moondream 3 preview (9 B MoE / 2 B active, unoptimized inference): https://moondream.ai/blog/moondream-3-preview · models/benchmarks page (COCO 51.2 mAP, RefCOCO+ 79.1 mIoU, CountBench 86.4, ScreenSpot 80.4, licensing): https://moondream.ai/p/models
- Moondream 2 GGUF (int4/int8, edge): https://huggingface.co/moondream/moondream2-gguf · ggml-org GGUF: https://huggingface.co/ggml-org/moondream2-20250414-GGUF
- LocateAnything-3B-GGUF (Qwen2.5-3B + MoonViT, parallel box decoding, per-quant coord-delta table, NVIDIA non-commercial license, llama.cpp fork): https://huggingface.co/yuuko-eth/LocateAnything-3B-GGUF · paper: https://arxiv.org/html/2605.27365v2
- Rex-Omni "Detect Anything via Next Point Prediction" (3 B, Qwen2.5-VL-3B, next-point-prediction, RefCOCOg/COCO/LVIS): https://arxiv.org/html/2510.12798v1 · https://github.com/IDEA-Research/Rex-Omni
- InternVL3.5 (grounding, 2B improvements): https://arxiv.org/html/2508.18265v1 · InternVL3 (2B RefCOCO-avg 86.7): https://arxiv.org/pdf/2504.10479
- Florence-2 (tiny grounding specialist, RefCOCO/+/g SOTA-small after fine-tune): https://openaccess.thecvf.com/content/CVPR2024/papers/Xiao_Florence-2_Advancing_a_Unified_Representation_for_a_Variety_of_Vision_Tasks_CVPR_2024_paper.pdf
- Grounding DINO 1.5 Edge (open-vocab detector, 75.2 FPS TensorRT edge): https://arxiv.org/html/2405.10300v1
- MiniCPM-V 4.5/4.6 (8 B, Qwen3-8B base; GGUF/llama.cpp): https://huggingface.co/openbmb/MiniCPM-V-4_5-gguf · https://arxiv.org/abs/2509.18154
- **Quantization × grounding:** MBQ (no grounding tested): https://arxiv.org/html/2412.19509v1 · VLMQ (no grounding): https://arxiv.org/html/2508.03351v1 · Reliable-VQA PTQ (INT4 ~1–2 pp of bf16, INT3 collapse): https://arxiv.org/html/2602.13289 · **PTQ4RIS** (direct localization degradation under PTQ; W4A8 −2.4 mIoU, W4A4 −5.4, naive PTQ −20 to −34): https://arxiv.org/html/2409.17020v1 · DA-PTQ (coordinate regression more sensitive than text): https://arxiv.org/abs/2604.11572 · "Best Practices for Quantization of VLMs" (3.5–4.5 bpw optimal for VQA/caption, no grounding): https://arxiv.org/html/2601.15287v1 · LUQ (sub-4-bit hurts multimodal far more than language-only): https://arxiv.org/html/2509.23729v2
- Coordinate-format effects (text vs bin vs grid tokens; 1000-base most robust): https://arxiv.org/html/2510.03230v1 · Rex-Omni quantized-coordinate special tokens 0–999: https://arxiv.org/html/2510.12798v1
