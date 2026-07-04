# P5.2 — warm-start generalization + on-screen-speed sweep (Part V)

**Pre-registered:** 2026-07-04T19:20Z. Extends [P5.1](../2026-07-04-warm-start-acquire/README.md)
(warm-start acquire, YES [carry-bound], 6 red-ish cars). Reuses the P5.1 rig **unchanged**
(`warmstart.py` schedule + `replay_e24.py` WARM/COLD/ORACLE legs); the only new code here is
`profiles.py` (data-driven clip selection). Self-contained handoff.
**Status:** PRE-REGISTERED — dataset selection + matrix pending the UAV123 download.

## Research question

P5.1 showed warm-start beats cold on 6 near-identical cars. Two things it left open, both
central to Part V:

**RQ-P5.2a (generalization):** does the warm-start win hold across object *categories*
(person, boat, truck, group, bike, uav — not just cars)?

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

## Estimates (mark vs actual)

- **Matrix wall:** ~33 min (75 legs × ~26 s/leg realized in P5.1; per-leg time is ~constant —
  each leg replays a fixed ~686-frame window, not the whole clip). Plus one-time ~1 h tarball
  download + ~10 min extract/profile.
- **W:** est ~17–20/25 (cars reproduce ~5/6; person/boat likely lower on seed quality; expect
  a few `[detection-bound]` small-target misses).
- **C:** est ~3–6/25 (only slow on-screen targets survive the ~4.5 s cold staleness — which is
  exactly RQ-P5.2b: cold should pass the slow bin and fail the fast bin).
- **Speed sweep:** est WARM−COLD gap ≈ 0 in the slow bin, large in the fast bin (ρ > 0).

## Selected clips (TBD — filled from profiles.json before running)

| clip | category | frames | size% | speed%/s | bin | caption | anchor? |
|---|---|---|---|---|---|---|---|
| _(25 rows: 6 P5.1 cars + ~19 across categories/speeds)_ | | | | | | | |

## Results (TBD)

| clip | speed%/s | WARM gen/cov | COLD gen/cov | ORACLE gen/cov | WARM−COLD gap | WARM PASS? |
|---|---|---|---|---|---|---|
| _(25 rows)_ | | | | | | |

`W=_/25, C=_/25, O=_/25.` RQ-P5.2a = TBD. RQ-P5.2b: Spearman ρ(gap, speed) = TBD;
gap by bin slow/med/fast = TBD. Estimate-vs-actual: TBD.

## Deliverables (proof/)

1. **`proof/gap_vs_speed.png`** (primary, the Part V thesis figure): scatter of per-clip
   (WARM−COLD) coverage gap vs on-screen speed, points coloured by category, with the ρ and the
   per-bin means — shows warm-start's payoff growing with target speed.
2. **`proof/generalization_grid.png`**: WARM/COLD/ORACLE PASS across the 25 clips grouped by
   category (does the win hold beyond cars).
3. One overlay clip on a **fast non-car** target where WARM passes and COLD misses (the money
   shot: fresh warm box tracks the fast mover, stale cold box lands where it *was*).

Figures from a committed `make_proof.py` over `runs/*/results.json` + `profiles.json`.
