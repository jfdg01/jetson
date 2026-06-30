# Stage 2 Phase A Re-run: Grounding Probe (Fine-tuned SmolVLM-500M)

**Campaign:** Stage 2 — post-fine-tuning grounding evaluation  
**Date:** TBD (2026-06-16)  
**Script:** `runners/run_grounding_probe.py --vlm-model /home/jfdg/models/smolvlm_ft_q8_0.gguf`  
**Raw output:** `experiments/2026-06-15-stage2-finetune/raw/phase_a_rerun_stdout.log` (to be captured)

---

## RQ addressed

**RQ-S2.1**: Does LoRA fine-tuning on RefDrone improve grounding accuracy of SmolVLM-500M on the held-out val set (parse rate, IoU@0.25, pixel error)?

---

## Configuration

| Parameter | Value |
|-----------|-------|
| Model | `smolvlm_ft_q8_0.gguf` (Stage 2 fine-tuned, Q8_0) |
| mmproj | `mmproj-SmolVLM-500M-Instruct-f16.gguf` (original, reused — vision encoder frozen) |
| Quant | Q8_0 (text backbone) / f16 (vision) |
| Eval set | RefDrone val × VisDrone val, n=50, seed=42 |
| Device | Jetson Orin Nano 8GB (`ssh jetson`) |
| Power mode | MAXN_SUPER (25W), `jetson_clocks` locked |
| Baseline comparison | Stage 1 Phase A: SmolVLM-500M original Q8_0 |

---

## Results

<!-- TO FILL after run_stage2_export.py step 4 completes -->

### Baseline (Stage 1, original SmolVLM-500M Q8_0, seed=42, n=50)

*(Copy from experiments/2026-06-XX-phase-a/README.md once confirmed)*

| Metric | Baseline value |
|--------|----------------|
| Parse rate | TBD |
| IoU@0.25 (median) | TBD |
| Mean pixel error | TBD |
| TTFT (median) | TBD |

### Fine-tuned (Stage 2, smolvlm_ft_q8_0, seed=42, n=50)

| Metric | FT value | Δ vs baseline | G2 gate |
|--------|----------|---------------|---------|
| Parse rate | TBD | TBD | G1: ≥ 30% |
| IoU@0.25 (median) | TBD | TBD | G2: ≥ 20% (PASS ≥ 30%) |
| Mean pixel error | TBD | TBD | |
| TTFT (median) | TBD | TBD | |

---

## Sample outputs

<!-- TO FILL: paste 3–5 representative raw model outputs (good + bad) -->

---

## Decision gate outcomes

| Gate | Threshold | FT value | Outcome |
|------|-----------|----------|---------|
| G1: parse_rate | ≥ 30% | TBD | TBD |
| G2: IoU@0.25 | ≥ 20% (PASS ≥ 30%) | TBD | TBD |

---

## Analysis / notes

<!-- TO FILL -->
