# E3 — Identity robustness: twin-target / distractor test

**Pre-registered:** 2026-07-02T10:51Z (planning session; executor fills Results only).
**Status:** NOT STARTED — trigger: after E2 (`../2026-07-02-follow-speed-ceiling/`).

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

## Results (TBD)

| scenario | runs | ID-switch / wrong-lock | recovered after re-emerge | verdict |
|---|---|---|---|---|
| S1 crossing | 1 | | | |
| S2 decoy | 3 | | | |

AerialMind: | quartile | n tracks | IoU@0.25 | ID-consistency | → TBD

## Definition of done

README filled, RESULTS row + RQ-E3 verdict in `docs/{results,questions}/part4-end-to-end.md`,
DECISIONS entry (twin-rejection mitigation deferred to appearance gate — what/why/given up),
commit.
