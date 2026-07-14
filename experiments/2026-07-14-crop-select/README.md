# P5.4 — ROI-constrained select-on-command (crop the prompt frame to the carried candidates)

- **Date:** pre-registered 2026-07-14T02:25Z (Madrid wall-clock)
- **Status:** COMPLETE — RQ-P5.4a FAIL (VSEL 3/5), RQ-P5.4b FAIL (VSWP 3/5), overall **NO [match-bound, resolution-bound]**. Ran 2026-07-14T02:33Z (Madrid). Matrix clean (10/10, no abort). A FAIL is a valid result.
<!-- prior status -->
- **Status (pre-run):** PRE-REGISTERED — matrix not yet run
- **Roles:** design + patches by **Fable**; **Opus** runs the matrix and fills Results only — do **NOT** re-patch code. If a run crashes for infra reasons, rerun the single cell; if the code is wrong, stop and report instead of editing.
- **Branch:** `experiment/crop-select`
- **Part:** V (anticipatory grounding). Predecessor: P5.3 multi-candidate select — **NO [match-bound]** (WSEL 3/5, SWAP 2/5), record in
  [`../2026-07-14-multi-candidate-select/README.md`](../2026-07-14-multi-candidate-select/README.md).

## Research question

P5.3's late-binding select (VLM fires on the **full** prompt frame; box IoU-matched to the two
carried candidate boxes; matched track delivered) failed with **NO_MATCH dominant** (4 of 7
non-passes): the deployed VLM boxed an object *outside both carries*. This experiment constrains
the VLM to a crop that **contains exactly the carried candidates** — the union of the two carried
boxes at the prompt frame, inflated ×1.5, floored at 256 px, LANCZOS-resized to 512 (the deployed
Part III re-anchor budget, `grounding/roi.py`, M=2.0@512 = +22.6pp) — and keeps everything else of
P5.3 identical (same 5 frozen scenes, same IoU-match floor 0.10, same deliver fairness rule).

- **RQ-P5.4a (ROI select works):** with the VLM fired on the candidates-union ROI crop, does the
  target phrase deliver the named target's live track? **YES iff VSEL PASS ≥ 4/5** (per-run PASS =
  selection==target AND genuine_lock IoU≥0.25 at deliver AND coverage≥0.5 over 10 s).
- **RQ-P5.4b (the phrase drives it):** does the distractor phrase flip the selection? **YES iff
  VSWP PASS ≥ 4/5** (per-run PASS = selection==distractor AND delivered box off the target,
  IoU<0.25 vs target GT at deliver, AND no failure reason).
- **Overall P5.4 = YES iff both.** Verdicts are mechanical from `runs/*/results.json`.

Non-gating recorded quantities (thesis content either way):

- **NO_MATCH count** across the 10 runs vs P5.3's 4 — the mechanism's specific claim is that the
  ROI window kills the third-object NO_MATCH family *by construction*.
- **Measured ROI acquire latency** vs P5.3's full-frame ~4.5–4.9 s. Estimate (marked as estimate):
  ~1.5–2.5 s, extrapolating the Part III ROI-anchor ≈2.0 s. A latency drop also shrinks the
  realtime bridge, so carries drift less before delivery — a second-order help, not the claim.
- **CLIP crop-scoring secondary arm** (`circlectx`, ViT-L/14 primary + ViT-B/32): the selection it
  *would* have made per run. This settles the P5.3-pre-registered crop-scoring question as a
  documented secondary rather than burning the cycle on it (see pilot below).

## P5.3 audit (this cycle, load-bearing for the design)

Re-read of `../2026-07-14-multi-candidate-select/runs/*/results.json`:

- In **every** NO_MATCH scene the carried **target** box at the prompt frame was ON GT
  (IoU 0.868 car10:615, 0.891 car7:460, 0.726 car3:200) — the carries were fine; the failure is
  the VLM's free-frame grounding, confirming the `[match-bound]` diagnosis. The match rule never
  mis-fired: when the VLM box overlapped a carry, the right track was delivered.
- One carry-maintenance exception: **SWAP_car7_460's distractor carry** drifted from its seed
  `[900,308,1000,352]` to `[0,407,41,424]` (frame edge) during idle catch-up. Deterministic
  (`idle_catchup_multi` is non-realtime), so it **will reproduce** in VSWP_car7_460. P5.4 tags this
  with a pre-registered diagnostic: `carry_disp` = centre shift seed→prompt / frame diagonal,
  `carry_suspect` iff > 0.35 (non-gating; attributes a failure to carry maintenance, not select).
- car3:200 WSEL picked the white distractor for "the red car": the target is ~16×40 px — the
  Part II small-object resolution ceiling. The ROI crop's 2–5× LANCZOS upscale attacks exactly this.

## Design-time pilot (disclosed; provenance = `pilot_variants.py`)

The loop steer named CLIP crop-scoring (deep-research target from P5.3) as candidate #1. The
deep-research cycle was run (ReCLIP IPS, red-circle visual prompting — SOURCES.md) and then
**falsified at design time** before pre-registering a verdict on it:

- Smoke test: vanilla ReCLIP IPS (crop + blur σ=100 sum, ViT-L/14) on the easiest scene
  (car9:300) picked the **silver target for "the black car"** at prob 0.963 — CLIP is
  size/quality-biased toward the larger, sharper crop. UAV123 candidates are 16–100 px, far below
  the RefCOCO sizes ReCLIP was validated on.
- Pilot (`pilot_variants.py`): 5 variants × 2 CLIP models on the deterministic `cand_at_prompt`
  boxes from the P5.3 runs, 3 scenes × 2 captions = 6 selections. Chance = 3/6. Results: ips 3/6,
  crop 3/6, ctx 4/6, circle 3–4/6, **circlectx 5/6** (red ellipse + 2.5× context window @336) —
  the only above-chance variant, and with near-tie margins.
- **Pilot bias disclosed:** the pilot used 3 of the 5 verdict scenes (selection outcomes only, no
  carry/deliver dynamics). That is why the CLIP arm is **recorded, non-gating** in P5.4 — its
  per-run selections are evidence, not a verdict. Gating an experiment on a 5/6-with-near-ties
  method would have pre-registered a predictable FAIL.

**Pivot rationale:** the audit says the bottleneck is *where the VLM is allowed to look*, and the
repo already owns a validated fix for exactly that — the Part III ROI-crop lever (deployed,
+22.6pp, ≈2.0 s anchor). ROI-constrained select uses only deployed, validated components
(`grounding/roi.py` round-trip + deployed q8_0 VLM + P5.3 match rule) and attacks both observed
failure modes (third-object grounding excluded by construction; small candidates upscaled).

## Rejected alternatives

- **CLIP crop-scoring as the gating mechanism** — falsified by the design-time pilot (above);
  demoted to recorded secondary arm. Kept in the record because P5.3 pre-registered it.
- **SigLIP instead of CLIP** — same family, same crop-size pathology expected; no evidence it
  fixes the 16–100 px regime; would add a new model to the stack for a secondary arm.
- **VLM multiple-choice ("which crop matches: A or B?")** — the deployed model is fine-tuned to
  the terse 4-integer box contract; its instruction-following on novel multiple-choice formats is
  unvalidated and off-contract. Would need its own validation campaign first.
- **Idle-window candidate maintenance / t_p sweep** (loop-steer candidate #2) — upstream of the
  observed failure: the audit shows carried boxes were on GT at the prompt in the failing scenes.
  Selection, not maintenance, is the binding constraint (car7 SWAP is the one exception, tagged by
  the `carry_disp` diagnostic instead).
- **Dead levers** (charter list) — none re-proposed: no cold-acquire speedups, no VLM swap, no
  EdgeTAM, no SR, no text-only scene index.

## Mechanism (what actually runs)

`select_p54.py`, importing the P5.3 rig (`select_p53.py`) and the deployed ROI lever
(`grounding/roi.py`) rather than copying them:

1. Seed two carries at `f0` (target from GT[f0], distractor from the frozen hand-annotated box —
   identical to P5.3), idle catch-up `f0→prompt` at CAND_HZ = CARRY_HZ/2 = 3.075 Hz each
   (deterministic, non-realtime).
2. At the prompt frame: `union_window` = `roi_window` (margin 1.5, min_side 256) over the union of
   the carried boxes; `crop_resize` LANCZOS long-edge 512; fire the deployed Jetson q8_0 VLM on
   the crop with the leg's caption; `map_to_full` the terse box back to frame pixels.
   (JetsonBackend max_side=1024 is downscale-only, so the 512 crop is fed untouched.)
3. Realtime bridge: both carries alternate realtime steps (frames drop at wall-clock) while the
   VLM runs; `deliver = prompt + round(measured_acquire_s × fps)` — same fairness rule as P5.3.
4. IoU-match the mapped box against the carried boxes **at the prompt frame** (floor 0.10,
   unchanged); deliver the matched track's *current* (bridged) box; 10 s realtime coverage on the
   winner at full CARRY_HZ = 6.15 Hz (the measured on-Orin SAM2-TRT budget). REGROUND off
   (isolate the select mechanism, mirroring P5.3 v1).
5. Per run also record: `carry_disp`/`carry_suspect`, the CLIP `circlectx` selection (non-gating),
   `acquire_s`, `roi_window`, `match_ious`, and an overlay MP4 of `f0→cover end`.

Scenes: the **frozen P5.3 set**, referenced in place —
[`../2026-07-14-multi-candidate-select/scenes.json`](../2026-07-14-multi-candidate-select/scenes.json)
(car10:240, car10:615, car9:300, car7:460, car3:200; t_p=8 s, cover 10 s, fps 30). Frozen so the
before/after against P5.3 is cell-by-cell.

## Software / hardware config

- Host: RTX 3090 box, venv `.venv-ft` (torch 2.6.0+cu124, transformers 4.57.6,
  opencv-contrib, sam2). SAM2 carry runs locally **rate-capped to 6.15 Hz** (measured on-Orin
  TRT rate, E1) — same replay convention as E18/P5.1–P5.3.
- Jetson Orin Nano 8 GB over `ssh jetson`: deployed Qwen2-VL-2B **q8_0** + mmproj via
  `JetsonBackend`, max_side=1024, **15W + jetson_clocks** (NOPASSWD).
- CLIP checkpoints `openai/clip-vit-large-patch14` + `openai/clip-vit-base-patch32`
  (HF, already cached locally this cycle; ~1.7 GB + ~600 MB).
- Data: UAV123 at `experiments/2026-07-03-real-video-replay/data/UAV123` (present).

## Run matrix (Opus: copy-paste, in order)

```bash
cd /home/gara/jetson   # branch experiment/crop-select

# 0. power mode + selfcheck (no hardware)
ssh jetson "sudo nvpmodel -q; sudo jetson_clocks --show | head -5"
.venv-ft/bin/python experiments/2026-07-14-crop-select/select_p54.py --selfcheck

# 1. the matrix: 5 scenes x {VSEL,VSWP} = 10 runs (idempotent: skips cells
#    whose results.json exists; rerun a crashed cell by deleting its dir)
mkdir -p experiments/2026-07-14-crop-select/raw
.venv-ft/bin/python experiments/2026-07-14-crop-select/select_p54.py \
    --matrix experiments/2026-07-14-multi-candidate-select/scenes.json \
    --out runs 2>&1 | tee experiments/2026-07-14-crop-select/raw/matrix_$(date +%Y%m%d_%H%M).log

# (single-cell rerun example)
# rm -rf experiments/2026-07-14-crop-select/runs/VSEL_car9_300
# .venv-ft/bin/python experiments/2026-07-14-crop-select/select_p54.py \
#     --matrix experiments/2026-07-14-multi-candidate-select/scenes.json \
#     --only car9:300 --legs VSEL --out runs 2>&1 | tee -a experiments/2026-07-14-crop-select/raw/rerun.log

# 2. proof figures (DoD-7)
.venv-ft/bin/python experiments/2026-07-14-crop-select/make_proof.py
```

Proof deliverables (`proof/`, committed + captioned):

1. `p54_pass_grid.png` — P5.3 vs P5.4 PASS grid per scene, NO_MATCH cells marked. Shows VSEL
   3/5 = P5.3 WSEL 3/5 cell-for-cell, VSWP 3/5 up from SWAP 2/5, and the surviving car10:615 /
   car3:200 / car7:460 failures.
2. `p54_acquire_match.png` — acquire latency + winning match IoU per run vs P5.3. The clear win:
   ROI acquire ~2.08 s median vs P5.3 full-frame ~4.5–4.9 s (~2.3×), with match IoU 0.48–0.75 on
   the cells that grounded a carry.
3. `p54_vsel_car10_615.mp4` — proof-of-failure: the P5.3 NO_MATCH cell, still NO_MATCH under ROI.
   The VLM grounds "the white car" onto the in-crop big silver sedan (a third object *between* the
   two carries, inside the union crop by construction), so no carry matches → no delivery. This is
   the figure behind the "ROI reduces but does not eliminate NO_MATCH" finding.
4. `p54_vsel_car9_300.mp4` — positive contrast: same rig, "the silver car" grounds the carried
   silver target inside the ROI crop, match IoU 0.75, delivered live track locks at IoU 0.83,
   coverage 0.97 → PASS. Late-binding select works when the VLM grounds a carry; the verdict FAILs
   only because that condition still misses on 2/5 scenes.

## Verdict + abort rules (mechanical)

- Per-run PASS = `leg_pass()` in `select_p54.py` (printed and stored as `"pass"` in results.json).
- RQ-P5.4a YES iff VSEL 4/5; RQ-P5.4b YES iff VSWP 4/5; overall YES iff both. Suffix the verdict
  with `[carry-bound]` if the only failures have `carry_suspect` non-empty, `[match-bound]` if
  NO_MATCH persists (>0 runs), `[resolution-bound]` if car3 still mis-selects with a valid match.
- **Abort:** Jetson backend fails to boot 3× → stop, report infra. First two VSEL runs both
  NO_MATCH *with a valid parsed VLM box* → stop and inspect (window/mapping suspect — do not
  patch, report). Any run hung > 20 min wall → kill, mark cell INVALID in the log, continue.
  ≥ 3 INVALID cells → stop without a verdict.
- Estimates (marked as estimates): VSEL 4–5/5, VSWP 3–4/5 (VSWP_car7_460 is the known
  carry-drift risk cell), wall ≈ 25–40 min total (10 runs × ~2–4 min: Jetson boot dominates).

## Results (filled 2026-07-14T02:33Z)

Jetson power mode check output: `NV Power Mode: 15W` (+ `sudo jetson_clocks`). Rig on local
RTX 3090 (SAM2 carry, rate-capped to 6.15 Hz), VLM q8_0 max_side 1024 on the Jetson over SSH,
ROI crop LANCZOS long-edge 512. n=1 per cell (deterministic, as P5.1/P5.2/P5.3). Wall ~4 min
total (Jetson kept warm across cells). Matrix ran 10/10, exit 0, no abort triggered.

| Scene | VSEL sel | VSEL match_iou | VSEL iou@deliver | VSEL cov | VSEL PASS | VSWP sel | VSWP PASS | clip sel (VSEL/VSWP) | acq_s (VSEL/VSWP) |
|---|---|---|---|---|---|---|---|---|---|
| car10:240 | target | 0.674 | 0.746 | 1.00 | **PASS** | distractor | **PASS** | target / distractor | 2.09 / 2.08 |
| car10:615 | NO_MATCH (0.000) | — | — | 0.00 | FAIL | NO_MATCH (0.000) | FAIL | target / target | — / — |
| car9:300 | target | 0.747 | 0.833 | 0.97 | **PASS** | distractor | **PASS** | target / distractor | 2.06 / 2.06 |
| car7:460 | target | 0.602 | 0.591 | 1.00 | **PASS** | NO_MATCH (0.000)† | FAIL | target / target | 1.60 / — |
| car3:200 | distractor | 0.480 | 0.000 | 0.00 | FAIL | distractor | **PASS** | distractor / distractor | 2.11 / 2.11 |

† VSWP_car7_460 is the pre-registered carry-drift cell: the distractor carry drifted from its
seed to the frame edge during idle catch-up (`carry_suspect=['distractor']`, `carry_disp` 0.36),
so the union crop mis-framed the distractor and the VLM box matched neither carry → NO_MATCH.
Attributable to carry maintenance, not the select mechanism, exactly as pre-registered.

- **RQ-P5.4a:** VSEL 3/5 (car10:240, car9:300, car7:460) → **FAIL** (needs ≥4/5)
- **RQ-P5.4b:** VSWP 3/5 (car10:240, car9:300, car3:200) → **FAIL** (needs ≥4/5)
- **Overall P5.4 = NO [match-bound, resolution-bound]** (YES requires both a and b). NO_MATCH
  persists (3 runs) → `[match-bound]`; car3:200 VSEL mis-selects the white distractor for "the
  red car" with a *valid* match (m_iou 0.48) → `[resolution-bound]`. Not `[carry-bound]`: the
  car10:615 NO_MATCH failures have empty `carry_suspect`.
- NO_MATCH count: **3** (P5.3 baseline 4) · CLIP circlectx tally: **7/10** correct (VSEL→target /
  VSWP→distractor) · median ROI acquire: **2.08 s** (P5.3 full-frame ~4.5–4.9 s).

### What broke where

- **ROI cut acquire latency ~2.3× (4.5–4.9 s → 2.08 s median), as predicted from the Part III
  ROI-anchor ≈2.0 s lever** — the single unambiguous win. Every cell that grounded a carry did so
  at ~1.6–2.1 s. This is a deployed, validated component doing exactly what it was expected to.
- **ROI did NOT move the VSEL verdict: identical 3/5 to P5.3's WSEL, cell-for-cell** (same PASSes
  car10:240/car9:300/car7:460, same 2 failures car10:615 NO_MATCH + car3:200 wrong-object). The
  crop constrains *where* the VLM looks, but both VSEL failures survive the crop:
  - **car10:615 NO_MATCH (both legs):** the union crop still contains the pre-flagged big silver
    sedan mid-frame; the VLM grounded the caption onto that in-crop third object, not either
    carry. ROI excludes objects *outside* the union, but a distractor object *between* the two
    carries is inside the crop by construction — so the third-object NO_MATCH family is reduced,
    not eliminated (4→3). The "kills NO_MATCH by construction" hypothesis is **falsified**.
  - **car3:200 VSEL `[resolution-bound]`:** the 2–5× LANCZOS upscale did NOT rescue the ~16×40 px
    red target — the VLM still boxed the white-car distractor for "the red car" (match valid at
    0.48, so it delivered the wrong track, IoU 0.0). Upscaling a 16 px object to ~80 px is not
    enough for colour disambiguation at this scale.
- **VSWP improved 2/5 → 3/5 vs P5.3 SWAP:** car10:240 now passes — the ROI crop let the
  distractor caption ("the black car") ground onto the carried distractor where the full frame had
  NO_MATCH'd. The crop helps the *distractor*-caption grounding more than the target's.
- **CLIP circlectx (non-gating secondary) 7/10**, in line with the design-time pilot's
  above-chance-but-fragile 5/6; it agreed with the VLM selection on the same 7 runs and would not
  have rescued car10:615 (picked target both legs) — confirms the pilot call to keep it
  non-gating rather than pre-registering a verdict on it.

### Estimate vs actual

- VSEL landed **3/5** vs estimated 4–5/5 — worse; the ROI upscale did not fix car3's resolution
  ceiling as hoped, and car10:615's in-crop third object was not anticipated to survive the crop.
- VSWP landed **3/5** vs estimated 3–4/5 — in range; the car7 carry-drift cell failed exactly as
  the pre-registered `carry_disp` diagnostic flagged.
- Acquire latency **2.08 s median** vs estimated ~1.5–2.5 s — dead on the estimate; the ROI lever
  transferred from Part III as predicted.
- Wall **~4 min** vs estimated 25–40 min — far under (Jetson server stayed warm across all 10
  cells; boot was not re-paid per cell).

## Ledger checklist (after the verdict)

- [x] RESULTS row(s) → `docs/results/part5-anticipatory.md`
- [x] QUESTIONS entry (RQ-P5.4a/b + verdicts) → `docs/questions/part5-anticipatory.md`
- [x] DECISIONS entry (CLIP demoted to secondary on pilot evidence; ROI pivot) → `docs/decisions/part5-anticipatory.md`
- [x] SOURCES — appended this cycle (ReCLIP, red-circle VP, CLIP checkpoints)
- [x] 4 proof deliverables committed + captioned above
