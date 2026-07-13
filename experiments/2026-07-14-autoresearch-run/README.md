# 2026-07-14 autoresearch run — 48 h unattended burn (operating charter)

**Pre-registered:** 2026-07-14T01:10Z (Madrid wall-clock). **Status:** CHARTER COMMITTED; burn
window 2026-07-14T01:10Z → **2026-07-15T18:00Z** (Wed 18:00 Madrid, hard deadline baked into the
driver). This is not a single experiment — it is the **operating charter** for an autonomous
sequence of `next-experiment` cycles. Each cycle produces its own `experiments/<campaign>/`
record per the normal definition of done; this file records how the run works, the honest audit
of Part V at start, a ranked (non-binding) research backlog, and the dead-levers list.

## Goal and token-burn rationale

North star (unchanged): a Jetson Orin Nano 8 GB on-device system where an operator says
"follow that white car" / "switch to that blue truck" over a drone video feed and the drone does
it end-to-end, at 15 W, no cloud.

The thesis has a validated warm-start acquire (P5.1/P5.2) but the *select* in select-on-command
has never been exercised: every Part V clip had a single dominant target, so the phrase→track
language layer — the literal north-star sentence — is untested. A large token budget spent on an
unattended iterative loop is the right shape for this: the open questions are offline-replayable
(UAV123 clips through the real Jetson backend), each answer reshapes the next question, and no
step needs a human judgment call if every experiment is pre-registered with mechanical verdict
rules. Negative results merge and count — they are thesis content.

## Mechanism (already built — do not modify mid-run)

- **Driver:** `scripts/autoresearch.py` (stdlib-only, no venv). One crontab entry fires it every
  10 min wrapped in `flock -n`, so at most one cycle runs at a time; ticks landing mid-cycle are
  skipped, giving back-to-back near-continuous cycles. (At charter-commit time the crontab entry
  was not yet installed — the operator installs it to start the burn.)
- **One tick = at most one cycle:** the driver runs
  `claude -p "<one-cycle prompt>" --model opus --dangerously-skip-permissions` from the repo
  root, with a 4 h hard timeout per cycle (stuck cycle is killed; next tick retries fresh).
- **The cycle = the `next-experiment` skill** (`.claude/skills/next-experiment/SKILL.md`):
  Opus (loop driver, the workhorse) reads status, spawns **one fresh Fable design subagent**
  (smart judgment: audit the most recent merged results, pick the single highest-leverage RQ,
  write the pre-registered README + design-code patch on `experiment/<slug>`), verifies the
  handoff, runs the matrix, fills Results, appends the RESULTS/QUESTIONS/DECISIONS ledger rows,
  cuts the proof deliverables, commits, merges `--no-ff` to `main`, decrements
  `.claude/loop-budget`. A FAIL verdict still merges and still loops; the *next* cycle's Fable
  audit re-reviews it.
- **Model split:** Fable = audit + pick-RQ + design only (fresh context each cycle, no loop
  state). Opus = everything mechanical. Neither role crosses over.
- **Token-window resilience:** a cycle that exhausts the 5 h token window just fails; the next
  tick after the window resets starts a fresh cycle. No state is lost because everything lands
  in git per cycle.

### Guards (checked every tick, cheapest first)

1. **Kill switch:** `.claude/autoresearch.STOP` present → tick does nothing.
2. **Deadline:** now ≥ 2026-07-15T18:00Z Madrid → the driver removes its own crontab line and
   stops forever.
3. **Runaway cap:** `.claude/loop-budget` ≤ 0 or missing → tick does nothing until reseeded
   (`echo N > .claude/loop-budget`). Seeded at 200 at run start — an intentionally
   non-binding cap; the deadline and STOP file are the real limits.
4. **Per-cycle:** 4 h subprocess timeout; the skill's own process-failure rules (incomplete
   Fable handoff, matrix crash past abort criteria, merge conflict) stop that cycle without
   merging and leave the branch for a human — the *driver* keeps ticking, and the next cycle's
   Fable audit sees the stranded branch in `git log`/status.

### How a human stops it

- `touch /home/gara/jetson/.claude/autoresearch.STOP` (instant, reversible), **or**
- `crontab -e` and delete the `autoresearch.py` line (permanent), **or**
- `echo 0 > /home/gara/jetson/.claude/loop-budget` (pauses after the current cycle).

### Where to look while it runs

- `.claude/autoresearch.log` — one line per tick (CYCLE-START/END/TIMEOUT, budget, skips).
- `.claude/autoresearch-logs/cycle-<epoch>.log` — full stdout of each Opus cycle.
- `.claude/loop.log` — the skill's own timeline stamps (CYCLE-START / FABLE-DESIGN /
  EXEC-START / MERGED per cycle).
- `git log --oneline main` — one merge commit per completed cycle; each cycle's science is in
  its own `experiments/<campaign>/README.md`.

## Iterative philosophy — no master plan

There is **no fixed sequence of experiments**. Each cycle's Fable subagent audits the latest
merged results and picks the next RQ from what the data actually says; the backlog below is
steering material it may draw from **or override** when fresh results point elsewhere. The
`.claude/loop-focus` file carries the run's standing steer (top directions + operating
preferences); the skill passes it to Fable verbatim, and Fable is explicitly allowed to deviate
when its audit shows the binding constraint is elsewhere.

**Deep-research threading:** when a method or literature gap blocks the next RQ (e.g. "what are
the credible phrase→track matching approaches at this compute budget?"), a cycle should first
run the `deep-research` skill, land the findings as SOURCES.md entries (link + what for), and
design the experiment on top of the cited findings — a research cycle is a valid cycle. It still
produces a committed artifact (SOURCES rows + a short methods note in that cycle's campaign dir)
and still merges.

**Operating preferences for cycles (not rules — preferences):**
- Prefer **offline UAV123-clip replay experiments** (the P5.1 rig `replay_e24.py` lineage runs
  the real backend on the Jetson over recorded clips) — they are deterministic, unattended-safe,
  and directly comparable to P5.1/P5.2. Reserve live/SITL work for on-device gate checks a
  replay cannot answer (co-residency memory/thermal, follow-loop integration).
- Keep the deployed backend frozen unless an RQ explicitly targets it: Qwen2-VL-2B Q8_0 terse
  max_side 1024, SAM2.1-tiny TRT fp16 ~6.15 Hz, mask gate app_tau 12.0, Jetson 15 W +
  jetson_clocks. All numbers carry this config.
- Every cycle obeys the CLAUDE.md definition of done (pre-registered README, mechanical verdict
  rules, ledger rows, 2–3 proof deliverables from a committed `make_proof.py`-style script).

## Audit of Part V at run start (2026-07-14, honest)

**Established (do not re-litigate):**
- **P5.1 = YES [carry-bound]** (merge `4376693`): idle-window VLM seed + SAM2 catch-up +
  select-on-command, WARM 5/6 == ORACLE 5/6 vs COLD 1/6 on the UAV123 `car*` clips at t_p=8 s.
- **P5.2a = YES, P5.2b = NO [flat-in-speed]** (merge `162c819`): WARM 21/25 vs COLD 5/25 across
  5 categories; Spearman ρ(WARM−COLD gap, on-screen speed) = −0.06 — the win is **delivery-lag
  removal, not motion-compensation**. Speed-adaptive acquire is a dead direction (no speed axis).

**Under-supported / open (what the audit says a 40 h loop can actually move):**
1. **The "select" in select-on-command is untested.** All 31 Part V clips are
   single-dominant-target; the phrase→track selector was trivially a 1-of-1 pick. The north-star
   sentence ("that *white* car", "switch to that *blue truck*") is a multi-candidate
   disambiguation problem, deliberately deferred in P5.1's DECISIONS. Highest leverage: this is
   the last unvalidated stage of the end-to-end pipeline.
2. **The warm mechanism tested so far is a degenerate 1-shot seed at t=0**, not the
   PART5-PROPOSAL's running candidate set (periodic boxes+labels, multiple carried tracks).
   Targets entering the scene after t=0, and carry drift over long idle windows, are unmeasured.
3. **t_p = 8 s is the only prompt time ever tested** (frozen in P5.1). The `[ready-only]` regime
   only; the early-prompt fallback (t_p < acquire ≈ 4.5 s) is explicitly out of scope so far.
   The Part V claim "keep tracked over the idle window" rests on one window length.
4. **2-clip `[detection-bound]` seed headroom** (person18, car17: ORACLE passes, the idle-window
   VLM seed misses) — small/deformable targets; the idle window is long enough for retry/best-of-N
   seeding that was never attempted.
5. **On-device cost of a *real* idle loop is unmeasured** — PART5-PROPOSAL's Phase-0 caveat
   (periodic VLM pass + N co-resident SAM2 carries at 15 W / 8 GB) was sidestepped because
   P5.1/P5.2 fired one acquire, carried one track.
6. Minor: COLD's 5 survivors are *interpreted* as deliver-frame geometry accidents (plausible,
   spot-checkable in one cheap cycle if a design ever leans on it).

## Ranked research backlog (steering suggestions — NOT a fixed sequence)

Each cycle's Fable may draw from this or override it based on fresh data. Costs are estimates.

1. **P5.3 multi-candidate select-on-command.** RQ: given ≥2 warm-carried same-class candidates,
   does phrase→track selection (attribute phrases: colour/position/type) pick the operator's
   target at prompt time, vs the trivial 1-candidate case? Why: the last untested pipeline stage
   and the literal north-star sentence; everything downstream (retarget switch) depends on it.
   Offline replay (needs clip curation: UAV123 scenes with visible distractors, or composited
   twins; GT exists only for the annotated target — design must handle that). Est: 2–3 cycles
   (curation + matrix).
2. **Idle-window candidate maintenance.** RQ: does a periodic idle re-scan (running candidate
   set, not a 1-shot t=0 seed) hold WARM performance over a t_p sweep (e.g. 4/8/16/30 s) and
   catch targets entering after t=0? Why: converts the degenerate 1-shot rig into the actual
   PART5-PROPOSAL mechanism and tests carry drift over long windows. Offline replay. Est: 1–2
   cycles.
3. **Early-prompt fallback (t_p < acquire).** RQ: what policy wins when the prompt lands before
   the warm track is established — block-cold, partial-warm handoff, or defer-and-notify? Why:
   the only prompt-timing regime with no answer; bounded, cheap, closes the P5.1 scope cut.
   Offline replay. Est: 1 cycle.
4. **Seed-quality headroom (close the `[detection-bound]` gap).** RQ: does best-of-N / retry
   seeding across the idle window recover person18 + car17 (WARM → ORACLE parity at scale)
   without regressing the 21? Why: free compute in the idle window, directly measurable, small.
   Offline replay. Est: 1 cycle.
5. **Deep-research: phrase→track matching methods.** When backlog #1 needs a method choice
   (VLM multiple-choice over crops vs CLIP-style crop-text similarity vs text-index matching),
   run a deep-research cycle first and land SOURCES.md citations before designing. Est: 1 cycle,
   no Jetson.
6. **On-device idle-loop gate.** RQ: does the periodic idle scan + K co-resident carries fit
   15 W / 8 GB (memory, thermals, carry Hz) on the Jetson? Why: PART5-PROPOSAL Phase-0 caveat;
   gates deployment of #1/#2. Needs Jetson (gate check, not a matrix). Est: 1 cycle.
7. **Occlusion-at-select policy.** RQ: on `[deliver-occluded]` clips (car7, person10), does a
   defer-select / reacquire-on-reappear policy convert structural misses into late PASSes? Why:
   2/25 of the current miss set; bounded. Offline replay. Est: 1 cycle.
8. **Warm-select → follow integration (SITL retarget switch).** RQ: does "switch to that other
   candidate" mid-follow work end-to-end with warm candidates feeding the Part III/IV follow
   stack? Why: the full north-star demo; expensive and dependent on #1 landing first — late-run
   material only. Needs SITL + Jetson. Est: 2+ cycles.

## Dead levers — do NOT re-propose (Part IV audit + closed campaigns)

From `experiments/HANDOFF-acquire-arc.md`, the Part IV ledgers, and closed-campaign memory:

- **Any sub-2 s *cold*-acquire speedup.** The arc is closed: motion-comp NCC flow (E19,
  fragile), second coarse VLM pass (E21, wrong shape), CPU motion+colour prior (E22, floods on
  silver / loses tiny reds), widened operator crop cell (E23, containment necessary but not
  sufficient — admits decoys). The operator-phrase cell crop (E20) works but stays
  [hint-fragile] and is superseded by warm-start.
- **Speed-adaptive acquire.** P5.2b: the WARM−COLD gap is flat in speed (ρ=−0.06) — there is no
  speed axis to adapt to.
- **Identity-blind REGROUND cues:** size prior (E3), motion (E4), colour (E3/E7/E13) — cannot
  separate a two-car blend box. The mask-bound median gate is the only cue that beats it, and
  only at ~0.75 rate (E16).
- **`--reground-hold chase`:** regresses 6/8 → 0/10 (E17); pre-lock chase-hold does not
  transfer to REGROUND.
- **Learned SR on the ROI crop** (Swin2SR, 2026-06-30): loses to free LANCZOS (+1331 ms, worse
  IoU).
- **Replacing Qwen2-VL-2B** (VLM bake-off, closed 2026-07-02, early-stopped — no arm beat the
  incumbent) and **EdgeTAM over SAM2 TRT** (E1: SAM2 TensorRT fp16 kept).
- **Text-only scene index as the primary warm representation** (PART5-PROPOSAL: prose
  round-trips re-derive E20's cell coarseness; keep geometry — boxes + carried tracks — with
  text only as the matching layer on top).

## Results (TBD — filled at run end or by the first post-run human session)

| # | cycle campaign dir | RQ id | verdict | merge commit |
|---|---|---|---|---|
| — | *(one row per merged cycle; reconstruct from `git log --oneline main` + `.claude/loop.log`)* | | | |

Post-run close-out checklist: fill this table; verify every merged cycle met the definition of
done (spot-check ledgers + proof/); note cycles that ended in process-failure stops and their
stranded branches; append a run-level DECISIONS entry if the run changed Part V direction.
