# RESULTS — Part II · Principled rebuild (v2, Phases 0–4)

Index: [`../../RESULTS.md`](../../RESULTS.md) · Companion: [`../questions/`](../questions/) (research questions) · [`../decisions/`](../decisions/) (what was chosen & why).
Per-campaign detail lives in `experiments/<campaign>/README.md`. Append, never overwrite.

---

## Part II — Principled rebuild (v2)

### Phase 0 — Backend-fidelity harness (2026-06-17)
Full writeup: [`experiments/2026-06-17-phase0-backend-fidelity/`](../../experiments/2026-06-17-phase0-backend-fidelity/README.md)  
RefCOCO val, seed-42, n=100. Local RTX 3090.

| Step | Backend | Model | IoU@0.25 | parse | mean_iou | center_std | Manifest |
|---|---|---|---|---|---|---|---|
| 0a anchor | HF bf16 | smolvlm_ft3 | **85.0%** | 100% | 0.567 | 187.8 | `runs/20260617T115913Z` |
| 0b parity | GGUF F16 | smolvlm_ft3 | **69.0%** | 100% | 0.393 | 149.7 | `runs/20260617T121539Z` |
| 0b parity | GGUF Q8_0 | smolvlm_ft3 | **67.0%** | 100% | 0.389 | 148.0 | `runs/20260617T121756Z` |
| 0c.2 spine | HF bf16 | SmolVLM-500M **base** | 0.0% | 9% | 0.004 | 61.3 | `runs/20260617T165959Z` |
| 0c.2 spine | HF bf16 | **Qwen2-VL-2B base** | **15.0%** | 24% | 0.393 | 162.1 | `runs/20260617T170339Z` |
| 0c.2 spine | GGUF F16 | Qwen2-VL-2B base | 13.0% | 18% | 0.548 | 198.7 | `runs/20260617T171534Z` |
| 0c.2 spine | GGUF Q8_0 | Qwen2-VL-2B base | 14.0% | 19% | 0.533 | 187.5 | `runs/20260617T172502Z` |

**✅ Gate: Qwen2-VL-2B** — zero-shot 15% vs SmolVLM-base 0%, deploy fidelity gap −2pp ≪ SmolVLM-ft3's −16pp, native dynamic resolution attacks tiny-object ceiling.

---

### Phase 1 — Dataset audit gate (2026-06-17)
Full writeup: [`experiments/2026-06-17-phase1-dataset-audit/`](../../experiments/2026-06-17-phase1-dataset-audit/README.md)

**Well-posedness (box-per-caption):**

| Split | Captions | Mean boxes/caption | Well-posed (=1 box) | Trainable budget |
|---|---|---|---|---|
| RefDrone train | 12 339 | **3.80** | 4 101 (33.2%) | **4 101** |
| RefDrone val | 1 421 | **3.33** | 439 (30.9%) | **439** |
| RefCOCO val (control) | 2 000 | **1.00** | 2 000 (100%) | 2 000 |

**Object size (√area px) at 512 long-edge:**

| Split | p5 | p10 | p25 | p50 | p75 | p90 | p95 |
|---|---|---|---|---|---|---|---|
| RefDrone train @512 | 6.0 | 7.2 | 10.2 | **15.9** | 25.4 | 38.6 | 49.7 |
| RefDrone val @512 | 5.5 | 6.5 | 9.4 | 14.6 | 23.8 | 35.9 | 44.7 |
| RefCOCO val (control) | 106.9 | 116.1 | 136.4 | **172.0** | 224.4 | 281.6 | 327.2 |

**✅ Gate:** 33% of captions usable (small budget → RefCOCO warm-start + `largest_box_aug` lever); median aerial object ≈16 px @512 (resolution is the dominant lever).

---

### Phase 2 — Resolution strategy (2026-06-17)
Full writeup: [`experiments/2026-06-17-phase2-resolution/`](../../experiments/2026-06-17-phase2-resolution/README.md)  
No-training ladder · RefDrone well-posed val (n=439) · Qwen2-VL-2B base · HF bf16 greedy.

| Arm | max_side | parse | IoU@0.25 | mean_iou | center_std | Manifest |
|---|---|---|---|---|---|---|
| ladder | 512 | 100.0% | 4.1% | 0.031 | 129.1 | `runs/20260617T190608Z` |
| ladder | 768 | 100.0% | 10.7% | 0.065 | 157.9 | `runs/20260617T191130Z` |
| **ladder** | **1024** | **91.8%** | **30.3%** | 0.202 | 192.0 | `runs/20260617T191739Z` |
| ladder | 1280 | 92.0% | 38.7% | 0.313 | 196.1 | `runs/20260617T192436Z` |

**✅ Gate: max_side=1024** — resolution is the dominant lever (4.1% → 38.7%, 9.4× with frozen weights); elbow at 1024 (+19.6pp jump 768→1024 = 78% of 1280 ceiling); clears 20% gate before training; 1280 held as Phase-3 lever.

---

### Phase 3 — LoRA fine-tune (2026-06-17/18)
Full writeup: [`experiments/2026-06-17-phase3-train/`](../../experiments/2026-06-17-phase3-train/README.md)  
Qwen2-VL-2B + RefDrone well-posed (4101/439) + max_side=1024 · LoRA r16/α32 attn+MLP (vision frozen, 18.5 M trainable = 0.83%) · lr 2e-4 · 3 epochs · batch 16.

| Model | max_side | n | parse | IoU@0.25 | mean_iou | center_std | Manifest |
|---|---|---|---|---|---|---|---|
| base (Phase 2) | 1024 | 439 | 91.8% | 30.3% | 0.202 | 192.0 | `runs/20260617T191739Z` |
| + LoRA (in-loop) | 1024 | 200 | 100.0% | 65.0% | 0.497 | 226.6 | `runs/20260617T212559Z` |
| **+ LoRA (full val)** | **1024** | **439** | **100.0%** | **59.5%** | **0.451** | **215.2** | `runs/20260617T212559Z` |

**✅ Gate PASS:** 59.5% = 3.0× the 20% gate and 3.1× Part-I Stage 4 (19.5%). Gate cleared at epoch 1 → reserved levers not needed. Gain decomposition: base@512→1024 (4.1%→30.3%) × LoRA (30.3%→59.5%). Checkpoint: `runs/v2/phase3-refdrone-1024/`.

---

### Phase 4 — Export & deploy (2026-06-18)
Full writeup: [`experiments/2026-06-18-phase4-export-deploy/`](../../experiments/2026-06-18-phase4-export-deploy/README.md)  
GGUF export + Jetson eval (n=439, same contract, CUDA full-offload, 15 W, clocks locked, pinned llama.cpp `57fe1f07`).

| Backend | Size | n | parse | IoU@0.25 | mean_iou | center_std | Manifest |
|---|---|---|---|---|---|---|---|
| HF bf16 **(reference)** | — | 439 | 100.0% | **59.5%** | 0.451 | 215.2 | `runs/20260617T212559Z` |
| GGUF **F16** (Jetson) | 3.09 GB | 439 | 100.0% | **62.2%** | 0.466 | 218.2 | `runs/20260617T233529Z` |
| GGUF **Q8_0** (Jetson) | 1.65 GB | 439 | 100.0% | **62.6%** | 0.468 | 217.4 | `runs/20260618T001147Z` |

**✅ Gate PASS:** HF→F16 = −2.7pp, F16→Q8_0 = −0.5pp (both within noise; deployed *beats* HF). Part-I catastrophe (−23pp runtime + −7pp quant on SmolVLM) does not reproduce — payoff of spine selection in Phase 0c. **Q8_0 is the deploy artifact** (1.65 vs 3.09 GB, indistinguishable accuracy). Jetson server: `-np 1 --cache-ram 0 --no-cache-idle-slots` (avoids 8 GB OOM). **Phases 0–4 complete.**

---
