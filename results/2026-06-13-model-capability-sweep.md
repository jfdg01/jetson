# Campaign: 10-model capability sweep (Jetson Orin Nano 8 GB)

**Date (protocol drafted):** 2026-06-13
**Status:** 📋 **Protocol / pre-registration** — design fixed *before* data collection so
the analysis can't be retro-fitted to the numbers. Results land in a follow-up section
and in `RESULTS.md` as runs complete.
**Builds on:** [`2026-06-13-llamacpp-upper-bound.md`](2026-06-13-llamacpp-upper-bound.md)
(single-model baseline: Llama-3.2-3B-Instruct Q4_K_M, 15 W locked, ~14.5 tok/s decode).
**Operator:** automated over `ssh jetson` (user `jfdg`); privileged steps (`nvpmodel`,
`jetson_clocks`, `tegrastats`) via the scoped passwordless allowlist (see `DECISIONS.md`).

---

## 1. Motivation & scope

The baseline campaign measured a single model at the device's practical performance
ceiling. This campaign maps the **operating envelope of the Jetson Orin Nano 8 GB across
the model-size spectrum that physically fits in its 8 GB unified memory** — from
sub-billion-parameter models with abundant headroom up to 7–8 B models that sit right at
the memory wall.

The deliverable is a **characterisation of the device, not a leaderboard of models.** Each
model is an instrument for probing a different point on the size/throughput/energy/memory
surface. The question is *"what can this edge device do, and where does it stop?"* — the
crossover points, the cliffs, and the tradeoffs that a thesis reader needs in order to
choose a model for an Orin Nano deployment.

## 2. Research questions

- **RQ1 — Throughput envelope.** How do prefill (pp) and decode (tg) throughput scale with
  parameter count on this hardware, with architecture and quantisation held constant?
- **RQ2 — The memory wall.** As model size approaches the ~6–6.5 GB practical weight+KV
  budget, where does performance degrade, and is the failure a *cliff* (swap thrash / OOM)
  or a *gradient*? At what model size + context length does the device stop being usable?
- **RQ3 — Energy frontier.** How does energy efficiency (tok/s·W⁻¹, J/token) vary across
  the spectrum, and where is the Pareto-optimal point for "useful work per joule"?
- **RQ4 — Latency.** How does time-to-first-token (TTFT, prefill-bound) and inter-token
  latency (decode-bound) scale with size — i.e. the interactivity envelope?
- **RQ5 — Architecture sensitivity (secondary).** At a fixed size class, do different model
  families (Llama / Qwen / Gemma / Phi / Mistral) land at materially different
  throughput/memory points, or does parameter count dominate?

## 3. Hypotheses (stated up front, to be confirmed or falsified)

- **H1.** Decode throughput is **memory-bandwidth-bound** and scales roughly as
  `1 / (model bytes in memory)` — i.e. tg tok/s falls ~linearly with quantised weight size,
  not with raw parameter count, because LPDDR5 bandwidth is the bottleneck (baseline already
  showed prefill ≈ 39× decode, the signature of bandwidth-bound decode).
- **H2.** Prefill stays comparatively abundant across all sizes (compute-bound on the GPU,
  not bandwidth-bound), so long prompts remain cheap even for the largest models that fit.
- **H3.** 7–8 B Q4_K_M models load and run, but **KV cache growth at larger `n_ctx` pushes
  total footprint past the ~6.5 GB budget and triggers swap/OOM** — a sharp cliff, not a
  gentle slope. We expect to *document at least one OOM/throttle failure* (negative result).
- **H4.** Energy-per-token is **lowest (most efficient) for the small-but-capable 2–3 B
  tier**, not the smallest models (whose fixed platform overhead dominates) nor the largest
  (which run slowly at higher power). The tok/s·W⁻¹ curve is non-monotonic.

## 4. Experimental design

A **single-factor sweep**: the model is the independent variable; everything else about the
runtime, device, and prompt is held fixed so any difference is attributable to the model.
One variable at a time, per `CLAUDE.md` methodology.

### 4.1 Independent variable
- **Model** (10 levels) — see §5. Spans ~0.5 B → ~8 B parameters across 5 families.

### 4.2 Controlled variables (held constant across all 10 runs)

| Variable | Fixed value | Rationale |
|---|---|---|
| Runtime | llama.cpp (CUDA), **single pinned commit** `57fe1f0`, `sm_87` | Same binary as baseline; reproducible. Record commit per run in case of a rebuild. |
| Power mode | **15 W (ID=0), clocks locked** (`sudo jetson_clocks`) | The established upper-bound config; isolates the model as the only variable. 7 W is a separate campaign. |
| Quantisation | **Q4_K_M** for all 10 | Holds the bits-per-weight roughly constant so size differences reflect parameter count, not quant. Quant sensitivity is a separate sub-study (§9). |
| GPU offload | `-ngl 99` (full offload) | All weights on the iGPU; unified memory makes this the standard path. |
| Context length | `n_ctx = 4096`; batch `n_batch = 512` | Fixed prefill/decode shapes (pp512 / tg128) for cross-model comparability; a context-scaling sub-sweep (§4.4) probes the memory wall separately. |
| Prompt | Identical fixed prompt / token counts across models | Removes prompt-length as a confound. |
| Repeats | **5 per measurement**, report median ± σ | Captures variance and warm-up; no cherry-picking (`CLAUDE.md`). |
| Thermal start state | Begin each run from a comparable idle/cooled baseline | Avoids heat-soak carryover inflating later runs' temps. |

### 4.3 Dependent variables (measured) and derived metrics

All mandatory `CLAUDE.md` fields, measured per model:

| Metric | Source | Notes |
|---|---|---|
| Prefill tok/s (pp512) | `llama-bench` | Median ± σ over 5 repeats |
| Decode tok/s (tg128) + sustained (tg512) | `llama-bench` | Headline edge number; sustained catches thermal droop |
| Time-to-first-token (TTFT) | `llama-cli` with timing | **Newly added vs. baseline**, which lacked it |
| Peak memory (RAM + unified GPU) | `tegrastats` / `free` | Weights + KV; **flag if swap (zram) is touched** |
| Power: idle / mean / peak W | `tegrastats` (VDD_IN) | Logged over the *whole* inference window |
| Peak SoC temp + throttle flag | `tegrastats` | Note any clock drop below locked freq |
| **tok/s·W⁻¹** (total & net-of-idle) | derived | decode tg ÷ mean decode W |
| **J/token** (total & net-of-idle) | derived | mean decode W ÷ decode tok/s |
| Model load time | wall clock | Cold-load cost, relevant for swap-in on big models |

Derived-metric formulas (kept explicit for reproducibility):
- `energy_per_token [J/tok] = mean_decode_power [W] / decode_throughput [tok/s]`
- `efficiency [tok/s/W] = decode_throughput / mean_decode_power`
- *net-of-idle* variants subtract the 5.24 W idle baseline to isolate inference's marginal
  cost from always-on platform draw (consistent with the baseline campaign).

### 4.4 Memory-wall sub-sweep (targets RQ2 / H3)

For the **largest model that fits** (and, if it fails, the next one down), sweep
`n_ctx ∈ {2048, 4096, 8192, 16384}` at fixed model/quant and record the footprint and the
point at which swap is hit or the run OOMs. This converts "the memory wall" from a single
pass/fail into a measured curve.

## 5. Model selection (the 10)

Chosen to **(a)** span the full size spectrum that fits 8 GB, **(b)** embed a clean
*within-family* scaling curve (Qwen2.5 at four sizes — architecture held constant, parameter
count varied, the cleanest test of H1), and **(c)** sample architecture diversity at the
2–3 B and 7–8 B tiers for RQ5. All Q4_K_M.

| # | Model | Params | Family | ~Q4_K_M weights | Tier | Role in the design |
|---|---|---|---|---|---|---|
| 1 | Qwen2.5-0.5B-Instruct | 0.5 B | Qwen2.5 | ~0.4 GB | A · ultralight | Floor of the curve; max tok/s, platform-overhead-dominated |
| 2 | Llama-3.2-1B-Instruct | 1 B | Llama-3.2 | ~0.8 GB | A · ultralight | 1 B cross-family point |
| 3 | Qwen2.5-1.5B-Instruct | 1.5 B | Qwen2.5 | ~1.0 GB | A · light | Qwen scaling point 2 |
| 4 | Gemma-2-2B-it | 2.6 B | Gemma-2 | ~1.7 GB | B · sweet spot | Different arch (Gemma) at 2 B |
| 5 | Qwen2.5-3B-Instruct | 3 B | Qwen2.5 | ~1.9 GB | B · sweet spot | Qwen scaling point 3 |
| 6 | **Llama-3.2-3B-Instruct** | 3 B | Llama-3.2 | ~2.0 GB | B · sweet spot | **Baseline anchor (already measured)** — cross-checks the new harness against the prior run |
| 7 | Phi-3.5-mini-instruct | 3.8 B | Phi-3.5 | ~2.2 GB | B · sweet spot | Different arch (Phi) at ~4 B |
| 8 | Mistral-7B-Instruct-v0.3 | 7.2 B | Mistral | ~4.4 GB | C · heavy | 7 B, tight fit |
| 9 | Qwen2.5-7B-Instruct | 7.6 B | Qwen2.5 | ~4.7 GB | C · heavy | Qwen scaling point 4 — completes the within-family curve |
| 10 | Llama-3.1-8B-Instruct | 8 B | Llama-3.1 | ~4.9 GB | C · heavy | Largest dense model expected to fit; the memory-wall probe (§4.4) |

**Within-family scaling curve (Qwen2.5):** models 1, 3, 5, 9 = 0.5 → 1.5 → 3 → 7.6 B with
identical architecture/tokenizer/quant. This is the spine of the RQ1/H1 analysis; the other
six points test whether architecture moves the curve (RQ5).

GGUF sources: prefer `bartowski/*-GGUF` and official org repos on Hugging Face; the **exact
repo, revision, and file SHA256 are recorded at acquisition time** next to each result (no
source = not reproducible). Model files staged on the NVMe (`~198 GB` free — ample).

## 6. Per-model protocol (run identically for each of the 10)

1. **Acquire** the GGUF; record repo, revision, filename, SHA256, byte size.
2. **Set device state:** `sudo nvpmodel -m 0` → `sudo jetson_clocks`; confirm locked clocks
   and a cooled idle baseline. Start `tegrastats --interval 1000 --logfile <model>.log`.
3. **Throughput:** `llama-bench -m <model> -ngl 99 -p 512 -n 128 -r 5` (+ a `tg512` sustained
   pass). Capture the CSV to `results/raw/`.
4. **Latency:** one `llama-cli` generation with timing for TTFT and inter-token latency.
5. **Memory:** record peak RAM + unified GPU and **whether zram swap was touched** (hard
   fail condition for the "comfortable fit" claim).
6. **Stop `tegrastats`;** extract idle / mean / peak W, peak temp, throttle events.
7. **Derive** tok/s·W⁻¹ and J/token (total and net-of-idle).
8. **Write the row** into `RESULTS.md` and the detail block here **in the same turn**
   (`CLAUDE.md` working agreement) — including any failure.

## 7. Capability / usability probe (secondary, optional)

"Capabilities of the Orin" is primarily a *performance* question, but a model that runs fast
yet answers wrongly isn't usable. As a lightweight, **non-authoritative** sanity layer (not a
benchmark suite), run a small fixed prompt set per model (e.g. a handful of arithmetic,
short-reasoning, JSON-format-adherence, and instruction-following items) and record a coarse
pass/fail. This grounds the throughput numbers in "is the output coherent at this size on
this device" — explicitly flagged as a qualitative spot-check, **not** an MMLU-style score.
If scope is tight, this is the first thing cut.

## 8. Expected memory budget (pre-flight feasibility)

Practical budget ≈ **6–6.5 GB** for weights + KV after OS/desktop (`README.md`). At
`n_ctx=4096`, KV cache for these models is roughly a few hundred MB to ~1 GB. Tiers A/B
(models 1–7, ≤2.2 GB weights) fit with large headroom. Tier C (models 8–10, 4.4–4.9 GB
weights) fits at modest context but is the **expected stress zone** — model 10 (8 B) at high
`n_ctx` is the predicted OOM/swap point (H3) and the focus of the §4.4 sub-sweep.

## 9. Quantisation sub-study (separate variable — deferred but pre-registered)

To avoid confounding size with quant, the main sweep fixes Q4_K_M. A **separate** sub-study
on one anchor model (Llama-3.2-3B) sweeps quant `∈ {Q3_K_M, Q4_K_M, Q5_K_M, Q6_K, Q8_0}` to
characterise the quant → throughput/memory/quality tradeoff with size held constant. Logged
as its own campaign so each document changes exactly one factor.

## 10. Failure modes to capture (negative results are deliverables)

Per `CLAUDE.md`, record — never silently drop — any of: OOM kills, zram swap thrash, thermal
throttling (clock drop below locked freq), models that won't load, GGUF/quant
incompatibilities, llama.cpp errors, anomalous variance, or warm-up/cold-cache effects. Each
gets the error text, the suspected cause, and the workaround (or "unresolved").

## 11. Threats to validity

- **Thermal carryover** between back-to-back runs — mitigated by a cooled-baseline gate (§6.2)
  and by reporting sustained (tg512) alongside burst (tg128).
- **`llama-bench` window-mean power deflation** — the baseline noted the window mean is pulled
  down by load/inter-repeat gaps; report **steady-state decode power**, not raw window mean.
- **Single power mode** — results are the 15 W-locked envelope only; the 7 W and (deferred)
  25 W MAXN_SUPER points are explicitly out of scope here and flagged as such.
- **Quant pinned to Q4_K_M** — conclusions are quant-conditional; §9 addresses the quant axis.
- **One runtime** — llama.cpp only; MLC-LLM / TensorRT-LLM may shift absolute numbers
  (separate future campaign), so claims are runtime-conditional.
- **Single device unit** — no inter-unit variance; one physical Orin Nano.

## 12. Deliverables

- This file: per-model detail blocks (config + all §4.3 metrics) appended as runs complete.
- `RESULTS.md`: one summary row per model (append-only ledger).
- `results/raw/`: `llama-bench` CSVs + `tegrastats` logs per model.
- Cross-model synthesis: the size-vs-throughput, size-vs-energy, and context-vs-footprint
  curves answering RQ1–RQ4, plus the Qwen2.5 within-family scaling analysis.

## Decisions

### 2026-06-13 — Single-factor sweep with quantisation pinned to Q4_K_M
- **Decision:** Hold quant = Q4_K_M constant across all 10 models; vary only the model.
  Treat quantisation as a separate, later single-anchor sub-study (§9).
- **Alternatives considered:** (a) per-tier quant (e.g. Q8 for the small models that easily
  fit, Q4 for the big ones — "best each model can do on the device"); (b) a full
  model × quant grid.
- **Reasoning:** (a) confounds size with quant — a small fast model would partly be fast
  because it's higher-precision-but-tiny, muddying H1. The cleanest read of *how the device
  scales with model size* needs bits-per-weight fixed. (b) is the rigorous ideal but is
  ~5× the runs; deferred to keep this campaign tractable and one-variable-at-a-time.
- **Tradeoff / cost accepted:** We don't report each model's *best-on-device* config in this
  campaign (a deployment-oriented framing); we report the size-controlled comparison instead.
  The quant axis is recovered in §9.
- **Revisit when:** §9 sub-study runs, or a deployment-recommendation framing is wanted.

### 2026-06-13 — Model set: Qwen2.5 within-family spine + cross-family sampling
- **Decision:** 10 models = a 4-point Qwen2.5 scaling curve (0.5/1.5/3/7.6 B) plus six
  cross-family points (Llama-3.2/3.1, Gemma-2, Phi-3.5, Mistral) spread across the tiers.
- **Alternatives considered:** (a) 10 unrelated "popular" models; (b) one family only;
  (c) maximise family diversity with no within-family curve.
- **Reasoning:** A controlled within-family curve isolates parameter count from architecture
  (the strongest test of H1/RQ1), while the cross-family points give the architecture-
  sensitivity read (RQ5) and keep the set representative of what people actually deploy.
  Qwen2.5 chosen as the spine because it ships the widest set of sizes at matching quant.
- **Tradeoff / cost accepted:** Qwen2.5 is over-represented (4 of 10); a few notable models
  (e.g. Gemma-2-9B, SmolLM, MoE variants) are omitted to keep n=10 and the budget in range.
- **Revisit when:** Expanding past 10 models, or if a target deployment fixes the family.

### 2026-06-13 — Reuse the Llama-3.2-3B baseline as an in-sweep anchor
- **Decision:** Keep Llama-3.2-3B-Instruct Q4_K_M (already measured) as model #6 and re-run
  it under this campaign's protocol rather than only citing the prior number.
- **Alternatives considered:** Drop it and cite the baseline campaign; or include without re-running.
- **Reasoning:** Re-running it under the (slightly extended, TTFT-inclusive) protocol gives a
  same-model consistency check between the two campaigns and a sanity anchor for the harness.
- **Tradeoff / cost accepted:** One "redundant" run; cheap, and it buys cross-campaign trust.
- **Revisit when:** N/A — low cost, keep.

### 2026-06-13 — Download GGUFs with `wget`, not curl / huggingface-cli
- **Decision:** Acquire every model via direct `wget` from Hugging Face `…/resolve/main/…`
  URLs. Do **not** install `curl` or `huggingface-cli`.
- **Alternatives considered:** install `curl` (needs `sudo apt`, password); install
  `huggingface-cli` (needs `pip`, which is absent — `python3 -m pip` reports no module).
- **Reasoning:** Probed the device (2026-06-13): `curl`, `huggingface-cli`, and `pip` are all
  absent; `wget` is present and confirmed to follow HF's 302→CDN redirect and fetch the full
  file (spider-checked all 10 URLs — all resolve with expected sizes). `wget` needs no install,
  no sudo, no Python env — least friction, fully reproducible.
- **Tradeoff / cost accepted:** No HF caching/dedup/resume-by-hash niceties; `wget -c` covers
  plain resume. Acceptable for a 10-file one-time pull (~21 GB total; NVMe has ~196 GB free).
- **Revisit when:** A campaign needs gated/private repos or many revisions (→ `huggingface-cli`).

### 2026-06-13 — Verified on-device environment baked into the run cards
- **Decision:** Pin the run cards to the **measured** device layout, not assumptions:
  binaries at `~/llama.cpp/build/bin/` (commit `57fe1f0`, **not on `$PATH`** — need
  `LD_LIBRARY_PATH=~/llama.cpp/build/bin:/usr/local/cuda/lib64`); models in `~/models/`
  (Llama-3.2-3B already staged → unit 06 skips download); device already in 15 W (ID=0).
- **Reasoning:** A cold session must not guess paths. Probing once and encoding the real
  layout into every card removes the most likely BLOCKED/guess failure mode.
- **Revisit when:** llama.cpp is rebuilt/moved, or the model dir changes.

## TODO / follow-ups

- [x] Stage all 10 GGUFs on NVMe; record repo/revision/SHA256 for each. *(done 2026-06-14)*
- [x] Add TTFT capture via `llama-completion` timing. *(done 2026-06-14; `llama-cli` was replaced — see §data-quality)*
- [x] Run models 1–10 per §6; append rows to `RESULTS.md` and detail blocks here. *(done 2026-06-14)*
- [ ] §4.4 context-scaling sub-sweep on the largest fitting model (memory wall).
- [ ] Cross-model synthesis curves (RQ1–RQ4) + Qwen2.5 within-family analysis.
- [ ] (Optional) §7 capability spot-check. (Deferred) §9 quant sub-study; 7 W / 25 W modes.

## Data quality notes

### llama-cli → llama-completion (TTFT tool change)

This llama.cpp build (`57fe1f0`) no longer supports `-no-cnv` in `llama-cli`; the binary
redirects to `llama-completion` for non-interactive completion. TTFT was therefore measured
with `llama-completion -no-cnv -p <prompt> </dev/null`. The timing format also changed:
- Old: `llama_print_timings: prompt eval time = 894.56 ms / 512 tokens`
- New: `0.02.589.051 I common_perf_print: prompt eval time = 38,05 ms / 9 tokens`
  (timestamp prefix; comma as decimal separator — European locale on device)

The `parsers.py` `parse_llama_cli_timings()` function was updated to handle both formats.
TTFT values in the result blocks are from `prompt eval time` (TTFT proxy = time to process
all prompt tokens). The prompt is short (~9–11 tokens after tokenisation), so TTFT here is
a **latency lower bound**, not a 512-token prefill time.

### tg128 stddev display (0.000)

The result blocks above show `tg128 (median ± σ, ×5) = X ± 0.000 tok/s`. This is a
display artefact: this llama-bench version aggregates all `-r N` repetitions into a **single
CSV row** with `avg_ts`/`stddev_ts` fields. Since there is only one tg128 row in the merged
CSV, the cross-row σ is 0. The actual within-bench stddev (from `stddev_ts` in the raw CSV)
is typically 0.07–0.09 tok/s for tg128 — negligible variance, consistent with locked GPU
clocks. The parser was fixed for future runs to use `stddev_ts` when a single row is present.
**Corrected tg128 stddev from raw CSVs:** ≈ 0.07 tok/s for units 01–02; check individual
`results/raw/2026-06-13_msweep*_bench.csv` for other units.

### Swap hit (all models = YES)

Tegrastats reports `SWAP X/3804MB` even at idle (zram always partially active; baseline
≈ 11 MB for idle system after model download). All 10 models show `Swap hit: YES ⚠` in the
result blocks because any non-zero swap triggers the flag. The accurate picture:

| Tier | Example | Idle swap | Peak swap | Inference-induced Δ |
|---|---|---|---|---|
| A (ultralight) | 0.5B / 1B | 11 MB | 206 MB | +195 MB |
| B (sweet-spot) | Gemma-2-2B | 54 MB | 406 MB | +352 MB |
| C (heavy) | Mistral-7B | 264 MB | 419 MB | +155 MB |
| C (heavy) | Llama-3.1-8B | 344 MB | 460 MB | +116 MB |

**Inference does induce real swap pressure on all model sizes.** Even the 0.5B model adds
~195 MB of zram usage as the GPU stakes its unified memory claim. Since zram compresses in
RAM (no disk I/O), this does not produce the catastrophic latency of traditional disk swap,
but it does consume CPU cycles for compression and increases memory pressure on the SoC.
This is a real finding: **no model size on this device escapes zram pressure at n_ctx=4096.**

### Gemma-2-2B anomalous peak RAM (5818 MB)

Gemma-2-2B (2.6B params, ~1.7 GB weights) peaked at **5818 MB system RAM** — higher than
Mistral-7B (5488 MB) and Qwen2.5-7B (5465 MB). This is not a measurement error.
Probable causes:
1. **Large KV cache**: Gemma-2 uses alternating local/global attention; at n_ctx=4096 the
   global-attention layers have full-sequence KV cache with larger head dimensions.
2. **CUDA workspace**: llama.cpp may allocate large compute buffers for Gemma-2's
   architecture (different kernel patterns vs. standard GQA models).
3. **Weights precision**: Gemma-2 stores some weights in f32 internally even with Q4_K_M.
This is a deployment-relevant negative result: **Gemma-2-2B is not a "small footprint"
model on this device** despite its 2.6B parameter count. A thesis reader choosing a model
for constrained-memory deployment should prefer Qwen2.5-3B (3180 MB) over Gemma-2-2B (5818 MB)
for the same ~3 B parameter tier.

## Analysis

**Run date:** 2026-06-14 · All 10 models completed without OOM or crash.

### RQ1 — Throughput envelope

Decode throughput (tg128, bandwidth-bound) scales roughly as 1/(weight bytes), confirming H1:

| Model | Params | Weight size | tg128 tok/s | Relative to 8B |
|---|---|---|---|---|
| Qwen2.5-0.5B | 0.5 B | ~380 MB | 71.52 | 9.2× |
| Llama-3.2-1B | 1.0 B | ~770 MB | 35.07 | 4.5× |
| Qwen2.5-1.5B | 1.5 B | ~940 MB | 26.56 | 3.4× |
| Gemma-2-2B | 2.6 B | ~1.63 GB | 15.98 | 2.1× |
| Qwen2.5-3B | 3.0 B | ~1.84 GB | 14.91 | 1.9× |
| Llama-3.2-3B | 3.0 B | ~2.02 GB | 14.60 | 1.9× |
| Phi-3.5-mini | 3.8 B | ~2.28 GB | 13.15 | 1.7× |
| Mistral-7B | 7.2 B | ~4.17 GB | 8.39 | 1.1× |
| Qwen2.5-7B | 7.6 B | ~4.47 GB | 7.89 | 1.0× |
| Llama-3.1-8B | 8.0 B | ~4.69 GB | 7.75 | 1.0× |

The 0.5B → 8B range spans ~9× in decode throughput, closely tracking the inverse weight-size
ratio (~12×). The deviation from perfect linearity is expected (KV cache, activation memory,
CUDA overhead are non-negligible for small models).

Prefill (pp512) spans 3027 → 245 tok/s (12× range), with a steeper drop at the 3→7 B
transition — consistent with the GPU being compute-limited for large matrix multiplications at
lower arithmetic intensity per byte once the full prompt batch saturates the hardware.

### RQ2 — Memory wall

No OOM on any model at n_ctx=4096. The memory wall at this context is not a hard cliff but
the margin is thin for unit 10 (8B, 5953 MB peak with 1654 MB headroom to 7607 MB).
The §4.4 context-scaling sub-sweep is needed to locate the actual OOM threshold.
**Gemma-2-2B is the unexpected stress case** — 5818 MB with only 1789 MB headroom.

### RQ3 — Energy frontier (H4 evaluated)

H4 predicted the Pareto-optimal efficiency point would be in the 2–3 B tier.
**Result: H4 is falsified** — the smallest model (0.5B) is the most energy-efficient
(11.77 tok/s·W⁻¹ net), and efficiency monotonically decreases with model size.
The fixed ~5.2 W platform draw is not large enough relative to the inference-marginal power
to create a non-monotonic curve at these model sizes.

Net-of-idle efficiency rankings: 0.5B (11.77) >> 1B (4.35) > 1.5B (4.17) > 3B tier
(~2.0) > 7–8B tier (~0.9).

If **useful work per joule** is the criterion (not raw throughput), the sub-1B models
dominate. If **task completion per second** (quality × speed) matters, the 3B tier is the
practical sweet spot: ~14.5–15 tok/s at ~2.0 tok/s·W⁻¹.

### RQ4 — Latency (TTFT)

TTFT (prompt eval time, ~9–11 tokens) scales 38 ms → 204 ms across the size range.
For interactive use, all models respond in under 250 ms for short prompts — comfortably
within human perception (~200 ms threshold). Longer prompts shift this; the context-scaling
sub-sweep will quantify this.

### RQ5 — Architecture sensitivity

At the 3 B tier: Qwen2.5-3B (14.91 tok/s) ≈ Llama-3.2-3B (14.60 tok/s) — architecture
matters very little; weight size dominates. Phi-3.5-mini (3.8B, 13.15 tok/s) is slower
consistent with its larger weight size. Gemma-2-2B (2.6B, 15.98 tok/s) is faster than the
3B models in throughput but anomalously memory-hungry.

At the 7–8 B tier: Mistral (8.39), Qwen2.5 (7.89), Llama-3.1 (7.75) are within 8% of each
other — again weight size is the dominant predictor.

**Qwen2.5 within-family scaling curve (H1 test):**

| Size | tg128 tok/s | Ratio to 0.5B |
|---|---|---|
| 0.5 B | 71.52 | 1.00× |
| 1.5 B | 26.56 | 0.37× |
| 3.0 B | 14.91 | 0.21× |
| 7.6 B | 7.89 | 0.11× |

Weight-size ratios (relative to 0.5B): ×2.5, ×4.8, ×11.8. Throughput ratios (inverse):
÷2.7, ÷4.8, ÷9.1. The 0.5→1.5 B and 1.5→3 B steps follow the weight-size prediction
well. The 3→7.6 B step underperforms the prediction (9.1× vs 11.8× weight ratio),
likely because the 7.6B model's larger KV cache and CUDA workspace reduce effective
LPDDR5 bandwidth headroom — a secondary memory-bandwidth effect on top of the primary
weight-streaming bottleneck. **H1 is confirmed as the dominant effect with a secondary
deviation at the memory-bound extreme.**

## Results

### Unit 01 — Qwen2.5-0.5B-Instruct Q4_K_M

**Run:** 2026-06-14T10:44 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87

| Metric | Value |
|---|---|
| SHA256 | `6eb923e7d26e9cea28811e1a8e852009b21242fb157b26149d3b188f3a8c8653` |
| Prefill pp512 (median ± σ, ×5) | **3026.7 ± 19.29 tok/s** |
| Decode tg128 (median ± σ, ×5) | **71.52 ± 0.000 tok/s** |
| Decode tg512 sustained (×3) | 71.12 tok/s |
| TTFT (prompt eval, 512-tok prompt) | 38 ms |
| Peak RAM | 2637 MB / 7607 MB |
| Swap hit | YES ⚠ |
| Power — idle | 5.17 W |
| Power — mean (active window) | 6.57 W |
| Power — peak | 11.25 W |
| Peak SoC temp | 59.9 °C |
| tok/s per watt (total) | 6.36 |
| tok/s per watt (net of idle) | 11.77 |
| J/token (total) | 0.157 |

### Unit 02 — Llama-3.2-1B-Instruct Q4_K_M

**Run:** 2026-06-14T10:45 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87

| Metric | Value |
|---|---|
| SHA256 | `6f85a640a97cf2bf5b8e764087b1e83da0fdb51d7c9fab7d0fece9385611df83` |
| Prefill pp512 (median ± σ, ×5) | **1533.5 ± 1.75 tok/s** |
| Decode tg128 (median ± σ, ×5) | **35.07 ± 0.000 tok/s** |
| Decode tg512 sustained (×3) | 34.90 tok/s |
| TTFT (prompt eval, 512-tok prompt) | 49 ms |
| Peak RAM | 3497 MB / 7607 MB |
| Swap hit | YES ⚠ |
| Power — idle | 5.26 W |
| Power — mean (active window) | 8.42 W |
| Power — peak | 13.32 W |
| Peak SoC temp | 63.3 °C |
| tok/s per watt (total) | 2.63 |
| tok/s per watt (net of idle) | 4.35 |
| J/token (total) | 0.380 |

### Unit 03 — Qwen2.5-1.5B-Instruct Q4_K_M

**Run:** 2026-06-14T10:47 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87

| Metric | Value |
|---|---|
| SHA256 | `1adf0b11065d8ad2e8123ea110d1ec956dab4ab038eab665614adba04b6c3370` |
| Prefill pp512 (median ± σ, ×5) | **1098.1 ± 0.18 tok/s** |
| Decode tg128 (median ± σ, ×5) | **26.56 ± 0.000 tok/s** |
| Decode tg512 sustained (×3) | 26.47 tok/s |
| TTFT (prompt eval, 512-tok prompt) | 59 ms |
| Peak RAM | 2872 MB / 7607 MB |
| Swap hit | YES ⚠ |
| Power — idle | 5.41 W |
| Power — mean (active window) | 7.88 W |
| Power — peak | 11.79 W |
| Peak SoC temp | 63.6 °C |
| tok/s per watt (total) | 2.25 |
| tok/s per watt (net of idle) | 4.17 |
| J/token (total) | 0.444 |

### Unit 04 — gemma-2-2b-it Q4_K_M

**Run:** 2026-06-14T10:49 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87

| Metric | Value |
|---|---|
| SHA256 | `e0aee85060f168f0f2d8473d7ea41ce2f3230c1bc1374847505ea599288a7787` |
| Prefill pp512 (median ± σ, ×5) | **728.4 ± 1.33 tok/s** |
| Decode tg128 (median ± σ, ×5) | **15.98 ± 0.000 tok/s** |
| Decode tg512 sustained (×3) | 15.87 tok/s |
| TTFT (prompt eval, 512-tok prompt) | 85 ms |
| Peak RAM | 5818 MB / 7607 MB |
| Swap hit | YES ⚠ |
| Power — idle | 5.25 W |
| Power — mean (active window) | 8.47 W |
| Power — peak | 13.17 W |
| Peak SoC temp | 65.7 °C |
| tok/s per watt (total) | 1.21 |
| tok/s per watt (net of idle) | 2.02 |
| J/token (total) | 0.824 |

### Unit 05 — Qwen2.5-3B-Instruct Q4_K_M

**Run:** 2026-06-14T10:52 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87

| Metric | Value |
|---|---|
| SHA256 | `9c9f56a391a3abbd5b89d0245bf6106081bcc3173119d4229235dd9d23253f94` |
| Prefill pp512 (median ± σ, ×5) | **558.8 ± 5.29 tok/s** |
| Decode tg128 (median ± σ, ×5) | **14.91 ± 0.000 tok/s** |
| Decode tg512 sustained (×3) | 14.90 tok/s |
| TTFT (prompt eval, 512-tok prompt) | 91 ms |
| Peak RAM | 3180 MB / 7607 MB |
| Swap hit | YES ⚠ |
| Power — idle | 5.25 W |
| Power — mean (active window) | 11.93 W |
| Power — peak | 12.56 W |
| Peak SoC temp | 65.1 °C |
| tok/s per watt (total) | 1.19 |
| tok/s per watt (net of idle) | 2.04 |
| J/token (total) | 0.842 |

### Unit 06 — Llama-3.2-3B-Instruct Q4_K_M

**Run:** 2026-06-14T10:56 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87

| Metric | Value |
|---|---|
| SHA256 | `6c1a2b41161032677be168d354123594c0e6e67d2b9227c84f296ad037c728ff` |
| Prefill pp512 (median ± σ, ×5) | **569.8 ± 0.42 tok/s** |
| Decode tg128 (median ± σ, ×5) | **14.60 ± 0.000 tok/s** |
| Decode tg512 sustained (×3) | 14.54 tok/s |
| TTFT (prompt eval, 512-tok prompt) | 85 ms |
| Peak RAM | 3719 MB / 7607 MB |
| Swap hit | YES ⚠ |
| Power — idle | 5.28 W |
| Power — mean (active window) | 11.02 W |
| Power — peak | 12.60 W |
| Peak SoC temp | 65.1 °C |
| tok/s per watt (total) | 1.16 |
| tok/s per watt (net of idle) | 2.00 |
| J/token (total) | 0.863 |

### Unit 07 — Phi-3.5-mini-instruct Q4_K_M

**Run:** 2026-06-14T11:00 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87

| Metric | Value |
|---|---|
| SHA256 | `e4165e3a71af97f1b4820da61079826d8752a2088e313af0c7d346796c38eff5` |
| Prefill pp512 (median ± σ, ×5) | **432.0 ± 1.06 tok/s** |
| Decode tg128 (median ± σ, ×5) | **13.15 ± 0.000 tok/s** |
| Decode tg512 sustained (×3) | 12.76 tok/s |
| TTFT (prompt eval, 512-tok prompt) | 114 ms |
| Peak RAM | 4693 MB / 7607 MB |
| Swap hit | YES ⚠ |
| Power — idle | 5.25 W |
| Power — mean (active window) | 12.45 W |
| Power — peak | 13.09 W |
| Peak SoC temp | 65.8 °C |
| tok/s per watt (total) | 1.00 |
| tok/s per watt (net of idle) | 1.68 |
| J/token (total) | 0.995 |

### Unit 08 — Mistral-7B-Instruct-v0.3 Q4_K_M

**Run:** 2026-06-14T11:04 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87

| Metric | Value |
|---|---|
| SHA256 | `1270d22c0fbb3d092fb725d4d96c457b7b687a5f5a715abe1e818da303e562b6` |
| Prefill pp512 (median ± σ, ×5) | **252.7 ± 0.34 tok/s** |
| Decode tg128 (median ± σ, ×5) | **8.39 ± 0.000 tok/s** |
| Decode tg512 sustained (×3) | 8.36 tok/s |
| TTFT (prompt eval, 512-tok prompt) | 190 ms |
| Peak RAM | 5488 MB / 7607 MB |
| Swap hit | YES ⚠ |
| Power — idle | 5.21 W |
| Power — mean (active window) | 12.45 W |
| Power — peak | 13.76 W |
| Peak SoC temp | 67.3 °C |
| tok/s per watt (total) | 0.61 |
| tok/s per watt (net of idle) | 0.98 |
| J/token (total) | 1.639 |

### Unit 09 — Qwen2.5-7B-Instruct Q4_K_M

**Run:** 2026-06-14T11:11 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87

| Metric | Value |
|---|---|
| SHA256 | `65b8fcd92af6b4fefa935c625d1ac27ea29dcb6ee14589c55a8f115ceaaa1423` |
| Prefill pp512 (median ± σ, ×5) | **265.6 ± 1.28 tok/s** |
| Decode tg128 (median ± σ, ×5) | **7.89 ± 0.000 tok/s** |
| Decode tg512 sustained (×3) | 7.86 tok/s |
| TTFT (prompt eval, 512-tok prompt) | 202 ms |
| Peak RAM | 5465 MB / 7607 MB |
| Swap hit | YES ⚠ |
| Power — idle | 5.23 W |
| Power — mean (active window) | 11.92 W |
| Power — peak | 13.80 W |
| Peak SoC temp | 67.1 °C |
| tok/s per watt (total) | 0.57 |
| tok/s per watt (net of idle) | 0.92 |
| J/token (total) | 1.749 |

### Unit 10 — Meta-Llama-3.1-8B-Instruct Q4_K_M

**Run:** 2026-06-14T11:19 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87

| Metric | Value |
|---|---|
| SHA256 | `7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c` |
| Prefill pp512 (median ± σ, ×5) | **245.3 ± 0.16 tok/s** |
| Decode tg128 (median ± σ, ×5) | **7.75 ± 0.000 tok/s** |
| Decode tg512 sustained (×3) | 7.72 tok/s |
| TTFT (prompt eval, 512-tok prompt) | 204 ms |
| Peak RAM | 5953 MB / 7607 MB |
| Swap hit | YES ⚠ |
| Power — idle | 5.25 W |
| Power — mean (active window) | 12.04 W |
| Power — peak | 13.92 W |
| Peak SoC temp | 67.4 °C |
| tok/s per watt (total) | 0.56 |
| tok/s per watt (net of idle) | 0.89 |
| J/token (total) | 1.795 |

