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
- ★ **Record G6 as NOT RUN rather than substitute the base model.** Running base
  `Qwen/Qwen2-VL-2B-Instruct` in place of the deployed checkpoint would have produced a real number
  that answers a different question (~15% vs ~63% IoU@0.25) and is not comparable to P5.17's 56/56.
  *Given up:* a filled cell in the results table, and a tested pre-registration. *Kept:* the
  prediction stays falsifiable. **The decision stands; the stated reason was wrong** — see the
  correction below. Refusing the substitution was right for reasons that survive the correction,
  which is the only thing that kept a bad premise from producing a bad number.
- ★ **Correction 2026-07-20T20:10Z — do not trust a negative search whose term encodes a format
  assumption.** G6 was called blocked by a missing checkpoint. The deployed model was on the Jetson
  the whole time as `/home/jfdg/grounding/phase3-terse100eos-1024-q8_0.gguf` + `mmproj`, at exactly
  the paths `grounding/deploy/{video,serve}.py` point at, and **P5.17 grounded through those same
  files** via `JetsonBackend`. The search was `find -name "*.safetensors"`, which cannot see a
  `.gguf`; its empty result was read as absence of the model rather than absence of the *training*
  format. *Recorded as content, not just fixed:* this is the same family as the vacuous metrics in
  P6.0 and P6.1 — a check that cannot observe the thing it claims to rule out, returning a
  confident answer. The difference is that a vacuous metric reads as success and this read as
  failure; both are unfalsifiable from inside the check. **Standing rule for this repo: before
  declaring an artifact missing, search the deployment format on the deployment host, and check
  which backend the comparison experiment actually used.**
- **Accept the loss of the merged HF/safetensors training directory, for now.** It exists on
  neither machine. It is needed to resume LoRA training or re-export to new quantisations; it is
  *not* needed to ground, because every Part V select number came from the Jetson GGUF. *Given up:*
  cheap re-export and fine-tuning resumption — re-obtaining either means retraining. *Deferred:*
  whether to retrain now or when a re-export is actually wanted. Flagged in the P6.1 README
  residuals so the decision is made deliberately rather than discovered later.
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
- ★ **Run the CARLA renderer async and pace it to wall time, instead of driving it with
  `world.tick()`.** Synchronous mode makes the client the clock master, which is wrong here twice
  over: SITL is already a clock master and runs in wall-clock real time, so there were two of them;
  and sim time then only advances on `tick()`, so a 4.5 s VLM acquire costs **zero sim seconds** and
  the delivery lag that Parts IV and V exist to measure stops existing. Async gives one clock for
  all three (sim == wall == SITL); `fixed_delta_seconds` stays as a substep cap and the camera gets
  an explicit `sensor_tick`. *Given up:* tick-level determinism — two runs of the same seed are no
  longer frame-comparable. *Kept:* reproducibility via `SEED` + logged tracks + n>=25, which is the
  same standard every Part V number was held to. Bit-exact replay would need full lockstep, already
  rejected above. *Note the shape:* sync mode would have produced a **better-looking** acquire
  latency by making the cost of thinking free — the third vacuous-metric near-miss in Part VI after
  P6.0's "0 track losses" and P6.1's `slave_err_*`.
- **Build an interactive manual-flight UI (`runners/carla_debug_ui.py`) as infrastructure, not as an
  experiment.** Every Part V select number came from replayed video; before P6.2 puts the select in a
  control loop, there is value in a human flying the camera and watching the tracker respond.
  Documented in `runners/CARLA_DEBUG_UI.md`. *Deliberately not* given an `experiments/` campaign, an
  RQ or a ledger row: manual flying produces impressions, and this repo's rule is that a number
  carries its config and its n. *Given up:* the tempting shortcut of citing "it follows well when I
  fly it" as evidence. The one measured figure on this rig stays 5/23 lock at 960x540; converting
  manual impressions into a result means a scripted flight logging `(frame_n, box, actor_id, lock)`
  at n>=25.
- **Keep the tracker's box chain ground-truth-free, and say so in the tool doc.** `track["box"]` is
  written only by the VLM and by `carry.step()`; `match_actor()` reads the world purely to colour
  the overlay and count locks. *Consequence recorded up front:* a P6.2 controller must key off
  `track["box"]` and never `track["actor"]`, or the loop is GT-driven and every number from it is
  worthless. *Also flagged:* the green/red box colour **is** GT-derived, so "the box was green" is
  not independent evidence that the box was on the car.
- **Draw overlays on received frames, never into the engine.** An earlier revision had
  `unproject()`/`draw_box_2d()` painting boxes via `world.debug.*`; both are deleted. A box rendered
  into the world becomes part of the image the model is asked to ground, which corrupts the view
  under test. *Given up:* the convenience of seeing the box in any CARLA viewport. *Same family as*
  the Phase C sky-camera defect — a rendering choice that silently changes what the experiment
  measures while every log still reads like success.

## CARLA GT capture bank (unnumbered infrastructure, 2026-07-21)

- **Run the bank in `synchronous_mode`, and keep flight asynchronous.** `carla_render.py:40-45`
  records an explicit choice *against* sync for the flight rig, and that choice is correct there:
  sim time advances only on `world.tick()`, so a 4.5 s VLM acquire would cost zero sim seconds and
  the delivery lag that Parts IV and V exist to measure would stop existing. The bank is capture,
  not flight — no controller consumes the lag — so it buys determinism instead. *Given up:* one
  uniform configuration across Part VI. *Mitigation, because that is a real cost:* every manifest
  carries `"mode": "sync"` and every number below names which configuration produced it. **Drift
  and latency figures are not commensurable between the two**, since `DRIFT_S` is wall-clock.
- **Settle the CARLA GT API against a live server instead of reading the docs.**
  `runners/carla_probe_gt.py` was written and committed (`2d0917a`) purely to answer four questions,
  and it earned itself on the first: an `EnvironmentObject.bounding_box` is **world**-space, so
  `get_world_vertices()` takes `carla.Transform()` — the identity. Passing the object's own
  transform, which is the obvious guess and the correct call for an *Actor*, **doubles** every
  coordinate (`-51,166` becomes `-102,333`). All 29 parked-car boxes would have landed somewhere
  plausible, on rooftops and pavements, with nothing downstream that would notice. *Given up:* an
  hour. *Bought:* the two buckets now use deliberately different calls, documented at the call site.
- **Gate G-A on an analytic area prediction, not on monotonic shrink.** The slate's rule was
  "projected area decreases monotonically as the camera climbs" — already sharper than rev 1's
  "non-degenerate and inside the frame", but still weak, because **a box built from the wrong
  transform also shrinks monotonically**. A receding camera shrinks almost anything. So G-A now
  predicts the pixel area analytically from the known world footprint
  (`px_per_m = (W/2)/tan(fov/2)/z`) and asserts the measured area lands inside 0.75-1.35x, with
  monotonicity kept only as the cheap second check. `tests/test_carla_gt_bank.py` pins the
  distinction: `test_monotonic_shrink_alone_is_weak` exists to show the discarded rule passing a
  deliberately misplaced box.
- **Keep GT boxes whose vertices fall behind the camera plane; record `n_proj` instead of dropping
  them.** `carla_debug_ui.actor_box()` returns `None` unless all 8 vertices project, which is right
  for *matching* — a truncated box makes a bad IoU — and wrong for *capture*, where a close target
  is exactly the case a follow controller must handle (slate hazard 2.3f). The bank writes the box
  with `n_proj` and `partial` alongside it, so a consumer can apply the stricter rule and no
  consumer is forced to.
- **Carry a semantic-segmentation camera at the same pose as the RGB camera, and store `veh_fill`
  per GT row.** Corner-projected GT has no depth test (hazard 2.3c), so a car parked behind a
  building projects a clean, correct, entirely invisible box — confirmed by looking at the G-A
  overlays, where boxes sit squarely on building facades. `veh_fill` measures what fraction of each
  box covers vehicle-class pixels, which turns that from an invisible defect into a filterable
  column. *Given up:* a second camera's render cost (capture ran 28.9-30.7 Hz with it). *Known
  ceiling, recorded at the call site:* the tag is class-level, not instance-level, so two
  overlapping cars both read high; instance segmentation is the upgrade if an audit ever confuses
  adjacent vehicles.
- **Kill the in-flight autoresearch cycle rather than let it share the GPU.** The README
  pre-registered "autoresearch collision" as an operational guard and armed
  `.claude/autoresearch.STOP` at 00:27Z; the cycle already running (pid 360646) was deliberately
  left alone so as not to corrupt its branch. That judgement was **wrong and was reversed at
  22:40Z**: the live cycle read this campaign's freshly-committed script and launched
  `carla_gt_bank.py --gate-c` against the same server on port 2100, reloading the world underneath
  the bank capture and killing it with `_queue.Empty` 0.9 min in. *Recorded because it is the
  general lesson:* a kill switch that only prevents *new* work is not isolation while an old worker
  is still running, and a shared repo is a channel — the intruder found the work by reading the
  commit. *Given up:* that cycle's partial progress. The retry driver resumed and lost one clip.
- **Name the campaign directory and branch without an experiment number.** The autoresearch cycle
  re-created the branch as `experiment/p63-carla-gt-bank`, reintroducing the exact numbering
  collision the slate's own review had already caught and corrected (`PART6-SLATE:16-19`): rev 1
  renumbered the committed **P6.2** (closed-loop select-and-follow) out to P6.3 to make room for
  diagnostics. **P6.2 keeps its committed meaning.** The branch was renamed to
  `experiment/carla-gt-bank` and this campaign claims no `P<part>.<n>` id, per the slate's ruling
  that the diagnostics stay "unnumbered candidates until one is promoted". *Gate verdicts are not
  results*, and this campaign produces only gate verdicts and an artifact.
- **Keep the GT bank out of git; treat the seeded runner as the record.**
  `.gitignore:41` whitelists `gt.jsonl` under `experiments/*/runs/`, a rule written when a
  `gt.jsonl` was small. This campaign's is 31.7 MB per clip, so the 25-clip bank would have put
  **793 MB into a 593 MB `.git`**. It is also written incrementally, and a `git add -A` mid-capture
  had already committed a **truncated clip03** (17.9 MB against 32.4 MB on disk) that still parses
  as valid JSONL — well-formed and wrong, the failure mode this campaign exists to detect. Excluded
  with a rule scoped to this campaign rather than a change to the global one other campaigns
  depend on. *What justifies it:* the bank is deterministic from `--seed`, so the runner plus the
  committed per-clip `manifest.json` reproduce it; the thesis artifacts are the manifests and the
  `proof/` figures, not 793 MB of JSONL. *Given up:* byte-level reproducibility of *this particular*
  capture if CARLA's determinism ever drifts across versions, and the ability to re-derive figures
  without a CARLA install. *Deferred:* 113 MB of already-committed blobs stay in branch history
  until the driver is idle — rewriting history under a running unattended capture is the worse
  trade on an unmerged, unpushed, local-only branch.
- **Resolve the camera-pose-lag question offline instead of paying for a live probe.** An
  adversarial review flagged that GT is projected from the camera actor transform read *after*
  `world.tick()`, which if stale would put every box one frame of camera motion behind its pixels —
  the P5.13 zero-order-hold class, invisible in any log. Rather than queue a live
  `image.transform` probe behind the capture, the `track_gain 0.0` clips answer it directly: their
  commanded camera path is a closed form in the frame index, so the logged pose can be scored
  against the command at frame `i` and at `i-1`. Both clips say **current**, by an order of
  magnitude (0.359/0.178 cm vs 1.910/2.239 cm on a 2.09 cm step). *Given up:* the exact residual —
  whether the *render* lagged the actor transform — which is instead **bounded** at one camera step
  in pixels, worst case 3.35 px. *Why it is recorded:* the check cost nothing, needed no server,
  and turned a blocking re-capture question into a bounded one; `check_pose_lag.py` is committed so
  it re-runs on any future bank.
