# PROGRAM — Warm-start maintain-and-deliver, powered to significance

**Status:** pre-registered 2026-07-23T23:05Z (Madrid). Frozen. Resumable across sessions.
**Owner doc.** This is the authoritative cross-experiment spine for the six experiments
below. Each experiment has its own self-contained `experiments/2026-07-23-*/README.md`
(the source of truth for running it); this file holds only the shared rules, the frozen
gates in one place, the sequencing, and the shared-infra build (R-35). If a per-experiment
README and this file ever disagree on a **frozen gate**, this file wins and the README is
the bug.

## 0. Why these six

Part V established the thesis contribution — **warm-start maintain-and-deliver** removes the
delivery-lag staleness that capped Part IV (E18-n25 now confirmed: cold acquire lands stale,
ORACLE 23/25 vs COLD 3/25, deflated McNemar p=4.01e-05). The generalization claim
`P5.2a` is the best-powered number in the thesis (p=6.10e-05 deflated). But three things are
still *not* inferential or not measured at all:

1. **The select negative** (SWAP) was called at n=13, p=0.25 — descriptively "select fails"
   but never powered. R-36 either powers it or honestly reports it is not separable at n.
2. **The carry lever** (ROI-crop re-anchor) was adopted on a per-frame IoU argument, never
   as a paired outcome test against plain carry. P5.21 powers it.
3. **Grounding vs carry vs delivery** were only ever measured end-to-end. REG isolates whether
   the residual select failures are a *grounding* asymmetry or live downstream.
4. **Every Part V number was measured on replayed video the system could not influence.**
   P6.2-DELIVERY / P6.2-COUPLING put warm-start in front of a flying copter so the pixels are
   a consequence of its own control output — the C1/C2/C3 claims the Part VI proposal listed as
   unfalsified.

### 0.1 Substrate and priority (author steer, frozen 2026-07-23T23:05Z)

**CARLA `Town10HD_Opt` is the primary substrate; piloting a moving-target follow is the priority
of this round.** Author decision, recorded here so it survives sessions:

- **Why CARLA-primary.** Town10HD gives *reusable, controllable* scenarios — the same seeded traffic
  layout re-run under different **weather, time-of-day, and camera angle** — which is far higher ROI
  than scavenging one-off UAV clips. Reusability is what makes the paired WARM-vs-COLD contrast
  cheap to power and re-run, and it is what makes the *next* round (a weather/ToD/oblique-camera
  robustness sweep) a factor change on the same rig rather than a new data-collection campaign.
- **Piloting is the priority, and it IS in this round.** Following a moving target is the hard half:
  the ~4.85 s cold lock-in latency means the target can be **stale or gone from frame entirely** by
  the time the box lands. That is precisely the **P6.2-DELIVERY** flagship — it is not deferred to a
  next round. WARM delivers at 0.00 s (target still where it was); COLD spends ~4.85 s during which
  the target translates/exits. CARLA's controllability is used to *engineer* scenarios where the
  target reliably crosses or leaves frame during the acquire window (an admission screen, 2.1(a)).
- **What stays on real UAV imagery.** The **real-imagery perception/carry claims (REG, R-36, P5.21)
  stay on UAV123** — the honesty caveat S5 forbids a real-imagery perception claim from a CARLA
  render (P5.17: sim grounds too cleanly). CARLA cannot substitute for these; that is why they are
  kept, secondary and parallel-bankable, "for the static part." If suitable UAV clips are thin, they
  are scoped down (fewer clips, disclosed), never moved to sim.
- **What is given up / deferred to next round.** Weather/ToD/camera-angle are *not* separate powered
  factors this round (each would need its own n and blow the significance budget). They enter this
  round only as **scenario diversity baked into the P6.2 seed bank** (each distinct seed draws a
  condition, so the WARM>COLD contrast is shown to hold across conditions as a covariate, not a
  tested factor). A dedicated **condition-robustness sweep is the explicit starting point for the
  next round.**

The slate is deliberately **maintain-and-deliver, not select**: selecting-among-candidates is a
*measured negative* (multi-candidate select OOM-killed at N=2 on the Orin — R-16; bigger SAM2
dead — P5.20). R-36 tests maintain *against* select as the paired contrast; it does not try to
make select work.

## 1. Shared rules (frozen, apply to all six)

**S1 — n counts DISTINCT SOURCE CLUSTERS, not cells.** A UAV123 `car1` and `car1_s1` are one
cluster; independent CARLA seeds are distinct clusters. One *gating* cell per cluster. Extra
onsets/subsequences inside a cluster may be recorded but collapse under R-29 ICC and never
inflate n. (This is the R-36 lesson — the committed 13-clip SWAP data was already at its n.)

**S2 — reachability is pre-registered, not discovered.** Paired-binary designs use the exact
McNemar test; it reaches alpha=0.05 only at **b+c >= 6 one-directional** (5 -> p=0.0625 fails,
6 -> p=0.03125 passes). Every paired experiment below states its *reachability* up front: the
pilot/committed discordance and the projected b at the target n. If a gate is not reachable by
construction, that is disclosed here before any run (no P5.3/P5.4/P5.5 unreachable-gate repeat).

**S3 — continuous designs cannot be cluster-deflated.** Wilcoxon signed-rank / bootstrap CI
designs (P6.2-COUPLING, the descriptive companions) keep `n_effective == n_rows`; `grounding/stats.py`
`paired_continuous` refuses deflation. That forces **one flight per arm per seed, no reps**, and
**per-item values saved** (the E20 / P5.2b lost-aggregate lesson — never store only the mean).

**S4 — the gate and its miss-label are frozen before the run.** Both outcomes are content. A
"tie" or a "miss" is a pre-registered, publishable measured-negative, not a failed run. The
exact PASS predicate is named (a code symbol, e.g. `leg_pass_p56`), never chosen post-hoc.

**S5 — honesty caveat (all P6.x sim claims inherit it).** A CARLA/sim PASS licenses a
**control-coupling** claim only — "the maintained track survives the closed loop / is deliverable
to the controller." It does **not** license a real-imagery *perception* claim: P5.17 showed the
sim grounds 56/56 clean renders, too easy to separate perception contracts. Real-imagery
perception authority stays with Part V and E18-n25. Every P6.x README repeats this in its own
words and every P6.x claim's caveat field carries it.

**S6 — registration on completion.** A claim enters `thesis/claims.json` when it produces data
(the R-34 pattern), copying the `E18-cold-acquire-vs-warm-oracle-n25` template. Until then the
frozen design lives here + in the README + as a REMEDIATION task. `machine` is `rtx-3090` for
replay, `both` for anything that boots `JetsonBackend` (the frozen on-device 6-id set in the
integrity test is not extended — REG/P6.2 register as `both`). `counts['n']` is the source count
b/c were recorded at; deflation reads it. After any `claims.json` edit run
`.venv-ft/bin/python thesis/run_stats.py` (regenerates `stats-report.md` + the README machine
table + figures — never hand-edit), then hand-bump the README claim-count prose, then `make test`.

**S7 — look at it.** Every sim/flight run dumps >=1 mid-run PNG into `runs/<id>/` and the frame is
opened with the Read tool before any verdict (CLAUDE.md rule; the Phase C sky-camera bug is the
scar). Geometry claims (GT box, mask, track id) need the box drawn on the real frame and viewed.
Mechanical asserts in the scoring script: >99%-one-colour frame = failed render; byte-identical
across time = dead feed.

## 2. The six experiments — frozen gates

| ID | Name | Design / test | Unit | n (frozen) | Reach | Machine | Wave |
|---|---|---|---|---|---|---|---|
| **R-36** | maintain-vs-select | paired-binary, exact McNemar | distinct UAV123 clip | >=25 (target 30) | **marginal** — see 2.1 | rtx-3090 | 1 |
| **P5.21** | ROI-carry vs plain carry | paired-binary, exact McNemar | distinct UAV123 seq | >=27 | pilot-gated | rtx-3090 | 1 |
| **REG** | grounding isolation | paired-binary, exact McNemar (same frame) | distinct UAV123 clip | >=28 (R-36 bank) | ~b=8 (pilot) | both | 1 |
| **P6.2-DELIVERY** | closed-loop WARM vs COLD | paired-binary, exact McNemar | distinct CARLA seed | >=25 | screen-gated | both | 2 |
| **P6.2-COUPLING** | coupled vs decoupled warm carry | paired-continuous, Wilcoxon + boot CI | same CARLA seed | >=25 (n_eff==n) | two-sided | both | 2 |
| *(companions)* | P6.3-LAT, P6.2-CEILING | **descriptive only, no Holm** | on P6.2 matrix | — | n/a | both | 2 |

### 2.1 R-36 — the one honest reachability risk, disclosed up front

The committed SWAP data (P5.18, 13 distinct clips) is **b=3, c=0, n=13 -> exact McNemar p=0.25**.
That is **not reachable** — it is 3 discordant pairs short of the 6 needed. R-36 is therefore not
"re-run at bigger n"; it requires **>=12 NEW distinct SWAP-hard base clips** curated to reproduce
the ~0.23 WSEL>SWAP discordance one-directionally. Projected b~6 at n=25-26 is **marginal**; the
plan **over-provisions to n~30** (projected b~7) and draws the new clips from SWAP-hard families —
late-entry (car18), carry-drift (person10), distractor-confusion (multi-same-class scenes) — with
**one hard SWAP scene per distinct clip** (multiple onsets per clip wash out under S1). Pre-registered
miss branch: if b<6 or the discordance splits two-directional -> **"select fails but is not
separable-from-maintain at this n"** — honest content, cited as the powered ceiling of the select
negative, not a failure to report.

### 2.2 Exact frozen gates (verbatim — READMEs and claims copy these)

- **R-36:** Reject H0(maintain==select) at exact two-sided McNemar p<0.05, deflated to distinct
  clips (R-29 ICC upper95), Part-V Holm family. Arm A = WSEL `leg_pass_p56(leg,'wsel')`
  (selection_correct AND genuine_lock AND coverage>=0.5). Arm B = strengthened SWAP
  `leg_pass_p56(leg,'swap')` (selection=='distractor' AND deliver_iou<0.25 AND
  deliver_iou_distractor>=0.25 AND reason is None). Discordant = pairs where WSEL and SWAP
  outcomes differ. Directional expectation b(WSEL-pass, SWAP-fail) > c.

- **P5.21:** Reject H0(ROI-carry==plain-carry) at exact two-sided McNemar p<0.05, deflated,
  Part-V Holm. Arm A = plain `StreamCarry` (1024-eager, GT frame-0 seed, prune_after=32). Arm B =
  ROI-crop+lanczos re-anchor (`roi_reanchor`, ROI_MARGIN=2.0, ROI_RES=512, LANCZOS4, prune_after=32).
  Per-seq PASS = final-frame track IoU>=0.25 vs GT (carry survived). Win = deployable lever; tie =
  measured-negative closing the last non-capacity carry lever. **Not a construction trap:** a
  held-out pilot must show plain-carry base rate strictly between 0 and 1 (headroom) *before* the
  gate is locked. Drift-reinforcement guard: when the predicted box has clearly drifted, the crop is
  clamped/skipped; drift-reinforcement failures (c>0) are reported as the negative.

- **REG:** Reject H0(grounding symmetric) at exact two-sided McNemar p<0.05, deflated, Part-V Holm.
  Same prompt frame, two phrases. Arm A = target phrase, correct = box IoU>=0.25 vs target GT. Arm B
  = distractor phrase, correct = box IoU>=0.25 vs distractor GT. b = target-correct AND
  distractor-wrong; directional expectation b >> c (grounding resolves the referent but not an
  arbitrary distractor). **Dependent decomposition** of the R-36 population -> declared in the same
  Part-V Holm family, NOT independent confirmation. Pre-registered symmetric branch: b~c ->
  "select failure is not isolable to grounding," redirecting attribution to carry/delivery. The
  distractor-grounding base rate is piloted before reachability is claimed (the P5.18 0.65 is
  end-to-end, confounded — isolated grounding may differ).

- **P6.2-DELIVERY:** Reject H0(WARM==COLD) at exact two-sided McNemar p<0.05, deflated to distinct
  CARLA scenarios, Part-VI Holm (family currently m=0). Arm A = WARM (idle-window VLM seed + SAM2
  carry, deliver-on-command, acquire 0.00s). Arm B = COLD (blocking full-frame VLM acquire at
  t_prompt, real ~4.85s wall-clock, copter holds, stale box). Per-flight FOLLOW PASS =
  **genuine_lock at delivery** (delivered box IoU>=0.25 vs target `actor_box` at the delivery frame)
  **AND post-prompt coverage>=0.5** (PID-driven track IoU>=0.25 vs `actor_box`) **AND no identity
  swap** (driven track never re-assigned to a non-target actor id). Co-primary descriptive: WARM
  absolute lock rate + Wilson interval (answers C1: does maintain survive the loop at all).
  Pre-registered surprise: COLD>=10/25 -> the loop did NOT amplify delivery-lag beyond replay,
  recorded plainly. **Admission screens (GT-only, before the run — generate seeds until 25 pass
  BOTH):** (a) target `actor_box` translates >=1 box-width during the 4.85s acquire window (a
  moving target, or COLD trivially ties); (b) an oracle-GT-driven arm follows it (coverage>=0.5, the
  scenario is followable). The E10 real-follow ceiling ~2.5 m/s squeezes the admissible band to
  ~1.9-2.5 m/s on-screen — engineer TM target speed into it. **Target-exits-frame is a first-class
  COLD failure mode, not just staleness:** the per-flight record logs whether the target `actor_box`
  is still in-frame at the COLD delivery frame, and the scenarios are engineered (via screen (a)) so
  a meaningful fraction of COLD acquires deliver onto a target that has already left frame — the
  concrete cost of lock-in latency this round is built to measure. **Condition diversity:** each of
  the 25 distinct seeds draws one condition (weather / time-of-day / camera-yaw) from a fixed
  rotation, so the WARM>COLD contrast is shown to hold across conditions as a covariate — NOT a
  powered factor this round (that is next round, 0.1).

- **P6.2-COUPLING:** Wilcoxon signed-rank (two-sided) + bootstrap 95% CI on per-scenario mean
  post-prompt follow-error (px). Arm A = COUPLED (warm track drives PID; drone chases its own
  perception). Arm B = DECOUPLED (identical warm perception, but oracle `actor_box` drives PID —
  feedback path cut). `n_effective==n_rows` (S3): one flight per arm per seed, no reps, per-item
  values saved. Two-outcome gate: (i) coupled significantly worse -> closed-loop coupling degrades
  the maintained track, quantified; (ii) no significant difference AND CI within the measured
  schedule-noise band -> C1 closed as "warm carry survives self-induced ego-motion," a **bounded
  null** (never proven equivalence). Reuses the WARM flights from DELIVERY as the coupled arm.

- **Companions (DESCRIPTIVE, no inferential claim, no Holm):** **P6.3-LAT** = end-to-end delivery
  latency distribution WARM vs COLD under real SSH + VLM-tail jitter — report the distribution and
  jitter band, **not** a signed-rank p (the E20 false-precision lesson). **P6.2-CEILING** = WARM vs
  oracle-GT-driven follow-error magnitude + bootstrap 95% CI against the control ceiling — report the
  bounded gap, not a tautological p. Both ride the P6.2 flight matrix; neither is registered as an
  inferential claim.

## 3. Sequencing (frozen — reflects the 0.1 piloting-first steer)

- **Priority: the R-35 flight harness build starts now** (this session) and **P6.2-DELIVERY is the
  flagship deliverable of the round.** Piloting the moving-target follow is the point; the build is
  the critical path.
- **Wave A (the priority, gated only on the R-35 build):** P6.2-DELIVERY (+ the descriptive
  companions), then P6.2-COUPLING (reuses the DELIVERY WARM flights). CARLA Town10HD_Opt.
- **Wave B (real-imagery banks, no rig build; run in parallel / as fill while the rig is built):**
  R-36, P5.21, REG on UAV123. These give cheap real-imagery significance the sim cannot provide
  (S5) and are what the perception/carry claims rest on. Secondary to the flight, not dropped — if
  UAV clips are thin they are scoped down and disclosed. Each reaches alpha by construction (R-36
  marginal — over-provision).
- **Next round (out of scope here, pre-noted):** condition-robustness sweep — weather / time-of-day /
  oblique camera angle as powered factors on the same P6.2 rig.

## 4. R-35 — the closed-loop CARLA harness (shared infra, build spec)

**The problem the build solves.** `runners/carla_render.py` (P6.1) is an **async** flight renderer:
ArduCopter SITL as physics, a position-slaved free RGB camera following a live GUIDED flight — but
**no GT, no tracker, no designated target**. `runners/carla_gt_bank.py` is a **sync** capture bank:
per-frame identity GT for a designated moving target among 80 TM-autopilot vehicles
(`gt_rows`/`actor_box`, `gt.jsonl`) — but **no SITL, no MAVLink, a scripted camera**. They are
disjoint. R-35 merges them into one **async closed-loop harness** wired into `run_phase_c.py`'s
control seams.

**Build = merge, at these exact seams (grounding-verified):**

1. **Image source Gazebo -> CARLA.** `run_phase_c.py` reads frames from `_gz_latest_frame`
   (`_on_image`/`_setup_gz_node` :340, `_grab_gazebo_frame` :395). CARLA's `_on_image`/`_latest['bgr']`
   single-slot buffer (`carla_render.py` :65) is drop-in shaped. Swap the producer, keep the reader.
2. **Pose tick.** Real tick at `run_phase_c.py` :789-801 via `_update_gz_pose` :417 (the proposal's
   :755-767 cite is STALE). CARLA equivalent = `cam.set_transform(ned_to_carla(...))`
   (`carla_render.py` :51). **Fix or bound the R-10 yaw** (drained but never filled, constant 0.0) —
   immaterial while the camera is hardcoded nadir (pitch -90), so bound it explicitly and note it.
3. **Detection source seam.** `LatestDetectionSlot` (:123-159) is source-agnostic
   (`write(capture_ts,bbox,vlm_ms,raw_text)->bool` / `read()->Detection`, monotonic stale-rejection);
   `_control_step_c` (:584) consumes it unchanged. Only the producer THREAD is swapped.
4. **WARM and COLD producers — MUST BE WRITTEN (neither exists; Part V modules are replay-only).**
   - WARM = idle-window VLM seed (`vlm_acquire` / `JetsonBackend`) + `StreamCarry.step(frame)` per
     live frame + deliver-on-command. **`prune_after=32`, not 100** (R-16: PRUNE_AFTER=100 OOM-kills
     n=2+VLM on the Orin; CARRY_HZ=6.15 is RETIRED — real 2.69 Hz solo @1024).
   - COLD = blocking full-frame `vlm_acquire` at t_prompt with real Jetson wall-clock latency
     (~4.85s), copter holds.
   - **The idle window needs a live ring buffer.** `idle_catchup_multi` re-walks PAST frames by index
     — structurally impossible on a live camera (past frames are gone). Replace with a ring buffer of
     the idle window (or true real-time carry). **This is the single biggest new-code item.**
5. **Latency model.** Replace the replay frame-index emulation (`fr=fs+round(lat*fps)`) with real
   `time.monotonic` staleness / grace against wall-clock (C2).
6. **GT + scoring.** Fold `gt_rows`/`actor_box` (`carla_gt_bank.py` :205 / `carla_debug_ui.py` :209)
   + live single-target designation into the async loop, per-frame. Add in-loop scoring
   PASS = `genuine_lock` (delivery IoU>=0.25 vs `actor_box`) AND `coverage>=0.5` AND no identity swap
   (`match_actor` :220, MATCH_OVERLAP=0.30, DRIFT_S=5.0 as the drift-vs-swap discriminator). None of
   this exists in the loop today.
7. **G6 first.** Run the never-executed grounding-over-CARLA check before anything else: does the
   deployed q8_0 resolve ~25x50px cars at 60m AGL? Unknown, and it gates every P6.x number. If it
   fails, drop working altitude into the admissible band (per the DELIVERY admission screen) or
   record G6 as a blocker with the frame that shows why (look-at-it).

**Determinism is lost** (real-time async sim, on purpose — sync would erase the 4.85s delivery lag).
Mitigation = seeded layouts + report a measured schedule-noise band (3 scenarios x2/arm) and require
the effect margin to exceed it (the P5.20 precedent). Do NOT adopt `ardupilot_gazebo` lockstep; do
NOT put the copter under CARLA physics (P6.1 decision, still standing).

**First build increment (this session):** the harness skeleton that runs end-to-end in `--dry-run`
(CARLA image source + pose-slave + target designation + GT projection + in-loop scoring + a stub
detection producer that reads the oracle `actor_box`), dumping a mid-run overlay PNG for look-at-it.
The heavy WARM/COLD producers (SAM2 ring buffer, on-device VLM) land in the next increment.

## 5. Results (TBD)

Filled per experiment in each `experiments/2026-07-23-*/README.md`. This table is the rollup index.

| ID | Verdict | b/c or W | p (deflated) | n_eff | Holm | Date |
|---|---|---|---|---|---|---|
| R-36 | TBD | | | | | |
| P5.21 | TBD | | | | | |
| REG | TBD | | | | | |
| P6.2-DELIVERY | TBD | | | | | |
| P6.2-COUPLING | TBD | | | | | |

## 6. Provenance / do-not-re-derive

- Committed R-36 SWAP data: b=3,c=0,n=13,p=0.25 (P5.18). Marginal; needs 12+ new SWAP-hard clips.
- Dead levers (do not re-propose): multi-candidate select (OOM N=2, R-16), bigger SAM2 (P5.20),
  Swin2SR (R/latency), caption lever (P5.5 M==MC), CLIP crop-scoring (P5.4), speed-sweep
  motion-comp (P5.2b flat rho=-0.06).
- `carla_render.py` and `carla_gt_bank.py` are disjoint (one flies, one has GT) — R-35 merges them.
- `idle_catchup_multi` re-walks past frames — impossible live; ring buffer required.
- Only `StreamCarry.step` is stream-native; everything else in the warm stack is replay-coupled.
- Cross-run CARLA actor ids are NOT stable across `load_world`; designate target by spawn index, not id.
