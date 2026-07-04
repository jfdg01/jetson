# HANDOFF: acquire-latency arc (E18 -> E22), written 2026-07-04T12:15Z

This file is the entry point for a FRESH orchestrator conversation (any capable
model) to continue the Part-IV acquire-latency arc. It records the loop mechanics
and the current state; the per-campaign READMEs are the source of truth for each
campaign. Delete this file when the arc is closed out (fold anything still relevant
into the ledgers first).

## The arc in one paragraph

On real UAV123 video under honest wall-clock frame-drop replay, the ~4.85 s blocking
full-frame VLM acquire lands STALE — the target moves ~146 frames during it (E18,
1/6 PASS; carry itself is fine, oracle 6/6). Bolt-on motion compensation failed
(E19). Cutting acquire latency via a location-prior crop works: an operator-phrase
3x3-cell crop cut acquire to 1.57-2.07 s and flipped 3/6 clips (E20, PARTIAL
[hint-fragile] — a WRONG hint makes the VLM hallucinate in the empty crop and the
garbage lock poisons the mask-gate template). Remaining questions: can the hint be
automated by a coarse VLM pass (E21, drafted) or a ~free CPU motion+colour prior
(E22, drafted)?

## State right now (2026-07-04T12:15Z)

| campaign | dir (`experiments/`) | status |
|---|---|---|
| E18 real-video-replay | `2026-07-03-real-video-replay/` | COMPLETE, merged `e2343a8` |
| E19 motion-comp-acquire | `2026-07-04-motion-comp-acquire/` | COMPLETE, merged `18b90fa` |
| E20 prompt-scoped-acquire | `2026-07-04-prompt-scoped-acquire/` | COMPLETE, audited + merged to main 2026-07-04 (PARTIAL [hint-fragile], cell 3/6, mean scoped acquire 1.85 s; 27/27 legs clean, zero fallbacks) |
| E21 coarse-to-fine | `2026-07-04-coarse-to-fine-acquire/` | DRAFT (README only, on the E20 branch). Launch gate: E20 merged PARTIAL/YES — met, pending audit |
| E22 cv-proposal | `2026-07-04-cv-proposal-acquire/` | DRAFT (README only, on the E20 branch). Phase-0 offline audit is free and may run any time after E20 merges; E22 may be re-ordered before E21 (see its Launch gate) |

Orientation for a cold start: read `CLAUDE.md` (workflow rules), then this file, then
the E20 README end-to-end, then the E21/E22 READMEs. Auto-memory (if you have it)
has one file per campaign under the project memory dir; keep it updated the same way.

## The loop (per campaign)

Division of labor that has worked for E18-E20:

1. **Orchestrator drafts** (or, for E21/E22, the draft already exists): pre-registered
   README committed on a fresh `experiment/<name>` branch off main BEFORE any run,
   plus any load-bearing core module with a selfcheck (E20's `scope.py` pattern).
   For E21/E22 the READMEs specify exactly which code the executor writes.
2. **Orchestrator spawns an executor subagent** (Opus-class; keeps orchestrator
   tokens for judgment work) whose prompt says: read the campaign README, execute its
   "Execution plan (for the executor)" step by step, and report back verdict + table
   + `git log --oneline main..HEAD`. Include VERBATIM the anti-stall rule: the
   matrix takes hours; the executor must NOT end its turn to "wait" but must poll
   `runs/*/results.json` in a foreground loop and continue straight through to the
   final commits. Three executors stalled this way (E19 twice, E20 once); resume a
   stalled one by sending it a message repeating that rule.
   Give the executor the git trailer block with YOUR conversation's session URL:
   `Co-Authored-By: <your model> <noreply@anthropic.com>` +
   `Claude-Session: <your session URL>`.
3. **Orchestrator audits** (checklist below), **merges to main** `--no-ff` with a
   descriptive one-paragraph merge message stating the verdict and mechanism (see
   `git log` for the E17/E18/E19 pattern), deletes the branch. NEVER push.
4. **Orchestrator updates auto-memory** (one `project-e2X-*.md` file + a MEMORY.md
   index line, if the memory system is available) and reports to the user: verdict
   first, mechanism, next lever; send a proof clip via the file tool if available.
5. **Check the next campaign's Launch gate**, adjust its README if the new results
   changed anything material (record the adjustment as a decision), branch, spawn.

## Audit checklist (before any merge)

- `git log --oneline main..HEAD`: pre-reg commit precedes harness/results commits;
  working tree clean.
- Spot-check 3-4 `runs/*/results.json` against the README Results table (gen/cov/
  latency numbers match; reps are independent, not copies — t_lock may differ only
  at ms level, the rig is near-deterministic under greedy decode).
- Verdict = mechanical application of the FROZEN rules in the pre-registered README
  (no post-hoc rule bending); regression guard actually evaluated per clip.
- Ledgers appended under Part 4 (`docs/{results,questions,decisions}/part4-end-to-end.md`),
  not the root redirects; Madrid wall-clock timestamps; no emojis.
- Proof clips exist under `proof/`, are COMMITTED, and are captioned in the README.
- `.gitignore` per convention: `data/` + `runs/*/overlay.mp4` ignored;
  `runs/*/results.json` committed.
- Estimate-vs-actual section filled; "what broke / what surprised" honest.

## Immediate next action: launch E21 (or re-order E22 first)

E20 is audited and merged; its README Results section is authoritative. Two E20
findings that E21/E22 already account for: cellbuf ≈ cell (both drafts dropped buf
legs, their D2), and the residual FAILs (car3/car7/car18) are TARGET-SIZE bound, not
latency bound — arrival-frame IoU 0.00-0.02 while coverage is 0.98+, i.e. the carry
latches the right object from the submit frame but the raw arrival-frame box misses
a small displaced target. A perfect automated prior can therefore be expected to
reproduce E20's 3/6, not beat it (both drafts pre-register this).

Next step: check E21's Launch gate (met), branch `experiment/coarse-to-fine-acquire`
off main, spawn the executor per "The loop" step 2. Or run E22's free offline
Phase-0 prior audit first to decide the order (E22's Launch gate explains why).

One E20 deployment note not yet acted on anywhere: the hint-escape idea (after N
consecutive mask-gate rejects following a scoped acquire, drop to full-frame AND
re-bind a fresh template) — recorded in E20's README; a candidate small campaign or
a DECISIONS-documented deploy change after the arc closes.

## Facts a fresh session needs (so you don't re-derive them)

- **Rig**: `replay_e19.py` -> `replay_e20.py` lineage under the campaign dirs;
  scorer + wall-clock replay in
  `experiments/2026-07-03-real-video-replay/replay_source.py`; crop grammar in
  `experiments/2026-07-04-prompt-scoped-acquire/scope.py`. Data (gitignored, on
  disk): `experiments/2026-07-03-real-video-replay/data/UAV123/`.
- **Frozen numbers**: full-frame acquire ~4.85 s (E18); E20 cell acquire 1.57-2.07 s;
  carry cap 6.15 Hz (E1, TensorRT co-resident); lock metric = first accepted box
  IoU>=0.25 vs GT at ARRIVAL frame; PASS = genuine_lock AND cov >= 0.50, best of
  n=2; clips car3/car7/car9/car10/car14/car18 at 30 fps, captions frozen (4x "the
  red car", car9 "the white car", car7 "the silver car").
- **E18 A-leg baselines (gen/cov best)**: car3 F/0.976, car7 F/0.285, car9 F/0.993,
  car10 P/1.000, car14 F/0.903, car18 F/0.711.
- **Environment**: venv `.venv-ft` only; `ssh jetson` with NOPASSWD
  `sudo nvpmodel`/`sudo jetson_clocks` (15W board, no MAXN — never claim otherwise);
  Jetson VLM server self-boots per run via `JetsonBackend`; Python over shell; the
  executor must never push, never touch main.

## Open levers beyond E22 (for the session that closes the arc)

- Even a perfect prior at ~1.6-2.0 s leaves small/fast targets stale (E20's car3/
  car7/car18). Next honest levers, in rough order of preference: (a) M-margin crop
  around a prior box at a 512 cap (ROI-campaign geometry, sub-second acquire —
  given up in E20 D7 / E21 D1 for single-knob cleanliness, explicitly flagged as
  the follow-up); (b) convergence-scored lock (score the lock after BUF catch-up
  instead of at the raw arrival frame — a METRIC change, breaks comparability,
  needs its own pre-registration and an explicit DECISIONS entry); (c) accept and
  document the ceiling: coverage (which every crop arm repairs to >0.9) is the
  deployed-relevant metric, first-lock staleness is inherent to a ~1.6 s blocking
  acquire on a 30 fps world.
- The [hint-fragile]/[prior-wrong] failure mode (hallucination in an empty crop +
  mask-gate template poisoning) has no client-side defense yet; a verify-before-bind
  step (e.g. re-ground the accepted box full-frame once, async, and unbind on
  disagreement) is unexplored.
