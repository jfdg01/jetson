# Experiments — isolated-session execution methodology

> **STATUS 2026-07-21T18:05Z — historical, for the Part-I campaigns only.** The
> cold-session card runner described below was **never built**: `run-unit.sh` and
> `run-campaign.sh` do not exist and no commit ever added them (the Part-I campaigns were
> driven by hand). The *methodology* section is real and is thesis content — it is the
> control that later became the `next-experiment` skill and `scripts/autoresearch.py`. The
> *usage* section is a specification of a tool that was never written. Kept rather than
> deleted because the design is cited by the thesis section on multi-agent development
> (REMEDIATION R-11); do not follow it as instructions.
>
> Current experiment loop: `.claude/skills/next-experiment/SKILL.md`. Current ledger rules:
> `CLAUDE.md`. Where the two disagree with anything below, they win.

This directory defines **how experiments are run**, not their results (those live in
`experiments/` and `RESULTS.md`). It is a **general, reusable methodology**: every campaign
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
- `run-unit.sh` — **never written.** Was to spawn one fresh `claude -p` session for one card.
- `run-campaign.sh` — **never written.** Was to iterate a campaign's cards in order, each in
  its own fresh session, skipping `DONE`, halting on `FAILED`/`BLOCKED`, resumable.

## Usage — SPECIFICATION ONLY, THESE COMMANDS DO NOT RUN

Neither script exists on disk. The block below is the interface that was designed and never
implemented; it is left as a record of the design, not as something to copy-paste. (The
one-unit line is additionally malformed — it is missing the `/` before `01-qwen2.5`, which is
itself evidence it was never executed.)

```bash
# one unit, fresh session:
runners/run-unit.sh runners/campaigns/2026-06-13-model-capability-sweep/01-qwen2.5-0.5b-instruct.md

# whole campaign, sequential, resumable (skips DONE, stops on FAILED/BLOCKED):
runners/run-campaign.sh runners/campaigns/2026-06-13-model-capability-sweep
```

Overridable env vars, as designed: `CLAUDE_MODEL` (default `sonnet`), `CLAUDE_PERM` (default
`bypassPermissions`).

### Permissions / autonomy note

Hands-off execution means the spawned session runs `ssh`, `llama-bench`, and file writes
without a human approving each call, so the launcher defaults to
`--permission-mode bypassPermissions`. This is acceptable **only** because this is the
operator's own dedicated testbed device with a scoped sudo allowlist (see `DECISIONS.md`).
For a tighter setup, set `CLAUDE_PERM=acceptEdits` and pass an explicit `--allowedTools`
allowlist instead. Never point this at an untrusted repo or device.

## Authoring a new campaign

1. Pre-register the design in `experiments/<date>-<campaign>.md` (RQs, controlled variables,
   metrics) — the *what/why*.
2. Create `campaigns/<campaign>/` and write one card per unit from
   `_template.runcard.md` — the *how*, concretized (exact commands, exact model, exact
   output paths). Keep one variable changing across cards.
3. Run the cards. (`run-campaign.sh` was the intended driver and does not exist — the Part-I
   campaigns were run by hand; today this is the `next-experiment` skill's job.) Each card's
   session appends its result row to the **per-Part ledger doc**, `docs/results/part<N>-*.md`
   — never to `RESULTS.md`, which is a thin redirect index — plus a detail block to the
   campaign's `experiments/*.md`, then sets its own `status:`.

## Lifecycle of a unit `status:`

```
TODO ──▶ RUNNING ──▶ DONE        (success: results written, RESULTS.md row appended)
                └──▶ FAILED      (ran, but errored/OOM/throttle — negative result written)
                └──▶ BLOCKED     (precondition unmet/ambiguous — session stopped without guessing)
```

`FAILED` and `BLOCKED` are first-class outcomes — a `FAILED` unit must still leave a documented
negative result behind (prime directive: never silently drop a failure).
