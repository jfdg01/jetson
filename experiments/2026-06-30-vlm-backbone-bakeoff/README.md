# VLM backbone bake-off — is Qwen2-VL-2B still the right spine?

**Date:** 2026-06-30T14:03Z (pre-registration) · **Branch:** `experiment/vlm-sweep`
**Status:** **DRAFT / pre-registered** — suite + config frozen here *before* GPU hours are spent; Results/Findings/Decision filled as runs land.
**Train box:** local RTX 3090 24 GB, `.venv-ft`, python 3.12.10, torch 2.6.0+cu124, transformers 4.57.6, peft 0.19.1 (git_sha `7eb03a8` at draft).
**Deploy / latency box:** Jetson Orin Nano 8 GB @ **15 W** (`nvpmodel -m 0` + `jetson_clocks`).
**Stack-native runtime:** llama.cpp `57fe1f0` CUDA sm_87, `llama-server`, Q8_0, ngl=99. Off-stack models (see suite) measured via TensorRT/ONNX — runtime recorded per arm.
**Data:** RefDrone well-posed (4101 train / 439 val), the Phase-1 audited split. Same `grounding/contract.py` `parse_bbox`/`iou`/`center_std` metric path as every prior campaign.

## Question

The whole v2/v3 line is built on **Qwen2-VL-2B**, chosen in Part I before the small-VLM
field moved. It works (deployed Q8_0 = 62.6% IoU@0.25 whole-frame, 85.2% with ROI
re-anchor @ ≈2.0 s) but it was never *compared* against the architectures that now exist.
Given a real GPU-hour budget for fine-tuning, **which backbone gives the best
speed / accuracy / fit on aerial referring-grounding after a fine-tune?**

The decision criteria, in priority order (from the working brief):

1. **As fast as possible** — anchor wall latency on the Jetson, the binding constraint.
2. **Fits the Jetson** — ≤ ~3 GB headroom measured (2026-06-30); rarely binding, but recorded.
3. **Decent locating performance** — IoU@0.25 on RefDrone val *after* fine-tune.

## Why architecture, not size, sets the speed (the design rationale)

Output is ~10 tokens (4 ints), so **decode is free and prefill over vision tokens dominates**.
That makes the vision-token strategy — not param count — the primary speed lever. The suite
is chosen to span that axis, so the result tells us *which architecture wins*, not which Qwen
wins:

| Token strategy | tokens (typ.) | speed | small-target recall |
|---|---|---|---|
| aggressive pixel-shuffle (SmolVLM2) | ~81/tile | fastest | poor (pixels discarded) |
| tiling + pixel-shuffle (InternVL) | 256/tile | fast | good (tiles) |
| fixed-grid seq2seq (Florence-2) | ~577 | very fast | medium (fixed res) |
| fixed-res SigLIP (PaliGemma2) | 256/1024/4096 @224/448/896 | tunable | good @448+ |
| naive dynamic-res (Qwen family) | scales w/ area (~1300 @1024²) | slow hi-res | best (sees all) |

**Interaction the deployed path already exploits:** the ROI re-anchor crop makes the target
fill the frame, so a dynamic-res model's one advantage (tiny targets in full frames) only
matters on **cold acquire**. The bake-off therefore measures *both* paths (whole-frame and
ROI-crop), because a fast low-token model may lose whole-frame but win the deployed ROI path.

## Pre-registration

### Research questions

- **RQ-B.1 (winner):** After a matched LoRA fine-tune, which of the 5 contenders maximises
  RefDrone-val IoU@0.25 **per second of Jetson anchor wall**? (Pareto front, not a single number.)
- **RQ-B.2 (beat baseline):** Does any contender beat the deployed Qwen2-VL-2B on **both**
  axes — IoU@0.25 ≥ its whole-frame 63.1% / ROI 85.2% **and** anchor wall ≤ its 4.4 s
  (whole-frame) / ≈2.0 s (ROI)?
- **RQ-B.3 (compression vs recall):** Does aggressive token compression (SmolVLM2, Florence
  fixed-res) survive on tiny aerial targets *once ROI-cropped*, or does it collapse on cold
  acquire? (The central architecture hypothesis.)
- **RQ-B.4 (health):** Every arm non-degenerate — `parse_rate ≥ 90%`, `center_std` well above
  the ~61 marginal-mean collapse floor (the Part-I Stage-2 failure mode).

### The suite (5 arms, current Qwen2-VL-2B omitted = baseline)

| Arm | Model | Params | Architectural bet | REC proxy† | Runtime | FT cost |
|---|---|---|---|---|---|---|
| A | **InternVL3-2B** | 2B | tiling + pixel-shuffle generalist; best grounding/param @2B | 86.7 | llama.cpp | medium |
| B | **Qwen2.5-VL-3B** | 3B | dynamic-res, absolute-coord grounding; reuses our harness | 89.1 | llama.cpp | medium |
| C | **PaliGemma2-3B @448** | 3B | fixed-res SigLIP, purpose-built detection-FT base (`<loc>` tokens) | RefCOCO ckpts | TensorRT/ONNX | medium |
| D | **Florence-2-large** | 0.77B | tiny seq2seq detection-*native* specialist; speed ceiling | SoTA zero-shot | TensorRT/ONNX | low |
| E | **SmolVLM2-500M** | 0.5B | aggressive pixel-shuffle; speed *floor*, already tooled on-device | weak OOB | llama.cpp | lowest |

† RefCOCO-family REC accuracy (box IoU≥0.5, **natural** images) — a *ranking* proxy only.
Our task is aerial IoU@0.25; these numbers order the bench, they do **not** predict the winner.

**Pruning rationale (negative space, recorded as content):** cut Qwen3-VL-2B (redundant token
strategy with B, less mature FT recipe); cut Moondream2 (SigLIP+small-LLM detection-native =
overlaps C/D, no new axis); cut MiniCPM-V / DeepSeek-VL2 / 7B-class (8B prefill or MoE serving
cost violates criterion 1 — fit was never the constraint, speed is).

### Fine-tune method (FIXED across arms) + learning rate (SWEPT per arm)

**Method — held constant; this is the controlled baseline. Changing it breaks the comparison.**
LoRA, **bf16** (plain, not QLoRA — 2–3B fits the 3090's 24 GB; Phase-3 proved it),
**r=16 / α=32 / dropout=0.05** on the LLM attention+MLP projections, **vision tower frozen**,
**effective batch 16** (bs 2 × grad-accum 8), seed **42**, greedy eval. Verbatim `GROUNDING_PROMPT`
+ `parse_bbox`/`iou` from `grounding/contract.py`. *Why LoRA, not full FT:* Phase-3 cleared the
aerial gate with LoRA (18.5 M trainable, 0.83% of params); it isolates the variable to the
backbone and keeps a 5–6-arm sweep affordable.

**Learning rate — swept per arm, NOT fixed (deliberate).** lr is the most scale/architecture-
sensitive knob and the suite spans 0.5B → 3B across 5 architectures; a single Qwen-tuned lr would
make the bake-off measure *"which model likes Qwen's lr,"* not which grounds best. Per arm:
**lr ∈ {1e-4, 2e-4, 4e-4}**, pick best on **in-loop val IoU@0.25**. Epochs **cap at 3 but
early-stop on the in-loop eval** (the right number differs by model/scale). **No Optuna, no broader
grid** — lr is the only knob that changes the answer (YAGNI).

**Per-arm deviations (logged confounds, not controls):** target-module names, native resolution,
and chat template differ by architecture (Qwen dynamic ≤1024 long-edge; PaliGemma 448; Florence
768; InternVL 448-tile; SmolVLM2 384-tile). Recorded per arm — the comparison is "best achievable
per architecture," not "identical knobs."

**Reserved lever — NOT pulled here.** Unfreezing / LoRA-ing the **vision tower** is the highest
grounding upside (localization lives in vision features) but would confound this first pass. Held
as the dependent follow-up **`experiments/2026-06-30-vision-tower-unfreeze/`** — pulled only if the
frozen-vision results hit a ceiling. Same discipline as Phase-3's reserved `largest_box_aug` /
`max_side=1280` levers.

GPU-hour discipline: spend asymmetrically. D and E are tiny — cheap floor/ceiling anchors. Put the
budget on A/B/C's lr sweep; within-architecture variance is worth more than a 6th model.

### Success criterion (gate)

Standing aerial gate is **IoU@0.25 ≥ 20%** (Phase-3 lineage), but the *bake-off* bar is
**RQ-B.2**: beat the deployed Qwen2-VL-2B on the speed/accuracy Pareto. A model that clears
20% but is slower **and** less accurate than the incumbent is a documented negative, not a win.

## Method

The three stages reuse existing entry points — `run_arm.py` (lands with arm A) is a thin
per-arm wrapper over them, so a fresh session can drive a stage directly if the wrapper is absent.
Each arm = **one `TrainConfig`** (model id, target modules, resolution); a run is fully described
by its config + manifest in `runs/`.

1. **Fine-tune** (RTX 3090, `.venv-ft`): `grounding/train/trainer.py` + `grounding/train/config.py`
   (the Phase-3 loop) for llama.cpp-path arms; HF `Seq2SeqTrainer` for Florence (arm D, seq2seq,
   different loop). → LoRA adapter + merged weights.
2. **Export** (stack-native arms A/B/E): `grounding/export/` → GGUF + mmproj, `scp` to Jetson via
   `grounding/deploy/serve.py:push`. Arms C/D: convert to TensorRT/ONNX (engine build recorded per arm).
3. **Accuracy eval** (RefDrone val, n=439): `grounding/eval/harness.py:evaluate` over the **same**
   `contract.py` path — whole-frame *and* ROI-crop — reporting parse rate, IoU@0.25, mean IoU, center_std.
4. **Latency eval** (Jetson, 15 W): serve each arm, measure separated prefill/decode/wall per anchor,
   both paths, + `tegrastats` peak-RAM (same capture as the 2026-06-30 headroom run) to confirm fit.

```bash
source .venv-ft/bin/activate
# intended per-arm driver (wrapper over the entry points above):
python experiments/2026-06-30-vlm-backbone-bakeoff/run_arm.py --arm internvl3-2b --stage all
# manual fallback if the wrapper isn't written yet — train via the Phase-3 loop with an arm config:
python -m grounding.train.trainer --config experiments/2026-06-30-vlm-backbone-bakeoff/configs/internvl3-2b.py
```

## Estimates (up-front priors — mark as ESTIMATE, record actual-vs-estimate in Results)

Weak priors, stated so a wrong one becomes content. **FT-time anchor:** Phase-3 Qwen2-VL-2B LoRA
= 6153 steps / ~6550 s (~1.8 h) on the 3090 (3 epochs, 4101 samples, max_side 1024).
**IoU priors** extrapolate from the REC proxy + the Qwen2-VL-2B → 63.1% WF / 85.2% ROI mapping;
aerial domain shift caps confidence, so ranges are wide. **Latency priors** scale the baseline by
the arm's vision-token count.

| Arm | est. FT wall (3090) | est. IoU@0.25 WF | est. IoU@0.25 ROI | est. anchor wall (ROI, Jetson 15 W) |
|---|---|---|---|---|
| A InternVL3-2B | ~2 h | 65–72% | 85–88% | ~1.5–2.5 s |
| B Qwen2.5-VL-3B | ~2.5–3 h | 66–73% | 85–89% | ~2–3 s (3B prefill) |
| C PaliGemma2-3B@448 | ~2–2.5 h | 60–72% | 80–87% | ~1.5–2.5 s |
| D Florence-2-large | ~1 h | 50–70% (high variance) | 78–88% | **~0.5–1.5 s (speed ceiling)** |
| E SmolVLM2-500M | ~0.5–1 h | 40–65% (collapse risk) | 70–86% | **fastest, ~0.3–1 s** |

**Est. total campaign:** ~25–35 GPU-h (A/B/C at 2–3 settings each; D/E single cheap runs) +
~0.5–1 h Jetson eval per arm/path. Plan as a **multi-day, multi-session** campaign.

## Results (TBD)

Fill as arms complete. One row per arm × path; record **actual** next to the estimate above and
flag divergence (`Δ vs est.`):

| Arm | path | parse | IoU@0.25 (Δ vs est.) | mean IoU | center_std | prefill | decode | wall (Δ vs est.) | peak RAM | FT wall (Δ vs est.) |
|---|---|---|---|---|---|---|---|---|---|---|
| _baseline_ Qwen2-VL-2B | whole-frame 1024 | 100% | 63.1% | 0.477 | — | 837 tok / 3712 ms | 12 tok / 547 ms | 4400 ms | ~4.6 GB | ~6550 s |
| _baseline_ Qwen2-VL-2B | ROI re-anchor | — | 85.2% | — | — | — | — | ≈2000 ms | — | — |
| A–E | … | | | | | | | | | |

(Baseline rows from `2026-06-30-whole-frame-resolution` + the deployed ROI lever — the curve the
suite is measured against.)

## Findings

TBD.

## Decision

TBD — which spine replaces Qwen2-VL-2B (or whether it stays), with what was given up.

## Risks / honest caveats (pre-registered)

- **REC ≠ aerial.** RefCOCO@0.5 on natural images orders the bench; the winner is decided on
  RefDrone IoU@0.25. Do not let the proxy pre-bias the read.
- **SmolVLM2 / Florence may not learn boxes well** — not box-pretrained / fixed-res. Treated as
  hypotheses (RQ-B.3), and they're the cheapest arms, so a negative is low-cost content.
- **Off-stack deployment effort (C, D).** PaliGemma2 and Florence-2 need a TensorRT/ONNX path on
  the Jetson — that's the device-native fast path anyway, but it's integration time, budgeted.
- **Per-arm FT confounds** (target modules, resolution, chat template) cannot be fully equalised
  across architectures. Logged per arm; the comparison is "best achievable per architecture,"
  not "identical knobs."

## Status & next step (where a cold session picks up)

- **2026-06-30T14:03Z — pre-registered, nothing run.** Suite + config + estimates frozen above.
- **Next step:** scaffold `run_arm.py` + `configs/internvl3-2b.py` and launch **arm A
  (InternVL3-2B)** FT on the 3090. Arm A is the strongest prior and validates the whole harness
  (FT → export → GGUF → Jetson serve → dual-path eval) before the costlier arms.
- **Open decisions before launch:** (1) the per-arm LoRA target-module names for non-Qwen
  architectures (the one real unknown — set per arm, log as a confound); (2) TensorRT vs ONNX for
  C/D on the Jetson.
- **Done when:** all 5 arms have both Results rows filled (actual + Δ-vs-est.), Findings written,
  Decision recorded, and the ledger entries appended (see below).

## Ledger follow-through (per CLAUDE.md definition-of-done)

Held until results exist (these append a *verdict*, not a plan):
**RESULTS** Part IV — one row per arm/path · **QUESTIONS** Part IV — RQ-B.1…B.4 one-line verdicts ·
**DECISIONS** Part IV — the spine choice + what was given up · **SOURCES** — model/dataset cards
for any new arch pulled in.

## Files

- `README.md` — this pre-registration (source of truth + handoff).
- `run_arm.py` — per-arm FT + eval runner (lands with arm A). `configs/` — one `TrainConfig` per arm.
- `runs/` — per-arm provenance manifests (git_sha, lockfile, config). `raw/` → `experiments/raw/`.
