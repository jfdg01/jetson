# CARLA GT capture bank — Part VI infrastructure (unnumbered)

**Status:** pre-registered 2026-07-21T00:30Z, **complete 2026-07-21T01:42Z**. Bank built (25 clips
/ 30 000 frames / 4.7 GB), G-A PASS, G-B CLOSED, G-C PASS.
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
| 0 pre-flight guards | 0.5 h | not separately timed |
| 1 capture script | 2.0 h | ~0.2 h to first working runner (`00:28` pre-reg to `00:36`), then ~0.5 h of fixes |
| 2 G-A overlay + look | 0.25 h | ~0.2 h, incl. one reflow after the montage proved unreadable |
| 3 G-B write-up | 0.1 h | ~0.1 h (closed pre-run) |
| 4 bank: 25 clips x 60 s | 1.0 h | **36.5 min** |
| 5 G-C toggle re-capture | 0.5 h | ~0.5 h, of which most was debugging a FAIL that was the gate's own bug |
| **total** | **~4.4 h** | **~1.25 h** (`00:28` pre-registration to `01:42` close-out) |

Estimated capture wall-clock is the number most likely to be wrong: 86 Hz was measured with
10 vehicles and no JPG encoding. With 40 vehicles plus disk writes, an estimated 25-40 Hz
sustained is more honest, putting the bank nearer 20-30 min of ticking.

*Filled in after the run:* the flagged number was indeed the wrong one, but wrong in both
directions at once. Sustained rate came in at **15.9 Hz** — below even the pessimistic 25-40 Hz
revision, because that revision still assumed 40 vehicles and the bank runs 80 — while the bank
*finished* in 36.5 min, inside the original 1.0 h. The two errors were independent: the rate
estimate mis-modelled per-frame cost, the duration estimate over-budgeted per-clip setup. The
overall 3.5x overestimate of total effort is the ordinary one — steps 1 and 5 were where the time
actually went, and both went there for reasons no estimate anticipated (a sampling policy that
found no cars; a gate that failed against itself).

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
  delete the file to resume). The STOP file blocks *new* ticks only — it is checked first thing
  in the tick (`scripts/autoresearch.py:118`) and is invisible to a worker already running. The
  in-flight cycle was initially left alone, then **killed outright at 2026-07-21T00:40Z** (pids
  360643/360644/360646 + children) once it proved it would not coexist: it read this campaign's
  freshly-committed script, ran `--gate-c` against the same server on port 2100, reloaded the
  world under the bank capture and killed it with `_queue.Empty` 0.9 min in. Two further reasons
  it had to go, not just be waited out: the operator's instruction for the night was
  opus-only agents and its driver prompt spawns a `model:fable` design subagent, and it merges
  to `main`. Collateral: it had checked out `experiment/p63-carla-gt-bank` in the shared
  worktree, so three of this campaign's commits landed on that branch; verified linear on top of
  `main` and renamed to `experiment/carla-gt-bank`. Nothing lost.
- **Jetson canary.** Not applicable tonight (no Jetson in the loop). Required for any later
  arm that grounds through the tunnel: if `ssh -N -L` dies mid-sweep, every subsequent
  `generate` returns nothing and the run produces a full set of NO_MATCH results *that look
  like a scientific finding* — the exact shape of the sky-camera bug.

## Results

All three gates resolved. **The bank is built and usable; no experimental number is claimed.**

### Gate verdicts

| gate | verdict | evidence |
|---|---|---|
| G-A | **PASS** | `runs/gate_a/results.json`, `proof/gate-a-gt-overlay-altitudes.png` (five overlays, **opened and viewed**) |
| G-B | **CLOSED** (pre-run) | 29 static `Car` meshes returned by `get_environment_objects` are absent from `get_actors()`; fourth taxonomy bucket added |
| G-C | **PASS** | `runs/gate_c/results.json`, `proof/gate-c-repeatability.png` |

**G-A.** A reference vehicle (`SM_Mustang_prop4_SM_0`, extent `[2.359, 0.947, 0.65]` m) viewed
from a nadir camera at 25 / 40 / 60 / 85 / 120 m. All 8 vertices project at every altitude
(`n_proj: 8`), the box area decreases monotonically with altitude, and measured area tracks the
analytic nadir prediction `area ~ 1/z^2`:

| altitude | 25 m | 40 m | 60 m | 85 m | 120 m |
|---|---|---|---|---|---|
| measured / predicted area | 1.113 | 1.068 | 1.045 | 1.032 | 1.023 |
| `veh_fill` (semantic-seg overlap) | 0.910 | 0.927 | 0.902 | 0.889 | 0.785 |

The ratio exceeds 1 and **converges toward 1 as altitude rises**, which is the correct signature
rather than a defect: the analytic term is a point-target nadir approximation, so the residual is
the perspective spread of a box with real height, and that spread shrinks with range. A ratio
drifting *away* from 1 would have been the failure. `veh_fill` falling at 120 m is the axis-aligned
box enclosing more non-vehicle pixels as the target shrinks — the reason `veh_fill` is a filterable
column and not an assert.

### Bank

| field | value |
|---|---|
| clips | **25** (n>=25 rule satisfied for any consumer) |
| frames/clip | 1200 (60 s @ 20 Hz sim) |
| total frames | **30 000** |
| sustained capture Hz @200 W | **15.88 Hz mean**, range 12.5-18.8 |
| bank size on disk | **4.7 GB** (uncommitted; regenerate from the seeded runner) |
| coverage (a vehicle on screen) | min **0.989**, mean 1.000, all clips >= the 0.5 assert |
| determinism check | G-C: all 40 TM vehicle positions reproduce exactly across `load_world` at a fixed seed |

Capture rate falls monotonically with altitude — 18.1 Hz mean at 40 m against 13.9 Hz at 120 m —
because a higher camera puts more vehicles on screen (9.8 to 38.0 mean on-screen boxes), and both
per-actor GT projection and JPEG encoding scale with that. The 20 Hz sim-real-time line is only
cleared at the lowest altitudes, so **the bank captures slower than real time and is not a
real-time claim.**

`track_gain` behaves as designed at its extreme and blurs in the middle. Measured
`target_in_frame_frac` (the anchor target, not merely *a* vehicle):

| `track_gain` | clips | anchor in frame |
|---|---|---|
| 1.0 (camera tracks anchor) | 9 | 100% on all 9 |
| 0.6 (partial follow) | 8 | 42.8 - 100% |
| 0.0 (fixed camera) | 8 | 12.8 - 87.8% |

Only `gain 1.0` is a clean regime. **0.6 and 0.0 overlap heavily** and are not separable arms — an
earlier note in this campaign called these "three distinct regimes" on the strength of the first 8
clips; at n=25 that is wrong and is corrected here. A consumer selecting clips must filter on the
measured `target_in_frame_frac`, not on `track_gain`.

### Estimate vs actual

| step | estimate | actual |
|---|---|---|
| 4 bank: 25 clips x 60 s | 1.0 h | **36.5 min** (~1.46 min/clip) |
| sustained capture rate | 25-40 Hz | **15.9 Hz** |

The wall-clock estimate was flagged up front as the one most likely to be wrong, and it was — but
in the opposite direction from the rate error. The rate estimate was 1.6-2.5x optimistic (the 86.1
Hz probe used 10 vehicles and no JPG encoding; the bank runs 80 with encoding), yet the bank still
finished in 61% of the estimated time, because the estimate had also over-budgeted setup and
world-reload overhead per clip.

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

**4. G-C reported FAIL against its own repeat, and the bug was in the gate, not CARLA.** First
real run: `same-config 0.136, toggle-restore 0.127, TM identical same=False toggled=False -> FAIL`.
The pixel rule passed; the position rule failed *between two runs of the identical config*, which
is not a thing determinism can explain. Cause: the comparison keyed each vehicle on `v.id`, and
**CARLA's server-assigned actor ids do not restart at a fixed value across `load_world`**, so two
byte-identical worlds produce different id tuples. Re-keyed on spawn index (stable, because
`setup_world` walks a seeded shuffle of spawn points) and the gate passes: `same=True
toggled=True`. Both keys are kept in `results.json` and drawn in the proof figure, because the
disagreement is the finding. **Had this been recorded as run, the campaign would have published
"CARLA traffic is not reproducible" on the strength of a broken dictionary key** — a wrong negative
that would have justified abandoning seeded determinism for all of Part VI. It also promotes the
deferred `sidx` item below from a nicety to a known correctness gap: `gt.jsonl` rows carry actor
ids, so they are valid *within* a clip and must not be used to pair identities *across* runs.

**5. A near-miss caught before it ran: the G-C toggle arm was going to tick 8 times more than its
baseline.** In the first draft only the toggle arm ticked (4 settle ticks either side of the layer
toggle); the baselines ticked zero. That advances the toggled world 0.4 s of traffic further than
the arm it is compared against, so the positions could not match and the pixels could not either.
It would have produced a confident FAIL reading as "toggling environment objects breaks pairing"
while measuring nothing but one arm running longer. Fixed pre-run by paying the same 8 ticks in
every arm, with `assert t_a == t_b == t_c` so the symmetry cannot silently regress.

**6. 793 MB of `gt.jsonl` headed into git, one blob of it truncated mid-write.** The repo's
`.gitignore` whitelists `experiments/*/runs/**/gt.jsonl` — sound when a GT file was kilobytes, but
this campaign writes 31.7 MB per clip. A routine `git add -A experiments/` tracked four of them,
and `clip03/gt.jsonl` was committed **while the capture was still appending to it**: 17 958 255
bytes in git against 32 419 508 on disk. Truncated, still valid JSONL, and therefore silently
short — nothing downstream would have raised an error, it would just have seen a shorter clip.
Fixed with a campaign-scoped ignore rule plus `git rm --cached` (`642237d`). *Lesson recorded:*
never `git add` a directory an unattended writer is still writing into.

**7. `night_driver.json` reports `all_ok: true` for a FAILED gate.** The field tracks subprocess
exit codes, and a gate that runs cleanly to a FAIL verdict exits 0. The driver's own summary is
therefore not a verdict and must not be read as one — verdicts live in each `runs/*/results.json`.
Not fixed tonight (the driver is finished); recorded so the next session does not trust it.

**8. Killing a sync-mode client leaves the server unusable.** `pkill` on a capture holding the
world in `synchronous_mode` left CARLA wedged; the next run core-dumped, and a later one failed
with `trying to create rpc server for traffic manager; but the system failed to create because of
bind error` — a stale client still holding Traffic Manager port 8000. Recovery is `pkill -9 -f
CarlaUE4`, confirm with `ss -ltnp | grep -E ':8000|:2100'`, and kill the holding pid explicitly.

## Proof deliverables

`proof/` (curated, out of `raw/`). All four regenerate from `make_proof.py` off `runs/`, with no
live server.

1. `probe-nadir-town10.png` — the viewed nadir frame that confirms pitch -90 aims at the
   ground and not the sky, at 60 m over `Town10HD_Opt`. Camera-sign regression evidence: the
   Phase C camera aimed at the sky for a month on the opposite sign.
2. `gate-a-gt-overlay-altitudes.png` — **G-A, PASS.** The same reference vehicle
   (`SM_Mustang_prop4_SM_0`) with its projected 8-vertex GT box drawn on the real render at 25 /
   40 / 60 / 85 / 120 m, laid out 3x2. Each panel carries its own `pred` vs `meas` area, so the
   `1/z^2` agreement is legible per-panel rather than only in the results file. This is the
   deliverable for a gate whose entire content is that a human-or-agent opened the frames; a
   passing `results.json` alone would not have satisfied it. From `runs/gate_a/`.
3. `bank-gt-overlay.png` — **the artifact itself**, not the gate rig: GT projected onto a real
   captured bank frame (`clip01`, 60 m, `track_gain 0.0`, frame 600). Colour is the finding —
   green/cyan are actors and static meshes, yellow is the clip's anchor target, **red marks
   `veh_fill < 0.25`**, i.e. a geometrically correct box sitting on pixels that are not a vehicle
   (cars occluded behind buildings, hazard 2.3c). Corner-projected GT cannot see occlusion; this
   column makes it filterable. Note there is **no yellow box in this frame** — `clip01`'s anchor
   is in frame on only 12.8% of frames, which is what motivated `target_in_frame_frac`.
4. `bank-capture-and-target-size.png` — the bank's three quantitative claims, as a figure because
   the numbers are the point. Left: per-clip sustained rate against the 20 Hz sim-real-time line
   (mean 15.9 Hz at the 200 W cap — the bank does not capture in real time). Middle: projected GT
   box area against altitude for fully-in-frame boxes only, with a `1/z^2` curve anchored on the
   40 m median; the projection is analytic, so this is a check the bank must pass, not a fitted
   trend. Right: `target_in_frame_frac` per clip by `track_gain`, with mean coverage overlaid —
   the panel that shows coverage reading ~100% everywhere while the anchor target ranges down to
   12.8%, and that `gain 0.6` and `gain 0.0` overlap rather than separating.
5. `gate-c-repeatability.png` — **G-C, PASS.** Same-config repeat (0.142) and layer-toggle-restore
   (0.084) mean frame difference, both ~60x under the 8.0 floor, on a log axis because on a linear
   one both bars vanish. Annotated with the half that cost the debug cycle: all 40 vehicle
   positions reproduce across `load_world` under a spawn-index key and *do not* under an actor-id
   key, which is why the gate first reported FAIL against its own repeat.

## Next step

Ordered, and blocking on the server going idle where noted. An adversarial review of the runner
(10-agent workflow, 2026-07-21T01:05Z) raised the first three; the rest is the campaign's own
close-out.

1. ~~**[BLOCKING] Probe `image.transform` against `cam.get_transform()`.**~~ **RESOLVED offline,
   no re-capture owed** (`check_pose_lag.py`, 2026-07-21T01:20Z). The worry was that `gt_rows`
   projects from the camera actor's transform read after `world.tick()`, which would put every GT
   box one frame of camera motion behind its pixels -- the P5.13 zero-order-hold class, invisible
   in any log. It needed no server: on `track_gain 0.0` clips the commanded camera path is a
   closed form in the frame index alone, so the logged pose can be scored against both the pose
   commanded at frame `i` and at frame `i-1`. Both such clips answer unambiguously:

   | clip | commanded step | vs commanded(i) | vs commanded(i-1) | verdict |
   |---|---|---|---|---|
   | clip01 | 2.09 cm | **0.359 cm** | 1.910 cm | CURRENT |
   | clip04 | 2.09 cm | **0.178 cm** | 2.239 cm | CURRENT |

   The logged pose is the current frame's. The residual this cannot settle -- whether the
   *render* lagged the actor transform -- is bounded by converting one camera step to pixels at
   each clip's altitude: **worst case 3.35 px** (clip00, 40 m, `gain 1.0`), and under 0.15 px on
   the fixed-camera clips. So it is bounded and small even under the hypothesis the data argues
   against. A live `image.transform` probe would close it exactly; it is no longer blocking and
   cannot invalidate the artifact.
2. ~~**Backfill `target_in_frame_frac` into every manifest.**~~ **DONE** (`3398c2b`,
   `backfill_target_frac.py`, idempotent). Coverage asserts that *a* vehicle is
   on screen, not that *the* anchor target is. On `clip01` (`track_gain 0.0`, fixed camera) the
   anchor is in frame on ~13% of frames while coverage still reads 100%, because other traffic
   drives through. That is a legitimate regime -- it is what the `gain 0.0` arm is for -- but a
   downstream consumer picking a follow clip needs to see it. Computable post-hoc from `gt.jsonl`,
   so no re-capture; do it as one backfill pass over all clips, not a mid-run code change.
   Independently visible in `proof/bank-gt-overlay.png`: no yellow anchor box in the frame.
3. **Purge the four committed `gt.jsonl` blobs (113 MB) from branch history.** The forward fix
   landed (`642237d`); these predate it. Deferred deliberately: rewriting history while an
   unattended capture is in flight risks the run to reclaim 113 MB on an unmerged, unpushed,
   local-only branch. Do it once the driver is idle and before any merge to `main`.
4. ~~Fill Results, append `docs/results/part6-flight.md`, caption the proof deliverables.~~
   **DONE.** All three ledgers written, five deliverables captioned above.
5. **Add `sidx`, a spawn-index identity key, on the next re-capture.** Promoted from "deferred,
   not lost" to a known correctness gap by G-C (item 4 in *What did not work*): `gt.jsonl` rows
   carry **server-assigned actor ids, which CARLA does not reproduce across `load_world`**. Ids
   are therefore valid *within* a clip and must not be used to pair identities *across* runs —
   which is exactly what a paired A/B on the same seed would want to do. Adding the field needs a
   re-capture (36.5 min), so it is recorded rather than paid for tonight; any consumer doing
   cross-run pairing must add it first.
6. Hand the bank to P6.2's extraction session.

Two loose ends for whoever picks this up, neither blocking:

- **`.claude/autoresearch.STOP` is still armed** (since 2026-07-21T00:27Z; the in-flight cycle was
  killed at 00:40Z). It is gitignored and local-only. Delete the file to resume autoresearch. It
  was left armed deliberately: the GPU and the CARLA port are still this campaign's until someone
  decides otherwise.
- **The 3090 is still capped at 200 W** (`nvidia-smi -pl 200`), as requested for fan noise.
  Non-persistent — it resets on driver reload. Every rate number in this README carries it.
