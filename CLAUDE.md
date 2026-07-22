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

## Project parts (I–IV complete, V paused at P5.20, VI in progress)

- **Part I — Exploratory:** device benchmark campaigns + VLM grounding fine-tune (Stages 1–4). Frozen.
- **Part II — v2 principled rebuild:** single-frame grounding. Qwen2-VL-2B Q8_0, RefDrone IoU@0.25 = 62.6%, Phases 0–4 all done.
- **Part III — v3 object permanence:** persistent moving-target tracking. T0–T4 all done, demo built, terse+ROI latency levers deployed (anchor ≈2.0 s ROI re-anchor, 85.2% IoU@0.25).
- **Part IV — v4 end-to-end workflow refinement (COMPLETE):** hardened the integrated NL→ground→track→fly pipeline. The acquire-latency arc (E18–E23) on real UAV123 video closed: the ~4.85 s cold acquire lands stale on moving targets; an operator-phrase crop hint (E20) is the only working sub-2s acquire but stays hint-fragile; automating the hint (E21/E22) and widening the crop cell (E23) both failed.
- **Part V — v5 anticipatory grounding / warm-start acquire (PAUSED 2026-07-20 at P5.20, resumable):** paused to start Part VI, with two open residuals carried forward rather than dropped — P5.19's grace precision is 2/4 (the wrong ones deliver a confident box instead of abstaining), and carry drift owns 8 of its 10 residual failures now that the capacity lever is dead (P5.20). The premise: the operator's prompt arrives mid-flight, not at frame 0 — the pre-prompt stream is free compute. Keep salient objects tracked over the idle window and select on command, instead of cold-acquiring under time pressure. Reframe: `experiments/PART5-PROPOSAL-anticipatory-grounding.md`. **Statistical standing (added 2026-07-21, R-4/R-19):** the Part V verdicts below are as-run labels. Several are descriptively right but were never inferential at their n — P5.1 is p=0.125, the P5.3/P5.4/P5.5 gates were unreachable by construction, and the P5.10/P5.13/P5.17 "ties" have zero or one discordant pair, so no test ran. **P5.2 is the one that is properly powered** (p=6.10e-05 deflated to 23 independent clips, survives Holm; 3.05e-05 undeflated — cite the deflated one, per HANDOFF invariant I2) and is what the warm-start claim should rest on. Per-claim standing, with caveats, is in `thesis/claims.json` and `thesis/stats-report.md`; do not restate a verdict from this file without checking it there. **P5.1 warm-start acquire = YES [carry-bound]:** idle-window VLM seed + SAM2 catch-up + select-on-command lands 5/6 on the UAV123 `car*` clips, matches the GT-seed oracle exactly, beats the cold blocking acquire 1/6 — removes the ~135-frame delivery staleness that capped the Part IV arc. **P5.2 warm-start generalization = YES / speed-sweep NO:** 25 clips × 5 categories × a data-driven on-screen-speed sweep — WARM 21/25 vs COLD 5/25 (RQ-P5.2a YES, generalizes past cars), but the WARM−COLD gap is **flat in speed** (Spearman ρ=−0.06; RQ-P5.2b NO) — the warm-start win is delivery-lag removal, not motion-compensation, so cold fails broadly regardless of target speed.
- **Part VI — v6 closed-loop flight (IN PROGRESS):** every Part V number was measured on replayed video the system could not influence — no vehicle in the loop. Part VI puts the warm-start select in front of a flying copter so the pixels become a consequence of its own control output. Proposal: `experiments/PART6-PROPOSAL-closed-loop-flight.md`. The rig already exists (`runners/run_phase_c.py`: ArduCopter SITL as physics, a pose-slaved renderer, VLM→ByteTrack→PID→MAVLink closed) — the remaining work is porting the Part V select modules out of `experiments/` into it. Staging: **P6.0** flight-rig capability gate (PASS), **P6.1** renderer swap Gazebo→CARLA (YES), **P6.2** closed-loop select-and-follow vs an oracle-driven no-coupling control. Decisions recorded up front and still standing: do **not** adopt `ardupilot_gazebo` lockstep, and do **not** put the copter under CARLA physics — pose-slaving already delivers the ego-motion under test, and it is what made the renderer swappable. **P6.1 = YES:** CARLA 0.9.16 `Town10HD_Opt` renders at 48.1 Hz with 40 autonomous vehicles while the camera follows a live GUIDED flight (0→84.4 m at 60 m AGL); the control stack is untouched. That 48.1 Hz is **render-loop throughput with no perception in the window**, measured in sync mode where the sim ran 2.41x faster than wall clock — the "2.4x the control rate" headroom reading is withdrawn (R-10), and the renderer is position-slaved, not pose-slaved (yaw never arrived). This replaces the plan to upgrade the scene to the P5.9/P5.12 `select_arena` bank — the flight world was empty (four entities, no targets) and the vendored Gazebo asset library has no city or traffic. P6.1's non-gating G6 was recorded NOT RUN and first called a P6.2 blocker; **that was wrong and is corrected (2026-07-20T20:10Z)** — the deployed model is on the Jetson at `/home/jfdg/grounding/phase3-terse100eos-1024-q8_0.gguf` (+ `mmproj`), which is what `grounding/deploy/video.py` points at and what P5.17 itself grounded through via `JetsonBackend`. Only the merged HF/safetensors *training* directory is lost (costs LoRA resumption and re-export, not grounding). **P6.2 is not blocked.**

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
| `HANDOFF.md` | **read first** — the thesis-integrity invariants + the session entry/exit protocol. Volatile task state lives in `thesis/REMEDIATION.md`; mechanical enforcement in `tests/test_thesis_integrity.py` | rarely — an invariant that can be checked belongs in the test instead |
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

## Look at it: visual verification is mandatory

Rendering, simulator, camera-feed and overlay work **fails silently**. A black frame, an unlit
mesh, a camera aimed at nothing, a GT box one frame stale, a video of 300 identical frames —
each of these exits 0, writes well-formed files, and prints a log that reads like success. An
agent that only reads logs will confidently report a working simulator over a black video. This
has already happened here (see the EGL ICD / sensors-plugin / infinite-plane gotchas in
`runners/sitl/GAZEBO_LIVE_FEED.md`), which is why this is a rule and not advice.

**Any claim about what a render, sim, camera feed, overlay or clip *shows* must be backed by an
image the agent actually opened with the Read tool.** "The pipeline ran", "112 frames written",
"no errors in the log" are not evidence about pixels. The frame, viewed, is.

- **Dump a frame, then look at it.** Every sim/render run writes at least one PNG into its
  `runs/<id>/` dir — mid-run, not frame 0 (frame 0 is routinely black before the first render
  completes) — and the agent Reads it before writing any verdict.
- **Geometry claims need an overlay.** A GT/box/mask/track-ID claim is unverified until the
  boxes are drawn on the real frame and that image is viewed. A GT dump nobody rendered over a
  frame is a hypothesis.
- **Auditing includes looking.** A later cycle auditing an earlier result (or Fable auditing
  Opus's run) opens the committed `proof/` frames. "The README says PASS" is not an audit.
- **Assert what you'd notice.** Cheap mechanical checks catch the classic failures without
  relying on an agent to spot them: a frame that is >99% one colour is a failed render, not a
  night scene; frames byte-identical across time are a dead feed, not a still camera. Put the
  assert in the script.
- **Can't see it, say so.** No frame captured → "cannot verify, no frame" and the run is
  INVALID. Never infer a picture from a log.

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
