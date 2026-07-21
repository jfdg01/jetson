# RESULTS — Part I · Exploratory (device benchmarks + grounding Stages 1–4)

Index: [`../../RESULTS.md`](../../RESULTS.md) · Companion: [`../questions/`](../questions/) (research questions) · [`../decisions/`](../decisions/) (what was chosen & why).
Per-campaign detail lives in `experiments/<campaign>/README.md`. Append, never overwrite.

**Global config (all llama.cpp runs):** Jetson Orin Nano 8 GB · 15 W locked (`nvpmodel -m 0` + `jetson_clocks`) · llama.cpp `57fe1f0` CUDA sm_87 · pp512/tg128 · 5 reps each. **Not** uniform across the tables below (corrected 2026-07-21, R-7): quantisation is Q4_K_M for the capability sweep, Q8_0 for G1 and the VLM rows and q4_0 QAT for G2-G5; and `llama-bench` received neither `-c` nor `-b`, so `n_ctx=4096` applies only to the `llama-completion` TTFT runs, not to any pp512/tg128 number here.
**Idle baseline:** ~5.2 W · ~1820 MB RAM · swap 11-50 MB for units 01-04 only; from unit 05 onward every log starts on a ~207-344 MB pre-existing zram baseline that never grows during inference (corrected 2026-07-21, R-7). "Swap hit" therefore means growth >50 MB over the run's own starting value, not over 50 MB absolute.

---

## Part I — Exploratory

### Campaign: llamacpp-upper-bound (2026-06-13)
Full writeup: [`experiments/2026-06-13-llamacpp-upper-bound/`](../../experiments/2026-06-13-llamacpp-upper-bound/README.md)

| Model / quant | Params | pp512 tok/s | tg128 tok/s | Peak RAM | Mean/Peak W | tok/s·W⁻¹ (total board, peak W, tg512) | J/tok (same basis) | Peak °C |
|---|---|---|---|---|---|---|---|---|
| Llama-3.2-3B-Instruct Q4_K_M | 3.2 B² | 570.0 ± 2.4 | 14.61 ± 0.00 (tg512 sustained 14.53 ± 0.02) | 3457 MB³ | 12.5 / 13.6 | ≈1.1 | ≈0.94 | 66.9 |

¹ TTFT not captured here; added in capability sweep (unit 06 re-run → 85 ms).  
² Params taken from the GGUF `model_n_params` = 3,212,749,888 (corrected 2026-07-21, R-21 — the cell read "3.0 B", the marketing name; same correction as the sweep table below).  
³ Peak RAM corrected 2026-07-21 (R-21). The cell previously read "1.87 GiB wts", which is the GGUF **weight size** (`model_size` = 2,011,539,712 B), not a peak-RAM measurement, and so read as if the 3B model needed half the memory it actually did. 3457 MB is the maximum `RAM x/7607MB` sample in this campaign's own `raw/2026-06-13_tegra_decode.log` (215 samples; the idle log holds a flat 1735 MB). The sweep measured 3719 MB for the same model and quant, so the two campaigns agree to ~7%.

---

### Campaign: model-capability-sweep (2026-06-14)
Full writeup: [`experiments/2026-06-13-model-capability-sweep/`](../../experiments/2026-06-13-model-capability-sweep/README.md)

| # | Model / quant | Params² | pp512 tok/s³ | tg128 tok/s³ | tg512 tok/s | TTFT ms⁴ | Peak RAM MB | Idle/Mean/Peak W | tok/s·W⁻¹ (net of idle, peak W)⁵ | J/tok (total board, peak W)⁵ | Peak °C | Swap peak MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | Qwen2.5-0.5B-Instruct Q4_K_M | 0.5 B | 3027 ± 19 | 71.52 ± 0.07 | 71.12 | 38 | 2637 | 5.17/6.57/11.25 | 11.77 | 0.157 | 59.9 | 206 |
| 02 | Llama-3.2-1B-Instruct Q4_K_M | 1.2 B | 1534 ± 2 | 35.07 ± 0.03 | 34.90 | 49 | 3497 | 5.26/8.42/13.32 | 4.35 | 0.380 | 63.3 | 206 |
| 03 | Qwen2.5-1.5B-Instruct Q4_K_M | 1.5 B | 1098 ± 0 | 26.56 ± 0.01 | 26.47 | 59 | 2872 | 5.41/7.88/11.79 | 4.17 | 0.444 | 63.6 | — |
| 04 | Gemma-2-2B-it Q4_K_M | 2.6 B | 728 ± 1 | 15.98 ± 0.01 | 15.87 | 85 | 5818¹ | 5.25/8.47/13.17 | 2.02 | 0.824 | 65.7 | 406 |
| 05 | Qwen2.5-3B-Instruct Q4_K_M | 3.1 B | 559 ± 5 | 14.91 ± 0.02 | 14.90 | 91 | 3180 | 5.25/11.93/12.56 | 2.04 | 0.842 | 65.1 | — |
| 06 | Llama-3.2-3B-Instruct Q4_K_M | 3.2 B | 570 ± 0 | 14.60 ± 0.00 | 14.54 | 85 | 3719 | 5.28/11.02/12.60 | 2.00 | 0.863 | 65.1 | — |
| 07 | Phi-3.5-mini-instruct Q4_K_M | 3.8 B | 432 ± 1 | 13.15 ± 0.00 | 12.76 | 114 | 4693 | 5.25/12.45/13.09 | 1.68 | 0.995 | 65.8 | — |
| 08 | Mistral-7B-Instruct-v0.3 Q4_K_M | 7.2 B | 253 ± 0 | 8.39 ± 0.00 | 8.36 | 190 | 5488 | 5.21/12.45/13.76 | 0.98 | 1.639 | 67.3 | 419 |
| 09 | Qwen2.5-7B-Instruct Q4_K_M | 7.6 B | 266 ± 1 | 7.89 ± 0.01 | 7.86 | 202 | 5465 | 5.23/11.92/13.80 | 0.92 | 1.749 | 67.1 | — |
| 10 | Meta-Llama-3.1-8B-Instruct Q4_K_M | 8.0 B | 245 ± 0 | 7.75 ± 0.01 | 7.72 | 204 | 5953 | 5.25/12.04/13.92 | 0.89 | 1.795 | 67.4 | 460 |

¹ Gemma-2-2B anomalously exceeds Mistral-7B — large KV cache + CUDA workspace at 4096 ctx. Swap "—" rows = growth not separately extracted; raw tegrastats in `experiments/raw/`.  
² Params re-derived 2026-07-21 (R-21) from each GGUF's `model_n_params` so the column is one quantity throughout. Eight rows already carried the measured count; **units 02 and 06 carried the marketing name** and are corrected — 1.0 B → 1.2 B (1,235,814,432) and 3.0 B → 3.2 B (3,212,749,888) — as is unit 05, 3.0 B → 3.1 B (3,085,938,688). This column is the x-axis of the RQ1 bandwidth-bound scaling argument, and the two Llama-3.2 rows were exactly the ones that looked anomalous against the 1/weight-bytes trend.  
³ What the ± means, stated 2026-07-21 (R-21) because the two columns did not use the same one. **pp512 ±** is the spread between the two 5-rep aggregates (bench and sustained) — the sample SD of two run *means*, i.e. |Δ|/√2 — not measurement noise; `llama-bench`'s own within-run σ over the 5 reps is larger in every unit but one (01: ±64.4/±79.8 against the quoted ±19; 06: ±2.3/±2.7 against a quoted ±0, which is the rounding of ±0.42). **tg128 ±** is `llama-bench`'s within-run `stddev_ts` from the bench CSV; units 02 (±0.07 → ±0.03), 03, 04, 05 (±0.00 → ±0.02), 09 and 10 are corrected here to the value the CSV actually emits (the rest already matched). Note the upper-bound table above quotes pp512 on the *other* basis (570.0 ± 2.4 = the within-run σ), so the two tables' ± are not comparable.  
⁴ TTFT is `prompt eval time` on the 12–14-token prompt of the `llama-completion` run (verified against all ten `raw/*_ttft.txt`), **not** the first-token latency of the pp512 workload one column to the left — that prompt is ~40× longer, so this is a lower bound. Qualifier restored 2026-07-21 (R-21); it exists in the campaign README and had been dropped here.  
⁵ The two efficiency columns are on **different bases** and are therefore not reciprocals (1/2.02 ≠ 0.824). Verified by recomputation on all ten rows: `tok/s·W⁻¹ = tg128 / (peak W − idle W)` (unit 01: 71.52/(11.25−5.17) = 11.77) and `J/tok = peak W / tg128` (unit 01: 11.25/71.52 = 0.157). Labels added 2026-07-21 (R-21); the campaign README says "(net)" and the qualifier had been dropped here. **Do not compare this column against the Gemma table's `tok/s·W` below without converting** — see the note there.  
Cross-run consistency (unit 06 = baseline model), like for like: tg128 **14.61 → 14.60** tok/s (−0.07%) and tg512 **14.53 → 14.54** (+0.08%) ✓ — reproducible to well under 0.1%. Corrected 2026-07-21 (R-21): this line read "tg128 14.53 → 14.60 (+0.5%)", which compared the upper bound's tg512 sustained against the sweep's tg128 — two different tests — and so overstated the run-to-run drift by roughly 7×, understating the reproducibility the check exists to demonstrate.

#### Gemma-family sweep (2026-06-14)
RAM = tegrastats mmap lower bound; swap = growth over idle (corrected from false-positive "swap > 0" test).
Full writeup: [`experiments/2026-06-14-gemma-family-sweep/README.md`](../../experiments/2026-06-14-gemma-family-sweep/README.md)

| Unit | Model + quant | Params | pp512 | tg128 | Peak W | tok/s·W (total board, peak W)ᵃ | J/tok (total board, peak W)ᵃ | °C | Peak RAM | Swap |
|---|---|---|---|---|---|---|---|---|---|---|
| G1 | gemma-3-270m-it Q8_0 | 0.27B | 7097 | 104.42 | 10.9 | 9.62 | 0.104 | 58 | 2458 MB | none |
| G2 | gemma-3-4b-it q4_0 QAT | 4.0B | 502 | 12.15 | 12.7 | 0.96 | 1.043 | 65 | 4617 MB | none |
| G3 | gemma-4-E2B-it q4_0 QAT | 5.1B | 701 | 20.44 | 11.9 | 1.71 | 0.584 | 64 | 2968 MB | none |
| G4 | gemma-4-E4B-it q4_0 QAT | 8.0B | 362 | 11.42 | 12.7 | 0.90 | 1.110 | 66 | 4374 MB | +97 MB |
| G5 | gemma-3-12b-it q4_0 QAT | 12.0B | **CUDA OOM at load** | — | 6.6 | — | — | 57 | weights ~7.7 GiB > VRAM | — |

ᵃ Basis labels added 2026-07-21 (R-21). This table's `tok/s·W` is **total board** (G1: 104.42/10.85 = 9.62), so here the two columns *are* reciprocals (1/9.62 = 0.104). The capability-sweep table above uses the same header for a **net-of-idle** quantity, so the two are not on a common basis and must not be read across. Converted: the campaign README's own net-of-idle figures are G1 **18.38**, G2 1.62, G3 3.05, G4 1.53 — on that basis G1 beats the Gemma-2-2B anchor's 2.02 by ~9×, not the ~5× the raw 9.62-vs-2.02 juxtaposition suggests. The gemma README's HG4 scorecard makes exactly that mismatched comparison; its falsified verdict survives the correction (it gets stronger), but the ratio in it does not.

Note: tegrastats under-counts mmap'd weights; `--no-mmap` residents: G2 4632 MiB, G3 3677 MiB (+709 MiB gap — PLE shared matrices not paged in). G4 requires mmap (4.7 GiB malloc > free RAM). G5 hard OOM at load.

#### VLM command-parse feasibility (2026-06-14) — *not* Phase A grounding
Full writeup: [`experiments/2026-06-14-vlm-feasibility/README.md`](../../experiments/2026-06-14-vlm-feasibility/README.md)  
Latency of one command-parse call on 3 committed test images (768×432 / 347×280 / 480×270), N=5 warm passes each. **This campaign measures no IoU and grounds nothing against ground truth** — quality is a prose judgement in its `Grounding` column, carried into `Notes` below.

| Unit | Model | Setup | per_frame | Hz | img_tok | Mean W | RAM | Notes |
|---|---|---|---|---|---|---|---|---|
| V1 | SmolVLM-256M Q8_0 | vlm-server 15W | 304 ± 65 ms | 3.29 | 64 | 6.6 | 1777 MB | poor — incoherent JSON, wrong targets |
| V2 | SmolVLM-500M Q8_0 | vlm-server 15W | 338 ± 148 ms | 2.96 | 64 | 7.2 | 2241 MB | partial — sometimes correct object class |
| V3 | gemma-3-4b-it q4_0 | vlm-server 15W | 9576 ± 98 ms | 0.10 | 256 | 9.7 | 6414 MB | swap; good — correct class+colour |
| V4 | gemma-4-E2B-it q4_0 QAT | `--reasoning off` | 2035 ± 611 ms | 0.49 | 144 | 8.2 | 4616 MB | canonical; partial — inconsistent colour |
| V5 | gemma-4-E4B-it q4_0 QAT | `--reasoning off` | 2963 ± 576 ms | 0.34 | 144 | 8.8 | 6444 MB | swap canonical; partial — inconsistent targets |

Retitled and split from the Phase A rows 2026-07-21 (R-21): V1–V5 previously sat under a heading reading "VLM grounding (Phase A, zero-shot)" with no link, which sent a reader chasing these numbers into the wrong campaign — they come from `2026-06-14-vlm-feasibility`, while Phase A is the RefDrone bbox probe below. The per-frame ± is also restored from the source table; it had been dropped. It matters most for V4, where ±611 ms on a 2035 ms mean is 30%, which is what makes the "0.49 Hz, just at the 0.5 Hz boundary" reading in that campaign's decision fragile.

#### VLM grounding (Phase A, zero-shot, RefDrone val N=50 seed-42, 2026-06-15)
Full writeup: [`experiments/2026-06-14-stage1-baseline/phase-a-grounding-probe.md`](../../experiments/2026-06-14-stage1-baseline/phase-a-grounding-probe.md)

| Unit | Model | Setup | per_frame | Hz | img_tok | Mean W | RAM | Notes |
|---|---|---|---|---|---|---|---|---|
| S1 | SmolVLM-256M Q8_0 | Phase A grounding | 279 ms | 3.58 | — | — | 2338 MB | parse=0/50; IoU@0.25 **undefined** (0 parsed)ᵇ |
| S2 | SmolVLM-500M Q8_0 | Phase A grounding | 832 ms | 1.20 | — | — | 2734 MB | parse=2/50 (4%); IoU@0.25 = 0/2ᵇ |

ᵇ Denominators restored 2026-07-21 (R-21). Both rows previously read "IoU@0.25=0%", which is not what the artifact records: S1's is **0/0** — an empty denominator, undefined rather than measured at zero — and S2's is 0/2, two items. Neither is an IoU measurement of any weight, and the verdict does not rest on them: the informative statement is the parse rate, 0/50 with a 95% Wilson interval of [0, 0.071], which is enough on its own to abandon the spine (`claims.json` P1-S1.2, n_effective 47 over 50 items — 3 images appear twice). The gate the campaign actually failed on was parse rate ≥50%.

---

### Campaign: toy-nl-demo (2026-06-15)
Full writeup: [`experiments/2026-06-15-toy-demo/README.md`](../../experiments/2026-06-15-toy-demo/README.md)  
TURN: closed heuristic, <1 ms, no model. FOLLOW/ZOOM: zero-shot SmolVLM-500M Q8_0, both failed (format echo / full-frame bbox). Pre-registered expected outcome — pipeline mechanics work, grounding needs fine-tuning.

---

### Campaign: phase-b-sitl (2026-06-15)
Full writeup: [`experiments/2026-06-14-stage1-baseline/phase-b-sitl.md`](../../experiments/2026-06-14-stage1-baseline/phase-b-sitl.md)  
x86_64 SITL (not Jetson). Oracle bbox → ByteTrack → cascade PID → pymavlink offboard.

| Trials | Loop Hz | Mean pixel err | Coverage | Track losses | Result |
|---|---|---|---|---|---|
| 3 × 60 s, one scenario (n_effective = 1) | 19.99 | 12.9 px | 100% | 0 (cannot fail — see below) | **PASS** (capability gate) |

Zero variance is real: programmatic rover trajectory, P-controller converges to the same steady-state lag each run.

Reframed 2026-07-21 (R-21). The row previously read `19.99 ± 0.0` / `12.9 ± 0.0 px` over "3 × 60 s", which presents it as three replicates with a measured spread. It is not: the three trials share one programmatic trajectory (0.25 m/s north, rover re-anchored 0.5 m ahead at each start), so `claims.json` P1-S1.3 records **n_effective = 1** against 3597 frames, and a ± over non-independent runs is not a sampling error — the ± columns are dropped rather than restated. The frame count must never be used as n. **"Track losses = 0" is structurally guaranteed, not an outcome:** the ~25 Hz synchronous oracle supplied a detection every frame, so the LOST_TIMEOUT that declares a loss could never elapse — the same reasoning the Phase C retraction box below uses to state that Phase B is unaffected by the ByteTrack defect. What 3/3 shows is that the stack **can** close the loop; it says nothing about a rate over scenarios. The 12.9 px is still an honest number against the pre-registered <50 px threshold (no widening) — it is one scenario's number.

---

### Campaign: phase-c-vlm (2026-06-15)
Full writeup: [`experiments/2026-06-14-stage1-baseline/phase-c-vlm.md`](../../experiments/2026-06-14-stage1-baseline/phase-c-vlm.md)

| Mode | Platform | Key metrics | Result |
|---|---|---|---|
| inject-oracle Branch-1 | x86_64 SITL | hz=19.99 · coast_max=99 frames · reseed=0.000 s (the three gated quantities) · track_cov=98.1% · oracle_cov=100% · ~~px_err=89.4~~ · ~~1 track loss~~ | **PASS** (integration) |
| ~~vlm zero-shot Branch-2~~ | SITL + Jetson SmolVLM-500M Q8_0 | ~~hz=19.99 px_err=190.5 valid=12.5% track_cov=21%~~ | **RETRACTED 2026-07-20** |

> **⚠ Retracted 2026-07-20 by P6.0** ([`../results/part6-flight.md`](part6-flight.md), full detail in
> [`experiments/2026-07-20-p60-flight-rig/README.md`](../../experiments/2026-07-20-p60-flight-rig/README.md)).
> **Branch-2 is withdrawn:** the Gazebo camera was aimed at the **sky** (pitch −π/2 instead of +π/2)
> for this entire campaign, so the frame was flat gray — 100.0% one colour, mean 218, std 0.0. The
> VLM was grounding an NL expression in a blank image; those numbers measure a broken render, not
> the model. **RQ-S1.4 → UNANSWERED.** Not re-run: SmolVLM-500M was eliminated in the Part IV bake-off.
> **Branch-1's px_err 89.4 is also withdrawn** — a separate ByteTrack defect (lost tracks could only
> be re-found by a *low*-score detection, so its 1 Hz `score=1.0` injections spawned a new ID every
> time and the Kalman coast degraded to zero-order hold) inflated it. Branch-1's integration PASS
> stands; the pixel-error figure does not. Phase B is unaffected (25 Hz synchronous oracle → a
> detection every frame → no track ever went lost).

Branch-1 metrics corrected 2026-07-21 (R-21). The cell read `hz=19.99 ~~px_err=89.4~~ valid=100%`, and **`valid` is not a Branch-1 measurement** — the Branch-1 table in the artifact has no such column; `valid` is Branch-2's VLM-parse-rate metric, and an *injected* oracle box is valid by construction, so a 100% there is a quantity that cannot fail. In its place: the three quantities the Branch-1 gate actually turns on (hz ≥15 ✓, coast ≥15 frames ✓, re-seed <2 s ✓) and the two Branch-1 numbers that could have failed and were omitted, `track_cov` 98.1% (run 3's forced gap) and `oracle_cov` 100%. The track-loss count is struck for the reason the box above gives: with the ByteTrack re-find defect a track was continuously replaced rather than lost, so both "1 loss" and "0 losses" are vacuous. The PASS is unchanged — none of the three gates turns on pixel error or loss count.

---

### Stage 2: SmolVLM fine-tune (2026-06-16)
Full writeup: [`experiments/2026-06-15-stage2-finetune/train-log.md`](../../experiments/2026-06-15-stage2-finetune/train-log.md)  
1 epoch · 23,437 steps · 32,723 s · mean loss 0.8341.

| Epoch | Parse rate | IoU@0.25 | Result |
|---|---|---|---|
| 1 | 100% | **1.0%** | **FAIL — mode collapse** |

**Negative result:** LoRA text-only on SmolVLM; frozen SigLIP cannot update spatial features → collapses to marginal mean bbox (~[223,111,229,120] in 512×288 space). Demonstrates limit of text-only LoRA for spatial grounding.

---

### Stage 3: RefCOCO fine-tune (2026-06-16–17)
Full writeup: [`experiments/2026-06-16-stage3-refcoco-finetune/train-log.md`](../../experiments/2026-06-16-stage3-refcoco-finetune/train-log.md)  
Fix: well-posed RefCOCO targets + normalized 0–1000 coords + attn+MLP LoRA.

| Run | Date | Outcome |
|---|---|---|
| Run 1 | 2026-06-16 | **CRASHED** — CUDA unspecified launch failure at 70% epoch 1 (RTX 3090 hardware fault); loss was healthy (1.25→0.94). No mid-epoch checkpoint → all progress lost. |
| **Run 2** | 2026-06-17 | **SUCCESS** — 11.0 h · parse=100% · **IoU@0.25=82.5%** · center_std=200.5 · mean_iou=0.527. |

Export parity (HF bf16 vs GGUF, RefCOCO val n=100, seed-42): HF 85/100 → F16 62/100 → Q8_0 55/100 — **−30pp total gap FAIL** (gate ≤5pp). Root cause: the transformers→llama.cpp **Idefics3 preprocessing divergence**, −23pp (85 → 62). The remaining −7pp (F16 62 → Q8_0 55) is **not separable from noise**: the paired McNemar over the same 100 items gives b=17, c=10, exact p=0.248 (re-derived here from `raw/g3_parity_gguf_f16.jsonl` and `raw/g3_parity_gguf.jsonl`; registry `claims.json` P1-S3.3). Softened 2026-07-21 (R-21) — the sentence read "preprocessing divergence (−23pp) + Q8_0 quant (−7pp)", which presents the two as additive root-cause terms when only the first is significant. The fidelity loss is in the **export path**, not in the 8-bit quantisation, and the −7pp is reported as an observed difference the test cannot distinguish from zero. Motivates spine switch to Qwen2-VL-2B.

---

### Stage 4: RefCOCO→RefDrone curriculum (2026-06-17)
Full writeup: [`experiments/2026-06-17-stage4-refdrone-curriculum/train-log.md`](../../experiments/2026-06-17-stage4-refdrone-curriculum/train-log.md)  
Init from Stage 3 merged weights, LoRA on well-posed RefDrone subset (4101 train / 439 val), 3 epochs. **Eval capped at n=200**, and the same 200 items are reused at every epoch — the three rows below are one val set scored three times, not three independent measurements (n stated 2026-07-21, R-21; it appeared nowhere in this block before).

| Epoch | mean_loss | parse_rate | IoU@0.25 | mean_iou | center_std |
|---|---|---|---|---|---|
| 1 | 1.0287 | 100.0% | 12.5% | 0.072 | 214.1 |
| 2 | 0.9478 | 100.0% | 16.0% | 0.087 | 214.3 |
| 3 | 0.9168 | 100.0% | **19.5%** | 0.109 | 211.5 |

Gate G4 (IoU@0.25 ≥20%) — **NARROW MISS**: 39/200 = 19.5% against a 40/200 threshold, i.e. a **one-item** miss. Reframed 2026-07-21 (R-21) from "0.5pp short", which is a precision the data does not carry: the 95% Wilson interval on 39/200 is [0.146, 0.255] and straddles the gate, so these data cannot separate "missed" from "met". The recorded NARROW MISS is a defensible **engineering** decision — the gate was pre-registered and the count is one short of it — and an indefensible statistical one; it is kept as the former and must be cited as the former (`claims.json` P1-S4.1). Loss still descending at LR anneal → budget/capacity bound, not failure mode. ~20× lift over Stage 2 (~1%) and ~10× over the 2.0% RefCOCO-init cross-domain floor (a Stage-3 checkpoint evaluated off-domain, not a zero-shot floor; corrected 2026-07-21, R-7 — the two multipliers were swapped here). The 2.0% rests on 1/50, whose 95% interval reaches ~10.6%, so read the second multiplier as a bound. Next levers: largest-box augmentation, higher resolution.

---
