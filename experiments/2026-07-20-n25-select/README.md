# P5.18 — n25-select: the Part V select claim at real n (n >= 25 per leg)

**Pre-registered:** 2026-07-20T02:45Z (Madrid wall clock). Design + patches by Fable; Opus runs
the matrix and fills Results only — do NOT re-patch code.
**Status:** COMPLETE (2026-07-20T05:15Z) — **NO [SWAP-bound]**, branch 2. WSEL 22/26 clears the
bar, strengthened SWAP 17/26 misses it. See Results.
**Branch:** `experiment/n25-select`.
**Rig:** RTX 3090 workstation (`.venv-ft`: python 3.12.10, torch 2.6.0+cu124, transformers
4.57.6) + Jetson Orin Nano 8 GB over `ssh jetson` (llama.cpp q8_0, `NV Power Mode: 15W` mode 0 +
`jetson_clocks` — record `nvpmodel -q` output in Results). VLM =
`phase3-terse100eos-1024-q8_0.gguf` + `mmproj-phase3-terse100eos-1024-f16.gguf`, MAX_SIDE 1024.
Carry = SAM2 `facebook/sam2.1-hiera-tiny` bf16. Data = UAV123 @ 1280x720, 30 fps
(`experiments/2026-07-03-real-video-replay/data/UAV123`, `_s` synthetic clips excluded).

## RQ-P5.18

**Does the GT-free warm-start select result (P5.16) hold at statistically conclusive n on real
video?** P5.14 and P5.16 delivered the first Part V select YESes, but each leg gated on **n=5
scenes** — explicitly too small under the standing sample-size rule (n >= 25 per arm). This run
re-powers the *same frozen pipeline* (P5.16 harness, byte-identical) on **26 gating scenes per
leg** spanning 13 clips and 4 UAV123 categories (car, bike, person, wakeboard).

**Pre-registered thresholds (counts of real n, frozen in `verdict_p518.py`):**

- **n = 26** gating scenes per leg (car3:200 control excluded from counts).
- **PASS bar = 20 of 26 per leg** — the same 0.8 claim P5.16 made at n=5 (4/5), now at real n.
  Binomial context (estimates): a true per-scene rate of 0.9 clears 20/26 with p ~0.99; a true
  rate of 0.6 clears it with p ~0.03.
- **YES** iff WSEL >= 20/26 **and** strengthened SWAP >= 20/26.
- **Saturation note** (non-gating caveat) iff both legs >= 25/26 — records that the scene set
  may under-stress the pipeline; it does not change the verdict.
- Single-arm design: no arm-to-arm separation minimum applies (nothing is compared). The
  prompt-time re-ground **shadow** call still runs inside the harness and its
  agreement/disagreement count is reported as a non-gating diagnostic (continuity with P5.14's
  4/12 shadow disagreement).
- **INFRA [n-underflow]** iff valid (scored) cells < 25 in either leg after the retry rule
  below. A missing/INVALID cell counts as FAIL for the bar (conservative; the bar never
  rescales).

**Legs (unchanged from P5.6/P5.14/P5.16):** WSEL = operator phrase names the *idle-tracked
target*; pass = correct selection + genuine lock + coverage >= 0.5 (`leg_pass_p56`). SWAP =
phrase names the *distractor*; strengthened pass = distractor selected, delivered box off the
target GT (IoU < 0.25) **and on** the hand-annotated `distractor_gt_prompt` (IoU >= 0.25), no
failure reason. Weak SWAP (off-target only) is reported non-gating.

## Context and rationale (audit trail)

- **Why this and not bank v4:** P5.17 was the third consecutive sim delivery-contract tie (DD
  56/56 vs RG 55/56) with both arms at ceiling — its pre-registered branch-3 conclusion closed
  sim-select discrimination, and the loop-focus STATUS note marks the steer's sim question
  ANSWERED (NO). The steer's own deferred item — select on real UAV123 — is the live
  continuation. A fourth sim A/B is explicitly out of scope.
- **Why re-power instead of a new lever:** P5.14/P5.16's YESes are the load-bearing Part V
  results and they rest on 5 gating scenes per leg. The human's standing rule calls that an
  anecdote. Nothing about the pipeline is changed here — the single factor is the scene set
  (5 -> 26 gating scenes). If the YES survives, Part V's select claim becomes thesis-grade; if
  it collapses, the n=5 result was noise and the failure buckets say where.
- **Why the GT-free (P5.16) variant and not GT-seeded (P5.14):** P5.16 showed removing the seed
  oracle costs ~1 cell in 12; the GT-free pipeline is the deployable one, so it is the one
  worth powering. (Rejected: re-powering P5.14 — it answers a weaker question for the same
  GPU time.)
- **Scene supply was the historical blocker** (P5.5 audit: "data-starved"; the sim detour was
  motivated by it). The unlock here is hand curation at design time: I walked 20+ UAV123 clips
  as stride-100 montages, rendered 2-up ds/prompt frames for every candidate window, and
  hand-annotated the distractor at the prompt frame on 10-px-grid zooms
  (`curate_p518.py montage|scene|zoom`, all renders under `curation/`, all opened with the Read
  tool during curation — the per-scene observations are recorded in `scenes_p518.json` notes).
  Two annotation errors were caught *by looking* (wakeboard8:450 first zoom missed the boat by
  ~180 px; wakeboard8:750 wake spray initially mistaken for hull) — recorded in the scene notes.
- **Drops (curation negatives, recorded):** car9:1350 dropped — two black sedans near the
  target at prompt and an intermediate zoom could not settle which was the ds-trailing car; a
  hand GT box I cannot confidently assign makes the SWAP gate meaningless (annotation-quality
  bar, not difficulty). Also dropped for viability: car3:650, car3:850, car7:150, car7:250,
  person13:300, wakeboard6:600. Whole-clip rejects: car17, car14, car2/car4 (4 frames on
  disk), person18, person6, person1, boat2, boat3, all `_s` clips.
- **Composition caveats (pre-registered):** bike1 contributes 6 scenes of one recurring
  blue-vs-yellow rider pair; the wakeboard family contributes 7 scenes of one recurring
  boarder-vs-boat pair; 8+ scenes carry late-entry discovery risk (distractor absent at ds).
  These correlate failures within families — the failure-bucket table in Results must report
  per-family counts so a family-wide collapse is visible as such.

## Scene set (frozen)

`scenes_p518.json` — 27 scenes, 26 gating + 1 non-gating control:

- 6 legacy P5.16 scenes **verbatim** (car10:240, car10:615, car9:300, car7:460 [pre-registered
  predicted SWAP FAIL, carried from P5.6], car9:560 [t_p 6.0 as-run], car3:200 [non-gating
  control, predicted WSEL PASS under direct delivery]).
- 21 new scenes, all t_p 8.0 (prompt = f0+240, ds = f0-150): car9:950, car9:1150, car3:1050,
  car10:850, car18:150, bike1:{450,750,1050,1950,2250,2450}, person20:1050, person10:450,
  person15:150, wakeboard6:{150,350}, wakeboard8:{150,450,750}, wakeboard2:150, wakeboard3:150.
  Per-scene captions, hand boxes and curation notes live in the JSON.

**Mechanical verification (already run at design time):** `curate_p518.py verify` asserts per
scene: pre-roll exists, coverage fits the clip, target GT present at ds and prompt, <= 60 NaN
GT frames in cover, captions differ, distractor box in-bounds, distractor-target GT IoU < 0.25,
same-clip scenes >= 200 frames apart. Output `verify OK: 27 scenes (26 gating), 13 clips` and
the two annotated grids `curation/verify_grid_{0,1}.png` — **both opened with the Read tool at
design time**: every magenta hand box sits on the named distractor object, every in-crop red
target GT on the target. person20:1050's overlap caveat (woman-adjacent backpack man; wrong-
neighbour IoU 0.234 < 0.25) is handled by a mandatory per-cell visual audit (below).

## Code changes (already committed — Opus: do NOT edit these files)

**The harness is byte-identical P5.16 code** (`experiments/2026-07-19-autodisc-select/
discover_p516.py` and its P5.14/P5.6/P5.5/P5.3 imports) — zero patches. `--matrix` accepts any
scenes file and an absolute `--out` overrides the output root, so no runner shim exists. Frozen
constants (recorded into every results.json): DS_OFFSET 150, IOU_SAME 0.5, CARRY_HZ 6.15,
CAND_HZ 3.075, MATCH_FLOOR 0.1, DIST_FLOOR 0.25, APP_TAU 12.0, LOSS_S 1.0, ROI_MARGIN 2.0,
ROI_MIN_SIDE 256, ROI_RES 512, REANCHOR_OFFSETS [90,165], cover_s 10.0.

New files on this branch (all Fable, design time):

- `scenes_p518.json` — the frozen 27-scene ledger (the experiment's single factor).
- `curate_p518.py` — curation/annotation tool + `verify` gate (design-time; Opus does not run
  `montage/scene/zoom`, may re-run `verify`).
- `verdict_p518.py` — **sole verdict authority** (selfcheck green at design time).
- `make_proof.py` — proof figures from `runs/*/results.json`.
- `curation/verify_grid_{0,1}.png` + `curation/zoom_*.png` — committed curation evidence (the
  verification grids I read and the 10-px-grid zooms the hand boxes were annotated on). The
  stride-100 montages and per-scene 2-ups (~91 MB) are NOT committed — regenerable via
  `curate_p518.py montage|scene` from the UAV123 data.

## Run matrix (Opus)

All commands from `/home/gara/jetson`. R0 first; the matrix is one command.

```bash
# R0 — preflight (no GPU claims yet)
.venv-ft/bin/python experiments/2026-07-19-autodisc-select/discover_p516.py --selfcheck
.venv-ft/bin/python experiments/2026-07-20-n25-select/verdict_p518.py --selfcheck
.venv-ft/bin/python experiments/2026-07-20-n25-select/curate_p518.py verify
ssh jetson "sudo nvpmodel -q; sudo jetson_clocks"   # record power mode into Results

# R1 — the matrix: 27 scenes x {WSEL, SWAP} = 54 cells, resumable
.venv-ft/bin/python experiments/2026-07-19-autodisc-select/discover_p516.py \
  --matrix /home/gara/jetson/experiments/2026-07-20-n25-select/scenes_p518.json \
  --out /home/gara/jetson/experiments/2026-07-20-n25-select/runs
```

Snapshots land in `experiments/2026-07-20-n25-select/runs/DSC_<LEG>_<clip>_<f0>/`
(`results.json`, `deliver.png`, `discovery_<cand>.png`, `overlay.mp4`). The harness skips any
cell whose `results.json` exists — re-running the command resumes.

**Abort / INVALID rules (mechanical):**

- A cell exceeding 20 min wall: kill the process, delete that cell's partial dir, re-run with
  `--only <clip>:<f0> --legs <LEG>` once. A second 20-min hang on the same cell: leave the dir
  absent (the cell becomes INVALID) and continue the matrix.
- Three *consecutive* cells hanging or SSH-failing = Jetson down: stop, power-cycle-free
  recovery only (`ssh jetson` checks, re-run); if unreachable, the run is INFRA — record and
  stop.
- Never rerun a scored cell (`results.json` present): n=1 deterministic replay, the first
  scored result stands. Runs are independent per cell; partial matrices resume cleanly.
- A `_frame_health` assert (>99% one-colour frame) inside a cell: that cell is INVALID as-is;
  retry once per the hang rule (the source frames are real UAV123 jpgs, so this firing at all
  is suspect — record it).

## Visual verification (mandatory, downgrade-only)

`verdict_p518.py` **refuses to run** until `visual_downgrades.json` exists and its `audited`
list covers the mechanically-required set. Procedure:

1. After the matrix, write `experiments/2026-07-20-n25-select/visual_downgrades.json` as
   `{"audited": [], "downgrades": []}` and run the verdict script once. Its assert message
   prints the exact required cell ids (every failing gating cell, capped at the 12 lowest-metric;
   5 rank-sampled passing cells; person20:1050 both legs).
2. Open each required cell's `runs/<id>/deliver.png` with the Read tool. For cells whose
   failure bucket is `discovery`, also open `runs/<id>/discovery_<cand>.png` (it exists only
   for accepted discoveries; a missing PNG for a candidate is itself the evidence that the
   discovery never happened).
3. What the PNGs show (header text is burned into each): **deliver.png** = the prompt frame
   with green = delivered box, red = target GT, blue = `distractor_gt_prompt` hand box.
   *WSEL PASS looks like:* green on/overlapping red on the named target. *SWAP PASS looks
   like:* green on/overlapping blue, clearly off red. *Failure looks like:* green on the wrong
   object, green on background, or no green box at all (nothing delivered).
   **discovery_<cand>.png** = the frame the VLM saw at its accepted call, green = VLM box
   (red = target GT when the candidate is the target). *Correct looks like:* green on the
   captioned object. *The P5.16 headline failure mode looks like:* green on a *different*
   same-class object (wrong-object discovery, surfaces later as a lost track or a wrong
   delivery — classify by what you see, seed-correctness first).
   **person20:1050 (both legs):** confirm the delivered green box is on the *backpack man*,
   not the adjacent woman — the hand box was tightened so a woman-delivery mechanically fails,
   but the visual check is the backstop; a green box centred on the woman that still passes
   numerically MUST be downgraded.
4. Record every audited cell id in `audited`. A cell whose PNG contradicts its numeric pass
   goes in `downgrades` with a one-line `seen`. **The visual gate only downgrades — never
   upgrades.** Then run the verdict for real:

```bash
.venv-ft/bin/python experiments/2026-07-20-n25-select/verdict_p518.py
.venv-ft/bin/python experiments/2026-07-20-n25-select/make_proof.py
```

Open the two proof figures and `proof/deliver_headline.png` with the Read tool before writing
Results (the headline is mechanically the *worst passing* SWAP cell — say what you see in it).

## Verdict rules

`verdict_p518.py` is the sole authority; its branches are exhaustive and frozen (see its
docstring): **INFRA [n-underflow]** / **1 YES** (with saturation note) / **2 NO [SWAP-bound]**
/ **3 NO [WSEL-bound]** / **4 NO [select-broken]**. It also emits per-failing-cell buckets
(precedence: `discovery` > `carry-loss` > `wrong-selection` > `carry-quality` /
`on-target-not-distractor` / `off-distractor`), the weak-SWAP count, the control-cell outcome
and the shadow-agreement diagnostic — all non-gating. Copy its printed verdict line verbatim
into Results, QUESTIONS and the merge commit.

## Estimates (marked as estimates)

- **Runtime:** ~30 s/cell (P5.16 actual: mean 29 s, max 30 s) x 54 cells ≈ **27–35 min**
  matrix; whole run incl. R0, visual audit and proof < 1.5 h. Hard cap 10 h is not in play;
  if the matrix somehow exceeds 5 h, something is broken — apply the hang rule, do not wait
  it out.
- **Predicted branch: 1 (YES), sub-saturation.** Point estimates: WSEL 22–24 of 26, SWAP
  20–22 of 26. Predicted failure families: car7:460 SWAP (carried P5.6 prediction,
  carry-off-object), 1–3 late-entry `discovery` failures (car18:150, bike1:450/750,
  person10:450, person15:150 are the at-risk set), 0–2 wakeboard cells (water glare imagery,
  smallest distractor wakeboard3:150). The plausible alternative is **branch 2
  [SWAP-bound]** if late-entry discovery fails broadly on the distractor side — SWAP carries
  all the discovery risk (the target is always present at ds; the distractor often is not).
- **Wrong-estimate contingency is content:** if bike1 or wakeboard fails as a *family* (>= 4
  of its scenes on one leg), say so explicitly in Results — the composition caveat above
  pre-registers that reading.

## Results

> **Statistical correction, 2026-07-21 (R-4).** `n_effective` 26 -> **13**: the 26 gating
> cells are cut from 13 distinct UAV123 clips (`scenes_p518.json`: `bike1` 6, `car9` 4,
> `car10` 3, `wakeboard8` 3, `wakeboard6` 2, 8 singletons). The verdict above is unchanged
> — deflation only widens intervals, so it cannot rescue a miss — but WSEL becomes 11/13
> and, against a 0.8 bar with 13 independent units, **no result could have reached
> alpha = 0.05** (0.8^13 = 0.055 even at 13/13). "Clears" is descriptive here, never
> inferential. Method: `thesis/01-metodo-estadistico.md`; registry: `thesis/claims.json`.

**Run:** 2026-07-20T05:15Z, branch `experiment/n25-select`, pre-reg commit `246f11a`.
**Status:** COMPLETE. Matrix 54/54 cells scored, zero INVALID, zero retries fired.

**Verdict (verbatim from `verdict_p518.py`, the sole authority):**

```
P5.18 VERDICT branch 2: NO [SWAP-bound]: WSEL 22/26 passes, SWAP 17/26 < 20
```

**Versions / config:** python 3.12.10, torch 2.6.0+cu124, transformers 4.57.6 (`.venv-ft`,
RTX 3090). VLM `phase3-terse100eos-1024-q8_0.gguf` + `mmproj-phase3-terse100eos-1024-f16.gguf`,
MAX_SIDE 1024, served from the Jetson Orin Nano 8 GB over `ssh jetson` — `nvpmodel -q` reports
`NV Power Mode: 15W` (mode 0) + `jetson_clocks`, matching the header. Carry = SAM2
`facebook/sam2.1-hiera-tiny` bf16. Data = UAV123 @ 1280x720 30 fps. Frozen constants recorded in
every `results.json` and confirmed unchanged from the header (DS_OFFSET 150, IOU_SAME 0.5,
CARRY_HZ 6.15, CAND_HZ 3.075, MATCH_FLOOR 0.1, DIST_FLOOR 0.25, APP_TAU 12.0, LOSS_S 1.0,
ROI_MARGIN 2.0, ROI_MIN_SIDE 256, ROI_RES 512, REANCHOR_OFFSETS [90,165], cover_s 10.0).
Harness byte-identical P5.16 (`discover_p516.py`), zero patches — the single factor is the
scene set.

### Failing cells (all 13) + the audited passing sample

`what I saw` is what the pixels showed when I opened the PNG with the Read tool — all 19
required audit cells were opened; full per-cell notes in `visual_downgrades.json`.

| cell | pass | weak | d_iou | d_dist | cov | fail bucket | what I saw (PNG) |
|---|---|---|---|---|---|---|---|
| WSEL car7:460 | FAIL | — | none | — | 0.00 | carry-loss | **No green box at all.** Nothing delivered; target track lost during idle. |
| SWAP car7:460 | FAIL | weak | 0.00 | 0.00 | 0.00 | off-distractor | Green stranded on the far-**left kerb/planter** at the frame edge, off both cars. The carried P5.6 prediction, bit exactly. |
| WSEL car9:950 | FAIL | — | none | — | 0.00 | carry-loss | **No green box at all.** Target track lost. |
| SWAP car9:950 | FAIL | — | 0.32 | 0.00 | 0.84 | on-target-not-distractor | Discovery was **correct** (green on the black car beside the silver); by delivery green had drifted forward onto the **silver target** while the real black car trails under the blue box. Identity drift. |
| WSEL car9:1150 | FAIL | — | 0.00 | — | 0.00 | carry-quality | Green is a tiny box near the intersection at the **top** of frame, nowhere near the target. |
| SWAP car9:1150 | FAIL | weak | 0.00 | 0.00 | 0.00 | off-distractor | Green on a **third vehicle** up the road, off both target and distractor. |
| WSEL car3:1050 | FAIL | — | 0.00 | — | 0.00 | carry-quality | Green far up the **empty road**, well ahead of the target. |
| SWAP car3:1050 | FAIL | weak | 0.05 | 0.00 | 0.17 | off-distractor | Green slid off the car onto **roadside vegetation** beside the target GT. |
| SWAP car18:150 | FAIL | — | 0.58 | 0.00 | 1.00 | on-target-not-distractor | **Late-entry wrong-object discovery.** Asked for "the black SUV" at f=134, the VLM boxed the **red Mustang** (the target) — the SUV is not in frame yet. Distractor track seeded on the target at birth. |
| SWAP bike1:450 | FAIL | — | 0.59 | 0.00 | 0.92 | on-target-not-distractor | Same **late-entry** failure: asked for "the cyclist in the yellow shirt" at f=435, green boxed the **blue-shirt rider** (target); yellow rider not yet in frame. |
| SWAP bike1:2250 | FAIL | — | none | — | 0.00 | discovery | **`discovery_distractor.png` absent** (outcome `in_flight`) — the VLM call had not returned by the prompt frame. No green box delivered. |
| SWAP person10:450 | FAIL | — | none | — | 0.00 | carry-loss | **No green box at all.** Discovery accepted, carry lost before delivery. |
| SWAP wakeboard3:150 | FAIL | weak | 0.00 | 0.00 | 0.00 | off-distractor | Smallest distractor in the set; delivery off it (predicted at-risk cell). |
| WSEL person20:1050 | pass | — | 0.90 | — | 1.00 | — | Green tight on the **hatted man in the suit**, red GT coincident. Mandated backstop — clean. |
| SWAP person20:1050 | pass | weak | 0.00 | 0.64 | 0.01 | — | Green covers the **backpack man** (blue box) and is clearly off the target. **Caveat:** the box is loose enough to absorb the adjacent woman — but it is *not centred* on her and the man is fully enclosed, so the pre-registered downgrade condition is not met. Recorded as the marginal cell it is. |
| SWAP car10:850 | pass | weak | 0.00 | 0.97 | 0.00 | — | Green tight on the **white van** (distractor), target silver car further down the road. Textbook. |
| SWAP bike1:750 | pass | weak | 0.00 | 0.61 | 0.00 | — | Green tight on the **yellow-shirt rider**. Same pair that fails at f0=450 — here both riders are already in frame at discovery. |
| SWAP wakeboard6:150 | pass | weak | 0.00 | 0.75 | 0.00 | — | Green on the **speedboat** (distractor), tiny wakeboarder target out on the wake. |
| WSEL wakeboard8:750 | pass | — | 0.85 | — | 0.68 | — | Green tight on the **wakeboarder**; water glare did not break it. |
| WSEL bike1:2250 | pass | — | 0.41 | — | 1.00 | — | Green on the **blue-shirt rider**, hugging the body not the bicycle — which is why IoU is only 0.41 against a GT that includes the bike. Correct object. |
| **41 unaudited passing cells** | pass | — | — | — | — | — | Not individually opened (outside the mechanically-required audit set); their numeric passes stand. |

**Counts:** WSEL **22/26**, strengthened SWAP **17/26** (bar 20/26), weak SWAP 21/26, control
car3:200 **passes on both legs**, shadow agreement 38/48 (the shadow re-ground selected *nothing*
in 9/48). Valid cells 26/26 per leg — no n-underflow. **Visual audit: 19/19 cells opened, ZERO
downgrades** — every numeric pass I opened sits on the correct object and every numeric fail is
visibly wrong.

**Failure buckets** (13 failing cells): `off-distractor` 4 (SWAP car7:460, car9:1150, car3:1050,
wakeboard3:150) · `on-target-not-distractor` 3 (SWAP car9:950, car18:150, bike1:450) ·
`carry-loss` 3 (WSEL car7:460, WSEL car9:950, SWAP person10:450) · `carry-quality` 2 (WSEL
car9:1150, car3:1050) · `discovery` 1 (SWAP bike1:2250).

**Per-family breakdown — the headline structural finding.** The pre-registration asked for this
table so a family-wide collapse would be visible as such. One happened, but **not in the families
that were flagged**:

| family | gating scenes | WSEL | SWAP |
|---|---|---|---|
| car | 10 | **6/10** | **5/10** |
| bike1 | 6 | 6/6 | 4/6 |
| person | 3 | 3/3 | 2/3 |
| wakeboard | 7 | 7/7 | 6/7 |
| **total** | **26** | **22/26** | **17/26** |

**All four WSEL failures are cars**, and non-car WSEL is a clean **16/16**. The pre-registered
worry was a bike1 or wakeboard family collapse (>= 4 of one family on one leg); neither happened
(bike1 6/6, wakeboard 7/7 on WSEL). The car family carried the failure instead, concentrated in
three clips (car7, car9 x2, car3) — small, low-contrast sedans on palm-lined roads with heavy
shadow banding, where SAM2 has the least appearance signal to hold identity on.

**Two mechanisms, cleanly separated by the visual audit:**

1. **SWAP failures strictly contain WSEL failures.** All 4 WSEL failures also fail SWAP, plus 5
   SWAP-only failures. The SWAP-only set is where the leg is lost, and **3 of those 5 are
   distractor-side discovery problems** (car18:150 and bike1:450 = late-entry wrong-object
   discovery; bike1:2250 = discovery still in flight at the prompt). This is exactly the
   asymmetry the pre-registration named: the target is always present at the discovery frame,
   the distractor often is not. When the distractor has not yet entered frame, the VLM has no
   abstain path and grounds the nearest same-class object — the target — so the "distractor"
   track is seeded on the target at birth and delivery can never be correct.
2. **Delivery quality is bimodal — there are no near-misses.** Passing cells cluster at IoU
   0.40–0.97; every failing cell is at 0.00 or delivered nothing at all (see `deliver_iou.png`).
   No cell sits near the 0.25 floor. **Threshold tuning therefore cannot recover this leg** —
   the failures are catastrophic (track lost, or locked on the wrong object), not marginal.

**Non-gating diagnostics.** Discovery: 102/104 candidate calls accepted (2 `in_flight` at the
prompt), mean accepted latency 4.77 s (min 4.38, max 8.56). Delivery `acquire_s` = **0.00 s on
every cell** vs the shadow prompt-time re-ground at mean **4.68 s** — the direct-delivery
contract's latency advantage from P5.14 reproduces at n=26 and is not what failed here.

**Estimate-vs-actual.**

| | predicted | actual |
|---|---|---|
| branch | **1 (YES)**, sub-saturation | **2 — NO [SWAP-bound]** |
| WSEL | 22–24 / 26 | **22/26** — inside the predicted band |
| SWAP | 20–22 / 26 | **17/26** — 3 below the band, and below the bar |
| matrix runtime | 27–35 min | **~26 min** (52 gating cells, mean 29.3 s/cell, max 35.7 s) |

The WSEL prediction was exactly right; **the SWAP prediction was wrong, and that is the result.**
The pre-registration named branch 2 as "the plausible alternative … if late-entry discovery fails
broadly on the distractor side" — that is precisely what fired. Named at-risk cells that bit:
car7:460 SWAP (the carried P5.6 carry-off-object prediction, dead on), car18:150 and bike1:450
(the late-entry set), wakeboard3:150 (smallest distractor, within the predicted 0–2 wakeboard
failures). Named at-risk cells that did *not* bite: bike1:750, person15:150. Unpredicted: the
car-family concentration, which is the single biggest lesson in the run.

**What this does and does not overturn.** It does **not** overturn warm-start delivery: WSEL
22/26 (0.85) clears the bar and the P5.14 latency advantage reproduces. It **does** overturn the
n=5 SWAP claim — P5.16 reported SWAP 4/5 (0.80) and the true rate at n=26 is 0.65, comfortably
inside what 4/5 could not distinguish. **The n=5 anecdote was optimistic; the sample-size rule
earned its keep on its first application.**

**Proof deliverables** (all three opened with the Read tool before this section was written):

- `proof/pass_matrix.png` — per-scene PASS/FAIL grid, both legs, n=26 gating + control.
  Shows the verdict's shape at a glance: the car block red on both legs, bike1/person/wakeboard
  green on WSEL, and the SWAP-only failures (orange = weak-only) scattered across families.
  Config: GT-free P5.16 harness, UAV123, Jetson 15W + jetson_clocks.
- `proof/deliver_iou.png` — delivery IoU per gating cell, WSEL vs target GT and SWAP vs the hand
  distractor GT, with MATCH_FLOOR 0.10 and DIST_FLOOR 0.25 drawn. **This is the bimodality
  figure**: green passes sit 0.40–0.97, red failures all at 0.00 / no-delivery, nothing near the
  floors.
- `proof/deliver_headline.png` — mechanically the *worst passing* SWAP cell (car9:560,
  iou_d 0.478). What I saw: the green delivered box sits on the small distant white car with the
  blue distractor hand box beneath it, and is clearly off the red target GT (the silver car under
  the road-sign gantry). A genuine but low-margin pass — this is what the bottom of the passing
  distribution actually looks like.

## Definition of done (Opus, after the verdict)

1. Fill Results above (incl. what-I-saw column for every audited cell — write what the pixels
   showed, not what the numbers imply).
2. Append RESULTS row(s) to `docs/results/part5-anticipatory-grounding.md`, QUESTIONS entry
   (RQ-P5.18 + one-line verdict) to `docs/questions/part5-anticipatory-grounding.md`, DECISIONS
   entry to `docs/decisions/part5-anticipatory-grounding.md` (the n=25 re-power decision + what
   was given up), all under Part V.
3. Commit `runs/*/results.json`, `runs/verdict.json`, `visual_downgrades.json`, the three
   `proof/` PNGs, and the audited cells' `deliver.png`/`discovery_*.png` (the visual-claim
   evidence). Do NOT commit `overlay.mp4` (size) unless one clip is the proof of a headline
   failure — then commit exactly that one.
4. Leave the branch ready to merge (working tree clean apart from pre-existing stray
   `2026-07-20-bankv3-select/runs/` leftovers on main — do not add them).

### Shadow re-ground (RG), analysed under R-5 (2026-07-21)

The shadow arm was recorded here and never analysed. It is now analysed by
`thesis/analyse_shadow_rg.py`, and the analysis is **one-directional on purpose**.

- **RG selection-correct: 38/48** of the gating cells that have a shadow record,
  9 of the failures by abstention (`selected: null`, no candidate matched
  above the floor). This is a **ceiling**, not a pass rate: the shadow never carries
  a track after its re-ground, so it is never charged coverage or delivered IoU.
- **It is not paired against DD, and the obvious pairing is vacuous.** DD's
  selection is string equality against the stored caption
  (`select_p56.bind_by_caption`, with an assert that exactly one matches), so DD
  scores 48/48 by construction and cannot mis-select. Pairing DD `pass` against RG
  `selected` instead — one criterion folding in coverage, IoU and carry survival,
  the other selection only — is the shape R-21 catalogues as MISLEADING, and the
  paired p it produces is not reported.
- **The dropped cells are not missing at random.** `meta.shadow` is written after
  the early `fail()` returns, so every cell without one is a DD failure. Dropping
  them conditions the number on DD surviving to the prompt.
- **RG is not an independent contract.** It matches its VLM box against
  `cand_at_prompt` — DD's own maintained tracks — so a drifted carry costs RG a
  match. Its failures are re-ground failures plus inherited carry drift.
