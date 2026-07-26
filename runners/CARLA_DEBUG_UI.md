# CARLA live demo panel — tool + findings

**Status: WORKING, all stages live; guided-layout rewrite 2026-07-25T15:35Z.**
Infrastructure for Part VI,
not an experiment. No RQ, no gated result — but every number it prints is measured on
the deployed stack at run time, not replayed (see "What this cannot tell you").

One window that runs the whole thesis stack with nothing faked: **CARLA 0.9.16 renders
on the 3090, ArduCopter SITL is the physics, and BOTH models run on the Orin** —
Qwen2-VL-2B Q8_0 grounding over `JetsonBackend` (ssh), SAM2 carry over the ssh-stdio
bridge at `~/sam2-bench/carry_ssh_bridge.py`. No SAM2 on the 3090, ever: the 3090 runs
only the simulator.

## The four switches

Each one is a different demo, and they compose. Everything is live in every
combination.

| switch | values | what it changes |
|---|---|---|
| **PILOT** | `spectator` \| `copter` | `spectator` flies a camera on a stick — perception in isolation, any view you like, no flight dynamics. `copter` arms an ArduCopter SITL and slaves the camera to the pose the autopilot reports (P6.1), so the pixels are a **consequence** of the control output. |
| **ACQUIRE** | `warm` \| `cold` | `warm` maintains a track from the moment you designate and **delivers** it on command (P5.1 / P6.2-DELIVERY: maintain-and-deliver). `cold` does nothing until the command, then grounds under time pressure (E18 / R-34). The on-screen `deliver` timing is that comparison, measured live. |
| **DESIGNATE** | `vlm` \| `oracle` | `vlm` runs the deployed grounder on a point crop around the click. `oracle` seeds the carry from the CARLA projected box and skips the VLM — which is the scope P6.2-DELIVERY's claim was measured in (G6: q8_0 is non-discriminative on a car at 45 m nadir). Switching between them separates "grounding failed" from "carry/control failed". |
| **FOLLOW** | `manual` \| `assist` \| `auto` | `manual` = operator has sole authority. `assist` = the model aims (gimbal/look only, never position). `auto` = **closed loop**: the delivered box drives the copter through `CascadePID` → `SET_POSITION_TARGET_LOCAL_NED`, the same path `run_p62_flight.py` measured. `auto` needs `PILOT=copter` and says so if it does not have one. |

## Run it

```bash
.venv-ft/bin/python runners/carla_debug_ui.py                       # spectator, starts CARLA if needed
.venv-ft/bin/python runners/carla_debug_ui.py --pilot copter        # + SITL, arm, take off to --alt
.venv-ft/bin/python runners/carla_debug_ui.py --clean-world         # destroy every leftover actor first
.venv-ft/bin/python runners/carla_debug_ui.py --designate oracle --acquire cold
.venv-ft/bin/python runners/carla_debug_ui.py --pilot copter --smoke 45 \
    --out runs/carla-ui-spd --clean-world --auto-spawn 40           # unattended, writes smoke.png
```

| file | role |
|---|---|
| `carla_debug_ui.py` | the panel |
| `carla_render.py` | the non-interactive pose-slaved renderer (P6.1). Shares the axis convention, not the code. |
| `boot_sim.py` | `launch_sitl()` lives here; the panel calls it rather than re-spelling the P6.1 command |
| `carla_trace.py` | reads a follow trace back (`trace.jsonl` → ground / identity / switches / drift / bloat) |
| `ui_shot.py` | grabs the panel's own window to a PNG, so a layout claim can be looked at |
| `carla_ui_proof/` | six committed frames, so an audit can look without a rerun |

Controls: click the view to take the stick — the green border is the only "am I flying?"
signal. `wasd` move, `qe` up/down, arrows look (gimbal in copter mode), `space` pause,
`t` cycles FOLLOW, `g` delivers, **Shift-click a car designates it**, `drop` stops. The
key list is printed on the video header, where the keys are used.

**`wasd` is relative to the VIEW, not to north** (copter mode, 2026-07-25T17:10Z). The
nadir camera yaws with the arrow keys, so a world-absolute `wasd` steered sideways or
backwards on screen the moment the view was rotated — which reads as broken controls, not
as a frame mismatch. `manual_velocity(held, v, yaw_deg)` rotates the key vector by the
gimbal yaw: `w` is up-screen at every yaw, `d` is screen-right. The rotation used is the
**gimbal's**, because SITL never sends vehicle yaw (R-10) and the camera is
position-slaved. Guarded by `test_manual_velocity_is_relative_to_the_view`, which states
the assert in screen terms — push `w`, and the ground must slide *down* the frame — and
runs it through the real `project()` + `ned_to_carla` at five yaws.

`--smoke N` is the unattended path: it finds the car nearest frame centre, designates it,
delivers, engages AUTO, flies for N seconds, then writes `smoke.png` and prints the
verdict line and the mode echo. Synthetic key injection is banned in this repo (`xdotool keydown` is a
global XTEST event and has typed into the user's terminal), so `--smoke` calls the same
functions the widgets call instead of faking input.

## The layout is the pipeline (redesign, 2026-07-25T15:35Z)

The panel had grown into six full-width control rows of identical visual weight stacked
above the video, with the two lines that actually matter — the per-stage timings and the
mode echo — in the smallest, lowest-contrast text on the screen. Nothing said what to
press first, a two-tab Notebook offered two ways to start the same follow, the fly-speed
slider read as a bare `45`, and the right-hand column was a mostly-empty void holding a
thumbnail ~800 px away from its own caption. `carla_ui_proof/ui-idle-step2.jpg` is the
result of the rewrite, `ui-lost-step3.jpg` is the same panel with a failing track.

One rule, applied to the geometry: **left = what you DO, right = what HAPPENED, top =
is it ALIVE.** Three regions:

- **Header lamps** — `CARLA`, `ORIN`, `COPTER`, `TRACK`, `LOOP`. Colour and one word
  each, **no numbers**: green = healthy, amber = maintaining / next thing to do, grey =
  not yet, red = failing. A lamp answers "is it alive"; the instruments column answers
  "how well". They carried their own numbers (rate, carry Hz, altitude, drift seconds)
  for one revision and that is what put the same fact in four places at once.
- **A 340 px stage rail**, five numbered cards in operator order: **1 WORLD**,
  **2 PILOT**, **3 DESIGNATE**, **4 DELIVER**, **5 FOLLOW**. Controls only — no numbers
  at all. The numbered badge is green when the stage is satisfied, amber when it is the
  next one to do, grey otherwise, and the `deliver (g)` button lights amber with badge 4
  because it is the one control the `NEXT` line can point *at*.
- **One amber `NEXT` line** above the cards — the only prose on the panel, and it names a
  single action ("step 3 -- Shift-click a car in the view, or type a caption and press
  follow"). It is computed from the **last satisfied** stage, not the first unsatisfied
  one: `spectator` is a legal way to run the whole demo, so a session that never arms a
  copter must not be pinned on "step 2" forever while it is carrying a target. It also
  pre-empts itself with `working -- <what>` while `bg()` is busy (the operation names
  itself, and a long one reports progress: `climbing 31/45 m`) and "waiting for the first
  camera frame" before the first frame lands.
- **A 380 px instruments column** down the right that owns **every number in the panel**
  (see the next section).
- **The flown view takes every remaining pixel**, with the key list and the
  "click the view to take the stick" indicator on its header. There is no second view:
  the Jetson's own 960x540 feed was shown here (a rail card first, then a
  picture-in-picture) and it earned its removal — same camera at a fifth of the pixels,
  so it showed nothing the operator was not already looking at, while costing a resize
  and a blit per feed frame. What the Jetson sees that the flown view cannot show is the
  box *latency*, and that is a number: `lag` in the instruments column.

Three rules the redesign follows, all of them costed rather than tasteful:

- **Progressive disclosure by disabling and by ordering, never by hiding.** Hiding a
  widget costs a geometry pass per state change, and the tick that would pay for it is
  the one flying the camera.
- **Segmented switches for modes, comboboxes only for values.** `acquire`, `designate`
  and `follow` are switches whose state an operator has to be able to *see*, not open;
  the map name and the two resolutions are value pickers and stay closed comboboxes. The
  Notebook is gone: both designation paths are one card, ordered by which one to reach
  for (Shift-click first — the EXP-3 point crop is what works at 45 m nadir — typed
  caption second). The three switches were plain radiobuttons for one revision and the
  report was "it's difficult to discern the radio button selection": Tk's indicator is a
  ~9 px circle whose on and off states differ by a fill colour this dark palette
  flattens to the same grey. `seg()` builds them with `indicatoron=0` — the whole button
  is the indicator — and paints the lit one in `ACCENT` on `DARK`, so the current mode is
  legible in a screenshot at 0.55 scale (`ui-loop-closed.jpg`).
- **Per-tick work stays a `.config(text=...)`.** The same ~60 Hz tick paints the frame
  and flies the camera (finding 8), so every state update goes through `setw()`, which
  memoises the last kwargs per widget and skips Tk entirely when nothing changed. The
  cards, badges and lamps are hand-rolled from `tk.Frame`/`tk.Label` because clam's
  `LabelFrame` ignores the palette.

## The instruments column (was: the verdict bar, and before that the timings strip)

The numbers were in **four places at once** — the lamps, the card headers, a bar across
the bottom and a telemetry block in the rail — and the operator's complaint was the
consequence: *"we have data in the bottom line, left side, top side and topright, please
centralize it"*. They are now one 380 px column, read top to bottom in the order you care
in a failure. Every field is read straight off the live `track` dict each tick, and a
stage that has not run prints `--`, never `0.00` (`_f`, guarded by
`tests/test_pilot_modes.py`).

```
carry 9.4 Hz Orin, lag 0, lock 60/60 (207/210 all)          <- verdict, largest text, red on DRIFT/LOST
+30/30 vehicles (30 total)                                  <- transient: what the last world/link op did
1 WORLD      30 cars spawned   30 Hz render
2 PILOT      copter  44.6 m AGL
3 DESIGNATE  oracle GT box
4 DELIVER    0.00 s command to box
5 FOLLOW     auto  0.0 m/s
deliver 0.00 s | ground 0 ms | carry 106 ms (9.4 Hz) Orin | catch-up 6.5 s | lag 0 f | feed 5 Hz | disp 25 Hz
orin  9.31 W  tj 59 C  gpu 100%  ram 7.0/7.8 GB              <- what the Orin COSTS (P6.6)
+4.12 W over idle  2.11 J/frame  (P6.6: idle 5.19, carry 10.84 W)
armed mode 4  alt 44.6 m  gimbal -90/0
N  101.9  E  -25.7  D  -44.6
cmd -0.0  0.0  0.0   got 0.1 m/s
```

The five per-stage lines carry the **same numbers 1-5 as the rail cards** on the other
side of the picture, so "what did stage 3 cost" is one horizontal glance from the control
that runs stage 3. That is why `card()` no longer has a `val` label.

**The graph is gone** (removed 2026-07-26T14:20Z). `draw_graph` drew the last ~48 s as a
state ribbon over three autoscaled lanes (carry Hz / lag frames / on target %). In use it
added nothing the two live number lines above it do not already say: the operator reads
the current value off `gtimes`, and the *history* only mattered for the one shape (the lag
spike draining through the catch-up) that no one watches live — it is measured offline in
`runs/*/results.json`, which is where every thesis number comes from anyway. Removed
with it: the `PLOT_HZ/PLOT_N/PLOT_H` constants, the `plot` label, the `hist`/`lock` EMA
in `preview`, and `test_graph_draws_and_survives_holes`. Restore from git if the shape is
ever wanted back on screen.

- **`deliver`** — command to box in hand. First, because it is the number the whole
  warm-start argument is about. WARM is ~0.00 s by construction; COLD is the grounding.
- **`ground`** — the on-device VLM point-crop call only. `0 ms` under `designate oracle`
  because there is no call.
- **`carry`** — ms per SAM2 step on the Orin, and the rate it implies.
- **`catch-up`** — how long the tracker spent draining the backlog the grounding built.
- **`lag`** — frames the tracker is behind live, now.
- **`cmd` vs `got`** — commanded NED velocity against the copter's own reported ground
  speed. Two different numbers is the point: `cmd 4.0 got 5.7` means the airframe is
  doing what it can, not what it was told.
- **`lock a/b (c/d all)`** — rolling on-target count over the last 60 steps, cumulative
  in parens. **GT-derived** (`match_actor`), so it is a debug read, not a result.

### The Orin cost dashboard (added 2026-07-26T18:40Z)

Everything above says what the Orin *delivers*. These two lines say what it *costs*, and
they are the P6.6 axis on screen: `runners/orin_telemetry.py` reads the board's INA3221
rails and thermal zones over one persistent `ssh`, one `cat` per second, and the panel
prints the live watts beside the **measured reference figures** from
`experiments/2026-07-25-maintain-cost/` (`P66_IDLE_W` / `P66_CARRY_W` in
`grounding/contract.py`). A reading you cannot compare is a reading you cannot judge:
`9.31 W` alone means nothing, `+4.12 W over idle, carry measures 10.84` does.

- **`sysfs, not tegrastats`** — tegrastats is effectively a singleton (starting one wants
  `tegrastats --stop` first) and a power campaign owns that process for its whole run, so
  a panel that started its own would either fail or stomp the measurement. P6.6's numbers
  come off these same rails, so the two are comparable by construction. Cross-checked:
  the panel reads **5.19 W** with the board idle and the models resident, against arm A0's
  **5.195 W** median through tegrastats.
- **`J/frame`** = live watts / achieved carry Hz — the metric that made 512 win P6.6 on
  energy per carried frame. Prints `--` with no carry running.
- **`gpu`** comes from `/sys/devices/platform/gpu.0/load`, which is **per-mille** (999 =
  99.9%). Treating it as a percent reads a saturated GPU as 10% busy and looks entirely
  plausible on screen; `tests/test_orin_telemetry.py` pins it.
- **Colour** is WARN on `tj >= 85 C` (the board throttles at 97, so 85 is the watch line,
  not the limit) or under 1 GB of RAM headroom — the ring OOM-killed the N=2 selector on
  this board (R-16), so that is the failure about to happen, not a curiosity.
- **A dead or stale link prints a dash**, never the last good number. `read()` gates on
  the reading's *age*, not on the ssh being alive: a wedged `cat` loop keeps the pipe open.
- **`--no-orin-telemetry`** turns it off. Passive is not free: a second consumer on the
  device is exactly what cost P6.6 a repeat, so a power campaign gets an off switch.

## Measured live (2026-07-25, all on one Town10HD_Opt, copter at 45 m nadir)

Three runs, same tool, one switch changed at a time. Both frames were opened and looked
at, per the repo's visual-verification rule; they are in `carla_ui_proof/`.

| run | switches | `deliver` | `ground` | `carry` | on target | frame |
|---|---|---|---|---|---|---|
| `runs/carla-ui-spd` | copter / warm / **oracle** / auto | 0.00 s | 0 ms | 107 ms (9.3 Hz) | **231/234**, `lock 60/60` | `oracle-lock-45m.jpg` |
| `runs/carla-ui-vlm` | copter / warm / **vlm** / auto | 0.00 s | **8500 ms** | 108 ms (9.3 Hz) | **0/417**, `DRIFT 82 s` | `vlm-g6-miss-45m.jpg` |
| `runs/carla-ui-cold` | copter / **cold** / vlm / auto | **10.23 s** | ~8.5 s | — | — | — |

**The ORACLE run is the system working.** 40 cars, clean world, 45 s of AUTO flight:
green box tight on a white SUV labelled `white SUV in the center`, held 231 of 234 carry
steps, copter flown from the origin out to N90.5 at 4.0 m/s commanded / 5.7 m/s achieved.

**The VLM run is G6, reproduced live and in pixels.** Same altitude, same target
(`vehicle.nissan.patrol_2021`, hit-tested, designation confirmed). The grounder returned
a box sitting on the road's painted `BUS` marking a few pixels off the car, captioned
`yellow SUV in the center` — the caption colour was sampled off a white/silver SUV in
deep tree shadow. Carry then held that patch of asphalt perfectly: `0/417` on target,
`DRIFT 82 s`, AUTO commanding 0.1 m/s because its target is not moving. **Nothing
downstream failed.** This is why `designate oracle` exists and why P6.2-DELIVERY held
designation constant in both arms.

**The panel carries at `image_size` 640 — EXP-1's adopted default (changed
2026-07-26T15:05Z, was 512).** 640 is 99.4% of 1024's median IoU (0.811 vs 0.816) at 2.5x
the throughput (5.76 vs 2.34 Hz). The old 512 was justified by "the tracker must outrun the
5 Hz feed or the catch-up never converges" — **that reading came from bad data**: the live
stack carries at 5-9 Hz, so 640 costs the catch-up nothing. The dropdown is now **640-1024
only**; below 640 EXP-1's Hz curve saturates (~9-10 Hz at 256/384/512), so the accuracy
those sizes cost buys no speed. Raise it for the small/distant tail, where `held_frac`
climbs all the way to 1024 (0.859 -> 0.921).

**WARM vs COLD is 0.00 s vs 10.23 s** on this pipeline. Note the honest gap: 10.23 s is
**twice** the ~4.85 s the thesis cites for a cold acquire (E18/R-34). That figure was the
terse whole-frame call; this is a point crop upscaled to 1024 plus PNG-over-ssh, and the
difference is unmeasured here. Cite E18 for the acquire cost; cite this only as "cold is
still an order of magnitude worse than warm on the live rig". **That 10.23 s was measured
at `ground` 1024; the default is now 512** — the same run has not been repeated there.

## Copter pilot mode

`--pilot copter` calls `boot_sim.launch_sitl()` if 5760 is dead, waits, connects
pymavlink, arms, takes off, then slaves the camera to the NED the autopilot reports.

- **The camera is hard nadir, north-up.** R-10: yaw never arrives from the autopilot, so
  the renderer is position-slaved, not pose-slaved. Body-forward is therefore north and
  body-right is east, which is what makes `pid_to_ned` in `run_p62_flight.py` the
  identity `(vx, vy)` and what `tests/test_pilot_modes.py` asserts the key mapping
  against. Flipping a sign here does not crash, it flies away from the target.
- **A GUIDED velocity setpoint expires after ~3 s of silence.** Resent at `CMD_HZ`
  (10 Hz) — twice the feed rate, a fiftieth of the render tick.
- **AUTO gains are raised.** `CascadePID`'s default `kp_lat=0.02` holds a target only
  under dense (20 Hz oracle) delivery; at the on-device carry rate the steady-state
  offset `v/kp` walks a moving target off frame. `AUTO_KP_LAT=0.06`, `AUTO_MAX_V=8.0` are
  what the P6.2 warm arm flew. P only — add D when it rings, not before. Untuned against
  the ~5.7 m/s the airframe actually achieves; `cmd` vs `got` is the instrument for that.
- **Gotcha: `--alt` does not re-trim an airborne copter.** `arm_and_takeoff` returns the
  current altitude if the vehicle is already above 5 m, so a copter left flying by a
  previous run keeps its old altitude and `--alt 25` silently does nothing. Restart SITL
  or land it. Documented, not patched — reusing the aircraft is what makes a reload cheap.

## Designation: VLM vs ORACLE

`designate vlm` is the deployed path: the click gives a point, `rich_caption` builds a
RefDrone-style expression from the clicked car's own pixels (colour) and CARLA type
(object word) with position pinned to the constant `in the center`, and a `ground_res`-sided
square is cut out of the **native** sensor frame around the click and fed 1:1 to the Orin.

Native, not from the 960 feed: the sensor is 1920² (a real drone camera is 4K-class), so a
512 px crop out of it is 512 px of real detail instead of a 256 px feed patch stretched back
up. The window comes from `point_window` (`grounding/roi.py`), which **shrinks symmetrically**
at the frame edge rather than sliding — a click 100 px from the border gets a 200 px crop, not
a 512 px one slid off the click. Giving up context, not centring, is deliberate: G6 and
`runs/g6_gate/probe8.py` both show this grounder collapses when the target is off-centre
(5/8 centred vs 0/8 off-centre at a fixed caption), and `in the center` is what the caption
asserts. Every click writes the exact image that was fed to `<out>/click-<n>.png`.

`designate oracle` skips the VLM and seeds the carry from the CARLA projected box.
**That is not cheating, and it is not a shortcut** — it is exactly the scope in which
P6.2-DELIVERY's flagship number was measured, because at 45 m nadir the deployed q8_0
cannot discriminate a car (G6). It isolates carry + control. `follow` by typed caption
refuses under `oracle` (there is no box to seed from) and says so; the UI selftest
asserts that refusal.

## Authority: MANUAL / ASSIST / AUTO

`t` cycles, or use the stage-5 radiobuttons.

- **MANUAL (default).** Operator has sole authority. The model grounds and tracks; it
  draws a box and moves nothing.
- **ASSIST.** The model *aims* — `center_delta` pans the tracked box to frame centre —
  and in spectator mode it also *closes* (CHASE, below). It never commands position on
  the copter. Operator input is live in both modes; in ASSIST an arrow key **outranks**
  aim and a held `wasd` outranks CHASE for as long as it is held, otherwise the two sum
  and the view crawls against the input. Assist is inert while paused and with no track.
- **AUTO.** Position control, copter only: box → `CascadePID` → NED velocity → MAVLink.
  This is the P6.2 loop, and it is the reason the "deliberately not built" note that used
  to live in this file is gone.

### CHASE: hold the target at a set on-screen size (spectator)

The only range signal available is the box itself — no depth sensor, no target pose. So
CHASE regulates **apparent size**: `chase_speed(areas)` drives the box area to
`CHASE_TARGET_FRAC` of the frame, flying forward when the target is under size and
backward when it is over. That two-sided setpoint is what makes it a station-keeper
rather than a pursuer: undersized means too few pixels for a re-ground to succeed,
oversized means ordinary relative motion walks the target off the frame edge.

The error is taken in **log area**, because area falls as 1/d² — one log unit is a fixed
ratio of range whether the target is near or far, so a single gain behaves identically at
every distance. Output is `CHASE_GAIN` m/s per log unit, clamped to ±`CHASE_SPEED`.

That log error alone commands the same few m/s at every range, which crawls in from far
out, so it is **scaled by range**: `exp(err/2)` = `sqrt(target_area/area)` is exactly how
many times further out than the setpoint the target is (again because area ~ 1/d²). A
small box is a far target and gets a fast approach; a big one is close and gets a gentle
one. Speed is therefore `CHASE_GAIN · err · exp(err/2)`, still clamped to ±`CHASE_SPEED`.
The clamp is **one-sided in practice**: a hugely oversized box means the copter is very
*close*, and the same range scaling makes that retreat slow by construction, so only the
closing branch ever saturates.

Motion is along the **boresight**: `boresight(pitch, yaw)` is the direction the camera is
actually looking. The earlier ground frame dropped the pitch to hold altitude, but that
closed *ground* distance rather than *slant range*, so a target below the copter need not
grow at all. Since ASSIST already parks the target at frame centre, the boresight is the
line to the target — flying down it is what makes the box bigger. The cost is that
altitude is no longer held by construction: a nose-down chase descends. `floor_climb()`
is the guard. Dipping below `CHASE_FLOOR` **latches** a climb to
`CHASE_FLOOR + CHASE_CLIMB` and holds it until reached; a bare clamp would release at the
floor and, since the chase is still commanding descent, sink straight back and buzz along
it. A held `wasd` outranks the escape and clears the latch — flying the camera low by
hand is deliberate, sinking into the road is not. `z` is CARLA world z and Town10's ground
is ~0, so it doubles as AGL; a map with real relief needs a terrain raycast
(`ponytail:` in the constants).

Unlike aim, CHASE is *not* charged once per box; it stays latched between measurements.
That is correct, because moving genuinely does change the pixels — the box grows toward
the setpoint, the error shrinks, and the loop settles itself. It is a closed loop where
aim (on a frozen box) is an open one. The one failure that shape does not cover is the
box dying altogether, so CHASE additionally drops after `CHASE_STALE` (0.6 s, ~3 feed
periods) without a new measurement, rather than flying at a target nobody can see.

Two robustness choices worth keeping: **area**, not width or height, because a box that
shrinks in one axis is usually the target turning; and the **median** of the last
`CHASE_HIST` measurements, not the newest, because the failure being guarded against is
a single blown-up mask, which is exactly what a median rejects and a mean does not.

| knob | value | what it is |
|---|---|---|
| `CHASE_TARGET_FRAC` | 0.012 | wanted box area as a fraction of frame — a car at ~125x50 px, ~17 m |
| `CHASE_GAIN` | 5.0 | m/s per log unit of area error, before range scaling |
| `CHASE_SPEED` | 30.0 | speed cap; also the floor-escape climb rate |
| `CHASE_FLOOR` | 5.0 | min altitude (world z ≈ AGL) before the escape latches |
| `CHASE_CLIMB` | 15.0 | how far above the floor the escape climbs to |
| `CHASE_DEADBAND` | 0.15 | log-area hold band — ±16% of area, ±7.8% of range |
| `CHASE_HIST` | 5 | measurements median-filtered into one reading |

### Where CHASE_TARGET_FRAC = 0.012 comes from

Not arbitrary — but not a controlled sweep either. What it rests on:

**Measured, in this repo.** The 429-sample `native` arm of
`experiments/2026-06-30-roi-sr-upscale/sr_probe_out/sr_per_sample.csv` gives grounding
IoU@0.25 against GT box size in fed pixels, and it is monotone with a clear knee:

| GT long edge (fed px) | n | IoU@0.25 |
|---|---|---|
| <30 | 44 | 59.1% |
| 30–45 | 64 | 70.3% |
| 45–60 | 86 | 74.4% |
| 60–90 | 90 | 80.0% |
| **90–150** | 99 | **88.9%** |
| >150 | 46 | 93.5% |

The other three arms reproduce the same shape independently. `0.012` puts a car at
125 px long edge, i.e. inside that 90–150 knee; past 150 px you buy +4.6pp for a large
range cost. Corroborated coarsely by
`experiments/2026-06-30-whole-frame-resolution/` (28.8 px fed → 31.4%; 54 px → 63.1%;
68 px → 65.4%, saturated) and, observationally, by select pass rate on real video:
recomputed over the 54 cells of `experiments/2026-07-20-late-entry-rescue/`, failures
have median target long edge 40 px and passes 61 px. **That last one is confounded with
clip identity** (the small bin is a different set of scenes) — it corroborates the curve,
it cannot stand alone.

The carry does **not** constrain the setpoint: P5.15 survival over 25 clips is flat in
seed box size (3/4, 7/7, 8/8, 6/6 across the four size bins). Its death mode is mask
leakage, not pixel starvation. Only the VLM pushes the setpoint up.

**External corroboration.** OpenRef buckets referring-expression accuracy by frame-area
fraction and reports Qwen2-VL-7B at 8.7 (Tiny, <1%) / 37.2 (Small, 1–10%) / 59.1
(Medium) — the largest single jump is at the **1%-of-frame** boundary, which lands on
the repo's own knee from an unrelated measurement. No aerial visual-servoing paper
publishes a frame-area setpoint; the values that exist are for other regimes (an
underwater convoy at 0.50, a hobby face-follow at ~0.075, a DJI patent giving only an
0.8-of-a-dimension upper limit).

**Geometry (exact, given the pinhole model).** f = 480 px, VFOV 58.7°. For a 4.5x1.8 m
car: frac 0.004 → 30 m, **0.012 → 17.3 m**, 0.040 → 9.5 m. Worst-case open-loop
time-to-exit against 5 m/s of lateral relative motion: 3.19 s at 0.004, 1.8 s at 0.012,
**0.89 s at 0.040** — against a ~4.5 s cold re-ground. That is the argument against the
original 0.04 as much as the IoU curve is.

**Acceptable range: 0.008–0.020.** Below that, grounding falls off the knee; above it,
you pay range and edge margin for ≤+5pp.

**Still unknown, state it as such.** The "too large" branch is unmeasured — no evidence
exists that 0.04 *degrades* tracking, only that it buys no grounding and costs geometry.
And **the repo has never run a target-size sweep.** Closing this properly means sweeping
`CHASE_TARGET_FRAC` ∈ {0.004, 0.008, 0.012, 0.020, 0.040} in the rig at n≥25 per arm,
scoring re-ground IoU and track-loss rate.

### Three consequences worth flagging

**A 45–60 m working altitude is incompatible with whole-target grounding at this size,
and the panel now shows it.** At 60 m slant range a car is 36 px long edge / frac 0.0010 —
below every knee measured, in OpenRef's Tiny bucket. The `runs/carla-ui-vlm` row above is
that prediction landing at 45 m: `0/417`. The two live answers are a point crop
(`designate vlm`, which still missed here) or holding designation constant (`oracle`).

**An area setpoint couples standoff to target class.** Same 0.012 holds a truck at 33 m,
a car at 17 m, a motorcycle at 11 m, a pedestrian at 6.3 m. The person-following
literature servos on bbox *height* for exactly this reason. The value here is calibrated
for cars; treat it as such until something needs otherwise.

**The floor can fight the setpoint on a shallow approach — untested.** 0.012 holds a car at
17.3 m *slant* range, and altitude at that range is `17.3·sin(pitch)`: fine at a 45° look
down (12.2 m), but it falls below the floor as the look flattens out. The escape then
latches a climb, which shrinks the box, which re-commands a close — a limit cycle. Whether
it happens depends on where ASSIST parks the pitch, which nothing here measures yet. The
fix is a floor below the setpoint geometry, not a bigger climb, and lowering `CHASE_FLOOR`
10.0 → 5.0 (2026-07-20T22:55Z, on request) moves the breach from anything shallower than
35.3° to anything shallower than 16.8°. Untested in flight; it buys headroom, it does not
prove the cycle gone.

### One correction per measurement, not per tick

The aim law is split in two on purpose. `center_delta(box)` returns the **whole** angle
that would centre that box; `ease(remaining, dt)` decides how much of it to spend this
tick. `fly()` charges the outstanding correction **once per new box** — keyed on
`track["stamp"]`, a counter the follow thread bumps on every publish — and then spends
it down. A box that stops updating is therefore worth exactly one correction.

That is the fix for the occlusion runaway, and the reason there is no timer or interval
anywhere: **the tracker's own update rate is the interval.** The box lives in *pixels*,
so a per-tick law is an open loop — turning the camera does not change a stale box, the
error never shrinks, and the controller integrates a constant error until the view has
swept away from the target entirely. Since the target is then out of frame, the tracker
can never re-acquire it and the box never updates again: unrecoverable, from a 2 s
occlusion. Under charge-once, the same occlusion costs one pan to where the target last
was, then the camera holds and waits — which is what the carry needs, because it does
re-find targets several seconds later.

`ASSIST_RATE` (top of `carla_debug_ui.py`, default 3.0 /s) is the calibration knob: the
fraction of the *outstanding* correction spent per second, so the view **eases** onto
the target — ~95% of it in a second — instead of snapping. Raise it if the camera lags
a fast target; lower it if a box jumping across frame (a track switch, a catch-up replay
finishing) whips the view. `min(1.0, ASSIST_RATE * dt)` makes it dt-correct and
overshoot-proof in the same expression — a stalled tick spends the remainder exactly and
stops.

Note the ceiling this leaves: aim is charged from a box measured on an already-delivered
frame, so it always trails a moving target by roughly the carry's own latency.

**Tried and reverted: snap-to-centre with a deadzone rectangle.** Closing 100% of the
error per tick, with a centred quarter-frame box inside which the camera held still,
read as violent on the actual view — the camera sat dead, then jerked. The proportional
ease has no deadzone and no dead-and-jerk: it is always converging, slowly. Do not
re-propose the deadzone as a fix for jitter without watching the pan first.

Aim law tested headless in `tests/test_center_delta.py`: holds still when centred, turns
the right way on both axes, returns the full angle (not a step), spends a *fraction* of
it per tick (the pan-not-snap assert), never overshoots however long the tick, converges
to <0.1 deg on a re-measured target — and `test_a_frozen_box_is_worth_one_correction`
holds the total rotation to the one measured angle across a simulated 60 s occlusion,
which is the assert that fails if anyone reintroduces a per-tick law.

## Design constraints (the non-obvious ones)

**The sim free-runs at its own pace.** This is the whole point: a real camera does not
wait for the model. The renderer is async and paced by wall time, so an 8.5 s VLM acquire
costs 8.5 real seconds of vehicle motion and the delivery lag Parts IV and V exist to
measure still exists. Synchronous mode would make the client the clock master and quietly
delete that lag. See `docs/decisions/part6-flight.md`.

**One camera, two rates.** The operator sees every frame (up to 30 Hz); the Jetson gets
every 6th (5 Hz), always resampled to a fixed 960x960 — plus a reference to that same
frame at native resolution, which is what a click crops from. Two sensors would double the
render cost to show the same pixels, and pinning the Jetson feed means VLM cost and box
pixel coordinates do not move when the window is resized.

**Nothing is drawn into the engine.** Every overlay is cv2-drawn onto a frame *received
from the sensor*. `world.debug.*` would put the box in the world the model is looking at,
which corrupts the view under test. An earlier revision had `unproject()`/`draw_box_2d()`
for exactly that; both are deleted, deliberately.

**Ground truth enters in exactly two places, both labelled.** `track["box"]` is written
by the VLM (`roi_reanchor` + `parse_bbox`), by `carry.step()`, and — only under
`designate oracle`, which is a switch the operator sets and the strip prints — by the
CARLA projected box. `match_actor()` reads `world.get_actors()`, but only to colour the
box and count locks.

> A Part VI controller must key off `track["box"]` and never `track["actor"]` — the
> moment control reads the actor, the loop is GT-driven and every number from it is
> worthless. AUTO obeys this: `oracle` seeds the *first* box and nothing after it.

**Tk owns the main thread; CARLA RPCs go through `bg()`.** One whole-world operation at a
time, and `bg()` **refuses** rather than queues — a second spawn request while the first
is mid-batch is a mistake, not something to serialise. `queue()` is the one exception, for
startup ordering (see the actor findings below).

**The starting grid is deterministic, the traffic is not.** `spawn_vehicles()` draws from a
private `random.Random(SPAWN_SEED)` over blueprints sorted by id, so the same seed puts the
same models on the same spawn points on every run — verified 3/3 identical plans
(model + point + server-accepted flag) at n=50 on 0.9.16, 2026-07-20T21:05Z. What it does
*not* buy is repeatable driving: the traffic manager's `set_random_device_seed()` cannot be
used here. Calling it while vehicles are batch-registered times out `register_vehicle` after
2000 ms and then aborts the client process with `Responding error from function
set_actor_simulate_physics: Actor could not be found in the registry` — a core dump, not an
exception. Reproduced at both 20 and 50 cars; removing the seed call fixes it. Repeatable
traffic needs synchronous mode, which this rig deliberately does not use (see above).

Three conditions on the determinism: the world must be otherwise empty (an occupied spawn
point is rejected server-side, so re-spawning on top of an old fleet is a different fleet),
the count must be the same (the draw is sequential, so 30 cars is a prefix of 50, not a
subset chosen the same way), **and the camera must be in the same place** — the points are
now sorted by distance to the camera before the draw is consumed.

**Hand cars back to nobody before destroying them.** `clear()` and `clean_world()` call
`set_autopilot(False)` on every vehicle and let a tick land before `DestroyActor`. Without
it the traffic manager keeps stepping an actor that is already gone and the resulting
server-side error aborts the UI process. Same crash as the seed call, reached from the
other end. **`load_world` is the third way in:** it destroys every actor server-side
without asking, so clicking "load" with an autopilot fleet up killed the UI the same way
(CARLA itself survived). `load_world()` now does the same handback-then-tick before the
swap.

## Findings (what we learned)

1. **Headless costs nothing here.** The UI reads an attached RGB sensor, never the
   viewport, so `-RenderOffScreen` frees the GPU that SAM2 contends for and changes
   nothing functionally. The spectator has no pixels of its own — attaching a camera to
   it is what makes the flown view grabbable.
2. **Render at display size or it looks broken.** Upscaling a 960x540 sensor into a
   maximised window reads as a "stuck resolution". The camera is respawned at the
   display size on a debounced `<Configure>` (400 ms, snapped to 32 px steps — each
   respawn is a destroy + spawn round-trip). Capped at 1080p30.
3. **`sensor_tick` is a request, not a promise.** A GPU-contended sensor quietly ships
   fewer frames. The `CARLA` lamp shows *measured* delivery rate, which is the only way
   to notice.
4. **Pause = synchronous mode with no ticker.** Traffic, physics and the camera freeze
   together. Two traps: keys must be gated while paused (the spectator still accepts
   `set_transform` on a frozen world, so held keys fly it blind and the view snaps on
   resume), and the server must be put back to async on *every* exit path —
   window-close, SIGINT and SIGTERM. A server left in sync mode with nothing ticking it
   hangs the next client that connects.
5. **A timed-out `carla.Client` stays unhappy.** Reusing one across retries made a CARLA
   that *was* coming up look like one that never did. Each auto-launch attempt builds a
   fresh Client; startup budget is 300 s.
6. **FOV is a free knob now.** It once had to match CarlaUE4's viewport default, because
   the operator was looking at the viewport. Headless removed that constraint. 90 deg is
   inherited, not chosen, and is an untested lever on lock rate.
7. **`t.MaxFPS` via `-ExecCmds` does nothing.** Measured: the server free-runs at **190 Hz**
   (step 5.3 ms) with the flag set to 30. The rate in the `CARLA` lamp is `sensor_tick`
   frame *delivery*, a different knob. If a real cap on GPU draw is wanted, this flag is
   not it — and nothing currently caps the world clock.
8. **The tick both paints and flies, so display cost became fly cost.** `fly()` used a
   nominal 1/60 s step while the tick actually ran at ~18 Hz at 1080p: holding `w` with
   the slider at 45 m/s moved the camera at **13.3 m/s**, with 64% of sampled intervals
   showing no movement at all — that is what "choppy" was. Two fixes: `fly()` moves by
   *measured* elapsed time (clamped at 100 ms so a stall cannot teleport the camera), and
   the display path uses PIL `ImageTk` over Tk's PPM parser (28.8 ms to 7.5 at 1080p —
   Tk was parsing a 5 MB text blob every frame) plus `cvtColor` over `[:, :, ::-1]`
   (6.3 ms to 0.3). After: 44.6 m/s measured against a 45 m/s slider, tick ~41 Hz.
   *Ceiling:* one Tk thread still paints and flies, so a big enough window still steals
   from the fly rate — the dt fix makes speed correct, not the loop fast.
9. **Closing the window kills the server, but only one this process started.**
   `ensure_carla` returns the `Popen` or `None`; `stop_carla` TERMs the process group
   (`CarlaUE4.sh` forks the real binary, so signalling the launcher alone leaves it
   running) then KILLs the remainder. A CARLA you started with `carlahl` is left alone,
   and gets handed back unpaused. *Not covered:* a hard crash. `xdotool windowclose`
   destroys the window, which aborts Tk with an X error and skips every Python cleanup
   handler — the server is orphaned. Use `killcarla` for that.
10. **Waiting on the launcher is not waiting on the server** (the "close it, relaunch it,
    it hangs" bug). `stop_carla` polled `proc`, which is the `/bin/sh` from
    `CarlaUE4.sh`. The shell dies the instant the group is signalled, so `poll()`
    returned, `stop_carla` returned, and the escalation to `SIGKILL` **never ran** —
    `CarlaUE4-Linux-Shipping` needs ~7 s to exit and was left orphaned. Measured on the
    orphan: it keeps port 2000 `LISTEN`ing (`connect_ex` = 0) while `get_server_version`
    times out. The next launch therefore probed a dead socket, spawned a second server
    that could not bind, and sat in the 300 s wait loop — the hang. Three fixes, and the
    first is the actual bug:
    - `stop_carla` reaps the launcher (so its zombie does not read as alive) and then
      waits on the **process group** via `killpg(pgid, 0)`, SIGTERM 8 s then SIGKILL 5 s.
    - `ensure_carla` treats a bound-but-silent port as dead by definition — a healthy
      server answers in milliseconds — and clears it, but only if `ss` says the owner is
      a `CarlaUE4*` process. Anything else is an error, not a kill.
    - The wait loop aborts the moment `CarlaUE4.sh` exits, instead of timing out.

    Verified by running the user's flow twice back to back: connect 9 s, close, connect
    9 s, port free after each, no manual `pkill`. `tests/test_carla_lifecycle.py`
    (opt-in, `CARLA_LIFECYCLE_TEST=1`) is that flow. *Known and harmless:* a sibling UE4
    helper in its own session can outlive the group by tens of seconds. It holds no port
    and blocks nothing, so the test asserts on the **port**, not on `pgrep` being empty.
11. **`drop` cleared the box, then the box came back and stayed.** Setting the stop
    event does not stop the follow thread where it is: it is typically inside a ~100 ms
    `carry.step()` (or an ~8.5 s VLM grounding), and it published its result *after*
    `do_drop` had cleared `track["box"]` — leaving a frozen square on screen with no
    thread left to move it. Fixed with one `track_lock`: the thread re-checks its own
    stop event under the lock immediately before publishing, and `do_drop`/`do_follow`
    set the event and clear the box **inside** that same lock. Not a display bug — the
    stale box also fed ASSIST, so the camera kept chasing a dropped target.
12. **A signal handler must not touch Tk.** Ctrl+C ran teardown straight from the
    `SIGINT` handler, but a signal lands mid-bytecode — usually *inside* `tick()`. So
    `root.destroy()` ran, the handler returned, and the interrupted callback carried on
    into a dead widget: `_tkinter.TclError: invalid command name ".!frame.!scale"`.
    Now `SIGINT`/`SIGTERM`/the X button only set a `closing["want"]` flag, and the tick
    is the single place that tears down — at a point where nothing is half-executed.
    `unpause_on_exit` is idempotent so the flag cannot fire it twice. Regression test:
    `test_ctrl_c_exits_clean` (same opt-in file) boots the real UI, SIGINTs it, and
    asserts exit 0, no traceback, and a free port.

    *Not a bug:* `UserWarning: cannot import name '_C' from 'sam2'` on the first
    follow. Upstream SAM2 without its compiled extension; it disables one mask
    post-processing step and is explicitly documented as safe to ignore.
13. **A Tk rail that overflows drops widgets silently, and only a screenshot says so.**
    The first build of the stage rail packed ~935 px of cards into a ~915 px column: the
    KEYS card was clipped mid-row and the Jetson thumbnail card **was not rendered at
    all** — no error, no warning, exit 0, and the code that creates it runs fine. Found by
    grabbing the window and looking, then fixed by moving pixels out of the rail rather
    than by scrolling it: the thumbnail became a `place()`d PIP over the video (and the PIP
    was then removed outright — see the layout section), the KEYS
    card was deleted and its content moved to the video header, and `ptel` was cut to
    three wrapped 8 pt lines. The rail now ends with ~60 px of air, which is the margin a
    longer status string is allowed to eat. Same class of failure as a black render:
    `pack()` has no error path for "does not fit".
14. **`xdotool search --name` returns the WM's frame as well as the app's window, and the
    frame is the bigger one.** `ui_shot.py` picked "the largest match", which grabbed the
    reparenting frame — a screenshot that is pure black with a title bar on it, and which
    passes any "did the file get written" check. Fixed with an `is_client()` filter: only
    the real client window carries `WM_STATE`. The `>99% one colour` assert in the same
    script is what caught it. (The first implementation of this script used
    `ffmpeg -f x11grab` on the window's geometry, which returns whatever is *on top* — it
    screenshotted the user's browser. `xwd -id` reads the window's own pixels, needs no
    raise, and cannot capture anything else.)
15. **`recv_match(type=...)` starves every message you did not ask for first.** Reading
    the rail on a screenshot showed `hb no link` on a copter that was armed and flying:
    `recv_match(type="LOCAL_POSITION_NED")` consumes and discards everything else in the
    buffer, so the `HEARTBEAT` call after it always saw an empty buffer. Both are drained
    from one loop now. The fix's own first version was worse than the bug — a **tuple**
    passed as `type=`, which pymavlink only wraps when it is a bare string
    (`not isinstance(type, list) and not isinstance(type, set)`), so the filter became
    `[("A","B")]`, nothing ever matched, and `pilot["ned"]` froze at `(0, 0, -alt)`: a
    camera that stops following the copter while every widget still reads healthy. It
    must be a **list**.
16. **`--smoke` picks the nearest car, which is not the trackable one.** Four consecutive
    smoke runs at 45 m nadir with carry 512 lost or drifted the mask: `DRIFT 53s` on a
    `vehicle.nissan.micra`, then three `SMOKE FAIL: no carried box after 60s` on a
    `vehicle.micro.microlino` and a `vehicle.dodge.charger_police_2020`. Recorded as
    behaviour, not patched: at that altitude and tracker resolution a small hatchback is
    a handful of pixels, which is exactly the small/distant-target tail EXP-1 keeps 1024
    as a fallback for. The showcase runs pick the target deliberately for the same reason
    (`run_p62_matrix.py --showcase`). Nearest-to-centre is a convenience for the
    unattended path, not a claim that any car is followable.
17. **One busy flag froze the camera for operations that could not have hurt it.** The
    report was *"arm+takeoff is the one that freezes the world with a 'one operation at a
    time'"*. It was not stuck: `bg()` took one whole-world operation at a time and `fly()`
    stood down for **any** busy flag, so a ~40 s SITL boot + climb blocked the render tick
    and refused every unrelated button, in silence. `busy` is now `{on, world, what}`:
    world ops (load, spawn, clear) invalidate the CARLA handles `fly()` steers and still
    stop it, **link** ops (arm, takeoff, land) touch only MAVLink and leave every handle
    valid, so the camera keeps flying through them. And the long one now narrates —
    `arm_and_takeoff(m, alt, note=...)` and `wait_alt(..., note=...)` take a progress sink
    (`note()`, marshalled to Tk through `after()`), so the panel says `GUIDED + arm`, then
    `climbing 31/45 m`. Silence for 20 s reads as a hang whether or not it is one.
18. **A blocking helper that also reads the shared MAVLink socket steals the pose the
    camera is slaved to.** `to origin` "freezes the view with no apparent function":
    `reset_to_origin()` blocks for up to 40 s *and* calls `recv_match("LOCAL_POSITION_NED")`
    itself, which is finding 15's starvation from the other side — the panel's own drain
    gets nothing, `pilot["ned"]` stops advancing, and the camera stops following the copter
    that is in fact flying. It also fired in spectator mode, where there is no copter at
    all. Fixed by splitting the non-blocking half out (`sitl_fly_leg.send_position`) and
    giving the goto to the loop that already flies: `pilot["goto"]` is a target the command
    tick resends at `CMD_HZ` and clears on `GOTO_TOL` / `GOTO_TIMEOUT`, reporting
    `to origin: 42 m to go` from the tick. A held movement key clears it (the operator
    outranks a goto, same as ASSIST), and it is a position setpoint **or** a velocity
    setpoint in a given tick, never both. Without a copter it refuses instantly.
19. **A "correct but subtle" overlay colour is a bug.** The maintained (undelivered) box
    was grey and 1 px — technically distinct from the delivered green box, and the report
    was *"the first track is grey and hard to see too"*. It is now `WARN` amber and drawn
    as four corner **brackets** whose length scales with the target, so it is visible on
    real imagery and still unmistakably not the delivered box in a still frame
    (`ui-maintained-vs-delivered.jpg`, both states drawn on the same 45 m nadir CARLA
    frame). The test asserts the amber pixels, a minimum pixel count and that the middle
    of each edge stays background — a closed rectangle would pass a colour-only check.
20. **A control nobody can explain is an unfinished experiment.** *"the flow is a bit
    unclear even to me, why does `g` exist?"* — asked by the person who commissioned the
    panel. `g` **is** the operator's command arriving mid-flight, which is the entire
    premise of Part V, and the two acquire modes differ only in what the system was
    allowed to do before it. The DELIVER card now says so in the current mode's own words
    and re-says it when the mode changes: WARM = "the box already exists (stage 3 has been
    carrying it unasked), so `g` just hands it over: one carry step, ~0 s"; COLD = "`g` is
    also the *start* of grounding, so the VLM runs now, under time pressure, and the box
    lands ~4.8 s stale on a moving target".
21. **The panel demoed maintain-and-deliver and let the viewer read it as select.** Next
    report from the same person: *"i thought the idea was to have all candidates
    pre-selected and then use them to choose between; the current system is only a
    prechoice of one (that the user does itself, so functionally it is the same thing)"*.
    The read is correct — with **N=1 the maintain step and the select step are the same
    act**, and the panel's Shift-click stands in for the idle-window discovery (P5.16:
    24/24 GT-free discoveries accepted) rather than reproducing it. What warm/cold
    compares is not *which* target but **who owns the box while it is being produced**:
    the interval between the click and `g` is the idle window, warm carries through it and
    cold does not. That is exactly P6.2-DELIVERY, which held designation constant with
    ORACLE in both arms so designation was *not* under test.
    N=1 is the thesis position, not a demo shortcut: R-16 OOM-kills the multi-candidate
    selector at N=2 on the Orin with the deployed `PRUNE_AFTER=100` ring, select never won
    a discordant pair in 8 runs (P5.3 3/5, P5.4 3/5 cell-for-cell, P5.5 SWAP 3/5, P5.10
    24/24 tie, P5.13 24/24 vs 23/24, P5.17 56/56 vs 55/56, P5.18 SWAP 17/26, R-36 b=5/c=0
    p=0.0625), R-38 put the residual failure downstream of grounding, and R-28 settled the
    scope. The DESIGNATE card now says all of that in four lines, because a demo that
    invites the wrong claim is worse than one that shows less. **A live N=2 maintain-and-
    select mode is still buildable** — R-16 measured `PRUNE_AFTER=32` as free — and would
    demo the dead lever rather than the claim; it is not in the panel.

## Actors leak, and a leaked world lies (2026-07-25T13:50Z)

Caught by the user looking at a frame and asking why there were so many mangled cars.
There were: **190 vehicles, 20 walkers and 3 orphaned cameras** in Town10 after four
`--smoke` runs at 30 cars each. `clear()` only ran on the hot-reload path, so a normal
exit left the whole fleet behind, and the next run re-spawned onto the same seeded spawn
points — which the server accepts as *overlapping* actors, so cars ended up interpenetrated
and physics-locked in piles.

This is not cosmetic. **Every scene characterisation taken before the fix is void**: the
"traffic" was stacked duplicates, and a `lock 54/60` measured against it came from a
degenerate near-static pileup, not from a tracked moving car.

Three fixes:

- `unpause_on_exit` now stops and destroys the camera sensor **unconditionally** (not
  only on reload) and calls `clear()` on a real exit. The sensor part also fixed
  `Fatal Python error: PyGILState_Release ... runtime state: finalizing` — the sensor
  callback was firing into an interpreter that was already tearing down.
- `clean_world()` + `--clean-world` + a "clear all" button destroy **every** vehicle,
  walker, controller and camera in the world, not just the ones this process spawned.
  Nothing else legitimately holds actors on this rig, so scorched earth is the right
  default for a demo tool.
- The selftest exits through `unpause_on_exit` instead of `root.destroy()`, which is what
  made it stop leaking a sensor per run.

**Then the opposite failure.** A cleaned world put 30 cars over all of Town10HD and left
**none** under a ~50 m nadir footprint: `lock 4/7`, 150 consecutive `lost` steps. Two
fixes: spawn points are sorted by distance to the camera before the draw, and in copter
mode the spawn is deferred until after take-off (`queue()`), so "near the camera" means
near where the camera actually ended up rather than near the origin.

## A lost mask is a MISS, not a pause (2026-07-25T14:05Z)

The rolling lock counter and `hits`/`steps` were only updated in the branch where the
carry returned a box. So a run printed **`lock 60/60` after 87 consecutive lost steps** —
the deque simply stopped moving and froze at its last good value. Fixed: the `b is None`
branch appends `False`, bumps `steps`, and stamps `lost_s`. The verdict line now names the
two failures apart, because they need different operator actions:

```
LOST 12s -- no mask, drop and re-follow.
DRIFT 82s off target -- drop and re-follow.
```

`LOST` is the tracker returning nothing; `DRIFT` is the tracker confidently returning the
wrong thing. A frozen counter made both invisible.

## Delivery latency must not include a server boot (2026-07-25T13:20Z)

The first COLD delivery read **18.84 s** because it paid for the on-Orin `llama-server`
starting up. That is a lie in the wrong direction — it flatters the warm arm by inflating
cold. The backend is now a single locked, lazily-built `JetsonBackend` (`get_backend()`)
prewarmed by a startup thread, and the same COLD delivery re-measured **10.23 s**.

Also instrumented: when the carry bridge dies, the exit status is now captured and
printed (`carry bridge died (rc=-9)`). `-9` is the Orin OOM killer, which leaves no
traceback and is exactly why `ui_bridge.err` looked clean. Seen once before the
instrumentation existed; not reproduced since, so it stays open.

## The carry bridge is resident, not per-designation (2026-07-25T20:20Z)

Same lesson as the section above, one process along. The panel used to `Popen` a fresh
`carry_ssh_bridge.py` for every designation, so the operator's wait from "locked in" to a
live box included `ssh` + `import torch`/`sam2` + `from_pretrained` + the first CUDA
forward. Driving the panel, that read as **6–10 s**, and the panel's own 64 live traces
have a median `catchup_s` of **6.52 s**.

P6.7 (`experiments/2026-07-25-handoff-latency/`) decomposed it on the Orin: `ssh` 0.301 +
`import` 2.846 + `weights` 1.800 = **4.95 s of 6.15 s is process start-up**, and only
0.36 s is the tracker catching up. None of it is optimisable on an Orin; it can only be
paid in advance. So `get_bridge()` now keeps **one** bridge for the session, `prewarm_bridge()`
pays the whole thing at start-up next to the `llama-server` prewarm, and each designation
just re-`init`s (which rebuilds `StreamCarry` on the already-loaded predictor).

First live designation after the change: **`catchup_s` 0.343 s**, on the panel's own
readout, same metric as the 6.52 s median — `runs/p67-panel/trace-127/trace.jsonl`,
`ev="live"`. `ui_bridge.err` from that run shows one `[bridge] model loaded in 1.8s` and
*two* `init`s (the prewarm's dummy frame, then the real seed), which is the residency
working. Consequences worth knowing:

- **Dropping a track no longer kills the bridge.** `_stop_current()` only sets the stop
  flag; the process is reaped on window close, so a re-follow costs one `init`, not a
  6 s cold start. An orphan on the Orin is now possible only if the panel is killed
  without closing its window.
- **A carry-resolution change from the combobox respawns it**, as does a dead process
  (`poll()` is not None — `rc=-9` is still the Orin OOM killer). Respawn is the failure
  mode, not the normal mode, and it costs exactly today's old behaviour, once.
- **`bridge_io` guards the pipe, not just the dict.** The framing is one framed send then
  one framed recv, so a follow holds it for its whole life. The next follow has already
  set the old one's stop flag, so it waits at most one carry step.
- **G3 says residency is free on the 8 GB board**: a resident SAM2 costs the deployed
  `llama-server` **x1.000** on grounding latency (3791.1 → 3791.2 ms over 25 paired
  requests) and leaves 1315 MB of `MemAvailable`, with 0 `rc=-9` over 50 consecutive
  designations on one bridge.

What this does **not** fix: the seam is now short, but at 76 m the smoke run above still
drifted (`lock 0/129`) from a 5x13 px VLM seed box. Latency and grounding quality are
separate problems and this only closes the first.

## Walker AI is dead on Town10HD_Opt — and it is the simulator, not the tool

The selftest's "walkers move" assert failed with `only 0 walkers moved`. Reproduced
**outside** the UI with CARLA's own canonical sequence (spawn walker, spawn
`controller.ai.walker`, `start()`, `go_to_location(get_random_location_from_navigation())`):
5/5 walkers moved 0.00 m in 5 s, while `get_random_location_from_navigation()` returned
valid points and `Carla/Maps/Town10HD_Opt.bin` exists on disk. Converted to a printed
NOTE with the reproduction in the comment; the **car** motion assert stays a hard gate,
because that is the one that catches a frozen world.

## Dark theme

`apply_dark(root)`, one call after `tk.Tk()`. The video panes were `#1e1e1e` from the
start; a white control strip around them is what the eye adapts to, and then the
render you are judging looks underexposed. Palette: `DARK #1e1e1e`, `DARK_HI #2d2d2d`,
`TEXT #e0e0e0`, `ACCENT #3fbf5f` (focus ring, same green as an on-target box),
`ALERT #ff6b6b` (the drift banner). Three added by the redesign: `MUTED #8a8a8a`
(secondary text — a unit, a hint), `LINE #3a3a3a` (card borders and unlit pills) and
`WARN #e0a03f` ("this is the next thing to do", and "this number is not healthy but not
dead"). Four colours is the whole vocabulary: green / amber / grey / red, used for lamps
and stage badges alike, so the two mean the same thing in both places.

One colour lives outside that vocabulary, on the render only: a **thin soft-blue** (BGR
`235,180,120`) rectangle is the CARLA projected box of the seed target — ground truth, drawn
for the eye so a click's VLM box and the carried box can be judged against it at a glance. It
is a reference overlay, never an input: nothing reads it, and under `designate oracle` the
seed comes from the same projection, so there the green box starts on top of it.

Three separate mechanisms, because Tk has three:

- `tk_setPalette` — every classic Tk widget in one call, including already-built ones.
- `ttk.Style` with theme `clam` — ttk's default theme ignores colour options outright,
  so the Combobox needs the theme swap before `configure` does anything.
- `option_add` — the Combobox *dropdown* (a plain Tk Listbox the theme never reaches),
  plus `Entry`/`Spinbox` backgrounds and `Checkbutton.selectColor`. These last two are
  the contrast a flat dark palette loses: a text field must look like a hole you can
  type in, and an unchecked box defaults to a white square louder than anything else
  on screen. `option_add` only affects widgets created after the call.

Verified by screenshot, not by reading the code: the control strip was rendered with
the real `apply_dark` under a throwaway harness and grabbed with `ffmpeg -f x11grab`.
The first grab is what showed the invisible entries and the white checkbox.

## Committed frames

Four of the seven are the redesign, and every one was opened with the Read tool before
anything in this file was written about it (`runners/ui_shot.py`, `--name "CARLA debug"`).

| frame | run / config | what it shows |
|---|---|---|
| `ui-idle-step2.jpg` | spectator / warm / vlm / manual, 50 cars, no track — **first redesign revision**, before the numbers were centralised | The guided idle state. `CARLA 20 Hz` and `ORIN ready` green; `COPTER spectator`, `TRACK none`, `LOOP open` grey; `+50/50 vehicles (50 total)` in the transient slot. Amber `NEXT step 2 -- arm the copter (or stay spectator and fly the camera by hand)`, badge 1 green, badge 2 amber, 3-5 grey. Card values read `50 spawned` / `spectator` / `ground --` / `deliver --` / `manual`. Verdict bar `20 Hz live` over `deliver -- \| ground -- \| carry -- \| catch-up -- \| lag 0 f \| feed 5 Hz \| disp 44 Hz` — every unrun stage `--`, not `0.00`. |
| `ui-lost-step3.jpg` | copter / warm / oracle / manual, carry 512, 44.7 m nadir — **first redesign revision** (per-card numbers, bottom verdict bar, PIP) | A failing track read off the panel. `CARLA 29 Hz`, `ORIN carry 9.0 Hz`, `COPTER 45 m` green, **`TRACK lost 14 s` red**, `LOOP open` grey; verdict bar red with `LOST 14s -- no mask, drop and re-follow.  carry 9.0 Hz Orin, lag 0, lock 0/60 (0/73 all)` over `carry 111 ms (9.0 Hz) Orin \| catch-up 6.1 s`. DESIGNATE's own number reads `oracle GT box` (no VLM call to time); telemetry `armed mode 4  alt 44.7 m  gimbal -90/0` / `N 21.3 E 159.0 D -44.7`; the `NEXT` line is back to amber step 3 because the track is gone. Note *why* it is gone, visible in the view: the copter was reused from a previous run and is parked over rooftops with no car under the footprint — the `--alt` gotcha and finding 16's failure mode in one frame. |
| `ui-loop-closed.jpg` | copter / warm / oracle / **auto**, 30 cars, carry 512, 44.6 m nadir | The whole stack working, read off the panel: all five lamps green, `NEXT loop closed -- read the instruments column`, `oracle` / `warm` / `auto` lit in the three segmented switches, green box tight on a `vehicle.nissan.patrol_2021`. Instruments: verdict `carry 9.4 Hz Orin, lag 0, lock 60/60 (207/210 all)`, per-stage `30 cars spawned / 30 Hz render`, `copter 44.6 m AGL`, `oracle GT box`, `0.00 s command to box`, `auto 0.0 m/s`, and the graph with a fully green ribbon, `carry Hz 9 / max 10`, `lag frames 0 / max 18` (the one spike is the seed) and `on target % 100 / max 100`. This is also the frame that fixed the graph: at 0.55 scale the first version drew a full-scale sample straight through its own lane label. |
| `ui-maintained-vs-delivered.jpg` | one 45 m nadir CARLA frame, both overlay states | Left: **maintained** — amber corner brackets, `maintaining: <caption>`, the box the system carries before anyone asked for it. Right: the same target **delivered** — closed green rectangle. The warm-start claim is that the system tracks things it has not been asked about, so this distinction has to survive a glance; it was grey-on-asphalt before. |
| `oracle-lock-45m.jpg` | copter / warm / oracle / auto, 40 cars | The flown view only (`smoke.png`, no panel chrome). The system working: green box tight on a white SUV, captioned `white SUV in the center`, `lock 60/60` (231/234 all). |
| `ui-orin-cost-loaded.jpg` | spectator / cold / vlm / manual, 6 cars, a live on-device carry, with a 45 s CUDA matmul deliberately run alongside it on the Orin | The cost dashboard under real device load, and the P6.6 contamination fingerprint live. `orin 9.31 W  tj 59 C  gpu 100%  ram 7.0/7.8 GB` over `+4.12 W over idle  2.11 J/frame  (P6.6: idle 5.19, carry 10.84 W)` — the second consumer shows up exactly as P6.6 said it would: watts and GPU up, and the carry rate collapsed to `carry 227 ms (4.4 Hz)` against the 6.27 Hz the same configuration measures alone, which then costs `LOST 16s`. Idle, the same two lines read `orin 5.19 W ... +0.00 W over idle  -- J/frame`, matching arm A0's 5.195 W tegrastats median. |
| `vlm-g6-miss-45m.jpg` | copter / warm / **vlm** / auto | Flown view only. G6 in pixels: the grounder boxes a painted road marking beside the car, carry then holds that asphalt perfectly — `0/417`, `DRIFT 82 s`. |

## Follow trace

Added after a manual session where the box drifted off a blue car onto scenery, then
onto a white van, while the verdict read `lock 584/633` — 92%. Two separate lies:
`match_actor` returns *any* vehicle whose projected centre lands in the box (so a van
inside the box read as locked), and the counter was cumulative over the whole follow (so
a few hundred bad frames hid behind the good ones that preceded them).

- **Identity lock.** The target's actor id is adopted at catch-up (`lag<=1`), not at the
  seed — the seed box describes a frame seconds old, so asking at seed time names
  whatever has since driven into that rectangle. Green means *that* actor.
- **Drift flag.** `DRIFT_S = 5.0` s continuously off-target turns the verdict line red and
  writes `drift-<n>.png`.
- **Rolling lock.** `lock <hits>/60` over the last 60 steps, cumulative in parens.
- **Trace.** Every follow writes `<out>/trace-<seed_n>/trace.jsonl`: per step
  `n, box, area_ratio, aspect, actor, actor_type, on_target, lag, lock60`, plus
  `ground / identity / switch / drift / lost / live / bridge_died / end` events. PNGs at
  the seed, at every identity change, and at each drift flag.
- **Reader.** `.venv-ft/bin/python runners/carla_trace.py <trace.jsonl>`. No argument
  runs its self-check.

`area_ratio` is for mask bloat (off the car onto a billboard); `drift` + `switch` are for
the track ending up on another vehicle.

Not done: nothing re-grounds. A drifted track stays drifted until the operator drops and
re-follows — the flag says so rather than fixing it, and AUTO keeps steering on a flagged
box. That is deliberate: an automatic re-ground would hide the failure the panel exists
to show.

## Hot reload

`r` + Enter in the launching terminal re-execs the script and leaves CARLA running.
`q` + Enter quits normally (kills the server if this process started it). Booting
CARLA costs 10-30 s plus one round-trip per spawned car, and none of that is what
you are editing.

Five things it has to get right, all in `reload_argv` / `unpause_on_exit`:

- **`--auto-spawn 0` is forced.** The old cars live in the server, not in the UI, so
  respawning would stack another batch on every reload.
- **The camera sensor is destroyed first.** It is an actor, and the server survives.
- **`clear()` is skipped** on this path only — keeping the fleet is the whole point of a
  reload. Every other exit clears (see the leak finding).
- **The server's pgid rides along** in `--adopt-pgid`. `execv` keeps our PID so the
  process group is still ours to signal, but the `Popen` object is gone; without the
  handoff the last exit orphans the server.
- **A paused world is unpaused before the exec**, same as handing it to any other
  client: sync mode with nothing ticking hangs the next connection.

Line-buffered, not raw single-key — cbreak would mean restoring termios on every exit
path including the crashes, to save one keystroke. `tests/test_reload_argv.py` covers
the argv rewrite headless.

## Tests

| what | where | needs |
|---|---|---|
| key→NED signs, **view-relative `wasd` through the real projection**, `_f` missing-vs-zero, maintained-vs-delivered overlay (amber, thick enough, brackets not a closed box) | `tests/test_pilot_modes.py` | nothing (carla egg importable) |
| aim law: pan-not-snap, no overshoot, one correction per frozen box | `tests/test_center_delta.py` | nothing |
| reload argv rewrite | `tests/test_reload_argv.py` | nothing |
| mode switching, AUTO refusing without a copter, `oracle`+caption refusing, spawn determinism, cars actually driving | `carla_debug_ui.py --selftest` | a live CARLA |
| launch/close/relaunch, Ctrl+C exit | `tests/test_carla_lifecycle.py` | `CARLA_LIFECYCLE_TEST=1` + CARLA |

## What this cannot tell you

Manual flying produces impressions, not results. The numbers in "Measured live" are
single runs of a live pipeline — they demonstrate that the stack works end to end at the
altitude and resolution stated, and they are **not** measurements at the repo's n≥25
standard. Specific traps:

- **The green/red box colour is GT-derived** (`match_actor`). "The box was green" and
  "the box sat on the car" are the same statement, not independent confirmation.
- **`designate oracle` puts GT in the seed.** Everything downstream of it is honest, and
  nothing upstream of it is being tested. Read an `oracle` run as a carry+control claim
  only — which is exactly the scope caveat on P6.2-DELIVERY.
- **n=1 per cell.** 231/234 and 0/417 are one run each. The direction is stark enough to
  demonstrate; the rate is not a result. Turning any of this into one means the harness in
  `runners/run_p62_matrix.py`, not this panel.
- **The live COLD number is not E18's.** 10.23 s here vs ~4.85 s there, different
  grounding path, unexplained gap. Do not cite the panel's cold latency.

## Unverified

- **Key handling.** Synthetic key injection is banned in this repo: `xdotool keydown` is
  a global XTEST event and goes to whatever window has focus — it once typed into the
  user's terminal. Verification needs a human at the keyboard. `--smoke` covers the
  designate → deliver → AUTO path by calling the same functions the widgets call.
- **Resize by dragging the frame.** The WM ignores `xdotool windowsize`, so the debounced
  respawn is confirmed only via maximise/restore.
- **Layout fit at any other window size.** No assert catches a rail that overflows
  (finding 13) — `pack()` has no error path for "does not fit", so the only check is
  `ui_shot.py` plus looking. The panel frames are a maximised 2560x1011 window scaled 0.55
  to 1408x556; the rail column is ~915 px tall there and has ~60 px of slack. Those frames
  predate BOTH the graph removal and the +2 font bump (2026-07-26), which move the slack in
  opposite directions — re-shoot `ui_shot.py` and look before trusting the numbers.
- **The carry bridge death** (`rc` now logged, seen once, not reproduced since).
