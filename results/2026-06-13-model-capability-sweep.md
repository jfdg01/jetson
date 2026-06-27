# Campaign: 10-model capability sweep (Jetson Orin Nano 8 GB)

**Date:** 2026-06-13 (protocol) · 2026-06-14 (data) · **Status:** Complete
**Runtime:** llama.cpp `57fe1f0` CUDA sm_87 · **Power:** 15 W locked (`nvpmodel -m 0` + `jetson_clocks`)
**Builds on:** `2026-06-13-llamacpp-upper-bound.md` (Llama-3.2-3B baseline: ~14.5 tok/s decode)

---

## Research questions & hypotheses

- **RQ1** Decode throughput vs. parameter count — H1: bandwidth-bound, scales as `1/(weight bytes)`
- **RQ2** Memory wall — H3: 7–8B Q4_K_M at large `n_ctx` hits swap/OOM (cliff, not gradient)
- **RQ3** Energy efficiency — H4: Pareto-optimal at 2–3B tier (non-monotonic curve)
- **RQ4** TTFT latency vs. model size
- **RQ5** Architecture sensitivity at fixed size class

## Design

Single-factor sweep — model is the only independent variable.

| Controlled variable | Value |
|---|---|
| Quantisation | Q4_K_M (all 10) |
| GPU offload | `-ngl 99` (full) |
| Context | `n_ctx=4096`, `n_batch=512` |
| Repeats | 5 per measurement, median ± σ |
| Prompt | Identical fixed prompt across all models |

**Measured:** pp512 tok/s, tg128 tok/s, tg512 tok/s, TTFT, peak RAM, swap hit, idle/mean/peak W (VDD_IN), peak SoC temp, throttle flag.
**Derived:** `J/tok = mean_decode_W / tok_s` · `tok/s/W = tok_s / mean_decode_W` · net-of-idle subtracts 5.24 W platform baseline.

## Models (all Q4_K_M, `-ngl 99`)

| # | Model | Params | ~Weights | Tier | Role |
|---|---|---|---|---|---|
| 01 | Qwen2.5-0.5B-Instruct | 0.5 B | ~380 MB | A | throughput floor; Qwen spine pt 1 |
| 02 | Llama-3.2-1B-Instruct | 1.0 B | ~770 MB | A | cross-family 1B |
| 03 | Qwen2.5-1.5B-Instruct | 1.5 B | ~940 MB | A | Qwen spine pt 2 |
| 04 | Gemma-2-2B-it | 2.6 B | ~1.63 GB | B | cross-family 2B (Gemma arch) |
| 05 | Qwen2.5-3B-Instruct | 3.0 B | ~1.84 GB | B | Qwen spine pt 3 |
| 06 | Llama-3.2-3B-Instruct | 3.0 B | ~2.02 GB | B | **baseline anchor** (cross-campaign sanity) |
| 07 | Phi-3.5-mini-instruct | 3.8 B | ~2.28 GB | B | cross-family ~4B (Phi arch) |
| 08 | Mistral-7B-Instruct-v0.3 | 7.2 B | ~4.17 GB | C | 7B cross-family |
| 09 | Qwen2.5-7B-Instruct | 7.6 B | ~4.47 GB | C | Qwen spine pt 4 |
| 10 | Llama-3.1-8B-Instruct | 8.0 B | ~4.69 GB | C | memory-wall probe |

GGUF source: `bartowski/*-GGUF` / official org repos on HF. Exact SHA256 per unit below.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Quant fixed | Q4_K_M for all 10 | Isolates size from quant; quant axis is a separate sub-study |
| Model spine | Qwen2.5 at 0.5/1.5/3/7.6B | Clean within-family scaling curve — strongest H1 test |
| Baseline anchor | Re-run Llama-3.2-3B | Cross-campaign consistency check; worth 1 extra run |
| Download tool | `wget` (not curl/huggingface-cli) | Both absent on device; `wget -c` covers resume |
| Binary paths | `~/llama.cpp/build/bin/`, `LD_LIBRARY_PATH=~/llama.cpp/build/bin:/usr/local/cuda/lib64` | Not on `$PATH`; baked in to avoid cold-session failures |

## Data quality notes

**TTFT tool change:** Build `57fe1f0` dropped `-no-cnv` in `llama-cli`; TTFT measured via `llama-completion -no-cnv`. Timing format changed: added timestamp prefix + comma decimal separator (European locale). `parsers.py parse_llama_cli_timings()` updated to handle both. TTFT = `prompt eval time` on ~9–11 token prompt — a latency lower bound, not 512-tok prefill.

**tg128 stddev = 0.000 (display artefact):** llama-bench merges `-r 5` into one CSV row; cross-row σ = 0. Actual `stddev_ts` ≈ 0.07 tok/s (negligible; locked clocks). Parser fixed to use `stddev_ts` when single row present.

**Swap (all models = YES — zram, not disk):** zram is always partially active at idle (~11 MB). All 10 models trigger the flag, but this is RAM-compressed swap (no disk I/O). Inference-induced Δ:

| Tier | Peak swap | Δ vs idle |
|---|---|---|
| A (0.5–1.5B) | ~200 MB | +~190 MB |
| B (Gemma-2-2B) | 406 MB | +352 MB |
| C (Mistral-7B) | 419 MB | +155 MB |
| C (Llama-3.1-8B) | 460 MB | +116 MB |

No model escapes zram pressure at n_ctx=4096. CPU compression cycles are real overhead even without disk swap.

**Gemma-2-2B anomalous RAM (5818 MB):** Higher than Mistral-7B (5488) and Qwen2.5-7B (5465) despite ~1.6 GB weights. Probable cause: alternating local/global attention → large global-attention KV cache at n_ctx=4096 + large CUDA workspace. **Deployment note:** Qwen2.5-3B (3180 MB) is far more memory-efficient than Gemma-2-2B for similar parameter count.

## Results

All 10 runs completed 2026-06-14 without OOM or crash · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87

| Unit | Model | pp512 tok/s | tg128 tok/s | tg512 tok/s | TTFT ms | Peak RAM MB | Mean W | tok/s·W⁻¹ (net) | J/tok |
|---|---|---|---|---|---|---|---|---|---|
| 01 | Qwen2.5-0.5B | 3026.7 ± 19.29 | 71.52 | 71.12 | 38 | 2637 | 6.57 | **11.77** | 0.157 |
| 02 | Llama-3.2-1B | 1533.5 ± 1.75 | 35.07 | 34.90 | 49 | 3497 | 8.42 | 4.35 | 0.380 |
| 03 | Qwen2.5-1.5B | 1098.1 ± 0.18 | 26.56 | 26.47 | 59 | 2872 | 7.88 | 4.17 | 0.444 |
| 04 | Gemma-2-2B ⚠ | 728.4 ± 1.33 | 15.98 | 15.87 | 85 | **5818** | 8.47 | 2.02 | 0.824 |
| 05 | Qwen2.5-3B | 558.8 ± 5.29 | 14.91 | 14.90 | 91 | 3180 | 11.93 | 2.04 | 0.842 |
| 06 | Llama-3.2-3B | 569.8 ± 0.42 | 14.60 | 14.54 | 85 | 3719 | 11.02 | 2.00 | 0.863 |
| 07 | Phi-3.5-mini | 432.0 ± 1.06 | 13.15 | 12.76 | 114 | 4693 | 12.45 | 1.68 | 0.995 |
| 08 | Mistral-7B | 252.7 ± 0.34 | 8.39 | 8.36 | 190 | 5488 | 12.45 | 0.98 | 1.639 |
| 09 | Qwen2.5-7B | 265.6 ± 1.28 | 7.89 | 7.86 | 202 | 5465 | 11.92 | 0.92 | 1.749 |
| 10 | Llama-3.1-8B | 245.3 ± 0.16 | 7.75 | 7.72 | 204 | 5953 | 12.04 | 0.89 | 1.795 |

Peak W / temp: 01: 11.25W/59.9°C · 02: 13.32W/63.3°C · 03: 11.79W/63.6°C · 04: 13.17W/65.7°C · 05: 12.56W/65.1°C · 06: 12.60W/65.1°C · 07: 13.09W/65.8°C · 08: 13.76W/67.3°C · 09: 13.80W/67.1°C · 10: 13.92W/67.4°C

SHA256: 01:`6eb923e7...` 02:`6f85a640...` 03:`1adf0b11...` 04:`e0aee850...` 05:`9c9f56a3...` 06:`6c1a2b41...` 07:`e4165e3a...` 08:`1270d22c...` 09:`65b8fcd9...` 10:`7b064f58...`
*(Full hashes in archive copy)*

## Analysis

### RQ1 — Throughput (H1 confirmed)

Decode is bandwidth-bound; tg128 scales as ~1/(weight bytes). 0.5B → 8B spans 9× in throughput (71.52 → 7.75 tok/s), tracking the ~12× weight-size ratio closely.

Qwen2.5 within-family scaling:

| Size | tg128 tok/s | vs 0.5B |
|---|---|---|
| 0.5B | 71.52 | 1.00× |
| 1.5B | 26.56 | 0.37× |
| 3.0B | 14.91 | 0.21× |
| 7.6B | 7.89 | 0.11× |

0.5→3B steps match weight-size prediction well. 3→7.6B underperforms prediction (9.1× vs 11.8× weight ratio) — KV cache + CUDA workspace reduce effective LPDDR5 bandwidth at the heavy end. **H1 confirmed as dominant; secondary deviation at memory-bound extreme.**

### RQ2 — Memory wall

No OOM at n_ctx=4096. Thinnest margin: Llama-3.1-8B at 5953 MB (1654 MB headroom). Gemma-2-2B is the surprise at 5818 MB. Context-scaling sub-sweep still needed to locate actual OOM threshold.

### RQ3 — Energy efficiency (H4 falsified)

H4 predicted a non-monotonic efficiency curve peaking at 2–3B. **Falsified:** efficiency monotonically decreases with size. Platform draw (~5.2W) is not large enough to create the predicted curve.
- Best raw efficiency: 0.5B (11.77 tok/s·W⁻¹ net)
- Best task-completion sweet spot: 3B tier (~14.5 tok/s, ~2.0 tok/s·W⁻¹)

### RQ4 — TTFT

38 ms (0.5B) → 204 ms (8B). All models respond under 250 ms for short prompts — within interactive threshold. Longer prompts: context-scaling sub-sweep pending.

### RQ5 — Architecture sensitivity

Weight size dominates; architecture is secondary. At 3B: Qwen2.5 (14.91) ≈ Llama (14.60) within 2%. At 7–8B: Mistral / Qwen2.5 / Llama within 8% of each other.

## Open items

- [ ] Context-scaling sub-sweep on Llama-3.1-8B: `n_ctx ∈ {2048, 4096, 8192, 16384}` (memory wall)
- [ ] Cross-model synthesis curves (RQ1–RQ4)
- [ ] Quant sub-study: Llama-3.2-3B × {Q3_K_M, Q4_K_M, Q5_K_M, Q6_K, Q8_0}
- [ ] (Deferred) §7 capability spot-check; 7 W / 25 W MAXN_SUPER campaigns
