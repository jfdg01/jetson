# VLM Benchmark — Head-to-Head Aerial Grounding Sweep

**Branch:** `2026-06/vlm-sweep`  
**Started:** 2026-06-28  
**Device:** Jetson Orin Nano 8 GB · 15 W locked · sm_87  
**Purpose:** Select the best VLM spine for the next-generation rewrite by comparing five
current models on aerial drone grounding, both zero-shot and after fine-tuning on the same
dataset and recipe.

---

## Why this exists

The v2/v3 spine (Qwen2-VL-2B Q8_0) was chosen in June 2026 against the models available
then. The field has moved: Qwen2.5-VL, SmolVLM2, InternVL2.5, and Gemma 3 vision are all
now supported in llama.cpp and fit in the device budget. This campaign measures them all
under identical conditions before committing the rewrite to a new spine.

Zero-shot results matter as a prior; fine-tuned results are the actual thesis number. A
small fast model that fine-tunes to parity beats a large slow model with a better zero-shot
floor. Both measurements are recorded.

---

## Candidate models

| ID | Model | HF repo (GGUF) | Rec. quant | Model | mmproj | Total |
|---|---|---|---|---|---|---|
| **A** | Qwen2.5-VL-3B | `ggml-org/Qwen2.5-VL-3B-Instruct-GGUF` | Q8_0 | 3.29 GB | 0.85 GB | 4.14 GB |
| **B** | Qwen2.5-VL-7B | `ggml-org/Qwen2.5-VL-7B-Instruct-GGUF` | Q4_K_M | 4.68 GB | 0.85 GB | 5.53 GB |
| **C** | SmolVLM2-2.2B | `ggml-org/SmolVLM2-2.2B-Instruct-GGUF` | Q8_0 | 1.93 GB | 0.59 GB | 2.52 GB |
| **D** | InternVL2.5-4B | `ggml-org/InternVL2_5-4B-GGUF` | Q8_0 | 3.61 GB | 0.34 GB | 3.95 GB |
| **E** | Gemma 3 4B | `ggml-org/gemma-3-4b-it-GGUF` | Q8_0 | 4.13 GB | 0.81 GB (F16 only) | 4.94 GB |

Model B (7B) is the only tight fit — a load+RAM smoke test gates it before eval time is
committed. All others have comfortable headroom.

---

## Runtime

**llama.cpp:** rebuild at `27c8bb4f63ad9f20bf5901067810a4be5ffe20c4` (release b9829,
2026-06-28). This is the first commit that covers all five candidates via the `libmtmd`
multimodal framework (merged April–May 2025). Build flags unchanged from v2/v3:

```bash
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87
cmake --build build --config Release -j$(nproc)
```

CLI is now `llama-mtmd-cli` (not the old `llama-server --mmproj` pattern). This commit
replaces `57fe1f07` as the pinned runtime for all runs in this campaign and must be logged
on every run-card.

---

## Dataset

**Eval (frozen):** RefDrone well-posed val, **n=439**, same as v2/v3. The 85.2% IoU@0.25
baseline is the comparator — the val set must not change.

**Train:** `synth/results/train_corpus.jsonl` — RefDrone well-posed (n=4101) merged with
VisDrone synthetic pairs generated and IoU-filtered by the teacher pipeline in `synth/`.
See `synth/README.md` for the full pipeline. All five models are fine-tuned on this same
corpus — dataset version is a controlled variable, not a per-model variable.

---

## Phase plan

### Phase 0 — Preflight (no GPU)

| Step | What | Gate |
|---|---|---|
| 0-A | Rebuild llama.cpp at `27c8bb4f` on Jetson, verify all 5 models load and produce a bounding box on one RefDrone image | All 5 pass (or candidate dropped with rationale) |
| 0-B | Load + RAM test for model B (Qwen2.5-VL-7B Q4_K_M) — confirm it fits at max_side=1024 with KV headroom | Record peak RAM; drop to Q3_K_M if over budget |
| 0-C | Dataset audit — check whether RefDrone train can be expanded under the same well-posed filter; decide on VisDrone augmentation | Final train corpus size and composition committed before Phase 1 |

### Phase 1 — Zero-shot sweep

All 5 models, RefDrone well-posed val (n=439), same `GROUNDING_PROMPT` and `parse_bbox`/`iou`
contract as v2/v3. Greedy decode. Record per model:

- Parse rate (%)
- IoU@0.25 (%)
- Mean IoU
- Tokens/s on Jetson (15 W locked)

No fine-tuning yet. This is the prior.

### Phase 2 — Fine-tuning

Same LoRA recipe as v2 Phase 3 (r=16/α=32, `q/k/v/o_proj`, vision frozen, lr 2e-4,
3 epochs, effective batch 16). Same final training corpus from Phase 0-C. Run on the RTX
3090 (local), one run per candidate. Record:

- Training loss curve
- In-loop val IoU (n=200, per epoch)
- GPU-hours consumed

### Phase 3 — Post-finetune eval

Each fine-tuned checkpoint exported to GGUF (F16 + Q8_0 + mmproj), scored on RefDrone
well-posed val (n=439) on Jetson. Same contract as Phase 1 for direct comparison. Record:

- Parse rate, IoU@0.25, mean IoU, tokens/s
- Δ from zero-shot (Phase 1 → Phase 3)
- Δ from v2/v3 baseline (85.2%)

### Phase 4 — Winner selection and deployment

Rank candidates by **fine-tuned IoU@0.25 × tokens/s** (Pareto front). Document the
tradeoff. Deploy the winner as the recommended spine for the rewrite. A candidate that is
≥85.2% IoU and faster than the v2/v3 spine is a clear upgrade; below that threshold,
document the gap and its implications for the thesis.

---

## Results index

| Phase | File | Status |
|---|---|---|
| 0-A Smoke tests | `results/phase0-smoke-tests.md` | pending |
| 0-B RAM test (model B) | `results/phase0-ram-test-7b.md` | pending |
| 0-C Dataset audit | `results/phase0-dataset.md` | pending |
| 1 Zero-shot sweep | `results/phase1-zero-shot.md` | pending |
| 2 Fine-tuning runs | `results/phase2-finetune/` | pending |
| 3 Post-finetune eval | `results/phase3-post-finetune.md` | pending |
| 4 Winner + deployment | `results/phase4-winner.md` | pending |

---

## Baseline to beat

| Metric | v2/v3 value | Source |
|---|---|---|
| IoU@0.25 (deployed, Jetson) | **85.2%** | `results/2026-06-25-roi-crop-anchor` |
| Spine | Qwen2-VL-2B Q8_0 | Phase 4 deploy |
| llama.cpp commit | `57fe1f07` | v2/v3 pinned |
| Train data | RefDrone well-posed, n=4101 | Phase 3 |
| Val data | RefDrone well-posed, n=439 | Frozen |
