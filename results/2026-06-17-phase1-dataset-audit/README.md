# Phase 1 — Dataset audit gate

**Part II (v2) · branch `v2/principled-rebuild` · started 2026-06-17**

The second gated phase. Before any GPU run, v2 computes the **box-per-caption** and
**object-size** distributions of every corpus and **bakes them into the canonical
schema**. The point is to make ill-posedness *visible before training*, not after.

This phase exists because of the Part-I Stage-2 failure: RefDrone is mdetr-format,
where one `(image, caption)` referring expression maps to **many** boxes (Part-I
measured a mean of 3.80). Stage 2 emitted each box as a separate sample sharing the
same caption, so the loss was minimised by predicting the **marginal-mean box** →
mode collapse (IoU@0.25 ≈ 1%, `center_std` → floor). A one-box-per-caption audit gate
would have caught this *for free, before a single GPU-hour*. Phase 1 builds that gate.

It also produces the **object-size distribution** that the Part-I post-mortem named as
the aerial IoU ceiling (binding constraint #2): VisDrone objects are 5–30 px and shrink
to 2–11 px after the 512 long-edge resize. Phase 1 measures this distribution exactly
(pre- and post-resize percentiles) so Phase 2 (resolution strategy) is chosen against
real numbers rather than a remembered range.

## Pre-registered research questions

| RQ | Question | Pass / metric | Source |
|---|---|---|---|
| **RQ-1.1** (well-posedness) | Is the aerial target well-posed once filtered to one box per caption, and how much supervision survives that filter? | Box-per-caption histogram computed for RefDrone train+val; **well-posed (exactly-one-non-empty-box, non-empty-caption) fraction** reported; the well-posed subset size is the trainable budget | `grounding.data.audit` over RefDrone mdetr JSON |
| **RQ-1.2** (object size) | What is the object-size distribution in the aerial domain, before and after the `IMAGE_SIZE=512` long-edge resize? | √area percentiles {p5,p10,p25,p50,p75,p90,p95} in px, pre- and post-resize; confirm/quantify the 2–11 px post-resize range that motivates Phase 2 | same audit |
| **RQ-1.3** (in-domain control) | Is RefCOCO (the warm-start corpus) well-posed by construction? | Box-per-caption ≈ 1 after the many-captions→one-box expansion; object sizes large (control vs aerial) | audit over `load_refcoco` |

**Gate:** the well-posed RefDrone subset is confirmed one-box-per-caption (the Stage-2
killer is excluded by construction), the trainable budget is known, and the aerial
object-size distribution (pre/post-resize) is quantified and recorded — all before any
GPU run. Then proceed to Phase 2 (resolution strategy).

## Controlled variables

- **RefDrone source:** mdetr JSON `RefDrone_{train,val}_mdetr.json`
  (`/home/gara/refdrone-annotations/`, mirrors the HF cache
  `sunzc-sunny--RefDrone`); images under `data/VisDrone2019-DET/images/{train,val}`.
- **Well-posed filter (verbatim from Part-I `run_stage4_finetune.RefDroneWellPosedDataset`):**
  group annotations by `image_id`; a box is *real* iff `not empty and bbox != [0,0,0,0]`;
  **keep only captions with exactly one real box and a non-empty caption**; multi-box
  (ill-posed) and empty/negative captions dropped. COCO xywh → xyxy → normalize 0–1000.
- **Object size:** √(w·h) in pixels for every *real* box; post-resize multiplies by
  `IMAGE_SIZE / max(img_w, img_h)` (the long-edge resize the frozen encoder sees).
- **RefCOCO control:** `load_refcoco` (already live from Phase 0), seed-42, on the
  canonical one-box samples.
- **No GPU. No model.** Pure distribution statistics; CPU-only; reproducible from the
  committed JSON + this code.

## Method / commands

```bash
source .venv-ft/bin/activate
# RefDrone train + val audit (writes a manifest under runs/<id>/):
python -m grounding.data.audit --dataset refdrone --split train
python -m grounding.data.audit --dataset refdrone --split val
# RefCOCO control:
python -m grounding.data.audit --dataset refcoco --split validation --max-samples 2000
```

## Results

**Run 2026-06-17, CPU-only, `.venv-ft`.** Audit = pure annotation statistics over the
mdetr JSON (no model, no GPU, no images required for the raw view). Manifests:
`runs/20260617T173529Z-audit-refdrone-train`, `…-refdrone-val`,
`runs/20260617T173532Z-audit-refcoco-validation`.

### RQ-1.1 — well-posedness (box-per-caption) ✅ the Stage-2 sentinel reproduces

| Split | Captions (pre-filter) | Real boxes | **Mean boxes/caption** | **Well-posed (=1 box)** | Trainable budget (images on disk) |
|---|---|---|---|---|---|
| RefDrone **train** | 12 339 | 46 874 | **3.80** | 4 101 (**33.2%**) | **4 101** (0 missing) |
| RefDrone **val** | 1 421 | 4 734 | **3.33** | 439 (**30.9%**) | **439** (0 missing) |
| RefCOCO val (control) | 2 000 | 2 000 | **1.00** | 2 000 (**100%**) | 2 000 |

The RefDrone train mean of **3.80 boxes/caption reproduces the Part-I figure exactly** —
the audit gate would have flagged the Stage-2 ill-posed target *for free, before a single
GPU-hour*. Only **~⅓** of aerial captions are well-posed; the long tail is extreme (one
train caption carries **242** boxes). `assert_well_posed` (min 0.95) **FAILS on the raw
corpus (0.332)** and **PASSES on the one-box-filtered subset (1.000)** — the gate works in
both directions. The well-posed loader (`load_refdrone`) recovers the full one-box bucket
with **zero missing images** (train 4101, val 439), so the trainable budget = the histogram
`1` count exactly.

### RQ-1.2 — object size, pre/post 512 long-edge resize ✅ constraint #2 quantified

√(w·h) in pixels per real box. Post-resize = ×`512/max(img_w,img_h)` (the frozen-encoder input).

| Split | view | p5 | p10 | p25 | p50 | p75 | p90 | p95 |
|---|---|---|---|---|---|---|---|---|
| RefDrone train | pre | 17.3 | 20.8 | 29.5 | 47.3 | 76.8 | 115.3 | 149.3 |
| RefDrone train | **@512** | **6.0** | **7.2** | **10.2** | **15.9** | 25.4 | 38.6 | 49.7 |
| RefDrone val | @512 | 5.5 | 6.5 | 9.4 | 14.6 | 23.8 | 35.9 | 44.7 |
| RefCOCO val (control) | @512 | 106.9 | 116.1 | 136.4 | **172.0** | 224.4 | 281.6 | 327.2 |

The Part-I "2–11 px after resize" claim is **confirmed and sharpened**: the aerial
**bottom quartile is 6–10 px** post-resize (p5≈6, p25≈10) with a **median of ~16 px** — an
order of magnitude smaller than the RefCOCO control median (**172 px**, ~11× larger). This
is binding constraint #2 in numbers, and it is what Phase 2 (resolution strategy) must beat.

### RQ-1.3 — RefCOCO control ✅ well-posed by construction

100% one-box (the many-captions→one-box expansion is inherently well-posed) and objects are
large (median √area 208 px pre / 172 px post-resize). Confirms the audit machinery and isolates
the aerial domain — *not* the contract — as the source of both the box-per-caption and the
object-size problems.

**Gate ✅ — Phase 1 complete.** The well-posed RefDrone target is one-box-per-caption by
construction (the Stage-2 killer is excluded), the trainable budget is known (**4 101 train /
439 val**), and the aerial object-size distribution is quantified pre/post-resize. The two
numbers that gate downstream work: **only 33% of captions are usable** (small supervision
budget → favours warm-start from RefCOCO + the `largest_box_aug` lever) and **median object
≈16 px / bottom-quartile 6–10 px at 512** (resolution is the dominant lever). → Phase 2.

## Decisions

_(see DECISIONS.md Part II — Phase 1 entry)_
