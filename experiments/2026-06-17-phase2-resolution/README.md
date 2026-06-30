# Phase 2 — Resolution strategy

**Part II (v2) · branch `v2/principled-rebuild` · started 2026-06-17**

The third gated phase. Phase 1 quantified binding constraint #2 in numbers: aerial
objects in the RefDrone well-posed set have a **median √area of ~16 px at the 512
long-edge resize, bottom quartile 6–10 px** (vs a RefCOCO control median of 172 px).
That is the tiny-object ceiling Part I never confronted head-on. Phase 2 makes the
input transform a **pre-registered, measurable variable** and chooses one strategy
**by the numbers, without training**, on the Phase-0 harness.

## The lever, and why it is a clean single variable

The v2 spine (Phase 0c) is **Qwen2-VL-2B-Instruct**, which has *native dynamic
resolution*: feeding more pixels gives the encoder more to work with on small
objects, with no architecture change. Two facts make the input long-edge size a
clean, single-variable sweep:

1. **Metric-safety.** The contract stores boxes normalized 0–1000 relative to the
   *original* image, so a whole-image resize leaves the ground-truth box invariant —
   no box remapping, no coordinate-frame change. The only thing that varies across
   the ladder is how much detail the encoder sees.
2. **No upscaling.** VisDrone originals are ~2000×1500, so every ladder arm here
   still *downscales* — higher arms simply throw away less information. No
   interpolation artifacts confound the comparison.

`HFBackend` gains a `max_side` parameter (default `IMAGE_SIZE=512`, preserving every
Phase-0/1 number); the sweep loads the model once and mutates `max_side` per arm.

**Tiling / coarse-to-fine crops are deliberately deferred** (logged in DECISIONS.md
Part II). Grounding at inference has no known target location, so tiling needs a
multi-pass run plus an ambiguous cross-tile merge — a far larger intervention than
the cheap, single-pass native-resolution lever, which must be exhausted first.

## Pre-registered research questions

| RQ | Question | Pass / metric | Source |
|---|---|---|---|
| **RQ-2.1** (resolution → IoU) | Does increasing the input long edge raise aerial grounding accuracy on the Qwen2-VL-2B **base** model (no training)? | IoU@0.25 pass-rate and mean_iou on RefDrone well-posed val, swept over {512, 768, 1024, 1280} | `grounding.resolution` ladder over `load_refdrone("val")` |
| **RQ-2.2** (parse / collapse) | Does higher resolution keep the output well-formed and input-dependent (no degenerate behaviour)? | parse_rate and `center_std` per arm; `center_std` must stay non-degenerate | same |
| **RQ-2.3** (diminishing returns) | Where does the resolution ladder plateau, so Phase 3 trains at the smallest size that captures most of the gain? | the elbow in IoU@0.25 vs max_side | same |

**Gate:** one resolution strategy (a specific `max_side`) is chosen and justified by
the measured IoU/parse/center_std tradeoff across the ladder, documented in
`experiments/` + `RESULTS.md` + `DECISIONS.md` in the same turn. Then proceed to Phase 3
(train), which trains at the chosen resolution.

## Controlled variables

- **Model:** `Qwen/Qwen2-VL-2B-Instruct` **base** (no fine-tuning) — isolates the
  resolution effect from any training effect.
- **Data:** RefDrone well-posed val = **439 samples** (Phase-1 budget), via
  `load_refdrone("val")` (seed-42 deterministic order). One real box per caption.
- **Backend:** `HFBackend` (bf16, the fidelity reference), greedy decode
  (`do_sample=False`), verbatim `GROUNDING_PROMPT`, `MAX_NEW_TOKENS=64`. Only
  `max_side` changes between arms.
- **Ladder:** input long edge ∈ {512, 768, 1024, 1280} px.
- **Scoring:** the single Phase-0 path (`contract.parse_bbox` → `contract.iou`);
  gate fraction over all 439, mean_iou over parsed only, `center_std` over parsed.

## Method / commands

```bash
source .venv-ft/bin/activate
python -m grounding.resolution \
    --model Qwen/Qwen2-VL-2B-Instruct --split val --sides 512,768,1024,1280
```

Each arm writes a `kind="eval"`, `phase="2"` manifest under `runs/<id>/` carrying
`resolution_max_side`, so every number is traceable to exact code + deps + data.

## Results

Ladder over RefDrone well-posed val (**n = 439**, Qwen2-VL-2B **base** — zero training,
HFBackend bf16 greedy, verbatim contract). Each arm = one `kind="eval"` manifest.

| max_side | parse_rate | **IoU@0.25** | mean_iou | center_std | Δ IoU@0.25 vs prev | manifest |
|---|---|---|---|---|---|---|
| 512  | 100.0% | 4.1%  | 0.031 | 129.1 | —        | `runs/20260617T190608Z` |
| 768  | 100.0% | 10.7% | 0.065 | 157.9 | +6.6 pp  | `runs/20260617T191130Z` |
| 1024 | 91.8%  | **30.3%** | 0.202 | 192.0 | **+19.6 pp** | `runs/20260617T191739Z` |
| 1280 | 92.0%  | 38.7% | 0.313 | 196.1 | +8.4 pp  | `runs/20260617T192436Z` |

**RQ-2.1 (resolution → IoU): YES, decisively.** Input long edge is *the* dominant lever.
The base model (no training) goes from 4.1% → 38.7% IoU@0.25 purely on resolution — a
**9.4× swing** with the weights untouched. This reframes Part-I's Stage-4 19.5% miss as
**resolution-starved at 512**: the same family clears the 20% gate at 1024 (30.3%) and
1280 (38.7%) *before any fine-tuning*.

**RQ-2.2 (parse / collapse): healthy throughout.** `center_std` rises monotonically
(129 → 196) — the opposite of mode collapse (Part-I collapse floor ≈61); higher
resolution makes outputs *more* input-dependent, not less. parse_rate stays ≥ 91.8%;
the small dip from 100% at ≥1024 is the model occasionally emitting prose around the
JSON on harder small-object crops, not degenerate output. Both clear the Phase-3
parse ≥ 90% / non-degenerate bars even at the base.

**RQ-2.3 (diminishing returns / elbow): the elbow is at 1024.** Marginal IoU@0.25 gains
are +6.6 pp (512→768), **+19.6 pp (768→1024, the dominant jump)**, +8.4 pp (1024→1280).
The curve has no true plateau yet (1280 still climbs in mean_iou), but **1024 captures
~78% of the 1280 IoU@0.25 ceiling** while the per-step return more than halves past it.
1024 is the smallest size on the "captures most of the gain" side of the elbow.

## Decisions

**Chosen: `max_side = 1024`** — data-driven elbow + deployment-awareness. Full rationale
(alternatives, tradeoff, revisit-when) in **DECISIONS.md Part II — 2026-06-17T20:00 Phase 2**.
Phase 3 trains at this resolution (`grounding/train/config.py` `image_size=1024`,
`resolution_strategy="resize1024"`).
