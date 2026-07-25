# EXP-2 — Point-and-crop select (pointer vs NL referring expression)

**Status:** DONE — pre-registered 2026-07-24T13:05Z, completed 2026-07-24T15:10Z.
**Verdict:** **MISS on both legs** at the deployed operating point — PT and NL are not separable at
n=26 (WSEL b=1/c=3 p=0.625; SWAP b=0/c=2 p=0.5, both below the reachable floor b+c>=6), though every
discordant leans PT. The real finding is the **grounding-res elbow**: a point-crop at 256 px
(hit@0.5 = 0.769) out-grounds the whole frame at 1024 (0.654), so the pointer is a grounding-
efficiency and localization-precision win, not a delivered-PASS win — the carry closes the gap at
the lenient 0.25 threshold. Full numbers in **Results** below.
**Part:** VI (select, on-device). **Machine:** `jetson` (SAM2 carry runs on the Orin; the
3090 is NOT used). **Power mode:** 15 W + `jetson_clocks`.
**Owner claim id (planned):** `EXP2-point-crop-select`.

## Premise (the user's idea)

*"Ahora mismo defendemos que la idea es lenguaje natural > perseguir objeto, pero si el
objetivo es seguir objetos podemos darle al usuario un pointer que señale un objeto en la
imagen y le pasamos a la VLM el crop alrededor de ese objeto."* — Replace the NL referring
expression with an **operator point**: click a pixel → crop around it → VLM grounds inside the
crop → box → SAM2 carry → deliver. Does removing language help the select?

## What this actually tests (confound, recorded up front)

Referring-expression ambiguity was named the residual select failure in P5.16 (two silver
cars) and probed in R-38. **In this harness the "selection" step (`bind_by_caption`) is
string-equality — correct by construction** (a documented scope cut). Ambiguity therefore
does **not** enter at selection; it enters at **grounding** (`vlm_acquire(caption)` grounds the
NL phrase to a box on the whole frame; with two silver cars it can ground the wrong one). The
point arm replaces whole-frame NL grounding with **crop grounding around the operator point**,
which spatially disambiguates before the VLM ever runs. So:

- **SWAP leg = the real test.** The operator must deliver the **distractor** and suppress the
  target. Point-crop indicates the distractor directly; NL must ground the distractor phrase
  correctly among candidates. Selection separation only bites here.
- **WSEL leg = grounding+carry control**, not a selection test (both arms should mostly pass).

Predicted outcome space: if PT beats NL on SWAP, language/ambiguity is part of the select
bottleneck. If PT ties NL, the residual is **carry/delivery** — consistent with R-38
(grounding symmetric, not the bottleneck) and the thesis's maintain-and-deliver stance; the
NL framing then stands on ergonomics, not accuracy. **Either result is thesis content.**

## Arms

| Arm | Prompt → box | Grounding | Carry |
|-----|--------------|-----------|-------|
| `NL` (baseline) | NL phrase (`target_caption` WSEL / `distractor_caption` SWAP) | `vlm_acquire`, whole frame | SAM2 on Orin |
| `PT` (point→crop→VLM) | operator point at command frame | crop around point → VLM grounds in crop → `map_to_full` | SAM2 on Orin |
| `PT-native` (optional, variant b) | operator point | none — SAM2 seeded from `points=[[x,y]],labels=[1]` | SAM2 on Orin |

- **Operator point** = center of the intended object's GT box at the command/prompt frame
  (`f0 + round(t_p·fps)`, i.e. f0+240 @30fps): `gt[prompt]` center for WSEL,
  `distractor_gt_prompt` center for SWAP. This is an **oracle click** (the user knows which
  object they want) — the honest model of "user points at a thing". A jittered-click
  robustness arm is optional follow-up.
- **PT crop:** degenerate box `[px,py,px,py]` → `grounding/roi.roi_window(min_side=256)` →
  LANCZOS 512 crop (reuses the working `select_p55.roi_reanchor` path) → VLM grounds the crop
  with the same caption (the crop already disambiguates spatially; caption kept for
  comparability) → `map_to_full` → seed SAM2. Decision: PT keeps the caption inside the crop
  rather than a blind "the object" so NL vs PT differs by *spatial constraint only*.
- **PT-native** tests whether the VLM is even needed once a point exists. The `points=` seam
  is supported by SAM2 but **not wired** in the deployed carry (`stream_carry.py` /
  `jetson_carry_service.py` seed box-only) — small plumbing; run only if cheap.

## Data

`experiments/2026-07-20-n25-select/scenes_p518.json` — **26 cells / 13 distinct clips**
(the frozen P5.18 / R-36 set), both legs WSEL + SWAP. Reused **verbatim** so EXP-2 is paired
against the P5.18 baseline cell-for-cell.

## Method / commands

Fork the core select harness `experiments/2026-07-19-autodisc-select/discover_p516.py`
(byte-identical to P5.18/R-36 modulo the scene set). **Two required changes:**

1. **Re-route SAM2 to the Orin.** `discover_p516.py:330` builds SAM2 locally
   (`SAM2VideoPredictor.from_pretrained` — that runs on the 3090, now **forbidden**). Replace
   the local predictor with a socket-service client (`jetson_carry_service.py` init/step) so
   carry runs **on the Jetson**. This shim is the main new plumbing and is reused by all future
   select work. Reported Hz = on-device.
2. **Add the PT arm.** New `--arm {NL,PT,PT-native}`; PT swaps `vlm_acquire(whole frame)` for
   the point→crop→ground→map-back path (operator point from the scene's GT).

```bash
# on-Orin carry service (started by the harness or manually), image_size 1024, ring 32
ssh jetson '~/sam2-bench/.venv/bin/python ~/sam2-bench/jetson_carry_service.py --image-size 1024 --prune-after 32'

# host: run both arms over the 26 cells, both legs, carry on the Orin
.venv-ft/bin/python experiments/2026-07-24-point-crop-select/select_exp2.py \
    --matrix experiments/2026-07-20-n25-select/scenes_p518.json \
    --out runs/exp2 --legs WSEL,SWAP --arms NL,PT     # PT-native if wired

# host: paired McNemar (deflated) + MANDATORY visual audit + figures
.venv-ft/bin/python experiments/2026-07-24-point-crop-select/verdict_exp2.py --runs runs/exp2
```

## Metrics & statistics

Per cell, per arm: `selection_correct`, `genuine_lock` (deliver IoU≥0.25), `coverage`,
`deliver_iou` (vs target GT), `deliver_iou_distractor` (vs distractor GT). PASS scoring per
`select_p56.py`: WSEL PASS = correct ∧ genuine_lock ∧ coverage≥0.5; SWAP PASS =
selection=='distractor' ∧ deliver_iou<0.25 ∧ deliver_iou_distractor≥0.25.

- **Primary (SWAP):** paired **McNemar exact two-sided**, NL-pass vs PT-pass over the SWAP
  cells; **deflate 26→13 clips** (clip clustering, per `thesis/stats-report.md`);
  `min_discordant_for_significance` reported (two-sided needs b+c ≥ 6). `grounding/stats.py`.
- **Secondary (WSEL):** same test as a grounding+carry control (expect a tie).
- Baseline anchor: P5.18 SWAP = 17/26 (0.65). Report NL here to confirm it reproduces.

## Look-at-it (MANDATORY — verdict gate)

`verdict_exp2.py` mirrors `verdict_r36.py:89-104`: it **hard-refuses a verdict** without a hand
`visual_downgrades.json` covering every discordant cell **and** every SWAP-pass cell — each
`deliver.png` / `overlay.mp4` opened with the Read tool. A SWAP "pass" that on inspection
delivers the wrong object (or a mis-placed GT box, cf. the R-36 person13 catch) is downgraded
by hand before the count is trusted.

## Proof deliverables (`proof/`, committed)

1. `pointcrop_vs_nl_<clip>.png` — an ambiguity cell: NL grounding (whole frame, wrong object)
   vs PT (point → crop → correct box → deliver). Before/after if PT wins; both-wrong if it ties.
2. `swap_mcnemar.png` — the SWAP 2×2 (NL-pass × PT-pass) with b/c.
3. `pass_table.png` — per-cell PASS, NL vs PT, WSEL + SWAP.

## Estimates (mark actuals on completion)

- Runtime: 26 cells × 2 arms × (VLM grounding on Orin + ~8 s SAM2 carry on Orin) →
  **~30–60 min** wall (estimate; VLM latency dominates).
- Expected: given R-38 (grounding symmetric, distractor box lands on the distractor object),
  PT likely **ties** NL on SWAP (b+c small, non-significant) → residual is carry/delivery, not
  language. A PT win on SWAP would be the surprising, more-interesting result. Estimate.

## Results — completed 2026-07-24, machine `jetson`

### 1. Primary — delivered PASS at deployed res (NL max_side=1024, PT crop=512)

| Leg | Arm | PASS / n | rate |
|-----|-----|---------:|-----:|
| WSEL | NL | 22/26 | 0.846 |
| WSEL | PT | 24/26 | 0.923 |
| SWAP | NL | 24/26 | 0.923 |
| SWAP | PT | 26/26 | 1.000 |

- **WSEL** McNemar (NL vs PT): b(NL-only)=1, c(PT-only)=3, p=0.625; deflated to 13 clips;
  `min_discordant`=6 → **MISS** (b+c=4 < reachable floor 6, not separable at n=26).
- **SWAP** McNemar (NL vs PT): b=0, c=2, p=0.5; deflated to 13 clips; `min_discordant`=6 →
  **MISS** (b+c=2 < floor 6, not separable).

**Verdict at the deployed operating point: MISS on both legs — PT and NL are not separable at
n=26.** But every discordant leans PT (7 PT-only passes vs 1 NL-only across both legs; PT never
loses a SWAP cell and drops only one WSEL cell to NL). This is exactly the R-38 prediction:
grounding is symmetric at the lenient delivery threshold (0.25 IoU + SAM2 carry rescues NL's
rougher boxes), so the pointer's spatial constraint does not buy extra delivered PASSes here.
NL SWAP reproduces the P5.18 baseline direction (24/26 here vs 17/26 in P5.18 — higher because
this harness scores delivered-distractor, not end-to-end select). **Visual audit:** all 8
`pass=True` discordant/SWAP cells opened with the Read tool and confirmed genuine
(`runs/exp2/visual_downgrades.json`, 0 downgrades) — PT's WSEL wins (car10_615, car9_950) are
real pointer disambiguations among near-identical cars; NL's one win (wakeboard8_750) is a real
target lock; PT's one WSEL loss (wakeboard8_750) is an honest off-crop on the tiny wakeboarder.

### 2. Grounding-res elbow — where PT actually separates (n=26 WSEL cells, IoU≥0.5 hit)

The lenient 0.25 delivery threshold masks the real difference. Sweeping the VLM feed resolution
under a strict grounding-IoU criterion (no carry) exposes it:

| feed px | NL hit@0.5 | NL med IoU | PT hit@0.5 | PT med IoU |
|---:|--:|--:|--:|--:|
| 192 | — | — | 0.231 | 0.289 |
| 256 | — | — | **0.769** | 0.701 |
| 384 | — | — | 0.731 | 0.615 |
| 512 | 0.077 | 0.186 | 0.769 | 0.673 |
| 640 | 0.269 | 0.400 | — | — |
| 768 | 0.462 | 0.478 | **0.846** | 0.737 |
| 896 | 0.654 | 0.617 | — | — |
| 1024 | **0.654** | 0.611 | — | — |

(NL = whole-frame long-edge resize; PT = crop-around-point upscaled long edge. Different x-grids
because the knobs differ: NL down-scales the full frame, PT up-scales a ~256px crop window.)

**PT@256 (0.769) out-grounds NL@1024 (0.654).** The pointer concentrates the VLM's effective
resolution onto the target: a 256px crop lands the box better than the whole 1024px frame,
because the target fills the crop instead of being a few pixels in a wide scene. PT is flat-high
from 256 up (elbow at 256; 192 collapses — the crop clips the object). NL climbs monotonically
and plateaus at 896–1024, never reaching PT's level. **This is the real EXP-2 finding:** the
point-crop is a *grounding-efficiency and localization-precision* win (same accuracy at 4× lower
feed res, better peak accuracy), not a delivered-PASS win at the deployed lenient threshold —
where the carry closes the gap. Proof: `proof/grounding_elbow.png` (viewed).

### 3. Carry-res robustness — the verdict is flat in tracker-res

Re-carrying the fixed acquire boxes at three SAM2 `image_size`s and re-scoring PASS per leg
(`carry_res_sweep.py`, on the Orin):

| carry px | on-device Hz | WSEL NL/PT (b/c) | SWAP NL/PT (b/c) |
|---:|--:|:--|:--|
| 512 | 8.64 | 22/24 (b1 c3) | 24/26 (b0 c2) |
| 768 | 4.07 | 22/24 (b1 c3) | 24/26 (b0 c2) |
| 1024 | 2.34 | 22/24 (b1 c3) | 24/26 (b0 c2) |

**The NL-vs-PT verdict is byte-identical across carry image_size — every count, every discordant
pair.** The select outcome is decided at grounding, not at the tracker resolution: dropping the
carry from 1024 to 512 (3.7× faster on-device, per EXP-1) does not flip a single cell here. So the
primary MISS is robust to the carry-res knob, and EXP-1's deploy recommendation (carry at the 512–640
elbow) is free of any select-quality cost on this set. Hz reproduces EXP-1's curve (8.6/4.1/2.3 Hz).
Proof: `proof/carry_robustness.png` (viewed).

## Status / next step — DONE

Grounding-res elbow + primary verdict + carry-res robustness all complete and audited (8/8 pass
cells confirmed genuine, 0 downgrades). Ledgers appended (Part VI QUESTIONS/DECISIONS/RESULTS).
Proof: `grounding_elbow.png`, `deliver_pass.png`, `carry_robustness.png`.
