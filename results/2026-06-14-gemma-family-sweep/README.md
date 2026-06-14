# Campaign: Gemma-family generational + edge-architecture sweep (Jetson Orin Nano 8 GB)

**Date (protocol drafted):** 2026-06-14
**Status:** 📋 **Protocol / pre-registration** — design and predictions fixed *before* data
collection, so the analysis can't be retro-fitted to the numbers (same discipline as the
10-model sweep). Results land in §8 and in root `RESULTS.md` as runs complete.
**Builds on:** [`../2026-06-13-model-capability-sweep.md`](../2026-06-13-model-capability-sweep.md)
— that sweep already ran **`gemma-2-2b-it` Q4_K_M** as unit 04 (728 pp / 15.98 tg tok/s,
peak 5818 MB, 0.824 J/tok). That datapoint is the **anchor** this campaign extends across the
rest of the Gemma family.
**Operator:** automated over `ssh jetson` (user `jfdg`); privileged steps via the scoped
passwordless allowlist (see root `DECISIONS.md`).

> **All web-sourced numbers below (sizes, params, release dates) are vendor/secondary-source
> claims gathered 2026-06-14 — see §10 Sources. They are *predictions to be measured on
> device*, not results. Per `CLAUDE.md`: no unverified claim becomes a thesis number.**

---

## 1. Motivation & scope

The capability sweep characterised the device across **model size** with architecture held
loosely constant. This campaign holds the **family constant (Gemma) and varies generation
and architecture** to ask a different question:

> *Does a newer Gemma generation deliver more useful capability per byte and per joule on the
> Orin Nano — and where does the Gemma family hit the 8 GB wall?*

Gemma is uniquely suited to this because, as of mid-2026, the family spans:
- **Three live generations** — Gemma 2 (2024), Gemma 3 (2025), Gemma 4 (Apr 2026).
- **Four architectural ideas** in one family — classic **dense**, **QAT** (quantization-aware
  trained int4 checkpoints), **PLE / "effective-parameter"** edge models (E2B/E4B), and a
  **26B-A4B MoE** (too big for us; defines the upper bound we *can't* reach).
- **Modality growth** — text-only (270M) → text+vision (3-4B/12B) → text+vision+**native
  audio** (Gemma 4 E2B/E4B).

This is a **device characterisation**, not a Gemma leaderboard. Each model is an instrument
probing a different point on the generation × architecture × modality surface.

## 2. Research questions

- **RQ-G1 — Generational efficiency.** At a comparable on-device footprint, does Gemma 3/4
  beat Gemma 2 on tok/s·W⁻¹ and J/token, or does newer = heavier with no edge benefit?
- **RQ-G2 — Does QAT pay off on Orin?** Vendor int4 **QAT** GGUFs (`q4_0`) claim near-BF16
  quality at ~Q4 size. Do they cost throughput/memory vs the community `Q4_K_M` we used in the
  sweep, and is the footprint actually smaller?
- **RQ-G3 — The "effective parameter" (PLE) reality check.** Gemma 4 E2B/E4B advertise small
  *effective* params but carry **Per-Layer Embeddings** that inflate real memory. Spec sheets
  disagree by ~2× on Q4 size (§4, §6). **Measure the true on-device weight + KV footprint.**
- **RQ-G4 — Where is the Gemma memory wall?** Gemma 3 **12B** Q4 (~6.6–7 GB weights) is
  deliberately placed at/over the ~6.5 GB practical budget. Cliff or gradient? (extends sweep H3)
- **RQ-G5 — Modality cost (secondary, may defer).** Does enabling vision (mmproj) on the 3-4B/
  E-series change load footprint and TTFT materially vs text-only on the same model?

## 3. Hypotheses (stated up front)

- **HG1.** Decode throughput stays **memory-bandwidth-bound** (sweep H1 held): tg tok/s tracks
  `1 / (bytes resident in memory)` regardless of generation. So a Gemma-4 E4B and a Gemma-2/3
  model of the *same resident size* land at *similar* tg, and any generational win shows up as
  **quality-per-byte**, not raw speed.
- **HG2.** QAT `q4_0` is **marginally slower** than `Q4_K_M` per byte (q4_0 is a simpler block
  format → similar bandwidth, llama.cpp kernels comparable) but within ±10% — i.e. QAT's value
  is quality, not speed, and it costs us little throughput.
- **HG3.** Gemma 4 E2B/E4B **real Q4 footprint exceeds the optimistic "mobile" spec** (1.1/2.5
  GB) and lands nearer Google's VRAM-table Q4 figure (2.9/4.5 GB) once PLE + KV at n_ctx=4096
  are counted. E4B therefore behaves, memory-wise, like a ~7-8B dense model on this device.
- **HG4.** Gemma 3 **270M** is **prefill-saturated and decode-fast but platform-overhead-bound**
  on energy — it will *not* beat the 2-3B tier on tok/s·W⁻¹ (echoing sweep H4: smallest ≠ most
  efficient), because the ~5.2 W idle floor dominates at its tiny compute.
- **HG5.** Gemma 3 **12B** Q4 triggers **swap thrash** at n_ctx=4096 (predicted total > 8 GB) —
  we expect to **document a degraded/failed run** (negative result = thesis content per
  `CLAUDE.md`). If it loads at all, expect tg well below the ~7.7 tok/s of the 8B sweep models.

## 4. The five models — selection & rationale

Anchor already in hand: **`gemma-2-2b-it` Q4_K_M** (sweep unit 04). The five below were chosen
to maximise *spread across generation, architecture, modality, and the memory wall* while every
model still has a real chance of running on 8 GB (except 12B, which is the deliberate stress).

| # | Model (instruct) | Gen | Arch idea | Modality | Total / active params | Claimed Q4 size | Why it's interesting (the probe) |
|---|---|---|---|---|---|---|---|
| G1 | **gemma-3-270m-it** | 3 | tiny dense | text | 0.27 B | ~0.3 GB | **Throughput ceiling / overhead floor.** Smallest real Gemma; tests the fixed-cost (idle-W, load-time) regime and whether tg saturates a bandwidth or a launch-overhead limit. |
| G2 | **gemma-3-4b-it (QAT q4_0)** | 3 | QAT dense | text+vision | 4 B | ~2.6–3 GB | **Generational + QAT + vision anchor.** Direct heir to the Gemma-2-2B anchor; first vision-capable unit; tests RQ-G1/RQ-G2 head-on at a size we *know* fits. |
| G3 | **gemma-4-E2B-it (QAT)** | 4 | PLE "effective-2B" | text+vision+audio | 5.1 B total / 2.3 B active | 1.3–2.9 GB ⚠️ | **Newest edge arch, smallest.** PLE footprint reality check (RQ-G3); the spec-sheet size disagreement is the experiment. |
| G4 | **gemma-4-E4B-it (QAT)** | 4 | PLE "effective-4B" | text+vision+audio | 8 B total / ~4 B active | 2.5–4.5 GB ⚠️ | **Headline "best newest-gen edge model the Orin can run."** Expected to sit memory-wise like our 7-8B dense runs but at 4B-class compute. The flagship datapoint. |
| G5 | **gemma-3-12b-it (QAT q4_0)** | 3 | QAT dense | text+vision | 12 B | ~6.6–7 GB | **Deliberate memory-wall stress (RQ-G4 / HG5).** Placed *over* the practical budget on purpose to characterise the cliff. Negative result is the expected, valuable outcome. |

⚠️ **The two Q4 figures for E2B/E4B come from conflicting sources** (Google VRAM table vs
Unsloth/HF actual GGUF file sizes). Resolving this on device is RQ-G3 — *do not* pre-commit to
either number in the thesis.

**Why not these:** Gemma-4 **26B-A4B MoE** (~14.4 GB) and **31B** (~17.5 GB) exceed 8 GB by
~2× even at Q4 — MoE must load all experts, so "4B active" does not help footprint; both are
out of scope and noted only as the unreachable ceiling. Gemma-3 **27B** (~14 GB) likewise.
Gemma-3 **1B** is skipped as redundant — the 270M (floor) and 4B (working tier) bracket it and
the sweep already has dense 1B-class points (Llama-3.2-1B, Qwen2.5-1.5B).

## 5. Experimental design

Single-family sweep; **generation/architecture is the independent variable**, runtime + device
+ prompt held fixed exactly as in the capability sweep so cross-campaign rows are comparable.

| Variable | Fixed value | Notes / deviation from sweep |
|---|---|---|
| Runtime | llama.cpp (CUDA), `sm_87`, **pinned commit recorded per run** | ⚠️ **may require a rebuild** — see §7 (Gemma 4 support gate). The sweep used `57fe1f0`; record the actual commit used here. |
| Power mode | **15 W (ID=0), clocks locked** (`sudo jetson_clocks`) | Identical to sweep upper-bound config. |
| GPU offload | `-ngl 99` (full offload) | Unified memory; standard path. |
| Context / batch | `llama-bench`: batch **not overridden** (default 2048), context auto-sized per test; `n_ctx = 4096` set **only** on the `llama-completion` TTFT run | pp512 / tg128 (+ tg512 sustained) shapes. **Matches the anchor sweep exactly** — it likewise passed neither `-c` nor `-b` to `llama-bench`. The 4096-ctx KV allocation is captured in peak RAM via the TTFT run. |
| Quantisation | **QAT `q4_0`** for G2–G5; best-available Q4 for G1 | **Deviation from the sweep's `Q4_K_M`** — intentional: QAT is the *vendor-recommended realistic deployment artifact* for Gemma 3/4. Comparability to the sweep is therefore **approximate** (≈ same bits/weight, different block format). Logged as a Decision (§9). |
| Repeats | **5 per measurement**, report median ± σ | No cherry-picking (`CLAUDE.md`). |
| Modality | **text-only path first** for every model | Vision/audio is a follow-up sub-run (RQ-G5), not the primary number, and only where mmproj is available. |
| Thermal start | begin each run from a cooled idle baseline | Avoid heat-soak carryover. |

**Dependent variables (measured):** pp512 tok/s, tg128 tok/s, tg512 sustained, TTFT, peak RAM,
peak swap, idle/mean/peak W, peak °C. **Derived:** tok/s·W⁻¹ (net of idle), J/token. Same
columns as `RESULTS.md` so the new rows append cleanly.

## 6. Predicted operating points (ESTIMATES — to be confirmed/falsified)

Interpolated from the sweep's bandwidth-bound tg curve; **explicitly estimates, not results.**

| # | Model | Predicted resident size | Predicted tg128 tok/s | Predicted regime |
|---|---|---|---|---|
| G1 | gemma-3-270m | < 1 GB | ~90–120 (est.) | overhead/launch-bound; huge headroom |
| G2 | gemma-3-4b QAT | ~3.5–4.5 GB w/ KV | ~12–15 (est.) | comfortable; ~Gemma-2-2B class |
| G3 | gemma-4-E2B QAT | ~3–5 GB w/ KV (RQ-G3) | ~12–16 (est.) | fits; PLE footprint TBD |
| G4 | gemma-4-E4B QAT | ~5–6.5 GB w/ KV | ~8–12 (est.) | near wall; ~7-8B-dense footprint |
| G5 | gemma-3-12b QAT | > 8 GB (over budget) | < 7 or **fails** | **swap thrash expected (HG5)** |

## 7. Pre-run gate: does our llama.cpp build support Gemma 4? (BLOCKING)

Gemma 4 shipped **2026-04-02**; QAT checkpoints **2026-06-05**. The sweep binary (`57fe1f0`)
predates an unknown amount of Gemma-4 graph support. **Before G3/G4, confirm support; do not
guess.** Gate steps:

1. **Gemma 3 first.** G1/G2/G5 are Gemma 3 — well-supported in `57fe1f0`-era builds; run these
   to validate the harness on the family before touching Gemma 4.
2. **Probe Gemma 4 load:** attempt `llama-cli -hf ggml-org/gemma-4-E2B-it-GGUF` (official
   ggml-org GGUF) on device. If it loads → proceed. If it errors on unknown arch/tensor →
   **rebuild llama.cpp** at a commit with Gemma-4 support and **log the new commit + build flags
   in `raw/` and `DECISIONS.md`** (a rebuild changes the runtime variable vs the sweep — note it
   on every affected row).
3. **Candidate GGUF repos (verify on device; exact repo/quant not yet confirmed):**
   - G1 `gemma-3-270m-it` → ggml-org / unsloth GGUF
   - G2 `gemma-3-4b-it` QAT → `google/gemma-3-4b-it-qat-q4_0-gguf`
   - G3 `gemma-4-E2B-it` → `ggml-org/gemma-4-E2B-it-GGUF` (or unsloth UD-Q4_K_XL)
   - G4 `gemma-4-E4B-it` → `ggml-org/gemma-4-E4B-it-GGUF` (or unsloth UD-Q4_K_XL)
   - G5 `gemma-3-12b-it` QAT → `google/gemma-3-12b-it-qat-q4_0-gguf`
   Record the **resolved repo, file, byte size, and SHA** per `CLAUDE.md` once downloaded.

## 8. Results


### Unit G1 — gemma-3-270m-it Q8_0

**Run:** 2026-06-14T15:27 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87
**Gen/arch:** Gemma 3 / tiny dense · 0.27B params
**Note:** Only Q8_0 available upstream; no QAT release for 270M. Deviation from Q4 plan documented in §5 of campaign README.

| Metric | Value |
|---|---|
| SHA256 | `0ef57d2c838458a1952664260dcba38e5bdda37494f3af732f06e4add24068e3` |
| Prefill pp512 (median ± σ, ×5) | **7097.4 ± 51.48 tok/s** |
| Decode tg128 (median ± σ, ×5) | **104.42 ± 0.216 tok/s** |
| Decode tg512 sustained (×3) | 101.84 tok/s |
| TTFT (prompt eval) | 22 ms |
| Peak RAM (tegrastats, mmap lower bound — see §11) | 2458 MB / 7607 MB |
| Swap growth over idle | no — 0 MB over 306 MB baseline |
| Power — idle | 5.17 W |
| Power — mean (active) | 9.24 W |
| Power — peak | 10.85 W |
| Peak SoC temp | 57.7 °C |
| tok/s per watt (total) | 9.62 |
| tok/s per watt (net of idle) | 18.38 |
| J/token (total) | 0.104 |


### Unit G2 — gemma-3-4b-it q4_0 QAT

**Run:** 2026-06-14T15:55 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87
**Gen/arch:** Gemma 3 / QAT dense · 4.0B params


| Metric | Value |
|---|---|
| SHA256 | `76aed0a8285b83102f18b5d60e53c70d09eb4e9917a20ce8956bd546452b56e2` |
| Prefill pp512 (median ± σ, ×5) | **502.5 ± 3.30 tok/s** |
| Decode tg128 (median ± σ, ×5) | **12.15 ± 0.016 tok/s** |
| Decode tg512 sustained (×3) | 12.09 tok/s |
| TTFT (prompt eval) | 130 ms |
| Peak RAM (tegrastats, mmap lower bound — see §11) | 4617 MB / 7607 MB |
| Swap growth over idle | no — +17 MB over 303 MB baseline (within noise) |
| Power — idle | 5.18 W |
| Power — mean (active) | 11.79 W |
| Power — peak | 12.68 W |
| Peak SoC temp | 65.3 °C |
| tok/s per watt (total) | 0.96 |
| tok/s per watt (net of idle) | 1.62 |
| J/token (total) | 1.043 |


### Unit G3 — gemma-4-E2B-it q4_0 QAT

**Run:** 2026-06-14T16:00 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87
**Gen/arch:** Gemma 4 / PLE effective-2B · 5.1B params
**Note:** PLE footprint reality check (RQ-G3). True resident size is the result.

| Metric | Value |
|---|---|
| SHA256 | `3646b4c147cd235a44d91df1546d3b7d8e29b547dbe4e1f80856419aa455e6fd` |
| Prefill pp512 (median ± σ, ×5) | **700.8 ± 25.14 tok/s** |
| Decode tg128 (median ± σ, ×5) | **20.44 ± 0.227 tok/s** |
| Decode tg512 sustained (×3) | 21.00 tok/s |
| TTFT (prompt eval) | 107 ms |
| Peak RAM (tegrastats, mmap lower bound — see §11) | 2968 MB / 7607 MB |
| Swap growth over idle | no — +2 MB over 312 MB baseline |
| Power — idle | 5.25 W |
| Power — mean (active) | 10.71 W |
| Power — peak | 11.94 W |
| Peak SoC temp | 63.9 °C |
| tok/s per watt (total) | 1.71 |
| tok/s per watt (net of idle) | 3.05 |
| J/token (total) | 0.584 |


### Unit G4 — gemma-4-E4B-it q4_0 QAT

**Run:** 2026-06-14T16:04 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87
**Gen/arch:** Gemma 4 / PLE effective-4B · 8.0B params
**Note:** Flagship edge datapoint. Expected memory-wall interaction (HG3).

| Metric | Value |
|---|---|
| SHA256 | `e8b6a059ba86947a44ace84d6e5679795bc41862c25c30513142588f0e9dba1d` |
| Prefill pp512 (median ± σ, ×5) | **361.9 ± 43.94 tok/s** |
| Decode tg128 (median ± σ, ×5) | **11.42 ± 0.189 tok/s** |
| Decode tg512 sustained (×3) | 11.79 tok/s |
| TTFT (prompt eval) | 157 ms |
| Peak RAM (tegrastats, mmap lower bound — see §11) | 4374 MB / 7607 MB |
| Swap growth over idle | **yes (modest) — +97 MB over 314 MB baseline** (only unit to touch swap; consistent with E4B sitting nearest the wall) |
| Power — idle | 5.22 W |
| Power — mean (active) | 11.35 W |
| Power — peak | 12.68 W |
| Peak SoC temp | 65.7 °C |
| tok/s per watt (total) | 0.90 |
| tok/s per watt (net of idle) | 1.53 |
| J/token (total) | 1.110 |


### Unit G5 — gemma-3-12b-it q4_0 QAT

**Run:** 2026-06-14T16:10 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87
**Gen/arch:** Gemma 3 / QAT dense · 12.0B params
**Note:** Deliberate memory-wall stress (RQ-G4 / HG5). OOM/swap expected.
**Outcome: FAILED TO LOAD — hard CUDA OOM at model load, before any inference.**
(The 0.00 tok/s rows the harness first emitted were a reporting artifact — llama-bench
printed a CSV header then aborted; corrected to the failure narrative below. The
underlying run genuinely never produced a token.)

| Metric | Value |
|---|---|
| SHA256 | `dd53172ff3a7b1b16c8fb3d944b87f42a6228ff2de3825b8813ae90d988434cd` |
| Load result | **OOM — `cudaMalloc` failed allocating 7694 MiB for the model weights** |
| Failure mode | hard fail at load with `-ngl 99`; auto-`-fit` was aborted (`n_gpu_layers already set by user to 99, abort`) — see raw `gsweepG5_ttft.txt` |
| Prefill / Decode | n/a — model never loaded |
| Peak RAM (system, at failure) | 766 MB / 7607 MB (weights never became resident; the failed alloc was GPU-side) |
| Swap growth over idle | n/a — +50 MB over 324 MB baseline during the failed allocation; no inference |
| Power — peak | 6.63 W (no compute phase ever started) |
| Peak SoC temp | 56.8 °C |

> **Negative result — expected per HG5 / RQ-G4, but the *mechanism* differs from the
> prediction.** HG5 predicted *swap-thrash at n_ctx=4096*; what actually happened was a
> hard `cudaMalloc` OOM **at load**, before the KV cache or any inference. The 12B Q4
> weights alone (~7.7 GiB) exceed the free unified-memory budget. **Open question for the
> RQ-G4 follow-up:** is this a true cliff, or would partial offload (`-ngl` < 99) let it
> limp? Addressed by the footprint/partial-offload re-run (§11).


### 8.6 Findings & hypothesis scorecard

Headline numbers are direct measurements (llama-bench / llama-completion) and are
**not** affected by the tegrastats data-quality issues in §11 — only the *footprint*
(peak RAM) and *swap* fields were; those are corrected above and re-measured in §11.

| ID | Prediction | Verdict | Evidence |
|---|---|---|---|
| **HG1** | Decode is bandwidth-bound by *total resident bytes*; same-size models → same tg | **Refined / partly false** | E2B (3194 MB file) decodes **20.44 tg** vs G2 (3009 MB file) **12.15 tg** — the *larger* file is *faster*. Decode tracks **active params per token**, not resident bytes: 20.44/12.15 = 1.68 ≈ 4.0B(dense active)/2.3B(E2B active). |
| **HG2** | QAT `q4_0` ≈ `Q4_K_M` ±10% per byte | **Not cleanly testable here** | No same-model `Q4_K_M` vs QAT pair was run; deferred to a quant-sensitivity sub-study (Decision §9). |
| **HG3** | PLE real Q4 footprint exceeds the optimistic mobile spec (1.1/2.5 GB), nearer Google's VRAM table (2.9/4.5 GB) | **Supported** | Authoritative `--no-mmap` resident: E2B **3677 MiB** (§11.3) vs VRAM-table 2.9 GB — 27% above spec. E4B: N/A (too large for malloc on 8 GB Jetson — mmap is essential); tegrastats lower bound 4374 MB is near the VRAM-table 4.5 GB. Both are far above the optimistic mobile spec (1.1/2.5 GB), and E4B's true resident exceeds the tegrastats lower bound (mmap under-counts demand-paged weights). |
| **HG4** | 270M will *not* beat the 2–3B tier on tok/s·W⁻¹ (idle floor dominates) | **Falsified** | G1 = **9.62 tok/s·W** (18.4 net of idle), **0.104 J/tok** — vs the Gemma-2-2B anchor's 2.02 tok/s·W / 0.824 J/tok. Premise was wrong: at 104 tg/s the throughput swamps the idle floor. *Caveat:* tok/s·W is not capability-weighted — the honest claim is "270M produces cheap, fast tokens," not "best edge model." |
| **HG5** | 12B triggers swap-thrash at n_ctx=4096 (degraded/failed run) | **Outcome right, mechanism wrong** | Failure confirmed — but it was a hard `cudaMalloc` OOM **at load** (weights ~7.7 GiB > free unified memory), *before* KV/inference, with **no** swap-thrash. Cliff-vs-gradient under partial offload is the §11 follow-up. |

**The flagship datapoint (RQ-G1 + RQ-G3):** Gemma-4 **E2B** is the best edge operating point in
this sweep — fastest decode (20.44 tg), lowest J/tok among the multi-B models (0.584), comfortable
footprint (no swap), text+vision+audio — because PLE keeps *active* params (≈2.3 B) low while total
params (5.1 B) stay on disk/PLE. This is the generational + architectural win the campaign set out
to find.

## 9. Decisions (campaign-specific)

### 2026-06-14T00:00 — Use vendor QAT `q4_0` GGUFs for Gemma 3/4, not community `Q4_K_M`
- **Decision:** Quantise G2–G5 with Google's **QAT int4 (`q4_0`)** checkpoints; only G1 (270M,
  no QAT release) uses best-available community Q4.
- **Alternatives considered:** (a) match the sweep exactly with `Q4_K_M` for all; (b) unsloth
  dynamic `UD-Q4_K_XL`; (c) this — vendor QAT.
- **Reasoning:** QAT is the *realistic, vendor-recommended* deployment artifact for Gemma 3/4 on
  edge — testing anything else mischaracterises what a deployer would actually ship. The thesis
  question is "what can the Orin run *well*," and QAT is the answer the family was designed for.
- **Tradeoff / cost accepted:** Breaks strict quant parity with the `Q4_K_M` sweep, so Gemma-vs-
  other-family comparisons across campaigns are **approximate** (different block format, ~same
  bits/weight). Noted on every cross-campaign comparison.
- **Revisit when:** a quant-sensitivity sub-study is run (would add `Q4_K_M` Gemma points).

### 2026-06-14T00:00 — Place Gemma-3-12B over budget on purpose
- **Decision:** Include 12B Q4 (~6.6–7 GB) despite expecting it to exceed 8 GB at n_ctx=4096.
- **Alternatives considered:** cap the campaign at E4B (largest expected-to-fit model).
- **Reasoning:** RQ-G4 needs a characterised failure to locate the Gemma memory wall; a
  documented OOM/swap-thrash is thesis content (`CLAUDE.md`: record what doesn't work).
- **Tradeoff:** one of five runs may yield a failure/degraded number rather than a clean point —
  which is the intended result, not a wasted run.
- **Revisit when:** never; if it unexpectedly fits, that itself is the finding.

## 10. Sources (web, gathered 2026-06-14 — claims, not measurements)

- [Gemma 4 model overview — Google AI for Developers](https://ai.google.dev/gemma/docs/core)
- [Gemma releases — Google AI for Developers](https://ai.google.dev/gemma/docs/releases)
- [Run Gemma with llama.cpp — Google AI for Developers](https://ai.google.dev/gemma/docs/integrations/llamacpp)
- [Gemma 4 — How to Run Locally — Unsloth](https://unsloth.ai/docs/models/gemma-4)
- [Gemma 3 — How to Run & Fine-tune — Unsloth](https://unsloth.ai/docs/models/tutorials/gemma-3-how-to-run-and-fine-tune)
- [google/gemma-3-12b-it-qat-q4_0-gguf — Hugging Face](https://huggingface.co/google/gemma-3-12b-it-qat-q4_0-gguf)
- [unsloth/gemma-4-E2B-it-GGUF — Hugging Face](https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF)
- [Gemma 3 QAT models — Google Developers Blog](https://developers.googleblog.com/en/gemma-3-quantized-aware-trained-state-of-the-art-ai-to-consumer-gpus/)
- [Running Gemma 4 Locally: VRAM Requirements table — knightli.com](https://knightli.com/en/2026/05/01/gemma-4-local-vram-quantization-table/)
- [llama.cpp Discussion #22735 — Gemma 4 support — GitHub](https://github.com/ggml-org/llama.cpp/discussions/22735)

## 11. Data quality & post-hoc corrections

Two derived/reported metrics from the first run were unreliable and have been corrected.
The **directly measured** numbers (pp512, tg128, tg512, TTFT, power) are unaffected and stand.

### 11.1 Swap "hit" was a false positive (corrected)
The harness flagged a swap hit on **every** unit. Inspection of the raw tegrastats logs shows
the device carried a **flat ~300 MB pre-existing swap baseline** that never grew during inference
(e.g. G1: `SWAP 306/3804MB` constant for the whole run). The detector used `any(swap > 0)`, which
flags a static baseline as a hit.

- **Fix:** `parsers.py` now measures **growth over the idle baseline** (`swap_growth_mb`), with a
  50 MB threshold (`TegrastatsSummary.SWAP_HIT_THRESHOLD_MB`). Added regression tests.
- **Re-derived results (growth over idle):** G1 0 MB, G2 +17 MB, G3 +2 MB, **G4 +97 MB (real,
  modest — the only unit to touch swap, consistent with E4B nearest the wall)**, G5 +50 MB during
  the failed allocation (no inference). §8 tables and `RESULTS.md` updated.
- **Scope check:** the earlier 10-model sweep had *genuine* swap growth (msweep01 11→206 MB, etc.),
  so its numbers survive — only the gemma sweep was over-flagged. `RESULTS.md` footnote ² updated.

### 11.2 Peak RAM under-counts mmap'd weights — true footprint re-measure (RQ-G3)
tegrastats "RAM used" omits mmap'd, file-backed weight pages, so the peak-RAM column is a **lower
bound**: E2B's reported 2968 MB is *below* its own 3194 MB GGUF, which is impossible for resident
weights. Because **RQ-G3 (true PLE footprint) is the campaign's headline question**, peak-RAM
sampling is not good enough to answer it.

- **Method:** authoritative footprint comes from llama.cpp's own per-buffer allocation report
  (`model` + `KV` + `compute` buffer sizes), captured with `--no-mmap --verbose`. New parser
  `parse_llama_load_buffers` + `LlamaLoadFootprint`; new `--footprint` mode in
  `experiments/run_gemma_sweep.py` runs this for G2/G3/G4.
- **RQ-G4 follow-up (cliff vs gradient):** the same mode re-runs **G5 with partial offload**
  (`--g5-ngl`, default 28) to test whether 12B *limps* on a CPU/GPU split or is a true cliff.

#### 11.3 Footprint re-run results

Method: `llama-cli -ngl 99 -c 4096 --no-mmap -n 16` (no `--verbose` — it flooded stderr with
per-tensor debug output generating GB-scale logs without adding buffer-size information).
llama.cpp prints two allocation passes per load (a probe/dry-run with all-zero model and KV
buffers, then the real allocation); the parser uses last-wins for compute (probe = real value,
so accumulating doubles it) and sums non-zero KV lines (to capture multiple flash-attention
KV-cache segments).  Raw logs: `./raw/*_footprint.txt`.

| Unit | Model | model MiB | KV MiB | compute MiB | **resident MiB** | Notes |
|---|---|---|---|---|---|---|
| G2 | gemma-3-4b-it | 4283 | 254 | 95 | **4632** | CUDA0 3003 MiB (transformer layers) + CUDA_Host 1280 MiB (256k-vocab embedding table, stays on CPU even at -ngl 99) |
| G3 | gemma-4-E2B-it | 3494 | 36 | 147 | **3677** | PLE split: CPU 2153 MiB (shared embeddings) + CUDA0 1342 MiB (per-layer weights); two KV segments (24+12 MiB) |
| G4 | gemma-4-E4B-it | — | — | — | **N/A** | **Failed to load with `--no-mmap`** — 4.7 GiB malloc > free unified RAM. Mmap is *essential* for G4; tegrastats peak 4374 MB (mmap lower bound, §11.1) remains the best footprint estimate |

**G5 partial offload (`-ngl 28`):** **CLIFF** — `cudaMalloc` failed allocating **5168 MiB** on
GPU even at -ngl 28 (28/46 layers offloaded). At -ngl 99 it fails allocating 7694 MiB. This is
a clean cliff: there is no partial-offload operating point that keeps G5 on the Orin Nano at
reasonable quality (would need ≈ -ngl 14 to get below ~3 GiB GPU allocation, at very low
GPU utilization). See §8 Unit G5 for the full OOM characterisation.

_Run: 2026-06-14T17:13 UTC (G2/G3 verbose) and 2026-06-14T19:01–19:02 UTC (G3/G4/G5 clean) ·
15 W locked · llama.cpp `57fe1f0` CUDA sm\_87 · `--no-mmap` (no `--verbose`)_

**Parser fix (2026-06-14):** Earlier runs used `--verbose` which generated 2.3 GB (G2) and
425 MB (G3) logs; the accumulating parser double-counted compute buffers (probe pass = real
value, so each device appeared twice).  Fixed parser uses last-wins for compute, zero-filtered
accumulation for KV.  Self-tests added to `experiments/parsers.py`.

