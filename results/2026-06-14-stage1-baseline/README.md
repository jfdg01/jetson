# Stage 1 — Zero-Shot Grounding Baseline & SITL Pipeline

**Pre-registered:** 2026-06-14  
**Status:** Phase A complete (2026-06-15); Phase B/C pending  
**Depends on:** VLM feasibility campaign (V1–V5, 2026-06-14); literature sweep (`literature-sweep.md`)

---

## Why this stage matters

The hardware budget is settled. What is not settled is whether any on-device VLM can ground aerial NL expressions at all in zero-shot. This is the *pivot question* for the thesis:

- If zero-shot grounding is acceptable → Stage 2 fine-tune is an incremental improvement on a working baseline.
- If both models fail to ground → the fine-tune is load-bearing, not optional, and Stages 2–3 become the thesis contribution.

Stage 1 answers that question with evidence, then stands up the modular control pipeline independently of the answer, using oracle bbox injection. The shape of the whole thesis follows from Stage 1's results.

---

## Research questions

| ID | Question | Blocks if unanswered |
|---|---|---|
| **RQ-S1.1** | Does PaliGemma-2-3B Q4_K_M load in llama.cpp commit `57fe1f0` on the Orin Nano and emit `<locXXXX>` detection tokens? What is its Hz and peak RAM? | Phase A model selection |
| **RQ-S1.2** | What is zero-shot grounding quality (parse rate, IoU@0.25, IoU@0.5) of SmolVLM-256M, SmolVLM-500M, and PaliGemma-2-3B Q4_K_M on a fixed 50-image RefDrone single-target sample? | Stage 2 design |
| **RQ-S1.3** | Does the modular pipeline (oracle bbox → ByteTrack → cascade PID → MAVLink offboard) achieve ≥1 Hz end-to-end with stable track on a slow target in SITL? | Stage 2 integration strategy |
| **RQ-S1.4** | Replacing oracle with the best zero-shot VLM from RQ-S1.2: how much does following error and track-loss increase vs oracle? | Stage 1 closed-loop baseline |

---

## Controlled variables (fixed across all experiments in this stage)

| Variable | Value |
|---|---|
| Device | Jetson Orin Nano 8 GB |
| Power mode | 15 W locked (`nvpmodel -m 0` + `jetson_clocks`) |
| Runtime | llama.cpp commit `57fe1f0`, GGUF, sm_87 |
| VLM quants | SmolVLM-256M Q8_0, SmolVLM-500M Q8_0, PaliGemma-2-3B Q4_K_M |
| Grounding dataset | RefDrone — fixed 50-image single-target sample, seed=42 |
| Tracker | ByteTrack (Kalman + IoU + low-score association) |
| Controller | Cascade PID: outer on bbox-center pixel error, inner handled by autopilot |
| MAVLink library | pymavlink, offboard velocity setpoints (body-frame vx, vy, vz, yaw_rate) |

---

## Phase 0 — Smoke tests (Day 1)

Three unknowns can silently invalidate days of downstream work. Verify these *before* writing any probe or integration code.

### 0-A: PaliGemma-2-3B llama.cpp compatibility

PaliGemma uses a non-standard multimodal architecture (SigLIP encoder + Gemma LM + `mmproj` vision projector) and a special `<loc>` token vocabulary. llama.cpp's multimodal support is the most brittle part of the stack — this must be verified on the exact commit in use.

**Procedure:**
1. Download PaliGemma-2-3B Q4_K_M GGUF + `mmproj` companion file from HF (identify correct file pair first).
2. Load via `llama-server` with `--mmproj <path>`.
3. Send one test call: `detect cat\n` with a generic image. Verify the raw response contains `<loc` tokens.
4. If successful: continue to Phase A. Record download path, file hashes, Hz, peak RAM.
5. If fails (load error, garbage output, no `<loc>` tokens): document the exact error, record as a negative result, collapse to SmolVLM-only path for Phase A. Do not invest further time in PaliGemma compatibility without a newer llama.cpp build.

**Decision gate:** PaliGemma in or out of Phase A — recorded in `DECISIONS.md`.

### 0-B: Coordinate normalization conventions

Three different conventions are in play:
- **SmolVLM output:** to be determined empirically (not a native detection model — format depends on prompting)
- **PaliGemma output:** `<locXXXX>` where each token is a 0–1023 integer encoding a y/x coordinate in `[y_min, x_min, y_max, x_max]` order on a 1024×1024 grid, normalized by image size
- **RefDrone annotations:** confirm format from the downloaded annotation files (expected: absolute pixel coordinates)

**Procedure:**
1. Download RefDrone from HF. Open one annotation file. Record exact coordinate format (absolute px, normalized 0–1, XYXY vs XYWH, top-left vs center).
2. For PaliGemma: verify the `<loc>` decoding formula (`coord / 1024 * image_dim`) on one overlaid example.
3. For SmolVLM: test two prompt formats (see Phase A) and note what coordinate space the model uses in its response.
4. Write and test coordinate-normalization unit functions *before* the bulk probe. A visual overlay on 2 images per model confirms correctness.

**Why this matters:** Wrong normalization produces IoU ≈ 0 everywhere, which is indistinguishable from genuine grounding failure without the overlay check. Record the normalization convention for each model in the Phase A results file.

### 0-C: Dataset access

**Procedure:**
1. RefDrone on HF (`sun-langwei/RefDrone` or equivalent): attempt `huggingface-cli download`. Verify images + annotation JSON are accessible without special access request.
2. UAVNLT: check the MDPI paper for a download link. If the link is dead or requires institutional access, flag it now. UAVNLT is a Phase A secondary; its absence doesn't block Phase A, only constrains Phase A's video/tracking evaluation.
3. Record access status (public / gated / unavailable) in the results file.

---

## Phase A — Zero-shot grounding probe (Days 2–4)

### Dataset preparation

- Source: RefDrone
- Sample: 50 images, randomly selected with `random.seed(42)` from the validation or test split (do not use training split to avoid data-leakage confusion)
- Filter: **single-target expressions only** — RefDrone includes multi-target (0–242 referents) and no-target cases; scoring these with a single-box output method is methodologically incorrect. Filter to expressions with exactly one annotated bbox. Record the filter count (expected ~40–80% of expressions are single-target).
- Diversity: note the class distribution in the sample (car, pedestrian, truck, etc.) for the results write-up.

### Models

| Model | Quant | Prior Hz (from V-campaign) | Prior RAM |
|---|---|---|---|
| SmolVLM-256M | Q8_0 | 3.29 Hz | 1777 MB |
| SmolVLM-500M | Q8_0 | 2.96 Hz | 2241 MB |
| PaliGemma-2-3B | Q4_K_M | **unmeasured** | **unmeasured** |

PaliGemma Hz and RAM are measured here for the first time on this device — they are currently an interpolation. Record them as RQ-S1.1 data.

### Prompting strategies

**PaliGemma:** Use the native detection prefix. The correct format is:
```
detect <referring expression>
```
No alternative formats needed — the `<locXXXX>` vocabulary is the model's trained output format.

**SmolVLM:** SmolVLM is a chat/captioning model, not a detection model. Bbox output must be elicited via prompting. Test **two** formats; pick the one with the higher parse rate for the bulk run and note the decision:

- **Format A (JSON):** `"Give the bounding box of '<expression>' as JSON {\"x1\":...,\"y1\":...,\"x2\":...,\"y2\":...} in pixel coordinates. Image size is {W}×{H}. If not present, reply null."`
- **Format B (plain coordinates):** `"Locate '<expression>' in the image. Reply with only: x1,y1,x2,y2 in pixel coordinates. If not present, reply 'none'."`

Both formats ask for **absolute pixel coordinates** matching RefDrone's GT convention (avoids a normalization conversion step). Test on 5 images each; pick the higher parse-rate format.

### Metrics

Collect the following **per model**:

| Metric | Definition |
|---|---|
| **Parse rate** | % of N=50 responses that yield a well-formed, in-bounds bbox |
| **IoU@0.25** | % of *parsed* bboxes with IoU ≥ 0.25 vs GT |
| **IoU@0.5** | % of *parsed* bboxes with IoU ≥ 0.5 vs GT |
| **Mean IoU** | Mean over parsed bboxes (excluding unparseable) |
| **Hz** | Measured on-device (for PaliGemma, first measurement; for SmolVLM, cross-check against V-campaign) |
| **Peak RAM (MB)** | From tegrastats during the probe run |

Report parse rate and IoU separately — an unparseable response and a wrong-box response are different failure modes with different fixes.

### Overlay sanity check

After the bulk run for each model, overlay predictions vs GT boxes on 5 randomly selected *parsed* responses. This is the primary defense against silent normalization bugs. If overlays look systematically offset or scaled, debug the normalization before trusting aggregate IoU numbers.

### Decision gate (end of Phase A)

The Phase A results determine which model enters the Phase C closed loop, and how load-bearing Stage 2 fine-tuning is:

| Result | Implication |
|---|---|
| PaliGemma IoU@0.25 > SmolVLM IoU@0.25 by >10 pp | PaliGemma is the accuracy ceiling; use it in Phase C and as fine-tune target for Stage 2 |
| Both models within 10 pp | SmolVLM-500M is the candidate (Hz advantage outweighs marginal grounding gap) |
| Best model IoU@0.25 < 30% | Fine-tune is load-bearing; Stage 2 is the thesis centerpiece, not Stage 1 |
| Best model parse rate < 50% | Prompt engineering or format-instruct fine-tuning needed before grounding quality is meaningful |

Document the decision in `DECISIONS.md` with the Phase A numbers as evidence.

---

## Phase B — SITL pipeline integration (Days 1–10, parallel to Phase A)

> **Prerequisite:** A working SITL environment (ArduPilot SITL + Gazebo or PX4 SITL + Gazebo). This is an explicit external dependency. If SITL is not available when Phase A completes, Phase B is the next setup milestone and Phase C is blocked until it is ready.

### Architecture

```
Camera feed (SITL Gazebo plugin or pre-recorded video)
    │
    ▼
Oracle bbox source                    (Phase B)
    │  [replaced by VLM in Phase C]
    ▼
ByteTrack                             (Kalman + IoU + low-score association)
    │  target_id → (cx, cy, w, h) at camera rate
    ▼
Cascade PID controller
  Outer loop (runs at tracker rate, ~10–25 Hz):
    error_yaw   = cx − W/2   →  yaw_rate setpoint
    error_lat   = cy − H/2   →  vy setpoint  
    error_range = A_target − A_current  →  vx setpoint
  Inner loop: autopilot (ArduPilot/PX4 attitude controller, ~50–400 Hz)
    │
    ▼
pymavlink offboard: SET_POSITION_TARGET_LOCAL_NED
  type_mask = velocity-only (vx, vy, vz, yaw_rate)
  ~20 Hz heartbeat + setpoint stream
    │
    ▼
SITL vehicle (copter)
```

The oracle source emits the GT bbox of the simulated target from the SITL world state — no VLM involved. This makes Phase B a pure systems validation: does the tracker + controller + MAVLink loop work mechanically, independent of grounding quality?

### Test scenario

- **Vehicle:** simulated quadcopter in ArduPilot/PX4 SITL + Gazebo
- **Target:** constant-velocity ground vehicle at 2 m/s (slow, unambiguous tracking scenario)
- **Duration:** 60 seconds per run, 3 runs (report mean ± std)
- **Camera:** downward-facing or forward-facing (specify and fix; note in the results)

### SITL environment setup checklist

Document each step as it is completed (these are one-time setup costs, not experimental variables):

- [ ] SITL software installed and committed to `DECISIONS.md` (ArduPilot vs PX4, version)
- [ ] Gazebo world with simulated target vehicle
- [ ] Camera plugin streaming to ROS2 topic or direct socket
- [ ] pymavlink offboard mode confirmed working (arm → takeoff → offboard hold)
- [ ] ByteTrack integrated and receiving oracle bboxes
- [ ] End-to-end loop running: oracle → tracker → PID → MAVLink → vehicle moves

### Metrics (Phase B)

| Metric | Definition | Target |
|---|---|---|
| **End-to-end loop Hz** | Rate of tracker→controller→setpoint cycle | ≥1 Hz |
| **Pixel following error** | Mean Euclidean distance (bbox center → image center), px | < 50 px (8% of 640-wide image) |
| **Track-loss events** | Count of ByteTrack ID switches on an unoccluded target | 0 |
| **Steady-state standoff** | Mean target range (m) after 10 s | within ±1 m of setpoint |

**Success threshold to proceed:** ≥1 Hz loop rate AND pixel following error < 50 px on the slow-target scenario, over all 3 runs. If the loop is slower than 1 Hz, profile to find the bottleneck (MAVLink overhead, tracker, Python GIL) before Phase C.

---

## Phase C — VLM in the loop (after Phase A + B complete)

Replace the oracle bbox source with the best-performing VLM from Phase A. This is the Stage 1 closed-loop baseline.

### Changes from Phase B

- VLM runs on the Jetson at measured Hz (2.96–3.29 Hz for SmolVLM, TBD for PaliGemma)
- VLM output is parsed and fed to ByteTrack as the re-seed box (not per-frame — tracker runs at camera rate, VLM updates at VLM rate)
- Between VLM updates, ByteTrack propagates with Kalman prediction only

### Metrics (Phase C, same scenario as Phase B)

Report the **delta vs oracle** for each metric:

| Metric | Oracle (Phase B) | VLM-in-loop (Phase C) | Delta |
|---|---|---|---|
| End-to-end loop Hz | — | — | — |
| Pixel following error | — | — | — |
| Track-loss events | — | — | — |
| VLM update rate (Hz) | n/a | measured | — |
| Grounding failures triggering re-seed errors | n/a | counted | — |

This delta is the quantified cost of the zero-shot VLM vs perfect perception — and it establishes the baseline that Stage 2 fine-tuning must beat.

---

## Deliverables

| Artifact | Location |
|---|---|
| This plan (pre-registered) | `results/2026-06-14-stage1-baseline/README.md` |
| Phase 0 smoke-test notes | `results/2026-06-14-stage1-baseline/phase-0-smoke-tests.md` |
| Phase A results | `results/2026-06-14-stage1-baseline/phase-a-grounding-probe.md` |
| Phase B results | `results/2026-06-14-stage1-baseline/phase-b-sitl.md` |
| Phase C results | `results/2026-06-14-stage1-baseline/phase-c-vlm-in-loop.md` |
| Grounding probe script | `experiments/run_grounding_probe.py` |
| Updated summary table | `RESULTS.md` (append row per model per phase) |
| Decisions logged | `DECISIONS.md` (PaliGemma compat, model selection, SITL choice) |

---

## Timeline (indicative)

| Day(s) | Work |
|---|---|
| 1 | Phase 0: PaliGemma compat smoke-test; RefDrone + UAVNLT download; coordinate conventions |
| 2–4 | Phase A: grounding probe script; bulk run on 50-image sample; overlay sanity check; decision gate |
| 1–7 | Phase B: SITL setup (can start in parallel, depends on environment availability) |
| 8–10 | Phase B: tracker + controller + MAVLink integration and validation |
| 11–12 | Phase C: VLM-in-loop; delta measurements |
| 13 | Write-up: Phase A + B + C results files; `RESULTS.md` rows; `DECISIONS.md` entries |

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| PaliGemma fails to load in current llama.cpp commit | Medium | Medium — lose one model candidate | Phase 0 catches this on Day 1; collapse to SmolVLM-only path is pre-planned |
| SmolVLM zero-shot parse rate < 50% | Medium | High — invalidates Phase C until prompt fixed | Phase A measures this explicitly; prompt format B is the fallback |
| RefDrone not publicly accessible | Low | Medium — need alternative aerial dataset | Check in Phase 0; fallback: use VisDrone with manually written expressions |
| SITL environment not available | Medium | Blocks Phase B/C | Phase A has zero SITL dependency; log as decision if SITL setup extends beyond Day 7 |
| End-to-end loop < 1 Hz in Phase B | Low | Medium — threshold not met | Profile bottleneck; likely Python GIL or MAVLink overhead, addressable without VLM changes |

---

## Caveats (pre-registered)

- PaliGemma-2-3B on-device Hz is currently an interpolation from the V-campaign data, not a measured value. Do not report the interpolated number in any thesis section; use only Phase A's measured value.
- RefDrone reports that current SOTA grounding models "perform poorly vs ground-level datasets." Expecting low zero-shot numbers is correct; do not interpret low IoU as a methodology failure.
- UAVNLT is a secondary source for this stage. Its absence blocks nothing in Phase A or B.
- The 50-image sample is deliberately small — sufficient to determine parse rate and the presence/absence of meaningful grounding signal, not sufficient for publication-grade accuracy claims. Stage 2 evaluation uses the full dataset.
