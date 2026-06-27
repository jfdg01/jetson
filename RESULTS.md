# RESULTS — Jetson Orin Nano Edge-LLM Benchmarks

Running ledger. Append, never overwrite. See `CLAUDE.md` for required fields.

**Global config (all llama.cpp runs):** Jetson Orin Nano 8 GB · 15 W locked (`nvpmodel -m 0` + `jetson_clocks`) · llama.cpp `57fe1f0` CUDA sm_87 · Q4_K_M · ngl=99 · n_ctx=4096 · pp512/tg128 · 5 reps each.  
**Idle baseline:** ~5.2 W · ~1820 MB RAM · ~11–50 MB swap (zram; "swap hit" = growth >50 MB over idle).

---

## Part I — Exploratory

### Campaign: llamacpp-upper-bound (2026-06-13)
Full writeup: [`results/2026-06-13-llamacpp-upper-bound.md`](results/2026-06-13-llamacpp-upper-bound.md)

| Model / quant | Params | pp512 tok/s | tg128 tok/s | Peak RAM | Mean/Peak W | tok/s·W⁻¹ | J/tok | Peak °C |
|---|---|---|---|---|---|---|---|---|
| Llama-3.2-3B-Instruct Q4_K_M | 3.0 B | 570.0 ± 2.4 | 14.53 ± 0.02 | 1.87 GiB wts | 12.5 / 13.6 | ≈1.7 | ≈0.86 | 66.9 |

¹ TTFT not captured here; added in capability sweep (unit 06 re-run → 85 ms).

---

### Campaign: model-capability-sweep (2026-06-14)
Full writeup: [`results/2026-06-13-model-capability-sweep.md`](results/2026-06-13-model-capability-sweep.md)

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

¹ Gemma-2-2B anomalously exceeds Mistral-7B — large KV cache + CUDA workspace at 4096 ctx. Swap "—" rows = growth not separately extracted; raw tegrastats in `results/raw/`.  
Cross-run consistency (unit 06 = baseline model): tg128 14.53 → 14.60 tok/s (+0.5%) ✓

#### Gemma-family sweep (2026-06-14)
RAM = tegrastats mmap lower bound; swap = growth over idle (corrected from false-positive "swap > 0" test).
Full writeup: [`results/2026-06-14-gemma-family-sweep/README.md`](results/2026-06-14-gemma-family-sweep/README.md)

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
Full writeup: [`results/2026-06-15-toy-demo/README.md`](results/2026-06-15-toy-demo/README.md)  
TURN: closed heuristic, <1 ms, no model. FOLLOW/ZOOM: zero-shot SmolVLM-500M Q8_0, both failed (format echo / full-frame bbox). Pre-registered expected outcome — pipeline mechanics work, grounding needs fine-tuning.

---

### Campaign: phase-b-sitl (2026-06-15)
Full writeup: [`results/2026-06-14-stage1-baseline/phase-b-sitl.md`](results/2026-06-14-stage1-baseline/phase-b-sitl.md)  
x86_64 SITL (not Jetson). Oracle bbox → ByteTrack → cascade PID → pymavlink offboard.

| Trials | Loop Hz | Mean pixel err | Coverage | Track losses | Result |
|---|---|---|---|---|---|
| 3 × 60 s | 19.99 ± 0.0 | 12.9 ± 0.0 px | 100% | 0 | **PASS** |

Zero variance is real: programmatic rover trajectory, P-controller converges to the same steady-state lag each run.

---

### Campaign: phase-c-vlm (2026-06-15)
Full writeup: [`results/2026-06-14-stage1-baseline/phase-c-vlm.md`](results/2026-06-14-stage1-baseline/phase-c-vlm.md)

| Mode | Platform | Key metrics | Result |
|---|---|---|---|
| inject-oracle Branch-1 | x86_64 SITL | hz=19.99 px_err=89.4 valid=100% | **PASS** |
| vlm zero-shot Branch-2 | SITL + Jetson SmolVLM-500M Q8_0 | hz=19.99 px_err=190.5 valid=12.5% track_cov=21% | **negative (expected)** |

---

### Stage 2: SmolVLM fine-tune (2026-06-16)
Full writeup: [`results/stage2-finetune/train-log.md`](results/stage2-finetune/train-log.md)  
1 epoch · 23,437 steps · 32,723 s · mean loss 0.8341.

| Epoch | Parse rate | IoU@0.25 | Result |
|---|---|---|---|
| 1 | 100% | **1.0%** | **FAIL — mode collapse** |

**Negative result:** LoRA text-only on SmolVLM; frozen SigLIP cannot update spatial features → collapses to marginal mean bbox (~[223,111,229,120] in 512×288 space). Demonstrates limit of text-only LoRA for spatial grounding.

---

### Stage 3: RefCOCO fine-tune (2026-06-16–17)
Full writeup: [`results/stage3-refcoco-finetune/train-log.md`](results/stage3-refcoco-finetune/train-log.md)  
Fix: well-posed RefCOCO targets + normalized 0–1000 coords + attn+MLP LoRA.

| Run | Date | Outcome |
|---|---|---|
| Run 1 | 2026-06-16 | **CRASHED** — CUDA unspecified launch failure at 70% epoch 1 (RTX 3090 hardware fault); loss was healthy (1.25→0.94). No mid-epoch checkpoint → all progress lost. |
| **Run 2** | 2026-06-17 | **SUCCESS** — 11.0 h · parse=100% · **IoU@0.25=82.5%** · center_std=200.5 · mean_iou=0.527. |

Export parity (HF bf16 vs GGUF, RefCOCO val n=100, seed-42): HF 85.0% → F16 62.0% → Q8_0 55.0% — **−30pp total gap FAIL** (gate ≤5pp). Root cause: transformers→llama.cpp Idefics3 preprocessing divergence (−23pp) + Q8_0 quant (−7pp). Motivates spine switch to Qwen2-VL-2B.

---

### Stage 4: RefCOCO→RefDrone curriculum (2026-06-17)
Full writeup: [`results/stage4-refdrone-curriculum/train-log.md`](results/stage4-refdrone-curriculum/train-log.md)  
Init from Stage 3 merged weights, LoRA on well-posed RefDrone subset (4101 train / 439 val), 3 epochs.

| Epoch | mean_loss | parse_rate | IoU@0.25 | mean_iou | center_std |
|---|---|---|---|---|---|
| 1 | 1.0287 | 100.0% | 12.5% | 0.072 | 214.1 |
| 2 | 0.9478 | 100.0% | 16.0% | 0.087 | 214.3 |
| 3 | 0.9168 | 100.0% | **19.5%** | 0.109 | 211.5 |

Gate G4 (IoU@0.25 ≥20%) — **NARROW MISS** (19.5%, 0.5pp short). Loss still descending at LR anneal → budget/capacity bound, not failure mode. ~10× lift over Stage 2 (~1%) and ~10× over zero-shot cross-domain floor (~2%). Next levers: largest-box augmentation, higher resolution.

---

## Part II — Principled rebuild (v2)

### Phase 0 — Backend-fidelity harness (2026-06-17)
Full writeup: [`results/2026-06-17-phase0-backend-fidelity/`](results/2026-06-17-phase0-backend-fidelity/README.md)  
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
Full writeup: [`results/2026-06-17-phase1-dataset-audit/`](results/2026-06-17-phase1-dataset-audit/README.md)

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
Full writeup: [`results/2026-06-17-phase2-resolution/`](results/2026-06-17-phase2-resolution/README.md)  
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
Full writeup: [`results/2026-06-17-phase3-train/`](results/2026-06-17-phase3-train/README.md)  
Qwen2-VL-2B + RefDrone well-posed (4101/439) + max_side=1024 · LoRA r16/α32 attn+MLP (vision frozen, 18.5 M trainable = 0.83%) · lr 2e-4 · 3 epochs · batch 16.

| Model | max_side | n | parse | IoU@0.25 | mean_iou | center_std | Manifest |
|---|---|---|---|---|---|---|---|
| base (Phase 2) | 1024 | 439 | 91.8% | 30.3% | 0.202 | 192.0 | `runs/20260617T191739Z` |
| + LoRA (in-loop) | 1024 | 200 | 100.0% | 65.0% | 0.497 | 226.6 | `runs/20260617T212559Z` |
| **+ LoRA (full val)** | **1024** | **439** | **100.0%** | **59.5%** | **0.451** | **215.2** | `runs/20260617T212559Z` |

**✅ Gate PASS:** 59.5% = 3.0× the 20% gate and 3.1× Part-I Stage 4 (19.5%). Gate cleared at epoch 1 → reserved levers not needed. Gain decomposition: base@512→1024 (4.1%→30.3%) × LoRA (30.3%→59.5%). Checkpoint: `runs/v2/phase3-refdrone-1024/`.

---

### Phase 4 — Export & deploy (2026-06-18)
Full writeup: [`results/2026-06-18-phase4-export-deploy/`](results/2026-06-18-phase4-export-deploy/README.md)  
GGUF export + Jetson eval (n=439, same contract, CUDA full-offload, 15 W, clocks locked, pinned llama.cpp `57fe1f07`).

| Backend | Size | n | parse | IoU@0.25 | mean_iou | center_std | Manifest |
|---|---|---|---|---|---|---|---|
| HF bf16 **(reference)** | — | 439 | 100.0% | **59.5%** | 0.451 | 215.2 | `runs/20260617T212559Z` |
| GGUF **F16** (Jetson) | 3.09 GB | 439 | 100.0% | **62.2%** | 0.466 | 218.2 | `runs/20260617T233529Z` |
| GGUF **Q8_0** (Jetson) | 1.65 GB | 439 | 100.0% | **62.6%** | 0.468 | 217.4 | `runs/20260618T001147Z` |

**✅ Gate PASS:** HF→F16 = −2.7pp, F16→Q8_0 = −0.5pp (both within noise; deployed *beats* HF). Part-I catastrophe (−23pp runtime + −7pp quant on SmolVLM) does not reproduce — payoff of spine selection in Phase 0c. **Q8_0 is the deploy artifact** (1.65 vs 3.09 GB, indistinguishable accuracy). Jetson server: `-np 1 --cache-ram 0 --no-cache-idle-slots` (avoids 8 GB OOM). **Phases 0–4 complete.**

---

## Part III — Persistent tracking / object permanence (v3)

Branch `v3/object-permanence`. Problem: keep a lock on a moving target across occlusion/scale change. Headline metrics: temporal (SOT success-precision, ID switches, re-acq time, oracle coverage). Single-frame IoU@0.25 retained as per-anchor sanity check.  
Charter: [`results/2026-06-18-part3-charter/README.md`](results/2026-06-18-part3-charter/README.md)

---

### T0 — Cadence & dynamics harness (2026-06-18) ✅
Full writeup: [`results/2026-06-18-t0-cadence/`](results/2026-06-18-t0-cadence/README.md)  
On-Orin anchor-cadence sweep + tracker cost + dynamics analysis. Anchor = Qwen2-VL-2B Q8_0 `phase3-refdrone-1024-q8_0`.

| Probe | Metric | Value |
|---|---|---|
| **T0a anchor cadence** | wall Hz @512/768/1024 (N=8) | **0.44 / 0.27 / 0.16 Hz** |
| | prefill @512/768/1024 | 1113 / 2431 / 5111 ms (dominant, ∝ pixels) |
| | decode (resolution-independent) | ~1.1 s / 24 tok ≈ 21.6 tok/s |
| | power/thermal/mem | idle 5.2W, mean 10.9W, peak 11.7W; 62.7°C; 4849 MB; no swap |
| **T0b tracker cost** | `ByteTracker.update()` median (1180 fr) | **0.051 ms** → ~1000× headroom under 50 ms |
| | coast horizon (`MAX_LOST_FRAMES=30`) | **1.5 s** @ 20 Hz |
| **T0c dynamics** | target px velocity (nadir, 1–10 m/s, 10–30 m) | 18.5–554 px/s (≤27.7 px/frame) |
| **T0d re-ID geometry** | target crop @10/20/30 m | 111×222 / 55×111 / 37×74 px |

**Key verdicts:** anchor_period (2.27 s @512) > coast_horizon (1.5 s) → re-acq must be event-triggered on loss. Tracker holds lock between anchors with ~1000× headroom. **Spine confirmed: Q8_0 @512** (768/1024 add latency with no fidelity gain on 640×480 camera + downscale).

---

### T1 — Data & temporal contract (2026-06-18) ✅
Full writeup: [`results/2026-06-18-t1-temporal-contract/`](results/2026-06-18-t1-temporal-contract/README.md)  
Temporal-metric suite added to `grounding/contract.py` (SOT success/precision, ID switches, purity, reacq time, oracle coverage, following error). Memoryless-ByteTrack baseline established.

| Clip | SOT succ | coverage | ID sw | purity | reacq fail | follow px |
|---|---|---|---|---|---|---|
| `clean_follow` (control) | 1.000 | 1.000 | 0 | 1.000 | 0/1 | 0.03 |
| `crossing_occlusion` | 0.827 | 0.575 | **1** | **0.725** | **1/2** | 67.7 |

**Finding:** memoryless tracker re-locks wrong same-class object after occlusion — purity 0.725, 1 ID-switch, 1/2 reacqs failed. Constraint #2 (object permanence) made numeric.

---

### T2 — Permanence mechanism (2026-06-24) ✅
Full writeup: [`results/2026-06-24-t2-permanence/`](results/2026-06-24-t2-permanence/README.md)  
Appearance memory: store target descriptor at acquisition, re-acquire by min descriptor distance + refuse-to-lock gate. EMA refinement while locked. Pixels not rendered (T1 decision); appearance = per-instance scalar with noise scaling by crop size.

| Policy | ID sw | purity | reacq fail | coverage | SOT succ | follow px |
|---|---|---|---|---|---|---|
| memoryless baseline (T1) | 1 | 0.725 | 1 | 0.575 | 0.827 | 67.7 |
| **re-ID, snr ≳ 1** | **0** | **1.000** | **0** | **0.695** | **1.000** | **0.13** |
| re-ID, snr ≤ 0.8 (below knee) | 1 | 0.751 | 1 | 0.575 | 0.827 | 67.7 |

**✅ Gate PASS (snr ≳ 1):** appearance gate fully resolves wrong-object re-lock above the knee; degrades to baseline below it. Coverage 0.695 = visible-frame ceiling (139/200). Control unchanged.

---

### T3 — Closed-loop integration in SITL (2026-06-24) ✅
Full writeup: [`results/2026-06-24-t3-closed-loop/`](results/2026-06-24-t3-closed-loop/README.md)  
Lock drives the camera (cascade-PID → body velocity → copter → re-projection). 20 Hz control / 1 Hz detect, 10 m alt. Distractor crosses + briefly occludes at t=29–31 s.

| Policy | Kinematic A/B coverage | Live ArduCopter SITL coverage | Occlusion frames |
|---|---|---|---|
| memoryless baseline | 49.2% | 53.7% | 40 |
| **re-ID (snr 8)** | **97.6%** | **71.5%** | 40 |

**✅ Gate PASS:** Phase-C ≈0% → 97.6% kinematic / 71.5% live SITL. Live margin smaller due to PID-lag + inertia lowering both policies' absolute coverage; direction + mechanism hold.

---

### T4 — On-Orin deployment + sim-to-device (2026-06-24) ✅
Full writeup: [`results/2026-06-24-t4-deployment/`](results/2026-06-24-t4-deployment/README.md)  
Integrated two-tier loop on actual Orin Nano 8 GB (15 W). One file (`bytetrack.py`) pushed to device.

| Tier | Dev box / T0a | Orin (T4) | Sim-to-device |
|---|---|---|---|
| fast: `ByteTracker.update` median (p99) | 0.051 ms (0.103) | **0.143 ms (0.291)** | 2.8× slower, **99.7% of 50 ms budget free** |
| slow: VLM anchor @512 wall | 2265 ms (0.44 Hz) | **2264 ms (0.44 Hz), 100% parse** | **−0.03%** |

**✅ Gate PASS:** fast tracker holds 20 Hz with ~350× headroom; anchor reproduces T0a cadence. `deploys_within_t0_budget = True`. **T0–T4 all GATE PASS. Part III COMPLETE.**

---

### 2026-06-26 — Terse output re-LoRA
Full writeup: [`results/2026-06-25-terse-output-retrain/`](results/2026-06-25-terse-output-retrain/README.md)

Retrain anchor to emit 4 space-separated integers instead of `{"bbox": [...]}`. One variable changed; base/data/resolution/LoRA/quant identical to 62.6% deploy.

**Iter-1** (bare ints 0–1000): model reverted to bracketed prior `[x1, x2, x3, x4]` — shed only the `{"bbox": …}` wrapper. Root cause: Qwen tokenizes digits 1-per-token, so digit count dominates, not JSON syntax.

| Metric | JSON deploy | iter-1 | iter-2b (deploy) |
|---|---|---|---|
| RefDrone IoU@0.25 (Orin Q8_0, n=439) | 62.6% | 61.0% (−1.6pp noise) | **63.1%** (+0.5pp) |
| parse_rate (Orin) | 100% | 99.3% | **100%** |
| decode tokens | ~24 | 21 | **12** (−43%) |
| decode ms | 967 | — | **531** (−45%) |
| anchor wall @512 | 1807 ms | 2114 ms | **1372 ms** (−24%) |

**Iter-2b win** (bare ints 0–100 + EOS-supervision fix): halve the digits + supervise `<|im_end|>` on the target (iter-2 without fix collapsed to 5% parse — outputs never learned to stop). Clean bare `28 44 36 59`, 100% parse. **Strict upgrade: better accuracy AND ~half decode.** Replaces the deploy artifact.

---

### 2026-06-26 — ROI-crop anchor (GATE PASS)
Full writeup: [`results/2026-06-25-roi-crop-anchor/`](results/2026-06-25-roi-crop-anchor/README.md)  
Inference-time only — no retraining. Feed anchor a crop around tracker's box (GT box × margin M) instead of full frame.

| Config (M=2.0) | Prefill ms (Orin Q8_0, 15W) | Decode ms | IoU@0.25 (HF n=439) | vs full-frame |
|---|---|---|---|---|
| full-frame @1024 (baseline) | 3691 | 966 | 62.6% | — |
| **ROI crop @512 ← deploy** | **1374** | 964 | **85.2%** | **2.7× prefill · +22.6 pp** |
| ROI crop @384 (max-speed) | 885 | 964 | 82.5% | 4.2× prefill · +19.9 pp |
| full-frame @512 (downscaled) | — | — | 15.9% | resolution ceiling laid bare |

Drift (RQ4): flat 82–85% up to 0.5·box prior drift; 74–80% even at full-box drift — all above baseline. Tight upscaled crop is *both* faster *and* more accurate (super-resolution beats resolution constraint #2). Decode unchanged — orthogonal to terse decode lever; two stack toward sub-1s anchor.

---

### 2026-06-26 — ROI re-anchor demo tab + live on-device confirm
Full writeup: [`results/2026-06-26-roi-demo-tab/`](results/2026-06-26-roi-demo-tab/README.md)  
ROI lever wired into deploy GUI ("Re-anchor speedup" tab). Live on deployed terse Q8_0 model.

| Upload | Full-frame prefill | ROI re-anchor prefill | Speedup |
|---|---|---|---|
| "the white car" | 4034 ms | 1388 ms | 2.91× |
| "the red car" | 3042 ms | 1375 ms | 2.21× |
| "the bus" | 3696 ms | 1373 ms | 2.69× |

ROI prefill pinned at ~1375 ms (fixed 512×512, matches offline 1374 ms). Boxes preserved/tightened. On-device IoU@0.25 via GGUF still open.

---

### 2026-06-27 — ROI re-anchor shrink-and-drift death spiral (negative + fix)
Full writeup: [`results/2026-06-27-roi-shrink-spiral/`](results/2026-06-27-roi-shrink-spiral/README.md)  
Fast re-anchor cadence on "Live tracking" tab collapsed lock: re-anchor crops 4·box natively → shrinking box → smaller crop → fewer pixels → smaller box (unbounded positive feedback). Fix: floor crop side (`roi_window` gains `min_side`; deploy `ROI_MIN_CROP=384 px`). Eval sweep unchanged (`min_side=0` default). On-Orin replay re-confirm open.
