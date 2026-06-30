# 2026-06-27 — ROI re-anchor shrink-and-drift death spiral (negative result + fix)

**Status:** bug found via the GUI "Live tracking" tab, fixed with a one-line guard,
self-checks green. On-device behaviour re-confirm still pending (see Open below).

## What broke

Forcing a **fast re-anchor cadence** on the deploy GUI's "Live tracking (your video)"
tab (re-anchor ≈ 0.7–1.1 s instead of the measured 2.0 s) collapsed the lock within
the clip. The per-anchor stats told the whole story:

| frame | elapsed | crop fed | box (full-frame px) | result |
|---|---|---|---|---|
| 30  | 6.55s | 780×780 | 195×117 | correct (yellow car) |
| 60  | 1.09s | 288×288 | 72×56   | correct |
| 90  | 0.79s | 135×136 | 15×34   | **drifting** (box off the car) |
| 120 | 0.80s | 128×128 | 19×32   | wrong |
| 150 | 0.69s | 86×86   | **0×21** | degenerate, locked on a *white* car |
| 180 | 0.71s | 108×109 | 16×27   | wrong object |

## Root cause — unbounded positive feedback

The deployed re-anchor (`grounding/deploy/video.py::_anchor_box`) crops a square window
`ROI_MARGIN (4×) · max(box_w, box_h)` around the **previous** box and feeds it
**native** (`crop_resize(..., upscale=False)`, chosen for prefill parity). That makes
crop size proportional to box size, with nothing to stop it shrinking:

```
box shrinks ──▶ crop = 4·box shrinks ──▶ less context + fewer pixels
     ▲                                              │
     └────────── VLM returns smaller/drifted box ◀──┘
```

Read straight off the table: box 195px → crop 780px; box 21px → crop **86px** → fed at
**64 prompt tokens**. At 86×86 native the model has almost no pixels and no surrounding
context, so it returns a smaller/off box, which shrinks the next crop, and so on.
Because no fast-tracker loss is declared (the GUI's CSRT coast doesn't trip on this
slow drift), the system **never falls back to full-frame re-acquire** — the spiral has
no floor and no escape.

Forcing a fast cadence didn't *cause* the spiral; it just packed enough re-anchor
iterations into the short clip for the collapse to become visible. At the measured
2.0 s cadence a 9 s clip only fits ~3 anchors — too few to bottom out — which is why
the demo looked fine until the cadence was pushed.

## Fix — floor the crop side

One guard breaks the feedback loop: a minimum crop side. `roi_window` gains an optional
`min_side` (px); once `ROI_MARGIN·box < min_side` the crop size pins constant regardless
of how small the box gets, so the VLM always retains enough surrounding context to pull
the box back onto the target.

- `grounding/roi.py` — `roi_window(..., min_side=0.0)`. Default `0` keeps the
  single-frame RefDrone eval sweep (`experiments/2026-06-25-roi-crop-anchor`) byte-for-byte
  unchanged; only the deploy path opts in. Self-check asserts a ~1% box floors to
  `min_side`.
- `grounding/deploy/video.py` — `ROI_MIN_CROP = 384`, threaded into the re-anchor crop
  and the GUI's "fed" preview so the panel matches what was actually sent.

`384` px ≈ a third of the 1080-wide extracted frame — enough road context around a
receding car that a slightly-off box still has the target inside the next crop. Fed
native it stays well under the 1024 full-frame budget, so the prefill lever is intact.

## Decisions

### 2026-06-27T00:00 — floor the ROI re-anchor crop (`ROI_MIN_CROP`)
- **Decision:** Add a `min_side` floor to `roi_window`; set `ROI_MIN_CROP = 384` px in
  the deploy re-anchor path. Eval default stays `min_side=0` (sweep unchanged).
- **Alternatives considered:**
  (a) **Re-enable `upscale=True` for small crops** — recovers super-resolution pixels
  but a small crop upscaled to a square `OUT_RES` carries *more* vision tokens than the
  letterboxed full frame, making re-anchor prefill slower than the acquire it replaces
  (the exact reason `upscale=False` was chosen). Doesn't fix the *context* loss anyway —
  upscaling an 86px crop still shows only 86px of scene.
  (b) **Divergence check → force full-frame re-acquire** when the re-anchor box lands
  near the crop edge or jumps. Robust, but more moving parts and needs an on-device
  threshold; deferred.
  (c) **Cap the per-step shrink rate** (box can't drop more than X%/anchor) — stateful,
  and still collapses slowly. Rejected.
- **Reasoning:** The floor is the minimal change that removes the unbounded feedback:
  it makes the crop size constant below the threshold, so the loop cannot run away. One
  kwarg, default-off for the eval, one constant in deploy. Latency lever preserved
  (floored crop fed native ≪ 1024 budget).
- **Tradeoff / cost accepted:** A receding target eventually sits inside a fixed 384px
  crop fed native → back to the Part II resolution ceiling for that target (the box is
  small in the crop), but it is no longer *worse* than full-frame and it no longer
  drifts onto the wrong object. The floor value is a hand-set heuristic tuned to the
  1080-wide demo frames, not swept.
- **Revisit when:** the floor alone still drifts on fast/erratic targets on-Orin → add
  alternative (b), the divergence-triggered full-frame re-acquire. Re-tune `384` if the
  deploy frame resolution changes.

## Open follow-ups
- On-Orin re-confirm: replay the same clip at the fast cadence with the floor in place
  and verify the lock holds (offline self-checks pass; on-device replay not yet run).
- Still inherited from `2026-06-25-roi-crop-anchor`: quantified on-device Q8_0 ROI
  IoU@0.25 (RefDrone via GGUF).
