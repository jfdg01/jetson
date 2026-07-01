# VLM backbone bake-off — is Qwen2-VL-2B still the right spine?

**Date:** 2026-06-30T14:03Z (pre-registration) · **Branch:** `experiment/vlm-sweep`
**Status:** **CLOSED — early-stopped 2026-07-02T00:21Z** (arms A/B/C/E measured, D cancelled un-run; Decision: **keep Qwen2-VL-2B**). Pre-registered 2026-06-30 before any GPU hours.
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
- **RQ-B.4 (health):** Every arm non-degenerate — `parse_rate ≥ 90%`, `center_std` not collapsed
  toward 0. **Scale correction (2026-06-30):** the "~61 floor" is a Part-I 0–1000-coord number; the
  v2 contract normalizes coords **0–100**, where RefDrone-val **ground-truth `center_std` = 22.9**.
  So healthy ≈ 23 (matches the true target spread); collapse → near 0. Judge arms against ~23, not 61.

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
| **A** InternVL3-2B | whole-frame 1024 (HF local, n=200) | 100% | **48.5%** (est 65–72% → **−17 to −24pp**) | 0.298 | 22.3 | — | — | **N/A — Jetson deploy BLOCKED** | — | ~3.3 h/leg (est ~2h → **+65%**) |
| **A** InternVL3-2B | ROI re-anchor | — | — | — | — | — | — | N/A (not deployed) | — | — |
| **B** Qwen2.5-VL-3B | whole-frame 1024 (Jetson Q8_0, n=439) | 100% | **53.1%** (est 66–73% → **−13 to −20pp**; HF n=200 = 58.0%, Q8_0 −4.9pp) | 0.399 | 21.6 | 837 tok / 5002 ms | 12 tok / 842 ms | 5990 ms (baseline WF 4400) | n/m | ~3.4 h/leg (est 2.5–3h) |
| **B** Qwen2.5-VL-3B | ROI re-anchor M=2.0@512 (Jetson Q8_0, n=439) | 100% | **33.0%** (est 85–89% → **−52 to −56pp; ROI COLLAPSE**) | 0.170 | 22.9 | 385 tok / 1916 ms | 12 tok / 838 ms | 2817 ms (est ~2–3s → in range) | n/m | — |
| **C** PaliGemma2-3B@448 | whole-frame @448 (HF local, n=200) | 100% | **56.0%** (in-loop best 57.0%; est 60–72% → **−4 to −16pp**; vs 62.6% incumbent −6.6pp) | 0.391 | 22.1 | — | — | TBD — Jetson export (TensorRT/ONNX) pending | — | ~2.6 h/leg (est ~2–2.5h → in range) |
| **E** SmolVLM2-500M | whole-frame @512 (in-loop val, lr=1e-4 leg) | 100% | **5.5%** (est 40–65% → **−35 to −60pp; CAPACITY COLLAPSE**) | 0.038 | 12.7–18.6 (< GT 22.9) | — | — | N/A — eliminated at leg 1, never deployed | — | ~2.8 h/leg (est 0.5–1 h *total* → ~8× under-est) |
| **D** Florence-2-large | — | — | **CANCELLED un-run — campaign early-stopped 2026-07-02** (see Findings) | — | — | — | — | — | — | — |

(Baseline rows from `2026-06-30-whole-frame-resolution` + the deployed ROI lever — the curve the
suite is measured against.)

**Two incumbent numbers, used deliberately:** **63.1%** is the baseline-row WF figure from the
`2026-06-30-whole-frame-resolution` re-measurement (n=439, same harness as arm B's Jetson bench);
**62.6%** is the Phase-4 deployed Q8_0 figure (the number the thesis quotes as "what's running").
They are the same model/config measured in two campaigns; deltas quote whichever the comparison is
actually against (Jetson-harness rows → 63.1%, "vs deployed incumbent" verdicts → 62.6%).

## Findings

_Partial — arms A, B, C in; E training, D queued (see Status)._

- **Arm A (InternVL3-2B) is a double negative.** (1) Accuracy laggard: whole-frame IoU@0.25 = **48.5%**
  (n=200, HF, best lr=4e-4 merge), **−14.1pp under the 62.6% incumbent** and well below the 65–72%
  estimate. (2) Off-stack at the pinned toolchain: GGUF export fails at llama.cpp `57fe1f0` — the mmproj
  converter filter wants `model.vision_tower.*` / `model.multi_modal_projector.*` but the transformers
  `-hf` checkpoint ships `vision_tower.*` / `multi_modal_projector.*` (no `model.` prefix) → 0 vision
  tensors emitted; the LLM half separately wants a SentencePiece `tokenizer.model` the Qwen2-BPE backbone
  doesn't ship. Not patched (pinned converter is a controlled variable) and no checkpoint surgery on the
  worst arm (a silently-misaligned GGUF is worse than none). Latency = **N/A (blocked)**. A weak, hard-to-
  deploy arm — eliminated on accuracy alone; deployment is moot.
- **Arm B (Qwen2.5-VL-3B): ROI re-anchor COLLAPSES — the headline negative.** Whole-frame Q8_0 on Jetson
  = 53.1% (n=439), already **−10pp under the 63.1% incumbent WF and below its own 58.0% HF** (Q8_0 costs
  −4.9pp). But the deployed **ROI re-anchor makes it *worse*, not better: 33.0% << 53.1% WF** — the exact
  inversion of the incumbent, where ROI (85.2%) >> WF (63.1%). **Verified against an independent code path**
  (canonical `harness.evaluate` + `roi.evaluate_roi`, n=40: WF 42.5%, ROI 20.0% — same collapse), so it is
  not a bench artifact. Mechanism is open (a GT-centered 512 zoom that lifts the 2B *drops* the 3B — the
  FT'd 3B does not transfer to the cropped/upscaled distribution the incumbent thrives on), but the read is
  firm: **the lever the whole deployment depends on does not survive a backbone swap to Qwen2.5-VL-3B.**
  On latency it is *slower* than the 2B it would replace (WF 5990 ms vs 4400 ms; ROI 2817 ms vs ≈2000 ms) —
  a bigger, less accurate, ROI-hostile arm. Eliminated.
- **Arm C (PaliGemma2-3B@448) is the strongest non-baseline arm — and still loses.** A purpose-built
  detection-FT base (native `<loc>` pretraining) with the cleanest FT of the field: parse 100%, healthy
  center_std (22.1, no collapse), monotonic to E3, and a clear lr optimum (2e-4). Whole-frame IoU@0.25 =
  **56.0%** (in-loop peak 57.0%), the best of arms A/B/C — yet still **−6.6pp under the 62.6% Qwen2-VL-2B
  incumbent**. The read: even the detection-native 3B, fine-tuned cleanly, does not beat the deployed 2B on
  aerial whole-frame accuracy under the fixed 3-epoch budget. Jetson latency is still pending (off-stack
  TensorRT/ONNX, like A), but on accuracy alone it is not a spine upgrade. The pattern across A/B/C is
  consistent: **more params ≠ more aerial grounding accuracy here; none of the larger backbones clears the incumbent.**

- **Arm E (SmolVLM2-500M) collapsed — RQ-B.3 answered in the negative.** lr=1e-4 leg:
  E1/E2/E3 = 5.0/5.0/5.5% IoU@0.25 (parse=100%, mean_iou 0.02–0.04, center_std 12.7–18.6 < GT 22.9 —
  near-constant box guesses while the loss trains fine). The pre-registered capacity-collapse risk
  played out: aggressive pixel-shuffle token compression does not learn aerial boxes at 500M. Leg 2
  (lr=2e-4) was killed mid-E1 at the early-stop; an arm-A-sized lr rescue (+10pp across the swept
  range) would still leave it ~50pp under the incumbent — no lr outcome could change its verdict.
- **Campaign early-stopped 2026-07-02T00:21Z (user-authorized); arm D cancelled un-run.** With A/B/C
  all below the incumbent on accuracy and E collapsed, no remaining run could change the adoption
  decision: even a strong Florence-2 number would sit on an off-stack runtime (TensorRT/ONNX
  integration cost), carry arm B's demonstrated ROI-transfer risk, and optimize a criterion (anchor
  speed) that the acquire-once re-layer (`experiments/2026-07-01-temporal-acquire-carry/`) demotes to
  a once-per-acquire cost. Given up, recorded as not-measured (not estimates): Florence-2's
  "speed-ceiling" datapoint, arm E legs 2–3, and Jetson latency for A/C/D. The CPU-validated arm-D
  driver (`run_florence.py`, `florence_loc.py`) stays in the tree, un-run, should the datapoint ever
  be wanted.

## Decision

**Keep Qwen2-VL-2B as the spine (2026-07-02).** No arm reached the incumbent's accuracy, let alone
the RQ-B.2 double bar: A 48.5% (and GGUF-blocked at the pinned toolchain), B 53.1% WF / **33.0% ROI
collapse** + slower on both paths, C 56.0% (best challenger, still −6.6pp), E 5.5% (collapse);
D cancelled at the early-stop. The deployed ROI lever (85.2%) is backbone-specific — arm B proved it
does not transfer — so the spine and the lever are a matched pair; swapping the spine forfeits the
lever. **Given up:** Florence-2's speed datapoint; the vision-tower-unfreeze follow-up
(`experiment/vlm-vision-unfreeze` stays a parked pre-draft — anchor-speed optimization is moot under
the acquire-once pivot); A/C/D latency numbers. **Context:** the temporal re-layer moves the VLM off
the hot path, inverting criterion 1 (speed) into a minor cost — which *strengthens* the incumbent:
it wins the now-binding accuracy axis outright.

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
- **2026-06-30T14:50Z — arm A (InternVL3-2B) FT LAUNCHED on the 3090.** Harness validated end-to-end
  for an off-Qwen architecture (dry-run loss=1.89, LoRA 20.8M / 0.99% trainable). lr sweep
  {1e-4,2e-4,4e-4} running under the crash-resistant launcher. Throughput ~1.06 step/s →
  ~65 min/epoch, ~3.2 h/lr, **~10 h for the full arm-A sweep**. Logs: `raw/internvl3-2b-sweep.log`.

  **Per-arm harness deviations discovered + applied (logged confounds, not controls):**
  - `OpenGVLab/InternVL3-2B-hf` (transformers-native `internvl`, loads through the generic
    `AutoModelForImageTextToText` harness — no trust_remote_code). LLM is Qwen2-based so the
    default LoRA targets (`q/k/v/o_proj`, `gate/up/down_proj`) matched and skipped the InternViT
    vision tower by construction (`freeze_vision` holds).
  - **`max_seq_len=4096`** (new `TrainConfig` field; Qwen baseline stays at 1280). InternVL
    dynamic-tiles @1024 long-edge → **measured 817..3385 tokens, median ~2100** over 30 train
    samples; the Qwen-tuned 1280 cap truncated the vision span and broke image-token alignment.
    This high token count is itself a **speed signal** for the Jetson latency stage (RQ-B.1).
  - **`gradient_checkpointing=True` + `batch_size=1` / `grad_accum=16`** (effective batch still 16).
    The ~2-3k-token sequences OOM'd at batch 2 on the 24 GB 3090 (245 MiB short at peak); both
    new `TrainConfig` knobs are off/baseline-default for Qwen so the incumbent run is byte-identical.

- **2026-06-30T15:55Z — arm A lr=1e-4 epoch-1 eval (health PASS).** parse=100%, IoU@0.25=29.0%
  (already > 20% gate at epoch 1/3), mean_iou=0.170, center_std=22.7 ≈ GT 22.9 → fully input-dependent,
  no mode collapse. Sweep continues (epochs 2-3, then lr=2e-4, 4e-4).
- **2026-06-30T18:01Z — arm A lr=1e-4 sweep leg COMPLETE** (merged + `DONE`). Per-epoch IoU@0.25:
  E1 29.0% → **E2 37.0%** → E3 35.5% (slight overfit past E2; early-stop pick = **E2 37.0%**,
  mean_iou=0.236). parse=100% all epochs, center_std 22.5-22.8 ≈ GT 22.9 throughout. lr=2e-4 leg
  now training (E1 loss=2.26 from fresh adapter). Best-of-sweep TBD after lr=2e-4, 4e-4.
- **2026-06-30T21:15Z — arm A lr=2e-4 sweep leg COMPLETE.** Per-epoch IoU@0.25: E1 27.5% →
  E2 36.5% → **E3 42.0%** (monotonic — unlike lr=1e-4 it kept climbing, best = E3, mean_iou=0.262).
  parse=100% all epochs, center_std 21.6-24.5 ≈ GT 22.9. **New sweep best: 42.0% (lr=2e-4 E3)**,
  +5pp over lr=1e-4's peak — the higher lr learns better here. lr=4e-4 (final leg) next; the
  climbing-to-E3 shape suggests 4e-4 may want >3 epochs, but epochs are fixed at 3 (pre-registered).
- **2026-07-01T08:55Z — arm A (InternVL3-2B) SWEEP COMPLETE. Winner: lr=4e-4 E3 = 47.5%.**
  Full per-epoch IoU@0.25 grid (parse=100%, center_std 21.6-24.5 ≈ GT 22.9 throughout — no collapse anywhere):

  | lr | E1 | E2 | E3 | best | shape |
  |---|---|---|---|---|---|
  | 1e-4 | 29.0 | **37.0** | 35.5 | 37.0 | peaks E2, slight overfit |
  | 2e-4 | 27.5 | 36.5 | **42.0** | 42.0 | monotonic |
  | 4e-4 | 30.0 | 43.5 | **47.5** | **47.5** | monotonic, steepest |

  **Read:** accuracy rises with lr across the whole swept range; the best leg (4e-4) was still
  climbing at E3 (+4pp E2→E3), so 3 epochs is likely **undertrained** for InternVL3-2B — the 47.5%
  is a *floor*, not a converged number. **Caveat for the cross-arm comparison:** 47.5% sits well
  below the Qwen2-VL-2B incumbent (Phase-3 LoRA 59.5% HF / 62.6% Q8_0 Jetson) at the same r=16 LoRA /
  3-epoch / lr-swept protocol — arm A (the strongest prior) **underperforms the incumbent** under the
  pre-registered budget. The undertraining flag + 4e-4-edge-of-grid both say the protocol may be
  pinching InternVL specifically (its ~2-3k-token tiled sequences see fewer effective updates/epoch);
  record as a confounded loss, not a clean one. Final whole-frame re-score of the merged lr=4e-4
  ckpt running now (authoritative number for the RESULTS row).
- **2026-07-01T09:10Z — arm A authoritative accuracy = 48.5%** (whole-frame re-score of the merged
  lr=4e-4 ckpt: n=200, parse=100%, IoU@0.25=48.5%, mean_iou=0.298, center_std=22.3; ~1pp over the
  in-loop E3 = greedy-decode noise on merged-vs-adapter weights). Arm A accuracy half DONE; its
  Jetson export+latency half is **blocked** on the open llama.cpp-internvl-mmproj question (separate
  workstream, not gating the rest of the sweep).
- **2026-07-01T09:12Z — arm B (Qwen2.5-VL-3B-Instruct) FT — OOM on first launch, fixed, relaunched.**
  First launch mirrored the incumbent exactly (batch 2 / grad_accum 8 / **no** grad-ckpt / max_seq_len
  1280). The forward-only `--dry-run` PASSed (LoRA 37.2M / 0.98% trainable, loss=5.30) but the **batch-2
  backward OOM'd by 72 MiB** on the 3090's 24 GB at step <50 — a forward-only dry-run can't see the
  backward's activation peak. **Fix:** `gradient_checkpointing=True` (recompute activations in backward,
  frees several GB); kept batch 2 / ga 8, so the *only* new confound vs the 2B incumbent is grad-ckpt,
  not the batch size. Relaunched (PID 286757); now stepping past the OOM point (2051 steps/epoch = 4101/2
  confirms batch 2; GPU 23.2/24 GB, holding). **Lesson logged:** the bake-off dry-run gate is forward-only
  and under-tests memory for ≥3B arms — treat first-50-steps as the real OOM gate. lr sweep {1e-4,2e-4,4e-4},
  log `raw/qwen2.5-vl-3b-sweep.log`. The only clean deltas vs the 62.6% baseline remain +1B params + the
  Qwen2.5 vision encoder (+ grad-ckpt, which is numerically ~neutral).
- **2026-07-01T12:20Z — arm B lr=1e-4 leg COMPLETE.** Per-epoch IoU@0.25: E1 **56.0%** / E2 55.0% /
  E3 55.5% (@0.25 saturates ~55-56%; mean_iou climbs 0.352 → 0.384 → 0.413 = boxes tightening under a
  flat threshold count). parse=100%, center_std 21.6-22.3 ≈ GT 22.9. Best = E1 56.0%. Already far above
  arm A's whole sweep (best 47.5%) and near the 62.6% incumbent — **on lr=1e-4, which for arm A was the
  weakest leg** (+10pp came from 2e-4/4e-4). lr=2e-4, 4e-4 legs next; if the arm-A lr-shape repeats,
  arm B's best could clear the incumbent.
- **2026-07-01T14:05Z — arm B lr=2e-4 leg COMPLETE.** Per-epoch IoU@0.25: E1 48.0% / E2 **60.5%** /
  E3 59.0% (mean_iou monotonic 0.312 → 0.444 → 0.453, but @0.25 turned over at E2 — E3's tighter
  mean box didn't add threshold-crossers). parse=100%, center_std 22.0-22.2 ≈ GT 22.9. Best =
  E2 60.5%, +4.5pp over the lr=1e-4 leg (56.0%) and 2.1pp under the 62.6% incumbent. The arm-A
  lr-shape repeats (2e-4 > 1e-4); **lr=4e-4 (final leg) is the one that could clear the incumbent.**
- **2026-07-01T16:12Z — arm B (Qwen2.5-VL-3B) SWEEP COMPLETE. Winner: lr=2e-4 E2 = 60.5%.** Full grid
  (IoU@0.25 per epoch): lr=1e-4 56.0/55.0/55.5 (best E1), lr=2e-4 48.0/**60.5**/59.0 (best E2), lr=4e-4
  49.5/58.5/59.5 (best E3). parse=100% throughout, center_std 20.7-22.3 ≈ GT 22.9 (no collapse). Unlike
  arm A (monotonic, 4e-4 steepest), arm B **peaks at lr=2e-4** and plateaus ~58-60% across 2e-4/4e-4 —
  it saturates the @0.25 metric near 60% and higher lr just trades E2↔E3 placement (lr=4e-4 E3 has the
  tightest boxes, mean_iou=0.489, but not more @0.25 crossers). **Best 60.5% lands 2.1pp under the 62.6%
  Q8_0 incumbent** under the same fixed 3-epoch budget — the extra 1B params + grad-ckpt do NOT beat the
  2B incumbent on accuracy here. Whole-frame re-score of the winning lr=2e-4 merged checkpoint (final-epoch
  E3 merge, not the E2 peak): n=200, parse=100%, **IoU@0.25=58.0%**, mean_iou=0.447, center_std=22.1.
  Caveat mirrors arm A: the in-loop early-stop pick (E2 60.5%) and the re-scored artifact (E3 58.0%)
  differ because the merge saves the last epoch, not the best — the deployable number is the 58.0%
  re-score unless we re-merge E2. Next: arm C (PaliGemma2-3B@448, grad-ckpt pre-set) on the freed GPU;
  arm B Jetson export+latency is a bf16 3B GGUF (Qwen2.5-VL is llama.cpp-supported, unlike arm A's InternVL).

  **Crash-resistance infra (per user requirement, 2026-06-30):** added to the shared trainer —
  atomic mid-epoch adapter save every 300 steps (`latest/`), atomic per-epoch adapters (`epochN/`,
  the resume source), **epoch-level resume** on restart (warm-start from highest `epochN`, bounds a
  crash to <1 epoch ≈ 65 min), append-mode CSVs (no truncation on crash), per-lr `DONE` sentinel so
  the sweep skips finished lrs, and `launch_arm.sh` (8-retry auto-restart). Verified: `latest/`
  landed atomically at step 300, no `.tmp` leftover.
- **2026-07-01T11:35Z — arm C (PaliGemma2-3B pt-448) FT LAUNCHED on the 3090.** Dry-run PASS
  (loss=2.97, LoRA 23.8M / 0.777% trainable, grad-ckpt on). lr sweep {1e-4,2e-4,4e-4} running under
  the crash-resistant launcher; E1 loss 3.19 → ~1.17 by step 450. Throughput ~1.52 s/step @220W
  (see fan note) → ~52 min/epoch, ~2.6 h/lr, **~8 h for the full arm-C sweep**. Logs:
  `raw/paligemma2-3b-sweep.log` (note: PaliGemma's processor prints a per-collate "passing both text
  and images" notice that neither `TRANSFORMERS_VERBOSITY=error` nor a `warnings` filter suppresses —
  cosmetic; grep `E[0-9] step` for the loss trend).

  **Per-arm harness deviation (logged confound):** PaliGemma has **no chat template**. The shared
  trainer + eval backends now branch on `processor.chat_template is None` → PaliGemma-native path:
  plain prompt (no `apply_chat_template`), target passed as `suffix=` so the processor builds the
  masked `labels` itself (prefix+image −100, suffix supervised, `<eos>` appended), and plain-prompt
  generation at eval. Text backbone is Gemma2, so the default LoRA targets (`q/k/v/o_proj`,
  `gate/up/down_proj`) matched and the SigLIP vision tower stayed frozen by construction. Fixed
  448×448 square input (processor squishes regardless), but coords are normalized `[0,100]` to the
  original image → scale-invariant, **no coordinate confound** from the squish. The `chat_template is
  None` branch is inert for the Qwen incumbent (byte-identical path preserved). Gated model: launcher
  exports `HF_TOKEN` from `.hugging-face-token`.

- **2026-07-01T11:20Z — GPU fan/power finding (train box, RTX 3090, driver 595).** User asked to run
  fans at ~80% (93% under load is too loud). **`GPUTargetFanSpeed` is firmware-blocked on this card:**
  Coolbits=4 is active (`/etc/X11/xorg.conf.d/20-nvidia-coolbits.conf`, confirmed in Xorg.0.log) and
  `GPUFanControlState=1` assigns cleanly, but every `GPUTargetFanSpeed` assignment throws "Unknown
  Error" — even under load, both fans, standalone or combined. The attribute reads/queries fine and
  claims writable (range 0–100, target type Fan); the driver/VBIOS just rejects the write. No
  nvidia-settings path exists; `coolgpus` / a second X on `:1` also fail (`:0` holds DRM master).
  **Power cap is the only working noise lever** (auto fan curve tracks temp): measured 260W→93% fan
  / 1.33 s·step⁻¹, 230W→~83% / ~1.4, **220W→~75% / 1.52 (chosen)**, 200W→60% / 1.6 (a sharp curve step
  sits between 200–230W). Set `sudo nvidia-smi -pl 220` for the rest of the campaign: ~75% fan at
  ~14% throughput cost. Fan reverted to auto (`GPUFanControlState=0`) — never left in manual with no
  valid target. Not persistent across reboot; re-apply `-pl 220` if the box restarts mid-campaign.
- **2026-07-01T12:10Z — arms D/E scoped + arm B export blocker found (parallel prep while C trains).**
  CPU-side probes (no GPU contention) locked the remaining arms:
  - **Arm E = `HuggingFaceTB/SmolVLM2-500M-Video-Instruct`** (`smolvlm`, Llama text backbone).
    SmolVLMProcessor HAS a chat template → **fits the shared harness unchanged** (same path as the
    Qwen incumbent / arm B); LoRA targets match, vision frozen by construction. Config written
    (`configs/smolvlm2-500m.py`). Two notes: (1) its processor hard-depends on **`num2words`** —
    installed into `.venv-ft`, added to `requirements-ft.txt` (run `make lock` to pin); (2) the
    pre-registered "384-tile" is wrong for this checkpoint — its native tile is **512**
    (`max_image_size.longest_edge=512`), so `image_size=512` (one native tile, speed-floor intent).
    Token count / fit to be confirmed by a dry-run before launch (GPU-gated on arm C finishing).
  - **Arm D = `microsoft/Florence-2-large`** confirmed **encoder-decoder** (`florence2` /
    `florence2_language`), no chat template, native `<loc_N>` output. It does **not** load through the
    causal `AutoModelForImageTextToText` harness — needs the pre-registered separate **Seq2Seq** path
    (HF `Seq2SeqTrainer` or a custom enc-dec loop) plus a decision on native-loc vs terse-int contract.
    The hardest arm; build deferred until the GPU frees (validation is GPU-gated).
  - **Arm B Jetson export BLOCKER:** the pinned converter `/tmp/llama.cpp-57fe1f0/convert_hf_to_gguf.py`
    is **gone** (tmp cleared on the reboot). Export needs llama.cpp re-cloned at commit `57fe1f0`, AND
    whether that pinned commit supports **Qwen2.5-VL** vision-tower mmproj is **unverified** (the
    incumbent was Qwen2-VL, older) — a potential pinned-commit wall analogous to arm A's InternVL
    uncertainty. Logged; conversion is CPU-side (GPU-free) once the converter is restored.
- **2026-07-01T12:07Z — arm B Jetson export FIXED + bench running; arm A deployment BLOCKED (characterized).**
  Both prior blockers resolved to root cause; llama.cpp re-cloned at `57fe1f0` and **verified end-to-end**
  (converter `conversion/qwenvl.py` registers `Qwen2_5_VLForConditionalGeneration`; runtime `clip.cpp`/
  `mtmd.cpp` handle both `QWEN25VL` and `INTERNVL` projector types; Jetson build is at the exact same
  commit `57fe1f0…`).
  - **Arm B export cause of earlier exit-1:** the `to_gguf` wrapper shells out to bare `python`, which
    resolved to the system pyenv (no torch) instead of `.venv-ft`. Fix: run the export with `.venv-ft/bin`
    on `PATH`. All three GGUFs then built clean (Q8_0 3.1 GB, f16 5.8 GB, mmproj-f16 1.3 GB). **Arm B
    dual-path Jetson bench is running now** (n=439, Q8_0, whole-frame 1024 + ROI M=2.0@512) via the new
    `jetson_bench.py` driver (deploys, serves `llama-server` ngl=99, loops `generate_stats` so IoU +
    prefill/decode/wall come from one pass). Early read (n=43 WF): IoU@0.25 ≈ 46%, wall ≈ 6000 ms — i.e.
    the 3B is both **less accurate and slower** than the 2B incumbent (63.1% / 4400 ms). Full numbers land
    in the Results table.
  - **Arm A (`InternVL3-2B-hf`) Jetson export BLOCKED — format incompatibility at the pinned commit (a
    documented negative, not a transient).** InternVL *is* supported by `57fe1f0` (both converter and
    runtime), but the **transformers-native `-hf` checkpoint layout doesn't match the converter's
    expectations**: (1) mmproj — the InternVL mmproj filter accepts only `model.vision_tower.*` /
    `model.multi_modal_projector.*`, while our merged checkpoint uses top-level `vision_tower.*` /
    `multi_modal_projector.*` (no `model.` prefix) → **zero vision tensors matched** (`n_tensors=0`,
    empty mmproj); (2) LLM half — the converter takes the SentencePiece path and dies on a missing
    `tokenizer.model`, which the Qwen2-BPE backbone doesn't ship. Deploying arm A would require either
    **patching the pinned converter** (breaks the "same commit as the Jetson build" invariant — a
    controlled variable) or **checkpoint-key surgery + tokenizer grafting** on the *worst-performing arm*
    (48.5% WF, well below the 62.6% incumbent), risking a silently-misaligned GGUF (a wrong latency
    number is worse than none). Decision: **record the blocker with root cause, latency = N/A (not
    stack-native-deployable at `57fe1f0` without format surgery).** Arm A is thus a double negative —
    accuracy laggard *and* off-stack to deploy — so it is not a spine candidate regardless. (This is the
    "off-stack deployment effort" the Risks section pre-registered for C/D, biting A too.) Empty partial
    GGUF removed.
- **2026-07-01T15:05Z — arm B dual-path bench DONE + ROI collapse VERIFIED; arm A/B Results rows filled.**
  Full n=439 Jetson Q8_0 (`raw/qwen2.5-vl-3b-jetson.json`): **WF** parse=100%, IoU@0.25=**53.1%**,
  mean_iou=0.399, center_std=21.6, prefill 837 tok/5002 ms, decode 12 tok/842 ms, wall 5990 ms; **ROI
  M=2.0@512** parse=100%, IoU@0.25=**33.0%**, mean_iou=0.170, center_std=22.9, prefill 385 tok/1916 ms,
  decode 12 tok/838 ms, wall 2817 ms. The ROI number **inverts** the incumbent ordering (2B: ROI 85.2% >>
  WF 63.1%; 3B: ROI 33.0% << WF 53.1%), so per the no-unverified-claims rule I cross-checked it against the
  **canonical harness** (`harness.evaluate` + `roi.evaluate_roi`, independent of `jetson_bench.py`): n=40 gave
  WF 42.5% / ROI 20.0% — same collapse, **confirmed real**. Recorded arm B's two rows + arm A's accuracy-only
  row (latency=N/A-blocked) in the Results table and wrote Findings. Arms A and B are both **eliminated**.
- **2026-07-01T15:05Z — infra fix: stray root `runs/` leak closed.** `manifest.write(runs_dir="runs")`
  defaults to a *cwd-relative* path; drivers launched from the repo root (this campaign's `trainer` / `to_gguf`)
  leaked provenance to `/home/gara/jetson/runs/` instead of the experiment tree (the sibling
  `whole-frame-resolution` experiment avoided it only because it ran from *inside* its own dir). Fix:
  `trainer.py` and `to_gguf.py` now pass a config-derived `runs_dir` (the run's `output_dir` / exported
  `checkpoint`) so the manifest co-locates with its artifact, cwd-independent; added `/runs/` to `.gitignore`
  as a guard (root `/runs/` is always a leak); moved the 7 stray records into
  `runs/<arm>/<lr>/<id>/`. Caveat: arm C's *already-running* process still has the old code in memory, so
  its remaining per-lr manifests re-leak to root until relaunch — harmless (guarded), re-swept at sweep end.
- **2026-07-01T15:25Z — arm D contract DECIDED + CPU-validated bridge landed (GPU-free prep during the
  arm-C wait).** Resolved the open "native-loc vs terse-int" question: **score Florence-2 in its NATIVE
  `<loc_N>` format and convert to the shared IoU space**, not force the terse-int target on it. Rationale:
  the RQ is "which backbone locates best per Jetson-second"; target format is each architecture's native
  interface, so evaluate every arm at its strength and compare on the format-agnostic IoU@0.25 (arms A/B
  already showed a foreign contract handicaps a backbone). Given up: target-format is no longer held constant
  across arms. Built + **CPU-validated the contract bridge** `florence_loc.py` (render GT→`<loc_N>`, parse via
  the processor's own `post_process_generation`); because loc bins are resolution-independent fractions, both
  directions run in the [0,100] contract space via `image_size=(100,100)`, so Florence output lands directly
  on `GroundingSample.bbox`. Self-check round-trips at ≤0.05-unit drift (half a loc bin). Wrote
  `configs/florence2-large.py` (image_size 768, BART-decoder LoRA surface). The enc-dec **training driver**
  (`run_florence.py`) is deliberately deferred until the GPU frees — it can only be validated live, so it is
  not written blind. Confirmed on CPU: Florence has 1000 `<loc_*>` tokens, `chat_template is None` (would
  mis-route through the shared trainer's PaliGemma `suffix=` branch → separate driver required),
  `AutoModelForCausalLM(trust_remote_code=True)`.
- **2026-07-01T17:55Z — arm C DONE (eliminated); arm E LAUNCHED; arm D driver written + CPU-validated.**
  - **Arm C (PaliGemma2-3B@448) complete.** Sweep winner **lr=2e-4, in-loop IoU@0.25 = 57.0%** (E3;
    lr1e-4 51.5%, lr4e-4 50.5% — 2e-4 clearly best, all monotonic to E3). Whole-frame re-score of the
    winning merged E3 checkpoint: n=200, parse=100%, **IoU@0.25 = 56.0%**, mean_iou=0.391, center_std=22.1.
    **−6.6pp under the 62.6% incumbent** — the strongest non-baseline arm so far but still below it. FT
    wall ≈2.6 h/leg (est ~2–2.5h, in range). Row filled. Jetson export (TensorRT/ONNX, off-stack like A)
    still pending — latency TBD. Same in-loop-peak vs re-score caveat as A/B (merge saves last epoch = the peak here, so no gap).
  - **Waiter bug fixed (root cause of the earlier missed notification).** The background completion
    waiter used `pgrep -f "run_arm.py --arm paligemma2-3b"`, whose pattern **matched the waiter's own
    command line** → the `until ! pgrep` loop never exited (self-match). Killed it manually; arm C's
    python had already exited cleanly. New waiters watch the launcher **PID** (`kill -0 $PID`), which
    cannot self-match. Also swept one fresh root `runs/` leak from arm C's old in-memory code into
    `runs/paligemma2-3b/lr0.0004/`; root `runs/` now clean.
  - **Arm E (SmolVLM2-500M) LAUNCHED on the 3090.** Dry-run initially failed: SmolVLM/Idefics3
    processors need `images` grouped **per-text** (list-of-lists), not the flat list Qwen2-VL (arm B)
    takes — added a `_images_arg()` branch (keyed on processor class name) in both the trainer collate
    and `eval/backends.py` so the fix doesn't touch the already-passed arms. Dry-run then PASS (loss=2.76,
    LoRA 9.6M / 1.85% trainable). Sweep {1e-4,2e-4,4e-4} running under the crash-resistant launcher; E1
    loss 2.12 → 1.12 by step 300. Throughput ~1.6 s/step → ~55 min/epoch, **~8 h for the full sweep**
    (the 500M is small per-param but still 3 lr × 3 epochs × 2051 steps). Logs: `raw/smolvlm2-500m-sweep.log`.
  - **Arm D (Florence-2) driver written + CPU-validated (`run_florence.py`).** The pre-registered enc-dec
    Seq2Seq path: `AutoModelForCausalLM(trust_remote_code=True, attn_implementation="eager")` (Florence's
    old remote modeling lacks `_supports_sdpa`), a Florence collate (task-token+caption input, `caption<loc_N>`
    decoder labels via `florence_loc.render_target`), and a `FlorenceBackend` that generates loc tokens,
    parses via `florence_loc.parse_bbox`, and **returns the box as the terse-int string** so
    `harness.evaluate` + `contract.iou` + all crash-resistance/eval-CSV machinery are reused **unchanged**.
    LoRA is scoped to the `language_model` subtree by full-name match (DaViT's MLP also uses `fc1/fc2`, so a
    bare suffix list would leak into the vision tower and break freeze_vision). Two fixes found during CPU
    validation: (1) Florence remote code needs **`einops` + `timm`** — installed into `.venv-ft`, added to
    `requirements-ft.txt` + pinned in the lock (einops 0.8.2, timm 1.0.27); (2) Florence doesn't cast
    `pixel_values` to the weight dtype (Qwen did internally) → explicit bf16 cast in collate + generate.
    CPU dry-run gets past load / LoRA-scoping / collate / into the forward cleanly (bf16 CPU forward is just
    slow); **final live validation is GPU-gated behind arm E.** `launch_arm.sh` now takes an optional driver
    arg (`run_florence.py`) so arm D reuses the same 8-retry restart + epoch-resume wrapper.
- **2026-07-02T00:11Z — arm D generate bug caught + fixed on CPU (zero GPU burned); arm E leg 1 collapsed.**
  - **Florence generate crash found by CPU smoke, fixed with `use_cache=False`.** A CPU smoke of the one
    path the dry-run didn't cover (`PeftModel.generate` → decode → `florence_loc.parse_bbox` → terse ints)
    hit `AttributeError: 'NoneType' object has no attribute 'shape'` at Florence's remote
    `prepare_inputs_for_generation` (line 2197 indexes the **legacy tuple KV-cache**,
    `past_key_values[0][0].shape`, which transformers 4.57's Cache API no longer provides). Without the
    smoke this would have burned a full GPU epoch (~1 h) before dying at arm D's first in-loop eval. Fix:
    `use_cache=False` in `FlorenceBackend.generate` — uncached decode of ≤64 tokens on a ~300M decoder is
    a non-cost. Re-smoke PASS: generate → `'1 1 99 99'` → `contract.parse_bbox` OK (untrained LoRA, box
    quality irrelevant; the contract is "terse ints or empty"). Process note: the first smoke *reported*
    exit 0 because the output was piped through `tail` — the traceback in the log was the truth; the
    re-run used no pipe.
  - **Arm E leg 1 (lr=1e-4) finished COLLAPSED: E1/E2/E3 = 5.0/5.0/5.5% IoU@0.25**, parse 100%,
    mean_iou 0.02–0.04, center_std 12.7–18.5 — the pre-registered capacity-collapse risk playing out
    (loss trains fine, boxes are near-constant guesses). Leg 2 (lr=2e-4) mid-E1, on pace ~3 h/leg.
  - **Uncommitted work landed in three clean commits** (`c77309f` grounding infra + gitignore +
    requirements; `6a465e9` bake-off drivers + provenance + raw logs + README; `a5d2fe0` temporal
    experiment pre-registration). The gitignore whitelist keeps per-run provenance
    (manifest/run-card/results.json/CSVs) committed while ignoring the ~66 GB of checkpoints.
- **2026-07-02T00:21Z — CAMPAIGN EARLY-STOPPED (user-authorized) and CLOSED.** Arm E leg 1 finished
  collapsed (5.0/5.0/5.5%); killed the leg-2 (lr=2e-4) trainer mid-E1 (step ~1550/2051) and its
  auto-restart launcher; arm D cancelled un-run. Rationale in Findings (no remaining outcome could
  change the adoption decision); Decision recorded above. Ledger rollups written: RESULTS/QUESTIONS/
  DECISIONS Part IV + SOURCES model cards. The 3090 and Jetson are freed for the temporal campaign
  (`experiments/2026-07-01-temporal-acquire-carry/`, Phase 0 next).
- **Open decisions — resolved by the early-stop:** (1) arm A blocker → **accepted** (loser arm, moot);
  (2) TensorRT vs ONNX for C/D → **moot** (latency cancelled).
- **Done when:** ~~all 5 arms filled~~ → closed early-stopped; unfilled cells are recorded as
  cancelled-by-decision, not missing.

## Ledger follow-through (per CLAUDE.md definition-of-done)

Held until results exist (these append a *verdict*, not a plan):
**RESULTS** Part IV — one row per arm/path · **QUESTIONS** Part IV — RQ-B.1…B.4 one-line verdicts ·
**DECISIONS** Part IV — the spine choice + what was given up · **SOURCES** — model/dataset cards
for any new arch pulled in.

## Files

- `README.md` — this pre-registration (source of truth + handoff).
- `run_arm.py` — per-arm FT (lr sweep) + local whole-frame eval runner. `configs/` — one `TrainConfig` per arm.
- `launch_arm.sh <arm>` — crash-resistant launcher (auto-restart + resume). Use this, not `run_arm.py` directly, for long runs.
- `runs/<arm>/lr<x>/` — per-lr output: `epochN/` + `latest/` adapters, `train_loss.csv`, `eval_iou.csv`, merged weights + `DONE` sentinel.
- `runs/` — per-arm provenance manifests (git_sha, lockfile, config). `raw/` — verbatim launcher/training logs for this campaign.
