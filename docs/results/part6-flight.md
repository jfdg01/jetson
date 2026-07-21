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
   The "0 track losses" metric was vacuous, though **not for the reason first recorded** — see the
   vacuous-metric audit below.

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
| G2 render | PASS | dominant-colour fraction **0.007–0.026** (gate < 0.99), frames opened with the Read tool |
| G3 pose slaving | PASS | copter flew **0 → 84.4 m north** under its own GUIDED control at a held 60.0 m; content at ticks 150/300/599 distinct and consistent with position; nadir `pitch=-90` confirmed by viewed frame |
| G4 traffic | PASS | **40/40** vehicles spawned with autopilot; first vs last frame not byte-identical |
| G5 rate | PASS | **48.1 Hz** mean — *render-loop wall throughput of a bare client*, no perception in the window (gate >= 20 Hz); 5/599 ticks under 15 Hz, all in the first ~5 s of cold shader compilation. The "2.4x the control rate" reading is withdrawn: see the audit below |
| G6 grounding | **NOT RUN** | see the correction below — first recorded as blocked by a missing checkpoint, which was wrong |

Sizing observation (non-gating, pre-registration input for P6.2): at 90 deg FOV nadir, a car is
~10 px at 100 m, ~25x50 px at 60 m, and at 30 m the frame is mostly building facade. **60 m is the
working altitude for P6.2.**

### Vacuous-metric audit (R-10, 2026-07-21)

Three Part-VI numbers were re-derived from the artifacts. All three are worse than the
ledger said, and two were disowned for the wrong reason.

**`slave_err_*` — vacuous, and the published value is not in the file.** The camera is a
spawned, unattached `sensor.camera.rgb`: a kinematic actor with no dynamics, so
`get_transform()` returns the transform `set_transform()` was handed one line earlier
(`world.tick()` sits between them, so there is not even a sync-mode race to measure). The
artifact holds `slave_err_mean_m = 1.815e-06`, not `0.000` — the zero is the `:.3f` print
format, so a reader grepping `results.json` for the published number will not find it. The
residual is float32 round-trip noise: it does not correlate with per-tick speed (r = +0.02)
and is 5 orders of magnitude below the 0.143 m the camera moves per tick.

Two things the earlier note missed. The metric reads `.location` only, so **rotation is
never compared** — and `pose_track[:, 3]` (yaw) holds exactly **one distinct value, 0.0,
across all 600 ticks**, because `MavlinkPose` fills yaw from a non-blocking `ATTITUDE` poll
that never delivered, the same silent-stream failure the campaign already documents for
`LOCAL_POSITION_NED`. Nobody noticed *because* `slave_err` cannot see rotation. The renderer
was **position-slaved**, not pose-slaved; the consequence is bounded only because the camera
is fixed nadir.

**A non-vacuous replacement, computed from the committed artifact** (no re-run;
`pose_staleness.py` in the campaign dir): `MavlinkPose.__call__` drains non-blocking and
returns `self.last` when no new sample arrived, so every tick with a repeated `pose_track`
row rendered the camera where the aircraft *was*.

| quantity | value |
|---|---|
| render ticks reusing a stale pose | **362 / 599 = 60.4%** |
| fresh `LOCAL_POSITION_NED` samples | 237 (19.0 Hz) |
| inter-sample gap, mean / max | 0.053 s / **0.547 s** |
| aircraft speed, median | 7.21 m/s |
| implied camera lag, typical / worst | 0.38 m / **3.9 m** |

That is a real, falsifiable, nonzero slaving error, ~6 orders of magnitude larger than the
metric that was published, and it fails in the right direction when the pose stream stalls.
It is a **lower bound**: `pose_track` stores no `time_boot_ms`, so the SITL-side
sensor-to-wire latency is not recoverable from disk.

**48.1 Hz — measurement point stated, and the headroom claim withdrawn.** It is
`1/mean(diff(wall stamps))` around `set_transform` + `world.tick()` + `get_transform()` in
`carla_render.py`. No VLM, no SAM2, no ByteTrack, no PID, no JPEG, no transport is inside
that window — grepping the renderer for any of them returns only comments. It is the CARLA
server's render+step throughput as seen by a bare client, and it is not a system rate under
any reading.

Worse, the run was **synchronous mode**: 600 ticks x `fixed_delta_seconds` 0.05 = 30 s of
simulated time delivered in 12.46 s of wall time, so the sim ran **2.41x faster than real
time** while SITL, the pose source, ran on the wall clock. The 40 autonomous vehicles
experienced 30 s of driving while the copter experienced 12.5 s of flight. And
`48.08 / 19.93 = 2.41` is the *same number* as `30 s / 12.46 s`, because `FIXED_DT` equals
the control period — so "2.4x the P6.0 control rate" was never headroom, it was a
restatement of the clock skew. That reading is withdrawn everywhere.

The figure is also **not reproducible from HEAD**: `87a5b48` rewrote the loop to async with
a wall-clock pacer and `sensor_tick = 0.05`, landing 3.5 h after the results were committed.
Re-running the documented command today yields ~20 Hz by construction. The as-run code is
`d925c74:runners/carla_render.py`.

**What still evidences G3** is unchanged and does not depend on any of the above: the pose
source moved 84.4 m under closed-loop autopilot control and the rendered content changed
accordingly across three frames that were opened and viewed.

**"0 track losses" (P6.0) — vacuous, but the recorded mechanism is wrong.** The ledger says
it was vacuous *because of* the ByteTrack re-find bug. It was not. The counter increments
only when `tracker.update()` returns an empty list, which needs `MAX_LOST_FRAMES = 30`
frames at `CONTROL_HZ = 20` — **1.5 s with no detection at all**. That branch was equally
reachable before and after the fix; the bug changed ID churn and Kalman velocity, not the
emptiness condition. What makes the `0` uninformative is that the 1 Hz `score=1.0` injection
never produced a 1.5 s drought, and the one run designed to force one (`GAP_INJECT_RUN = 3`)
never executed — every committed artifact is `run1`. The proof is that the maximally-broken
pre-fix run (40 IDs, px_err 64.7) and the fixed run (7 IDs, 36.0) **both report 0**: a metric
identical across a defect that nearly doubled the pixel error has no diagnostic power for the
property it gated. Honest phrasing: *0 track losses means the detection supply never stalled;
it is not evidence the loop held the target, before or after the fix.* Related: `LOST_TIMEOUT_S
= 3.0` in `run_phase_c.py` is dead code — the implemented threshold is 1.5 s, half the
documented value — and no `results.json` exists for P6.0 at all, so the `0` is prose; it is
reconstructable from the `track_id` column of the four CSVs, and reconstructing it gives 0
empty-track frames in all four.

**Estimate vs actual.** Render rate landed mid-range as predicted (48.1 vs 30–60 Hz estimated — but see
the audit above for what that rate is and is not) and
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

## Re-analisis estadistico retroactivo (2026-07-21T13:30Z) — Partes I-VI

Cross-cutting, not a flight campaign; recorded here because Part VI is the open Part. Registry
`thesis/claims.json` (65 claims, Parts I-VI), engine `grounding/stats.py`, report
`thesis/stats-report.md`, method `thesis/01-metodo-estadistico.md`.

| Bucket | n | Note |
|---|---|---|
All p below are **post-deflation** — computed at `n_effective`, the value
`thesis/stats-report.md` currently prints. The first version of this table quoted the
undeflated p (5.151e-73, 9.555e-26, 1.988e-7, 3.052e-5, 0.01612) and the pre-R-4 bucket
sizes (26 / 33); R-7 caught them stale by one remediation cycle.

| Bucket | n | Note |
|---|---|---|
| Significant after Holm-Bonferroni | 6 | `P1-S3.3-export-parity-catastrophe` 1.345e-4 (worst-case marginal bound), `P2-RQ2.1-resolution-ladder-1024` 7.771e-6, `P2-RQ3.1-lora-aerial-gate` 3.679e-53, `P3-ROI-M2.0-512` 7.235e-19, `P5.2a-warm-generalization` 6.104e-5, `P5.12-bankv21-recal` 3.365e-4 |
| No test possible (0 discordant pairs) | 30 | `p` is undefined, **not** 1.0 — absence of a test, not proven equality |
| Design could never reach alpha=0.05 | 35 | n<=5 paired: floor is p=0.0625 with a perfect result |
| Raw per-item data missing | 3 | `thesis/rerun-backlog.md` |

Raw-significant but Holm-rejected: `P2-RQ4.1-deploy-fidelity` 0.0355,
`P5.15-plain-carry-survival` 0.002908. `P3-carry-OP768-accuracy` was listed here at
0.01267 and no longer belongs: deflated to its 93 source sequences it is p=0.096, not
significant even before Holm (see correction 3 below).

**Three recorded conclusions corrected by the re-analysis.**

1. **Swin2SR's rejection is not supported on accuracy.** lanczos vs swin2sr b=21 c=14 p=0.3105;
   bicubic vs swin2sr b=22 c=12 p=0.1214; bicubic vs native p=0.2624. No arm differs at n=429. The
   decision stands, but on **latency** (+1331 ms/crop), not on IoU.
2. **The Part I "fidelity catastrophe" is the export, not the quantisation.** F16 vs Q8_0 b=17 c=10
   **p=0.2478** — no evidence the quantisation costs accuracy. HF vs GGUF is significant under
   *every* pairing consistent with the surviving marginals (worst case 1.345e-4 for Q8_0,
   2.19e-3 for F16).
3. ~~**Carry at 768 does lose accuracy vs 1024** (sign test 55 vs 31, p=0.013).~~ **Superseded
   2026-07-21 (R-7).** The 55-vs-31 sign test counts 186 tracks, but they come from 93 distinct
   sequences; on that unit it is b=28, c=16, **p=0.096** — not significant, Holm 1. So the
   defensible statement is the weaker one: 768 was adopted on an effect-size bound plus an FPS
   constraint, and this data cannot resolve whether it costs accuracy at all. The undeflated
   p is 0.013 (not the 0.014 the registry caveat printed until R-7 corrected it).

Figures: `thesis/proof/stats-power.png` (paired designs by effective n, red = could never reach
alpha), `thesis/proof/stats-forest.png` (18 gated arms, Wilson CI on effective n vs the gate). Both
opened and visually verified.

## Machine disclosure audit (R-1) — cross-cutting, 2026-07-21T18:05Z

Record: `experiments/2026-07-21-machine-disclosure/README.md`. Machine: RTX 3090 workstation
(file reading only; nothing measured). Data: `raw/machine-audit.json`, 76 rows with a quoted
evidence string each.

| Metric | Value |
|---|---|
| Campaigns audited | 76 |
| Host `stated` in the campaign's own record | 61 |
| Host `inferred` only (code / sibling doc / inheritance chain) | 9 |
| Host `unknown` (nothing in the tree says) | 6 |
| VLM ran on the Jetson | 47 |
| VLM ran on both machines (fidelity comparisons) | 7 |
| VLM ran on the 3090 only | 5 |
| No VLM in the campaign | 15 |
| VLM host unclear | 2 |

Per-Part disclosure defects: Part I 0/9, Part II 1/5, Part III 4/11, Part IV 7/27, Part V 2/20,
Part VI 1/3. Part I is fully disclosed; the concentration is Part III (`unknown`, SITL/kinematic
work with no VLM) and Part IV (`inferred` via «byte-identical to E19» chains).

**Substantive finding (M1).** The 6.15 Hz carry rate cap used by every Part IV/V campaign was
measured by E1 at image_size **768**; those campaigns run SAM2 at **1024**
(`SAM2VideoPredictor.from_pretrained` default, no override). E1 recorded that 1024 «needs 1.9×»
and never gated it. E18 further miscites the cap's provenance as «measured at 640x480». So the
emulated on-device stride is optimistic, plausibly by ~2×, biasing carry-dependent PASSes
favourably. Folded into **R-16** as a required measurement axis (gate at 1024, not 768).

Figures: `proof/disclosure-by-part.png`, `proof/vlm-host-by-part.png`. Both opened and visually
verified; the first one falsified the draft paragraph it illustrates.
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
