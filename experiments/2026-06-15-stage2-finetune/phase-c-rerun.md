# Stage 2 Phase C Re-run: Drone Control Loop (Fine-tuned SmolVLM-500M)

**Campaign:** Stage 2 — post-fine-tuning drone control evaluation  
**Date:** TBD (2026-06-16)  
**Script:** `runners/run_phase_c.py --vlm-model /home/jfdg/models/smolvlm_ft_q8_0.gguf`  
**Raw output:** `experiments/2026-06-15-stage2-finetune/raw/phase_c_rerun_stdout.log` (to be captured)

---

## RQ addressed

**RQ-S2.4 / G4**: Does improved grounding accuracy translate to viable drone-control loop latency and command validity with the fine-tuned model (Branch-2)?

---

## Configuration

| Parameter | Value |
|-----------|-------|
| Model | `smolvlm_ft_q8_0.gguf` (Stage 2 fine-tuned, Q8_0) |
| mmproj | `mmproj-SmolVLM-500M-Instruct-f16.gguf` (original, reused) |
| Branch | Branch-2 (VLM grounding → drone command) |
| Trials | 3 × 60s |
| Device | Jetson Orin Nano 8GB (`ssh jetson`) |
| Power mode | MAXN_SUPER (25W), `jetson_clocks` locked |
| Baseline comparison | Stage 1 Phase C Branch-2 |

---

## Stage 1 Phase C Branch-2 baseline

*(Copy from Phase C campaign doc)*

| Metric | Baseline |
|--------|----------|
| Valid-command rate | TBD |
| Mean pixel error | TBD |
| Commands/sec (throughput) | TBD |
| PASS/FAIL | FAIL (below G4 threshold) |

---

## Fine-tuned results

<!-- TO FILL after run_stage2_export.py step 5 completes -->

### Trial 1 (60s)

| Metric | Value |
|--------|-------|
| Valid-command rate | TBD |
| Mean pixel error | TBD |
| Commands/sec | TBD |

### Trial 2 (60s)

| Metric | Value |
|--------|-------|
| Valid-command rate | TBD |
| Mean pixel error | TBD |
| Commands/sec | TBD |

### Trial 3 (60s)

| Metric | Value |
|--------|-------|
| Valid-command rate | TBD |
| Mean pixel error | TBD |
| Commands/sec | TBD |

### Aggregate (median across 3 trials)

| Metric | FT value | Δ vs baseline | G4 gate |
|--------|----------|---------------|---------|
| Valid-command rate | TBD | TBD | ≥ 30% |
| Mean pixel error | TBD | TBD | < 100 px |
| Commands/sec | TBD | TBD | — |

---

## Decision gate G4 outcome

| Condition | Threshold | Value | Met? |
|-----------|-----------|-------|------|
| valid_rate ≥ 30% | 30% | TBD | TBD |
| px_err < 100px | 100px | TBD | TBD |
| **G4 overall** | BOTH conditions | — | **TBD → Branch-2 STRETCH** |

---

## Analysis / notes

<!-- TO FILL: compare latency distribution; note any parsing failures; thermal state -->
