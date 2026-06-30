# Phase A — Zero-Shot Grounding Probe

**Campaign:** Stage 1 Zero-Shot Grounding Baseline  
**Date:** 2026-06-14 (started), 2026-06-15 (complete)  
**Status:** Complete  
**Script:** `runners/run_grounding_probe.py`

---

## Setup

- **Models:** SmolVLM-256M-Instruct Q8_0 (S1), SmolVLM-500M-Instruct Q8_0 (S2)
- **PaliGemma status:** Excluded — see `DECISIONS.md` entry 2026-06-14 (PR #7553 not merged in baseline commit `57fe1f0`)
- **Dataset:** RefDrone val split, N=50, seed=42, single-target filter
  - Annotation source: `sunzc-sunny/RefDrone` (corrected from `sun-langwei/RefDrone` — see DECISIONS.md)
  - Image source: VisDrone 2019-DET (downloaded separately)
  - Bbox format: XYWH absolute pixels (to verify in Phase 0-B)
- **Prompt formats tested:** A (JSON) and B (plain csv) — winner selected by parse rate on N=5 pilot

---

## Prerequisites checklist

- [x] `sunzc-sunny/RefDrone` annotations downloaded — `/home/gara/refdrone-annotations/`
- [x] VisDrone 2019-DET val images downloaded — `/home/gara/visdrone-dataset/VisDrone2019-DET-val/images/` (1428/1428 present)
- [x] Annotation format verified (XYWH absolute px, caption in image record, 7 no-target items filtered) — Phase 0-B 2026-06-15
- [x] Jetson clocks locked: `sudo nvpmodel -m 0 && sudo jetson_clocks` (confirmed 2026-06-15 before S2 run — CPU min=max=1510400 kHz)
- [x] SmolVLM models on device (confirmed from VLM feasibility campaign)

---

## Run command

```bash
# Prerequisite: lock clocks on device
# ssh jetson 'sudo nvpmodel -m 0 && sudo jetson_clocks'

# Dry-run first to verify SSH tunnel and commands:
python runners/run_grounding_probe.py \
    --refdrone-ann /home/gara/refdrone-annotations/RefDrone_val_mdetr.json \
    --visdrone-images /home/gara/visdrone-dataset/VisDrone2019-DET-val/images \
    --dry-run

# Full run (SmolVLM already on device from V-campaign):
python runners/run_grounding_probe.py \
    --refdrone-ann /home/gara/refdrone-annotations/RefDrone_val_mdetr.json \
    --visdrone-images /home/gara/visdrone-dataset/VisDrone2019-DET-val/images \
    --skip-download

# Format pilot only (5 images, tests both prompt formats):
python runners/run_grounding_probe.py \
    --refdrone-ann /home/gara/refdrone-annotations/RefDrone_val_mdetr.json \
    --visdrone-images /home/gara/visdrone-dataset/VisDrone2019-DET-val/images \
    --skip-download --pilot-only
```

---

## Results

### Unit S1 — SmolVLM-256M-Instruct Q8_0

**Run:** 2026-06-15T07:34 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87  
**Dataset:** RefDrone val split, N=50, seed=42, single-target filter (439/1428 images)  
**Prompt format:** A  
**Note:** Both files already on device from VLM feasibility campaign (V1).

| Metric | Value |
|---|---|
| Server load time | 3 s |
| Format pilot | Format A: 0/5 parsed (0%) |
| **Parse rate** | **0/50 (0.0%)** |
| **IoU@0.25** (of parsed) | **0/0 (0.0%)** |
| **IoU@0.5** (of parsed) | **0/0 (0.0%)** |
| **Mean IoU** (of parsed) | **0.000** |
| Median wall ms / frame | 279 ms |
| **Hz** (grounding rate) | **3.58 Hz** |
| Peak RAM | 2338 MB |
| Swap hit | no |
| Power — mean (active) | 8.58 W |
| Peak SoC temp | 53.8 °C |

**Observation:** S1 produced 0 parseable responses across both format pilots and the bulk run. The model generated free-text descriptions rather than structured coordinates — no bbox-like output in any of the 50 responses.

---

### Unit S2 — SmolVLM-500M-Instruct Q8_0

**Run:** 2026-06-15T07:43 UTC · 15 W locked · llama.cpp `57fe1f0` CUDA sm_87  
**Dataset:** RefDrone val split, N=50, seed=42, single-target filter (439/1428 images)  
**Prompt format:** A  
**Note:** Both files already on device from VLM feasibility campaign (V2).

| Metric | Value |
|---|---|
| Server load time | 3 s |
| Format pilot | Format A: 0/5 parsed (0%) |
| **Parse rate** | **2/50 (4.0%)** |
| **IoU@0.25** (of parsed) | **0/2 (0.0%)** |
| **IoU@0.5** (of parsed) | **0/2 (0.0%)** |
| **Mean IoU** (of parsed) | **0.001** |
| Median wall ms / frame | 832 ms |
| **Hz** (grounding rate) | **1.20 Hz** |
| Peak RAM | 2734 MB |
| Swap hit | no |
| Power — mean (active) | 5.74 W |
| Peak SoC temp | 56.8 °C |

**Observation:** S2 generated coordinate-like output on most frames but consistently used Python-style single-quoted dicts (`{'x1': ..., 'y1': ..., 'x2': ..., 'y2': ...}`) and alternative schemas (`{'bbox': [x,y,x2,y2]}`), neither of which passes the JSON double-quote parser. The 2 frames that parsed produced degenerate or out-of-range boxes (IoU ≈ 0). S2 is slower than S1 (832 ms vs 279 ms per frame) due to larger model size, with no corresponding quality gain.

**Parser note (negative result, documented):** The 0% pilot parse rate masked the fact that S2 _was_ generating bbox-structure output, just in an unparseable format. A more permissive parser (accepting single quotes, key variants like `bbox`, `x`, `y`) would increase parse rate — but the IoU scores on the two frames that did parse were effectively zero, so format is not the binding constraint.

---

## Decision gate (post-run)

| Result | Threshold | Actual | Trigger? |
|---|---|---|---|
| Best model IoU@0.25 | ≥ 30% | 0% (S2, 0/2 parsed) | **YES — below threshold** |
| Best model parse rate | ≥ 50% | 4% (S2) | **YES — below threshold** |

**Verdict:** Both conditions for the "fine-tune is load-bearing" branch are met.

- **IoU@0.25 < 30%:** Zero-shot SmolVLM cannot localize drone targets at all. Fine-tuning must supply the grounding capability from scratch — it is not incremental improvement.
- **Parse rate < 50%:** Prompt engineering alone cannot recover grounding quality before the bulk IoU metric is even meaningful. However, as noted above, S2 output structure suggests the format failure is secondary to the model simply not understanding the localization task.

**Selected model for Phase C (fine-tuning):** S2 — SmolVLM-500M-Instruct Q8_0  
**Rationale:** S2 showed marginally higher parse rate (4% vs 0%) and generated bbox-like structure in its responses, indicating the 500M model has at least latent awareness of coordinate output formats. S1 produced pure free-text with no structural signal whatsoever. S2 also fits comfortably in RAM (2734 MB, no swap). S2's lower Hz (1.20 vs 3.58) is acceptable at this scale — 50-image evaluation runs complete in under 1 minute.  
→ Decision logged in `DECISIONS.md`
