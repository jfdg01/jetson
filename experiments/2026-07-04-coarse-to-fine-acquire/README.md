# E21 coarse-to-fine acquire (drafted 2026-07-04)

**Status: COMPLETE — RQ-E21 NO (REGRESSIVE) [prior-wrong] (c2f 1/6).** Branch
`experiment/coarse-to-fine-acquire`. Pre-registered 2026-07-04T12:05Z; 13-run matrix
executed 2026-07-04T13:00Z-13:16Z; results written 2026-07-04T13:25Z. Launch gate
CONFIRMED against E20's merged README (PARTIAL [hint-fragile], cell 3/6) before running.

Drafted
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

## Results (2026-07-04T13:25Z)

Run: 13/13 legs, zero crashes (`raw/matrix.log`, rollup `raw/summary.txt`). Jetson
15W + jetson_clocks (`raw/jetson-power.txt`, GPU pinned 624.75 MHz). Every c2f leg got
a valid (non-None) coarse box, so the pre-registered COARSE_MAX_SIDE 320->448
contingency never fired (the coarse premise is not dead at the plumbing level — it is
dead at the *accuracy* level, which is the result). The E20 cell / E18 A columns are
verified against E20's merged official README table.

### Per-clip table (PASS = genuine_lock AND coverage >= 0.50; clip = best of n=2)

| clip | E18 A best (gen/cov) | E20 cell best (gen/cov) | c2f r1 (gen/cov) | c2f r2 (gen/cov) | c2f best PASS? | coarse hint ok? | coarse_s | total acquire_s |
|---|---|---|---|---|---|---|---|---|
| car3 | F / 0.976 | F / 0.982 | F / 0.980 | F / 0.980 | FAIL | MISS (bottom center vs bottom left) | 0.97 | 2.80 |
| car7 | F / 0.285 | F / 0.997 | F / 0.000 | F / 0.000 | FAIL | HIT (top center) | 0.93 | 2.73 |
| car9 | F / 0.993 | **P** / 0.996 | F / 0.991 | F / 0.989 | FAIL | HIT (bottom center) | 0.97 | 2.80 |
| car10 | **P** / 1.000 | **P** / 1.000 | F / 0.000 | F / 0.000 | FAIL | MISS (middle right vs center) | 1.00 | 2.90 |
| car14 | F / 0.903 | **P** / 0.907 | **P** / 0.590 | **P** / 0.590 | **PASS** | MISS (top left vs center) | 0.97 | 2.57 |
| car18 | F / 0.711 | F / 0.981 | F / 0.888 | F / 0.885 | FAIL | MISS (top left vs middle left) | 0.97 | 2.57 |

c2f = **1/6 PASS** (only car14 — and its coverage regressed 0.907 -> 0.590). E20 cell
was 3/6; E18 A was 1/6 (car10). Both clips E20 flipped (car9, car14) plus the one E18
held (car10) come apart under c2f: car9 loses the genuine lock, car10 wrong-cells to
cov 0.000, car14 survives only as a low-coverage regression.

### Coarse-hint hit table (logged coarse cell vs GT cell at the submit frame, D4)

| clip | coarse cell | GT cell | hit? |
|---|---|---|---|
| car3 | bottom center | bottom left | MISS |
| car7 | top center | top center | **HIT** |
| car9 | bottom center | bottom center | **HIT** |
| car10 | middle right | center | MISS |
| car14 | top left | center | MISS |
| car18 | top left | middle left | MISS |

**Coarse-hint hit rate = 4/12 reps (2/6 clips: car7, car9; deterministic per clip,
both reps identical).** 4/6 clips voted the wrong 3x3 cell -> suffix **[prior-wrong]**
(threshold was >= 2). The 320px coarse pass grounds "the red car" off-target even for
the large, centred, "easy" targets: car10 (E20/E18's most reliable clip) landed
`middle right`, car14 landed `top left` — both are actually `center`.

### Latency (per `mc_log`: coarse_s = coarse pass, acquire_s = both passes)

| quantity | E18 full-frame | E20 scoped cell | E21 coarse-to-fine |
|---|---|---|---|
| coarse pass wall | — | — | **0.97 s** (n=12, 0.93–1.00) |
| total acquire wall | ~4.85 s | 1.85 s | **2.73 s** (n=12, 2.57–2.90) |
| frame backlog at arrival | ~146 | 47–62 | 77–87 |
| arrival-frame IoU (r1) | 1/6 >= 0.25 | car9 0.32, car10 0.57, car14 0.73 pass | car3 0.00, car7 0.00, car9 **0.24**, car10 0.00, car14 0.55, car18 0.00 |

The coarse pass is cheap (0.97 s, ~as estimated) but it is *additive*: total acquire
rises 1.85 s -> 2.73 s, so the backlog grows 47–62 -> 77–87 frames. car9 is the clean
demonstration: correct cell, same frame-0 fine crop as E20, but the arrival-frame IoU
falls 0.32 (E20) -> **0.24** (E21) — just under the 0.25 lock threshold — purely
because the extra ~1 s let the target move further before arrival. The prior automates
fine on car9; the automation's own latency un-flips it.

### Verdict (frozen rules applied mechanically)

c2f 1/6 -> **NO** (rule: <= 1/6). Regression guard: **BREACH** on car7 (0.000 vs E18A
0.285), car10 (0.000 vs 1.000), car14 (0.590 vs 0.903) -> **(REGRESSIVE)**. Wrong
coarse cell on 4/6 clips (>= 2) -> **[prior-wrong]**. Final: **RQ-E21 NO (REGRESSIVE)
[prior-wrong]**. The automated coarse prior is both too inaccurate (4/6 wrong cell) and
too slow (the extra pass re-opens the very staleness gap the crop was meant to close).

### Estimate vs actual

| estimate | actual | verdict |
|---|---|---|
| coarse pass ~0.8–1.0 s | 0.97 s mean (0.93–1.00) | hit |
| total acquire ~2.6–3.0 s | 2.73 s mean (2.57–2.90) | hit |
| c2f <= E20 cell, ~2/6 PASS (car10, car9 survive) | **1/6** (car14 only); car9 AND car10 both dropped | **worse** |
| coarse cell hit rate ~4/6 (car3, car7 the likely misses) | **2/6** (car7 HIT, car9 HIT); car3/car10/car14/car18 MISS | **worse, wrong misses** |

Both quality estimates were too optimistic and mis-attributed. The latency estimates
were exact.

### What broke / what surprised

- **Nothing crashed; 13/13 legs clean, every coarse pass returned a valid box** (so the
  320->448 contingency did not trigger). The failure is entirely in accuracy + latency,
  not plumbing.
- **The coarse prior misses the EASY targets.** The pre-registration guessed the small
  car3 (16 px) and boundary car7 (40 px) would miss; instead car7 HIT and the large,
  centred car10/car14 — E20/E18's most reliable clips — MISSED (grounded `middle right`
  / `top left` for `center` targets). At 320 px the VLM's box for "the red car" is
  imprecise enough that its *centroid* falls in a neighbouring cell even for a big
  central car. Cell voting does not rescue this: an off-by-one cell crops away the
  target.
- **A correct coarse cell is not enough — the extra pass un-flips car9.** car9's coarse
  cell was right and its fine crop identical to E20's, yet the genuine lock is lost:
  arrival-frame IoU 0.32 -> 0.24, straddling the 0.25 threshold, because ~1 s more
  latency = ~29 more frames of target motion before arrival. This is the pre-registered
  "the prior automates fine; the extra ~1 s re-opens the staleness gap" outcome,
  realised on the one clip where the prior worked.
- **car7 collapses even with a correct cell (cov 0.997 -> 0.000).** Same frame-0 fine
  crop as E20, but the longer acquire widens the SAM2 init(frame 0) -> first-live-step
  (frame 82 vs E20's ~55) jump; for the fast, small silver car SAM2 cannot bridge it,
  the mask goes empty, and it drops to REGROUND (3 gate rejects). Latency hurts carry
  bridging, not just the arrival-frame metric.
- **Wrong cells reproduce E20's [hint-fragile] automatically.** car10's `middle right`
  crop contains no red car; the VLM hallucinates a box at the frame's right edge
  (~x 1240–1280), carry locks it (cov 0.000), and the poisoned mask-gate template then
  rejects all 10 full-frame REGROUND re-offers of the true car (gate_rej=10). The E20
  wrong-hint probe is now an unforced, self-inflicted error whenever the coarse pass
  votes wrong — which is 4/6 of the time.
- **Net:** automating the E20 hint with a coarse VLM pass is a dead end on both axes.
  The follow-up lever is E22 (a ~ms CPU motion+colour prior) or E21-D1's given-up
  M-margin ROI crop (a tighter, latency-cheaper prior geometry), not a second VLM pass.

### Proof clips (committed under `proof/`)

- `proof/car9_E20cell_vs_E21c2f.mp4` — the automation-cost before/after: top = E20
  `cell_car9_r1` (operator "bottom center" hint, genuine PASS); bottom = E21
  `c2f_car9_r1` (automated pass votes the SAME correct cell, but the extra ~1 s coarse
  pass drops the arrival IoU 0.32 -> 0.24 and the genuine lock is lost). A correct
  automated hint is still not free.
- `proof/car10_E20cell_vs_E21c2f_wrongcell.mp4` — the automated [prior-wrong] failure
  (the analogue of E20's wrong-hint probe): top = E20 `cell_car10_r1` (operator
  "center", PASS cov 1.00); bottom = E21 `c2f_car10_r1` (coarse pass votes `middle
  right`, hallucinates a red box on the empty right edge, cov 0.000, and poisons the
  mask gate — 10 REGROUND rejects, never recovers).
