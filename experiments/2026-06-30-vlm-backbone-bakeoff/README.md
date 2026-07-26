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

*Earlier entries — the full session-by-session log of launches, deviations and
false starts — moved to `STATUS-LOG.md` on 2026-07-26. The closing entries stay
here.*

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
