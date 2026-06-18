# T0 — Cadence & dynamics harness (Part III, v3)

**Phase:** Part III · T0 (measure-before-design gate)
**Branch:** `v3/object-permanence`
**Pre-registered:** 2026-06-18
**Charter:** [`results/2026-06-18-part3-charter/README.md`](../2026-06-18-part3-charter/README.md)
**Plan:** Part III object-permanence plan (anchor = deployed Qwen2-VL-2B Q8_0; data = SITL clips).

## Why this phase exists

Part III is forced into a **two-tier architecture** by the hardware: a VLM forward
pass on the Orin is ~0.3–1.2 Hz, but a following loop needs ~20 Hz (a ~20–60× gap).
So a **fast per-frame tracker holds the lock at 20 Hz** while the **VLM runs sparsely
as the semantic anchor**. Before designing the identity-memory mechanism (T2) or the
loop (T3), T0 quantifies the **cadence-vs-dynamics budget**: *how far does "the white
van" move between two anchors, vs how long / how accurately can the fast tracker coast?*

This is the Part III analog of Part II's "measure backend fidelity before any GPU run":
**measure cadence-vs-dynamics before tuning the loop.** Everything T2/T3 chooses is
governed by the numbers produced here.

## Research questions

- **RQ-T0a — Anchor cadence.** What is the deployed Qwen2-VL-2B Q8_0 end-to-end
  anchor rate (Hz) on the Orin Nano (15 W locked), over the real deploy path
  (`grounding/deploy/serve.py` → `JetsonBackend`), at the Part-II resolutions
  (512 / 768 / 1024 long-edge)? Split prefill vs decode; record power/thermals.
- **RQ-T0b — Tracker cost.** Is the per-frame `bytetrack.py` (Kalman predict + IoU
  match + update) comfortably under the 50 ms (20 Hz) budget on the target host, and
  how much headroom remains for an added appearance / re-ID model (constraint #2)?
- **RQ-T0c — Target dynamics.** For plausible aerial-follow scenarios (altitude ×
  target ground speed), what is the target's **pixel velocity** (px/frame), its
  **scale-change rate**, and the **out-of-frame / occlusion durations**? Crossed with
  RQ-T0a this gives the budget: `anchor_period × px_velocity` vs the tracker's
  coasting horizon (`MAX_LOST_FRAMES = 30` frames = 1.5 s @ 20 Hz) and vs the bbox
  size (association sanity at re-anchor).
- **RQ-T0d — Re-ID feasibility (constraint #2 pre-check).** How large (px) is the
  target crop at follow altitude — i.e. how much appearance signal is even available
  for an appearance/re-ID memory? *Geometry half answered here; the embedding-
  separability half is deferred to T1 (needs rendered realistic pixels).*

## Controlled variables / methodology

- **Device + power mode:** Orin Nano 8 GB, `nvpmodel -m 0` (15 W) — the board has
  only 15 W (mode 0) and 7 W (mode 1); no 25 W MAXN_SUPER. `jetson_clocks` state
  recorded next to the numbers (NOPASSWD path).
- **Anchor model:** `phase3-refdrone-1024-q8_0.gguf` (1.65 GB) + `mmproj-phase3-refdrone-1024-f16.gguf`,
  deployed at `/home/jfdg/grounding/`. llama.cpp pinned commit `57fe1f0`, CUDA sm_87,
  `-ngl 99`, `n_ctx 4096`, greedy (`temperature=0`), `cache_prompt=False` — the same
  request path as the Part-II deploy gate (`_llama_server_chat`).
- **Anchor input:** a synthetic 640×480 RGB frame with vehicle-like rectangles on a
  textured ground (deterministic, fixed seed); caption `the white van`. The image is
  long-edge-resized to each `max_side` with the verbatim `_resize_keep_aspect`.
- **Cadence metric:** wall-clock end-to-end latency around `backend.generate()`
  (the rate the real loop sees, incl. tunnel + preprocessing), N reps after warm-up;
  report median + spread. Server-side `prompt_ms` / `predicted_ms` recorded when the
  response carries them, for the prefill/decode split.
- **Tracker metric:** wall-clock per `ByteTracker.update()` call over a realistic
  single-target stream at 20 Hz, N frames; report mean / median / p99 ms and implied
  max Hz. Host recorded (RTX 3090 workstation — the SITL/eval host, not the Orin).
- **Dynamics metric:** analytic, via `oracle_bbox.project()` stepped at 20 Hz over
  scripted seeded trajectories (altitude ∈ {10, 20, 30} m × target speed ∈ {1, 3, 5,
  10} m/s). Pixel velocity = center displacement/frame; scale-change rate from bbox
  area; out-of-frame from `project()→None`; occlusion duration = occluder_width /
  target_speed (analytic, pending the T1 occluder ray test).

## Gate (advance to T1 only when all are green AND documented same-turn)

1. **Cadence-vs-dynamics budget quantified** — a concrete table: anchor Hz (per
   resolution), tracker headroom, target px/frame & px-per-anchor-period, coasting
   horizon, out-of-frame/occlusion durations.
2. **Anchor spine confirmed by the numbers** — Qwen2-VL-2B Q8_0 cadence is within a
   workable range for sparse anchoring (Gemma 4 dropped; no other model in scope).
3. **Re-ID feasibility answered** — appearance vs motion-continuity, with the crop-size
   data backing the call (embedding half flagged for T1).
4. Findings written to this file + a `RESULTS.md` row + a `DECISIONS.md` entry in the
   **same turn**.

## Harness

`experiments/run_t0_cadence.py --phase {a,b,c,d,all}` — reuses `JetsonBackend`
(deploy path, T0a), `experiments/sitl/bytetrack.py` (T0b), and
`experiments/sitl/oracle_bbox.py` (T0c/d). Raw tegrastats logs land in
`results/raw/`.

## Results

**Run date:** 2026-06-18 · **Device:** Orin Nano 8 GB, `nvpmodel -m 0` (15 W) ·
`jetson_clocks` state: **not confirmed engaged** (the NOPASSWD `jetson_clocks --show`
returned only the machine banner, not the per-rail clock dump — so these cadence
numbers are a *default-15 W* operating point, conservative vs a clock-locked upper
bound). · Anchor model `phase3-refdrone-1024-q8_0.gguf` + `mmproj-…-f16.gguf`,
llama.cpp `57fe1f0`, `-ngl 99`, `n_ctx 4096`, greedy, `cache_prompt=False`.
T0a from the on-Orin post-parser-fix run (`results/raw/t0-results-20260618T113850.json`,
tegrastats `results/raw/t0a-tegrastats-20260618T113636.log`); T0b/c/d re-run locally
same-turn (RTX 3090 host) to supersede a stale 11:28 dynamics JSON that carried a
10 m px-velocity bug. Authoritative combined: `results/raw/t0-results-combined-authoritative.json`.

### RQ-T0a — Anchor cadence (on-Orin, end-to-end deploy path)

N=8 reps after 2 warm-ups; wall = end-to-end around `backend.generate()` (what the loop
sees); server `prompt_ms`/`predicted_ms` from the top-level `timings` block (`prompt_ms`
**includes** the CLIP image encode). Caption `the white van`, 24 output tokens, parse_rate
100% at every resolution.

| long-edge | wall median | **wall Hz** | prefill (prompt_ms) | decode (predicted_ms) | prompt toks | decode tok/s |
|---|---|---|---|---|---|---|
| **512** | 2265 ms | **0.44 Hz** | 1113 ms | 1106 ms | 316 | 21.7 |
| 768 | 3644 ms | 0.27 Hz | 2431 ms | 1110 ms | 631 | 21.6 |
| 1024 | 6416 ms | 0.16 Hz | 5111 ms | 1118 ms | 1063 | 21.5 |

**Decode is ~constant** (~1.1 s / 24 tok ≈ 21.6 tok/s, resolution-independent);
**prefill (image encode) dominates and scales steeply** with resolution
(1113 → 2431 → 5111 ms, ≈ linear in prompt-token count, i.e. in pixels). Prefill is
therefore the cadence lever.

**Power / thermals (whole T0a window):** idle 5.2 W, mean 10.9 W, peak 11.7 W; peak SoC
62.7 °C (no throttle); peak RAM 4849 MB; **no swap growth**. Comfortably inside the 8 GB
budget with the single-slot server config.

### RQ-T0b — Tracker cost at 20 Hz (constraint #2 headroom)

`ByteTracker.update()` over a 1180-frame single-target stream (RTX 3090 host):
median **0.051 ms**, p99 0.103 ms → implied max ~19.5 kHz. Against the 50 ms (20 Hz)
budget that is **~1000× headroom** (99.9 % of the budget free). Coast horizon today =
`MAX_LOST_FRAMES = 30` frames = **1.5 s** at 20 Hz.

### RQ-T0c — Target dynamics (analytic, nadir crossing, 20 Hz)

Pixel velocity = `focal·v/h`; in-frame time is the FOV-footprint dwell. Scale-change from
a stationary target under a 2 m/s descent.

| altitude | 1 m/s | 3 m/s | 5 m/s | 10 m/s | in-frame @1 m/s |
|---|---|---|---|---|---|
| 10 m | 55.4 px/s (2.77 px/fr) | 166 | 277 | 554 px/s (27.7 px/fr) | 12.7 s |
| 20 m | 27.7 px/s | 83 | 139 | 277 px/s | 21.4 s |
| 30 m | 18.5 px/s | 55 | 92 | 185 px/s | 30.0 s |

Scale-change under descent: **median 1.0 % / frame, max 2.0 % / frame** (gradual; not a
per-frame stressor on its own). Per-tracker-frame motion peaks at **27.7 px/frame**
(10 m × 10 m/s) — small vs the target box (110–222 px at 10 m), so **frame-to-frame
association at 20 Hz is never the bottleneck**; the budget tension is loss/occlusion, below.

### RQ-T0d — Re-ID crop geometry (constraint #2 pre-check, geometry half)

Target crop (4×2 m vehicle, nadir):

| altitude | crop (px) | area |
|---|---|---|
| 10 m | 110.9 × 221.7 | 24 576 px² |
| 20 m | 55.4 × 110.9 | 6 144 px² |
| 30 m | 37.0 × 73.9 | 2 731 px² |

At 10–20 m the crop (≥ 55 px short side) is comfortably above the ~32–64 px floor a small
appearance/re-ID head needs; at 30 m (37 px short side) it is marginal. **Embedding-
separability half deferred to T1** (needs rendered realistic pixels under the no-pure-
color constraint).

### The cadence-vs-dynamics budget (the headline)

Two distinct budgets fall out, and they have **opposite verdicts**:

1. **Inter-anchor tracking (comfortable).** Between two anchors the 20 Hz tracker sees
   every frame; per-frame motion ≤ 27.7 px is tiny vs the box, and the tracker costs
   0.05 ms. So the fast tracker *carries the lock* between anchors with ~1000× compute
   headroom — leaving ample room for an added appearance/re-ID model (constraint #2 is
   computationally free).
2. **Recovery-after-loss (tight — the binding tension).** The chosen anchor cadence at
   512 is **2.27 s/anchor**, but the coast horizon is only **1.5 s**. So
   `anchor_period (2.27 s) > coast_horizon (1.5 s)`: a *scheduled* re-anchor cannot
   recover a fully-lost target before the Kalman track is dropped. Consequences,
   pre-registering T2/T3 design:
   - **Re-acquisition must be event-triggered** (fire an anchor *on loss*), not only on
     a timer — the timer alone is too slow by ~0.8 s.
   - At low altitude + high speed the target is **in frame only ~1.2 s** (10 m × 10 m/s)
     and traverses the full 640 px frame in well under one anchor period — exactly the
     regime where Part-I Phase C (memoryless @ ~1 Hz) collapsed to ~0 % coverage. The
     fast tracker *must* hold identity through these gaps; the anchor cannot keep up
     alone. This quantifies *why* the two-tier architecture is mandatory, not a choice.
   - The 1.5 s coast horizon is a **tunable** (`MAX_LOST_FRAMES`) — T2 may extend it,
     but extending blind constant-velocity coasting trades recall for ID-switch risk,
     which is precisely the permanence problem T2 must solve with memory rather than a
     longer blind coast.

**Anchor resolution choice = 512 long-edge.** The SITL camera is **640×480**, and
`_resize_keep_aspect` is downscale-only, so 768/1024 give **no fidelity benefit** on
these frames (no upscaling) while costing 1.6×/2.8× the latency — pure loss. 512 is the
fastest *and* lossless-for-this-camera operating point: **0.44 Hz / 2.27 s period**.

## Gate verdict — ✅ PASS (all four conditions met, documented same-turn)

1. **Cadence-vs-dynamics budget quantified** — anchor 0.44/0.27/0.16 Hz (prefill-bound),
   tracker 0.05 ms (1000× headroom), target 18.5–554 px/s, coast horizon 1.5 s, and the
   key inequality `2.27 s anchor > 1.5 s coast` → event-triggered re-acquisition required.
2. **Anchor spine confirmed by the numbers** — Qwen2-VL-2B Q8_0 @ **512 long-edge**
   (0.44 Hz) is the operating point; 768/1024 dropped (no benefit at 640 px source);
   Gemma 4 stays dropped (0.34–0.49 Hz image-only, slower). No other model in scope.
3. **Re-ID feasibility answered** — geometry supports an appearance head at 10–20 m
   (≥ 55 px), marginal at 30 m; motion-continuity must backstop high altitude. Appearance
   *is* on the table for T2; embedding-separability check carried into T1.
4. **Written same-turn** — this file + a `RESULTS.md` row + a `DECISIONS.md` Part III
   entry, all this turn. ➡ **advance to T1.**
