# Jetson Orin Nano — Device Capabilities & LLM Testbed

Hardware survey of the `ssh jetson` host, captured for masters-thesis research on
running local LLMs at the edge. Probed on **2026-06-13**.

> **Note:** despite the directory name, this is **not** the original Jetson Nano
> (Maxwell GPU, 4 GB, JetPack 4.x). It is a **Jetson Orin Nano 8GB Developer Kit**
> running JetPack 6.2.2 — roughly an order of magnitude more capable.

## Project layout

The repo is a lab notebook in two parts:

- **Part I — Exploratory** (`results/`, `experiments/`, `experiments/legacy/`,
  `archive/`): device benchmark campaigns + the VLM grounding fine-tune arc (Stages
  1–4). Complete and frozen as the historical record. Legacy per-stage trainers /
  exporters live in `experiments/legacy/`; research prose in `archive/research/`.
- **Part II — Principled rebuild (v2)** (`grounding/` package, branch
  `v2/principled-rebuild`): a deliberate rebuild organised around one shared
  *contract* and a fidelity-before-GPU workflow. See `grounding/README.md`.

```
grounding/        # v2 package: contract.py (shared truth) + data/ eval/ train/ export/ deploy/ resolution.py
experiments/      # device-benchmark tooling (stdlib-only) + legacy/ (archived Part-I scripts)
archive/research/ # archived research/handoff prose
results/          # Part-I experiment writeups (one dir per campaign)
DECISIONS.md      # decision log (Part II newest-first at top; Part I below)
RESULTS.md        # results ledger (Part II appended at bottom)
```

The ledgers (`DECISIONS.md`, `RESULTS.md`) are append-only and carry a `Part II`
demarcation; Part I content is untouched.

## Connection

```bash
ssh jetson        # user: jfdg, hostname: jetson
```

## Platform summary

| Component | Value |
|---|---|
| **Board** | NVIDIA Jetson Orin Nano Developer Kit |
| **SoC** | Tegra234 (Orin) |
| **JetPack** | 6.2.2 (`nvidia-jetpack 6.2.2+b24`) |
| **L4T / BSP** | R36.5.0 (`nvidia-l4t-core 36.5.0`) |
| **Kernel** | Linux 5.15.185-tegra, aarch64 |
| **OS** | Ubuntu 22.04 (Python 3.10.12) |

## CPU

- **6× ARM Cortex-A78AE** (single cluster, 1 thread/core)
- Max clock ~1.5 GHz (default 15 W mode); min ~115 MHz

## GPU

- **NVIDIA Ampere architecture**, integrated (`Orin (nvgpu)`)
- **1024 CUDA cores + 32 Tensor cores** (3rd-gen), compute capability **8.7 (sm_87)**
- Driver 540.5.0, reports CUDA 12.6
- No dedicated VRAM — uses **unified memory shared with the CPU** (see below)

## Memory & storage

- **8 GB LPDDR5** unified (7.4 GiB visible), shared between CPU and GPU
  — this is the **primary constraint** for model sizing.
- **3.7 GiB swap** (zram, 6 devices)
- **232 GB NVMe SSD** (ADATA SWORDFISH) at `/`, ~198 GB free — root is on NVMe, fast.

## Power / thermals

- **`nvpmodel` modes available: `15W` (ID 0, default) and `7W` (ID 1)**
- `jetson_clocks` available (needs `sudo`) to lock max clocks for benchmarking
- Monitor live with `tegrastats` (CPU/GPU/mem/temps), no root needed
- ⚠️ The JetPack 6.2 **"Super" mode (25 W / MAXN_SUPER)** is *not* enabled here —
  only 7 W and 15 W modes are present. Enabling it (firmware + `nvpmodel`) would
  raise GPU clocks and LLM throughput

## Installed ML / CUDA stack

| Library | Version |
|---|---|
| CUDA Toolkit | 12.6.11 (`/usr/local/cuda` → 12.6) |
| cuDNN | 9.3.0 |
| TensorRT | 10.3.0 (incl. `python3-libnvinfer`) |
| nvcc | present at `/usr/local/cuda/bin/nvcc` (not on default PATH) |

`nvcc` is not on `$PATH` by default — you may add it:
```bash
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
```

### Not yet installed (you'll add these for the thesis)
- **No** PyTorch / Transformers / ONNX Runtime / llama.cpp / Ollama
- **No Docker** (user `jfdg` is not in the docker group; would need install)
- **No `cmake`** (have `gcc`, `git`, `python3-venv`)

---

## What LLMs can realistically run here

The hard limit is **~8 GB unified memory shared by CPU+GPU+OS**. After the OS and
desktop (~0.6–1.5 GB), budget **~6–6.5 GB** for model weights + KV cache.
Use **4-bit quantization** (GGUF `Q4_K_M`, AWQ, or TensorRT-LLM INT4) for anything ≥3B.

| Model size | Quant | Approx. weights | Fits? | Notes |
|---|---|---|---|---|
| 1–2B (Qwen2.5-1.5B, Llama-3.2-1B, Gemma-2-2B) | Q4–Q8 | 0.7–2 GB | ✅ Easy | Fast, lots of headroom for context |
| 3–4B (Phi-3-mini, Llama-3.2-3B, Qwen2.5-3B) | Q4_K_M | ~2–2.5 GB | ✅ Comfortable | Good sweet spot for Orin Nano |
| 7–8B (Llama-3.1-8B, Qwen2.5-7B, Mistral-7B) | Q4_K_M | ~4.5–5 GB | ⚠️ Tight | Works with small context; watch KV cache + swap |
| 7–8B | Q5/Q6/Q8 | 6–8.5 GB | ❌ / risky | OOM or heavy swapping |
| 13B+ | any | >7 GB | ❌ | Won't fit |

### Runtime

* We are running with llama.cpp

### Benchmarking checklist for the thesis
- Set a fixed power mode before each run: `sudo nvpmodel -m 0` (15 W) and lock clocks
  `sudo jetson_clocks`; consider enabling 25 W Super mode for a third data point.
- Log `tegrastats` during inference for power, GPU util, and thermal throttling.
- Report tokens/sec (prefill vs. decode), time-to-first-token, peak RAM, and
  power draw per model/quant — the interesting edge-LLM tradeoffs.

---

## Environment conventions (per global rules)

Python work on the Jetson should use a venv per project:
```bash
python3 -m venv .venv && source .venv/bin/activate
```
Do not `pip install` globally. Note: PyTorch for Jetson must come from NVIDIA's
prebuilt aarch64 wheels (Jetson PyPI index), **not** stock PyPI.
