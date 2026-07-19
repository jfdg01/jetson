# P5.12 — Bank v2.1: recalibrated designed-crossing scene bank (build gate, re-run)

**Pre-registered:** 2026-07-19T12:24Z (Madrid wall-clock).
**Run:** 2026-07-19T12:31Z – 2026-07-19T12:49Z (Madrid wall-clock).
**Status:** COMPLETE — **RQ-P5.12 = YES**. 4/4 gate runs pass, G4a/G4b/G7 pass,
**12/12 bank cells pass all gates**, 0 INFRA, visual gate V PASS (12/12 genuine
occlusions, 0 render defects). P5.11's NO confirmed calibration-bound.
**Machine:** RTX 3090 workstation (Gazebo does not run on the Jetson). No Jetson
leg — this is a dataset-build gate, no on-device VLM in the RQ.
**Branch:** `experiment/bankv21-recal` off `main` @ `cce99af` (the P5.11 merge).

## RQ-P5.12

> Was P5.11's `NO` **gate-calibration-bound rather than render-bound**? Re-run
> the identical 16-run v2 record matrix over a **v2.1 seed bank chosen by an
> offline screen that enforces the two properties P5.11's gates measured after
> the fact** (per-clip clear-frame supply, pairwise seed diversity), against
> gates recalibrated **once, from the P5.11 recorded population** — and does
> that bank now clear >= 11/12?

**YES iff** `verdict_p512.py` prints YES (rules below, all numeric) AND the
operator's visual gate V confirms the named overlays. Anything else is NO.

### RQ type, and the renumbering (decision + what was given up)

P5.11 pre-registered its follow-up as "P5.12 — v2 discrimination A/B". That
A/B is **deferred to P5.13**, unchanged in intent, and this recal takes the
P5.12 slot. Rationale: the A/B consumes the bank, and P5.11 delivered 3/12
usable cells. Running a 24-cell Jetson select matrix on a 3-clip bank repeats
the exact mistake P5.11 was created to fix (P5.10 burned a full matrix on a
bank whose geometry was later found degenerate). What is given up: one more
cycle before the select question is touched — the fourth in a row spent on
scene data rather than on contracts.

**Rejected alternative: nudge the thresholds and re-grade P5.11's existing
runs.** No new recording, near-zero cost, and the recorded clips are on disk.
Rejected because it is threshold-fitting on the same data that motivated the
thresholds — the pass count would be a foregone conclusion and carry no
evidence. The recalibration here is instead frozen *before* any v2.1 frame is
recorded, and it is paired with an offline screen that makes the two failing
gates satisfiable **by construction**, so the run is a real test of whether
prediction transfers to render.

### Pre-registered follow-up (next cycle, verbatim intent)

**P5.13 — v2 discrimination A/B:** rerun the P5.10 matrix (`select_p510.py`
contracts DD vs RG, same thresholds: DELIVER_FLOOR 0.25, MATCH_FLOOR 0.10,
dominance rule, MODEL Qwen2-VL-2B q8_0 terse on Jetson) on bank v2.1 with
**prompt frame 150** (6.0 s idle; the SAM2 dual carry must survive a designed
occlusion mid-idle). Success = the contracts SEPARATE (|DD_total − RG_total|
>= 4 of 24, either direction). Consumes this bank unchanged if YES.

## Context (P5.11 audit -> this design)

P5.11 = **NO [G4b seed-diversity FAIL; bank 3/12]**. The audit finding that
drives this cycle: **the generator and the renders were not the problem.**

- All 12 crossing-peak overlays were opened with the Read tool in P5.11:
  **12/12 genuine designed occlusions, 0 render defects.**
- G4a determinism passed exactly (`mean|diff| = 0.0`), so `record()` realizes
  `author_scenario` byte-exactly.
- The three failures were all **admission** failures, and all were predictable
  offline:

| P5.11 failure | Cause | Fixed by |
|---|---|---|
| G4b: min pairwise divergence 0.77 m < 1.0 at pair (9, 14) | seeds admitted first-N-passing, no diversity constraint | screen S7 |
| 7/12 cells fail G6c `n_clear >= 60` | floor set from a single probe (seed 1, n_clear 80); population spans 23..119 | floor 60 -> 40 + screen S6 |
| 1/12 cell fails G8b `bdom >= 0.55` (bank06, 0.488) | floor set from the probe median 0.687; population of *confirmed genuine* occlusions spans 0.487..0.700 | floor 0.55 -> 0.40 |

Recorded population provenance: `curation/p511_population.json` (12 cells,
extracted by `curation/extract_p511_population.py` from P5.11's `runs/`),
with `visual_status` recording that every cell was visually confirmed.

### The recalibration, and why it is not threshold-fitting

Two floors move. Both were single-probe extrapolations; both are re-set from
the 12-cell population of clips **that were visually confirmed defect-free**,
and both are re-set to sit below the observed-correct minimum but far above
the defect signature the gate exists to catch:

- **G6c `n_clear` 60 -> 40.** At 40 the statistic keeps teeth: `p10` is the
  4th-lowest of >= 40 samples, and `frac(< 0.90) <= 0.02` admits **zero** bad
  frames below n = 50. Proven, not asserted: `verdict_p512.py --selfcheck`
  negative 3 doctors 10 clear frames to `frag = 0.5` and the gate fails at the
  lowered floor.
- **G8b `bdom` 0.55 -> 0.40.** The defect this gate catches is wrong z-order
  (white drawn in front), which drives the statistic toward ~0. Observed
  correct minimum 0.487; 0.40 separates them with margin. G8a/G8c unchanged.

Every other gate is byte-identical to P5.11. No gate is loosened to admit a
clip anyone has looked at and doubted.

### The v2.1 seed screen (generator untouched)

`runners/scenegen.py` gains an **admission** screen only — `author_scenario`,
`profile="v2"`, and `record()` are unchanged, so the renders P5.11 validated
are the renders P5.12 gets. S1–S5 (`v2_crossing_screen`) are unchanged; two
constraints are added:

- **S6 — predicted clear-frame floor (>= 45).** `predicted_clear_count()`
  computes, from pure projection, the frames where white's occluded fraction
  <= 0.05 and its box is visible. Under byte-determinism this **equals** the
  recorded G6c pool — verified 12/12 exactly against P5.11's recorded
  `n_clear`. 45 is a 5-frame belt over the recalibrated floor of 40.
- **S7 — pairwise diversity (>= 1.1 m).** Greedy admission in ascending seed
  order; a seed is admitted only if its whole-scenario divergence is >= 1.1 m
  against **every gate seed and every already-admitted seed**. Same formula as
  G4b, so the guarantee is exact; the 0.1 m over G4b's 1.0 m floor is
  belt-and-braces.

Pinned admission over seeds 1..56 (`V2_1_BANK_PINNED`, computed offline
2026-07-17, re-verified 2026-07-19):

```
[1, 2, 3, 4, 6, 14, 17, 28, 29, 33, 40, 56]
```

Predicted clear counts: 80, 57, 119, 96, 77, 77, 112, 74, 67, 112, 94, 152 —
all >= 45, min 57. Min pairwise divergence over the full 15 (3 gate + 12
bank): **1.106 m at pair (2, 29)** — clears G4b's 1.0 m floor.

Note the screen **splits the P5.11 duplicate pair**: seed 9 is now excluded
(predicted clear 32 < 45) while 14 is admitted, and seed 13 (P5.11 bank11,
n_clear 23) is excluded. Both exclusions are pinned as regression asserts in
`scenegen.py selfcheck` case 6g.

**New cross-run gate G7 (screen pin):** at verdict time `sg.v2_1_bank()` is
re-run and must reproduce `BANK_SEEDS` byte-for-byte. If the generator or the
screen drifted between pre-registration and the verdict, the campaign cannot
pass.

## Code changes (already on this branch — Opus: do NOT edit)

| File | What |
|---|---|
| `runners/scenegen.py` (+125) | `predicted_occl_white()`, `predicted_clear_count()`, `scenario_divergence()`, `V2_1_SCREEN`, `V2_1_BANK_PINNED`, `v2_1_bank()`, `screen21` CLI; selfcheck 6g (pins the admission, the 9/13 exclusions, and the 1.0 m G4b clearance). Generator profile untouched. |
| `verdict_p512.py` | forward copy of P5.11's byte-frozen `verdict_p511.py` with exactly three pre-registered changes (BANK_SEEDS, `N_CLEAR_FLOOR` 40, `BDOM_FLOOR` 0.40) plus gate G7; `--selfcheck` adds negative 3 (recalibrated G6c keeps teeth). |
| `make_proof.py` | P5.11's proof script retargeted at `verdict_p512` (3 PNGs from `runs/*`). |
| `curation/p511_population.json`, `curation/extract_p511_population.py` | recalibration provenance — the 12-cell recorded population and the script that extracted it. |

Verified 2026-07-19T12:24Z, before pre-registration was frozen:
`scenegen.py selfcheck` -> `scenegen selfcheck OK`; `verdict_p512.py
--selfcheck` -> all 4 assertions fire, `v2.1 screen admission reproduces the
pinned bank`, `verdict_p512 selfcheck OK`.

## Versions / config

RTX 3090 workstation, gz sim 8.14.0 (Harmonic), `.venv-ft` Python 3.12,
numpy/cv2 as pinned in `requirements-ft.lock.txt`. World
`runners/sitl/worlds/select_arena.sdf`, 1280x720 @ 25 Hz, hfov 1.2 rad.
Power mode: n/a (workstation). No model inference in this campaign.

## Run matrix (16 runs, one fresh server session each)

Identical discipline to P5.11 (session-per-run keeps G4a honest). Only the
bank seed list differs.

| run | seed | frames | note |
|---|---|---|---|
| seed101_A | 101 | 300 | gate |
| seed202_B | 202 | 300 | gate |
| seed303_C | 303 | 300 | gate |
| seed101_D | 101 | 300 | gate (determinism pair with A) |
| bank01..bank12 | 1, 2, 3, 4, 6, 14, 17, 28, 29, 33, 40, 56 (in order) | 300 | bank |

Per run (replace `SEED`/`RUN` from the table; **keep the `nohup gz sim` launch
as its own clean background command** — the Bash sandbox reaper kills
gz+python combos):

```bash
cd /home/gara/jetson
EXP=experiments/2026-07-17-bankv21-recal
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
.venv-ft/bin/python experiments/2026-07-17-bankv21-recal/verdict_p512.py

# proof deliverables (3 PNGs under proof/)
.venv-ft/bin/python experiments/2026-07-17-bankv21-recal/make_proof.py
```

Gotchas (inherited, all still binding): `killserver` is the only sanctioned
kill and must print `remaining: 0`; the EGL ICD env line or frames are BLACK;
the world needs its sensors plugin (already in the SDF); frame 0 is routinely
black (warmup handles it — a `warmup frame dead` RuntimeError means the EGL
env was dropped). `--profile v2` is REQUIRED on every record call — a bare v1
run writes 240-frame no-crossing clips that fail G0/G9.

### Infra / abort rules (pre-registered)

- A run dying mid-record: retry once with a fresh server. Second death of the
  same cell: gate run -> campaign INCOMPLETE (fix infra first); bank cell ->
  write `runs/<cell>.INFRA` with the reason and move on. **> 1 INFRA bank cell
  = NO [infra]** (verdict enforces).
- `gz topic -l` empty after 120 s: killserver, check `raw/gz_$RUN.log`, retry
  once; twice = INCOMPLETE.
- Total wall blowing past 3x the estimate: stop, snapshot logs, record
  INCOMPLETE — do not grind.
- **No threshold may move during or after the run.** A gate that fails is a
  NO, and any further recalibration needs a new pre-registration. This rule is
  the whole point of freezing the floors before recording.

## Verdict rules (mechanical — `verdict_p512.py` is the authority)

Per-run G0/G1/G2c/G3/G5/G6c, cross-run G4a/G4b/**G7**, bank-only G8/G9 — full
numeric definitions in the `verdict_p512.py` docstring (committed,
pre-registered, byte-frozen with this README). **Overall YES iff:** 4/4 gate
runs pass G0–G6c AND G4a AND G4b AND G7 AND >= 11/12 bank cells pass all gates
incl. G8/G9, <= 1 INFRA cell, 0 present-but-failing cells. The script prints
PASS/FAIL per gate per run and the final line; Opus pastes it verbatim and
does not deliberate.

## LOOK AT IT (mandatory, before writing any verdict)

Open with the Read tool and describe in Results what you saw:

1. **Every bank cell's crossing-peak overlay** `runs/bankNN/overlay_f<xpeak>.png`
   (xpeak = `v2_xpeak_pred_f` in that cell's results.json). VALID designed
   occlusion = ONE blue car body drawn IN FRONT, white car mostly hidden
   BEHIND it (roofline sliver above is expected), both green GT boxes on the
   stack, boxes overlapping. RENDER DEFECT = white body fragments/patches NOT
   explainable as "behind blue", either car sunk into the road or clipped by a
   kerb, or two separated cars at the predicted peak. Reference for VALID:
   `../2026-07-17-bankv2-crossing/curation/probe_seed1/overlay_f0087.png`.
2. **One post-prompt overlay per cell** `overlay_f0225.png`: two separated,
   intact, correctly-boxed cars — the frame class P5.13 delivery is graded on.
3. **Mid-run sanity on at least 2 gate runs**: `overlay_f0150.png` — not
   black, not >99% one colour, cars present.
4. The `make_proof.py` montage — it must look like 12 copies of the probe's
   occlusion, not 12 different failure modes.

Six of the twelve seeds (1, 2, 3, 4, 6, 14) were recorded and visually
confirmed in P5.11; **they still get looked at** — a byte-determinism argument
is not a substitute for opening the frame. Seeds 17, 28, 29, 33, 40, 56 have
never been rendered.

No frame captured = the cell is INVALID, never a log-inferred PASS.

## Estimates (marked as estimates)

- Wall per run: ~35 s record loop (P5.11 actual ~8.8 fps) + ~25 s world load +
  finalize ≈ 1.5–2 min; 16 runs ≈ **30–40 min total** (estimate; P5.11 actual
  for the same matrix is the reference).
- **Expected verdict: YES** (estimate). G4b is now guaranteed by construction
  (1.106 m computed offline vs a 1.0 m floor), G6c's pool is guaranteed by an
  offline prediction that matched the recorded value 12/12 exactly, and G8b's
  floor sits below the observed-correct minimum across the whole confirmed
  population. Residual risk is not in the calibration.
- **Expected fail modes if NO** — all of them are *new* information, which is
  why the run is worth the 40 minutes:
  - The six never-rendered seeds (17, 28, 29, 33, 40, 56) render a defect the
    six known-good ones don't — i.e. the offline screen does not fully predict
    render integrity. This is the real hypothesis under test.
  - G8b < 0.40 on a new seed: the hold window lands at extreme sway. Would be
    a genuine generator finding, not a threshold to nudge.
  - G4a determinism breaking across fresh server sessions (clean in P5.9 and
    P5.11; would invalidate the S6-predicts-recorded argument outright).
  - An INFRA pair from gz-transport flake (P5.7's killer; not seen since the
    proxy landed).
- Seed 56's predicted clear count (152) is the highest in the pool and its
  tail IoU the lowest (0.024) — if any cell is a clean showcase for the
  proof montage, that is the estimate.

## Results

**Run:** 2026-07-19T12:31Z – 2026-07-19T12:49Z (Madrid wall-clock), RTX 3090
workstation, gz sim 8.14.0, `.venv-ft`. All 16 runs completed first attempt —
**zero retries, zero INFRA cells, zero gz-transport flake.**

### Gate runs

All four gate runs pass G0/G1/G2c/G3/G5/G6c.

| run | seed | G0 | G1 | G2c | G3 | G5 | G6c | fps | purW/B | wfrag p10 | n_clear |
|---|---|---|---|---|---|---|---|---|---|---|---|
| seed101_A | 101 | PASS | PASS | PASS | PASS | PASS | PASS | 8.06 | 0.692/0.786 | 1.000 | 115 |
| seed202_B | 202 | PASS | PASS | PASS | PASS | PASS | PASS | 7.99 | 0.807/0.803 | 0.995 | 68 |
| seed303_C | 303 | PASS | PASS | PASS | PASS | PASS | PASS | 7.99 | 0.731/0.827 | 0.999 | 112 |
| seed101_D | 101 | PASS | PASS | PASS | PASS | PASS | PASS | 8.26 | 0.692/0.786 | 1.000 | 115 |

Cross-run: **G4a** determinism A vs D `gt_identical=True`, `frame_mean_absdiff
= 0.0`, `frac_gt8 = 0.0` -> PASS (byte-exact across two fresh server sessions,
matching P5.9/P5.11). **G4b** min pairwise divergence **1.11 m** at pair (2,
29) vs the 1.0 m floor -> PASS. **G7** screen pin reproduces `[1, 2, 3, 4, 6,
14, 17, 28, 29, 33, 40, 56]` -> PASS.

### Bank cells

**12/12 pass all gates** (G0, G1, G2c, G3, G5, G6c, G8, G9). P5.11 was 3/12.

| run | seed | G0 | G1 | G2c | G3 | G5 | G6c | G8 | G9 | n_clear | n_occ | bdom | xpeak |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bank01 | 1 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 80 | 76 | 0.687 | 87 |
| bank02 | 2 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 57 | 73 | 0.627 | 74 |
| bank03 | 3 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 119 | 69 | 0.600 | 85 |
| bank04 | 4 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 96 | 76 | 0.700 | 88 |
| bank05 | 6 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 77 | 46 | 0.488 | 69 |
| bank06 | 14 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 77 | 45 | 0.541 | 56 |
| bank07 | 17 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 112 | 79 | 0.746 | 82 |
| bank08 | 28 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 74 | 79 | 0.636 | 92 |
| bank09 | 29 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 67 | 93 | 0.668 | 94 |
| bank10 | 33 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 112 | 71 | 0.566 | 77 |
| bank11 | 40 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 94 | 70 | 0.546 | 83 |
| bank12 | 56 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 152 | 83 | 0.608 | 89 |

Both recalibrated floors are load-bearing and both are cleared with margin
except at their designed edge:

- **G6c `n_clear >= 40`:** population min 57 (bank02). At the *old* 60 floor
  bank02 (57) would still have failed — i.e. the 60 floor was rejecting clips
  the offline screen now proves are fine. Under the old floor this bank would
  be 11/12, not 12/12.
- **G8b `bdom >= 0.40`:** population min **0.488** (bank05, seed 6) — the exact
  value that failed P5.11's 0.55 floor. It passes here, and the visual gate
  below confirms it is a genuine (if shallow) occlusion, not a z-order defect.

### Predicted-vs-recorded n_clear (the S6 transfer claim)

**The offline prediction transfers exactly: 12/12 cells, delta 0 on every one.**
This is the strongest single result of the campaign — `predicted_clear_count()`
is pure projection with no renderer in the loop, yet it reproduces the recorded
G6c pool byte-for-byte, which is what makes the S6 screen a legitimate
*pre*-selection rather than a post-hoc filter.

| seed | predicted | recorded | delta |
|---|---|---|---|
| 1 | 80 | 80 | 0 |
| 2 | 57 | 57 | 0 |
| 3 | 119 | 119 | 0 |
| 4 | 96 | 96 | 0 |
| 6 | 77 | 77 | 0 |
| 14 | 77 | 77 | 0 |
| 17 | 112 | 112 | 0 |
| 28 | 74 | 74 | 0 |
| 29 | 67 | 67 | 0 |
| 33 | 112 | 112 | 0 |
| 40 | 94 | 94 | 0 |
| 56 | 152 | 152 | 0 |

Note this held for the **six never-before-rendered seeds** (17, 28, 29, 33, 40,
56) exactly as for the six P5.11-known ones — the hypothesis actually under
test in the pre-registration ("does the offline screen predict render
integrity on unseen seeds?") is answered YES.

### Verdict (`verdict_p512.py` output, verbatim)

```
run          seed G0 G1 G2c G3 G5 G6c G8 G9  fps    purW/B        wfragp10 nclr nocc bdom   xpeak
seed101_A    101  1  1  1   1  1  1   -  -   8.06   0.692/0.786   1.0    115  60   None   90
seed202_B    202  1  1  1   1  1  1   -  -   7.99   0.807/0.803   0.995    68   55   None   88
seed303_C    303  1  1  1   1  1  1   -  -   7.99   0.731/0.827   0.999    112  25   None   89
seed101_D    101  1  1  1   1  1  1   -  -   8.26   0.692/0.786   1.0    115  60   None   90
bank01       1    1  1  1   1  1  1   1  1   8.13   0.593/0.792   0.995    80   76   0.687  87
bank02       2    1  1  1   1  1  1   1  1   8.16   0.838/0.855   0.995    57   73   0.627  74
bank03       3    1  1  1   1  1  1   1  1   8.11   0.749/0.847   0.997    119  69   0.6    85
bank04       4    1  1  1   1  1  1   1  1   8.18   0.791/0.799   0.992    96   76   0.7    88
bank05       6    1  1  1   1  1  1   1  1   8.06   0.808/0.781   0.992    77   46   0.488  69
bank06       14   1  1  1   1  1  1   1  1   8.12   0.790/0.782   0.993    77   45   0.541  56
bank07       17   1  1  1   1  1  1   1  1   8.23   0.786/0.828   0.994    112  79   0.746  82
bank08       28   1  1  1   1  1  1   1  1   8.06   0.613/0.760   0.993    74   79   0.636  92
bank09       29   1  1  1   1  1  1   1  1   8.19   0.715/0.864   0.999    67   93   0.668  94
bank10       33   1  1  1   1  1  1   1  1   8.09   0.803/0.817   0.995    112  71   0.566  77
bank11       40   1  1  1   1  1  1   1  1   8.09   0.610/0.787   1.0    94   70   0.546  83
bank12       56   1  1  1   1  1  1   1  1   8.21   0.706/0.828   0.993    152  83   0.608  89
G4a determinism seed101_A vs seed101_D: gt_identical=True frame_mean_absdiff=0.0 (<= 2.0) frac_gt8=0.0 (<= 0.01) -> PASS
G4b seed diversity (15 seeds, v2): min pairwise scenario divergence 1.11 m (>= 1.0) at pair (2, 29); recorded-f0 faithful=True over 16 runs -> PASS
G7 screen pin: v2.1 screen admission reproduces the pinned bank: [1, 2, 3, 4, 6, 14, 17, 28, 29, 33, 40, 56] -> PASS
RQ-P5.12 OVERALL: YES (YES iff 4/4 gate runs pass G0,G1,G2c,G3,G5,G6c AND G4a AND G4b AND G7 AND >= 11/12 bank cells also pass G8,G9 with <= 1 infra loss and 0 gate failures; the visual gate V -- operator opens the named overlay PNGs, including every bank cell's crossing-peak overlay -- can only downgrade this to NO)
```

### Visual gate V (what the operator actually saw)

Every PNG below was opened with the Read tool. **Result: V PASS — 12/12 genuine
designed occlusions, 0 render defects.** The mechanical YES is NOT downgraded.

Reference for VALID (P5.11 probe, `../2026-07-17-bankv2-crossing/curation/probe_seed1/overlay_f0087.png`):
blue car body drawn in front, white car's roofline a pale sliver above it, both
green GT boxes stacked and overlapping.

Crossing-peak overlays (`runs/bankNN/overlay_f<xpeak>.png`), one line each:

| cell | seed | frame | what I saw |
|---|---|---|---|
| bank01 | 1 | f0087 | Pixel-identical to the P5.11 probe reference. Blue in front, white roofline sliver above, both boxes on the stack. VALID. |
| bank02 | 2 | f0074 | Blue body in front on the start/finish line, white cabin sliver above-left, boxes overlapping. Cars sit on the road, no kerb clipping. VALID. |
| bank03 | 3 | f0085 | Blue in front, white roof visible above; slightly more of the white cabin than the probe. Both boxes overlap. VALID. |
| bank04 | 4 | f0088 | Tightest stack of the set — white almost fully hidden, only a small pale wedge at upper-left. VALID. |
| bank05 | 6 | f0069 | **Shallowest occlusion in the bank** (bdom 0.488). White cabin is a large white mass sitting above the blue body rather than a thin sliver — white's lower body is genuinely hidden behind blue, so this is a real occlusion, but it is the weakest one and it is visibly weaker than the rest. No defect: white is one contiguous body, not fragments, and both cars are on the road. VALID (weakest). |
| bank06 | 14 | f0056 | Same character as bank05 — substantial white cabin above the blue. Contiguous, correctly z-ordered, boxes overlap. VALID (weak). |
| bank07 | 17 | f0082 | Never rendered before. Textbook: strong occlusion, white reduced to a roofline sliver. Cleanest of the six new seeds. VALID. |
| bank08 | 28 | f0092 | Never rendered before. Blue in front, thin white roof strip above, boxes stacked. VALID. |
| bank09 | 29 | f0094 | Never rendered before. Blue in front, small white sliver. VALID. |
| bank10 | 33 | f0077 | Never rendered before. Larger white cabin visible (bdom 0.566) but contiguous and correctly behind blue. VALID. |
| bank11 | 40 | f0083 | Never rendered before. Blue in front, white roof band above, boxes overlap. VALID. |
| bank12 | 56 | f0089 | Never rendered before. Blue in front, white sliver above. Clean. VALID. |

Post-prompt overlays (`overlay_f0225.png`), all 12 opened: **all 12 show two
separated, intact, correctly-boxed cars** — white on the left, blue on the
right, both fully rendered bodies on the road surface, no sinking, no
fragmentation, no kerb clipping. In bank01/bank04/bank06/bank09 the two GT
boxes still touch or slightly overlap at f0225 (the cars have separated but not
widely); in bank03/bank08/bank11/bank12 they are cleanly disjoint. All are the
frame class P5.13 delivery will be graded on.

Gate mid-run sanity (`overlay_f0150.png`): **seed101_A** — full-colour track
scene, two separated cars boxed near frame centre, checkerboard start line in
the foreground, not black, not one-colour. **seed303_C** — same, camera pose
differs, both cars intact and boxed. Both VALID.

`make_proof.py` montage: reads as **12 copies of the probe's occlusion**, not
12 different failure modes — same blue-in-front / white-behind geometry in
every tile, varying only in stack tightness and camera pose. Gate met.

**One honest caveat surfaced by looking, which the numbers alone understate:**
bank05 (seed 6) and bank06 (seed 14) are visibly shallower occlusions than the
other ten, and the crossing-trace figure shows their occlusion window is
*fragmented* (multiple separate orange bands) rather than one contiguous block.
They pass every gate and they are genuine occlusions, but if P5.13 finds the
contracts failing to separate, these two cells are the first place to look —
they carry less occlusion stress than the bank average.

### Estimate vs actual

| quantity | estimate | actual | note |
|---|---|---|---|
| wall, 16 runs | 30–40 min | **~18 min** (12:31–12:49Z) | Estimate was ~2x pessimistic. Record loop ran ~8.0–8.3 fps as predicted; the world load was faster than the assumed 25 s. |
| verdict | YES | **YES** | Correct. |
| bank pass rate | >= 11/12 | **12/12** | Beat the bar. |
| G4b min divergence | 1.106 m (offline) | **1.11 m** (recorded) | Matches. |
| S6 predicted vs recorded n_clear | "equals under determinism" | **12/12 delta 0** | Exact, including on all six never-rendered seeds. |
| INFRA cells | up to 1 tolerated | **0** | No gz-transport flake at all; the P5.7 killer stayed dead. |
| seed 56 as showcase | highest clear count (152), cleanest | **partly right** | 152 clear frames confirmed and its occlusion is clean, but bank07/seed 17 (bdom 0.746) is the visually strongest occlusion and the better montage showcase. |
| fail modes if NO | six new seeds render a defect | **did not occur** | The offline screen fully predicted render integrity on unseen seeds — the real hypothesis under test passed. |

Surprises, recorded plainly:

1. **The strongest evidence was the one that cost nothing.** The S6
   predicted-vs-recorded table came out delta-0 on all 12 cells. That turns
   "the screen picks plausible seeds" into "the screen computes the recorded
   statistic exactly", which is a much stronger claim than the
   pre-registration asserted.
2. **The old G6c floor of 60 was rejecting a good clip.** bank02 records
   n_clear 57 and is visually flawless. Under P5.11's floor this bank would be
   11/12 rather than 12/12 — direct confirmation that the P5.11 NO was
   calibration-bound, since the same generator produced a defect-free clip that
   the old threshold refused.
3. **bank05's 0.488 bdom is the same number that failed P5.11**, now passing,
   and the frame confirms it was never a defect — it is a shallow but real
   occlusion. This is exactly the case the recalibration was written for, and
   it is the one cell where the operator's eyes, not the gate, carry the
   verdict.

## Proof deliverables (`proof/`, from `make_proof.py`)

Reproducible from `runs/*/results.json` via the committed
`make_proof.py`. All three were opened with the Read tool before being
captioned. **Filename caveat:** the script is a retarget of P5.11's and still
emits `p511_*` filenames; the figure *titles* and all content are P5.12. The
committed script was not edited (executor does not modify committed code) —
the stale prefix is cosmetic and noted here rather than silently fixed.

1. **`p511_occlusion_montage.png`** — the headline deliverable. 3x4 montage of
   every bank cell's crossing-peak overlay, captioned with cell / seed / peak
   frame / GT-GT IoU. Config: bank v2.1, `--profile v2`, 300 frames, 1280x720
   @ 25 Hz, gz 8.14.0. **Shows:** all 12 clips realize the same designed
   geometry — blue occluder drawn in front of the white target, white reduced
   to a roofline sliver, both GT boxes stacked. This is the visual evidence
   that the P5.11 NO was not render-bound: the renders were always fine.
   Contrast in stack tightness across tiles (bank04 tightest, bank05 loosest)
   is the bdom spread made visible.
2. **`p511_gate_grid.png`** — 12x8 PASS grid, all cells green `P`, titled
   "12/12 cells pass all". Config: same 12 bank runs, graded by
   `verdict_p512.py` at the recalibrated floors (`N_CLEAR_FLOOR` 40,
   `BDOM_FLOOR` 0.40). **Shows:** the recalibrated build gate clears the whole
   bank — the direct before/after against P5.11's 3/12 on the same generator.
3. **`p511_crossing_traces.png`** — per-clip recorded GT-GT IoU vs frame, with
   the `occl >= 0.5` window shaded, the P5.13 prompt frame (f150) dashed, and
   the peak-floor 0.20 / tail-cap 0.15 lines dotted. Config: same 12 runs.
   **Shows:** every clip peaks inside its occlusion window and decays to a low
   tail well before f150, i.e. the designed crossing happens mid-idle and is
   over by prompt time — the temporal structure P5.13's dual-carry test needs.
   Also shows the bank05 / bank06 fragmented-occlusion caveat noted above.

## Status / next step

**COMPLETE — RQ-P5.12 = YES.** Bank v2.1 is built, gated and visually
confirmed: 4/4 gate runs pass, G4a/G4b/G7 pass, 12/12 bank cells pass all
gates, 0 INFRA, visual gate V PASS (12/12 genuine occlusions, 0 defects). The
P5.11 NO is confirmed **gate-calibration-bound, not render-bound**.

The bank at `runs/bank01..bank12` (seeds 1, 2, 3, 4, 6, 14, 17, 28, 29, 33, 40,
56) is the deliverable and is ready to be consumed unchanged.

**Next step: P5.13 — v2 discrimination A/B**, exactly as pre-registered above:
rerun the P5.10 matrix (`select_p510.py`, contracts DD vs RG, DELIVER_FLOOR
0.25, MATCH_FLOOR 0.10, dominance rule, Qwen2-VL-2B q8_0 terse on Jetson) over
this bank with **prompt frame 150**. Success = the contracts separate,
`|DD_total - RG_total| >= 4` of 24. If they do not separate, check bank05 and
bank06 first (weakest occlusion stress, per the visual gate).
