# RESULTS — Part IV · End-to-end workflow refinement (v4)

Index: [`../../RESULTS.md`](../../RESULTS.md) · Companion: [`../questions/`](../questions/) (research questions) · [`../decisions/`](../decisions/) (what was chosen & why).
Per-campaign detail lives in `experiments/<campaign>/README.md`. Append, never overwrite.

---

## Part IV — End-to-end workflow refinement (v4)

Goal: the two-tier follow loop passed T0–T4 in isolation, but the integrated NL→ground→track→fly pipeline does not hold up end-to-end. Part IV hardens it.

### 2026-06-30 — VLM backbone bake-off ([`experiments/2026-06-30-vlm-backbone-bakeoff/`](../../experiments/2026-06-30-vlm-backbone-bakeoff/README.md))

FT: LoRA r=16/α=32 bf16, vision frozen, eff. batch 16, lr swept {1e-4, 2e-4, 4e-4}, ≤3 epochs,
RefDrone well-posed (4101/439), RTX 3090. Deploy rows: Jetson Orin Nano 8 GB @ 15 W, llama.cpp
`57fe1f0` Q8_0 ngl=99. **Campaign early-stopped 2026-07-02** — decision determined before arms D /
E-legs-2-3 (see README Findings).

| Arm | best lr | path | parse | IoU@0.25 | mean IoU | wall/anchor | verdict |
|---|---|---|---|---|---|---|---|
| baseline Qwen2-VL-2B (deployed) | — | WF@1024 / ROI M=2.0@512 | 100% | 63.1% / 85.2% | 0.477 / — | 4400 / ≈2000 ms | **incumbent, kept** |
| A InternVL3-2B | 4e-4 | WF@1024 (HF, n=200) | 100% | 48.5% | 0.298 | N/A — GGUF export blocked @`57fe1f0` | eliminated |
| B Qwen2.5-VL-3B | 2e-4 | WF@1024 / ROI M=2.0@512 (Jetson Q8_0, n=439) | 100% | 53.1% / **33.0% (ROI collapse)** | 0.399 / 0.170 | 5990 / 2817 ms | eliminated |
| C PaliGemma2-3B@448 | 2e-4 | WF@448 (HF, n=200) | 100% | 56.0% | 0.391 | not measured (moot) | eliminated |
| E SmolVLM2-500M | 1e-4 (leg 1 only) | WF@512 (in-loop val) | 100% | **5.5% (capacity collapse)** | 0.038 | not deployed | eliminated |
| D Florence-2-large | — | — | — | cancelled un-run | — | — | cancelled |

### 2026-07-02 — Temporal acquire-carry, Phase 0 zero-shot ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

Zero-shot SAM2.1-hiera-tiny (`sam2==1.1.0`, bf16 autocast, RTX 3090) memory-carry from a single
first-frame GT box prompt; AerialMind 93 seqs × 2 tracks (longest + longest-with-gap), ≤300-frame
window, scored on labeled frames only. First launch invalidated at 42/93 by a GT decode bug
(labels are top-left-encoded, not JDE center — see campaign README Findings); rerun clean.

| Run | tracks | mean IoU | IoU@0.25 | IoU@0.5 | ID-consistency | occ-recovery | pred-absent | FPS (3090) | wall |
|---|---|---|---|---|---|---|---|---|---|
| phase0-zeroshot-carry | 186 | 0.602 | **0.849** | 0.750 | **0.891** | 0.329 (70 gaps) | 3.5% | 14.4 | 58.4 min |

Demo (real Jetson Q8_0 acquire, M0205): occlusion clip — acquire IoU 0.947 @4.54 s, carry 252 f
through a 40-frame GT gap, mean IoU 0.886; retarget clip — mid-video caption switch truck→"the
black car", retarget IoU 0.721 @4.1 s, mean IoU 0.887. Committed `ab6d6d7`.

### 2026-07-02 — Temporal acquire-carry, Phase 1 SITL latency-injection ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

Oracle-box follow loop (perception perfect) with the temporal design's measured costs injected:
acquire/reground latency U(4.1, 4.6) s, parse-fail p=0.007, 5 s synthetic occlusion @ t=30 s,
LossGate 60 no-box frames (3 s @ 20 Hz). ArduCopter SITL, 10 m AGL, gimbal-level camera, rover
programmatic north; 75 s/trial. `phase1_sitl.py`, raw CSVs in campaign `raw/phase1-sitl/`.

| Rover speed | in-FOV frac | first lock | regrounds | occlusion relock wall | carry px-err | verdict |
|---|---|---|---|---|---|---|
| 0.25 m/s (gate) | **1.000** | 4.31 s | 1 | **4.46 s** | 16.1 px | **PASS** |
| 0.5 m/s | **1.000** | 4.26 s | 1 | 4.21 s | 32.0 px | PASS |
| 1.0 m/s | 0.482 | 4.36 s | 1 (8 failed re-acquires) | never | 66.2 px | FAIL — speed ceiling |

### 2026-07-02 — Temporal acquire-carry, Phase 2 Jetson FPS knee ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

SAM2.1-hiera-tiny on the Orin Nano 8 GB @ **15 W + jetson_clocks** (`torch==2.8.0`,
`~/sam2-bench/.venv`, M0205 100-frame bench); accuracy = full 186-track AerialMind eval on the
3090, same protocol as Phase 0. Accuracy bar = 0.799 (1024's 0.849 − 5 pp); FPS gate ≥ 5.

| image_size | Jetson FPS solo | co-resident (VLM Q8_0) | IoU@0.25 | mean IoU | verdict |
|---|---|---|---|---|---|
| 1024 | 2.68 | 2.68 (RAM 6963/7607 MB) | **0.849** | 0.602 | accuracy reference; FPS FAIL |
| **768 (OP)** | 4.89 | 4.89 | **0.830** | 0.585 | acc PASS; FPS marginal FAIL (−2.2%) |
| 640 | 7.25 | 7.24 (RAM 6144/7607 MB) | 0.787 | 0.551 | FPS PASS; acc FAIL by 1.2 pp |
| 512 | 12.13 | — | 0.737 | 0.506 | FPS PASS; acc FAIL (−11.2 pp) |

Operating point **768** by the pre-frozen rule; co-residency costs zero FPS at every size
measured (RQ-T.3). TensorRT export (`experiments/2026-07-02-carry-trt-export/`) is the named
fix for the 2.2% rate shortfall.

### 2026-07-02 — Temporal acquire-carry, Phase 3 integrated end-to-end ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

Streaming carry parity (3.0): stream-vs-batch mean box-IoU 0.9974 @1024 / 0.9968 @512 (gate
≥0.99). Integrated trials: ArduCopter SITL + synthetic nadir renderer, real Jetson Q8_0 VLM
acquire, 5 s bridge occlusion @ t≈30 s, rover 0.25 m/s north, 75 s.

| Run | carry | in-FOV | first lock | acq (rej) | relock wall | px-err | carry rate | verdict |
|---|---|---|---|---|---|---|---|---|
| 3a run 1 | 3090 @1024 | 0.544 | 2.7 s | 2 (0) | 2.36 s | 8.6 | 12.0 FPS | FAIL — VLM locked a road dash during occlusion (unvalidated reground) + ingress lag |
| 3a run 2 (+size-prior validation, dead-reckoning, 3 s loss gate) | 3090 @1024 | **1.000** | 2.65 s | 7 (**5**) | 13.9 s | 16.2 | 13.6 FPS | **PASS** |
| 3b | **Jetson @768, VLM co-resident** | **1.000** | 3.02 s | 7 (5) | 14.35 s | 22.5 | **4.1 FPS** | behavioral legs **PASS**; rate leg **4.1 < 5 FPS marginal FAIL** (pre-registered expected outcome at OP=768) |

3b rate: whole-trial 7.6 Hz is inflated by blind phases; carry-phase 4.1 FPS = Jetson 204.6 ms/step
+ ~40 ms JPEG/tunnel (est. 4.5–4.8 — wire overhead underestimated). Dead-reckoning held the
copter-target gap at ~2.2 m across the 13.9 s blind window (3a-2 CSV forensics).
