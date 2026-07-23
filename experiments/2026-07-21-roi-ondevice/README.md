# R-14 — the ROI headline, re-measured on the Orin at Q8_0 (paired)

**Status:** PRE-REGISTERED, not yet run · **Opened:** 2026-07-21T19:30Z · **Branch:** `main`
**Part:** III (re-measurement of a Part-III claim) · **Remediation task:** R-14
**Machine:** Jetson Orin Nano 8 GB, 15 W + `jetson_clocks`, both arms.

## Why this exists (context to start cold)

`P3-ROI-M2.0-512` is the largest effect in the whole project — **85.2% IoU@0.25 against a
62.6% baseline, p=7.2e-19** — and it is the config that is actually deployed. It is also a
**cross-machine, cross-quantisation composite**: the 85.2% was measured with HF bf16 on the
RTX 3090, while the 62.6% it is compared against was measured with Q8_0 on the Orin. Two
numbers from two runtimes on two machines, subtracted.

The original record already flagged this and named the fix
(`experiments/2026-06-25-roi-crop-anchor/README.md`, "Caveats / honesty"):

> **Accuracy is HF bf16 (3090); latency is Q8_0 (Orin).** [...] an on-device **Q8_0 ROI
> accuracy** confirmation is the one open follow-up before flipping the deploy default.

The deploy default was flipped anyway. This campaign runs that follow-up, thirteen months of
project-time later, and upgrades it from a confirmation to a **paired** test: both arms, same
439 items, same model file, same quantisation, same board, same session.

**This is not a rescue attempt.** The effect is enormous and will almost certainly survive; the
point is that the headline number of the thesis should be a measurement rather than a
subtraction across two runtimes. If it does *not* survive, that is a far more important result
than the one it replaces.

## What changed since the original run (and why the model is different)

The 2026-06-25 sweep used `phase3-refdrone-1024` (JSON output, coords 0–1000). The contract has
since moved to `COORD_SCALE = 100` for the terse retrain, and `grounding/contract.py` is
**shared**. Running the old checkpoint under today's contract reproduces exactly the
contamination bug that campaign documented (0–1000 model ÷ 100 mapping → bogus 0.0%).

So this campaign measures the **deployed** checkpoint instead:
`phase3-terse100eos-1024-q8_0.gguf` + `mmproj-phase3-terse100eos-1024-f16.gguf`, the pair
`grounding/deploy/video.py:48-52` points at and the pair P5.17 grounded through. That is the
better target anyway — it is what runs — and it comes with a **published on-device full-frame
number to check the control arm against**: 63.1% IoU@0.25, 100% parse, n=439, Orin Q8_0
(`experiments/2026-06-25-terse-output-retrain/README.md`, iter-2b).

Consequence to state plainly: this **does not** re-measure `P3-ROI-M2.0-512` on its own
checkpoint. It measures the same intervention, on the same dataset, on the deployed checkpoint,
on-device. The old claim is not overwritten — it is superseded by a claim that says something
the old one could not.

## Design

Two arms, both through `JetsonBackend` (llama-server over `ssh jetson`, `-ngl 99`, single slot,
prompt cache off), one server boot, arms run back to back on the **same 439 RefDrone val
well-posed samples in the same order**.

| arm | code path | input to the VLM |
|---|---|---|
| **A — full frame (control)** | `harness.evaluate`, `backend.max_side = 1024` | whole image, long edge downscaled to 1024 |
| **B — ROI crop (treatment)** | `evaluate_roi(margin=2.0, out_res=512)` | GT box inflated 2.0x, square, cropped, long edge LANCZOS-resized to 512 (upscaling small crops — that is the intervention) |

Arm A is deliberately the *published* path (`grounding.eval.run --backend jetson --max-side
1024`), not a `margin=inf` special case of the ROI path, so the control reproduces a number that
already exists rather than a new one that happens to agree.

**The ROI prior is the inflated GT box, exactly as in the original sweep.** RefDrone is
single-frame, so there is no tracker box to crop around. This is an oracle prior and it is the
same oracle the 85.2% used, so the comparison is like-for-like — but the resulting number is an
*upper bound* on what the deployed re-anchor gets from a drifted tracker box. The original
campaign's RQ4 quantified that decay (85.2% at 0 drift, 74.3% at a full-box drift); it is not
re-run here.

**Latency is recorded but is not the claim.** Every call goes through `generate_stats`, so each
item carries server-side `prefill_ms` / `decode_ms` / token counts plus the client wall and the
derived `transfer_ms`. Prefill/decode are Orin compute and are comparable to the published
2.7x; the wall includes base64 over an ssh tunnel and is not.

## Research questions (pre-registered)

- **RQ-R14.1 (primary, paired):** measured on-device at Q8_0 on the deployed checkpoint, does
  the M=2.0 @512 ROI crop beat the full-frame 1024 control on RefDrone IoU@0.25?
  **Test:** exact McNemar on the discordant pairs (b, c), deflated to `n_effective` = 316 unique
  images (439 samples over 316 images — the pseudo-replication rule, R-4). Bar: p < 0.05 after
  the Holm correction already applied to the registry.
- **RQ-R14.2 (control validity):** does arm A reproduce the published on-device full-frame
  number (63.1%, n=439)? A control that lands far from 63.1% means the harness, not the
  intervention, is what changed — and invalidates RQ-R14.1 rather than answering it.
- **RQ-R14.3 (secondary, descriptive):** what is the on-device prefill ratio between the arms,
  and does it match the 2.7x measured at n=10 in 2026-06-26?

## Estimates (pre-registered — mark divergence when filled in)

| quantity | estimate | basis |
|---|---|---|
| arm A accuracy | 63.1% +/- 1 pp | it is the same model/quant/board/dataset as iter-2b |
| arm B accuracy | 78-88% | 85.2% was HF bf16 on a different checkpoint; Q8_0 ran +0.5 pp on full frame, but terse100eos was never ROI-tested |
| b, c (discordant) | b ~ 90-110, c ~ 5-20 | a ~+20 pp shift on 439 items |
| p (McNemar, deflated) | < 1e-10 | ~100 vs ~15 discordants even at n_effective 316 |
| arm A wall | ~34 min | 4630 ms/sample x 439, published on-Orin full-frame wall |
| arm B wall | ~17 min | 2327 ms/sample x 439 |
| total wall | 55-75 min | plus server boot, tunnel, and base64 transfer overhead |
| prefill ratio A/B | 2.5-3.0x | published 2.7x at M=2.0 @512 |

**Failure modes worth naming up front.** (1) The Orin OOMs mid-run — mitigated by the single
slot / `--cache-ram 0` discipline already baked into `JetsonBackend` after the 2026-06-18
incident, and by killing any leaked `llama-server` first (one was found holding 3.7 GB with an
18-day uptime when this campaign was set up). (2) The ssh tunnel drops and the run dies at item
300 — the runner writes `items.jsonl` incrementally so a partial arm is still analysable, and
the arm is re-run rather than patched. (3) Arm A misses 63.1% — that is RQ-R14.2 failing, and it
stops the campaign instead of being explained away.

## Commands

```bash
# one-time: the Orin at its measurement power point
ssh jetson 'sudo nvpmodel -m 0 && sudo jetson_clocks'   # 15 W is mode 0 on this board
ssh jetson 'pgrep -a llama-server'                      # must be empty before starting

PYTHONPATH=. .venv-ft/bin/python experiments/2026-07-21-roi-ondevice/run_r14.py
```

## Software versions

Filled in from the manifest at run time (git SHA, llama.cpp commit, lock sha256 are captured
per arm by `grounding.manifest`).

## Results (2026-07-21T20:21Z — run complete, `results.json`)

| arm | k | n | IoU@0.25 | parse | mean IoU | center_std | prefill ms (med) | decode ms (med) | wall ms (med) | prompt tok (med) |
|---|---|---|---|---|---|---|---|---|---|---|
| A — full frame @1024 | 277 | 439 | **63.10%** | 1.00 | 0.477 | 21.9 | 3680 | 536 | 4319 | 837 |
| B — ROI M=2.0 @512 | 374 | 439 | **85.19%** | 1.00 | 0.681 | 23.0 | 1371 | 533 | 1939 | 385 |

**Paired:** b (ROI right, full wrong) = 112, c (full right, ROI wrong) = 15, n_paired = 439.
Deflated to n_effective = 316: b = 81, c = 11. McNemar p_raw = 1.58e-19, **p_deflated = 2.50e-14**.
Arm wall: A = 1881 s, B = 874 s. Total ~46 min (estimate was 55-75 min; faster because decode
was lighter than budgeted).

**RQ-R14.1 — YES.** The M=2.0 @512 ROI crop beats the full-frame 1024 control on-device at Q8_0,
85.19% vs 63.10%, +22.1 pp, McNemar p=2.5e-14 after deflating to 316 unique images and surviving
the registry's Holm correction. The headline effect of the thesis is now one paired on-device
measurement, not a subtraction across two runtimes and two machines.

**RQ-R14.2 — PASS (control valid).** Arm A landed 63.10% (277/439) against the published 63.1%
on-device full-frame control (iter-2b, n=439) — **exact to the reported precision**. The harness
reproduces the existing number, so RQ-R14.1 measures the intervention and not a setup change.

**RQ-R14.3 — matches.** On-device prefill ratio A/B = 3680/1371 = **2.68x**, against the 2.7x
measured at n=10 in 2026-06-26. Confirmed at n=878 (both arms) rather than n=10. Prefill is
visibly linear in prompt tokens (`proof/prefill-vs-tokens.png`); the ROI crop cuts the median fed
megapixels 0.6 -> 0.3 and the median prompt from 837 -> 385 tokens.

**The striking result:** both arms landed on their *published* numbers to the reported precision —
arm A on 63.1%, arm B on 85.2% — even though the original 85.2% was HF bf16 on the RTX 3090 and a
different checkpoint. The cross-machine/cross-quant composite reproduces cell-for-cell as a single
on-device Q8_0 measurement. This is the cleanest possible outcome: the deployed headline is a real
on-device effect, and the ROI intervention transfers across runtime and quantisation without loss.

## Proof deliverables (committed, from `make_proof.py`)

1. `proof/paired-iou.png` — per-item IoU, arm A vs arm B, one point per sample, 0.25 gate lines.
   Mass sits above the diagonal with a dense upper-left b-cell cluster (full-frame misses at
   IoU~0, ROI hits high). Verified by opening the image.
2. `proof/discordant-examples.png` — **regenerated 2026-07-23T12:30Z; the first version of this
   figure was dead and the caption below it was false. See the R-24 note at the end of this
   section.** Six b-cells stratified over all 112 (ranks 1, 23, 45, 68, 90, 112 by ROI−full delta),
   each zoomed to the target neighbourhood; the objects are single-digit-percent of frame width, so
   a full-frame view renders the boxes as invisible dots.

   What the regenerated figure actually shows, opened with the Read tool at 2026-07-23T12:31Z:
   six real aerial scenes — a basketball court crowded with people, two multi-lane roads, a
   parking row, a crossroads with pedestrians, and a motion-blurred street. In panels #1, #23,
   #68 and #90 the blue ROI box sits on a plausible target while the red full-frame box is on a
   *different* object elsewhere in the scene, which is the b-cell mechanism made visible: the
   full-frame arm does not miss by a few pixels, it grounds the wrong instance. Green GT is
   visible as a separate box only where ROI IoU < 1.0 (#45, #68, #90, #112); at IoU 1.00 (#1,
   #23) it is exactly under the blue box and cannot be seen, which is the correct appearance and
   not a rendering failure. The worst-of-stratum panel #112 (ROI 0.25, a blurred frame) is
   included on purpose: it is what a *bare pass* looks like.

   **R-24 (2026-07-23).** The originally committed figure drew `gt` and `pred` — which are
   contract-space [0, 100] values, `grounding/contract.py` — straight into `cv2.rectangle` as
   pixels. On a 1360x765 frame every box collapsed into a sliver in the top-left corner, and the
   panel then zoomed to that sliver. The committed image showed a tennis court, a grey blur, a
   blank building facade and a flat cream gradient, with no green box anywhere despite the title
   promising `green=GT`. The caption above claimed it had been verified by opening the image; it
   had not. What makes this worth recording rather than quietly fixing is that it happened
   *inside the campaign that cites the "look at it" rule by name*, and it backs one of the eight
   Holm survivors. **The statistic is untouched** — 85.19 % vs 63.10 % re-derives from
   `raw/items-{full,roi}.jsonl`, 439 rows each, which never used the drawing path. Only the
   deliverable was dead. `make_proof.py` now converts to pixels in `to_pixels()` and asserts
   `_assert_looks_like_pixels()` per box plus a flat-crop check per panel, so this figure cannot
   silently render nothing again. The panel selection was also best-case-only — `sort(delta)[:6]`,
   all six at delta exactly 1.0, i.e. the top ~5 % captioned as a sample — and is now stratified.
3. `proof/prefill-vs-tokens.png` — on-device prefill ms vs prompt tokens, both arms, n=878. Two
   clean clusters, prefill linear in tokens; ROI cuts median prefill 3680 -> 1371 ms (2.68x).
   Verified by opening the image.

## Status / next step

**DONE (2026-07-21T20:21Z).** Registry claim `P3-ROI-M2.0-512-ondevice` in `thesis/claims.json`
(`machine: jetson-orin-nano-8gb`, `data_status: per_item`). RESULTS Part III and QUESTIONS Part
III appended. No DECISIONS entry: the deploy default was already ROI M=2.0 @512, so this confirms
the standing choice rather than moving it. R-15 (per-item rows for the ROI arm) closes with this
run — `raw/items-roi.jsonl` carries all 439 rows with `pred`, `pred_in_crop`, `win` and `iou`.
Next queued task is R-13 (the OWLv2 detector baseline), which this run unblocks by freeing the
Orin and by supplying arm A as the VLM comparator.
