# Phase 3 — Config-driven LoRA fine-tune (RefDrone aerial grounding)

**Date:** 2026-06-17 / 2026-06-18 (train run + full-val eval)
**Branch:** `v2/principled-rebuild`
**Spine:** Qwen2-VL-2B-Instruct (Phase 0c) · **Data:** RefDrone well-posed (Phase 1) · **Resolution:** `max_side=1024` (Phase 2)
**Status:** ✅ **PASS** — gate cleared decisively, without any reserved lever.

## Pre-registration (what / why)

Phase 3 is the single config-driven LoRA loop (`grounding/train/trainer.py` +
`grounding/train/config.py`) that replaces the Part-I per-stage script forks. Everything
that varied across Part-I Stages 2/3/4 (model, data mix, lr/epochs, resolution, LoRA
hyperparameters) is captured by one `TrainConfig` instance, so a run is fully described by
its config and experiments differ only by config — no diverging forks.

**Research questions**

- **RQ-3.1 (gate):** Does the Phase-0/1/2 stack — Qwen2-VL-2B + RefDrone well-posed +
  `max_side=1024` — clear the standing aerial gate **IoU@0.25 ≥ 20%** after a LoRA
  fine-tune? (Part-I Stage 4 narrowly *missed* the same target at 19.5%.)
- **RQ-3.2 (health):** Is the output non-degenerate — `parse_rate ≥ 90%` and `center_std`
  far above the ~61 marginal-mean collapse floor that killed Part-I Stage 2?
- **RQ-3.3 (decomposition):** How much of the result is resolution (Phase-2 base 1024 =
  30.3% zero-shot) vs the fine-tune on top?

**Controlled variables** — verbatim `GROUNDING_PROMPT` and `parse_bbox`/`iou`/`center_std`
metric from `grounding/contract.py`; seed 42; bf16; greedy decode at eval; the same
RefDrone well-posed split (4101 train / 439 val) audited in Phase 1; the same `max_side=1024`
input resize used for both the collate transform and the in-loop eval.

**Config** (`TrainConfig`, manifest `runs/20260617T212559Z`): epochs 3, lr 2e-4 (the
validated Part-I Stage-3 RefCOCO-PASS value), batch_size 2 × grad_accum 8 = **effective
batch 16**, LoRA **r=16 / α=32 / dropout=0.05** on the LLM attention+MLP projections
(`q,k,v,o,gate,up,down_proj`), **vision tower frozen by construction** (18.5 M trainable =
0.83% of params). No warm-start (`init_from=None`). Reserved levers **not** used:
`largest_box_aug` (off) and `max_side=1280`.

## Results

**In-loop eval** (RefDrone well-posed val, n=200, greedy, per epoch) — `eval_iou.csv`:

| Epoch | parse | IoU@0.25 | mean_iou | center_std | mean train loss |
|---|---|---|---|---|---|
| 1 | 100.0% | 63.0% | 0.469 | 212.3 | 0.649 |
| 2 | 100.0% | 65.0% | 0.494 | 224.3 | 0.580 |
| 3 | 100.0% | 65.0% | 0.497 | 226.6 | 0.522 |

**Authoritative full-val eval** (RefDrone well-posed val, **n=439**, greedy, final merged
checkpoint) — directly comparable to the Phase-2 base ladder (also n=439):

| Model | max_side | n | parse | **IoU@0.25** | mean_iou | center_std |
|---|---|---|---|---|---|---|
| Qwen2-VL-2B **base** (Phase 2) | 1024 | 439 | 91.8% | 30.3% | 0.202 | 192.0 |
| Qwen2-VL-2B **+ LoRA (Phase 3)** | 1024 | 439 | **100.0%** | **59.5%** | **0.451** | **215.2** |

Train loss fell monotonically 0.857 → ~0.49 over 3 epochs (6153 steps, ~6550 s wall).
Merged checkpoint: `runs/v2/phase3-refdrone-1024/` (per-epoch adapters in `epoch{1,2,3}/`).

## Analysis

- **RQ-3.1 — PASS, decisively.** 59.5% IoU@0.25 on the full val is **~3.0× the gate** (20%)
  and **~3.1× Part-I Stage 4's 19.5%** on the same aerial task. The gate was already cleared
  at **epoch 1** (63% in-loop), so neither reserved lever (`largest_box_aug`, `max_side=1280`)
  was needed.
- **RQ-3.2 — healthy.** parse_rate **100%** (full val), and `center_std` 215 (full val) /
  rising 212 → 227 (in-loop) — ≈3.5× above the ~61 collapse floor and *increasing* with
  training, the exact opposite of the Stage-2 marginal-mean collapse signature. The
  fine-tune also *fixed* the base model's parse leakage (91.8% → 100%): the ~8% of base
  outputs that wrapped prose around the JSON are gone.
- **RQ-3.3 — decomposition.** The 19.5% → 59.5% gain over Part-I decomposes cleanly into two
  pre-registered, independently-measured levers: **resolution** (512 → 1024 lifts the *base*
  model 4.1% → 30.3% zero-shot, Phase 2) and **the LoRA fine-tune** (30.3% → 59.5% on top,
  this phase). Resolution and fine-tuning each roughly double the score; together they ~3×
  Part-I. This is the central v2 result: the Part-I miss was not a training failure but a
  resolution-starved setup, and a clean well-posed target + adequate resolution + a single
  honest LoRA loop clears the bar with large margin.
- **In-loop vs full-val gap** (65.0% n=200 vs 59.5% n=439) is the expected small-sample
  optimism of the held-back eval subset; the n=439 number is the one carried forward.

## Decisions

See `DECISIONS.md` (Part II) entry **2026-06-18T00:30 — Phase 3 PASS**. In short: accept the
well-posed / 1024 / lr-2e-4 / 3-epoch config as the v2 trained spine and proceed to Phase 4
(export & deploy) with the **HF full-val 59.5% as the fidelity reference** the deployed GGUF
must land within the Phase-0 budget of.

## Reproduce

```bash
source .venv-ft/bin/activate
# train (RTX 3090, ~1.8 h):
python -m grounding.train.trainer --image-size 1024
# authoritative full-val eval of the merged checkpoint:
python -m grounding.train.trainer --eval-only runs/v2/phase3-refdrone-1024 --image-size 1024 --eval-n 439
```

Manifest: `runs/20260617T212559Z/` (config + eval_history + full_val). Artifacts under
`runs/v2/phase3-refdrone-1024/`: `eval_iou.csv`, `train_loss.csv`, per-epoch adapters,
merged weights (gitignored).
