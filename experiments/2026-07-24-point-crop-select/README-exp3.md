# EXP-3 — CARLA click-to-ground-to-track TIMING at the discovered resolutions

**Status:** **STOPPED — PARTIALLY COMPLETE, NOT RUNNING.** Pre-registered 2026-07-24T16:20Z;
`acquire` ran the same afternoon and nothing after it did; state recorded 2026-07-25T13:10Z.

- **Completed:** the `acquire` stage, twice — once per caption mode (`--caption generic`, then
  `--caption rich`). Each leg is 25 clips × 2 arms = 50 grounding calls on the Orin, 4.1 min of
  VLM wall clock per leg (8.2 min across both, sum of `ground_ms`). Outputs
  `runs/exp3/acquire.json` (generic) and `runs/exp3/acquire_rich.json` (rich), plus their `.log`
  files and a handful of unaudited overlay/colour-check PNGs.
- **Not completed:** `carry` (never launched — no SAM2 leg exists), `score`, the paired Wilcoxon,
  the mandatory look-at-it audit across both arms, the `proof/` figures, the interactive click
  demo, and the Part VI ledger rows (RESULTS / QUESTIONS / DECISIONS).
- **No claim was registered.** `EXP3-carla-click-timing` was the *planned* id; it is **not** in
  `thesis/claims.json` and nothing below may be cited as a thesis result.
- **To finish it**, a future session needs, in order: (1) `select_exp3.py carry` on the Orin for
  both arms, (2) `select_exp3.py score`, (3) the overlay audit with the Read tool, (4) a
  `make_proof_exp3.py` that does **not yet exist** (see the command block), (5) the three ledger
  rows and a claim registration. Decide first whether the acquire numbers below (which point
  *against* the pre-registered expectation) still justify the carry spend, or whether EXP-3 should
  be re-scoped or abandoned — that decision is unmade.

**Part:** VI (select, on-device). **Machine:** `jetson` (VLM q8_0 + SAM2 carry both on the Orin;
the 3090 only rendered the frames earlier — no tracker on the 3090). **Power mode:** 15 W + `jetson_clocks`.
**Owner claim id (planned):** `EXP3-carla-click-timing`.

## Premise (the user's idea)

*"En CARLA: un usuario hace click en un objeto, lo grounded-eamos con la resolución descubierta
apropiada y después lo trackeamos con la mejor resolución. Quiero una comparación de tiempos sobre
las mismas escenas."* — Compose the two elbows found earlier into one **clicked** pipeline and time
it on identical CARLA scenes:

- **grounding** at the point-crop elbow — EXP-2 showed **PT@256 out-grounds NL@1024** (the crop
  concentrates the VLM's resolution onto the target);
- **carry** at the tracker elbow — EXP-1 showed **image_size 640 = 99.4 % of 1024's IoU at 2.5×
  throughput**, and the select verdict was flat across carry-res.

The question EXP-3 answers that EXP-1/EXP-2 could not: **on a live-scene pipeline (click → ground →
track), how much wall-clock does using the discovered resolutions actually save, and does it cost
any accuracy?** The user chose a **real mouse→actor hit-test** (not an oracle designation) and the
**existing 25-clip CARLA bank** as the scene set.

## What this tests (and the honest risk, recorded up front)

A CARLA-specific risk: P6.2 found the deployed q8_0 **non-discriminative on whole-frame nadir cars
at 45 m** (it needed an ORACLE designation, G6). EXP-3 does **not** ground the whole frame — it
grounds a **crop around the click**, which is exactly the EXP-2 mechanism that upsamples a tiny
target to fill the feed. So EXP-3 is a direct test of whether the point-crop **rescues** grounding
where whole-frame failed. Target sizes span **13–42 px** (40 m → 120 m altitude), so the OPT/FULL
split doubles as an altitude-vs-accuracy probe: the 256 crop feeds the car near-native (≈40 px at
40 m), the 1024 crop upscales it ≈4× (≈160 px) — more absolute pixels, more VLM compute. Where the
256 feed keeps enough car to ground, OPT wins timing for free; where it doesn't, FULL buys accuracy
with latency. **Either way is thesis content.**

## Arms (differ ONLY in the two resolution knobs, on identical frames)

| Arm | ground crop res (`ROI_RES`) | carry `image_size` | meaning |
|-----|---:|---:|---|
| `OPT` | 256 | 640 | the discovered elbows (EXP-2 + EXP-1) |
| `FULL` | 1024 | 1024 | naive full-res baseline |

Both arms are the **same clicked pipeline**: click → `hit_test` (screen px → actor id over the
already-projected GT boxes) → `roi_reanchor` grounds a 256-px crop **window** around the click,
resized to `ROI_RES` → SAM2 carry at `image_size`. The click per scene = the target vehicle's
GT-box center at the command frame (models "the user clicks the salient car"); the **real hit-test
runs on that pixel** and is scored (does it resolve to `target_id`?). An interactive-mouse demo
(`click_demo.py`) exercises the same `hit_test` on a live window for one clip.

## Data — the existing deterministic bank

`experiments/2026-07-21-carla-gt-bank/runs/bank/` — **25 clips × 1200 frames** (~60 s @ ~18 Hz),
`Town10HD_Opt`, nadir, sync-mode deterministic (Gate-C: two same-seed runs bit-identical), 80
vehicles/clip, altitudes 40/60/80/100/120 m. Per-frame per-vehicle GT in `gt.jsonl` (2D box keyed
by CARLA actor id + logged camera pose). One designated **target** per clip (`manifest.target_id`,
camera-followed). Replayed from disk — **no new rendering**. (Bank frames + `gt.jsonl` are
gitignored/local-only; committed artifacts are `manifest.json` + `proof/`.)

## Method / commands

Command frame = first frame ≥ 100 where the target is on-screen and ≥ 120 visible px. Carry window
= 8 s fed at ~5 Hz (strided from the ~18 Hz bank), same frames to both arms. Grounding latency =
wall-clock around the VLM call (includes client resize + ssh transfer + prefill + decode — the real
deployed latency, and larger feeds cost more of all four). Carry latency = on-device `StreamCarry.step`
ms per frame (from the bridge, excludes transport).

```bash
# RAN (twice, once per caption mode) -> runs/exp3/acquire.json + runs/exp3/acquire_rich.json
.venv-ft/bin/python select_exp3.py acquire --out runs/exp3 --caption generic
.venv-ft/bin/python select_exp3.py acquire --out runs/exp3 --caption rich
# NOT RUN — no output for either stage exists
.venv-ft/bin/python select_exp3.py carry   --out runs/exp3   # SAM2 carry on the Orin, both arms
.venv-ft/bin/python select_exp3.py score   --out runs/exp3   # timing + accuracy, paired
.venv-ft/bin/python select_exp3.py --selfcheck
# DOES NOT EXIST — never written. `make_proof_exp3.py` is nowhere in the repo (verified
# 2026-07-25 by `find`); a future session must write it, not look for it.
.venv-ft/bin/python make_proof_exp3.py --out runs/exp3        # figures
```

**Missing-script warning.** Two files this README names were never created and are not on disk
anywhere in the repo: `make_proof_exp3.py` (above) and the interactive `click_demo.py` referenced
under *Arms* and in proof deliverable 4. Both were plans, not artifacts. Do not go looking for
them; the `hit_test` they were to exercise lives in `select_exp3.py`.

## Metrics & statistics

Per clip × arm: `hit_ok` (hit-test resolved the click to `target_id`), `ground_iou` (vs target GT
at cmd) + `hit@0.5`, `ground_ms`, `coverage` (frac of window frames IoU≥0.25 vs the GT track),
`carry_median_iou`, `carry_median_ms` / `carry_hz`, `end_to_end_ms`.

- **Primary — TIMING:** paired **Wilcoxon signed-rank** OPT vs FULL over the clips on `ground_ms`,
  `carry_median_ms`, `end_to_end_ms`; report median paired diff. (Continuous latency, one pair per
  clip → signed-rank, not McNemar.)
- **Accuracy guardrail:** paired OPT vs FULL on `ground_iou` and `coverage` — the timing win only
  counts if these do not regress. Reported by altitude (the analysis axis).
- **Hit-test:** overall `hit_ok` rate (both arms use the same click, so it is arm-independent).

## Look-at-it (MANDATORY)

Every scored cell writes `runs/exp3/overlays/<arm>_<clip>.jpg` — target GT (red), grounded box
(green), click (yellow dot). Open a low/mid/high-altitude overlay for **each arm** with the Read
tool before writing any verdict; a `ground_iou` number is not trusted until the box is seen on the
car. `_overlay` asserts the cmd frame is <99 % one colour (dead-render guard).

**Not done.** The audit above never ran. What the stopped run left on disk is six PNGs in
`runs/exp3/overlays_rich/` (`FULL_clip00/08/11/16/24`, `OPT_clip11` — a FULL-heavy, non-systematic
sample, so no per-arm comparison is possible from it) plus five `colorcheck_clip*.png` and a
`color_contact_sheet.png` from the rich-caption colour extractor. One frame was opened on
2026-07-25 to confirm the artifacts are genuine renders and not dead frames: `FULL_clip11.png`
shows a nadir road with a silver car, the red GT box, the green grounded box overlapping it
(`ground_iou` 0.92) and the yellow click dot on the roof. That is a liveness check on **one**
cell — it is not the per-arm, per-altitude audit this section requires.

## Proof deliverables (`proof/`, committed)

1. `exp3_timing.png` — grounding ms + carry ms (or Hz), OPT vs FULL, per altitude — the headline
   speed comparison.
2. `exp3_accuracy_vs_alt.png` — ground_iou + coverage, OPT vs FULL, vs altitude — the guardrail
   (where does the 256 crop stop grounding the tiny car?).
3. `exp3_click_overlay.png` — a clicked scene: click → hit-test box → grounded box → GT, both arms.
4. (if demo run) `click_demo.mp4` — a real interactive click driving ground+track on one clip.

**None of the four exists.** No EXP-3 figure or clip was produced; the `proof/` directory in this
campaign holds EXP-2 deliverables only.

## Estimates (mark actuals on completion)

- Runtime: 25 clips × 2 arms; acquire ~3–4 min (VLM boot + 50 grounds), carry ~10–15 min (OPT @640
  ~5.8 Hz + FULL @1024 ~2.3 Hz over ~40 frames × 25 × 2). Estimate.
- Expected: OPT grounding **~3–4× faster** than FULL (256 vs 1024 feed) and carry **~2.5× faster**
  (640 vs 1024, per EXP-1). Accuracy: OPT ties FULL at 40–60 m; a possible FULL edge at 80–120 m
  where the 256 crop starves the 13–20 px car. End-to-end OPT clearly faster. Marked estimates.

## Partial results — `acquire` stage ONLY. NOT A FINDING.

Everything in this section is the acquire half of a two-half experiment. **It is not a result, no
claim was registered for it, and it must not be cited** — the primary metric (`end_to_end_ms`) and
the accuracy guardrail (`coverage`) both need the `carry` stage that never ran, and the mandatory
per-arm overlay audit was never done. It is recorded because it is ~8 min of on-Orin q8_0
measurement that would otherwise be lost, and because it points *against* the pre-registered
expectation — which is exactly the kind of thing a future session must not rediscover from scratch.

Source: `runs/exp3/acquire.json` (generic caption `"car"`) and `runs/exp3/acquire_rich.json`
(rich caption, e.g. `"silver car in the center"`, colour read off the pixels inside the GT box).
Both files are committed via a narrow `.gitignore` re-include; the `.log` and `.png` siblings are
not, and the `.log` content is a strict subset of the JSON.

**Grounding latency (the one thing the acquire stage does measure cleanly)** — wall clock around
the VLM call, deployed path (client resize + ssh transfer + prefill + decode), Jetson q8_0,
15 W + `jetson_clocks`, n = 25 clips per cell:

| leg | arm | `ground_ms` median | min–max | median FULL/OPT |
|---|---|---:|---:|---:|
| generic | OPT (crop→256) | 1014 | 874–1412 | — |
| generic | FULL (crop→1024) | 9051 | 4219–9077 | **8.93×** |
| rich | OPT (crop→256) | 1017 | 875–1396 | — |
| rich | FULL (crop→1024) | 9063 | 4212–9087 | **8.91×** |

The ~8.9× is stable across both captions and larger than the estimated 3–4×. It is also
uncontested — nobody has argued the 256 feed is slower.

**Hit-test:** `hit_ok` = **50/50 in both legs** (100 %). The click→actor resolution over the
projected GT boxes never failed, at any altitude. This is the one sub-result that is complete on
its own terms, since the hit-test does not depend on the carry stage.

**Accuracy (the guardrail — where it goes wrong):** `ground_iou` vs the target GT box at the
command frame.

| leg | arm | mean IoU | median IoU | hit@0.5 | hit@0.25 |
|---|---|---:|---:|---:|---:|
| generic | OPT | 0.110 | 0.000 | 3/25 | 5/25 |
| generic | FULL | 0.161 | 0.000 | 5/25 | 5/25 |
| rich | OPT | 0.229 | 0.256 | 2/25 | 13/25 |
| rich | FULL | 0.470 | 0.656 | **14/25** | 16/25 |

Per-altitude hit@0.5, rich leg (n = 5 per cell): 40 m OPT 1/5 vs FULL 4/5; 60 m 1/5 vs 3/5;
80 m 0/5 vs 3/5; 100 m 0/5 vs 2/5; 120 m 0/5 vs 2/5. Paired over the 25 clips, the rich leg has
12 discordant pairs where **FULL** clears 0.5 and OPT does not, and **0** the other way.

**What this does and does not say.** The pre-registered expectation was "OPT ties FULL at 40–60 m,
a possible FULL edge at 80–120 m". The acquire data does not show a tie at any altitude — the
256 crop loses to the 1024 crop everywhere in the rich leg, i.e. the OPT arm buys its 8.9× by
throwing away the pixels the VLM needed. But this is **not** a verdict:

- Half the pipeline is missing. Nothing here touches carry, `coverage`, or `end_to_end_ms`.
- The two legs differ by a knob (`--caption`) that is **not** in the pre-registered arm table, so
  the generic-vs-rich comparison is post-hoc. Note the generic leg grounds badly in *both* arms
  (3/25 and 5/25) — with the caption `"car"` and 80 vehicles in frame, the referring expression is
  ambiguous by construction, so that leg mostly measures prompt underspecification, not resolution.
- No visual audit. A `ground_iou` of 0.00 with `hit_ok` true can be a box on the wrong car or a box
  nowhere near one, and only the overlays distinguish those. They were not opened arm-by-arm.
- No statistics were run and none should be quoted from this table.

## Status / next step

**Stopped, not running** (see the status block at the top). `acquire` completed on the Orin in two
caption legs; nothing downstream was launched, and no process is live. The data that exists is
`runs/exp3/acquire.json` + `runs/exp3/acquire_rich.json`, both now committed — they were gitignored
by `experiments/*/runs/**` until 2026-07-25, when a one-line re-include was added for exactly these
two paths (the `runs/**` rule stays, it guards the multi-GB artifacts).

Next, for whoever picks this up — but read the partial-results section first, because the honest
next step may be to drop EXP-3 rather than pay for the carry stage:

1. Decide whether to continue. The acquire half already contradicts the pre-registered expectation
   (OPT does not tie FULL at any altitude), and EXP-3's premise was that the point crop *rescues*
   grounding. If it does not, the timing comparison is a comparison between a fast wrong answer and
   a slow less-wrong one, and the interesting experiment is a different one. Record the decision.
2. If continuing: `select_exp3.py carry` then `score`, both arms, then the paired Wilcoxon.
3. Do the look-at-it audit properly — low/mid/high altitude, **both** arms, opened with the Read
   tool — before any verdict. The single frame checked so far is a liveness check, nothing more.
4. Write `make_proof_exp3.py` (it does not exist) and, only if a demo is still wanted,
   `click_demo.py` (also does not exist).
5. Only then: Part VI ledger rows (RESULTS / QUESTIONS / DECISIONS), a claim registered in
   `thesis/claims.json`, and committed `proof/` figures.

If the decision is to abandon EXP-3, that is a legitimate outcome and belongs in DECISIONS with its
rationale — the acquire numbers above are the evidence for it, and they stay here either way.
