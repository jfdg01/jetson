# P5.5 — Maintained-candidate select-on-command (idle-window distractor re-anchor + unique captions)

**Pre-registered:** 2026-07-14T06:16Z (Madrid wall-clock).
**Status:** PRE-REGISTERED — design + code + smoke test done, graded matrix NOT run.
**Branch:** `experiment/select-generalization`.
**Division of labour:** design + patches by Fable; **Opus runs the matrix and fills
the Results section only — do NOT re-patch code.** All code files listed under
"Committed artifacts" are already committed — Opus: do NOT edit these files. If a
run crashes on an infra error (SSH drop, OOM), delete that run's dir and re-run
that cell once; if it crashes twice, record it as `infra` in Results and move on.

## Research question

**RQ-P5.5a:** Does idle-window candidate maintenance (per-candidate ROI re-anchor
of the distractor carry, deployed Part III lever) plus referentially-unique
captions lift warm select-on-command (WSEL) to **>= 4/5 PASS** on the 5 gating
multi-candidate scenes (P5.3 baseline: 3/5)?

**RQ-P5.5b:** Same treatment on the negative-control leg (SWAP): **>= 4/5 PASS**
(P5.3 baseline: 2/5)?

**Overall verdict: YES iff both.** Anything else is NO (partial results are still
content — the failure classification below says *which* family survived).

## Context: the audit that motivates this (read before touching anything)

P5.3 (`experiments/2026-07-14-multi-candidate-select/`) concluded NO
[match-bound]; P5.4 (`experiments/2026-07-14-crop-select/`) attacked the acquire
with an ROI'd *select-time* crop and concluded NO again, verdict cell-for-cell
identical. The P5.5 audit (this cycle) re-opened every non-passing P5.3 cell's
`results.json` + frames and **re-diagnosed the failure families**:

| P5.3 cell | recorded blame | audit re-diagnosis |
|---|---|---|
| SWAP car7:460 | match-bound | **distractor-carry DRIFT** — carry slid to the frame edge `[0,407,41,424]`; the VLM boxed the black car *correctly* (`[678,598,781,648]`, visually verified) |
| SWAP car10:615 | match-bound | **distractor-carry DRIFT** — van carry shrank 137x245 -> 37x94 (displacement only 0.147, so P5.4's `carry_disp>0.35` diagnostic missed it); VLM boxed the van *correctly* |
| WSEL car10:615 | match-bound | **genuine phrase ambiguity** — "the white car" grounded the silver sedan ahead |
| SWAP car10:240 | match-bound | **tiny-box match near-miss** — VLM box 1.6 px outside the carried black car's box (IoU 0.0 vs MATCH_FLOOR 0.10) |
| WSEL car3:200 | resolution | resolution (confirmed; 16x40 px target) |

So "match-bound" was substantially a **maintenance problem** (2/5 failing cells)
plus a **captioning problem** (2 cells), not a grounding-model problem. The VLM
grounded the phrase correctly in 3 of the 5 failing cells. This directly serves
loop-focus direction 2 (idle-window candidate maintenance) fused with direction 1
(the multi-candidate select stage stays the graded task).

**Scene-survey negative result (thesis content):** an exhaustive contact-sheet
sweep of every downloaded UAV123 clip (car1_s..car4_s, car14, car17, car18, plus
re-sweeps of car3/7/9/10; sheets committed under `curation/`) found **exactly one**
additional clean co-visible same-class pair — car9:560 (silver + maroon sedans).
car14/car17/car18/car1_s/car4_s are single-vehicle or crowd-scene clips; car3_s's
pairs never co-persist through an 8 s idle + acquire window; car2/car4 have only
4 frames on disk. Scene-set *expansion* is data-starved; the set below is 5
inherited P5.3 scenes + car9:560.

### Rejected alternatives (recorded, with reasons)

- **Pure maintenance-only t_p sweep (loop-focus direction 2 alone):** cannot flip
  the WSEL caption-ambiguity cell, so it caps at 4/5 WSEL even if perfect; fusing
  captions + maintenance tests both real failure families in one matrix. Loser
  because it answers less per GPU-hour.
- **Scene-set expansion as the main axis:** falsified by the survey above.
- **Caption-only arm as gating:** cannot fix the two drift cells (the VLM already
  grounded those correctly). Kept as the non-gating M arm for attribution.
- **Dead levers not re-proposed:** union-crop select + CLIP crop-scoring (P5.4),
  sub-2s cold-acquire automations (E19–E23), speed-adaptive acquire, Swin2SR, VLM
  swap, EdgeTAM, text-only scene index, identity-blind REGROUND cues.

## Design

One mechanism change on top of the frozen P5.3 rig (`select_p53.py`, imported not
copied), select step at the prompt **unchanged** (full-frame VLM -> IoU match vs
carried boxes at the prompt, MATCH_FLOOR 0.10 -> realtime bridge -> deliver the
matched track's current box -> 10 s realtime coverage):

- **Lever 1 — idle-window distractor maintenance.** At f0+90 and f0+165 (both
  before every scene's prompt), crop the deployed ROI window
  (`grounding/roi.py`, margin 2.0, min_side 256, long edge 512 LANCZOS) around
  the distractor carry's current box, fire the VLM with the distractor caption on
  the crop, map the box back, and **reseed** the SAM2 carry there. Accept rule =
  parseable + in-frame valid, deliberately **no IoU floor vs the prior** (a
  drifted carry must not veto its own fix). The target carry is never re-anchored
  (GT-oracle-seeded target carries never drifted in P5.1/P5.3/P5.4 —
  single-factor discipline). This is NOT P5.4's dead union-crop-select: the ROI
  here maintains a carry during idle; the select-time acquire stays full-frame.
- **Lever 2 — referentially-unique captions (MC arm)** only on the two cells the
  audit tagged caption-bound: car10:240 SWAP distractor -> "the black car in
  front of the white car"; car10:615 WSEL target -> "the white car in front of
  the white van". Every caption that passed in P5.3 is kept verbatim.

**Arms.** `MC` = maintenance + new captions, all 6 scenes x {WSEL, SWAP} = 12 runs
(gating). `M` = maintenance + OLD P5.3 captions, only the 2 caption-changed
scenes x 2 legs = 4 runs (attribution: separates what maintenance fixed from what
the caption fixed; non-gating). 16 runs total.

**Scenes** (`scenes_p55.json`, committed; validated by `curate_p55.py check`):
5 scenes inherited verbatim from P5.3 (same f0, t_p=8.0, distractor boxes) + new
car9:560 (t_p=6.0 — at t_p=8 the prompt frame has the target under a road-sign
gantry; distractor box `[578,522,624,598]` verified on the 40 px-grid zoom render,
`curation/frame_car9_560_z.jpg`). car3:200 is the **non-gating** resolution-bound
control (P5.4 showed it is out of scope for these levers; kept to record whether
they move a resolution-bound cell at all — expected: no).

**Deployment-budget note (recorded, not graded):** the idle window is
non-realtime in this rig (P5.1/P5.3 convention). In deployment the two ROI calls
(~2.1 s each, P5.4 measurement) fit an 8 s idle window; in car9:560's 6 s window
two rounds + carry cadence is marginal — if Part V graduates to a live idle loop,
round count must become idle-length-aware. Out of scope here.

**Known biases / limits (recorded):** target seed is still the GT oracle box at
f0 (P5.1 scope cut, unchanged); distractor has no GT, so SWAP correctness rests
on the match rule + target-GT exclusion, as in P5.3; n=1 per cell
(deterministic replay); captions were written by the designer with knowledge of
the failure frames (fitted-to-scene risk is the price of the caption lever — the
M arm bounds how much of the verdict it buys).

## Committed artifacts (Opus: do NOT edit these)

| File | Role |
|---|---|
| `scenes_p55.json` | frozen 6-scene set, MC captions + `old_*` M captions, gating flags |
| `select_p55.py` | the rig: P5.3 flow + segmented idle + distractor ROI re-anchor; arms; `--selfcheck` (also re-runs the upstream P5.3 suite) |
| `verdict_p55.py` | mechanical verdict + failure classification from `runs/*/results.json` |
| `make_proof.py` | proof figures from `runs/` (pass grid vs P5.3, re-anchor trajectories) |
| `curate_p55.py` | design-time curation tool (contact sheets / grid frames / scene check) |
| `curation/*.jpg` | curation provenance: contact sheets + grid/zoom renders behind every hand-set box |
| `runs/MC_WSEL_car3_200/` | disclosed smoke run (see below) — a real matrix cell, kept |

## Run matrix (Opus starts here)

Config: SAM2 carry local (RTX 3090, sam2 1.1.0, torch 2.6.0+cu124, rate-capped
to the on-Orin 6.15 Hz budget, CAND_HZ 3.075 per candidate); VLM = Qwen2-VL-2B
q8_0 terse on the Jetson over SSH (`llama-mtmd-cli` build 57fe1f0, max_side 1024
full-frame / 512 pre-resized ROI crops), **15W + `sudo jetson_clocks`** (both
NOPASSWD — run the clocks line before the matrix; power mode is already 15W, the
only mode on this board). transformers 4.57.6, opencv 4.13.0, venv `.venv-ft`.
Frames: UAV123 under `experiments/2026-07-03-real-video-replay/data/UAV123`.

```bash
cd /home/gara/jetson
ssh jetson 'sudo jetson_clocks'
mkdir -p experiments/2026-07-14-select-generalization/raw

# sanity (no GPU/Jetson): must print "select_p55 selfcheck OK"
.venv-ft/bin/python experiments/2026-07-14-select-generalization/select_p55.py --selfcheck

# gating arm: 12 runs (idempotent: re-running skips cells with results.json)
.venv-ft/bin/python experiments/2026-07-14-select-generalization/select_p55.py \
    --matrix experiments/2026-07-14-select-generalization/scenes_p55.json \
    --arm MC --out runs 2>&1 | tee experiments/2026-07-14-select-generalization/raw/matrix_MC_$(date +%Y%m%d_%H%M).log

# attribution arm: 4 runs (auto-restricted to the old_*-bearing scenes)
.venv-ft/bin/python experiments/2026-07-14-select-generalization/select_p55.py \
    --matrix experiments/2026-07-14-select-generalization/scenes_p55.json \
    --arm M --out runs 2>&1 | tee experiments/2026-07-14-select-generalization/raw/matrix_M_$(date +%Y%m%d_%H%M).log

# verdict (mechanical; paste its output into Results)
.venv-ft/bin/python experiments/2026-07-14-select-generalization/verdict_p55.py

# proof figures + copy 2 headline overlays into proof/
.venv-ft/bin/python experiments/2026-07-14-select-generalization/make_proof.py
```

Each run snapshots to `runs/<ARM>_<LEG>_<clip>_<f0>/results.json` and records
`overlay.mp4` (green = held/delivered box, red = target GT, blue = distractor
seed at f0) — the MP4s are gitignored in `runs/`; copy the curated ones into
`proof/` (tracked).

**Abort criteria (mechanical):** any single run hanging **> 15 min** wall (normal
is 25–60 s + one-time model boot) -> kill it, delete that run dir, mark the cell
INVALID/`infra` in Results, continue with the rest. Jetson unreachable -> stop,
record where, leave the branch as-is. Never delete a *completed* run dir.

## Verdict rules (mechanical — computable from `runs/*/results.json`)

`verdict_p55.py` implements exactly this; its printed output is the verdict.

- Per-run PASS = `pass` field (WSEL: correct selection + genuine lock IoU>=0.25
  at deliver + coverage>=0.5; SWAP: distractor selected + deliver IoU vs target
  GT < 0.25 + no failure reason — `leg_pass`, unchanged from P5.3).
- Gating scenes = car10:240, car10:615, car9:300, car7:460, car9:560
  (car3:200 excluded — resolution control).
- **RQ-P5.5a: MC WSEL PASS >= 4/5 gating -> YES.**
- **RQ-P5.5b: MC SWAP PASS >= 4/5 gating -> YES.**
- **Overall YES iff both.** Missing gating cells -> INCOMPLETE, verdict not final.
- Failure classification per non-passing cell (mechanical, in `verdict_p55.py`):
  `carry-drift` (NO_MATCH + distractor displaced vs its last accepted anchor:
  centre shift > 0.25 of anchor diagonal OR area ratio outside [0.4, 2.5] —
  the area check is the P5.4 `carry_disp` lesson), `match/grounding` (NO_MATCH,
  not displaced), `grounding` (wrong selection), `carry` (lock/coverage),
  `infra`.

## Estimates (marked as estimates)

- Runtime: ~30–45 s/run + ~40 s one-time boots -> **16 runs ≈ 12–20 min** total
  (smoke run: 27 s wall).
- MC WSEL: **4–5/5** (car10:615 should flip on the unique caption; risk cells:
  none structural).
- MC SWAP: **3–4/5** (car7:460 + car10:615 should flip on maintenance;
  car10:240's near-miss caption fix is the least certain; car9:560's ~46x76 px
  receding distractor is the riskiest new cell).
- M arm: expected to reproduce the P5.3 failures on the caption-bound cells while
  keeping the drift cells fixed — that split is the attribution result.
- car3:200 control: expected FAIL both legs (resolution-bound; smoke run
  confirms WSEL FAIL, wrong selection, same as P5.3/P5.4).

## Smoke test (disclosed, 2026-07-14T06:16Z)

One real-stack cell was run at design time to verify the rig end-to-end:
`MC_WSEL_car3_200` (the non-gating control) — results.json + overlay.mp4
produced; both re-anchor rounds fired and were accepted; full-frame select
acquire 4.51 s; cell FAILs by wrong selection exactly as the P5.3/P5.4 baseline
predicts for the resolution-bound control. Kept under `runs/` (idempotent skip
will preserve it). `--selfcheck` also passes (P5.5 asserts: re-anchor rounds at
f0+90/165 around the current carry box, drifted-carry reseed flips a P5.3-style
SWAP drift failure, reject path leaves the carry alone, rounds >= prompt are
skipped, M-arm caption swap; plus the full upstream P5.3 suite).

## Results (TBD — Opus fills this section only)

Paste `verdict_p55.py` output, then the table:

| cell | arm | leg | pass | selection | acquire_s | reanchor accepted | fail class / reason |
|---|---|---|---|---|---|---|---|
| MC_WSEL_car10_240 | MC | WSEL | | | | | |
| MC_SWAP_car10_240 | MC | SWAP | | | | | |
| MC_WSEL_car10_615 | MC | WSEL | | | | | |
| MC_SWAP_car10_615 | MC | SWAP | | | | | |
| MC_WSEL_car9_300 | MC | WSEL | | | | | |
| MC_SWAP_car9_300 | MC | SWAP | | | | | |
| MC_WSEL_car7_460 | MC | WSEL | | | | | |
| MC_SWAP_car7_460 | MC | SWAP | | | | | |
| MC_WSEL_car9_560 | MC | WSEL | | | | | |
| MC_SWAP_car9_560 | MC | SWAP | | | | | |
| MC_WSEL_car3_200 (control) | MC | WSEL | FAIL | distractor | 4.51 | [True, True] | grounding: wrong selection (smoke) |
| MC_SWAP_car3_200 (control) | MC | SWAP | | | | | |
| M_WSEL_car10_240 | M | WSEL | | | | | |
| M_SWAP_car10_240 | M | SWAP | | | | | |
| M_WSEL_car10_615 | M | WSEL | | | | | |
| M_SWAP_car10_615 | M | SWAP | | | | | |

- **RQ-P5.5a (MC WSEL >= 4/5 gating): _/5 -> TBD**
- **RQ-P5.5b (MC SWAP >= 4/5 gating): _/5 -> TBD**
- **Overall: TBD**
- Attribution (M vs MC on car10:240 / car10:615): TBD
- Estimate-vs-actual divergences: TBD

## Deliverables checklist (Opus, after the matrix)

1. Fill Results above (estimate-vs-actual included).
2. `make_proof.py` -> `proof/p55_pass_grid.png`, `proof/p55_reanchor_traj.png`;
   copy 1–2 headline overlays into `proof/` (drift-cell SWAP if it flips, e.g.
   `runs/MC_SWAP_car7_460/overlay.mp4` -> `proof/car7_460_SWAP_MC.mp4`);
   caption each in this README (what it shows, which run).
3. Append RESULTS row(s) to `docs/results/part5-anticipatory.md`, QUESTIONS
   entry (RQ-P5.5a/b + one-line verdicts) to `docs/questions/part5-anticipatory.md`,
   DECISIONS entry (accept-without-IoU-floor re-anchor rule; distractor-only
   maintenance; caption/maintenance attribution split) to
   `docs/decisions/part5-anticipatory.md`.
4. Commit on this branch; do not merge (the loop's reviewer merges).
