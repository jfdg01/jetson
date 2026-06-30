# CLAUDE.md

This repo is the working record for a **master's thesis** on running local LLMs on
edge hardware (Jetson Orin Nano 8 GB). The numbers and notes here go into the
thesis, so **documentation is a first-class deliverable, not an afterthought.**

## Prime directive: lab notebook

Every experiment needs: the exact command, the software versions, the power mode,
and the date. Capture what works AND what doesn't — negative results are thesis content.
No unverified claims; mark estimates as estimates. A decision without its rationale is
not documented — record what was chosen, why, and what was given up.

**Timestamp rule (docs only):** whenever you write a date into a doc (RESULTS,
QUESTIONS, DECISIONS, experiment README, SOURCES — anything but a folder name),
write it as `YYYY-MM-DDThh:mmZ` using the **Madrid wall-clock time** (the hour on
the local clock, not converted to UTC), e.g. `2026-06-30T18:45Z`. Within 15
minutes is close enough; never assume `00:00`. Folder names stay date-only.

## Project parts (I–III complete, IV in progress)

- **Part I — Exploratory:** device benchmark campaigns + VLM grounding fine-tune (Stages 1–4). Frozen.
- **Part II — v2 principled rebuild:** single-frame grounding. Qwen2-VL-2B Q8_0, RefDrone IoU@0.25 = 62.6%, Phases 0–4 all done.
- **Part III — v3 object permanence:** persistent moving-target tracking. T0–T4 all done, demo built, terse+ROI latency levers deployed (anchor ≈2.0 s ROI re-anchor, 85.2% IoU@0.25).
- **Part IV — v4 end-to-end workflow refinement (IN PROGRESS):** the two-tier follow loop passed T0–T4 in isolation but the integrated NL→ground→track→fly pipeline doesn't hold up end-to-end; Part IV hardens it.

## Repository map

Three roles. The per-experiment record is the source of truth; the ledgers are rollups that
point back to it; never duplicate content across files — link.

| Path | Role | Update rule |
|---|---|---|
| `experiments/<campaign>/README.md` | **source of truth** — the full per-experiment record (command, versions, power mode, date, rationale). Raw logs in `experiments/raw/`. | one dir per campaign |
| `RESULTS.md` → `docs/results/part{1-n}-*.md` | ledger: metric tables, one row per run | **append** under the run's Part |
| `QUESTIONS.md` → `docs/questions/part{1-n}-*.md` | ledger: research question + one-line verdict per run. Root is a pure redirect (Part table only) — **append to the per-Part doc, not the root** | **append** under the run's Part |
| `DECISIONS.md` → `docs/decisions/part{1-n}-*.md` | ledger: cross-cutting choices + rationale | **append** under the run's Part |
| `SOURCES.md` | reference: every external paper/model/dataset (link + what for) | **append** when you pull one in |
| `README.md` | reference: hardware/platform survey + this map | edit when the platform changes |
| `docs/` | the per-Part ledger detail files above | — |
| `grounding/` | v2/v3 Python package (`contract.py`, `data/`, `eval/`, `train/`, `export/`, `deploy/`, `resolution.py`, `roi.py`) | — |
| `runners/` | Part-I automation + SITL follow stack (`sitl/`); `legacy/` = archived, superseded by `grounding/` | — |

The three ledger root files are **thin redirects** (a Part table) — open only the Part you're
writing, so a session doesn't drag all other chapters into context. Per-run entries go in the
per-Part doc, never the root.

## Per-experiment workflow (definition of done)

A campaign isn't done until:

1. `experiments/<campaign>/README.md` written — command, software versions, power mode, date; what worked **and** what didn't.
2. **RESULTS** row(s) appended under the run's Part.
3. **QUESTIONS** entry (RQ/`Q-*` id + one-line verdict) appended under the run's Part.
4. **DECISIONS** entry appended under the run's Part — only if a non-trivial choice was made (what / why / what was given up).
5. **SOURCES** appended if a new paper/model/dataset was used.
6. New Part? add a row to each of the three ledger root indexes and create `docs/{results,questions,decisions}/partN-*.md`.

Every number carries its config (power mode, flags, ctx). Negative/unexpected results are content — record them plainly.

## Tooling

Single venv: `.venv-ft` — torch + transformers + opencv-contrib + pymavlink. All work goes here.

```bash
make help      # list all targets
make sync      # reproduce .venv-ft from the lock
make test      # run pytest contract + manifest + audit suite
```

`requirements-ft.txt` = direct deps; `requirements-ft.lock.txt` = pinned set (`uv pip sync` target). Edit the former, run `make lock`. Do not `pip install` globally.

## Environment

- Device: `ssh jetson` (user `jfdg`). `sudo nvpmodel` and `sudo jetson_clocks` are **NOPASSWD** (run non-interactively over SSH); `apt install`, firmware flashing, etc. still need an interactive password.
- `nvcc`: `/usr/local/cuda/bin/nvcc` (not on default `$PATH`).
- HF token for gated models: `.hugging-face-token` at repo root (gitignored).

## Working agreement

- Don't leave findings only in chat — land them via the workflow above before the session ends.
- If a tool is missing (`ffmpeg`, `cmake`, a Python package), say what's needed and why — don't work around it. Document installs in the relevant `experiments/` README.
