# E21 coarse-to-fine acquire (drafted 2026-07-04)

**Status: DRAFT — BLOCKED ON E20 MERGE + LAUNCH GATE.** Not yet run. Drafted
2026-07-04T12:05Z by the orchestrator session, before E20's official audit, as a
complete handoff: a fresh conversation should be able to run this campaign from this
file alone. See `experiments/HANDOFF-acquire-arc.md` for the arc-level loop
(audit -> merge -> launch) this campaign sits in.

## Launch gate (check before doing anything)

Run E21 only if E20 (`experiments/2026-07-04-prompt-scoped-acquire/`) merged with
verdict PARTIAL or YES on the `cell` arm. (Pre-audit peek 2026-07-04: cell = 3/6
PASS -> PARTIAL [hint-fragile]; gate expected MET. Confirm against E20's official
README Results before launching.) If E20 were NO, record E21 as a pre-registered
decline in the ledgers and stop.

## Context (self-contained chain)

- **E18** (`experiments/2026-07-03-real-video-replay/`): on real UAV123 footage under
  wall-clock frame-drop replay, the ~4.85 s blocking full-frame VLM acquire lands
  STALE (target moves ~146 frames during it): A-leg 1/6 PASS. Carry itself is fine
  (oracle-init B-leg 6/6).
- **E19** (`experiments/2026-07-04-motion-comp-acquire/`): bolt-on compensation fails.
  FLOW (NCC shift + arrival-frame init) is catastrophic when wrong (cov 0.000, and it
  poisons the E14 mask-gate template); BUF (submit-frame init + catch-up) repairs
  coverage but structurally cannot flip the arrival-frame `genuine_lock` metric.
- **E20** (`experiments/2026-07-04-prompt-scoped-acquire/`): the operator's phrase
  ("the red car in the bottom left") picks a padded 3x3-cell crop client-side; the VLM
  grounds the frozen caption in the crop. Acquire falls 4.85 s -> 1.57-2.07 s; 3/6
  clips flip to PASS (car9, car10, car14); coverage rises on all six (car7
  0.285 -> 0.997); the remaining 3 fails are small/fast targets still stale at ~58
  frames. `cellbuf` (BUF composition) adds nothing over `cell`. Wrong-hint probe:
  the VLM HALLUCINATES a box in the empty cell (cov 0.000 both reps) and the garbage
  lock poisons the mask-gate template, which then rejects the true car — verdict
  suffix [hint-fragile].

**E21's question: can a cheap coarse VLM pass replace the operator's hint** — same
crop mechanism, prior produced automatically? This removes E20's UX contract (the
operator must say where the target is, and a wrong hint is catastrophic).

## RQ-E21

Does a low-resolution first VLM pass (coarse box -> 3x3 cell -> E20 cell-crop second
pass) preserve E20's cell-arm wins without an operator hint, at a total acquire
latency that still beats staleness on at least the E20-flipped clips?

## Design

Two-pass acquire, first ACQUIRE attempt only:

1. **Coarse pass**: downscale the submit frame CLIENT-SIDE to max side
   `COARSE_MAX_SIDE = 320` (`cv2.resize`, INTER_AREA); send to the unchanged backend
   (its 1024 cap leaves a 320px image alone); call `vlm_acquire` with the FULL frame
   dims `w0, h0` so the parsed box lands directly in full-frame coords (the contract
   coords are relative, COORD_SCALE). ~57.6k px vs 590k full = ~10x fewer; est.
   ~0.8-1.0 s.
2. **Cell quantise**: `hint = scope.hint_for(coarse_box, w0, h0)` (reuse E20's
   committed `experiments/2026-07-04-prompt-scoped-acquire/scope.py` — import it, do
   not copy). The coarse box is NOT trusted as a box, only as a cell vote — at 320px
   a 16px-wide target (car3) is ~4px; box edges are noise but the cell may survive.
3. **Fine pass**: exact E20 scoped submit on `scope.crop_rect(hint, w0, h0)`, box
   `scope.map_back`'d. Est. 1.6-2.0 s (E20 measured).

Fallbacks (floor = E18 behaviour, mirroring E20 D4): coarse pass returns None/invalid
-> this attempt continues as a plain FULL-FRAME submit (one pass, no crop); fine pass
invalid -> next ACQUIRE attempt is full-frame. REGROUND always full-frame.
Pre-registered contingency (use at most once, document it): if the SMOKE coarse pass
returns None, bump `COARSE_MAX_SIDE` to 448 and re-smoke; if still None, STOP and
report — the coarse-prior premise is dead at these target sizes and that is the
(negative) result.

## Decisions

- **D1 — coarse box is a cell vote, not a box.** Quantising through `hint_for` reuses
  the audited E20 crop path and makes E21 vs E20 a one-variable comparison: who
  supplies the hint. Given up: using the coarse box directly as an ROI (an M-margin
  crop like the 2026-06-26 ROI campaign) — tighter crop, but a new mechanism and a
  second knob; if E21 is promising but marginal, that is the follow-up.
- **D2 — no `buf` composition legs.** E20 measured cellbuf ≈ cell on every clip (no
  PASS added, cov within noise). 12 legs bought nothing there; dropped here. Given
  up: re-testing BUF at E21's slightly higher latency.
- **D3 — COARSE_MAX_SIDE = 320** (~10x px cut, est. ~0.9 s). 448 is the pre-registered
  one-shot fallback, not a sweep. Given up: a resolution sweep (E20 D7 rationale —
  single knob, clean attribution).
- **D4 — coarse correctness is measured post-hoc, not gated at runtime.** There is no
  client-side truth at runtime (same as E20's wrong-hint exposure). Every run logs
  `coarse_hint` and post-hoc compares it to the GT cell at the SUBMIT frame
  (`hint_for` on the GT box) — that number is E21's real deliverable either way.

## Frozen config

Everything not named above is byte-identical to E20: Qwen2-VL-2B Q8_0 terse on Jetson
(JetsonBackend, max_side 1024, 15W + jetson_clocks — record `raw/jetson-power.txt`),
SAM2.1-hiera-tiny StreamCarry at 6.15 Hz, E14/E16 mask gate (app_tau 12.0), LOSS_S
1.0, wall-clock replay + E18 scorer (lock_iou 0.25, 30 fps). Clips + captions frozen:
car3/car14/car18/car10 "the red car", car9 "the white car", car7 "the silver car".
Data: `experiments/2026-07-03-real-video-replay/data/UAV123/` (already on disk).

## Code (executor writes; keep diffs localised)

- `replay_e21.py`: fork of `experiments/2026-07-04-prompt-scoped-acquire/replay_e20.py`.
  Changes ONLY in the acquire submission: add the coarse pass + quantise step ahead of
  the E20 scoped submit; CLI `--c2f` flag (default off = byte-equivalent E20/E18 path),
  `--coarse-side` (default 320); drop `--scope-hint` from the matrix path (E21's hint
  is computed, but keep the flag working for debugging). `mc_log` entries gain
  `"coarse_s", "coarse_box", "coarse_hint", "acquire_s"` (total incl. both passes).
  Extend the selfcheck: (a) stub backend returns a box in a known cell at coarse res
  -> fine submit receives that cell's rect; (b) coarse None -> the same attempt
  falls through to a full-frame submit (assert rect is None); (c) E20 checks still
  green. Selfcheck runs offline (no Jetson).
- `run_matrix.py`: E20 pattern. Matrix: smoke (`c2f` car10 x1, sanity: coarse_s < 1.5 s
  AND total acquire_s < 3.5 s AND a valid mapped box, else STOP per contingency) +
  `c2f` 6 clips x n=2 = **13 legs**. Run dirs `runs/c2f_<clip>_r<rep>/`.
- `summarize.py`: per-clip table + coarse-hint hit table (log vs GT cell at submit
  frame) + latency (coarse_s, total acquire_s vs E20's 1.57-2.07 and E18's ~4.85).
- `make_proof.py`: 2-3 committed captioned clips under `proof/`: at minimum one
  E20-cell vs E21-c2f side-by-side on an E20-flipped clip, and the most instructive
  failure (wrong coarse cell if one occurs — the automated analogue of E20's wrong
  probe).

## Scoring + verdict rules (frozen before any run)

Per clip: PASS = `genuine_lock` AND coverage >= 0.50, better of n=2. Primary arm `c2f`.

- **YES**: c2f >= 4/6 PASS (i.e. matches or beats E20 cell).
- **PARTIAL**: 2-3/6.
- **NO**: <= 1/6.
- Suffix **[prior-wrong]** if the coarse hint mismatches the GT submit-frame cell on
  >= 2 clips (counting a clip if either rep is wrong).
- **Regression guard**: no clip's c2f coverage may fall > 0.10 below its E18 A-leg
  best (car3 0.976, car7 0.285, car9 0.993, car10 1.000, car14 0.903, car18 0.711);
  a breach marks the arm REGRESSIVE regardless of locks.

## Pre-registered estimates (marked as estimates)

- Coarse pass ~0.8-1.0 s; total acquire ~2.6-3.0 s -> ~80-90 frames stale: WORSE than
  E20's ~58. So the honest expectation is **c2f <= E20 cell**: est. **2/6 PASS**
  (car10 and car9 survive — slow/large targets; car14 was marginal at E20's latency
  and likely drops).
- Coarse cell hit rate: est. **4/6** (car3's 16px target and car7's 40px near a cell
  boundary are the likely misses at 320px).
- If hit rate is high but PASSes drop vs E20, the verdict story is "the prior
  automates fine; the extra ~1 s re-opens the staleness gap" -> the follow-up lever
  is E22 (a ~ms prior) or D1's given-up M-margin crop.

## Execution plan (for the executor)

1. Branch `experiment/coarse-to-fine-acquire` off main (E20 must already be merged).
   Confirm the launch gate above. Run E20's `scope.py` selfcheck still green.
2. Write `replay_e21.py`; `--selfcheck` green; commit.
3. `raw/jetson-power.txt` via `ssh jetson "sudo nvpmodel -q; sudo jetson_clocks --show"`
   (NOPASSWD, non-interactive).
4. Smoke leg; apply the sanity/contingency rule above.
5. Full 13-leg matrix, logging to `raw/matrix.log`. **CRITICAL ANTI-STALL RULE: do NOT
   end your turn to "wait" — the E19 and E20 executors both stalled doing this. Poll
   `runs/*/results.json` count in a foreground loop in your own session until 13/13,
   then continue straight through.**
6. `summarize.py`; apply the frozen verdict rules mechanically; fill Results below
   (per-clip table incl. E20-cell and E18-A baseline columns, coarse-hint hit table,
   latency table, estimate-vs-actual, what broke/surprised, captioned proof clips).
7. Ledgers: append to `docs/results/part4-end-to-end.md`,
   `docs/questions/part4-end-to-end.md` (RQ-E21 + one-line verdict),
   `docs/decisions/part4-end-to-end.md` (D1-D4). Madrid wall-clock timestamps
   `YYYY-MM-DDThh:mmZ`. No emojis anywhere.
8. Commit: results.json COMMITTED; `data/` and `runs/*/overlay.mp4` gitignored (copy
   E20's `.gitignore`); proof clips COMMITTED. Use the trailer block your orchestrator
   gives you (Co-Authored-By + Claude-Session of the CURRENT session). **Never push,
   never merge to main, never commit on main.**
9. Final message = completion report: verdict, per-clip table, coarse hit rate, mean
   latencies, breakages, `git log --oneline main..HEAD`.

## Results (TBD)

| clip | E18 A best (gen/cov) | E20 cell best (gen/cov) | c2f r1 | c2f r2 | c2f best PASS? | coarse hint ok? | coarse_s | total acquire_s |
|---|---|---|---|---|---|---|---|---|
| car3 | F / 0.976 | F / 0.982 | | | | | | |
| car7 | F / 0.285 | F / 0.997 | | | | | | |
| car9 | F / 0.993 | **P** / 0.996 | | | | | | |
| car10 | **P** / 1.000 | **P** / 1.000 | | | | | | |
| car14 | F / 0.903 | **P** / 0.907 | | | | | | |
| car18 | F / 0.711 | F / 0.981 | | | | | | |

(The E20 column here is from the orchestrator's pre-audit peek at the run JSONs;
verify against E20's official README Results when it merges and correct if needed.)

Verdict: TBD. Coarse hit rate: TBD. Estimate-vs-actual: TBD.
What broke / what surprised: TBD.
