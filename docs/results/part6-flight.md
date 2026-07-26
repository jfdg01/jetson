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

| leg | track ids used | mean px err vs oracle | mean loop Hz (`1/mean(dt)`) | track cov † | track losses † | ticks < 15 Hz |
|---|---|---|---|---|---|---|
| G3-pre (camera fixed, tracker broken) | 40 | 64.7 | 19.80 | 100.0% | 0 | 2/792 (0.25%) |
| **G3-post (both fixed)** | **7** | **36.0** | **19.80** | **100.0%** | **0** | 2/792 (0.25%) |

Pixel error **−44%** from the tracker fix alone, at identical control rate. Mid-run Gazebo frame
dominant colour 0.751 (passes the >99%-one-colour render assert; frame viewed, see `proof/`).

**Rate definition (corrected 2026-07-21T19:45Z, R-21).** This column first published **19.93** for
both legs. That is `make_proof.py`'s mean of the instantaneous rates, `mean(1000/dt)` — a
Jensen-biased estimator that overstates delivered throughput. The column now carries the runner's
own recorded metric, `loop_hz_mean = 1/mean(dt)` (`run_phase_c.py:900-902`), which recomputes from
both CSVs as **19.80**; ticks/elapsed is 19.84 (pre) / 19.83 (post), and 19.83 is what the campaign
README's G3-post row prints. One quantity, three published values — nothing turns on the choice (the
gate is >= 15 Hz and every variant clears), but a reader could not reconcile the files. The
campaign README still prints 19.93 in its own before/after table and needs the same pass. The
`< 15 Hz` denominator is **792**, not 793: the first tick records `dt = 0` and is excluded from the
rate (`run_phase_c.py:877`), so 793 ticks give 792 intervals.

† **Vacuous by construction, both columns (R-21, 2026-07-21T19:45Z).** R-10 disowned the `0 track
losses` below; the `100.0%` beside it is the same metric and is disowned here. `track_coverage_pct`
counts frames in which `tracker.update()` returned something and `track_loss_events` counts entries
into the empty case — one `track is None` branch, published twice. Reaching it needs
`MAX_LOST_FRAMES = 30` at `CONTROL_HZ = 20`, i.e. 1.5 s with no detection at all, which the 1 Hz
`score=1.0` injection never produced: all four committed CSVs have **0 rows with an empty
`track_id`**, before and after the tracker fix. 100.0% coverage means the detection supply never
stalled; it is not evidence the loop held the target.

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
| G1 server | PASS | server 0.9.16 == client 0.9.16, `Town10HD_Opt` loaded, world ticks advancing — **400 ticks / 399 frames** in the run this row names (`runs/g1-scripted/results.json`); see the provenance note below for what was withdrawn from this cell |
| G2 render | PASS | dominant-colour fraction **0.007–0.026** (gate < 0.99), frames opened with the Read tool |
| G3 pose slaving | PASS | copter flew **0 → 84.4 m north** under its own GUIDED control at a held 60.0 m; content at ticks 150/300/599 distinct and consistent with position; nadir `pitch=-90` confirmed by viewed frame |
| G4 traffic | PASS | **40/40** vehicles spawned with autopilot; first vs last frame not byte-identical |
| G5 rate | PASS | **48.1 Hz** mean — *render-loop wall throughput of a bare client*, no perception in the window (gate >= 20 Hz); 5/599 ticks under 15 Hz, all in the first ~5 s of cold shader compilation. The "2.4x the control rate" reading is withdrawn: see the audit below |
| G6 grounding | **NOT RUN** | see the correction below — first recorded as blocked by a missing checkpoint, which was wrong |

**G1 provenance (corrected 2026-07-21T19:45Z, R-21).** This row first read "155 spawn points, 41
vehicle blueprints, 599 ticks", and all three were wrong in the same way — none is recoverable from
what was committed. No server stdout was kept for P6.1 (the campaign dir has no `raw/`), and the
as-run runner (`d925c74:runners/carla_render.py`) never printed a spawn-point or blueprint count at
all, so **155 and 41 are unattributed prose and are withdrawn** rather than restated; they are not
in evidence for or against. The tick count belonged to a different run: `runs/g1-scripted/`
records `ticks: 400, frames_received: 399, vehicles: 30`, while **599** is `runs/g3-mavlink/`'s
frame count (its `tick_dt` has 599 entries of 600 ticks) — a reader who opened the named run found
different numbers. Settling the two withdrawn counts needs a live 0.9.16 server queried for
`get_map().get_spawn_points()` and the four-wheel `vehicle.*` blueprint filter, with the output
committed to `raw/`; nothing in the gate verdict depends on either.

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
to **445 lines** (`wc -l` at `d925c74`: `carla_render.py` 260 + `sitl_fly_leg.py` 185 — the **387**
first published here is the sum of two campaign-README figures, 229 + 158, and neither addend
reproduces from the committed source under any counting rule, raw, non-blank, or
non-blank-non-comment; corrected 2026-07-21T19:45Z, R-21), all of it in the unforeseen risk:
driving SITL without MAVProxy. Eight silent
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

### P6.2-DELIVERY — closed-loop WARM maintain-and-deliver vs COLD blocking acquire (2026-07-24)

Detail: [`../../experiments/2026-07-23-p62-delivery/README.md`](../../experiments/2026-07-23-p62-delivery/README.md).
Config: RTX-3090 host + CARLA 0.9.16 `Town10HD_Opt` (pose-slaved nadir renderer, async on purpose —
sync erases the delivery lag), ArduCopter SITL physics, SAM2 carry on the 3090 rate-capped to the
Jetson 2.69 Hz (`prune_after=32`); **ORACLE target designation** — grounding held constant via GT-box
seed because the deployed q8_0 is non-discriminative at 45 m nadir (G6 center-bias); PID kp_lat=0.05
max_v=4.0; alt 45 m; 25 distinct seeds + first-3 x2 noise band. Run: `run_p62_matrix.py --oracle`.

**FOLLOW PASS: WARM 23/25 vs COLD 2/25.** Exact McNemar b=21, c=0 (one-directional), n_eff=25,
two-sided **p=9.54e-07**; reachable (b+c=21 >> 6), survives Part-VI Holm. WARM Wilson95
**[0.750, 0.978]**. COLD `target-exits-frame=0` — cold fails by staleness, not frame-exit; surprise
branch null. Schedule-noise band: 0 rep flips (seeds 0-2 both reps agree). WARM residuals: seed 8
late carry-drift (cov 0.091), seed 13 non-lock + anomalous road-spanning GT box (author-flagged,
counted WARM=0). The 2 COLD passes (seeds 14, 20) are slow/favorable targets (seed 20 world-disp
15.2 m, lowest in the bank).

**Result: YES [oracle-designation scope].** Closed-loop warm-start delivers a followable lock the PID
holds; cold hovers blind through the ~4.85 s lag then delivers a stale box off-target. E18-n25
delivery-lag staleness **holds and amplifies in closed loop** — self-induced ego-motion does not
rescue cold. Control-coupling claim only (S5); does NOT license a nadir-grounding claim (G6). Proof:
`proof/p62_warm_vs_cold.png` (behaviour), `proof/p62_follow_pass.png` (numbers).

### P6.2-COUPLING — coupled vs decoupled warm carry (isolates C1) (2026-07-24)

Detail: [`../../experiments/2026-07-23-p62-coupling/README.md`](../../experiments/2026-07-23-p62-coupling/README.md).
Config: identical rig to P6.2-DELIVERY (RTX-3090, CARLA `Town10HD_Opt` pose-slaved nadir, SITL
physics, SAM2 carry rate-capped 2.69 Hz, ORACLE designation, alt 45 m). Paired-continuous, same 25
CARLA seeds. **COUPLED arm** = the DELIVERY WARM flights reused (warm track drives the PID);
**DECOUPLED arm** = byte-identical warm perception but the oracle `actor_box` drives the PID
(feedback path cut). Metric = per-seed post-prompt follow-error (px) of the warm track vs `actor_box`.
Run: `run_p62_matrix.py --coupling --coupled-root runs/p62_delivery` (decoupled re-fly uses
`build_grounding_carry(carry_only=True)` — no Jetson `llama-server`, oracle_gt seeds from GT).

**Wilcoxon signed-rank (two-sided) p=0.596 (n.s.).** Median paired diff **−0.42 px**, bootstrap 95%
CI **[−4.56, +4.08] px**, within the warm-arm schedule-noise band (max |rep diff| **6.70 px**, mean
2.58; from DELIVERY seeds 0-2 ×2). Mean follow-error coupled **26.77** vs decoupled **63.18** — the
mean gap is entirely stochastic SAM2 carry drift firing on different seeds per run (decoupled re-fly
drew two fresh catastrophic leaks: seed14 760 px, seed21 249 px; both arms drifted on seed13 377/285
and seed8 ~72), which the outlier-robust median/signed-rank do not see. 22 of 25 seeds sit in 5-25 px
both arms.

**Result: BOUNDED NULL (frozen gate outcome ii). C1 closed = "warm carry survives self-induced
ego-motion."** Closing the control loop does not systematically degrade the maintained track vs an
oracle driving the same warm perception; any coupling penalty is below the noise floor. Not proven
equivalence (two-sided design). Control-coupling scope only (S5). Proof:
`proof/p62_coupling_paired.png` (numbers), `proof/coupled_seed24_i200_iou084.png` +
`proof/coupled_seed24_i399_iou093.png` (coupled arm holding lock through its own ego-motion),
`proof/decoupled_seed14_carryleak.png` (the failure mode is carry, not coupling — a leak in the arm
with no feedback loop).

### P6.2-SHOWCASE — on-Jetson closed-loop flight (2026-07-24) · qualitative, NOT in Holm family

One WARM closed-loop flight, `run_p62_matrix.py --showcase --alt 45 --t-prompt 14 --seconds 28`,
target police charger (oracle designation), CARLA Town10HD_Opt + ArduCopter SITL. SAM2 carry routed
LITERALLY to the Orin over ssh-stdio; a 3090 `_HostCarry` twin scored in lockstep for the parity gate.

| metric | value | note |
|---|---|---|
| post-prompt coverage | **0.495** (202/560 lock frames) | copter flies its own PID output; target held through a road curve |
| carry parity (Jetson vs 3090-twin, median IoU/step) | **0.960** (min 0.805, 90% ≥ 0.9) | 52/52 both-boxed; gate ≥ 0.95 PASS — E1 mask parity 1.000 holds live |
| ssh round-trip | 424 ms/step (~2.4 Hz), compute 422 ms | transport ~2 ms; carry compute dominates |
| seed / acquire | oracle ≈ 0 s, first deliver t=1.95 s | idle-window seed, no cold-acquire lag |

**Result: PASS (qualitative).** The closed loop holds a lock with SAM2 carry running literally on the
Jetson in-loop; the in-rig parity gate confirms the on-device carry reproduces the parity-checked 3090
carry. Follow honest not perfect (2.69 Hz carry vs 20 Hz GT sawtooths delivered IoU, peaks ~0.5–0.6).
Proof: `proof/flight_follow_overlay.png` (GT + Jetson-carried box on the charger through a curve),
`proof/flight_trace.png` (delivered IoU over the flight + carry parity vs the 3090 twin per step).

### EXP-1 — carry-res ELBOW (SAM2 track image_size 256→1024, on the Orin) (2026-07-24)

**Engineering measurement, not a registered claim (R-44).** This campaign was run to *choose an
operating point*, not to test a thesis hypothesis: it is not in `thesis/claims.json`, carries no
Holm entry, and nothing below is an inferential result. The paired tests it ran are descriptive
companions to the effect sizes and live in the campaign README, not in this row.

Seed box held fixed (GT), only SAM2 internal `image_size` swept across 7 points. 38 UAV123 clips,
contiguous-GT window (24 steps @ stride 11). Carry runs ON the Orin via the ssh-stdio bridge; 3090
NOT used. Machine `jetson`, 15 W + `jetson_clocks`. `run_exp1.py`.

| image_size | median-of-median IoU | mean held_frac | PASS (medIoU≥0.25) | on-device Hz |
|---:|--:|--:|--:|--:|
| 256 | 0.675 | 0.721 | 28/38 | **10.20** |
| 384 | 0.760 | 0.768 | 29/38 | 9.64 |
| 512 | 0.780 | 0.837 | 32/38 | 8.71 |
| **640** | **0.811** | 0.859 | 32/38 | **5.76** |
| 768 | 0.803 | 0.882 | 33/38 | 4.08 |
| 896 | 0.805 | 0.897 | 35/38 | 2.99 |
| 1024 | 0.816 | 0.921 | 36/38 | 2.34 |

**Elbow = 512–640.** IoU plateaus above 512 (+0.036 over a 2× size jump; flat within noise from 640
up); Hz is flat-high (~9–10 Hz, overhead-bound) below 640 then falls off a cliff (each step ~halves
the rate). **640 = 99.4% of 1024's IoU at 2.5× throughput** (5.76 vs 2.34 Hz); 512 = 96% at 3.7×.
Below 512 the speed saturates so it is pure IoU loss. Paired 768-vs-1024 (original contrast) holds:
delta −0.0086, CI95 [−0.0135,−0.0017]; on PASS, 3 of 38 clips lose at 768 and none gain. **Tail is
resolution-gated:**
the bulk of clips is flat across all sizes but 9 small/distant clips (truck2/3, uav3, bike3, person21,
car11/13…) collapse at low res and recover only by 896–1024 — so `held_frac` keeps rising to 1024
even as median IoU plateaus. Deploy: carry at **640** default, **1024 size-gated fallback** for small
targets. Proof: `proof/elbow_iou_hz.png`, `proof/per_clip_iou.png`, `proof/hz_ondevice.png`. Detail:
`experiments/2026-07-24-resolution-decoupled-carry/README.md`.

### EXP-2 — point-crop vs NL referring-expression select (26 P5.18 cells / 13 clips, on the Orin) (2026-07-24)

**Engineering measurement, not a registered claim (R-44).** Same standing as EXP-1: run to choose a
grounding operating point, not in `thesis/claims.json`, no Holm entry, no inferential number quoted
here. Its paired tests are in the campaign README.

Operator point → crop → VLM grounds crop → SAM2 carry (PT) vs whole-frame NL referring expression
(NL). SAM2 carry on the Jetson; 3090 not used (`machine=jetson`).

**Primary — delivered PASS at deployed res** (NL max_side=1024, PT crop=512, carry 1024):

| Leg | NL | PT | discordant cells (NL-only b / PT-only c) | verdict |
|---|--:|--:|:--|:--|
| WSEL | 22/26 | 24/26 | b=1 c=3 | MISS (b+c=4 < the reachable floor 6) |
| SWAP | 24/26 | 26/26 | b=0 c=2 | MISS (b+c=2 < the reachable floor 6) |

The MISS is a *design* verdict, not a test outcome: deflated to 13 clips the design needs b+c>=6
discordant pairs before any two-sided exact test can reach alpha=0.05, and neither leg produced
them. No p-value is quoted because none of them could have been informative.

Not separable at n=26, but every discordant leans PT (7 PT-only vs 1 NL-only; PT never loses a SWAP
cell). Consistent with R-38: at the lenient 0.25-IoU delivery threshold the SAM2 carry rescues NL's
rougher boxes, so the pointer buys no extra delivered PASS. 8/8 pass cells visually confirmed genuine.

**Grounding-res elbow** (n=26 WSEL cells, strict IoU≥0.5, no carry) — the real separation:

| feed px | 192 | 256 | 384 | 512 | 640 | 768 | 896 | 1024 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| NL hit | — | — | — | 0.077 | 0.269 | 0.462 | 0.654 | **0.654** |
| PT hit | 0.231 | **0.769** | 0.731 | 0.769 | — | 0.846 | — | — |

**PT@256px (0.769) out-grounds NL@1024px (0.654)** — the point-crop concentrates the VLM's effective
resolution onto the target; PT is flat-high from a 256px crop, NL climbs to a lower plateau. The
point-crop is a grounding-efficiency + localization-precision win (≥ NL accuracy at 4× lower feed
res), not a delivered-PASS win at the deployed threshold.

**Carry-res robustness** — the verdict is flat in tracker-res: re-carrying the fixed acquire boxes at
image_size 512/768/1024 gives byte-identical counts (WSEL 22/24, SWAP 24/26, same b/c) at every size
(8.6/4.1/2.3 Hz on-device) — so EXP-1's 512–640 carry elbow costs zero select quality here. Proof:
`proof/grounding_elbow.png`, `deliver_pass.png`, `carry_robustness.png`. Detail:
`experiments/2026-07-24-point-crop-select/README.md`.

### P6.7 — the handoff seam: designation -> live SAM2 track (25 CARLA clips x 2 lags x 2 arms, on the Orin) (2026-07-25)

What the operator waits through between "locked in" and a live track. Paired arms on the same
25 CARLA GT clips (`Town10HD_Opt`, replayed at 5 Hz from disk): **COLD** = one bridge `Popen`
per designation (what `runners/carla_debug_ui.py` does today), **WARM** = bridge already
resident and CUDA already warm. Two designation lags: 0.0 s (oracle click) and 4.85 s (the
E18/R-34 cold grounding lag). SAM2 on the Orin via the ssh-stdio bridge, `image_size=512`,
15 W + `jetson_clocks`, `llama-server` resident throughout; the 3090 was not used.
`handoff_p67.py`. `machine=jetson-orin-nano-8gb`, n_effective = n_rows = 25.

**Stage decomposition (medians, seconds).** Columns are independent medians, so they do not
sum to the `t_handoff` median.

| stage | COLD @ lag 0.0 | COLD @ lag 4.85 | WARM @ lag 0.0 | WARM @ lag 4.85 |
|---|--:|--:|--:|--:|
| `ssh_spawn` | 0.301 | 0.307 | 0 | 0 |
| `import` (torch + sam2) | **2.846** | **2.893** | 0 | 0 |
| `weights` (`from_pretrained`) | 1.800 | 1.800 | 0 | 0 |
| `warmup_init` | 0.670 | 0.670 | 0.120 | 0.121 |
| `drain` (catch-up proper) | 0.361 | 0.658 | 0.178 | 0.392 |
| **`t_handoff`** | **6.148** | **6.311** | **0.299** | **0.515** |
| `steps_to_live` (median) | 3 | 6 | 1 | 4 |

**4.95 s of the 6.15 s — 80% — is process start-up**, and `import torch` alone exceeds
everything else combined. Only 0.36 s is the tracker actually catching up, which is why the
panel's `catchup_s` was invariant (0.06 s) between a 0-frame oracle click and a ~21-frame
caption follow: it was never measuring catch-up.

**G1 (the lever) = PASS at both lags.**

| lag | COLD median | WARM median | speed-up | concordant pairs | Wilcoxon (two-sided) |
|--:|--:|--:|--:|--:|--:|
| 0.0 s | 6.148 s (IQR 5.95–6.20) | **0.299 s** (IQR 0.30–0.30) | 20.6x | 25/25 | p=5.96e-08 |
| 4.85 s | 6.311 s (IQR 6.17–6.51) | **0.515 s** (IQR 0.51–0.53) | 12.3x | 25/25 | p=1.23e-05 |

Every pair moves the same way in both lags. 5.96e-08 = 2/2^25 is the exact floor for a
two-sided signed-rank test at n=25. At lag 4.85 two clips share an identical paired
difference (5.7946 s) and that tie in `|d|` makes scipy's default method fall back to the
normal approximation (**1.228e-05**); `method="exact"` on the same numbers gives 5.96e-08.
The registry uses the default, so the claim is registered at the conservative 1.228e-05.

**G2 (quality non-inferiority) = PASS**, paired, 20 000-resample percentile bootstrap.

| lag | metric | COLD | WARM | paired delta | CI95 | p |
|--:|---|--:|--:|--:|---|--:|
| 0.0 | median IoU | 0.000 | **0.674** | +0.049 | [+0.006, +0.502] | 0.00021 |
| 0.0 | box-present frac | — | — | 0.000 | [0.000, +0.010] | 0.027 |
| 0.0 | identity swaps | 79 | 68 | 0 | [−1, 0] | 0.11 |
| 4.85 | median IoU | 0.000 | 0.000 | 0.000 | — | 0.123 |
| 4.85 | box-present frac | — | — | 0.000 | — | 0.065 |
| 4.85 | identity swaps | — | — | 0.000 | — | 0.358 |

n=24 on the IoU rows (in `clip01` the target leaves frame before COLD's tracker exists). The
lag-4.85 rows pass **over a floor** — both arms sit at median IoU 0.000 — and are recorded as
uninformative, not as reassurance.

**The unanticipated result: COLD does not just delay the track, it loses it.** On-target clip
counts, paired: lag 0 COLD **11/24** vs WARM **20/25**, exact McNemar b=8 c=0, **p=0.0078**;
lag 4.85 COLD 7/24 vs WARM 10/25, b=4 c=1, p=0.375. The loss is altitude-gated (target size):

| altitude | median target area | COLD on-target @ lag 0 | WARM on-target @ lag 0 |
|--:|--:|--:|--:|
| 40 m | 1595 px² | 4/5 | 5/5 |
| 60 m | 659 px² | 3/5 | 5/5 |
| 80 m | 289 px² | 2/5 | 4/5 |
| 100 m | 132 px² | 1/5 | 3/5 |
| 120 m | 160 px² | 1/4 | 3/5 |

Mechanism: with `CATCHUP_JUMP=12` at `CAM_HZ=5`, one SAM2 step crosses **2.4 s of world**. A
tracker that took 6.15 s to boot wakes to a ~31-frame backlog whose first hop is that 2.4 s;
on `clip03` (100 m, 7x17 px seed) the *first* step already reads IoU 0.000 with the mask on an
overpass 60 px away. Cold start-up -> long backlog -> large temporal jumps -> lost track.

**G3 (residency, the pre-registered honest risk) = PASS, and not narrowly.**

| quantity | value | limit |
|---|--:|--:|
| `rc=-9` over designations on one resident bridge | **0 / 50** | 0 over 25 |
| `MemAvailable` floor, `llama-server` only | 2258 MB | — |
| `MemAvailable` floor, + SAM2 resident | **1315 MB** | > 0 |
| `ground_ms` median, SAM2 absent | 3791.1 ms | — |
| `ground_ms` median, SAM2 resident | **3791.2 ms** | <= 4359.8 ms (+15%) |

A resident SAM2 costs the VLM **x1.000** across 25 paired grounding requests with genuine
per-request spread (3738.4–3876.5 vs 3738.6–3842.3 ms; server `prompt_ms` 3163.0 vs 3163.3).
The pre-registered fallback arm `PIPELINE` was not run — it existed only for a G3 failure.

**RQ-e (catch-up policy, no gate) — a monotone trade, and no setting wins both.** 75 WARM
cells, 25 clips x `CATCHUP_JUMP` in {1, 12, 999}, all at lag 4.85 s.

| `CATCHUP_JUMP` | median `t_handoff` | median steps to live | median IoU | on target (IoU >= 0.25) |
|---|--:|--:|--:|--:|
| 1 — replay every frame | 5.312 s | 50 | **0.596** | **17 / 25** |
| 12 — deployed | **0.517 s** | 4 | 0.000 | 10 / 25 |
| 999 — jump to live | **0.314 s** | 2 | 0.000 | 8 / 25 |

Paired exact McNemar on per-clip on-target: `j1` vs `j999` b=11, c=2, p=0.0225; `j1` vs `j12`
b=9, c=2, p=0.0654; `j12` vs `j999` b=4, c=2, p=0.6875. **Descriptive only** — RQ-e carried no
gate, is not registered in `thesis/claims.json`, and is not Holm-corrected. Replaying the gap
frame-by-frame is the only setting that keeps the track, and it gives back the whole latency
win (5.31 s to cross 4.85 s of world). 12 and 999 are statistically the same policy, so the
deployed value buys nothing over jumping straight to live: by 12 frames the identity is
already lost. The residual therefore sits upstream in grounding latency, not in the bridge.

Proof: `proof/stage-budget.png`, `proof/paired-handoff.png`, `proof/quality-paired.png`,
`proof/jump-tradeoff.png`, `proof/seam-{COLD,WARM}.png`, `proof/loss-{COLD,WARM}.png`. Detail:
`experiments/2026-07-25-handoff-latency/README.md`.

### EXP-4 — native source vs zoom, disentangled (MODE 2 click-crop, lever a')

Run 2026-07-26T20:05Z. Bank-1920-single: 25 CARLA `Town10HD_Opt` nadir captures at 1920²/FOV90,
one designated vehicle each, footprint 61-221 px, altitude solved per target from
`alt = f*L/target_px` (20-120 m). Grounding is `phase3-terse100eos-1024-q8_0.gguf` on the Orin
(15 W + `jetson_clocks`) over `JetsonBackend`; CARLA on the 3090 at 200 W. Four arms, **all fed
at 512** so feed size is not a confound; window centred on the GT centre (the perfect operator
click) in every arm. No carry.

| arm | source | window | FOV | feed | hit@0.5 | mean IoU | median IoU | median wall_s |
|---|---|---|---|--:|--:|--:|--:|--:|
| **A (CONTROL, deployed)** | 960 | 512 | 53.3% | 512 1:1 | 0.60 | 0.4629 | 0.5455 | 2.04 |
| B | 1920 | 1024 | 53.3% | 512 2:1 down | 0.52 | 0.4249 | 0.5000 | 2.04 |
| **C (MODE 2)** | 1920 | 512 | 26.7% | 512 1:1 native | **0.92** | **0.7651** | **0.8571** | 2.03 |
| D (FOV-matched zoom control) | 960 | 256 | 26.7% | 512 2x LANCZOS up | 0.88 | 0.6350 | 0.6667 | 2.04 |

| contrast | b | c | p (McNemar, exact) | p (Wilcoxon, IoU) | median IoU diff |
|---|--:|--:|--:|--:|--:|
| **C vs D** (primary) | 1 | 0 | 1.0 | 0.00285 | 0.0000 |
| A vs D (zoom alone) | 1 | 8 | 0.0391 | 0.0400 | 0.0000 |
| A vs B (downscale-chain null) | 4 | 2 | 0.6875 | 0.6832 | 0.0000 |
| C vs A (MODE 2 vs deployed) | 8 | 0 | 0.0078 | 0.00059 | +0.3308 |

n = 25, **deflated n = 25**: the 30 m separation rule was enforced at selection time (minimum
realized pairwise camera separation 31.1 m), so there is no post-hoc collapse. The model is
greedy, so the run is deterministic — a repeat invocation reproduced the table byte-for-byte.

**Primary MISSES its pre-registered gate** (b+c = 1, floor 6), which retires lever (a'): native
1920 pixels buy nothing at hit@0.5 over a 2x LANCZOS upscale of the 960 display frame. The
secondaries carry the result — magnification alone wins (A vs D, p=0.039) and MODE 2 beats the
deployed control decisively (C vs A, p=0.0078, +0.33 median IoU). C's residual 8% is
referring-expression ambiguity, not detail: the C-loss proof frame grounds a different grey car
under the caption "the grey car". Descriptive-plus-tested but **not yet in
`thesis/claims.json`**; not Holm-corrected here.

Proof: `proof/exp4-arms.png`, `proof/exp4-C-win-t06-yellow-taxi.png`,
`proof/exp4-C-loss-t03-grey-ambiguity.png`. Detail:
`experiments/2026-07-26-crop-mode/README.md` §6.

---

### EXP-5 — carry-crop mechanism pilot (MODE 2, levers b / c / e)

Run 2026-07-26T22:40Z. 12 UAV123 clips x 6 arms = 72 carry runs, SAM2 on the Orin over
`carry_ssh_bridge.py` (15 W + `jetson_clocks`), CARLA not involved. Stride 11, 24 steps
(~8.8 s per clip), frozen EXP-1 seed boxes. Metric = per-clip median IoU vs GT.
**Exploratory pilot: no test, no p-value, gates nothing** — the n>=25 rule binds gating arms
and this is not one.

| arm | carry | `image_size` | tail >= 0.25 | tail median IoU | easy median IoU | vetoes | spirals | on-device Hz |
|---|---|---|---|---|---|---|---|---|
| A1 CONTROL (deployed) | plain frame | 640 | 4/8 | 0.223 | 0.905 | 0 | 0 | 5.75 |
| A2 CONTROL-2 (fallback) | plain frame | **1024** | **8/8** | 0.683 | 0.913 | 0 | 0 | **2.34** |
| A3 GUARD-ONLY | plain + guard | 640 | 3/8 | 0.000 | 0.905 | 44 | 0 | 5.73 |
| **A4 CROP-FIXED-NOGUARD** | fixed 512 window | 640 | **7/8** | **0.703** | 0.907 | 0 | 0 | **6.30** |
| A5 CROP-FIXED-GUARD (pre-reg treatment) | fixed 512 + guard | 640 | 5/8 | 0.560 | 0.907 | 24 | 0 | 6.29 |
| A6 CROP-SCALED-GUARD | `roi_window` + guard | 640 | 6/8 | 0.707 | **0.882** | 5 | 1 (`uav3`) | 6.50 |

`D_MAX` = 4.2 (pre-registered rule: 99th pct of A1's per-step displacement, raw 4.2055 over
n=278 steps; p50 0.531, p95 2.087). The rule is contaminated by construction — the CONTROL
distribution contains the drift events the veto exists to catch. Diagnostic split: TAIL p99
4.559, EASY p99 **1.734**. The rule was honoured as written and 4.2 was used; a tighter
threshold makes the failure below worse, not better.

**Verdict as pre-registered: KILL.** Kill gate 3 fires (A5 5/8 < A2 8/8 — the config flag
wins). The proceed gate fails and was **unreachable by construction**: only 4 tail clips sit
below 0.25 in A1, so ">= 4/8 recovered" demanded a perfect 4/4, and `uav3` (720x480, so its
window is 480 — barely a crop) is recovered by nothing below 1024. Kill gates 1 and 2 did not
fire.

The arm decomposition localizes the kill. **Lever e (the guard) is dead as specified**: it
self-latches, because holding the previous box on veto freezes the reference the next veto is
measured against. `car13`/A3 = 23 displacement + 1 area vetoes, 20 lost steps, 0.000, where A1
held 0.639; `bike3`/A5 = one real burst vetoed at ratio 3.67, then the frozen reference drives
the ratio 3.10 -> 5.95 monotonically, 13 area vetoes, 0.000, where A4 absorbed the same burst
and finished at 0.92. **Lever c is answered: FIXED beats SCALED** — A6 reaches 6/8 but
regresses an easy control (`car18` 0.921 -> 0.000, box collapses to 0.37 area ratio and the
window strands) and owns the only monotone spiral. **Lever b (the fixed crop) survives and is
free**: A4 beats A1 on the tail 7/8 vs 4/8 (+0.48 tail median), does not regress the easy
clips, and is *faster* — 6.30 vs 5.75 Hz, transport not compute (median step 159 vs 174 ms; a
512 crop is a smaller JPEG than a 1280x720 frame at the same `image_size`).

Not in `thesis/claims.json` and no Holm correction — exploratory by pre-registration. A4 is
carried into EXP-6 as a **declared post-hoc arm promotion**, with a held-out-26 primary
stratum so the promotion is not graded on the 12 clips that produced it.

Proof: `proof/exp5-arms.png`, `proof/exp5-guard-latches.png`, `proof/exp5-scaled-strands.png`.
Detail: `experiments/2026-07-26-crop-mode/README.md` §7.

### EXP-6 — carry-crop at gate scale (MODE 2, lever b confirmed)

**Engineering measurement, not a registered claim (R-44).** Same standing as EXP-1/EXP-2: a
shipping gate on a carry mode, not in `thesis/claims.json`, no Holm entry. The signed-rank
p-values behind every row below are in the campaign README.

Run 2026-07-26T23:40Z. 38 UAV123 clips x 3 arms = 114 carry runs, SAM2 on the Orin over
`carry_ssh_bridge.py` (15 W + `jetson_clocks`), CARLA not involved. Same frozen EXP-1 staging
as EXP-5 (stride 11, 24 steps, ~8.8 s per clip). Metric = per-clip median IoU vs GT; primary
test Wilcoxon signed-rank on the **held-out 26** (the clips EXP-5 never touched), deflated by
UAV123 base sequence; delivered-PASS (median IoU >= 0.25) + exact McNemar secondary.

| arm | carry | `image_size` | median-of-median IoU | PASS | tail-8 PASS | on-device Hz |
|---|---|---|---|---|---|---|
| CONTROL (deployed) | plain frame | 640 | 0.811 | 32/38 | 4/8 | 5.76 |
| **TREATMENT** | fixed 512 window | 640 | **0.815** | **35/38** | **7/8** | **6.31** |
| CONTROL-2 (fallback) | plain frame | 1024 | 0.817 | 36/38 | 8/8 | 2.34 |

TREATMENT vs CONTROL by stratum (median paired difference; PASS discordants as b / c):

| stratum | n / n_eff | TRT | CTL | PASS | diff | PASS discordants |
|---|---|---|---|---|---|---|
| **held-out 26 (PRIMARY)** | 26 / 24 | 0.831 | 0.833 | 24 / 24 | +0.0085 | b=0 c=0 |
| pilot 12 (contaminated) | 12 / 12 | 0.774 | 0.681 | 11 / 8 | +0.0735 | b=3 c=0 |
| all 38 (descriptive) | 38 / 36 | 0.815 | 0.811 | 35 / 32 | +0.0190 | b=3 c=0 |
| tail 8 | 8 / 8 | 0.703 | 0.223 | 7 / 4 | +0.0940 | b=3 c=0 |
| non-tail 30 | 30 / 28 | 0.853 | 0.834 | 28 / 28 | +0.0060 | b=0 c=0 |

TREATMENT vs CONTROL-2: held-out 26 diff +0.0050; all 38 +0.0015; tail-8 +0.0080 — under 0.01
median IoU in every stratum, and one clip apart on PASS (35/38 vs 36/38), at 2.7x the rate. The
signed-rank
p-values for each row are in the campaign README (R-44: they stay out of the ledger because this
campaign is an engineering gate, not a registered claim).

**Verdict: PARTIAL PASS — throughput-matched parity with the 1024 fallback, tail-scoped win,
not a blanket carry replacement.** Exactly the pre-registered most-likely outcome. The
shipping gate passes (d_IoU -0.002, d_PASS -1 clip, rate 2.7x, all inside the pre-registered
bounds). The accuracy gate **fails**: +0.0085 median IoU on the held-out 26 with zero PASS
discordants is a bounded null, and the stratum is at ceiling under both arms (PASS 24/24 each, both ~0.83), so
there was nothing there for a crop to add. The effect lives in the resolution-gated tail
(0.703 vs 0.223, PASS 7/4) — descriptive, n=8, not a powered claim.

Two artefacts checked rather than assumed. **`n_lost` (38 vs CONTROL's 24) is not a crop
cost**: every extra lost step falls in `car11`/`uav3`/`uav8`, the three clips that read 0.000
in *all three* arms — the crop never loses a target the plain arm holds. **The 720x480
subgroup** (`uav3`, `uav8`; the only two non-1280x720 clips) is uninformative, not negative:
the window is `min(512, 480) = 480`, barely a crop, and both are 0.000 in both arms. `uav3`
reaches 0.436 under CONTROL-2, i.e. it is resolution-gated and only the 1024 fallback delivers
it — the size-gated-fallback argument, measured.

Estimate vs actual: PASS predicted 32/35/36, measured 32/35/36; CONTROL 0.811 predicted and
measured. TREATMENT's median-of-median came in 0.815 against a predicted 0.845 (the pilot's
margin did not survive 26 ceiling clips). On-device cost ~12 min against a ~3-4 hr estimate
(that estimate priced all three arms at 1024 timings; two run at 640).

Not in `thesis/claims.json` — the primary is a null and the parity result is an engineering
gate, not a thesis claim; no Holm entry. Machine: SAM2 on `jetson-orin-nano-8gb`, no 3090.

Proof: `proof/exp6-arms.png`, `proof/exp6-win.png`, `proof/exp6-loss.png`.
Detail: `experiments/2026-07-26-crop-mode/README.md` §8.

### EXP-7 — composed MODE 2, closed loop: NOT RUN (gate not met)

Recorded 2026-07-26T23:55Z. §9's entry condition was "runs only if EXP-4 and EXP-6 both
pass". EXP-4 missed its primary (lever a' retired) and EXP-6 is a partial pass, so the gate
did not fire — and the composition makes that substantive rather than procedural: EXP-4
retired the native-1920 source, so MODE 2's ground half collapses onto the already-deployed
`roi_reanchor` on the 960 frame, and EXP-6's carry half is a measured null against the
deployed carry except on the size-gated path. TREATMENT would have been the deployed system
plus a null. 25 live CARLA seeds and ~1-2 days not spent. Detail:
`experiments/2026-07-26-crop-mode/README.md` §9.

### P6.6 — what maintaining costs: watts and rate-sustain of the warm carry (5 arms x 300 s x 3 repeats, on the Orin) (2026-07-26)

Run 2026-07-26T14:06Z-15:51Z, `machine=jetson-orin-nano`, 15 W + `jetson_clocks`, no CARLA and
no 3090 in the loop. `tegrastats --interval 500` on the device; the parser takes the **instant**
mW figure and trapezoid-integrates over the steady window (from the SAM2 step-loop start, not
process start), so an irregular sample cadence does not bias the mean. Arm order randomised
inside each repeat (`seed=666`), cooldown between arms until `tj` returns within 2 C of the A0
median. Every number is the median of 3 repeats; repeat-to-repeat spread of the mean is
0.010-0.036 W, two orders of magnitude below the deltas.

| arm | `VDD_IN` mean W | over `A0` | `CPU_GPU_CV` W | `SOC` W | achieved Hz | J per carried frame |
|---|---|---|---|---|---|---|
| A0 idle-bare (`llama-server` stopped) | 5.195 | — | 0.989 | 1.386 | — | — |
| A1 idle-deployed (resident, idle) | 5.193 | -0.002 | 0.989 | 1.385 | — | — |
| **B carry-640 (deployed default)** | **10.842** | **+5.647** | 4.128 | 2.263 | 6.273 | 1.728 |
| C carry-512 | 10.689 | +5.494 | 4.135 | 2.211 | 10.043 | 1.064 |
| D ground (repeated q8_0 acquires) | 11.504 | +6.309 | 4.292 | 2.457 | — | — |

**RQ-P6.6a: the maintain price is +5.65 W over an idle board = 1.4-3.8% of hover.** The hover
figure is a **literature range for a small copter (150-400 W), not measured here** — this
project has no airframe, and `proof/maintain-price.png` draws it as a band for that reason. All
of the +5.65 W is SAM2's: `A1 - A0 = -0.002 W`, so a resident `llama-server` holding the
deployed q8_0 (`ram_max` 4169 MB vs 1524 MB bare) draws nothing measurable while idle. Warm
start's memory residency is free; only the carry costs.

Joules to deliver one box, warm (maintain the whole window, 0 s stale) vs cold (idle, then a
4.85 s blocking acquire at arm D's power, 4.85 s stale): 10 s 108.4/107.7 = 1.01x; 30 s
325.3/211.6 = 1.54x; 60 s 650.5/367.4 = 1.77x; 120 s 1301.0/679.0 = 1.92x. **Break-even is a
9.9 s idle window**; past that warm is strictly more energy for strictly less staleness, capping
at ~1.9x by 2 min (asymptote `P_carry / P_idle` = 2.09x).

| arm | repeat | Hz first 60 s | Hz last 60 s | delta % | `tj` start-end C | G1 |
|---|---|---|---|---|---|---|
| B carry-640 | r0 / r1 / rerun | 6.267 / 6.233 / 6.250 | 6.283 / 6.267 / 6.267 | +0.27 / +0.53 / +0.27 | 56.3-65.1 / 56.9-65.3 / 57.8-65.5 | PASS |
| C carry-512 | r0 / r1 / r2 | 10.033 / 10.000 / 10.000 | 10.050 / 10.050 / 10.050 | +0.17 / +0.50 / +0.50 | 58.4-65.2 / 58.7-65.3 / 57.4-65.6 | PASS |

**RQ-P6.6b: G1 PASSES 6/6, and the sign is up, not down.** Every carry arm ends the 300 s window
faster than it started, by +0.17% to +0.53% — one bin of jitter, not a trend, against a
pre-registered fail threshold of 10% decay. `tj` soaks ~57 to ~65 C and flattens; no clock cut
anywhere. The worst *clean* single sample in the whole matrix is 11.885 W (`D_r2`) against a
15 W cap, so the rail is not the binding constraint. 300 s is the measured window — a 20-minute
loiter is extrapolation, not a result.

Third finding, unasked for: **carry power is rail-bound, not work-bound.** 512 runs 1.60x the
rate of 640 (10.043 vs 6.273 Hz) at 0.15 W *less*, so J per carried frame falls 38% (1.728 to
1.064). Both arms sit at `GR3D_FREQ` 99% and both land ~10.7-10.8 W: at 15 W the GPU saturates
either way and the resolution knob buys throughput at constant draw. EXP-1 chose 640 on the
accuracy elbow alone; the energy axis points at 512 harder than EXP-1 did.

Arm B repeat 2 is **excluded and was re-run** into `runs/p66_b_clean` — the CARLA debug panel
was started on the host mid-arm and `runners/carla_debug_ui.py:2827` prewarms the Orin, putting
a second GPU consumer inside the window (`ram_max` 7460 vs 3243-3497 MB, rate 5.987 vs
6.273-6.280 Hz, power up). The rerun reproduces the clean repeats to 0.03 W and 0.000 Hz. The
contaminated record is kept, not deleted: -4.7% of the carry rate for one competing process is
the only measurement here of that effect.

Not in `thesis/claims.json` — this is a characterisation curve with one pre-registered
falsifiable prediction (G1) that passed, not a gated claim, so no Holm entry. Estimate vs
actual: every power estimate was **high** except the idle floor (B predicted 11-13 W, measured
10.84; D predicted 14-15 W peaks, measured 11.50 mean / 11.89 max).

Proof: `proof/power-by-arm.png`, `proof/carry-rate-decay.png`, `proof/maintain-price.png`.
Detail: `experiments/2026-07-25-maintain-cost/README.md`.

### EXP-8 Stage 0 — the carry ring's identity boundary (2026-07-26T19:06Z, `jetson`, 15 W + `jetson_clocks`)

`sam2.1-hiera-tiny`, `image_size=640`, K=`num_maskmem`=7, M=`max_obj_ptrs_in_encoder`=16,
3 UAV123 clips (`bike1`, `bike3`, `boat2`) × 120 steps @ stride 2, sha1 of the video-resolution
mask per step, 360 comparisons per row against `PRUNE_AFTER=100`.

| P | mask-identical vs P=100 | median IoU | RSS growth / run | peak RSS | peak CUDA | ms/step |
|---|---|---|---|---|---|---|
| 8 | 12.50% | 0.910 | 31.2 MB | 1274.5 MB† | 505.3 MB | 175.2 |
| 14 | 21.94% | 0.908 | 194.8 MB | 2013.5 MB | 505.3 MB | 172.8 |
| **15** | **100%** | 0.909 | 164.3 MB | 2016.8 MB | 505.3 MB | 173.0 |
| 16 | 100% | 0.909 | 182.3 MB | 2045.7 MB | 505.3 MB | 172.8 |
| 32 | 100% | 0.909 | 341.8 MB | 2172.9 MB | 509.6 MB | 172.9 |
| 100 (deployed) | 100% | 0.909 | 853.3 MB | 2844.7 MB | 529.6 MB | 173.8 |

† `ringP8` ran first, with a process baseline 580 MB below every other arm (a stale bridge from an
earlier session was resident and was killed ~1 min in), so its *peak* is not comparable across arms
and its first clip's 298 ms is excluded from rate reads. Its *growth* is comparable. Growth, not
peak, is the ring's own cost — peak carries a per-process baseline.

**H1 was a pre-registered point prediction and it landed on the exact frame.** From the arithmetic
alone — at step *n* SAM2 reads back to *n*−max(( `num_maskmem`−1)·stride, `max_obj_ptrs`−1) while
`StreamCarry` has popped {*j* ≤ *n*−1−P} — identity requires **P ≥ 15**. Measured lowest identical
P = **15**, with 360/360 steps byte-identical, collapsing to 21.9% at P = 14. `PRUNE_AFTER = 100`
therefore retains **85 frames the model provably never reads**, at a measured **8.1 MB per retained
frame** (growth 853.3 MB at P=100 vs 164.3 MB at P=15, over 85 frames) — **~670 MB of host RAM**
held for nothing, steady-state, on a board with 8 GB shared between CPU and GPU. Estimate vs
actual: I pre-registered ~4.9 MB/frame from the retained float32 3×640×640 input tensor alone and
~410 MB freed; the true cost is **1.65×** that, the balance being the retained
`non_cond_frame_outputs` entry and allocator slack.

Accuracy and rate are **flat across every P tested** (median IoU 0.908–0.910, ~173 ms/step),
including P = 8 where only 12.5% of steps are bit-identical. The ring is not a speed or accuracy
knob in either direction — it is pure RAM. This refutes the *rationale* of `D-R16.2`
(`docs/decisions/part4-end-to-end.md:682`, "the ring is a memory *horizon*") above 15 frames:
SAM2's horizon is `max_obj_ptrs_in_encoder` and the ring cannot extend it. Adopted as
`read_window()` in `stream_carry.py` (derived from the model's config, not hard-coded).

Not in `thesis/claims.json` — an engineering measurement with a passed falsifiable prediction, same
standing as EXP-1/EXP-2/EXP-6 after R-44, so no Holm entry. Benign, arm-invariant warning: SAM2
skips `fill_holes_in_mask_scores` because the `_C` extension is not compiled in the Orin venv.

Proof: `proof/ring_identity.png`. Detail: `experiments/2026-07-26-carry-memory-horizon/README.md`.

### EXP-8 Stage 1 — the memory-horizon sweep: K and M (2026-07-26T21:58Z, `jetson`, 15 W + `jetson_clocks`)

10 arms x 38 UAV123 clips x 24 steps @ stride 11, `image_size=640`, `PRUNE_AFTER=32`,
`sam2.1-hiera-tiny`, one service restart per arm. Baseline is stock K=`num_maskmem`=7,
M=`max_obj_ptrs_in_encoder`=16. Deltas are arm-minus-base on per-clip `median_iou` (Wilcoxon +
bootstrap CI95, Holm over the 9-comparison EXP-8 family); PASS is `median_iou >= 0.25`, exact
two-sided McNemar, b = clips flipping PASS->FAIL.

| Arm | K | M | med-of-med IoU | delta [CI95], p (Holm) | held_frac | PASS/38 | b/c, p | re-find | ms/step | peak CUDA MB |
|---|---|---|---|---|---|---|---|---|---|---|
| `base` | 7 | 16 | 0.811 | — | 0.859 | 32/38 | — | 3/129 (2.3%) | 173.4 | 506.7 |
| `K5` | 5 | 16 | 0.779 | -0.0035 [-0.0087, 0.0000], p=0.0087 (Holm 0.059) | 0.842 | 31/38 | b=1/c=0, p=1 | 5/144 (3.5%) | 166.5 | 506.7 |
| `K4` | 4 | 16 | 0.777 | -0.0029 [-0.0119, 0.0000], p=0.0084 (Holm 0.059) | 0.838 | 31/38 | b=1/c=0, p=1 | 12/148 (8.1%) | 163.8 | 506.7 |
| `K3` | 3 | 16 | 0.773 | -0.0021 [-0.0174, 0.0000], p=0.0116 (Holm 0.059) | 0.833 | 31/38 | b=1/c=0, p=1 | 9/152 (5.9%) | 161.2 | 506.7 |
| `K2` | 2 | 16 | 0.767 | -0.0076 [-0.0250, 0.0000], p=0.0025 (Holm 0.020, reject) | 0.820 | 31/38 | b=1/c=0, p=1 | 5/164 (3.0%) | 156.4 | 506.7 |
| `K1` | 1 | 16 | 0.752 | -0.0175 [-0.0321, -0.0049], p=2.0e-05 (Holm 1.8e-04, reject) | 0.728 | 28/38 | b=4/c=0, p=0.125 | 27/248 (10.9%) | 153.9 | 506.7 |
| `M8` | 7 | 8 | 0.802 | 0.0000 [-0.0006, 0.0000], p=0.259 (Holm 1) | 0.856 | 32/38 | b=0/c=0, undef | 6/131 (4.6%) | 174.0 | 506.7 |
| `M4` | 7 | 4 | 0.824 | 0.0000 [-0.0008, +0.0006], p=0.86 (Holm 1) | 0.855 | 32/38 | b=0/c=0, undef | 7/132 (5.3%) | 173.8 | 506.7 |
| `M2` | 7 | 2 | 0.807 | +0.0001 [-0.0004, +0.0023], p=0.896 (Holm 1) | 0.849 | 32/38 | b=0/c=0, undef | 3/138 (2.2%) | 173.6 | 506.7 |
| `M32` | 7 | 32 | 0.810 | 0.0000 [0.0000, 0.0000], p=0.748 (Holm 1) | 0.859 | 32/38 | b=0/c=0, undef | 3/129 (2.3%) | 174.0 | 506.7 |

**M is inert (H3 NO).** Every M arm is null on the continuous metric (p >= 0.259) with **zero
discordant pairs** — not one clip changes PASS status anywhere from M=2 to M=32, so McNemar is
undefined rather than merely non-significant. The one clip that moves, `car13` (0.639 to 0.475 at
M=2), is a ~10 px high-nadir target where the overlay shows carry and GT coincident: mask-boundary
jitter on a handful of pixels, not a lost track. M=32 does not win, so **G3 does not fire**. The
pre-registered caveat holds: M > 16 is off-distribution for the trained pointer embedding, and this
measures it as harmless, not as tested at its design point.

**K is real, monotone, and a bad trade (H2 NO).** K is the one lever that moves the continuous
metric, and it moves one way only: **b=0 in all five K arms** — a shortened dense memory never once
wins a clip. K5..K2 each cost exactly one clip (`building3`) and buy 4-10% of the step; K=1 costs
**four** clips, 13 points of held_frac, and buys 11.2%. Against EXP-1's resolution lever (2.46x rate
for -0.6% IoU) the exchange rate is not close. Per-clip it is a cliff, not a slope: `car7` is
perfect through K=2 (0.894..0.903) then exactly 0.000 at K=1. **Peak CUDA is 506.7 MB in all ten
arms, to the decimal** — neither lever buys one byte of device memory (as estimated; a 640 mask slot
is ~205 KB, and the megabytes were always host-side, which is Stage 0's finding).

Three failure mechanisms, each verified by opening the overlay rather than inferred from the number:
mask **leak onto a neighbour** (`building3` @ K5, box bleeds onto the adjacent mosque); **identity
swap onto a same-class distractor** (`car7` @ K1, box jumps to a different silver car, disjoint from
GT, hence exactly 0.000); **mask collapse to empty** (`car13`, `truck3` @ K1, no carried box at all).
None is drift — the pre-registration expected a horizon lever to fail by drifting; it fails by
losing the object's identity outright. Re-find is non-inferior in every arm, the specific loss
D-R16.2 feared; K1's higher rate (10.9%, CI [7.6, 15.4] vs base 2.3% [0.8, 6.6]) sits on a nearly
double-sized denominator, so it enters the lost state more often and recovers from shallow losses.

**Verdict: keep K=7 and M=16.** G2 fired on the letter for K=1 (CI excludes -0.05, re-find
non-inferior, >=5% ms) but was **not adopted** — the -0.05 margin was written against
median-of-median IoU, which is by construction blind to a minority of clips going to zero, and PASS
was not in the gate. Recorded as a mis-specified gate rather than retuned after the fact. Stage 2
not run (vacuous: with nothing adopted, its interaction cell *is* `base`).

Not in `thesis/claims.json` — an engineering measurement, same standing as EXP-1/EXP-2/EXP-6 after
R-44, so no Holm entry in the thesis family. Proof: `proof/horizon_elbow.png`,
`proof/refind_by_arm.png`, `proof/drift_building3.mp4`. Detail:
`experiments/2026-07-26-carry-memory-horizon/README.md`.

### EXP-9 — encoder runtime x capacity: TensorRT fp16 and `hiera-small` (2026-07-26T22:02Z, `jetson`, 15 W + `jetson_clocks`)

Full 2x2, 38 UAV123 clips x 24 steps @ stride 11, `image_size=640`, K=7 M=16 P=32, one bridge per
arm, co-resident with the deployed `llama-server` throughout. Baseline = the deployed config
(`sam2.1-hiera-tiny`, eager bf16), which is EXP-8's `base`. Deltas are arm-minus-base on per-clip
`median_iou` (Wilcoxon + bootstrap CI95, Holm over EXP-9's local 3-comparison family); PASS is
`median_iou >= 0.25`, exact two-sided McNemar, b = clips flipping PASS->FAIL.

**Stage 0 census (co-resident, `llama-server` up).** All three models load and step on 8 GB:

| Model | Params | peak CUDA MB | peak RSS MB | ms/step | Hz | host available MB during |
|---|---|---|---|---|---|---|
| tiny | 38.9 M | 505.3 | 1899.2 | 163.3 | 6.12 | 1407 |
| small | 46 M | 545.4 | 1944.5 | 176.2 | 5.68 | 1353 |
| base_plus | 80.8 M | 758.7 | 2180.4 | 241.8 | **4.14** | 1059 |

**Stage 1, the 2x2:**

| Arm | Model | Encoder | med-of-med IoU | delta [CI95], p (Holm) | held_frac | PASS/38 | b/c, p | re-find | ms/step | Hz | speedup | peak CUDA MB | peak RSS MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `base` | tiny | eager bf16 | 0.811 | — | 0.859 | 32/38 | — | 3/129 (2.3%) | 173.7 | 5.757 | 1.00x | 506.7 | 2056.2 |
| `trt` | tiny | TRT fp16 | 0.815 | 0.0000 [0.0000, +0.0007], p=0.098 (Holm 0.294) | 0.860 | 32/38 | b=0/c=0, undef | 2/128 (1.6%) | **145.4** | **6.879** | **1.195x** | 439.5 | 2331.6 |
| `small` | small | eager bf16 | 0.798 | +0.0003 [-0.0046, +0.0036], p=0.987 (Holm 1) | 0.879 | 34/38 | b=2/c=0, p=0.50 | 16/110 (14.5%) | 185.8 | 5.383 | 0.935x | 547.0 | 2125.0 |
| `small_trt` | small | TRT fp16 | 0.800 | +0.0002 [-0.0040, +0.0036], p=0.961 (Holm 1) | 0.878 | 34/38 | b=2/c=0, p=0.50 | 17/111 (15.3%) | 152.4 | 6.561 | 1.14x | 465.8 | 2315.6 |

`base` reproduces EXP-8 to the third decimal (0.811 / 32 PASS / 506.7 MB / 173.7 vs 173.4 ms), so
the harness is the same instrument and the deltas are the swaps.

**TRT fp16 is adopted (G2 fired: 1.195x >= 1.15, non-inferior, PASS 32=32).** It is the first carry
lever since EXP-1 to buy rate at literally zero measured accuracy cost — the paired median delta is
**0.0000** with a CI95 of [0.0000, +0.0007], and per-clip it is flat on all 38.

**`hiera-small` is not adopted (G3 fails), and `base_plus` is ruled out on rate, not memory.**
All three arms are non-inferior; none wins. `min_discordant` for a significant McNemar at n=38 is
**6** against an observed max of **2**, so the small arms' 2-clip PASS gain (`person21`, `uav3`) is
**underpowered by construction, not a measured tie** (I4). The one real behavioural separation is
re-find: small recovers on 16/110 lost steps vs tiny's 3/129, ~6x, CI95 non-overlapping
(0.092-0.223 vs 0.008-0.066) — that is the mechanism behind both flips. H3 is a YES and wider than
predicted: `base_plus`, which P5.20 wrote off, loads with 1059 MB of board headroom; what excludes
it is 4.14 Hz against E1's >= 5 Hz co-resident gate.

**The H1 magnitude is the finding.** Predicted +52 % (114 ms) from E1's 768-resolution encoder
share; measured **+19.5 %** (145.4 ms), which fires the pre-registered "under +25 % -> the
encoder-share model is wrong" branch. Solving backwards, a 2.31x encoder that saves 28.3 ms means
the encoder is `28.3 / (1 - 1/2.31) = 49.9 ms` = **28.7 % of the 640 step, not 60 %**. That bounds
every future encoder-side lever without running it: a *free* encoder caps the step at 123.8 ms
(+18 % over `trt`), and INT8 over fp16 buys ~7 ms (**+5 % over `trt`**). The carry's time is no
longer in the encoder.

**Two mis-specified gates, both recorded rather than retuned.** G1 (TRT-vs-eager mask parity,
>= 0.99) **FAILED** both engines — 0.8427 tiny, 0.9866 small — because it compares two 24-step
*recursive* carries, which scores trajectory agreement, not engine fidelity. The control the
pre-registration lacked (`diag_g1.py`): eager-vs-eager is **exactly 1.0000** on both models, and
eager-vs-TRT is **1.0000 / 0.9949 at step 1**, before any state exists. Engines faithful, carry
amplifies; the whole tiny failure is one clip (`bike3`). TRT arms ran under a recorded
`--g1-override` with **G2 unrelaxed** — adoption still had to clear non-inferiority against ground
truth, which is what G1 never asked. G3 separately demanded a Wilcoxon **IoU** win while small's
actual signal is **PASS/re-find**; it fails either way at this n, but the aim was wrong.

H4 (descriptive, `inferential: false`): distractor-dense n=26 -> base 21 / trt 21 / small 23 /
small_trt 23 PASS; distractor-free n=12 -> 11 everywhere. Both PASS flips land in the dense stratum,
which is where H4 pre-specified a capacity win would appear — directionally consistent, +2 on n=26
is not evidence, not claimed as any. Stage 2 (INT8) **not run**: G4 gates it on a capacity arm
winning G3, a planned skip rather than dropped scope, and the encoder-share bound above now makes
it a skip on value too.

Not in `thesis/claims.json` — an engineering measurement, same standing as EXP-1/EXP-2/EXP-6/EXP-8
after R-44, so no Holm entry in the thesis family. Proof: `proof/rate-vs-iou.png`,
`proof/per-clip-delta.png`, `proof/memory-census.png`, plus the two PASS-flip overlay pairs
(`uav3`, `person21`). Detail:
`experiments/2026-07-26-encoder-runtime-capacity/README.md`.
