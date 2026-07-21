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

## Results (TBD)

| arm | k | n | IoU@0.25 | parse | mean IoU | prefill ms (median) | decode ms (median) | wall ms (median) |
|---|---|---|---|---|---|---|---|---|
| A — full frame @1024 | | 439 | | | | | | |
| B — ROI M=2.0 @512 | | 439 | | | | | | |

**Paired (TBD):** b = , c = , n_effective = 316, McNemar p = .

**RQ-R14.1:** TBD · **RQ-R14.2:** TBD · **RQ-R14.3:** TBD

## Proof deliverables (TBD)

Planned, under `proof/`, from a committed `make_proof.py` reading the two `items.jsonl`:

1. `paired-iou.png` — per-item IoU, arm A vs arm B, one point per sample, with the 0.25 gate
   lines. The numbers are the point here, so this is a figure, not a clip.
2. `discordant-examples.png` — the crops and full frames for a handful of b-cells (ROI right,
   full-frame wrong) with both predicted boxes and the GT drawn on. This one exists because
   the "look at it" rule applies: a +20 pp claim should be visibly true on individual images.
3. `prefill-vs-tokens.png` — on-device prefill ms against prompt tokens for both arms, which is
   the linear-in-area model the original campaign asserted, now at n=878 instead of n=10.

## Status / next step

Pre-registered. Next: run `run_r14.py` (~1 h of Orin wall time), fill in Results, then the
ledger appends (RESULTS Part III, QUESTIONS Part III, DECISIONS if the deploy default moves)
and the registry entry — R-14 is `DONE` only when a paired, on-device claim citing this run is
in `thesis/claims.json` with `machine: jetson-orin-nano-8gb`.
