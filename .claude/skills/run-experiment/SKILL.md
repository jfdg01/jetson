---
name: run-experiment
description: Draft a pre-registered experiment yourself, then spawn ONE Opus subagent to execute the matrix while you keep judgment tokens. When it returns, audit, merge --no-ff to main, update memory, report. One experiment per invocation, no autonomous loop. Use this over next-experiment for the manual, human-in-the-loop cadence.
---

# run-experiment

The lightweight experiment loop: **you draft, a subagent executes, you audit + merge.**
One experiment per invocation. No budget counter, no `loop.log`, no auto-looping, no
design subagent — that's the heavier `next-experiment` skill. Use this when a human is
steering each experiment and just wants the matrix run off their plate.

North star: a Jetson Orin Nano system where a user says "follow that white car" / "switch
to that blue truck" over a drone video feed and the drone does it, end-to-end.

## Division of labor

| You (orchestrator, this conversation) | Opus executor subagent (one per invocation) |
|---|---|
| audit prior results, pick the RQ, write the pre-registered README + any load-bearing core module, commit on `experiment/<slug>`, spawn the executor, audit its handoff, **merge to `main`**, update memory, report | read the README, run the matrix, snapshot runs, fill Results, cut proof clips, append ledgers, commit on the branch, report back verdict + table + `git log --oneline main..HEAD` |

The executor never touches `main`, never pushes, never merges. It does mechanical work only.

## 1 — Draft (you)

Write `experiments/YYYY-MM-DD-<slug>/README.md` on a fresh `experiment/<slug>` branch off
clean `main`, following CLAUDE.md's "definition of done". Pre-register BEFORE any run:

- Header: `**Pre-registered:** <Madrid wall-clock YYYY-MM-DDThh:mmZ>`, `**Status:** PRE-REGISTERED, not yet run.`
- `RQ-<id>`: one falsifiable question, thresholds as numbers.
- Context/rationale: why now, what the audit of the last result found, what alternative you rejected and why.
- Any load-bearing core module (the E20 `scope.py` pattern): write it WITH a runnable selfcheck, commit it now, mark the section "already committed — executor: do NOT edit."
- Run matrix: exact copy-pasteable commands (full flags), power mode, versions, which machine / whether the Jetson is needed, per-run `runs/` snapshot dirs, gotchas (outputs clobbered between runs → snapshot immediately). Commands must RECORD whatever the 2–3 deliverables need — video for runs where a clip is the deliverable, and enough `runs/*/results.json` for a `make_proof.py` figure. Decide up front per deliverable: **clip if the behaviour is the point, statistical figure (matplotlib bar/line/scatter — per-clip IoU, acquire-latency, PASS rate, a sweep curve) if the numbers are the point.** A purely-quantitative campaign (offline gate, latency sweep) may be all figures.
- Verdict rules (mechanical — the executor does not deliberate): a rule for every decision it could face, plus abort criteria (hang > T min / crash / missing file → snapshot, mark INVALID, continue).
- Estimates (runtime + expected numbers, marked as estimates); empty Results (TBD) table with exact columns.

Commit the README (+ core module) on the branch. `git status` clean.

## 2 — Spawn the executor (Agent tool, model: "opus")

`subagent_type: "general-purpose"`, `model: "opus"`. Fresh context — the prompt is
self-contained. Give it: the README path, "run its Run matrix step by step and fill Results
only, do NOT re-design or edit committed core code", and to report back verdict + Results
table + `git log --oneline main..HEAD`. Include the git trailer block with YOUR session URL.

**Paste this anti-stall rule VERBATIM** (five prior executors ended their turn to "wait" and
stalled — E19 x2, E20, E21, E22):

> The matrix takes hours. Do NOT end your turn to wait for it. Launch each run, then poll
> `runs/*/results.json` (or the run's log) in a FOREGROUND loop — `sleep` and re-check —
> until it completes, then continue straight through to filling Results, producing the proof
> deliverables (clips and/or `make_proof.py` figures), appending ledgers, and the final commit. Only end your turn when the branch is
> committed and clean or a run hit its README abort criteria. If you find yourself about to
> say "I'll wait for this to finish", you are stalling — poll instead.

If it does stall, resume it with SendMessage repeating that rule — don't respawn.

## 3 — Audit its handoff (you)

Before merging (this is a handoff gate, you trust the science you pre-registered):

- `git log --oneline main..HEAD`: pre-reg commit precedes harness/results commits; working tree clean.
- Spot-check 3–4 `runs/*/results.json` against the README Results table (gen/cov/latency match; reps are independent, not copies — near-deterministic under greedy decode, t_lock differs only at ms level).
- Verdict = mechanical application of the FROZEN README rules, no post-hoc bending; regression guard actually evaluated per clip.
- Ledgers appended under the CURRENT Part (`docs/{results,questions,decisions}/partN-*.md`), NOT the root redirects; Madrid wall-clock timestamps; no emojis.
- Deliverables exist under `proof/` (clips and/or figures), COMMITTED, captioned in the README; figures come from a committed reproducible script, not hand-drawn.
- `.gitignore`: `data/` + `runs/*/overlay.mp4` (large video) ignored; `runs/*/results.json` committed.
- Estimate-vs-actual filled; "what broke / what surprised" honest.

If anything is missing or the executor errored: STOP, do not merge, leave the branch,
write what happened in the README Status line, tell the human.

## 4 — Merge, remember, report (you)

- `git checkout main && git merge --no-ff experiment/<slug>` with a one-paragraph message stating verdict + mechanism (see the E17/E18 merge commits for the pattern). Delete the branch. **NEVER push.**
- Update auto-memory if available: one `project-e<n>-<slug>.md` file + a MEMORY.md index line.
- Report to the human: verdict first, then mechanism, then the next lever. Send a proof clip via the file tool if you have one.

## Rules

- One experiment per invocation. No autonomous looping — the human invokes again for the next.
- You design + audit + merge; the executor does mechanical work only and never touches `main` or pushes.
- No unverified claims; estimates labelled as estimates. Timestamps `YYYY-MM-DDThh:mmZ` Madrid wall-clock, real hour.
- Negative/FAIL verdicts are thesis content — document and merge them the same as a PASS.
