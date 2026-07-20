# DECISIONS — Part VI (v6 Closed-loop flight)

> Decision log for the closed-loop flight chapter (v6). Index: [`../../DECISIONS.md`](../../DECISIONS.md).
> Per-experiment decisions also live in `experiments/<campaign>/README.md`. ★ = headline decision.
> **Append** — add each new decision at the bottom (chronological, oldest first; matches RESULTS/QUESTIONS).

---

<!-- append decisions below -->

### P6.0 — flight-rig capability gate (2026-07-20)

★ **Keep SITL-as-physics + Gazebo-as-pose-slaved-renderer; do not adopt `ardupilot_gazebo`
lockstep.** Each control tick drains `LOCAL_POSITION_NED` and pushes the camera model pose via
`set_pose`. This already delivers what Part VI is testing — camera pixels that move as a
consequence of the copter's own control output. *Given up:* physically-coupled rotor
downwash / airframe dynamics visible in the render, and frame-accurate determinism between sim and
flight. Neither is load-bearing for a perception-in-the-loop question. *Cost avoided:* rebuilding
the world, the vehicle model, and the runner around a plugin that is installed but unused.

- **Fix the tracker rather than raise the detection rate around it.** The cheap workaround was to
  inject faster until the ID churn stopped. That would have hidden a real ByteTrack defect behind
  a config value and carried it into P6.1, where the detection source is a real ~1 Hz VLM and the
  churn cannot be hidden. *Given up:* a larger diff on shared Part-I infra than a capability gate
  would normally justify (`runners/sitl/bytetrack.py`, round-1b re-find + regression test).
- ★ **Retract RQ-S1.4 rather than silently patch the camera.** A recorded Part I verdict is now
  known to rest on a blank gray image. The alternative — fix the pitch, say nothing, let the old
  numbers stand — was rejected outright. *Given up:* a clean-looking Part I chapter. *Kept:* the
  retraction is itself thesis content about how silent render failures hide inside *confirmed*
  hypotheses, which is a stronger methodological result than the original negative was.
- **Do not re-run Phase C Branch-2 to recover the answer.** Re-running would measure
  SmolVLM-500M, a backbone already eliminated in the Part IV bake-off and superseded by the
  deployed Qwen2-VL-2B. *Given up:* an answer to RQ-S1.4 — it stays UNANSWERED rather than being
  answered about a model nothing downstream uses.
- **Do not re-run Phase C Branch-1 either, but stop quoting its pixel error.** Branch-1's px_err
  89.4 is inflated by the same tracker defect (it injected at 1 Hz). Its integration PASS does not
  turn on the pixel-error magnitude, so the verdict stands and the number is flagged instead.
  *Given up:* a comparable pre/post pixel-error figure for Part I.
- **Score P6.0 as a capability gate, not a research question.** Mechanical thresholds and an abort
  rule, n=1 per configuration. *Given up:* the n≥25 sample-size rule, deliberately — that rule
  governs *gating experimental arms*, and "does the rig arm and fly" is not one. P6.1 is a real
  arm and gets the full treatment, pre-registered before it runs.

### P6.1 — CARLA renderer swap (2026-07-20)

- ★ **Renumber Part VI staging: the CARLA swap becomes P6.1, closed-loop select-and-follow becomes
  P6.2.** CLAUDE.md originally scoped P6.1 as select-and-follow, but that arm is blocked on scene
  content — there is nothing in the Gazebo flight world to select *between* — so the renderer swap
  is its enabler and had to be gated first, on its own, because it could fail on its own.
  *Given up:* a stable pre-announced number for the select-and-follow arm. *Precedent:* P5.1 was
  pre-registered as E24 and renumbered at merge; renumbering an experiment that has not run is
  cheap. Recorded before the run, not after.
- ★ **Swap the renderer rather than populate Gazebo.** The vendored `SITL_Models` library is 34
  models — rovers, cones, barrels, a tractor unit, a boat — with no city and no traffic; the
  P5.9/P5.12 `select_arena` bank is rovers on a racetrack because that is what those assets allow.
  Authoring a photoreal populated town in Gazebo is a content project, not an experiment.
  *Given up:* continuity with every Part V sim number — CARLA renders are not comparable to the
  Gazebo bank, so P5.17's 56/56 becomes a *contrast* rather than a baseline. *Kept:* the entire
  control stack, unchanged.
- **Keep pose-slaving; do not spawn the copter as a CARLA actor and do not use CARLA physics.**
  Identical rationale to P6.0's rejection of `ardupilot_gazebo` lockstep, which was
  renderer-agnostic and survives the swap verbatim. CARLA's vehicle physics is *ground*-vehicle
  physics and would not model a multirotor. *Given up:* rotor downwash and airframe dynamics
  visible in the render — not load-bearing for a perception-in-the-loop question.
- **Use the packaged 0.9.16 release, not a source build, and not 0.10.0.** The package is 8.35 GB
  against an Unreal Engine toolchain build measured in hours and tens of GB. 0.9.16 is also the
  first release shipping cp312 wheels (0.9.15 stops at cp310), which is what avoids standing up a
  second Python environment; 0.10.0 has a newer tag but an *older* release date (2024-12-19 vs
  2025-09-16) and moved to UE5 with a reduced map set. *Given up:* custom map authoring and asset
  import, which need the source build. Revisit and re-record if P6.2 needs a bespoke map.
- **Install the client into `.venv-ft`, no new venv.** `carla==0.9.16` resolves with **zero**
  transitive dependencies (verified by `uv pip install --dry-run`), so it cannot perturb the pinned
  torch/transformers/opencv set every Part II–V number was measured against. *Given up:* nothing
  identified.
- ★ **Record G6 as NOT RUN rather than substitute the base model.** The deployed checkpoint is
  missing, and running base `Qwen/Qwen2-VL-2B-Instruct` in its place would have produced a real
  number that answers a different question (~15% vs ~63% IoU@0.25) and is not comparable to
  P5.17's 56/56. *Given up:* a filled cell in the results table, and a tested pre-registration.
  *Kept:* the prediction stays falsifiable, and the missing checkpoint is surfaced as a P6.2
  blocker instead of being quietly papered over.
- **Name the vacuous slaving-error metric instead of deleting or citing it.** `slave_err_*` is
  identically zero because CARLA's free camera is kinematic — it compares a number against itself.
  Deleting it hides that the check was attempted; citing it fabricates a result. It stays in
  `results.json`, is flagged in the README and the results ledger, and is deliberately **not**
  plotted in the proof figure. *Precedent:* P6.0's "0 track losses", the same failure shape found
  one experiment earlier.
- **Verify every camera-axis sign against a viewed frame before recording any number.** Direct
  consequence of the Phase C sky-camera defect, where `+pi/2` aimed the camera up for a month and
  produced a *confirmed* negative on a blank image. The NED to Unreal mapping turned out correct
  on every row including the pitch sign — being right by inspection rather than by assumption is
  the point. *Given up:* nothing but a few minutes.
- **Score P6.1 as a capability gate, n=1 per configuration.** Same carve-out as P6.0: the n>=25
  sample-size rule governs *gating experimental arms*, and "does the renderer render" is not one.
  P6.2 is a real arm and gets the full treatment.
