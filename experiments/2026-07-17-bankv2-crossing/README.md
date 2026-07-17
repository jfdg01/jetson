# P5.11 — Bank v2: designed-crossing scene bank (build gate)

**Pre-registered:** 2026-07-17T18:11Z (Madrid wall-clock).
Design + patches by Fable; Opus runs the matrix and fills Results only — do
NOT re-patch code.
**Status:** PRE-REGISTERED, not yet run.
**Machine:** RTX 3090 workstation (Gazebo does not run on the Jetson). No
Jetson leg — this is a dataset-build gate, no on-device VLM in the RQ.
**Branch:** `experiment/bankv2-crossing` off `main` @ `113a1c7`.

## RQ-P5.11

> Can the P5.9 scene generator author and record a **12-clip bank v2** where
> the two candidates **actually cross** — sustained designed occlusion
> (recorded white-occluded >= 50% for >= 25 frames, GT-GT IoU peak >= 0.20)
> inside a **doubled idle window** (prompt at 6.0 s, clip 12.0 s) — while
> every clip still passes render-integrity gates that mechanically separate
> the designed occlusion from a render defect?

**YES iff** `verdict_p511.py` prints YES (rules below, all numeric) AND the
operator's visual gate V confirms the named overlays. Anything else is NO.

### RQ type: build gate, not the A/B (decision + rejected alternative)

Two candidate RQs were on the table per the direction pick:

- **(a) BANK-CAPABILITY gate** — deliver + validate the v2 dataset. **Chosen.**
- **(b) v2-DISCRIMINATION A/B** — rerun the P5.10 DD-vs-RG matrix on v2.
  **Rejected for this cycle.** The A/B is meaningless on an unvalidated bank:
  P5.10's null result cost a full matrix on the Jetson before the audit traced
  it to bank v1 geometry (max GT-GT IoU 0.000 on all 12 clips). Repeating that
  order — run the select matrix first, audit the scenes later — is the exact
  mistake this campaign exists to fix. The bank build is the single
  highest-leverage first gate; the A/B is pre-registered as the follow-up
  (next section) and consumes this bank unchanged if YES.

### Pre-registered follow-up (next cycle, verbatim intent)

**P5.12 — v2 discrimination A/B:** rerun the P5.10 matrix (`select_p510.py`
contracts DD vs RG, same thresholds: DELIVER_FLOOR 0.25, MATCH_FLOOR 0.10,
dominance rule, MODEL Qwen2-VL-2B q8_0 terse on Jetson) on bank v2 with
**prompt frame 150** (6.0 s idle — double P5.10's 3 s, and the SAM2 dual
carry must survive a designed occlusion mid-idle). Success = the contracts
SEPARATE (|DD_total − RG_total| >= 4 of 24, either direction — an RG win is
the ID-swap-repair story, a DD win is the acquire-latency story; both are
thesis content). P5.10's harness needs only the bank path, `--prompt-frame`,
and clip length changed.

## Context (P5.10 audit -> this design)

- **P5.10 = NO [scene-bound], branch 2/3:** DD 24/24 == RG 24/24 on bank v1;
  gap 0 < 4. The RefDrone VLM grounded every clean render on the first call.
  Audit (this cycle, recomputed independently): max GT-GT image IoU across
  all 12 bank-v1 clips = **0.000** — the two cars never overlap on screen, so
  neither carry drift nor grounding ambiguity is ever exercised, and the
  P5.5-style ID-swap failure mode cannot occur.
- **Direction pick (human, 2026-07-17T17:55Z):** harden the bank — crossing/
  occlusion events, longer idle window, ideally a non-colour attribute.
- **Non-colour disambiguation: deferred, with rationale.** Every integrity
  gate (G2/G6/G8) attributes pixels to a car by its colour mask; a same-colour
  pair would blind the gates and the designed-occlusion partition itself.
  Colour stays the select attribute in v2; position-phrase legs ("the leading
  car") can be added to the P5.12 A/B without touching the bank, since GT
  IDs + per-frame boxes make any positional phrase gradeable after the fact.

### The design tension, resolved numerically

Hardening re-introduces exactly what P5.9's G6 gate was built to kill: a
crossing looks like kerb-clipping/body-fragmentation. The resolution is a
**mechanical partition by per-frame GT geometry** (no judgment calls):

| Frame class | Definition (gt.jsonl fields) | Integrity rule |
|---|---|---|
| CLEAR | `occl <= 0.05` for that car | v1-grade G2/G6 thresholds apply unchanged — fragmentation here is a render DEFECT |
| OCCLUDED | white `occl >= 0.50` | white's fragmentation is DESIGNED (not graded); instead the occluder must be intact (G8c) and actually drawn in front (G8b) |

`occl` = fraction of a car's GT box covered by the other car's box **when the
other car is nearer the camera** — pure projection, computed at record time.
White is farther than blue on every frame **by construction** (blue rides
5.9–7.5 m behind; camera trails both), so the occluder identity is a design
fact, not an inference. A clip whose occlusion never renders (z-order bug,
transparency) fails G8b; a clip that fragments outside the designed window
fails G6c; a clip whose crossing never happens fails G9/screen.

### Scene design v2 (already committed in `runners/scenegen.py`, profile "v2")

Two-stage overtake prep, all authored in numpy, GT projected offline:

- White target: constant lane (lat −3.0..−2.4), v 2.2–3.4 m/s, small sway.
- Blue distractor: starts right lane (lat 0.7–1.3), **pulls IN** behind the
  target's lane (smoothstep, start 0.7–1.0 s, 0.9–1.2 s long), **HOLDS**
  dead-centre in-lane 1.3–1.8 s (= the sustained occlusion window), **pulls
  OUT** to the far-left lane (1.3–1.7 s). Worst-case manoeuvre end 5.7 s <
  prompt 6.0 s.
- Camera: **low and long** — alt 4.0–6.0 m, standoff 22–26 m trailing (v1's
  alt 16–26 never occludes: the sightline to the far car clears the near
  car's roof by metres — measured in the design scan below).
- Corridor asserts (kerb-safe LAT_SAFE/S_SAFE_MAX from P5.9) plus a
  **no-contact assert**: along-track gap `|ds| >= 5.5 m` on every frame, so
  the image-space crossing never implies physical contact.
- Clip: **300 frames = 12.0 s @ 25 Hz**, prompt frame 150 (6.0 s idle,
  double P5.10's 3 s).

### Design-time measurements (all offline, pure projection, this cycle)

1. **v1-geometry falsification:** first v2 draft kept v1's camera
   (alt 16–26, standoff 14–22) + a single-sweep lane change: peak predicted
   GT-GT IoU **0.000 on 60/60 seeds** — same blindness as bank v1.
2. **Static scan** over (alt, standoff, gap) at lat-aligned poses: overlap
   requires alt <= ~8 m; chosen region alt 4–6 / standoff 22–26 / gap
   5.5–7 m predicts IoU 0.20–0.41, white 42–73% covered.
3. **Single-sweep falsification:** with the low camera but one fast lane
   change, peak IoU 0.11–0.23 and **zero** seeds sustain IoU >= 0.25 — a
   blink, not an occlusion window. This motivated the two-stage hold.
4. **Final sweep (seeds 1–60), two-stage + low camera:** peak IoU min/med/max
   0.186/0.268/0.370; sustained IoU >= 0.15 for median 70 frames; white
   >= 50% occluded for median 76 frames; **52/60 pass the screen**.
   Reproduce: `.venv-ft/bin/python runners/scenegen.py screen --lo 1 --hi 60 --need 12`

### Offline crossing screen (pre-registered, in `scenegen.py` as `V2_SCREEN`)

A seed enters the bank only if its **predicted** traces satisfy all five:

| # | Rule | Value |
|---|---|---|
| S1 | peak GT-GT IoU | >= 0.20 |
| S2 | consecutive frames IoU >= 0.15 | >= 25 (1.0 s) |
| S3 | consecutive frames white-occluded >= 0.50 | >= 25 (1.0 s) |
| S4 | peak frame | <= 125 (>= 1 s before prompt) |
| S5 | max IoU over frames 150–299 (post-prompt) | <= 0.15 |

**Bank seeds (fixed by the screen, first 12 of 1..60):**
`[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 14]` (seeds 11, 12 fail S3/S5).
Gate seeds stay 101/202/303 (P5.9 continuity); gate runs are **not**
screened — 303's predicted occlusion window is 24 frames (one short of S3),
which is precisely why S/G8/G9 are bank-cell properties, not generator
properties.

### Calibration probe (recorded this cycle, committed under `curation/`)

One full v2 clip (seed 1, 300 frames) was recorded at design time to verify
the occlusion actually renders and to calibrate G8 — the P5.9 `probe_kerb.py`
precedent. `curation/probe_seed1/` (committed: `results.json`, `gt.jsonl`,
`progress.json`, 4 overlay PNGs; frames/ and mp4s are local-only, 144 MB):

- Screen realized exactly: peak 0.331 @ f87 (predicted == recorded), 76-frame
  occlusion window, tail 0.134. 8.77 fps wall, 0 dead frames.
- **Looked at** (Read tool, this session): `overlay_f0087.png` = blue body in
  front of white with only the white roofline visible above — the designed
  occlusion, rendered; `overlay_f0075.png` = same window earlier;
  `overlay_f0225.png` = post-prompt, two cleanly separated intact bodies.
- Clear-frame integrity: white frag p10 0.995 over n_clear = 80, blue 1.000
  over 300 — v1-grade thresholds hold on the partition (hence G6c's
  n_clear >= 60 floor, NOT v1's 200: designed occlusion + entry/exit grazing
  eats ~220 of white's 300 frames).
- **G8a calibration surprise (kept as content):** white's own-colour pixel
  count barely drops during occlusion (ratio 0.894, max 1.354) because the
  roofline stays visible — a "npx must drop" gate would fail a CORRECT
  render; that gate was discarded pre-registration. The z-order signal that
  does discriminate: **blue-dominance in the box-intersection** during
  occlusion = median 0.687 (worst frames 0.27 at window edges — hence the
  gate is on the median, floor 0.55).

## Code changes (already committed on this branch — Opus: do NOT edit)

| File | What |
|---|---|
| `runners/scenegen.py` | `author_scenario(profile="v2")` two-stage overtake; `V2_SCREEN` + `v2_crossing_screen()` + `screen` CLI; record(): per-frame `npx`/`nearer`/`occl` in gt.jsonl, crossing-peak overlay, `v2_screen` + clear-partition aggregates in results.json; selfcheck 6d (v1 byte-stability regression: seed-101 params unchanged), 6e (v2 determinism/corridor/no-contact/occluder-invariant over 40 seeds), 6f (screen regression pins: seed 1 passes, seed 11 fails) |
| `experiments/2026-07-17-bankv2-crossing/verdict_p511.py` | mechanical verdict (gates below) + `--selfcheck` (grades the committed probe as a bank cell + two doctored negatives) |
| `experiments/2026-07-17-bankv2-crossing/make_proof.py` | 3 proof figures from `runs/*` (traces, gate grid, occlusion montage) |
| `experiments/2026-07-17-bankv2-crossing/curation/probe_seed1/` | calibration clip provenance (see above) |

All verified this cycle: `scenegen.py selfcheck` OK, `verdict_p511.py
--selfcheck` OK (probe passes all bank gates, bdom 0.687; negatives fire),
`make_proof.py` smoke-tested on the probe.

## Versions / config

RTX 3090 workstation, gz sim 8.14.0 (Harmonic), `.venv-ft` Python 3.12,
numpy/cv2 as pinned in `requirements-ft.lock.txt`. World
`runners/sitl/worlds/select_arena.sdf`, 1280x720 @ 25 Hz, hfov 1.2 rad.
Power mode: n/a (workstation). No model inference in this campaign.

## Run matrix (16 runs, one fresh server session each)

Same session discipline as P5.9 (session-per-run keeps G4a honest). Runs:

| run | seed | frames | note |
|---|---|---|---|
| seed101_A | 101 | 300 | gate |
| seed202_B | 202 | 300 | gate |
| seed303_C | 303 | 300 | gate |
| seed101_D | 101 | 300 | gate (determinism pair with A) |
| bank01..bank12 | 1,2,3,4,5,6,7,8,9,10,13,14 (in order) | 300 | bank |

Per run (replace `SEED`/`RUN` from the table; **keep the `nohup gz sim`
launch as its own clean background command** — the Bash sandbox reaper kills
gz+python combos):

```bash
cd /home/gara/jetson
EXP=experiments/2026-07-17-bankv2-crossing
SEED=101 RUN=seed101_A   # <-- change per run, table above
mkdir -p $EXP/raw $EXP/runs

# 0. guarantee no stale server (kills by process group; exit 0 = clean)
.venv-ft/bin/python runners/scenegen.py killserver

# 1. fresh headless server, nohup'd alone
SITL=$PWD/runners/sitl/external/SITL_Models/Gazebo
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json \
GZ_SIM_RESOURCE_PATH="$SITL/models:$SITL/worlds" \
nohup gz sim -s runners/sitl/worlds/select_arena.sdf > $EXP/raw/gz_$RUN.log 2>&1 &

# 2. wait for the camera topic (~15-25 s world load)
for i in $(seq 40); do gz topic -l 2>/dev/null | grep -q uav_cam && break; sleep 3; done
gz topic -l | grep uav_cam   # MUST print the image topic

# 3. record (~35 s loop at ~8.8 fps + finalize; DONE line at end)
nohup .venv-ft/bin/python runners/scenegen.py record --seed $SEED --frames 300 \
    --profile v2 --out $EXP/runs/$RUN > $EXP/raw/rec_$RUN.log 2>&1 &
for i in $(seq 60); do test -f $EXP/runs/$RUN/results.json && break; sleep 5; done
tail -5 $EXP/raw/rec_$RUN.log   # expect "[scenegen] DONE ..."

# 4. kill this session's server (verified process-group kill)
.venv-ft/bin/python runners/scenegen.py killserver
```

After all 16 runs:

```bash
# mechanical verdict (paste its FULL output into Results)
.venv-ft/bin/python experiments/2026-07-17-bankv2-crossing/verdict_p511.py

# proof deliverables (3 PNGs under proof/)
.venv-ft/bin/python experiments/2026-07-17-bankv2-crossing/make_proof.py
```

Gotchas (inherited from P5.9, all still binding): `killserver` is the only
sanctioned kill and must print `remaining: 0`; the EGL ICD env line or frames
are BLACK; the world needs its sensors plugin (already in the SDF); frame 0
is routinely black (warmup handles it — a `warmup frame dead` RuntimeError
means the EGL env was dropped). `--profile v2` is REQUIRED on every record
call — a bare v1 run writes 240-frame no-crossing clips that fail G0/G9.

### Infra / abort rules (pre-registered)

- A run dying mid-record: retry once with a fresh server. Second death of the
  same cell: gate run -> campaign INCOMPLETE (fix infra first); bank cell ->
  write `runs/<cell>.INFRA` with the reason and move on. **> 1 INFRA bank
  cell = NO [infra]** (verdict enforces).
- `gz topic -l` empty after 120 s: killserver, check `raw/gz_$RUN.log`, retry
  once; twice = INCOMPLETE.
- Total wall estimate blowing past 3x (see Estimates): stop, snapshot logs,
  record INCOMPLETE — do not grind.

## Verdict rules (mechanical — `verdict_p511.py` is the authority)

Per-run gates G0/G1/G2c/G3/G5/G6c, cross-run G4a/G4b, bank-only G8/G9 — the
full numeric definitions live in the `verdict_p511.py` docstring (committed,
pre-registered, byte-frozen with this README; G1/G3/G5 byte-for-byte from
P5.9, G0 scaled 240->300, G2/G6 re-scoped to the CLEAR partition, G8/G9 new).
**Overall YES iff:** 4/4 gate runs pass G0–G6c AND G4a AND G4b AND >= 11/12
bank cells pass all gates incl. G8/G9, <= 1 INFRA cell, 0 present-but-failing
cells. The script prints PASS/FAIL per gate per run and the final line; Opus
pastes it verbatim and does not deliberate.

## LOOK AT IT (mandatory, before writing any verdict)

Open with the Read tool and describe in Results what you saw:

1. **Every bank cell's crossing-peak overlay** `runs/bankNN/overlay_f<xpeak>.png`
   (xpeak = `v2_xpeak_pred_f` in that cell's results.json, ~f44–f103).
   VALID designed occlusion = ONE blue car body drawn IN FRONT, white car
   mostly hidden BEHIND it (roofline sliver above is expected), both green GT
   boxes on the stack, boxes overlapping. RENDER DEFECT = white body
   fragments/patches NOT explainable as "behind blue" (e.g. white shards
   inside the blue silhouette, z-fighting stripes), either car sunk into the
   road or clipped by a kerb, or two separated cars at the predicted peak
   (crossing failed to render). Reference for VALID: the committed
   `curation/probe_seed1/overlay_f0087.png`.
2. **One post-prompt overlay per cell** `overlay_f0225.png`: two separated,
   intact, correctly-boxed cars (this is the frame class delivery will be
   graded on in P5.12). Reference: probe `overlay_f0225.png`.
3. **Mid-run sanity on at least 2 gate runs**: `overlay_f0150.png` — not
   black, not >99% one colour, cars present.
4. The `make_proof.py` montage after it runs — it must look like 12 copies of
   the probe's occlusion, not 12 different failure modes.

Cheap asserts already in the scripts: dead-frame std check at warmup +
per-frame (G1), byte-identical consecutive frame counter (G1), G8b
blue-dominance (z-order). No frame captured = the cell is INVALID, never a
log-inferred PASS.

## Estimates (marked as estimates)

- Wall per run: ~35 s record loop (probe: 8.77 fps) + ~25 s world load +
  finalize ≈ 1.5–2 min; 16 runs ≈ **30–40 min total** (estimate).
- Expected verdict: YES — 52/60 seeds pass the offline screen and the probe
  passed every gate; residual risk sits in G4a (determinism across fresh
  server sessions was clean in P5.9, unverified for the v2 camera) and in
  per-seed render variance of G8b's 0.55 floor (probe 0.687; estimate).
- Expected fail modes if NO: G8b < 0.55 on a seed where the hold window sits
  at extreme sway (recalibration would need a NEW pre-registration, not a
  threshold nudge); or an INFRA pair from gz-transport flake (P5.7's killer,
  not seen in P5.9/P5.10 with the proxy).

## Results (TBD — Opus fills; paste verdict output verbatim)

### Gate runs

| run | seed | G0 | G1 | G2c | G3 | G5 | G6c | fps | notes |
|---|---|---|---|---|---|---|---|---|---|
| seed101_A | 101 | | | | | | | | |
| seed202_B | 202 | | | | | | | | |
| seed303_C | 303 | | | | | | | | |
| seed101_D | 101 | | | | | | | | |

G4a: (TBD) G4b: (TBD)

### Bank cells

| run | seed | G0 | G1 | G2c | G3 | G5 | G6c | G8 | G9 | n_occ | bdom | xpeak_f | looked-at verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bank01 | 1 | | | | | | | | | | | | |
| bank02 | 2 | | | | | | | | | | | | |
| bank03 | 3 | | | | | | | | | | | | |
| bank04 | 4 | | | | | | | | | | | | |
| bank05 | 5 | | | | | | | | | | | | |
| bank06 | 6 | | | | | | | | | | | | |
| bank07 | 7 | | | | | | | | | | | | |
| bank08 | 8 | | | | | | | | | | | | |
| bank09 | 9 | | | | | | | | | | | | |
| bank10 | 10 | | | | | | | | | | | | |
| bank11 | 13 | | | | | | | | | | | | |
| bank12 | 14 | | | | | | | | | | | | |

### Verdict

(TBD — paste `verdict_p511.py` full output; visual gate V statement: which
overlays were opened, what was seen, downgrade yes/no.)

### Estimate vs actual

(TBD — wall time, fps, any gate that surprised.)
