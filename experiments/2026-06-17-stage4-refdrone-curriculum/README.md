# Stage 4 — RefCOCO→RefDrone Curriculum for *Aerial* Grounding (well-posed subset)

**Pre-registered:** 2026-06-17
**Campaign status:** SETUP → TRAINING
**Script:** `runners/run_stage4_finetune.py`
**Builds on:** Stage 3 (`experiments/2026-06-16-stage3-refcoco-finetune/`), which PASSED gate G2
(RefCOCO IoU@0.25 = 82.5%) but is *ground-level* — aerial transfer measured at 2.0% (RQ-S3.4).

---

## Motivation

The thesis target domain is **aerial / drone-view** visual grounding on a Jetson Orin Nano.
The arc so far has separated *two* independent failure axes:

- **Stage 2 (FAILED, mode collapse):** text-only LoRA directly on RefDrone. Root cause =
  **ill-posed target** — RefDrone is mdetr-format where each *(image, caption)* maps to
  **many boxes** (mean 3.80 per caption). Stage 2 expanded *one annotation = one sample*, so
  the same (image, caption) was paired with different boxes; the loss-minimising answer is
  the marginal-mean box → collapse (IoU@0.25 ≈ 1%).
- **Stage 3 (PASS, but ground-level):** corrected the *objective* on RefCOCO (well-posed:
  many-captions → one box, large objects, normalized 0–1000 coords). G2 IoU@0.25 = **82.5%**,
  center_std non-degenerate. This proved the **machinery + objective are sound** — but RefCOCO
  is the wrong *domain*. Cross-domain aerial transfer is 2.0% (RQ-S3.4 floor).

So we have a model that can ground well (wrong domain) and a domain that defeated a naive
objective (right domain). **Stage 4 closes the gap with a curriculum**: initialise from the
Stage 3 RefCOCO-merged weights (which already encode single-box grounding + the coordinate
protocol) and fine-tune on RefDrone — **but only after fixing the ill-posed target that sank
Stage 2.**

### The fix: well-posed subset only (user-approved)

Train on **only the captions that have exactly one box** — the exact structural mirror of the
Stage 3 well-posed fix (one caption → one box, deterministic). This is the dominant Stage 2
root cause removed at the source, while staying in the aerial domain. It also matches the
**deployment contract**: the unified prompt, the `_parse_bbox` parser, and Phase C all expect
a single `{"bbox": [...]}` response.

Dropped: multi-box captions (the ill-posed killer) and pure-empty/negative captions.

---

## Dataset facts (verified from the mdetr JSONs, 2026-06-17)

RefDrone cache: `~/.cache/huggingface/hub/datasets--sunzc-sunny--RefDrone/snapshots/*/RefDrone_{train,val}_mdetr.json`
Images: `data/VisDrone2019-DET/images/{train,val}/<file_name>`.

mdetr structure: each `images[]` record = one referring expression (`file_name`, `width`,
`height`, `caption`, `id`); `annotations[]` link by `annotation.image_id == images[].id`,
carry `bbox` (**COCO `[x,y,w,h]`**, NOT xyxy) and an `empty` flag (`bbox==[0,0,0,0]` for
negatives).

| split | caption-instances | exactly-one-box (kept) | % | dropped (multi/empty) |
|-------|------------------:|-----------------------:|---:|---|
| train | 13,022 | **4,101** | 31.5% | ~8,238 multi-box + 683 empty |
| val   |  1,428 | **439**   | 30.7% | rest multi-box/empty |

(These counts are asserted in the verification step; the dataset class prints the live
breakdown on load.)

### Coordinate convention (unchanged from Stage 3)
COCO `[x,y,w,h]` → xyxy (`x2=x+w, y2=y+h`) → normalized integer **0–1000** bins via
`_normalize_bbox`. Resolution-independent; the model never sees pixel coordinates.

### Prompt (unchanged, unified verbatim with probe + Phase C)
```
Locate "{target}". Return the bounding box as JSON {"bbox": [x1, y1, x2, y2]} with integer coordinates normalized from 0 to 1000.
```

---

## Research questions

| ID | Question | Pass criterion | Instrument |
|----|----------|---------------|-----------|
| **RQ-S4.1** | Does the well-posed subset + curriculum init avoid the Stage 2 mode collapse on aerial data? | center_std non-degenerate AND IoU@0.25 ≥ 20% on RefDrone well-posed val | in-loop `evaluate()` (n=200) |
| **RQ-S4.2** | Does the model emit a valid JSON bbox in ≥ 90% of calls? | parse_rate ≥ 90% | in-loop `evaluate()` |
| **RQ-S4.3** | How much does curriculum init (from ft3) beat from-scratch on the same subset? | report IoU@0.25 of `--init-from MODEL_ID` control vs ft3 init (descriptive) | second training arm (optional, run only if primary passes/borderline) |

---

## Decision gates

| Gate | Threshold | Meaning if FAIL |
|------|-----------|-----------------|
| **G1: parse_rate** | ≥ 90% on RefDrone well-posed val | format learning broken — pipeline bug |
| **G4-S4: aerial IoU@0.25** (primary go/no-go) | ≥ 20% on RefDrone well-posed val | aerial grounding not learned even when well-posed + warm-started → genuine difficulty of tiny aerial objects through a frozen SigLIP (a result) |
| **G2b: mode-collapse sentinel** | center_std non-degenerate | collapse recurred despite the well-posed fix → deeper limit, not the Stage 2 cause |

**G4-S4 is the real go/no-go.** 20% is the original Stage 2 gate; clearing it from the 2.0%
RefCOCO-init cross-domain floor is a real, measurable aerial grounding skill.

**Honest framing (thesis):** aerial is genuinely hard — VisDrone objects are 5–30 px, i.e.
2–11 px after the 512 long-edge resize, fed through a *frozen* SigLIP encoder. If G4-S4 misses
with healthy parse_rate + center_std, that is a clean capacity/representation negative result
(distinct from the Stage 2 ill-posed failure), and the documented next levers are **higher
input resolution** and/or **largest-box data augmentation** (→ ~12,339 samples) and/or
**vision-encoder LoRA**.

---

## Method

| Parameter | Value | Δ vs Stage 3 |
|-----------|-------|--------------|
| Base / init | **`./smolvlm_ft3`** (Stage 3 RefCOCO merged) | curriculum warm-start (was base `SmolVLM-500M-Instruct`) |
| FT method | LoRA (PEFT), r=16, α=32, dropout=0.05, bias=none | same |
| LoRA targets | `q,k,v,o,gate,up,down_proj` (text backbone) | same |
| Vision encoder | **FROZEN** (SigLIP) | same (preserves mmproj GGUF reuse) |
| Image size | long edge 512 | same |
| Batch | 2 × grad_accum 8 = effective 16 | same |
| Epochs | **3** | was 1 (small set → more passes) |
| LR | **1e-4**, cosine annealing | was 2e-4 (lower, so curriculum init isn't clobbered) |
| Max seq len | 1280 | same |
| Precision | bf16 | same |
| Seed | 42 | same |
| Hardware | local RTX 3090 24 GB; **not** the Jetson | same |
| Train size | ~4,101 well-posed captions (all) | was 50k RefCOCO caption-box pairs |

~256 steps/epoch (4101/16) → ~768 optimiser steps total ≈ **~1 h** on the RTX 3090.

### Controlled variables (held identical to Stage 3 where comparable)
Base architecture, LoRA target set + rank, image long-edge 512, coordinate convention
(0–1000), unified prompt, seed 42, eval metric (`evaluate()` incl. center_std). **Changed this
stage (independent variables):** dataset (RefCOCO → RefDrone well-posed), init (base → ft3
curriculum), epochs (1 → 3), LR (2e-4 → 1e-4).

---

## Reproduction

```bash
source .venv-ft/bin/activate
# images: data/VisDrone2019-DET/images/{train,val}/  ; RefDrone mdetr JSON auto-resolved from HF cache
python runners/run_stage4_finetune.py --dry-run                      # verify model+LoRA+collate+JSON resolve
python runners/run_stage4_finetune.py --init-from ./smolvlm_ft3 --epochs 3 --lr 1e-4   # ~1h
python runners/run_stage4_finetune.py --eval-only ./smolvlm_ft4      # re-eval merged ckpt
```

Outputs: merged checkpoint `./smolvlm_ft4/` (+ `epoch{N}/` adapters), incremental CSVs
`experiments/2026-06-17-stage4-refdrone-curriculum/raw/{train_loss,eval_iou}.csv`.

---

## Decisions

### 2026-06-17 — Well-posed subset only (RefDrone one-box captions)
- **Decision:** Train Stage 4 on only the 4,101 train / 439 val RefDrone captions that have
  exactly one non-empty box; drop multi-box and empty/negative captions.
- **Alternatives:** (a) **largest-box augmentation** — keep multi-box captions but supervise
  the single largest box (→ ~12,339 samples), more data but a heuristic, possibly ambiguous
  target; (b) **multi-box → list output** — change the response schema to a list of boxes,
  but that breaks the single-`bbox` deployment contract shared with the probe/parser/Phase C
  and changes the task definition mid-thesis.
- **Reasoning:** The well-posed subset is the exact structural mirror of the validated Stage 3
  fix, removing the dominant Stage 2 root cause at the source, with zero change to the
  deployment contract. Cleanest controlled comparison.
- **Tradeoff:** Discards ~63% of RefDrone annotations → small train set (mitigated by the
  ft3 curriculum warm-start). If the gate fails for lack of data, (a) is the first fallback.
- **Revisit when:** G4-S4 fails with healthy parse_rate + center_std → try largest-box
  augmentation and/or higher input resolution.

### 2026-06-17 — Curriculum init from Stage 3 (ft3) rather than from base
- **Decision:** Initialise Stage 4 from the merged RefCOCO checkpoint (`./smolvlm_ft3`), train
  a fresh LoRA adapter on top at a lower LR (1e-4).
- **Alternatives:** From-scratch from base `SmolVLM-500M-Instruct` (kept available as the
  `--init-from MODEL_ID` control arm, RQ-S4.3).
- **Reasoning:** ft3 already encodes single-box grounding + the 0–1000 coordinate protocol;
  warm-starting should transfer that skill and let the small aerial set adapt the domain
  rather than re-learn grounding from zero. Lower LR avoids clobbering that init.
- **Tradeoff:** Risk of negative transfer if ground-level spatial priors hurt aerial; the
  from-scratch control quantifies this.
- **Revisit when:** RQ-S4.3 shows from-scratch ≥ curriculum → drop the warm-start.
