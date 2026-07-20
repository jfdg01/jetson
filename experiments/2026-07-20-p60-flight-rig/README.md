# P6.0 — Flight-rig capability gate

**Started:** 2026-07-20T12:34Z · **Completed:** 2026-07-20T13:20Z (Madrid wall-clock)
**Status:** COMPLETE — gate **PASS** (G1–G4), two rig defects found and fixed
**Part:** VI — closed-loop flight. Proposal: [`../PART6-PROPOSAL-closed-loop-flight.md`](../PART6-PROPOSAL-closed-loop-flight.md)
**Type:** capability gate, not a research question. Mechanical gates + abort rule below; no RQ verdict.

> **Honest provenance.** This record was written *during and after* the bring-up, not before it.
> P6.0 began as an unscoped "get the drone flying" session in response to the user's request and
> only became a gate once two real defects surfaced. Everything below is what actually happened,
> including the part where the pre-registration discipline was skipped. The gates in
> [Gates](#gates) were written down before the final post-fix run (G3-post) and that run was
> scored against them unchanged; the earlier runs are reported as bring-up, not as gate evidence.
> **P6.1 gets a proper pre-registration.**

---

## Why this exists

Part VI puts the Part V warm-start select in front of a *flying* copter, so the pixels become a
consequence of the system's own control output. Before any of that is meaningful, the rig itself
has to be known-good: SITL actually arms and flies, Gazebo actually renders, the perception
→ control chain actually closes at rate. P6.0 is that check.

The rig was believed to already work — it is the Phase B/C stack from Part I, last exercised
2026-06-15. It did not work. Two defects had been sitting in it, silently, for a month.

---

## Setup

| Component | Version / config |
|---|---|
| Host | x86_64, Linux 7.0.0-28-generic, RTX 3090 (driver 595.71.05) |
| Flight stack | ArduCopter **4.6.3** official (`~/ardupilot`, `92b0cd788e`, `ArduCopter-stable`) |
| Simulator | Gazebo Sim **8.14.0** (Harmonic), headless `gz sim -s -r`, `ogre2` |
| World | `runners/sitl/worlds/phase_c.sdf` — 200×200 m green ground box, orange 4×2×1 m rover, nadir 640×480 60° camera at 10 m |
| Runner | `runners/run_phase_c.py` |
| Detections | `--inject-oracle` — geometric projection of SITL world state, 1 Hz, `score=1.0` (emulates the VLM's rate without needing the Jetson) |
| Control | ByteTrack → cascade PID → `SET_POSITION_TARGET_LOCAL_NED` @ 20 Hz |
| Power mode | n/a — no Jetson in this gate (perception is injected, not inferred) |
| EGL | `__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json` |

**Architecture note (decision carried from the proposal):** SITL is the physics, Gazebo is a
**pose-slaved renderer** — each control tick drains `LOCAL_POSITION_NED` and pushes the camera
model pose via `set_pose`. This is *not* `ardupilot_gazebo` lockstep. See
[Decisions](#decisions).

### Commands

```bash
# G1/G2 — autopilot leg, no pixels
.venv-ft/bin/python runners/run_phase_c.py --inject-oracle \
    --runs 1 --duration 30 --out-dir <scratch>/p60

# G3 — full closed loop with real Gazebo pixels rendered under oracle control
.venv-ft/bin/python runners/run_phase_c.py --inject-oracle --gazebo \
    --runs 1 --duration 40 --out-dir <scratch>/p60d

# G4 — module self-tests
.venv-ft/bin/python runners/sitl/bytetrack.py
.venv-ft/bin/python runners/sitl/cascade_pid.py
.venv-ft/bin/python runners/sitl/oracle_bbox.py
```

---

## Gates

| id | Gate | Threshold | Result |
|---|---|---|---|
| **G1** | Autopilot leg closes: connect → GUIDED → arm → 10 m takeoff → 20 Hz command loop → LAND → disarm, unattended | completes, no manual step | **PASS** |
| **G2** | Camera renders a real scene | mid-run frame dominant colour < 0.99 **and** the frame is opened and looked at | **PASS** (0.751) |
| **G3** | Closed loop holds the target | mean loop rate ≥ 15 Hz, track coverage 100%, 0 track losses, ≤ 1% of ticks under 15 Hz | **PASS** (19.93 Hz, 100%, 0, 0.25%) |
| **G4** | Module self-tests green | `bytetrack` / `cascade_pid` / `oracle_bbox` all pass | **PASS** |

**Abort rule (declared before the post-fix run):** if G3 could not reach 15 Hz with pixels in the
loop, Part VI would drop to a lower control rate rather than drop Gazebo — the ego-motion render
is the whole point of Part VI, the 20 Hz figure is not.

---

## What happened

### Defect 1 — the camera was aimed at the sky (found G2)

`phase_c.sdf` and `run_phase_c.py:_update_gz_pose()` both set camera pitch to **−π/2**. `R_y(θ)`
maps the camera's +X view axis to `(cos θ, 0, −sin θ)`, so −π/2 gives `(0, 0, +1)` = **up**.
**+π/2 is down.** Wrong since the original Phase C commit `5426ed0`.

Empirically: at −π/2 the camera renders a flat gray frame, **100.0% one colour, mean 218,
std 0.0**; at +π/2 it renders the ground plane and the rover. Both frames are in
[`proof/camera-before-after.png`](proof/camera-before-after.png) and were captured by an actual
probe run, not mocked up.

This retroactively **invalidated Phase C Branch-2** (Part I): its live-VLM numbers (valid_rate
12.5%, px_err 190.5, track_cov 20.7%) were SmolVLM-500M grounding an NL expression in a blank
gray image. **RQ-S1.4 has been retracted to UNANSWERED**; see the caveat block in
[`../2026-06-14-stage1-baseline/phase-c-vlm.md`](../2026-06-14-stage1-baseline/phase-c-vlm.md)
and `docs/questions/part1-exploratory.md`. Branch-1 renders no frames and is unaffected. Not
re-run — SmolVLM-500M was eliminated in the Part IV bake-off.

It survived a month because **no frame from that run was ever saved or viewed** and the degraded
metrics matched the pre-registered *expected* outcome. A broken render was indistinguishable from
a confirmed hypothesis. This is the concrete case that the "Look at it" rule (`03d37bb`, added
2026-07-17, a month *later*) exists for. Diagnosis also had to clear an **orphaned `select_arena`
gz server** left alive from earlier P5 work, still answering on topics — exactly the P5.8 scar.

Fixed in both places. `run_phase_c.py` now dumps a mid-run PNG every run and warns loudly when a
frame is >99% one colour.

### Defect 2 — ByteTrack never re-found a lost track (found G3)

With the camera fixed, G3 ran clean at 19.93 Hz with "0 track losses" — and the CSV showed
**40 distinct track IDs in a 40 s run**, one per 1 Hz detection.

Root cause: `ByteTracker.update()` matched *lost* tracks only in round 2, against **low**-score
detections. A sparse `score=1.0` source (oracle inject, and the VLM in the live path) always
lands in round 1, never matches a lost track, and falls through to "create new track". So:

- a track went lost after **one** detectionless frame (19 of every 20),
- the next detection spawned a fresh ID instead of reviving it,
- therefore **no track ever received a second measurement**, its Kalman velocity stayed 0,
- and the advertised "Kalman coast" silently degraded to **zero-order hold** — the box froze
  between detections while the target kept moving.

The "0 track losses" metric was vacuous: a track never *dies*, it is continuously replaced.

Fix: a round-1b **re-find** step — leftover high-confidence detections are matched against lost
tracks at `HIGH_IOU_THR` and revive them. This is standard ByteTrack; this implementation had
dropped it. Regression test `_test_sparse_high_conf_keeps_id` added, and verified to **fail on
the pre-fix tracker** (`id churn: expected one id, got [1, 2, 3, 4, 5]`) and pass after.

Same 40 s flight, same config, before vs after — [`proof/tracker-id-churn.png`](proof/tracker-id-churn.png):

| | track ids used | mean px err vs oracle | max px err | mean loop Hz | ticks < 15 Hz |
|---|---|---|---|---|---|
| before fix | **40** | **64.7** | 312.3 | 19.93 | 2 / 793 (0.25%) |
| after fix | **7** | **36.0** | 308.2 | 19.93 | 2 / 793 (0.25%) |

Pixel error **−44%** from a tracker fix alone, at identical control rate.

**Blast radius:** Phase B ran the oracle at ~25 Hz synchronously — a detection every frame, so no
track ever went lost and no churn occurred. Phase B is unaffected. Phase C **Branch-1** ran at
1 Hz and *was* affected: its px_err 89.4 is inflated by this defect. Not re-run (it is a Part I
integration smoke test whose PASS verdict does not turn on the pixel-error magnitude), but the
number should not be quoted as a tracking-quality result.

---

## Results

Bring-up runs (pre-fix, reported for provenance, **not** gate evidence):

| run | duration | mean Hz | track cov | px err | track losses | ids | notes |
|---|---|---|---|---|---|---|---|
| G1 (`p60`) | 30 s | 19.96 | 100.0% | 45.9 | 0 | 30 | no pixels; camera bug not yet found |
| G2 (`p60b`) | 15 s | 19.96 | 100.0% | 23.2 | 0 | 15 | short leg; camera probed separately |
| G3-pre (`p60c`) | 40 s | 19.93 | 100.0% | 64.7 | 0 | 40 | camera fixed, tracker still broken |

Gate run (post-fix, scored against the gates above):

| run | duration | mean Hz | track cov | px err | track losses | ids | mid-run frame |
|---|---|---|---|---|---|---|---|
| **G3-post** (`p60d`) | 40 s | **19.83** | **100.0%** | **36.0** | **0** | 7 | dominant colour **0.751** |

**Gate verdict: PASS.** The rig flies, renders, and closes the loop at rate.

### On the runner's printed "Branch-1 FAIL"

Every run prints `Branch-1 FAIL — hz=19.83 (ok) coasting_max=19 (ok) reseed=N/A (fail <2s)`.
This is **not a piloting failure**. The Branch-1 criterion inherited from Phase C requires a
re-seed-after-forced-gap measurement, which cannot be produced by a short run with zero track
losses — there is no gap to re-seed from. The gate is unsatisfiable rather than failed. Left
as-is; P6.1 defines its own gates and does not inherit Branch-1.

---

## Residuals (carried into P6.1, not fixed here)

1. **7 track IDs remain post-fix**, all after t≈31 s. The rover walks away, the copter falls
   behind, and inter-detection displacement exceeds `HIGH_IOU_THR=0.3` — a genuine association
   limit at 1 Hz, not the same bug. Both traces in the figure diverge together after t≈30 s, so
   this is the control leg losing the target, not the tracker losing the box.
2. **`_append_results_md` hardcodes `SmolVLM-500M Q8_0` and `15W locked`** in the row it writes.
   Stale for any run that is not the original Phase C config. Scratch runs (`--out-dir`) no longer
   touch the repo ledger, so this is now cosmetic, but it must be fixed before a live-VLM P6.1 run
   writes a real row.
3. **The live-VLM path still targets `_probe.MODELS[1]` (SmolVLM-500M)**, not the deployed
   Qwen2-VL-2B. P6.1 needs this repointed.
4. **`phase_c.sdf` is still the two-model toy world.** The P5.9/P5.12 `select_arena` bank is the
   intended Part VI scene; the port has not been done.
5. **`bytetrack.py`'s Kalman noise is tuned for ~25 Hz** (docstring says so). At 1 Hz detections
   the process noise is likely too small. Not touched — out of scope for a capability gate, and
   the re-find fix already recovered most of the error.

---

## Decisions

- **Keep SITL-as-physics + Gazebo-as-pose-slaved-renderer; do not adopt `ardupilot_gazebo`
  lockstep.** The existing rig already delivers what Part VI is testing — camera pixels that move
  as a consequence of the copter's own control output. *Given up:* physically-coupled rotor
  downwash / airframe dynamics visible in the render, and frame-accurate sim/flight determinism.
  Neither is load-bearing for a perception-in-the-loop question. *Cost avoided:* rebuilding the
  world, the model, and the runner around a plugin that is already installed but unused.
- **Fix the tracker rather than route around it.** The alternative was to raise the injection rate
  until churn stopped, which would have hidden the defect behind a config value and carried it into
  P6.1 with a real ~1 Hz VLM, where it cannot be hidden. *Given up:* a slightly larger diff on
  shared Part-I infra than a capability gate would normally justify.
- **Retract RQ-S1.4 rather than silently patch it.** A recorded Part I verdict is now known to rest
  on a blank image. *Given up:* a clean-looking Part I chapter. Kept: the negative result is still
  content, and the retraction is itself thesis content about how silent render failures hide inside
  confirmed hypotheses.
- **Do not re-run Phase C Branch-2.** It would measure SmolVLM-500M, a backbone already eliminated
  in the Part IV bake-off and superseded by the deployed Qwen2-VL-2B. *Given up:* an answer to
  RQ-S1.4; it stays UNANSWERED.

---

## Proof deliverables

Rebuild all three: `.venv-ft/bin/python experiments/2026-07-20-p60-flight-rig/make_proof.py`

| file | what it shows | run / config |
|---|---|---|
| [`proof/camera-before-after.png`](proof/camera-before-after.png) | **Defect 1, before/after.** Same camera, same world, same gz build: at pitch −π/2 a flat gray frame (100.0% one colour, mean 218, std 0.0); at +π/2 the green ground and the orange rover. The left panel is the image Phase C Branch-2's VLM was grounding in. | `cam_probe` on `phase_c.sdf`, gz 8.14.0 headless ogre2 |
| [`proof/tracker-id-churn.png`](proof/tracker-id-churn.png) | **Defect 2, before/after, numbers are the point.** Same 40 s closed-loop flight: track-id count 40 → 7 and mean pixel error 64.7 → 36.0 px. The pre-fix sawtooth resets to 0 at each 1 Hz detection and ramps linearly between them — the zero-order-hold signature. | G3-pre (`105344`) vs G3-post (`110444`), `--inject-oracle --gazebo`, 40 s |
| [`proof/midrun-frame.png`](proof/midrun-frame.png) | **G2/G3 "look at it" artifact.** Mid-run Gazebo frame from the post-fix closed-loop run: green ground, orange rover held near frame centre by the PID. Dominant colour 0.751, so it passes the >99%-one-colour render assert mechanically as well as visually. | G3-post (`110444`), t = 20 s |

---

## Next step

**P6.1 — closed-loop select-and-follow**, pre-registered properly *before* running, per the
per-experiment workflow. Blocking work from the residuals above: repoint the live-VLM path at
Qwen2-VL-2B (3), port `select_arena` into the runner (4), fix the stale ledger row (2).
