# P5.7 — Simulator scene-generator capability gate (select-arena v1)

**Pre-registered:** 2026-07-17T14:45Z (Madrid wall-clock).
**Status:** PRE-REGISTERED, not yet run.
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

## Results (TBD — filled by Opus)

Run date/time: TBD. Versions: TBD (from `results.json`).

| run | seed | G1 | G2 (pur0/pur1) | G3 bothvis | G5 fps | V visual (one line) |
|---|---|---|---|---|---|---|
| seed101_A | 101 | | | | | |
| seed202_B | 202 | | | | | |
| seed303_C | 303 | | | | | |
| seed101_D | 101 | | | | | |

- G4a (A vs D): gt_identical = TBD, frame mean |diff| = TBD, frac>8 = TBD → TBD
- G4b (seeds differ): min pairwise f0 distance = TBD → TBD
- `verdict_p57.py` full output: TBD (paste)
- **RQ-P5.7 overall: TBD**
- Estimate-vs-actual divergences: TBD

## Deliverables (cut by Opus after the matrix)

1. Fill Results above (including V lines and estimate-vs-actual).
2. `make_proof.py` → `proof/p57_overlay_grid.png` (the 4×3 visual-gate grid),
   `proof/p57_determinism.png` (A-vs-D per-frame diff + worst pair),
   `proof/p57_seed101_overlay.mp4` (behaviour clip: moving cars + moving camera +
   locked GT boxes). Caption each here (what it shows, which run).
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
