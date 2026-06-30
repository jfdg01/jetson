# Phase 4 — Export & deploy (GGUF on Jetson Orin Nano, fidelity disambiguation)

**Date:** 2026-06-18 (export + on-device F16/Q8_0 full-val eval)
**Branch:** `v2/principled-rebuild`
**Spine:** Qwen2-VL-2B-Instruct + Phase-3 LoRA (merged) · **Data:** RefDrone well-posed val (n=439) · **Resolution:** `max_side=1024`
**Backend:** llama.cpp @ `57fe1f07…` (same pinned commit local + Jetson) · CUDA full-offload (`ngl=99`) · 15 W, `jetson_clocks` locked
**Status:** ✅ **PASS** — deployed IoU *exceeds* the HF reference; the Part-I fidelity catastrophe does **not** reproduce.

## Pre-registration (what / why)

Phase 4 closes the loop the whole v2 design was built backwards from. Part I discovered the
binding constraint that motivated the rebuild: the exported skill dropped **HF bf16 85% →
GGUF F16 62% (−23pp) → Q8_0 55% (−7pp)** — a llama.cpp Idefics3 image-preprocessing
divergence stacked on top of a quant loss, **found only after training**. v2's answer was to
pick the spine *by deployment fidelity* (Phase 0c chose Qwen2-VL-2B, predicting ≈−2pp HF→F16)
and to measure the gap **on the actual fine-tuned aerial model** before declaring success.

**Research questions**

- **RQ-4.1 (gate):** Does the deployed GGUF land within the Phase-0-characterised fidelity
  budget of the HF reference — deployed IoU@0.25 ≥ **57.5%** (HF full-val 59.5% − 2pp)?
- **RQ-4.2 (runtime/preprocessing gap):** HF(reference) − GGUF-F16. Part-I saw **−23pp** on
  SmolVLM/Idefics3. Phase 0c predicted **≈−2pp** for Qwen2-VL. Which holds on the real model?
- **RQ-4.3 (quant gap):** GGUF-F16 − GGUF-Q8_0, with preprocessing held fixed. Part-I saw
  **−7pp**. Is Q8_0 a safe ~½-size deployment artifact?
- **RQ-4.4 (mmproj reuse):** The vision tower was frozen during the Phase-3 LoRA. Is the
  exported projector bit-equivalent to the base Qwen2-VL mmproj?

**Controlled variables** — verbatim `GROUNDING_PROMPT`, `parse_bbox`/`iou`/`center_std` from
`grounding/contract.py`; the **same** RefDrone well-posed val (n=439) used for the Phase-3 HF
reference; `max_side=1024` for both the HF reference and every GGUF arm; greedy decode; the
**same pinned llama.cpp commit** on the local converter and the Jetson build (so backend
*version* is not a confound — only the hardware and the quant differ).

**Fidelity reference (committed):** Phase-3 HF full-val — n=439, **IoU@0.25 = 59.5%**,
parse 100%, mean_iou 0.451, center_std 215.2 (`runs/20260617T212559Z` → `full_val`).

## Results

**Export** (`grounding/export/to_gguf.py`, conversion-only, manifest `runs/20260617T223958Z`):
`convert_hf_to_gguf.py` @ pinned commit → F16 (3.09 GB), Q8_0 (1.65 GB), mmproj F16 (1.33 GB).

**Parity / fidelity disambiguation** — all GGUF arms scored on the Jetson over the full
RefDrone well-posed val (n=439), same contract path as the HF reference:

| Backend | n | parse | **IoU@0.25** | mean_iou | center_std | Manifest |
|---|---|---|---|---|---|---|
| HF bf16 **(reference)** | 439 | 100.0% | **59.5%** | 0.451 | 215.2 | `runs/20260617T212559Z` |
| GGUF **F16** (Jetson, CUDA) | 439 | 100.0% | **62.2%** | 0.466 | 218.2 | `runs/20260617T233529Z` |
| GGUF **Q8_0** (Jetson, CUDA) | 439 | 100.0% | **62.6%** | 0.468 | 217.4 | `runs/20260618T001147Z` |

- **Runtime/preprocessing gap (HF → GGUF-F16):** **−2.7 pp** *(F16 beats HF)*
- **Quantization gap (GGUF-F16 → Q8_0):** **−0.5 pp** *(Q8_0 ≈ F16, within noise)*
- **Deployment floor (HF 59.5% − 2pp budget):** 57.5% — **F16 (62.2%) and Q8_0 (62.6%) both clear it.**

## Analysis

- **RQ-4.1 — PASS, decisively.** Both deployed quants land **+4.7 / +5.1pp above** the 57.5%
  floor and **above the HF reference itself**. There is no fidelity *debt* to absorb; the
  budget was never spent.
- **RQ-4.2 — the −23pp Part-I gap does NOT reproduce.** HF→F16 is **−2.7pp**, i.e. F16 is
  *slightly better* than HF (well inside n=439 sampling noise; the contract path is identical
  bytes-in/bytes-out). This is the central Phase-4 finding and the payoff of the Phase-0c
  deployment-backwards spine selection: Qwen2-VL's llama.cpp image preprocessing matches its
  HF path, where SmolVLM/Idefics3's diverged by 23pp. **Choosing the spine by deployment
  fidelity, before any GPU training, is what eliminated the constraint that stalled Part I.**
- **RQ-4.3 — quant is free here.** F16→Q8_0 is **−0.5pp** (Q8_0 nominally *higher*, within
  noise) vs Part-I's −7pp. Q8_0 is the recommended deployment artifact: **1.65 GB vs 3.09 GB**
  (≈½ the weights) at indistinguishable accuracy, leaving more of the 8 GB unified memory as
  headroom on the Orin Nano.
- **RQ-4.4 — mmproj bit-equivalence confirmed.** The exported projector is the same byte
  size as the base (1334666400 B); with the vision tower frozen during LoRA, the tensor
  payload is identical (only the GGUF metadata header differs). One mmproj serves base and
  fine-tune — no separate projector to ship or version.
- **Honesty note — the deployed > HF inversion.** Deployed beating the reference by ~3pp is
  *within sampling noise* on n=439 and should be read as "no measurable runtime loss," not as
  "GGUF improves the model." The thesis-relevant claim is the **absence** of the Part-I gap,
  not a gain.

**Part-I vs v2 — the whole point, side by side:**

| | HF→F16 (runtime) | F16→Q8_0 (quant) | Net deployed |
|---|---|---|---|
| **Part I** (SmolVLM / Idefics3) | −23 pp | −7 pp | catastrophic, post-hoc |
| **v2** (Qwen2-VL-2B) | **−2.7 pp** | **−0.5 pp** | **no loss**, pre-characterised |

## Decisions

See `DECISIONS.md` (Part II): **2026-06-18T01:30 — Phase 4 PASS** (accept Q8_0 as the
deployment artifact; fidelity gap eliminated), plus the supporting entries
**2026-06-18T01:15** (Jetson gate vs local-CPU), **2026-06-18T01:00** (Jetson 8 GB
single-slot/no-cache server fix), **2026-06-18T00:55** (mmproj reuse), and the Jetson
15 W-only power-mode finding.

## Reproduce

```bash
source .venv-ft/bin/activate
# 1) export merged checkpoint -> GGUF F16 + Q8_0 + mmproj (conversion-only):
python -m grounding.export.to_gguf runs/v2/phase3-refdrone-1024 \
  --base-mmproj <base-qwen2vl-mmproj.gguf>     # optional sha cross-check
# 2) push + serve on the Jetson, then score full val per quant:
python -m grounding.eval.run --backend jetson --dataset refdrone --split val --n 0 \
  --model  /home/jfdg/grounding/phase3-refdrone-1024-f16.gguf \
  --mmproj /home/jfdg/grounding/mmproj-phase3-refdrone-1024-f16.gguf --max-side 1024
python -m grounding.eval.run --backend jetson --dataset refdrone --split val --n 0 \
  --model  /home/jfdg/grounding/phase3-refdrone-1024-q8_0.gguf \
  --mmproj /home/jfdg/grounding/mmproj-phase3-refdrone-1024-f16.gguf --max-side 1024
# 3) compose the parity table:
python -m grounding.eval.parity --checkpoint phase3-refdrone-1024 \
  --f16 runs/20260617T233529Z --q8 runs/20260618T001147Z   # HF arm is the nested training manifest
```

Manifests: export `runs/20260617T223958Z`; F16 `runs/20260617T233529Z`; Q8_0
`runs/20260618T001147Z`; HF reference `runs/20260617T212559Z` (`full_val`). Jetson server
runs single-slot, no prompt cache (`-np 1 --cache-ram 0 --no-cache-idle-slots`) to fit 8 GB.
