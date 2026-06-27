# TODO — whole-system interactive demo (Part III)

**Goal:** one interactive browser tool that walks the *entire* Part III system in one
place — language anchor → fast tracker → object permanence → closed-loop following —
with the real measured numbers, for the professor.

## ⚠️ SUPERSEDED (2026-06-25T13:00) — see DECISIONS.md
The static 4-tab page below was **retired** the same day. The demo is now a **2-tab live
`grounding/deploy/gui.py`**: tab 1 = manual single-image VLM test (kept), tab 2 = **Level-2
tracking on 3 short real videos** (`video.py --track` → mp4). Permanence/closed-loop panels
dropped from the *viewer* (still fully in `results/`). The original plan is kept below for the record.

## ✅ BUILT — `results/2026-06-25-system-demo/` (2026-06-25)
The unified page is **done as a static 4-tab HTML** — open
`results/2026-06-25-system-demo/index.html`, no server. The Open-questions were resolved:
scope = single 4-tab page; closed-loop stage 4 = **included now**; run target = **static
GIF only, no live Orin** ("static so I can simply show it"). So tab 2 embeds the
pre-rendered real-Orin anchor GIF instead of a live grounding GUI. New code: `on_frame`
hook in `run_t3.run_loop` + `experiments/sitl/closedloop_viz.py` (stage-4 viz, self-check
PASS 49.2%→97.6%). See that folder's `README.md`. Sections below are the original plan,
kept for the record.

Done so far: Demo 1 (grounding GUI), Demo 2 (permanence GIF), **Level-1 real-video
test verified**, and **the unified static page (this TODO's goal)**.

## The honest seam (design around this, do NOT fake it)
There is **no single continuous end-to-end video**, because the two tiers live in
different data worlds:
- The **real VLM anchor** only runs on **real aerial stills** (RefDrone), on the Orin.
- **Tracking / permanence / closed-loop** run on **synthetic kinematic clips** (labels
  only, no rendered frames — T1 decision). Their "VLM anchor" is **oracle-simulated**
  (as in T3/T4).

So the demo **narrates the pipeline as three honest stages**, each with its own real
data + real numbers, and explains the bridge between them. It must not render a frame
where a live-VLM box drives the SITL clip — that scene never existed.

## Build — single page, three sections, reuse what exists
One tool. Laziest path = **extend `grounding/deploy/gui.py` into a 3-tab page**, not a
new app. Most pieces already exist.

1. **Architecture + cadence (the "why two tiers")** — static panel: two-tier diagram +
   the real T0/T4 numbers. Anchor 0.44 Hz / 2.26 s period; tracker 0.14 ms / 20 Hz /
   ~350× headroom; coast 1.5 s < anchor period → **event-triggered re-acq**. Pull
   verbatim from `results/2026-06-24-t4-deployment/` + `results/2026-06-18-t0-cadence/`.
   *New: a bit of HTML/SVG. No model code.*

2. **Anchor tier — live on Orin** — the existing grounding GUI with presets
   (`gui.py` + `PRESETS`). Language → box, live on the deployed Qwen2-VL-2B Q8_0.
   *Already built; just becomes tab 2.*

3. **Tracking tier — permanence (sim)** — embed the `permanence_viz` animation
   (memoryless vs re-ID through the crossing/occlusion). Pre-generate the GIF; serve it.
   Headline overlaid: purity 0.72 / 1 ID-switch → 1.00 / 0.
   *Already built; embed `results/2026-06-24-t2-permanence/permanence.gif`.*

## Optional 4th stage — closed-loop following (decide before building)
A panel showing the cascade-PID loop holding a *moving* lock (the T3 result that beats
the Phase-C ~0%). **Not free:** `run_t3.py` only emits summary coverage %, no per-frame
trace. Would need a `run_t3` replay that dumps per-frame {lock box, true-target box,
following error} to frames — same monkeypatch/replay trick `permanence_viz` used. ~half
a day. Skip for v1 unless the professor specifically wants the control loop shown.

## Open — confirm before building
1. **Scope:** 3-section single page (recommended) — or just bolt the permanence panel
   onto the existing grounding GUI and keep them lighter?
2. **Closed-loop panel (stage 4):** include now, or defer (permanence already carries the
   object-permanence story)?
3. **Run target:** dev-box browser driving the Orin for the live anchor (as today) — OK?
   The Orin can't host the page + render the sim itself without PIL installed there.

## Testing on a real sample video — three levels
The whole stack runs on either real *stills* (VLM) or synthetic *kinematic clips*
(tracker/permanence). To exercise it on a **real video**, note the crux: the fast
tracker (`bytetrack.py`) is **detection-fed**, and in the stack those detections come
from `oracle_bbox` (perfect SITL labels). Real video has no oracle → the 20 Hz tier has
nothing to eat unless given a real per-frame mechanism. Hence three levels:

- **Level 1 — anchor tier on real video — DONE + VERIFIED on real footage.**
  `grounding/deploy/video.py`. Samples a real clip at the VLM's true on-Orin cadence
  (~1 anchor / 2.26 s) and *holds the box stale* between anchors, so the cadence drift is
  visible (green = fresh VLM box, orange = held +Xs). Fully real, reuses
  `JetsonBackend.generate` + `parse_bbox`. Accepts a video file **or a directory of frames**
  (`_read_frames`) — VisDrone-VID is natively jpg sequences.
  **Verified run (2026-06-25):** seq `uav0000182_00000_v` (150 frames on disk under
  `data/VisDrone2019-VID/.../images/val/`), caption "the black SUV in the middle of the
  road" → 3 real Orin VLM passes, box tracked the SUV down-frame. GIF coherent.
  ```bash
  source .venv-ft/bin/activate
  python -m grounding.deploy.video \
    --video data/VisDrone2019-VID/VisDrone2019-VID/images/val/uav0000182_00000_v \
    --caption "the black SUV in the middle of the road"      # → /tmp/anchor-on-video.gif
  python -m grounding.deploy.video --selfcheck   # offline schedule-math check
  ```
  *Dataset note:* official VisDrone Google-Drive mirrors are throttled; fetched one seq via
  `remotezip` HTTP range-requests from the HuggingFace re-host `lanlanlan23/VisDrone2019`
  (`VisDrone2019-VID.zip`). Frames are gitignored-scale (not committed).
- **Level 2 — two-tier on real video (FUTURE, the real prize).** VLM box every ~2.26 s
  *seeds a fast visual tracker* that holds the lock between anchors at frame rate — the
  actual architecture on real footage. Frictions: (a) installed opencv is the **headless**
  build → only `TrackerMIL` present; `CSRT`/`KCF` need `uv add opencv-contrib-python`;
  (b) genuinely new integration (~half a day) and it surfaces the honest T2/T3 frontier —
  we have no non-oracle per-frame tracker yet. This is where a real per-frame detector or
  template tracker would slot in.
- **Level 3 — closed-loop following on real video: IMPOSSIBLE.** A pre-recorded clip
  can't be *followed* — the camera trajectory is baked in, no actuation to close the loop
  on. Stays sim-only (or a real drone). Physical wall, not a code gap.

## On-Orin constraints (unchanged)
No camera, no on-device SITL, kinematic clips only. Stage 2 is the genuine on-Orin VLM;
stages 1/3/4 are real numbers + deterministic sim artifacts.
