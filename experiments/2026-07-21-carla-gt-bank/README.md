# CARLA GT capture bank — Part VI infrastructure (unnumbered)

**Status:** pre-registered 2026-07-21T00:30Z, run in progress.
**Claims no experimental number.** This is the artifact-producing night described in
`experiments/PART6-SLATE-carla-gt.md` section 6: build a deterministic CARLA ground-truth
bank, verify three gates, and stop. No VLM, no SAM2, no Jetson, no closed loop.

## Why this is unnumbered

Rev 1 of the slate assigned `P6.2a/b/c` to a set of no-vehicle diagnostics and pushed the
committed `P6.2` (closed-loop select-and-follow vs oracle-driven control) out to `P6.3`.
That was one of three structural errors the slate's own review caught (`PART6-SLATE:16-19`).
**P6.2 keeps its committed meaning.** This campaign is infrastructure feeding it, so it takes
no `P<part>.<n>` id — consistent with the slate's ruling that the diagnostics are "unnumbered
candidates until one is promoted".

## Context and restrictions

The bank exists because CARLA gives what UAV123 never could: **per-frame identity truth**.
UAV123 carried one GT box per clip, so "the box drifted off the target" and "the box swapped
to a different car" were literally the same observation (`PART6-SLATE:41-43`). With
`actor_box` projecting any actor's 3D bounding box to pixels, a drifted box can be named.

Restrictions honoured tonight, each a recorded decision rather than a preference:

- **Sync for the bank, async for flight** (`PART6-SLATE:141-146`). `carla_render.py:40-45`
  records an explicit choice *against* `synchronous_mode` for the flight rig: sim time only
  advances on `world.tick()`, so a 4.5 s VLM acquire would cost zero sim seconds and the
  delivery lag Parts IV/V exist to measure would stop existing. That stands for flight. The
  bank is **capture, not flight** — no controller consumes the lag — so it runs sync and buys
  determinism instead. Both configurations coexist; **every result names which produced it.**
- **Drift is reported in frames, not seconds** (`PART6-SLATE:148-149`). `DRIFT_S` is
  wall-clock (`time.time()`), so durations are not commensurable between the sync bank and the
  async flight arms.
- **No Tk.** `carla_debug_ui.py --selftest` constructs a `tk.Tk()` root and a detached job has
  no display (`PART6-SLATE:170-172`). The bank imports only module-level helpers.
- **No number is claimed.** Gate verdicts are not results.

## Hardware and software config

| item | value |
|---|---|
| GPU | RTX 3090, **power limit 200 W** (default 350 W; capped at user request for fan noise) |
| persistence mode | Disabled — `nvidia-smi -pm 1` needs an interactive password, so the runner re-asserts `-pl 200` per clip |
| CARLA | 0.9.16, server and client both, `Town10HD_Opt` |
| launch | `-RenderOffScreen -quality-level=Epic -carla-rpc-port=2100 -ExecCmds="t.MaxFPS 30"` |
| RPC port | **2100**, not the default 2000 — a dedicated port so `ensure_carla` cannot adopt a stranger's world |
| camera | 640x480, FOV 90, nadir (pitch -90, confirmed by a viewed frame) |
| venv | `.venv-ft` |
| date | 2026-07-21 |
| clips | 25 x 60 s at `fixed_delta_seconds` 0.05 (20 Hz sim) = 1200 frames each |
| traffic | 80 autopilot vehicles, `tm.set_random_device_seed(seed)`, 29 static `Car` meshes |
| camera plan | anchored on a spawned vehicle (`target_rank`), `track_gain` 0.0 / 0.6 / 1.0, bounded drift `drift_m` 0 / 25 / 50 m over the clip, altitude swept 40-120 m |
| detachment | `setsid nohup runners/night_driver.py`, per-step retries, resumable (a clip with a complete manifest is skipped) |

**The 200 W cap is part of every rate number below.** CARLA at Epic alone draws 172 W against
that 200 W ceiling, so the cap is binding, not decorative.

## Live-server probes (done, committed `2d0917a`)

Four API questions could not be settled from source, and each silently produces a well-formed
wrong answer if guessed. `runners/carla_probe_gt.py` settled them against a live server;
raw output in `runs/probe/results.json`.

| question | answer | why it mattered |
|---|---|---|
| Is `EnvironmentObject.bounding_box` world- or local-space? | **WORLD** | Vertices come from `get_world_vertices(carla.Transform())` — the *identity*. Passing the object's own transform **doubles** its coordinates (`-51,166` becomes `-102,333`), placing all 29 parked-car boxes somewhere plausible but wrong. Actors are the opposite case: their box is local (`bbox_loc ~ [0,0,0.7]`) and does take `get_transform()`. **The two buckets need different calls.** |
| Does the sync-mode image match its tick? | **yes, delta 0 on 40/40** | An off-by-one would make every GT box one frame stale — the exact defect P5.13 was charged with, and invisible in any log. |
| Sync capture rate at 200 W | **86.1 Hz** (10 vehicles, Epic, 640x480) | 25 clips x 60 s x 20 Hz = 30 000 ticks. At 86 Hz that is ~6 min of ticking, so the slate's 1.0 h estimate has real headroom even with 40 vehicles and JPG encoding. |
| Any occlusion test in 0.9.16? | **`world.cast_ray` exists**, returns labelled hits | `PART6-SLATE:84` lists "no occlusion or depth test" as hazard 2.3c. It is buildable, not merely deferrable. |

## Gates (pre-registered, verbatim rules from the slate)

**G-A — GT projection verified by looking.** Project the 8 `bounding_box` vertices; overlay on
>=5 mid-run frames spanning near / far / high-pitch; **Read them**. Assert projected area is
*monotonically decreasing* for a vehicle driving away — an assert that can actually fail,
unlike rev 1's "non-degenerate and inside the frame". Must also exercise hazard 2.3f (near
target, one vertex behind the camera plane, `actor_box` returns `None`).

**G-B — CLOSED before the run.** `world.get_environment_objects(carla.CityObjectLabel.Car)`
returns 29 static meshes absent from `get_actors().filter('vehicle.*')`, so a mask drifting
onto a parked car scores as *loss*, not *swap*. Verdict recorded, fourth taxonomy bucket added.

**G-C — pairing holds across a toggle.** Byte-identical is the wrong bar: TAA, motion blur and
auto-exposure carry state across frames, so it fails for reasons unrelated to layers and then
gets softened until it stops gating. Instead: measure the **same-config repeat**
frame-difference baseline first, gate on `toggle-restore difference <= same-config difference`,
and separately assert **TM actor positions at frame N are identical**.

**Not tonight: G6** (grounding calibration, n>=25) — needs the Jetson and the deployed VLM,
both excluded. Its decision rule stays as pre-registered in `PART6-SLATE:133-137`.

## Estimates (up front, marked as estimates)

| step | estimate | actual |
|---|---|---|
| 0 pre-flight guards | 0.5 h | see Results |
| 1 capture script | 2.0 h | |
| 2 G-A overlay + look | 0.25 h | |
| 3 G-B write-up | 0.1 h | |
| 4 bank: 25 clips x 60 s | 1.0 h | |
| 5 G-C toggle re-capture | 0.5 h | |
| **total** | **~4.4 h** | |

Estimated capture wall-clock is the number most likely to be wrong: 86 Hz was measured with
10 vehicles and no JPG encoding. With 40 vehicles plus disk writes, an estimated 25-40 Hz
sustained is more honest, putting the bank nearer 20-30 min of ticking.

## Operational guards

Each is a measured failure mode from this repo, not a hypothetical.

- **Dirty world.** `ensure_carla` adopts any server answering on the port and returns
  `proc=None`, so `stop_carla` will not clean it — and spawn-seed determinism holds *only on a
  fresh world*, because occupied spawn points are rejected server-side and silently drop cars.
  Adopting a live world voids every paired comparison. Guard: dedicated port 2100 +
  actor-count assert + abort.
- **Disk.** Measured: `runs/carla-ui/trace-138` = 410 carry steps to 64 MB, ~2.8 GB/h of
  following, and the switch-PNG path can push that to ~19 GB/h. 72 GB free at 83%. Guard: cap
  frames per clip, abort under 10 GB.
- **VRAM.** One Epic server only. Measured tonight: CARLA alone holds 6.6 GB of 24 GB. A
  second server plus co-resident SAM2 is tight; a third OOMs, and a sweep killed by OOM leaves
  an 8 GB server that the next experiment then adopts.
- **Autoresearch collision.** The `*/10` autoresearch cron was live tonight with a deadline of
  2026-07-22T10:00 and no STOP file, and cycle pid 360646 was mid-flight at 00:27. Two
  autonomous drivers cannot share one GPU and one CARLA server, and it merges to `main`.
  Guard: `.claude/autoresearch.STOP` armed at 2026-07-21T00:27Z (gitignored, local-only;
  delete the file to resume). The in-flight cycle was left to finish rather than corrupt its
  branch.
- **Jetson canary.** Not applicable tonight (no Jetson in the loop). Required for any later
  arm that grounds through the tunnel: if `ssh -N -L` dies mid-sweep, every subsequent
  `generate` returns nothing and the run produces a full set of NO_MATCH results *that look
  like a scientific finding* — the exact shape of the sky-camera bug.

## Results (TBD)

### Gate verdicts

| gate | verdict | evidence |
|---|---|---|
| G-A | TBD | |
| G-B | TBD | |
| G-C | TBD | |

### Bank

| field | value |
|---|---|
| clips | TBD |
| frames/clip | TBD |
| sustained capture Hz @200 W | TBD |
| bank size on disk | TBD |
| determinism check | TBD |

### What did not work

**1. Uniform random camera placement produced a bank with no targets in it.** The first
`clip_plan` sampled the camera at `n0, e0 ~ U(-60, 60)` and swept altitude. It captured clips that
passed every check in place at the time — 1200 frames each, `dominant_frac` 0.002, mid frame not
identical to last, exactly 40 vehicle ids and 29 environment ids, 30 Hz — and **77-80% of frames
contained no on-screen vehicle at all**:

| clip | alt | on-screen mean | frames with zero targets |
|---|---|---|---|
| clip00 | 40 m | 0.67 | 916/1200 |
| clip01 | 60 m | 2.35 | 926/1200 |
| clip02 | 80 m | 2.31 | 959/1200 |
| clip03 | 100 m | 25.45 | 0/1200 |

A nadir camera dropped at a random point over a city sees rooftops; Town10's traffic lives on a
thin road network, and clip03 was simply lucky. Nothing in any log said so. It was found by
overlaying `gt.jsonl` on a captured frame and looking at it, which is the rule working as
intended — and the earlier G-A gate did not catch it, because G-A deliberately points the camera
at a known reference car and so is blind to whether the *sampling policy* finds cars.

Fixed by anchoring each clip on a spawned vehicle (`target_rank`), which puts targets in frame by
construction and is also the geometry P6.2 needs: a copter above the car it is following.
`track_gain` sweeps 0.0 / 0.6 / 1.0 so the target sits still in frame, drifts across it, or is
tracked. Vehicles raised 40 to 80. **Coverage is now measured per clip and asserted `>= 0.5`** —
the check that was missing, now impossible to omit silently.

**2. Expressing camera drift as a velocity did not survive a change of clip length.** The first fix
kept a `speed` in m/s. At 8 m/s a 20 s smoke test drifts 160 m and looks fine; the real 60 s clip
drifts 480 m and walks the camera off a ~400 m map. clip00 came back at 22.8% coverage and the new
assert caught it. Drift is now a **total displacement in metres** over the clip (`drift_m`,
0/25/50), so it is bounded by construction and independent of clip length. *Lesson recorded:* a
smoke test that shortens the run does not exercise anything that accumulates with time.

**3. Two agents, one GPU.** Covered in DECISIONS: the in-flight autoresearch cycle read this
campaign's freshly-committed script and ran `--gate-c` against the same server, killing the bank
capture 0.9 min in with `_queue.Empty`. A STOP file that blocks new ticks is not isolation from a
worker already running.

**4. Killing a sync-mode client leaves the server unusable.** `pkill` on a capture holding the
world in `synchronous_mode` left CARLA wedged; the next run core-dumped, and a later one failed
with `trying to create rpc server for traffic manager; but the system failed to create because of
bind error` — a stale client still holding Traffic Manager port 8000. Recovery is `pkill -9 -f
CarlaUE4`, confirm with `ss -ltnp | grep -E ':8000|:2100'`, and kill the holding pid explicitly.

## Proof deliverables

`proof/` (curated, out of `raw/`):

1. `probe-nadir-town10.png` — the viewed nadir frame that confirms pitch -90 aims at the
   ground and not the sky, at 60 m over `Town10HD_Opt`. Camera-sign regression evidence: the
   Phase C camera aimed at the sky for a month on the opposite sign.
2. TBD — G-A overlay montage (GT boxes on real frames, near/far/high-pitch).
3. TBD — a figure, since the numbers are the point for G-C.

## Next step

Fill Results, append the Part VI ledgers (`docs/results/part6-flight.md`,
`docs/questions/part6-flight.md`, `docs/decisions/part6-flight.md`), cut the remaining proof
deliverables, and hand the bank to P6.2's extraction session.
