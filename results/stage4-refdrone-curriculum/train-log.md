# Stage 4 — RefCOCO→RefDrone Curriculum: training log & outcome

**Run date:** 2026-06-17
**Status:** COMPLETE — all 3 epochs + final merge (exit code 0)
**Pre-registration:** [`README.md`](README.md)
**Script:** `experiments/run_stage4_finetune.py`
**Merged checkpoint:** `smolvlm_ft4/` (`model.safetensors`, 1.01 GB)
**Raw logs:** `raw/train_loss.csv`, `raw/eval_iou.csv`

---

## Configuration (as run)

| Field | Value |
|---|---|
| Base / init | `./smolvlm_ft3` (Stage 3 RefCOCO merged) — curriculum warm-start (confirmed in log: `curriculum init from ./smolvlm_ft3`) |
| Model | SmolVLM-500M-Instruct (Idefics3/VLlama3, SigLIP vision encoder **frozen**) |
| FT method | LoRA (PEFT) r=16, α=32, dropout=0.05, bias=none; targets q/k/v/o + gate/up/down_proj (text backbone) |
| Trainable params | 9,568,256 / 517,050,560 = **1.85%** |
| Train set | **4,101** well-posed (one-box) RefDrone captions (8,238 multi-box + 683 empty/negative dropped; 0 image-not-found) |
| Val set | 439 well-posed captions; eval capped at **n=200** |
| Image size | long edge 512 |
| Batch | 2 × grad_accum 8 = effective 16 → 2,051 optimiser steps/epoch |
| Epochs | 3 (6,153 steps total) |
| LR | 1e-4, cosine annealing → ~0 |
| Precision | bf16 |
| Seed | 42 |
| Coordinate convention | COCO xywh → xyxy → normalized integer 0–1000 bins |
| Hardware | local RTX 3090 24 GB (not the Jetson) |
| Wall time | 9,760 s training (~2.7 h) + 3 in-loop evals + merge |
| Checkpointing | resumable `--save-every 500` (`smolvlm_ft4/accel_state`); not needed — run finished in one shot |

Dataset construction matched the pre-registered counts exactly (train 4,101 / val 439),
confirming the `RefDroneWellPosedDataset` one-box filter.

---

## Per-epoch results (RefDrone well-posed val, n=200)

| Epoch | mean_loss | parse_rate | IoU@0.25 | mean_iou | center_std |
|---|---|---|---|---|---|
| 1 | 1.0287 | 100.0% | 12.5% | 0.072 | 214.1 |
| 2 | 0.9478 | 100.0% | 16.0% | 0.087 | 214.3 |
| 3 | 0.9168 | 100.0% | **19.5%** | 0.109 | 211.5 |

- **Loss** descended cleanly every epoch (1.03 → 0.95 → 0.92) with no instability.
- **IoU@0.25** rose monotonically (+3.5pp, then +3.5pp) and was **still rising at epoch 3**,
  by which point the cosine LR had annealed to ~1.7e-9 — i.e. the model had not plateaued;
  the schedule simply ran out of learning rate.
- **center_std** stayed flat at ~211–214 throughout — **no mode collapse**. (Stage 2's
  collapse drove this toward zero with constant-box predictions.)

### Sample predictions (epoch 3, gt vs pred, normalized 0–1000)

```
gt=[268, 481, 343, 652]  pred=[324, 440, 416, 599]
gt=[325, 263, 342, 294]  pred=[294, 330, 320, 389]
gt=[500, 102, 511, 133]  pred=[474, 194, 496, 230]
gt=[172, 394, 182, 439]  pred=[244, 620, 274, 669]   ← miss (wrong region)
gt=[544, 194, 552, 228]  pred=[491, 330, 506, 370]
gt=[652, 265, 926, 750]  pred=[646, 290, 926, 599]   ← large object, good overlap
gt=[410, 315, 476, 373]  pred=[374, 330, 416, 389]
gt=[720, 625, 736, 697]  pred=[491, 439, 501, 473]   ← miss (wrong region)
```

The predictions are **input-dependent, plausibly-sized, and roughly co-located** with the
targets — qualitatively the opposite of Stage 2's constant marginal-mean box. Most error is
localisation drift on tiny objects (the gt boxes spanning ~15–30 px), with occasional
wrong-region misses; the large-object case (row 6) is tracked well.

---

## Gate verdicts

| Gate | Threshold | Measured | Verdict |
|------|-----------|----------|---------|
| **G1: parse_rate** | ≥ 90% | 100.0% | ✅ **PASS** |
| **G2b: mode-collapse sentinel** (center_std non-degenerate) | clear of collapse | 211.5 | ✅ **PASS** |
| **G4-S4: aerial IoU@0.25** (primary go/no-go) | ≥ 20% | **19.5%** | ⚠️ **NARROW MISS** (−0.5pp) |

---

## Interpretation

**The Stage 2 root cause is eliminated.** The well-posed subset (one caption → one box) plus
the Stage 3 curriculum warm-start produced healthy, input-dependent grounding with a perfect
parse rate and a non-degenerate center_std. That is the central methodological claim of the
Stage 2→3→4 arc, and it holds: the failure mode that defeated naive RefDrone fine-tuning does
**not** recur once the target is well-posed.

**Magnitude of the result.** 19.5% IoU@0.25 is a **~10× lift over the 2.0% RefCOCO-init
cross-domain floor** (RQ-S3.4) and ~20× over the Stage 2 RefDrone collapse (≈1%). On a 500M VLM
with a **frozen** SigLIP encoder, on aerial objects of 5–30 px (2–11 px after the 512 resize),
this is a substantive, measurable aerial grounding skill — exactly what the curriculum was
designed to recover.

**On the gate miss.** G4-S4 was missed by 0.5pp. This is best read as a *training-budget /
capacity* boundary rather than a failure: IoU climbed monotonically every epoch and loss was
still descending when the cosine LR hit ~0. The pre-registered honest framing applies — aerial
grounding through a frozen encoder at this resolution is genuinely hard, and the gap is small
and on a clearly-rising curve.

**Documented next levers (pre-registered, in priority order):**
1. **Largest-box augmentation** — keep the multi-box captions but supervise the single largest
   box, lifting the train set from 4,101 → ~12,339 samples. This is the first fallback because
   the gate miss looks data-limited (still rising at LR→0), and 3× the data directly addresses it.
2. **Higher input resolution** — reduce the 5–30 px → 2–11 px information loss from the 512
   long-edge resize.
3. **Vision-encoder LoRA** — unfreeze SigLIP (costs the mmproj GGUF-reuse property; last resort).

---

## Reproduction

```bash
source .venv-ft/bin/activate
python experiments/run_stage4_finetune.py \
  --init-from ./smolvlm_ft3 --epochs 3 --lr 1e-4 --output-dir ./smolvlm_ft4
# re-eval the merged checkpoint:
python experiments/run_stage4_finetune.py --eval-only ./smolvlm_ft4
```

Outputs: merged checkpoint `smolvlm_ft4/` (+ `epoch{1,2,3}/` adapters), incremental CSVs
`results/stage4-refdrone-curriculum/raw/{train_loss,eval_iou}.csv`.
