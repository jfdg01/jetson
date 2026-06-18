# Part III — Persistent tracking / object permanence (charter)

**Status:** charter / theory only. No code, no GPU, no measured result yet.
**Branch:** `v3/object-permanence` (from `v2/principled-rebuild`).
**Date:** 2026-06-18.
**Scope of this doc:** state the paradigm shift, the binding constraints, the assets
we already have, the architecture family under consideration, the new metric suite,
an honest treatment of the Gemma 4 request, and a *proposed* gated phase plan
(T0–T4). This is the "general terms" pre-registration — specifics are filled in at
each phase's startup, exactly as Part II did.

---

## 1. The paradigm shift: from a frame to a stream

Part II answered **"where is the object the phrase refers to, in this one image?"**
and shipped it: Qwen2-VL-2B + LoRA, GGUF Q8_0 on the Orin, RefDrone well-posed val
**IoU@0.25 = 62.6%**, deployment-fidelity catastrophe eliminated. That is a
**single-frame referring-grounding** result.

Part III asks a fundamentally different question:

> **Given a referring phrase and a *video stream* from a moving drone, keep a lock on
> that one moving target across time — surviving occlusion, scale change, motion
> blur, brief exits from frame, and re-acquisition — well enough to close a
> following control loop.**

This is **persistent single-object tracking (SOT) under language conditioning**, with
**object permanence** as the headline difficulty: the identity of the target must
persist *through frames where the target is not cleanly visible*. A single-frame
detector, however good, does not solve this — it has no notion that the box in frame
*t+1* is the *same* object as the box in frame *t*, and no memory of the target while
it is occluded.

The metric changes accordingly. IoU@0.25 on one frame is **necessary but not
sufficient**. The Part III success criteria are temporal (see §6).

---

## 2. This is NOT from scratch — what Part I and Part II already give us

The user framed this as possibly "from complete scratch." It is not, and that is good
news: two prior arcs hand us most of the scaffolding, so Part III can spend its effort
on the genuinely unsolved piece (permanence) rather than rebuilding plumbing.

**From Part I (`experiments/sitl/`) — a working SITL follow stack already exists:**
- `bytetrack.py` — minimal ByteTrack: Kalman constant-velocity tracker (8-D state
  `[cx,cy,w,h,vx,vy,vw,vh]`) + two-round IoU matching, single dominant target,
  **coasts between sparse detections**. This is the per-frame motion model.
- `oracle_bbox.py` — pinhole projection of SITL world-state → pixel bbox: a
  perfect-perception upper bound, **and a free source of perfect labels** for any
  SITL-rendered training/eval clip.
- `cascade_pid.py` — outer-loop velocity setpoints from bbox centre + area (P-only,
  I/D stubbed).
- `offboard.py` — pymavlink ArduPilot SITL offboard state machine, 20 Hz
  `SET_POSITION_TARGET_LOCAL_NED`.
- Phase B/C precedent: **Phase B** (oracle bbox closed loop) PASSED; **Phase C**
  (zero-shot SmolVLM-500M @ ~1 Hz in the loop, async VLM thread + 20 Hz control/track
  thread with Kalman coasting) — **Branch-2 NEGATIVE**: zero-shot perception was not
  usable, and naive 1 Hz + dumb coasting could not hold a lock on a moving target
  (expected oracle-coverage near 0%). *The rate mismatch + memoryless coasting is the
  documented failure Part III must beat.*

**From Part II (`grounding/`) — a deployable language-grounding anchor:**
- Qwen2-VL-2B + LoRA, GGUF Q8_0, **62.6% IoU@0.25** on RefDrone, **runtime fidelity
  −2.7pp** (no Part-I-style collapse). This is a credible *semantic anchor* for
  acquisition and re-acquisition.
- The **shared-contract discipline** (`grounding/contract.py`: GROUNDING_PROMPT
  verbatim, `parse_bbox`, `iou`, `center_std`, pytest-locked) — Part III extends the
  contract with *temporal* primitives rather than starting a new one.
- The managed toolchain (uv + pinned lock, Makefile, per-run manifests, pinned
  llama.cpp) carries over unchanged.

So Part III's job is the **bridge and the memory**, not the plumbing.

---

## 3. The forced architecture: sparse VLM anchor + fast per-frame tracker

A VLM forward pass on the Orin is **slow** — measured ~0.3–1.2 Hz depending on model
and resolution. A drone following loop needs **~20 Hz** identity maintenance. These
two rates are ~20–60× apart, and that gap is not closable by making the VLM faster; it
is structural. The only architecture that survives the hardware is:

```
  ┌─────────────────────────────────────────────────────────────┐
  │  20 Hz control/track thread                                   │
  │   per-frame tracker (motion + appearance) holds the lock,     │
  │   feeds bbox → cascade_pid → offboard setpoints               │
  └───────────────▲──────────────────────────┬──────────────────┘
                  │ correction / (re)seed      │ track state
  ┌───────────────┴──────────────────────────▼──────────────────┐
  │  ~0.3–1.2 Hz async VLM anchor thread                          │
  │   language-conditioned grounding (Part-II model or Gemma 4)   │
  │   = acquisition + periodic re-anchor + re-acquisition         │
  └──────────────────────────────────────────────────────────────┘
```

The **VLM is the semantic conscience** (it knows *which* object the phrase means); the
**fast tracker is the working memory** (it knows *where that object went* between
anchors). Part I built exactly this skeleton and showed the naive version fails — so
Part III's contribution is making the fast tracker *carry identity through absence*,
and making the VLM re-anchor *correctly* rather than re-locking the wrong object.

---

## 4. The two binding constraints (the Part III analogs of Part II's two)

Part II was organised around two binding constraints (deployment-fidelity gap;
resolution ceiling). Part III has its own two, and the whole design pivots on them:

### Constraint #1 — detection-cadence vs target-dynamics budget *(the new dominant variable)*
The analog of Part II's deployment-fidelity gap. How far a moving target travels (in
pixels, and in IoU-decay) between two VLM anchors sets whether the fast tracker can
bridge the gap at all. This is a **budget**: `anchor_period × target_pixel_velocity`
vs the tracker's coasting horizon. It is set by (a) VLM Hz on the Orin, (b) target
dynamics, (c) tracker quality. **It must be measured before designing the loop** —
the Part-I "fidelity-before-GPU" discipline becomes **"measure cadence-vs-dynamics
before tuning the loop."**

### Constraint #2 — identity through absence / object permanence *(the new accuracy frontier)*
The analog of Part II's resolution ceiling. The current `bytetrack.py` is a
**constant-velocity Kalman filter with NO appearance / re-ID memory**. When the target
is occluded or leaves frame and reappears, the tracker has nothing to recognise it
by — re-acquisition can re-lock the **wrong object** (the classic ID-switch). This is
the genuinely unsolved piece and the one the thesis chapter is *about*. Candidate
remedies (to be chosen by data, not opinion): lightweight appearance embedding /
re-ID head, motion-prior gating, VLM re-verification of the re-acquired box, or a
short-horizon memory of target appearance.

---

## 5. The "fidelity-before-GPU" analog: measure before you train

Part II's signature move was de-risking cheaply before spending GPU. Part III's
equivalent **pre-training measurement battery** (no training, mostly no GPU):

1. **On-Orin cadence sweep** — VLM Hz vs resolution / token-budget for each anchor
   candidate (Part-II Qwen2-VL-2B Q8_0; Gemma 4 E2B/E4B with the token-budget lever).
2. **Per-frame tracker cost** — can the chosen tracker (+ any appearance head) actually
   run at 20 Hz on the Orin alongside the control loop?
3. **Target-dynamics & occlusion statistics** — on whatever video data we adopt:
   distribution of target pixel-velocity, occlusion durations, out-of-frame events,
   scale change. This *defines* the cadence budget (#1) and the permanence demand (#2).

Only after these three are measured do we design the loop and (if needed) train.

---

## 6. New metric suite (successors to single-frame IoU@0.25)

Single-frame IoU is retained as a *per-anchor sanity check* but is no longer the
headline. Part III headline metrics (to be locked into the extended contract):

- **Track continuity / SOT success & precision plots** — success (IoU-overlap) vs
  threshold, precision (centre error) vs threshold, over the whole clip.
- **ID switches / identity purity** — how often the lock jumps to a different object;
  the direct measure of constraint #2.
- **Re-acquisition time** — frames/seconds from target reappearance to a correct
  re-lock after occlusion/out-of-frame.
- **Oracle-coverage** (carried from Phase C) — fraction of frames the tracked box
  matches the SITL oracle GT above threshold; the closed-loop ground truth.
- **Closed-loop following error** — pixel/world offset of the drone's framing vs the
  oracle, and **track-loss events** (LOST_TIMEOUT exceedances).

---

## 7. The Gemma 4 question — honest treatment

The user asked specifically to try **Gemma 4** ("a very good fit"). Verified facts
(web search, 2026-06-18) and the measured caveat:

**What's real and genuinely appealing:**
- Gemma 4 exists, Apache 2.0, multimodal, with **variable aspect-ratio / resolution
  preservation** (directly attacks an aerial tiny-object weakness) and a
  **configurable token budget per image (70–1120)** — an explicit latency lever.
- 256K context. Sizes E2B, E4B, 12B, 26B A4B, 31B.

**The constraints that temper "very good fit":**
- **Native video (1 fps / 60 s) is 26B / 31B ONLY.** Those do **not** fit the 8 GB
  Orin. The E2B/E4B that *do* fit are **image-only** — so on our hardware Gemma 4 is
  still a per-frame anchor, not a video model. No free object permanence from it.
- **Measured caveat (2026-06-14 Orin benchmark):** Gemma 4 E2B/E4B already ran at
  **0.49 Hz / 0.34 Hz** — the **slowest** VLM candidates on the device, *slower* than
  SmolVLM-500M (1.2 Hz). The token-budget lever that could speed them up is **untested**.

**Honest position for the charter:** Gemma 4 E2B/E4B are a **legitimate anchor
candidate to measure in T0's cadence sweep**, where the token-budget lever is finally
exercised — but they enter as the *slow* incumbent-to-beat, not a foregone choice. The
spine is picked **by the numbers** (Part II discipline), comparing Gemma 4 (with token
budget swept) against the already-deployed Qwen2-VL-2B Q8_0 and, if relevant, a
detector+re-ID baseline. We do not bank "good fit" as a result before it is measured.

---

## 8. Proposed gated phases (T0–T4) — *proposal, open to debate*

Same discipline as Part II: each phase gated; do not start the next until the prior
gate is green AND documented in `results/` + `RESULTS.md` + `DECISIONS.md` in the same
turn. Names are T-prefixed (tracking) to keep them distinct from Part II's 0–4.

- **T0 — cadence & dynamics harness (measure-before-design).** The §5 battery:
  on-Orin VLM Hz sweep (incl. Gemma 4 token-budget), per-frame tracker cost at 20 Hz,
  target-dynamics/occlusion stats on the adopted data. **Gate:** the cadence-vs-
  dynamics budget (#1) is quantified and the anchor spine is picked by the numbers.
- **T1 — data & temporal contract.** Choose data (real aerial referring-video vs
  SITL-generated clips with free oracle labels) and extend `contract.py` with the
  temporal metric primitives (§6), pytest-locked. **Gate:** a scored eval clip set
  exists with GT and the temporal metrics are reproducible.
- **T2 — permanence mechanism (constraint #2).** Add identity-through-absence to the
  fast tracker: appearance/re-ID memory and/or VLM re-verification on re-acquisition.
  **Gate:** ID-switch rate and re-acquisition time beat the memoryless ByteTrack
  baseline on the T1 eval set.
- **T3 — closed-loop integration.** Wire anchor + permanent tracker + cascade_pid +
  offboard in SITL; beat the Phase-C negative (oracle-coverage well above ~0% on a
  *moving* target). **Gate:** sustained following with bounded track-loss over a clip.
- **T4 — on-Orin deployment.** Run the full loop on the Orin within the T0 cadence
  budget; characterise the sim-to-device gap (the Part III analog of the Part II
  deployment gate). **Gate:** deployed loop holds the lock within the budgeted
  fidelity of the SITL result.

---

## 9. Open forks for the user (to debate before T0)

1. **Anchor model.** (a) Reuse the deployed **Qwen2-VL-2B Q8_0** (known 62.6%, 1.2 Hz,
   −2.7pp fidelity) as the anchor and spend Part III on permanence; (b) **Gemma 4
   E2B/E4B** with the token-budget lever (variable-resolution upside vs measured 0.34–
   0.49 Hz, untested speed lever); (c) a **detector + re-ID** baseline (fast, but loses
   open-vocabulary language conditioning). *My lean: enter T0 with (a) as the
   incumbent and measure (b) against it; keep (c) as a non-VLM baseline.*
2. **Data.** Real aerial **referring-video** datasets (realistic, but labelling +
   licensing cost, and may lack the exact "follow this phrase" framing) vs
   **SITL-generated clips** (free perfect oracle labels via `oracle_bbox.py`, full
   control of occlusion/dynamics, but sim-to-real gap). *My lean: SITL-first for the
   permanence mechanism (free GT, controllable difficulty), with a small real-video
   eval set as the reality check.*
3. **Permanence mechanism family** (settled in T2, but flag now): lightweight
   appearance embedding/re-ID vs VLM re-verification vs both.

---

## 10. What stays binding from before

- **Shared contract discipline** — extend `contract.py`, never fork; GROUNDING_PROMPT
  stays verbatim; pytest gate.
- **Document every result in `results/` + `RESULTS.md` + `DECISIONS.md` the same turn.**
- **Measure before you spend** — T0 before any training (fidelity-before-GPU analog).
- **Hardware truth** — Orin Nano 8 GB, power modes only 0 = 15 W (default/max) and
  1 = 7 W (no 25 W on this board); training on the RTX 3090 24 GB; `.venv-ft` for GPU
  work, never pip-install globally; local commits only unless a push is explicitly
  authorized.
