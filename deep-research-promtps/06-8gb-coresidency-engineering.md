# DR-06 — Fitting a third model on an 8 GB Orin Nano: memory, thermal, and scheduling engineering

## Context (assume no prior knowledge)
My UAV perception stack already runs **two** models co-resident on a **Jetson Orin Nano 8 GB**
(15 W, `jetson_clocks`, unified 8 GB CPU/GPU memory, no MAXN on this board): a 2B VLM
(Qwen2-VL-2B, Q8_0 GGUF via llama.cpp, ~2.5–3 GB) and SAM2.1-hiera-tiny (TensorRT fp16 encoder,
~6 Hz). The next architecture step (warm-start phase 2) wants to add a **third** always-on model —
a lightweight candidate *proposer/detector* — running continuously during the idle window. On an
8 GB unified-memory board that is already near budget, this is a real systems problem: memory
pressure, thermal/power at 15 W, and scheduling three models that contend for one small GPU.

## Research question
What are the practical engineering techniques (2023–2026) for running **three concurrent deep
models on a Jetson Orin Nano 8 GB** within memory, thermal, and 15 W power limits — covering
memory budgeting on unified memory, GPU sharing/scheduling, quantization to claw back headroom,
and swap-vs-co-resident trade-offs?

## Sub-questions to cover
- **Unified-memory budgeting** on Orin Nano 8 GB: measuring real footprint (llama.cpp KV cache +
  weights, TensorRT engine workspaces), avoiding OOM, and how much is realistically free after a
  Q8 2B VLM + SAM2-tiny. What headroom does a third ~200–800 MB model need?
- **GPU sharing / scheduling** across frameworks (llama.cpp CUDA + TensorRT + PyTorch/ONNX-Runtime):
  CUDA streams, MPS availability on Jetson, priority, and avoiding one model starving another
  latency-critical one.
- **Quantization to reclaim memory**: INT4/INT8/AWQ/GPTQ for the VLM, INT8 TensorRT for the
  detector/tracker — expected memory savings and the accuracy cost (esp. for spatial grounding).
- **Co-resident vs on-demand swap**: keeping the third model warm vs loading it only in the idle
  window; model load-latency and memory-defragmentation realities on Jetson.
- **Thermal / power** at 15 W: sustained-load throttling behaviour, `tegrastats`-based budgeting,
  and how three models affect sustained clocks and FPS.

## Constraints / priorities
- Real numbers/tooling for **Orin Nano 8 GB specifically** (or closest Orin variant) preferred over
  datacenter-GPU advice.
- Must keep the tracker's few-Hz real-time loop; the proposer can be lower-rate.
- Practical, deployment-focused: profiling commands, config knobs, known pitfalls.

## Desired output
A deployment playbook: an itemised **memory budget** for VLM + SAM2 + a third model on 8 GB, a
recommended **scheduling/co-residency** scheme, quantization levers with their accuracy costs, and
the profiling tools (`tegrastats`, Nsight, jetson-stats) to verify it. Concrete Jetson-specific
gotchas called out. Citations / reference deployments where available.
