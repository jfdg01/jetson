# Campaign: llama.cpp upper-bound throughput (Jetson Orin Nano 8GB)

**Date:** 2026-06-13T14:10
**Goal:** Establish an upper bound on LLM throughput (tok/s) and power draw on the
edge device, as a ceiling for later optimized/constrained runs.
**Operator:** automated over `ssh jetson` (user `jfdg`), passwordless sudo configured
via `/etc/sudoers.d/99-jetson-bench`.

## Device & configuration

| Item | Value |
|---|---|
| Board | NVIDIA Jetson Orin Nano Developer Kit 8 GB (module `p3767-0003`) |
| JetPack / L4T | 6.2.2+b24 / R36.5.0 |
| nvidia-l4t-nvpmodel | 36.5.0-20260115194252 |
| Power mode | **15 W (ID=0)** |
| Clocks | **Locked** via `sudo jetson_clocks` |
| Runtime | llama.cpp (CUDA), built on-device, `sm_87` |
| CUDA / cmake | 12.6 / 3.22.1 |

## ⚠️ Finding: 25 W MAXN_SUPER is NOT available without a firmware update

The active nvpmodel config (`/etc/nvpmodel.conf` →
`/etc/nvpmodel/nvpmodel_p3767_0003.conf`) defines **only two modes**:

```
< POWER_MODEL ID=0 NAME=15W >
< POWER_MODEL ID=1 NAME=7W >
```

`sudo nvpmodel -p --verbose` confirms: no `MAXN_SUPER` / 25 W profile present.

**Why it's blocked:** The JetPack 6.2 "Super" boost for the Orin Nano 8 GB requires
both an updated nvpmodel profile *and* a **bootloader/firmware update** that unlocks
the higher GPU/CPU clock ceiling. Adding a MAXN entry to the conf alone would not
deliver the boost (clocks stay capped) and risks instability.

**Decision:** Did **not** attempt the firmware/bootloader update remotely. The
operator has no physical access this session; a failed flash leaves the device
unbootable with no recovery path. **The achievable upper bound this session is
therefore 15 W with locked clocks.** Enabling true 25 W Super is deferred to a
session with physical access (see TODO).

→ This means the headline "upper bound" here is the **15 W-locked ceiling**, not the
absolute silicon ceiling. The 25 W Super run will be a separate, higher data point.

## Build

```bash
cd ~/llama.cpp
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87 -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j6
```
- `LLAMA_CURL` flag is deprecated/ignored (curl on by default). Harmless warning.
- Status: _build in progress at time of writing._
- **Decision — native build, not cross-compiled:** built on-device rather than on the
  x86_64 workstation. The Orin is aarch64; an x86_64 binary won't run there, and a
  correct CUDA cross-compile for `sm_87` needs an aarch64 cross-toolchain + target
  CUDA libs (fragile, slower to set up than the native build). llama.cpp is built
  once and reused across all models, so the build cost is one-time. Full rationale in
  [`DECISIONS.md`](../DECISIONS.md).

## Model

| Model | Quant | Source | Size |
|---|---|---|---|
| Llama-3.2-3B-Instruct | Q4_K_M | `bartowski/Llama-3.2-3B-Instruct-GGUF` (HF) | ~2.0 GB |

Chosen as the single most solid general-purpose pick (README "sweet spot": useful
model, fits comfortably in 8 GB with KV headroom). ~9 more models to follow.

## Benchmark plan

1. `llama-bench` for prefill (pp512) and decode (tg128) tok/s, multiple repeats.
2. `tegrastats --interval 1000 --logfile` over a sustained generation for power
   (idle / mean / peak W), GPU util, SoC temp, and throttle detection.
3. Derive energy efficiency: decode tok/s ÷ mean W (tok/s·W⁻¹) and J/token.

## Results

**Config:** Orin Nano 8 GB · 15 W (ID=0) · clocks **locked** (`jetson_clocks`) ·
llama.cpp `57fe1f0` CUDA `sm_87` · Llama-3.2-3B-Instruct Q4_K_M · `ngl 99` (full
GPU offload) · unified VRAM reported 7607 MiB.

### Throughput (`llama-bench`, 5 repeats)

| Test | tok/s (mean ± σ) |
|---|---|
| **Prefill** (pp512) | **570.0 ± 2.4** |
| **Decode** (tg128) | **14.61 ± 0.00** |
| Decode sustained (tg512 ×3) | 14.53 ± 0.02 |

Prefill ≈ **39×** decode — typical for memory-bandwidth-bound decode on a small
unified-memory device. Decode is the headline edge number: **~14.5 tok/s**.

### Power (`tegrastats`, VDD_IN = total board input)

| Phase | Mean | Peak | Notes |
|---|---|---|---|
| Idle | 5.24 W | 5.28 W | desktop + OS, GPU idle |
| Decode | 12.5 W | 13.6 W | window-mean deflated by model-load + inter-repeat gaps; steady-state ≈ peak |

- **Peak SoC junction temp: 66.9 °C — no thermal throttling** observed (CPU held
  1510 MHz throughout, confirming locked clocks). Plenty of thermal headroom.
- Board peak 13.6 W sits just under the 15 W class budget, as expected.

### Energy efficiency (decode — the key edge metric)

| Metric | Total board | Net of idle (Δ over 5.24 W) |
|---|---|---|
| tok/s per watt | **≈ 1.1** (14.53 / 13.6) | ≈ 1.7 (14.53 / 8.34) |
| Energy per token | **≈ 0.94 J/tok** | ≈ 0.57 J/tok |

(Using steady-state decode power ≈ 13.6 W. "Net of idle" isolates the marginal cost
of inference above the always-on platform draw.)

### Interpretation

This is the **15 W-locked upper bound**, not the silicon ceiling — 25 W MAXN_SUPER
(deferred, see Decisions) would raise both throughput and power. As a ceiling for
later optimized/constrained runs: a useful 3B model sustains **~14.5 tok/s** (faster
than human reading) at **~13.6 W**, well within thermal limits. Prefill is abundant
(570 tok/s), so long prompts are cheap; **decode bandwidth is the binding
constraint**, as expected for edge.

Raw logs: `results/raw/2026-06-13_tegra_idle.log`,
`results/raw/2026-06-13_tegra_decode.log`, `results/raw/2026-06-13_llama_build.log`.

## TODO / follow-ups

- [ ] Enable 25 W MAXN_SUPER (firmware + nvpmodel) **with physical access**; re-run
      as a higher upper-bound data point.
- [ ] 7 W mode run for the low-power end of the tradeoff curve.
- [ ] Remaining ~9 models.
