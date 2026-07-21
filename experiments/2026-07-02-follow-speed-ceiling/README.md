# E2 — Speed ceiling with levers on: 0.5 / 1.0 / 1.5 m/s

**Pre-registered:** 2026-07-02T10:51Z (planning session; executor fills Results only).
**Status:** DONE 2026-07-02T19:40Z — all three speeds FAIL; levers-on ceiling < 0.5 m/s (below
Phase 1's oracle levers-off 1.0). See Results. Ran on the 3a rig (Jetson Q8_0 anchor over ssh, local 3090 carry). See the rig correction below.

## Research question

**RQ-E2:** Phase 1 mapped the ceiling at 1.0 m/s levers-OFF and named the mechanism (REGROUND
blind window = LossGate 3 s + acquire ~4.3 s, not first acquire). Phase 3a run 2 implemented the
levers (size-prior validation, dead-reckoning, time-based LossGate) and held a 13.9 s blind window
at 0.25 m/s. **Do the levers move the measured ceiling — from 1.0 m/s to what?**

## Frozen design decisions (do not re-derive)

- **Speeds:** 0.5, 1.0, 1.5 m/s — one SITL trial each, levers ON, on the integrated rig
  (`phase3_sitl.py`; the Jetson anchor is unconditional, so this pre-registered «record which» had only one possible answer — see the rig correction under Results). Phase 1's injected-latency trials are the levers-OFF baseline;
  do NOT rerun them.
- **Patch 1 — `--speed` flag:** `phase3_sitl.py` line ~40 hardcodes `SPEED = 0.25`. Add
  `--speed` (float, default 0.25) to the argparse, thread it to wherever `SPEED` is read
  (rover velocity, metrics header). One trial per invocation.
- **Patch 2 — DR clip:** dead-reckoning clips estimated velocity at ±1.5 m/s, which *equals* the
  top test speed — it would saturate exactly when needed. Raise the clip constant to **±2.5**.
  (Given up: making it a flag; a constant with a `# was 1.5, saturated at the 1.5 m/s trial
  speed` comment is enough.)
- **Patch 3 — bridge scaling (per speed, computed in the scenario setup):** occlusion must stay
  ~5 s fully hidden at every speed. Bridge center N = `ROVER_START_N + speed*30` (occlusion at
  t≈30 s), bridge N-extent `L = 5*speed + TARGET_LEN_M`. At 0.25 m/s this reproduces the 3a
  geometry (sanity check: it must).
- **Precheck (before any trial):** ground texture / render extent must cover the rover path to
  `N = start + speed*75` (≈112 m at 1.5 m/s). Run the `sitl_cam.py --selfcheck` style render at
  the far endpoint; if the car pixels vanish because the texture is bounded, extend the texture,
  don't shorten the trial.

## Gates and metrics (per speed)

Same as 3a run 2: in-FOV fraction ≥ 0.90, occlusion relock (REGROUND succeeds after the bridge),
DR gap drift over the blind window. Ceiling = highest speed with PASS. Logs → `raw/`, metrics
json → `runs/speed-<v>/`.

## Estimates (mark actuals vs these)

- 0.5 m/s: PASS comfortably (in-FOV ≥ 0.98). ESTIMATE.
- 1.0 m/s: PASS iff DR velocity error stays < ~0.2 m/s over the ~7 s blind window — genuinely
  uncertain (~60% PASS). ESTIMATE.
- 1.5 m/s: likely FAIL — relock must catch the car on a sliver of footprint; PID + footprint
  limits. A measured FAIL with the mechanism named is full thesis content. ESTIMATE.
- Effort: ~30–45 min including the three patches.

`ADVISOR (only if a trial fails in a way Phase 1 did not predict — e.g. first-acquire fails, or
DR diverges at 0.5 m/s): "Speed trial at <v> m/s failed via <mechanism>, but the Phase 1 model
predicts the ceiling is set by the REGROUND blind window. Symptom: <paste>. Rig bug or real
finding?"`

## Results (2026-07-02T19:40Z)

Ran with the Jetson Q8_0 anchor and a local 3090 carry @1024 (`phase3_sitl.py --speed <v>`, no
`--remote-carry`), one trial each.

Gate = in-FOV ≥ 0.90 AND
recovered_after_occlusion. Sweep runner: `run_e2.sh`. Raw per speed in `runs/speed-<v>/`.

> **Rig correction (2026-07-21, R-17).** In this campaign "local-VLM" meant **local carry**, not a local VLM: `--remote-carry` is off, so SAM2 runs on the 3090. The anchor **always** ran on the Orin. `phase3_sitl.py` constructs `JetsonBackend(..., ssh_host="jetson")` unconditionally with no local fallback branch, and prints `[3] booting Jetson q8_0 server...` before every run; there is no `--remote` flag at all. The label propagated README to README saying the opposite of what the code did — against our own interest, since the anchor was in fact on-device. Artifact-side confirmation: `runs/speed-1.0/results.json` records `n_acquire_attempts: 32`, so inference did run.


| speed (m/s) | in-FOV | relock | DR fired | verdict | failure mode |
|---|---|---|---|---|---|
| 0.5 | 0.484 | none (`n_regrounds=0`) | no | **FAIL** | confident-latch under occlusion |
| 1.0 | 0.076 | never locked (`first_lock=None`) | no | **FAIL** | initial acquire, car outruns lock |
| 1.5 | 0.051 | never locked (`first_lock=None`) | no | **FAIL** | initial acquire, car outruns lock |

**Ceiling moved: 1.0 (levers off, Phase 1, oracle box) → < 0.5 (levers on, real carry).** The
levers do NOT lift the ceiling — they *can't*, because at every tested speed the binding constraint
is something they don't touch:

- **0.5 m/s — confident-latch (reproduced: trial-1 in-FOV 0.486, re-run 0.484).** Acquires at 5.0 s
  and chases fine, then at the occlusion SAM2 latches the stationary bridge and returns a *confident,
  centered* box instead of `None`. Both levers are gated on `out is None` (`phase3_sitl.py` DR block
  + the LossGate REGROUND, lines 96–103, 223–234), so neither fires; the copter parks over the
  occluder (px_err→0) while the rover drives away (gap 3→24 m). Phase 1's oracle box could never
  produce this — the oracle always knew the car's position, so "loss" was always an honest `None`.
- **1.0 & 1.5 m/s — never acquires.** The copter never leaves home (`copter_n=0.0` the whole trial);
  the car exits the FOV at t≈6 s, before the ~5 s async VLM acquire + stale-box SAM2 init can form a
  lock. Every subsequent re-acquire then sees only background and is rejected by the size prior
  (31/32 attempts rejected). in-FOV collapses to ~0.05–0.08. This is the *acquire-latency vs target
  speed* limit, not occlusion.

### Estimate vs actual (a wrong estimate is content)

| speed | estimate | actual |
|---|---|---|
| 0.5 | PASS comfortably (in-FOV ≥ 0.98) | **FAIL** 0.484 — confident-latch, unmodeled |
| 1.0 | ~60% PASS (DR error over blind window) | **FAIL** 0.076 — never locks; DR blind window never reached |
| 1.5 | likely FAIL (relock on a sliver) | **FAIL** 0.051 — but via initial acquire, not relock |

The estimates assumed the REGROUND blind window Phase 1 named was the binding constraint at every
speed. It is not: with real (not oracle) carry, two earlier failure modes bind first — confident
carry-latch at 0.5, acquire-latency at ≥1.0 — so the levers, which target the blind window, are
never the thing that decides the trial.

## Fixability (not attempted here — measurement only)

Both modes are addressable and neither needs the levers redesigned away: (1) confident-latch → the
loss signal must include a *confidence/staleness* test, not just `box is None`, so a low-confidence
or non-moving carry box triggers REGROUND; (2) acquire-latency → velocity-extrapolate the stale
acquire box before prompting SAM2 (the `phase3_sitl.py:85` ponytail note already flags this), and/or
hold the copter's last commanded chase velocity during the first acquire instead of freezing at
home. Left for a follow-up campaign; recorded as the named next step, not silently.

## Definition of done

README filled, RESULTS row + RQ-E2 verdict in `docs/{results,questions}/part4-end-to-end.md`,
DECISIONS entry only if a non-trivial choice came up, commit.
