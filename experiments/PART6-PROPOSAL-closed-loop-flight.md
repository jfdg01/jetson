# PART VI PROPOSAL: closed-loop flight — the drone actually moves (draft 2026-07-20T12:38Z)

Parked proposal, not yet a Part. Origin: Part V's select arc reached a real YES
(P5.19, `experiments/2026-07-20-late-entry-rescue/`) and its follow-up capability
probe closed (P5.20 — carry capacity is a dead lever). The select contract now works
**offline, on replayed real video, with no vehicle in the loop.** Part VI closes that
loop: put the warm-start select in front of a flying copter and measure whether the
system still holds when the pixels are a *consequence* of its own control output.

Promote to a real Part VI (with the three ledger scaffolds) only when work actually
starts. Same rule as `PART5-PROPOSAL-anticipatory-grounding.md`, which this file
mirrors in structure.

---

## 1. Why this is the next step

Two halves of the thesis pipeline have each been validated, **never together**:

| | vehicle in the loop | pixels |
|---|---|---|
| **Part III / IV** (T0–T4, E2–E17) | YES — ArduCopter SITL, real MAVLink, PID follow, ceiling **2.5 m/s** | Gazebo headless nadir camera (Phase C) / analytic frames |
| **Part V** (P5.1–P5.20) | NO — offline replay, no MAVLink, no control | real UAV123 video, plus Gazebo scene banks |

Part V deliberately froze the vehicle to isolate perception, and the isolation
worked — but it also means **every Part V number was measured on a video the system
could not influence.** In flight the coupling is causal: the select fires, the
controller reacts, the airframe moves, and the *next* frames the carry consumes are
different because of that reaction. Nothing in the repo has ever tested that.

Concretely, three claims are currently unfalsified because no experiment could
falsify them:

- **C1 — carry survives self-induced ego-motion.** P5.15 showed the unmaintained
  warm carry survives 24 s of idle (24/25). All 25 of those clips had a camera whose
  motion was *independent* of the tracker. A closed loop adds camera motion that is a
  function of the tracker's own error — including the failure mode where a drifting
  carry steers the camera to keep the *wrong* object centred, which is
  self-reinforcing and cannot appear in replay.
- **C2 — the latency budget survives real wall-clock.** P5.14–P5.20 all emulated
  Jetson VLM latency by mapping measured milliseconds onto a frame index
  (`discover_p516.discover`: `cur = fr = fs + round(lat*fps)`). That is honest for a
  replay and useless in flight: real-time sim means the 4.51 s discovery call and the
  0.37–0.60 s grace delivery are now charged against a copter that keeps moving. The
  first honest end-to-end latency measurement of this system does not exist yet.
- **C3 — the select contract is deliverable to a controller at all.** The P5.x
  select/resolve/discover modules live in `experiments/<campaign>/`, not in
  `runners/`. `runners/run_phase_c.py` still uses single-target VLM grounding
  (`_vlm_grounding_thread` → `LatestDetectionSlot` → ByteTrack → PID). Warm-start,
  multi-candidate arbitration and select-on-command have **never been wired to
  `send_velocity_body`.**

Part VI's claim is therefore about **control coupling**, not perception robustness.
Stating that scope up front matters — see the honesty caveat in §5.

## 2. Do we need the sim? Yes, and it is already built

Yes: the loop is causal, so replay is structurally incapable of testing it. You need
something that renders pixels *in response to* commands.

The good news is that the rig exists and was validated in Part III/IV. `phase_c.sdf`
+ `run_phase_c.py` already close the full chain:

```
Jetson VLM (ssh)  ──►  LatestDetectionSlot  ──►  ByteTrack  ──►  CascadePID
                                                                      │
   Gazebo camera image topic  ◄── set_pose(copter_ned) ◄──┐           ▼
   (gz-transport, headless EGL)                           │  send_velocity_body()
                                                          │           │
                                                 LOCAL_POSITION_NED   ▼
                                                          └──── ArduCopter SITL
```

The architecture: **ArduCopter SITL is the physics; Gazebo is a slaved renderer.**
The copter is not a physics model inside Gazebo — the loop drains
`LOCAL_POSITION_NED` from SITL and pushes the camera model's pose into Gazebo with
`set_pose` each control tick (`runners/run_phase_c.py:755-767`). The camera is forced
nadir (gimbal-stabilised), the target rover pose is scripted.

Everything needed is installed and working:

| Piece | Where | State |
|---|---|---|
| ArduCopter SITL | `~/ardupilot`, `Tools/autotest/sim_vehicle.py` | installed |
| Gazebo Harmonic | `gz sim` 8.14.0 | installed |
| Offboard MAVLink controller | `runners/sitl/offboard.py:50-327` | WORKS (GUIDED, arm, takeoff, 20 Hz velocity) |
| bbox → velocity PID | `runners/sitl/cascade_pid.py:51-107` | WORKS (P-only, self-tested) |
| VLM → track → PID → MAVLink | `runners/run_phase_c.py:553-600, 806` | WORKS |
| Gazebo headless camera | `runners/run_phase_c.py:335-410`, `worlds/phase_c.sdf` | WORKS (EGL ICD pin required) |
| Persistent gz-transport requester | `runners/scenegen.py:94-300` | WORKS (P5.8 fix: 0 failures / 1920 calls) |
| Calibrated multi-car scene | `worlds/select_arena.sdf`, `sitl/models/hatchback_{white,blue,red}` | WORKS (P5.9 16/16, P5.12 12/12) |
| Part V select / warm-start | `experiments/2026-07-20-*/` | **NOT in `runners/`** — the gap |

So Part VI is **not** "build a simulator". It is "port the Part V select contract
into the rig that already flies, and upgrade that rig's scene to the one Part V
proved is fair."

### The one architecture decision to record: do NOT adopt `ardupilot_gazebo`

`~/ardupilot_gazebo/build/libArduPilotPlugin.so` is built on this box (left over from
the parked live-feed work) and `external/SITL_Models` vendors quad models that use it.
The tempting "correct on paper" move is to run a real physics copter inside Gazebo,
with the camera on the airframe and ArduPilot in lockstep over the plugin's FDM
interface.

**Recommendation: don't.** What it buys is aerodynamic coupling and true airframe
attitude on the camera. What it costs is a second flight-dynamics path to validate
(SITL's own model was what Parts III/IV measured — swapping it invalidates the 2.5 m/s
ceiling as a comparison baseline), lockstep timing against a renderer that already has
a documented flake history, and a gimbal question the current rig sidesteps by forcing
nadir. The thesis question is "does the perception contract survive control coupling",
not "is the airframe model right". Pose-slaving already delivers real ego-motion, real
parallax, and real control-induced camera movement — which is the entire mechanism
under test.

Keep the plugin on the shelf. If a later experiment's binding constraint turns out to
be *attitude-induced* (roll/pitch smearing the nadir view during aggressive
acceleration), that is the moment to spend the plugin, and the diagnosis will justify
it. Recording this now so a future cycle does not re-litigate it from scratch.

## 3. Proposed staging (lazy-first, one gate at a time)

### P6.0 — flight-rig capability gate (infra, no research claim)

Precedent: P5.7/P5.8. Before spending a matrix, prove the rig runs.

Bring up `run_phase_c.py` unchanged on current HEAD (it has not been exercised since
Part IV) and clear mechanical gates only:

- SITL arms, takes off, and holds GUIDED for a full trial with no MAVLink stall.
- The Gazebo camera topic sustains a frame rate at or above the carry rate for the
  whole trial (no mid-run gz-transport death — P5.8's persistent requester pattern is
  the reference; **never put ephemeral `gz service` CLI calls in a per-frame loop**).
- **Look at it (CLAUDE.md rule):** dump a mid-run frame, Read it, and assert
  mechanically that it is not >99% one colour and that frames are not byte-identical
  across time.
- Record real wall-clock latency for one Jetson VLM call in-loop — the input C2 needs.

Fails → the cycle's output is the diagnosis, same as P5.7. That is a legitimate
result, not a wasted cycle.

### P6.1 — closed-loop select-and-follow (the actual first experiment)

Wire the P5.19 warm-start machinery (aligned discovery dedup + bounded grace delivery)
into the Phase C control loop, replacing `_vlm_grounding_thread`'s single-target cold
grounding. Fly a multi-candidate scene; issue the operator prompt at `t_p > 0` (the
Part V premise); score the follow.

The design must be a **paired comparison**, because a bare closed-loop pass number
means nothing on its own. The obvious pairing: same scenes, same seeds, arm A = select
output drives the controller, arm B = select output is computed but the controller is
driven by the oracle projection (`runners/sitl/oracle_bbox.py`). B is the no-coupling
control; A−B isolates exactly the causal-coupling cost that replay could not measure.
The pre-registration must fix the gate before the run, per the usual discipline.

Sample size: **n >= 25 gating cells per arm** (standing rule,
`feedback-sample-size-n25`). Real-time sim makes each trial cost wall-clock that
replay did not, so scope must be cut on scene variety, never on n. Estimate the matrix
wall before committing; 1 h target, 10 h hard cap.

### P6.2 — determined by P6.1's binding constraint

Do not pre-plan it. Candidate directions, in the order the current evidence favours:
carry-drift-steers-the-camera (the C1 self-reinforcing mode, and P5.19's residual
failures are already 8/10 carry-drift); real-latency budget violation (C2); follow
ceiling interaction (does the 2.5 m/s ceiling still hold when the box comes from
select rather than from the oracle?).

## 4. Scene: upgrade Phase C's world, reuse Part V's bank

`phase_c.sdf` is a two-model toy — one camera, one scripted rover on the Sonoma mesh.
It was adequate for a follow test with an oracle box; it is **not** adequate for a
select test, which needs multiple plausible candidates and a referring expression that
discriminates between them.

`select_arena.sdf` + `models/hatchback_{white,blue,red}` already is that scene,
calibrated across P5.9 (16/16), P5.12 (12/12 with the recalibrated admission screen)
and P5.17 (n=56, zero render defects). The lazy path is to merge: take
`select_arena.sdf`'s content and give its camera the Phase C pose-slaving treatment,
rather than authoring a new world.

Two carried-forward caveats from the bank work, both to be re-checked once the camera
moves: the half-sunk-distractor kerb-clipping defect (P5.8 fix-before-use; P5.9's
kerb-safe recalibration addressed it, verify it survives a moving viewpoint), and the
P5.12 audit note that crossing peaks converge and the target is never occluded *in
front*.

## 5. Honesty caveat that must be pre-registered, not discovered

**A Gazebo PASS does not license a real-imagery claim.** P5.17 established this
directly: the RefDrone-fine-tuned Qwen2-VL-2B grounded **56/56** clean Gazebo renders,
so the discriminating-contract experiment tied and the sim-select arc was closed as
exhausted. Gazebo pixels are too easy for the grounding stage.

The consequence for Part VI is a scoping rule, and it is a feature, not a problem:
because Gazebo makes grounding nearly free, a closed-loop failure there is **almost
certainly attributable to control coupling** rather than to perception — which is
exactly the variable Part VI is trying to isolate. The rule to write into the
pre-registration: Part VI claims are about the control loop; any perception-robustness
claim still requires real video, and the Part V real-video results remain the
authority on that axis.

## 6. Known risks / gotchas inherited

- **Determinism is lost.** Every Part V sim result rested on frame-stepped
  puppeteering (`scenegen.py` steps the world and dumps a frame per tick, byte-identical
  across sessions — P5.7's 108/108 probe). SITL runs in real time and cannot be stepped
  that way, so Part VI trials are stochastic. Mitigation is statistical, not exact:
  seeded scene layout + n >= 25 + report the schedule-noise band, exactly as P5.20 did
  when it set MIN_SEP = +3 against an observed +-2 noise band.
- **Gazebo/EGL:** headless camera rendering needs
  `__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json`, the
  `gz-sim-sensors-system` plugin with `ogre2`, and thin `<box>` ground rather than
  infinite `<plane>` — all three fail *silently* to black/blank frames. See
  `runners/sitl/GAZEBO_LIVE_FEED.md`.
- **Server teardown:** kill by process group with the `/proc` scan
  (`scenegen.py`'s `killserver`), never by pid file (kills the bash wrapper, orphans a
  live server that keeps answering on the topic) and never `pkill -f "gz sim"` (it
  self-matches its own launching shell).
- **Sandbox reaper** kills commands that mix `gz sim` strings with Python — launch gz
  as a clean `nohup gz sim ... &` in its own command.
- **ArduPilot SITL quirks** already handled in `offboard.py`: TCP accepts a single
  client, heartbeat priming is required before mode changes, `ARMING_CHECK=0`.
- **Two machines, real time.** The VLM lives on the Jetson over `ssh jetson`
  (15 W + jetson_clocks, no MAXN on this board); SITL + Gazebo + SAM2 carry live on the
  3090. Under real-time sim the SSH round-trip is now inside the control latency and
  must be measured, not assumed.

## 7. Status / next action

Draft only. To promote to Part VI:

1. Add a Part VI row to each of the three ledger root indexes and create
   `docs/{results,questions,decisions}/part6-*.md`.
2. Update the CLAUDE.md project-parts list (Part V → complete/paused, Part VI → in progress).
3. Pre-register **P6.0** in `experiments/<date>-p60-flight-rig/README.md` per the
   per-experiment workflow — it is a capability gate, so it needs pre-registered
   mechanical gates and an abort rule, not a research question.

Open question to settle before P6.0 is written: whether Part V is being **closed** or
merely **paused** at P5.20. P5.19's grace precision (2/4 — the wrong ones deliver a
confident box rather than abstaining) is a live, un-attacked weakness, and carry drift
owns 8 of its 10 residual failures with the capacity lever now dead. Either that
becomes P5.21, or it is explicitly carried into Part VI as a known residual. It should
not be silently dropped.
