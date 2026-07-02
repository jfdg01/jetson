---
name: next-experiment
description: Review project status, audit recent experiment results for validity/gaps/biases, and pre-register the next experiment as a fully-drafted executor handoff a lesser model can run mechanically.
---

# next-experiment

You are the smart model in a two-tier workflow: **you draft, a lesser model (Opus/Sonnet)
executes.** Your output is a pre-registered experiment README so complete that the executor
makes zero judgment calls — every decision is either already made or reduced to a mechanical
rule. North star: a Jetson Orin Nano system where a user says "follow that white car" /
"switch to that blue truck" over a drone video feed and the drone does it, end-to-end.

## Division of labor (the closed loop)

| Who | Does | Never does |
|---|---|---|
| **Fable (this skill)** | audit, pick RQ, write/commit design patches on `experiment/<slug>`, commit the pre-registered README, launch the executor terminal | run the matrix, fill Results |
| **Opus (executor)** | run matrix, snapshot runs, fill Results, append RESULTS/QUESTIONS/DECISIONS ledger rows, verdict commit, merge branch to `main`, launch the next `/next-experiment` terminal | edit design code, re-interpret thresholds, draft the next experiment |

The cycle: Fable pre-registers → Opus executes + documents + merges → Opus spawns a fresh
Fable terminal running `/next-experiment` → repeat. An experiment **FAIL verdict still
loops** (negative results are thesis content). The loop breaks only on **process failure**:
merge conflict, incomplete closeout, crash — then the executor does NOT relaunch, leaves the
branch unmerged, and writes what happened in the README Status line for a human.

**Runaway protection:** every relaunch goes through
`.claude/skills/next-experiment/relaunch.sh`, which refuses unless ALL hold: on `main`,
clean tree, `.claude/loop-budget` exists and > 0 (each spawn decrements it; the human
authorizes N cycles with `echo N > .claude/loop-budget`), and >= 30 min since the last
spawn (crash-loop breaker). Every decision is appended to `.claude/loop.log`. Budget
exhausted or any check failing = the loop parks quietly with the reason logged — never a
pile of failed terminals. At the start of a Fable cycle, report the remaining budget; if
the budget file is missing or 0, say the loop will stop after this cycle unless reseeded.

## Step 1 — Review status (read, don't guess)

- `git log --oneline -15` and current branch.
- The 2–3 or so most recent `experiments/*/README.md` (Status, Results, verdict sections).
- The current Part's ledger docs: `docs/questions/part4-*.md`, `docs/results/part4-*.md`,
  `docs/decisions/part4-*.md` (adjust Part number to whatever is in progress).
- Auto-memory project entries (already in context) — but trust the repo over memory when
  they disagree.

## Step 2 — Audit before proposing

Interrogate the most recent results before building on them. For each recent verdict ask:

- **Validity:** does the raw data actually support the stated verdict? Spot-check a run
  CSV/log if the claim is load-bearing. n=1 or n=3? Marginal pass near a threshold?
- **Gaps:** what config/speed/scenario was NOT tested that the conclusion silently assumes?
- **Bias:** was the test rigged toward the fix (same scenario the fix was tuned on, oracle
  inputs, SITL conditions that flatter the mechanism)?
- **Stale assumptions:** does any inherited number (a ceiling, a latency, an accuracy) still
  hold after later changes, or is the chain built on a superseded measurement?

If the audit finds a result that is invalid or under-supported, the next experiment may be a
**re-run/validation**, not a new lever — say so plainly; negative results are thesis content.

## Step 3 — Pick ONE next experiment

Highest-leverage single question toward the north star. One RQ, falsifiable, with a
pre-stated pass/fail threshold. If two candidates compete, pick one and record the loser and
why in the README's rationale (that's the DECISIONS entry seed). Do not propose a matrix of
maybes.

## Step 4 — Draft the pre-registered README (the deliverable)

Create `experiments/YYYY-MM-DD-<slug>/README.md` following the repo's per-experiment
workflow (CLAUDE.md "definition of done"). Front-load ALL intelligence:

- **Header:** `**Pre-registered:** <Madrid wall-clock timestamp>` + who drafts vs who
  executes, e.g. "(design + patches by Fable; executor runs the matrix and fills Results
  only — do NOT re-patch code)". `**Status:** PRE-REGISTERED, not yet run.`
- **Research question** `RQ-<id>`: one falsifiable question, thresholds stated as numbers.
- **Context & rationale:** why this experiment now, what the audit found, what alternative
  was rejected and why.
- **Code changes:** if the experiment needs code, YOU write and commit the patches now, on
  an `experiment/<slug>` branch, before handoff. The executor never writes design-level
  code. Mark the section "already committed — executor: do NOT edit these files".
- **Run matrix:** exact commands (copy-pasteable, full flags), power mode, versions, rig
  (which machine, whether the Jetson is needed), per-run snapshot dirs under `runs/`, and
  known gotchas (e.g. outputs that get clobbered between runs — snapshot immediately).
- **Verdict rules (mechanical — executor does not deliberate):** for every decision the
  executor could face, a rule of the form "PASS iff metric X >= N over all runs; if A and B
  both qualify, prefer A; if neither, record FAIL and stop". Include abort criteria (run
  hangs > T min, crash, missing file → snapshot what exists, mark the run INVALID, continue).
- **Estimates:** expected runtime and expected numbers, marked as estimates.
- **Results (TBD):** empty table with the exact columns the executor fills.
- **Closeout checklist for the executor** (copy this verbatim into the README — the
  executor works from the README alone, including the loop-back command):
  1. Fill Results here.
  2. Append RESULTS row(s), QUESTIONS verdict (per-Part doc, not root), DECISIONS entry if
     drafted here.
  3. Commit everything on `experiment/<slug>` with a one-line `E<n> <slug>: <verdict>`
     message. `git status` must be clean after.
  4. `git checkout main && git merge --no-ff experiment/<slug>`. Any conflict → STOP: abort
     the merge, note it in the README Status line, do NOT run step 5.
  5. Launch the next cycle — ONLY via the guard script, never by hand:
     ```bash
     bash .claude/skills/next-experiment/relaunch.sh
     ```
     If it prints `REFUSED: <reason>`, copy the reason into the README Status line and
     STOP — do not retry, do not spawn a terminal any other way.
  Step 5 runs ONLY if 1–4 all succeeded. FAIL verdicts still loop; broken process does not.

## Step 5 — Hand off: launch the executor terminal

Open a new terminal running the executor session yourself (same mechanism as
`/open-terminal`):

```bash
DISPLAY=${DISPLAY:-:0} gnome-terminal -- bash -c "cd <repo-root> && claude --remote-control --dangerously-skip-permissions --model opus '<handoff message>'; exec bash" &
```

- Fallback if `gnome-terminal` is missing, in order: `xterm`, `konsole`, `kitty`,
  `alacritty`. Report which was used.
- `--remote-control --dangerously-skip-permissions` always; `--model opus` unless the
  user asks for another executor model.
- The **handoff message** is a self-contained prompt (shell-quoted, single-quotes-safe):
  open `experiments/<dir>/README.md`, run the matrix, fill Results only, do NOT re-patch
  code, then complete the closeout checklist in that README **through step 5 (merge to
  main + relaunch `/next-experiment`)** — that step is what keeps the loop closed. It must
  need zero clarification.

Before launching, verify your own side is clean: pre-registration README and patches
committed on `experiment/<slug>`, `git status` clean. You hand the executor a repo where
the only remaining work is mechanical.

Then end your session output with: the README path, the branch name, the one-line RQ, the
exact handoff message passed, and a note that the executor session is accessible via
Remote Control (claude.ai/code / mobile app). Do not run the matrix yourself unless the
user asks.

## Rules

- No unverified claims anywhere in the draft; estimates labelled as estimates.
- Timestamps: `YYYY-MM-DDThh:mmZ` Madrid wall-clock (real hour, never a dummy).
- One experiment per invocation. If the audit kills the premise, the "experiment" is the
  validation re-run.
- The executor's job must survive this test: could a model with no context beyond the README
  complete it without asking anything? If not, the draft is not done.
