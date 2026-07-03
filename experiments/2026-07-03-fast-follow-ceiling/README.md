# E10 fast-follow-ceiling — where does the follow loop actually stop, once the rig and the caps stop lying?

**Pre-registered:** 2026-07-03T12:26Z (Madrid wall-clock)
design + patches by Fable; Opus runs the matrix and fills Results only — do NOT re-patch code.
**Status:** COMPLETE 2026-07-03T12:45Z — **RQ-E10 = YES**, measured ceiling **2.5 m/s**
(reg-1.5 PASS; s2.0 3/3; s2.5 3/3; s3.0 0/2 never-locked = first-acquire). See Results.

## RQ-E10

**Does the deployed lever stack (Fix B + motion loss-gate + pursuit DR + motion
acquire-hold) hold a follow at 2.0 m/s once the two rig artifacts — the 140 m
world edge and the 2.5 m/s DR speed cap — are removed?**

Falsifiable form: with `--vmax 4.0` and the world texture auto-extended,
>= 2/3 legs at `--speed 2.0` pass the standard follow gate
(`in_fov_frac >= 0.90 AND recovered_after_occlusion`), AND the 1.5 m/s
regression leg still passes. Secondary (does not decide the RQ): the highest
speed in {1.5, 2.0, 2.5, 3.0} that passes its threshold is recorded as the
**measured ceiling**.

## Context & rationale (audit of E1–E9)

Theme for this cycle: *"improve the speed at which the system can operate so
we can track fast moving objects."*

- **E6's verdict is valid but its framing hides the real state.** Raw JSON
  spot-check (`experiments/2026-07-03-first-acquire/runs/mh-1.5b/results.json`:
  in_fov 1.0, first_lock 16.57 s) matches the published table. But "ceiling
  >= 1.0 m/s" undersells it: **every speed tested with the full stack passes
  (up to 1.5). The ceiling has never been measured — the ladder just stops.**
- **2.0 m/s was abandoned for a rig limitation, not a system failure.** E6
  README: "Given up: 2.0 m/s (NadirCam texture covers N∈[-20,140]; a 2.0 m/s
  car reaches 150.5 m and runs off the world. Not run.)"
- **Three hard-coded caps bind by construction above ~2 m/s**, so even if the
  world were big enough, higher speeds would fail for reasons that are code
  constants, not system properties:
  1. `pursuit_vel(..., vmax=2.5)` — blind pursuit can never out-run a 2.5 m/s car;
  2. `hist_vel` clamps the velocity estimate to ±2.5 m/s — DR under-predicts;
  3. `CascadePID` MAX_VX/VY = 3.0 — at 3.0 m/s target speed the copter has
     zero closing-speed margin.
- **Physics says 2.0–2.5 should be reachable.** KP_LAT = 0.02 gives a
  steady-state trailing error of speed/0.02 px: 100 px (~1.8 m) at 2.0 m/s,
  125 px at 2.5, 150 px at 3.0 — all geometrically inside the 640x480 frame
  at 10 m AGL. The expected failure modes are dynamic (occlusion relock at
  speed; standing-start first-acquire: the car crosses the ±4.33 m N
  half-footprint in ~1.4 s at 3.0 m/s), not geometric.
- Therefore the binding constraint for the speed theme is **"never measured
  above 1.5 + caps baked in"** — a ceiling probe with the rig fixed is the
  highest-leverage first cycle; later cycles can attack whichever failure
  mode the probe exposes.

**Rejected alternatives** (→ DECISIONS seed):
- *1.5 m/s relock-latency cut* (23–28 s residual walls): a quality fix on an
  already-passing config; no evidence it binds above 1.5. Do the ceiling
  probe first, then attack the mode it exposes.
- *VLM draw-latency reduction*: E5's decision entry already records "nothing
  shrinks the ~5 s VLM wall — no cheap headroom"; only worth revisiting if
  relock is what binds at the new ceiling.
- *On-device carry FPS uplift*: SITL follow verdicts run carry on the host
  3090; a Jetson FPS lever cannot move this ceiling measurement.

## Code changes (already committed — Opus: do NOT edit these files)

| File | Change | Default behavior |
|---|---|---|
| `experiments/2026-07-01-temporal-acquire-carry/sitl_cam.py` | `NadirCam(n_max=140.0)` param: texture rows = `(n_max − n0) · PX_PER_M`; selfcheck asserts default height unchanged + car renders at N=250 on an `n_max=260` world | bit-identical (140 = old constant) |
| `runners/sitl/cascade_pid.py` | `CascadePID(max_vx=MAX_VX, max_vy=MAX_VY)` per-instance limits used in `compute()`; `_test_clamp` extended | bit-identical (defaults = module constants; all existing callers use kwargs) |
| `experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py` | new `--vmax` flag (default **2.5** = E2–E9 behavior): threads into `hist_vel` clamp, `pursuit_vel(..., vmax=)`, `CascadePID(max_vx=max(3.0, vmax), ...)`; `NadirCam(n_max=max(140.0, c(duration_s)+20.0))` auto-extends the world to the trial's reach; `vmax` recorded in cfg; selfcheck gains a raised-clamp assertion | bit-identical at `--vmax 2.5` and speeds <= 1.5 (`max(140, 133) = 140`) |
| `experiments/2026-07-03-fast-follow-ceiling/run_e10.py` | the matrix runner (below) | — |

All three selfchecks pass post-patch (2026-07-03, host):
`.venv-ft/bin/python runners/sitl/cascade_pid.py`,
`... sitl_cam.py`, `... phase3_sitl.py --selfcheck`.

## Run matrix

Rig: host 3090 (SITL + renderer + SAM2 carry) + Jetson Orin Nano over `ssh jetson`
(the script boots the Qwen2-VL-2B Q8_0 llama-server on the Jetson for ACQUIRE/REGROUND;
verified in the run log: "[3] booting Jetson q8_0 server..."). Same stack as E2–E9.
**Power mode: 15 W (mode 0) + jetson_clocks** on the Jetson — this board's firmware
(L4T R36.5) has no MAXN_SUPER, only 15W/7W (see `docs/decisions/part2-rebuild.md`); the
E2–E9 "MAXN_SUPER" labels were a mislabel now corrected, so E10 is directly comparable.
SITL must be up per the E2–E9 procedure (ArduCopter SITL,
`runners/run_phase_b.py` params: TAKEOFF_ALT_M 10.0, ROVER_START_N 0.5).

One command runs everything (9 legs, snapshots each into `runs/<label>/`):

```bash
cd /home/gara/jetson
echo "$(date -Is) EXEC-START fast-follow-ceiling" >> .claude/loop.log
.venv-ft/bin/python experiments/2026-07-03-fast-follow-ceiling/run_e10.py 2>&1 | tee experiments/2026-07-03-fast-follow-ceiling/raw/matrix.log
```

(`mkdir -p experiments/2026-07-03-fast-follow-ceiling/raw` first if needed.)

Legs, in order (common flags: `--vmax 4.0 --loss-gate motion --dr pursuit --acquire-hold motion`):

| leg | `--speed` | purpose |
|---|---|---|
| reg-1.5 | 1.5 | regression guard: new flags, old world (`max(140, 133) = 140` — the world extension does NOT engage, isolating the cap change) |
| s2.0a/b/c | 2.0 | primary RQ (world auto-extends to n_max ≈ 171) |
| s2.5a/b/c | 2.5 | ceiling probe |
| s3.0a/b | 3.0 | stretch probe (expected FAIL; 2 legs only) |

Gotchas (baked into the runner, listed so you can recognize them):
- `phase3_sitl.py` clobbers `raw/phase3a-sitl/trial-<v>ms.{csv,mp4}` and
  `runs/phase3a-sitl/results.json` on every run — the runner snapshots per
  leg immediately; **the csv/mp4 filename depends on the speed** (e.g.
  `trial-2.0ms.csv`), which the runner handles.
- A leg is killed at 20 min (E6 actuals: ~2.5 min/leg; 20 min = hung SITL).
- If SITL dies mid-matrix, restart it and re-run only the missing legs by
  editing nothing: re-running `run_e10.py` re-executes all legs; it is
  cheaper (~30 min total) to just re-run the whole matrix than to surgery it.

## Verdict rules (mechanical — Opus does not deliberate)

The runner prints all of this; the rules it applies:

- **Per-leg gate:** PASS iff `trial["in_fov_frac"] >= 0.90 AND
  trial["recovered_after_occlusion"] == true` in the leg's
  `runs/<label>/results.json`.
- **RQ-E10 = YES** iff reg-1.5 PASS **and** >= 2/3 of s2.0 legs PASS.
- **reg-1.5 FAIL → RIG-REGRESSION**: RQ-E10 = NO regardless of the 2.0
  results; the patch changed <= 1.5 m/s behavior and the 2.0+ numbers are
  not comparable to E2–E9. Record it plainly; do not debug in this campaign.
- **Measured ceiling** (secondary, does not decide the RQ): highest speed
  with >= 2/3 PASS (1.5 needs 1/1; 3.0 needs 2/2).
- **Per-FAIL-leg binding mode** (printed by the runner): `first_lock_s`
  null → "never-locked (first-acquire)"; else the state at the start of the
  first >= 1 s contiguous `in_fov == 0` run in the CSV: ACQUIRE →
  first-acquire, REGROUND/RETARGET → relock, CARRY → tracking-trail.
- **Abort:** leg killed at 20 min → INVALID, continue; **2 INVALID legs →
  stop, campaign verdict INVALID-RUN** (fix the rig outside this campaign,
  re-run fresh).

## Estimates (marked as estimates)

- Runtime: ~25–35 min total (9 legs x ~2.5–3 min, per E6 actuals — E6's own
  2–2.5 h estimate was wildly over; using actuals).
- reg-1.5 PASS: ~85% (same config as E6 mh-1.5 legs, 3/3 there).
- s2.0 >= 2/3: ~55% (trailing error 100 px is fine; relock after the bridge
  at 2.0 m/s is the risk).
- s2.5 >= 2/3: ~30–40%.
- s3.0: expect FAIL (standing-start first-acquire physics above), verdict
  value = which binding mode is printed.

## Results

Ran 2026-07-03T12:45Z. Rig: host 3090 (SITL + SAM2 carry @1024) + Jetson Q8_0
acquire, **15 W + jetson_clocks**. Full stack (`--vmax 4.0 --loss-gate motion
--dr pursuit --acquire-hold motion`). Raw: `raw/matrix.log`, per-leg
`runs/<label>/{results.json,trial.csv,trial.mp4}`.

| leg | gate | in_fov_frac | recovered | first_lock_s | attempts | rejected | n_regrounds | relock_walls_s | carry_px_err_mean | binding mode (FAIL only) |
|---|---|---|---|---|---|---|---|---|---|---|
| reg-1.5 | PASS | 1.000 | True | 16.57 | 18 | 16 | 1 | 25.89 | 80.2 | — |
| s2.0a | PASS | 1.000 | True | 2.30 | 7 | 5 | 1 | 13.87 | 102.2 | — |
| s2.0b | PASS | 1.000 | True | 2.30 | 7 | 5 | 1 | 13.82 | 102.1 | — |
| s2.0c | PASS | 1.000 | True | 2.30 | 7 | 5 | 1 | 13.89 | 102.1 | — |
| s2.5a | PASS | 1.000 | True | 2.30 | 4 | 2 | 1 | 6.76 | 127.4 | — |
| s2.5b | PASS | 1.000 | True | 2.30 | 4 | 2 | 1 | 6.76 | 127.9 | — |
| s2.5c | PASS | 1.000 | True | 2.30 | 4 | 2 | 1 | 6.76 | 128.9 | — |
| s3.0a | FAIL | 0.052 | False | None | 32 | 31 | 0 | — | — | never-locked (first-acquire) |
| s3.0b | FAIL | 0.052 | False | None | 32 | 31 | 0 | — | — | never-locked (first-acquire) |

**RQ-E10 verdict: YES** — reg-1.5 PASS **and** s2.0 3/3 PASS. The follow stack holds
2.0 m/s (and 2.5) once the rig edge + caps are removed.
**Measured ceiling: 2.5 m/s** (1.5 1/1, 2.0 3/3, 2.5 3/3, 3.0 0/2).

### What this means (vs the theme: track faster objects)

- **The old "ceiling" was rig, not physics.** E2's "< 0.5 m/s" and the untested
  assumption behind E6's ">= 1.0" both fell to the same three artifacts E10 removed:
  the 140 m world edge (car ran off-map) and the 2.5 m/s pursuit / ±2.5 hist_vel /
  3.0 PID caps. With the caps parameterized (defaults bit-identical; reg-1.5 confirms
  no <= 1.5 behavior change), the loop tracks to **2.5 m/s** — 5x the E2 figure.
- **Above 2.5 the binding constraint is first-acquire, not tracking.** Both 3.0 legs
  never locked (in_fov 0.052, 31/32 acquires rejected, first_lock None) — the
  E5/E6 acquire-lottery: the standing-start copter cannot get a repeatable VLM draw
  before a 3.0 m/s car crosses the FOV. Once locked (2.0/2.5), carry+pursuit hold
  in_fov 1.000 to trial end. So the lever that raises the ceiling past 2.5 is
  **first-acquire reliability at speed**, not the pursuit controller or carry FPS.
- **Latency signature, secondary:** relock wall-time *falls* with speed (25.9 s @1.5
  -> 13.9 @2.0 -> 6.8 @2.5) and carry pixel error rises modestly (80 -> 128 px) — a
  faster car re-enters the acquire FOV sooner and trails slightly wider, both benign
  while in_fov stays 1.000.

## Video deliverables (Opus fills in — DoD item 7)

Every leg's mp4 is snapshotted to `runs/<label>/trial.mp4` by the runner —
that is all the footage the deliverables need. Cut 2–3 clips into `proof/`
(curated thesis clips, **committed**), caption each here with what it shows
and which run it came from:

Cut 2026-07-03T13:01Z (from `runs/<label>/trial.mp4`, occlusion window t≈30-35 s,
re-encoded libx264 for clean seeks):

1. `proof/e10-s2.0-follow.mp4` — **the RQ moment (after).** `s2.0a` t=22-48 s: the
   loop holding a 2.0 m/s follow through the occlusion window and relocking, in_fov
   1.000. This is the "after"; the "before" is E6's on-record given-up 2.0 m/s —
   **no footage of that exists** (E6 concluded 2.0 unreachable without running it at
   the removed caps, so there is nothing to film).
2. `proof/e10-ceiling.mp4` — **the measured ceiling.** `s2.5a` t=22-48 s: 2.5 m/s,
   the highest passing speed, holding through the same occlusion window (in_fov 1.000,
   relock 6.76 s).
3. `proof/e10-first-fail.mp4` — **the first failing speed.** `s3.0a` t=10-36 s: 3.0 m/s
   never locks — the acquire-lottery churn (31/32 draws rejected, first_lock None),
   the car pulls away, in_fov 0.052. Binding mode = first-acquire, not tracking.

`ffmpeg -ss <t0> -t <dur> -i runs/<label>/trial.mp4 -c:v libx264 -pix_fmt yuv420p proof/<name>.mp4`

## Closeout checklist (Opus)

1. Fill Results table + verdicts above; record estimate-vs-actual divergences.
2. Cut + caption + commit the video deliverables into `proof/` (section above).
3. Append one row per leg (or one summary row per speed) to
   `docs/results/part4-end-to-end.md` under E10.
4. Append RQ-E10 + one-line verdict to `docs/questions/part4-end-to-end.md`.
5. Append the DECISIONS entry to `docs/decisions/part4-end-to-end.md`: chose
   ceiling probe w/ rig fix (world `n_max` + `--vmax`); rejected relock-latency
   cut, VLM draw-latency work, on-device carry FPS (rationales in Context
   above).
6. Commit on this branch: `E10 fast-follow-ceiling: <verdict summary>`.
   Do NOT merge — the parent session merges.
