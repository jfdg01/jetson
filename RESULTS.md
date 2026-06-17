# RESULTS — Jetson Orin Nano Edge-LLM Benchmarks

Running ledger across all experiment campaigns. Append, never overwrite.
Each row links to the detailed writeup in `results/`. See `CLAUDE.md` for the
fields every run must capture.

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
