# CARLA manual-flight UI — tool + findings

**Status: WORKING (2026-07-20T23:30Z).** Infrastructure for Part VI, not an experiment.
No RQ, no gated result, no `experiments/` campaign — the numbers it can produce are
manual-testing impressions, not measurements (see "What this cannot tell you").

Goal: fly a camera through CARLA like a videogame, then hand the frame to the deployed
grounding stack and watch it follow. Three things in one window:

1. **Fly** — `wasd`/`qe` to move, arrows to look. You are the drone.
2. **Follow** — type a referring expression ("the red car"), hit `follow`. The frame
   goes to the Jetson VLM, the box goes to the SAM2 carry, and the overlay shows what
   the tracker believes. This is the Part V warm-start select driven by a human-flown
   camera instead of replayed video.
3. **Assist** — `t` or the checkbox. The model gets aim authority and pans the tracked
   object to centre; the operator keeps position and can override the aim at any time.

## What exists

| File | Role |
|---|---|
| `carla_debug_ui.py` | the UI. Auto-starts a headless CARLA if nothing answers on the RPC port. |
| `carla_render.py` | the non-interactive pose-slaved renderer (P6.1). Shares the axis convention, not the code. |

Run it:

```bash
.venv-ft/bin/python runners/carla_debug_ui.py          # starts CARLA if needed
.venv-ft/bin/python runners/carla_debug_ui.py --carla /path/to/CarlaUE4.sh
```

Controls: click either image to take the stick — the green border is the only "am I
flying?" signal. `wasd` ground-plane move along heading, `qe` up/down, arrows tilt/pan,
`pause` freezes the world, `follow`/`drop` start and stop tracking.

## Authority: MANUAL vs ASSIST

Who flies the camera is one flag — the `assist: centre on target` checkbox, or `t`.

- **MANUAL (default).** The operator has sole authority. The model grounds and tracks;
  it draws a box and moves nothing.
- **ASSIST.** The model steers too: it *aims* (`center_delta` pans the tracked box to
  the middle of the frame) and it *closes* (CHASE, below). It never climbs or descends.

Operator input is live in both modes; in ASSIST an arrow key **outranks** aim, and a
held `wasd` outranks CHASE, for as long as it is held (otherwise the two sum and the
view crawls against the input). Assist is inert while paused and whenever there is no
track.

### CHASE: hold the target at a set on-screen size

The only range signal available is the box itself — no depth sensor, no target pose. So
CHASE regulates **apparent size**: `chase_speed(areas)` drives the box area to
`CHASE_TARGET_FRAC` of the frame, flying forward when the target is under size and
backward when it is over. That two-sided setpoint is what makes it a station-keeper
rather than a pursuer: undersized means too few pixels for a re-ground to succeed,
oversized means ordinary relative motion walks the target off the frame edge.

The error is taken in **log area**, because area falls as 1/d² — one log unit is a fixed
ratio of range whether the target is near or far, so a single gain behaves identically at
every distance. Output is `CHASE_GAIN` m/s per log unit, clamped to ±`CHASE_SPEED`.

Motion is along the **boresight**: `boresight(pitch, yaw)` is the direction the camera is
actually looking. The earlier ground frame dropped the pitch to hold altitude, but that
closed *ground* distance rather than *slant range*, so a target below the copter need not
grow at all. Since ASSIST already parks the target at frame centre, the boresight is the
line to the target — flying down it is what makes the box bigger. The cost is that
altitude is no longer held by construction: a nose-down chase descends, and there is no
floor guard yet (`ponytail:` in `boresight`).

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
| `CHASE_GAIN` | 5.0 | m/s per log unit of area error |
| `CHASE_SPEED` | 6.0 | speed cap, both directions |
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

### Two consequences worth flagging

**P6.1's 60 m working altitude is incompatible with grounding at this size.** At 60 m
slant range a car is 36 px long edge / frac 0.0010 — below every knee measured, in
OpenRef's Tiny bucket. Either CHASE descends to ~15–20 m, or grounding goes through an
ROI crop. This bears on P6.2 directly.

**An area setpoint couples standoff to target class.** Same 0.012 holds a truck at 33 m,
a car at 17 m, a motorcycle at 11 m, a pedestrian at 6.3 m. The person-following
literature servos on bbox *height* for exactly this reason. The value here is calibrated
for cars; treat it as such until something needs otherwise.

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
frame, so it always trails a moving target by roughly the carry's own latency. It is a
debug aid, not the P6.2 controller.

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

Deliberately not built: position control (a follow-distance/standoff loop), which is
the P6.2 closed-loop question and belongs in the flight rig, not in a debug panel. This
is the aim half only.

## Design constraints (the non-obvious ones)

**The sim free-runs at its own pace.** This is the whole point: a real camera does not
wait for the model. The renderer is async and paced by wall time, so a 4.5 s VLM acquire
costs 4.5 real seconds of vehicle motion and the delivery lag Parts IV and V exist to
measure still exists. Synchronous mode would make the client the clock master and quietly
delete that lag. See `docs/decisions/part6-flight.md`.

**One camera, two rates.** The operator sees every frame (up to 30 Hz); the Jetson gets
every 6th (5 Hz), always resampled to a fixed 960x540. Two sensors would double the
render cost to show the same pixels, and pinning the Jetson feed means VLM cost and box
pixel coordinates do not move when the window is resized.

**Nothing is drawn into the engine.** Every overlay is cv2-drawn onto a frame *received
from the sensor*. `world.debug.*` would put the box in the world the model is looking at,
which corrupts the view under test. An earlier revision had `unproject()`/`draw_box_2d()`
for exactly that; both are deleted, deliberately.

**No ground truth in the box chain.** `track["box"]` has exactly two writers: the VLM
(`generate` + `parse_bbox`) and `carry.step()`. There is no GT seed oracle. `match_actor()`
reads `world.get_actors()`, but only to colour the box and count locks.

> If a Part VI controller is added, it must key off `track["box"]` and never
> `track["actor"]` — the moment control reads the actor, the loop is GT-driven and every
> number from it is worthless.

**The starting grid is deterministic, the traffic is not.** `spawn_vehicles()` draws from a
private `random.Random(SPAWN_SEED)` over blueprints sorted by id, so the same seed puts the
same 50 models on the same 50 spawn points on every run — verified 3/3 identical plans
(model + point + server-accepted flag) at n=50 on 0.9.16, 2026-07-20T21:05Z. What it does
*not* buy is repeatable driving: the traffic manager's `set_random_device_seed()` cannot be
used here. Calling it while vehicles are batch-registered times out `register_vehicle` after
2000 ms and then aborts the client process with `Responding error from function
set_actor_simulate_physics: Actor could not be found in the registry` — a core dump, not an
exception. Reproduced at both 20 and 50 cars; removing the seed call fixes it. Repeatable
traffic needs synchronous mode, which this rig deliberately does not use (see above).

Two conditions on the determinism: the world must be otherwise empty (an occupied spawn
point is rejected server-side, so re-spawning on top of an old fleet is a different fleet),
and the count must be the same — the draw is sequential, so 30 cars is a prefix of 50, not a
subset chosen the same way. Startup auto-spawns `--auto-spawn` (default 50) on a fresh
server, which is the case that holds.

**Hand cars back to nobody before destroying them.** `clear()` calls `set_autopilot(False)`
on every vehicle and lets a tick land before `DestroyActor`. Without it the traffic manager
keeps stepping an actor that is already gone and the resulting server-side error aborts the
UI process. Same crash as above, reached from the other end.

## Findings (what we learned)

1. **Headless costs nothing here.** The UI reads an attached RGB sensor, never the
   viewport, so `-RenderOffScreen` frees the GPU that SAM2 contends for and changes
   nothing functionally. The spectator has no pixels of its own — attaching a camera to
   it is what makes the flown view grabbable.
2. **Render at display size or it looks broken.** Upscaling a 960x540 sensor into a
   maximised window reads as a "stuck resolution". The camera is respawned at the
   display size on a debounced `<Configure>` (400 ms, snapped to 32 px steps — each
   respawn is a destroy + spawn round-trip). Capped at 1080p30: a 3090 does not have
   more than that spare with SAM2 co-resident.
3. **`sensor_tick` is a request, not a promise.** A GPU-contended sensor quietly ships
   fewer frames. The status line shows *measured* delivery rate, which is the only way
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
   (step 5.3 ms) with the flag set to 30. The rate in the status line is `sensor_tick`
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
    event does not stop the follow thread where it is: it is typically inside a ~200 ms
    `carry.step()` (or a ~4.5 s VLM grounding), and it published its result *after*
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

## What this cannot tell you

Manual flying produces impressions, not results. Two specific traps:

- **The green/red box colour is GT-derived** (`match_actor`). "The box was green" and
  "the box sat on the car" are the same statement, not independent confirmation.
- **The only measured number on this rig is a lock rate of 5/23 (22%)**, taken at
  960x540 on a ~20x22 px distant car. Better-looking manual results at 1080p on near
  targets are plausible on the merits and are *not* in tension with that figure — they
  are simply unmeasured. Turning them into a result means logging
  `(frame_n, box, actor_id, lock)` over a scripted flight at n>=25.

## Unverified

- **Key handling.** Synthetic key injection is banned in this repo: `xdotool keydown` is
  a global XTEST event and goes to whatever window has focus — it once typed into the
  user's terminal. Verification needs a human at the keyboard.
- **Resize by dragging the frame.** The WM ignores `xdotool windowsize`, so the debounced
  respawn is confirmed only via maximise/restore.
