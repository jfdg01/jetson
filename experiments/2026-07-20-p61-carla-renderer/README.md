# P6.1 — CARLA renderer swap (capability gate)

**Status:** COMPLETE 2026-07-20T19:05Z — **YES**, G1–G5 all pass. G6 **NOT RUN** — non-gating, and
**not a blocker**: the "missing checkpoint" reason first recorded here was wrong and was corrected
2026-07-20T20:10Z (the deployed model is on the Jetson at
`/home/jfdg/grounding/phase3-terse100eos-1024-q8_0.gguf`). See "G6 was not run — but the reason
first recorded was wrong" below. **P6.2 is not blocked.**
**Campaign dir:** `experiments/2026-07-20-p61-carla-renderer/`
**Part:** VI (v6 closed-loop flight). Predecessor: [P6.0 flight-rig gate](../2026-07-20-p60-flight-rig/README.md).

Everything down to `## Estimates` was written **before** the run, per the repo's per-experiment
workflow, and is left as pre-registered — including the estimates, so that estimate-vs-actual
divergence is itself recorded. `## Results` onward was filled in afterwards.

---

## Why this experiment exists

P6.0 established that the rig flies and closes VLM to ByteTrack to PID to MAVLink at 19.93 Hz.
It did **not** establish that there is anything worth looking at. Three findings converge on the
same conclusion — the bottleneck is now the *world*, not the loop:

1. **The Gazebo flight world is empty.** `iris_runway.sdf` contains four entities: `axes`,
   `runway`, `iris_with_gimbal`, `sun`. There are no targets of any kind. Confirmed live on
   2026-07-20 during a manual piloting session: the copter was flown to
   `XYZ [141.237 216.871 100.192]` and the gimbal camera returned nothing but sky at every
   commanded pitch. Cause is not the camera — the only ground geometry in the world is the runway
   model's `<plane><size>1500 100</size>`, so at Y=216 m the aircraft was 167 m past the edge of
   the only surface that exists. **Frames captured and viewed** (`proof/gaz-empty-world-sky.png`).
2. **The vendored asset library cannot fix it.** `runners/sitl/external/SITL_Models/Gazebo/models/`
   holds 34 models: rovers, cones, barrels, a DAF tractor unit, a lawnmower, a boat, and the
   `sonoma_raceway` terrain. No city, no traffic, no vehicle population. The P5.9/P5.12
   `select_arena` bank is rovers on a racetrack, which is what those assets allow.
3. **The existing sim is too easy to discriminate anything.** P5.17 closed sim-select
   discrimination at n=56: DD 56/56 vs RG 55/56, a third straight contract tie, with the P5.13
   defect provably fixed. RG's VLM grounded **56/56 clean Gazebo renders**. The recorded reading
   was that DD's real-video edge is real-imagery fragility. That reading has never been tested
   against a renderer between "clean Gazebo" and "UAV123".

CARLA is the field's answer to exactly this gap: photoreal Unreal Engine towns, a populated
vehicle fleet, an autonomous traffic manager, weather and time-of-day, a Python API, and a
citation record in perception work. It originates from CVC Barcelona (Dosovitskiy, Ros,
Codevilla, López, Koltun).

## What is being changed, and what is not

**Only the renderer.** SITL remains the physics. The renderer remains pose-slaved. This preserves
the P6.0 decision verbatim — the recorded rationale for rejecting `ardupilot_gazebo` lockstep was
that pose-slaving already delivers the ego-motion under test, and that rationale is renderer-
agnostic.

```
  ArduCopter SITL  ──LOCAL_POSITION_NED──▶  control loop  ──set camera transform──▶  CARLA server
   (physics,                                (unchanged)                              (renderer +
    unchanged)      ◀──MAVLink setpoints──                ◀────camera frames────      traffic)
```

Unchanged: `runners/run_phase_c.py` control structure, `runners/sitl/bytetrack.py` (including the
P6.0 round-1b re-find fix), the PID, the MAVLink plumbing, the Part V select modules.
Replaced: the Gazebo `set_pose` service call and the gz-transport image subscription.

## Decisions (pre-registered, with rationale)

- ★ **Renumber Part VI staging: CARLA swap becomes P6.1, closed-loop select-and-follow becomes
  P6.2.** CLAUDE.md previously scoped P6.1 as select-and-follow. That experiment is blocked on
  scene content — there is nothing in the world to select between — so the renderer swap is its
  enabler and must be gated first, on its own, because it can fail on its own. *Given up:* a
  stable pre-announced number for the select-and-follow arm. *Precedent:* P5.1 was pre-registered
  as E24 and renumbered at merge; renumbering an experiment that has not run is cheap.
- **Keep pose-slaving; do not spawn the copter as a CARLA actor and do not use CARLA physics.**
  Same rationale as P6.0. CARLA's vehicle physics is ground-vehicle physics and would not model a
  multirotor; adopting it would also reintroduce the determinism and coupling costs already
  rejected. *Given up:* rotor downwash and airframe dynamics visible in the render — not
  load-bearing for a perception-in-the-loop question.
- **Use the packaged release, not a source build.** 8.35 GB download versus an Unreal Engine
  toolchain build measured in hours and tens of GB. *Given up:* the ability to author custom maps
  and import new assets, which needs the source build. If P6.2 needs a bespoke map this decision
  gets revisited and recorded then.
- **Install the client into `.venv-ft`, no new venv.** `carla==0.9.16` resolves with **zero**
  transitive dependencies (verified by `uv pip install --dry-run`), so it cannot perturb the
  pinned torch/transformers/opencv set that every prior Part II–V number was measured against.
  *Given up:* nothing identified.
- **Gate first, science second.** This campaign answers "does the swap work", not "is CARLA
  harder to ground". The grounding-difficulty question is real and interesting (see G6, recorded
  as **non-gating** below) but it is a research question needing n>=25 per the sample-size rule,
  and it belongs in its own pre-registered arm.
- **Verify every camera-axis sign against a viewed frame before recording any number.** Direct
  consequence of the Phase C sky-camera defect, where a `+pi/2` pitch aimed the camera up for a
  month and produced a *confirmed* negative result on a blank gray image. CARLA uses a
  left-handed Unreal frame while ArduPilot reports NED; the mapping below is a **hypothesis until
  a frame is opened**, not a fact.

## Setup

| Item | Value |
|---|---|
| Date | 2026-07-20 |
| Host | 3090 workstation (not the Jetson — see restriction below) |
| GPU | NVIDIA GeForce RTX 3090, 24576 MiB, driver 595.71.05 |
| OS | Linux 7.0.0-28-generic |
| CARLA server | 0.9.16, packaged Linux release, published 2025-09-16 |
| CARLA package | `CARLA_0.9.16.tar.gz`, 8346095504 bytes, from `https://tiny.carla.org/carla-0-9-16-linux` (308 to `carla-releases.b-cdn.net`) |
| CARLA install path | `~/carla/CARLA_0.9.16/` (outside the repo, gitignored by absence) |
| CARLA client | `carla==0.9.16` (cp312 wheel) in `.venv-ft`, added to `requirements-ft.txt` |
| Python | 3.12.10 (`.venv-ft`) |
| ArduPilot | 4.6.3 `92b0cd788e`, SITL build `build/sitl/bin/arducopter` |
| Power mode | n/a — no Jetson in this campaign |

**Restriction: no Jetson.** Same as P6.0. The CARLA server needs a desktop GPU and cannot run on
the Orin Nano; the perception model is exercised on the 3090. Any latency figure from this
campaign is therefore a **3090 figure and is not a deployment number**. Jetson-side latency
claims continue to come from the Part II–V on-device runs.

**Version note.** `carla` on PyPI ships cp312 wheels only from 0.9.16 onward (0.9.15 stops at
cp310). Selecting 0.9.16 is what avoids standing up a second Python environment. 0.10.0 exists and
is *newer* by tag but predates 0.9.16 by release date (2024-12-19 vs 2025-09-16) and moved to
UE5 with a reduced map and feature set; 0.9.16 is the maintained line.

## Commands

```bash
# server (terminal 1) -- off-screen rendering, fixed step to match the control loop
~/carla/CARLA_0.9.16/CarlaUE4.sh -RenderOffScreen -quality-level=Epic

# gate runner (terminal 2)   [to be written: runners/carla_render.py]
.venv-ft/bin/python runners/carla_render.py --gate --out experiments/2026-07-20-p61-carla-renderer/runs/
```

Actual as-run commands:

```bash
# server
cd ~/carla/CARLA_0.9.16 && ./CarlaUE4.sh -RenderOffScreen -quality-level=Epic -carla-rpc-port=2000

# SITL -- physics only, no MAVProxy, no Gazebo
cd ~/ardupilot && PATH="$HOME/.venv-mavproxy/bin:$PATH" \
  ./Tools/autotest/sim_vehicle.py -v ArduCopter --no-rebuild --no-mavproxy -l 40.4168,-3.7038,0,0

# G1/G2/G4/G5, scripted sweep
.venv-ft/bin/python runners/carla_render.py --gate --vehicles 30 --seconds 20 \
  --out experiments/2026-07-20-p61-carla-renderer/runs/g1-scripted
# target-size sizing sweep
.venv-ft/bin/python runners/carla_render.py --gate --vehicles 40 --seconds 8 --alt 60 \
  --out experiments/2026-07-20-p61-carla-renderer/runs/alt60
# G3, camera slaved to a live SITL flight (this also flies the copter)
.venv-ft/bin/python runners/carla_render.py --gate --vehicles 40 --seconds 30 --alt 60 --mavlink \
  --out experiments/2026-07-20-p61-carla-renderer/runs/g3-mavlink
# figure
.venv-ft/bin/python experiments/2026-07-20-p61-carla-renderer/make_proof.py
```

## Coordinate mapping — VERIFIED against viewed frames

ArduPilot `LOCAL_POSITION_NED` is right-handed North-East-Down in metres. CARLA uses the Unreal
frame: left-handed, X forward/North, Y right/East, Z up, `carla.Location` in metres,
`carla.Rotation` in **degrees**.

| From (NED) | To (CARLA) | Note |
|---|---|---|
| `x` (North) | `Location.x` | direct |
| `y` (East) | `Location.y` | direct — both are East-positive |
| `z` (Down) | `Location.z = -z` | sign flip, CARLA Z is up |
| yaw (rad, CW from North) | `Rotation.yaw = degrees(yaw)` | both CW in a left-handed frame |
| camera nadir | `Rotation.pitch = -90` | **the sign most likely to be wrong** |

**Result: the hypothesis was correct on every row, including the pitch sign.** `pitch=-90` renders
ground. Confirmed by opening `runs/g1-scripted/frame_00200.png` with the Read tool before any
number below was recorded. Given the Phase C precedent — a `+pi/2` pitch aimed the Gazebo camera at
the sky for a month and produced a *confirmed* negative result on a blank image — being right by
inspection rather than by assumption is the point, not a formality.

## Gates

Mechanical thresholds, n=1 per configuration. This is a capability gate, not a research arm, so
the n>=25 sample-size rule is deliberately not applied (same carve-out as P6.0).

| Gate | Criterion |
|---|---|
| **G1** server | CARLA server starts, client connects, a town map loads, world tick advances |
| **G2** render | a mid-run frame is captured **and opened with the Read tool**; dominant-colour fraction < 0.99 (not a blank render); the frame shows recognisable road/buildings |
| **G3** pose slaving | camera transform tracks SITL: commanded flight over >= 50 m produces a frame sequence whose content changes monotonically with position; the nadir sign is confirmed by a viewed frame showing **ground, not sky** |
| **G4** traffic | >= 20 autonomous vehicles spawned and moving; two frames >= 5 s apart are not byte-identical (dead-feed assert) |
| **G5** rate | render + transfer sustains >= 20 Hz at the control-loop resolution, matching the P6.0 loop rate; ticks under 15 Hz reported |
| **G6** grounding (**NON-GATING**) | the deployed Qwen2-VL-2B is run on CARLA frames and the outcome recorded. Reported as an observation only — a real verdict needs n>=25 and its own pre-registration |

**Abort rule.** If G1 or G2 fails, stop and record a NO rather than tuning — a renderer that will
not render is not a configuration problem. If G5 fails but G1–G4 pass, record the achieved rate,
do not lower the control rate to make it pass, and carry the shortfall as a residual into P6.2.

## Estimates (up-front, to be compared against actual)

| Quantity | Estimate | Basis |
|---|---|---|
| Download | ~15 min | 8.35 GB, actual: **~5 min** (already complete) |
| Extract + first server start | ~20 min | ~20 GB unpack, cold Unreal shader compile |
| Runner implementation | ~150 lines | direct port of the `set_pose` path in `run_phase_c.py` |
| Render rate at 640x480 | 30–60 Hz | 3090 at Epic quality, offscreen; comfortably above the 20 Hz gate |
| Total wall time | 2–4 h | including the sign-verification loop |
| **G6 prediction** | Qwen2-VL-2B grounds CARLA frames **worse than the 56/56 it managed on Gazebo, but better than on UAV123** | if CARLA lands at the Gazebo ceiling, "sim is too easy" is a scene-content claim not a fidelity claim, and that is the more interesting outcome |

Recording the G6 prediction up front is deliberate: the Phase C post-mortem found that a broken
render was indistinguishable from a *confirmed* pre-registered negative. A prediction that can be
embarrassed is the point.

## Results

Run 2026-07-20T18:20Z–19:05Z. Raw: `runs/g1-scripted/`, `runs/alt60/`, `runs/alt30/`,
`runs/g3-mavlink/` (each with `results.json` and the captured frames).

| Gate | Verdict | Measured | Notes |
|---|---|---|---|
| G1 server | **PASS** | server 0.9.16 == client 0.9.16; `Town10HD_Opt` loaded; 155 spawn points, 41 vehicle blueprints; 599 ticks advanced | 13 maps available |
| G2 render | **PASS** | dominant-colour fraction **0.007–0.026** across four runs (gate < 0.99) | frames opened with the Read tool; photoreal town, buildings, road markings, trees, pedestrians |
| G3 pose slaving | **PASS** | copter flew **0 → 84.4 m north** under its own GUIDED control at a held 60.0 m; frame content at tick 150 / 300 / 599 is distinct and consistent with the reported position | nadir sign confirmed by viewed frame |
| G4 traffic | **PASS** | **40/40** vehicles spawned with autopilot; first and last frames not byte-identical; traffic visibly moved between viewed frames | |
| G5 rate | **PASS** | **48.1 Hz** mean (gate >= 20 Hz); 5/599 ticks under 15 Hz, all in the first ~5 s | the sub-15 Hz ticks are cold shader compilation, not steady-state |
| G6 grounding (non-gating) | **NOT RUN** | — | non-gating; the "checkpoint not on this machine" reason first recorded here was **wrong**, corrected below |

**Overall: YES.** The renderer swap works. SITL remains the physics, the renderer remains
pose-slaved, the control stack is untouched, and the world now contains a photoreal town with 40
autonomously-driven vehicles rendering at more than twice the P6.0 control rate.

### G6 was not run — but the reason first recorded was wrong

**As first written (2026-07-20T19:05Z):** G6 was pre-registered as "run **the deployed
Qwen2-VL-2B** on CARLA frames". The checkpoint `runners/runs/v2/phase3-terse100eos-1024` does not
exist on this machine — `runners/runs/**` is gitignored (`.gitignore:25`, manifests only), there
are no `.safetensors` anywhere under `~`, and the HF cache holds only SAM2 and CLIP. Substituting
base `Qwen/Qwen2-VL-2B-Instruct` (~15% IoU@0.25 per the Phase-0c note in `contract.py`, against
~63% for the deployed terse checkpoint) would answer a different question, so G6 was recorded NOT
RUN and called a hard blocker for P6.2.

**Correction (2026-07-20T20:10Z): the checkpoint was never missing, and P6.2 is not blocked.**
Prompted to check the Jetson, it is there, in the deployment format, at exactly the paths the
repo's own constants point at:

```
/home/jfdg/grounding/phase3-terse100eos-1024-q8_0.gguf         1646571200 B, 2026-06-26
/home/jfdg/grounding/mmproj-phase3-terse100eos-1024-f16.gguf   1334666400 B, 2026-06-26
```

matching `_REMOTE_MODELS['q8_0']` / `_REMOTE_MMPROJ` / `_DEFAULT_REMOTE_DIR = /home/jfdg/grounding`
(`grounding/deploy/video.py:48-52`, `grounding/deploy/serve.py:27`), with `llama-server` built at
`/home/jfdg/llama.cpp/build/bin/`.

**And P5.17 grounded through those same two files.** `select_p517.py:397-403` constructs a
`JetsonBackend` over `ssh jetson`, not an `HFBackend` — so the 56/56 that G6 was supposed to be
comparable against was itself measured on the Jetson GGUF. Running G6 that way is not a
substitution, it is the *matching* configuration.

**What is actually missing** is only the merged HF/safetensors *training-format* directory, which
`HFBackend` would load and which nothing in the Part V select arc uses. Losing it costs the ability
to resume LoRA training or re-export, not the ability to ground.

**The error was searching for the wrong artifact.** `find -name "*.safetensors"` on both machines
returns nothing and reads as "the model is gone", when the deployed artifact is a `.gguf` and the
question was always about the deployed model. The failure mode is worth recording: a search whose
*negative* result is confidently wrong because the search term encoded an assumption about format
that the deployment had already moved past. Same family as the vacuous metrics above — a check that
cannot see the thing it is checking for.

G6 remains **NOT RUN** — this correction landed after the campaign closed, and G6 is a non-gating
observation that the pre-registration says needs its own arm at n>=25. It is now unblocked work,
not a blocker.

### The slaving-error metric is vacuous — do not cite it

`results.json` reports `slave_err_mean_m = 0.000` and `slave_err_max_m = 0.000`. This looks like a
perfect result and means nothing. The camera is a spawned, unattached `sensor.camera.rgb` — a
kinematic actor with no dynamics — so `cam.get_transform()` returns exactly what `set_transform()`
was just handed, with `world.tick()` between them so there is not even a client/server race to
measure. The metric compares a number against itself.

This is the same failure shape as P6.0's "0 track losses" — a counter that reads healthy because
the thing it measures cannot vary. It is kept in `results.json` and named here specifically so a
later cycle does not mistake it for evidence. **What actually evidences G3** is that the *pose
source* moved 84.4 m under closed-loop autopilot control and the *rendered content* changed
accordingly across three frames that were opened and looked at.

#### R-10 audit (2026-07-21): three corrections and a replacement

**The published `0.000` is not in the file.** `results.json` holds
`slave_err_mean_m = 1.815e-06` and `slave_err_max_m = 8.53e-06`; `0.000` is the `:.3f` print
format. Anyone grepping the artifact for the published number will not find it. The residual is
float32 round-trip noise — it does not correlate with per-tick speed (r = +0.02) and is five
orders of magnitude below the 0.143 m the camera moves per tick.

**The metric ignores three of six DOF, and one of them was broken.** `err` reads `.location`
only; rotation is never compared. `pose_track[:, 3]` (yaw) holds exactly **one distinct value,
0.0, across all 600 ticks** — `MavlinkPose` fills yaw from a non-blocking `ATTITUDE` poll that
never delivered, the same silent-stream failure this campaign already documents for
`LOCAL_POSITION_NED`. It went unnoticed *because* `slave_err` cannot see rotation. The renderer
is **position-slaved**, not pose-slaved. The consequence is bounded here only because the camera
is fixed nadir; it would not be for an oblique camera.

**A non-vacuous replacement, from the artifact already on disk.** Real slaving error lives
upstream: `MavlinkPose.__call__` drains non-blocking and returns `self.last` when no new sample
arrived, so a repeated `pose_track` row is a tick that rendered the camera where the aircraft
*was*. `pose_staleness.py` (this dir, no re-run needed) computes:

| quantity | value |
|---|---|
| render ticks reusing a stale pose | **362 / 599 = 60.4%** |
| fresh `LOCAL_POSITION_NED` samples | 237 (19.0 Hz) |
| inter-sample gap, mean / max | 0.053 s / **0.547 s** |
| aircraft speed, median | 7.21 m/s (commanded 8.0) |
| implied camera lag, typical / worst | 0.38 m / **3.9 m** |

Nonzero, falsifiable, ~6 orders of magnitude larger than the metric that was published, and it
degrades in the right direction when the pose stream stalls. It is a **lower bound**:
`pose_track` stores no `time_boot_ms`, so SITL-side sensor-to-wire latency is not on disk. It is
computable only for `g3-mavlink` — the other three runs predate the field and used scripted poses.

### What 48.1 Hz measures, and what the 2.4x was

`mean_hz` is `1/mean(diff(wall stamps))` around `set_transform` + `world.tick()` +
`get_transform()` in `carla_render.py`. **No perception is inside that window** — no VLM, no SAM2,
no ByteTrack, no PID, no JPEG, no transport; grepping the renderer for any of them returns only
comments and variable names. It is the CARLA server's render+step throughput as seen by a bare
client. It is not a system rate, and G6 (grounding) was NOT RUN, so no perception ran at all.

**The run was synchronous mode, and the clock skewed.** 600 ticks x `fixed_delta_seconds` 0.05 =
30 s of simulated time delivered in 12.46 s of wall time: the sim ran **2.41x faster than real
time** while SITL, the pose source, ran on the wall clock. The 40 autonomous vehicles drove for
30 s while the copter flew for 12.5 s, so traffic in the proof frames moves ~2.4x too fast
relative to the aircraft.

**Therefore the headroom claim is withdrawn.** `48.08 / 19.93 = 2.41` and `30 s / 12.46 s = 2.41`
are the same number, because `FIXED_DT = 0.05` equals the control period. "2.4x the P6.0 control
rate" restates the clock skew; it never measured spare capacity.

**And the figure is not reproducible from HEAD.** `87a5b48` ("run the renderer async instead of
driving it with `world.tick()`") rewrote the loop to async with a wall-clock pacer and
`sensor_tick = 0.05`, landing 3.5 h after these results were committed. Re-running the documented
command today gives ~20 Hz by construction. The as-run code is `d925c74:runners/carla_render.py`.
The decision to go async is recorded in `docs/decisions/part6-flight.md` and was taken for the
right reason — it just also invalidates this number's reproducibility, which was not noted at the
time.

### Target size versus altitude (sizing observation, non-gating)

Frames at 100 m, 60 m and 30 m were captured and viewed to size targets for P6.2, since a select
arm needs targets a grounding model can resolve:

| Altitude | Frame coverage (90 deg FOV) | Car size | Read |
|---|---|---|---|
| 100 m | ~200 m | ~10 px — too small to ground reliably | `runs/g1-scripted/frame_00200.png` |
| 60 m | ~120 m | ~25x50 px, clearly resolved, several cars per frame | `runs/alt60/frame_00080.png` |
| 30 m | ~60 m | large, but the frame is mostly building facade | `runs/alt30/frame_00080.png` |

**60 m is the working altitude for P6.2.** Not a gate, but it is a pre-registration input that
would otherwise have been guessed.

### Estimate vs actual

| Quantity | Estimate | Actual | Divergence |
|---|---|---|---|
| Download | ~15 min | ~5 min | faster |
| Extract + first server start | ~20 min | ~20 min | on target |
| Runner implementation | ~150 lines | 229 lines (`carla_render.py`) + 158 (`sitl_fly_leg.py`) | **2.6x over.** The overrun is entirely `sitl_fly_leg.py`, which was not foreseen at all — see below |
| Render rate at 640x480 | 30–60 Hz | **48.1 Hz** | mid-range, as predicted |
| Total wall time | 2–4 h | ~5 h | over, all of it in the MAVLink bring-up |
| G6 prediction | worse than Gazebo's 56/56, better than UAV123 | **untested** | not run; correction landed after close (checkpoint is NOT absent) |

The runtime estimate missed because the pre-registration assumed the *renderer* was the risk. It
was not — CARLA worked on essentially the first try. The risk was the thing not written down:
driving SITL without MAVProxy.

### What did not work

The renderer swap was uneventful. Everything below is the SITL side, and every item was a silent
or misleading failure rather than a loud one — which is why they cost the afternoon.

1. **`--out=udp:...` is a MAVProxy flag, not a SITL flag.** Launched with `--no-mavproxy`, so
   nothing was ever listening on 14551 and the renderer blocked forever in `wait_heartbeat()` with
   no error. Fixed by sharing one TCP link (see 6).
2. **`--serial1=udpclient:127.0.0.1:14551` does not stream either.** Tried as a second endpoint;
   no heartbeat ever arrived. Abandoned.
3. **ArduPilot streams almost nothing to a GCS that never asks.** `LOCAL_POSITION_NED` never
   arrived, so the pose consumer read its *initial* value forever. Had this not been caught, G3
   would have rendered a frozen camera over a moving world and the run would have looked
   plausible. Fixed with `MAV_CMD_SET_MESSAGE_INTERVAL` for `LOCAL_POSITION_NED` and `ATTITUDE`
   in `connect()`. **This is the P6.1 analogue of the Phase C sky camera** — a config omission
   that produces well-formed, entirely wrong output at exit 0.
4. **`COMMAND_ACK` must be matched to its own command id.** Taking the first ACK off the wire read
   the *arm* ack as the *takeoff* reply, reported a spurious rejection, then retried takeoff while
   the copter was already climbing — which really does fail, so the bogus diagnosis confirmed
   itself. Fixed with `wait_ack(m, command)`.
5. **The arm ACK precedes the armed state.** `COMMAND_ACK: ACCEPTED` arrives seconds before the
   `HEARTBEAT` armed bit sets; a takeoff sent in that window returns `MAV_RESULT_FAILED`. Trust
   the heartbeat, not the ack.
6. **GUIDED must be set before arming and never re-asserted after.** Setting the mode on an armed,
   still-landed copter *disarms it*. An earlier "fix" that re-asserted GUIDED inside the takeoff
   retry loop made things strictly worse, and the whole sequence must finish inside `DISARM_DELAY`
   (10 s) or the copter disarms itself mid-retry. This step order is load-bearing and is commented
   as such in `arm_and_takeoff()`.
7. **A copter left flying by a previous run rejects `NAV_TAKEOFF`** (it is not `land_complete`),
   surfacing as the same opaque `MAV_RESULT_FAILED`. `arm_and_takeoff()` now detects altitude
   > 5 m and reuses the airborne vehicle instead.
8. **`pkill -f <pattern>` kills its own wrapper shell.** The pattern matched the `bash -c` command
   line containing it, so every SITL restart returned exit 144 and silently did not restart —
   which made several unrelated diagnoses look reproducible when they were just stale state. Use
   `pkill -x arducopter`.

## Proof deliverables

Three, under `proof/`, committed and captioned:

1. `gaz-empty-world-sky.png` and `gaz-empty-world-gimbal-down.png` — **already captured**, both
   viewed. The Gazebo gimbal camera during the 2026-07-20 manual flight, showing sky and the
   copter's own airframe and nothing else. The second was taken after publishing
   `data: -1.57` to `/gimbal/cmd_pitch` (nadir) and is *still* sky — which is the point: the
   aim was fine, there was simply no ground below. The pose reading
   `XYZ [141.237 216.871 100.192] RPY [0.0027 -0.0001 1.2688]` was queried via
   `gz model -m iris_with_gimbal -p` seconds later in the same hover, **not** simultaneously with
   the frame; treat it as the position to within a few metres of drift, not a synchronised label.
   This is the motivating evidence: the flight world has no content past the runway edge.
2. `carla-nadir-frame.png` — the **after** to deliverable 1's before, and the single frame that
   closes G2 and G3. Same nadir viewpoint, same pose-slaved architecture, same `pitch=-90` that
   returned sky in Gazebo. Tick 599 of `runs/g3-mavlink/` at 60.0 m, with the camera following a
   live ArduCopter GUIDED flight: a photoreal intersection with moving traffic (red bus, several
   cars, pedestrians at the crossing), road markings, street trees and building facades. This is
   the frame that was opened before any number in the results table was written.
3. `pose-slaving-track.png` — figure from `make_proof.py`, reproducible from
   `runs/g3-mavlink/results.json` alone. Top: the SITL-reported north position climbing 0 → 84.4 m
   while altitude holds flat at 60.0 m, with the three viewed frames marked at their ticks — the
   pose source really is live and moving. Bottom: per-tick wall-clock rate against the 20 Hz gate,
   mean 48.1 Hz, with the only sub-15 Hz ticks in the first ~5 s of shader compilation.
   Deliberately **not** plotted: commanded-versus-realised camera position, which is identically
   zero by construction and would be a fabricated result (see the vacuous-metric note above).

## Residuals carried in from P6.0

Still open, and still blocking the select-and-follow arm (now P6.2):

- the live-VLM path targets `_probe.MODELS[1]` (SmolVLM-500M), not the deployed Qwen2-VL-2B
- `_append_results_md` hardcodes a stale `SmolVLM-500M Q8_0` / `15W locked` row
- `bytetrack.py` Kalman noise is tuned for ~25 Hz and is likely too tight at 1 Hz detection
- 7 track IDs remained after the round-1b fix once the copter fell behind at t~31 s — a genuine
  1 Hz association limit, not the same defect

## Residuals added by P6.1

- **G6 untested.** ~~The deployed grounding checkpoint is missing~~ — **corrected
  2026-07-20T20:10Z, see above:** the deployed Q8_0 GGUF is on the Jetson at
  `/home/jfdg/grounding/`, P5.17 grounded through it via `JetsonBackend`, and P6.2 is **not**
  blocked. G6 stays NOT RUN because the correction landed after the campaign closed and it is a
  non-gating observation the pre-registration assigns to its own n>=25 arm.
- **The merged HF/safetensors training-format checkpoint is genuinely gone** (no `.safetensors` on
  either machine). Costs LoRA resumption and re-export, not grounding. Worth a deliberate decision:
  accept it, or re-export from the GGUF path / retrain.
- The `slave_err_*` fields in `results.json` are vacuous by construction. Left in place, flagged
  here; do not cite them. R-10 replaced them with pose-sample staleness (`pose_staleness.py`) and
  found that yaw was never slaved at all.
- CARLA has weather and time-of-day and this campaign used neither — every frame is the default
  clear midday. A fidelity claim that only holds at noon is not much of a claim.
- The camera is fixed nadir. Real UAV footage (and the Part V bank) is oblique. Not exercised.

## Software installed for this campaign

Per the repo rule that every install is documented with what, version and why:

| What | Version | Where | Why |
|---|---|---|---|
| CARLA server | 0.9.16 packaged Linux release | `~/carla/CARLA_0.9.16/` (outside the repo) | the renderer under test |
| `carla` client | 0.9.16 (cp312 wheel, **zero** transitive deps) | `.venv-ft`, pinned in `requirements-ft.txt` | Python API to the server |
| `matplotlib` | 3.11.0 | `.venv-ft`, now explicit in `requirements-ft.txt` | `make_proof.py` figure (it was already a transitive pin in the lock) |
| MAVProxy | 1.8.74 | `~/.venv-mavproxy` | manual piloting; also the only PATH that lets `sim_vehicle.py` resolve its build deps |
| `empy` / `pexpect` / `future` | 3.3.4 / 4.9.0 / 1.0.0 | `~/.venv-mavproxy` | `sim_vehicle.py` waf build and process control |
| `matplotlib` / `opencv-python` / `lxml` / `Pillow` / `pyyaml` | 3.11.1 / 5.0.0.93 / — / 12.3.0 / 6.0.3 | `~/.venv-mavproxy` | MAVProxy `console` and `map` modules |

`~/.venv-mavproxy` is a **separate** environment created from `/usr/bin/python3`
(3.12.3, `--system-site-packages`) rather than `.venv-ft`, because MAVProxy's GUI modules need
wxPython 4.2.1, which is installed only for the system interpreter. Note `python3` on PATH is a
pyenv shim (3.12.10), which is also why `sim_vehicle.py`'s waf build resolved `python` to whatever
venv was first on PATH and demanded `empy` be installed *there*.

## Status / next step

**COMPLETE — YES.** G1–G5 pass with viewed evidence; G6 not run — non-gating, and left not-run
because the correction landed after the campaign closed, **not** because the checkpoint is absent
(it is not absent; that reason was wrong).

**Next: P6.2 closed-loop select-and-follow. Not blocked** (correction 2026-07-20T20:10Z — the
deployed model is on the Jetson). P6.2 inherits from here: 60 m working altitude, `Town10HD_Opt`,
40 autonomous vehicles, seed 20260720, `runners/sitl_fly_leg.py` for the arm/takeoff sequence, and
`JetsonBackend` against `/home/jfdg/grounding/phase3-terse100eos-1024-q8_0.gguf` — the same
grounding path P5.17 used, which makes its 56/56 the direct comparison. The four P6.0 residuals
above are still open and still apply.

Grounding now runs on the actual edge device while the renderer runs on the 3090, so P6.2 gets a
real deployment latency figure rather than a 3090 one — but the ssh round-trip is in the loop and
must be reported as part of it.
