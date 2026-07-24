# P6.2-COUPLING — coupled vs decoupled warm carry (isolates C1)

**Pre-registered 2026-07-23T23:05Z (Madrid). Frozen before any run. Self-contained handoff.**
Spine: `experiments/PART6-PROGRAM-warm-start-significance.md`. Rides the R-35 flight harness and
the P6.2-DELIVERY seed bank + WARM flights. If this README and the program doc disagree on the
frozen gate, the program doc wins.

## Status / next step

- **PRE-REGISTERED, NOT RUN.** Gated on R-35 (the harness) and on P6.2-DELIVERY producing its WARM
  flights (this experiment reuses them as the coupled arm). Runs after DELIVERY.

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

## Command (intended — runner built under R-35, not yet runnable)

```bash
# coupled arm = the P6.2-DELIVERY WARM flights (already on disk); decoupled arm re-flies with oracle drive
.venv-ft/bin/python runners/run_p62_flight.py --arms decoupled --bank runs/p62_delivery/bank.jsonl \
    --oracle-drive --out runs/p62_coupling
.venv-ft/bin/python runners/score_p62.py --coupling \
    --coupled runs/p62_delivery --decoupled runs/p62_coupling --wilcoxon --bootstrap 10000
```

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

## Results (TBD)

| metric | COUPLED | DECOUPLED | note |
|---|---|---|---|
| per-seed mean follow-err (px) | (saved per seed) | (saved per seed) | Wilcoxon input |
| Wilcoxon W, p | | | two-sided |
| bootstrap 95% CI of paired diff | | | vs schedule-noise band |
| schedule-noise band (px) | | | from DELIVERY |

**Verdict:** TBD. **Proof (>=2):** (1) coupled-vs-decoupled per-seed follow-error paired figure
(`make_proof.py`); (2) an overlay clip of the coupled arm chasing its own perception (the ego-motion
made visible), viewed.
