# RESULTS — Part VI · Closed-loop flight (v6)

Index: [`../../RESULTS.md`](../../RESULTS.md) · Companion: [`../questions/`](../questions/) (research questions) · [`../decisions/`](../decisions/) (what was chosen & why).
Per-campaign detail lives in `experiments/<campaign>/README.md`. Append, never overwrite.

---

## Part VI — Closed-loop flight (v6)

Goal: every Part V number was measured on replayed video the system could not influence — no
vehicle in the loop. Part VI puts the warm-start select in front of a flying copter, so the
pixels become a consequence of its own control output. Reframe origin:
`experiments/PART6-PROPOSAL-closed-loop-flight.md`.

Rig: ArduCopter SITL as physics, Gazebo as a pose-slaved renderer (not `ardupilot_gazebo`
lockstep), `runners/run_phase_c.py` closing VLM → ByteTrack → cascade PID → MAVLink at 20 Hz.

<!-- append one result row per campaign below -->

### P6.0 — flight-rig capability gate (2026-07-20)

Detail: [`../../experiments/2026-07-20-p60-flight-rig/README.md`](../../experiments/2026-07-20-p60-flight-rig/README.md).
Config: x86_64 + RTX 3090 (no Jetson in this gate — detections are injected, not inferred);
ArduCopter 4.6.3 (`92b0cd788e`); Gazebo Sim 8.14.0 headless `ogre2`; world `phase_c.sdf`;
`run_phase_c.py --inject-oracle --gazebo`, 1 Hz `score=1.0` detections, 20 Hz control,
40 s runs, n=1 per configuration (capability gate, not a statistical claim).

**Gate verdict: PASS** (G1 autopilot leg · G2 camera renders · G3 loop holds at rate · G4 self-tests).

Same 40 s flight, before and after the ByteTrack round-1b re-find fix:

| leg | track ids used | mean px err vs oracle | mean loop Hz | track cov | track losses | ticks < 15 Hz |
|---|---|---|---|---|---|---|
| G3-pre (camera fixed, tracker broken) | 40 | 64.7 | 19.93 | 100.0% | 0 | 2/793 (0.25%) |
| **G3-post (both fixed)** | **7** | **36.0** | **19.93** | **100.0%** | **0** | 2/793 (0.25%) |

Pixel error **−44%** from the tracker fix alone, at identical control rate. Mid-run Gazebo frame
dominant colour 0.751 (passes the >99%-one-colour render assert; frame viewed, see `proof/`).

Two rig defects found, both silent for a month:

1. **Camera aimed at the sky.** Pitch was −π/2 in `phase_c.sdf` and `run_phase_c.py` since
   `5426ed0`; `R_y(θ)` maps +X to `(cos θ, 0, −sin θ)`, so **+π/2 is DOWN**. At −π/2 the render is
   a flat gray frame: **100.0% one colour, mean 218, std 0.0**. This **retroactively invalidates
   Phase C Branch-2** (Part I) — see the retraction below and in `part1-exploratory.md`.
2. **ByteTrack never re-found a lost track.** Lost tracks were matched only against *low*-score
   detections, so a sparse `score=1.0` source spawned a new ID on every detection. No track ever
   got a second measurement, so Kalman velocity stayed 0 and the "coast" was zero-order hold.
   The "0 track losses" metric was vacuous — a track never died, it was continuously replaced.

**Retraction (Part I).** Phase C Branch-2's live-VLM numbers — valid_rate 12.5%, px_err 190.5,
track_cov 20.7%, 19 track losses — are **withdrawn**: the VLM was grounding in a blank gray
image. Phase C **Branch-1**'s px_err 89.4 is inflated by defect 2 and should not be quoted as a
tracking-quality figure (its integration PASS stands). **Phase B is unaffected** — its ~25 Hz
synchronous oracle gave a detection every frame, so no track ever went lost.

### P6.1 — CARLA renderer swap (2026-07-20)

Detail: [`../../experiments/2026-07-20-p61-carla-renderer/README.md`](../../experiments/2026-07-20-p61-carla-renderer/README.md).
Config: 3090 workstation (no Jetson — the CARLA server needs a desktop GPU, so nothing here is a
deployment number); CARLA server + client 0.9.16 packaged Linux release, `Town10HD_Opt`,
640x480 @ 90 deg FOV, `fixed_delta_seconds=0.05`, traffic-manager seed 20260720;
ArduCopter 4.6.3 (`92b0cd788e`) SITL as physics, `--no-mavproxy`; `runners/carla_render.py`,
n=1 per configuration (capability gate, not a statistical claim).

**Gate verdict: YES** — G1 server · G2 render · G3 pose slaving · G4 traffic · G5 rate all pass.
G6 (grounding, pre-registered **non-gating**) **NOT RUN**.

| gate | verdict | measured |
|---|---|---|
| G1 server | PASS | server 0.9.16 == client 0.9.16, `Town10HD_Opt`, 155 spawn points, 41 vehicle blueprints, 599 ticks |
| G2 render | PASS | dominant-colour fraction **0.005–0.026** (gate < 0.99), frames opened with the Read tool |
| G3 pose slaving | PASS | copter flew **0 → 84.4 m north** under its own GUIDED control at a held 60.0 m; content at ticks 150/300/599 distinct and consistent with position; nadir `pitch=-90` confirmed by viewed frame |
| G4 traffic | PASS | **40/40** vehicles spawned with autopilot; first vs last frame not byte-identical |
| G5 rate | PASS | **48.1 Hz** mean (gate >= 20 Hz, 2.4x the P6.0 control rate); 5/599 ticks under 15 Hz, all in the first ~5 s of cold shader compilation |
| G6 grounding | **NOT RUN** | deployed checkpoint `runners/runs/v2/phase3-terse100eos-1024` absent from this machine |

Sizing observation (non-gating, pre-registration input for P6.2): at 90 deg FOV nadir, a car is
~10 px at 100 m, ~25x50 px at 60 m, and at 30 m the frame is mostly building facade. **60 m is the
working altitude for P6.2.**

**`slave_err_mean_m = 0.000` in `results.json` is vacuous — do not cite it.** CARLA's free camera is
a kinematic actor, so `get_transform()` returns exactly what `set_transform()` was handed; the
metric compares a number against itself. Same failure shape as P6.0's "0 track losses". What
evidences G3 is that the *pose source* moved 84.4 m under closed-loop autopilot control and the
*rendered content* changed accordingly across three frames that were opened and viewed.

**Estimate vs actual.** Render rate landed mid-range as predicted (48.1 vs 30–60 Hz estimated) and
the renderer swap was uneventful. The 2–4 h estimate ran to ~5 h and the ~150-line runner estimate
to 387 lines, all of it in the unforeseen risk: driving SITL without MAVProxy. Eight silent
failures, chief among them that ArduPilot streams almost nothing to a GCS that never requests it —
`LOCAL_POSITION_NED` never arrived and the pose consumer read its initial value forever, which
would have rendered a **frozen camera over a moving world at exit 0**. That is the P6.1 analogue
of the Phase C sky camera. Full list in the campaign README.
