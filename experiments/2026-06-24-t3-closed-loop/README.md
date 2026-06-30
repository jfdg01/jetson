# T3 — Closed-loop permanence integration in SITL (Part III)

**Status:** ✅ **GATE PASS** (2026-06-24). **Branch:** `v3/object-permanence`.
**Prereq:** T2 (permanence mechanism) gate PASS — appearance-memory re-ID
(`experiments/2026-06-24-t2-permanence/`, DECISIONS 2026-06-24).

T3 closes the loop: the lock now **drives the camera** (cascade-PID → body velocity →
copter motion → re-projection), so a *wrong* lock steers the aircraft off the true
target and the failure **compounds** — the true target drifts out of frame. This is the
exact mechanic of the Phase-C negative ("naive rate-mismatch + memoryless coasting could
not hold a moving lock"), now made an **identity** test by adding a same-class distractor
that crosses, briefly occludes the target, then veers away.

## What T3 adds over T2

T2 scored the re-ID policy on **recorded** clips (open loop — the camera path was fixed).
T3 puts the same T2 appearance gate **inside a control loop** and asks the harder
question: when the lock decision *moves the camera*, does memory still hold the target?

| | T0 | T1 | T2 | **T3** |
|---|---|---|---|---|
| camera path | — | fixed (recorded) | fixed (recorded) | **driven by the lock (closed loop)** |
| failure mode | — | wrong re-lock | wrong re-lock | **wrong re-lock → camera steers off → target lost** |

## Scenario (`runners/run_t3.py`)

Reuses the whole Part-I SITL stack unchanged: `oracle_bbox.project` (pinhole camera),
`bytetrack.ByteTracker` (constant-velocity Kalman), `cascade_pid.CascadePID` (P-only
image→body-velocity), `offboard.OffboardController` (pymavlink), and the T2
`reid_policy._observe` appearance model.

- Copter hovers at **10 m**, downward camera, **20 Hz** control / **1 Hz** detect (the
  Phase-C sparse-anchor cadence — Kalman coasts the 19 intermediate frames).
- **Target** rover: 0.5 m ahead, **0.25 m/s** north (Phase-B/C dynamics).
- **Distractor** (same class): rides **2.2 m east** of the target, then **veers east at
  0.30 m/s after t = 31 s** — a lock that grabs it gets steered away and the true target
  exits frame.
- **Scripted occlusion** of the target over **t = 29–31 s** (40 frames @ 20 Hz): the
  identity-through-absence event the chapter is about.

Two policies share one harness (apples-to-apples):
- **baseline** — memoryless re-acq (nearest track to last lock position) → grabs the
  distractor at the blackout, follows the wrong vehicle.
- **reid** — the T2 appearance-memory gate refuses the distractor during the blackout
  and re-locks the true target after it.

**Headline metric:** true-target oracle-coverage % — fraction of frames the lock IoU vs
the TRUE target's (unsuppressed) oracle box ≥ 0.25. Phase-C negative ≈ **0%** on a moving
target.

> `ponytail:` the dry-run integrates the velocity setpoints kinematically (no flight
> dynamics) — the controlled, deterministic A/B. The `--live` path flies the *same loop*
> on real ArduCopter SITL for the sim-to-flight check. Both are kept; the kinematic A/B is
> the clean comparison, live SITL is the reality check.

## Results

### Kinematic closed loop (deterministic A/B — `.venv-ft/bin/python runners/run_t3.py`)

| policy | true-target coverage | occlusion frames |
|---|---|---|
| memoryless baseline | **49.2 %** | 40 |
| **re-ID (snr 8)** | **97.6 %** | 40 |

The memoryless baseline swaps to the distractor at the occlusion and is steered off
(true-target coverage collapses to ~half); the appearance gate refuses during the
blackout and re-locks the true target, holding **97.6 %** — i.e. **every visible frame**.

### Live ArduCopter SITL (real flight dynamics — `.venv/bin/python runners/run_t3.py --live`)

One **independent fresh flight per policy** (boot → GUIDED → arm → takeoff → 60 s loop →
land), so both see identical initial conditions:

| policy | true-target coverage | occlusion frames |
|---|---|---|
| memoryless baseline | **53.7 %** | 40 |
| **re-ID (snr 8)** | **71.5 %** | 40 |

reid beats memoryless **in real flight** too. The margin is smaller than the kinematic
A/B because real P-only-PID lag + airframe inertia lower the absolute coverage of *both*
policies (the copter chases a moving target with finite gain), but the **direction and the
mechanism hold**, and **both crush the Phase-C ~0 % negative** on a moving target.

## Gate (charter / CLAUDE.md)

> T3 — closed-loop integration in SITL: **beat the Phase-C negative (oracle-coverage well
> above ~0 % on a moving target).**

**Met.** Phase-C ≈ 0 % → T3 re-ID **97.6 %** (kinematic) / **71.5 %** (live SITL), and the
memoryless baseline (49–54 %) shows the win is the **permanence mechanism**, not just the
faster loop — the appearance gate is what holds identity through the occlusion/crossing
that steers the memoryless policy off the true target.

## Decisions

### 2026-06-24 — closed-loop A/B isolates permanence; kinematic primary + live SITL confirm

- **Decision:** Deliver T3 as a **two-policy closed-loop A/B** (memoryless vs T2 re-ID) on
  one shared harness, with a **deterministic kinematic dry-run as the primary comparison**
  and a **live ArduCopter SITL run as the sim-to-flight confirmation**. Build a focused new
  runner (`runners/run_t3.py`, ~280 lines) reusing oracle_bbox + bytetrack + cascade_pid
  + offboard + the T2 `_observe` rather than extending the 1239-line `run_phase_c.py`.
- **Alternatives considered:** (a) **Extend `run_phase_c.py`** — rejected: it carries
  Gazebo + VLM + dual-branch baggage irrelevant to the permanence A/B; a focused runner is
  the shorter, clearer diff. (b) **Live SITL only** — rejected: real flight dynamics lower
  *both* policies' absolute coverage and add run-to-run noise, blurring the mechanism's
  contribution; the kinematic A/B is the clean controlled comparison and is deterministic
  (self-check-able). (c) **Kinematic only** — rejected: the charter says *in SITL*; the live
  run is the honest reality check that the loop physically flies and the win survives real
  dynamics. (d) **Both policies in one shared flight** — rejected: the first policy leaves
  the copter chased-off, so the second starts degraded (observed: reid 2.8 % when run second
  on a shared flight vs 71.5 % on its own fresh flight) — one fresh takeoff per policy is the
  apples-to-apples that matches the kinematic A/B.
- **Tradeoff:** the kinematic dry-run abstracts away flight dynamics (no inertia/PID lag);
  the live SITL run is noisier and slower (two boots + two 60 s flights). Accepted: the two
  together bracket the result — clean mechanism isolation + real-flight confirmation.
- **Live-SITL launch notes (reproducibility):** GUIDED **must** be set before
  `NAV_TAKEOFF` (else takeoff is silently rejected and the copter never climbs); the SITL
  must be launched with `--uartA=tcp:5760` (Phase-C parity) or the lockstep physics clock
  never advances ("Waiting for internal clock bits") and the copter arms but cannot climb;
  the live loop drains `LOCAL_POSITION_NED` to the **freshest** pose each frame (a single
  non-blocking `recv_match` starves and freezes the projected camera at the origin); and
  each flight `pkill`s stale `arducopter` + hard-reaps the process so port 5760 is free for
  the next boot. Live SITL is run foreground (the sandbox reaps detached long-lived
  network process trees).
- **Revisit when:** T4 moves to the Orin (on-device cadence within the T0 budget) and/or a
  real appearance encoder replaces the scalar `_observe` (T2 upgrade path) — both will
  re-measure this loop with the real perception stack.

## Verification

```
.venv-ft/bin/python runners/run_t3.py          # deterministic kinematic self-checks (3 PASS)
.venv/bin/python    runners/run_t3.py --live    # real ArduCopter SITL, one flight per policy
```
Self-checks: reproducibility, occlusion-actually-happens (≥10 frames; got 40),
reid-beats-baseline (reid > baseline AND reid ≥ 80 %; got 49.2 % → 97.6 %). All green
(2026-06-24).
