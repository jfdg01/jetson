# CARLA debug UI — findings and incident history

*Split out of `CARLA_DEBUG_UI.md` on 2026-07-26: that file is the usage/reference doc
(switches, layout, authority modes, design constraints), this one is what went wrong and
what it taught. **The finding numbers are unchanged and must never be renumbered** — they
are cited from `runners/sitl_fly_leg.py` and `docs/decisions/part6-flight.md`.*

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

