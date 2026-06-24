# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

## Project parts: I (exploratory), II (v2 rebuild), III (object permanence)

The notebook is split into three parts. **Part I — Exploratory** is the original
record: device benchmark campaigns + the VLM grounding fine-tune arc (Stages 1–4),
now frozen. **Part II — Principled rebuild (v2)** is the deliberate single-frame
grounding rebuild on branch `v2/principled-rebuild`, organised around one shared
*contract* and a **fidelity-before-GPU** workflow (see the v2 section below) — ALL
phases 0–4 complete, deployed on Jetson (Qwen2-VL-2B Q8_0, RefDrone IoU@0.25 = 62.6%).
**Part III — Persistent tracking / object permanence (v3)** is the next phase on
branch `v3/object-permanence`: moving from a single *frame* to a *video stream* —
keep a lock on a moving target across occlusion / scale change / out-of-frame and
close a following control loop (see the v3 section below). All of `DECISIONS.md` and
`RESULTS.md` are append-only and carry `Part II` / `Part III` demarcations; earlier
parts are untouched.

## Where things go

- `README.md` — stable hardware/platform survey + the Part I/II project-layout map.
- `CLAUDE.md` — this file: working conventions.
- `grounding/` — **v2 Python package** (Part II). The shared `contract.py` plus
  `data/ eval/ train/ export/ deploy/ resolution.py`. See `grounding/README.md`.
- `results/` — one Markdown file per experiment campaign (e.g.
  `results/2026-06-13-llamacpp-upper-bound.md`). Raw tool output (llama-bench CSV,
  `tegrastats` logs) lives alongside in `results/raw/`.
- `RESULTS.md` (root) — a running **summary table** across all experiments, the
  at-a-glance ledger the thesis pulls from. Append, don't overwrite.
- `experiments/` — Part-I Python automation scripts, run cards, and the
  isolated-session execution methodology. See `experiments/README.md`.
- `experiments/legacy/` — archived Part-I per-stage trainers / exporters / demo
  (kept for the record; superseded by `grounding/`).
- `archive/research/` — archived research & handoff prose (literature sweep, research
  prompts, handoff notes).
- `DECISIONS.md` — project-wide decision log (most-recent first; Part III on top).

## v2 — Principled rebuild architecture (Part II)

v2 is designed **backwards from deployment** and **de-risks cheaply before spending
GPU**. The whole effort pivots on **one shared contract** — the verbatim
`GROUNDING_PROMPT`, the `parse_bbox` parser, and the IoU / `center_std` metric —
defined in exactly one place (`grounding/contract.py`) and imported everywhere
(probe, train, export, Jetson) so prompt/parser/metric can never drift again.

Two findings from Part I are *binding constraints* the v2 design is organised around:
1. **Deployment-runtime fidelity gap** — exported skill dropped HF bf16 85% → GGUF
   F16 62% (−23pp, a llama.cpp Idefics3 image-preprocessing divergence) → Q8_0 55%
   (−7pp quant). The runtime penalty dominates the quant penalty, and it was only
   found *after* training. **v2 measures backend fidelity before any GPU run.**
2. **Tiny-object resolution ceiling** — aerial objects 5–30 px → 2–11 px after the
   512 long-edge resize through a frozen SigLIP encoder. **v2 treats resolution as an
   explicit, pre-registered variable.**

Phased, gated workflow (each phase's module is fleshed out at its own startup; do not
start the next phase until the prior gate is green and documented in `results/` +
`RESULTS.md` + `DECISIONS.md` in the same turn):
- **Phase 0 — backend-fidelity harness first** (`grounding/eval/`): backend-agnostic
  eval spine (HF / GGUF / Jetson behind one interface) + HF-vs-llama.cpp parity probe;
  pick the model spine *by the numbers*, not by opinion.
- **Phase 1 — dataset audit gate** (`grounding/data/`): box-per-caption + object-size
  distributions baked into the canonical schema before any GPU run.
- **Phase 2 — resolution strategy** (`grounding/resolution.py`): tiling/crops vs
  higher-res vs accepting the frozen-512 ceiling, chosen and pre-registered.
- **Phase 3 — train** (`grounding/train/`): one config-driven LoRA loop (not per-stage
  forks), only after 0–2 are green. Gate: aerial IoU@0.25 ≥ 20%, `center_std`
  non-degenerate, parse_rate ≥ 90%.
- **Phase 4 — export & deploy** (`grounding/export/`, `grounding/deploy/`): GGUF export
  with the F16-vs-Q8 disambiguation as a default gate; Jetson serve + Phase C hook.

**venvs:** `.venv-ft` (torch 2.6.0+cu124 — reused, painful to rebuild) for all
GPU/eval/training work, and for any Part-III script that uses `numpy`/`scipy`/`PIL`
(e.g. `run_t0_cadence.py`); `.venv` for the Part-I device-benchmark tooling **and**
pymavlink SITL offboard (it is not purely stdlib — pymavlink is installed there).

## v3 — Persistent tracking / object permanence architecture (Part III)

v3 moves the problem from a single **frame** to a **video stream**: given a referring
phrase, keep a lock on that *moving* target across time — through occlusion, scale
change, motion blur, brief out-of-frame and re-acquisition — well enough to close a
drone following loop. Single-frame IoU@0.25 (Part II's headline) is retained only as a
per-anchor sanity check; the Part III headline metrics are **temporal** (track
continuity / SOT success-precision, ID switches, re-acquisition time, oracle-coverage,
closed-loop following error). The full charter is
`results/2026-06-18-part3-charter/README.md`.

**This is not from scratch.** Part I already built the SITL follow stack
(`experiments/sitl/`: ByteTrack Kalman tracker, oracle_bbox perfect-perception upper
bound + free labels, cascade_pid outer loop, pymavlink offboard) and ran Phase B
(oracle closed loop, PASS) / Phase C (zero-shot VLM @ ~1 Hz, Branch-2 NEGATIVE — naive
rate-mismatch + memoryless coasting could not hold a moving lock). Part II produced a
deployable language-grounding **anchor** (Qwen2-VL-2B Q8_0, 62.6%). v3's job is the
**bridge and the memory**, not the plumbing.

**Forced architecture (hardware-imposed):** a VLM forward pass on the Orin is
~0.3–1.2 Hz; a following loop needs ~20 Hz. That ~20–60× gap is structural, so v3 runs
a **fast per-frame tracker (motion + appearance) at 20 Hz holding the lock**, with the
**VLM as a sparse async semantic anchor** for acquisition, periodic re-anchor and
re-acquisition.

Two findings become v3's *binding constraints* (the analogs of Part II's two):
1. **Detection-cadence vs target-dynamics budget** (the new dominant variable, analog
   of the deployment-fidelity gap) — how far the target moves between anchors vs the
   tracker's coasting horizon. **Measure on-Orin cadence + target dynamics before
   tuning the loop** (the "fidelity-before-GPU" discipline becomes "measure cadence-vs-
   dynamics before design").
2. **Identity through absence / object permanence** (the new accuracy frontier, analog
   of the resolution ceiling) — the current ByteTrack is constant-velocity Kalman with
   **NO appearance / re-ID memory**, so re-acquisition can re-lock the *wrong* object.
   This is the genuinely unsolved piece the Part III chapter is about.

Proposed gated phases (T0–T4; same gate rule — don't start the next until the prior is
green and documented in `results/` + `RESULTS.md` + `DECISIONS.md` same-turn):
- **T0 — cadence & dynamics harness** (measure-before-design): on-Orin VLM Hz sweep
  (incl. Gemma 4 token-budget lever), per-frame tracker cost at 20 Hz, target-dynamics
  / occlusion stats. Gate: cadence-vs-dynamics budget quantified, anchor spine picked
  by the numbers.
- **T1 — data & temporal contract**: choose data (real aerial referring-video vs
  SITL clips with free oracle labels); extend `contract.py` with temporal metric
  primitives, pytest-locked.
- **T2 — permanence mechanism**: add identity-through-absence (appearance/re-ID memory
  and/or VLM re-verification). Gate: beat memoryless-ByteTrack ID-switch / re-acq.
- **T3 — closed-loop integration** in SITL: beat the Phase-C negative (oracle-coverage
  well above ~0% on a *moving* target).
- **T4 — on-Orin deployment** within the T0 cadence budget; characterise sim-to-device.

**Gemma 4 note (honest):** the user wants to try Gemma 4 (variable-resolution + a
70–1120 token/image latency lever — real appeal). But video-capable Gemma 4 is 26B/31B
(won't fit 8 GB Orin); the fitting E2B/E4B are image-only and already measured at
**0.34–0.49 Hz on the Orin — the slowest candidates** (slower than SmolVLM-500M 1.2 Hz).
The token-budget speed lever is untested. So Gemma 4 enters T0 as a *candidate to
measure*, not a foregone choice; the anchor spine is picked **by the numbers** against
the already-deployed Qwen2-VL-2B Q8_0.

**venvs / hardware unchanged:** `.venv-ft` for GPU/eval/train, stdlib `.venv` for
device tooling; Orin Nano 8 GB inference, RTX 3090 24 GB training.

## Python tooling

There are **two toolchains** by design — keep them separate:

- **Part I (`experiments/`)** is **stdlib-only** — no pip dependencies for the
  data-collection path, so device-benchmark results reproduce without pinning a
  dependency tree. Documented immediately below.
- **Part II (`grounding/`)** is the managed toolchain — **uv + a fully-pinned
  lockfile**, file-based run manifests, **pytest**, driven by a **Makefile**. See
  "v2 toolchain (Part II)" further down and `DECISIONS.md` (Part II) for *why*.

### Part I — device-benchmark tooling (stdlib-only)

```bash
# Activate the venv (created at repo root)
source .venv/bin/activate

# Run the parser unit tests (no pytest needed)
python experiments/parsers.py          # prints "all parsers tests passed"

# 10-model capability sweep (campaign 2026-06-13)
# Prerequisite: ssh jetson 'sudo nvpmodel -m 0 && sudo jetson_clocks'
python experiments/run_campaign.py [--only 01,03] [--dry-run] [--start-from 05] [--skip-download]

# Gemma-family sweep (campaign 2026-06-14)
python experiments/run_gemma_sweep.py [--only G1,G3] [--dry-run] [--start-from G3] [--skip-download]

# Gemma footprint re-measure (§11 / RQ-G3): authoritative --no-mmap buffers for G2/G3/G4
# and partial-offload cliff probe for G5
python experiments/run_gemma_sweep.py --footprint [--g5-ngl 28]
```

HF token for gated models (e.g. Gemma): place it in `.hugging-face-token` at the
repo root (gitignored). `run_gemma_sweep.py` reads it automatically.

## v2 toolchain (Part II)

The `grounding/` package and all GPU/eval/training work use a managed, reproducible
toolchain. **All commands go through the `Makefile`** (`make help` lists them) so they
are identical across sessions.

```bash
make help          # list targets
make sync          # reproduce .venv-ft EXACTLY from the lock (uv pip sync)
make dev           # add dev/test tooling (pytest) on top of .venv-ft
make test          # run the pytest contract + manifest + audit suite
make lock          # regenerate the pinned lock after editing requirements-ft.txt

# Run a single test file or test:
.venv-ft/bin/python -m pytest tests/test_contract.py -v
.venv-ft/bin/python -m pytest tests/test_contract.py::test_iou_zero_when_no_overlap -v
```

`pyproject.toml` exists **only** to configure pytest (`testpaths`, `addopts`) and mark the repo root for package imports. It does **not** manage runtime deps — those live in `requirements-ft.txt` + `requirements-ft.lock.txt`.

- **Dependencies** — `uv` (user-local at `~/.local/bin/uv`) with a **fully-pinned
  transitive lockfile**. `requirements-ft.txt` is the human-edited *direct* deps;
  `requirements-ft.lock.txt` is the authoritative pinned set (`uv pip sync` target).
  It carries `--extra-index-url .../whl/cu124` so the `torch==2.6.0+cu124` /
  `torchvision==0.21.0+cu124` wheels stay findable — **the env is reproduced by
  freezing what works, not by re-resolving** (`.venv-ft` is painful to rebuild).
  Dev/test tooling (`pytest`) lives in `requirements-dev.txt`, kept *out* of the
  runtime lock. **Edit policy:** edit `requirements-ft.txt`, apply, then `make lock`.
- **Experiment tracking** — plain per-run **manifest files** (no MLflow/W&B daemon).
  `grounding/manifest.py` (stdlib-only) captures git SHA + dirty flag, the pinned
  `LLAMACPP_COMMIT`, the lockfile sha256, python/platform, and the run config, then
  writes `runs/<id>/manifest.json` + `run-card.md` (+ `results.json`). Provenance is
  plaintext and committed; multi-GB checkpoints under `runs/` are gitignored (see
  `.gitignore` negation block). **Every eval/train/export run writes a manifest.**
- **Testing** — `pytest` (`make test`). `tests/test_contract.py` locks the
  `GROUNDING_PROMPT` byte-identical and pins parser/metric behaviour;
  `tests/test_manifest.py` covers the manifest writer. The contract suite is the
  regression gate against prompt/parser/metric drift.
- **llama.cpp** — **pinned** to commit
  `57fe1f07c3b6a1de3f4fff19098e2056a85275b7` (recorded in `grounding/manifest.py` as
  `LLAMACPP_COMMIT` and stamped into every run manifest), so the −23pp Idefics3
  preprocessing fidelity gap is measured against a fixed backend.

## Experiment automation architecture

Each campaign has one Python script (`experiments/run_<campaign>.py`) that:

1. **Preflight** — SSH to the device, verify llama-bench binary and commit, check
   disk space, warn if clocks not locked.
2. **Model acquisition** — download via `wget -c` on the device if not present;
   verify with `sha256sum`.
3. **Benchmark loop** — for each `ModelSpec` in the script's `MODELS` list:
   - Start `tegrastats --logfile` in the background via SSH.
   - Run `llama-bench` (pp512 + tg128, then tg512 sustained).
   - Run `llama-completion` for a TTFT timing block.
   - Stop `tegrastats`; `scp` the log back to `results/raw/`.
4. **Parse + write** — `parsers.py` digests raw text into typed dataclasses
   (`BenchRow`, `TegrastatsSummary`, `LlamaCliTimings`, `LlamaLoadFootprint`);
   the script formats a Markdown result block and appends it to the campaign doc
   and a summary row to `RESULTS.md`.

`parsers.py` is side-effect-free (text in → dataclasses out) and has inline
`_test_*` functions runnable directly with `python experiments/parsers.py`.

**Key invariants in the parsers:**
- `TegrastatsSummary.swap_hit` measures *growth over the idle baseline*, not
  `swap > 0` — the device always carries a pre-existing zram baseline.
- `parse_llama_load_buffers` de-duplicates the probe/real pass double-count:
  model buffers accumulate, compute buffers last-wins per device, KV skips zeros.
- `parse_bench_csv` handles both the old `t/s = "14.61 ± 0.00"` format and the
  newer explicit `avg_ts`/`stddev_ts` column format.

## SITL follow stack (`experiments/sitl/`)

Four modules, built for Phase B (oracle closed-loop) and Phase C (VLM-in-the-loop), reused by Part III:

- **`oracle_bbox.py`** — perfect-perception upper bound. Converts SITL world-state (copter NED + attitude, rover NED) to pixel bounding boxes via a pinhole camera model (downward-facing, `FOV_H_DEG=60`, `IMG_W=640`, `IMG_H=480`). No ML; used as the free-label source for the 20 Hz tracker during T0c/T1+.
- **`bytetrack.py`** — simplified ByteTrack with a constant-velocity Kalman filter (8-D state: `[cx,cy,w,h,vx,vy,vw,vh]`) and two-round IoU matching. No appearance embedding — re-ID via appearance is constraint #2 (object permanence), not yet addressed here. Needs `numpy` + `scipy` → **run under `.venv-ft`**.
- **`cascade_pid.py`** — P-only cascade PID outer loop (image-plane error → body-frame velocity setpoints). Runs at tracker/oracle rate; autopilot handles attitude at 400 Hz.
- **`offboard.py`** — pymavlink state machine (`CONNECT → ARM → TAKEOFF → OFFBOARD → LAND`), sends `SET_POSITION_TARGET_LOCAL_NED` velocity-only at ~20 Hz. Needs `pymavlink` → **run with the project `.venv`** (pymavlink is installed there; it is NOT purely stdlib).

Unit tests for each: `python experiments/sitl/<module>.py` (inline `_test_*` functions, no pytest).

### Adding a new campaign

1. Write a `results/<date>-<campaign>/README.md` pre-registering RQs, controlled
   variables, and metrics (the *what/why*).
2. Create `experiments/run_<campaign>.py` by copying the closest existing script.
   Add `ModelSpec` entries to `MODELS`. The `ModelSpec` dataclass fields and the
   `run_unit` / `format_result_block` / `results_md_row` trio are the extension
   points.
3. Run with `--dry-run` first to verify the command strings and paths.
4. After a real run, commit raw logs + the updated campaign doc + `RESULTS.md` row
   together so the record stays atomic.

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
- tegrastats RAM **under-counts mmap'd weights** (demand-paged; pages not yet
  accessed won't be resident). Use `--no-mmap` + `parse_llama_load_buffers` for
  authoritative footprints, especially for models with shared weight matrices (e.g.
  Gemma MoE / PLE architectures).

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
- **Ask the user to install tools whenever a development or measurement need requires
  it.** Don't work around a missing tool (ffmpeg, cmake, python packages, apt packages)
  — state what is needed and why, then ask. The user can run `sudo apt install` or
  other package managers interactively. Always document which tool was installed and
  why in `DECISIONS.md`.
