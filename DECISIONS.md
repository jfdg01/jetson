# DECISIONS — project-wide decision log

Cross-cutting decisions and their rationale, most recent first. Campaign-specific
decisions live in the relevant `results/*.md`. Format defined in `CLAUDE.md`.

The log is split into three parts. **Part III — Persistent tracking / object
permanence (v3)** holds decisions from the `v3/object-permanence` branch onward
(newest first). **Part II — Principled rebuild (v2)** holds the single-frame grounding
rebuild decisions (`v2/principled-rebuild`). **Part I — Exploratory** below is the
original notebook (device benchmark campaigns + grounding Stages 1–4), left untouched
as the historical record (paths in Part I entries refer to the tree as it was then;
legacy scripts now live under `experiments/legacy/`).

---

# Part III — Persistent tracking / object permanence (v3)

<!-- v3 decisions are appended here, most recent first. -->

### 2026-06-26T22:30 — terse output format (4 space-separated ints) replaces JSON in the contract

- **Decision:** Change the grounding contract's output format from `{"bbox": [x1,y1,x2,y2]}`
  to **four space-separated integers** (`x1 y1 x2 y2`) and **re-LoRA** the anchor on it
  (`runs/v2/phase3-terse-1024/`). Deliberately breaks the byte-identical `GROUNDING_PROMPT`
  contract test (`tests/test_contract.py`), re-pinned to the new string. `parse_bbox` now
  requires *exactly four* integers.
- **Alternatives considered:** (a) keep JSON (zero decode saving — the scaffolding is the
  cost); (b) prompt-only change without retraining (saves nothing — the deployed weights emit
  learned JSON byte-for-byte); (c) a delimited terse form like `[123,456,234,567]` (keeps an
  anchor for the parser but re-adds 4–6 scaffolding tokens, defeating the point).
- **Reasoning:** the on-Orin anchor decode is ~24 tok ≈ 1.1s of the 2.27s anchor, almost all
  JSON scaffolding. Measured: JSON 23 tok → terse 15 tok (**−8 tok, −35%**, the exact 8
  scaffolding tokens). Re-LoRA cost **+1.0 pp** IoU@0.25 (60.5% vs 59.5% HF — noise, accuracy
  is free) at the price of **−9 pp parse_rate** (91% vs 100%: no brackets to anchor on, model
  needs all 3 epochs to learn the format). Net: real token saving, no accuracy loss.
- **Tradeoff / cost accepted:** −9pp parse_rate (mitigated: exactly-4 guard makes a
  dropped/extra coord an honest parse-fail, not silent corruption). The contract test is no
  longer a regression anchor to the *original* deployed JSON weights — but those are superseded
  by this re-train. On-Orin Q8_0 decode wall-time not yet measured (token premise is local-only).
- **Revisit when:** the on-Orin export + deploy measures decode wall-time — if it doesn't drop
  materially (≈−0.37s expected), or if 91% parse hurts a downstream consumer, revert to JSON
  (the saving would not justify the parse cost). See `results/2026-06-25-terse-output-retrain/`.

### 2026-06-25T15:00 — install CSRT (opencv-contrib-python) + add a live-tracking demo tab

- **Decision:** Replace `opencv-python` with the same-version **`opencv-contrib-python==4.13.0.92`**
  in `.venv-ft` (a strict superset that ships `TrackerCSRT_create`), and add a third
  GUI tab **"Live tracking (your video)"**: upload a clip + type a phrase → the real
  two-tier pipeline runs on the Orin (`video.py render --track`) and returns the
  annotated GIF in the browser. `video.py:_make_tracker()` now auto-selects CSRT.
- **Alternatives considered:** (a) stay on MIL (the 2026-06-25T12:30 deferral — no new
  dep, but a visibly weaker tracker); (b) install both opencv-python + contrib (they
  share the `cv2/` dir → file clash, unsupported); (c) opencv-contrib-python-headless
  (no codecs/GUI — but we want mp4 decode for uploads).
- **Reasoning:** the user asked for it explicitly now that Level-2 is the headline.
  contrib is the upstream-recommended single package; same version → satisfies
  `ultralytics`'s `opencv-python>=4.6.0` at the version level, and `cv2` imports
  identically, so nothing at runtime breaks (verified: torch+CUDA intact, mp4 decode
  OK, real end-to-end /track run on the Orin produced a coherent CSRT-tracked GIF).
- **Tradeoff / cost accepted:** `pip check` will note `ultralytics requires
  opencv-python` (different dist name) — cosmetic only; `cv2` is fully present. The
  pinned dep is now explicit in `requirements-ft.txt` + the lock, overriding the
  transitive `opencv-python`. The live tab is single-user (shares the one `_BACKEND`,
  no request lock) and slow (~15-30 s/clip, real ssh VLM passes) — fine for a demo.
- **Revisit when:** a non-contrib pin is forced (e.g. ultralytics hard-pins a conflicting
  opencv build), or the demo needs concurrent users (then a backend pool / queue).

### 2026-06-25T13:00 — demo rebuilt around Level-2; old static 4-tab page retired

- **Decision:** Replace the static 4-tab whole-system page
  (`results/2026-06-25-system-demo/` — architecture / anchor / permanence / closed-loop)
  with a **2-tab live `grounding/deploy/gui.py`**: **(1) manual grounding** (the existing
  preset/upload → live-Orin VLM box, kept verbatim — "test the VLM in isolation") and
  **(2) Level-2 tracking on video** (the new headline: VLM anchors + MIL coast on real
  footage, shown as **3 short ~5 s clips**). The old static page and its three GIFs
  (`anchor-on-video.gif` 40 MB, `permanence.gif`, `closedloop.gif`) are deleted.
- **Alternatives considered:** (a) keep the static 4-tab page and just swap tab 2's GIF;
  (b) two separate artifacts (live gui + a static video page); (c) commit the heavy GIFs.
- **Reasoning:** the user's new ask is narrower — keep only the **manual single-image VLM
  test** and grow **Level 2** to several videos. The manual test is *inherently live* (it
  calls the Orin), so the laziest coherent home for both is the already-live `gui.py`: tab 1
  is the live test unchanged, tab 2 just serves pre-rendered clips (works even with the Orin
  down). The permanence / closed-loop / architecture panels are dropped from the demo per the
  user ("for now I only need …") — they remain fully documented in `results/` + `RESULTS.md`,
  so nothing is lost from the record, only from this one viewer. **Clips served as mp4**
  (`<video loop muted>`), not GIF: the Level-2 GIF is ~40 MB vs ~0.6 MB mp4 (ffmpeg
  one-liner), so the page is light and the mp4s are small enough to keep.
- **Video source:** 2 more **VisDrone-VID val** sequences (we already have
  `uav0000182_00000_v`), fetched via **`uv run --with remotezip`** HTTP range-requests from
  the HF re-host `lanlanlan23/VisDrone2019` — an **ephemeral env**, so the painful pinned
  `.venv-ft` lockfile is **not** touched (rendering still uses `.venv-ft`). ~150 frames/seq
  ≈ 5 s @ 30 fps, matching the verified clip length.
- **Tradeoff / cost accepted:** the demo no longer shows permanence/closed-loop in the same
  window (deliberate, reversible — those tabs/GIFs are recoverable from git + still in
  `results/`). Tab 1 needs `ssh jetson` reachable to run live; tab 2 does not.
- **Revisit when:** the professor wants the permanence / closed-loop stories back in one
  page → re-add them as tabs (the GIFs are in git history); or Level 2 graduates from demo
  to a measured number → it needs its own `results/` campaign, not just a viewer.

### 2026-06-25T12:30 — Level-2 real-video tracker = MIL (built-in), not CSRT yet

- **Decision:** The two-tier "VLM anchor seeds a fast tracker that coasts between anchors"
  on real video (Level 2, `grounding/deploy/video.py --track`) uses **`cv2.TrackerMIL`**,
  the only tracker in the installed **headless OpenCV 4.13** build. We are **NOT** adding
  `opencv-contrib-python` (CSRT/KCF) at this point. `_make_tracker()` auto-selects CSRT if
  it is ever present, so the upgrade is a no-code swap.
- **Alternatives considered:** `uv add opencv-contrib-python` now to get **CSRT** (clearly
  the stronger tracker for fast aerial/scale-changing motion) or **KCF** (faster, weaker).
- **Reasoning:** ladder discipline — use what's installed before paying for a dependency.
  MIL ships with the current build (zero install), and the first job is just to see whether
  the *architecture* (anchor→coast→re-anchor) reads correctly on real footage; tracker
  quality is a second-order tuning knob. Adding contrib touches the **pinned `.venv-ft`
  lockfile**, and `opencv-contrib-python` vs the existing headless `opencv-python-headless`
  both vendor `cv2` → a real conflict risk in an env that is painful to rebuild. Not worth
  that until MIL is shown to be the bottleneck.
- **Tradeoff / cost accepted:** MIL drifts more under fast motion / scale change, so the
  between-anchor coast may visibly wander on hard clips. Acceptable: anchors re-ground every
  ~2.26 s, capping drift, and the demo's point is the cadence/coast structure, not SOTA
  tracking. First real run (seq `uav0000182_00000_v`, "the black SUV…", 3 Orin anchors)
  produced a coherent GIF.
- **Revisit when:** MIL visibly loses the lock on a clip we want to show → `uv add
  opencv-contrib-python`, verify `cv2` still imports + the contract tests pass, then
  `_make_tracker()` picks CSRT automatically. Also revisit if Level 2 ever graduates from
  demo to a measured T2/T3 number (then tracker choice needs justifying by the numbers).

### 2026-06-25T00:00 — whole-system demo ships as a static page, not a live tool

- **Decision:** The professor-facing whole-system demo is a **static, self-contained
  HTML folder** (`results/2026-06-25-system-demo/index.html` + 3 GIFs), opened from
  `file://` — no server, no live Orin inference in the page. Stage-4 closed-loop is
  **included** via a new `experiments/sitl/closedloop_viz.py` that drives the existing
  T3 harness through a one-line `on_frame` hook added to `run_t3.run_loop` (no new
  control/perception code).
- **Alternatives considered:** (a) extend `grounding/deploy/gui.py` into a live 4-tab
  page driving the Orin (the TODO's original "laziest path"); (b) defer stage 4.
- **Reasoning:** the user's explicit ask — *"static so I can simply show it"*. A live
  page needs `ssh jetson` reachable, the llama-server up, and PIL on a host; a static
  folder travels to any laptop/projector and never fails mid-talk. Tab 2 therefore
  embeds the **pre-rendered real-Orin anchor GIF** (3 genuine VLM passes) rather than a
  live grounding call — the numbers are still 100 % real, just frozen. The `on_frame`
  hook reuses the verbatim closed-loop, so the stage-4 viz cannot drift from the T3
  result (self-check asserts re-ID coverage > baseline and ≥ 80 %).
- **Tradeoff / cost accepted:** no live "type a caption, watch the box" interactivity in
  the page (the live GUI still exists separately for that). The anchor GIF is ~41 MB, so
  GIFs are referenced by relative path, not base64-embedded — the folder is the unit you
  copy. The demo deliberately shows **three honest stages with a stated seam**, never a
  single faked end-to-end video (the two tiers live in different data worlds — T1).
- **Revisit when:** the committee wants live "type-a-phrase" grounding in the room →
  boot `grounding/deploy/gui.py` against the Orin as a separate live tab.

### 2026-06-24T18:40 — T4 gate PASS: on-Orin deployment within the T0 cadence budget

- **Decision:** Close Part III with an **on-Orin timing/cadence reconciliation** rather
  than a physical hardware-in-the-loop flight. `experiments/run_t4.py` times the fast
  tier on the device CPU (T4a), fires the **real deployed Qwen2-VL-2B Q8_0 grounding
  model** as the in-loop anchor through the verbatim contract path (T4b), and reconciles
  both against the 50 ms / 1.5 s-coast T0 budget (T4c). Reuses the T0 harness wholesale
  (imports `run_t0_cadence`); one file pushed to the device.
- **Result:** PASS. Fast tier 0.143 ms median / 0.291 ms p99 on aarch64 @ 15 W — 2.8×
  the dev box but **99.7 % of the 20 Hz budget free** (~350× headroom). Real VLM anchor
  2264 ms / **0.44 Hz**, **−0.03 % drift vs T0a**, **100 % bbox parse** (deployed model
  intact). Anchor period 2.26 s > 1.5 s coast → event-triggered re-acq required, the T0
  verdict confirmed on the metal. `deploys_within_t0_budget = True`.
- **Alternatives considered:** (a) **Full HW-in-the-loop flight on the Orin** — rejected:
  no physical airframe/camera; the deployable claim is whether the two-tier *timing* fits
  the device, measured directly here. (b) **Trust T0's mixed-host budget** — rejected:
  T0b was the dev box; the charter says *on-Orin within the T0 budget*, so the tracker
  tier had to be measured on aarch64 to honestly close the gate. (c) **Re-run the T3 SITL
  loop pointed at the on-device VLM** — rejected as premature: per-frame VLM-in-the-loop
  integration is separate engineering; the gate is the cadence budget, decided by the two
  tier timings + the event-triggered re-acq condition, all measured here.
- **Tradeoff / cost accepted:** T4 proves the loop *fits* the device timing budget through
  the actual deployed artifacts, not that a physical drone flies it. The closed-loop
  *behaviour* is the T3 SITL PASS; T4 is the honest deployment-feasibility characterisation.
- **Revisit when:** a physical airframe + camera is available for a true HW-in-the-loop
  flight, or a real appearance encoder replaces the scalar T2 `_observe` (adds per-frame
  cost to re-measure against this headroom). **This closes Part III (T0–T4 all PASS).**

### 2026-06-24T12:00 — T3 gate PASS: closed-loop A/B (kinematic primary + live SITL confirm)

- **Decision:** Deliver T3 as a **two-policy closed-loop A/B** (memoryless vs the T2 re-ID
  gate) on one shared harness (`experiments/run_t3.py`), with a **deterministic kinematic
  dry-run as the primary comparison** and a **live ArduCopter SITL run as the sim-to-flight
  confirmation**. The lock drives cascade-PID → body velocity → copter motion → re-projection,
  so a wrong lock steers the camera off the true target (the Phase-C compounding failure),
  now an *identity* test via a same-class distractor that crosses, briefly occludes the
  target (t = 29–31 s), then veers away. Build a focused new runner reusing oracle_bbox +
  bytetrack + cascade_pid + offboard + the T2 `_observe`, not an extension of the 1239-line
  `run_phase_c.py`.
- **Result:** Phase-C ≈ 0 % on a moving target → re-ID **97.6 %** (kinematic) / **71.5 %**
  (live SITL) true-target coverage; memoryless baseline 49.2 % / 53.7 %. The baseline-vs-reID
  gap localises the win to the **permanence mechanism** (the appearance gate holds identity
  through the occlusion/crossing), not merely the faster loop. Live margin < kinematic because
  real PID-lag + inertia lower both policies' absolute coverage; direction + mechanism hold,
  both ≫ 0 %. Full writeup: `results/2026-06-24-t3-closed-loop/`.
- **Alternatives considered:** (a) extend `run_phase_c.py` — rejected (Gazebo/VLM/dual-branch
  baggage; focused runner is the shorter diff); (b) live-SITL only — rejected (flight noise
  blurs the mechanism; kinematic A/B is the clean deterministic, self-check-able comparison);
  (c) kinematic only — rejected (charter says *in SITL*; the live run is the honest reality
  check); (d) both policies in one shared flight — rejected (first policy leaves the copter
  chased-off → reid starts degraded: 2.8 % shared vs 71.5 % on its own fresh takeoff). One
  fresh flight per policy is the apples-to-apples that matches the kinematic A/B.
- **Tradeoff:** kinematic abstracts away flight dynamics; live SITL is noisier + slower (two
  boots + two 60 s flights). Accepted — together they bracket the result (mechanism isolation
  + real-flight confirmation). Live-SITL reproducibility gotchas captured in the writeup
  (GUIDED before takeoff; `--uartA=tcp:5760` or the lockstep clock never advances; drain
  `LOCAL_POSITION_NED` to freshest; hard-reap arducopter between flights; run foreground).
- **Revisit when:** T4 (on-Orin within the T0 cadence budget) and/or a real appearance
  encoder replaces the scalar `_observe` — both re-measure this loop with the real stack.

### 2026-06-24T00:00 — T2 gate PASS: appearance-memory re-ID with an explicit SNR/range knob

- **Decision:** Solve object permanence (constraint #2) with a stored **appearance
  descriptor** matched at re-acquisition behind a **refuse-to-lock gate**
  (`experiments/sitl/reid_policy.py`), and model appearance as a scalar whose observation
  noise scales with crop size — one `snr` knob that *is* the T0d separability-vs-range
  frontier. Reuse the T1 tracker and §6 metric assembly unchanged (factored
  `assemble_scores` out of `clip_recorder.score_clip`).
- **Result:** above the knee (snr ≳ 1) the gate **beats the memoryless baseline**:
  identity purity 0.725→1.000, ID switches 1→0, failed re-acq 1→0, coverage 0.575→0.695
  (= the 139/200 visible-frame ceiling), following error 67.7→0.13 px. Below the knee it
  degrades to the baseline (noise ≥ van/decoy gap). Control clip unchanged (no regression).
- **Alternatives considered:** (a) **VLM re-verification** of each re-acq crop — deferred
  to T3/T4: it is the other permanence lever but needs rendered crops + an on-Orin VLM call
  inside the cadence budget; the appearance gate is the cheap renderer-free slice that
  already clears the gate. (b) **Render RGB now + real embedding** — rejected (same reason
  T1 deferred rendering): heavy non-deterministic dependency before it is load-bearing; the
  scalar+noise stand-in isolates the *mechanism* (memory + gate) from the *encoder* and
  turns range-dependence into a measured `snr` variable. (c) **Motion-only re-ID** — that
  *is* the baseline that fails (both vehicles share the crossing region).
- **Tradeoff / cost accepted:** the win is **conditional on separability** (snr ≳ 1);
  below the knee appearance memory alone is no better than memoryless. Reported as the
  headline frontier, not smoothed over.
- **Revisit when:** T2+ renders crops (swap `_observe` for an embedding distance off the
  same manifests) and/or T3 adds VLM re-verification for the low-SNR regime.

### 2026-06-18T15:30 — T1 gate PASS: temporal contract + scored clip set without a renderer

- **Decision:** Close the T1 gate with (a) the §6 temporal metrics locked in the shared
  `contract.py` (T1b) and (b) a **renderer-free** clip set — deterministic NED
  trajectory→pixel-GT via `oracle_bbox.project_object`, written as `labels.jsonl` +
  `manifest.json`, scored by the **memoryless-ByteTrack baseline** (`clip_recorder.py`).
  Gazebo rendering is deferred to T2.
- **Alternatives considered:** render RGB in Gazebo now (rejected — the gate scores boxes
  not pixels; pixels are load-bearing only when an appearance re-ID head/real VLM consumes
  crops, i.e. T2); oracle-association scoring for the headline (rejected — trivially hides
  the failure; kept only as a sanity test). See the campaign doc for the full rationale.
- **Reasoning:** the §6 metrics operate on `(pred_box, gt_box, visible, locked_id)`, all of
  which the oracle projection supplies deterministically. Keeping T1 pure-stdlib+numpy
  preserves the "de-risk cheaply before GPU/renderer" discipline and gives a reproducible
  baseline now. Control clip near-perfect (purity 1.0) while the 4-stressor clip drops to
  purity 0.725 / 1 ID-switch / coverage 0.575 → the suite both discriminates and quantifies
  constraint #2 (object permanence) as the explicit T2 target.
- **Tradeoff / cost accepted:** clips carry no photometric realism, so the appearance half
  of re-ID and a real VLM anchor can't be exercised until T2 adds a render pass keyed off
  the same manifests.
- **Revisit when:** T2 needs appearance crops → render frame-aligned RGB from these
  manifests (trajectory + intrinsics already define the SDF camera).

### 2026-06-18T13:30 — T0 gate PASS: anchor spine = Qwen2-VL-2B Q8_0 @ 512, event-triggered re-acquisition, two-tier architecture confirmed by the numbers

- **Decision:** Pass the **T0 (cadence & dynamics) gate** and lock the operating point
  for the rest of Part III. (1) **Anchor spine = the deployed Qwen2-VL-2B Q8_0 at 512
  long-edge** — measured **0.44 Hz / 2.27 s per anchor** on the Orin (15 W); 768/1024
  long-edge dropped, and **Gemma 4 stays dropped**. (2) **The two-tier architecture is
  mandatory, not a preference** — a 20 Hz fast tracker holds the lock, the VLM anchors
  sparsely. (3) **Re-acquisition must be event-triggered (fire an anchor on loss), not
  timer-only**, because `anchor_period (2.27 s) > coast_horizon (1.5 s)`. (4) **An
  appearance/re-ID head is admitted into the design space for T2** (compute-free at
  0.05 ms tracker cost; geometrically feasible at 10–20 m).
- **Alternatives considered:** (a) **Anchor at 768/1024 long-edge** for headroom — rejected
  by the numbers: the SITL camera is 640×480 and `_resize_keep_aspect` is downscale-only,
  so 768/1024 do **no** upscaling (zero fidelity gain on these frames) while costing
  1.6×/2.8× the latency (0.27/0.16 Hz). Pure loss. (b) **Gemma 4 as anchor** — stays
  rejected: image-only E2B/E4B already at 0.34–0.49 Hz (slower than the 512 Qwen point),
  video variants don't fit 8 GB; the untested token-budget lever didn't earn a seat. (c)
  **Timer-only periodic re-anchor** (simplest scheduler) — rejected: 2.27 s anchor period
  exceeds the 1.5 s Kalman coast, so a purely scheduled anchor arrives ~0.8 s after the
  track is already dropped. (d) **Lean on motion continuity alone (no appearance), extend
  `MAX_LOST_FRAMES`** — rejected as the *primary* mechanism: longer blind constant-velocity
  coasting trades recall for ID-switch risk, which is exactly the permanence failure T2
  exists to fix; appearance/re-ID is kept on the table instead.
- **Reasoning:** Two budgets fell out with **opposite verdicts**, and that split *is* the
  finding. **Inter-anchor tracking is comfortable** — per-frame target motion ≤ 27.7 px
  (10 m × 10 m/s) is tiny against a 110–222 px box, and the tracker costs 0.051 ms median
  (~1000× headroom under the 50 ms budget), so the fast loop carries the lock between
  anchors with ample room for an added appearance model. **Recovery-after-loss is tight** —
  the 2.27 s anchor period vs the 1.5 s coast horizon means a fully-lost target can't be
  re-anchored before its track is dropped; at low altitude + high speed the target is in
  frame only ~1.2 s and crosses the whole frame inside one anchor period — precisely the
  regime where Part-I Phase C (memoryless @ ~1 Hz) collapsed to ~0 % coverage. This
  quantifies *why* the two-tier architecture is forced and what T2/T3 must beat. Prefill
  (image encode) dominates and scales ∝ pixels (1113→2431→5111 ms) while decode is
  ~constant (~21.6 tok/s) — so resolution is the only cadence lever, and at this camera
  size 512 is both fastest and lossless.
- **Tradeoff / cost accepted:** `jetson_clocks` was **not confirmed engaged** (the NOPASSWD
  `--show` returned only the machine banner), so the cadence numbers are a *conservative
  default-15 W* point, not a clock-locked upper bound — a clock-locked run could only make
  the anchor faster, so the budget verdict (anchor > coast) is the safe side. T0c/d
  dynamics are **analytic** (pinhole projection via `oracle_bbox`), not yet from rendered
  pixels; the re-ID embedding-separability half is deferred to T1 where realistic frames
  exist (the no-pure-color constraint can't be tested on analytic boxes). The 1.5 s coast
  horizon is a tunable left at its current `MAX_LOST_FRAMES=30` default for now.
- **Revisit when:** T1 rendered clips give real occlusion/out-of-frame durations and a
  measured re-ID embedding separability (may move the appearance-vs-motion call or the
  coast-horizon tuning); or a clock-locked Orin run is taken (raises the cadence ceiling);
  or the target-dynamics envelope changes (faster targets / higher altitude shrink the
  budget further).

- **Decision:** Open **Part III** on branch `v3/object-permanence` (from
  `v2/principled-rebuild`) to attack **persistent single-object tracking under language
  conditioning** — keep a lock on a *moving* target across a video stream (occlusion,
  scale change, motion blur, out-of-frame, re-acquisition) well enough to close a
  following loop. Frame it explicitly as **NOT from scratch**: reuse the Part-I SITL
  follow stack (`experiments/sitl/`: ByteTrack, oracle_bbox, cascade_pid, offboard) and
  the Part-II deployed grounding anchor (Qwen2-VL-2B Q8_0, RefDrone 62.6%). Pre-register
  the general terms in `results/2026-06-18-part3-charter/README.md`: two binding
  constraints (#1 detection-cadence vs target-dynamics budget; #2 identity-through-
  absence / object permanence), the forced sparse-VLM-anchor + 20 Hz-fast-tracker
  architecture, a temporal metric suite (track continuity, ID switches, re-acquisition
  time, oracle-coverage, closed-loop error), and a proposed gated phase plan T0–T4.
  This turn is **charter + rules only — no code, no GPU, no measured result.**
- **Alternatives considered:** (a) **Start a clean v3 ignoring Part I/II** — rejected:
  the SITL stack and the deployed anchor are exactly the plumbing Part III would
  otherwise rebuild; the genuinely unsolved piece is permanence, so effort should go
  there. (b) **Commit to Gemma 4 as the anchor up front** (user's stated "very good
  fit") — rejected as a *decision*, kept as a *candidate*: Gemma 4's video-capable
  variants (26B/31B) don't fit the 8 GB Orin, and the fitting E2B/E4B already measured
  **0.34–0.49 Hz** on-device (slowest candidates, untested token-budget speed lever).
  The spine is picked by the numbers in T0, Part-II style. (c) **Skip the charter, jump
  to coding the loop** — rejected: violates the gated, measure-before-spend discipline
  that made Part II work; Phase C already showed the naive loop fails, so the design
  must be pre-registered. (d) **Extend Part II in place (no new branch/part)** —
  rejected: the metric, the problem (stream vs frame) and the binding constraints all
  change; a clean Part III demarcation keeps the lab notebook honest.
- **Reasoning:** Part II's success came from designing backwards from the constraint
  and de-risking cheaply before GPU. Part III inherits that: its two binding
  constraints are the temporal analogs of Part II's (cadence-vs-dynamics ↔ deployment-
  fidelity; permanence ↔ resolution ceiling), and its "fidelity-before-GPU" analog is
  "measure on-Orin cadence + target dynamics before designing the loop." The
  hardware-imposed ~20–60× rate gap (VLM 0.3–1.2 Hz vs control 20 Hz) forces the
  sparse-anchor + fast-tracker architecture; Phase C proved the naive version fails, so
  the contribution is making the tracker carry identity through absence and the VLM
  re-anchor correctly.
- **Tradeoff / cost accepted:** A third Part adds notebook surface and another gated
  arc to maintain. Charter-only this turn means no measured numbers yet — accepted: the
  whole point is to pre-register before spending GPU. The temporal metric suite is a new
  contract surface to lock (deferred to T1). Real-video vs SITL data and anchor-model
  choice are left as open forks for the user rather than decided unilaterally.
- **Revisit when:** T0 numbers come in (cadence budget + spine pick may reshape the
  phase plan); or the user resolves the open forks (anchor model, data source); or a
  Gemma 4 token-budget sweep changes its on-Orin viability.

---

# Part II — Principled rebuild (v2)

<!-- v2 decisions are appended here, most recent first. -->

### 2026-06-18T01:30 — Phase 4 PASS: accept Q8_0 as the deployment artifact; the Part-I fidelity gap does not reproduce on Qwen2-VL — Phases 0–4 complete

- **Decision:** Declare **Phase 4 PASS** and ship **GGUF Q8_0** as the Jetson deployment artifact. Measured on-device over the full RefDrone well-posed val (n=439), same contract path as the HF reference: HF 59.5% → **F16 62.2%** (runtime/preprocessing gap **−2.7pp**) → **Q8_0 62.6%** (quant gap **−0.5pp**). Both deployed quants clear the pre-registered fidelity floor (57.5% = HF 59.5% − 2pp budget) and in fact *exceed* the HF reference within n=439 noise. Q8_0 chosen over F16: ≈½ the weights (1.65 vs 3.09 GB) at indistinguishable accuracy. This closes the v2 phased arc — **Phases 0–4 all green and documented.**
- **Alternatives considered:** (a) **Ship F16** — rejected: no accuracy benefit over Q8_0 (−0.5pp, noise) for 2× the memory footprint on an 8 GB unified-memory device. (b) **Push to lower quant (Q4_K_M / Q5)** — deferred, not rejected: Q8_0 already fits with headroom and the thesis claim ("no fidelity loss") is cleanest at Q8; a Q4 ladder is a *future* size/accuracy probe, not needed to pass the gate. (c) **Treat deployed > HF as a real gain** — rejected as a *claim*: +2–3pp on n=439 is within sampling noise; the honest, thesis-relevant statement is the **absence** of the Part-I gap, not an improvement.
- **Reasoning:** Phase 4 is the de-risking the whole v2 design was built backwards from. Part I's −23pp runtime + −7pp quant collapse (SmolVLM/Idefics3) was the binding constraint that justified the rebuild; the entire point of Phase 0c was to pick a spine whose llama.cpp preprocessing matches its HF path *before* spending GPU. The on-device numbers vindicate that bet: Qwen2-VL's HF→F16 gap is −2.7pp (vs SmolVLM's −23pp), so the budget was never spent. Measuring on the Jetson at the same pinned llama.cpp commit as the local build isolates the variable to hardware+quant, not backend version.
- **Tradeoff / cost accepted:** The disambiguation cost two full n=439 on-device evals (CUDA, minutes each) rather than a local CPU run (CPU-hours) — accepted, and cheaper. We deploy Q8_0 without having mapped the lower-quant frontier (Q4/Q5), so the *minimum* deployable footprint is unknown; accepted because the gate is about fidelity, not minimization. The "deployed > HF" inversion is recorded as noise, not banked as headroom.
- **Revisit when:** a tighter memory budget forces a lower quant (then run the Q4/Q5 ladder with this same n=439 harness); or the deployment resolution/prompt changes (re-measure — the gap is preprocessing-sensitive); or a different aerial dataset/spine is adopted (the −2.7pp figure is Qwen2-VL-specific and must be re-characterised).

### 2026-06-18T01:15 — Phase 4: run the authoritative F16-vs-Q8 disambiguation and deployment gate on the Jetson, not on local CPU

- **Decision:** Make the **Jetson** the site of the headline F16↔Q8 disambiguation and the deployment gate (full RefDrone val, n=439). Keep `export.to_gguf` **conversion-only by default**; its `run_fidelity_gate=True` path is an *optional* small-n local-CPU smoke (does the GGUF load + parse), explicitly not the gate.
- **Alternatives considered:** (a) **Local CPU-only llama.cpp** (the box has no nvcc/CUDA) — rejected for the headline: an n=439 GGUF eval at 1024px is CPU-*hours* per arm, and it would measure a non-deployment machine. (b) **Local + Jetson both, as a cross-check** — deferred: the local build and the Jetson build are the *same pinned commit*, so the only added signal would be CPU-vs-CUDA numerics, not worth the CPU-hours now. (c) **Trust the HF number and skip on-device eval** — rejected outright: that is exactly the Part-I mistake (the −23pp gap was invisible until measured on the real backend).
- **Reasoning:** The Jetson *is* the deployment target, has CUDA (seconds/sample), and runs the identical pinned llama.cpp commit as the local converter — so backend *version* is held fixed and only hardware+quant vary. Measuring fidelity where the model will actually run is the only honest gate.
- **Tradeoff / cost accepted:** Depends on `ssh jetson` being up and the device free (one GPU/server → F16 and Q8 run serially, not concurrently). No CPU-vs-CUDA numeric cross-check captured (accepted; same commit).
- **Revisit when:** the local box gains CUDA (then a free local cross-check becomes cheap); or a future spine doesn't fit the 8 GB device (then local eval is the only option and the CPU-hours must be paid).

### 2026-06-18T01:00 — Jetson 8 GB OOM fix: serve single-slot with no prompt cache (`-np 1 --cache-ram 0 --no-cache-idle-slots`)

- **Decision:** Launch the on-device `llama-server` (in `JetsonBackend`) with **`-np 1 --cache-ram 0 --no-cache-idle-slots`** — one slot, no prompt-cache RAM, no idle-slot cache. Required to evaluate the F16/Q8 GGUFs over n=439 without the server being OOM-SIGKILLed mid-run.
- **Alternatives considered:** (a) **Defaults** — rejected: `--cache-ram` defaults to 8192 MiB, which on an 8 GB *unified*-memory device collides with the model weights + KV + CUDA context; the F16 eval crashed at sample 64/439 with `RemoteDisconnected` (server SIGKILLed). (b) **Cap `--cache-ram` to a small non-zero value** — workable but adds a tuning knob with no benefit for a single-stream eval. (c) **Reduce `n_ctx` / offload fewer layers** — rejected: would change the measured configuration (we want full offload at the trained resolution); the cache, not the model, was the regression.
- **Reasoning:** The eval is strictly single-request/sequential, so multi-slot and prompt caching buy nothing and only consume the scarce unified memory. Disabling them makes memory stable (~5.8 GB RSS, ~1.3 GB headroom) and the n=439 run completes cleanly for both quants.
- **Tradeoff / cost accepted:** No prompt-cache reuse → marginally slower if prompts shared prefixes (they don't matter here; each sample is independent). Single slot → no concurrency, fine for batch eval, would need revisiting for a serving workload.
- **Revisit when:** deploying for *concurrent* inference (then size `--cache-ram`/slots against measured free memory); or moving to a larger-memory Jetson where the defaults fit.

### 2026-06-18T00:55 — mmproj reuse: regenerate from the merged checkpoint but treat it as bit-equivalent to the base projector (vision frozen)

- **Decision:** Export the multimodal projector (`mmproj`) from the merged Phase-3 checkpoint for self-contained provenance, but rely on it being **tensor-bit-equivalent to the base Qwen2-VL mmproj** (only the GGUF metadata header differs). Confirmed by identical byte size (1334666400 B) and the frozen-vision construction; one mmproj serves both base and fine-tune.
- **Alternatives considered:** (a) **Ship the base mmproj directly, skip regeneration** — works, but regenerating from the checkpoint keeps each deployed skill self-contained (no external base dependency to track). (b) **Assume the LoRA changed the projector** — false by construction: Phase-3 froze the vision tower and put LoRA only on the LLM attn+MLP, so the projector weights are untouched.
- **Reasoning:** The export code already cross-checks the regenerated mmproj's sha256 against the base; the match makes the provenance explicit and rules out a silent projector drift between base parity (Phase 0) and deployment (Phase 4).
- **Tradeoff / cost accepted:** Regeneration spends a little disk/time to produce a file that is payload-identical to one we already had — accepted for provenance cleanliness.
- **Revisit when:** a future run *unfreezes* the vision tower (then the projector genuinely changes and must be exported + re-parity-checked per checkpoint).

### 2026-06-18T00:50 — Jetson power mode: this unit has only 15 W (mode 0, default/max) and 7 W (mode 1); no 25 W MAXN_SUPER

- **Decision:** Record that the deployment Jetson Orin Nano exposes **only two nvpmodel modes — 0 = 15 W (default, the max on this unit) and 1 = 7 W** — and run all Phase-4 deployment evals at **mode 0 + `jetson_clocks` locked** (the on-device upper bound). The CLAUDE.md mention of a 25 W `MAXN_SUPER` does not apply to this board/firmware.
- **Alternatives considered:** (a) **Assume MAXN_SUPER 25 W exists** — rejected: `nvpmodel -q` on the device lists only modes 0/1; claiming a 25 W run would be an unverified number. (b) **Run at 7 W for an efficiency point** — deferred: the Phase-4 gate is about deployment *fidelity*, not the power/throughput curve; a 7 W-vs-15 W sweep is a separate (optional) measurement.
- **Reasoning:** No unverified claims (prime directive). The available power envelope is a hardware/firmware fact that must be stated as measured, and 15 W + locked clocks is the honest "max performance" deployment condition for this unit.
- **Tradeoff / cost accepted:** No 25 W headline number (the hardware can't provide one). No 7 W efficiency datapoint captured in Phase 4 (accepted; out of scope for the fidelity gate).
- **Revisit when:** the device firmware is updated and `nvpmodel -q` exposes a higher mode; or a power/efficiency campaign is run (then sweep 7 W vs 15 W with `tegrastats` logged).

### 2026-06-18T00:45 — Auto-continuation: move the self-resume scheduler out of the session into the OS crontab

- **Decision:** Replace the in-harness auto-continuation (the earlier `CronCreate durable:true` attempt) with an **OS-level crontab entry** that runs a committed wrapper script, so the scheduler is independent of any Claude session and survives Pro 5-hour-window token exhaustion. Pieces: `scripts/auto_continue.sh` (the wrapper, run every 15 min by the user crontab), `scripts/auto_continue_prompt.md` (a self-contained, idempotent continuation prompt that re-derives project state every fire), and a gitignored `.auto-continue/` runtime-state dir (logs, sentinels, lock). Each tick the wrapper launches a fresh headless `claude -p --dangerously-skip-permissions --add-dir <repo>`; when the window is exhausted that call fails fast (rate-limited, ~no token cost) and the next tick retries; when the window resets the next tick simply succeeds. Five ordered safety guards: **STOP** sentinel (operator kill switch) → **DONE** sentinel (all phases complete → stop launching) → **flock** (atomic mutex, never two headless runs) → **pgrep -x claude** (defers to ANY live claude, so cron only takes over once the interactive session is gone) → **timeout 3h** (bounds a hung run; next tick resumes). Smoke-tested: STOP/DONE skip cleanly and the live interactive session is correctly deferred to.
- **Alternatives considered:** (a) **Harness `CronCreate`/`ScheduleWakeup`** — the prior approach; rejected because `durable:true` was not honored → the schedule lived only inside the session and died with it on token exhaustion (the exact failure this redesign fixes). (b) **Parse the rate-limit reset time and sleep until then** — rejected as needless complexity ("opt for the simpler approach"): blind bounded retries every 15 min cost ~nothing when rate-limited and resume within ≤15 min of reset. (c) **A long-lived daemon / `while true; sleep`** — rejected: a daemon is itself fragile (dies on reboot, no built-in restart) whereas cron is already running, reboot-persistent, and the rclone job proves it works on this box. (d) **systemd timer** — equivalent robustness but heavier to install/inspect than a one-line crontab append next to the existing job; cron chosen for parity with what's already there. (e) **No pgrep guard (flock only)** — rejected: flock alone prevents headless-vs-headless overlap but would let a headless run fire *while the user's interactive session is live*, double-spending tokens and risking git races; pgrep makes cron strictly a fallback.
- **Reasoning:** The binding requirement was robustness across the event that kills the session (token-window exhaustion), so the scheduler *must* live outside the session — the OS crontab is the simplest durable thing that satisfies that and is already proven on this machine. Idempotency (re-derive state every fire, never redo committed work) makes bounded retries safe and removes any need to checkpoint scheduler state. The guard ladder makes the default behaviour conservative: it does nothing while a human/session is active, stops itself when work is done or on operator command, and can never stack concurrent runs.
- **Tradeoff / cost accepted:** Cron launches a `--dangerously-skip-permissions` headless agent unattended — a powerful, persistent capability; mitigated by the STOP kill switch, the DONE auto-stop, the repo-scoped `--add-dir`, the never-push rule baked into the prompt, and the `.auto-continue/BLOCKED.md` stop-and-explain path for anything needing a human. Up to ~15 min resume latency after a window reset (accepted). The wrapper assumes the crontab `PATH`/`HOME` it pins stay valid; if `claude` moves, the pinned `PATH` needs updating.
- **Revisit when:** all phases finish (the agent writes `.auto-continue/DONE`; the crontab line can then be removed); or the harness gains a genuinely durable cross-session scheduler (then reconsider (a)); or unattended headless runs prove too costly/risky (tighten cadence, add a heartbeat/cost cap, or require an explicit per-tick enable flag).

### 2026-06-18T00:30 — Phase 3: accept the well-posed / 1024 / lr-2e-4 / 3-epoch LoRA config as the v2 trained spine — Phase 3 PASS

- **Decision:** Accept the single config-driven LoRA fine-tune (`grounding/train/{config,trainer}.py`) of **Qwen2-VL-2B** on **RefDrone well-posed (4101 train / 439 val)** at **`max_side=1024`** as the v2 trained aerial grounder, and carry its **HF full-val IoU@0.25 = 59.5%** as the fidelity reference for Phase 4. Config: LoRA r16/α32/dropout0.05 on the LLM attn+MLP projections (vision frozen by construction, 18.5 M trainable = 0.83%), lr 2e-4, 3 epochs, batch 2 × grad_accum 8 (effective 16), bf16, seed 42, no warm-start, verbatim contract, greedy eval. Results: in-loop val n=200 epoch1/2/3 = 63.0 / 65.0 / 65.0% IoU@0.25 (parse 100%, center_std 212→227); **authoritative full-val n=439 = 59.5% IoU@0.25, parse 100%, mean_iou 0.451, center_std 215.2** — directly comparable to the Phase-2 base-1024 ladder (30.3% on the same n=439). Manifest `runs/20260617T212559Z`; merged checkpoint `runs/v2/phase3-refdrone-1024/`. Docs: `results/2026-06-17-phase3-train/`.
- **Alternatives considered:** (a) **Pull a reserved lever** (`largest_box_aug` to recover the ~12339-sample budget, and/or `max_side=1280`) — *not needed*: the gate (20%) was cleared at **epoch 1** (63%) and the final is ~3× the bar, so spending the levers would add cost and a second variable for no gating benefit; both stay in reserve for a future accuracy push. (b) **Warm-start from a RefCOCO LoRA** (the Part-I Stage-3→4 curriculum that reached Stage-3 82.5%) — not used: the from-scratch RefDrone fine-tune already clears the gate with large margin, so the extra curriculum stage is unjustified complexity now; `init_from` remains available if a later push needs it. (c) **Train more epochs / higher lr** — rejected: in-loop IoU plateaus at epoch 2→3 (65.0→65.0, mean_iou +0.003) while loss still falls — more epochs risk overfitting the 4101-sample budget for no held-out gain. (d) **Report the in-loop n=200 number (65%) as headline** — rejected: it is the small-sample-optimistic subset; the n=439 full-val (59.5%) is the apples-to-apples comparison to the Phase-2 base ladder and is the number carried forward.
- **Reasoning:** This is the central v2 result and it validates the whole fidelity-before-GPU design. Part-I Stage 4 *missed* the same aerial gate at 19.5%; the v2 stack hits **59.5% (~3.1×)** with a single honest LoRA loop and no per-stage forks. The 19.5%→59.5% gain decomposes cleanly into the two pre-registered, independently-measured levers the rebuild was organised around: **resolution** (binding constraint #2 — base 512→1024 = 4.1%→30.3% zero-shot, Phase 2) **× the fine-tune** (30.3%→59.5%). The Part-I miss was therefore a resolution-starved setup, not a training failure — exactly the diagnosis v2's phased gates were built to surface *before* spending GPU. Health is unambiguous: parse 100% (the fine-tune even fixed the base model's 8% prose-leak), and `center_std` 215 and *rising* with training — ≈3.5× the ~61 marginal-mean collapse floor, the precise opposite of the Stage-2 failure mode whose root cause Part-I eliminated.
- **Tradeoff / cost accepted:** The trained ceiling is bounded by the small well-posed budget (4101) and the 1024 resolution; the unused levers (`largest_box_aug`, 1280) mean a known, pre-measured headroom is left on the table — a deliberate trade for a clean single-variable baseline that already passes. The headline 59.5% is an **HF bf16, greedy** number on the held-out well-posed val; the *deployed* number is what Phase 4 must defend (within the Phase-0 fidelity budget). center_std/IoU are measured on the well-posed subset only — out-of-subset (multi-box) aerial captions are out of scope by the Phase-1 decision.
- **Revisit when:** Phase 4 export/deploy lands the GGUF *outside* the Phase-0 fidelity budget of 59.5% (then debug the backend, not the training); or a later accuracy push is wanted — then pull the reserved levers in single-variable order (`max_side=1280`, then `largest_box_aug`, then RefCOCO warm-start via `init_from`) and re-measure each; or overfitting is suspected — then add a train/val loss-gap check and early-stop.

### 2026-06-17T20:00 — Phase 2: choose `max_side=1024` as the input long-edge resolution — Phase 2 complete

- **Decision:** Train and deploy the v2 aerial grounder at an **input long-edge resize of `max_side=1024`** (Qwen2-VL native dynamic resolution; whole-image downscale, no tiling). Chosen by a no-training resolution ladder on the Phase-0 harness over the RefDrone well-posed val (n=439, Qwen2-VL-2B **base**, HFBackend bf16 greedy, verbatim contract), arms ∈ {512, 768, 1024, 1280}. Numbers (IoU@0.25 / parse / center_std): **512 → 4.1% / 100% / 129.1**, **768 → 10.7% / 100% / 157.9**, **1024 → 30.3% / 91.8% / 192.0**, **1280 → 38.7% / 92.0% / 196.1**. Marginal IoU@0.25 gains +6.6 / **+19.6** / +8.4 pp identify the elbow at 1024 (it captures ~78% of the 1280 ceiling; per-step return halves past it). `image_size=1024` / `resolution_strategy="resize1024"` set in `grounding/train/config.py`. Manifests: `runs/20260617T190608Z` (512), `runs/20260617T191130Z` (768), `runs/20260617T191739Z` (1024), `runs/20260617T192436Z` (1280).
- **Alternatives considered:** (a) **`max_side=1280`** (highest measured accuracy, 38.7%) — *not chosen now, kept as the explicit Phase-3 lever*: it is +8.4 pp over 1024 but costs ~1.56× the visual tokens (∝ area) for both 3090 training throughput/VRAM and, decisively, the **8 GB Jetson** deploy footprint + decode latency (Phase-4 constraint), and the per-step return has more than halved — it is past the elbow. (b) **`max_side=512`** (the Part-I setting, preserves every Phase-0/1 number) — rejected: 4.1% zero-shot is the resolution-starved regime that produced Part-I's 19.5% ceiling; binding constraint #2 in action (median aerial object ≈16 px → ~8 px at 512). (c) **`max_side=768`** — rejected: at 10.7% it is still below the 20% gate before training and sits *before* the dominant +19.6 pp jump; it would leave most of the cheap resolution headroom on the table. (d) **Tiling / coarse-to-fine crops** — deferred (pre-registered in the Phase-2 README): grounding has no known target location at inference, so tiling needs a multi-pass run + ambiguous cross-tile box merge — a far larger intervention than the single-pass native-resolution lever, which must be exhausted first. (e) **Go even higher than 1280** (1536+, all upscaling-free since VisDrone originals are ~2000×1500) — rejected for now: no plateau is *yet* visible, but each step's marginal return is shrinking while cost grows ∝ area; chasing it pre-training inverts the cost/benefit and is better revisited only if 1024 training misses the gate.
- **Reasoning:** v2 makes resolution a pre-registered, measured variable instead of an accident. The ladder shows resolution is **the** dominant lever (4.1% → 38.7%, a 9.4× swing with weights frozen), and that the base model already clears the 20% gate at 1024 *before training* — so 1024 starts Phase-3 above the bar with fine-tuning headroom on top. The choice is the textbook elbow: 1024 sits exactly on the high-return side of the single largest marginal jump (768→1024 = +19.6 pp) and captures ~78% of the ceiling, while 1280's +8.4 pp costs disproportionately more compute on the memory-constrained deployment target the whole project is designed backwards from. `center_std` rising monotonically (129 → 196, far above the ~61 collapse floor) confirms higher resolution makes outputs *more* input-dependent — no collapse risk introduced. Picking the smallest size that captures most of the gain is exactly the RQ-2.3 mandate and keeps 1280 in reserve as a clean, single-variable Phase-3 lever.
- **Tradeoff / cost accepted:** We leave +8.4 pp of *base-model* IoU@0.25 (1024→1280) on the table in exchange for ~35% fewer visual tokens — a deliberate accuracy-for-deployability trade, justified because the deliverable is a model *on the 8 GB Jetson* and because fine-tuning is expected to lift the 1024 curve anyway. The ≥1024 arms drop parse_rate from 100% to ~92% (occasional prose around the JSON on hard small-object crops); accepted as still well above the Phase-3 ≥90% bar and a training-fixable behaviour. All numbers are base-model (zero training), so they bound the *starting* point, not the trained ceiling — the Phase-3 gate is measured after fine-tuning, not inferred from here.
- **Revisit when:** the Phase-3 aerial gate (IoU@0.25 ≥ 20%, parse ≥ 90%, center_std non-degenerate) is missed *at 1024* — then escalate to `max_side=1280` (the pre-measured next lever) and/or enable the Phase-1 `largest_box_aug` budget lever in the same turn; or Phase 4 finds 1024 is comfortably within the Jetson footprint/latency budget with headroom — then re-evaluate 1280 for a deployed accuracy gain; or a tiling strategy is later justified (re-open alternative (d) and re-audit the post-transform object-size distribution).

### 2026-06-17T18:00 — Phase 1: keep the one-box well-posed filter as the only tractable target; budget 4101/439; resolution is the dominant lever — Phase 1 complete

- **Decision:** Adopt the **one-box-per-caption well-posed subset** of RefDrone as the v2 aerial training target, confirmed by a CPU-only annotation audit (`grounding/data/audit.py`, kind="audit" manifests) *before* any GPU run. The audit measures box-per-caption distribution and √area object-size percentiles (pre/post the `IMAGE_SIZE=512` long-edge resize) on RefDrone train+val, with RefCOCO as the well-posed-by-construction control. Numbers: RefDrone **train mean 3.80 boxes/caption** (matches Part-I exactly), **only 33.2% well-posed** → **4101 trainable samples** (val 30.9% → 439), **0 images missing**; aerial object **@512 median ≈16 px, bottom-quartile 6–10 px** vs RefCOCO control median 172 px. The gate (`assert_well_posed`, min 0.95) FAILS on the raw corpus (0.332) and PASSES on the filtered subset (1.000). The audit stats are baked into the canonical schema (`AuditStats`) and committed as manifests `runs/20260617T173529Z-audit-refdrone-{train,val}`, `runs/20260617T173532Z-audit-refcoco-validation`.
- **Alternatives considered:** (a) **Use all boxes per caption** (the Part-I Stage-2 setup: emit each box as a separate sample sharing the caption) — rejected: this is the exact ill-posed target that drove the Stage-2 marginal-mean collapse (IoU ≈1%, center_std → floor); the audit reproduces its 3.80 mean precisely, confirming the gate would have caught it for free. (b) **`largest_box_aug`** — keep multi-box captions but supervise the single largest-area box (recovers the full ~12,339-caption budget) — *not rejected, deferred*: it is a pre-registered Phase-3 data-scaling lever (a `load_refdrone` flag, already implemented), to be A/B'd against the strict one-box subset *after* a clean baseline exists, not folded in blind now. (c) **Skip the audit, train directly on the filtered subset** — rejected: the box-per-caption + object-size distributions are the two binding-constraint measurements the whole gate exists to make explicit; skipping them re-introduces the "discover the data problem after GPU spend" anti-pattern. (d) **Pad/upweight the small budget with synthetic boxes** — rejected: out of scope and unjustified before a baseline shows the 4101-sample budget is actually the bottleneck.
- **Reasoning:** v2's Phase-1 gate exists precisely to make ill-posedness visible *before* training. The audit confirms the one-box filter is the only target that excludes the Stage-2 killer by construction (well-posed fraction → 1.0), and quantifies the cost: a small (4101) but clean supervision budget. The object-size measurement turns binding constraint #2 from a remembered range ("2–11 px") into committed numbers (median 16 px, p25 10 px @512) — establishing **resolution as the dominant downstream lever** and feeding Phase 2 real targets. The small budget independently argues for **warm-starting from RefCOCO** (large, 100%-well-posed, grounding-rich) before the aerial fine-tune, and keeps `largest_box_aug` in reserve as the documented budget-scaling lever.
- **Tradeoff / cost accepted:** The strict filter discards ~⅔ of aerial captions (8238 train) — a real supervision loss accepted in exchange for a well-posed target; `largest_box_aug` is the lever to claw it back if 4101 proves insufficient at the Phase-3 gate. The audit is annotation-only (no image decode, no model), so object-size percentiles assume the recorded `width`/`height` are correct; spot-checked against the 0-missing-image load. RefCOCO size audit de-normalizes the canonical 0–1000 bbox back to pixels (a small rounding path), used only for the control comparison, not for training.
- **Revisit when:** the Phase-3 aerial gate (IoU@0.25 ≥ 20%) is missed and data volume is implicated — then enable `largest_box_aug` (or curriculum) and re-audit the expanded corpus in the same turn; or Phase 2 picks a resolution strategy that changes the effective object-size distribution (re-run the post-resize audit at the new input size).

### 2026-06-17T17:30 — Phase 0c.2: select **Qwen2-VL-2B** as the v2 spine, by the parity numbers — Phase 0 complete

- **Decision:** Adopt **Qwen2-VL-2B-Instruct** as the model spine for v2 training (Phases 1–4), replacing the Part-I incumbent SmolVLM-500M. Chosen by a base-vs-base zero-shot RefCOCO parity probe (n=100, seed-42, verbatim contract) on the two survivors of the 0c.1 deployment filter. Numbers: **Qwen2-VL-2B base HF 15.0% IoU@0.25 / parse 24% / center_std 162.1 (healthy)** vs **SmolVLM-500M base HF 0.0% / parse 9% / center_std 61.3 (collapsed)**; Qwen deployment fidelity **HF→GGUF-F16 = −2pp**, F16→Q8_0 ≈ 0pp — against SmolVLM-ft3's **−16pp** runtime gap measured in 0b. Manifests: `runs/20260617T165959Z` (SmolVLM HF), `runs/20260617T170339Z` (Qwen HF), `runs/20260617T171534Z` (Qwen F16), `runs/20260617T172502Z` (Qwen Q8_0).
- **Alternatives considered:** (a) **Keep SmolVLM-500M** (incumbent, smallest footprint, already deployed Part-I) — rejected: its base model has *zero* zero-shot grounding (must manufacture the capability from scratch in training) and its deployment path costs −16pp (the Idefics3 preprocessing divergence), the exact binding constraint #1 that v2 exists to minimise. (b) **Decide on size/footprint alone** (SmolVLM is 4× smaller) — rejected: footprint is a Phase-4 constraint to *verify*, not the selection axis; an 8 GB Jetson comfortably runs a 2B Q8_0 (1.6 GB weights), and Part-I ran 3B-class models. (c) **Run the SmolVLM-base GGUF arms too** for symmetry — rejected: SmolVLM base has 0% grounding to lose, so its HF→GGUF gap is undefined-at-floor; the SmolVLM deployment gap that matters was already measured on the grounding-capable `smolvlm_ft3` in 0b. (d) **Defer the choice to a post-training bake-off** (train both, compare) — rejected: that doubles GPU spend and re-introduces the "commit before measuring" anti-pattern; the spine question is answerable cheaply *before* training, which is the whole point of Phase 0.
- **Reasoning:** Three independent, data-driven axes all point to Qwen2-VL-2B. (1) **Grounding-native**: a real zero-shot floor (15%, healthy center_std) for the trainer to lift, vs SmolVLM-base collapse. (2) **Deployment fidelity ~8× better**: −2pp vs −16pp runtime gap on the *pinned* `57fe1f0` path — directly de-risks the constraint that capped Part-I. (3) **Native dynamic resolution**: Qwen2-VL is not forced through the 512 long-edge → frozen-SigLIP resize that shrank aerial objects to 2–11 px (binding constraint #2), so it brings leverage on the resolution ceiling into Phase 2 for free. Quant cost is negligible on both (≈0–2pp), confirming again that runtime, not quant, is the deployment question — and Qwen wins it.
- **Tradeoff / cost accepted:** 4× the parameters (2B vs 0.5B) → larger Jetson footprint + slower decode (to be confirmed in Phase 4; Q8_0 = 1.6 GB + 1.3 GB mmproj, within budget). A new architecture vs the Part-I work — but the contract is model-agnostic and both backends host Qwen unchanged; only `train/config.py` needs Qwen2-VL LoRA target modules (a config change, not a fork). Absolute zero-shot scores are modest (15% IoU, 24% parse), but that is expected of a base model on a strict JSON contract; fine-tuning lifts the ceiling (SmolVLM base 0% → ft3 HF 85% is the existence proof).
- **Revisit when:** Qwen2-VL-2B fails its Phase-3 gate (aerial IoU@0.25 ≥ 20%, parse ≥ 90%, center_std non-degenerate) or its Phase-4 deployed footprint/throughput is unviable on the 8 GB Jetson — then reconsider SmolVLM-500M (smaller, −16pp gap accepted) or a smaller Qwen variant; or if the pinned llama.cpp later admits PaliGemma/Florence (0c.1), which could re-open the candidate set.

### 2026-06-17T16:00 — Phase 0c: disqualify PaliGemma 2 and Florence-2 by a zero-cost deployment-backwards filter, before any download

- **Decision:** Resolve the spine question (RQ-0.3) by applying the **cheapest screen first** to all four candidates — a *deployment-backwards filter*: does the pinned llama.cpp `57fe1f0` support the candidate's vision projector, both at runtime (`tools/mtmd/clip.cpp` `PROJECTOR_TYPE_*` + `clip_graph_*`) and in conversion (`conversion/*.py` `@ModelBase.register` + `--mmproj`)? Result: **SmolVLM-500M** (IDEFICS3) and **Qwen2-VL-2B** (QWEN2VL, `conversion/qwenvl.py`) are deployable; **PaliGemma 2** and **Florence-2** have *zero* projector support (grep `paligemma|florence` in `clip.cpp` → 0 hits) and are **disqualified before any model download**. The parity probe (0c.2) runs only on the two survivors.
- **Alternatives considered:** (a) **Literally "try all" four** — download PaliGemma 2 (3B) + Florence-2 (0.77B), write per-model output-format adapters (`<locXXXX>` / region tokens → bbox), and probe their HF zero-shot in-domain IoU anyway — rejected: it spends GPU + disk + adapter-engineering on spines we have *already proven we cannot serve* on the target device, which is the exact "discover the deployment gap after the work" anti-pattern v2 was built to kill; their non-JSON formats also break the shared contract, so the number wouldn't even be contract-comparable. (b) **Download prebuilt third-party GGUFs** to test deployability — rejected: those are built at unknown commits, not our pinned `57fe1f0`; the grep tests *our* backend, which is the actual deployment path. (c) **Switch the pinned llama.cpp commit** to one that might support PaliGemma — rejected: the pin is a binding fidelity control (the −16pp measurement is against `57fe1f0`); moving it to admit a candidate would invalidate 0a/0b.
- **Reasoning:** v2 is designed *backwards from deployment* — deployability is a *gate*, not a tiebreaker, so it is applied before the expensive accuracy probe. The filter costs zero downloads (source grep) yet eliminates two of three grounding-native candidates definitively. The user's "try all" is honoured in spirit and method: all four *are* screened; the screen is simply decisive for two. Qwen2-VL survives and is the strongest possible challenger — it is grounding-native *and* its native dynamic resolution directly attacks binding constraint #2 (the tiny-object 512 ceiling).
- **Tradeoff / cost accepted:** We forgo a *curiosity* datapoint — PaliGemma/Florence zero-shot accuracy on RefCOCO — which the grounding literature would predict is strong. Accepted: a high zero-shot score on an undeployable model is not actionable for this thesis (the deliverable is a model *on the Jetson*), and chasing it would burn the GPU budget the phase exists to protect. If the framing ever changes (e.g. a server-class deployment target), revisit.
- **Revisit when:** the pinned llama.cpp adds a PaliGemma/Florence projector (then they re-enter the race); or the deployment target stops being the Jetson/llama.cpp; or Qwen2-VL fails its 0c.2 probe *and* SmolVLM is judged insufficient, forcing a wider search (then reconsider an HF-only spine with a custom export path).

### 2026-06-17T14:30 — Phase 0b: measure the GGUF fidelity gap on a local CPU-only llama.cpp build, greedy decode

- **Decision:** Run the Phase-0b parity self-check entirely **locally on a CPU-only llama.cpp build** rather than over the Jetson. Built llama.cpp at the pinned commit `57fe1f0` with `-DGGML_CUDA=OFF -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release` (→ `llama-server`, `llama-mtmd-cli`, `llama-cli` in `/tmp/llama.cpp-57fe1f0/build/bin`), `scp`'d the projector `mmproj-SmolVLM-500M-Instruct-f16.gguf` from the Jetson (`/home/jfdg/models/`, 199 MB), and had `GGUFBackend` boot a local `llama-server` per run on a free port. Both GGUF arms decode **greedy** (`temperature=0`) — a deliberate departure from the Part-I GGUF arm's server-default sampling — for harness determinism. `eval/parity.py` *composes* the three committed run manifests (it does not re-run inference). Result: HF 85.0% → F16 69.0% (**runtime −16.0 pp**) → Q8_0 67.0% (**quant −2.0 pp**); runtime ≫ quant reproduced.
- **Alternatives considered:** (a) **Per-sample SSH round-trips to the Jetson** (the real deployment target) — rejected: 100 samples × server round-trips over SSH is slow and couples the self-check to device availability/thermals; the Jetson is the *deployment* measurement (Phase 4), not the place to *calibrate the instrument*. (b) **A CUDA llama.cpp build locally** — rejected: `nvcc` is absent on this box and, decisively, the gap is an *image-preprocessing* (Idefics3 path) divergence, not a compute one, so it measures identically on CPU — GPU would only buy speed the self-check doesn't need. (c) **Match Part-I's sampled decode exactly** to reproduce the −23pp number to the point — rejected: the claim under test is the *structure* of the gap (runtime ≫ quant), not a single magnitude; determinism is worth more to a reusable harness than chasing a sampling-dependent figure. (d) **`llama-mtmd-cli` per sample** — rejected: would reload the model 100× on CPU; `llama-server` loads once and matches the Part-I OpenAI-endpoint path.
- **Reasoning:** The user explicitly chose the simpler self-contained path ("opt for the simpler approach, i dont mind cpu time or disk space"). CPU is not a compromise here because the quantity being measured is preprocessing fidelity, which is backend-compute-independent. Booting `llama-server` via the same OpenAI `/v1/chat/completions` path the Part-I `g3_parity` used, with identical resized-then-lossless-PNG pixels, keeps the only residual each runtime's own internal image handling — exactly what the −16pp number attributes. Composing manifests instead of re-running honours the manifest-per-run rule: every cell in the parity table is traceable to a committed `runs/<id>/`.
- **Tradeoff / cost accepted:** CPU eval is ~2 min/100 samples (fine). The greedy change means the v2 magnitudes (−16 / −2 pp) are not numerically identical to Part-I's (−23 / −7 pp); accepted because the direction, dominance ordering, and order of magnitude all match and the determinism is a net gain. The `/tmp` build is ephemeral (path hard-coded as `_DEFAULT_LLAMACPP_BIN`, overridable via `LLAMACPP_BIN_DIR`); if `/tmp` is cleared the build must be redone — accepted as cheap and documented.
- **Revisit when:** Phase 0c needs the parity probe on a non-Idefics3 spine candidate whose gap *is* compute-sensitive (then re-measure on GPU); or the `/tmp` build is lost (rebuild at `57fe1f0`); or Phase 4 measures the *actual* Jetson number, at which point the device replaces this local proxy.

### 2026-06-17T12:30 — Phase 0: implement the read-only RefCOCO loader during Phase 0 (ahead of the Phase-1 data gate)

- **Decision:** Write `grounding/data/refcoco.py` as a **read-only / inference-only** adapter *now*, during Phase 0, even though `data/` is nominally a Phase-1 module. It loads the HF `jxu124/refcoco` annotations + local COCO train2014 images and emits canonical `GroundingSample`s with boxes normalized via `contract.normalize_bbox`; its flatten + seed-42 shuffle + cap behaviour is lifted verbatim from the Part-I `run_stage3_finetune.RefCOCODataset` so `load_refcoco("validation", max_samples=N)` yields the *same* subset the Part-I numbers came from. It does **not** compute the Phase-1 audit statistics (box-per-caption / object-size distributions) — `data/audit.py` adds those on top at Phase 1 startup.
- **Alternatives considered:** (a) **Hard-wait for Phase 1** and hand the harness a synthetic / hand-written sample list — rejected: the anchor self-check (RQ-0.1) is only meaningful against the *real* seed-42 RefCOCO subset; a toy set can't reproduce the Part-I 82.5%. (b) **Inline the loader inside `eval/run.py`** — rejected: duplicates dataset logic the Phase-1 audit will need and re-introduces the copy-paste drift v2 exists to prevent. (c) **Pull the val subset from a cached file** — rejected: no such artefact exists and it would be one more un-versioned input.
- **Reasoning:** Phase 0 is the *fidelity harness*, and a fidelity harness is untestable without a real eval set, so the loader is a genuine Phase-0 dependency, not a Phase-1 land-grab. Keeping it strictly read-only respects the gate's intent — "no GPU *training* before the dataset audit" — while letting the harness self-check run. Lifting the exact subset construction is what makes the 85.0% (n=100) ≈ 82.5% (n=200) comparison valid. The Phase-1 work (audit stats baked into the schema) is purely additive on top.
- **Tradeoff / cost accepted:** A slice of `data/` is touched before its phase, so the module's docstring and this entry must flag the ordering so a reader doesn't assume the Phase-1 gate ran early. Risk that the Phase-1 audit later wants to refactor the loader — accepted as cheap (the read path is small and already shaped by the canonical schema).
- **Revisit when:** Phase 1 startup — fold the audit statistics in and confirm the loader's subset semantics still match what the audit assumes; if the audit needs a different split/shuffle, re-baseline the anchor in the same turn.

### 2026-06-17T12:00 — End-to-end toolchain: uv lockfile, file-based run manifests, pytest contract gate, pinned llama.cpp

- **Decision:** Settle the v2 *operational* toolchain before any Phase-0 code, so every result is reproducible and cross-backend-comparable by construction. (a) **Dependency management → `uv` + a fully-pinned lock.** Installed `uv` 0.11.21 (user-local at `~/.local/bin`, no sudo). Captured the live `.venv-ft` (89 pkgs, torch 2.6.0+cu124) into **`requirements-ft.lock.txt`** via `uv pip freeze` — locking *what already works* rather than re-resolving the painful cu124 stack — with `--extra-index-url https://download.pytorch.org/whl/cu124` recorded in the lock so the two `+cu124` wheels are findable. `requirements-ft.txt` stays the human-level direct-deps file (now also declaring the index); regenerate the lock with `make lock` after edits. (b) **Experiment tracking → plain per-run manifest files**, no tracking server: `grounding/manifest.py` (stdlib-only, like `contract.py`) writes `runs/<id>/manifest.json` + `run-card.md` (+ `results.json`) capturing git SHA + dirty flag, pinned llama.cpp commit, lockfile sha256, dataset sha256, full config, python/platform. (c) **Testing → `pytest`** (9.1.0, in `requirements-dev.txt` layered on `.venv-ft`, kept out of the runtime lock): `tests/test_contract.py` + `tests/test_manifest.py` (22 tests, green) lock the prompt byte-string, parser tolerance, IoU/center_std maths, and the manifest writer. (d) **llama.cpp pinned** to the Jetson checkout commit **`57fe1f07c3b6a1de3f4fff19098e2056a85275b7`** as a binding constant (`manifest.LLAMACPP_COMMIT`). (e) **Orchestration → `Makefile`** (`test/sync/dev/lock/env-ft`) over the already-installed `typer` + the dataclass `TrainConfig`; `.gitignore` updated so `runs/` checkpoints are ignored but the manifest/run-card/results text stays committed.
- **Alternatives considered:** (a) Deps: **keep `requirements*.txt` with no lock** (weakest reproducibility — the −23pp numbers wouldn't rebuild from the repo alone) or **`pip freeze` only, no uv** (works but forgoes uv's fast `pip sync` rebuild and the user chose uv). (b) Tracking: **MLflow-local** (adds a daemon + SQLite, metrics leave plaintext) or **W&B-cloud** (best UX but a cloud dependency; run data leaves the machine — at odds with the self-contained-notebook ethos) — rejected for a single-operator thesis where greppable/committable files are the deliverable. (c) Config/CLI: **Hydra/OmegaConf** — rejected as heavier than the dataclass-config + Typer already in hand. (d) Re-resolving deps via `uv pip compile` from the top-level requirements — rejected: would risk bumping transitive versions away from the validated cu124 stack; freezing the live env is the faithful "lock what works."
- **Reasoning:** The binding constraint of the whole v2 effort is *cross-backend comparability* — the fidelity gap is sensitive to the exact llama.cpp build and Python env, so "which bits ran" must be recoverable for every number. File-based manifests + a pinned lock + a pinned runtime commit make each run self-describing without standing infrastructure, matching the existing `results/` + `RESULTS.md` lab-notebook pattern. A pytest gate on the contract turns the "five copies silently diverged" Part-I failure into a CI-style guarantee that the prompt/parser/metric cannot drift. All choices favour plaintext, no daemons, no cloud — consistent with the stdlib-first, reproducibility-over-prose prime directive.
- **Tradeoff / cost accepted:** `uv` is a new user-local tool dependency (documented; mitigated by being a standalone binary, not a global pip install). The lock pins *exactly* the current stack, so intentional upgrades now require a deliberate `make lock` + re-baseline of parity. File manifests have no comparison UI (accepted: `git diff`/`grep` across run-cards suffices at this scale). pytest adds a dev dependency, isolated in `requirements-dev.txt`.
- **Revisit when:** Run volume grows past what grepping run-cards can manage (then reconsider a local MLflow over the same manifests); or a Phase-0 model candidate needs deps the locked `.venv-ft` can't satisfy (then a second venv + its own lock); or the llama.cpp pin is bumped (re-baseline the Phase-0 parity numbers in the same turn and log the new commit here).

### 2026-06-17T00:00 — Principled rebuild: branch `v2/principled-rebuild`, shared-contract package, fidelity-before-GPU workflow

- **Decision:** Halt the exploratory line and rebuild deliberately. (a) Consolidated Part I onto `main` (committed the uncommitted Stage 4 work, merged `stage3-refcoco-finetune`) and branched **`v2/principled-rebuild`** from it. (b) Tidied by **archive, never delete**: `git mv` the five per-stage trainers/exporters + `demo_nlcommand.py` → `experiments/legacy/`, and the research/handoff prose → `archive/research/`. (c) Stood up an importable `grounding/` package whose **`contract.py` is the single source of truth** (GROUNDING_PROMPT verbatim + parse_bbox + iou + center_std + constants), with `data/ eval/ train/ export/ deploy/ resolution.py` as **skeletons only** (typed signatures + `NotImplementedError`), each filled at the startup of its gated phase. (d) `DECISIONS.md`/`RESULTS.md` made append-only with a Part II demarcation (Part I untouched); `README.md`/`CLAUDE.md` updated with the v2 layout. The experiment arc is organised as gated **Phases 0–4** (fidelity harness → dataset audit → resolution → train → export/deploy).
- **Alternatives considered:** (a) **Keep iterating on the `stage3-*` branch** — rejected: five copies of the contract had already silently diverged and per-stage forks duplicated the loop; the next collapse would be invisible. (b) **Rewrite history / reset the ledgers** for a clean tree — rejected: violates the prime directive (the lab notebook must stay intact and linear). (c) **Delete the legacy scripts** — rejected for the same reason; they document results, so they are archived, not removed. (d) **Decide the model (SmolVLM vs PaliGemma/Florence-2/Qwen2-VL) and the resolution strategy now** — rejected: those are deferred to be settled *by measurement* in Phases 0 and 2, not by opinion up front. (e) **A fresh venv** — rejected: reuse `.venv-ft` (torch 2.6.0+cu124 is painful to rebuild).
- **Reasoning:** The two findings that actually stalled progress are *process* failures, not code-tidiness ones, and the structure is built to make them impossible to repeat. (1) **Deployment-runtime fidelity gap** — the skill dropped HF bf16 85% → GGUF F16 62% (−23pp, llama.cpp Idefics3 preprocessing) → Q8_0 55% (−7pp quant), and this was discovered *after* training; v2 puts a backend-agnostic fidelity harness (`eval/`) **before** any GPU run and picks the spine by the parity numbers. (2) **Tiny-object resolution ceiling** — 5–30 px → 2–11 px through a frozen SigLIP at 512; v2 makes resolution an explicit pre-registered variable (`resolution.py`). The shared contract guarantees prompt/parser/metric are byte-identical across probe/train/export/deploy, so every thesis number is comparable by construction. Designing backwards from deployment and de-risking cheaply before spending GPU is the explicit lesson from the ~20 h cross-domain detour.
- **Tradeoff / cost accepted:** Up-front scaffolding effort and indirection (a package + import discipline) before any new result; the skeleton-only modules mean nothing runs yet. The phased gates deliberately slow the path to the next training run in exchange for not burning GPU on an un-de-risked configuration. Reusing `.venv-ft` ties v2 to the existing pinned stack until a model candidate forces a change.
- **Revisit when:** A Phase-0 candidate model needs a dependency `.venv-ft` can't satisfy (then a second venv); or if the fidelity harness shows the GGUF preprocessing gap is unfixable for the chosen spine (then reconsider the runtime, not just the model). Per-phase decisions are logged as each phase fills.

---

# Part I — Exploratory (device campaigns + grounding Stages 1–4)

### 2026-06-17T00:00 — Stage 4 outcome: RefCOCO→RefDrone well-posed curriculum — G4-S4 NARROW MISS (19.5%), Stage 2 root cause eliminated

- **Decision:** Ran Stage 4 (`experiments/run_stage4_finetune.py`) — a curriculum fine-tune initialised from the Stage 3 RefCOCO-merged checkpoint (`./smolvlm_ft3`), LoRA on top at LR 1e-4 cosine, 3 epochs, on the **well-posed RefDrone subset only** (4,101 train / 439 val captions with exactly one non-empty box; multi-box ~8,238 + empty/negative 683 dropped). This is the structural mirror of the validated Stage 3 well-posed fix, applied in the aerial domain. **Outcome:** G1 parse_rate **PASS** (100%), G2b collapse sentinel **PASS** (center_std 211.5, flat ~211–214 across epochs — no recurrence of Stage 2 collapse), G4-S4 primary go/no-go **NARROW MISS** at **19.5% IoU@0.25** (gate ≥20%, −0.5pp). IoU climbed monotonically 12.5→16.0→19.5% with loss still descending (1.03→0.95→0.92) as cosine LR annealed to ~0. Merged checkpoint `smolvlm_ft4/` (1.01 GB). Full writeup: `results/stage4-refdrone-curriculum/train-log.md`.
- **Alternatives considered:** (a) **Largest-box augmentation** — keep multi-box captions, supervise the single largest box (→ ~12,339 samples); more data but a heuristic, possibly ambiguous target. (b) **Multi-box → list output schema** — breaks the single-`bbox` deployment contract shared with the probe/parser/Phase C. (c) **From-scratch from base** (`--init-from MODEL_ID`) instead of ft3 curriculum — kept as the RQ-S4.3 control arm, not run since the primary was borderline-positive. (d) **Higher input resolution** / **vision-encoder LoRA** — deferred next levers (the latter costs the mmproj GGUF-reuse property).
- **Reasoning:** parse_rate 100% + healthy center_std confirm the well-posed subset removed the Stage 2 ill-posed-target root cause at the source, in the aerial domain, with zero change to the deployment contract — the central methodological claim of the Stage 2→3→4 arc holds. 19.5% is a **~10× lift over the 2.0% RefCOCO-init cross-domain floor** (RQ-S3.4) and ~20× over the Stage 2 collapse (≈1%) — a substantive, measured aerial grounding skill on a 500M VLM with a frozen SigLIP encoder against 5–30 px objects (2–11 px after the 512 resize). The 0.5pp gate miss reads as a *training-budget / capacity* boundary, not a failure mode: IoU was still rising when the LR ran out.
- **Tradeoff / cost accepted:** The well-posed filter discards ~63% of RefDrone annotations → small train set (4,101), mitigated by the ft3 warm-start but likely the reason the gate was missed (curve still rising at LR→0). ~2.7 h GPU on the local RTX 3090. The result is 0.5pp short of the pre-registered gate — honestly recorded as a NARROW MISS, not rounded up.
- **Revisit when:** To clear the 20% gate, the pre-registered first fallback is **largest-box augmentation** (→ ~12,339 samples), since the miss looks data-limited; then **higher input resolution** to reduce the tiny-object information loss; then **vision-encoder LoRA** as a last resort. Export to GGUF + Jetson Phase C deferred until G4-S4 clears.

---

### 2026-06-16T10:40 — Stage 3 launched: re-diagnose Stage 2 as ill-posed target, switch to RefCOCO

- **Decision:** Run a corrected Stage 3 fine-tune (`experiments/run_stage3_finetune.py`) rather than stopping at the Stage 2 negative result. Re-diagnose the Stage 2 mode collapse as **two stacked causes** — (1, dominant) an *ill-posed target*: RefDrone is one-caption→many-boxes (~3.8 boxes/caption), so "one annotation = one sample" trained the model on the same (image,caption) with conflicting boxes, for which the marginal-mean box (mode collapse) is the correct loss-minimiser; (2) raw resized-pixel coordinates on 5–30 px tiny objects through a frozen encoder. Fix both: dataset → **RefCOCO** (`jxu124/refcoco` + COCO train2014, many-captions→one-box = well-posed, large objects); coordinates → **normalized 0–1000 integer bins** (PaliGemma/Florence convention); LoRA → **attention + MLP** (was attention-only) for capacity; unified prompt shared verbatim with the grounding probe and Phase C. Vision encoder stays frozen.
- **Alternatives considered:** (a) Accept Stage 2 FAIL and write up — superseded by the user's explicit handoff to fix the dataset and produce a competent next iteration. (b) Re-run RefDrone deduplicated to one-box-per-caption — still leaves tiny-object pixel regression and aerial-only data; weaker fix. (c) Unfreeze the vision encoder (the Stage 2 log's suggested fix) — rejected as the *first* lever because the reframed diagnosis pins the dominant cause on the target, not the encoder; freezing also preserves direct reuse of the existing mmproj GGUF (no vision re-export). (d) Swap to a grounding-native model (PaliGemma, Qwen-VL-grounding) — different model family, breaks the SmolVLM-500M-on-Jetson thesis thread.
- **Reasoning:** parse_rate=100% in Stage 2 proved the pipeline (data, label masking, LoRA loop) works; the failure was the objective, not the machinery. A well-posed objective is the cheapest, highest-leverage change and is testable on standard data with literature-comparable numbers. Normalized coords + large objects remove the secondary cause. Keeping vision frozen keeps the GGUF export path (reuse `mmproj-SmolVLM-500M-Instruct-f16.gguf`) intact and trainable params small. An explicit `center_std` mode-collapse sentinel is added to `evaluate()` so a recurrence is caught immediately rather than diagnosed post-hoc.
- **Tradeoff / cost accepted:** RefCOCO is ground-level COCO imagery, not aerial — Stage 3 proves the grounding *skill + coordinate protocol* can be learned at all, but introduces a domain gap to the aerial Phase A/C task (measured descriptively as RQ-S3.4, expected to show a penalty). ~10h more GPU on the local RTX 3090 (50k caption-box pairs, 1 epoch) + ~13 GB COCO download (authorized by the handoff). If SmolVLM-500M lacks the capacity, G2 still fails — but now as a *clean capacity-ceiling* result distinct from the ill-posed-target failure.
- **Revisit when:** (1) G2 (IoU@0.25 ≥ 30% on RefCOCO val) fails with healthy parse_rate + non-degenerate center_std → escalate to vision-encoder LoRA (Stage 4). (2) G2 passes but RQ-S3.4 aerial transfer ≈ 0 → RefCOCO→RefDrone(deduped) curriculum or a synthetic aerial grounding set. (3) GGUF parity G3 > 5pp → compare f16 / Q4_K_M. Full pre-registration: `results/stage3-refcoco-finetune/README.md`.

---

### 2026-06-16T10:00 — Stage 2 outcome: G2 FAIL — text-only LoRA insufficient for spatial grounding

- **Decision:** Accept the G2 gate failure (IoU@0.25=1%, gate ≥20%) as a valid negative result. Skip GGUF export and Jetson Phase A/C re-runs (G3/G4 gates are moot if grounding doesn't work). Document the finding and move to thesis write-up.
- **Alternatives considered:** (a) Run 1–2 more epochs with saved LoRA adapter (`smolvlm_ft/epoch1/`) — rejected: the failure is mode collapse driven by frozen vision features, not underfitting; more epochs will not fix the root cause and will cost another ~9h of compute. (b) Re-run with vision encoder unfrozen (add LoRA to `vision_model.*` layers) — plausible path, but significantly increases VRAM use and training time; out of scope for this thesis iteration. (c) Try a model with coordinate-aware visual tokens (SpatialVLM, Qwen-VL grounding) — different model family, different thesis scope. (d) Convert to GGUF and do Jetson Phase A anyway — no value: the model is known to predict constant boxes; Jetson inference would just reproduce the same collapse at lower throughput; the finding is already documented.
- **Reasoning:** parse_rate=100% confirms the training pipeline (data loading, label masking, LoRA training loop) is functioning correctly. The failure is specifically spatial: the frozen SigLIP encoder cannot update its spatial feature mappings, so the text backbone has no information gradient path to learn "where in the image is the target." The model converged to the trivial minimum of predicting the marginal mean training bbox. This is a well-documented failure mode for modular VLM fine-tuning (frozen vision + LoRA text) on localization tasks that require dense spatial correspondence.
- **Tradeoff / cost accepted:** 9.1h of GPU training for a negative result. This is thesis content: understanding *why* naive text-only LoRA fails on aerial grounding is itself a contribution. The result cleanly motivates either (a) vision-encoder fine-tuning or (b) using a model designed for grounding.
- **Revisit when:** If a Stage 3 is in scope, explore: (1) add `vision_model.encoder.layers.*.self_attn.*` to LoRA targets; (2) reduce learning rate to 5e-5 to avoid destabilising the encoder; (3) use 3+ epochs with warmup; (4) consider SpatialVLM or Qwen-VL-grounding as drop-in replacement.

---

### 2026-06-15T22:00 — Stage 2 fine-tuning: LoRA on SmolVLM-500M with RefDrone MDETR JSON + VisDrone images

- **Decision:** Fine-tune SmolVLM-500M-Instruct using LoRA (r=16, alpha=32) applied to the LLaMA text backbone's `q_proj, k_proj, v_proj, o_proj` layers. Load RefDrone annotations from the MDETR-format JSON files (`RefDrone_train_mdetr.json`, `RefDrone_val_mdetr.json`) distributed alongside the HuggingFace repo. Use a local `.venv-ft` venv with torch 2.6.0+cu124, transformers 5.12.1, peft 0.19.1, accelerate 1.14.0, bitsandbytes 0.49.2. Training runs on the local RTX 3090 24 GB, then merged checkpoint is SCP'd to the Jetson for GGUF conversion.
- **Alternatives considered:** (a) Full fine-tuning (all parameters) — ruled out: 511M parameters at bfloat16 = ~1 GB for weights alone; with gradients + optimizer states this exceeds 24 GB VRAM. (b) QLoRA (4-bit base + LoRA) — possible fallback if batch_size=2 + gradient accumulation causes OOM; bitsandbytes installed as optional dep. (c) Fine-tune on a subset of text backbone only (freeze vision encoder) — rejected: the vision encoder's aerial-image representations are also likely suboptimal; fine-tuning attention is the cheaper lever that still adapts cross-modal alignment. (d) Use `Idefics3ForConditionalGeneration` directly (the actual HF class for `idefics3` model_type) instead of `SmolVLMForConditionalGeneration` — `SmolVLMForConditionalGeneration` works fine and maps to the same underlying code; using the explicit SmolVLM class is cleaner in intent.
- **Reasoning:** (1) RefDrone dataset format: the `sunzc-sunny/RefDrone` HuggingFace repo stores annotations as individual `.txt` files inside zips for the HF streaming interface, but also ships three MDETR COCO-format JSON files (`RefDrone_{train,val,test}_mdetr.json`) that are directly loadable. `load_dataset()` fails because the streaming interface expects JSON Lines, not individual txt files. Directly loading the MDETR JSON is more reliable and gives richer metadata (image dimensions, tokens_positive, etc.). (2) SmolVLMProcessor.from_pretrained fails in transformers 5.12 with a video_processor_type error — AutoProcessor works and returns Idefics3Processor, which is functionally equivalent. (3) LoRA target modules confirmed from SmolVLM config: LLaMA text backbone with GQA (15Q heads, 5 KV heads); standard module names `q_proj, k_proj, v_proj, o_proj` are present. Trainable params: 4,161,536 (0.81% of 511M). (4) Dry-run smoke test passes: model loads, LoRA is applied, 1 forward pass with real processor output (loss = 4.35). (5) GGUF export: merge LoRA via `peft.PeftModel.merge_and_unload()` → save HF format → SCP to Jetson → `convert_hf_to_gguf.py --outtype q8_0` at commit `57fe1f0`. Verify GGUF parity (ΔIoU@0.25 ≤ 5pp) before calling Stage 2 complete.
- **Tradeoff / cost accepted:** Only the text backbone's attention layers are adapted — the vision encoder (SigLIP-based) is frozen. If the failure mode is vision-encoder representations (not cross-modal alignment), this fine-tuning won't help. This is a known risk (logged in `results/stage2-finetune/README.md` risk register). The fallback is to add `vision_model` layers to LoRA targets at the cost of more trainable parameters. Effective batch size = 16 (batch=2 × grad_accum=8) — small relative to dataset size (~46k non-empty annotations); may need ≥3 epochs.
- **Revisit when:** (1) OOM during training → switch to QLoRA or reduce batch; (2) Phase A re-run IoU@0.25 < 20% after 3 epochs → add vision encoder LoRA layers or increase r; (3) GGUF ΔIoU@0.25 > 5pp → try Q4_K_M instead of Q8_0.

---

### 2026-06-15T18:30 — Phase C Gazebo integration: decoupled render-only approach + gz transport Python bindings

- **Decision:** Implement the Phase C Gazebo rendering layer as a **decoupled, render-only** gz sim process. SITL runs with `--model quad` (same built-in physics as Phase B); Gazebo runs headless (`gz sim -s -r`). Python moves `downward_cam` and `target_rover` model poses every control frame via the `/world/phase_c/set_pose` gz transport service. SITL and Gazebo share no physics coupling.
- **Alternatives considered:** (a) Full ArduPilot-Gazebo coupling (`--model gazebo` + `libArduPilotPlugin.so`): SITL delegates physics to Gazebo, camera sensor built into the Iris model. Rejected: requires patching the ardupilot_gazebo world/model SDF to add a camera sensor, introduces complex FDMCC bridge handshake, and the ardupilot_gazebo Iris models have no built-in camera. (b) ROS 2 image bridge: gz→ROS→Python. Rejected: ROS overhead and extra dependency. (c) gz→socket bridge (custom C++ plugin): maintains render isolation but adds C++ build work.
- **Reasoning:** The decoupled approach reuses 100% of the Phase B SITL pipeline unchanged. All that changes is: (1) a headless gz sim process for rendering, (2) Python calls `_update_gz_pose()` to keep the camera and rover models in sync with SITL telemetry, (3) `_grab_gazebo_frame()` converts the gz transport `Image` callback (raw R8G8B8 bytes) to JPEG via Pillow. The gz Python transport bindings are confirmed available at `/usr/lib/python3/dist-packages/gz/` (Gazebo Harmonic 8.13.0, `transport13` + `msgs10`). The set_pose service uses a 50 ms timeout — well within the 50 ms control period at 20 Hz.
- **Tradeoff / cost accepted:** Camera pose is updated once per 20 Hz control frame (not continuously by the gz rendering thread). At 20 Hz copter motion is ≤0.05 m/frame, producing at most 1–2 px camera shift between pose updates at 10 m altitude — negligible for VLM grounding. The target rover NED position is programmatic, so the gz pose is the authoritative position (no physics drift).
- **Revisit when:** If per-frame pose calls at 20 Hz add measurable latency to the control loop (log loop_dt spikes > 10 ms in phase-c raw CSVs). Alternative: drop pose updates to 5 Hz in a background thread.

---

### 2026-06-15T17:30 — Phase C `run_phase_c.py`: async slot architecture, track-loss definition, re-seed test

- **Decision:** Build `experiments/run_phase_c.py` as a two-thread architecture: a 20 Hz control+track thread reading from a lock-protected `LatestDetectionSlot`, and a `~1 Hz` detection thread that writes either oracle injections (`--inject-oracle`) or live VLM calls (Gazebo frame → Jetson llama-server). Three specific design choices worth recording:
  1. **Track-loss events count empty-ByteTracker returns only** (not ID changes). With score=1.0 detections and the `_lost`-list re-detection pattern in ByteTrack, every 1 Hz injection creates a new track ID when the previous track has drifted to `_lost` after 30 frames (1.5 s). Counting ID changes would inflate the loss metric to equal the injection count. Pre-registered limitation (§3.4): "SmolVLM emits no confidence; score=1.0 for any parsed box; ByteTrack's low-score association unused."
  2. **Forced re-seed gap in run 3 of `--inject-oracle`**: injection pauses for `LOST_TIMEOUT_S + 1 = 4 s` at t=30 s, validates Branch-1 criterion 3 (re-seed < 2 s) reproducibly in a pre-registered run structure.
  3. **Gazebo frame-grabber left as `NotImplementedError` stub**: the exact gz transport topic name is not known until Gazebo Harmonic is installed. The stub raises a clear error with install instructions; `--inject-oracle` bypasses it entirely for the Branch-1 gate.
- **Alternatives considered:** (a) Import Gazebo Python bindings at module load time and mock them for `--inject-oracle` — rejected: couples the non-Gazebo code path to a not-yet-installed package. (b) Count ID changes as track-loss events (Phase B's definition) — rejected: produces misleading metric at 1 Hz VLM; honest to count only full-track-disappearance per the Phase C context. (c) Use `MAX_LOST_FRAMES = 60` in ByteTrack to match `LOST_TIMEOUT_S = 3.0 s` at 20 Hz — rejected: changing ByteTrack's constant without documenting it in the pre-registration would be an undocumented deviation; the 1.5 s drop is documented as a known difference.
- **Reasoning:** The `LatestDetectionSlot` stale-rejection (monotonic timestamp guard) was unit-tested for the read-returns-copy invariant, older-ts rejection, and same-ts rejection. The `xyxy_to_cxcywh` adapter was unit-tested for center, size, and degenerate (zero-size) boxes. The dry-run (`--inject-oracle --dry-run`) confirmed: Hz=20.31 ≥ 15, track-coverage=100%, coasting_max=19 ≥ 15, track-losses=0.
- **Tradeoff / cost accepted:** The live VLM path (`_vlm_grounding_thread`) and the Gazebo frame-grabber (`_grab_gazebo_frame`) are stubs — they raise `NotImplementedError` until Gazebo Harmonic is installed and the camera topic identified. The Branch-1 gate (`--inject-oracle`) is fully testable without Gazebo.
- **Revisit when:** Gazebo Harmonic is installed — implement `_grab_gazebo_frame()` against the real gz transport API (run `gz topic -l` to find the camera topic), then run Branch-1 in live mode to confirm the VLM path doesn't block the control thread.

### 2026-06-15T13:00 — Toy NL-command demo: scope, image source, and honest grounding claim

- **Decision:** Build `experiments/demo_nlcommand.py` as a lightweight orchestration
  layer over existing infrastructure (llama-server on Jetson, Phase A client helpers) with
  three command verbs (FOLLOW/ZOOM → VLM grounding; TURN → heuristic yaw with no VLM call).
  Tested on VisDrone nadir frames (the thesis target domain). Grounding failures reported
  honestly as the expected zero-shot result; not smoothed over or tested on easier imagery
  to manufacture a success.
- **Alternatives considered:**
  - (a) **Use non-aerial imagery** (street-level photo where SmolVLM might ground "white car")
    — rejected: the thesis target is aerial drone frames. Showing zero-shot success on a
    ground-level image would misrepresent the system's capability on the actual deployment
    domain.
  - (b) **Build as a full measurement campaign** with tegrastats, RESULTS.md device rows, and
    N-frame sweep — rejected: the demo's goal is pipeline validation and presentation, not a
    new benchmark. The latency numbers recorded in RESULTS.md (534 ms, 2046 ms) are real
    observations but not campaign-grade measurements (single calls, no spread).
  - (c) **Gate on VLM grounding working before writing the demo** — rejected: the pipeline
    mechanics (server lifecycle, async port-forward, command parsing, bbox parsing) are
    independent of grounding quality and are the deliverable. Grounding quality is a measured
    output, not a precondition.
- **Reasoning:** The toy demo serves two thesis purposes: (1) demonstrates the end-to-end
  pipeline concept for a committee/reader audience (TURN always works; FOLLOW/ZOOM show the
  VLM path firing); (2) records the honest zero-shot baseline that motivates Stage-2
  fine-tuning. Building it before the fine-tune exists is the correct sequence — it
  establishes what the zero-shot system does before fine-tuning changes it.
- **Tradeoff / cost accepted:** The demo is not visually impressive for FOLLOW/ZOOM on
  aerial imagery until Stage-2 fine-tuning is done. The honest outcome: TURN commands
  demonstrate the pipeline working; FOLLOW/ZOOM demonstrate the VLM path firing while
  being explicit that grounding fails zero-shot. This is documented in RESULTS.md and in
  `results/2026-06-15-toy-demo/README.md`.
- **Revisit when:** Stage-2 fine-tuned SmolVLM-500M GGUF is ready — re-run the demo
  with `--start-server` pointing at the fine-tuned weights; the rest of the pipeline is
  unchanged.

---

### 2026-06-15T09:30 — Phase B target: programmatic rover trajectory + gimbal-stabilized oracle camera

- **Decision:** Drive the Phase B target with a **programmatic** constant-velocity trajectory (0.25 m/s north, 0.5 m ahead) computed in the copter's own NED frame and anchored to the copter's captured (N,E) at each trial start, rather than reading the second SITL (ArduRover) instance's position telemetry. Pair this with a **gimbal-stabilized (nadir) oracle camera** — level roll/pitch fed into the projection, real yaw retained — modeling a 2-axis stabilized downward camera rather than an airframe-fixed one.
- **Alternatives considered:** (a) **ArduRover telemetry directly** — the two SITL instances don't share an NED origin (~584 m D discrepancy at CMAC home), so cross-instance position differencing is invalid without an uncalibratable frame offset. (b) **Body-fixed camera (real attitude into oracle)** — empirically diverged: ArduPilot's nose-down accel pitch (~13°) tilts a body-fixed camera, injecting `FOCAL_PX·tan(pitch) ≈ 130 px` of apparent target shift, far exceeding the true ~28 px offset and forming a positive-feedback loop (pixel error → vx → pitch → more apparent error → saturation; first live run hit 246 px mean, vx pinned at 3 m/s). (c) **Lower the P gain** to suppress pitch — treats the symptom, leaves the unstable mode in place.
- **Reasoning:** The programmatic trajectory sidesteps the cross-instance NED mismatch and makes runs self-consistent; anchoring to the copter's real (N,E) keeps the target in-frame from t=0 even as the copter drifts between runs. A gimbal-stabilized nadir camera is the standard tracking-UAV assumption and removes the attitude coupling at its source, touching only the oracle call site (not `oracle_bbox.py`). Yaw is kept because the body→NED velocity transform needs the true heading. With both in place: 19.99 Hz, 12.9 px mean error, 100% oracle coverage, 0 track losses across 3×60 s — **Phase B PASS**, threshold met honestly with no widening.
- **Tradeoff / cost accepted:** (1) The target is scripted, not a physics-simulated vehicle — Phase B validates the tracker→PID→MAVLink loop, not target dynamics. (2) The gimbal assumption means Phase B does not exercise attitude de-rotation; if Phase C's camera is **fixed-mount**, attitude compensation becomes a required, not-yet-validated pipeline step.
- **Revisit when:** Phase C uses a real/rendered **fixed-mount** camera (then add and validate attitude de-rotation) or needs a physics-driven target vehicle (then reconcile the two-instance NED frames or use a single combined sim).

Campaign-specific sub-decisions (honest pixel-error coverage gate, telemetry-drain bug fix, disabled yaw channel) are documented in `results/2026-06-14-stage1-baseline/phase-b-sitl.md` under `## Decisions`.

---

### 2026-06-15 — Phase B SITL toolchain: ArduPilot headless + local x86_64; no Gazebo for Phase B

- **Decision:** Use **ArduPilot SITL (ArduCopter/ArduRover, Copter-4.6.3, built 2026-06-15)** running headlessly on the **local x86_64 workstation (Ubuntu 24.04)**. No Gazebo for Phase B. Oracle bboxes are computed by geometric projection from SITL world-state telemetry, not from rendered video. pymavlink (offboard velocity setpoints) is the sole MAVLink interface. ByteTrack is implemented as a minimal in-repo Python module (~250 lines, numpy + scipy only). Gazebo Harmonic will be added for Phase C only if a real camera rendering is found necessary; the decision is deferred and documented as Phase C's first sub-task.
- **Alternatives considered:**
  - (a) **PX4 SITL**: Also mature and well-supported, but requires ROS2 for typical offboard workflows and has a heavier cmake build. CLAUDE.md specifies pymavlink directly; ArduPilot exposes the same offboard interface over raw MAVLink with less setup friction. PX4 is a valid alternative if ArduPilot SITL proves problematic, but there is no reason to prefer it here.
  - (b) **Gazebo Harmonic from the start**: Adds camera rendering and a physics-engine target vehicle but also adds ~1–2 hours of setup and a significant CPU draw during runs. Phase B only needs to validate that the MAVLink control loop achieves ≥1 Hz — no vision is in the loop yet. Oracle bbox from geometric projection is functionally equivalent for Phase B's success criterion.
  - (c) **Run SITL on the Jetson (aarch64)**: The Jetson has 153 GB free disk and 3.2 GB free RAM but only a 6-core Cortex-A78AE CPU. SITL + Gazebo + simultaneous VLM inference would exhaust RAM and compete heavily for CPU. aarch64 Gazebo pre-built packages are less mature. The Jetson is the *measurement device* for Phase C; running the simulation there as well conflates the measurement with the stimulus.
  - (d) **Pre-recorded video as camera feed (no SITL physics)**: Would validate VLM grounding (Phase A/C concern) but not the MAVLink offboard control loop — the drone's response to setpoints needs a dynamics model to close the loop. Ruled out for Phase B; acceptable as a supplementary offline probe in Phase C if needed.
- **Reasoning:** Phase B's sole job is to verify the tracker → PID → MAVLink loop works mechanically before the VLM is added. ArduPilot headless SITL on the local machine achieves this with the least external-dependency surface. A SITL vehicle responds to offboard velocity setpoints identically whether or not Gazebo is rendering it. The oracle bbox—computed from the SITL-reported world position of the target vehicle projected through a pinhole camera model—is functionally a perfect-perception upper bound, which is exactly what Phase B asks for. ArduCopter Copter is the controller mode; pymavlink sends `SET_POSITION_TARGET_LOCAL_NED` (type_mask: velocity + yaw_rate only). A second ArduRover SITL instance (port 5770) serves as the scripted ground vehicle at 2 m/s.
- **Tradeoff / cost accepted:** Without Gazebo, Phase B does not produce rendered camera frames — Phase C will need to revisit whether Gazebo is required or whether a pre-recorded aerial video over a similar scene can serve as the Phase C camera feed. This is the primary deferred cost. Also: headless oracle bbox bypasses any rendering/detection pipeline, so Phase B numbers represent an upper bound that VLM performance in Phase C will fall below by design.
- **Revisit when:** Phase C requires actual rendered camera frames (not just MAVLink position telemetry). If so, add Gazebo Harmonic with the `ardupilot_gazebo` plugin and log the Gazebo install as a new DECISIONS entry.

---

### 2026-06-15T08:10 — Phase A decision gate: S2 selected for Phase C fine-tuning

- **Decision:** Select SmolVLM-500M-Instruct Q8_0 (S2) as the fine-tuning target for Stage 2 (Phase C). The zero-shot baseline establishes that both SmolVLM models completely fail at drone grounding without fine-tuning.
- **Alternatives considered:** (a) S1 (SmolVLM-256M-Instruct Q8_0) — smaller, faster (3.58 Hz), but parse rate 0% with no bbox-structure in responses; (b) S2 (SmolVLM-500M-Instruct Q8_0) — slower (1.20 Hz), parse rate 4%, but generated bbox-like coordinate structures in most responses (using single-quoted Python dicts, failing JSON parser — not complete absence of grounding representation); (c) pursue prompt engineering before fine-tuning — ruled out because the binding constraint is zero localization signal, not output formatting.
- **Reasoning:** Both models fail the IoU@0.25 < 30% threshold (both 0%). Both also fail the parse-rate < 50% threshold (S1: 0%, S2: 4%). Under the pre-registered decision gate, fine-tuning is therefore load-bearing and Stage 2 is the thesis centerpiece. S2 is preferred over S1 because it demonstrated latent awareness of coordinate output structure in its raw responses — it generated `{'x1': ..., 'y1': ..., 'x2': ..., 'y2': ...}` and `{'bbox': [x,y,x2,y2]}` patterns consistently. S1 produced only free-text descriptions. S2's structure suggests the fine-tuning signal has something to anchor to. S2 also fits comfortably in RAM (2734 MB, no swap). The speed gap (1.20 Hz vs 3.58 Hz) is acceptable for evaluation runs and expected to narrow post-quantization if needed.
- **Tradeoff / cost accepted:** S2 runs more slowly at inference. At 1.20 Hz unquantized on the zero-shot probe, fine-tuned performance will depend on whether llama.cpp can export and run the fine-tuned weights at similar speed. The slower rate is within the thesis's 0.5–2 Hz target range for drone control.
- **Revisit when:** Phase C fine-tuning results show S2 fails to converge or occupies too much RAM in the fine-tuned form — then fall back to S1.

---

### 2026-06-14 — PaliGemma excluded from Stage 1; SmolVLM-only grounding path

- **Decision:** Remove PaliGemma (v1 and v2) from the Stage 1 grounding candidate list. Stage 1 Phase A will evaluate SmolVLM-256M Q8_0 and SmolVLM-500M Q8_0 only.
- **Alternatives considered:** (a) Use a custom llama.cpp build that includes PR #7553; (b) Proceed with SmolVLM-only path as pre-planned in the risk register.
- **Reasoning:** PaliGemma support in llama.cpp (PR #7553 by abetlen) is unmerged draft code as of 2026-06-14 — the maintainer deferred it pending a new vision API initiative. The controlled variable for this thesis is llama.cpp commit `57fe1f0`, which predates and excludes PR #7553. A custom build would break the controlled-variable invariant and introduce untested code. Additionally, no GGUF conversion of PaliGemma **2** (the model specified in the plan) has been published; the only available GGUF (`abetlen/paligemma-3b-mix-224-gguf`) is PaliGemma v1. This is exactly the risk the register anticipated: "PaliGemma fails to load in current llama.cpp commit."
- **Tradeoff / cost accepted:** We lose one data point (the potential accuracy ceiling from PaliGemma's native `<loc>` detection vocabulary). Phase A now answers: "What is the zero-shot ceiling for SmolVLM?" rather than "which of PaliGemma or SmolVLM is better?" The fine-tune target for Stage 2 will be SmolVLM-500M (or 256M if 500M underperforms). If PaliGemma GGUF support matures before Stage 2 fine-tuning, revisit.
- **Revisit when:** (1) A community GGUF for PaliGemma-2-3B-mix-224 is published AND (2) PaliGemma support is merged into llama.cpp mainline (or we decide to adopt a specific fork). At that point, add it as an optional Phase A extension rather than a controlled variable.

### 2026-06-14 — RefDrone HF dataset repo ID correction

- **Decision:** Use `sunzc-sunny/RefDrone` as the RefDrone dataset source, replacing `sun-langwei/RefDrone` cited in the Stage 1 README.
- **Alternatives considered:** None — the original ID returns HTTP 401; the correct ID was confirmed from the project's GitHub page.
- **Reasoning:** The Stage 1 README noted the repo as `sun-langwei/RefDrone` "or equivalent" with a flag that it was unconfirmed. Phase 0-C found the correct repo: the GitHub project (`github.com/sunzc-sunny/refdrone`) links explicitly to `huggingface.co/datasets/sunzc-sunny/RefDrone` (CC-BY-4.0, appears public). Additionally: RefDrone annotations do NOT bundle images — VisDrone 2019-DET images must be downloaded separately and matched by filename.
- **Tradeoff / cost accepted:** Minor extra download step (VisDrone images). No methodological impact.
- **Revisit when:** N/A — factual correction.

---

### 2026-06-14T20:00 — Gemma-4 E2B/E4B are thinking models; disable reasoning for VLM campaign

- **Decision:** Re-run V4 (Gemma-4-E2B) and V5 (Gemma-4-E4B) with `--reasoning off` passed
  to `llama-server`. Initial runs (thinking enabled, default) produced empty `content` fields
  — all 50 `max_tokens` were consumed by the `reasoning_content` chain-of-thought scratchpad.
- **Alternatives considered:** (a) increase `max_tokens` to 500–1000 to let thinking complete;
  (b) disable thinking with `--reasoning off`.
- **Reasoning:** For drone command generation, latency is the binding constraint (0.5–2 Hz
  target). Thinking mode adds hundreds of ms of per-token decode on top of the CLIP encode and
  prefill cost. A drone controller cannot budget extended reasoning on every camera frame.
  `--reasoning off` (llama-server 57fe1f0 flag, also `--reasoning-budget 0`) is the correct
  deployment configuration. The initial invalid runs are retained in the campaign README as a
  documented negative result.
- **Tradeoff / cost accepted:** With reasoning disabled, grounding quality may be slightly lower
  than thinking mode. Capability samples from the re-run suggest quality is acceptable for the
  "follow that object" task.
- **Revisit when:** If a future use case can tolerate >3 s latency per frame AND benefits from
  the reasoning overhead (e.g., complex scene parsing), re-enable thinking and increase
  `max_tokens` accordingly.

### 2026-06-14T22:00 — Install ffmpeg on Jetson for llama-server image decoding

- **Decision:** Install `ffmpeg` on the Jetson (`sudo apt install -y ffmpeg`).
- **Alternatives considered:** (a) pass image file paths via `file://` URL (blocked by server unless `--media-path` set, and then limited to that directory); (b) rebuild llama.cpp with a different image backend; (c) install ffmpeg.
- **Reasoning:** `llama-server` uses `ffprobe` (part of ffmpeg) to detect image/audio/video format when loading from base64 buffers. Without it, the server returns "Failed to load image or audio file" on every image request. ffmpeg is standard dev tooling with no downside.
- **Tradeoff / cost accepted:** None significant. ffmpeg is ~50MB installed.
- **Revisit when:** Never — this is a permanent tooling dependency for VLM work on the Jetson.

### 2026-06-14T21:00 — VLM measurement instrument: llama-server, not llama-mtmd-cli

- **Decision:** Use `llama-server` + Python `urllib` client as the timing instrument. `llama-bench` and `llama-mtmd-cli` were ruled out.
- **Alternatives considered:** (a) `llama-bench` (no image support confirmed); (b) `llama-mtmd-cli --perf -v` (single-shot only, can't do warm multi-frame); (c) `llama-server` with `cache_prompt: false`.
- **Reasoning:** `llama-bench` has no `--image` flag (confirmed). `llama-mtmd-cli` can only do single-shot inference per process invocation; two separate processes each pay CUDA graph compilation (~180ms), making warm-state measurement impossible from the CLI. `llama-server` keeps the model and CUDA graphs loaded across requests; `cache_prompt: false` ensures each request processes the full prompt from scratch (correct model for per-frame drone use). `timings.prompt_ms` in the `__verbose` response field includes CLIP encode time (verified empirically: `prompt_ms + predicted_ms ≈ wall-clock`). Also confirmed that `llama-mtmd-cli -hf` requires HTTPS (not built in `57fe1f0`), so model downloads must be done via `wget`.
- **Tradeoff / cost accepted:** `llama-server` adds small JSON serialization overhead (measured <10ms). Requires `ffmpeg` for image decoding (installed 2026-06-14).
- **Revisit when:** A later llama.cpp build adds image support to llama-bench with per-frame timing.

### 2026-06-14T21:00 — Architecture fork deferred to empirical result

- **Decision:** Defer the end-to-end-VLM vs. decomposed (detector + LLM) architecture decision to the VLM feasibility campaign result. The campaign's measured per-frame latency vs. required control rate (0.5–2 Hz) is the decision criterion. Not pre-deciding in favour of either architecture.
- **Alternatives considered:** (a) Adopt decomposed immediately (YOLO + LLM) as the practical choice; (b) adopt end-to-end VLM as the thesis-coherent narrative choice; (c) this — run the experiment and let the numbers decide.
- **Reasoning:** The 0.5–2 Hz control rate target is plausible even at 500 ms–2 s per-frame (the drone's own controller holds between high-level updates). A SmolVLM-256M smoke test produced a rough additive lower bound of ~744 ms (277 ms CLIP + 362 ms prefill + 105 ms decode) on a **cold, single-slice 512×512 image with a 14-token decode** — this is NOT a warm per-frame measurement (CUDA graph compilation fired mid-generation), underestimates image token count at campaign resolution (1280×720 will tile into more slices), and uses a shorter decode than the campaign will. **Do not interpret as "1.3 Hz viable."** A warm, 1280×720, 30-token measurement is required before any viability claim. Deciding before measuring would bias the framing. "End-to-end VLM can't close a tracking loop" is a valid thesis finding if the data show it; the decomposed path is the fallback documented in the thesis, not the default assumption.
- **Tradeoff / cost accepted:** Thesis narrative depends on what the data show. If end-to-end is too slow, the decomposed path needs its own measurement campaign.
- **Revisit when:** VLM campaign results are in. Decision criterion: if best-fitting VLM warm per_frame_ms ≤ 2000 ms AND grounding is correct → end-to-end viable; otherwise → document why decomposed is necessary.

---

### 2026-06-14T19:30 — Fix footprint parser (compute double-count) and drop --verbose from load probe

- **Decision:** Remove `--verbose` from the `_capture_load` command in `run_gemma_sweep.py`, and fix `parse_llama_load_buffers` in `parsers.py` to use **last-wins for compute buffers** and **zero-filtered accumulation for KV buffers** (skipping the probe pass's all-zero KV lines).
- **Alternatives considered:** (a) keep `--verbose` and filter by timestamp/pass; (b) take only the first occurrence of each buffer type; (c) this — minimal targeted fix with clear reasoning per field.
- **Reasoning:** llama.cpp runs two allocation passes per load: a probe/dry-run (model=0, KV=0, compute=real) and the real allocation (model=real, KV=real, compute=real). The original accumulating parser double-counted compute buffers (probe_value + real_value = 2×real). `--verbose` was intended to surface buffer-size lines, but those lines appear in normal (non-verbose) output anyway; `--verbose` only added GGML per-tensor debug output (2.3 GB for G2, 425 MB for G3) that flooded SSH buffers and left a stray llama-cli process on the Jetson for >10 min. Without `--verbose`, logs are tens of KB per model. Side effect of the stray process: it consumed 3.3 GB of RAM on the Jetson, causing subsequent footprint re-runs to falsely OOM.
- **Tradeoff / cost accepted:** The G2 footprint numbers come from the original (verbose) log parsed with the fixed parser (only 14 buffer-size lines in 2.3 GB, confirmed by grep). G4 cannot be measured with `--no-mmap` regardless of verbose flag (4.7 GiB malloc > free RAM on 8 GB Jetson); tegrastats 4374 MB remains the best estimate for G4.
- **Revisit when:** llama.cpp changes its buffer-reporting format, or a tegrastats-inline footprint approach makes the separate probe run unnecessary.

### 2026-06-14T18:30 — Correct two tegrastats-derived metrics post-hoc (swap + footprint), don't re-run the sweep

- **Decision:** After the gemma-family sweep, fix **two derived metrics in place** rather than re-running the campaign: (1) swap detection switched from `any(swap > 0)` to **growth over idle baseline** (`swap_growth_mb`, 50 MB threshold); (2) **true footprint** for RQ-G3 re-measured authoritatively via llama.cpp's own per-buffer load report (`--no-mmap --verbose`, new `--footprint` mode) instead of trusting tegrastats peak-RAM sampling. Directly measured throughput/power/TTFT numbers stand unchanged.
- **Alternatives considered:** (a) full re-sweep of all five units; (b) leave the numbers and footnote the caveats; (c) this — targeted parser fix + a ~20 min footprint-only re-run of G2/G3/G4 (+ G5 partial-offload probe).
- **Reasoning:** The expensive, device-bound measurements (pp/tg/TTFT/power) were never in question — only two *derived* fields were wrong: swap was a flat ~300 MB pre-existing baseline mis-flagged on every unit, and tegrastats RAM under-counts mmap'd weights (E2B's 2968 MB < its 3194 MB GGUF, an impossibility for resident weights). A full re-sweep would burn hours reconfirming good data. RQ-G3 (true PLE footprint) is the campaign's headline question, so it alone justified a small, focused re-measure using the runtime's own allocation report (authoritative, no sampling).
- **Tradeoff / cost accepted:** Footprint comes from a separate `--no-mmap` run, not the original benchmarked run, so it's a *characterisation* of the same model+ctx rather than a byte-exact reading of the benchmarked process. `--no-mmap` also changes the load path vs the original (mmap) runs — acceptable because we want the resident-allocation breakdown, which mmap obscures.
- **Revisit when:** the harness is changed to capture llama.cpp buffer sizes inline during the main benchmark run (would make the separate footprint pass unnecessary); or a quant-sensitivity sub-study re-runs these models anyway.

### 2026-06-14T17:00 — llama.cpp build gate for Gemma 4 (no rebuild required)

- **Decision:** Proceed with the existing `57fe1f0` llama.cpp binary for the Gemma-family sweep, including Gemma 4 (E2B/E4B) units. **No rebuild.**
- **Alternatives considered:** (a) Rebuild at a later commit with explicit Gemma 4 QAT GGUF testing; (b) proceed and fall back to rebuild only on runtime failure.
- **Reasoning:** Inspected `src/llama-arch.cpp` on the device at commit `57fe1f0`; the file contains `GEMMA4` and `GEMMA4_ASSISTANT` architecture enum entries and their string mappings. Gemma 4 shipped 2026-04-02 and QAT checkpoints 2026-06-05; `57fe1f0` post-dates both. The §7 gate in the campaign README is satisfied by source inspection rather than a live load probe. If a runtime failure occurs (e.g. `unknown tensor`), rebuilding at the latest commit is pre-approved and must be documented per the campaign README §7 protocol: record new commit hash, build flags, and note the runtime variable change on all affected rows.
- **Tradeoff / cost accepted:** Source inspection is not as definitive as a live model load. If Gemma 4 QAT GGUFs use a tensor name introduced after `57fe1f0`, we will learn this at runtime (unit G3/G4 will error). The fallback (rebuild) is low-risk.
- **Revisit when:** Unit G3 or G4 fails with an architecture/tensor error at runtime — at that point, rebuild, update this entry, and re-run.

### 2026-06-14T13:30 — Use llama-completion (not llama-cli) for TTFT measurement

- **Decision:** Switch the TTFT capture command from `llama-cli -no-cnv` to `llama-completion -no-cnv`, redirect stdin from `/dev/null` on the remote command, and add `stdin=subprocess.DEVNULL` to all local SSH subprocess calls.
- **Alternatives considered:** (a) keep `llama-cli` with different flags; (b) use `llama-server` endpoint; (c) parse TTFT from `llama-bench` output.
- **Reasoning:** `llama-cli` in build `57fe1f0` dropped `-no-cnv` support and dropped users into an interactive loop that flooded stdout indefinitely. `pkill -f tegrastats` was also replaced with `pkill tegrastats` (name-only match) because `-f` matched the word "tegrastats" in the SSH shell's own argv, killing the SSH connection (exit 255). The timing format changed in `llama-completion` (timestamp prefix; comma decimal separators from European locale); `parsers.py` was updated to handle both old and new formats.
- **Tradeoff / cost accepted:** TTFT prompt is ~9–11 tokens (short-prompt latency), not a 512-token prefill. Values (38–204 ms) represent latency lower bounds.
- **Revisit when:** llama.cpp is rebuilt; recheck if `llama-cli` restores `-no-cnv`.

### 2026-06-14T13:30 — Sequential automated sweep via run_campaign.py (not per-unit run cards)

- **Decision:** Run the 10-model sweep via `experiments/run_campaign.py` Python orchestrator rather than the isolated-Claude-session methodology designed 2026-06-13.
- **Alternatives considered:** The run-card / isolated-session methodology (see below).
- **Reasoning:** The orchestrator was already written, thoroughly debugged, and covers the full protocol. `run-unit.sh` driver was not yet built. Single device means no parallelism benefit from fan-out. The orchestrator produced identical data with less setup friction.
- **Tradeoff / cost accepted:** No per-unit context isolation. Acceptable because the orchestrator is deterministic code, not a language model that can drift between units.
- **Revisit when:** A campaign needs per-unit qualitative judgment (e.g. §7 capability eval) — then isolated Claude sessions are more appropriate.

### 2026-06-13T15:05 — Execute each experiment unit in a fresh, isolated Claude session

- **Decision:** Adopt an **isolated-session execution methodology** (in `experiments/`): every
  campaign is decomposed into independent **units** (for the model sweep, one unit per model),
  and **each unit is run by a freshly spawned, cold Claude session** initialized only from
  `CLAUDE.md` + a single self-contained **run card**. The repo filesystem is the message bus —
  run cards in, result blocks / `RESULTS.md` rows / raw logs out; no session shares another's
  in-memory context. A constant `bootstrap-prompt.md` enforces the restriction (one unit only,
  capture failures, fulfil the output contract, then STOP; BLOCKED+stop on ambiguity, never
  guess). Cards carry `status:` (TODO/RUNNING/DONE/FAILED/BLOCKED) as the single source of
  truth; `run-unit.sh` / `run-campaign.sh` spawn sessions via `claude -p`, sequential and
  resumable.
- **Alternatives considered:** (a) one long-lived session driving all ~10 models; (b) Agent-tool
  sub-agents fanned out from an orchestrator session; (c) this — independent headless `claude -p`
  sessions per unit.
- **Reasoning:** Fresh context per unit is an **experimental control**, not just tooling: it
  eliminates cross-run context contamination (earlier models' numbers/debugging can't bias later
  setup or interpretation) and forces every unit through the identical protocol by construction.
  It also stays within context budget (a 10-model sweep would overflow one session) and is
  reproducible/resumable (a unit = a versioned file; re-run = re-spawn). (a) contaminates and
  overflows; (b) keeps a long-lived orchestrator whose context still grows per spawned summary,
  and the Jetson is a single device so the fan-out parallelism sub-agents buy is unusable anyway.
- **Tradeoff / cost accepted:** Each unit pays cold-start overhead (re-reads `CLAUDE.md`,
  re-derives device state) and no live cross-unit synthesis — synthesis is a separate pass that
  reads the on-disk results. Hands-off runs default to `--permission-mode bypassPermissions`,
  acceptable only because this is the operator's own testbed device with a scoped sudo allowlist;
  tighten via `CLAUDE_PERM=acceptEdits` + `--allowedTools` if needed.
- **Revisit when:** A campaign genuinely needs live cross-unit reasoning mid-run (→ orchestrator +
  sub-agents), units can run concurrently on independent hardware (→ parallel dispatch), or the
  cold-start re-derivation cost becomes material (→ a cached device-state preamble).

---

### 2026-06-13T14:42 — Sudo on the Jetson: scoped passwordless for bench commands

- **Decision:** `jfdg` has NOPASSWD sudo for a tight, full-path command allowlist only,
  via `/etc/sudoers.d/10-jetson-bench` — `/usr/sbin/nvpmodel`, `/usr/bin/jetson_clocks`,
  `/usr/bin/tegrastats` (a `BENCH_CMDS` `Cmnd_Alias`). Everything else still requires the
  password. Expand the allowlist by adding a tool's absolute path to `BENCH_CMDS`, then
  `sudo visudo -cf /etc/sudoers.d/10-jetson-bench`. This is a consolidation of three
  same-day decisions: (1) full passwordless installed, (2) reverted once the device became
  reachable off-LAN via Tailscale, (3) scoped allowlist restored hands-off automation
  without standing full root.
- **Alternatives considered:** Blanket `NOPASSWD: ALL`; no NOPASSWD (pipe via `sudo -S`
  every time); this scoped allowlist.
- **Reasoning:** The scoped allowlist is the right balance now that the node is reachable
  off-LAN (Tailscale): it keeps power-mode flips, clock locking, and `tegrastats` logging
  hands-off while full paths + a curated alias keep the blast radius small and the intent
  auditable.
- **Tradeoff / cost accepted:** Any new privileged tool needs a one-line edit + re-validate
  before automation can use it passwordless — that friction is intentional (forces a
  conscious choice to widen privilege). File installed `0440 root:root`; `visudo -c`
  validates all of `/etc/sudoers.d/` OK.
- **Revisit when:** A new benchmark tool needs root (expand `BENCH_CMDS`); the allowlist
  grows large enough to warrant rethinking the trust model; or the device is repurposed
  or exposed to an untrusted network.

---

### 2026-06-13T14:30 — Remote access to the Jetson via Tailscale (WireGuard mesh)

- **Decision:** Enrolled the Jetson into the operator's existing Tailscale tailnet
  (account `javier.fco.dibo.gomez@`) for access from outside the LAN. Transport-only: no
  Tailscale-SSH/ACL mode — the existing OpenSSH `sshd` + `~/.ssh/jfdg01` key are
  unchanged; Tailscale only provides the network path. Brought up with
  `tailscale up --hostname=jetson --accept-dns=false`. Jetson tailnet IP: `100.127.45.66`.
  3090 workstation already on the tailnet (`100.103.89.71`). Added SSH alias
  `jetson-remote` → `100.127.45.66` (raw tailnet IP, not MagicDNS) in `~/.ssh/config`;
  LAN alias `jetson` → `192.168.1.136` retained for local low-latency use. Key expiry
  should be disabled for the `jetson` node in the Tailscale admin console (Machines →
  jetson → Disable key expiry) so the testbed doesn't drop off at the default ~180-day
  expiry.
- **Alternatives considered:** (a) Tailscale mesh; (b) Cloudflare Tunnel; (c) reverse SSH
  through a VPS (autossh/systemd); (d) public port-forward + DDNS.
- **Reasoning:** Tailscale needs no port-forwarding/router access, traverses NAT/CGNAT,
  self-heals across reboots and IP changes, gives a stable `100.x` address, and the 3090
  was already enrolled (zero account setup). It doesn't widen the public attack surface
  (no internet-facing sshd), unlike (d). Used the raw tailnet IP rather than a MagicDNS
  hostname because the tailnet reports a DNS health warning ("can't reach configured DNS
  servers"); a raw IP removes the DNS dependency entirely. `--accept-dns=false` so the
  broken MagicDNS resolver can't affect the Jetson's name resolution.
- **Tradeoff / cost accepted:** Dependency on a third-party coordination service (Tailscale
  control plane) and on the operator's identity provider for node auth. No hostname
  convenience until MagicDNS is fixed (raw IP only). Combined with the scoped
  passwordless-sudo entry, the device is now privileged-command-accessible from anywhere
  on the tailnet — acceptable because tailnet membership is gated by the operator's SSO
  and the device key.
- **Revisit when:** MagicDNS is fixed (switch alias to a hostname); or if a
  self-hosted/no-third-party path becomes a requirement (→ reverse SSH + VPS); or the
  device is exposed to an untrusted network.

---

### 2026-06-13T14:17 — Upper bound = 15 W with locked clocks

- **Decision:** Treat the **15 W locked-clock** config as today's upper bound. Did **not**
  enable 25 W MAXN_SUPER this session.
- **Alternatives considered:** Enable MAXN_SUPER via firmware/bootloader update + updated
  nvpmodel profile.
- **Reasoning:** The active nvpmodel profile (`p3767-0003`) only defines 15 W/7 W;
  unlocking Super requires a bootloader/firmware update. A failed flash leaves the device
  unbootable, and physical access is not available to recover from a brick.
- **Tradeoff / cost accepted:** Today's "upper bound" is the 15 W ceiling, not the absolute
  silicon ceiling. The 25 W Super number will be a separate, higher data point in a later
  session.
- **Revisit when:** A session where a firmware update is reasonable (physical access
  available as a fallback).

---

### 2026-06-13T13:50 — Build llama.cpp natively on the Orin, not cross-compiled locally

- **Decision:** Build llama.cpp directly on the Jetson (aarch64, CUDA `sm_87`) rather than
  building on the x86_64 workstation and copying the binary over.
- **Alternatives considered:** (a) Native on-device build; (b) cross-compile on the x86_64
  box with an aarch64 toolchain; (c) NVIDIA `jetson-containers` prebuilt images.
- **Reasoning:** Binaries are architecture-specific — an x86_64 build can't run on the ARM
  Orin. A correct cross-compile needs an aarch64 cross-toolchain + aarch64 CUDA target
  libs, which is fragile and slower to set up than the native build already underway.
  Critically, llama.cpp is built once and reused across all ~10 models — it's a one-time
  cost, not per-model.
- **Tradeoff / cost accepted:** Native build is slow on the 6-core CPU (~15–25 min, CUDA
  kernel compilation dominates). Accepted because it's one-time.
- **Revisit when:** We need frequent rebuilds (tracking llama.cpp master, sweeping build
  flags) — then switch to `jetson-containers` or a beefier aarch64 build host.

---

### 2026-06-13T13:45 — Runtime: llama.cpp (CUDA), not Ollama

- **Decision:** Use llama.cpp built with CUDA as the benchmarking runtime.
- **Alternatives considered:** Ollama (quick); llama.cpp (CUDA); both.
- **Reasoning:** `llama-bench` gives clean, separated prefill (pp) vs decode (tg)
  throughput and is the standard for reproducible thesis numbers. Ollama exposes only a
  coarser eval rate and adds overhead.
- **Tradeoff / cost accepted:** More setup (cmake install + on-device CUDA build).
- **Revisit when:** We want an easy-to-reproduce cross-check — add Ollama as a secondary,
  looser data source.

---

### 2026-06-13T13:40 — Headline model: Llama-3.2-3B-Instruct Q4_K_M

- **Decision:** Use Llama-3.2-3B-Instruct `Q4_K_M` as the first/most-solid general model.
- **Alternatives considered:** Llama-3.2-1B (max raw tok/s); Qwen2.5-7B (capability
  ceiling, tight fit).
- **Reasoning:** Best balance of "genuinely useful" and "fits 8 GB comfortably with KV
  headroom" — the README sweet spot. ~9 more models follow to cover the size/quant
  spectrum.
- **Tradeoff / cost accepted:** Not the absolute max-tok/s point (a 1B would be faster) nor
  the capability ceiling (7B) — those are separate data points in the broader sweep.
- **Revisit when:** Running the broader ~10-model sweep.
