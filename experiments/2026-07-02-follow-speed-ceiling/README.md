# E2 — Speed ceiling with levers on: 0.5 / 1.0 / 1.5 m/s

**Pre-registered:** 2026-07-02T10:51Z (planning session; executor fills Results only).
**Status:** NOT STARTED — trigger: Phase 3b of `../2026-07-01-temporal-acquire-carry/` closed
(PASS, or rate-only marginal FAIL after the TRT campaign). Runs on the 3a/3b rig; do it while
the rig is warm.

## Research question

**RQ-E2:** Phase 1 mapped the ceiling at 1.0 m/s levers-OFF and named the mechanism (REGROUND
blind window = LossGate 3 s + acquire ~4.3 s, not first acquire). Phase 3a run 2 implemented the
levers (size-prior validation, dead-reckoning, time-based LossGate) and held a 13.9 s blind window
at 0.25 m/s. **Do the levers move the measured ceiling — from 1.0 m/s to what?**

## Frozen design decisions (do not re-derive)

- **Speeds:** 0.5, 1.0, 1.5 m/s — one SITL trial each, levers ON, on the integrated rig
  (`phase3_sitl.py`, real Jetson acquire via `--remote` if 3b's server is up, else the local-VLM
  path 3a used — record which). Phase 1's injected-latency trials are the levers-OFF baseline;
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

## Results (TBD)

| speed (m/s) | in-FOV | relock | DR gap drift (m) | verdict |
|---|---|---|---|---|
| 0.5 | | | | |
| 1.0 | | | | |
| 1.5 | | | | |

Ceiling moved: 1.0 (levers off, Phase 1) → **TBD** (levers on).

## Definition of done

README filled, RESULTS row + RQ-E2 verdict in `docs/{results,questions}/part4-end-to-end.md`,
DECISIONS entry only if a non-trivial choice came up, commit.
