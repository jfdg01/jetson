# E4 — Follow hardening: fix the two binding modes E2 named

**Pre-registered:** 2026-07-02T21:05Z (design + patches by Fable; executor runs the matrix and
fills Results only — the code is already written and committed, do NOT re-patch it).
**Status:** READY TO RUN. Branch `experiment/follow-hardening`. Patches to `phase3_sitl.py` +
`stream_carry.py` landed and selfcheck-verified; this campaign holds the record + run artifacts.

## Research question

**RQ-E4:** E2 proved the levers-on follow ceiling is `< 0.5 m/s`, and named two failure modes the
occlusion levers don't touch: (A) **confident-latch** — under the bridge SAM2 returns a confident,
centered box on the *occluder*, so the `box is None` loss test never fires and REGROUND never
triggers (killed 0.5 m/s); (B) **acquire-latency** — the ~5 s async VLM acquire completes on a
frame where the stale box no longer overlaps the moved car, so carry locks background and the car
outruns the FOV (killed 1.0/1.5 m/s). **Do the two targeted fixes lift the ceiling, and to what
speed?**

- **RQ-E4a (confident-latch):** does a trust-aware loss gate make REGROUND fire under occlusion at
  0.5 m/s, recovering the follow (`n_regrounds >= 1`, `recovered_after_occlusion`, in-FOV >= 0.90)?
- **RQ-E4b (acquire-latency):** does initializing carry on the *submit* frame + replaying the
  buffered gap lift the >= 1.0 m/s trials off the floor (E2: in-FOV 0.076 / 0.051, never locked)?

## What was changed (already committed on this branch — executor: do NOT edit these files)

Two fixes. One is a strict correctness fix (always on, no flag); one is a lever (a flag, so its
effect is isolable against the frozen E2 baseline).

### Fix B — submit-frame carry init + catch-up replay (always on; the acquire-latency fix)

`phase3_sitl.py`. Before: carry was `make_carry`'d on the *current* frame with the ~2.5–5 s-stale
VLM box (the old `phase3_sitl.py:85` ponytail note flagged this). At 0.25 m/s the ~35 px drift was
harmless; at >= 1.0 m/s the box no longer overlaps the car and SAM2 locks background — E2's
"never locked" mode. Now:

- The SM keeps the frame the acquire was **submitted** on (`_submit_frame`, `_submit_t`) and
  initializes carry on *that* frame, where the VLM box is actually true.
- A rolling `acq_buf` (frame + pose @0.5 s while not in CARRY) is **replayed** through the fresh
  StreamCarry when the lock lands, so (1) the SAM2 track is brought current to ~now, and (2) `hist`
  is seeded with the target's trajectory *across the acquire gap* — so dead-reckoning has a real
  velocity the instant tracking resumes, and a car that outran the FOV during acquire can be chased
  blind instead of the copter freezing at home.
- `make_carry` signature is now `(frame_bgr, box, t_submit)`; the remote (3b) path is unchanged
  behaviorally (no replay/gate — a ponytail note says port it if 3b re-gates).

### Fix A — trust-aware loss gate (flag `--loss-gate {none,score,motion}`; the confident-latch fix)

A module-level `gate_box(box, score, mode, tau, motion_stale)` demotes an untrusted carry box to
`None`, so the *existing* LossGate (3 s) -> REGROUND machinery fires on a confident-but-wrong box
exactly as it does on an honest loss. Two modes (why two: see Risks):

- **`score`** — `stream_carry.py` now exposes `StreamCarry.last_score` (the SAM2.1
  `object_score_logits` of the last step; verified present in `track_step` output). Box demoted to
  loss when `last_score < --score-tau` (default 0.0: SAM2's own present/absent logit boundary).
  Remote path returns no score, so this mode is inert there (documented).
- **`motion`** — geometry-based backstop: while in CARRY, if the box's *estimated world position*
  stays static (`hist_vel()` magnitude `< 0.1 m/s`) for `> 2 s`, latch `motion_stale` -> demote to
  loss. We were told to follow a *mover*; a box that stops moving under the bridge is the occluder.

`--loss-gate none` reproduces E2 exactly (gate inert), so the E2 rows are the frozen baseline; do
not re-run them as a "control" — they are in `docs/results/part4-end-to-end.md` already.

Selfcheck (`phase3_sitl.py --selfcheck`) extended and passing: asserts carry is initialized on the
submit-tick frame (0, 16), not the resolve-tick frame (2, 20), plus a `gate_box` truth table.

## Run matrix (executor: this is the whole job — ~5 SITL trials, ~1 h)

Same rig as E2/E3: local-VLM path (Jetson **not** needed; do NOT pass `--remote-carry`), local 3090
carry @1024. `run_e4.sh` drives it and snapshots per run (the trial CSV/mp4 are overwritten each
run — the E2/E3 clobber gotcha; the script copies immediately). Two stages:

**Stage 1 — gate selection @ 0.5 m/s (the confident-latch speed), 3 runs:**

| run | command tail | snapshot dir |
|---|---|---|
| none | `--speed 0.5 --loss-gate none` | `runs/s1-none/` |
| score | `--speed 0.5 --loss-gate score --score-tau 0` | `runs/s1-score/` |
| motion | `--speed 0.5 --loss-gate motion` | `runs/s1-motion/` |

**Chosen-gate rule (mechanical — do not deliberate):** the chosen gate is the one whose 0.5 run has
`n_regrounds >= 1` AND `recovered_after_occlusion == true` AND `in_fov_frac >= 0.90`. If **both**
score and motion qualify, choose **score** (uses SAM2's own signal, no tuned constant). If
**neither** qualifies, record that plainly (RQ-E4a = no with the mechanism from the CSV) and still
run Stage 2 with **motion** to characterize the ladder. `none` is expected to reproduce E2's
confident-latch FAIL (in-FOV ~0.48, `n_regrounds = 0`) — that is the control, not a candidate.

**Stage 2 — speed ladder with the chosen gate, 2 runs** (0.5 already have it from Stage 1):

| run | command tail | snapshot dir |
|---|---|---|
| 1.0 | `--speed 1.0 --loss-gate <chosen>` | `runs/ladder-1.0/` |
| 1.5 | `--speed 1.5 --loss-gate <chosen>` | `runs/ladder-1.5/` |

**Ceiling = highest speed with PASS** (in-FOV >= 0.90 AND recovered_after_occlusion), the E2 gate.

## Gates and metrics

Per-run gate = `in_fov_frac >= 0.90 AND recovered_after_occlusion` (identical to E2/3a, so numbers
are directly comparable to the E2 rows). New signal in the trial CSV: `carry_score` column (SAM2
object-score logit per CARRY frame) — if the `score` gate under/over-fires, its distribution vs the
occlusion window (`occluded == 1`) is the diagnostic; put a one-line read in Results.

## Estimates (mark actuals vs these — a wrong estimate is content)

- **0.5 / none:** FAIL, reproduces E2 confident-latch (in-FOV ~0.48, `n_regrounds = 0`). ESTIMATE.
- **0.5 / motion:** PASS — geometry can't be fooled by a confident occluder; REGROUND fires
  ~2 s into the occlusion, relocks the car on egress. ~75% PASS. ESTIMATE.
- **0.5 / score:** uncertain (~50%). Risk: SAM2 may be *confidently wrong* on the occluder
  (high `object_score_logits` on the bridge blob) — if so `score` won't fire and that is itself the
  finding (SAM2 self-confidence doesn't separate the latch; motion is why there's a backstop).
  ESTIMATE.
- **1.0 / chosen:** genuinely uncertain (~50%). Submit-frame init + replay should land the lock on
  the car (fixing E2's "locked background"), but the copter still hovers through the ~5 s *first*
  acquire before the replay seeds DR — if the car clears the FOV in that window, in-FOV still
  misses 0.90. Fixing first-acquire hover (hold a guessed chase velocity from t=0) is deliberately
  **out of E4 scope** — named as the next lever if 1.0 fails here. ESTIMATE.
- **1.5 / chosen:** likely still FAIL (initial-hover window unrecoverable at this speed). A measured
  FAIL with the mechanism named is thesis content. ESTIMATE.
- **Effort:** ~1 h (5 trials @ ~90 s + SITL boot each, no patching).

## Risks / watch items (pre-registered, not after seeing data)

- **Replay stall:** when a lock lands, `acq_buf` (<= 24 frames @0.5 s) is replayed synchronously
  inside the control loop — worst case ~24 SAM2 steps (~4 s) but ~10 (acquire ~5 s) typical. A
  one-time burst while the copter is DR-chasing/hovering; if a run shows a multi-second `loop_ms`
  spike at the lock instant, that's this, note it. Does not affect the in-FOV metric (pure geometry).
- **`object_score_logits` calibration:** verified present in the SAM2.1 output; NOT verified that
  it separates the occluder-latch case. That's exactly what Stage 1 `score` measures — inspect the
  `carry_score` column if it behaves oddly.
- **motion gate false-trip on a parked target:** a car that legitimately parks trips the gate ->
  one REGROUND -> re-locks the still-visible parked car. Acceptable (ponytail note in code); only a
  problem if a scenario *requires* holding a parked target, which none here do.

`ADVISOR (advisor tool was disabled this session — if a run fails in a way this design did NOT
predict, e.g. the score gate fires during clean tracking, or replay corrupts the track so 0.25-class
speeds regress: reproduce once, record the CSV symptom, proceed on own judgment — the E2/E3
precedent.)`

## Results (TBD — executor fills)

Run: `bash experiments/2026-07-02-follow-hardening/run_e4.sh` then fill both tables.

**Stage 1 — gate selection @ 0.5 m/s:**

| gate | in_fov | n_regrounds | relock | recovered | verdict | notes |
|---|---|---|---|---|---|---|
| none | TBD | TBD | TBD | TBD | TBD (expect FAIL, E2 repro) | |
| score | TBD | TBD | TBD | TBD | TBD | carry_score read: TBD |
| motion | TBD | TBD | TBD | TBD | TBD | |

Chosen gate: **TBD** (per the mechanical rule above).

**Stage 2 — speed ladder, chosen gate:**

| speed | in_fov | first_lock_s | n_regrounds | recovered | verdict | E2 was |
|---|---|---|---|---|---|---|
| 0.5 | (from Stage 1) | | | | TBD | FAIL 0.484 |
| 1.0 | TBD | TBD | TBD | TBD | TBD | FAIL 0.076 |
| 1.5 | TBD | TBD | TBD | TBD | TBD | FAIL 0.051 |

**New ceiling:** TBD (E2 was `< 0.5`). **RQ-E4a:** TBD. **RQ-E4b:** TBD.

## Definition of done

1. This README's Results filled (both tables, estimate-vs-actual noted where they diverge).
2. RESULTS rows (one per run) appended under Part IV in `docs/results/part4-end-to-end.md`.
3. QUESTIONS entry (RQ-E4a / RQ-E4b + one-line verdicts) in `docs/questions/part4-end-to-end.md`.
4. DECISIONS entry in `docs/decisions/part4-end-to-end.md` **only if** a non-trivial choice arose
   (e.g. which gate was kept and why, or a scope call on first-acquire hover).
5. Commit on `experiment/follow-hardening`. Madrid wall-clock `YYYY-MM-DDThh:mmZ` timestamps, no
   emojis. Per-Part docs, never the root ledger files.
