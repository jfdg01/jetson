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
