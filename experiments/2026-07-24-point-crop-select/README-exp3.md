# EXP-3 — CARLA click-to-ground-to-track TIMING at the discovered resolutions

**Status:** PRE-REGISTERED + running — 2026-07-24T16:20Z
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
.venv-ft/bin/python select_exp3.py acquire --out runs/exp3   # VLM point-crop ground, both arms
.venv-ft/bin/python select_exp3.py carry   --out runs/exp3   # SAM2 carry on the Orin, both arms
.venv-ft/bin/python select_exp3.py score   --out runs/exp3   # timing + accuracy, paired
.venv-ft/bin/python select_exp3.py --selfcheck
.venv-ft/bin/python make_proof_exp3.py --out runs/exp3        # figures
```

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

## Proof deliverables (`proof/`, committed)

1. `exp3_timing.png` — grounding ms + carry ms (or Hz), OPT vs FULL, per altitude — the headline
   speed comparison.
2. `exp3_accuracy_vs_alt.png` — ground_iou + coverage, OPT vs FULL, vs altitude — the guardrail
   (where does the 256 crop stop grounding the tiny car?).
3. `exp3_click_overlay.png` — a clicked scene: click → hit-test box → grounded box → GT, both arms.
4. (if demo run) `click_demo.mp4` — a real interactive click driving ground+track on one clip.

## Estimates (mark actuals on completion)

- Runtime: 25 clips × 2 arms; acquire ~3–4 min (VLM boot + 50 grounds), carry ~10–15 min (OPT @640
  ~5.8 Hz + FULL @1024 ~2.3 Hz over ~40 frames × 25 × 2). Estimate.
- Expected: OPT grounding **~3–4× faster** than FULL (256 vs 1024 feed) and carry **~2.5× faster**
  (640 vs 1024, per EXP-1). Accuracy: OPT ties FULL at 40–60 m; a possible FULL edge at 80–120 m
  where the 256 crop starves the 13–20 px car. End-to-end OPT clearly faster. Marked estimates.

## Results (TBD)

Filled on completion: arm table (hit_ok, ground_iou/hit@0.5, ground_ms, coverage, carry_ms/Hz),
paired Wilcoxon on the three latencies + two accuracy fields, per-altitude breakdown, visual audit.

## Status / next step

Pre-registered; `acquire` running on the Orin. Next: `carry` (both arms), `score`, open overlays
(look-at-it), build the interactive `click_demo.py`, figures, then append the Part VI ledger rows
(RESULTS/QUESTIONS/DECISIONS) and commit proof.
