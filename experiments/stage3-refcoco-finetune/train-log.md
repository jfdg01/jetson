# Stage 3 — RefCOCO fine-tuning train log

Pre-registration: [`README.md`](README.md). This log records training runs for the
Stage 3 methodological correction (RefCOCO, normalized 0–1000 coords, attention+MLP
LoRA) after the Stage 2 RefDrone run failed with mode collapse.

---

## Run 1 — 2026-06-16 — CRASHED (CUDA hardware fault, 70% through epoch 1)

**Status: FAILED — not a code defect; GPU-level fault. All progress lost.**

| Field | Value |
|---|---|
| Date | 2026-06-16 (started ~10:46 local) |
| Host / GPU | local workstation, NVIDIA RTX 3090 24 GB, driver 595.71.05, CUDA 13.2 |
| Venv | `.venv-ft` (torch 2.6.0+cu124, transformers 4.57.6, peft 0.19, datasets 5.0) |
| Script | `runners/run_stage3_finetune.py` (pre-checkpointing version) |
| Config | 1 epoch, batch 2 × grad-accum 8 (eff. 16), lr 2e-4 cosine, LoRA r=16 (q,k,v,o,gate,up,down), max-samples 50000 → 25000 batches |
| Dataset | RefCOCO (`jxu124/refcoco`) + COCO train2014 (82,783 imgs, 0 missing) |

### What happened

The process died at **batch 17,450 / 25,000** (~70% through epoch 1), after
**28,548 s ≈ 7.9 h**:

```
RuntimeError: CUDA error: unspecified launch failure
  File ".../run_stage3_finetune.py", line 405, in train
    loss_val = loss.item()
```

`unspecified launch failure` is a low-level CUDA/driver fault (Xid-class event:
transient GPU instability — power/thermal microglitch or driver hiccup). CUDA
errors are reported asynchronously at the next CUDA call, so `loss.item()` is where
it *surfaced*, not where it *originated*. **This is a hardware/driver fault, not a
bug in the training code.** The GPU recovered to healthy idle immediately after
(39 °C, P8, ~350 MiB, 28 W).

GPU telemetry during the run was healthy throughout: a transient 82 °C early, then
steady ~76 °C / 63–69 % fan / ~214 W for hours. Thermals were not the obvious cause,
though `unspecified launch failure` can stem from subtle instability not visible in
coarse telemetry.

### Training was on track (this is the important part)

The loss trajectory up to the crash shows **genuine learning, no mode collapse** —
the opposite of the Stage 2 failure mode:

| Window | Mean loss |
|---|---|
| first 10 logged points | 1.253 |
| epoch thirds (0–33% / 33–66% / 66–70%) | 1.061 → 0.991 → 0.973 |
| last 10 logged points | 0.942 |

A clear descent that then flattens — consistent with a model that is fitting, not
collapsing to a constant. The RefCOCO + normalized-coords + attention+MLP-LoRA
design appears sound; the run just needed to finish.

### Damage: all 7.9 h lost

The crashed script only checkpointed **at epoch end**, and epoch 1 never completed.
`smolvlm_ft3/` was empty after the crash. The only surviving artifact is
[`raw/train_loss_run1.csv`](raw/train_loss_run1.csv) (350 logged points) and
[`raw/train_run_run1.log`](raw/train_run_run1.log).

### Fix applied before relaunch — mid-epoch checkpointing

`run_stage3_finetune.py` was hardened so a future blink costs ≤ `--save-every`
batches instead of the whole epoch:

- `--save-every N` (default 1000 batches ≈ 27 min) writes a **resumable** checkpoint
  via `accelerator.save_state()` (model + optimizer + LR scheduler) to
  `<output-dir>/accel_state`, plus a directly GGUF-exportable adapter copy under
  `<output-dir>/latest`, plus a `resume_meta.json` (epoch, batch index, global step,
  elapsed).
- `--resume-from STATE_DIR` reloads that state and uses
  `accelerator.skip_first_batches()` to continue from the exact batch, carrying
  forward the loss CSV and wall-clock offset.

Verified: `--dry-run` forward pass still loss=1.1602 (no regression); `ast.parse` OK.

### Decision

See `## Decisions` below — relaunch from scratch (no resumable checkpoint exists
from the dead run) with checkpointing enabled.

---

## Run 2 — 2026-06-16/17 — COMPLETE — **G1, G2, G2b all PASS**

**Status: SUCCESS — full epoch finished, all decision gates cleared.** This is the
result that replaces the failed Stage 2 RefDrone run.

| Field | Value |
|---|---|
| Date | started 2026-06-16 ~19:26 local, finished 2026-06-17 ~06:33 local |
| Host / GPU | local workstation, NVIDIA RTX 3090 24 GB, driver 595.71.05, CUDA 13.2, **power-capped 270 W** (`nvidia-smi -pl 270`) |
| Venv | `.venv-ft` (torch 2.6.0+cu124, transformers 4.57.6, peft 0.19, datasets 5.0) |
| Script | `runners/run_stage3_finetune.py` (with `--save-every 1000`) |
| Config | 1 epoch, batch 2 × grad-accum 8 (eff. 16), lr 2e-4 cosine, LoRA r=16 (q,k,v,o,gate,up,down), max-samples 50000 → 25000 batches |
| Dataset | RefCOCO (`jxu124/refcoco`) + COCO train2014 (82,783 imgs, 0 missing) |
| Wall-clock | **39,619 s ≈ 11.0 h** (full epoch, no interruption) |
| Mid-epoch checkpoints | every 1000 batches via `accelerator.save_state()` — none needed for recovery this run (no crash) |

### Result — the gates

| Gate | Threshold | Measured (val, n=… held-out) | Verdict |
|---|---|---|---|
| **G1** parse_rate | ≥ 90 % | **100.0 %** | ✅ PASS |
| **G2** IoU@0.25 (go/no-go) | ≥ 30 % | **82.5 %** | ✅ PASS (2.75× the bar) |
| **G2b** center_std non-degenerate | not collapsed | **200.5** (px, 0–1000 space) | ✅ PASS — boxes vary with input |
| mean_iou (descriptive) | — | **0.527** | — |

Raw: [`raw/eval_iou.csv`](raw/eval_iou.csv) — `1,1.0000,0.8250,0.5275,200.50`.

**Contrast with Stage 2 (RefDrone):** Stage 2 collapsed to a single constant box
(IoU@0.25 ≈ 1 %, center_std ≈ 0). Stage 3 produces input-dependent boxes that
overlap ground truth 82.5 % of the time at the 0.25 threshold — the methodological
correction (well-posed RefCOCO data + normalized-0–1000 coords + attention+MLP LoRA)
worked as hypothesized.

### Qualitative — eval sample predictions (gt vs pred, 0–1000 coords)

```
gt=[ 32, 209, 265, 734]  pred=[ 11, 191, 231, 751]
gt=[  1, 556, 222,1000]  pred=[ 10, 520, 231, 989]
gt=[  2, 254,1000, 988]  pred=[  1, 406, 999, 989]
gt=[  2, 651, 305,1000]  pred=[603, 620,1000, 989]
gt=[205,  67, 613, 514]  pred=[ 10, 110, 441, 471]
gt=[877,  54,1000, 673]  pred=[792,   2,1000, 702]
gt=[571, 190, 938,1000]  pred=[611, 200, 999, 989]
gt=[608, 286, 747, 912]  pred=[505, 370, 645, 890]
```

Boxes track ground truth in location and scale; the model emits valid JSON every
time (parse_rate 100 %). The weakest sample (row 4: a small bottom-strip box
predicted as a right-strip box) is a localization error, not a format or collapse
failure.

### Loss trajectory — clean descent, no collapse

| Window | Mean loss |
|---|---|
| first 10 logged points | 1.279 |
| epoch thirds (0–33 / 33–66 / 66–100 %) | 1.084 → 0.976 → 0.947 |
| last 10 logged points | 0.969 |
| epoch mean / min / max | 0.995 / 0.569 / 1.893 |

500 logged points in [`raw/train_loss.csv`](raw/train_loss.csv). Descends then
flattens at the cosine LR floor — a model that fit, did not collapse.

### Artifacts

- `smolvlm_ft3/` — merged HF checkpoint (`model.safetensors` 1.0 GB + config/tokenizer), ready for GGUF export.
- `smolvlm_ft3/epoch1/` — epoch-1 LoRA adapter checkpoint.
- `raw/train_run.log`, `raw/train_loss.csv`, `raw/eval_iou.csv`.

### Next — export + on-device validation (G3/G4/RQ-S3.5)

G2 PASSED, so the pipeline proceeds to `runners/run_stage3_export.py`:
HF→GGUF Q8_0 → Jetson transfer → smoke test → Phase A grounding probe (G3 parity,
G4 aerial transfer) → Phase C Branch-2 re-run. Recorded in this log when complete.

---

## On-device export + validation — 2026-06-17

Pipeline: `runners/run_stage3_export.py` (HF→GGUF Q8_0 → scp → smoke → Phase A).

| Field | Value |
|---|---|
| Date | 2026-06-17 |
| Device / power mode | Jetson Orin Nano 8GB, **15 W** (default, not locked) |
| Runtime | llama.cpp on Jetson (`llama-server -ngl 99`), convert via llama.cpp 57fe1f0 |
| Model | `smolvlm_ft3_q8_0.gguf` (436,805,632 B, md5 `a4e5925c803eb81196101f5667e38848`, identical local↔device) + reused `mmproj-SmolVLM-500M-Instruct-f16.gguf` (vision frozen, no re-export) |

**Steps 1–2 (convert + transfer):** GGUF Q8_0 written locally and `scp`'d to
`jetson:/home/jfdg/models/`; md5 matches on both sides (export survived transfer
bit-for-bit). The mmproj is reused unchanged because the SigLIP vision encoder was
frozen during fine-tuning — the LoRA only touched the LLaMA backbone, so the GGUF
multimodal projector from the base model is still correct.

### G4 / RQ-S3.4 — aerial domain-shift penalty (descriptive, pre-registered no-bar)

Phase A grounding probe, fine-tuned GGUF over RefDrone referring expressions on
VisDrone aerial imagery (the actual thesis target domain):

| Metric | Value |
|---|---|
| n / sample | 50 images, seed 42, format S3 (normalized 0–1000) |
| parse_rate | **100.0 %** |
| **IoU@0.25** | **2.0 %** |
| IoU@0.5 | 0.0 % |
| mean_iou | 0.025 |
| throughput | 1.77 Hz |
| peak RAM | 2738 MB |

Raw: [`raw/2026-06-14_groundingS2_responses.jsonl`](raw/2026-06-14_groundingS2_responses.jsonl),
[`raw/2026-06-14_groundingS2_tegra.log`](raw/2026-06-14_groundingS2_tegra.log),
[`raw/export_run.log`](raw/export_run.log). (Filename slot `S2` is the probe's
model-unit ID, not the coord format — the log confirms "prompt format forced to S3".)

**Reading:** This is the **expected COCO→aerial cross-domain collapse**, and it was
pre-registered as descriptive (no pass bar). The model retains *format* competence
end-to-end on aerial frames (100 % valid JSON, no mode collapse in the output
grammar), but its *localization* skill — trained on ground-level COCO objects that
fill a large fraction of the frame — does not transfer to tiny, densely-packed
overhead objects shot from a drone. IoU@0.25 of 2.0 % is at the random-guess floor.

This is an **honest negative and a thesis result**, not a regression: RefCOCO was
chosen as a *well-posed capability-ceiling* dataset (the README scope note is
explicit that "RefCOCO is ground-level COCO imagery, not aerial … a capability
ceiling probe, NOT a drop-in aerial model"). The 82.5 % in-domain (RefCOCO val) vs
2.0 % out-of-domain (VisDrone) gap **quantifies the domain-shift penalty** that
motivates aerial-specific data for any future drop-in model — the central methodology
lesson Stage 3 was designed to surface. The Stage 2 failure was a *broken method*
(ill-posed data + mode collapse); this is a *correct method hitting a domain wall*.

### G3 / RQ-S3.3 — GGUF Q8_0 export parity (HF bf16 vs GGUF Q8_0)

The export-run Phase A probe is **not** a usable G3 measurement: it ran only on
aerial RefDrone, where both HF and GGUF sit at the ~2 % noise floor, so any ΔIoU is
statistical noise and the 5 pp parity gate is meaningless there. G3 is therefore
measured *in-domain* on RefCOCO val (where the skill is real, HF = 82.5 %) with a
dedicated paired harness, `runners/run_stage3_g3_parity.py` — see the
[Decisions](#decisions) entry below.

**Result (paired, n = 100 RefCOCO val, seed 42, identical samples + identical
parser + identical IoU in normalized 0–1000 space):**

| Arm | parse_rate | IoU@0.25 | mean_iou |
|---|---|---|---|
| HF bf16 (transformers, local) | 100.0 % | **85.0 %** | 0.567 |
| GGUF Q8_0 (llama.cpp `-ngl 99`, Jetson) | 100.0 % | **55.0 %** | 0.312 |
| **ΔIoU@0.25** | — | **30.0 pp** | −0.255 |

Gate: ΔIoU@0.25 ≤ 5 pp → **FAIL** (30.0 pp). Raw:
[`raw/g3_parity.json`](raw/g3_parity.json),
[`raw/g3_parity_gguf.jsonl`](raw/g3_parity_gguf.jsonl),
[`raw/g3_parity_run.log`](raw/g3_parity_run.log).

**Reading — the skill survives, but with a large export penalty (cause not yet
isolated).** Both arms emit 100 % valid JSON (no grammar/format regression from
export), and the GGUF predictions are *plausible but systematically looser* — the
per-sample log shows boxes in the right region with degraded overlap (e.g. iou 0.665,
0.404, 0.371), not garbage. So the deployable artifact **is a working grounding model
(55 % IoU@0.25 in-domain)** — orders of magnitude above the Stage 2 failure (~1 %) and
the aerial floor (2 %) — but it loses ~30 pp vs the bf16 source.

A 30 pp drop is **implausibly large for Q8_0 weight quantization alone** (Q8_0 is
near-lossless for text perplexity). The harness isolates parser, IoU, ground truth
and the input image (the same 512-px PIL is handed to both arms), leaving **two**
non-isolated variables: (a) Q8_0 quantization of the LLaMA backbone, and (b)
llama.cpp's `clip`/mmproj **image-preprocessing path for the Idefics3/SmolVLM
architecture** (resize, image-splitting, normalization), which differs from the HF
`Idefics3` processor. Since the model predicts coordinates relative to *how it sees the
image*, a preprocessing divergence shifts boxes systematically — exactly the observed
signature. To attribute the penalty, a **second parity arm at GGUF F16** is being run
(same harness, `--gguf-path` for the f16 export): if F16 ≈ Q8_0 (~55 %) the loss is the
runtime preprocessing path, not quantization (and Q8_0 is vindicated as a quant
choice); if F16 recovers toward 85 %, the loss is quantization. Result appended below.

#### G3b — F16 vs Q8_0 disambiguation (penalty attributed)

A second GGUF arm at **F16** was exported (`smolvlm_ft3_f16.gguf`, 820,421,632 B,
md5 `31be67f74c5f3269f3234bd3397cf81a`, identical local↔device) and pushed through the
*same* harness / *same* 100 seed-42 samples (`--gguf-path … --quant F16 --skip-hf`):

| Arm | IoU@0.25 | mean_iou | step vs previous |
|---|---|---|---|
| HF bf16 (transformers, local) | **85.0 %** | 0.567 | — |
| GGUF **F16** (llama.cpp, Jetson) | **62.0 %** | 0.323 | **−23 pp** (bf16 → llama.cpp runtime) |
| GGUF **Q8_0** (llama.cpp, Jetson) | **55.0 %** | 0.312 | **−7 pp** (F16 → Q8_0 quantization) |

Raw: [`raw/g3_parity_f16.json`](raw/g3_parity_f16.json),
[`raw/g3_parity_f16_run.log`](raw/g3_parity_f16_run.log),
[`raw/g3_parity_gguf_f16.jsonl`](raw/g3_parity_gguf_f16.jsonl).

**Attribution — the export penalty is dominated by the runtime, not quantization.**
F16 is a near-lossless weight conversion of the bf16 checkpoint (16-bit → 16-bit; the
bf16↔f16 numerical difference on weights is far too small to move IoU by 23 pp). Yet
GGUF F16 already drops **23 pp** below HF bf16. That gap is therefore overwhelmingly
the **transformers → llama.cpp inference path** — specifically llama.cpp's
`clip`/mmproj **image-preprocessing for the Idefics3/SmolVLM architecture** (resize,
image-splitting, normalization) differing from the HF `Idefics3` processor. Because the
model emits coordinates relative to *how it sees the image*, a preprocessing mismatch
shifts every box systematically — matching the observed "plausible but looser"
signature (mean_iou collapses from 0.567 to ~0.32 while parse stays 100 %).

Going F16 → Q8_0 then costs a further **7 pp** — a real but comparatively small,
*expected* quantization cost. So of the total 30 pp export penalty, **~23 pp is runtime
preprocessing and ~7 pp is Q8_0 quantization.**

**Verdict on RQ-S3.3:** the grounding skill **survives export functionally** (Q8_0 GGUF
= 55 % in-domain, a working model) but **fails the ≤5 pp parity gate at both F16
(23 pp) and Q8_0 (30 pp)**. The headline finding for the thesis is not "Q8_0 is too
lossy" — it is that **the dominant cost of deploying an Idefics3-family grounding VLM to
llama.cpp on the edge is the image-preprocessing divergence between the two runtimes,
not the weight quantization.** Q8_0 is a defensible deployment quant (only ~7 pp below
its own runtime's F16 ceiling); recovering the larger 23 pp requires aligning the
preprocessing pipelines (e.g. pinning the HF processor's resize/split to match
llama.cpp's clip, or vice-versa) — logged as a follow-up, not attempted here.

### RQ-S3.5 — Phase C Branch-2 re-run with the fine-tuned model — **BLOCKED (deferred)**

Pre-registration: re-run the Phase C Branch-2 closed-loop VLM-grounding flight test
(`run_phase_c.py`) on the Jetson with the fine-tuned GGUF to see whether the improved
grounding moves the end-to-end tracking metrics.

**Status: cannot be executed — the simulation stack is not installed on the device.**
Branch-2 needs a live **Gazebo Harmonic** + **`ardupilot_gazebo`** SITL world to fly
against; on `ssh jetson` neither is present (`gz`/`ign`/`gazebo` binaries absent,
`~/ardupilot_gazebo` does not exist — checked 2026-06-17). Installing and validating a
full ArduPilot SITL + Gazebo Harmonic toolchain on the Orin Nano is a multi-hour
build/configuration task and a separate work item from VLM fine-tuning; it is **not**
attempted here.

This is an **honest blocked result, not a silent skip.** What it would have measured
(does better in-domain grounding translate to closed-loop tracking) is also partly
mooted by G4: the deployable target domain is *aerial*, where the fine-tuned model is
at the 2 % floor (G4), so a Phase C re-run on aerial frames would not be expected to
beat the zero-shot Branch-2 baseline regardless of GGUF parity. The path is left
**deferred** pending (a) an aerial-trained grounding model and (b) a provisioned
Gazebo/ArduPilot SITL stack on the device.

---

## Decisions

### 2026-06-17 — Measure G3 export parity in-domain (RefCOCO val), not at the aerial noise floor; then disambiguate quant vs runtime with an F16 arm
- **Decision:** Measure RQ-S3.3 (GGUF export parity) with a dedicated paired harness
  (`run_stage3_g3_parity.py`) on **RefCOCO val**, the in-domain set where the skill is
  real (HF = 82.5–85 %), pushing the *same* deterministic seed-42 samples through both
  arms with the *same* parser/IoU. After Q8_0 FAILed (ΔIoU@0.25 = 30 pp), add a
  **second GGUF arm at F16** (same harness, `--gguf-path`/`--skip-hf`) to attribute the
  penalty to either Q8_0 quantization or llama.cpp's Idefics3 image-preprocessing path.
- **Alternatives considered:** (a) reuse the export-run Phase A aerial probe as the G3
  number — rejected: both arms sit at the ~2 % cross-domain floor, so a 5 pp gate is
  statistical noise (a parity "PASS" there would be meaningless). (b) Declare G3 PASS
  from the matching md5 of the transferred file — rejected: bit-identical *transfer*
  says nothing about *behavioural* parity across runtimes. (c) Stop at the Q8_0 FAIL and
  attribute it to quantization — rejected as unsupported: a 30 pp drop is implausible
  for near-lossless Q8_0, so the cause must be isolated before claiming it.
- **Reasoning:** A parity gate is only informative where the metric has dynamic range.
  In-domain RefCOCO has it (85 % ceiling); aerial does not. The F16 arm is the one clean
  control that separates the two confounded variables the harness can't otherwise
  isolate (weight quant vs runtime preprocessing).
- **Tradeoff accepted:** Extra ~870 MB F16 export + transfer and a second Jetson
  server run; the residual non-isolated variable (each runtime's own image
  preprocessing) is folded into the gate by design — it *is* part of "does the exported
  artifact still work," so this is a behavioural, not bit-exact, parity check.
- **Revisit when:** if F16 ≈ Q8_0 (~55 %), the loss is the llama.cpp clip/mmproj
  preprocessing for Idefics3 — investigate the SmolVLM image-split/normalization path
  (or pin transformers' preprocessing to match) before trusting on-device IoU; if F16
  recovers toward 85 %, treat Q8_0 as too lossy for this grounding head and export a
  higher-precision quant for deployment.

### 2026-06-16 — Relaunch Stage 3 from scratch with mid-epoch checkpointing
- **Decision:** Add `--save-every` / `--resume-from` to the trainer, then relaunch
  Run 2 from scratch.
- **Alternatives considered:** (a) resume the crashed run — impossible, no checkpoint
  survived; (b) relaunch as-is and hope the fault doesn't recur — rejected, a second
  7.9 h loss is unacceptable and the fault is non-deterministic; (c) shrink the run
  to reduce exposure — rejected, would weaken the model vs the pre-registered config.
- **Reasoning:** The fault is a rare hardware event, not reproducible from code. The
  cheap, correct insurance is periodic resumable checkpoints; the config itself was
  working (loss descending, no collapse), so it is kept unchanged.
- **Tradeoff accepted:** ~27 min of extra disk churn granularity and a small
  per-checkpoint I/O cost; full restart re-spends the ~7.9 h already lost.
- **Revisit when:** if the fault recurs at a similar step, investigate driver/power
  (Xid in `dmesg`, `nvidia-smi -q`, PSU/thermals) rather than the training code.
