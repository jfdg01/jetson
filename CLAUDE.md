# CLAUDE.md

Working record for a **master's thesis** on local LLMs on edge hardware (Jetson Orin Nano 8 GB). Documentation is a deliverable, not an afterthought.

## Prime directive: lab notebook

Every experiment records: exact command, software versions, power mode, date. Negative results are thesis content. No unverified claims — mark estimates as estimates. A decision without its rationale is undocumented: what was chosen, why, what was given up.

**Timestamps (docs only):** `YYYY-MM-DDThh:mmZ` in **Madrid wall-clock** (local hour, not UTC-converted). Within 15 min is fine, never a dummy hour. Folder names stay date-only.

## Project parts

I–IV complete (frozen), V paused at P5.20 (reopened once for P5.21), VI in progress.

- **I — Exploratory:** device benchmarks + VLM grounding fine-tune (Stages 1–4).
- **II — v2 single-frame grounding:** Qwen2-VL-2B Q8_0, RefDrone IoU@0.25 = 62.6%. Phases 0–4 done.
- **III — v3 object permanence:** persistent moving-target tracking, T0–T4 done. Terse+ROI levers deployed (~2.0 s ROI re-anchor, 85.2% IoU@0.25).
- **IV — v4 end-to-end workflow:** NL→ground→track→fly hardened. Acquire-latency arc E18–E23 closed on UAV123: ~4.85 s cold acquire lands stale; operator-phrase crop hint (E20) is the only sub-2s acquire but hint-fragile; automating it (E21/E22) and widening the crop cell (E23) failed.
- **V — v5 anticipatory grounding / warm-start acquire:** premise — the prompt arrives mid-flight, so pre-prompt stream is free compute: carry salient objects over the idle window, select on command. Warm start works and generalizes past cars (P5.1, P5.2). Carry levers closed as measured negatives: P5.15 (carry not the fragile part), P5.20 (capacity dead), P5.21 (ROI re-anchor mildly regresses plain carry — keep ROI-crop for acquire prefill only). Residuals: P5.19 grace precision, carry drift. Proposal: `experiments/PART5-PROPOSAL-anticipatory-grounding.md`.
- **VI — v6 closed-loop flight (in progress):** Part V ran on replayed video; VI puts warm-start select in front of a flying copter so pixels are a consequence of its own control. Rig `runners/run_phase_c.py` (ArduCopter SITL physics, pose-slaved renderer, VLM→ByteTrack→PID→MAVLink). P6.0 gate PASS, P6.1 renderer swap Gazebo→CARLA YES, P6.2 closed-loop select-and-follow vs oracle no-coupling control. **P6.2-DELIVERY is the flagship** and the one properly-powered VI number (survives Holm per-Part and globally); caveat is load-bearing — grounding held constant by **ORACLE designation**, so the claim is control-coupling *conditional on correct designation*, not grounding+delivery jointly. P6.2-COUPLING is a **bounded null**, never proven equivalence. Deployed: **SAM2 track-res 640** (EXP-1), 1024 as size-gated fallback for small/distant targets. Proposal: `experiments/PART6-PROPOSAL-closed-loop-flight.md`.

**Standing decisions.** (R-28, author, 2026-07-23) The thesis defends **maintain-and-deliver, not select** — every Part V and VI result supports it; selecting among candidates ships as a measured proposal, not a result. Do **not** adopt `ardupilot_gazebo` lockstep and do **not** put the copter under CARLA physics — pose-slaving already gives the ego-motion under test and is what made the renderer swappable.

**Statistical standing (R-4/R-19).** Part V verdicts are as-run labels; several are descriptively right but were never inferential at their n. **P5.2 carries the warm-start claim.** Never restate a verdict without checking `thesis/claims.json`, `thesis/stats-report.md`, `docs/questions/part{5,6}-*.md`.

**Experiment IDs:** I–IV keep as-run labels (Part II `Phase 0-4`, Part III `T0-T4`, then flat `E1..E23`) — frozen, never renumber. **Part V onward is `P<part>.<n>`.**

## Repository map

Per-experiment record is source of truth; ledgers are rollups pointing back to it. Never duplicate across files — link.

| Path | Role | Update rule |
| --- | --- | --- |
| `experiments/<campaign>/README.md` | **source of truth** — full per-experiment record. Raw logs in `raw/` (legacy Part-I/`runners` logs in shared `experiments/raw/`) | one dir per campaign |
| `RESULTS.md` → `docs/results/part{1-n}-*.md` | ledger: metric tables, one row per run | **append** under the run's Part |
| `QUESTIONS.md` → `docs/questions/part{1-n}-*.md` | ledger: research question + one-line verdict | **append** under the run's Part |
| `DECISIONS.md` → `docs/decisions/part{1-n}-*.md` | ledger: cross-cutting choices + rationale | **append** under the run's Part |
| `HANDOFF.md` | **read first** — thesis-integrity invariants + session entry/exit protocol. Volatile state in `thesis/REMEDIATION.md`, enforcement in `tests/test_thesis_integrity.py` | rarely — a checkable invariant belongs in the test |
| `SOURCES.md` | every external paper/model/dataset (link + what for) | **append** when you pull one in |
| `README.md` | hardware/platform survey + this map | edit when the platform changes |
| `grounding/` | v2/v3 package (`contract.py`, `data/`, `eval/`, `train/`, `export/`, `deploy/`, `resolution.py`, `roi.py`) | — |
| `runners/` | Part-I automation + SITL follow stack (`sitl/`); `legacy/` = archived | — |

The three ledger roots are **thin redirects** (Part table only) — open only the Part you're writing. Per-run entries go in the per-Part doc, never the root.

## Per-experiment workflow (definition of done)

**Write the README _before_ you run anything.** `experiments/<campaign>/README.md` is a self-contained handoff: a fresh session with no context opens this one file and can start, continue, document or complete the experiment. Pre-register the exact command, versions, power mode, start date, context/restrictions, decisions + rationale, and up-front estimates (runtime, expected numbers — labelled as estimates). Leave a `## Results (TBD)` placeholder with the table shape you expect, plus current status / next step. Fill it in after the run and record estimate-vs-actual where they diverge — a wrong estimate is content.

Not done until:

1. `experiments/<campaign>/README.md` filled with what worked **and** what didn't.
2. **RESULTS** row(s) appended under the run's Part.
3. **QUESTIONS** entry (RQ/`Q-*` id + one-line verdict) appended.
4. **DECISIONS** entry appended — only if a non-trivial choice was made.
5. **SOURCES** appended if a new paper/model/dataset was used.
6. New Part? row in each of the three ledger root indexes + `docs/{results,questions,decisions}/partN-*.md`.
7. **2–3 thesis deliverables** in `experiments/<campaign>/proof/`, committed and captioned (what it shows, which run/config). Positive = before/after; negative = proof it didn't work. **Clip when the behaviour is the point** (locks/drifts/switches), **figure when the numbers are the point** — figures from a committed `make_proof.py`-style script reproducible from `runs/*/results.json`, saved PNG.

Every number carries its config (power mode, flags, ctx).

## Look at it: visual verification is mandatory

Render, sim, camera-feed and overlay work **fails silently** — black frames, unlit meshes, stale GT boxes, 300 identical frames all exit 0 and log like success. It has happened here (EGL ICD / sensors-plugin / infinite-plane gotchas in `runners/sitl/GAZEBO_LIVE_FEED.md`).

**Any claim about what a render, sim, feed, overlay or clip _shows_ needs an image the agent opened with Read.** "Ran fine", "112 frames written", "no errors" are not evidence about pixels.

- **Dump a frame, then look.** Every sim/render run writes a PNG into `runs/<id>/` — mid-run, not frame 0 (routinely black) — and the agent Reads it before any verdict.
- **Geometry claims need an overlay** drawn on the real frame and viewed. A GT dump nobody rendered is a hypothesis.
- **Auditing includes looking** — open the committed `proof/` frames. "The README says PASS" is not an audit.
- **Assert what you'd notice:** >99% one colour = failed render; byte-identical frames across time = dead feed. Put the assert in the script.
- **Can't see it, say so:** no frame → "cannot verify, no frame", run is INVALID. Never infer pixels from a log.

## Environment

- Single venv `.venv-ft`. `requirements-ft.txt` = direct deps, `requirements-ft.lock.txt` = pinned (`uv pip sync` target). Edit the former, run `make lock`. Never `pip install` globally.
- **Python over shell:** scripts are `.py`. Anything with loops, conditionals, parsing or retries goes in Python. Shell only inline in a Makefile target or README command block.
- Device `ssh jetson` (user `jfdg`). `sudo nvpmodel` / `sudo jetson_clocks` are **NOPASSWD**; `apt install` and flashing need an interactive password.
- `nvcc`: `/usr/local/cuda/bin/nvcc` (not on default `$PATH`).
- HF token for gated models: `.hugging-face-token` at repo root (gitignored).
- No emojis.

## Working agreement

- Don't leave findings in chat — land them via the workflow above before the session ends.
- **Isolate infra from experiment runs.** CLAUDE.md, skills and tooling changes go on `main` or their own branch, never onto an `experiment/<slug>` branch, and never while an executor is mid-run in the shared worktree (stash until it merges).
- **Install what you need** (`ffmpeg`, a package, a Jetson wheel) — in a venv, never global, documented in the relevant `experiments/` README. Only stops: interactive password (Jetson `apt`) — ask the user — and destructive actions.
