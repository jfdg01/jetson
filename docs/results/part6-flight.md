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
| G6 grounding | **NOT RUN** | see the correction below — first recorded as blocked by a missing checkpoint, which was wrong |

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

**Correction 2026-07-20T20:10Z — the G6 blocker was not real.** G6 was recorded NOT RUN because
`runners/runs/v2/phase3-terse100eos-1024` is absent from the 3090 and a `.safetensors` search
returned nothing on either machine. The deployed model was on the Jetson the whole time, in
deployment format, at the paths the repo's own constants point at:
`/home/jfdg/grounding/phase3-terse100eos-1024-q8_0.gguf` + its `mmproj` (both 2026-06-26), matching
`_REMOTE_MODELS`/`_REMOTE_MMPROJ`/`_DEFAULT_REMOTE_DIR` (`grounding/deploy/video.py:48-52`,
`grounding/deploy/serve.py:27`), with `llama-server` built at `/home/jfdg/llama.cpp/build/bin/`.
**P5.17 grounded through those same files** (`select_p517.py:397-403` builds a `JetsonBackend`, not
an `HFBackend`), so its 56/56 is a Jetson-GGUF number and running G6 that way is the *matching*
configuration, not a substitution. Only the merged HF/safetensors training-format directory is
genuinely lost — that costs LoRA resumption and re-export, not grounding. G6 stays NOT RUN (the
correction postdates the campaign, and the pre-registration assigns it its own n>=25 arm), but it
is unblocked work rather than a blocker. **P6.2 is not blocked.**

---

### CARLA GT capture bank — infrastructure, unnumbered (2026-07-21)

Detail: [`../../experiments/2026-07-21-carla-gt-bank/README.md`](../../experiments/2026-07-21-carla-gt-bank/README.md).
Config: x86_64 + RTX 3090 **power-capped 200 W** (default 350 W; capped at user request for fan
noise, and binding — CARLA at Epic alone draws 172 W of it); CARLA 0.9.16 server and client,
`Town10HD_Opt`, `-RenderOffScreen -quality-level=Epic -carla-rpc-port=2100`; **synchronous mode**,
`fixed_delta_seconds` 0.05 (20 Hz sim); camera 640x480 FOV 90 nadir; 80 autopilot vehicles under
`tm.set_random_device_seed(20260721)` plus 29 static `Car` meshes; venv `.venv-ft`; detached
`setsid nohup runners/night_driver.py`.

**Claims no experimental number.** This is the artifact-producing night from
`experiments/PART6-SLATE-carla-gt.md` §6 — build a deterministic GT bank, verify three gates, stop.
No VLM, no SAM2, no Jetson, no closed loop. Gate verdicts are not results. It is recorded here
because the bank is the input P6.2 consumes, and because the gates produced two findings that
would otherwise have been published as facts about CARLA.

**Sync here, async for flight.** `carla_render.py:40-45` records an explicit choice *against*
`synchronous_mode` for the flight rig: sim time only advances on `world.tick()`, so a 4.5 s VLM
acquire would cost zero sim seconds and the delivery lag Parts IV/V exist to measure would stop
existing. That stands. The bank is capture, not flight — no controller consumes the lag — so it
buys determinism instead. **Every number below is a sync-mode number.**

| gate | verdict | evidence |
|---|---|---|
| G-A — projected GT lands on the target | **PASS** | five overlays at 25/40/60/85/120 m, opened and viewed; all 8 vertices project; measured/analytic area 1.113 → 1.023, monotone |
| G-B — static meshes exist outside `get_actors()` | **CLOSED** (pre-run) | 29 `Car` `EnvironmentObject`s invisible to `get_actors().filter('vehicle.*')`; fourth taxonomy bucket added |
| G-C — pairing survives a layer toggle | **PASS** | same-config repeat 0.142 vs toggle-restore 0.084 mean abs frame diff, floor 8.0; all 40 TM vehicle positions identical across `load_world` |

The G-A ratio **exceeds 1 and converges toward 1 with altitude**, which is the correct signature,
not a defect: the analytic term `area ∝ (W/2)/tan(fov/2)/z²` is a point-target nadir
approximation, so the residual is the perspective spread of a box with real height, and that
spread shrinks with range. A ratio drifting *away* from 1 would have been the failure.

**The bank:**

| field | value |
|---|---|
| clips / frames | **25** clips × 1200 frames = **30 000** frames (60 s each @ 20 Hz sim) |
| sustained capture | **15.88 Hz** mean, range 12.5–18.8 (18.1 at 40 m → 13.9 at 120 m) |
| wall-clock | **36.5 min** (~1.46 min/clip), against a 1.0 h estimate |
| size | 4.7 GB, **not committed** — regenerate from the seeded runner |
| coverage (a vehicle on screen) | min 0.989, mean 1.000, every clip clears the 0.5 assert |
| anchor in frame (`target_in_frame_frac`) | `gain 1.0`: 100% on 9/9 · `gain 0.6`: 42.8–100% · `gain 0.0`: 12.8–87.8% |

Capture rate falls monotonically with altitude because a higher camera puts more vehicles on
screen (9.8 → 38.0 mean on-screen boxes) and both per-actor GT projection and JPEG encoding scale
with that. **The bank captures slower than 20 Hz sim-real-time at every altitude above 40 m; it is
not a real-time claim.** Sustained rate came in below even the pessimistic 25–40 Hz revision of the
86.1 Hz probe, because that revision still assumed 40 vehicles and the bank runs 80 — yet the bank
still finished inside its 1.0 h budget, the duration estimate having over-budgeted per-clip setup.

**Only `track_gain 1.0` is a clean regime.** `0.6` and `0.0` overlap heavily on the metric that
matters, so they are not separable arms. An earlier note in this campaign called these "three
distinct regimes" on the strength of the first 8 clips; at n=25 that is wrong and is retracted
here. A consumer selecting clips must filter on measured `target_in_frame_frac`, not `track_gain`.

**Two negatives worth more than the gate verdicts.**

*G-C first reported FAIL against its own same-config repeat.* The pixel rule passed; the position
rule failed between two runs of an identical config, which determinism cannot explain. Cause: the
comparison keyed each vehicle on `v.id`, and **CARLA's server-assigned actor ids do not restart at
a fixed value across `load_world`**, so two byte-identical worlds yield different id tuples.
Re-keyed on spawn index (stable — `setup_world` walks a seeded shuffle of spawn points) and it
passes. Both keys are retained in `results.json` and drawn in the proof figure. **Recorded as run,
this campaign would have published "CARLA traffic is not reproducible" on a broken dictionary
key** — a wrong negative that would have justified abandoning seeded determinism for all of Part
VI. It also makes `sidx` a known correctness gap rather than a nicety: `gt.jsonl` rows carry actor
ids, valid *within* a clip, invalid for pairing *across* runs.

*The first bank was well-formed and empty.* 25 clips at correct actor counts, passing blank-render
and dead-feed asserts, `dominant_frac` 0.002 — and **77–80% of frames containing no vehicle at
all**, because a nadir camera dropped at a uniform-random point over a city sees rooftops. Found by
overlaying `gt.jsonl` on a frame and looking. G-A is structurally blind to it: G-A aims the camera
at a known reference car, so it cannot detect that the *sampling policy* finds no cars. Fixed by
anchoring each clip on a spawned vehicle, and guarded by making target coverage a measured,
asserted per-clip field. General form: **a check that verifies the pixels are valid will not notice
that they are uninteresting.**

**Estimate vs actual.** 4.4 h estimated, ~1.25 h actual (00:28 pre-registration → 01:42 close-out).
Where the time went was not where the estimate put it: steps 1 (capture script) and 5 (G-C) took
nearly all of it, both for reasons no estimate anticipated — a sampling policy that found no cars,
and a gate that failed against itself. Also survived: an in-flight autoresearch cycle read this
campaign's freshly-committed script, ran `--gate-c` against the same server on port 2100, reloaded
the world under the bank capture and killed it with `_queue.Empty` 0.9 min in. **A STOP file that
blocks new ticks is not isolation from a worker already running.**

**Consumer read-back (added 2026-07-21T02:20Z).** Everything that had touched the bank was either
the code that wrote it or `make_proof.py` pulling single frames — nobody had loaded a whole clip
the way P6.2 will, which is the same gap that let the first bank ship 77–80% empty.
`check_bank.py` closes it: frame/GT alignment, index continuity, `box_vis` inside the image,
manifest agreeing with independently recomputed `target_in_frame_frac`, coverage above its floor.
**25/25 clips pass across 897 864 boxes**, which also confirms the backfill rather than trusting
it. One real defect found: `gt.jsonl` stores 2 dp, so a car 0.002 px inside the frame edge passes
the exact `x2 > x1` clip test and serialises as `[640.0, y1, 640.0, y2]` — a degenerate box that
hands a consumer a divide-by-zero IoU. The bug was in serialisation, not geometry, which is why
every geometric test passed. Fixed at capture time; **the shipped bank predates the fix and carries
19 of them (2.1e-05)**, too few to move any published number and deliberately not worth a 36.5 min
recapture that would invalidate the numbers already recorded above. The rate is gated at 1e-4 going
forward and written down here, because a tolerance nobody records is indistinguishable from a bug
nobody found.
