---
unit_id: model-capability-sweep-01
campaign: 2026-06-13-model-capability-sweep
title: "Qwen2.5-0.5B-Instruct Q4_K_M @ 15W locked"
status: TODO
created: 2026-06-13
---

# Unit 01: Qwen2.5-0.5B-Instruct Q4_K_M @ 15 W locked

> Executed by a fresh, isolated session via `experiments/run-unit.sh`. Your only context is
> `CLAUDE.md` + this card. Methodology: `experiments/README.md`. Design / RQs / hypotheses:
> `results/2026-06-13-model-capability-sweep.md` (read for context; do NOT edit its structure).

## Objective
Model #01 of the sweep — Tier A ultralight, family Qwen2.5, 0.5 B. Floor of the size curve: max decode tok/s, where fixed platform overhead dominates energy/token (tests the low end of H1 and H4).

## Preconditions  (verify ALL; if any fails → status: BLOCKED, note why, STOP)
- [ ] `ssh jetson true` succeeds.
- [ ] Runtime present at pinned commit: `git -C ~/llama.cpp rev-parse --short HEAD` == `57fe1f0`,
      and `~/llama.cpp/build/bin/llama-bench` exists. (Binaries are NOT on $PATH and need
      `LD_LIBRARY_PATH` — see Procedure.) If absent/mismatched → BLOCKED (building is not this unit's job).
- [ ] `df -h /` shows ample free space (need ~1 GB; NVMe had ~196 GB free).
- [ ] Network: `wget` can reach Hugging Face (curl/huggingface-cli are NOT installed; use `wget`).

## Inputs  (record exactly — verify SHA256 after acquisition)
| Field | Value |
|---|---|
| Model | Qwen2.5-0.5B-Instruct |
| Params | 0.5 B |
| Quant | Q4_K_M |
| GGUF repo | `bartowski/Qwen2.5-0.5B-Instruct-GGUF` (Hugging Face) |
| Revision | record the resolved commit hash at download |
| File | `~/models/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf` |
| SHA256 | <fill at acquisition; record in the result block> |
| Expected size | ~397 MB |

## Controlled config  (DO NOT change — held constant across the whole campaign)
- Power mode: **15 W (ID=0)**, clocks **LOCKED** (`sudo jetson_clocks`). (Device already defaults to 15 W.)
- Runtime: llama.cpp commit `57fe1f0`, CUDA `sm_87`, `-ngl 99` (full GPU offload).
- Context / batch: `n_ctx = 4096`, `n_batch = 512`.
- Shapes / repeats: `llama-bench -p 512 -n 128 -r 5`, plus a `tg512 -r 3` sustained pass.
- Begin from a cooled idle baseline (no heat-soak carryover from a prior unit).
- **Binaries need their lib dir on the path:** `export LD_LIBRARY_PATH=~/llama.cpp/build/bin:/usr/local/cuda/lib64`.

## Procedure  (run EXACTLY; the ONLY variable vs. sibling cards is the model)
```bash
# 0. set + lock power state, start the power log over the WHOLE window
ssh jetson 'sudo nvpmodel -m 0 && sudo jetson_clocks'
ssh jetson 'nohup tegrastats --interval 1000 --logfile /tmp/msweep01_tegra.log >/dev/null 2>&1 & echo started pid $!'

# 1. acquire model onto NVMe via wget (curl/hf-cli not installed), then record sha256
ssh jetson 'wget -c -O ~/models/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf \
   "https://huggingface.co/bartowski/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf"'
ssh jetson 'sha256sum ~/models/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf'   # record the hash + the resolved repo revision

# 2. let a few seconds of idle accrue in the tegrastats log before loading the model

# 3. throughput — prefill + decode, 5 repeats, CSV out
ssh jetson 'export LD_LIBRARY_PATH=~/llama.cpp/build/bin:/usr/local/cuda/lib64; \
   ~/llama.cpp/build/bin/llama-bench -m ~/models/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf -ngl 99 -p 512 -n 128 -r 5 -o csv' \
   | tee /tmp/msweep01_bench.csv
# sustained decode droop check
ssh jetson 'export LD_LIBRARY_PATH=~/llama.cpp/build/bin:/usr/local/cuda/lib64; \
   ~/llama.cpp/build/bin/llama-bench -m ~/models/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf -ngl 99 -n 512 -r 3'

# 4. TTFT — single timed generation (llama-cli prints first-token + per-token timings)
ssh jetson 'export LD_LIBRARY_PATH=~/llama.cpp/build/bin:/usr/local/cuda/lib64; \
   ~/llama.cpp/build/bin/llama-cli -m ~/models/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf -ngl 99 -c 4096 -n 128 \
   -no-cnv -p "Explain what an edge AI accelerator is in two sentences."'

# 5. memory — peak RAM + unified GPU during decode; note if zram swap was touched
ssh jetson 'free -m; cat /proc/swaps; tail -n 5 /tmp/msweep01_tegra.log'

# 6. stop the power log
ssh jetson 'pkill -f tegrastats || true'

# 7. pull artifacts back into the repo
scp jetson:/tmp/msweep01_tegra.log results/raw/2026-06-13_msweep01_tegra.log
cp /tmp/msweep01_bench.csv results/raw/2026-06-13_msweep01_bench.csv
```

## Output contract  (all of these, before you stop)
- [ ] `results/raw/2026-06-13_msweep01_tegra.log` and `results/raw/2026-06-13_msweep01_bench.csv` saved.
- [ ] Detail block appended to `results/2026-06-13-model-capability-sweep.md` (new
      "### Unit 01 — Qwen2.5-0.5B-Instruct" subsection under a "## Results" heading) with EVERY mandatory
      metric: pp512 + tg128 (median ± σ), tg512 sustained, TTFT, peak RAM + unified GPU + swap
      flag, idle/mean/peak W (steady-state decode power, not the deflated window-mean), peak SoC
      temp + throttle flag, tok/s·W⁻¹ and J/token (total + net-of-idle), model load time, SHA256.
- [ ] Exactly one row appended to `RESULTS.md` (append-only ledger), config next to numbers.
- [ ] This card `status:` → DONE (or FAILED).

## Done criteria
- [ ] All output-contract items complete; throughput reported as median ± σ over 5 repeats.
- [ ] Fit note for this tier: large headroom, OOM not expected.
- [ ] No thermal throttle, or throttle explicitly noted if it occurred.

## Failure handling  (failures are data)
This model is tiny; OOM is not expected.
Write the failure (error text + suspected cause + workaround/"unresolved") into the result
block and set `status: FAILED`. Do NOT retry with a changed config to force a pass.

## Guardrails  (the restriction)
- ONE unit only. Do not run sibling units, do not edit sibling cards, do not edit the
  pre-registration design doc's structure.
- Keep the controlled config fixed; the model is the only thing that differs from siblings.
- Ambiguous / precondition unmet → `status: BLOCKED`, note it, STOP. Never guess.
