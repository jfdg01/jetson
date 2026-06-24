# T1 — Data & temporal contract (Part III)

**Status:** ✅ **GATE PASS** (2026-06-18). T1b (temporal contract) pytest-locked;
T1a (scored clip set + memoryless baseline) implemented & self-checked.
**Branch:** `v3/object-permanence`.
**Prereq:** T0 (cadence & dynamics) gate PASS — anchor spine = Qwen2-VL-2B Q8_0 @ 512,
two-tier architecture mandatory, re-acquisition event-triggered
(`results/2026-06-18-t0-cadence/README.md`, DECISIONS 2026-06-18T13:30).

T1 makes the Part III goal **measurable**: it turns "keep a lock on the white van" into
numbers a gate can read. Two halves, in dependency order:

- **T1b — temporal metric contract** *(this turn)*: extend `grounding/contract.py`
  (never fork) with the §6 temporal primitives and pytest-lock each, mirroring how the
  single-frame metric is locked today. Pure-Python, stdlib-only, deterministic — fully
  verifiable now without Gazebo or GPU. **This is the cheapest, foundational slice and
  is done first** (the "de-risk cheaply" discipline).
- **T1a — scored SITL clip set** *(next)*: a small, reproducible set of referring-video
  clips (white van target + ≥1 same-class distractor; the four permanence stressors;
  free per-frame oracle GT via `oracle_bbox.py`; fixed seeds), rendered in Gazebo
  Harmonic (confirmed available locally: `gz` = Gazebo Sim 8.13.0).

## Why this ordering

The metrics must exist and be locked *before* the clips, so the clip recorder can be
validated against a known-good scorer and so "reproducible temporal metrics" (the gate
text) has a concrete, tested meaning. The metrics are also the only T1 piece that needs
neither the renderer nor the GPU, so they de-risk the gate at zero cost.

## RQs

- **RQ-T1.1** — Can the §6 temporal metric suite (SOT success/precision, ID-switch
  count, identity purity, re-acquisition time, oracle-coverage, following error,
  track-loss events) be expressed as pure, deterministic functions over a per-frame
  `(pred_box, gt_box, visible, locked_id)` stream, and pytest-locked like the
  single-frame metric? *(T1b)*
- **RQ-T1.2** — Does the SITL clip recorder produce a deterministic, replayable dataset
  (frames + `labels.jsonl` + `manifest.json`) whose oracle GT, scored by the T1b
  metrics, reproduces stable numbers across re-runs at a fixed seed? *(T1a)*
- **RQ-T1.3** — Do the clips actually contain the four permanence stressors at
  measurable severity (occlusion duration, out-of-frame events, scale-change rate,
  same-class distractor proximity), per the T0c dynamics envelope? *(T1a)*

## Controlled variables

- Coordinate convention: normalized boxes use `COORD_SCALE = 1000` from
  `grounding/contract.py` (anchor and GT share one convention).
- Camera intrinsics: `oracle_bbox.py` (IMG_W=640, IMG_H=480, FOV_H=60°, focal≈554 px) —
  identical to the SDF `downward_cam`, so the projected box is a frame-synced label.
- Single-frame IoU@0.25 (`IOU_GATE_THRESHOLD`) retained **only** as a per-anchor sanity
  check; the headline metrics are temporal.
- Fixed seeds per clip; render settings, trajectory params, and stressor tags recorded
  in each clip's `manifest.json`.

## Metrics (the §6 suite, locked in the contract)

| Metric | Function | Definition |
|---|---|---|
| SOT success | `sot_success` | fraction of *visible* frames with IoU(pred,gt) ≥ τ (default 0.25) |
| Success-plot AUC | `sot_success_auc` | mean success over an IoU-threshold sweep (OTB convention) |
| SOT precision | `sot_precision` | fraction of *visible* frames with centre error ≤ τ px (default 20) |
| ID switches | `count_id_switches` | times the locked object identity jumps between consecutive locked frames |
| Identity purity | `identity_purity` | fraction of locked frames where the lock is on the *true* target |
| Re-acquisition time | `reacquisition_frames` | frames from each target reappearance to the first correct re-lock |
| Oracle-coverage | `oracle_coverage` | fraction of **all** clip frames where the tracked box matches oracle GT ≥ τ (Phase-C convention) |
| Following error | `following_error` | mean centre offset (px) of the tracked box vs oracle, over co-present frames |
| Track-loss events | `track_loss_events` | runs where the target is visible but un-tracked for ≥ a timeout (LOST_TIMEOUT exceedances) |

`center_error` (Euclidean centre distance) underlies precision/following-error.

## Gate (charter §8)

> A scored eval clip set exists with GT and the temporal metrics are reproducible.

Concretely: (1) `make test` green with the new temporal-metric tests; (2) the clip
recorder emits the on-disk format and re-runs reproduce identical labels at a fixed
seed; (3) running the metrics on the clip set against `oracle_bbox` GT yields stable
numbers. Documented in `results/` + `RESULTS.md` + `DECISIONS.md` the same turn as the
gate pass.

## Progress

- **2026-06-18 — T1b done.** Added the §6 temporal primitives to
  `grounding/contract.py` (stdlib-only, deterministic) and locked them in
  `tests/test_contract.py`. `make test` green (see Decisions below).
- **2026-06-18 — T1a done → T1 GATE PASS.** `experiments/sitl/clip_recorder.py`
  (stdlib + numpy, no renderer) scripts deterministic multi-vehicle NED trajectories,
  projects per-frame pixel GT via `oracle_bbox.project_object` (per-object size +
  ray-vs-AABB occluder visibility), and writes `labels.jsonl` + `manifest.json`. Two
  clips emitted to `clips/`: **`crossing_occlusion`** (all four stressors) and
  **`clean_follow`** (control). A `score_clip()` entrypoint runs the **memoryless
  ByteTrack baseline** (event-triggered, appearance-blind re-acquisition to last
  position — the T0-mandated two-tier baseline) and computes the full §6 suite.

### No-renderer decision (T1a)

The T1 gate is *"a scored eval clip set exists with GT and the temporal metrics are
reproducible."* The **scorable artifact is the GT label stream**, not RGB pixels — the
§6 metrics operate on `(pred_box, gt_box, visible, locked_id)`. RGB frames are only
needed once an **appearance** re-ID head or a real VLM anchor consumes crops (T2+).
So T1a is pure stdlib+numpy and fully reproducible from the manifest; Gazebo Harmonic
rendering is deferred to T2 (when it actually buys something). This keeps the
"de-risk cheaply" discipline: the whole T1 gate closes with zero GPU and zero renderer.

### Baseline numbers (the bar T2 must beat)

Memoryless ByteTrack (constant-velocity Kalman, **no appearance / re-ID**), scored by
the §6 suite. Reproduce: `.venv-ft/bin/python experiments/sitl/clip_recorder.py --score <clip_dir>`.

| Metric | `clean_follow` (control) | `crossing_occlusion` (4 stressors) |
|---|---|---|
| frames | 120 | 200 |
| SOT success (IoU@0.25) | 1.000 | 0.827 |
| SOT precision (≤20 px) | 1.000 | 0.827 |
| success-plot AUC | 0.953 | 0.797 |
| **oracle-coverage** | **1.000** | **0.575** |
| following error (px) | 0.03 | 67.7 |
| **ID switches** | 0 | **1** |
| **identity purity** | **1.000** | **0.725** |
| re-acq events / failed | 1 / 0 | 2 / **1** |
| track-loss events (≥30 f) | 0 | 0 |

**Reading:** the control is near-perfect, so the suite isn't simply pessimistic. On the
hard clip the memoryless tracker **re-locks the wrong same-class object after the
occlusion** — identity purity falls to 0.725, one ID switch, one of two re-acquisitions
fails, and coverage drops to 0.575. This is precisely **constraint #2 (object
permanence)** made numeric, and it is the baseline the T2 appearance/re-ID mechanism
must beat (higher purity, 0 wrong-object switches, lower failed-reacq).

## Verification

```
.venv-ft/bin/python experiments/sitl/oracle_bbox.py     # project_object + occluder geometry
.venv-ft/bin/python experiments/sitl/clip_recorder.py   # reproducibility, stressors, scoring, discrimination
make test                                                # §6 contract locks (T1b)
```
All green (2026-06-18).

## Decisions

### 2026-06-18 — temporal metric definitions (T1b)

- **Decision:** Express the §6 suite as pure functions over a per-frame stream and
  pytest-lock them in the shared contract. Key definitional choices:
  - **SOT success/precision are scored over *visible* frames only** (the standard SOT
    convention — a metric of tracking quality while the target exists), with a `None`
    prediction on a visible frame counting as a miss (IoU 0 / infinite centre error).
  - **Oracle-coverage is scored over *all* frames** (denominator = clip length),
    deliberately distinct from SOT success: it is the closed-loop framing measure
    carried from Phase C (where it was ~0% on a moving target), and it *does* penalise
    windows where the drone fails to frame the target regardless of cause.
  - **ID-switch counts jumps of the locked identity** between consecutive locked frames
    (constraint-#2 failure signal); **identity purity** separately measures whether the
    lock is on the *true* target, so a tracker that locks the wrong object steadily
    scores 0 switches but low purity (the two together describe the failure).
  - **Re-acquisition time is keyed on visibility transitions** (absent→present): for
    each reappearance, frames until the first correct, in-frame re-lock; `None` if the
    target leaves again before re-lock (a failed re-acquisition).
- **Alternatives considered:** (a) score success over all frames (folds visibility into
  the number, hiding *why* coverage dropped) — rejected; keep SOT (visible-only) and
  oracle-coverage (all-frames) as two separate, complementary numbers. (b) Define
  ID-switch against GT identity only — rejected; the jump-count and the purity number
  answer different questions and the chapter needs both.
- **Tradeoff:** more functions to maintain, but each is tiny, stdlib-only, and locked;
  the contract stays the single source of truth and cannot drift.

### 2026-06-18 — clip GT without a renderer (T1a)

- **Decision:** Generate the T1 clip set as deterministic **trajectory→GT label streams**
  (`oracle_bbox.project_object` over scripted NED keyframes), **no Gazebo render**. Ship
  the memoryless-ByteTrack baseline as the scored output of the same file.
- **Alternatives considered:** (a) render RGB in Gazebo Harmonic now — rejected: the T1
  gate scores boxes, not pixels; rendering buys nothing until an appearance re-ID head /
  real VLM consumes crops (T2), and it adds a heavy, non-deterministic dependency to a
  gate that is otherwise pure-stdlib. (b) Inject synthetic appearance vectors now to test
  re-ID — rejected as T2 scope. (c) Oracle-association scoring (always lock nearest to GT)
  — rejected for the headline: it trivially scores purity≈1 and hides the failure; used
  only in the `clean_follow` sanity test. The **memoryless event-triggered re-acq** policy
  is the honest baseline and reproduces the constraint-#2 failure (purity 0.725).
- **Tradeoff:** the clips have no photometric realism, so they cannot yet exercise the
  *appearance* half of re-ID or a real VLM anchor — that realism is added in T2 when it is
  load-bearing. Accepted: T1 closes with zero GPU/renderer and a reproducible baseline.
- **Revisit when:** T2 needs appearance crops → add a Gazebo render pass keyed off the same
  manifests (the trajectory + intrinsics are already the SDF camera), so rendered frames
  line up frame-for-frame with these labels.
