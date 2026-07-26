---
name: next-experiment
description: Run one experiment cycle end-to-end — audit the last result, pick the next RQ, pre-register it, spawn one executor subagent for the matrix, audit the handoff, merge to main. One experiment per invocation; invoke under /loop with no interval for an autonomous cadence.
---

# next-experiment

One experiment per invocation. **You (Opus) do the judgment; subagents do the reading and the
running.** Fable is no longer used anywhere in this loop: Opus 5 designs and audits at least as
well and costs ~2.5x less per agent (global CLAUDE.md rule 6 — `fable-5 $10.28` vs `opus-5
$4.10`). If a cycle ever wants Fable, the human asks for it explicitly.

North star: a Jetson Orin Nano system where a user says "follow that white car" / "switch to that
blue truck" over a drone video feed and the drone does it, end-to-end.

## Model tiering (global CLAUDE.md rule 6)

| Stage | Who | Model |
|---|---|---|
| status digest, ledger scan, results spot-check | subagent, read-only | `sonnet`, effort `high` |
| audit, pick the RQ, pre-register, verdict, merge | **you, never delegated** | inherited Opus |
| run the matrix | one subagent | inherited Opus (it must re-plan around a crashing rig) |

The rule is *what the stage's output authorizes*, not its position: anything that gates a
multi-hour GPU run stays on Opus and stays with you.

**Ultracode.** When the human says "ultracode", author the cycle as ONE `Workflow` script —
phases `Audit` (sonnet/low), `Design` (inherit), `Execute` (inherit), `Verify` (sonnet/low) —
instead of hand-spawned agents. Same division of labor, same files on disk, deterministic
control flow. Max 6 agents in the whole run. Without the keyword, plain `Agent` calls.

## 1 — Status (delegate the reading, don't dump it here)

Spawn ONE read-only `sonnet` agent (`Explore` or `caveman:cavecrew-investigator`). Ask for a
digest, not files: the last 2-3 `experiments/*/README.md` (Status, verdict, what broke, residuals
carried forward), the current Part's `docs/{questions,results,decisions}/part<N>-*.md` rows, and
the dead levers not to re-propose. Resolve the Part number from CLAUDE.md, never hardcode it.

You then `Read` only the specific files it points at. Raw logs and full ledgers never enter this
context (global CLAUDE.md rules 1-2).

If the human gave a theme this session, it *steers*; it does not override the data. Say so
plainly when the audit shows the binding constraint is elsewhere, then pick that instead.

## 2 — Audit, then pick ONE (you — never delegated)

Interrogate the last result before building on it:

- **Validity** — does the raw data support the stated verdict? Spot-check a `runs/*/results.json`
  when the claim is load-bearing. Marginal pass near a threshold? Under-powered n?
- **Gaps** — what config/speed/scenario was NOT tested that the conclusion silently assumes?
- **Bias** — rigged toward the fix? Same scene it was tuned on, oracle inputs, flattering sim?
- **Stale** — does an inherited number (ceiling, latency, accuracy) still hold after later changes?
- **Look at it** — where the prior claim is visual, open its committed `proof/` frames with the
  **Read** tool. Reading a README that says PASS is not auditing the pixels (CLAUDE.md "Look at it").

If the audit finds the result invalid or under-supported, the next experiment is the
**validation re-run**, not a new lever. Then pick the single highest-leverage falsifiable RQ:

- numeric pass/fail thresholds, stated before the run;
- **n >= 25 per arm** on every gating condition, thresholds as counts out of the real n
  ("`>= 19 of 25`"), plus the pre-registered minimum arm-to-arm separation. Cut conditions or
  clip length to fit, never n;
- target <= 1 h wall-clock, **hard cap 10 h**;
- record the losing candidate and why — that seeds the DECISIONS entry.

## 3 — Pre-register (you), before anything runs

`git checkout main && git pull`, then `experiments/YYYY-MM-DD-<slug>/README.md` on a fresh
`experiment/<slug>` branch. Follow CLAUDE.md's definition of done:

- Header: `**Pre-registered:** <Madrid wall-clock YYYY-MM-DDThh:mmZ>`, `**Status:** PRE-REGISTERED, not yet run.`
- `RQ-<id>`: one falsifiable question, thresholds as numbers.
- Context/rationale: why now, what the audit found, what alternative was rejected and why.
- Any load-bearing core module (the E20 `scope.py` pattern): write it WITH a runnable selfcheck,
  commit it now, mark the section "already committed — executor: do NOT edit."
- **Run matrix:** copy-pasteable commands with full flags, power mode, versions, which machine
  (SAM2/tracker work is Jetson-only; CARLA is the 3090), per-run `runs/<id>/` snapshot dirs,
  gotchas (outputs clobbered between runs → snapshot immediately). The commands must RECORD what
  the deliverables need — video where a clip is the point, `runs/*/results.json` where a figure is.
- **Visual verification** (any render/sim/camera/overlay work): the matrix dumps inspectable PNGs
  mid-run (never frame 0), the README names the exact files to open and what PASS looks like vs
  failure. Cheap asserts in the script: >99% one colour = failed render; byte-identical frames =
  dead feed.
- **Verdict rules** — mechanical, one per decision the executor could face, plus abort criteria
  (hang > T min / crash / missing file → snapshot, mark INVALID, continue).
- Estimates (runtime + expected numbers, labelled as estimates); empty `Results (TBD)` table with
  the exact columns.

Commit on the branch. `git status` clean before you spawn anything.

## 4 — Execute (ONE Opus subagent)

`subagent_type: "general-purpose"`, inherited Opus, fresh self-contained prompt: the README path,
"run its Run matrix step by step and fill Results only — do NOT re-design or edit committed core
code", report back verdict + Results table + `git log --oneline main..HEAD`. Include the git
trailer block with YOUR session URL.

**Paste this anti-stall rule VERBATIM** (five prior executors ended their turn to "wait" and
stalled — E19 x2, E20, E21, E22):

> The matrix takes hours. Do NOT end your turn to wait for it. Launch each run, then poll
> `runs/*/results.json` (or the run's log) in a FOREGROUND loop — `sleep` and re-check — until it
> completes, then continue straight through to filling Results, producing the proof deliverables
> (clips and/or `make_proof.py` figures), appending ledgers, and the final commit. Only end your
> turn when the branch is committed and clean or a run hit its README abort criteria. If you find
> yourself about to say "I'll wait for this to finish", you are stalling — poll instead.

If it stalls anyway, resume it with `SendMessage` repeating that rule — don't respawn.

## 5 — Audit the handoff (you)

A handoff gate, not a re-litigation of science you pre-registered:

- `git log --oneline main..HEAD`: pre-reg commit precedes harness/results commits; tree clean.
- Spot-check 3-4 `runs/*/results.json` against the Results table; reps are independent runs, not
  copies (near-deterministic under greedy decode — `t_lock` differs at ms level).
- Verdict = mechanical application of the FROZEN rules. No post-hoc bending. An ambiguous rule is
  a process failure: record it, stop, do not merge.
- **Open the proof frames yourself with the Read tool** before accepting any render/sim/overlay
  verdict. "PASS" over a black frame reads identically to a real one in text. No frame → INVALID.
- Ledgers appended under the CURRENT Part doc, never the root redirects. Madrid wall-clock. No emojis.
- 2-3 deliverables under `proof/`, COMMITTED and captioned — clip when the behaviour is the point,
  figure from a committed `make_proof.py` when the numbers are. `.gitignore` covers `data/` and
  `runs/*/overlay.mp4`; `results.json` is committed.
- Estimate-vs-actual filled; "what broke / what surprised" honest.

Missing anything, or the executor errored → STOP, do not merge, leave the branch, write what
happened in the README Status line, tell the human.

## 6 — Merge and report

- `git checkout main && git merge --no-ff experiment/<slug>` with a one-paragraph message stating
  verdict + mechanism (see the E17/E18 merge commits). Delete the branch. **NEVER push.**
- Update auto-memory only if the cycle changed something the repo does not record (a steer, a
  standing decision) — per-run numbers live in the ledgers, not in memory.
- Report verdict first, then mechanism, then the next lever. Send a proof clip with the file tool.

## Looping

Autonomous cadence = `/loop` with **no interval** (dynamic mode): one full cycle per wake, and
you schedule the next wake yourself when the cycle closes. That replaces the whole old
apparatus — `.claude/loop-budget`, `.claude/loop.log`, the A/B/C/D resume state machine, the cron
`flock` single-driver rules — which existed only to survive cron restarts and mid-cycle
rate-limit kills. `/loop` is the loop; stopping it stops the run.

A FAIL verdict still loops: negative results are thesis content, and the next cycle's Step 2
audit is what re-reviews the merged result.

## Rules

- One experiment per invocation. Judgment (audit, RQ, verdict, merge) is never delegated; reading
  and running always are.
- No unverified claims; estimates labelled as estimates. Timestamps `YYYY-MM-DDThh:mmZ` Madrid
  wall-clock, real hour.
- If the audit kills the premise, the "experiment" is the validation re-run.
