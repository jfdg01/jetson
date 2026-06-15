---
name: run-jetson
description: Run, verify, and drive the Jetson edge-LLM thesis experiment pipeline. Use when asked to start an experiment, run a campaign, run a sweep, test parsers, verify the pipeline, screenshot results, or interact with the running experiment scripts.
---

**Start every session by invoking `/remote-control` before doing anything else.** This connects the session to the remote-control bus so the operator can observe and intervene.

This is the Jetson Orin Nano edge-LLM thesis experiment pipeline. It is driven by Python scripts in `experiments/` that SSH into the device, run `llama-bench`, and append structured results to `results/` and `RESULTS.md`. The smoke harness is `.claude/skills/run-jetson/smoke.sh`.

All paths are relative to the repo root (`/home/gara/jetson/`).

## Prerequisites

Python venv at repo root (already created):

```bash
source .venv/bin/activate
```

SSH access to the Jetson device:

```bash
ssh jetson   # must succeed; device alias configured in ~/.ssh/config
```

Power mode and clocks must be set before any real benchmark run (requires interactive sudo on the device — ask the user):

```bash
ssh jetson 'sudo nvpmodel -m 0 && sudo jetson_clocks'
```

## Run (agent path)

**Verify the pipeline is intact:**

```bash
bash .claude/skills/run-jetson/smoke.sh
```

Expected output ends with `=== smoke PASSED ===`.

**Dry-run any campaign to preview commands without touching the device:**

```bash
source .venv/bin/activate

# 10-model capability sweep
python experiments/run_campaign.py --dry-run

# Gemma-family sweep
python experiments/run_gemma_sweep.py --dry-run

# VLM feasibility campaign
python experiments/run_vlm_campaign.py --dry-run
```

**Run a specific subset of units (comma-separated IDs):**

```bash
python experiments/run_campaign.py --only 01,03
python experiments/run_gemma_sweep.py --only G1,G2
python experiments/run_vlm_campaign.py --only V1
```

**Resume a campaign from a unit (skips earlier ones):**

```bash
python experiments/run_campaign.py --start-from 05
```

**Skip model downloads (models already on device):**

```bash
python experiments/run_campaign.py --skip-download
```

**Isolated-session campaign runner** (spawns fresh `claude -p` per runcard — the reproducibility methodology):

```bash
# One unit
experiments/run-unit.sh experiments/campaigns/2026-06-13-model-capability-sweep/runcards/01-qwen2.5-0.5b-instruct.md

# Whole campaign (sequential, resumable — skips DONE, stops on FAILED/BLOCKED)
experiments/run-campaign.sh experiments/campaigns/2026-06-13-model-capability-sweep
```

Env overrides: `CLAUDE_MODEL` (default `sonnet`), `CLAUDE_PERM` (default `bypassPermissions`).

**Parser unit tests (no device needed):**

```bash
source .venv/bin/activate
python experiments/parsers.py
# → all parsers tests passed
```

## Run (human path)

```bash
source .venv/bin/activate
python experiments/run_campaign.py   # runs all 10 units; SSH to device required
```

Ctrl-C to abort. The run is resumable with `--start-from <last-completed-unit-ID>`.

## Gotchas

- **`tegrastats` RAM under-counts mmap'd weights.** Use `--no-mmap` and `parse_llama_load_buffers` for authoritative footprints. The Gemma sweep does this automatically.
- **`swap_hit` measures growth over idle baseline**, not `swap > 0` — the device always carries a pre-existing zram baseline. The parser accounts for this.
- **`parse_bench_csv` handles two CSV formats** — old `t/s = "14.61 ± 0.00"` and newer explicit `avg_ts`/`stddev_ts` columns. Don't manually parse bench output.
- **Gemma MoE / PLE models (G3–G5) double-count buffers** in a probe pass. `parse_llama_load_buffers` de-duplicates: model buffers accumulate, compute buffers last-wins per device, KV skips zeros.
- **HF token for gated models** (Gemma): place in `.hugging-face-token` at repo root (gitignored). `run_gemma_sweep.py` reads it automatically.
- **`nvcc` is not on default PATH** on the Jetson: `/usr/local/cuda/bin/nvcc`.
- **`sudo` on the Jetson requires a password** — power-mode and `jetson_clocks` commands must be run interactively by the user.

## Troubleshooting

- **`ssh jetson` hangs or refuses**: VPN/network issue, or device powered off. Ask the user to check physical device.
- **`ModuleNotFoundError`**: venv not activated. Run `source .venv/bin/activate` first.
- **`llama-bench: command not found` on device**: llama.cpp not built or not on PATH. Check `~/llama.cpp/build/bin/`.
- **OOM kill during benchmark**: reduce context (`-c 512`) or switch to a smaller quant. This is a valid result — record it as `FAILED` with the error.
- **`smoke PASSED` but real run fails preflight**: clocks not locked or disk space low on device. Run `ssh jetson 'df -h ~'` and check.
