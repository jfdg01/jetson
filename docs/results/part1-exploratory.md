# RESULTS — Part I · Exploratory (device benchmarks + grounding Stages 1–4)

Index: [`../../RESULTS.md`](../../RESULTS.md) · Companion: [`../questions/`](../questions/) (research questions) · [`../decisions/`](../decisions/) (what was chosen & why).
Per-campaign detail lives in `experiments/<campaign>/README.md`. Append, never overwrite.

**Global config (all llama.cpp runs):** Jetson Orin Nano 8 GB · 15 W locked (`nvpmodel -m 0` + `jetson_clocks`) · llama.cpp `57fe1f0` CUDA sm_87 · Q4_K_M · ngl=99 · n_ctx=4096 · pp512/tg128 · 5 reps each.
**Idle baseline:** ~5.2 W · ~1820 MB RAM · ~11–50 MB swap (zram; "swap hit" = growth >50 MB over idle).

---

## Part I — Exploratory

### Campaign: llamacpp-upper-bound (2026-06-13)
Full writeup: [`experiments/2026-06-13-llamacpp-upper-bound/`](../../experiments/2026-06-13-llamacpp-upper-bound/README.md)

| Model / quant | Params | pp512 tok/s | tg128 tok/s | Peak RAM | Mean/Peak W | tok/s·W⁻¹ | J/tok | Peak °C |
|---|---|---|---|---|---|---|---|---|
| Llama-3.2-3B-Instruct Q4_K_M | 3.0 B | 570.0 ± 2.4 | 14.53 ± 0.02 | 1.87 GiB wts | 12.5 / 13.6 | ≈1.7 | ≈0.86 | 66.9 |

¹ TTFT not captured here; added in capability sweep (unit 06 re-run → 85 ms).

---

### Campaign: model-capability-sweep (2026-06-14)
Full writeup: [`experiments/2026-06-13-model-capability-sweep/`](../../experiments/2026-06-13-model-capability-sweep/README.md)

| # | Model / quant | Params | pp512 tok/s | tg128 tok/s | tg512 tok/s | TTFT ms | Peak RAM MB | Idle/Mean/Peak W | tok/s·W⁻¹ | J/tok | Peak °C | Swap peak MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | Qwen2.5-0.5B-Instruct Q4_K_M | 0.5 B | 3027 ± 19 | 71.52 ± 0.07 | 71.12 | 38 | 2637 | 5.17/6.57/11.25 | 11.77 | 0.157 | 59.9 | 206 |
| 02 | Llama-3.2-1B-Instruct Q4_K_M | 1.0 B | 1534 ± 2 | 35.07 ± 0.07 | 34.90 | 49 | 3497 | 5.26/8.42/13.32 | 4.35 | 0.380 | 63.3 | 206 |
| 03 | Qwen2.5-1.5B-Instruct Q4_K_M | 1.5 B | 1098 ± 0 | 26.56 ± 0.00 | 26.47 | 59 | 2872 | 5.41/7.88/11.79 | 4.17 | 0.444 | 63.6 | — |
| 04 | Gemma-2-2B-it Q4_K_M | 2.6 B | 728 ± 1 | 15.98 ± 0.00 | 15.87 | 85 | 5818¹ | 5.25/8.47/13.17 | 2.02 | 0.824 | 65.7 | 406 |
| 05 | Qwen2.5-3B-Instruct Q4_K_M | 3.0 B | 559 ± 5 | 14.91 ± 0.00 | 14.90 | 91 | 3180 | 5.25/11.93/12.56 | 2.04 | 0.842 | 65.1 | — |
| 06 | Llama-3.2-3B-Instruct Q4_K_M | 3.0 B | 570 ± 0 | 14.60 ± 0.00 | 14.54 | 85 | 3719 | 5.28/11.02/12.60 | 2.00 | 0.863 | 65.1 | — |
| 07 | Phi-3.5-mini-instruct Q4_K_M | 3.8 B | 432 ± 1 | 13.15 ± 0.00 | 12.76 | 114 | 4693 | 5.25/12.45/13.09 | 1.68 | 0.995 | 65.8 | — |
| 08 | Mistral-7B-Instruct-v0.3 Q4_K_M | 7.2 B | 253 ± 0 | 8.39 ± 0.00 | 8.36 | 190 | 5488 | 5.21/12.45/13.76 | 0.98 | 1.639 | 67.3 | 419 |
| 09 | Qwen2.5-7B-Instruct Q4_K_M | 7.6 B | 266 ± 1 | 7.89 ± 0.00 | 7.86 | 202 | 5465 | 5.23/11.92/13.80 | 0.92 | 1.749 | 67.1 | — |
| 10 | Meta-Llama-3.1-8B-Instruct Q4_K_M | 8.0 B | 245 ± 0 | 7.75 ± 0.00 | 7.72 | 204 | 5953 | 5.25/12.04/13.92 | 0.89 | 1.795 | 67.4 | 460 |

¹ Gemma-2-2B anomalously exceeds Mistral-7B — large KV cache + CUDA workspace at 4096 ctx. Swap "—" rows = growth not separately extracted; raw tegrastats in `experiments/raw/`.  
Cross-run consistency (unit 06 = baseline model): tg128 14.53 → 14.60 tok/s (+0.5%) ✓

#### Gemma-family sweep (2026-06-14)
RAM = tegrastats mmap lower bound; swap = growth over idle (corrected from false-positive "swap > 0" test).
Full writeup: [`experiments/2026-06-14-gemma-family-sweep/README.md`](../../experiments/2026-06-14-gemma-family-sweep/README.md)

| Unit | Model + quant | Params | pp512 | tg128 | Peak W | tok/s·W | J/tok | °C | Peak RAM | Swap |
|---|---|---|---|---|---|---|---|---|---|---|
| G1 | gemma-3-270m-it Q8_0 | 0.27B | 7097 | 104.42 | 10.9 | 9.62 | 0.104 | 58 | 2458 MB | none |
| G2 | gemma-3-4b-it q4_0 QAT | 4.0B | 502 | 12.15 | 12.7 | 0.96 | 1.043 | 65 | 4617 MB | none |
| G3 | gemma-4-E2B-it q4_0 QAT | 5.1B | 701 | 20.44 | 11.9 | 1.71 | 0.584 | 64 | 2968 MB | none |
| G4 | gemma-4-E4B-it q4_0 QAT | 8.0B | 362 | 11.42 | 12.7 | 0.90 | 1.110 | 66 | 4374 MB | +97 MB |
| G5 | gemma-3-12b-it q4_0 QAT | 12.0B | **CUDA OOM at load** | — | 6.6 | — | — | 57 | weights ~7.7 GiB > VRAM | — |

Note: tegrastats under-counts mmap'd weights; `--no-mmap` residents: G2 4632 MiB, G3 3677 MiB (+709 MiB gap — PLE shared matrices not paged in). G4 requires mmap (4.7 GiB malloc > free RAM). G5 hard OOM at load.

#### VLM grounding (Phase A, zero-shot, 2026-06-14–15)

| Unit | Model | Setup | per_frame | Hz | img_tok | Mean W | RAM | Notes |
|---|---|---|---|---|---|---|---|---|
| V1 | SmolVLM-256M Q8_0 | vlm-server 15W | 304 ms | 3.29 | 64 | 6.6 | 1777 MB | |
| V2 | SmolVLM-500M Q8_0 | vlm-server 15W | 338 ms | 2.96 | 64 | 7.2 | 2241 MB | |
| V3 | gemma-3-4b-it q4_0 | vlm-server 15W | 9576 ms | 0.10 | 256 | 9.7 | 6414 MB | swap |
| V4 | gemma-4-E2B-it q4_0 QAT | `--reasoning off` | 2035 ms | 0.49 | 144 | 8.2 | 4616 MB | canonical |
| V5 | gemma-4-E4B-it q4_0 QAT | `--reasoning off` | 2963 ms | 0.34 | 144 | 8.8 | 6444 MB | swap canonical |
| S1 | SmolVLM-256M Q8_0 | Phase A grounding | — | 3.58 | — | — | 2338 MB | parse=0% IoU@0.25=0% |
| S2 | SmolVLM-500M Q8_0 | Phase A grounding | — | 1.20 | — | — | 2734 MB | parse=4% IoU@0.25=0% |

---

### Campaign: toy-nl-demo (2026-06-15)
Full writeup: [`experiments/2026-06-15-toy-demo/README.md`](../../experiments/2026-06-15-toy-demo/README.md)  
TURN: closed heuristic, <1 ms, no model. FOLLOW/ZOOM: zero-shot SmolVLM-500M Q8_0, both failed (format echo / full-frame bbox). Pre-registered expected outcome — pipeline mechanics work, grounding needs fine-tuning.

---

### Campaign: phase-b-sitl (2026-06-15)
Full writeup: [`experiments/2026-06-14-stage1-baseline/phase-b-sitl.md`](../../experiments/2026-06-14-stage1-baseline/phase-b-sitl.md)  
x86_64 SITL (not Jetson). Oracle bbox → ByteTrack → cascade PID → pymavlink offboard.

| Trials | Loop Hz | Mean pixel err | Coverage | Track losses | Result |
|---|---|---|---|---|---|
| 3 × 60 s | 19.99 ± 0.0 | 12.9 ± 0.0 px | 100% | 0 | **PASS** |

Zero variance is real: programmatic rover trajectory, P-controller converges to the same steady-state lag each run.

---

### Campaign: phase-c-vlm (2026-06-15)
Full writeup: [`experiments/2026-06-14-stage1-baseline/phase-c-vlm.md`](../../experiments/2026-06-14-stage1-baseline/phase-c-vlm.md)

| Mode | Platform | Key metrics | Result |
|---|---|---|---|
| inject-oracle Branch-1 | x86_64 SITL | hz=19.99 px_err=89.4 valid=100% | **PASS** |
| vlm zero-shot Branch-2 | SITL + Jetson SmolVLM-500M Q8_0 | hz=19.99 px_err=190.5 valid=12.5% track_cov=21% | **negative (expected)** |

---

### Stage 2: SmolVLM fine-tune (2026-06-16)
Full writeup: [`experiments/stage2-finetune/train-log.md`](../../experiments/stage2-finetune/train-log.md)  
1 epoch · 23,437 steps · 32,723 s · mean loss 0.8341.

| Epoch | Parse rate | IoU@0.25 | Result |
|---|---|---|---|
| 1 | 100% | **1.0%** | **FAIL — mode collapse** |

**Negative result:** LoRA text-only on SmolVLM; frozen SigLIP cannot update spatial features → collapses to marginal mean bbox (~[223,111,229,120] in 512×288 space). Demonstrates limit of text-only LoRA for spatial grounding.

---

### Stage 3: RefCOCO fine-tune (2026-06-16–17)
Full writeup: [`experiments/stage3-refcoco-finetune/train-log.md`](../../experiments/stage3-refcoco-finetune/train-log.md)  
Fix: well-posed RefCOCO targets + normalized 0–1000 coords + attn+MLP LoRA.

| Run | Date | Outcome |
|---|---|---|
| Run 1 | 2026-06-16 | **CRASHED** — CUDA unspecified launch failure at 70% epoch 1 (RTX 3090 hardware fault); loss was healthy (1.25→0.94). No mid-epoch checkpoint → all progress lost. |
| **Run 2** | 2026-06-17 | **SUCCESS** — 11.0 h · parse=100% · **IoU@0.25=82.5%** · center_std=200.5 · mean_iou=0.527. |

Export parity (HF bf16 vs GGUF, RefCOCO val n=100, seed-42): HF 85.0% → F16 62.0% → Q8_0 55.0% — **−30pp total gap FAIL** (gate ≤5pp). Root cause: transformers→llama.cpp Idefics3 preprocessing divergence (−23pp) + Q8_0 quant (−7pp). Motivates spine switch to Qwen2-VL-2B.

---

### Stage 4: RefCOCO→RefDrone curriculum (2026-06-17)
Full writeup: [`experiments/stage4-refdrone-curriculum/train-log.md`](../../experiments/stage4-refdrone-curriculum/train-log.md)  
Init from Stage 3 merged weights, LoRA on well-posed RefDrone subset (4101 train / 439 val), 3 epochs.

| Epoch | mean_loss | parse_rate | IoU@0.25 | mean_iou | center_std |
|---|---|---|---|---|---|
| 1 | 1.0287 | 100.0% | 12.5% | 0.072 | 214.1 |
| 2 | 0.9478 | 100.0% | 16.0% | 0.087 | 214.3 |
| 3 | 0.9168 | 100.0% | **19.5%** | 0.109 | 211.5 |

Gate G4 (IoU@0.25 ≥20%) — **NARROW MISS** (19.5%, 0.5pp short). Loss still descending at LR anneal → budget/capacity bound, not failure mode. ~10× lift over Stage 2 (~1%) and ~10× over zero-shot cross-domain floor (~2%). Next levers: largest-box augmentation, higher resolution.

---
