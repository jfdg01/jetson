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

One long-lived Fable session drives the whole loop. It executes each experiment by
spawning an **Opus executor subagent** (the Agent tool with `model: opus`), not by
opening terminals. The subagent runs in fresh context, so its matrix logs stay out of
Fable's context — only its final summary returns. Fable then **reviews that summary and
the branch, and merges** — this is the point of the redesign: the drafter sees the
executor's output and catches mistakes before anything lands on `main`.

| Who | Does | Never does |
|---|---|---|
| **Fable (this skill, the loop driver)** | audit, pick RQ, write/commit design patches on `experiment/<slug>`, commit the pre-registered README, spawn the Opus executor subagent, **review its returned work, merge to `main`**, then loop to the next experiment | run the matrix, fill Results |
| **Opus executor (subagent)** | run matrix, snapshot runs, fill Results, append RESULTS/QUESTIONS/DECISIONS ledger rows, commit on `experiment/<slug>`, return a summary of what it did and any problems | edit design code, re-interpret thresholds, merge to `main`, draft the next experiment |

The cycle: Fable pre-registers → spawns Opus subagent → subagent executes + documents +
commits on the branch + returns → Fable reviews + merges → Fable loops to the next
experiment in the same session. An experiment **FAIL verdict still loops** (negative
results are thesis content). The loop breaks only on **process failure**: the subagent
crashes/returns an error, a merge conflict, or an incomplete closeout — then Fable does
NOT loop, leaves the branch unmerged, and writes what happened in the README Status line
for a human.

**Runaway protection:** a plain counter in `.claude/loop-budget` (the human authorizes N
cycles with `echo N > .claude/loop-budget`). At the top of each cycle Fable reads it; if
missing or <= 0, Fable stops and says so. After a successful merge Fable decrements it
(`echo $((budget-1)) > .claude/loop-budget`). No process/PID policing is needed — a
failed subagent returns an error and Fable stops, so there is no way to pile up runaway
terminals. Every cycle boundary is stamped in `.claude/loop.log` (see Step 1). Report the
remaining budget at the start of each cycle.

<!-- ponytail: whole loop in one session; Fable's context grows per cycle (bounded — only
     the executor's final summary returns, not its logs) and autocompact (~130k) summarizes
     it across cycles. Add explicit context handoff only if that actually bites. -->


## Step 1 — Review status (read, don't guess)

- First action of every cycle: stamp the timeline —
  `echo "$(date -Is) CYCLE-START fable on $(git branch --show-current)" >> .claude/loop.log`
  (one line per cycle; paired with the HANDOFF/MERGED stamps it's how a human reconstructs
  the loop next morning — a HANDOFF with no following MERGED means the executor subagent
  died or was rejected at review).
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
- **Closeout checklist for the executor subagent** (copy this verbatim into the README —
  the executor works from the README alone; it commits on the branch and returns, it does
  NOT merge or loop):
  0. First action, before running anything:
     `echo "$(date -Is) EXEC-START <slug>" >> .claude/loop.log`
  1. Fill Results here.
  2. Append RESULTS row(s), QUESTIONS verdict (per-Part doc, not root), DECISIONS entry if
     drafted here.
  3. Commit everything on `experiment/<slug>` with a one-line `E<n> <slug>: <verdict>`
     message. `git status` must be clean after. Do NOT merge to `main` — that is Fable's
     review gate.
  4. Return a short summary: the verdict, the key numbers, and anything that went wrong or
     needed a judgment call (INVALID runs, aborts, surprises). This is what Fable reviews.
  If any step fails (crash, missing rig, run hangs past the README's abort criteria),
  stop and return what happened plainly — do not paper over it. FAIL verdicts are a normal
  result and still get committed; a broken *process* is what you report as a problem.

## Step 5 — Hand off: spawn the Opus executor subagent

Before spawning, verify your own side is clean: pre-registration README and patches
committed on `experiment/<slug>`, `git status` clean. You hand the executor a repo where
the only remaining work is mechanical. Stamp the handoff:
`echo "$(date -Is) HANDOFF <slug> -> opus executor" >> .claude/loop.log`.

Spawn the executor with the **Agent tool**, `subagent_type: "general-purpose"`,
`model: "opus"` (fresh context so its matrix logs don't fill yours; only its final
summary returns). Never omit the model. The **prompt** is a self-contained handoff — it
must need zero clarification:

> Open `experiments/<dir>/README.md` and work from it alone. Run the matrix exactly as
> written, fill Results only, do NOT edit any design code. Then complete the "Closeout
> checklist for the executor subagent" in that README: fill Results, append the
> RESULTS/QUESTIONS/DECISIONS ledger rows, commit everything on `experiment/<slug>` with a
> one-line `E<n> <slug>: <verdict>` message. Do NOT merge to main. Return a short summary:
> verdict, key numbers, and anything that went wrong or needed a judgment call.

## Step 6 — Review, merge, and loop

When the subagent returns, YOU review its work before anything lands on `main` — this is
the whole point of the redesign:

- Read the returned summary. Then `git log experiment/<slug> --oneline` and
  `git diff main...experiment/<slug>` — sanity-check that Results, ledger rows, and the
  verdict match the README's verdict rules and the raw runs. Spot-check a run CSV/log if a
  claim is load-bearing.
- **Sound** → merge: `git checkout main && git merge --no-ff experiment/<slug>`. Then
  `echo "$(date -Is) MERGED <slug> verdict=<v>" >> .claude/loop.log`.
- **Fixable documentation mistake** (wrong ledger row, missed a column) → you may fix it
  yourself on the branch and re-commit; never re-run the matrix or edit design code.
- **Process failure** (subagent errored, merge conflict, incomplete closeout, a claim the
  raw data doesn't support) → STOP: leave the branch unmerged, write what happened in the
  README Status line, log it, and do not loop. A human picks it up.

Then loop, in this same session:

- Read `.claude/loop-budget`. Decrement it after the successful merge:
  `echo $((budget-1)) > .claude/loop-budget`.
- Budget still > 0 and on clean `main` → go back to **Step 1** and draft the next
  experiment. FAIL verdicts still loop.
- Budget <= 0, missing, or any process failure above → stop and report: the last README
  path, branch, one-line RQ + verdict, remaining budget, and how to reseed
  (`echo N > .claude/loop-budget`). The session stays reachable via Remote Control
  (claude.ai/code / mobile).

Do not run the matrix yourself unless the user asks.

## Rules

- No unverified claims anywhere in the draft; estimates labelled as estimates.
- Timestamps: `YYYY-MM-DDThh:mmZ` Madrid wall-clock (real hour, never a dummy).
- One experiment per cycle. If the audit kills the premise, the "experiment" is the
  validation re-run.
- The executor's job must survive this test: could a model with no context beyond the README
  complete it without asking anything? If not, the draft is not done.
