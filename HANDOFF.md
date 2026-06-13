# HANDOFF — start the 10-model capability sweep

Everything is committed (`ed40fb6`) and ready. To run the sweep, open a **new Claude Code conversation in this repo**
(`/home/gara/jetson`) and paste the block below.

The sweep runs each model in its **own fresh, isolated session** (the launcher spawns one
`claude -p` per model). The conversation you paste into is just the **operator**: it
preflights, kicks off the launcher, and supervises — it does not run the benchmarks in its
own context. See `experiments/README.md` for why (cross-run isolation = experimental control).

---

## 📋 Copy-paste this into the new conversation

```
You are the operator for the 10-model Jetson capability sweep. Read these first:
- experiments/README.md         (isolated-session methodology)
- results/2026-06-13-model-capability-sweep.md  (design, RQs, hypotheses — do NOT edit its structure)
- experiments/campaigns/2026-06-13-model-capability-sweep/manifest.md  (the 10 units)

Then:
1. PREFLIGHT (do not skip): confirm `ssh jetson true` works; confirm
   `git -C ~/llama.cpp rev-parse --short HEAD` is 57fe1f0; confirm `df -h /` has room.
   If any fails, stop and tell me — do not improvise.
2. Launch the sweep:
       experiments/run-campaign.sh experiments/campaigns/2026-06-13-model-capability-sweep
   This runs units 01→10 sequentially, each in its OWN fresh isolated `claude -p` session.
   It skips any unit already DONE and HALTS on the first FAILED or BLOCKED unit.
3. SUPERVISE, do not interfere: each unit session does its own work and writes its own
   results (a row in RESULTS.md + a detail block in the campaign results file + raw logs in
   results/raw/). You do not run benchmarks yourself or edit unit results.
4. When the launcher stops, summarize: which units are DONE/FAILED/BLOCKED (read each card's
   `status:`), and for any FAILED/BLOCKED unit, surface the recorded reason. The 7–8B units
   (08,09,10) may legitimately OOM/swap — that is a valid result, not a bug; report it plainly.
5. Negative results are deliverables: never paper over an OOM, throttle, or error.

Constraints: this is a thesis lab notebook — follow CLAUDE.md. One variable changes across
units (the model); everything else is fixed by the run cards. Don't change power mode, quant,
or context. If something is ambiguous, ask me rather than guessing.
```

---

## What's already verified (so you don't have to wonder)

- **Device probed 2026-06-13:** binaries at `~/llama.cpp/build/bin/` (commit `57fe1f0`, need
  `LD_LIBRARY_PATH=~/llama.cpp/build/bin:/usr/local/cuda/lib64`); models in `~/models/`;
  device in 15 W (ID=0); NVMe ~196 GB free; `wget` works, `curl`/`pip`/`hf-cli` absent (cards
  use `wget`). All 10 GGUF URLs spider-checked OK. Unit 06 (Llama-3.2-3B) is already on disk.
- **Total download:** ~21 GB across 9 models (unit 06 local). Plan for download time on the
  big ones.

## Alternatives to the new-conversation route

- **Just run it in a terminal** (no operator conversation needed):
  ```bash
  cd /home/gara/jetson
  experiments/run-campaign.sh experiments/campaigns/2026-06-13-model-capability-sweep
  ```
- **One model at a time:**
  ```bash
  experiments/run-unit.sh experiments/campaigns/2026-06-13-model-capability-sweep/runcards/01-qwen2.5-0.5b-instruct.md
  ```

## Knobs

- `CLAUDE_MODEL` (default `sonnet` — ample for executing a run card; override e.g.
  `CLAUDE_MODEL=opus` if needed), `CLAUDE_PERM` (default `bypassPermissions` — hands-off, OK
  for this owned testbed; set `acceptEdits` to keep a human in the loop).
- Resume after a halt: fix the blocking issue, then re-run the same `run-campaign.sh` command —
  DONE units are skipped automatically.
