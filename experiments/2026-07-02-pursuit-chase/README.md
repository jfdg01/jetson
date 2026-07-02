# E5 — Pursuit chase: close the blind deficit instead of freezing it

**Pre-registered:** 2026-07-02T22:00Z (design + patch by Fable; executor runs the matrix and
fills Results only — the code is already written and committed, do NOT re-patch it).
**Status:** PRE-REGISTERED, not yet run. Branch `experiment/pursuit-chase`.

## Research question

**RQ-E5:** E4 left the follow ceiling at 0.5 m/s with 1.0/1.5 pinned to the E2 floor, naming
"first-acquire hover" as the mechanism. The E4 raw data says the binding constraint is subtler:
at 1.0 m/s the first lock lands **while the car is still in FOV** (lock 5.01 s, FOV exit 5.74 s),
but blind dead-reckoning commands only the *estimated target velocity* (`hist_vel()`), so the
~5.5 m deficit accrued during the acquire hover is **carried forever** (chase speed = target
speed, no closing term), and the velocity estimate's 0.39 m/s lateral error compounds unchecked
(ladder-1.0 CSV: copter drifts 11 m off-road over 40 s of REGROUND DR, then a blind wrong-relock
at t=48.6 s freezes it, gap explodes 15→35 m). **Does replacing velocity-matching DR with
position-seeking pursuit (command = estimated velocity + 0.5·(dead-reckoned position − copter
position), 2.5 m/s cap) lift the follow ceiling from 0.5 to >= 1.0 m/s, without regressing 0.5?**

PASS threshold per run: `in_fov_frac >= 0.90 AND recovered_after_occlusion` (identical to
E2/E4, directly comparable). **RQ-E5 = YES iff p-0.5 PASSes AND p-1.0 PASSes.**

## Context & rationale (audit of E4)

- E4's Results tables match its raw `runs/*/results.json` — numbers are valid.
- E4's *mechanism naming* is incomplete. "First-acquire hover" creates the deficit, but the
  hover ends with the car still visible at 1.0 m/s; what makes the deficit fatal is that no
  part of the controller can ever close it: PID needs the box (car exits FOV ~0.7 s after
  lock), and DR matches speed at best. Fixing the hover alone (e.g. moving during acquire)
  is not actionable anyway — before the first lock there is no velocity estimate to hold, so
  the E4-named "chase-velocity hold from t=0" lever is ill-posed. **Pursuit DR is the fix
  that exists**: after any lock, `hist` has position+velocity; pursuing the extrapolated
  position closes deficits from *any* source (first acquire, occlusion, estimate drift).
- Rejected alternative — raising acquire rate / shrinking the VLM latency: latency is already
  characterized (~5 s wall on Jetson Q8_0, E1/3b), no cheap headroom; and it would shrink,
  not remove, the deficit that pursuit closes generically. Recorded as the DECISIONS seed.
- Audit flag on E4's 1.5 row: "never locks" rests on n=1 where the FIRST acquire attempt
  (t=0 submit frame, car dead-center in FOV) was rejected — plausibly stochastic VLM/validate
  noise, since the identical setup at 1.0 accepted its first attempt. E5 runs 1.5 **twice**
  to probe this.
- Geometry for the estimates: FOV half-footprint at 8.8 m AGL is 3.81 m (FOCAL_PX 554.26,
  IMG_H 480); in-FOV holds to a gap of ~5.9 m (E4 ladder-1.0: exit at gap 6.15 m). Pursuit
  capped at 2.5 m/s closes a 1.0 m/s target at 1.5 m/s.

## What was changed (already committed on this branch — executor: do NOT edit these files)

One controller change in `experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py`,
behind a flag so the E2/E4 baseline is preserved:

- Module-level `pursuit_vel(hist_last, v_est, t, copter_ne, kp=0.5, vmax=2.5)`: blind-chase
  command = estimated velocity + 0.5/s · (position error to the dead-reckoned target
  position), total speed clamped to 2.5 m/s (under the PID's MAX_VX/VY 3.0; matches the
  existing per-axis hist_vel clamp).
- `--dr {velocity,pursuit}` (default `velocity` = E2/E4 behavior, bit-identical baseline).
  With `--dr pursuit`, the blind branch (`out is None`, any state) runs `pursuit_vel` on the
  same `hist` estimate before the body-frame transform. Nothing else changes: ACQUIRE before
  the first lock still hovers (empty `hist` — nothing to pursue), PID still owns the loop
  whenever a box is visible, CSV columns unchanged.
- Selfcheck extended with a `pursuit_vel` truth table (zero-error passthrough, deficit clamps
  to 2.5, lateral sign) — `--selfcheck` passing as committed.

Known limitation (pre-registered, out of scope): after a *wrong* relock on static background,
`hist` refills with static positions, the motion gate re-fires, and pursuit chases a static
predicted position — i.e. pursuit does not fix identity errors (that is the reserved E3b CLIP
gate). Pursuit should however make wrong-relocks *rarer* at 1.0 by keeping the copter near the
true track, where REGROUND sees the real car.

## Run matrix (executor: this is the whole job — 4 SITL trials, ~1 h)

Same rig as E2/E3/E4: local-VLM path (Jetson only serves the VLM over ssh as usual; do NOT
pass `--remote-carry`), local 3090 carry @1024, 75 s per trial. All runs use the E4 chosen
config `--loss-gate motion` plus `--dr pursuit`. `run_e5.sh` drives all four and snapshots
per run (results/CSV/mp4 are clobbered between runs — snapshot is immediate, in the script):

```bash
bash experiments/2026-07-02-pursuit-chase/run_e5.sh
```

| run | command tail | snapshot dir | role |
|---|---|---|---|
| p-0.5 | `--speed 0.5 --loss-gate motion --dr pursuit` | `runs/p-0.5/` | regression guard (E4 PASS speed) |
| p-1.0 | `--speed 1.0 --loss-gate motion --dr pursuit` | `runs/p-1.0/` | the RQ speed |
| p-1.5 | `--speed 1.5 --loss-gate motion --dr pursuit` | `runs/p-1.5/` | stretch |
| p-1.5b | `--speed 1.5 --loss-gate motion --dr pursuit` | `runs/p-1.5b/` | repeat: probes E4's suspected-stochastic first-acquire rejection |

Baselines are the E4 Stage 2 rows (`--dr velocity`, same gate) in
`../2026-07-02-follow-hardening/README.md` — do NOT re-run them.

## Verdict rules (mechanical — executor does not deliberate)

- Per-run gate: **PASS iff `in_fov_frac >= 0.90 AND recovered_after_occlusion == true`**
  (read both from the snapshotted `results.json`; the script's printed `gate` line uses the
  same rule).
- **Regression clause:** if p-0.5 FAILs, record `RQ-E5 = NO (pursuit regresses the 0.5
  baseline)` and still run/record the remaining rows — the regression mechanism (from the
  CSV: overshoot oscillation shows as sign-flipping `vx_cmd` while blind) is the finding.
- **RQ-E5 = YES iff p-0.5 PASS AND p-1.0 PASS.** Otherwise NO.
- **1.5 verdict:** PASS only if BOTH p-1.5 and p-1.5b PASS. If they split, record
  `1.5 = SPLIT (stochastic)` — the ceiling then excludes 1.5 and the split itself confirms
  the audit's stochastic-first-acquire flag; note which run locked and when.
- **New ceiling = highest speed with PASS** under the rules above.
- Diagnostics to put as one line each under the Results table (from `trial.csv`):
  - p-1.0: gap (m, `hypot(copter−rover)`) at first `in_fov` 1→0 transition, and wall time
    until `in_fov` returns to 1 (pursuit re-entry time). If it never returns, say so.
  - p-1.5/b: `first_lock_s` and whether the t=0 attempt was accepted (first CARRY row time).
- **Abort criteria:** any run hanging > 10 min past its 75 s trial (SITL boot included),
  crash, or missing output file → snapshot whatever exists, mark that run INVALID in
  Results, continue with the next run. Do not re-run INVALID rows more than once.

## Estimates (mark actuals vs these — a wrong estimate is content)

- **p-0.5:** PASS, in-FOV ~1.000 as E4 (pursuit near-inert when the deficit is small;
  residual risk is closing-overshoot oscillation). ~85% PASS. ESTIMATE.
- **p-1.0:** PASS ~55%. Deficit at first loss ~6 m; pursuit closes at ~1.5 m/s → car back
  in FOV in roughly 1–3 s; expected in-FOV ~0.90–0.95 (dangerously near the gate — a
  marginal number here is itself informative). Main risk: REGROUND wrong-relock during the
  blind chase re-polluting `hist`. ESTIMATE.
- **p-1.5 / p-1.5b:** FAIL more likely than not (~60–70% each). Deficit at first lock ~8 m
  (car left FOV at ~3.8 s, before the ~5 s resolve); pursuit must close ~1.0 m/s of speed
  advantage AND relock via validated REGROUND. At least one of the two locking at all would
  already overturn E4's "1.5 never acquires". ESTIMATE.
- **Runtime:** ~1 h total (4 trials @ ~75 s + SITL/VLM boot each). ESTIMATE.

## Results (TBD — executor fills)

| run | speed | in_fov | first_lock_s | n_regrounds | relock_walls_s | recovered | verdict | E4 (velocity DR) was |
|---|---|---|---|---|---|---|---|---|
| p-0.5 | 0.5 | | | | | | | PASS 1.000 |
| p-1.0 | 1.0 | | | | | | | FAIL 0.073 |
| p-1.5 | 1.5 | | | | | | | FAIL 0.051 (never locked) |
| p-1.5b | 1.5 | | | | | | | — |

- p-1.0 diagnostics (gap at FOV exit, re-entry wall): TBD
- p-1.5/b first-attempt read: TBD
- RQ-E5 verdict + new ceiling: TBD
- Estimate-vs-actual: TBD

## Closeout checklist for the executor

1. Fill Results above (table + diagnostics + estimate-vs-actual).
2. Append one RESULTS row per run under Part IV in `docs/results/part4-end-to-end.md`
   (config string: `local-VLM, 3090 carry @1024, loss-gate motion, dr pursuit, 75 s`).
3. Append the RQ-E5 verdict (one entry, one-line verdict per sub-question if split) in
   `docs/questions/part4-end-to-end.md` — the per-Part doc, never the root.
4. Append a DECISIONS entry in `docs/decisions/part4-end-to-end.md`: chose pursuit DR over
   acquire-latency reduction (rationale in "Context & rationale" above; what was given up:
   nothing shrinks the ~5 s VLM wall, pursuit sidesteps it).
5. Commit on `experiment/pursuit-chase`, message `E5 pursuit-chase: <one-line verdict>`.
   Madrid wall-clock `YYYY-MM-DDThh:mmZ` timestamps, no emojis.
