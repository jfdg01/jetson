# P6.2-COUPLING — coupled vs decoupled warm carry (isolates C1)

**Pre-registered 2026-07-23T23:05Z (Madrid). Frozen before any run. Self-contained handoff.**
Spine: `experiments/PART6-PROGRAM-warm-start-significance.md`. Rides the R-35 flight harness and
the P6.2-DELIVERY seed bank + WARM flights. If this README and the program doc disagree on the
frozen gate, the program doc wins.

## Status / next step

- **DONE 2026-07-24.** Ran after DELIVERY on the R-35 harness. Verdict: **outcome (ii) — bounded
  null**: closing the control loop does not degrade the warm track (Wilcoxon p=0.596, CI within the
  schedule-noise band). Next in the Wave-B slate: R-36 (maintain-vs-select McNemar).

## Question

RQ-P6.2-COUPLING (C1): does closing the control loop — letting the warm-maintained track *drive*
the copter so the pixels become a consequence of its own control — degrade the maintained track,
versus feeding the same warm perception while an oracle drives? Isolates self-induced ego-motion
from target motion.

## Design (frozen)

- **Paired-continuous, Wilcoxon signed-rank (two-sided) + bootstrap 95% CI** on per-scenario mean
  post-prompt follow-error (px) of the warm track vs `actor_box`.
- **Arm A = COUPLED:** the warm track drives the PID (`CascadePID` -> `send_velocity_body`); the
  drone chases its own perception. (These are exactly the P6.2-DELIVERY WARM flights — reused, not
  re-flown.)
- **Arm B = DECOUPLED:** identical warm perception (same seed, same `StreamCarry`), but the oracle
  `actor_box` drives the PID — the feedback path from perception to control is cut. The warm track
  is scored but does not steer.
- **Unit = same 25 distinct CARLA seeds** as DELIVERY. Follow-error metric is identical in both arms
  (warm track vs `actor_box`), so the only difference is who steers.
- **`n_effective == n_rows`** — Wilcoxon cannot be cluster-deflated (`grounding/stats.py`
  `paired_continuous` refuses). Therefore **one flight per arm per seed, NO reps**, and **per-item
  (per-seed) follow-error values are saved** (the E20 / P5.2b lost-aggregate lesson — never store
  only the aggregate).

### FROZEN GATE (verbatim, two-sided — both outcomes are content)

- (i) **coupled significantly worse** (Wilcoxon p<0.05, coupled error > decoupled) -> closed-loop
  coupling degrades the maintained track; report the magnitude + CI.
- (ii) **no significant difference AND the bootstrap CI lies within the measured schedule-noise
  band** -> C1 closed as **"warm carry survives self-induced ego-motion"**, a *bounded null* — never
  claimed as proven equivalence, only that any coupling penalty is below the noise floor.

The schedule-noise band is the P6.2-DELIVERY band (3 seeds x 2 flights/arm). A "no difference" that
exceeds the band is inconclusive, not a pass.

### Honesty caveat (inherited, S5)

Control-coupling claim only. A CARLA PASS says the warm track survives *this rig's* ego-motion; it
does not transfer to real-imagery perception.

## Command (as run)

The pre-registered command above named `run_p62_flight.py --arms decoupled`; that flag surface did
not exist. The decoupled arm was built minimally in the matrix driver instead (a `--oracle-drive`
control path in `run_p62_flight.py` + a `refly_decoupled` loop in `run_p62_matrix.py`). Deviation
recorded openly; the *design* is unchanged (same 25 seeds, warm perception byte-identical, only the
PID input swaps warm-track -> `actor_box`). Needs a live CARLA (port 2000) + SITL (tcp 5760):

```bash
# coupled arm = the P6.2-DELIVERY WARM flights (already on disk under runs/p62_delivery)
# decoupled arm re-flies each admitted seed with the oracle actor_box driving the PID:
.venv-ft/bin/python runners/run_p62_matrix.py --coupling \
    --coupled-root runs/p62_delivery --out runs/p62_coupling
# scoring (Wilcoxon two-sided + bootstrap 10000) runs inside run_coupling -> runs/p62_coupling/coupling.json
```

The decoupled re-fly uses `build_grounding_carry(carry_only=True)` — no Jetson `llama-server` is
booted, because in `oracle_gt` mode the warm producer seeds from the GT box and never calls
`acquire`. Only SAM2 carry (3090, rate-capped to the Jetson 2.69 Hz) + PID + CARLA render run.

## Environment / versions

Identical to P6.2-DELIVERY (same rig, same seeds). Pins stamped into `runs/p62_coupling/env.json`.

## Reuse map

Same seams as P6.2-DELIVERY. Additional: the DECOUPLED arm swaps only the PID *input* from the warm
track to `actor_box` at `run_phase_c.py:_control_step_c` (:584); perception (WARM producer +
`StreamCarry`) is byte-identical to the coupled arm. `grounding/stats.py` `paired_continuous` :171
(refuses deflation), bootstrap CI.

## Estimates (up front)

- Follow-error (est): coupled 25-60 px, decoupled 20-50 px (the coupled penalty, if any, is the
  ego-motion cost). Likely outcome (ii) — bounded null — because the nadir camera + position-slaved
  render make ego-motion largely a translation the PID already regulates. If the copter's own
  chase induces oscillation, (i) fires; that is the interesting negative.
- Runtime (est): only the DECOUPLED 25 flights are new (~1.5 h); coupled arm is reused. + scoring.

## Results (n=25, 2026-07-24)

| metric | COUPLED | DECOUPLED | note |
|---|---|---|---|
| mean follow-err (px) | 26.77 | 63.18 | mean inflated by carry-drift outliers (below); the median is the honest centre |
| **median paired diff (px)** | — | — | **−0.42** (coupled minus decoupled) |
| **Wilcoxon signed-rank, p (two-sided)** | — | — | **p = 0.596 (n.s.)** |
| bootstrap 95% CI of median paired diff | — | — | **[−4.56, +4.08] px** |
| schedule-noise band (warm arm, px) | — | — | max |rep diff| **6.70**, mean 2.58 (DELIVERY, 3 seeds × 2 flights) |

**Verdict: outcome (ii) — BOUNDED NULL. C1 closed as "warm carry survives self-induced ego-motion."**
The paired difference is not significant (Wilcoxon p=0.596) and its 95% CI [−4.56, +4.08] px lies
within the warm-arm schedule-noise band (±6.70 px); the median difference is −0.42 px. Closing the
control loop — letting the warm track drive the copter so the pixels become a consequence of its own
motion — does **not** systematically degrade the maintained track versus feeding the same warm
perception while an oracle drives. Per the frozen gate this is a *bounded null*: any coupling penalty
is below the noise floor, **not** a proven equivalence.

**Not the primary signal — stochastic carry-drift outliers (why the means diverge):** the coupled
mean (26.8) < decoupled mean (63.2) only because carry drift fired on *different* seeds per run and
the decoupled re-fly happened to draw two catastrophic SAM2 carry leaks the coupled run did not —
decoupled seed14 (760 px) and seed21 (249 px) — while both arms drifted on seed13 (coupled 377,
decoupled 285) and seed08 (~72 both). This is **run-specific carry variance, not a coupling penalty**:
it appears in the arm without a feedback loop, and the signed-rank/median (which the outliers cannot
dominate) shows no difference. 22 of 25 seeds sit in 5–25 px in both arms.

**Caveat on the band (honest):** the warm-arm band is n=3 pairs and skewed by one (seed1 |diff|=6.70;
the other two <1 px), so the CI's ±4.3 px half-width exceeds the two quiet pairs while staying under
the noisy one. The bounded-null reading rests primarily on the non-significant Wilcoxon and the
near-zero median (−0.42 px); the band comparison corroborates. (Cold's rep-noise is ~69 px — a
different, off-target regime, not the reference for a warm-vs-warm comparison.)

**Proof (committed under `proof/`):**
1. `p62_coupling_paired.png` — per-seed paired follow-error (numbers are the point). Left: 21 seeds
   on the y=x diagonal (5–25 px), 4 labelled carry-drift outliers. Right: sorted paired diff hugging
   zero inside the ±6.70 px band and the CI, 3 outliers off-scale, p=0.596. Reproducible:
   `make_proof.py` from `runs/p62_coupling/coupling.json`.
2. `coupled_seed24_i200_iou084.png` + `coupled_seed24_i399_iou093.png` — the COUPLED arm chasing its
   own perception: the track drives the copter and the target stays framed near centre across the
   flight (iou 0.84 → 0.93, on_tgt), buildings shifted between the two frames = the self-induced
   ego-motion made visible. Viewed with the Read tool.
3. `decoupled_seed14_carryleak.png` — contrast: the failure mode is *carry*, not coupling. GT (green)
   at the right edge, warm-track box (red) leaked to the top-left corner, on_tgt=False — a genuine
   SAM2 carry leak in the arm with **no** feedback loop. Valid render (a real Town10HD frame), not a
   defect.
