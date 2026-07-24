# P6.2-DELIVERY — closed-loop WARM maintain-and-deliver vs COLD blocking acquire

**Pre-registered 2026-07-23T23:05Z (Madrid). Frozen before any run. Self-contained handoff.**
Part VI flagship. Shared spine: `experiments/PART6-PROGRAM-warm-start-significance.md` (S1-S7,
sequencing, honesty caveat). Build tracked as **R-35** in `thesis/REMEDIATION.md`. If this README
and the program doc disagree on the frozen gate, the program doc wins.

## Status / next step

- **DONE 2026-07-24T04:10Z.** n=25 oracle burn complete: **WARM 23/25 vs COLD 2/25, McNemar b=21
  c=0, p=9.5e-07** (significant, reachable). Verdict YES [oracle-designation scope]. Results table +
  proof below. Ledgers appended (RESULTS/QUESTIONS/DECISIONS part6), claim registered in
  `thesis/claims.json`. Next in the six-experiment slate: P6.2-COUPLING (decoupled arm, Wilcoxon).
- **R-35 harness BUILT + closed-loop verified** (`runners/run_p62_flight.py`, 2026-07-24). The
  full loop flies: ArduCopter SITL physics -> CARLA pose-slaved nadir camera -> per-tick GT +
  detection producer -> `CascadePID` -> `MAV_CMD ...LOCAL_NED` velocity, at real-time 20 Hz
  (per-vehicle `bounding_box` was a ~17 ms RPC; caching it + one `world.get_snapshot()`/tick took
  the loop 356 ms/tick -> 50 ms/tick). Oracle-stub smoke: coverage 1.0, genuine_lock 100/100,
  overlays opened and viewed (real Town10HD nadir, boxes locked). PID sign verified live (lock held
  120 ticks; wrong sign -> copter flees -> iou->0).
- **G6 gate = conditional PASS** (see below). 60 m is viable; no altitude drop.
- **SAM2-carry device question RESOLVED** (`docs/decisions/part6-flight.md`): matrix carries on the
  3090 rate-capped to the Jetson's 2.69 Hz (E1 parity 1.000 -> device-identical boxes; SSH-carry
  would inject transport latency the drone never pays, contaminating the delivery-timing variable),
  plus one on-Jetson end-to-end showcase flight. Grounding stays on-device unconditionally. Carry
  backend written swappable (`p62_producers.carry_factory`).
- **Increment 3 (WARM/COLD producers) BUILT + closed-loop verified end-to-end** (2026-07-24).
  `runners/p62_producers.py` (`WarmColdProducer`, threaded so a ~4.85 s acquire never blocks the
  20 Hz loop; DI'd `acquire_fn`/`carry_factory`, offline selftest of the WARM-0-lag vs COLD-stale
  timing). Wired behind `--arm warm|cold` in `run_p62_flight`. First REAL WARM flight
  (`runs/p62_warm_smoke`, Jetson q8_0 grounding + 3090 StreamCarry prune_after=32): seeded at
  acquire_s=2.80 s (fits the idle window), **delivered at t=8.25 s ≈ t_prompt=8 s (0-latency, the
  warm-start point)**, carry HELD one vehicle for all 400 ticks (no drift/death), PID centered it
  (overlay box migrated right->center as the copter followed) over a live Town10HD flyover.
  Overlays opened + viewed (`overlay_00200/00399.png`).
- **Target-identity finding (drives the seed design):** that smoke scored coverage=0 because the GT
  target was "nearest world-origin" (Ford Mustang) while `the car in the center` grounded a
  *different* central car — two independent selection criteria pick different vehicles. **Fix: the
  target actor must be pinned per-seed and BOTH arms scored against it; the admission screen defines
  target := the actor the idle-grounding + `match_actor` locks, then verifies followability.** For
  clean paired McNemar the target trajectory must be byte-identical across arms -> scripted target
  motion (arm-independent), distractors stay autopilot.
- Next: the matrix runner (scripted-target seed-gen + admission -> 25 seeds -> paired WARM/COLD).

### PIVOT — oracle target-designation scope (2026-07-24T02:40Z), author-review flag

The G6 gate below establishes the deployed q8_0 grounder is **non-discriminative at this geometry**:
at the as-run 45 m nadir it locks the target only under a hand-picked spatial caption (`the car in
the center`, IoU 0.329) and grabs the wrong same-sized car under any generic phrase; an off-center
probe bank locked 0/8. Part VI's declared novelty is the **closed control loop**, not grounding (that
authority is Part V / E18-n25). So the flagship isolates the closed-loop delivery-timing variable by
**holding grounding constant via oracle target designation**: the operator's designation = the GT box
on the idle-window frame, driving real SAM2 carry (WARM) or a real 4.85 s blocking stub (COLD) + real
PID follow. This is P5's warm-vs-cold, now closed-loop.

**As-run deviations from the frozen pre-registration (recorded, not hidden):**
1. **WARM/COLD seed = oracle GT box, not `vlm_acquire`.** G6's VLM grounding is dropped from the
   gating path; the seam stays (`p62_producers.carry_factory`) for the on-Jetson showcase flight.
   `run_scenario(..., oracle=True)` skips the G6 grounding-lock screen and stamps
   `glog={"oracle": True, "source": "operator-designation (GT box)"}`.
2. **RENDER_ALT 60 -> 45 m** — cars render ~40 px (vs ~14-26 px at 60 m), inside SAM2's reliable
   carry band; the delivery-timing contrast is altitude-independent.
3. **PID gains tuned** kp_lat 0.02 -> 0.05, max_v 3.0 -> 4.0 m/s (the carry *rate* stays pinned to
   the Jetson 2.69 Hz = device faithfulness; only the controller is tuned, per `cascade_pid`'s own
   "calibrate after run 1" note). At 0.02 WARM lagged ~95 px and dropped coverage to 0.278 despite
   SAM2 holding on_tgt the whole flight; 0.05 recovers coverage 1.0.

**Claim-authority narrowing:** a PASS licenses a **closed-loop delivery-timing** claim *conditional
on correct target designation* — "given the operator designates the target, warm maintain-and-deliver
lands a followable lock where cold lands stale" — NOT a grounding+delivery claim. The nadir-grounding
center-bias is a documented limitation (G6). Registered in the claim's caveat field.

**Scoring-window correction (implementation, not a gate change):** `score_p62.follow_pass` clause-2
now scores the post-**prompt** window (`post_prompt` row flag), matching the frozen gate verbatim; it
previously used a post-**delivery** window, which let COLD's blind hover gap escape the coverage
denominator. This makes the code match the frozen README, not the README match the code.

**As-run command:** `.venv-ft/bin/python runners/run_p62_matrix.py --oracle --out runs/p62_delivery`
(defaults: n=25, noise-band 3, reps 2, kp_lat 0.05, max_v 4.0, prune_after 32, alt 45).

### G6 grounding-over-CARLA gate — CONDITIONAL PASS (2026-07-24)

Run on the Jetson (deployed `phase3-terse100eos-1024-q8_0.gguf` via `JetsonBackend`, max_side=1024,
15 W + jetson_clocks) against a clean `target_nadir` frame at the exact P6.2 geometry (Town10HD_Opt,
60 m AGL, 39 vehicles, target = Ford Mustang, GT box ~10x26 px). One Jetson boot, six captions
(`runs/g6_gate/probe_captions.py`):

| caption | IoU | pred | verdict |
|---|---|---|---|
| `the car` | 0.00 | (480,130,499,144) — a **different** small car, resolved | FAIL |
| `the black car` / `the small dark car` | 0.00 | (70,115,96,134) | FAIL |
| `the car in the center` | **0.329** | (320,230,326,254) — on target | **PASS** |
| `the dark car in the middle of the road` | 0.00 | (198,192,218,216) | FAIL |

**Finding:** the miss is **referring-expression ambiguity, not resolution** — the model cleanly
resolves ~14-24 px cars at 60 m (the `the car` prediction is a real, correctly-sized car, just the
wrong one among 39). A **discriminative spatial caption** (`the car in the center`, natural for the
nadir-centered launch target) locks it at IoU 0.329 > 0.25. **Design consequence:** WARM/COLD use a
discriminative referring phrase, and the seed **admission screen must require this exact grounding to
lock the target on the idle-window frame** — guaranteeing both arms *can* acquire, so the contrast is
delivery-timing + closed-loop control, not grounding luck. Proof: `proof/g6_caption_sensitivity.png`
(green=target, red=`the car` grabs wrong car, yellow=`the car in the center` on target).

## Question

RQ-P6.2-DELIVERY: on a copter that flies its own control output, does warm-start
maintain-and-deliver land a usable, followable lock on a moving target where a cold blocking
acquire lands stale or off-frame? This is the closed-loop test of the E18-n25 staleness finding —
the ~4.85 s cold lock-in latency is now paid in real wall-clock while the copter and the target
both move, so the target can be **stale or gone from frame** by the time the box arrives.

## Design (frozen)

- **Paired-binary, exact McNemar** (two-sided p<0.05), deflated to distinct CARLA scenarios (R-29
  ICC upper95), Part-VI Holm family (currently m=0).
- **Arm A = WARM:** idle-window VLM seed (`vlm_acquire` / `JetsonBackend`, deployed q8_0) +
  `StreamCarry.step` SAM2 carry per live frame (**`prune_after=32`**, R-16 OOM constraint) +
  deliver-on-command. Acquire latency at command = 0.00 s (the track already exists).
- **Arm B = COLD:** blocking full-frame `vlm_acquire` at t_prompt with real Jetson wall-clock
  latency (~4.85 s, `JetsonBackend` over SSH, not a stub); copter holds; the returned box is
  whatever the target has become 4.85 s later.
- **Unit = one distinct CARLA seeded scenario** = (traffic seed, designated target identity/spawn
  index, spawn region, drawn condition). Independent generative draws — NOT UAV123 `_s`
  subsequences. **n >= 25 distinct scenarios**, one gating flight per arm per scenario.

### FROZEN GATE (verbatim)

Reject H0(WARM==COLD) at exact two-sided McNemar p<0.05, deflated to distinct scenarios, Part-VI
Holm. Per-flight **FOLLOW PASS** =
1. **genuine_lock at delivery** — delivered box IoU >= 0.25 vs the target `actor_box` at the
   delivery frame; AND
2. **post-prompt coverage >= 0.5** — PID-driven track IoU >= 0.25 vs `actor_box` over the
   post-prompt follow window; AND
3. **no identity swap** — the driven track is never re-assigned to a non-target actor id
   (`match_actor`, MATCH_OVERLAP=0.30, DRIFT_S=5.0).

b = (WARM pass, COLD fail); c = (WARM fail, COLD pass); discordant = b+c. Reaches alpha only at
**b+c >= 6 one-directional**. Directional expectation b >> c.

**Co-primary (descriptive):** WARM absolute lock rate + Wilson 95% interval — answers C1 (does the
maintained track survive the loop at all), independent of the COLD contrast.

**Pre-registered surprise branch:** COLD >= 10/25 -> the closed loop did NOT amplify delivery-lag
beyond the replay result; recorded plainly, not suppressed.

### Admission screens (GT-only, run BEFORE the gate — generate seeds until 25 pass BOTH)

- (a) target `actor_box` translates >= 1 box-width during the 4.85 s acquire window (a genuinely
  moving target, else COLD trivially ties).
- (b) an oracle-GT-driven arm follows it: coverage >= 0.5 (the scenario is physically followable
  under the E10 ~2.5 m/s real-follow ceiling; admissible on-screen band ~1.9-2.5 m/s — engineer
  Traffic-Manager target speed into it).
- **target-exits-frame** is logged as a first-class COLD failure mode (not just staleness): the
  per-flight record stores whether the target is still in-frame at the COLD delivery frame.
  Scenarios are engineered via (a) so a meaningful fraction of COLD deliveries land on a target that
  has already left frame.

### Condition diversity (covariate, not a factor)

Each of the 25 distinct seeds draws one condition (weather / time-of-day / camera-yaw) from a fixed
rotation, so WARM>COLD is shown to hold across conditions. It is **not** a powered factor this round
(a powered weather/ToD/angle sweep is the next round, program-doc §0.1).

### Honesty caveat (inherited, S5)

A CARLA PASS licenses a **control-coupling** claim only — "warm-start delivers a followable lock the
controller can hold, where cold delivers stale." It does NOT license a real-imagery perception
claim; that authority stays with Part V / E18-n25 (sim grounds too cleanly — P5.17). Stated in the
claim's caveat field on registration.

### Determinism

Real-time async sim (async is deliberate — sync would erase the 4.85 s delivery lag under test).
Determinism is therefore lost. Mitigation: seeded layouts + a measured **schedule-noise band** (3
scenarios x 2 flights/arm) that the effect margin must exceed (P5.20 precedent). Do NOT adopt
`ardupilot_gazebo` lockstep; do NOT put the copter under CARLA physics (P6.1 decision).

## Command (intended — runner built under R-35, not yet runnable)

```bash
# G6 gate first: does the deployed q8_0 resolve ~25x50 px cars at 60 m AGL in Town10HD?
.venv-ft/bin/python runners/run_p62_flight.py --gate g6 --town Town10HD_Opt --alt 60

# generate + admission-screen the seed bank until 25 pass both screens
.venv-ft/bin/python runners/run_p62_flight.py --screen-seeds --n 25 --town Town10HD_Opt \
    --out runs/p62_delivery/bank.jsonl

# paired matrix: WARM and COLD on each admitted seed, 1 gating flight/arm/seed
.venv-ft/bin/python runners/run_p62_flight.py --arms warm,cold --bank runs/p62_delivery/bank.jsonl \
    --out runs/p62_delivery

# schedule-noise band: 3 seeds x 2 flights/arm
.venv-ft/bin/python runners/run_p62_flight.py --arms warm,cold --bank runs/p62_delivery/bank.jsonl \
    --noise-band 3 --reps 2 --out runs/p62_delivery_noise

# score + look-at-it overlays + McNemar
.venv-ft/bin/python runners/score_p62.py --runs runs/p62_delivery --overlay --stats
```

## Environment / versions (pin exact at run time)

- **Render + carry:** RTX-3090 host; CARLA 0.9.16 `Town10HD_Opt`; ArduCopter SITL (Copter-4.x,
  `runners/sitl`); SAM2 (hiera, TensorRT fp16 encoder per E1); Python 3.12 `.venv-ft` (`uv.lock`).
- **VLM acquire:** Jetson Orin Nano 8 GB, deployed `phase3-terse100eos-1024-q8_0.gguf` + mmproj at
  `/home/jfdg/grounding/`, via `JetsonBackend` over SSH; **power mode 15 W + jetson_clocks** (no
  MAXN on this board). `max_side=1024`.
- MAVLink via `pymavlink` (no MAVProxy — `sitl_fly_leg.py` scars); `MAV_CMD_SET_MESSAGE_INTERVAL`
  mandatory or the camera pose freezes.
- Exact package pins + CARLA build hash + SITL git rev stamped into `runs/p62_delivery/env.json` at
  run time (do not fabricate here).

## Reuse map (grounding-verified seams)

| Need | Symbol / file:line |
|---|---|
| detection-source seam (source-agnostic) | `run_phase_c.py:123` `LatestDetectionSlot`; consumed by `_control_step_c` :584 |
| CARLA image source (drop-in for Gazebo buffer) | `carla_render.py:65` `_on_image`/`_latest['bgr']` |
| pose slave | `carla_render.py:51` `ned_to_carla`; tick swap at `run_phase_c.py:789` (R-10 yaw bound) |
| per-frame target GT | `carla_gt_bank.py:205` `gt_rows`; `carla_debug_ui.py:209` `actor_box` |
| identity / drift-vs-swap | `carla_debug_ui.py:220` `match_actor` (OVERLAP 0.30, DRIFT_S 5.0) |
| stream-native carry | `experiments/2026-07-01-temporal-acquire-carry/stream_carry.py:65` `StreamCarry`, `.step` :102 (`prune_after=32`) |
| VLM acquire (WARM seed + COLD) | `experiments/2026-07-04-warm-start-acquire/replay_e24.py:93` `vlm_acquire`; `grounding/eval/backends.py:344` `JetsonBackend` |
| coverage / genuine_lock scoring primitive | `experiments/.../select_p513.py` `coverage`; `verdict_p516` |
| stats engine | `grounding/stats.py` `mcnemar` :114, `deflate_to_effective` :69, `Claim` :268 |

**Idle window needs a live ring buffer** — `idle_catchup_multi` (`select_p53.py:89`) re-walks PAST
frames by index, structurally impossible on a live camera. Replaced by a ring buffer of the idle
window in R-35. Biggest new-code item.

## Estimates (up front — mark as estimates)

- WARM lock rate (est): 20-23 / 25 (P5.2a warm generalization was 21/25 on replay; the loop may
  cost a few via ego-motion carry drift). COLD (est): 3-6 / 25 (E18-n25 was COLD 3/25 on replay;
  self-induced ego-motion + target-exit can only worsen it). => est b ~ 16-19, easily reachable.
- **This is the best-powered of the six by projection** — the E18-n25 effect is large and the loop
  is expected to widen it, not narrow it. The reachability risk is R-36's, not this one's.
- Runtime (est): G6 ~15 min; seed screening ~1-2 h (generate-until-25); matrix 50 flights x ~90 s
  flight + ~5-15 s VLM/arm ~ 2-3 h; noise band ~40 min; scoring/overlays ~20 min. ~5-6 h wall.
- Est cost: 3090 + Jetson SSH; no cloud. Within the 1 h target / 10 h hard cap per gating campaign.

## Descriptive companions (on THIS matrix — NOT inferential, no Holm)

Documented here because they ride the same 25 flights; registered as descriptive (non-inferential)
claims, never in the Holm family.

- **P6.3-LAT** — end-to-end delivery-latency distribution WARM vs COLD under real SSH + VLM-tail
  jitter. Report the distribution + jitter band, NOT a signed-rank p (the E20 false-precision
  lesson). WARM ~0.00 s at command; COLD ~4.85 s +/- Jetson tail.
- **P6.2-CEILING** — WARM vs oracle-GT-driven follow-error magnitude + bootstrap 95% CI against the
  control ceiling. Report the bounded gap, not a tautological p.

## Results (2026-07-24T04:10Z, n=25 oracle burn)

Run: `runners/run_p62_matrix.py --oracle --out runs/p62_delivery` (defaults above). 25 distinct
CARLA seeds, each admission-screened (moving target + oracle-followable); first 3 seeds x 2 reps for
the schedule-noise band. Scored by `score_p62.score_delivery` (`runs/p62_delivery/delivery.json`).

| metric | WARM | COLD | note |
|---|---|---|---|
| FOLLOW PASS (/25) | **23** | **2** | genuine_lock AND coverage>=0.5 AND no swap |
| target-in-frame at delivery (/25) | 25 | 25 | COLD exit-frame count = **0**: cold fails by staleness, not frame-exit |
| McNemar b / c | 21 | 0 | b=WARM-pass&COLD-fail; **one-directional, c=0** |
| deflated p, n_eff | p=**9.54e-07** | n_eff=25 | reachable (b+c=21 >> 6); Part-VI Holm m=1 -> survives |
| WARM Wilson 95% lock rate | **[0.750, 0.978]** | (n/a) | co-primary C1: maintained track survives the loop |
| schedule-noise band | 0 flips | 0 flips | seeds 0-2 both reps agree (warm pass, cold fail); effect(b=21) >> noise(0) |

Every COLD flight delivers a box for the last 143 post-prompt frames (after the ~4.85 s blocking
lag); for 23/25 it lands `on_target=0` (stale, on empty road or a distractor). The 2 COLD passes
(seeds 14, 20) are slow/favorable targets — seed 20 had the lowest world-displacement in the bank
(15.2 m), so the 4.85 s-stale box still overlapped. cold_target_exits_frame=0, surprise_branch null.

**WARM residuals (2/25), from the overlays (look-at-it):**
- **seed 8** — coverage 0.091, held 96 frames then the SAM2 carry drifted left onto empty road while
  the police car moved right. Late **carry-drift** (the P5.19/P5.20 residual, now in closed loop).
- **seed 13** — coverage 0.0, genuine_lock 0: the track never established. The overlay also shows an
  anomalous road-spanning GT box; **flagged for author review** whether this is a genuine carry
  failure or a scene/GT-projection artifact. Counted WARM=0 either way (conservative, does not
  inflate WARM).

**Verdict: YES [oracle-designation scope].** On a copter flying its own control output, warm-start
maintain-and-deliver lands a followable lock the PID holds where cold blocking acquire lands stale
(WARM 23/25 vs COLD 2/25, exact McNemar b=21 c=0, p=9.5e-07). The E18-n25 delivery-lag staleness
finding **holds and amplifies in closed loop** — self-induced ego-motion during the ~4.85 s lag does
not rescue cold; it leaves the copter hovering blind, then delivers a stale box off-target. Authority
is a control-coupling claim conditional on correct target designation (S5 caveat); it does NOT extend
to nadir grounding (G6 center-bias limitation).

**Proof deliverables (`proof/`, from `make_proof.py`, reproducible from `runs/p62_delivery/`):**
1. `p62_warm_vs_cold.png` — behavioural contact sheet on seed 00: WARM (row 1) green track hugs the
   yellow GT across frames 100/200/399 (iou 0.58 -> 0.77 -> 0.79); COLD (row 2) hovers blind (NO
   DELIVERY) through frames 100/200 then delivers a red stale box off-target at 399 (iou 0.00).
2. `p62_follow_pass.png` — per-scenario FOLLOW-PASS bars, WARM 23/25 vs COLD 2/25 (numbers proof).
3. `g6_caption_sensitivity.png` — the nadir-grounding center-bias that motivated the oracle scope.
