# Synthetic Data Generation — Teacher VLM Pipeline

**Branch:** `2026-06/vlm-sweep`  
**Started:** 2026-06-28  
**Hardware:** RTX 3090 (24 GB VRAM) — local machine  
**Feeds into:** `benchmark/` — all five candidate models are fine-tuned on the corpus
produced here.

---

## Purpose

The RefDrone well-posed training set is 4101 samples. That is enough to rank models
relatively, but a larger corpus gives more signal — especially for smaller models
(SmolVLM2-2.2B) that are more data-hungry. VisDrone has ~6,000+ aerial training images
with ground-truth detection boxes but no referring expressions. A strong teacher VLM on
the 3090 can generate `(referring expression, bbox)` pairs for those images; cross-checking
against VisDrone ground truth filters out hallucinated coordinates before they enter
training.

The result is a merged corpus (RefDrone well-posed + validated VisDrone synthetic) that
all five benchmark candidates are fine-tuned on under identical conditions.

---

## Teacher model

**Primary:** Qwen2.5-VL-7B-Instruct in BF16 (~14 GB VRAM, fits the 3090 with headroom)  
**Fallback:** Qwen2.5-VL-32B via Q4_K_M through llama.cpp (~20 GB) if 7B yield is too low

Qwen2.5-VL-7B is chosen for:
- Best bbox prediction accuracy in the ≤8B class
- Same arch family as benchmark candidates A/B, so its failure modes are well understood
- Comfortable fit — leaves 10 GB for activations and batch inference

**Note for thesis:** the teacher shares architecture with candidates A and B
(Qwen2.5-VL-3B, 7B). Synthetic data may structurally favour that family. This is
documented as a known bias; all five candidates are trained on the same corpus regardless,
so relative ranking remains valid.

---

## Source data

**VisDrone2019-DET train split** — already on disk at
`data/VisDrone2019-DET/images/train/`. Ground-truth detection boxes in VisDrone annotation
format (CSV per image: `x,y,w,h,score,category,truncation,occlusion`).

Only categories that correspond to discrete, nameable objects are used for referring
expression generation. Crowd/ignored regions (`category=0` or `score=0`) are skipped.

---

## Pipeline

### Step 1 — Candidate pair extraction

For each VisDrone train image:
- Parse ground-truth annotations; skip ignored/crowd regions
- For each valid object box, record `(image_path, gt_bbox_xyxy, category_name)`
- Filter: keep boxes where √(w·h) ≥ 10 px (below this the teacher cannot reliably
  localise; matches the aerial object-size floor from Phase 1 of v2)

Output: `experiments/candidates.jsonl` — one line per `(image, object)` pair.

### Step 2 — Teacher inference

For each candidate pair, prompt the teacher with the image and ask it to:
1. Describe the target object with a natural referring expression (colour, type, position)
2. Predict its bounding box in `[x1, y1, x2, y2]` normalised 0–1000 format (same as
   the grounding contract)

Batch inference on the 3090. Record raw teacher output per pair.

Prompt template (to be finalised in `synth/prompts.py` before running):

```
Given this aerial image, describe the {category} object and give its bounding box.
Answer in this exact format:
Referring expression: <description>
Bounding box: [x1, y1, x2, y2]
```

Output: `experiments/raw_teacher_output.jsonl`

### Step 3 — Parse and filter

Parse teacher bbox from raw output using the same `parse_bbox` from
`grounding/contract.py`. Compute IoU against the VisDrone ground-truth box.

**Acceptance threshold: IoU ≥ 0.4**

Chosen as a middle ground between two failure modes:
- Too strict (≥ 0.5, COCO standard): rejects valid teacher outputs that are spatially
  imprecise but correct — expected for a generative model predicting boxes from a
  natural-language description, especially on small aerial objects.
- Too loose (≤ 0.3): accepts outputs that are in the right region but wrong enough to
  introduce noise into training.

0.4 is a judgment call validated empirically by the yield gate (≥ 30%). If yield is
too low, drop to 0.3 and note the change in the thesis. If yield is healthy at 0.4,
it is defensible as stricter than the relaxed floor without demanding COCO-level
precision from a teacher that was never trained as a detector.

Below this the teacher has hallucinated or seriously mislocalised. Rejected pairs are
logged (not silently dropped) so yield rate is reportable.

Output: `experiments/accepted.jsonl`, `experiments/rejected.jsonl`

### Step 4 — Merge with RefDrone

Convert accepted pairs to the same format as RefDrone well-posed train (MDETR JSON
schema). Merge with the 4101 RefDrone samples. Record final corpus size and composition.

Output: `experiments/train_corpus.jsonl` — the canonical training corpus for `benchmark/`.

---

## Gates

| Gate | Criterion | Action if failed |
|---|---|---|
| Yield ≥ 30% | At least 30% of candidate pairs accepted at IoU ≥ 0.4 | Lower threshold to 0.3 and re-report, or switch to fallback teacher |
| Synthetic samples ≥ 2000 | Enough to materially augment 4101 base | If VisDrone supply is the limit, add VisDrone val split |
| Parse rate ≥ 80% | Teacher outputs parseable bbox most of the time | Revise prompt template; re-run |

---

## Results index

| Step | File | Status |
|---|---|---|
| Candidate extraction | `experiments/step1-candidates.md` | pending |
| Teacher inference | `experiments/step2-inference.md` | pending |
| Filter + yield | `experiments/step3-filter.md` | pending |
| Final corpus | `experiments/step4-corpus.md` | pending |

---

## Output consumed by benchmark

`synth/results/train_corpus.jsonl` → `benchmark/` Phase 0-C (dataset step).  
The benchmark README references this file as the canonical training corpus.
Both folders live on branch `2026-06/vlm-sweep`.
