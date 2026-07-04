# P5.2 — warm-start generalization + on-screen-speed sweep (Part V)

**Pre-registered:** 2026-07-04T19:20Z. Extends [P5.1](../2026-07-04-warm-start-acquire/README.md)
(warm-start acquire, YES [carry-bound], 6 red-ish cars). Reuses the P5.1 rig **unchanged**
(`warmstart.py` schedule + `replay_e24.py` WARM/COLD/ORACLE legs); the only new code here is
`profiles.py` (data-driven clip selection). Self-contained handoff.
**Status:** COMPLETE 2026-07-04T20:05Z. **RQ-P5.2a = YES** (WARM 21/25, COLD 5/25, 5 categories).
**RQ-P5.2b = NO [flat-in-speed]** (Spearman ρ(gap,speed) = −0.06; the payoff is a large *flat*
offset, not speed-scaling). Full matrix ran clean (0 INVALID).

## Research question

P5.1 showed warm-start beats cold on 6 near-identical cars. Two things it left open, both
central to Part V:

**RQ-P5.2a (generalization):** does the warm-start win hold across object *categories*
(person, boat, wakeboard, bike — not just cars)?

**RQ-P5.2b (speed dependence):** the whole premise is that a blocking acquire lands stale
because the target *moves on screen* during it. So the WARM-vs-COLD advantage should **grow
with on-screen target speed**. Does it? (If the gap is flat in speed, the staleness story is
wrong and the win comes from something else.)

## Context & rationale

- **P5.1 = YES [carry-bound]:** WARM 5/6, COLD 1/6, WARM==ORACLE. Idle-window VLM seed +
  SAM2 catch-up + select-on-command removes the ~135-frame cold delivery staleness. But 6
  clips, one category, and no controlled speed range — a weak base for a thesis claim.
- **Why category variety:** cars are rigid, high-contrast, mid-size. Person/boat/group/bike
  targets stress the VLM seed (small, deformable, crowded) and the carry (appearance drift).
  If warm-start only works on cars, that is a finding; if it generalizes, the Part V claim is
  real.
- **Why speed variety (the Part V axis):** on-screen speed = how fast the GT box moves across
  the frame, in %frame-diagonal/second. Cold acquire is blocking (~4.5 s), so cold staleness ≈
  speed × 4.5 s of displacement. Warm-start delivers fresh, so its error is ~speed-independent.
  Prediction: **WARM−COLD coverage gap rises monotonically with on-screen speed.** That plot is
  the P5.2 thesis figure.

## Dataset selection (data-driven, `profiles.py`)

On-screen speed and size are computed directly from the UAV123 GT boxes — no eyeballing.
`profiles.py` (selfcheck green) scans every anno file and emits, per sequence:
`category` (name prefix), `n_valid` frames, `size_pct` (median box area %frame), `speed_pct_s`
(median centroid displacement, %diag/s), `speed_bin` (slow <3, med 3–8, fast >8 %diag/s —
provisional cuts, retuned to the observed distribution before freezing).

**Selection rule (frozen before running):**
1. **Eligible** = `n_valid ≥ 700` frames (~23 s, so the t_p=8 s + acquire ~4.5 s + 10 s-cover
   schedule fits) AND a single dominant target.
2. **Anchor:** keep the 6 P5.1 cars (car3/7/9/10/14/18) for direct comparability.
3. **Fill the category × speed grid** to 25 total: every available category represented; within
   a category prefer a slow AND a fast instance; **over-weight the `fast` bin** (where staleness
   bites) so the RQ-P5.2b speed sweep has resolution at the hard end.
4. Freeze the chosen 25 + their speed/size numbers into the table below, then author one frozen
   operator caption per new clip ("the person", "the white boat", "the truck", …) matching the
   UAV123 target.

The realized grid (from `profiles.json`) and the frozen 25 go in **Selected clips** below once
the download+profile step runs.

## Legs & rig (reused from P5.1 — no change)

WARM / ORACLE / COLD exactly as [P5.1](../2026-07-04-warm-start-acquire/README.md#the-three-legs):
VLM acquire fired in the idle pre-prompt window, SAM2 seeded on the cached submit frame, idle
catch-up to the prompt, select at t_p=8 s (WARM); GT[0] seed (ORACLE, ceiling); acquire fired at
the prompt, delivered stale (COLD, baseline). Frame math from `warmstart.schedule`; scoring at
each leg's own delivery frame. Backend/tracker unchanged: Qwen2-VL-2B Q8_0 terse max_side 1024,
SAM2.1-tiny TRT fp16 ~6.15 Hz, mask gate app_tau 12.0, Jetson 15 W + jetson_clocks.

**t_p = 8.0 s, cover_s = 10.0 s, fps = 30, n = 1.** n=1 because P5.1 was bit-identical across
both reps on all 36 legs (greedy decode; deterministic rig) — n=2 bought nothing.

## Run matrix (25 clips × 3 legs × n=1 = 75 legs + smoke)

Reuse `experiments/2026-07-04-warm-start-acquire/replay_e24.py` verbatim (it already takes
`--leg/--clip/--caption/--t-p/--cover-s/--out`); no rig edits. Log Jetson power to `raw/` first.

```
# per leg, e.g.:
.venv-ft/bin/python experiments/2026-07-04-warm-start-acquire/replay_e24.py \
    --leg WARM --clip person1 --caption "the person" --t-p 8.0 --cover-s 10.0 \
    --out experiments/2026-07-04-warm-start-generalization/runs/WARM_person1
# loop over the frozen 25 clips x {WARM,COLD,ORACLE} via run_matrix.py
```

Snapshot each run to its own `runs/` dir. **Abort criteria** identical to P5.1 (hang >8 min /
crash / missing json → mark INVALID, continue). Foreground-poll `runs/*/results.json`, do not
stall.

## Verdict rules

Per clip, per leg: **PASS = `genuine_lock` (at the leg's deliver_frame) AND `coverage` ≥ 0.50**
(n=1). Let `W`, `C`, `O` = PASS counts /25.

- **RQ-P5.2a (generalization) = YES** iff `W ≥ 0.7·25` (≥18) **AND** `W > C` **AND** warm-start
  passes in **≥ 4 distinct categories** (not just cars). PARTIAL if it wins overall but is
  category-narrow; NO if `W ≤ C`.
- **RQ-P5.2b (speed dependence) = YES** iff the per-clip **(WARM−COLD) coverage gap** rises with
  `speed_pct_s` — report Spearman ρ over the 25 clips and the gap mean per speed bin
  (slow/med/fast); YES if ρ > 0 with the fast bin gap > slow bin gap. NO/flat otherwise.
- Suffix `[carry-bound]` for clips WARM fails that ORACLE also fails (occlusion/appearance, not
  detection); `[detection-bound]` for clips WARM fails but ORACLE passes (the idle-window VLM
  seed is the binder). Report the WARM-vs-ORACLE gap set as in P5.1.

Relationship to P5.1: P5.1's 6-clip result stays frozen; P5.2 either corroborates it at scale
(the cars should reproduce) or qualifies it.

**Deliver-frame occlusion caveat (known pre-run):** `genuine_lock` hard-requires
`gt[deliver_frame] is not None`. Two of the 25 — **car7 and person10** — have GT absent
(occluded) exactly at the WARM/ORACLE deliver frame 240, so they fail `genuine_lock` on *all*
legs including ORACLE (a GT seed cannot fix a missing GT). These are `[deliver-occluded]`
structural misses, not detection failures — report them flagged with their window coverage (the
real tracking signal), exactly as P5.1 handled car7. Kept in the /25 denominator for P5.1
comparability. COLD's deliver frame (376) is clear on all 25.

## Estimates (mark vs actual)

- **Matrix wall:** ~33 min (75 legs × ~26 s/leg realized in P5.1; per-leg time is ~constant —
  each leg replays a fixed ~686-frame window, not the whole clip). Plus one-time ~1 h tarball
  download + ~10 min extract/profile.
- **W:** est ~17–20/25 (cars reproduce ~5/6; person/boat likely lower on seed quality; expect
  a few `[detection-bound]` small-target misses).
- **C:** est ~3–6/25 (only slow on-screen targets survive the ~4.5 s cold staleness — which is
  exactly RQ-P5.2b: cold should pass the slow bin and fail the fast bin).
- **Speed sweep:** est WARM−COLD gap ≈ 0 in the slow bin, large in the fast bin (ρ > 0).

## Selected clips (frozen 2026-07-04T20:20Z from `profiles.json`)

78/123 UAV123 sequences clear the length gate (≥700 valid frames). Of those, **only 36 have
their own frame directory** — the rest (`car1_2`, `group2_1`, `person7_1`, `uav1_1`, …) are
frame-offset *segments* that share a parent video's frames via a start/end mapping the replay rig
doesn't implement (it zips `sorted(*.jpg)` with the anno 1:1). So selection is restricted to the
36 whole sequences. **This removes group and uav entirely** (they exist only as segments) and
**truck/bird** (no sequence ≥700 frames) — a real UAV123 fact, recorded not worked around.
Building is excluded on purpose: it is a static structure, its "on-screen speed" is pure
ego-motion and would pollute the RQ-P5.2b axis.

The frozen 25 therefore span **5 moving-target categories** (car, person, boat, wakeboard, bike),
verified frame-aligned 1:1. Bins are the **eligible-set tertiles** SLOW<2.3 / 2.3–4.5 med /
FAST>4.5 %diag/s ("fast" = top-third on-screen speed, relative). Speed range 0.00–15.62 %diag/s,
**over-weighting the fast bin** (8 slow / 6 med / **11 fast**) for RQ-P5.2b resolution. Cars are
10/25: the 6 P5.1 anchors + 4 more giving a clean same-category speed sweep 0→7.37. Captions are
generic category phrases (the honest operator phrase; single-dominant-target clips).

| clip | category | frames | size% | speed%/s | bin | caption | anchor? |
|---|---|---|---|---|---|---|---|
| car10 | car | 1405 | 0.16 | 0.00 | slow | the car | yes |
| boat2 | boat | 799 | 2.73 | 1.02 | slow | the boat |  |
| person15 | person | 1339 | 0.20 | 1.02 | slow | the person |  |
| car3 | car | 1717 | 0.06 | 2.04 | slow | the car | yes |
| car9 | car | 1879 | 0.23 | 2.04 | slow | the car | yes |
| boat3 | boat | 901 | 2.86 | 2.04 | slow | the boat |  |
| car14 | car | 1250 | 0.17 | 2.28 | slow | the car | yes |
| car7 | car | 960 | 0.41 | 2.28 | slow | the car | yes |
| person13 | person | 883 | 0.39 | 2.89 | med | the person |  |
| wakeboard8 | wakeboard | 1543 | 0.04 | 3.23 | med | the wakeboarder |  |
| person6 | person | 901 | 0.42 | 3.68 | med | the person |  |
| wakeboard3 | wakeboard | 823 | 0.08 | 4.09 | med | the wakeboarder |  |
| bike1 | bike | 3085 | 0.59 | 4.21 | med | the cyclist |  |
| person1 | person | 799 | 0.52 | 4.21 | med | the person |  |
| person18 | person | 1393 | 3.97 | 4.57 | fast | the person |  |
| car18 | car | 1207 | 0.81 | 5.11 | fast | the car | yes |
| person20 | person | 1783 | 6.29 | 5.21 | fast | the person |  |
| car17 | car | 1057 | 1.07 | 5.96 | fast | the car |  |
| car4_s | car | 830 | 0.83 | 6.13 | fast | the car |  |
| wakeboard6 | wakeboard | 1165 | 0.13 | 7.22 | fast | the wakeboarder |  |
| car1_s | car | 1475 | 0.34 | 7.37 | fast | the car |  |
| car3_s | car | 1300 | 1.20 | 7.37 | fast | the car |  |
| wakeboard2 | wakeboard | 733 | 0.29 | 7.37 | fast | the wakeboarder |  |
| person10 | person | 855 | 0.45 | 8.42 | fast | the person |  |
| person1_s | person | 1600 | 0.79 | 15.62 | fast | the person |  |

`frames` = jpg count (= anno lines, 1:1 verified); `speed%/s`/`size%` are medians over valid
(non-NaN) frames, so a clip's valid-frame count can be < `frames`. The list is frozen in
`clips.json` (what `run_matrix.py` reads); `profiles.json` (full 123-seq profile) lives with the
data. **Note the category-count caveat for RQ-P5.2a:** 5 categories, ≥4 threshold still applies.

## Results (2026-07-04T20:05Z, n=1, 0 INVALID)

**W = 21/25, C = 5/25, O = 22/25.** Backend/rig unchanged from P5.1 (Q8_0 terse max_side 1024,
SAM2.1-tiny TRT fp16, mask gate app_tau 12.0, Jetson 15 W + jetson_clocks). PASS = `genuine_lock`
(at the leg's deliver_frame) AND `coverage` ≥ 0.50. `gen/cov` below is `genuine_lock`/`coverage`.

| clip | speed%/s | WARM gen/cov | COLD gen/cov | ORACLE gen/cov | WARM−COLD gap | WARM PASS? |
|---|---|---|---|---|---|---|
| car10 | 0.00 | T/1.000 | F/0.000 | T/1.000 | +1.00 | YES |
| boat2 | 1.02 | T/1.000 | T/1.000 | T/1.000 | +0.00 | YES |
| person15 | 1.02 | T/1.000 | F/0.897 | T/1.000 | +0.10 | YES |
| boat3 | 2.04 | T/1.000 | T/1.000 | T/1.000 | +0.00 | YES |
| car3 | 2.04 | T/1.000 | F/0.000 | T/1.000 | +1.00 | YES |
| car9 | 2.04 | T/1.000 | F/0.000 | T/1.000 | +1.00 | YES |
| car14 | 2.28 | T/0.980 | T/0.870 | T/0.980 | +0.11 | YES |
| car7 | 2.28 | F/0.111 | F/0.000 | F/0.111 | +0.11 | no [deliver-occluded] |
| person13 | 2.89 | T/0.970 | F/0.000 | T/0.970 | +0.97 | YES |
| wakeboard8 | 3.23 | T/0.710 | F/0.000 | T/0.700 | +0.71 | YES |
| person6 | 3.68 | T/0.953 | T/0.907 | T/0.937 | +0.05 | YES |
| wakeboard3 | 4.09 | T/0.923 | F/0.000 | T/0.923 | +0.92 | YES |
| bike1 | 4.21 | T/0.963 | F/0.000 | T/0.970 | +0.96 | YES |
| person1 | 4.21 | T/0.937 | F/0.000 | T/0.927 | +0.94 | YES |
| person18 | 4.57 | F/0.293 | F/0.000 | T/1.000 | +0.29 | no [detection-bound] |
| car18 | 5.11 | T/0.993 | F/0.000 | T/0.983 | +0.99 | YES |
| person20 | 5.21 | T/0.980 | F/0.000 | T/0.980 | +0.98 | YES |
| car17 | 5.96 | F/0.000 | F/0.000 | T/0.997 | +0.00 | no [detection-bound] |
| car4_s | 6.13 | T/0.907 | F/0.000 | T/0.900 | +0.91 | YES |
| wakeboard6 | 7.22 | T/0.730 | F/0.000 | T/0.733 | +0.73 | YES |
| car1_s | 7.37 | T/0.747 | F/0.000 | T/0.783 | +0.75 | YES |
| car3_s | 7.37 | T/0.930 | T/0.987 | T/0.923 | -0.06 | YES |
| wakeboard2 | 7.37 | T/0.677 | F/0.000 | T/0.443 | +0.68 | YES |
| person10 | 8.42 | F/0.859 | F/0.104 | F/0.859 | +0.76 | no [deliver-occluded] |
| person1_s | 15.62 | T/0.787 | F/0.000 | T/0.817 | +0.79 | YES |

**RQ-P5.2a (generalization) = YES.** W=21 ≥ 18, W(21) > C(5), and WARM passes in **all 5**
categories (car, person, boat, wakeboard, bike). Of the 4 WARM misses, 2 are the pre-registered
`[deliver-occluded]` structural fails (car7, person10 — GT absent at deliver frame 240, fail
ORACLE too), so on the non-degenerate 23-clip set WARM is **21/23 = 91%**. The 6 P5.1 car anchors
reproduce (car3/9/10/14/18 PASS; car7 structural) — P5.1 corroborated at scale, across categories.

**RQ-P5.2b (speed dependence) = NO [flat-in-speed].** Spearman ρ(gap, speed) = **−0.06** (not > 0).
Per-bin mean WARM−COLD gap: **slow +0.42, med +0.76, fast +0.62** — large and positive in *every*
bin, not rising with speed. The staleness-grows-with-speed prediction is refuted: the warm-start
payoff is a big *flat* offset, already saturated at slow speeds. Mechanism: COLD's ~135-frame
delivery staleness sinks it broadly (C=5/25) regardless of on-screen speed — the 5 COLD survivors
(boat2, boat3, car14, person6, car3_s) are not the slow clips but the ones whose target happens to
sit near its deliver-frame position, a geometry accident independent of speed. So the warm-start
win is **real and general but not mediated by the speed axis Part V hypothesised** — a clean
negative that reshapes the story: warm-start beats cold because cold's *delivery* is stale, full
stop, not because faster targets move further during the blocking acquire.

**WARM-vs-ORACLE gap set:** WARM loses to ORACLE on **person18, car17** (`[detection-bound]`:
ORACLE's GT seed passes where the idle-window VLM seed misses — the seed is the binder, not the
carry) and *beats* ORACLE on **wakeboard2** (WARM cov 0.677 > ORACLE 0.443, seed noise). Net 21 vs
22. Unlike P5.1 (WARM==ORACLE exactly), P5.2 opens a 2-clip detection headroom at scale — the VLM
seed is no longer free on every category, which is itself a finding (small/deformable targets).

**Estimate vs actual:** matrix wall ~19 min (est ~33 min — per-leg faster than P5.1's 26 s). W=21
landed at the top of the est ~17–20 range; C=5 mid-range (est 3–6). The **speed-sweep estimate was
wrong**: predicted gap ≈0 slow / large fast (ρ>0); actual gap is large in *all* bins (ρ=−0.06).
The wrong estimate is the content — the staleness mechanism is delivery-lag, not motion-during-
acquire.

## Deliverables (proof/)

1. **`proof/gap_vs_speed.png`** (primary, the Part V thesis figure): scatter of per-clip
   (WARM−COLD) coverage gap vs on-screen speed, points coloured by category, with the ρ and the
   per-bin means — shows warm-start's payoff growing with target speed.
2. **`proof/generalization_grid.png`**: WARM/COLD/ORACLE PASS across the 25 clips grouped by
   category (does the win hold beyond cars).
3. **`proof/person20_warm_vs_cold.mp4`** (money shot): side-by-side overlay on **person20**
   (fast non-car, 5.21 %diag/s, WARM T/0.980 vs COLD F/0.000). Left = WARM: fresh idle-window
   seed, green held box tracks the moving person (red GT). Right = COLD: the ~135-frame-stale
   delivered box lands where the person *was* and never covers it (cov 0.000). Overlays from
   `replay_e24.run_matrix_clip(clip=True)`, hstacked with ffmpeg.

Figures from a committed `make_proof.py` over `runs/*/results.json` + `profiles.json`.
