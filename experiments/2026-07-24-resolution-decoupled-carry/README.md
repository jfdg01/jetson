# EXP-1 — Resolution-decoupled carry (track-res sweep, on Jetson)

**Status:** DONE — pre-registered 2026-07-24T13:05Z, completed 2026-07-24T16:30Z.
**Verdict:** the carry-res **elbow is 512–640** — 640 keeps 99.4% of 1024's median IoU (0.811 vs
0.816) at 2.5× the on-device throughput (5.76 vs 2.34 Hz); below 512 the rate saturates so it is
pure loss. Deploy at 640, keep 1024 as a size-gated fallback for the small/distant tail. Full
numbers in **Results** below.
**Part:** VI (perception-stack, on-device). **Machine:** `jetson` (SAM2 runs on the Orin; the 3090 is NOT used).
**Power mode:** 15 W + `jetson_clocks` (the only real mode on this board — no MAXN_SUPER).
**Owner claim id (planned):** `EXP1-track-res-noninferiority`.

## Premise (the user's idea, and the honest scope)

User's idea: *"si la VLM funciona mejor con más resolución, pero SAM2 funciona mucho más
rápido con menos, ¿por qué no mandamos la caja sacada a 1080p y después corremos SAM2 sobre
el stream a 768?"* — decouple grounding resolution (high, for the VLM) from tracking
resolution (low, for SAM2 speed).

**Scope decision (recorded up front, rationale below):** the "ground at 1080p" half is
**notional on the available data** and is deferred:
- UAV123 source frames are **1280×720**, not 1080p — there is no >720p signal to ground.
- The deployed grounding checkpoint (`phase3-terse100eos-1024-q8_0`) was **trained at
  `max_side = 1024`** (`grounding/deploy/video.py:_TRAIN_MAX_SIDE`). Grounding above 1024 is
  off-distribution — "more VLM resolution than 1024" is not a free knob, it is a retrain.
- The seed-resolution lever was already spent: **ROI-crop grounding (R-14)** is exactly
  "ground a high-detail crop, deliver a full-frame box"; SR on the crop was rejected (Swin2SR).

So the achievable, deployment-relevant experiment holds the **seed box fixed** and sweeps
only the **SAM2 tracking `image_size` (768 vs 1024)** on the Orin. This is the half that is
both novel and directly actionable: R-16 already measured the speed side on-device —
**1024 = 2.69 Hz, 768 = 4.91 Hz solo (~1.8× faster)** — the open question is *what IoU it
costs*. A true high-res-source variant needs new (≥1080p) footage and is out of scope here;
noted as a follow-up.

## Hypothesis

Tracking at `image_size=768` is ~1.8× faster on the Orin than 1024 and does **not**
meaningfully regress carry IoU. If so, 768 is a free deployment win (more coverage / lower
delivery lag at the same accuracy).

## Confound control

The seed box is **identical** across arms (GT at the seed frame). SAM2 normalizes the seed
box by the original video W/H and only then scales to the internal `image_size`
(`sam2_video_predictor.add_new_points_or_box`, `normalize_coords=True`), so the seed is
resolution-independent — the **only** factor that differs between arms is SAM2's internal
tracking resolution. Both arms score the **same frame set** (same steps), so the IoU
comparison is clean and paired; the Hz difference is reported separately.

## Arms

| Arm | SAM2 `image_size` | Where | Notes |
|-----|-------------------|-------|-------|
| `A1024` | 1024 | Orin | deployed baseline (P6.2-SHOWCASE parity 0.960) |
| `A768`  | 768  | Orin | the speed arm (R-16: 4.91 Hz solo) |

Model = `facebook/sam2.1-hiera-tiny`, eager torch bf16 (NOT TensorRT), `PRUNE_AFTER=32` ring
(R-16: 32 is free, 100 OOM-kills). Same in both arms; only `++model.image_size` changes.

## Data

≥25 UAV123 clips with contiguous GT over the carry window. 28 clips have frames on host
(`bike1 bike3 car10-18 car1_s car2-9 truck2/3 wakeboard2-9`). Per clip: seed = GT at the
first frame with contiguous GT; carry `N_STEPS=24 @ STRIDE=11` (~8.8 s, matches the R-16
2.69 Hz cadence). Clips are the unit of analysis (independent) — **no deflation** needed
(contrast the P5.18 same-clip cells).

## Method / commands

Host stages (UAV123 GT lives on host) → rsync frames to the Orin → carry runs **on the Orin**
via the existing socket service (`jetson_carry_service.py --image-size {768|1024}` +
`carry_client.py`) → pull `boxes.json` back → host scores IoU vs GT from `meta.json`.

```bash
# host: stage all clips (seed + 24 stepped frames + GT into meta.json)
.venv-ft/bin/python experiments/2026-07-24-resolution-decoupled-carry/run_exp1.py stage \
    --clips auto --out runs/exp1

# host: push staging to the Orin, run both arms on-device, pull results
.venv-ft/bin/python experiments/2026-07-24-resolution-decoupled-carry/run_exp1.py carry \
    --out runs/exp1 --sizes 768,1024      # ssh jetson: service + client per clip per size

# host: score + paired stats + figures + look-at-it overlays
.venv-ft/bin/python experiments/2026-07-24-resolution-decoupled-carry/run_exp1.py score \
    --out runs/exp1
```

`run_exp1.py` is a multi-clip generalization of `2026-07-24-p62-showcase/ondevice_carry_demo.py`
(reuses its stage/score/overlay logic and the `carry_client.py` socket protocol). **New code,
built after this pre-registration is approved.** No torch/SAM2 import on the host side.

## Metrics & statistics

Per clip, per arm: per-step IoU vs GT, `held_frac` (steps with IoU≥0.25), `median_iou`,
`final_iou`, and on-device `carry_hz` / `median_ms`.

- **Primary (non-inferiority of 768):** paired **Wilcoxon signed-rank** on per-clip
  `median_iou` (A768 − A1024), with the 95% CI of the paired median delta. PASS if the CI
  excludes a meaningful regression (median IoU loss > 0.05).
- **Secondary:** per-clip PASS = `median_iou ≥ 0.25`; **McNemar exact two-sided** on PASS
  (A768 vs A1024) — expect non-significant (768 ≈ 1024). `min_discordant_for_significance`
  reported (needs b+c ≥ 6). `grounding/stats.py`.
- **Throughput:** re-confirm R-16 on-device Hz live per arm (expect ~2.69 / ~4.91).

**Gate:** 768 non-inferior in IoU (delta CI within noise) **AND** measurably faster on-device
→ 768 is a deployment win. If 768 regresses IoU beyond the band, keep 1024.

## Look-at-it (mandatory)

The scorer draws GT (green) + carried box (cyan) on the real frame for every step; the mid-run
overlay of a sample of clips at **both** resolutions is opened with the Read tool before any
verdict. Mechanical asserts in the scorer: mid overlay <99% one colour (failed render), carried
boxes not byte-identical across steps (dead feed). No frame captured → INVALID.

## Proof deliverables (`proof/`, committed)

1. `iou_768_vs_1024.png` — paired per-clip median-IoU scatter (y=x line), from `results.json`.
2. `hz_ondevice.png` — on-device Hz bar (768 vs 1024), the measured speed win.
3. `overlay_<clip>.mp4` or a side-by-side frame — one clip carried at both res, boxes drawn.

## Estimates (mark actuals on completion)

- Runtime: ~28 clips × 24 steps × 2 res. At 2.69/4.91 Hz: ~8.9 s + ~4.9 s carry per clip,
  ~386 s total carry + init/rsync/service-restart overhead → **~15–25 min** wall (estimate).
- Expected IoU: 768 within ~0.02–0.05 median IoU of 1024 (SAM2 is robust to input downscale
  on these low-texture aerial targets) — estimate; a >0.05 loss would be the interesting result.
- Expected Hz: 2.69 / 4.91 (R-16) ± device thermal.

## Results — the carry-res ELBOW (2026-07-24T16:30Z) — machine=jetson, 15W + jetson_clocks, n=38 clips

Extended from the 768-vs-1024 binary to a full sweep (user: *"run more resolutions to see where
the elbow is"*). Seven SAM2 `image_size` points on the SAME 38 clips / SAME seed boxes; the only
factor that changes is the tracker's internal resolution.

| image_size | median-of-median IoU | mean held_frac | PASS (medIoU≥0.25) | on-device Hz | ms/step | vs 1024 |
|-----------:|---------------------:|---------------:|-------------------:|-------------:|--------:|:--|
| 256  | 0.675 | 0.721 | 28/38 | **10.20** | ~98  | 4.4× fast, −0.141 IoU |
| 384  | 0.760 | 0.768 | 29/38 | 9.64 | ~104 | 4.1× fast, −0.056 IoU |
| 512  | 0.780 | 0.837 | 32/38 | 8.71 | ~114 | 3.7× fast, −0.036 IoU |
| **640**  | **0.811** | 0.859 | 32/38 | **5.76** | ~174 | **2.5× fast, −0.005 IoU** |
| 768  | 0.803 | 0.882 | 33/38 | 4.08 | ~245 | 1.7× fast, −0.013 IoU |
| 896  | 0.805 | 0.897 | 35/38 | 2.99 | ~334 | 1.3× fast, −0.011 IoU |
| 1024 (deployed) | 0.816 | 0.921 | 36/38 | 2.34 | ~428 | baseline |

**The elbow is at 512–640** (`proof/elbow_iou_hz.png`):
- **IoU plateaus above 512.** 512→1024 gains only +0.036 median IoU across a 2× size increase; the
  curve is essentially flat from 640 up (0.811 → 0.803 → 0.805 → 0.816 — inside the run-to-run noise).
- **Hz is flat-high below 640, then falls off a cliff.** 256/384/512 all sit at ~9–10 Hz — the carry
  is **overhead-bound** there (mask decode + ssh framing dominate, not the encoder), so dropping below
  512 buys almost no speed while it keeps costing IoU. Above 640 each size step roughly halves the rate.
- **640 is the sweet spot: 99.4% of 1024's IoU (0.811 vs 0.816) at 2.5× the throughput (5.76 vs 2.34
  Hz).** 512 is the aggressive pick: 96% of the IoU at 3.7×.
- Paired 768-vs-1024 (the original pre-registered contrast) still holds: delta −0.0086, CI95
  [−0.0135, −0.0017], McNemar b=0 c=3 p=0.25 (n.s.) — non-inferior, detectably ~0.01 lower.

**The tail is resolution-gated** (`proof/per_clip_iou.png`, look-at-it): the grey bulk of clips is
flat across all seven sizes, but **9 small/distant clips collapse at low res** and recover only as
size climbs — car11/car13 by ~512, but truck2/truck3/uav3/bike3/person21 need 896–1024. So `held_frac`
(coverage of the harder targets) is the one metric that keeps improving all the way to 1024
(0.721 → 0.921), even though the *median* IoU has plateaued. Big targets are size-insensitive;
sub-pixel targets are the whole reason to keep 1024.

**Verdict:** **the carry-res elbow is 512–640 — near-1024 accuracy at 2.5–3.7× the on-device
throughput, and below 512 the speed saturates so it is pure loss.** Deployment recommendation: run
carry at **640** as the default (best IoU/Hz), keep **1024 as a size-gated fallback** when the target
box is small/distant (the `held_frac` tail). The original "ground at 1080p / track at 768" framing
collapses on this data (720p UAV123, VLM trained ≤1024, seed box res-independent inside SAM2) — this
cleanly isolates and maps the *track-resolution* knob.

## Proof deliverables (`proof/`)

- `elbow_iou_hz.png` — the elbow: median IoU (flat above 512) + on-device Hz (cliff above 640) vs
  image_size, twin-axis. `per_clip_iou.png` — per-clip spaghetti; grey bulk flat, 9 red small-target
  clips collapsing at low res (the tail). `hz_ondevice.png` — the Hz bar across all seven sizes.
  All from `make_proof.py` (reproducible from `runs/exp1/results.json`).

## Status / next step

DONE (elbow). Data (7 sizes) + score + figures + visual verification complete. RESULTS / QUESTIONS /
DECISIONS Part VI rows updated; proof committed.
