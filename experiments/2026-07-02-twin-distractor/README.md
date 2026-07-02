# E3 — Identity robustness: twin-target / distractor test

**Pre-registered:** 2026-07-02T10:51Z (planning session; executor fills Results only).
**Status:** DONE 2026-07-02T20:35Z. Patches landed in the parent campaign
(`sitl_cam.py` distractor render + two-blob selfcheck; `phase3_sitl.py --twin`), all 4 SITL
trials + AerialMind leg run, Results filled below. **RQ-E3a yes (CARRY holds a crossing),
RQ-E3b yes (REGROUND wrong-locks the decoy 3/3).**

## Research question

**RQ-E3:** "Follow the white car" with a second white car in scene. (a) Does CARRY (SAM2 memory)
hold the bound target through a crossing? (b) Does REGROUND re-lock the *wrong* twin when the
true car is still occluded? The size-prior validation cannot reject a twin by construction —
a wrong-lock result here is the pre-registered honest negative that motivates the reserved
mitigation (appearance-embedding gate on reground acceptance).

## Frozen design (do not redesign)

### SITL side — two scenarios, one small render patch

**Patch — `sitl_cam.py`:** `SceneRenderer.render(self, copter_ned, yaw, rover_ned,
distractor_ned=None)` — when set, draw a second car with the *identical* polygon/color as the
target (that identity is the experiment). Extend `--selfcheck`: one render with a distractor at a
known offset asserts two disjoint car-pixel blobs; existing assertions unchanged.
**Patch — `phase3_sitl.py`:** `--twin {crossing,decoy}` flag; the scenario code computes the
distractor path and passes `distractor_ned` into every render call. Speed 0.25 m/s, levers on,
same rig as 3a run 2 otherwise.

- **S1 `crossing`:** distractor starts 12 m ahead of the target at E=+3 m (adjacent lane),
  drives **south** (opposing) at the same speed — it passes the target around t≈20–24 s at 3 m
  lateral separation. Tests CARRY binding, no occlusion involved.
- **S2 `decoy` (adversarial):** distractor **parked** 2 m past the bridge's north edge at E=0
  (same lane). During the occlusion the copter's REGROUND sees exactly one white car — the decoy —
  while the true car is hidden under the bridge. Tests wrong-relock rate.

**Metrics (logged per frame):** box-center distance to true car vs to distractor.
S1: **ID-switch** = box closer to the distractor for > 1 s continuously → FAIL.
S2: **wrong-lock** = REGROUND accepts a box on the decoy (final following distance to the decoy
≈ 0 while the true car drives on) → the measured negative. Also record whether the tracker
*recovers* when the true car re-emerges. Run S2 **3 times** (relock timing vs decoy visibility
is jittery; one run is an anecdote). Logs → `raw/`, metrics → `runs/{s1-crossing,s2-decoy}/`.

### AerialMind side — pure analysis, zero new tracking runs

From the parent campaign's Phase 0 outputs (`runs/phase0-zeroshot-carry/per_track.csv`) plus the
AerialMind `labels_with_ids` (**top-left encoding, not JDE center** — the documented gotcha):
per track, compute **distractor density** = mean number of same-size (±50% area) GT boxes within
3× the target's box diagonal, per labeled frame. Split tracks at the top-quartile density; compare
IoU@0.25 and ID-consistency between the distractor-heavy quartile and the rest. ~30 lines of
pandas, `distractor_density.py` in this dir, table into Results.

## Estimates (mark actuals vs these)

- S1: CARRY survives the crossing (SAM2 memory is appearance+position); ID-switch < 10%. ESTIMATE.
- S2: wrong-lock in ≥ 50% of runs — expected FAIL, documented plainly; names the
  appearance-embedding gate as future work. Only if time remains and the user asks: E3b = CLIP
  crop-embedding cosine gate on reground acceptance (threshold from true-car crops). Not in scope
  otherwise. ESTIMATE.
- AerialMind: distractor-heavy quartile loses 2–8 pp IoU@0.25. ESTIMATE.
- Effort: ~1–2 h total.

`ADVISOR (only if S1 fails — that contradicts the Phase 0 ID-consistency 0.891 prior): "SITL
crossing-twin made CARRY switch identity (<paste metrics>), but population ID-consistency was
0.891. Render artifact, rig bug, or real SAM2 failure mode?"`
(The advisor tool was DOWN on 2026-07-02 for both the E2 session and the prep session. If it is
still down when the clause triggers, record that, reproduce the failure once, and proceed on own
judgment — the E2 precedent.)

## Executor handoff (prepped 2026-07-02T20:30Z, post-E2 — verified paths)

**Rig:** same as E2 / 3a run 2 — local-VLM path (Jetson not needed; do NOT pass
`--remote-carry`), local 3090 carry @1024. Speed is the default 0.25 (E2's `--speed` flag is
committed; don't pass it). Invocation shape:

```bash
cd /home/gara/jetson && .venv-ft/bin/python \
  experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py --twin crossing
```

**Files to patch** (both live in the parent campaign, not here):

- `experiments/2026-07-01-temporal-acquire-carry/sitl_cam.py` — `SceneRenderer.render()` at
  line 83 (add `distractor_ned=None`), `selfcheck()` at line 102 (add the two-blob assertion).
- `experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py` — argparse at ~line 338 (add
  `--twin {crossing,decoy}`); scenario constants near `SPEED` at line 48; E2 already raised the
  DR clip to ±2.5 (line ~228), leave it.

**Output plumbing (same gotcha E2 hit):** `phase3_sitl.py` overwrites
`<parent>/raw/phase3a-sitl/trial-*.csv` and `<parent>/runs/phase3a-sitl/results.json` on every
run. Snapshot after each run into this campaign's `runs/{s1-crossing,s2-decoy-run{1,2,3}}/` —
copy the loop pattern from `../2026-07-02-follow-speed-ceiling/run_e2.sh`.

**Metrics plumbing:** `results.json` already carries `n_regrounds`, `relock_walls_s`,
`recovered_after_occlusion`. The per-frame trial CSV
(`t_s,state,copter_n,...,rover_n,rover_e,in_fov,occluded,bbox_cx,bbox_cy,...`) has no distractor
state — add per-frame distractor NED columns and the projected pixel centers of both cars (the
renderer already does the NED→pixel projection), so box-center-distance to true car vs
distractor is computable per frame.

**S2 verdict amendment (pre-registered here, NOT after seeing data):** E2 found a
*confident-latch* mode at 0.5 m/s — under the bridge occlusion SAM2 latched the occluder and
returned a confident box, so `n_regrounds=0` and the levers never fired. 3a run 2 at 0.25 m/s
got honest loss and a REGROUND, so S2 at 0.25 should be measurable — but verify per S2 run:
if `n_regrounds == 0` (no REGROUND ever fired during the occlusion), the run is
**"S2 not measurable — confident-latch reproduced at 0.25"**, a distinct recorded result, NOT
"no wrong-lock = PASS". Wrong-lock rate is defined only over runs where REGROUND fired.

**AerialMind leg paths:** `per_track.csv` at
`experiments/2026-07-01-temporal-acquire-carry/runs/phase0-zeroshot-carry/per_track.csv`
(cols: `seq,tid,n_frames,n_labeled,mean_iou,iou_at_25,...,id_consistency,...`); GT at
`/home/gara/jetson/data/AerialMind/labels_with_ids/` — coordinates are **top-left encoded,
normalized** (not JDE center; the documented Phase 0 gotcha). The density metric (same-size
boxes within 3× box diagonal) works in normalized coords; no image loading needed.

**Definition of done is below** — ledger appends go to `docs/{results,questions}/part4-end-to-end.md`
(per-Part docs, never the root files), Madrid wall-clock timestamps, no emojis.

## Results (2026-07-02T20:35Z)

Run: `bash experiments/2026-07-02-twin-distractor/run_e3.sh` (speed 0.25, levers on, local
3090 carry @1024, local-VLM acquire). Snapshots in `runs/{s1-crossing,s2-decoy-run{1,2,3}}/`.
All four trials PASS the base gate (in-FOV 1.000, recovered_after_occlusion). The twin verdict
is a *separate* per-frame identity check (box-center distance to true car vs distractor).

| scenario | runs | ID-switch / wrong-lock | recovered after re-emerge | verdict |
|---|---|---|---|---|
| S1 crossing | 1 | **ID-switch 0.0 s** (0.0% of boxed frames closer to distractor) | yes — bridge relock @13.9 s onto true car | **PASS** — CARRY held |
| S2 decoy | 3 | **wrong-lock 3/3** (every REGROUND re-locked the decoy first) | no sustained recovery (see below) | **FAIL (expected)** |

**S1 crossing — CARRY holds (RQ-E3a: yes).** The distractor was continuously in-frame through
the pass (its pixel ~175-270 px from the tracked box, min ~175 px at t≈28 s, ~3 m lateral) and
CARRY never once put the box closer to it (`id_switch_s = 0.0`, `frac_box_closer_distractor =
0.0` over 968 boxed frames). Ends glued to the true car: final distance 0.27 m vs 25.94 m to the
(southbound, departed) distractor. SAM2 memory (appearance + position) is not fooled by an
identical twin passing at 3 m when the true target was never lost. Beats the < 10% estimate.

**S2 decoy — REGROUND wrong-locks the twin (RQ-E3b: yes), then the follow collapses.** All three
runs fired a real REGROUND during the occlusion (`n_regrounds = 1`, relock walls 14.0/18.5/13.9 s)
— so the E2 confident-latch amendment does **not** apply; these are measurable. In every run the
re-lock's *first* box landed on the decoy (t≈47 s, box-center closer to the decoy than to the
still-hidden true car), and the copter surged toward it — the pre-registered wrong-lock, 3/3. The
size-prior lever cannot reject it by construction (identical polygon → identical size). The tail
is a compound failure worth recording: because the decoy parks *in the true car's lane*, the true
car emerges from the bridge and drives through the decoy's position at t≈50 s, so the box
transiently transfers to the true car as they coincide (t≈51-68 s, box-closer-to-true) — but the
copter has already **static-latched** at N≈15.7 m (the E2 static/confident-latch mode reappearing
post-reground: a near-centered box → ~zero velocity command → the copter holds → the box stays
centered) and never resumes the follow. The true car escapes to N≈19.1 m while the copter sits
between the two cars, ending marginally closer to the decoy (final d_true 3.5-3.9 m vs d_dist
2.1-2.4 m). So the accidental same-lane crossing does *not* rescue the follow. `id_switch_s`
4.3-5.6 s, `frac_box_closer_distractor` 0.09-0.20. This is the honest negative the campaign was
built to produce — the size prior is identity-blind, so nothing in the current lever set can
prevent a same-appearance decoy from capturing the REGROUND. Motivates the reserved mitigation
(appearance-embedding gate on reground acceptance); E3b (CLIP cosine gate) not run this session.

**AerialMind leg — density does NOT degrade Phase 0 carry (estimate wrong).**
`distractor_density.py` over the 186 Phase 0 tracks, top-quartile split at density ≥ 6.96:

| quartile | n tracks | density | IoU@0.25 | ID-consistency |
|---|---|---|---|---|
| distractor-heavy | 47 | 11.27 | 0.858 | 0.896 |
| rest | 139 | 2.98 | 0.846 | 0.890 |

The distractor-heavy quartile is marginally **better**, not worse: IoU@0.25 **+0.011**,
ID-consistency **+0.006**. The estimate (heavy quartile loses 2-8 pp) was wrong — on AerialMind,
scene density alone (same-size neighbours near the target) does not hurt zero-shot carry; the
SITL S2 failure is driven specifically by *occlusion + a same-appearance decoy in-lane during
REGROUND*, not by crowding per se. (Density here is a normalized-coord proxy, top-left encoded per
the Phase 0 gotcha; anisotropic N/E normalization — a proxy, not metric.)

**Advisor:** the S1-failure advisor clause did not trigger (S1 passed). Advisor tool was DOWN this
session (as on the E2 / prep sessions); recorded, proceeded on own judgment per the E2 precedent.

## Definition of done

README filled, RESULTS row + RQ-E3 verdict in `docs/{results,questions}/part4-end-to-end.md`,
DECISIONS entry (twin-rejection mitigation deferred to appearance gate — what/why/given up),
commit.
