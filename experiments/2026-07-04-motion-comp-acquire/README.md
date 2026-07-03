# E19 motion-comp-acquire — does compensating the acquire's own latency close E18's stale-lock gap?

- **Pre-registered:** 2026-07-04T00:54Z (Madrid wall-clock)
- **Status:** PRE-REGISTERED, not yet run. Next step: Opus executes Steps 1-5 below.
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

## Results (TBD)

| clip | leg | rep | t_lock | genuine | coverage | mean_iou | MC detail (ncc/applied or catchup_s) | verdict |
|---|---|---|---|---|---|---|---|---|
| TBD | | | | | | | | |

- RQ-E19 verdict: TBD
- ctl reproduction: TBD
- Estimate-vs-actual: TBD
- What broke / what surprised: TBD

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
