# PART VI SLATE: what to run now that CARLA gives ground truth (rev 2 — 2026-07-21T00:40Z)

Instrument list and work queue for Part VI. Not a pre-registration; each entry is sized so it
*can become* one without further design. Companion to `PART6-PROPOSAL-closed-loop-flight.md`,
which owns Part VI's claim (control coupling).

**Rev 2 supersedes rev 1 after a three-way adversarial review** (thesis-examiner /
ops-realist / pre-mortem lenses, 2026-07-21T00:0Z-00:35Z). Rev 1's structure was wrong in
three ways and its central instrument was unsound. Both are recorded below rather than
quietly fixed, because the corrections are themselves content.

---

## 0. What rev 1 got wrong

**0.1 Numbering collision.** `CLAUDE.md` already commits **P6.2 = closed-loop select-and-follow
vs an oracle-driven no-coupling control**. Rev 1 assigned `P6.2a/b/c` to four diagnostics with
*no vehicle in the loop* and renamed the committed experiment `P6.3`. Corrected: P6.2 keeps its
committed meaning. The diagnostics are unnumbered candidates until one is promoted.

**0.2 Inverted dependency.** `PART6-PROPOSAL:161-163` says of P6.2: "determined by P6.1's
binding constraint. **Do not pre-plan it.**" Rev 1 pre-planned four diagnostics *ahead of* the
experiment whose job is to select among them, and scheduled that experiment last. Corrected:
the diagnostics below are a **toolbox**, selected by P6.2's binding constraint, not a queue.

**0.3 A pre-registered arm was demoted to a setup step.** `docs/questions/part6-flight.md:57`
carries **G6** forward as its own n>=25 arm ("does the deployed Qwen2-VL-2B ground CARLA frames
worse than the 56/56 on Gazebo but better than on UAV123?"). Rev 1's "G-D calibration" was G6
relabelled, stripped of its n, and moved into infrastructure. Corrected: it is G6, it keeps its
sample size, and it needs a pre-registered decision rule (below).

**0.4 A weaker control arm than the committed one.** The proposal specifies arm B as
*oracle projection drives the controller* (`sitl/oracle_bbox.py`). Rev 1 wrote "scripted
trajectory, no controller" — against which A-B confounds coupling with *having a controller at
all*. Corrected: arm B is the oracle-driven controller.

---

## 1. What the new rig gives

**1.1 Identity truth per frame.** `match_actor` names which actor the tracked box sits on;
`actor_box` projects any actor's 3D bounding box to pixels. UAV123 carried one GT box per clip,
so "drifted" and "swapped to another car" were the same observation.

**1.2 Controlled independent variables.** Distractor count, class, colour, separation, speed,
range, altitude, trajectory. Part V measured correlations against whatever UAV123 contained
(P5.2's speed sweep was data-driven for exactly this reason). These are now settable.

**1.3 Two difficulty dials, not one.**

```
carla.MapLayer: Buildings Decals Foliage Ground ParkedVehicles Particles Props StreetLights Walls
world.load_map_layer(...) / world.unload_map_layer(...)          # coarse, whole-layer
world.enable_environment_objects(ids, False)                     # per-object, finer
```

The second was found during review and is the better instrument — see 2.2.

## 2. Findings from the review that change the design

**2.1 The identity instrument was unsound at HEAD, and is fixed only in the working tree.**
`git show HEAD:runners/carla_debug_ui.py:201` matches actors by projecting `v.get_location()`
— a single origin point — into the tracker box. The working tree (+289 uncommitted lines)
replaces this with `actor_box` (all 8 `bounding_box.get_world_vertices()`) and overlap matching
at `MATCH_OVERLAP = 0.30`. **Commit this before it is used for any measurement**; an audit that
silently depends on uncommitted work is not reproducible.

**2.2 `ParkedVehicles` are static meshes, not actors — confirmed by running it.**
`world.get_environment_objects(carla.CityObjectLabel.Car)` returns **29** static meshes
(e.g. `SM_ChargerParked2_38_SM_0`, extent 2.50x1.05x0.77) that are absent from
`get_actors().filter('vehicle.*')`. So `match_actor` returns `None` for a mask that drifts onto
a parked car — it scores as *loss*, not *swap*. They carry a bounding box and a stable id, so
the fix is a fourth taxonomy bucket (~10 lines), and `enable_environment_objects` gives
per-object control, a finer dial than the map layer. **Gate G-B is closed.**

**2.3 Six ways the identity taxonomy comes back confidently wrong.** All verified in the current
working-tree code. Each is silent — the run reads as success.

| # | mechanism | where |
|---|---|---|
| a | `seed_id` never adopted (needs `lag<=1` **and** a match at that instant) -> `on_target` is true for **any** vehicle; `lock60` reads 60/60, taxonomy empty | `:906-911` |
| b | `seed_id` adopted at catch-up (~4.5 s after seed) — if the mask already drifted, the *wrong* car becomes the reference and every later frame scores correct | `:906-907` |
| c | no occlusion or depth test: a vehicle fully behind a building matches on >=0.30 projected overlap | `:232-244` |
| d | overlap is normalized by the **smaller** box, so a bloated box enclosing several cars scores 1.0 for each; `o > best_o` keeps whichever comes first in actor order — arbitrary, not centred | `:240-243` |
| e | a mask collapsed onto a wing mirror sits inside the actor box, scores 1.0, reads as a perfect lock | `:240-242` |
| f | `actor_box` returns `None` unless **all 8** vertices project, so a target close enough to put one vertex behind the camera plane becomes unmatchable and scores as drift — and CHASE drives targets to a fixed apparent size, so this fires hardest in the closed-loop arm | `:214-215` |

Also: `lost` frames never reach `recent.append`, so they are excluded from the `lock60`
denominator (`:896-897` vs `:937`) — a carry that loses the mask half the time still reads
60/60. Structurally identical to P6.0's vacuous "0 track losses".

**Minimum guards before any identity number is trusted:** log `n_inside` (how many actors
overlap the box) on every `step` row; **abort the cell if no `identity` event was emitted**;
count `lost` frames in the lock denominator; add the static-mesh and walker buckets
(`match_actor` filters `vehicle.*`, and the UI spawns walkers).

**2.4 The bloat metric is confounded with CHASE.** `area_ratio > 2.0` is measured against a
fixed `seed_area` while CHASE deliberately grows the box toward `CHASE_TARGET_FRAC`. Ordinary
range closure reads as mask leak.

**2.5 The matched-pairs layer design is weaker than rev 1 assumed.** Unloading a layer is not a
clean clutter ablation: it changes global illumination and auto-exposure, removes *occluders*
(the dominant driver of carry survival), and changes collision geometry so the traffic manager
re-routes — "same seed, same actors" is false in the cell that matters. Worst of all, **the
treatment moves the instrument**: with `Buildings` off there is nothing to occlude, so
`match_actor`'s no-depth-test bias (2.3c) shrinks, and the measured difference includes a change
in measurement error. Per-object `enable_environment_objects` (2.2) avoids most of this and is
the preferred dial.

**2.6 P5.20 already published the taxonomy on the imagery that matters.** 42/42 cells opened by
looking: real-video bloat lands on **empty asphalt**, which is not a removable layer. And P5.19
defines its residual failures as box-on-*neither*-GT — so same-class swaps are a priori near
zero, and asking "what fraction are swaps" leads with a question the prior evidence already
answers.

## 3. Gates

**G-A — GT projection verified by looking.** Project the 8 `bounding_box` vertices; overlay on
>=5 mid-run frames spanning near / far / high-pitch; **Read them**. Assert projected area is
*monotonically decreasing* for a vehicle driving away — an assert that can actually fail, unlike
rev 1's "non-degenerate and inside the frame". Must also exercise 2.3f (near target, vertex
behind camera).

**G-B — CLOSED.** See 2.2. Write it up; add the static-mesh bucket.

**G-C — pairing holds across a toggle.** Byte-identical is the wrong bar (TAA, motion blur and
auto-exposure carry state across frames, so it fails for reasons unrelated to layers and then
gets softened until it stops gating). Instead: measure the **same-config repeat** frame-difference
baseline first, gate on `toggle-restore difference <= same-config difference`, and separately
assert **TM actor positions at frame N are identical** — which is what pairing actually requires.
Requires `synchronous_mode`; see 4.1.

**G6 — grounding calibration (pre-registered, n>=25, NOT a setup step).** Decision rule, fixed
now: sim-select discrimination is *live* iff RG <= 0.85 at a reachable setpoint **and** those
failures are re-ground failures rather than target-not-resolvable failures — otherwise it only
proves small targets are small. Without a pre-registered threshold any outcome confirms the
runner's prior.

## 4. Recorded decisions

**4.1 Sync for the bank, async for flight.** `carla_render.py:40-45` records an explicit choice
*against* `synchronous_mode` for the flight rig: sim time only advances on `world.tick()`, so a
4.5 s VLM acquire would cost zero sim seconds and the delivery lag Parts IV/V exist to measure
would stop existing. That decision stands for flight. The GT bank is **capture, not flight**, so
it runs sync — determinism there is worth more than a lag that no controller consumes. Both
configurations coexist; every result must name which one produced it.

**4.2 `DRIFT_S` is wall-clock** (`time.time()`), so drift durations are not commensurable
between the sync bank and the async flight arms. Report drift in **frames** for the bank.

**4.3 Capture-then-analyze wherever the loop is open.** `select_p56.py` already consumes
`seq_dir.glob("*.jpg")` + a GT dict + `frame_at(idx)`. Dumping a labelled bank lets the
already-debugged Part V analysis run over CARLA frames, and confines CARLA's uptime to minutes
rather than a night. This seam breaks only for genuinely closed-loop arms (P6.2), where camera
pose depends on live tracker output.

## 5. The work queue

### P6.2 (committed) — closed-loop select-and-follow vs oracle-driven no-coupling
Part VI's claim. Arm A: the select drives the controller. Arm B: **oracle projection** drives
the same controller. Paired, n>=25. Fold in the **real-clock latency** measurement (C2) — the
first honest end-to-end wall-clock number for this system, and the only entry that falsifies a
named unfalsified premise. Add **grace precision** as a reported metric: P5.19's 2/4 means that
when the system is wrong it delivers a confident box instead of abstaining, the proposal flags it
as un-attacked, and under closed-loop control a confidently-wrong box is what steers the airframe.

**Blocked on ~6-10 h of extraction:** `follow()` (~160 lines) and `fly()` (~60) live inside Tk
closures in `carla_debug_ui.py` and are driven by `root.after`. The control math
(`center_delta`, `ease`, `chase_speed`, `floor_climb`, `boresight`) is already module-level and
importable headless — only the integration is trapped. **Do not build any unattended step on a
code path that constructs a Tk root** (`--selftest` calls `tk.Tk()`; a detached job has no
display). This is a dedicated session, not a nightly job.

**Design note:** CHASE regulates apparent target size to a setpoint and a scripted camera does
not, so arms must have matched realized size profiles or any carry-survival difference is
explained by target pixel size rather than by coupling.

### Toolbox — promoted only by P6.2's binding constraint
- **identity-truth carry audit** — keep as an *instrument inside* P6.2, not a standalone campaign.
  Its rev-1 motivation (opening P5.19's real-video residual) is not achievable in CARLA (2.6),
  and it needs every guard in 2.3 first. Pre-register a **minimum failure count**, or the
  taxonomy gets reported over n=2.
- **range / size envelope** — cheapest real number on the slate: GT boxes vs pixel area, no VLM,
  no SAM2, no Jetson. Claim is "in CARLA renders, grounding returns a usable box down to X px",
  an **optimistic upper bound**, *not* an operational altitude ceiling. State the input
  resolution it was measured at (interacts with RQ-2.3's resolution ladder).
- **distractor isolation** (same-class vs general clutter) — good science, wrong chapter.
  `PART6-PROPOSAL:195-201`: any perception-robustness claim still requires real video. This is
  **P5.21 on real video**; a CARLA version is a side note, not a gated result.

### Cut
- **bloat-surface naming** — the one bloat surface with real-video evidence is asphalt (2.6),
  which is not a removable layer. It would name a CARLA artefact.
- **another crossing/occlusion bank** — P5.13 and P5.17 closed that lever.
- **weather/lighting as a gating arm** — sim-gap makes an absolute number unclaimable; viable
  only as a mechanism probe, which is a different and more careful framing.
- **`ardupilot_gazebo` lockstep / copter under CARLA physics** — already decided against.

## 6. Tonight

**Build the GT capture bank. No VLM, no SAM2, no Jetson, no closed loop. No experiment claims a
number tonight.**

This drops the two fragile dependencies (Jetson SSH tunnel, SAM2 VRAM), keeps CARLA up for
minutes not hours, and the artifact is the required input for every other candidate — cheapest
thing to lose, largest thing to unblock.

| | step | h |
|---|---|---|
| 0 | commit the `actor_box` fix (2.1); pre-flight: orphan-kill `CarlaUE4`, dedicated RPC port 2100, `df` assert, actor-count assert | 0.5 |
| 1 | capture script from `carla_render.py`: sync mode, per-frame jpg, corner-projected GT for actors **and** the 29 static Car meshes, layer/object flags, seed | 2.0 |
| 2 | **G-A** — overlay GT on >=5 frames spanning near/far/high-pitch, **open them**, assert monotonic area | 0.25 |
| 3 | **G-B** — closed already (2.2); write it up | 0.1 |
| 4 | capture bank: 25 clips x 60 s (sync runs faster than real time) | 1.0 |
| 5 | **G-C** — re-capture 3 clips after a toggle; same-config baseline + TM position identity | 0.5 |
| | **total** | **~4.4** |

Morning artifact: a deterministic CARLA GT bank, three gate verdicts, and viewed overlay frames
proving the projection is not another sign error.

**Operational guards** (each is a measured failure mode, not a hypothetical):
- **Dirty world.** `ensure_carla` adopts any server answering on the port and returns
  `proc=None`, so `stop_carla` will not clean it — and `SPAWN_SEED` determinism holds *only on a
  fresh world* (occupied spawn points are rejected server-side and silently drop cars). Adopting
  a live world voids every paired comparison. Dedicated port + actor-count assert + abort.
- **Disk.** Measured: `runs/carla-ui/trace-138` = 410 carry steps -> 64 MB, ~2.8 GB/h of
  following; the switch-PNG path fires on every actor-id change, so a box flickering between ids
  at 5 Hz is ~6x that (~19 GB/h). 72 GB free at 83%. Cap PNGs per trace (~60), count the rest in
  the jsonl, abort under 10 GB.
- **Jetson canary** (for later arms that use it). If the `ssh -N -L` tunnel dies mid-sweep every
  subsequent `generate` returns nothing and the run produces a full set of NO_MATCH results *that
  look like a scientific finding* — the exact shape of the sky-camera bug. Re-ground one fixed
  reference frame with a known-good caption every N clips; canary fails -> abort loudly.
- **VRAM.** One Epic server only; kill any existing UI+server first (a second server plus
  co-resident SAM2 is tight, a third OOMs). A sweep killed by OOM leaves an 8 GB server that the
  next experiment then adopts.

**Cut from tonight:** everything in section 5. The audit and the envelope become tomorrow's first
jobs and run *on the bank* — by then they are pure-GPU replays over dumped frames with a canary
in front, which is a job worth leaving unattended. P6.2 needs its extraction session first.

**If science tonight is required anyway:** run the **range/size envelope**. GT only — it inherits
none of the Jetson/SAM2/VRAM failure modes and still produces a figure by morning.

**Status:** rev 2, reviewed. Nothing pre-registered yet.
