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
| G2 render | PASS | dominant-colour fraction **0.007–0.026** (gate < 0.99), frames opened with the Read tool |
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
