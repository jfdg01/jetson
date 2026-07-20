# CARLA manual-flight UI — tool + findings

**Status: WORKING (2026-07-20T23:30Z).** Infrastructure for Part VI, not an experiment.
No RQ, no gated result, no `experiments/` campaign — the numbers it can produce are
manual-testing impressions, not measurements (see "What this cannot tell you").

Goal: fly a camera through CARLA like a videogame, then hand the frame to the deployed
grounding stack and watch it follow. Two modes in one window:

1. **Fly** — `wasd`/`qe` to move, arrows to look. You are the drone.
2. **Follow** — type a referring expression ("the red car"), hit `follow`. The frame
   goes to the Jetson VLM, the box goes to the SAM2 carry, and the overlay shows what
   the tracker believes. This is the Part V warm-start select driven by a human-flown
   camera instead of replayed video.

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
