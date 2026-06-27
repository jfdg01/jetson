# RESULTS — Jetson Orin Nano Edge-LLM Benchmarks

Running ledger across all experiment campaigns. Append, never overwrite.
Each row links to the detailed writeup in `results/`. See `CLAUDE.md` for the
fields every run must capture.

This ledger is split into **Part I — Exploratory** (device benchmark campaigns +
grounding Stages 1–4, everything below up to the Part II marker), **Part II —
Principled rebuild (v2)** (single-frame grounding, `v2/principled-rebuild`), and
**Part III — Persistent tracking / object permanence (v3)** (`v3/object-permanence`),
each appended below in turn. Earlier parts are the untouched historical record.

All results: **Jetson Orin Nano 8 GB · 15 W locked (nvpmodel -m 0 + jetson_clocks) ·
llama.cpp commit `57fe1f0` CUDA sm_87 · Q4_K_M quant · ngl=99 (full GPU offload) ·
n_ctx=4096 · pp512 / tg128 benchmark shapes · 5 reps (pp) / 5 reps (tg) · 3 reps (tg512 sustained).**

Idle baseline: **~5.2 W**, **~1820 MB RAM**, **~11–50 MB swap** (zram always partially active).
"Swap hit" = peak swap exceeded idle swap by >50 MB; all models triggered this.

---

## Campaign: llamacpp-upper-bound (2026-06-13)

Single-model baseline to establish the 15 W performance ceiling.
Full writeup: [`results/2026-06-13-llamacpp-upper-bound.md`](results/2026-06-13-llamacpp-upper-bound.md)

| Date | Model / quant | Params | pp512 tok/s | tg128 tok/s | TTFT | Peak RAM | Mean/Peak W | tok/s·W⁻¹ net | J/tok | Peak °C |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-06-13 | Llama-3.2-3B-Instruct Q4_K_M | 3.0 B | 570.0 ± 2.4 | 14.53 ± 0.02 | n/a ¹ | 1.87 GiB wts | 12.5 / 13.6 | ≈1.7 | ≈0.86 | 66.9 |

¹ TTFT not captured in baseline campaign; added in the capability sweep (unit 06 re-run gives 85 ms).

---

## Campaign: model-capability-sweep (2026-06-14)

10-model sweep across 0.5–8 B parameters. All runs same date, same locked clocks.
Full writeup + per-model detail blocks: [`results/2026-06-13-model-capability-sweep.md`](results/2026-06-13-model-capability-sweep.md)

**Note on stddev display:** llama-bench (this build) aggregates `-r N` repetitions into a single CSV row
reporting `avg_ts` / `stddev_ts`. For tg128/tg512 there is only one such row, so ± below is the
within-bench internal stddev (not cross-row). For pp512 there are two measurements (bench + sustained
warm), so ± is the across-run spread. Raw CSVs are in `results/raw/`.

| # | Model / quant | Params | pp512 tok/s | tg128 tok/s | tg512 tok/s | TTFT ms | Peak RAM MB | Idle/Mean/Peak W | tok/s·W⁻¹ (net) | J/tok | Peak °C | Swap peak MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | Qwen2.5-0.5B-Instruct Q4_K_M | 0.5 B | 3027 ± 19 | 71.52 ± 0.07 | 71.12 | 38 | 2637 | 5.17 / 6.57 / 11.25 | 11.77 | 0.157 | 59.9 | 206 |
| 02 | Llama-3.2-1B-Instruct Q4_K_M | 1.0 B | 1534 ± 2 | 35.07 ± 0.07 | 34.90 | 49 | 3497 | 5.26 / 8.42 / 13.32 | 4.35 | 0.380 | 63.3 | 206 |
| 03 | Qwen2.5-1.5B-Instruct Q4_K_M | 1.5 B | 1098 ± 0 | 26.56 ± 0.00 | 26.47 | 59 | 2872 | 5.41 / 7.88 / 11.79 | 4.17 | 0.444 | 63.6 | — ² |
| 04 | Gemma-2-2B-it Q4_K_M | 2.6 B | 728 ± 1 | 15.98 ± 0.00 | 15.87 | 85 | 5818 ³ | 5.25 / 8.47 / 13.17 | 2.02 | 0.824 | 65.7 | 406 |
| 05 | Qwen2.5-3B-Instruct Q4_K_M | 3.0 B | 559 ± 5 | 14.91 ± 0.00 | 14.90 | 91 | 3180 | 5.25 / 11.93 / 12.56 | 2.04 | 0.842 | 65.1 | — ² |
| 06 | Llama-3.2-3B-Instruct Q4_K_M | 3.0 B | 570 ± 0 | 14.60 ± 0.00 | 14.54 | 85 | 3719 | 5.28 / 11.02 / 12.60 | 2.00 | 0.863 | 65.1 | — ² |
| 07 | Phi-3.5-mini-instruct Q4_K_M | 3.8 B | 432 ± 1 | 13.15 ± 0.00 | 12.76 | 114 | 4693 | 5.25 / 12.45 / 13.09 | 1.68 | 0.995 | 65.8 | — ² |
| 08 | Mistral-7B-Instruct-v0.3 Q4_K_M | 7.2 B | 253 ± 0 | 8.39 ± 0.00 | 8.36 | 190 | 5488 | 5.21 / 12.45 / 13.76 | 0.98 | 1.639 | 67.3 | 419 |
| 09 | Qwen2.5-7B-Instruct Q4_K_M | 7.6 B | 266 ± 1 | 7.89 ± 0.00 | 7.86 | 202 | 5465 | 5.23 / 11.92 / 13.80 | 0.92 | 1.749 | 67.1 | — ² |
| 10 | Meta-Llama-3.1-8B-Instruct Q4_K_M | 8.0 B | 245 ± 0 | 7.75 ± 0.00 | 7.72 | 204 | 5953 | 5.25 / 12.04 / 13.92 | 0.89 | 1.795 | 67.4 | 460 |

² Swap peak not separately extracted for these units; raw tegrastats logs in `results/raw/`. These units showed genuine swap *growth* during inference (spot-checked: msweep01 11→206 MB, msweep04 54→406 MB, msweep08 263→419 MB, msweep10 342→460 MB). NB: the original detector flagged any `swap > 0`, which is a false positive when a pre-existing baseline exists — corrected to a growth-over-idle test (see gemma campaign §11). The 10-model sweep numbers survive because the growth was real; the gemma sweep had flat swap and was over-flagged.
³ Gemma-2-2B peak RAM (5818 MB) anomalously exceeds Mistral-7B (5488 MB) — attributed to Gemma-2's large KV cache and CUDA workspace allocation at 4096 ctx; see campaign writeup.

**Cross-campaign consistency check (unit 06 = baseline model):**
Baseline tg128 = 14.53 tok/s · Campaign tg128 = 14.60 tok/s · Δ = +0.07 tok/s (+0.5%) ✓

### Gemma-family sweep (campaign `2026-06-14-gemma-family-sweep`)
Peak RAM is the tegrastats mmap lower bound (see campaign §11); swap column corrected to
*growth over idle* (the original "swap" flags were a pre-existing-baseline false positive).

| Date | Unit | Model + quant | Params | Power | pp512 | tg128 | Peak W | tok/s·W | J/tok | °C | Peak RAM / swap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-06-14 | G1 | gemma-3-270m-it Q8_0 | 0.27B | 15W locked | 7097 | 104.42 | 10.9 | 9.62 | 0.104 | 58 | 2458MB ⁴ · no swap |
| 2026-06-14 | G2 | gemma-3-4b-it q4_0 QAT | 4.0B | 15W locked | 502 | 12.15 | 12.7 | 0.96 | 1.043 | 65 | 4617MB ⁴ · no swap |
| 2026-06-14 | G3 | gemma-4-E2B-it q4_0 QAT | 5.1B | 15W locked | 701 | 20.44 | 11.9 | 1.71 | 0.584 | 64 | 2968MB ⁴ · no swap |
| 2026-06-14 | G4 | gemma-4-E4B-it q4_0 QAT | 8.0B | 15W locked | 362 | 11.42 | 12.7 | 0.90 | 1.110 | 66 | 4374MB ⁴ · +97MB swap |
| 2026-06-14 | G5 | gemma-3-12b-it q4_0 QAT | 12.0B | 15W locked | **FAILED — CUDA OOM at load** | — | 6.6 | — | — | 57 | weights ~7.7GiB > free VRAM ⁵ |

⁴ tegrastats RAM under-counts mmap'd weights (demand-paged; pages not accessed during the
short benchmark may not be resident). Authoritative `--no-mmap` resident footprints (campaign
§11.3): G2 **4632 MiB** (vs tegrastats 4617 MB — close because G2's weights are small enough
to be fully accessed); G3 **3677 MiB** (vs 2968 MB — 709 MiB gap: PLE shared matrices were
not all paged in during inference); G4 **N/A** (4.7 GiB malloc > free RAM; mmap is essential
for G4 on the Orin Nano — see §11.3).
⁵ G5 never loaded: `cudaMalloc` failed allocating 7694 MiB with `-ngl 99` (full offload, auto-fit
aborted). Hard OOM at load, not the swap-thrash HG5 predicted. See campaign §8 (Unit G5) / §11.
| 2026-06-14 | V1 | SmolVLM-256M-Instruct Q8_0 | 0.26B | 15W locked vlm-server | per_frame=304ms | 3.29Hz | img_tok=64 | 6.6W mean | 1777MB |  |
| 2026-06-14 | V2 | SmolVLM-500M-Instruct Q8_0 | 0.5B | 15W locked vlm-server | per_frame=338ms | 2.96Hz | img_tok=64 | 7.2W mean | 2241MB |  |
| 2026-06-14 | V3 | gemma-3-4b-it q4_0 | 4.0B | 15W locked vlm-server | per_frame=9576ms | 0.10Hz | img_tok=256 | 9.7W mean | 6414MB | swap |
| 2026-06-14 | V4 | gemma-4-E2B-it q4_0 QAT | 5.1B | 15W locked vlm-server | per_frame=3286ms | 0.30Hz | img_tok=144 | 8.6W mean | 4616MB | thinking-on INVALID (token budget exhausted on chain-of-thought) |
| 2026-06-14 | V5 | gemma-4-E4B-it q4_0 QAT | 8.0B | 15W locked vlm-server | per_frame=5359ms | 0.19Hz | img_tok=144 | 9.4W mean | 6444MB | thinking-on INVALID |
| 2026-06-14 | V4 | gemma-4-E2B-it q4_0 QAT | 5.1B | 15W locked vlm-server --reasoning off | per_frame=2035ms | 0.49Hz | img_tok=144 | 8.2W mean | 4616MB | canonical |
| 2026-06-14 | V5 | gemma-4-E4B-it q4_0 QAT | 8.0B | 15W locked vlm-server --reasoning off | per_frame=2963ms | 0.34Hz | img_tok=144 | 8.8W mean | 6444MB | swap canonical |
| 2026-06-15 | S1 | SmolVLM-256M-Instruct Q8_0 | Phase A grounding | 15W locked | format=A parse=0% iou@0.25=0% iou@0.5=0% mean_iou=0.000 | 3.58Hz | 2338MB  |
| 2026-06-15 | S2 | SmolVLM-500M-Instruct Q8_0 | Phase A grounding | 15W locked | format=A parse=4% iou@0.25=0% iou@0.5=0% mean_iou=0.001 | 1.20Hz | 2734MB  |

---

## Campaign: toy-nl-demo (2026-06-15)

End-to-end natural-language drone command demo (pipeline mechanics validation).
Script: [`experiments/demo_nlcommand.py`](experiments/demo_nlcommand.py)
Full writeup: [`results/2026-06-15-toy-demo/README.md`](results/2026-06-15-toy-demo/README.md)
**Device:** Jetson Orin Nano 8 GB · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87 · SmolVLM-500M Q8_0

### TURN commands (no VLM)

| Date | Command | Verb | Direction | yaw_rate_dps | parse_ok |
|---|---|---|---|---|---|
| 2026-06-15 | "turn around the right corner" | TURN | around | 40.0 | true |
| 2026-06-15 | "turn left" | TURN | left | -20.0 | true |

TURN commands resolve in <1 ms via a closed heuristic; no Jetson call, no model loaded.

### FOLLOW / ZOOM commands — zero-shot VLM grounding on VisDrone nadir frames

| Date | Command | Image (res) | VLM latency ms | parse_ok | VLM raw (summary) | Notes |
|---|---|---|---|---|---|---|
| 2026-06-15 | "follow that white car" | `0000001_05499_d_0000010.jpg` (1920×1080) | 534 | **false** | Template echo `{"x1":.., …}` (no coords) | Model repeated format without filling values |
| 2026-06-15 | "zoom on that red bird" | `0000026_00000_d_0000024.jpg` (1360×765) | 2046 | **false** | Whole-image bbox `[0,0,1360,765]` (degenerate, filtered) | SmolVLM returned full-frame coords when object absent |

**Finding:** Zero-shot SmolVLM-500M cannot ground specific objects in dense nadir drone frames.
Both failures are consistent with Phase A (S2: parse 4%, IoU@0.25 = 0%) and were the
pre-registered expected outcome. The pipeline mechanics work end-to-end; grounding quality
requires Stage-2 fine-tuning.

---

## Campaign: phase-b-sitl (2026-06-15)

SITL pipeline-integration validation (oracle bbox -> ByteTrack -> cascade PID -> pymavlink offboard).
Run on the **local x86_64 workstation**, not the Jetson — no on-device throughput/power columns apply,
so this campaign does not produce a standard device-ledger row. Full writeup:
[`results/2026-06-14-stage1-baseline/phase-b-sitl.md`](results/2026-06-14-stage1-baseline/phase-b-sitl.md)

| Date | Trials | Loop Hz | Mean pixel err (px) | Oracle coverage | Track losses | Result |
|---|---|---|---|---|---|---|
| 2026-06-15 | 3 x 60s | 19.99 +/- 0.0 | 12.9 +/- 0.0 | 100% | 0 | **PASS** |

Zero cross-run variance is real, not duplicated rows: the rover trajectory is programmatic and
re-anchored to the copter relative position each trial, so initial conditions are identical and the
P-controller converges to the same steady-state lag (~12 px) every run. Runs start at different
absolute copter N (0.01 / 16.2 / 32.4 m, carried drift) yet re-anchor 0.5 m ahead identically.
Threshold (Hz>=1, px_err<50, coverage>=80%) met honestly; no widening.

---

## Campaign: phase-c-vlm (2026-06-15)

Phase C closed-loop VLM-in-the-loop validation. Full writeup:
[`results/2026-06-14-stage1-baseline/phase-c-vlm.md`](results/2026-06-14-stage1-baseline/phase-c-vlm.md)

| Date | Mode | Platform | Key metrics | Result |
|---|---|---|---|---|
| 2026-06-15 | inject-oracle Branch-1 | x86_64 SITL | hz=19.99 px_err=89.4 valid=100% reseed=0.000s | **b1=PASS** |
| 2026-06-15 | vlm zero-shot Branch-2 | x86_64 SITL + Gazebo + Jetson SmolVLM-500M Q8_0 | hz=19.99 px_err=190.5 valid=12.5% track_cov=21% | b2=negative (expected) |

Branch-2 "negative" is the pre-registered expected outcome: zero-shot SmolVLM cannot ground
targets in aerial frames reliably (12.5% valid, IoU near 0). Motivates Stage 2.

---

## Stage 2: fine-tuning (COMPLETE — 2026-06-16)

Fine-tune SmolVLM-500M-Instruct on RefDrone + VisDrone aerial grounding data.  
Pre-registration: [`results/stage2-finetune/README.md`](results/stage2-finetune/README.md)  
Full writeup: [`results/stage2-finetune/train-log.md`](results/stage2-finetune/train-log.md)

Training: 1 epoch, 23,437 steps, 32,723s (~9.1h), mean loss=0.8341, exit code 0.  
Checkpoint: `smolvlm_ft/` (merged) + `smolvlm_ft/epoch1/` (LoRA adapter).

| Date | Model | Epoch | Parse rate | IoU@0.25 | G1 | G2 | Result |
|---|---|---|---|---|---|---|---|
| 2026-06-16 | SmolVLM-500M-Instruct LoRA r=16 (text only) | 1 | **100%** | **1.0%** | PASS | **FAIL** | **G2 FAIL — mode collapse** |

**Finding:** Model learned output format (100% parse rate) but collapsed to predicting a
near-constant bounding box (~[223,111,229,120] in 512×288 space) for all inputs. Root cause:
LoRA applied only to text backbone; frozen SigLIP vision encoder cannot update spatial
feature representations. Text side converged to predicting the marginal mean of the training
bbox distribution. Meaningful negative result: demonstrates limit of text-only LoRA for
spatial grounding in VLMs.

Full diagnosis: [`results/stage2-finetune/train-log.md#root-cause-diagnosis`](results/stage2-finetune/train-log.md)

---

## Stage 3 — RefCOCO fine-tuning (methodological correction)

Fine-tune SmolVLM-500M-Instruct on RefCOCO referring expressions, normalized 0–1000
coords, attention+MLP LoRA. Fixes the Stage 2 mode-collapse (well-posed targets +
more adaptation capacity).
Pre-registration: [`results/stage3-refcoco-finetune/README.md`](results/stage3-refcoco-finetune/README.md)
Full writeup: [`results/stage3-refcoco-finetune/train-log.md`](results/stage3-refcoco-finetune/train-log.md)

| Date | Run | Result | Notes |
|---|---|---|---|
| 2026-06-16 | Run 1 | **CRASHED** | CUDA `unspecified launch failure` (GPU hardware fault, not code) at batch 17,450/25,000 (~7.9 h, 70% of epoch 1). Loss descending healthily (1.25→0.94, no collapse). All progress lost — old script had no mid-epoch checkpoint. |
| 2026-06-17 | Run 2 | **SUCCESS** | Full epoch, 11.0 h, 270 W cap. **G1 parse_rate=100%**, **G2 IoU@0.25=82.5%** (gate ≥30%), **G2b center_std=200.5** (non-degenerate), mean_iou=0.527. Clean loss descent (1.28→0.97), no collapse. Merged checkpoint `smolvlm_ft3/` ready for GGUF export. |

**Negative result (hardware):** a transient RTX 3090 CUDA fault killed a long run that
was training correctly. Trainer hardened with resumable mid-epoch checkpointing
(`--save-every` / `--resume-from`) before relaunch.

**Positive result (Run 2):** the relaunched run completed cleanly and **passed all
training-side gates** — input-dependent boxes overlapping ground truth 82.5 % of the
time (IoU@0.25), a complete reversal of the Stage 2 RefDrone mode collapse
(IoU@0.25 ≈ 1 %). The methodological correction (well-posed RefCOCO + normalized-0–1000
coords + attention+MLP LoRA) is validated. On-device GGUF export + Phase A/C validation
(G3/G4/RQ-S3.5) is next. Full diagnosis:
[`results/stage3-refcoco-finetune/train-log.md`](results/stage3-refcoco-finetune/train-log.md)
| 2026-06-17 | S2 | SmolVLM-500M-Instruct Q8_0 | Phase A grounding | 15W locked | format=S3 parse=100% iou@0.25=2% iou@0.5=0% mean_iou=0.025 | 1.77Hz | 2738MB  |
| 2026-06-17 | G3/RQ-S3.3 | SmolVLM-500M-ft3 — HF bf16 vs GGUF Q8_0 | export parity (RefCOCO val, n=100, paired seed42) | 15W | HF bf16 iou@0.25=85.0% mean_iou=0.567 · GGUF F16 iou@0.25=62.0% mean_iou=0.323 · GGUF Q8_0 iou@0.25=55.0% mean_iou=0.312 · **ΔIoU@0.25=30.0pp → FAIL** (gate ≤5pp); both parse=100%. Disambiguated: −23pp = transformers→llama.cpp Idefics3 image-preprocessing divergence (runtime), −7pp = Q8_0 quantization. Skill survives export functionally; fails strict parity gate. | — | — |

---

## Stage 4 — RefCOCO→RefDrone curriculum (deployable *aerial* grounding)

Curriculum fine-tune: init from the Stage 3 RefCOCO-merged weights (`smolvlm_ft3`), then
LoRA fine-tune on the **well-posed RefDrone subset** (only the 4,101 train / 439 val
captions with exactly one box — the structural mirror of the Stage 3 fix, removing the
Stage 2 ill-posed-target root cause at the source). 3 epochs, LR 1e-4 cosine, local RTX 3090.
Pre-registration: [`results/stage4-refdrone-curriculum/README.md`](results/stage4-refdrone-curriculum/README.md)
Full writeup: [`results/stage4-refdrone-curriculum/train-log.md`](results/stage4-refdrone-curriculum/train-log.md)

| Epoch | mean_loss | parse_rate | IoU@0.25 | mean_iou | center_std |
|---|---|---|---|---|---|
| 1 | 1.0287 | 100.0% | 12.5% | 0.072 | 214.1 |
| 2 | 0.9478 | 100.0% | 16.0% | 0.087 | 214.3 |
| 3 | 0.9168 | 100.0% | **19.5%** | 0.109 | 211.5 |

**Gate verdicts (RefDrone well-posed val, n=200):**
- **G1 parse_rate ≥90% → PASS** (100.0%).
- **G2b mode-collapse sentinel (center_std non-degenerate) → PASS** (211.5; no collapse — the
  well-posed fix held, definitively distinct from the Stage 2 failure mode).
- **G4-S4 aerial IoU@0.25 ≥20% (primary go/no-go) → NARROW MISS** (19.5%, 0.5pp short).

**Result framing.** This is a **~10× lift over the 2.0% RefCOCO-init cross-domain floor**
(RQ-S3.4) and ~20× over the Stage 2 RefDrone collapse (≈1%). IoU climbed monotonically every
epoch (12.5→16.0→19.5%) and loss was still descending when the cosine LR annealed to ~0, so
the model had not plateaued — the gate miss is a *budget/capacity* boundary, not a failure
mode. The well-posed-subset + curriculum-init approach is **validated**: it converts the
intractable Stage 2 target into a learnable aerial grounding skill on a frozen-SigLIP
500M VLM. Honest negative-result framing per pre-registration: VisDrone objects are 5–30 px
(2–11 px after the 512 long-edge resize) through a frozen encoder; the documented next levers
are **largest-box augmentation** (→~12,339 samples) and/or **higher input resolution**.
Merged checkpoint: `smolvlm_ft4/`.

---

# Part II — Principled rebuild (v2)

<!-- v2 campaign result rows are appended below, in chronological order. -->

## Phase 0 — Backend-fidelity harness (2026-06-17)

Backend-agnostic eval spine (HF / GGUF / Jetson behind one interface, all importing
`grounding.contract`) + HF↔GGUF parity probe, run *before* any GPU training so the
deployment-fidelity gap is a known quantity. Spine picked by the numbers.
Full writeup: [`results/2026-06-17-phase0-backend-fidelity/`](results/2026-06-17-phase0-backend-fidelity/README.md)

Eval set: RefCOCO `validation`, seed-42 shuffle, first N (same subset construction as
the Part-I Stage-3 trainer). Local RTX 3090; `.venv-ft` (torch 2.6.0+cu124). Metrics
from the shared contract (IoU@0.25, parse_rate, mean IoU, `center_std`).

| Date | Step | Backend | Model | n | IoU@0.25 | parse_rate | mean IoU | center_std | Manifest | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-06-17 | 0a anchor | HF bf16 | smolvlm_ft3 | 100 | **85.0%** | 100.0% | 0.567 | 187.8 | `runs/20260617T115913Z` | ✅ reproduces Part-I 82.5% (n=200) |
| 2026-06-17 | 0b parity | GGUF F16 | smolvlm_ft3 | 100 | **69.0%** | 100.0% | 0.393 | 149.7 | `runs/20260617T121539Z` | ✅ runtime gap −16.0 pp vs HF (CPU build, `57fe1f0`) |
| 2026-06-17 | 0b parity | GGUF Q8_0 | smolvlm_ft3 | 100 | **67.0%** | 100.0% | 0.389 | 148.0 | `runs/20260617T121756Z` | ✅ quant gap −2.0 pp vs F16 — runtime ≫ quant reproduced |
| 2026-06-17 | 0c.2 spine | HF bf16 | SmolVLM-500M **base** | 100 | 0.0% | 9.0% | 0.004 | 61.3 | `runs/20260617T165959Z` | base collapse — no grounding to deploy |
| 2026-06-17 | 0c.2 spine | HF bf16 | **Qwen2-VL-2B base** | 100 | **15.0%** | 24.0% | 0.393 | 162.1 | `runs/20260617T170339Z` | ✅ grounding-native zero-shot (healthy center_std) |
| 2026-06-17 | 0c.2 spine | GGUF F16 | Qwen2-VL-2B base | 100 | 13.0% | 18.0% | 0.548 | 198.7 | `runs/20260617T171534Z` | runtime gap −2.0 pp vs HF |
| 2026-06-17 | 0c.2 spine | GGUF Q8_0 | Qwen2-VL-2B base | 100 | 14.0% | 19.0% | 0.533 | 187.5 | `runs/20260617T172502Z` | quant +1.0 pp vs F16 — fidelity ~8× better than SmolVLM |

**Phase 0 gate ✅ — v2 spine = Qwen2-VL-2B** (RQ-0.3 green): grounding-native zero-shot
(15% vs SmolVLM-base 0%), deployment fidelity gap −2pp ≪ SmolVLM-ft3's −16pp (0b), and
native dynamic resolution attacks the tiny-object resolution ceiling (constraint #2).
Phase 0 complete → proceed to Phase 1 (dataset audit gate).

## Phase 1 — Dataset audit gate (2026-06-17)

Box-per-caption + object-size distributions computed and baked into the canonical
schema *before* any GPU run — the gate that would have caught the Stage-2 ill-posed
target for free. CPU-only annotation statistics (no model, no images decoded).
Full writeup: [`results/2026-06-17-phase1-dataset-audit/`](results/2026-06-17-phase1-dataset-audit/README.md)

**RQ-1.1 — well-posedness (box-per-caption).** The Stage-2 sentinel reproduces exactly.

| Split | Captions | Real boxes | Mean boxes/caption | Well-posed (=1 box) | Trainable budget | Manifest |
|---|---|---|---|---|---|---|
| RefDrone train | 12 339 | 46 874 | **3.80** | 4 101 (**33.2%**) | **4 101** (0 missing) | `runs/20260617T173529Z-audit-refdrone-train` |
| RefDrone val | 1 421 | 4 734 | **3.33** | 439 (**30.9%**) | **439** (0 missing) | `runs/20260617T173529Z-audit-refdrone-val` |
| RefCOCO val (control) | 2 000 | 2 000 | **1.00** | 2 000 (**100%**) | 2 000 | `runs/20260617T173532Z-audit-refcoco-validation` |

**RQ-1.2 — object size (√area px), pre/post the 512 long-edge resize.** Constraint #2 in numbers.

| Split | view | p5 | p10 | p25 | p50 | p75 | p90 | p95 |
|---|---|---|---|---|---|---|---|---|
| RefDrone train | pre | 17.3 | 20.8 | 29.5 | 47.3 | 76.8 | 115.3 | 149.3 |
| RefDrone train | **@512** | **6.0** | 7.2 | **10.2** | **15.9** | 25.4 | 38.6 | 49.7 |
| RefDrone val | @512 | 5.5 | 6.5 | 9.4 | 14.6 | 23.8 | 35.9 | 44.7 |
| RefCOCO val (control) | @512 | 106.9 | 116.1 | 136.4 | **172.0** | 224.4 | 281.6 | 327.2 |

**Phase 1 gate ✅** — the well-posed RefDrone target is one-box-per-caption by construction
(`assert_well_posed` FAILS raw 0.332 / PASSES filtered 1.000), trainable budget known
(**4 101 train / 439 val**, 0 missing), and the aerial object-size distribution quantified.
The two gating numbers: **33% of captions usable** (small budget → favours RefCOCO warm-start +
`largest_box_aug` lever) and **median object ≈16 px / bottom-quartile 6–10 px @512** (resolution
is the dominant lever). Phase 1 complete → proceed to Phase 2 (resolution strategy).

## Phase 2 — Resolution strategy (2026-06-17)

Input long-edge resize made a pre-registered, measured variable. No-training ladder on
the Phase-0 harness over RefDrone well-posed val (**n=439**, Qwen2-VL-2B **base**,
HFBackend bf16 greedy, verbatim contract) — picks the resolution *by the numbers*.
Full writeup: [`results/2026-06-17-phase2-resolution/`](results/2026-06-17-phase2-resolution/README.md)

| Date | Arm | max_side | parse | **IoU@0.25** | mean_iou | center_std | Manifest | Note |
|---|---|---|---|---|---|---|---|---|
| 2026-06-17 | ladder | 512  | 100.0% | 4.1%  | 0.031 | 129.1 | `runs/20260617T190608Z` | Part-I setting — resolution-starved |
| 2026-06-17 | ladder | 768  | 100.0% | 10.7% | 0.065 | 157.9 | `runs/20260617T191130Z` | still below gate, pre-elbow |
| 2026-06-17 | ladder | **1024** | 91.8% | **30.3%** | 0.202 | 192.0 | `runs/20260617T191739Z` | ✅ **chosen** — elbow, clears 20% gate zero-shot |
| 2026-06-17 | ladder | 1280 | 92.0% | 38.7% | 0.313 | 196.1 | `runs/20260617T192436Z` | highest, but +8.4pp past elbow → Phase-3 lever |

**Phase 2 gate ✅ — v2 resolution = `max_side=1024`** (RQ-2.1/2.2/2.3 green): resolution is
**the** dominant lever (4.1% → 38.7% IoU@0.25, a 9.4× swing with frozen weights — reframes
Part-I's 19.5% miss as resolution-starved at 512); `center_std` rises monotonically (129 → 196,
≫ collapse floor 61) so no collapse risk; the elbow is at 1024 (the +19.6 pp 768→1024 jump
dominates, capturing ~78% of the 1280 ceiling) and it already **clears the 20% gate before any
training**, with 1280 held in reserve as the pre-measured Phase-3 lever. The 8 GB-Jetson
deploy footprint motivates 1024 over 1280. Phase 2 complete → proceed to Phase 3 (train).

## Phase 3 — Config-driven LoRA fine-tune (2026-06-17 / 2026-06-18)

One config-driven LoRA loop (`grounding/train/{config,trainer}.py`, replacing the Part-I
per-stage forks) on the full Phase-0/1/2 stack: **Qwen2-VL-2B + RefDrone well-posed (4101
train / 439 val) + `max_side=1024`**. LoRA r16/α32 on the LLM attn+MLP (vision frozen,
18.5 M trainable = 0.83%), lr 2e-4, 3 epochs, effective batch 16, verbatim contract, greedy
eval. Full writeup: [`results/2026-06-17-phase3-train/`](results/2026-06-17-phase3-train/README.md)

| Model | max_side | n | parse | **IoU@0.25** | mean_iou | center_std | Manifest |
|---|---|---|---|---|---|---|---|
| Qwen2-VL-2B **base** (Phase 2) | 1024 | 439 | 91.8% | 30.3% | 0.202 | 192.0 | `runs/20260617T191739Z` |
| Qwen2-VL-2B **+ LoRA** (in-loop) | 1024 | 200 | 100.0% | 65.0% | 0.497 | 226.6 | `runs/20260617T212559Z` |
| Qwen2-VL-2B **+ LoRA** (full val) | 1024 | **439** | **100.0%** | **59.5%** | **0.451** | **215.2** | `runs/20260617T212559Z` |

**Phase 3 gate ✅ — PASS, decisively.** Full-val **IoU@0.25 = 59.5%** is ~3.0× the 20% gate
and ~3.1× Part-I Stage 4's 19.5% on the same aerial task; gate cleared at **epoch 1** so
neither reserved lever (`largest_box_aug`, `max_side=1280`) was needed. Health: parse 100%
(fine-tune fixed base 91.8%→100%), `center_std` 215 and rising — ≈3.5× the ~61 collapse
floor, opposite of Stage-2 collapse. The 19.5%→59.5% gain decomposes cleanly: **resolution**
(base 512→1024 = 4.1%→30.3% zero-shot, Phase 2) **× the LoRA fine-tune** (30.3%→59.5% on top).
Merged checkpoint `runs/v2/phase3-refdrone-1024/`. Phase 3 complete → proceed to Phase 4
(export & deploy); HF full-val **59.5% is the fidelity reference** for the deployed GGUF.

## Phase 4 — Export & deploy (GGUF on Jetson, fidelity disambiguation) (2026-06-18)

Export the Phase-3 merged checkpoint to GGUF (`grounding/export/to_gguf.py`, `convert_hf_to_gguf.py`
@ pinned llama.cpp `57fe1f07…`) and run the **F16-vs-Q8_0 disambiguation on the Jetson** over the
full RefDrone well-posed val (n=439), same contract path as the HF reference. The Jetson runs the
*same pinned commit* as the local build (no backend-version confound) under CUDA full-offload, 15 W,
clocks locked. Full writeup: [`results/2026-06-18-phase4-export-deploy/`](results/2026-06-18-phase4-export-deploy/README.md)

| Backend | size | n | parse | **IoU@0.25** | mean_iou | center_std | Manifest |
|---|---|---|---|---|---|---|---|
| HF bf16 **(reference)** | — | 439 | 100.0% | **59.5%** | 0.451 | 215.2 | `runs/20260617T212559Z` |
| GGUF **F16** (Jetson) | 3.09 GB | 439 | 100.0% | **62.2%** | 0.466 | 218.2 | `runs/20260617T233529Z` |
| GGUF **Q8_0** (Jetson) | 1.65 GB | 439 | 100.0% | **62.6%** | 0.468 | 217.4 | `runs/20260618T001147Z` |

**Phase 4 gate ✅ — PASS, decisively.** Deployed IoU *exceeds* the HF reference: **runtime/preprocessing
gap (HF→F16) = −2.7pp** and **quant gap (F16→Q8_0) = −0.5pp** — both negative (deployed beats HF) and
within n=439 noise, i.e. **no measurable fidelity loss**. The Part-I catastrophe (**−23pp** runtime +
**−7pp** quant on SmolVLM/Idefics3) does **not** reproduce on Qwen2-VL — the payoff of picking the spine
by deployment fidelity in Phase 0c, *before* any GPU training. **Q8_0 is the deployment artifact**:
≈½ the weights (1.65 vs 3.09 GB) at indistinguishable accuracy, fitting the 8 GB unified memory with
headroom. mmproj is bit-equivalent to base (vision frozen). Jetson server runs single-slot, no prompt
cache (`-np 1 --cache-ram 0 --no-cache-idle-slots`) to avoid the 8 GB OOM. **Phases 0–4 complete.**

---

# Part III — Persistent tracking / object permanence (v3)

Branch `v3/object-permanence`. The problem moves from a single frame to a **video
stream**: keep a lock on a *moving* referred target across occlusion / scale change /
out-of-frame and close a following loop. Headline metrics become **temporal** (track
continuity / SOT success-precision, ID switches, re-acquisition time, oracle-coverage,
closed-loop following error) — single-frame IoU@0.25 is retained only as a per-anchor
sanity check.

**Charter pre-registered (2026-06-18):**
[`results/2026-06-18-part3-charter/README.md`](results/2026-06-18-part3-charter/README.md)
— paradigm shift, the two binding constraints (#1 cadence-vs-dynamics budget; #2
identity-through-absence), the forced sparse-VLM-anchor + 20 Hz-fast-tracker
architecture, the temporal metric suite, and the proposed gated phase plan T0–T4.

## T0 — Cadence & dynamics harness (measure before design) (2026-06-18)

On-Orin anchor-cadence sweep + 20 Hz tracker-cost profile + analytic target-dynamics &
re-ID crop geometry, to quantify the **cadence-vs-dynamics budget** that governs every
later phase. Device: Orin Nano 8 GB, 15 W (`nvpmodel -m 0`), `jetson_clocks` not
confirmed engaged (conservative default-15 W point). Anchor = deployed Qwen2-VL-2B Q8_0
(`phase3-refdrone-1024-q8_0`), llama.cpp `57fe1f0`, `-ngl 99`, greedy. Full writeup:
[`results/2026-06-18-t0-cadence/`](results/2026-06-18-t0-cadence/README.md)

| Probe | Measurement | Value |
|---|---|---|
| **T0a anchor cadence** | wall Hz @ 512 / 768 / 1024 long-edge (N=8) | **0.44** / 0.27 / 0.16 Hz |
| | prefill (image encode) @ 512/768/1024 | 1113 / 2431 / 5111 ms (dominant, ∝ pixels) |
| | decode (resolution-independent) | ~1.1 s / 24 tok ≈ 21.6 tok/s |
| | power / thermal / mem | idle 5.2 W, mean 10.9 W, peak 11.7 W; 62.7 °C; 4849 MB; no swap |
| **T0b tracker cost** | `ByteTracker.update()` median (1180 fr) | **0.051 ms** → ~1000× headroom under 50 ms |
| | coast horizon (`MAX_LOST_FRAMES=30`) | **1.5 s** @ 20 Hz |
| **T0c dynamics** | target px velocity (nadir, 1–10 m/s, 10–30 m) | 18.5 – 554 px/s (≤ 27.7 px/frame) |
| | scale-change under 2 m/s descent | 1.0 %/frame median, 2.0 % max |
| **T0d re-ID geometry** | target crop @ 10 / 20 / 30 m | 111×222 / 55×111 / 37×74 px |

**T0 gate ✅ — PASS.** Two budgets with opposite verdicts: (1) **inter-anchor tracking
is comfortable** — per-frame motion ≤ 27.7 px is tiny vs the 110–222 px box and the
tracker is ~free (0.05 ms), so the fast loop carries the lock between anchors with room
to spare for a re-ID head (constraint #2 is compute-free); (2) **recovery-after-loss is
tight** — `anchor_period (2.27 s @ 512) > coast_horizon (1.5 s)`, so re-acquisition must
be **event-triggered on loss**, not timer-only, and the fast tracker *must* hold identity
through gaps — quantifying *why* the two-tier architecture is mandatory and *why* Phase C
(memoryless @ ~1 Hz) collapsed to ~0 % on a moving target. **Anchor spine confirmed by
the numbers: Qwen2-VL-2B Q8_0 @ 512 long-edge** (640×480 camera + downscale-only resize
⇒ 768/1024 add latency with no fidelity gain). Re-ID appearance head geometrically
feasible at 10–20 m (≥ 55 px), marginal at 30 m; embedding-separability check carried
into T1.

### Part III — T1 data & temporal contract (2026-06-18) ✅ GATE PASS

T1b extended `grounding/contract.py` with the §6 temporal-metric suite (SOT
success/precision, success-AUC, ID-switches, identity purity, re-acquisition time,
oracle-coverage, following error, track-loss events), pure-stdlib & pytest-locked.
T1a added `experiments/sitl/clip_recorder.py`: deterministic trajectory→GT clips (no
renderer — boxes, not pixels, are what the gate scores; Gazebo deferred to T2) +
the **memoryless-ByteTrack baseline** (event-triggered, appearance-blind re-acq).
Full writeup: [`results/2026-06-18-t1-temporal-contract/`](results/2026-06-18-t1-temporal-contract/README.md).

| Clip | SOT succ | coverage | **ID sw** | **purity** | reacq fail | follow px |
|---|---|---|---|---|---|---|
| `clean_follow` (control) | 1.000 | 1.000 | 0 | 1.000 | 0/1 | 0.03 |
| `crossing_occlusion` (4 stressors) | 0.827 | **0.575** | **1** | **0.725** | **1/2** | 67.7 |

**T1 gate ✅ — PASS.** A scored eval clip set exists with reproducible GT and the
temporal metrics run deterministically (control near-perfect → suite isn't pessimistic;
hard clip exposes the failure). The memoryless tracker **re-locks the wrong same-class
object after occlusion** — purity 0.725, 1 ID-switch, 1/2 re-acquisitions failed,
coverage 0.575: **constraint #2 (object permanence) made numeric, and the baseline T2
must beat.** Verify: `python experiments/sitl/{oracle_bbox,clip_recorder}.py` + `make test`.

### Part III — T2 permanence mechanism (2026-06-24) ✅ GATE PASS

`experiments/sitl/reid_policy.py` adds an **appearance memory**: store the target's
descriptor at acquisition, re-acquire by minimum descriptor distance behind a
**refuse-to-lock gate**, EMA-refine while locked. Pixels aren't rendered yet (T1
decision), so appearance is a per-instance scalar with **noise scaling by crop size** —
one `snr` knob = the T0d separability-vs-range frontier. Tracker + §6 assembly reused
unchanged. Full writeup: [`results/2026-06-24-t2-permanence/`](results/2026-06-24-t2-permanence/README.md).

| policy (`crossing_occlusion`) | **ID sw** | **purity** | reacq fail | coverage | SOT succ | follow px |
|---|---|---|---|---|---|---|
| memoryless baseline (T1) | 1 | 0.725 | 1 | 0.575 | 0.827 | 67.7 |
| **re-ID, snr ≳ 1** | **0** | **1.000** | **0** | **0.695** | **1.000** | **0.13** |
| re-ID, snr ≤ 0.8 (below knee) | 1 | 0.751 | 1 | 0.575 | 0.827 | 67.7 |

**T2 gate ✅ — PASS** (separable regime, snr ≳ 1): ID switches 1→0, failed re-acq 1→0,
identity purity 0.725→**1.000**, coverage 0.575→**0.695** (= visible-frame ceiling
139/200). The appearance gate **fully resolves the wrong-object re-lock** above the knee
and **degrades to the baseline** below it (noise ≥ van/decoy gap) — an honest,
separability-dependent win, the quantitative statement of *when* appearance memory helps.
Control `clean_follow` unchanged (purity/coverage 1.0 → no regression). Verify:
`python experiments/sitl/reid_policy.py` + `make test`.

### Part III — T3 closed-loop integration in SITL (2026-06-24) ✅ GATE PASS

`experiments/run_t3.py` closes the loop: the lock **drives the camera** (cascade-PID →
body velocity → copter → re-projection), so a wrong lock steers the aircraft off the true
target and the failure compounds — the exact Phase-C mechanic, now an **identity** test
(same-class distractor crosses, briefly occludes the target at t = 29–31 s, then veers
away). Two policies share one harness, 20 Hz control / 1 Hz detect, 10 m alt. Reuses
oracle_bbox + bytetrack + cascade_pid + offboard + the T2 `_observe`. Headline: true-target
oracle-coverage % (Phase-C ≈ **0 %** on a moving target). Full writeup:
[`results/2026-06-24-t3-closed-loop/`](results/2026-06-24-t3-closed-loop/README.md).

| policy | kinematic A/B coverage | live ArduCopter SITL coverage | occlusion frames |
|---|---|---|---|
| memoryless baseline | 49.2 % | 53.7 % | 40 |
| **re-ID (snr 8)** | **97.6 %** | **71.5 %** | 40 |

**T3 gate ✅ — PASS:** Phase-C ≈ 0 % → re-ID **97.6 %** kinematic / **71.5 %** live SITL,
both ≫ 0 % on a *moving* target. The memoryless baseline (49–54 %) shows the win is the
**permanence mechanism** (appearance gate holds identity through the occlusion/crossing),
not just the faster loop. Live margin is smaller than kinematic because real PID-lag +
inertia lower *both* policies' absolute coverage, but direction + mechanism hold. Verify:
`.venv-ft/bin/python experiments/run_t3.py` (3 self-checks) + `--live` under `.venv`.

### Part III — T4 on-Orin deployment + sim-to-device (2026-06-24) ✅ GATE PASS

`experiments/run_t4.py` runs the **integrated two-tier loop on the actual Orin Nano 8 GB
(15 W)** and reconciles the **device** timings against the T0 cadence budget — the
deployment gate. T0 had measured the anchor on the Orin (T0a) but the tracker on the dev
box (T0b); T4 closes that. Reuses the T0 harness wholesale; one file (`bytetrack.py`)
pushed to the device. Full writeup:
[`results/2026-06-24-t4-deployment/`](results/2026-06-24-t4-deployment/README.md).

| tier | dev box / T0a | **Orin (T4)** | sim-to-device |
|---|---|---|---|
| fast: `ByteTracker.update` median (p99) | 0.051 ms (0.103) | **0.143 ms (0.291)** | 2.8× slower, **99.7 % of 50 ms budget free** |
| slow: VLM anchor @512 wall | 2265 ms (0.44 Hz) | **2264 ms (0.44 Hz), 100 % parse** | **−0.03 %** (deployed model intact) |

**T4 gate ✅ — PASS:** both tiers fit their roles on the metal — fast tracker holds 20 Hz
with ~350× headroom, real deployed Qwen2-VL-2B Q8_0 anchor reproduces the T0a cadence and
emits valid bboxes every rep; anchor period 2.26 s > 1.5 s coast → event-triggered re-acq
required (the T0 verdict, confirmed on-device). `deploys_within_t0_budget = True`. Verify:
`.venv-ft/bin/python experiments/run_t4.py` (self-check) + `--phase all` (on `ssh jetson`).

**Part III COMPLETE** — T0–T4 all GATE PASS. Cadence budget (T0) → temporal contract
(T1) → permanence mechanism (T2) → closed-loop A/B beating the Phase-C negative (T3) →
on-Orin deployment within budget (T4).

---

### 2026-06-26 — Terse output re-LoRA: cut JSON scaffolding from the anchor's decode

Part II re-train of the deployed grounding anchor (Qwen2-VL-2B) to emit **four
space-separated integers** instead of `{"bbox": [...]}`, to shrink decode latency for the
Part III sub-1s-anchor lever. One variable changed (output format); base/data/resolution/
LoRA/quant held identical to the 62.6% deploy. Writeup:
[`results/2026-06-25-terse-output-retrain/`](results/2026-06-25-terse-output-retrain/README.md).

**Iter-1 (bare ints, 0–1000)** — exported Q8_0, deployed + measured on the Orin:

| metric | JSON (deploy) | **iter-1 terse** | delta |
|---|---|---|---|
| RefDrone IoU@0.25 (Orin Q8_0, n=439) | 62.6% | **61.0%** | −1.6 pp (noise) |
| parse_rate (Orin) | 100% | 99.3% | ~0 |
| **decode tokens (Orin, real)** | ~24 | **21** | **−3 tok only** |
| anchor wall @512 (Orin) | 2265 ms | **2114 ms** | **−6.7%** |

**Negative-ish result:** accuracy held, but the token win mostly evaporated — the model
**reverted to its bracketed prior** (`[266, 476, 346, 644]`) instead of bare ints, shedding only
the `{"bbox": …}` wrapper. Root cause of *why* terse is hard: Qwen tokenizes digits 1-per-token,
so the dominant cost is digit count, not the JSON syntax.

**Iter-2b (bare ints, 0–100, + EOS-supervision fix) — WIN, replaces the deploy artifact.**
Two levers stacked + a bug fix: 0–100 precision (halve the digits), and supervise `<|im_end|>` on
the target (iter-2 without it collapsed to 5% parse — bare outputs never learned to stop, rambled
to the token cap). The model then emits clean bare `28 44 36 59`, 100% parse.

| metric | JSON deploy | **terse iter-2b** | delta |
|---|---|---|---|
| RefDrone IoU@0.25 (Orin Q8_0, n=439) | 62.6% | **63.1%** | **+0.5 pp** |
| parse_rate (Orin) | 100% | 100% | — |
| decode tokens (Orin, real imgs @512) | 21 | **12** | **−43%** |
| decode ms (Orin) | 967 | **531** | **−45%** |
| anchor wall @512 (Orin) | 1807 | **1372** | **−24%** |

**KEEP — strict upgrade**: better accuracy *and* ~half the decode. Stacks with the ROI-crop
prefill lever (2026-06-26T02:30) toward the sub-1s anchor. Full arc (iter-1 −7% → iter-2 collapse
→ iter-2b) in the writeup.

---

### 2026-06-26 — ROI-crop anchor: cut prefill AND beat the resolution ceiling (GATE PASS)

Part III latency lever #2 (sibling of terse output; attacks **prefill**, the other half of the
2.27s anchor). Feed the deployed Qwen2-VL-2B anchor a crop around the tracker's box (simulated
by inflating the RefDrone GT box by margin M) instead of the full frame. Inference-time only —
**no retraining**. Writeup:
[`results/2026-06-25-roi-crop-anchor/`](results/2026-06-25-roi-crop-anchor/README.md).

| config (M=2.0) | prefill ms (Orin Q8_0, 15W) | decode ms | IoU@0.25 (HF n=439) | vs full-frame |
|---|---|---|---|---|
| full-frame @1024 (deploy baseline) | 3691 | 966 | 62.6%¹ | — |
| **ROI crop @512** ⟵ **deploy** | **1374** | 964 | **85.2%** | **2.7× prefill · +22.6 pp** |
| ROI crop @384 (max-speed) | 885 | 964 | 82.5% | 4.2× prefill · +19.9 pp |
| full-frame **downscaled to 512** | — | — | **15.9%** | the resolution ceiling, laid bare |

¹deployed Q8_0@1024 on Jetson; HF full-frame-native control here = 64.0% (agrees). **Drift
(RQ4):** flat 82–85% up to 0.5·box prior drift; 74.3% (M=2.0) / 79.7% (M=3.0) even at a full-box
drift — all above baseline. **GATE PASS** — a tight upscaled crop is *both* faster *and* more
accurate (super-resolution beats Part II constraint #2). Open follow-up: on-device Q8_0 ROI
accuracy confirm. Decode unchanged (~964 ms) — orthogonal to the terse decode lever; the two
stack toward the sub-1s anchor.

---

### 2026-06-26 — ROI re-anchor demo tab + live on-device prefill confirm

Wired the ROI lever into the deploy GUI as a fourth tab ("Re-anchor speedup": full-frame anchor
vs ROI re-anchor side by side, live on the Orin). Doubles as a qualitative on-device check of
the latency lever on the **deployed terse Q8_0** model. Writeup:
[`results/2026-06-26-roi-demo-tab/`](results/2026-06-26-roi-demo-tab/README.md).

| upload | full-frame prefill | ROI re-anchor prefill | speedup |
|---|---|---|---|
| "the white car" | 4034 ms | 1388 ms | 2.91× |
| "the red car" | 3042 ms | 1375 ms | 2.21× |
| "the bus" | 3696 ms | 1373 ms | 2.69× |

ROI prefill pinned at **~1375 ms** (fixed 512×512 → matches the offline 1374 ms); full-frame
scales with upload size. Boxes preserved/tightened → the lever transfers to the deployed model.
Confirms the *latency* lever on-device; quantified on-device IoU@0.25 (RefDrone via GGUF) still
the open follow-up.

---

### 2026-06-27 — ROI re-anchor shrink-and-drift death spiral (negative result + fix)

Forcing a fast re-anchor cadence on the "Live tracking" tab collapsed the lock: the re-anchor
crops `4·box` and feeds it native, so a shrinking box → smaller crop → fewer pixels/context →
smaller box — unbounded positive feedback with no full-frame fallback (box 21px → crop 86px →
64 tokens → degenerate `0×21px` box on the wrong car). Fix: floor the crop side (`roi_window`
gains `min_side`; deploy `ROI_MIN_CROP = 384` px) so the crop pins constant below the threshold
and the loop can't run away. Eval sweep unchanged (`min_side=0` default); self-checks + pytest
green. Writeup: [`results/2026-06-27-roi-shrink-spiral/`](results/2026-06-27-roi-shrink-spiral/README.md).
Open: on-Orin replay re-confirm.
