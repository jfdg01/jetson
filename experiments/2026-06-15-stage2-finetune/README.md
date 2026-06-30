# Stage 2 — Fine-tuning SmolVLM-500M for Aerial Grounding

**Pre-registered:** 2026-06-15  
**Campaign status:** SETUP

---

## Motivation

Stage 1 Phase A established that SmolVLM-500M-Instruct Q8_0 achieves 0% IoU@0.25 and 4%
parse rate on VisDrone nadir frames zero-shot. Phase C confirmed this failure persists in
closed-loop: VLM valid rate 12.5%, mean pixel error 190 px (vs 89 px oracle ceiling).
Stage 2 tests whether supervised fine-tuning on aerial grounding data closes this gap
enough to make the system useful in the Phase C control loop.

This is the thesis centerpiece: the question is not whether fine-tuning helps (it does),
but **by how much, at what inference cost, and whether the gains survive GGUF quantization
to Q8_0**.

---

## Research questions

| ID | Question | Pass criterion | Measuring instrument |
|----|----------|---------------|---------------------|
| **RQ-S2.1** | Does fine-tuning SmolVLM-500M on RefDrone + VisDrone aerial data produce a model with IoU@0.25 ≥ 30% on the Phase A probe set? | IoU@0.25 ≥ 30% on Phase A probe | re-run `run_grounding_probe.py` with FT model |
| **RQ-S2.2** | Does the fine-tuned model parse a valid bounding box in ≥ 50% of Phase A probe calls? | parse_rate ≥ 50% | re-run `run_grounding_probe.py` with FT model |
| **RQ-S2.3** | Does fine-tuning survive GGUF Q8_0 quantization without a measurable accuracy drop? | ΔIoU@0.25 ≤ 5pp between HF and GGUF Q8_0 | compare HF eval vs GGUF eval on same probe set |
| **RQ-S2.4** | Does the fine-tuned model raise Phase C Branch-2 valid_rate to ≥ 30% AND px_err < 100? | valid_rate ≥ 30% AND mean px_err < 100 (Branch-2 stretch) | re-run `run_phase_c.py --vlm-model <FT>` |
| **RQ-S2.5** | Does inference speed remain within the 0.5–2 Hz target on the Jetson after fine-tuning? | VLM call rate ≥ 0.5 Hz on Jetson Orin Nano 8 GB | tegrastats + wall-clock in Phase C run |

---

## Datasets

### Primary: RefDrone (sunzc-sunny/RefDrone)
- HuggingFace repo: `sunzc-sunny/RefDrone` (CC-BY-4.0)
- Annotations: referring-expression grounding on aerial drone frames; bounding boxes for
  specific objects identified by NL referring expressions
- **Note:** RefDrone annotations do NOT bundle images — VisDrone 2019-DET images must be
  downloaded separately and matched by filename (see §Download below)
- Schema: `{"image": "<filename>", "sentence": "<referring expression>", "bbox": [x,y,w,h]}`
  (check actual HF schema after download; format inferred from paper)

### Secondary: VisDrone 2019-DET
- Source: http://aiskyeye.com/ (the official VisDrone dataset page)
- Alternative mirror: HuggingFace `daverkaz/VisDrone2019` (verify license before use)
- Used as the image source for RefDrone annotation filenames
- We use the `train` split for fine-tuning and `val` split for eval

### Prompt format (pre-registered)
```
<image>
Locate the <referring expression> in this aerial image. Return the bounding box as JSON: {"bbox": [x1, y1, x2, y2]} where coordinates are in pixels (0–width, 0–height).
```
Response target: `{"bbox": [x1, y1, x2, y2]}`

This format was chosen to match the JSON parse path already implemented in
`runners/run_grounding_probe.py` and `run_phase_c.py`.

---

## Method

### Model
- Base: `HuggingFace Hub: HuggingFaceTB/SmolVLM-500M-Instruct` (same checkpoint as Stage 1)
- Fine-tuning method: **LoRA** (PEFT), applied to attention projection layers
- LoRA rank r=16, alpha=32, dropout=0.05
- Target modules: `q_proj, v_proj` (standard for vision-language models; adjust if HF
  SmolVLM uses different attention module names)

### Training hardware
- **Local machine**: NVIDIA RTX 3090 24 GB VRAM (Ubuntu 24.04, CUDA 12.x)
- Batch size: 4 (effective 16 with gradient accumulation × 4)
- Max epochs: 3 (or until eval IoU plateaus)
- Max input image size: 512×512 (SmolVLM default; RefDrone images are 1920×1080 → resize)
- Optimizer: AdamW lr=2e-4, cosine schedule with 5% warmup

### GGUF export pipeline
1. Merge LoRA adapter into base weights: `peft.PeftModel.merge_and_unload()`
2. Save merged checkpoint to disk (HF format)
3. SCP merged checkpoint to Jetson (`~/smolvlm_ft/`)
4. On Jetson: `python ~/llama.cpp/convert_hf_to_gguf.py --outtype q8_0 ~/smolvlm_ft/ --outfile ~/smolvlm_ft_q8_0.gguf`
   - llama.cpp commit: `57fe1f0` (the controlled-variable commit used in Stage 1)
5. Verify load: `~/llama.cpp/llama-cli --model ~/smolvlm_ft_q8_0.gguf --image <test.jpg> -p "..."` (sanity check only)
6. Run Phase A probe: `python runners/run_grounding_probe.py --vlm-model ~/smolvlm_ft_q8_0.gguf`

---

## Decision gates

| Gate | After | Condition | Action if fail |
|------|-------|-----------|----------------|
| **G1: Parse rate** | Phase A re-run | parse_rate ≥ 30% on probe | Check prompt format; try 1 more epoch; if still < 30%, report as negative result |
| **G2: IoU** | Phase A re-run | IoU@0.25 ≥ 20% (relaxed floor; pass = ≥30%) | Report partial improvement; log delta from baseline |
| **G3: GGUF parity** | GGUF eval | ΔIoU@0.25 ≤ 5pp | Try Q4_K_M if Q8_0 shows ≥ 5pp drop; document quant sensitivity |
| **G4: Phase C** | Phase C re-run | valid_rate ≥ 30% AND px_err < 100 | Phase C "stretch" outcome; negative = still thesis-valid result |

---

## Controlled variables (held constant from Stage 1)

| Variable | Value |
|----------|-------|
| Jetson hardware | Orin Nano 8 GB, power mode MAXN_SUPER (25 W), jetson_clocks locked |
| llama.cpp commit | `57fe1f0` |
| Quantization | Q8_0 |
| Phase A probe set | Same VisDrone frames as Stage 1 (`experiments/2026-06-14-stage1-baseline/raw/grounding_probe_*.jpg`) |
| Phase C world | `runners/sitl/worlds/phase_c.sdf` (unchanged) |
| Phase C prompt | `"Locate the rover in this aerial image. Return JSON: {\"bbox\": [x1,y1,x2,y2]}"` (unchanged) |

---

## Download checklist

- [ ] `sunzc-sunny/RefDrone` via `huggingface-hub` (or `datasets.load_dataset`)
- [ ] VisDrone 2019-DET train/val images (aiskyeye.com or HF mirror)
- [ ] `HuggingFaceTB/SmolVLM-500M-Instruct` base checkpoint (for fine-tuning)
- [ ] Verify image filename correspondence between RefDrone annotations and VisDrone images

---

## Software checklist

- [ ] Local venv `.venv-ft` with: `torch`, `transformers`, `peft`, `datasets`, `accelerate`, `pillow`, `scipy`
- [ ] `runners/run_stage2_finetune.py` — training loop
- [ ] `runners/eval_ft_grounding.py` — HF-checkpoint evaluation (before GGUF conversion)
- [ ] Jetson: `convert_hf_to_gguf.py` already present at `~/llama.cpp/` (commit `57fe1f0`)

---

## Output files (pre-registered locations)

| File | Contents |
|------|----------|
| `experiments/2026-06-15-stage2-finetune/train-log.md` | Per-epoch loss + eval IoU, training time, GPU memory |
| `experiments/2026-06-15-stage2-finetune/phase-a-rerun.md` | Phase A grounding probe results with FT model |
| `experiments/2026-06-15-stage2-finetune/phase-c-rerun.md` | Phase C Branch-2 re-run with FT model |
| `experiments/2026-06-15-stage2-finetune/raw/train_loss.csv` | Raw loss curve |
| `experiments/2026-06-15-stage2-finetune/raw/eval_iou.csv` | Per-sample IoU on val set |
| `RESULTS.md` | Appended rows: Phase A FT, Phase C FT |

---

## Risk register

| Risk | Probability | Mitigation |
|------|------------|------------|
| RefDrone image/annotation filename mismatch after VisDrone download | Medium | Write a filename-matching script before training; abort if > 10% mismatch |
| GGUF conversion fails for fine-tuned weights (LoRA-merged checkpoint has non-standard keys) | Low-medium | Test round-trip with BASE model first; document if fine-tuned checkpoint needs key remapping |
| RTX 3090 OOM at batch_size=4 | Low | Reduce to batch_size=2 + gradient accumulation × 8; or use gradient checkpointing |
| Fine-tuned model overfits RefDrone; Phase A probe IoU near 0 on different VisDrone frames | Medium | Evaluate on held-out VisDrone val split; add data augmentation (flip, color jitter) |
| SmolVLM-500M attention module names differ from standard `q_proj/v_proj` | Low | Print model named_modules before training; adjust `target_modules` accordingly |
