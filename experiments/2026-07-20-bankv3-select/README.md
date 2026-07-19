# P5.17 — bankv3-select: a lag-stress sim bank that can actually cost RG its 4.4 s, then the P5.13 A/B at n >= 25

**Pre-registered:** 2026-07-20T00:55Z (Madrid wall clock). Design + patches by
Fable; Opus runs the matrix and fills Results only — do NOT re-patch code.
**Status:** COMPLETE 2026-07-20T01:45Z — BUILD PASS (28/28), select verdict
**NO [branch 3 — contracts-equivalent]** (DD 56/56 vs RG 55/56, |diff| 1 < 7).
Visual gate V PASS on both halves (does not downgrade).
**Branch:** `experiment/bankv3-select`
**Rig:** RTX 3090 workstation (Gazebo Sim 8.14.0 headless + SAM2
sam2.1-hiera-tiny bf16), Jetson Orin Nano 8 GB over `ssh jetson` for the VLM
(Qwen2-VL-2B q8_0 terse, llama.cpp, 15W + jetson_clocks — the only power mode
this board has, see memory). `.venv-ft`: Python 3.12, torch 2.6.0+cu124,
opencv 4.13.0, numpy 2.4.4. Versions are also stamped into every
`results.json` by the scripts.

## Research question

**RQ-P5.17a (gating):** On a sim bank whose scenes make the prompt-time
re-ground lag *geometrically costly* (every clip: GT box at the RG deliver
frame f260 has IoU <= 0.20 with the GT box at the prompt frame f150, for BOTH
cars) and that implements all three P5.13-mandated diversity gates, do the two
delivery contracts finally separate?
**Threshold:** |DD_total − RG_total| >= **7 cells** of n_cells (n_cells =
2 × n_valid_clips, n_valid_clips >= 25, so n_cells 50–56). Overall **YES iff
branch 1** (DD − RG >= 7); every other branch is a NO with a pre-registered
interpretation (see Verdict rules). Health floor for the tie branch:
ceil(0.8 × n_cells) per contract.

**RQ-P5.17b (diagnostic, non-gating):** far-leg DD failures − near-leg DD
failures >= 3 → the occlusion aftermath (named car was the occluded one), not
generic drift, is what breaks the carry.

This is one experiment with a build gate inside it: the select A/B only runs
if the bank build passes mechanically (>= 25/28 clips through all gates).
A build FAIL is a NO [build] result, documented like any other.

## Context and audit (what was looked at)

- **Human steer:** "continue experiments in the sim" + the standing
  sample-size rule (n >= 25 per gating arm, thresholds as counts, hard cap
  10 h, target ~1 h). The sim arc stands at P5.10 tie (bank v1 too easy),
  P5.11 build NO (gate mis-calibration, resolved), P5.12 build YES, P5.13
  select tie (branch 3). The DIRECTION PICK's purpose — "make the sim able to
  DISCRIMINATE direct-delivery from prompt-time re-grounding" — is executed
  here, not overridden.
- **Pixels opened at design time (Read tool):** P5.12
  `proof/p512_occlusion_montage.png` (all 12 crossing peaks near-identical:
  same blue-in-front-left composition — the S9/peak-span gates exist because
  of this image), `proof/p512_crossing_traces.png`, P5.13
  `proof/p513_*` cell grid + overlays (post-crossing segment near-static:
  named-car centre moves 0.4–15.6 px over the 109-frame delivery lag —
  measured, this is why RG's lag was FREE and the contracts tied), P5.9/P5.11
  committed frames.
- **Why the tie happened (code-located in `runners/scenegen.py` v2):** the
  camera tracks the two-car midpoint EVERY frame (post-prompt image motion
  ~0), `ds0` always negative (blue always the occluder, z-order constant in
  12/12 clips), `t_in0 ~ U(0.7, 1.0)` + narrow camera bands (every peak the
  same picture). Bank v3 changes exactly these three things.
- **Under-powered prior YESes (flagged, not re-run here):** P5.14 and P5.16
  are YES at n=5 gating scenes; under the standing rule they are anecdotes
  until re-run at n >= 25 on real video. This cycle serves the sim steer
  first; the real-video re-power is the natural next cycle if P5.17 lands
  branch 1 or 3.

### What each contract actually risks here (so the RQ is falsifiable, not rigged)

DD delivers the carried ZOH box AT f150 (acquire 0.00 s) — it is scored
against GT at f150 and is insensitive to post-prompt staleness; its risk is
the carry surviving the designed crossing (f42–f104 peaks). RG re-grounds the
f150 frame on the Jetson (~4.4 s), IoU-matches against the carried boxes at
f150, and delivers the matched track's ZOH box at ~f260 — the carry keeps
stepping through the lag, so RG's delivered box is carry-fresh within 8
frames; its risks are the VLM/match at f150 PLUS the carry surviving 110
MORE frames in which both cars recede fast (the camera anchor freezes at
f150; S8 guarantees the GT boxes move to IoU <= 0.20). The staleness gate is
therefore NOT a tautological "RG loses by construction": if SAM2 tracks the
receding cars cleanly (as it tracked everything in P5.10/P5.13), RG passes
and branch 3 fires. Branch 3 at this n, with realized staleness AND designed
crossings, is pre-registered as the CLOSE of the sim-select discrimination
question.

### Losing design candidates (for DECISIONS at merge)

1. **n >= 25 GT-free discovery validation in sim (P5.16 protocol on a sim
   bank):** rejected — changes two things at once vs P5.13 (bank AND
   seeding), discovery is colour-trivial on clean renders (P5.10: VLM
   grounded 24/24 first call), and the P5.13-mandated bank gates would go
   unexecuted a third time; also needs a ~9.5 s idle window → longer clips →
   new corridor math.
2. **Build-gate-only cycle (bank v3 alone, select later):** rejected — the
   P5.12 offline screen predicted every recorded gate value with delta 0 on
   all 12 clips including 6 unseen seeds, so the build is de-risked enough
   that stopping at build wastes the science slot.

## Code changes (all already committed by Fable on this branch — Opus: do NOT edit)

| File | Change |
|---|---|
| `runners/scenegen.py` | NEW `--profile v3` (`author_scenario_v3`): post-prompt camera anchor freeze at f150 (bob/sway stay on the true clock → feed alive, cars recede → real staleness); seeded z-order coin (`near` = white or blue, gap sign fixed per clip, no mid-clip z-flip — asserted); randomized pull-out end `t_end ~ U(4.2, 5.5) s` + wider camera bands (standoff 20–30 m, alt 3.5–7 m, aim ±2.5 m) for crossing-peak diversity. NEW offline screen `screen3` (S1–S9 incl. NEW S8 staleness + S9 set rules) + `V3_BANK_PINNED` (28 seeds). NEW selfcheck section 6h pinning all of it; sections 1–6g (v1/v2 pins) untouched and re-verified green. |
| `select_p517.py` | Forward-copy of P5.13's `select_p513.py`. Diff confined to: bank path (`runs/bank/`), clip list read from `runs/bank_valid.json` (never hand-typed), `p513→p517` strings. Carry pass, contracts, thresholds (MATCH_FLOOR 0.10, DELIVER_FLOOR 0.25, dominance rule), fail taxonomy, resumability: byte-similar → any A/B change vs P5.13 is scene-attributable. |
| `verdict_p517.py` | `--build` mode: per-clip gates G0/G1/G2c/G3/G5/G6c/G8/G9/G10 (G10 NEW: staleness realized in recorded GT; G9 extended with recorded z-order pin), cross-run G4a ×2 / G4b / G7 / G11 (NEW: valid-set diversity), writes `runs/bank_valid.json`. Select mode: SEP_MARGIN 7, health floor ceil(0.8·n), infra caps, 4 interpretation branches. Selfcheck: synthetic v3 fixture passes all gates + 6 doctored negatives fire. |
| `make_proof.py` | `p517_peak_montage.png`, `p517_staleness.png`, `p517_dd_vs_rg_cells.png` (reproducible from runs + authored scenarios). |
| `proof/p517_staleness.png` | Committed at pre-registration (deterministic, no run needed): v2.1 median ZOH IoU ~0.8 at f260 (the P5.13 tie, explained) vs v3 median ~0.08 with all 28 seeds <= 0.20 — the mechanism this bank adds, verified by looking before spending GPU time. |

All three selfchecks were run green at design time
(`scenegen.py selfcheck`, `select_p517.py --selfcheck`,
`verdict_p517.py --selfcheck`); Opus re-runs them in Step 0 (cheap, ~2 min).

### The v3 admission screen (already run at design time, ~3 s, offline)

`screen3` over seeds 1–300 with early stop admitted **28 seeds within
1–122**: `[2, 3, 6, 7, 8, 13, 17, 18, 21, 28, 32, 42, 48, 57, 68, 69, 70,
74, 89, 91, 92, 98, 101, 103, 104, 112, 116, 122]`, pinned as
`V3_BANK_PINNED`. Exact 14/14 near-white/near-blue mix (S9a), peak_f span 62
(42–104, S9b >= 30), 34/122 pass S1–S6+S8 (screen has teeth: seed 1 fails
predicted clear 33 < 45; seeds 111/117 fail S8 staleness). Admitted ranges:
peak IoU 0.209–0.463, run_occl50 35–88, clear_far 49–199, stale IoU
0.000–0.194 (all <= 0.20), tail 0.009–0.141. Min pairwise divergence over
the 28 = 1.32 m (G4b floor 1.0). All pinned in selfcheck 6h.

## Run matrix (Opus: execute top to bottom; zero judgment calls)

Everything from `/home/gara/jetson` on branch `experiment/bankv3-select`.
`EXP=experiments/2026-07-20-bankv3-select`. Raw logs → `$EXP/raw/`.

### Step 0 — preconditions (~3 min)

```bash
cd /home/gara/jetson && git checkout experiment/bankv3-select
mkdir -p experiments/2026-07-20-bankv3-select/{raw,runs/bank}
.venv-ft/bin/python runners/scenegen.py selfcheck                       # "scenegen selfcheck OK"
.venv-ft/bin/python experiments/2026-07-20-bankv3-select/select_p517.py --selfcheck   # "select_p517 selfcheck OK"
.venv-ft/bin/python experiments/2026-07-20-bankv3-select/verdict_p517.py --selfcheck  # "verdict_p517 selfcheck OK"
nvidia-smi --query-gpu=name --format=csv,noheader                       # RTX 3090
```

Any selfcheck failure = STOP, campaign INCOMPLETE (the frozen design
drifted); do not patch code, report back.

### Step 1 — record the 30 runs (~40 min)

30 runs = 28 bank clips + 2 determinism re-records. Run table (RUN ↔ SEED;
`_R` = re-record of the same seed in a FRESH server session, which the
per-run pattern below guarantees):

| RUN | SEED | | RUN | SEED | | RUN | SEED |
|---|---|---|---|---|---|---|---|
| s002 | 2 | | s042 | 42 | | s092 | 92 |
| s003 | 3 | | s048 | 48 | | s098 | 98 |
| s006 | 6 | | s057 | 57 | | s101 | 101 |
| s007 | 7 | | s068 | 68 | | s103 | 103 |
| s008 | 8 | | s069 | 69 | | s104 | 104 |
| s013 | 13 | | s070 | 70 | | s112 | 112 |
| s017 | 17 | | s074 | 74 | | s116 | 116 |
| s018 | 18 | | s089 | 89 | | s122 | 122 |
| s021 | 21 | | s091 | 91 | | s002_R | 2 |
| s028 | 28 | | s032 | 32 | | s007_R | 7 |

(Flat list, same content, copy-paste safe: seeds `2 3 6 7 8 13 17 18 21 28
32 42 48 57 68 69 70 74 89 91 92 98 101 103 104 112 116 122` as runs
`s%03d` — this is `V3_BANK_PINNED` in order — plus `s002_R` seed 2 and
`s007_R` seed 7. Run order does not matter; completeness does.)

Per run — this is the P5.12-proven pattern, 16/16 first-attempt there.
**Keep the `nohup gz sim` launch as its own clean background command** (the
Bash sandbox reaper kills gz+python combos). You may chain up to 3 of these
blocks per Bash call; each block must keep its internal order:

```bash
cd /home/gara/jetson
EXP=experiments/2026-07-20-bankv3-select
SEED=2 RUN=s002        # <-- change per run, table above

# 0. guarantee no stale server (exit 0 = clean; MUST print "remaining: 0")
.venv-ft/bin/python runners/scenegen.py killserver

# 1. fresh headless server, nohup'd alone (EGL env line or frames are BLACK)
SITL=$PWD/runners/sitl/external/SITL_Models/Gazebo
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json \
GZ_SIM_RESOURCE_PATH="$SITL/models:$SITL/worlds" \
nohup gz sim -s runners/sitl/worlds/select_arena.sdf > $EXP/raw/gz_$RUN.log 2>&1 &

# 2. wait for the camera topic (~15-25 s world load)
for i in $(seq 40); do gz topic -l 2>/dev/null | grep -q uav_cam && break; sleep 3; done
gz topic -l | grep uav_cam   # MUST print the image topic

# 3. record (~35-45 s loop at ~8 fps + finalize; DONE line at end)
nohup .venv-ft/bin/python runners/scenegen.py record --seed $SEED --frames 300 \
    --profile v3 --out $EXP/runs/bank/$RUN > $EXP/raw/rec_$RUN.log 2>&1 &
for i in $(seq 60); do test -f $EXP/runs/bank/$RUN/results.json && break; sleep 5; done
tail -5 $EXP/raw/rec_$RUN.log   # expect "[scenegen] DONE ..."

# 4. kill this session's server (verified process-group kill)
.venv-ft/bin/python runners/scenegen.py killserver
```

`--profile v3` is REQUIRED on every record call — a bare run writes v1
240-frame clips that fail G0/G9/G10.

**Infra rule (pre-registered):** a run dying mid-record → retry ONCE with a
fresh server. Second death of the same run: bank clip → write
`$EXP/runs/bank/<RUN>.INFRA` (one line: reason) and move on; `s002_R`/
`s007_R` → campaign INCOMPLETE (G4a needs them; fix infra first). **> 3
INFRA bank clips = build INVALID** (cannot reach n = 25; verdict enforces via
the >= 25 floor). `gz topic -l` empty after 120 s: killserver, check
`raw/gz_$RUN.log`, retry once; twice = INCOMPLETE. Total wall past 3× the
estimate: stop, snapshot logs, INCOMPLETE — do not grind.

### Step 2 — build verdict (~4 min, offline + frame reads)

```bash
.venv-ft/bin/python experiments/2026-07-20-bankv3-select/verdict_p517.py --build
```

Prints the full gate table and writes `runs/bank_valid.json`. Expected line:
`P5.17 BUILD: PASS -- <n>/28 clips valid` with n >= 25 (estimate: 26–28).
BUILD FAIL or INCOMPLETE → the select matrix does NOT run; record the table
in Results, verdict is **NO [build]**, jump to Step 6. **No threshold may
move during or after the run.**

### Step 3 — visual gate V, build half (mandatory, Read tool)

Deterministic sampling rule (n >= 25, so sampled + exhaustive-on-failures):
sort the `valid` list of `runs/bank_valid.json` lexicographically; take ranks
1, 8, 15, 22, and the last. For each of those 5 clips open with the Read
tool:

1. `runs/bank/<RUN>/overlay_f<peak>.png` where `<peak>` =
   `v3_xpeak_pred_f` from that run's `results.json` (4-digit zero-padded).
   **PASS looks like:** two cars on the road, each under a green GT box, the
   two boxes overlapping, and the car IN FRONT (partially covering the
   other) has the colour named in the build table's `near` column for that
   run. **FAIL looks like:** black/uniform frame; boxes on empty road; boxes
   not overlapping; the WRONG colour in front (z-order defect).
2. `runs/bank/<RUN>/overlay_f0150.png` AND `overlay_f0225.png`. **PASS:**
   both cars present in both; at f0225 both cars are VISIBLY smaller /
   farther down-road than at f0150 (the camera hold is real → staleness is
   real). **FAIL:** the two frames look the same (hold not working — G10
   should have caught it; if your eyes disagree with a passing G10, V
   downgrades).

Additionally open the same two files for EVERY bank clip that FAILED a gate
(cap 12, first by run order) and note what the failure looks like. Write one
line per opened image into Results ("looked at X: saw Y"). V can only
DOWNGRADE (a clip from valid → dropped, rerun `--build` prints nothing new —
instead document the downgrade in Results and, if valid drops below 25, the
verdict becomes NO [build/V]).

### Step 4 — select matrix (~25 min: SAM2 carries + Jetson VLM)

```bash
# offline bank preflight first (asserts phrases, frame health, gt schema)
.venv-ft/bin/python experiments/2026-07-20-bankv3-select/select_p517.py --preflight

# the matrix (resumable; completed cells are skipped on re-run)
nohup .venv-ft/bin/python experiments/2026-07-20-bankv3-select/select_p517.py \
    --matrix > experiments/2026-07-20-bankv3-select/raw/matrix.log 2>&1 &
# poll: watch cell lines appear; done when it prints "[P5.17] matrix done"
tail -3 experiments/2026-07-20-bankv3-select/raw/matrix.log
```

The script boots the Jetson llama.cpp server itself (reboot-once on
exception is built in). **Infra rule:** a cell that dies → re-run the matrix
command once (it resumes); a cell failing twice → write
`runs/<clip>_<leg>.INFRA` (one line: reason). INFRA counts FAIL for BOTH
contracts; **> 2 INFRA select cells = NO [infra]** (verdict enforces).

### Step 5 — select verdict + visual gate V, select half

```bash
.venv-ft/bin/python experiments/2026-07-20-bankv3-select/verdict_p517.py
```

Paste the FULL output into Results. Then with the Read tool open, for the
same 5 rank-sampled clips (Step 3 rule), the white-leg cell overlays:
`runs/<clip>_white/overlay_dd_f0150.png`, `overlay_vlm_f0150.png`, and
`overlay_rg_fNNNN.png` where NNNN = the 4-digit `delivF` from that cell's
verdict table row (e.g. `overlay_rg_f0262.png`).
**PASS looks like:** red box (named GT) on the white car, green box
(delivered) on/around the same car; in the RG overlay the green box sits on
the car AT ITS f-deliver position (cars visibly farther than at f150), not
hanging in the air at the f150 position. **FAIL:** green box on the other
car (switch), green box on empty road at the old position (stale/lost),
yellow VLM box on the wrong car. Also open the DD and RG overlays of EVERY
failing cell (cap 12, first by clip order) and write one line each into
Results. V can only downgrade (a cell PASS your eyes contradict → document,
flip that cell to FAIL, recompute the totals BY HAND in Results — the
mechanical output stays in the record unedited).

### Step 6 — proof, docs, commit

```bash
.venv-ft/bin/python experiments/2026-07-20-bankv3-select/make_proof.py
```

Open all 3 PNGs with the Read tool (montage: 28 labelled peak tiles, red
border only on non-valid clips; staleness: v3 curves under 0.20 at f260, v2.1
high; cells grid: green/red consistent with the verdict totals). Then:

1. Fill **Results** below (tables + verdict output + every "looked at" line).
2. Append the RESULTS row(s) to `docs/results/part5-anticipatory.md`, the
   QUESTIONS entry (RQ-P5.17a/b + one-line verdict) to
   `docs/questions/part5-anticipatory.md`, and the DECISIONS entry (bank-v3
   design choices + the two losing candidates above) to
   `docs/decisions/part5-anticipatory.md`. No new SOURCES expected (no new
   external asset; note it if one sneaks in).
3. Commit everything on this branch (runs/ stays uncommitted per repo
   convention EXCEPT `runs/bank_valid.json`; proof/ and raw logs <= 5 MB are
   committed; large mp4/frames stay local). Do NOT merge — Fable audits.

## Verdict rules (mechanical — `verdict_p517.py` is the authority)

Build: PASS iff >= 25/28 clips pass G0,G1,G2c,G3,G5,G6c,G8,G9,G10 AND G4a
(both pairs) AND G4b AND G7 AND G11, <= 3 INFRA. Numeric definitions in the
script docstring (committed before the run).

Select (RQ-P5.17a), n_cells = 2 × n_valid, floor = ceil(0.8 × n_cells):

- **Branch 1 — DD − RG >= 7: YES.** The lag-stress bank reproduces P5.14's
  real-video delivery-contract separation in sim at n >= 25; bank v3 is a
  working discriminating test-bed.
- **Branch 2 — RG − DD >= 7: NO [inverted].** Re-grounding repairs what the
  crossing breaks; inverts the P5.14 conclusion for occluded targets; next
  lever = hybrid carry + re-ground confirmation.
- **Branch 3 — |diff| < 7, both >= floor: NO [contracts-equivalent].** Third
  consecutive sim tie, now at proper n with realized staleness and designed
  crossings: sim-select discrimination is CLOSED; DD's real-video advantage
  is attributed to real-imagery VLM fragility clean renders cannot
  reproduce; select levers move to real video.
- **Branch 4 — |diff| < 7, a contract < floor: NO [carry/stack-bound].**
  Diagnose the stack before re-asking the contract question.

No post-hoc branches; the matching one applies as written. V only downgrades.

## Estimates (marked as estimates)

| Piece | Estimate | Basis |
|---|---|---|
| Step 0 selfchecks | ~3 min | measured at design time |
| 30 record runs | ~40 min (~75 s each) | P5.12 actual: 16 runs in ~18 min |
| Build verdict | ~4 min | G4a reads 1200 PNGs + 28 grades |
| Visual gate (build) | ~5 min | 10–34 images |
| Carry passes | ~4 min | P5.13 actual 5.8–6.5 s/clip × 28 |
| VLM leg | ~8 min | 2×n_valid calls × ~4.5 s + boot ~90 s |
| Select matrix wall | ~20–25 min | P5.13 matrix ≈ 15 min at 12 clips |
| Select verdict + V + proof | ~10 min | offline |
| **Total** | **~1 h 20 min** | 10 h hard cap ≈ 7× headroom |

Expected numbers (estimates, not claims): build valid 26–28/28 (offline
screen predicted recorded values with delta 0 in P5.12); DD_total
0.85–0.95 × n_cells; RG_total lower, dominated by DELIVERY_DRIFT /
DELIVERY_LOST if SAM2 loses the receding cars, else ≈ DD (branch 3). My
prediction: **branch 1** at modest margin; branch 3 is the live alternative
and is a publishable close-out, not a wasted run.

## Results (TBD — Opus fills; do not edit anything above this line except Status)

### Build gate table (full `--build` output)

```
run      seed near  G0 G1 G2c G3 G5 G6c G8 G9 G10 fps    purF/N        ffragp10 nclr nocc ndom   xpeak staleT/D
s002     2    white 1  1  1   1  1  1   1  1  1   8.84   0.675/0.796   1.0    110  58   0.662  83    0.127/0.16
s003     3    white 1  1  1   1  1  1   1  1  1   8.80   0.803/0.803   1.0    49   51   0.643  90    0.165/0.137
s006     6    white 1  1  1   1  1  1   1  1  1   8.79   0.743/0.796   1.0    82   58   0.665  100   0.096/0.181
s007     7    blue  1  1  1   1  1  1   1  1  1   8.67   0.701/0.766   1.0    109  42   0.513  80    0.027/0.0
s008     8    white 1  1  1   1  1  1   1  1  1   8.71   0.694/0.768   1.0    86   35   0.508  83    0.06/0.115
s013     13   white 1  1  1   1  1  1   1  1  1   8.79   0.680/0.730   1.0    115  45   0.585  99    0.032/0.052
s017     17   blue  1  1  1   1  1  1   1  1  1   8.76   0.596/0.826   0.994    69   86   0.652  87    0.061/0.032
s018     18   blue  1  1  1   1  1  1   1  1  1   8.66   0.761/0.816   0.993    75   88   0.559  46    0.031/0.037
s021     21   white 1  1  1   1  1  1   1  1  1   8.84   0.566/0.772   1.0    111  42   0.664  55    0.078/0.097
s028     28   blue  1  1  1   1  1  1   1  1  1   8.89   0.841/0.807   0.992    63   76   0.804  92    0.177/0.135
s032     32   blue  1  1  1   1  1  1   1  1  1   8.72   0.701/0.836   0.999    61   80   0.506  47    0.179/0.108
s042     42   blue  1  1  1   1  1  1   1  1  1   8.70   0.769/0.808   0.999    103  69   0.591  102   0.016/0.012
s048     48   blue  1  1  1   1  1  1   1  1  1   8.80   0.669/0.851   1.0    96   71   0.664  42    0.163/0.137
s057     57   blue  1  1  1   1  1  1   1  1  1   8.74   0.690/0.815   0.993    58   74   0.558  88    0.067/0.03
s068     68   blue  1  1  1   1  1  1   1  1  1   8.62   0.707/0.782   0.993    85   63   0.546  98    0.062/0.001
s069     69   white 1  1  1   1  1  1   1  1  1   8.86   0.624/0.769   1.0    113  62   0.742  104   0.143/0.178
s070     70   white 1  1  1   1  1  1   1  1  1   8.79   0.756/0.790   1.0    107  42   0.624  90    0.073/0.114
s074     74   blue  1  1  1   1  1  1   1  1  1   8.77   0.827/0.790   0.992    54   83   0.695  92    0.064/0.028
s089     89   blue  1  1  1   1  1  1   1  1  1   8.77   0.644/0.797   1.0    112  79   0.598  98    0.096/0.057
s091     91   blue  1  1  1   1  1  1   1  1  1   8.80   0.662/0.819   1.0    98   77   0.681  98    0.194/0.143
s092     92   white 1  1  1   1  1  1   1  1  1   8.75   0.775/0.776   1.0    67   45   0.603  82    0.058/0.099
s098     98   white 1  1  1   1  1  1   1  1  1   8.77   0.490/0.734   1.0    55   60   0.717  82    0.083/0.152
s101     101  white 1  1  1   1  1  1   1  1  1   8.79   0.876/0.752   1.0    58   44   0.637  93    0.04/0.064
s103     103  blue  1  1  1   1  1  1   1  1  1   8.73   0.780/0.856   0.992    59   84   0.62   98    0.113/0.081
s104     104  white 1  1  1   1  1  1   1  1  1   8.75   0.542/0.736   1.0    71   46   0.592  48    0.026/0.08
s112     112  white 1  1  1   1  1  1   1  1  1   8.70   0.682/0.780   1.0    199  44   0.55   94    0.109/0.15
s116     116  blue  1  1  1   1  1  1   1  1  1   8.77   0.682/0.837   0.996    109  80   0.744  64    0.168/0.191
s122     122  white 1  1  1   1  1  1   1  1  1   8.79   0.711/0.794   1.0    106  53   0.603  99    0.04/0.062
G4a determinism s002 vs s002_R (seed 2): gt_identical=True frame_mean_absdiff=0.0 (<= 2.0) frac_gt8=0.0 (<= 0.01) -> PASS
G4a determinism s007 vs s007_R (seed 7): gt_identical=True frame_mean_absdiff=0.0 (<= 2.0) frac_gt8=0.0 (<= 0.01) -> PASS
G4b seed diversity (28 seeds, v3): min pairwise scenario divergence 1.32 m (>= 1.0) at pair (21, 101); recorded-f0 faithful=True over 30 runs -> PASS
G7 screen pin: v3 screen admission reproduces the pinned bank: [2, 3, 6, 7, 8, 13, 17, 18, 21, 28, 32, 42, 48, 57, 68, 69, 70, 74, 89, 91, 92, 98, 101, 103, 104, 112, 116, 122] -> PASS
G11 valid-set diversity: near-white 14 (>= 10), near-blue 14 (>= 10), recorded peak span 62 (>= 30) -> PASS
P5.17 BUILD: PASS -- 28/28 clips valid, bank_valid.json written (PASS iff >= 25 valid AND G4a x2 AND G4b AND G7 AND G11 AND <= 3 infra; the visual gate V can only downgrade)
```

### Visual gate V — build ("looked at <path>: saw <one line>")

- looked at `runs/bank/s002/overlay_f0083.png` (peak, near=white): saw two cars mid-road under overlapping green GT boxes, the white car in front of the blue one -- matches `near=white`.
- looked at `runs/bank/s018/overlay_f0046.png` (peak, near=blue): saw the blue car in front, white behind and partly occluded by it, both boxed -- matches `near=blue`.
- looked at `runs/bank/s068/overlay_f0098.png` (peak, near=blue): saw a tight blue-in-front crossing, the white car's box mostly hidden behind the blue body -- genuine occlusion, not two side-by-side cars.
- looked at `runs/bank/s098/overlay_f0082.png` (peak, near=white): saw the white car in front, blue behind and above it in image space -- matches `near=white`.
- looked at `runs/bank/s122/overlay_f0099.png` (peak, near=white): saw the white car in front at a wider lateral gap than s068 -- the bank spans loose to tight crossings, not one repeated geometry.
- looked at `runs/bank/s002/overlay_f0150.png` + `overlay_f0225.png`: cars visibly smaller/farther at f225, checkerboard shifted down-frame -- recession real, feed alive.
- looked at `runs/bank/s018/overlay_f0150.png` + `overlay_f0225.png`: same recession; boxes shrink with the cars and stay on them.
- looked at `runs/bank/s068/overlay_f0150.png` + `overlay_f0225.png`: same, cars near the vanishing point by f225.
- looked at `runs/bank/s098/overlay_f0150.png` + `overlay_f0225.png`: same; road surface and barriers render normally (no black frame, no uniform fill).
- looked at `runs/bank/s122/overlay_f0150.png` + `overlay_f0225.png`: same; the checkerboard sits at a different position than the other four clips at the same frame index, so these are genuinely different scenarios, not one clip copied.
- looked at `proof/p517_peak_montage.png`: 28 labelled peak tiles, every tile shows two boxed cars, **no red border on any tile** (all 28 valid) -- consistent with the build table.
- looked at `proof/p517_staleness.png`: bank v3 median ZOH IoU **0.08** at the f260 deliver line with every per-seed curve under 0.20, vs bank v2.1 median **~0.79** -- the lag-stress mechanism this bank was built for is measured, not asserted.
- looked at `proof/p517_dd_vs_rg_cells.png`: 28 x 4 grid, all green except a single red at (s003, RG white) -- matches DD 56/56, RG 55/56 exactly.

### Select verdict (full output incl. branch marks)

```
cell        role  DD    dd_class      ddIoU  RG    rg_class        vlm_on  acq_s  delivF  ddCov  rgCov  
s002_blue   far   PASS  None          0.581  PASS  None            named   4.35   259     1.000  1.000  
s002_white  near  PASS  None          0.632  PASS  None            named   4.35   259     0.927  0.927  
s003_blue   far   PASS  None          0.604  PASS  None            named   4.34   259     1.000  1.000  
s003_white  near  PASS  None          0.605  FAIL  DELIVERY_DRIFT  named   4.34   259     0.627  0.098  
s006_blue   far   PASS  None          0.552  PASS  None            named   4.34   259     1.000  1.000  
s006_white  near  PASS  None          0.595  PASS  None            named   4.34   259     1.000  1.000  
s007_blue   near  PASS  None          0.583  PASS  None            named   4.35   259     1.000  1.000  
s007_white  far   PASS  None          0.583  PASS  None            named   4.35   259     1.000  1.000  
s008_blue   far   PASS  None          0.526  PASS  None            named   4.35   259     1.000  1.000  
s008_white  near  PASS  None          0.582  PASS  None            named   4.35   259     1.000  1.000  
s013_blue   far   PASS  None          0.512  PASS  None            named   4.34   259     1.000  1.000  
s013_white  near  PASS  None          0.432  PASS  None            named   4.34   259     1.000  1.000  
s017_blue   near  PASS  None          0.605  PASS  None            named   4.34   258     1.000  1.000  
s017_white  far   PASS  None          0.597  PASS  None            named   4.34   259     1.000  1.000  
s018_blue   near  PASS  None          0.608  PASS  None            named   4.35   259     1.000  1.000  
s018_white  far   PASS  None          0.639  PASS  None            named   4.35   259     1.000  1.000  
s021_blue   far   PASS  None          0.539  PASS  None            named   4.33   258     1.000  1.000  
s021_white  near  PASS  None          0.593  PASS  None            named   4.33   258     1.000  1.000  
s028_blue   near  PASS  None          0.615  PASS  None            named   4.33   258     1.000  1.000  
s028_white  far   PASS  None          0.600  PASS  None            named   4.33   258     1.000  1.000  
s032_blue   near  PASS  None          0.611  PASS  None            named   4.34   259     1.000  1.000  
s032_white  far   PASS  None          0.631  PASS  None            named   4.34   259     0.940  0.780  
s042_blue   near  PASS  None          0.614  PASS  None            named   4.35   259     1.000  1.000  
s042_white  far   PASS  None          0.623  PASS  None            named   4.35   259     1.000  1.000  
s048_blue   near  PASS  None          0.640  PASS  None            named   4.34   258     1.000  1.000  
s048_white  far   PASS  None          0.633  PASS  None            named   4.34   258     1.000  1.000  
s057_blue   near  PASS  None          0.630  PASS  None            named   4.34   259     1.000  1.000  
s057_white  far   PASS  None          0.622  PASS  None            named   4.34   259     1.000  1.000  
s068_blue   near  PASS  None          0.564  PASS  None            named   4.36   259     1.000  1.000  
s068_white  far   PASS  None          0.585  PASS  None            named   4.36   259     1.000  1.000  
s069_blue   far   PASS  None          0.560  PASS  None            named   4.33   258     1.000  1.000  
s069_white  near  PASS  None          0.599  PASS  None            named   4.33   258     0.840  1.000  
s070_blue   far   PASS  None          0.575  PASS  None            named   4.34   259     1.000  1.000  
s070_white  near  PASS  None          0.599  PASS  None            named   4.34   259     1.000  1.000  
s074_blue   near  PASS  None          0.600  PASS  None            named   4.34   258     1.000  1.000  
s074_white  far   PASS  None          0.580  PASS  None            named   4.34   258     1.000  1.000  
s089_blue   near  PASS  None          0.600  PASS  None            named   4.34   258     1.000  1.000  
s089_white  far   PASS  None          0.616  PASS  None            named   4.34   258     0.893  1.000  
s091_blue   near  PASS  None          0.622  PASS  None            named   4.34   258     1.000  1.000  
s091_white  far   PASS  None          0.619  PASS  None            named   4.34   259     1.000  1.000  
s092_blue   far   PASS  None          0.569  PASS  None            named   4.34   259     1.000  1.000  
s092_white  near  PASS  None          0.611  PASS  None            named   4.34   259     1.000  1.000  
s098_blue   far   PASS  None          0.538  PASS  None            named   4.34   259     1.000  1.000  
s098_white  near  PASS  None          0.554  PASS  None            named   4.34   259     1.000  1.000  
s101_blue   far   PASS  None          0.525  PASS  None            named   4.34   258     1.000  1.000  
s101_white  near  PASS  None          0.569  PASS  None            named   4.34   258     1.000  1.000  
s103_blue   near  PASS  None          0.621  PASS  None            named   4.35   259     1.000  1.000  
s103_white  far   PASS  None          0.658  PASS  None            named   4.35   259     1.000  1.000  
s104_blue   far   PASS  None          0.518  PASS  None            named   4.34   259     1.000  1.000  
s104_white  near  PASS  None          0.568  PASS  None            named   4.34   259     1.000  1.000  
s112_blue   far   PASS  None          0.538  PASS  None            named   4.34   259     1.000  1.000  
s112_white  near  PASS  None          0.598  PASS  None            named   4.35   259     1.000  1.000  
s116_blue   near  PASS  None          0.623  PASS  None            named   4.34   259     1.000  1.000  
s116_white  far   PASS  None          0.602  PASS  None            named   4.34   258     1.000  1.000  
s122_blue   far   PASS  None          0.557  PASS  None            named   4.34   258     1.000  1.000  
s122_white  near  PASS  None          0.588  PASS  None            named   4.34   258     1.000  1.000  

DD_total 56/56  RG_total 55/56  (health floor 45 = ceil(0.8*56))
DD by named-car role: far 28/28, near 28/28
DD fail classes: {}  RG fail classes: {'DELIVERY_DRIFT': 1}

RQ-P5.17a (|DD_total - RG_total| >= 7 of 56): NO (DD 56 vs RG 55, |diff| 1)
RQ-P5.17b (DIAGNOSTIC, non-gating; far-leg DD fails minus near-leg DD fails >= 3): NO (asym 0) -- YES means the occlusion aftermath, not generic drift, breaks the carry
OVERALL RQ-P5.17: NO (YES iff branch 1; the visual gate V can only downgrade)

Pre-registered interpretation branches (the matching one applies):
  [ ] branch 1: DD - RG >= 7: the lag-stress bank reproduces P5.14's real-video delivery-contract separation in sim at n >= 25 -- the staleness mechanism (target moves during the ~4.4 s re-ground lag) is sufficient to separate the contracts, and bank v3 is a working discriminating test-bed for select levers.
  [ ] branch 2: RG - DD >= 7: prompt-time re-grounding WINS on lag-stress scenes -- the carry through the crossing is the weak link and the VLM repairs it. Inverts the P5.14 delivery-contract conclusion for occluded targets; next lever = hybrid carry + re-ground confirmation.
  [X] branch 3: No separation, both contracts >= ceil(0.8*n): third consecutive sim contract tie, now at proper n WITH realized staleness and designed crossings. Pre-registered conclusion: sim-select discrimination is CLOSED -- the DD advantage seen on real video (P5.14) is attributable to real-imagery VLM fragility that clean renders cannot reproduce; further select levers must be tested on real video.
  [ ] branch 4: No separation, at least one contract < ceil(0.8*n): the stack fails upstream of the delivery contract (carry loss on both, or VLM failure on both); diagnose the stack before re-asking the contract question.
```

### Visual gate V — select

- looked at `runs/s002_white/overlay_dd_f0150.png`: green delivered box on the white car inside the red namedGT -- DD hands over the carried box with no lag. `overlay_vlm_f0150.png`: yellow VLM box on the white car (correct car). `overlay_rg_f0259.png`: green box on the white car **at its f259 position** (both cars visibly farther than at f150), not stranded at the f150 spot. PASS.
- looked at `runs/s018_white/{overlay_dd_f0150,overlay_vlm_f0150,overlay_rg_f0259}.png`: same pattern; the blue car is the near one here and neither box drifts onto it. PASS.
- looked at `runs/s068_white/{overlay_dd_f0150,overlay_vlm_f0150,overlay_rg_f0259}.png`: same; this is the tightest crossing sampled and the carry still holds the white car through it. PASS.
- looked at `runs/s098_white/{overlay_dd_f0150,overlay_vlm_f0150,overlay_rg_f0259}.png`: same. PASS.
- looked at `runs/s122_white/{overlay_dd_f0150,overlay_vlm_f0150,overlay_rg_f0258}.png`: same. PASS.
- **Failing cell** `runs/s003_white/overlay_rg_f0259.png`: the delivered green box is blown up to a huge region covering the road, the right barrier and the checkerboard, while the white car sits far to the left under its red namedGT -- a genuine mask blow-up during the 4.34 s re-ground lag, correctly classed `DELIVERY_DRIFT` (rgCov 0.098). The same clip's `overlay_dd_f0150.png` shows a tight green box on the white car (DD PASS) and `overlay_vlm_f0150.png` a correct yellow box on the white car, so the failure is in RG's post-grounding carry, not in the VLM pick.
- V verdict: **PASS on both halves -- no downgrade.** Every sampled PASS cell looks like a pass, and the one mechanical FAIL looks like a real failure.

### Estimate vs actual

| Piece | Estimated | Actual |
|---|---|---|
| record runs | ~40 min | **~31 min** (30 runs, 8.62–8.89 fps; one `s103` renderer stall, retried once per the pre-registered infra rule, passed) |
| select matrix | ~20–25 min | **~7 min** (56 cells, 0 INFRA, 0 VLM reboots) |
| total wall | ~1 h 20 | **~44 min** (EXEC-START 01:01Z, proof written 01:44Z) |

### Verdict

**RQ-P5.17a: NO [branch 3 -- contracts-equivalent].** DD 56/56 vs RG 55/56,
|diff| = 1, far below the pre-registered separation of 7; both contracts clear
the health floor 45 = ceil(0.8 x 56). **RQ-P5.17b: NO** (far-leg minus near-leg
DD failures = 0; DD is 28/28 in both roles, so there is no asymmetry to
attribute to the occlusion aftermath). **Infra: 0** consumed of the >3 budget
(the one `s103` renderer stall was resolved by the pre-registered single retry
and never needed an `.INFRA` marker).

**What this means (pre-registered branch-3 text, applied as written):** this is
the third consecutive sim contract tie -- now at n = 56 cells with *realized*
staleness (median ZOH IoU 0.08 at the deliver frame, measured, see
`proof/p517_staleness.png`) and *designed* crossings (max GT-GT IoU 0.28-0.44,
which bank v2.1 lacked). Both levers that P5.13's audit blamed for the earlier
tie have now been supplied, and the contracts still do not separate.
Pre-registered conclusion: **sim-select discrimination is CLOSED.** The DD
advantage measured on real video in P5.14 is attributed to real-imagery VLM
fragility that clean Gazebo renders cannot reproduce -- RG's VLM picked the
named car correctly on 56/56 sim cells (`vlm_on=named` everywhere), where on
real UAV123 frames it disagreed with DD on 4/12. Further select levers must be
tested on real video.

**What the bank is still good for:** the v3 generator, its offline screen, and
the 28 pinned seeds are a working, deterministic, GT-exact test-bed -- it just
cannot discriminate *this* question. Reuse it for stack-level questions where
clean renders are an asset (carry robustness through occlusion, mask-quality
gates, tracker swaps), not for VLM-fragility questions.
