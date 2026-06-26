# Demo tab: ROI re-anchor speedup (make the prefill lever visible) — Part III

**Status:** ✅ BUILT (2026-06-26) · **Branch:** `v3/object-permanence`.
**Kind:** demo/integration (not a benchmark campaign) — wires the validated ROI-crop
prefill lever into the professor demo as a fourth tab.

## Why this exists

`results/2026-06-25-roi-crop-anchor/` proved (offline, HF bf16, RefDrone) that a tight
ROI crop fed at 512 is **2.7× cheaper on prefill AND +22.6 pp more accurate** than the
full-frame anchor. That result is a table. This tab makes it **tangible and live**: upload
an image + phrase, watch the full-frame anchor and the ROI re-anchor run side by side on
the deployed Q8_0, with the prefill/decode split for each.

It also closes — qualitatively — the one open follow-up from that experiment: the offline
sweep was HF bf16 on the JSON (0–1000) checkpoint; **this tab runs ROI live on the deployed
terse Q8_0 (0–100) model**, so it's a real on-device check that the lever transfers.

## What the tab does (`grounding/deploy/gui.py`, tab "Re-anchor speedup")

Single uploaded image, two passes, one honest flow that mirrors the two-mode deploy:
1. **Full-frame acquire** — the deploy resize (`max_side=1024`), one VLM pass → box +
   its prefill cost. This is the expensive cold/re-acquire pass.
2. **ROI re-anchor** — crop a square **M=2.0×** box around the acquired box, upscale to
   **512 px** (`grounding.roi.roi_window` + `crop_resize`), re-anchor, map the prediction
   back (`map_to_full`). This is the cheap per-frame pass a following loop actually runs.

Both boxes are drawn on the full image (red = full-frame, green = ROI, grey = the crop the
VLM saw) and returned with `prefill_ms` / `decode_ms` from the server `timings` block, plus
the prefill speedup. Endpoint: `POST /compare`. No new dependency, no retraining; the crop
is the same image-transform + coordinate-map the offline experiment used.

## Scope / honesty

- **The "prior" here is the full-frame box, not an oracle.** That's faithful to deploy:
  the re-anchor crops around the *anchor's own* last position, exactly what the tracker
  would carry. (The offline experiment used a GT-centered prior + a drift sweep; here the
  prior is whatever the full-frame pass found.)
- **Re-anchor only.** A crop can't re-find an object that left the ROI — cold/re-acquire
  stays full-frame. This tab shows the re-anchor pass, not acquisition.
- **Live numbers ≠ the RefDrone benchmark.** Per-image latency depends on the upload's
  resolution and the target's size; treat the tab as a qualitative demonstration of the
  *shape* (crop → cheaper prefill, tighter box), with `results/2026-06-25-roi-crop-anchor/`
  as the quantified result.
- **Single-user demo.** Shares the one booted `_BACKEND` (no request lock), like the other
  live tabs.

## On-device check (live, deployed terse Q8_0, `ssh jetson` 15 W)

Integration test (`_compare` on example images, server `timings`):

| case | full-frame prefill | ROI re-anchor prefill | speedup | box (full → ROI, 0–100) |
|---|---|---|---|---|
| "the white car" | 4034 ms | 1388 ms | **2.91×** | [50,68,55,79] → [50,70,55,81] |
| "the red car" | 3042 ms | 1375 ms | **2.21×** | [71,81,76,87] → [72,87,78,93] |
| "the bus" | 3696 ms | 1373 ms | **2.69×** | [15,56,25,70] → [15,57,25,71] |

ROI prefill is pinned at **~1375 ms** (a 512×512 crop is a fixed vision-token count, so it
doesn't vary with the upload) — matching the offline experiment's 1374 ms — while full-frame
prefill scales with image size (3042–4034 ms here). Boxes are preserved/tightened, confirming
the lever **transfers to the deployed terse Q8_0**. (Decode here ~535 ms, lower than the ROI
experiment's 964 ms because the deploy uses the *terse* output format — the two latency levers
stacking, as intended.) This is a qualitative on-device confirm of the *latency* lever; the
quantified on-device **IoU@0.25** (RefDrone via the GGUF backend) remains the open follow-up.

## Anchor cadence re-measure (2026-06-26, terse Q8_0, 15 W, incl. ssh)

The "your video" tracking demo schedules fresh anchors at a fixed period
(`grounding/deploy/video.py:ANCHOR_PERIOD_S`). That constant was the stale T0/T4 **2.26 s**
(old JSON full-frame anchor @512, server-side). Re-measured the *actual* wall the demo
blocks on per anchor, on the deployed terse Q8_0, via `measure_cadence.py` (5 example
images × 2 reps, `video._anchor_box` — the exact GUI path, ssh + transfer included):

| anchor mode | wall (median) | min–max | n |
|---|---|---|---|
| full-frame **cold acquire** (@1024) | **4814 ms** | 3829–4941 | 10 |
| **ROI re-anchor** (@512 crop) | **2021 ms** | 1694–2081 | 10 |

**Honest reading — not a clean 3×:** the steady-state cadence is the ROI re-anchor at
**~2.0 s**, *barely below* the old 2.26 s. The 2.7× ROI win is real but it's **vs the deploy
full-frame @1024 (4.8 → 2.0 s = 2.4×)**, not vs the 2.26 s figure — that was 512 long-edge,
and a 512×512 ROI crop carries ~the same pixel count, so its prefill lands near the old
number. The genuinely wrong part was the GUI's **cold acquire**: it runs full-frame @1024
(~4.8 s), so the 2.26 s constant under-reported the real acquire by ~2×. `ANCHOR_PERIOD_S`
is now **2.0 s** (re-anchor), with the ~4.8 s one-time acquire documented in the comment.

## Files

- `grounding/deploy/gui.py` — tab HTML/JS + `_compare` handler + `_timed_post` (verbose
  POST for the prefill/decode split) + `_annotate` gains `color`/`window`.
- `measure_cadence.py` — on-Orin anchor-wall timing that set `ANCHOR_PERIOD_S` (above).
- Reuses `grounding/roi.py` (the validated crop/map helpers) and `grounding/contract.py`
  (scale-agnostic — works at the terse `COORD_SCALE`).

## Run

```bash
source .venv-ft/bin/activate
python -m grounding.deploy.gui          # http://127.0.0.1:8000 → "Re-anchor speedup" tab
```
