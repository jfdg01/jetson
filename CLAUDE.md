# CLAUDE.md — Jetson Edge-LLM Thesis Testbed

This repo is the working record for a **master's thesis** on running local LLMs on
edge hardware (Jetson Orin Nano 8 GB). The numbers and notes here go into the
thesis, so **documentation is a first-class deliverable, not an afterthought.**

## Prime directive: document everything

Treat this repo as a **lab notebook**. For every experiment, capture enough that a
reader (and the thesis committee) could reproduce it and trust the result.

- **Record what works AND what doesn't.** Failed builds, OOM kills, thermal
  throttling, driver mismatches, flags that did nothing, models that wouldn't load —
  negative results are thesis content. Never silently discard a failure; write down
  the error, the cause (if known), and the workaround (or "unresolved").
- **Document every decision and explain WHY.** Whenever a choice is made — a power
  mode, a runtime, a model, a build strategy, *not* doing something (e.g. skipping a
  risky firmware flash), picking option A over B — record it with: what was decided,
  the alternatives considered, the reasoning, and the tradeoff accepted. A decision
  without its rationale is not documented. See "Decision log" below.
- **Reproducibility over prose.** Every result must come with the exact command,
  the software versions, the power mode, and the date. If it can't be reproduced
  from what's written, it isn't done.
- **No unverified claims.** Don't write a tok/s number you didn't measure. Mark
  estimates as estimates. If a run was interrupted or noisy, say so.
- **Date and version every entry.** Hardware/firmware/runtime versions drift;
  an undated number is worthless for a thesis.

## Where things go

- `README.md` — stable hardware/platform survey of the device (already written).
- `CLAUDE.md` — this file: working conventions.
- `results/` — one Markdown file per experiment campaign (e.g.
  `results/2026-06-13-llamacpp-upper-bound.md`). Raw tool output (llama-bench CSV,
  `tegrastats` logs) lives alongside in `results/raw/`.
- `RESULTS.md` (root) — a running **summary table** across all experiments, the
  at-a-glance ledger the thesis pulls from. Append, don't overwrite.

## What to capture for every benchmark run

Mandatory fields for each row/entry:

| Field | Notes |
|---|---|
| **Date / time** | UTC; firmware and clocks can change between sessions |
| **Device + power mode** | e.g. Orin Nano 8GB, `MAXN_SUPER` (25 W) vs 15 W vs 7 W; clocks locked? (`jetson_clocks`) |
| **Runtime + version** | e.g. llama.cpp commit hash, build flags (`-DGGML_CUDA=ON`, `sm_87`) |
| **Model + quant** | full name + quant (e.g. Llama-3.2-3B-Instruct `Q4_K_M`), file size, source URL/hash |
| **Prefill tok/s (pp)** | prompt-processing throughput |
| **Decode tok/s (tg)** | token-generation throughput — the headline edge number |
| **Time-to-first-token** | latency, where measured |
| **Context length** | n_ctx / batch used |
| **Peak memory** | RAM + (unified) GPU, and whether swap was hit |
| **Power draw** | from `tegrastats` — idle, mean, peak watts during decode |
| **Energy efficiency** | tok/s per watt, or J/token — the key edge tradeoff metric |
| **Temps / throttling** | peak SoC temp; note any thermal throttle observed |
| **Notes / anomalies** | warm-up effects, variance across repeats, errors |

Run each benchmark **multiple times** and report the spread (or median), not a
single cherry-picked best. Note warm-up/cold-cache effects explicitly.

## Methodology notes (keep these honest in the writeup)

- State the **power mode and clock state before each run** — it's the dominant
  variable. Lock clocks (`sudo jetson_clocks`) for max-perf "upper bound" runs and
  say so; for realistic runs, note default/unlocked.
- Log `tegrastats` (or `tegrastats --logfile`) for the **whole** inference window so
  power/thermal numbers line up with the throughput numbers.
- Keep the model file, quant, and prompt **identical** across runtimes when
  comparing runtimes; change one variable at a time.
- Prefer `llama-bench` for authoritative prefill/decode separation; note when a
  number comes from a looser source (e.g. Ollama `--verbose` eval rate).

## Decision log

Every non-trivial decision gets logged with its reasoning — this is how the thesis
justifies methodology, and how we avoid re-litigating settled choices.

- **Where:** decisions specific to one campaign go in that campaign's `results/*.md`
  under a `## Decisions` heading. Cross-cutting/project-wide decisions go in the root
  **`DECISIONS.md`** log (most-recent first).
- **Format for each entry:**

  ```
  ### <date>T<time> — <short title>
  - **Decision:** what we chose to do (or chose NOT to do).
  - **Alternatives considered:** the options on the table.
  - **Reasoning:** why this one; the deciding factors.
  - **Tradeoff / cost accepted:** what we give up, and any risk taken on.
  - **Revisit when:** the condition under which this should be reconsidered (if any).
  ```
- "We're not doing X" is a decision too — log it (e.g. declining a remote firmware
  flash because of brick risk without physical access).
- Keep it honest: if a decision was forced by a constraint (time, access, hardware),
  say so rather than dressing it up as the ideal choice.

## Environment conventions

- Python work uses a **venv per project** (`python3 -m venv .venv`); never
  `pip install` globally. PyTorch on Jetson must come from NVIDIA's aarch64 wheels,
  not stock PyPI.
- The device is reached via `ssh jetson` (user `jfdg`). **`sudo` needs a password**
  there — power-mode changes, `jetson_clocks`, and `apt install` must be run
  interactively by the user; document which steps required root.
- `nvcc` is at `/usr/local/cuda/bin/nvcc` (not on default `$PATH`).

## Working agreement for Claude

- When you run a benchmark or hit a failure, **write it into `results/` and update
  `RESULTS.md` in the same turn** — don't leave findings only in chat.
- Surface negative/unexpected results plainly; don't smooth them over.
- When a number depends on a config (power mode, flags, ctx), always report the
  config next to the number.
