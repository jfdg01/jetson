# CLAUDE.md

This repo is the working record for a **master's thesis** on running local LLMs on
edge hardware (Jetson Orin Nano 8 GB). The numbers and notes here go into the
thesis, so **documentation is a first-class deliverable, not an afterthought.**

## Prime directive: lab notebook

Every experiment needs: the exact command, the software versions, the power mode,
and the date. Capture what works AND what doesn't — negative results are thesis content.
No unverified claims; mark estimates as estimates. A decision without its rationale is
not documented — record what was chosen, why, and what was given up.

**Timestamp rule (docs only):** dates in docs use `YYYY-MM-DDThh:mmZ` in **Madrid
wall-clock time** (local hour, not UTC-converted), e.g. `2026-06-30T18:45Z` — within
15 min is fine, never a dummy hour. Folder names stay date-only.

## Project parts (I–IV complete, V in progress)

- **Part I — Exploratory:** device benchmark campaigns + VLM grounding fine-tune (Stages 1–4). Frozen.
- **Part II — v2 principled rebuild:** single-frame grounding. Qwen2-VL-2B Q8_0, RefDrone IoU@0.25 = 62.6%, Phases 0–4 all done.
- **Part III — v3 object permanence:** persistent moving-target tracking. T0–T4 all done, demo built, terse+ROI latency levers deployed (anchor ≈2.0 s ROI re-anchor, 85.2% IoU@0.25).
- **Part IV — v4 end-to-end workflow refinement (COMPLETE):** hardened the integrated NL→ground→track→fly pipeline. The acquire-latency arc (E18–E23) on real UAV123 video closed: the ~4.85 s cold acquire lands stale on moving targets; an operator-phrase crop hint (E20) is the only working sub-2s acquire but stays hint-fragile; automating the hint (E21/E22) and widening the crop cell (E23) both failed.
- **Part V — v5 anticipatory grounding / warm-start acquire (IN PROGRESS):** the operator's prompt arrives mid-flight, not at frame 0 — the pre-prompt stream is free compute. Keep salient objects tracked over the idle window and select on command, instead of cold-acquiring under time pressure. Reframe: `experiments/PART5-PROPOSAL-anticipatory-grounding.md`. **P5.1 warm-start acquire = YES [carry-bound]:** idle-window VLM seed + SAM2 catch-up + select-on-command lands 5/6 on the UAV123 `car*` clips, matches the GT-seed oracle exactly, beats the cold blocking acquire 1/6 — removes the ~135-frame delivery staleness that capped the Part IV arc.

**Experiment IDs:** I–IV keep their as-run labels (Part II `Phase 0-4`, Part III `T0-T4`, then a flat `E1..E23`) — frozen, do not renumber. **Part V onward uses `P<part>.<n>`** (P5.1, P5.2, …). P5.1 was pre-registered as E24 and renumbered at merge.

## Repository map

Three roles. The per-experiment record is the source of truth; the ledgers are rollups that
point back to it; never duplicate content across files — link.

| Path | Role | Update rule |
|---|---|---|
| `experiments/<campaign>/README.md` | **source of truth** — the full per-experiment record (command, versions, power mode, date, rationale). Raw logs in `experiments/<campaign>/raw/` (legacy Part-I/`runners` logs live in the shared `experiments/raw/`). | one dir per campaign |
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

**Write a README *before* you run any experiment.** Treat `experiments/<campaign>/README.md` as a
self-contained handoff: a fresh conversation with no prior context should be able to open this one
file and have everything it needs to **start, continue, document, or complete** the experiment.
Pre-register it *before launching*: the exact command, software versions, power mode, start date,
the context/restrictions, the decisions and their rationale, and your up-front estimates (expected
runtime, expected numbers — mark them as estimates). Leave a clearly-labelled placeholder section
(e.g. `## Results (TBD)`) with the table headers / shape you expect to fill in, and note current
status / next step so a later session knows where to pick up. Drafting the record first forces the
setup to be coherent before you spend the time, and it's doubly important for multi-day or overnight
runs that span sessions. Then fill it in when the run finishes; record estimate-vs-actual where they
diverge — a wrong estimate is content.

A campaign isn't done until:

1. `experiments/<campaign>/README.md` completed — pre-registered fields above, now filled with what worked **and** what didn't.
2. **RESULTS** row(s) appended under the run's Part.
3. **QUESTIONS** entry (RQ/`Q-*` id + one-line verdict) appended under the run's Part.
4. **DECISIONS** entry appended under the run's Part — only if a non-trivial choice was made (what / why / what was given up).
5. **SOURCES** appended if a new paper/model/dataset was used.
6. New Part? add a row to each of the three ledger root indexes and create `docs/{results,questions,decisions}/partN-*.md`.
7. **2–3 thesis deliverables** under `experiments/<campaign>/proof/` (curated evidence only, out of `raw/`), **committed** and captioned in the README (what it shows, which run/config). Positive = before/after (failing then fixed); negative = proof it didn't work. **Clip when the behaviour is the point** (drone locks/drifts/switches), **figure when the numbers are the point** (a matplotlib plot of per-clip IoU, latency, PASS rate, a sweep curve) — a purely-quantitative result may be all figures. Figures come from a committed `make_proof.py`-style script (reproducible from `runs/*/results.json`), saved as PNG.

Every number carries its config (power mode, flags, ctx). Negative/unexpected results are content — record them plainly.

## Tooling

Single venv: `.venv-ft` — torch + transformers + opencv-contrib + pymavlink. All work goes here.

```bash
make help      # list all targets
make sync      # reproduce .venv-ft from the lock
make test      # run pytest contract + manifest + audit suite
```

`requirements-ft.txt` = direct deps; `requirements-ft.lock.txt` = pinned set (`uv pip sync` target). Edit the former, run `make lock`. Do not `pip install` globally.

**Python over shell:** write scripts as `.py`, not `.sh`. Anything beyond a couple of
one-line commands (loops, conditionals, parsing, retries) goes in a Python script run
with the venv. Shell is fine inline in a Makefile target or a README command block;
it's not fine as a standalone script.

## Environment

- Device: `ssh jetson` (user `jfdg`). `sudo nvpmodel` and `sudo jetson_clocks` are **NOPASSWD** (run non-interactively over SSH); `apt install`, firmware flashing, etc. still need an interactive password.
- `nvcc`: `/usr/local/cuda/bin/nvcc` (not on default `$PATH`).
- HF token for gated models: `.hugging-face-token` at repo root (gitignored).
- Don't use emojis

## Working agreement

- Don't leave findings only in chat — land them via the workflow above before the session ends.
- **Isolate infra from experiment runs.** Changes to CLAUDE.md, skills, or other tooling go on `main` (or their own branch), never committed onto an `experiment/<slug>` branch — and never while an executor is mid-run in the shared worktree (stash them until it merges). An experiment branch carries only that experiment's work, so its merge stays a clean, reviewable unit.
- **Install what you need.** If a tool or package is missing (`ffmpeg`, a Python package, a wheel on the Jetson), install it and move on — don't work around it or stall to ask. Installs go in a venv, never global. The only stops: anything needing an interactive password (Jetson `apt`) — ask the user to run it — and anything destructive. Document every install (what, version, why) in the relevant `experiments/` README.
