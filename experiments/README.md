# Experiments — isolated-session execution methodology

This directory defines **how experiments are run**, not their results (those live in
`results/` and `RESULTS.md`). It is a **general, reusable methodology**: every campaign
in this testbed is decomposed into independent **units**, and **each unit is executed by a
freshly spawned, cold Claude session** that is given exactly enough context to act and
nothing more.

## Why isolated sessions (this is methodology, not just tooling)

Running each unit in a fresh session is an **experimental control**, and we treat it as one
in the thesis writeup:

- **No cross-run context contamination.** A long-lived session accumulates state — earlier
  models' numbers, earlier debugging, earlier mistakes — that can bias how it sets up,
  interprets, or "rounds" later runs. A cold session can't be primed by what it never saw.
- **Identical protocol, every time.** Each session is initialized from the same on-disk
  context (`CLAUDE.md` + one run card), so every unit follows the same steps by construction,
  not by the operator remembering to.
- **Reproducible & resumable.** The unit of work is a versioned file. Re-running a unit =
  re-spawning a session on the same card. A campaign can be stopped and resumed; failed units
  retried in isolation.
- **Context budget.** A 10-model sweep would blow a single session's context window. N small
  cold sessions each stay well within budget.

> **The repo filesystem is the message bus.** No session needs another session's memory.
> Inputs (run cards) and outputs (result blocks, `RESULTS.md` rows, raw logs) all pass
> through committed files. This is what makes "fresh context per experiment" actually work.

## The three layers

### 1. Standing context — auto-loaded, free

Every `claude` session started in this repo automatically loads:
- global `~/.claude/CLAUDE.md` (Python/venv rules),
- project `CLAUDE.md` (lab-notebook prime directive, device access via `ssh jetson`, scoped
  passwordless sudo, the mandatory per-run metric fields, decision-log format),
- `README.md` (device hardware survey).

A run card therefore only needs to carry the **experiment-specific delta**, not re-explain the
device or the conventions.

### 2. The run card — one self-contained work order per unit

One file per unit (one model, one config). Template: [`_template.runcard.md`](_template.runcard.md).
Frontmatter `status:` is the **single source of truth** for orchestration. The body must make
the unit executable from a cold start: objective, preconditions, exact commands, the
**output contract**, done criteria, failure handling, and **guardrails**.

Cards for a campaign live in `campaigns/<campaign>/`, named `NN-<slug>.md` so they
sort into run order.

### 3. Bootstrap + launcher — spawn the cold session

- [`bootstrap-prompt.md`](bootstrap-prompt.md) — the **constant** kickoff text. The only
  variable is which card (`{{RUNCARD}}`). It encodes the restrictions: do only this unit,
  capture failures, fulfil the output contract, then **STOP**; if anything is ambiguous, set
  `status: BLOCKED` and stop — **don't guess**.
- [`run-unit.sh`](run-unit.sh) — spawn one fresh `claude -p` session for one card.
- [`run-campaign.sh`](run-campaign.sh) — iterate a campaign's cards in order, each in its own
  fresh session, skipping `DONE`, halting on `FAILED`/`BLOCKED`. Resumable.

## Usage

```bash
# one unit, fresh session:
experiments/run-unit.sh experiments/campaigns/2026-06-13-model-capability-sweep01-qwen2.5-0.5b-instruct.md

# whole campaign, sequential, resumable (skips DONE, stops on FAILED/BLOCKED):
experiments/run-campaign.sh experiments/campaigns/2026-06-13-model-capability-sweep
```

Overridable env vars: `CLAUDE_MODEL` (default `sonnet`), `CLAUDE_PERM` (default
`bypassPermissions`).

### Permissions / autonomy note

Hands-off execution means the spawned session runs `ssh`, `llama-bench`, and file writes
without a human approving each call, so the launcher defaults to
`--permission-mode bypassPermissions`. This is acceptable **only** because this is the
operator's own dedicated testbed device with a scoped sudo allowlist (see `DECISIONS.md`).
For a tighter setup, set `CLAUDE_PERM=acceptEdits` and pass an explicit `--allowedTools`
allowlist instead. Never point this at an untrusted repo or device.

## Authoring a new campaign

1. Pre-register the design in `results/<date>-<campaign>.md` (RQs, controlled variables,
   metrics) — the *what/why*.
2. Create `campaigns/<campaign>/` and write one card per unit from
   `_template.runcard.md` — the *how*, concretized (exact commands, exact model, exact
   output paths). Keep one variable changing across cards.
3. Run with `run-campaign.sh`. Each card's session appends its result to `RESULTS.md` and a
   detail block to the campaign's `results/*.md`, then sets its own `status:`.

## Lifecycle of a unit `status:`

```
TODO ──▶ RUNNING ──▶ DONE        (success: results written, RESULTS.md row appended)
                └──▶ FAILED      (ran, but errored/OOM/throttle — negative result written)
                └──▶ BLOCKED     (precondition unmet/ambiguous — session stopped without guessing)
```

`FAILED` and `BLOCKED` are first-class outcomes — a `FAILED` unit must still leave a documented
negative result behind (prime directive: never silently drop a failure).
