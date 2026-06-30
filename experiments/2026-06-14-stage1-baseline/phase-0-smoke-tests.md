# Phase 0 — Smoke Tests

**Campaign:** Stage 1 Zero-Shot Grounding Baseline  
**Date started:** 2026-06-14  
**Status:** ✅ Complete — all blocking items verified 2026-06-15; only 0-A device smoke test remains (non-blocking, confirming known negative)

---

## 0-A: PaliGemma-2-3B llama.cpp compatibility

**Purpose:** Verify PaliGemma-2-3B Q4_K_M loads in llama.cpp commit `57fe1f0` and emits `<loc>` detection tokens.

### Pre-check findings (local research, 2026-06-14)

**Finding 1 — No PaliGemma 2 GGUF exists.**  
The plan specified "PaliGemma-2-3B Q4_K_M." A HuggingFace search found no community GGUF conversion of PaliGemma 2. The only available GGUF is `abetlen/paligemma-3b-mix-224-gguf`, which converts PaliGemma v1 (`google/paligemma-3b-mix-224`), not PaliGemma 2 (`google/paligemma2-3b-mix-224`). The PaliGemma 2 mix model exists in HF Transformers / JAX only — no GGUF quantization has been published.

**Finding 2 — PaliGemma support is NOT merged in the llama.cpp baseline commit.**  
PaliGemma support in llama.cpp lives in PR #7553 (`ggml-org/llama.cpp`, opened by abetlen). As of 2026-06-14, this PR remains **open and unmerged** — a draft with the last commit in October 2024. The maintainer (ggerganov) indicated in October 2024 that merging may wait for a new vision-API initiative (issue #9687). Commit `57fe1f0` (the controlled variable for this thesis) does not include PR #7553 and therefore has no PaliGemma architecture support.

**Consequence:** Neither PaliGemma v1 nor v2 can be loaded by `llama-server` at commit `57fe1f0`. The device smoke test is expected to fail at load time with an "unsupported architecture" or similar error.

**Available PaliGemma v1 GGUF file pair (if a future build supports it):**

| File | Repo | Size |
|---|---|---|
| `paligemma-3b-mix-224-text-model-q4_k_m.gguf` | `abetlen/paligemma-3b-mix-224-gguf` | 1.63 GB |
| `paligemma-3b-mix-224-mmproj-f16.gguf` | `abetlen/paligemma-3b-mix-224-gguf` | ~861 MB |

Note: even if a compatible llama.cpp build were used, this would be PaliGemma v1, not v2.

### Device verification (TODO — run on Jetson)

Even with the above findings, the device test should be attempted and the exact error documented for the thesis record. It also confirms the baseline commit's multimodal capabilities (SmolVLM works there; PaliGemma may not).

**Commands to run on Jetson:**
```bash
# Attempt to download PaliGemma v1 GGUF
cd ~/models
wget -c "https://huggingface.co/abetlen/paligemma-3b-mix-224-gguf/resolve/main/paligemma-3b-mix-224-text-model-q4_k_m.gguf?download=true" \
     -O paligemma-3b-mix-224-text-model-q4_k_m.gguf
wget -c "https://huggingface.co/abetlen/paligemma-3b-mix-224-gguf/resolve/main/paligemma-3b-mix-224-mmproj-f16.gguf?download=true" \
     -O paligemma-3b-mix-224-mmproj-f16.gguf

# Load attempt
~/llama.cpp/build/bin/llama-server \
  -m ~/models/paligemma-3b-mix-224-text-model-q4_k_m.gguf \
  --mmproj ~/models/paligemma-3b-mix-224-mmproj-f16.gguf \
  -ngl 99 --port 8080
```

**Expected result:** Load failure (unsupported architecture or GGUF format error) at commit `57fe1f0`.

**Result to record here:** *(fill in after device run)*

| Field | Value |
|---|---|
| Date/time (UTC) | |
| llama.cpp commit | `57fe1f0` |
| Error message | |
| Decision gate | PaliGemma OUT — SmolVLM-only path |

### Decision

PaliGemma is excluded from Stage 1 per the pre-planned risk-register mitigation. This is documented in `DECISIONS.md` (entry 2026-06-14). SmolVLM-256M Q8_0 and SmolVLM-500M Q8_0 are the two grounding candidates for Phase A.

---

## 0-B: Coordinate normalization conventions

**Purpose:** Establish ground-truth coordinate format for RefDrone and SmolVLM prompt output before writing any IoU-computing code.

### RefDrone annotation format

**Source:** `sunzc-sunny/RefDrone` HF dataset (correct repo ID per 0-C). Annotations at `/home/gara/refdrone-annotations/RefDrone_val_mdetr.json`.

**Verified 2026-06-15** by inspecting the annotation JSON directly.

| Field | Reported | Verified |
|---|---|---|
| Format | XYWH | **XYWH — confirmed** |
| Coordinate space | Absolute pixels | **Absolute pixels — confirmed** |
| Origin | Top-left | **Top-left — confirmed** |
| Axis order | x_left, y_top, width, height | **x, y, w, h — confirmed** |

**Key structural finding:** RefDrone MDETR format uses one entry per (image, expression) pair in `d["images"]`, not one entry per unique file. The same physical image file appears multiple times with different captions and image IDs. This is intentional — each entry represents a distinct (image, NL expression, bbox) triplet.

**Val split statistics:**
- 1428 total image entries (unique `image_id`s) across 534 unique physical files
- 4741 total annotations
- 446 image_ids with exactly 1 annotation → single-target candidates
- **7 of those 446 have `bbox=[0,0,0,0]`** — no-target entries where the expression has no visible referent in the frame. These must be excluded (zero area ≠ "grounding failed"; they would produce IoU=0 for any non-null prediction, contaminating the parse-rate/IoU split). **`run_grounding_probe.py` updated (2026-06-15) to skip zero-dimension bboxes.**
- Valid single-target pool: **439 items** — well above N=50 sample size

**Expression location:** Stored in `d["images"][i]["caption"]`, not in the annotation record. The script's `img_info.get("caption")` lookup is correct.

**Overlay sanity check (sample of 3):**
- `0000291_01001_d_0000873.jpg` (1360×765): bbox [598,387,180,179] → x2=778, y2=566 — green bus at image center. ✓
- `0000249_02468_d_0000008.jpg` (960×540): bbox [354,459,51,56] → small car at bottom-center. ✓
- `0000103_01734_d_0000028.jpg` (1360×765): bbox [523,380,151,385] → pedestrian (tall box). ✓

All coordinates are within image bounds and aspect-ratio-plausible. **Normalization is not needed** — the GT bboxes and SmolVLM prompts both request absolute pixel coordinates, so no conversion step is needed at IoU computation time.

### SmolVLM output format

SmolVLM is a captioning/chat model; bbox output depends entirely on the prompt format. Two formats will be tested in Phase A (see README §Phase A — Prompting strategies). The coordinate convention from the model's response depends on the prompt — both format A (JSON absolute px) and format B (csv absolute px) request absolute pixel coordinates matching RefDrone's convention.

**Actions before Phase A:**
- Test format A and B on 5 images each.
- Verify that the model actually respects the "pixel coordinates" instruction vs hallucinating normalized coords.
- Write `parse_bbox_response()` unit functions after format is confirmed.

### PaliGemma

Not applicable — excluded at 0-A.

---

## 0-C: Dataset access

**Purpose:** Confirm images + annotations for RefDrone are downloadable; flag UAVNLT status.

### RefDrone

**Finding — Wrong repo ID in the plan.**  
The Stage 1 README specified `sun-langwei/RefDrone`. A direct HF fetch of that URL returned **HTTP 401 Unauthorized**. The correct repo is `sunzc-sunny/RefDrone` — confirmed via the GitHub project page at `github.com/sunzc-sunny/refdrone` which links to it explicitly.

| Field | Planned | Corrected |
|---|---|---|
| HF dataset repo | `sun-langwei/RefDrone` | **`sunzc-sunny/RefDrone`** |
| Access | Unknown | CC-BY-4.0, appears public |
| Images included? | Assumed yes | **No — images from VisDrone, downloaded separately** |
| Annotations | MDETR JSON | `RefDrone_{train,val,test}_mdetr.json` |

**Important:** RefDrone annotations reference VisDrone images. The VisDrone 2019-DET images must be downloaded separately. Both sources are needed for Phase A.

**Access result (verified 2026-06-15):**

| Dataset | Access status | Notes |
|---|---|---|
| `sunzc-sunny/RefDrone` (annotations) | **Downloaded — `/home/gara/refdrone-annotations/`** | CC-BY-4.0, public, no HF login needed |
| VisDrone 2019-DET-val (images) | **Downloaded — `/home/gara/visdrone-dataset/VisDrone2019-DET-val/images/`** | 1428/1428 images found (100% match) |

Filename convention matches: RefDrone annotation `file_name` values (e.g. `0000291_01001_d_0000873.jpg`) correspond directly to filenames in the VisDrone val `images/` subdirectory. No path manipulation needed — pass `--visdrone-images /home/gara/visdrone-dataset/VisDrone2019-DET-val/images` to the probe script.

### UAVNLT

Phase A secondary; its absence does not block Phase A. Status check deferred until RefDrone is confirmed accessible. If needed: check the MDPI paper for the download link.

**Access result:** *(to check if needed)*

---

## Summary / next actions

| Check | Status | Blocker? |
|---|---|---|
| 0-A: PaliGemma compat (research) | ✗ **Will fail** — PR #7553 not merged in `57fe1f0` | No — SmolVLM-only path pre-planned |
| 0-A: Device smoke test | ⏳ Pending (user must run on Jetson to confirm error message) | No — confirming known negative |
| 0-B: RefDrone annotation format | ✅ **Verified 2026-06-15** — XYWH absolute pixels, caption in image record, 7 no-target entries filtered | Complete |
| 0-C: RefDrone download | ✅ **Done** — `/home/gara/refdrone-annotations/` (CC-BY-4.0) | Complete |
| 0-C: VisDrone images | ✅ **Done** — `/home/gara/visdrone-dataset/VisDrone2019-DET-val/images/`, 1428/1428 present | Complete |
| 0-C: UAVNLT | Not started | No — Phase A secondary |

**Phase A is unblocked.** Dataset is verified and present locally; probe script is ready. The only remaining Phase 0 item is the device-side PaliGemma smoke test (0-A), which is optional (confirming a known negative) and does not block Phase A.

**To launch Phase A (once Jetson clocks are locked):**
```bash
source .venv/bin/activate
python runners/run_grounding_probe.py \
    --refdrone-ann /home/gara/refdrone-annotations/RefDrone_val_mdetr.json \
    --visdrone-images /home/gara/visdrone-dataset/VisDrone2019-DET-val/images \
    --skip-download

# Dry-run first to verify command strings:
python runners/run_grounding_probe.py \
    --refdrone-ann /home/gara/refdrone-annotations/RefDrone_val_mdetr.json \
    --visdrone-images /home/gara/visdrone-dataset/VisDrone2019-DET-val/images \
    --dry-run
```
