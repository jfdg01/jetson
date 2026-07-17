# P5.7 — Simulator scene-generator capability gate (select-arena v1)

**Pre-registered:** 2026-07-17T14:45Z (Madrid wall-clock).
**Status:** RUN 2026-07-17T14:31Z–14:47Z — **RQ-P5.7 = NO [infra FAIL: gz-transport
service flake]**. No gating run reached finalize: `seed101_A` crashed mid-clip twice
(frames 127 and 108 of 240), each on a fresh server session, on a `gz service` CLI
call timing out while the server stayed alive. Per the abort rule (INVALID → re-run
once with a fresh server → fails again → record `infra` FAIL and stop),
`seed202_B` / `seed303_C` / `seed101_D` were **not run**. `verdict_p57.py` prints
INCOMPLETE; V is **uncomputable** (overlays are written at finalize, so none exist).
The render path itself is healthy and the open G4a risk looks *better* than estimated
(108/108 frames byte-identical across two fresh sessions, non-gating) — the sole
blocker is per-frame service-call churn. See Results.
**Branch:** `experiment/sim-scenegen`.
**Division of labour:** design + patches by Fable; **Opus runs the matrix and fills
the Results section only — do NOT re-patch code.** All files under "Committed
artifacts" are already committed. If a run crashes on an infra error, follow the
abort criteria below — never silently re-run a completed cell.

## Research question

**RQ-P5.7:** Can the parked Gazebo Harmonic rig (`runners/sitl/GAZEBO_LIVE_FEED.md`)
be turned into a **deterministic on-demand scene generator** — two same-class
vehicles distinguishable by a stated colour, a UAV-style moving camera, per-frame
ground-truth boxes + stable track IDs dumped next to the frames — meeting ALL of:

- **G1 render-alive** (per run): 0 dead frames (std ≤ 5), 0 byte-identical
  consecutive frames, camera sim-stamps advance by exactly 40 ms every frame.
- **G2 GT-on-vehicle** (per run, both cars): median in-box colour purity ≥ 0.30
  AND ≥ 4× the lateral control-box purity (purity = fraction of pixels matching
  the car's authored colour inside the 12%-shrunk GT box; computed on frames where
  the car is visible with area ≥ 150 px).
- **G3 co-visibility** (per run): both cars visible with bbox area ≥ 150 px in
  ≥ 80% of frames.
- **G4 determinism:** (a) same seed, **fresh server session** → canonical GT
  (sim-stamps excluded) byte-identical AND frames mean |diff| ≤ 2.0 with
  frac(|diff|>8) ≤ 1%; (b) different seeds → frame-0 target positions ≥ 1 m apart
  pairwise.
- **G5 throughput** (per run): ≥ 0.5 generated frames/s wall (240-frame clip in
  ≤ 8 min).
- **V visual gate** (per run, judged by Opus from the dumped PNGs — see "Visual
  verification"): the overlay frames actually show what G1–G3 claim.

**Overall verdict: YES iff G1,G2,G3,G5 pass on all 4 runs AND G4a AND G4b AND V
passes on all 4 runs.** Anything else is NO, with the failing gate named.
`verdict_p57.py` computes G1–G5 mechanically; V can only downgrade its output.

## Context & rationale (audit summary)

**Why this now.** A human steer (2026-07-17T13:55Z, `.claude/loop-focus`)
supersedes the Part V select steer: build a working simulator scene generator so
the select task stops being bound to fixed UAV123 clips. The audit of
P5.3/P5.4/P5.5 supports the premise with one nuance:

- The verdicts are valid — raw `runs/*/results.json` spot-checks match the
  ledgers (e.g. P5.5 `MC_SWAP_car7_460` NO_MATCH max IoU 0.000 as recorded).
- The binding constraint on select is carry↔VLM agreement at the prompt, and **a
  sim does not fix that**. What the sim fixes is that the constraint is currently
  **unmeasurable**: the gating scene set is n=5, so every verdict swings on one
  cell (4/5 vs 3/5); UAV123 distractors have **no GT**, so failure taxonomy rests
  on hand audits that P5.5 itself proved partly wrong (two "caption-bound" cells
  were carry-bound); the P5.5 contact-sheet survey exhausted UAV123 (exactly one
  new usable pair found — scene expansion there is falsified); and the north-star
  phrase ("switch to the blue truck") needs colour-attributed same-class pairs
  UAV123 essentially lacks. A sim authors those scenes on demand with per-frame
  GT for **every** candidate. So: enabling step, honestly labelled — it makes the
  next select fix falsifiable at n>3 instead of directly fixing the VLM.
- **P5.6 (`experiment/direct-delivery-select`, `df6de31`, unrun): PARK, do not
  delete.** Its contract-change hypothesis (deliver the carried track, skip
  prompt-time re-ground) is still the live next lever from P5.5 — but it is
  exactly the n=5-starved test the sim unblocks. Resume it on sim scenes after
  this gate passes; do not run it on the starved UAV123 set.

**Rejected alternative:** running P5.6 as-is on UAV123 now. Loser because a 5-scene
gating set cannot separate its two failure families (shown three cycles running),
and the human steer explicitly redirects to the sim. Recorded in DECISIONS.

**Stale-doc note:** the steer described `experiment/gazebo-live-feed` as unmerged;
it is in fact **merged into main** (`3fe06f5` is an ancestor), and the 1.6 GB
vendored `SITL_Models` assets are present on this box. The parked "custom viewer
vs native GUI" decision is **moot for this campaign**: the generator needs no
viewer at all (headless server + programmatic frames); the MJPEG viewer remains
for humans and is untouched.

**Scope cut (recorded):** an instance-segmentation camera (pixel-perfect GT masks)
is deferred — analytic GT from commanded poses is exact by construction in the
lockstep design, and the colour-purity + visual gates catch projection bugs. If
G2 fails for tightness reasons, segmentation is the next lever, not a redesign.

## Design (what was built — verified by design-time probes, all findings below
were **seen in rendered frames**, per the visual-verification rule)

**Puppeteer lockstep, no physics, no actors.** `gz sim -s` runs the new world
`runners/sitl/worlds/select_arena.sdf` (Sonoma raceway + Sensors/ogre2 + a
25 Hz 1280×720 camera; **`<sky>` removed** — its clouds animate on sim time and
would break cross-session frame determinism). The world starts and stays
**paused**. `runners/scenegen.py` computes every pose (2 cars + camera) in seeded
numpy, pushes them with one batched `set_pose_vector` CLI call, then advances
exactly one camera period with `pause: true, multi_step: 40`. Nothing moves
except by command → every rendered frame shows exactly the commanded state → GT
boxes are pure projection of commanded 3D boxes (no estimation, no sync races).
Frames land via a subscribe-only pybind node (service *requests* over pybind
crash on the GIL — inherited gotcha, still true).

Design-time probe findings (2026-07-17, gz sim 8.14.0, RTX 3090 headless EGL;
frames viewed, not inferred):

1. Plain `multi_step: N` **leaks into free-running** — the sim keeps running
   after the batch (~15 fps realtime observed). `pause: true` must be in the same
   `WorldControl` request. This was the cause of a 463 ms stamp where 134 ms was
   expected.
2. SDF camera **pitch +90° = nadir** (straight down). The `gz_feed_view.py`
   docstring's "-90 = nadir" is wrong for raw quaternions; a −90° probe rendered
   pure sky (`curation/` of the parked doc's sky-race caveat, now explained).
3. **Fuel hatchback textures do not load** under this rig: `map_Kd`/`map_Ka`
   resolve to remote URLs ("Hatchback blue" even points at the *white* model's
   texture); after rewriting both to local paths the body still rendered white
   (`curation/probe_texture_stays_white.png`). A solid `<material>` override in
   the spawn SDF renders reliably (`curation/probe_solid_material_wins.png`) →
   **vehicle colour comes from the SDF material**, deterministic and parametric.
4. Mesh facing: rear faces −x → cars driven with model yaw = heading move
   nose-first (verified from a behind-the-car render).
5. `set_pose` applied while paused is reflected in the **very next** stepped
   frame (teleport probe) — no one-frame staleness.
6. End-to-end design smoke (seed 900, 60 frames, disclosed): 1.46 fps wall,
   purity 0.83 (white) / 0.90 (blue), bg 0.042 / 0.000, both-visible 100%,
   stamps exact, overlays visually verified —
   `curation/smoke900_overlay_f0030.png`, `curation/smoke900_overlay_f0045.png`,
   `curation/smoke900_results.json`. The 0.042 white bg purity (checkered grid
   is legitimately white) is why G2 is a ratio gate, not a hard bg ceiling.

**Scenario archetype (seeded):** two hatchbacks (id 0 `car_white` = target "the
white car", id 1 `car_blue` = distractor "the blue car") drive the Sonoma start
straight (heading 145°) at 2.5–6.5 m/s in opposite lanes with sinusoidal lane
wander; the camera flies behind/above the pair midpoint (standoff 14–22 m, alt
16–26 m, seeded bob/sway/aim-error) — UAV-like following footage. 240 frames
@ 25 fps virtual = 9.6 s clip. GT per frame: camera pose + per car {track id,
name, colour, phrase, 3D pose, projected bbox, px area, visible} → `gt.jsonl`.

## Committed artifacts (Opus: do NOT edit these)

| File | Role |
|---|---|
| `runners/scenegen.py` | the generator: seeded scenario author + gz puppeteer + GT + per-run metrics; `selfcheck` (no gz/GPU) |
| `runners/sitl/worlds/select_arena.sdf` | deterministic arena world (no sky, 25 Hz 720p camera, 1 ms physics) |
| `runners/sitl/models/hatchback_{white,blue,red}/` | vendored Fuel hatchback meshes (OpenRobotics, Fuel; map paths localised; colour comes from spawn SDF, red unused this campaign) |
| `verdict_p57.py` | mechanical verdict from `runs/*` (G1–G5) |
| `make_proof.py` | proof grid + determinism figure + clip copy from `runs/*` |
| `curation/*.png|json` | design-time probe/smoke provenance (see findings above) |

## Run matrix (Opus starts here)

Config: **RTX 3090 workstation only — the Jetson is NOT used** (Gazebo does not
run on it; no on-device claim is part of RQ-P5.7). gz sim 8.14.0 (Harmonic),
Python 3.12.10 / numpy 2.4.4 / opencv 4.13.0 via `.venv-ft`. No power-mode knob
applies (desktop GPU, stock clocks).

4 gating runs, **one fresh server session each** (session-per-run is what makes
G4a *cross-session*): `seed101_A`, `seed202_B`, `seed303_C`, `seed101_D`
(A/D = determinism pair). ~250 MB of PNG frames per run land in `runs/<id>/frames/`
(gitignored; `results.json` is tracked). Nothing clobbers between runs — each run
has its own dir; **never delete a completed run dir.**

Per run (repeat the block for each `SEED`/`RUN` pair 101/seed101_A, 202/seed202_B,
303/seed303_C, 101/seed101_D):

```bash
cd /home/gara/jetson
EXP=experiments/2026-07-17-sim-scenegen
SEED=101 RUN=seed101_A   # <-- change per run

# 0. dirs + no stale server (also kills the design-smoke server if still up)
mkdir -p $EXP/raw $EXP/runs
pkill -f "gz sim" || true; sleep 2

# 1. fresh headless server, nohup'd alone (sandbox reaper kills gz+python combos)
SITL=$PWD/runners/sitl/external/SITL_Models/Gazebo
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json \
GZ_SIM_RESOURCE_PATH="$SITL/models:$SITL/worlds" \
nohup gz sim -s runners/sitl/worlds/select_arena.sdf > $EXP/raw/gz_$RUN.log 2>&1 &
echo $! > $EXP/raw/gz_$RUN.pid

# 2. wait for the camera topic (~15-25 s world load)
for i in $(seq 40); do gz topic -l 2>/dev/null | grep -q uav_cam && break; sleep 3; done
gz topic -l | grep uav_cam   # MUST print the image topic; if empty after 120 s see aborts

# 3. record (background + poll; ~4-5 min; DONE line + results.json when finished)
nohup .venv-ft/bin/python runners/scenegen.py record --seed $SEED --frames 240 \
    --out $EXP/runs/$RUN > $EXP/raw/rec_$RUN.log 2>&1 &
for i in $(seq 90); do test -f $EXP/runs/$RUN/results.json && break; sleep 10; done
tail -5 $EXP/raw/rec_$RUN.log   # expect "[scenegen] DONE ..."

# 4. kill this session's server before the next run
kill $(cat $EXP/raw/gz_$RUN.pid) 2>/dev/null; sleep 2
```

After all 4 runs:

```bash
# mechanical verdict (paste its full output into Results)
.venv-ft/bin/python experiments/2026-07-17-sim-scenegen/verdict_p57.py

# proof deliverables
.venv-ft/bin/python experiments/2026-07-17-sim-scenegen/make_proof.py
```

## Visual verification (gating — Opus MUST do this per the CLAUDE.md rule)

Each run dumps three mid-run GT-overlay PNGs: `runs/<RUN>/overlay_f0060.png`,
`overlay_f0120.png`, `overlay_f0180.png`. **Open all three of every run with the
Read tool** (12 images total) before writing any verdict.

- **PASS looks like:** grey asphalt track surface with yellow lane lines filling
  most of the frame (oblique aerial view; a checkered start-grid strip may pass
  through); **two** cars — one white, one blue, clearly different colours; a green
  GT box **tight on each car** (edges within ~10% of the car silhouette, car
  centred in its box) labelled `id0 white` / `id1 blue`; across f0060→f0120→f0180
  of the same run the cars/grid have visibly moved (camera follows, so look at
  the ground pattern and car spacing, not absolute position).
- **FAIL looks like:** a black or single-colour frame; sky instead of ground;
  only one car, or two cars of the same colour; boxes floating off the vehicles,
  lagging behind them, or wildly over/under-sized; three identical-looking
  frames (dead feed).
- Reference for what PASS should resemble: `curation/smoke900_overlay_f0030.png`.
- Record one line per run in Results ("V: PASS — two colour-distinct cars, boxes
  tight, motion visible" or what was actually seen). **A missing PNG = that run
  is INVALID — never a log-inferred pass.** If V fails on any run, the overall
  verdict is NO even if `verdict_p57.py` prints YES; describe what the frames
  show.

## Verdict rules (mechanical — Opus does not deliberate)

- Run `verdict_p57.py`; its printed table + verdict is the G1–G5 result. Do the
  visual gate V yourself as specified above. **Overall = YES iff verdict_p57
  prints YES AND V passed on all 4 runs.**
- Missing/INVALID runs → verdict INCOMPLETE; re-run an INVALID run **once** with
  a fresh server; if it fails again, record it as `infra` FAIL and stop.
- **Abort criteria:** step 2 finds no topic after 120 s → snapshot the gz log,
  kill the PID, retry once with a fresh server; twice → run INVALID/`infra`.
  Recorder shows no new log line for > 5 min or no `results.json` after 15 min →
  kill both PIDs, snapshot logs, run INVALID, continue with remaining runs.
  Never delete a completed run dir; never edit code.

## Estimates (marked as estimates)

- Per run ≈ 4.5 min (240 frames at ~1.3–1.5 fps + ~40 s server load/warmup/video
  write); matrix ≈ 25–35 min; verdict + proof ≈ 5 min. (Smoke: 1.46 fps.)
- G1/G3/G5: expected PASS on all runs (smoke: 0 dead, both-visible 1.0, 1.46 fps).
- G2: purity ≈ 0.6–0.9 per car (smoke 0.83/0.90); ratio ≫ 4 except possibly
  white-vs-grid frames — median should hold.
- **G4a is the genuinely open gate:** GT identity should be exact (pure function
  of seed); frame identity across server sessions is the unknown (GPU/AA/shadow
  nondeterminism). Estimate mean |diff| < 1.0, but a NO here is a real finding
  (it would demote "deterministic frames" to "deterministic GT + near-identical
  frames" for every future sim campaign).
- Disk: ~1 GB total under `runs/` (gitignored).

## Results (filled by Opus)

Run date/time: **2026-07-17T14:31Z–14:47Z** (Madrid wall-clock). Versions: gz sim
8.14.0 (Harmonic), Python 3.12.10 / numpy 2.4.4 / opencv 4.13.0 via `.venv-ft`,
RTX 3090 (driver 595.71.05), headless EGL. No power-mode knob (desktop GPU, stock
clocks). Jetson not used, as pre-registered. No `results.json` exists for any run —
the columns below are therefore **not measured**, not "failed".

| run | seed | G1 | G2 (pur0/pur1) | G3 bothvis | G5 fps | V visual (one line) |
|---|---|---|---|---|---|---|
| seed101_A | 101 | n/a | n/a | n/a | n/a (1.48 fps observed while alive) | **uncomputable — no overlay PNG written (run died pre-finalize)** |
| seed202_B | 202 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN (stop rule) |
| seed303_C | 303 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN (stop rule) |
| seed101_D | 101 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN (stop rule) |

- G4a (A vs D): **not measured** — run D never ran. (See the non-gating probe below.)
- G4b (seeds differ): **not measured** — only seed 101 was attempted.
- `verdict_p57.py` full output (verbatim, exit 2):
  ```
  INCOMPLETE: missing runs ['seed101_A', 'seed202_B', 'seed303_C', 'seed101_D'] -- verdict not final
  ```
- **RQ-P5.7 overall: NO — `infra` FAIL.** The rig cannot currently generate a
  240-frame clip at all, so it does not meet the "on-demand scene generator" claim.
  Gates G1–G5 are unmeasured and V is uncomputable; the verdict rests on the
  pre-registered abort rule, not on a gate reading.

### What failed (the actual finding)

`seed101_A` was attempted twice, each with a **fresh** `gz sim -s` session, and
crashed mid-clip both times:

| attempt | frames done | died on | wall | server at crash |
|---|---|---|---|---|
| 1 | 127/240 (53%) | `set_pose_vector failed: Service call timed out` (scenegen.py:121) | 14:31:50→14:33:16, 1.48 fps | **ALIVE** (pid 28991) |
| 2 | 108/240 (45%) | `world control failed: Service call timed out` (scenegen.py:129) | 14:44:06→14:45:19, 1.48 fps | **ALIVE** (pid 33052) |

Both server logs contain exactly one error, identical across sessions:

```
NodeShared::RecvSrvRequest() error sending response: Host unreachable
```

Diagnosis (evidence, not inference): the sim never crashed — the server process was
alive at both crashes and the camera topic stayed up. `scenegen.py` drives the world
with **two `gz service` CLI subprocess calls per frame** (`set_pose_vector` +
`control`, `svc()` at scenegen.py:103), i.e. ~480 short-lived gz-transport nodes per
240-frame run. The server intermittently fails to route a *response* back to one of
those ephemeral nodes ("Host unreachable"); that CLI then burns its 5000 ms timeout,
returns non-zero, and `svc()`'s caller raises. The crash timestamp is ~5 s after the
last frame in both attempts, matching the timeout exactly. The two failures hit
*different* services, so the flake is in the transport/discovery layer, not in one
service handler.

**Rate (ESTIMATE, n=2 — small sample):** failures came after ~254 and ~216 calls
(mean ~236) → per-call failure ≈ 0.42%. A 240-frame run makes ~480 calls →
P(run completes) ≈ (1−1/236)^480 ≈ **13%**; P(all 4 gating runs complete) ≈
**0.03%**. So this was not bad luck: the matrix as designed is essentially
unrunnable, and re-running it unchanged is not worth the compute. Fixing it is a
design change (persistent transport node / batched stepping / retry-on-timeout) and
is **Fable's call, not mine** — flagged, not implemented.

### Non-gating salvage: the open G4a risk looks GOOD

Both INVALID attempts are seed 101 under fresh server sessions, leaving 127 and 108
raw frames — the overlapping 108 are exactly the cross-session comparison G4a asks
about (frame half only). Measured with `verdict_p57.frame_diff`'s metric:

- **108/108 frames byte-identical. mean |diff| = 0.000000** (gate ≤ 2.0),
  frac(|diff|>8) = 0.0 (gate ≤ 0.01).
- Render health over those frames: min per-frame std **21.07** (dead frame if ≤ 5 →
  no black/dead frames), **0** byte-identical consecutive frames (feed alive/moving).

**This is NOT a G4a pass** and must not be recorded as one: the runs are INVALID, no
finalize ran, the GT half (canonical `gt.jsonl` identity) is uncheckable, and it
covers 108/240 frames. But it does answer the pre-registered open risk in the
encouraging direction: GPU AA/shadow nondeterminism did **not** materialise across
fresh sessions — better than Fable's "mean |diff| < 1.0" estimate, which anticipated
small nonzero drift. The `<sky>` removal and puppeteer-lockstep design appear to have
bought exact frame determinism.

### Visual verification (mandatory gate)

**V is UNCOMPUTABLE for every run — recorded as INVALID, never a log-inferred pass.**
`overlay_f0060/0120/0180.png`, `gt.jsonl`, `overlay.mp4` and `results.json` are all
written at finalize (scenegen.py:414+), after the 240-frame loop. No attempt reached
finalize, so **0 of the required 12 overlay PNGs exist**. `make_proof.py` fails for
the same reason (`ValueError: need at least one array to concatenate`).

What I *did* look at, so the render path is not left log-inferred — the **raw** frames
(no GT boxes drawn; these cannot substitute for V, which grades GT-on-vehicle):

- `runs/seed101_A/frames/0060.png` (session 2) and
  `runs/seed101_A_attempt1_INVALID/frames/0060.png` (session 1): oblique aerial view
  of grey asphalt with yellow lane lines and the checkered start grid; **two cars,
  one clearly blue and one clearly white**, both well inside frame and plausibly
  UAV-framed. Not black, not sky, not one car, not two same-coloured cars. Matches
  `curation/smoke900_overlay_f0030.png` in look, minus the overlay. The two sessions'
  f0060 are byte-identical, confirmed numerically above.

So the design's visual risks (black EGL frames, nadir/sky mis-aim, texture-white
cars, dead feed) are all **clear** on the evidence available; the GT-projection half
of V is simply untested, because the run dies before any overlay is drawn.

### Estimate-vs-actual

| quantity | estimate | actual |
|---|---|---|
| per run | ~4.5 min | **never completed**; 1.48 fps → 240 frames would take ~2.7 min + finalize |
| matrix | 25–35 min | **~16 min to a hard stop** (2 attempts + diagnosis) |
| throughput (G5) | 1.3–1.5 fps | **1.48 fps observed** — on estimate; G5 would very likely have passed |
| G1/G3/G5 | expected PASS | unmeasured (no finalize) — render health consistent with PASS |
| G2 purity | 0.6–0.9 | unmeasured (purity is computed at finalize) |
| **G4a (flagged open risk)** | mean \|diff\| < 1.0, might fail | **0.000000, byte-identical** (non-gating, 108/240 frames) — better than estimated |
| **run completion** | **not listed as a risk** | **the gate that actually failed** — 0/2 completions, ~13% est. per-run odds |

The miss worth recording: the pre-registration budgeted for gate *failures* but
assumed the 240-frame loop would *finish* — the design smoke ran only 60 frames
(`curation/smoke900_results.json`), ~120 service calls, which is inside the ~236-call
mean-time-to-failure and so could not surface this. A 60-frame smoke cannot validate
a 240-frame run when the failure mode is per-call and cumulative.

### Mechanism note for future sim campaigns (no design change made)

The README's `kill $(cat $EXP/raw/gz_$RUN.pid)` is **insufficient**: `$!` records the
`nohup` **bash wrapper**, whose child is the actual `gz sim` ruby server (verified:
wrapper 28988 → server 28991, shared PGID). Killing the wrapper orphans a live
server, which would silently break the "fresh server session per run" property that
G4a's cross-session claim depends on — and a stale server would still answer on the
topic, so the next run would look fine. I killed the **process group**
(`kill -- -<pid>`, then verified `pgrep -af select_arena` is empty) before each
launch. Not a design change; the pid file is still written as pre-registered.
`pkill -f "gz sim"` (step 0) is also self-matching under this harness — the launching
shell's own command line contains the string — so it can kill its own wrapper; I
matched on `select_arena.sdf` instead.

## Deliverables (cut by Opus after the matrix)

The pre-registered deliverables assumed the success path and **could not be cut**:
`make_proof.py` needs all 4 runs' `results.json` + the overlay PNGs, and exits
`ValueError: need at least one array to concatenate`. Its file is **untouched** (it
is design code and stays valid for a re-run once the transport flake is fixed). The
negative result is evidenced instead by `make_proof_infra.py` (new, committed,
reproducible from the raw frames + logs that do exist):

1. **`proof/p57_infra_fail.png`** — the verdict in one figure: both `seed101_A`
   attempts (seed 101, fresh gz server session each) stop at 127/240 and 108/240
   frames, annotated with the ~254 / ~216 `gz service` calls made before the flake
   and the identical server-side error. Shows the failure is mid-clip, repeatable,
   and not a server death (server alive at both crashes).
2. **`proof/p57_crosssession_determinism.png`** — the non-gating G4a probe:
   per-frame mean |diff| between the two fresh sessions is flat **0.000000** against
   the 2.0 gate line over the 108 overlapping frames, with the f=60 pair side by
   side. Title states plainly that this is **not** a G4a pass (runs INVALID, GT half
   uncheckable, 108/240 frames). Answers the pre-registered open risk favourably.
3. **`proof/p57_render_ok_f0060.png`** — raw frame 60 of `seed101_A` (session 2,
   seed 101): two colour-distinct cars (one blue, one white) on the Sonoma start
   straight under the UAV-style oblique camera. Proof the render path, EGL vendor
   pin, camera aim and solid-colour materials all work — i.e. what remains broken is
   only the per-frame service-call transport, not the scene. No GT box is drawn (the
   overlay is a finalize-time artifact), which is exactly why V is uncomputable.
3. Append: RESULTS row(s) to `docs/results/part5-anticipatory.md`; QUESTIONS
   entry (RQ-P5.7 + one-line verdict) to `docs/questions/part5-anticipatory.md`;
   DECISIONS entry to `docs/decisions/part5-anticipatory.md` covering (a) sim as
   enabling step vs direct P5.6 rerun (what was given up), (b) P5.6 branch PARKED
   for a sim-powered rerun, (c) puppeteer-lockstep over actors/physics and the
   solid-colour-material decision (texture pipeline falsified), (d) segmentation
   camera deferred. SOURCES entry: Gazebo Fuel OpenRobotics Hatchback models
   (vendored under `runners/sitl/models/`, meshes CC-licensed on Fuel; used as
   the colour-distinct vehicle assets).
4. Commit on this branch; do not merge (the loop's reviewer merges).
