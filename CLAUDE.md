# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

This repo is the working record for a **master's thesis** on running local LLMs on
edge hardware (Jetson Orin Nano 8 GB). The numbers and notes here go into the
thesis, so **documentation is a first-class deliverable, not an afterthought.**

## Prime directive: lab notebook

Every experiment needs: the exact command, the software versions, the power mode,
and the date. Capture what works AND what doesn't — negative results are thesis content.
No unverified claims; mark estimates as estimates. A decision without its rationale is
not documented — record what was chosen, why, and what was given up.

## Project parts (all complete)

- **Part I — Exploratory:** device benchmark campaigns + VLM grounding fine-tune (Stages 1–4). Frozen.
- **Part II — v2 principled rebuild:** single-frame grounding on `v2/principled-rebuild`. Qwen2-VL-2B Q8_0, RefDrone IoU@0.25 = 62.6%, Phases 0–4 all done.
- **Part III — v3 object permanence:** persistent moving-target tracking on `v3/object-permanence`. T0–T4 all done, demo built, terse+ROI latency levers deployed (anchor ≈2.0 s ROI re-anchor, 85.2% IoU@0.25).

## Where things go

- `README.md` — hardware/platform survey + project-layout map.
- `grounding/` — v2 Python package (`contract.py`, `data/`, `eval/`, `train/`, `export/`, `deploy/`, `resolution.py`, `roi.py`).
- `results/` — one directory per experiment campaign. Raw logs in `results/raw/`.
- `RESULTS.md` — running summary table across all experiments. Append, don't overwrite.
- `experiments/` — Part-I automation scripts + SITL follow stack (`sitl/`).
- `experiments/legacy/` — archived Part-I trainers/exporters. Superseded by `grounding/`.
- `DECISIONS.md` — project-wide decision log. Add a one-line summary + link for each decision; full rationale, numbers, and alternatives go in `results/<campaign>/README.md`.

## Tooling

Single venv: `.venv-ft` — torch + transformers + opencv-contrib + pymavlink. All work goes here.

```bash
make help      # list all targets
make sync      # reproduce .venv-ft from the lock
make test      # run pytest contract + manifest + audit suite
```

`requirements-ft.txt` = direct deps; `requirements-ft.lock.txt` = pinned set (`uv pip sync` target). Edit the former, run `make lock`. Do not `pip install` globally.

## Environment

- Device: `ssh jetson` (user `jfdg`). `sudo` needs a password — power-mode changes, `jetson_clocks`, `apt install` must be run interactively.
- `nvcc`: `/usr/local/cuda/bin/nvcc` (not on default `$PATH`).
- HF token for gated models: `.hugging-face-token` at repo root (gitignored).

## Working agreement

- Write results into `results/` and update `RESULTS.md` before the session ends — don't leave findings only in chat.
- Surface negative/unexpected results plainly.
- Always report the config (power mode, flags, ctx) next to any number.
- If a tool is missing (`ffmpeg`, `cmake`, a Python package), say what's needed and why — don't work around it. Document installs in the relevant `results/` README.
