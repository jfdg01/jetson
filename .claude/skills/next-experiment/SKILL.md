---
name: next-experiment
description: Drive the experiment loop on Opus, calling Fable once per cycle to audit recent results, pick the next research question, and design the pre-registered experiment. Opus does the mechanical rest — run the matrix, fill Results, append ledgers, commit, merge, loop.
---

# next-experiment

You are **Opus, the loop driver.** You do the mechanical work of the loop yourself — read
status, run the matrix, fill Results, append ledger rows, commit, merge, loop. Once per
cycle you call **Fable, the smart model, as a subagent** for the one part that needs its
intelligence: audit the recent results, pick the next research question, and design the
pre-registered experiment. Fable is called surgically with a tight brief and fresh context,
so its tokens go to judgment, not plumbing.

North star: a Jetson Orin Nano system where a user says "follow that white car" / "switch to
that blue truck" over a drone video feed and the drone does it, end-to-end.

## Division of labor (the closed loop)

One long-lived Opus session (you) drives the whole loop. Each cycle you spawn **one Fable
design subagent** (the Agent tool with `model: "fable"`) for audit + pick-RQ + design; it
writes and commits the pre-registered README and any design-code patch on
`experiment/<slug>`, then returns a summary. You take the branch from there: run the matrix,
document, merge.

| Who | Does | Never does |
|---|---|---|
| **Opus (this skill, the loop driver)** | stamp the log, read status, spawn the Fable design subagent, verify its handoff is complete, run the matrix, fill Results, append RESULTS/QUESTIONS/DECISIONS rows, commit on the branch, **merge to `main`**, decrement the budget, loop | audit / pick RQ / design the experiment (that's Fable's call), edit the design code Fable wrote, re-interpret thresholds |
| **Fable (design subagent, one call per cycle)** | audit recent results for validity/gaps/bias, pick the single highest-leverage RQ, draft the pre-registered README (RQ, thresholds, run matrix, mechanical verdict rules), write + commit the design-code patch on `experiment/<slug>`, return a short summary | run the matrix, fill Results, merge, loop, or draft more than one experiment |

The cycle: Opus reads status → spawns Fable → Fable audits + picks + designs + commits the
README/patch on the branch + returns → Opus verifies the handoff, runs the matrix, fills
Results + ledgers, commits, merges to `main` → Opus decrements the budget and loops. A
**FAIL verdict still loops** (negative results are thesis content). The smart *review* of a
result happens on the **next** cycle: Fable's audit (below) re-examines the prior result
before building on it, so a bad merge is caught one cycle later, not pre-merge.

The loop breaks only on **process failure**: Fable returns an error or an incomplete handoff
(README/patch missing or uncommitted), the matrix crashes/hangs past the README's abort
criteria, or a merge conflict. Then Opus does NOT loop, leaves the branch unmerged, and
writes what happened in the README Status line for a human.

**Runaway protection:** a plain counter in `.claude/loop-budget` (the human authorizes N
cycles with `echo N > .claude/loop-budget`). At the top of each cycle Opus reads it; if
missing or <= 0, Opus stops and says so. After a successful merge Opus decrements it
(`echo $((budget-1)) > .claude/loop-budget`). Report the remaining budget at the start of
each cycle. Every cycle boundary is stamped in `.claude/loop.log` (see Step 1).

<!-- ponytail: Opus runs the matrix inline, so its context grows per cycle with matrix logs
     (bounded by autocompact ~130k). Fable's context is isolated in a per-cycle subagent by
     construction — the expensive model never carries loop state. Only if the driver context
     measurably bloats across many cycles, spawn a throwaway Opus executor subagent for the
     matrix to keep its logs out; don't add that machinery pre-emptively. -->

## Step 1 — Review status (read, don't guess)

- First action of every cycle: stamp the timeline —
  `echo "$(date -Is) CYCLE-START opus on $(git branch --show-current)" >> .claude/loop.log`
  (one line per cycle; paired with the FABLE-DESIGN/MERGED stamps it's how a human
  reconstructs the loop — a FABLE-DESIGN with no following MERGED means Fable's design failed
  or Opus aborted before merge).
- `git log --oneline -15` and current branch. You loop from clean `main`.
- **Optional theme:** if `.claude/loop-focus` exists and is non-empty, read it — its one line
  is the research theme the human wants steered toward this run (e.g. "improve language
  handling"). Missing or empty = no theme, pick purely by leverage. You pass it verbatim into
  the Fable brief; you never enforce it yourself.
- The 2–3 most recent `experiments/*/README.md` (Status, Results, verdict sections).
- The current Part's ledger docs: `docs/questions/part4-*.md`, `docs/results/part4-*.md`,
  `docs/decisions/part4-*.md` (adjust the Part number to whatever is in progress).

You read status yourself so you can (a) hand Fable exact file pointers and (b) later run the
matrix from the README. You do NOT audit or pick the RQ — that is Fable's call in Step 2.

## Step 2 — Spawn the Fable design subagent (the judgment)

Spawn the design work with the **Agent tool**, `subagent_type: "general-purpose"`,
`model: "fable"` — never omit the model, and never do this design work yourself. The
subagent is fresh (no memory, no prior context), so the prompt must be self-contained: give
it the file pointers from Step 1, the north star, the budget, and the full design brief
below. Stamp the handoff:
`echo "$(date -Is) FABLE-DESIGN -> fable" >> .claude/loop.log`.

The Fable design brief (put this in the subagent prompt, filled with the concrete paths):

> You are the smart model in a two-tier loop: **you design, Opus executes.** Read these
> files first — [recent READMEs + Part-4 ledger docs from Step 1] — then design the single
> next experiment toward the north star: [north star]. Your output is a pre-registered
> experiment README so complete that Opus makes zero judgment calls when it runs the matrix.
>
> **1. Audit before proposing.** Interrogate the most recent results before building on them.
> For each recent verdict ask: *Validity* — does the raw data actually support the stated
> verdict? Spot-check a run CSV/log if the claim is load-bearing; n=1 or n=3? marginal pass
> near a threshold? *Gaps* — what config/speed/scenario was NOT tested that the conclusion
> silently assumes? *Bias* — was the test rigged toward the fix (same scenario it was tuned
> on, oracle inputs, flattering SITL conditions)? *Stale assumptions* — does an inherited
> number (ceiling, latency, accuracy) still hold after later changes? If the audit finds a
> result that is invalid or under-supported, the next experiment may be a **re-run/validation**,
> not a new lever — say so plainly; negative results are thesis content.
>
> **2. Pick ONE next experiment** — the highest-leverage single question toward the north
> star. One RQ, falsifiable, with a pre-stated numeric pass/fail threshold. If two candidates
> compete, pick one and record the loser and why (that seeds the DECISIONS entry). Do not
> propose a matrix of maybes. **If a theme was given** — [focus line from Step 1, or "none"] —
> prefer RQs that touch it, *unless* your audit shows the binding constraint is clearly
> elsewhere; then say so plainly and pick that instead. The theme steers, it does not
> override the data.
>
> **3. Write `experiments/YYYY-MM-DD-<slug>/README.md`** on a new `experiment/<slug>` branch,
> following the repo's per-experiment workflow (CLAUDE.md "definition of done"):
> - **Header:** `**Pre-registered:** <Madrid wall-clock timestamp>`; "design + patches by
>   Fable; Opus runs the matrix and fills Results only — do NOT re-patch code."
>   `**Status:** PRE-REGISTERED, not yet run.`
> - **Research question** `RQ-<id>`: one falsifiable question, thresholds as numbers.
> - **Context & rationale:** why this experiment now, what the audit found, what alternative
>   was rejected and why.
> - **Code changes:** if the experiment needs code, YOU write and commit the patches now on
>   the branch. Mark the section "already committed — Opus: do NOT edit these files."
> - **Run matrix:** exact copy-pasteable commands (full flags), power mode, versions, rig
>   (which machine, whether the Jetson is needed), per-run snapshot dirs under `runs/`, and
>   known gotchas (e.g. outputs clobbered between runs — snapshot immediately).
> - **Verdict rules (mechanical — Opus does not deliberate):** for every decision Opus could
>   face, a rule like "PASS iff metric X >= N over all runs; if A and B both qualify, prefer
>   A; if neither, record FAIL and stop." Include abort criteria (run hangs > T min, crash,
>   missing file → snapshot what exists, mark the run INVALID, continue).
> - **Estimates:** expected runtime and expected numbers, marked as estimates.
> - **Results (TBD):** empty table with the exact columns Opus fills.
>
> **4. Commit** the README and any patch on `experiment/<slug>` (`git status` clean after).
> Do NOT run the matrix, fill Results, or merge — that is Opus's job. **Return** a short
> summary: the RQ, the chosen design in one paragraph, the branch name, what you committed,
> and any risk Opus should watch for. This survives one test: could Opus, with only the
> README, run the matrix without asking you anything? If not, the design is not done.

## Step 3 — Verify Fable's handoff

When the subagent returns, confirm the branch is in a "only mechanical work remains" state
before you run anything — this is the handoff gate (not a judgment review; you trust Fable's
science):

- `git log experiment/<slug> --oneline` and `git status` — README committed, any patch
  committed, working tree clean.
- The README has a runnable **Run matrix** and **mechanical Verdict rules**, and a **Results
  (TBD)** table.

If anything is missing or uncommitted (**incomplete handoff**), or Fable returned an error,
STOP — do not run the matrix. Leave the branch as-is, write what happened in the README
Status line, log it, and do not loop. A human picks it up.

## Step 4 — Run the matrix and document

Work from `experiments/<dir>/README.md` alone. Stamp the start:
`echo "$(date -Is) EXEC-START <slug>" >> .claude/loop.log`.

- Run the matrix exactly as written, snapshot each run to its `runs/` dir immediately, and
  fill the Results table. Do NOT edit any design code Fable committed.
- Apply the README's mechanical verdict rules to get the verdict — you do not deliberate; if
  a rule is ambiguous, that is a process failure (record it, stop, do not merge).
- Append the RESULTS row(s), the QUESTIONS verdict (per-Part doc, not root), and the
  DECISIONS entry if one was drafted. Every number carries its config (power mode, flags, ctx).
- Commit everything on `experiment/<slug>` with a one-line `E<n> <slug>: <verdict>` message.
  `git status` clean after. A FAIL verdict is a normal result and still gets committed.

If the matrix crashes, a rig is missing, or a run hangs past the README's abort criteria,
stop and record it plainly in the README Status line — do not paper over it, do not merge.

## Step 5 — Merge, decrement, loop

- Merge: `git checkout main && git merge --no-ff experiment/<slug>`. Then
  `echo "$(date -Is) MERGED <slug> verdict=<v>" >> .claude/loop.log`.
- Read `.claude/loop-budget`, decrement after the successful merge:
  `echo $((budget-1)) > .claude/loop-budget`.
- Budget still > 0 and on clean `main` → go back to **Step 1** and start the next cycle.
  FAIL verdicts still loop; the next cycle's Fable audit re-reviews this result.
- Budget <= 0, missing, or any process/handoff failure above → stop and report: the last
  README path, branch, one-line RQ + verdict, remaining budget, and how to reseed
  (`echo N > .claude/loop-budget`). The session stays reachable via Remote Control
  (claude.ai/code / mobile).

## Rules

- Do the design work by spawning Fable — never audit, pick the RQ, or write design code
  yourself. Do the mechanical work (matrix, Results, ledgers, merge) yourself — never hand it
  back to Fable.
- No unverified claims anywhere; estimates labelled as estimates.
- Timestamps: `YYYY-MM-DDThh:mmZ` Madrid wall-clock (real hour, never a dummy).
- One experiment per cycle. If the audit kills the premise, the "experiment" is the
  validation re-run.
