# Research Prompt: VLA for Drone Control — Academic Survey

**Purpose:** Feed this prompt into a deep-research LLM (Claude Opus with extended thinking,
or Perplexity Deep Research) to survey the academic landscape before designing the
fine-tuning pipeline. The hardware context section below is drawn from measured results
on the target device — include it verbatim so the model can reason about what is and
isn't feasible on this platform.

---

## Hardware Context (measured, not estimated)

**Device:** NVIDIA Jetson Orin Nano 8 GB  
**Runtime:** llama.cpp commit `57fe1f0`, CUDA `sm_87`, `llama-server` + Python urllib client  
**Power mode for all measurements:** 15 W locked (`nvpmodel -m 0` + `jetson_clocks`)  
**Total memory budget:** 7607 MB (unified CPU/GPU)  
**Practical model ceiling:** ~6.4 GB resident — the 12B Gemma-3 hard-OOM'd at load (`cudaMalloc` failed allocating 7694 MiB); models above this limit are non-starters without aggressive partial offload.

### Text-only throughput (llama-bench, tg128, locked clocks)

| Model | Quant | Params | tg128 tok/s | Peak RAM MB | Mean W | J/tok |
|---|---|---|---|---|---|---|
| Gemma-3-270M-it | Q8_0 | 0.27 B | 104.4 | 2458 | ~8 | 0.104 |
| Qwen2.5-0.5B-Instruct | Q4_K_M | 0.5 B | 71.5 | 2637 | 6.6 | 0.157 |
| Llama-3.2-1B-Instruct | Q4_K_M | 1.0 B | 35.1 | 3497 | 8.4 | 0.380 |
| Gemma-4-E2B-it (MoE) | Q4_0 QAT | 5.1 B | 20.4 | 2968 | 11.9 | 0.584 |
| Gemma-3-4B-it | Q4_0 QAT | 4.0 B | 12.2 | 4617 | 12.7 | 1.043 |
| Phi-3.5-mini-instruct | Q4_K_M | 3.8 B | 13.2 | 4693 | 12.5 | 0.995 |
| Gemma-4-E4B-it (MoE) | Q4_0 QAT | 8.0 B | 11.4 | 4374 | 12.7 | 1.110 |
| Mistral-7B-Instruct-v0.3 | Q4_K_M | 7.2 B | 8.4 | 5488 | 12.5 | 1.639 |
| Qwen2.5-7B-Instruct | Q4_K_M | 7.6 B | 7.9 | 5465 | 11.9 | 1.749 |
| Meta-Llama-3.1-8B-Instruct | Q4_K_M | 8.0 B | 7.8 | 5953 | 12.0 | 1.795 |

**Notable:** Gemma-4 uses a Mixture-of-Experts (MoE/PLE) architecture. E2B (5.1B total, ~2B active) achieves 20.4 tok/s — faster than Gemma-3-4B (12.2 tok/s) at similar quality, and uses only 2968 MB RAM (MoE shared matrices partially demand-paged). This is the most efficient large-model option on this hardware.

### VLM throughput (llama-server, warm inference, N=5 frames, locked clocks)

`per_frame_ms = prompt_ms + predicted_ms` (verified: CLIP encode is included inside `prompt_ms`; wall-clock residual ≤10 ms).

| Unit | Model | Params | Vision encoder | img tokens | per_frame_ms (median ± σ) | Hz | Peak RAM MB | Mean W | Notes |
|---|---|---|---|---|---|---|---|---|---|
| V1 | SmolVLM-256M-Instruct Q8_0 | 0.26 B | SigLIP-400M | 64 (fixed) | **304 ± 65 ms** | **3.29** | 1777 | 6.6 | Resolution-agnostic; no swap |
| V2 | SmolVLM-500M-Instruct Q8_0 | 0.50 B | SigLIP-400M | 64 (fixed) | **338 ± 148 ms** | **2.96** | 2241 | 7.2 | Resolution-agnostic; no swap |
| V3 | Gemma-3-4B-it q4_0 | 4.0 B | SigLIP | 256 | **9576 ± 98 ms** | **0.10** | 6414 | 9.7 | Swap hit; 6414 MB > comfortable threshold |
| V4 | Gemma-4-E2B-it q4_0 QAT | 5.1 B | SigLIP Matryoshka | 144 | **2035 ± 611 ms** | **0.49** | 4616 | 8.2 | `--reasoning off`; canonical result |
| V5 | Gemma-4-E4B-it q4_0 QAT | 8.0 B | SigLIP Matryoshka | 144 | **2963 ± 576 ms** | **0.34** | 6444 | 8.8 | `--reasoning off`; swap at 6444 MB |

**Key findings from VLM campaign:**
- SmolVLM-256M/500M comfortably clear the 2 Hz drone control rate target (3.29 / 2.96 Hz).
- Gemma-4-E2B (V4) is the largest model that fits comfortably in memory (4616 MB) while clearing 0.5 Hz — usable with command-rate decimation (VLM updates 2×/sec, drone autopilot holds track between frames).
- Gemma-3-4B (V3) is memory-pressured (swap) and an order of magnitude slower (0.10 Hz) — not viable for real-time use without architectural changes.
- Gemma-4 thinking/reasoning mode consumed all tokens in chain-of-thought; `--reasoning off` is mandatory for latency-sensitive drone applications.
- CUDA graph compilation adds ~180 ms cold-start penalty on first frame after load.
- SmolVLM uses fixed 64 image tokens regardless of input resolution (no tiling). Gemma uses adaptive tiling (144–256 tokens depending on image size).

### Practical constraints for the drone pipeline

- **Minimum viable loop rate:** 0.5–2 Hz is sufficient for high-level re-targeting; drone autopilot holds track between VLM updates.
- **Two viable operating points:**
  - **Fast / lightweight:** SmolVLM-256M @ 3.29 Hz, 1777 MB, 6.6 W — leaves 5.8 GB free for OS + tracker.
  - **Capable / moderate:** Gemma-4-E2B @ 0.49 Hz, 4616 MB, 8.2 W — much stronger grounding; memory permits a YOLO detector to co-run if needed.
- **Hard ceiling:** 7607 MB total; no model with >6.4 GB resident footprint will load. 12B models are out. 8B models (V5) work but cause swap.
- **Power envelope:** 6.6–9.7 W during VLM inference; Orin Nano TDP is 15 W, leaving 5–8 W for flight controller, camera, comms.

---

## Research Prompt

I'm building a master's thesis system: **natural language commanded drone object following**, running end-to-end on a Jetson Orin Nano 8 GB. The hardware capabilities are documented above — treat those numbers as ground truth when assessing feasibility.

The system concept: a drone camera sends frames to the Orin Nano. A user issues a natural language command ("follow the white car"). The on-device model processes each frame + the command and produces a structured output (e.g. a bounding box or directional command) that feeds a flight controller. The VLM runs at 0.5–3 Hz; the drone autopilot holds track between updates.

Please survey the academic literature and produce a structured research brief. For each paper or system cited, include: title, authors, year, venue, and the specific takeaway for this use case.

---

### 1. Vision-Language-Action (VLA) models for robotics

- What are the landmark papers? (RT-2, OpenVLA, π0, PaliGemma-based VLAs, octo, etc.)
- How do they map vision + language → actions? What action representations are used (continuous joint angles, discrete tokens, velocity commands)?
- Which have been tested on UAVs/drones specifically vs. ground robots?
- What is the smallest/most efficient VLA demonstrated? What were its latency and hardware requirements?
- Is there a GGUF-exportable or llama.cpp-compatible VLA checkpoint?

### 2. Natural language grounding in aerial / drone imagery

- Papers on NL-commanded object detection or tracking from UAV viewpoints.
- What aerial-specific datasets exist with NL annotations?
- What makes aerial imagery hard for VLMs trained on ground-level data? (scale variance, top-down perspective, small objects, motion blur, lack of context)
- Any work on "refer and follow" — NL referent expression → track that object?

### 3. Visual object tracking (VOT) + language on drones

- NL-specified single-object tracking: papers combining a tracker (SORT, DeepSORT, ByteTrack, SiamFC, OSTrack) with a language front-end to select the initial target.
- End-to-end learned vs. modular (VLM grounding → classical tracker): which performs better, what are the tradeoffs?
- State-of-the-art methods and numbers on UAV tracking benchmarks: UAV123, VisDrone, UAVDT, DTB70.
- Minimum viable tracker footprint — what is the lightest tracker that achieves competitive accuracy?

### 4. Edge deployment of VLMs for real-time robotics

- Papers or systems deploying small VLMs (<1B params) on embedded/edge hardware for robotics perception.
- Any work specifically on Jetson platforms for vision-language tasks?
- Reported latency/throughput numbers for drone-relevant tasks. How do they compare to the measurements above?
- Quantization strategies (GGUF, AWQ, GPTQ, QAT) used in robotics contexts and their accuracy/speed tradeoffs.

### 5. Fine-tuning small VLMs for structured grounded output

- Papers on fine-tuning SmolVLM, LLaVA-style models, PaliGemma, or Idefics for structured output (bounding boxes, referring expressions, grounding JSON).
- What dataset formats and training recipes work for teaching bbox output from NL descriptions?
- QLoRA / LoRA for VLMs: efficiency numbers, quality vs. full fine-tune tradeoffs.
- Any work using VisDrone, UAVDT, or aerial datasets as fine-tuning sources?
- GGUF export after LoRA merge: any known issues or best practices?

### 6. Datasets

- What are the best available datasets for (drone image, NL command, bbox) triplets?
- Is there a dataset where NL descriptions select objects in aerial imagery? If not, what is the closest proxy?
- How have papers handled the absence of NL annotations — auto-labeling with large VLMs, template generation, crowdsourcing?
- Key dataset stats: size, image resolution, object classes, annotation format, license.
- Relevant: VisDrone2019-DET, UAVDT, UAV123, NL-SOT (Natural Language Single Object Tracking), TNL2K, LaSOT.

### 7. System architecture patterns

- What are the dominant pipeline architectures for NL-commanded drone following?
  - Modular: NL parser → detector/grounder → tracker → controller
  - End-to-end learned: image + NL → action tokens
- How do papers handle the control interface? (MAVLink, ROS/ROS2, PX4, ArduPilot, discrete action tokens, continuous velocity commands)
- What controllers are used between perception output and actuation? (PID, MPC, learned policy, cascade)
- How is the object re-identification problem (target lost after occlusion) handled?

### 8. Open problems and honest failure modes

- What does the literature identify as unsolved in NL-commanded drone following?
- Where do current systems break? (re-ID after occlusion, ambiguous NL descriptions, sim-to-real gap, latency, OOD aerial viewpoints, adversarial backgrounds)
- What assumptions do most papers make that may not hold in real outdoor deployment?
- Be honest about sparseness — if a specific area has few papers, say so.

### 9. What I can reuse directly

Based on all of the above, give concrete recommendations:

1. **Starting checkpoint for fine-tuning:** which model is the best base for a grounding fine-tune targeting the Orin Nano hardware profile above? Must be GGUF-exportable.
2. **Dataset:** which dataset(s) to use for fine-tuning, with what preprocessing/augmentation?
3. **Auto-labeling strategy:** if no suitable annotated dataset exists, what is the best recipe for generating (image, NL command, bbox) triplets from an unlabeled aerial dataset?
4. **Downstream tracker:** which tracker should sit below the VLM output, and why? What is its memory footprint?
5. **Controller pattern:** what is the most appropriate controller for a "follow target" task given ~0.5–3 Hz VLM update rate?
6. **Evaluation metrics:** what metrics should I report to satisfy a thesis committee? (tracking accuracy, latency, power, end-to-end following error?)
7. **Related work positioning:** given the above, where is the gap that this thesis fills?

Be specific and cite papers. Where a claim is uncertain or the field is sparse, say so plainly. An honest picture of what is and isn't solved is more valuable than an inflated survey.
