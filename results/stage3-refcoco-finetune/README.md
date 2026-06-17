# Stage 3 — Fine-tuning SmolVLM-500M for Referring-Expression Grounding (RefCOCO)

**Pre-registered:** 2026-06-16
**Campaign status:** SETUP → TRAINING
**Script:** `experiments/run_stage3_finetune.py`
**Supersedes:** Stage 2 (`results/stage2-finetune/`), which FAILED gate G2 (IoU@0.25 = 1%, mode collapse).

---

## Motivation

Stage 2 fine-tuned SmolVLM-500M on RefDrone (aerial referring expressions) + VisDrone
images using attention-only text LoRA and **raw resized-pixel** coordinate targets. It
passed the format gate (parse_rate 100%) but failed the spatial gate catastrophically
(IoU@0.25 = 1%, mean_iou 0.008). Post-hoc inference confirmed **mode collapse**: the model
emitted a nearly constant box (~`[223,111,229,120]`) regardless of image or caption — four
different captions on the *same* image produced the *identical* prediction.

The Stage 2 train-log diagnosed a single root cause (frozen vision encoder). On closer
analysis the failure is **two stacked problems**, and Stage 3 fixes both plus adds capacity:

### Root cause 1 — ill-posed targets (the dominant cause)
RefDrone is a **one-caption → many-boxes** dataset: a single referring expression
("the cars") maps to ~3.8 boxes on average. Stage 2 expanded *one annotation = one sample*,
so the model repeatedly saw the same (image, caption) paired with *different* boxes. The
loss-minimising solution for an ambiguous target is exactly the marginal-mean box — i.e.
mode collapse is the *correct* response to an ill-posed objective. No amount of vision
fine-tuning fixes a target that is genuinely ambiguous.

### Root cause 2 — raw resized-pixel coordinates on tiny objects
VisDrone objects are 5–30 px in the 512-px resized frame. Stage 2 asked the text backbone
to regress exact pixel coordinates of tiny objects through a frozen visual representation —
near-impossible at 1 epoch.

### Stage 3 fixes
1. **Dataset → RefCOCO** (`jxu124/refcoco`, built on COCO train2014). RefCOCO is the
   *inverse*: **many captions → one box** (each ref group has several phrases, all describing
   the *same single* large COCO object). Expanding captions → samples is now **well-posed**.
   This directly removes root cause 1.
2. **Coordinates → normalized 0–1000 integer bins** (the PaliGemma / Florence-2 convention),
   resolution-independent. Combined with RefCOCO's large objects, this removes root cause 2.
3. **LoRA → attention + MLP** (`q,k,v,o,gate,up,down`) instead of attention-only, for more
   adaptation capacity in the text backbone. **Vision encoder stays frozen** (deliberate —
   preserves reuse of the existing `mmproj-SmolVLM-500M-Instruct-f16.gguf` for GGUF export;
   see Decisions).
4. **Unified prompt** shared verbatim across training, `run_grounding_probe.py`, and
   `run_phase_c.py`, so train/inference never diverge.

> **Scope note (thesis honesty):** RefCOCO is *ground-level* COCO imagery, not aerial. Stage 3
> therefore tests whether SmolVLM-500M can be taught the **grounding skill + coordinate
> protocol at all** under a well-posed objective. It is a methodological correction and a
> capability ceiling probe, NOT a drop-in aerial model. The aerial-domain gap (Phase A on
> VisDrone, Phase C in Gazebo) is measured separately and expected to show a domain-shift
> penalty — that penalty is itself a thesis result.

---

## Research questions

| ID | Question | Pass criterion | Instrument |
|----|----------|---------------|-----------|
| **RQ-S3.1** | Does a well-posed grounding objective (RefCOCO + normalized coords + attn+MLP LoRA) avoid the Stage 2 mode collapse? | center_std ≫ Stage 2 (non-degenerate spread) AND IoU@0.25 ≥ 30% on RefCOCO val | in-loop `evaluate()` on RefCOCO val (n=200) |
| **RQ-S3.2** | Does the fine-tuned model emit a valid JSON bbox in ≥ 90% of calls? | parse_rate ≥ 90% | in-loop `evaluate()` |
| **RQ-S3.3** | Does the skill survive GGUF Q8_0 export (HF↔GGUF parity)? | ΔIoU@0.25 ≤ 5pp HF vs GGUF Q8_0 | Phase A probe HF vs Jetson GGUF |
| **RQ-S3.4** | How large is the aerial domain-shift penalty? | report IoU@0.25 on VisDrone Phase A probe (descriptive, no pass bar) | `run_grounding_probe.py` with FT GGUF |
| **RQ-S3.5** | Does the FT model change Phase C Branch-2 valid_rate / px_err vs the zero-shot baseline? | report valid_rate + mean px_err (descriptive) | `run_phase_c.py --vlm-model <FT>` |

---

## Decision gates

| Gate | Threshold | Meaning if FAIL |
|------|-----------|-----------------|
| **G1: parse_rate** | ≥ 90% on RefCOCO val | format learning broken — pipeline bug |
| **G2: IoU@0.25** | ≥ 30% on RefCOCO val | grounding skill not learned even when well-posed → SmolVLM-500M capacity ceiling (a result) |
| **G2b: mode-collapse sentinel** | center_std non-degenerate (≫ a few px on the 0–1000 scale) | collapse recurred despite well-posed target → deeper architectural limit |
| **G3: GGUF parity** | ΔIoU@0.25 ≤ 5pp | quantization destroys the skill → try f16 or Q4_K_M comparison |
| **G4: aerial transfer** | descriptive only | quantifies domain gap; no gate |

G2 is the real go/no-go. If G2 passes, proceed to GGUF export + Phase A + Phase C. If G2
fails *with* healthy center_std and parse_rate, that is a clean capacity-ceiling negative
result for the 500M model (thesis content), distinct from the Stage 2 ill-posed-target
failure.

---

## Datasets

### Primary: RefCOCO — `jxu124/refcoco` (annotations) + COCO train2014 (images)
- HF repo: `jxu124/refcoco` (annotations only; **no image bytes**).
- Each row = one referring-expression group: `bbox` ([x1,y1,x2,y2] original pixels, XYXY),
  `captions` (list[str], all for the SAME box), `image_path`
  (`coco/train2014/COCO_train2014_<id>.jpg`), `raw_image_info` (JSON with width/height).
- Images: **COCO train2014** (~13 GB zip from `images.cocodataset.org`), extracted to
  `data/coco/train2014/`. Both RefCOCO train and val images live in train2014.
- Splits used: `train` (→ expanded captions, deterministic shuffle, capped to
  `--max-samples 50000`) and `validation` (200 samples for in-loop eval).
- License: COCO images CC-BY 4.0; RefCOCO annotations (UNC) research use.

### Coordinate convention (pre-registered)
Targets are normalized to integer **0–1000** bins via `_normalize_bbox`. The model never
sees pixel coordinates; resize is therefore safe and resolution-independent.

### Prompt (pre-registered, unified)
```
Locate "{target}". Return the bounding box as JSON {"bbox": [x1, y1, x2, y2]} with integer coordinates normalized from 0 to 1000.
```
Response target: `{"bbox": [x1, y1, x2, y2]}` (integers, 0–1000).

---

## Method

| Parameter | Value |
|-----------|-------|
| Base model | `HuggingFaceTB/SmolVLM-500M-Instruct` (same checkpoint as Stage 1/2) |
| FT method | LoRA (PEFT), r=16, alpha=32, dropout=0.05, bias=none |
| LoRA targets | `q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj` (text backbone) |
| Vision encoder | **FROZEN** (SigLIP) — preserves mmproj GGUF reuse |
| Image size | long edge 512 (coords normalized → safe) |
| Batch | 2 × grad_accum 8 = effective 16 |
| Epochs | 1 (50k samples) |
| LR | 2e-4, cosine annealing |
| Max seq len | 1280 (SmolVLM ~1136 image tokens + text) |
| Precision | bf16 |
| `num_workers` | 0 (processor closure not picklable) |
| Seed | 42 |
| Hardware | local RTX 3090 24 GB; **not** the Jetson |

### Controlled variables (held identical to Stage 1/2 where comparable)
Base checkpoint, image long-edge 512, Q8_0 export quant, mmproj file, Phase A probe
set (RefDrone×VisDrone val, n=50, seed=42), Phase C scenario. **Changed this stage
(the independent variables):** dataset, coordinate representation, LoRA target set.

### GGUF export pipeline (post-training)
1. `merge_and_unload()` → HF checkpoint at `./smolvlm_ft3/`.
2. `convert_hf_to_gguf.py --outtype q8_0` (llama.cpp `57fe1f0`) → `smolvlm_ft3_q8_0.gguf`.
3. SCP to `jetson:/home/jfdg/models/`, reuse existing `mmproj-SmolVLM-500M-Instruct-f16.gguf`.
4. Phase A probe (HF vs GGUF parity = G3; aerial transfer = G4).
5. Phase C Branch-2 re-run (RQ-S3.5).

---

## Reproduction

```bash
source .venv-ft/bin/activate
# images: data/coco/train2014/  (extracted from train2014.zip)
python experiments/run_stage3_finetune.py --dry-run          # verify model+LoRA+collate
python experiments/run_stage3_finetune.py                     # ~10h, 50k samples, 1 epoch
python experiments/run_stage3_finetune.py --eval-only ./smolvlm_ft3   # re-eval merged ckpt
```

Outputs: merged checkpoint `./smolvlm_ft3/` (+ `epoch1/` adapter), incremental CSVs
`results/stage3-refcoco-finetune/raw/{train_loss,eval_iou}.csv`.

---

## Decisions

### 2026-06-16 — RefCOCO over RefDrone for Stage 3
- **Decision:** Switch the fine-tuning dataset to RefCOCO (`jxu124/refcoco` + COCO train2014).
- **Alternatives:** (a) Re-run RefDrone with one-caption→one-box deduplication — still leaves
  tiny-object pixel regression + aerial-only data; (b) RefCOCO+ / RefCOCOg — larger but same
  family, RefCOCO is the canonical baseline; (c) a custom synthetic Gazebo grounding set —
  highest domain match but large engineering cost and no external validity. 
- **Reasoning:** RefCOCO's many-captions→one-box structure makes the objective well-posed,
  directly killing the dominant Stage 2 failure cause; large objects + normalized coords kill
  the secondary cause. It is the standard grounding benchmark, so results are interpretable
  against literature.
- **Tradeoff:** Ground-level, not aerial — introduces a domain gap measured as RQ-S3.4. We
  accept measuring the gap rather than eliminating it, because first we must prove the model
  can ground *at all* under a fair objective.
- **Revisit when:** G2 passes but RQ-S3.4 aerial transfer is near-zero → consider a
  RefCOCO→RefDrone(deduped) two-stage curriculum or a synthetic aerial set.

### 2026-06-16 — Keep vision encoder frozen
- **Decision:** Continue freezing SigLIP; adapt only text-backbone attn+MLP via LoRA.
- **Alternatives:** Unfreeze vision (full or vision-LoRA) — the Stage 2 log's suggested fix.
- **Reasoning:** The reframed diagnosis says the Stage 2 failure was the ill-posed target,
  not primarily the frozen encoder. Freezing preserves direct reuse of the existing mmproj
  GGUF (no vision re-export, no risk of breaking the Jetson llama.cpp mmproj path) and keeps
  trainable params small. Test the cheap, export-safe lever first.
- **Tradeoff:** If grounding needs updated spatial visual features, frozen vision caps the
  ceiling. If G2 fails with healthy parse_rate + center_std, vision-LoRA becomes the next
  experiment (Stage 4).
- **Revisit when:** G2 fails despite well-posed targets and non-degenerate center_std.
