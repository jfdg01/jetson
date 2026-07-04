# E19 motion-comp-acquire — does compensating the acquire's own latency close E18's stale-lock gap?

- **Pre-registered:** 2026-07-04T00:54Z (Madrid wall-clock)
- **Status:** COMPLETE (2026-07-04). RQ-E19 = **PARTIAL [flow-fragile]** — best
  arm FLOW 2/6 (car3 flipped to PASS, car10 held); BUF 1/6 (cannot flip
  genuine_lock structurally, but repairs coverage: car7 0.285 -> 0.934). ctl
  reproduced E18. Results + proof clips below.
- **Roles:** design + audit by Fable (this README + `mc.py`, selfcheck green).
  Opus does Steps 1-5: `replay_e19.py` wiring per spec, the matrix, Results,
  ledgers, proof clips. Every judgment is pre-made below; if a case is not
  covered by a rule here, record it verbatim and mark the leg `UNRULED`, do not
  invent a rule.
- **Branch:** `experiment/motion-comp-acquire` (from clean main `e2343a8`, the
  E18 merge).
- **Rig:** identical to E18 (host 3090 SAM2.1-hiera-tiny @1024 capped 6.15 Hz,
  Jetson Q8_0 terse self-boot, 15W + jetson_clocks, perception-only replay).
  Data: E18's six extracted UAV123 sequences, already on disk at
  `../2026-07-03-real-video-replay/data/` — do NOT re-download.
- **Versions:** same stack and venv (`.venv-ft`) as E18; pins in
  `requirements-ft.lock.txt`. Zero deltas to existing code; E19 adds only new
  files in this campaign dir.

## Context — why this experiment

E18 (RQ NO [grounding-bound], `e2343a8`) measured the sim-to-real binder: the
~4.85 s blocking full-frame VLM acquire computes a CORRECT box for the frame it
saw, but the target moves ~146 frames before the box arrives, so the lock lands
stale — genuine_lock missed on 5/6 clips while oracle-init carry passed 6/6.
car7 showed REGROUND inherits the same staleness and the appearance-only mask
gate accepts stale right-colour boxes (identity != position). E19 attacks the
measured mechanism directly: bridge the acquire's own latency before carry init.

## RQ-E19

**Does motion-compensating the acquire (and REGROUND) box for its own ~4.85 s
latency lift E18's A-full from 1/6 to the original YES bar (>= 4/6 clips PASS),
on the same six clips, captions, and scoring?**

Two independent compensation arms (either reaching the bar answers YES):

- **Arm FLOW** — `mc_shift` (`mc.py`, this dir): whole-frame NCC template match
  of the submit-frame box crop in the arrival frame; shift the box to the match
  before carry init; refuse (keep stale box) below NCC 0.5. One-shot, ~ms, no
  extra model. Known ceiling: appearance change (rotation/scale) over ~5 s.
- **Arm BUF** — replay-buffer catch-up: init StreamCarry on the SUBMIT frame
  with the VLM's box (correct for that frame, by E18's finding), then step
  carry forward through every 12th intermediate frame until caught up to live,
  each step still capped at 6.15 Hz with the wall clock RUNNING (catch-up costs
  real time during which more frames accrue; at K=12 the backlog ratio is
  (30/12)/6.15 ~= 0.41 < 1 so it converges, ~3-4 s — record actual). On replay
  the "buffer" is the frames dir itself (a deployed system would hold a raw
  ring buffer — memory, not compute, so this is honest). Known cost: coverage
  loss during convergence; no refusal path needed (carry init is on the exact
  frame the box describes).

Scoring: byte-identical to E18 — `score_run` from
`../2026-07-03-real-video-replay/replay_source.py`, per-clip PASS =
genuine_lock AND coverage >= 0.50, clip PASS = better of n=2 reps. Same six
clips, same D6 captions (copy them verbatim from the E18 README table).

- **YES** iff best arm >= 4/6 PASS.
- **PARTIAL** iff best arm 2-3/6.
- **NO** iff best arm <= 1/6 (motion compensation is not the right lever; the
  binder moves to raw acquire latency itself — faster/ROI acquire).
- **NOT-MEASURABLE** iff a selfcheck fails, the Jetson cannot be brought up, or
  the regression control inverts (ctl rules below).
- Suffix **[flow-fragile]** iff FLOW's refusal or a wrong match (shifted box
  IoU < 0.25 vs GT at arrival while the unshifted box would have scored the
  same or better) occurs on >= 2 clips — flags the NCC arm as unreliable even
  if BUF carries the verdict.

## Design decisions (pre-registered, with rationale)

- **D1 — two cheap arms, no new model.** FLOW is rung-4 lazy (cv2 already
  installed, ~ms); BUF reuses StreamCarry itself as the motion estimator.
  Given up: optical-flow trackers (KLT), a learned motion model, faster
  acquire (different lever — that is raw latency reduction, kept for a later
  E if E19 is NO).
- **D2 — MC applies to REGROUND identically.** Both arms compensate REGROUND
  re-acquires the same way (FLOW: template = proposal crop from the REGROUND
  submit frame; BUF: carry re-init on the submit frame + catch-up). The E14/E16
  mask gate then evaluates the descriptor at the COMPENSATED box location —
  this is exactly the position-awareness E18 showed the gate lacks. car7 is
  the direct test.
- **D3 — E18 comparability is the whole point.** Same clips, captions, rig,
  caps, scoring, thresholds. No new clips, no caption edits (a caption that
  failed in E18 stays as-is). E18's A legs are the baseline (committed in
  `../2026-07-03-real-video-replay/runs/`); E18's B legs are the ceiling. Given
  up: broader clip coverage — comparability beats breadth here.
- **D4 — regression control.** The E19 harness is a fork of `replay_e18.py`;
  before the matrix, run `ctl` = MC disabled on car3 + car10 (n=1 each) and
  require reproduction of E18's signature: car3 genuine=False with coverage
  >= 0.90, car10 PASS. If either inverts, the harness fork changed the
  baseline: NOT-MEASURABLE, stop, document.
- **D5 — refusal over teleport (FLOW).** Below NCC 0.5 the stale box is kept:
  E18 proved a stale box is usually recoverable by carry (cov 0.90-0.99); a
  confident wrong match on a distractor is not, and the mask gate only guards
  REGROUND, not first acquire. Threshold 0.5 is a pre-registered guess; log
  every NCC score so the threshold-vs-outcome table can be reported either way.

## Harness spec — `replay_e19.py` (Opus writes this)

Fork `../2026-07-03-real-video-replay/replay_e18.py` into this dir (provenance
comment at top), then:

1. Keep a reference to the submit frame + its wall time at every VLM call
   (ACQUIRE and REGROUND).
2. `--mc {none,flow,buf}`:
   - `none`: byte-equivalent behaviour to E18 (the D4 ctl).
   - `flow`: on box arrival, `box, ncc, applied = mc_shift(submit_frame, box,
     current_frame)` with the CURRENT grabbed frame; log `(ncc, applied)` per
     call; then init carry on the current frame with the (possibly shifted) box.
   - `buf`: init carry on the SUBMIT frame with the raw box; then loop: step
     carry on frame `last+12` from the frames dir while that index < the live
     wall-clock index, each step rate-capped at 6.15 Hz; when caught up, resume
     the normal live loop. Events during catch-up are appended with the WALL
     time they were produced at (they are stale outputs and score accordingly).
3. Mask gate (REGROUND): unchanged logic, but evaluated at the compensated box
   per D2.
4. `--selfcheck`: extend E18's with a stub-submit case asserting (a) flow arm
   shifts a synthetic moving patch's box (reuse the mc.py selfcheck geometry),
   (b) buf arm's catch-up loop terminates and ends within 12 frames of live.
   Green before any run.
5. `results.json` additionally records: arm, per-call MC log (ncc/applied or
   catch-up frame count + convergence seconds), and the E18-format score dict.

## Matrix (26 runs + smoke)

| leg | clips | --mc | n | purpose |
|---|---|---|---|---|
| smoke | car10 | flow | 1 | plumbing |
| ctl | car3, car10 | none | 1 | D4 regression guard (run FIRST) |
| A-flow | 6 | flow | 2 | arm 1 |
| A-buf | 6 | buf | 2 | arm 2 |

B legs are NOT re-run (E18's stand). Order: selfchecks, ctl, smoke, A-flow,
A-buf. Jetson 15W + jetson_clocks before first VLM leg; log `nvpmodel -q` to
`raw/`.

## Estimates (mark vs actuals when done)

- Matrix wall time: ~45 min (26 runs x ~35-65 s + Jetson boots).
- ctl: reproduces E18 (near-deterministic rig, E18 rep spread was 4th-decimal).
- A-flow: 4-5/6 PASS — NCC should survive ~5 s of appearance change on nadir
  cars; the risk clips are car7 (occlusion + distractor twin: wrong-match or
  refusal) and car14 (occ). genuine_lock should flip on car3/car9/car14/car18
  if the match lands.
- A-buf: 5-6/6 PASS but with a coverage dent from ~3-4 s convergence; car7 is
  the interesting one (does carry-from-submit-frame survive the occlusion it
  previously lost?).
- Overall: **YES via at least one arm, 4-6/6** (estimate). If both arms land,
  BUF is expected higher-coverage but slower-converging; FLOW is the deployable
  one (no buffer requirement on the Orin).

## Clips + captions (frozen — copied verbatim from E18's README, D3)

E19 = E18's exact six clips, resolutions, and captions. No new clips, no caption
edits (a caption that failed in E18 stays as-is). Data lives at
`../2026-07-03-real-video-replay/data/` (not re-downloaded).

| clip | frames | res | plain/distractor/occ | why chosen | caption |
|---|---|---|---|---|---|
| car3 | 1717 | 1280x720 | plain | single dominant vehicle, clean | the red car |
| car9 | 1879 | 1280x720 | plain | single dominant vehicle | the white car |
| car14 | 1327 | 1280x720 | plain, occ | 77 NaN GT gap (full occlusion) — exercises REGROUND for free | the red car |
| car18 | 1207 | 1280x720 | plain | oblique test-track view, real scale change | the red car |
| car7 | 1033 | 1280x720 | distractor, occ | 73 NaN gap + same-class cars beside target (~f520, ~f780) | the silver car |
| car10 | 1405 | 1280x720 | distractor | van + white car beside target (~f700) | the red car |

## Results (2026-07-04, matrix complete)

Rig as pre-registered: host 3090 (SAM2.1-hiera-tiny @1024, capped 6.15 Hz) +
Jetson Orin Nano q8_0 terse self-boot, 15W + jetson_clocks
(`raw/jetson-power.txt`). 27 runs (2 ctl + smoke + 12 flow + 12 buf), all valid.
Per-clip PASS = better of n=2 reps; PASS iff `genuine_lock` AND `coverage` >=
0.50. Full log `raw/matrix.log`; per-run `runs/*/results.json` (committed).

**ctl reproduction (D4): PASS.** car3 `--mc none`: genuine=False, cov=0.976
(rule: genuine=False with cov >= 0.90) — matches E18 A car3 (0.976). car10
`--mc none`: genuine=True, cov=1.000, PASS — matches E18 A car10. Neither
inverted; the harness fork did not move the baseline. Smoke (flow car10) green.

| clip | leg | rep | t_lock | genuine | coverage | mean_iou | MC detail (ACQ ncc/applied or catchup) | verdict |
|---|---|---|---|---|---|---|---|---|
| car3 | ctl none | 1 | 4.87 | False | 0.976 | 0.594 | - | FAIL (= E18, reproduces) |
| car10 | ctl none | 1 | 4.84 | True | 1.000 | 0.796 | - | PASS (= E18, reproduces) |
| car3 | A-flow | 1 | 4.90 | **True** | 0.982 | 0.597 | ncc=0.87 applied | **PASS** (E18: FAIL) |
| car3 | A-flow | 2 | 4.90 | **True** | 0.980 | 0.597 | ncc=0.87 applied | **PASS** |
| car9 | A-flow | 1 | 4.91 | False | 0.000 | 0.000 | ncc=0.32 REFUSED; 9 gate-rej in REGROUND loop | FAIL (E18 cov 0.993) |
| car9 | A-flow | 2 | 4.92 | False | 0.000 | 0.000 | ncc=0.32 REFUSED; 9 gate-rej | FAIL |
| car14 | A-flow | 1 | 4.85 | False | 0.000 | 0.000 | ncc=0.64 applied WRONG-MATCH; 5 gate-rej | FAIL (E18 cov 0.903) |
| car14 | A-flow | 2 | 4.86 | False | 0.000 | 0.000 | ncc=0.64 applied WRONG-MATCH; 5 gate-rej | FAIL |
| car18 | A-flow | 1 | 4.86 | False | 0.000 | 0.000 | ncc=0.51 applied WRONG-MATCH; 7 gate-rej | FAIL (E18 cov 0.711) |
| car18 | A-flow | 2 | 4.84 | False | 0.000 | 0.000 | ncc=0.51 applied WRONG-MATCH; 7 gate-rej | FAIL |
| car7 | A-flow | 1 | 4.85 | False | 0.000 | 0.000 | ncc=0.56 applied WRONG-MATCH; 3 gate-rej | FAIL (E18 cov 0.285) |
| car7 | A-flow | 2 | 4.84 | False | 0.000 | 0.001 | ncc=0.56 applied WRONG-MATCH; 3 gate-rej | FAIL |
| car10 | A-flow | 1 | 4.88 | True | 1.000 | 0.800 | ncc=0.96 applied | **PASS** |
| car10 | A-flow | 2 | 4.88 | True | 1.000 | 0.801 | ncc=0.96 applied | **PASS** |
| car3 | A-buf | 1 | 4.87 | False | 0.941 | 0.570 | backlog 238f, 19 steps, 3.09 s, gap 10 | FAIL (genuine) |
| car3 | A-buf | 2 | 4.87 | False | 0.940 | 0.571 | backlog 238f, 3.09 s | FAIL (genuine) |
| car9 | A-buf | 1 | 4.88 | False | 0.950 | 0.745 | backlog 239f, 3.09 s | FAIL (genuine) |
| car9 | A-buf | 2 | 4.87 | False | 0.950 | 0.744 | backlog 238f, 3.09 s | FAIL (genuine) |
| car14 | A-buf | 1 | 4.82 | False | 0.850 | 0.499 | backlog 237f, 3.09 s | FAIL (genuine) |
| car14 | A-buf | 2 | 4.82 | False | 0.853 | 0.504 | backlog 237f, 3.09 s | FAIL (genuine) |
| car18 | A-buf | 1 | 4.81 | False | 0.914 | 0.657 | backlog 236f, 3.09 s | FAIL (genuine; E18 cov 0.711 -> 0.914) |
| car18 | A-buf | 2 | 4.81 | False | 0.913 | 0.661 | backlog 236f, 3.09 s | FAIL (genuine) |
| car7 | A-buf | 1 | 4.82 | False | 0.934 | 0.699 | backlog 237f, 3.09 s | FAIL (genuine; E18 cov 0.285 -> 0.934) |
| car7 | A-buf | 2 | 4.82 | False | 0.934 | 0.699 | backlog 237f, 3.09 s | FAIL (genuine) |
| car10 | A-buf | 1 | 4.85 | True | 1.000 | 0.782 | backlog 238f, 3.09 s | **PASS** |
| car10 | A-buf | 2 | 4.85 | True | 1.000 | 0.781 | backlog 238f, 3.09 s | **PASS** |

Per-clip roll-up: **A-flow PASS = 2/6** (car3, car10). **A-buf PASS = 1/6**
(car10). Best arm = FLOW, 2/6.

- **RQ-E19 verdict: PARTIAL [flow-fragile]** (best arm FLOW 2/6, in the 2-3
  band). ctl reproduction PASS. [flow-fragile] fires by the pre-registered rule
  on 4 clips (>= 2 needed): ACQ refusal on car9 (ncc 0.32) and ACQ wrong-match
  on car14/car18/car7 — shifted-box IoU vs GT at arrival = 0.000 on all three
  while the unshifted box scores the same or better (0.013 / 0.000 / 0.000;
  analysis in `raw/flow_fragile_analysis.txt`, unshifted boxes taken from the
  E18 A frame-0 submits — same image, deterministic rig, rep NCC identical to
  2 dp). No UNRULED legs: every leg is covered by the frozen PASS + verdict
  rules.
- **D5 threshold-vs-outcome (logged, not tuned):** applied-and-right at ncc
  0.87-0.96 (car3, car10); applied-but-WRONG at 0.51-0.64 (car18, car7, car14);
  refused at 0.32-0.49. The pre-registered 0.5 threshold does not separate
  right from wrong matches — the wrong-match band overlaps the accept band, and
  (see below) refusal is not a safe fallback under flow anyway, so no threshold
  fixes this arm.
- **Estimate-vs-actual:**
  - Matrix wall time: est ~45 min — actual ~22 min of summed run wall time
    (~35 min elapsed incl. Jetson self-boots and one harness restart after a
    session interrupt; the restart re-ran only the smoke, no data loss).
  - ctl: est reproduces E18 — actual reproduces (car3 cov 0.9764 = E18's
    0.976). Held.
  - A-flow: est 4-5/6 — **actual 2/6.** WRONG. genuine_lock flipped only on
    car3; on car9 NCC refused (0.32) and on car14/car18/car7 it confidently
    matched the wrong thing at ncc 0.51-0.64. "NCC should survive ~5 s of
    appearance change on nadir cars" held only for car3 (0.87) and car10
    (0.96). The predicted risk clips (car7, car14) did fail, but so did car18
    and car9.
  - A-buf: est 5-6/6 with a coverage dent — **actual 1/6,** and structurally
    so: under the frozen E18 scorer the buf arm CANNOT flip genuine_lock on a
    fast target — its first emitted event is still the raw
    (submit-frame-correct) box timestamped at arrival, and catch-up only
    repairs *coverage* afterwards. Convergence itself behaved exactly as
    designed: backlog ~237 frames, 19 catch-up steps, 3.09 s, final gap < 12
    frames on every single run (est 3-4 s — held).
  - Overall: est YES via at least one arm — **actual PARTIAL [flow-fragile].**
- **What broke / what surprised:**
  - **FLOW is catastrophic when wrong, not graceful.** E18's `--mc none` inits
    carry on the SUBMIT frame, where the VLM box is *correct* — SAM2 latches
    the right car and its own tracking bridges the ~146-frame jump to live
    (that is where E18's cov 0.90-0.99 came from). FLOW inits on the ARRIVAL
    frame: when the NCC match is wrong (or refused, leaving a stale box on a
    frame it no longer describes), SAM2 latches background or the wrong object.
    Worse, ACQUIRE then binds the E14 mask-gate template to that wrong mask, so
    the gate — doing its job against a poisoned template — rejects the genuine
    relocks that follow (3-9 gate-rejects per failing run) and coverage pins at
    0.000, strictly below the no-MC baseline on the same clips (0.285-0.993).
    Both flow failure paths (refuse AND wrong-match) are fatal for the same
    reason: arrival-frame init discards the one thing E18 proved works —
    submit-frame-correct carry init.
  - **BUF's catch-up works as designed, but the metric it needed to move is
    decided before it starts.** genuine_lock is scored on the first accepted
    box at its arrival frame; buf emits that raw box at arrival (per the
    pre-registered harness spec), so buf inherits E18's genuine_lock verbatim
    on every clip. What it DOES fix is E18's car7 failure mode: REGROUND
    re-inits on the submit frame + catches up, so the occlusion clip goes cov
    0.285 -> 0.934 (and car18 0.711 -> 0.914) with zero gate rejects. BUF is
    the better *coverage* lever; it just cannot claim the lock.
  - **Net:** motion compensation as bolted on here does not close the
    stale-lock gap. The honest fix axis is the acquire latency itself
    (faster/ROI acquire), or a buf-style submit-frame init whose lock is
    re-scored at convergence — which the frozen E18 metric (correctly, for
    comparability) does not credit.

## Proof clips (`proof/`, committed)

- **`car3_E18_vs_E19.mp4`** — the before/after. Top = E18 A car3 (no MC): the
  acquire lands ~4.9 s stale, genuine_lock False. Bottom = E19 flow_car3_r1:
  same clip, same caption, NCC (0.87) shifts the box to the target's arrival
  position — genuine_lock True, cov 0.982, the E18-fail -> E19-pass flip that
  carries the PARTIAL verdict.
- **`car7_buf_REGROUND.mp4`** — the car7 REGROUND story under BUF
  (buf_car7_r1): the occlusion still trips a loss, but REGROUND re-inits carry
  on the submit frame and catches up 3.09 s later, so the E18 drift (cov 0.285,
  mask gate accepting a stale box) is gone — cov 0.934, zero gate rejects.
  Still FAIL on genuine_lock (structural, see Results) — this clip is the
  coverage-repair evidence, not a PASS.
- **`car9_flow_vs_buf.mp4`** — the arms diverging on one clip. Top = flow
  (NCC refused at 0.32, carry inits stale on the arrival frame, template
  poisoned, cov 0.000). Bottom = buf (submit-frame init + catch-up, cov 0.950).
  Same VLM box, opposite outcomes — the init-frame choice is the whole story.

## Definition of done (per CLAUDE.md)

1. This README completed (results, verdict, estimate-vs-actual).
2. RESULTS row(s) -> `docs/results/part4-end-to-end.md`.
3. QUESTIONS entry (RQ-E19 + verdict) -> `docs/questions/part4-end-to-end.md`.
4. DECISIONS entry (D1 arm choice, D5 refusal rule) -> `docs/decisions/part4-end-to-end.md`.
5. SOURCES: none expected (no new external asset; UAV123 already recorded).
6. 2-3 proof clips in `proof/` (committed), captioned here: the E18-fail ->
   E19-pass before/after on one clip (e.g. car3), the car7 REGROUND story
   (whichever way it goes), and a FLOW-vs-BUF comparison if they diverge.
7. `runs/*/results.json` committed; overlays gitignored (E18 convention:
   `.gitignore` = `data/`-equivalent none needed here, `runs/*/overlay.mp4`,
   `__pycache__/`).

## Steps for Opus (in order)

1. Write `replay_e19.py` per spec; both selfchecks green (`mc.py` already is);
   commit.
2. Copy the six clip captions verbatim from the E18 README into a table here;
   commit ("E19 clips = E18 clips, captions frozen").
3. ctl legs; verify D4 reproduction; commit. STOP (NOT-MEASURABLE) if inverted.
4. Smoke, then A-flow, then A-buf; write `runs/` + `raw/` as you go.
5. Fill Results + verdict by the pre-registered rules; complete definition of
   done; commit on this branch. Do NOT merge to main, do NOT push — Fable
   audits first.
