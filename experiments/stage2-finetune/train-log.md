# Stage 2 Fine-tuning: Training Log

**Campaign:** Stage 2 — LoRA fine-tuning of SmolVLM-500M-Instruct on RefDrone grounding data  
**Date:** 2026-06-15 (started) / 2026-06-16 (completed)  
**Device:** Local GPU (training host, not Jetson)  
**Script:** `runners/run_stage2_finetune.py`  
**Raw log:** `experiments/stage2-finetune/raw/train_stdout.log`

---

## Configuration

| Parameter | Value |
|-----------|-------|
| Base model | `HuggingFaceTB/SmolVLM-500M-Instruct` |
| Model type | `SmolVLMForConditionalGeneration` (idefics3 arch) |
| Total params | 511,643,840 |
| LoRA r / alpha | 16 / 32 |
| LoRA target modules | `q_proj, k_proj, v_proj, o_proj` (text backbone) |
| Trainable params | 4,161,536 (0.81%) |
| Dataset | RefDrone MDETR JSON + VisDrone 2019-DET images |
| Train samples | 46,874 non-empty annotations |
| Val samples | 200 (from 4,734 non-empty, capped for speed) |
| Batch size | 2 (grad_accum=8 → effective batch 16) |
| Epochs | 1 |
| Steps | 23,437 |
| Learning rate | 2e-4 (cosine schedule) |
| Max seq length | 1,280 tokens |
| Precision | bf16 |
| `num_workers` | 0 (processor closure not picklable across workers) |

## Training progress

Steps logged every 50 steps. Loss column is per-step (not smoothed).

| Step | Loss | LR | Wall time |
|------|------|-----|-----------|
| 0 | 1.7110 | 2.00e-04 | 3s |
| 50 | 1.1171 | 2.00e-04 | 69s |
| 100 | 0.8574 | 2.00e-04 | 136s |
| 500 | 1.0882 | 2.00e-04 | 676s |
| 1000 | 0.9103 | 1.99e-04 | 1352s |
| 2000 | 0.8764 | 1.96e-04 | 2686s |
| 3000 | 0.9887 | 1.92e-04 | 4048s |
| 4500 | 0.8836 | 1.82e-04 | 6085s |
| 10000 | — | — | ~13520s |
| 20000 | — | — | ~27040s |
| 22400 | 0.6721 | 9.56e-07 | 31263s |
| 23400 | 0.7053 | 9.20e-10 | 32673s |

Full step-by-step log: `experiments/stage2-finetune/raw/train_stdout.log`  
Full step loss CSV: `experiments/stage2-finetune/raw/train_loss.csv`

## Final training metrics

| Metric | Value |
|--------|-------|
| Final step loss (step 23400) | 0.7053 |
| Epoch 1 mean loss | 0.8341 |
| Min step loss observed | 0.6225 (step 22700) |
| Total wall time | 32,723s (~9.1 hours) |
| Steps completed | 23,437 / 23,437 (100%) |
| Training exit code | 0 (clean) |
| CSV output bug | CSVs written to `data/VisDrone2019-DET/results/…` instead of `experiments/stage2-finetune/raw/`; moved post-hoc (path resolved relative to visdrone_dir instead of repo root — bug in `iou_csv_path = Path("experiments/…")` when cwd was different) |

## Epoch 1 evaluation (end-of-epoch eval on 200 val samples)

| Metric | Value | Gate | Outcome |
|--------|-------|------|---------|
| Parse rate (valid JSON bbox) | **100.0%** | G1: ≥ 30% | **PASS** |
| IoU@0.25 rate | **1.0%** | G2: ≥ 20% | **FAIL** |
| Mean IoU | **0.008** | — | near-zero |

Eval CSV: `experiments/stage2-finetune/raw/eval_iou.csv`

## Decision gates (from pre-registration)

| Gate | Threshold | Result | Outcome |
|------|-----------|--------|---------|
| G1: parse_rate | ≥ 30% | 100% | **PASS** |
| G2: IoU@0.25 | ≥ 20% | 1% | **FAIL** |
| G3: GGUF ΔIoU | ≤ 5pp | N/A (G2 failed) | deferred |
| G4: Phase C valid_rate + px_err | ≥ 30% AND < 100px | N/A (G2 failed) | deferred |

## Root cause diagnosis: mode collapse (confirmed 2026-06-16)

Post-training inference on 5 val samples revealed the model predicts a nearly constant
bounding box regardless of image content or caption:

```
[0] gt: [225,145,292,213]  pred: {"bbox": [221,117,236,140]}  IoU: 0.0000
[1] gt: [167,276,176,286]  pred: {"bbox": [223,111,229,120]}  IoU: 0.0000
[2] gt: [134,270,145,280]  pred: {"bbox": [223,111,229,120]}  IoU: 0.0000
[3] gt: [100,269,109,282]  pred: {"bbox": [223,111,229,120]}  IoU: 0.0000
[4] gt: [87,269,97,280]    pred: {"bbox": [223,111,229,120]}  IoU: 0.0000
```

Items 1–4 are different RefDrone captions on the same VisDrone image; all get the
exact same prediction. The model learned the output format (100% parse rate) but
ignores image/caption content.

**Why this happened:**

1. **Frozen vision encoder**: LoRA targets only the text attention layers (`q_proj`,
   `k_proj`, `v_proj`, `o_proj`). The SigLIP vision encoder is completely frozen.
   The spatial feature representations that map "object at location X,Y" → visual
   tokens cannot be updated. The text backbone has no gradient path to learn which
   visual tokens correspond to which locations.

2. **Tiny objects, high spatial precision required**: VisDrone aerial objects are
   typically 5–30 px wide in the 512px-max-side resized images. Predicting exact
   pixel coordinates requires precise visual localization — far beyond what frozen
   vision features + 1-epoch text LoRA can learn.

3. **Mode collapse under teacher forcing**: With frozen vision features, the optimal
   solution for a 1-layer-of-attention text adaptor is to predict the marginal mean
   of the training bbox distribution. The model converged to outputting a box near
   the image center (≈[223,111,229,120] in 512×288 space) which minimises average
   loss without attending to image content.

**What parse_rate=100% tells us**: The text backbone successfully learned the output
*format* (JSON with `"bbox"` key, 4 integers). This is a positive signal — the LoRA
training loop, data pipeline, and label masking are all functioning correctly. The
failure is spatial, not syntactic.

**Thesis interpretation**: This is a meaningful negative result demonstrating the
limits of text-only LoRA for visual grounding tasks. To achieve spatial improvement,
options include: (a) unfreeze the vision encoder (full fine-tune or vision-LoRA),
(b) use a model with coordinate-aware visual tokens (e.g. SpatialVLM), or (c) use
significantly more training data and epochs.

## Anomalies / notes

- **AutoProcessor substitution:** `SmolVLMProcessor.from_pretrained()` fails in transformers 4.57.6 with `video_processor_type` error; replaced with `AutoProcessor` returning `Idefics3Processor` — functionally identical.
- **max_length=1280:** SmolVLM image tokens expand to ~1136 per image (17 tiles × 64 + special tokens). Setting max_length=512 caused `end_id_pos=None` TypeError in label masking. Fixed to 1280.
- **num_workers=0:** Processor closure cannot be pickled across DataLoader worker processes. Running in main process.
- **Loss behaviour:** Rapid drop from 1.71 → ~0.86 in first 100 steps, then slow cosine decay to 0.83 mean. LR annealed to near-zero by step 23,000. No divergence or NaN observed.
- **merged checkpoint tokenizer bug:** `AutoProcessor.from_pretrained("./smolvlm_ft")` fails with `AttributeError: 'list' object has no attribute 'keys'` — `extra_special_tokens` serialized as list instead of dict during `save_pretrained()`. Workaround: load processor from original `MODEL_ID` and weights from checkpoint. Not a problem for GGUF conversion (which uses the weights only).
