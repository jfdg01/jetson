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
  float noise because the camera is an unattached `sensor.camera.rgb`, a kinematic actor — it
  compares a number against itself. Deleting it hides that the check was attempted; citing it
  fabricates a result. It stays in `results.json`, is flagged in the README and the results ledger,
  and is deliberately **not** plotted in the proof figure. *Precedent:* P6.0's "0 track losses",
  the same failure shape found one experiment earlier.
- **Replace `slave_err_*` rather than only disowning it (R-10, 2026-07-21).** Naming a vacuous
  metric is the right *first* move but it leaves the property unmeasured. The audit found the
  replacement was computable from the already-committed artifact: consecutive identical
  `pose_track` rows are the ticks that reused a stale MAVLink pose, giving 60.4% stale ticks and a
  worst-case camera lag of ~3.9 m. *Given up:* nothing — no re-run was needed. *What this changes
  going forward:* when a metric is disowned as vacuous, the next question is not "is it flagged"
  but "what on disk measures the thing it was supposed to". Two of the three Part-VI vacuous
  metrics turned out to have an answer.
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

## Statistical framework (2026-07-21T13:30Z) — cross-cutting

- **Test chosen by design, never by p-value.** McNemar exact for paired binary, binomial exact +
  Wilson for a single arm against a gate, Fisher for unpaired, Wilcoxon + bootstrap for paired
  continuous. Fixed by an assertion in `tests/test_stats.py`, because on P5.2's numbers the
  *wrong* (unpaired) test gives the *prettier* p (1.2e-05 vs 3.1e-05). *Given up:* the smaller
  number. Choosing a test after seeing its output is p-hacking regardless of which one is chosen.
- **`mcnemar(0, 0)` returns NaN, not 1.0.** Three sim campaigns tied exactly. Reporting p=1.0 reads
  as "proven equivalent"; 0 discordant pairs means no test ran in either direction. *Given up:* a
  printable number in 26 of 65 rows.
- **Report a retrospective *design* bound, not observed power.** `min_discordant_for_significance(n)`
  is computed from n alone without looking at the outcome, which is what makes it legitimate post
  hoc — unlike observed power, which is the p-value relabelled. This is what produces the finding
  that 33 claims were unanswerable by construction.
- **Deflate every interval to `n_effective` before computing it** (`deflate_to_effective`). Caught
  live: E17 printed `n=1` beside a Wilson CI built from 10 rows of one deterministic failure. The
  correction is a design effect with deff = n_rows/n_effective and is deliberately blunt — it only
  widens intervals and weakens p-values, so it cannot manufacture a result. *Given up:* tighter
  intervals on every pseudo-replicated arm, which is the point.
- **Bound the claim rather than drop it when only marginals survive.** b-c is fixed by the arm
  totals; sweeping all consistent (b, c) gives a valid upper bound on p. Rescues Part I's strongest
  result (worst case still 1.345e-4). `claims.json` stores the worst-case pair so the published
  number is the bound, never the favourable pairing.
- **Holm-Bonferroni, not Bonferroni or Benjamini-Hochberg.** Holm is uniformly more powerful at the
  same family-wise error; BH is for screening and these are confirmatory pre-registered gates. NaN
  p-values are excluded from the family — a test that did not happen cannot spend alpha.
- **A claim with no per-item data is not defended, it is queued.** Three-level `data_status`
  (`per_item` / `counts_only` / `missing`); `missing` goes to `thesis/rerun-backlog.md` with its
  command. *Given up:* citing T2, T3 and Phase C. Phase C in particular has 13 complete CSVs that
  are deliberately left unextracted, because the input pixels were blank sky.

## D-MACH.1 — Machine disclosure: what gets re-measured on-device (2026-07-21T18:05Z)

Record: `experiments/2026-07-21-machine-disclosure/README.md` (R-1).

- **Do not re-run Part V on the Jetson.** In every rate-capped campaign the VLM anchor — the thing
  under test, and the dominant term in the latency the arc is about — already ran on the Orin at
  15 W with `jetson_clocks` over real SSH. The 3090 half is SAM2 propagation, and E1 verified the
  on-device TensorRT encoder produces masks at IoU 1.000 parity with the eager reference, so
  porting the carry would change *when* masks arrive, not *which*. That is exactly and only what
  the rate cap emulates. *Given up:* end-to-end on-device timing for twenty campaigns — weeks of
  Orin time to re-derive numbers whose sole machine-sensitive component is one scalar.
- **Measure that scalar instead — fold it into the existing R-16, do not open a new task.** The cap is 6.15 Hz measured at image_size 768;
  the campaigns run 1024. An E1-style co-resident FPS gate at 1024 either validates the cap or
  replaces it, at a fraction of the cost. Until it lands, no carry-dependent PASS may be stated as
  an on-device *rate*. *Given up:* the convenience of treating 6.15 Hz as settled.
- **Mark superseded rather than re-measure Stage 3's −23 pp parity result.** It confounds hardware
  with runtime (Jetson GGUF minus 3090 HF, and the Jetson leg ran unlocked at 15 W). Part II
  Phase 4 redid the comparison properly at −2.7 pp, and that is what Part II rests on. *Given up:*
  a clean headline for the number that motivated the Part II rebuild.
- **P5.20's `hiera-small` NO stands without an on-device re-run.** The arm provably cannot meet the
  Orin budget, and the bias direction is adverse to it — on-device it runs slower, so the NO can
  only harden. *Given up:* nothing; a re-run could not overturn the verdict.
- **Everything else is a text correction, not a measurement.** M3, M4, M6 and M8 are missing or
  wrong rig lines and route to R-7; M5 is already R-17. *Given up:* the appearance that this was a bigger problem than it was —
  it was mostly bookkeeping, and saying so plainly is the honest report.

### D-MACH.2 — `README.md` scopes the on-device claim instead of dropping it (R-6, 2026-07-21T19:40Z)

- **Keep «corre en la placa», bound to the deployed system.** It is true of the artifact
  the thesis delivers and false only of the experimental campaigns, so deleting it would
  trade one wrong sentence for a second one. The README now separates the two explicitly
  and puts the 47/13/3/2 machine split in the reader's path rather than in an appendix.
  *Given up:* the clean one-line pitch — the front matter is three sentences longer.
- **Quote the deployed operating point, not the best one.** The carry bullet published
  0.849 (1024 px) while the shipped configuration is 768 px at 0.830, a gap the registry
  shows is real (p = 0.014). The README now states 768 and names the trade.
  *Given up:* 1.9 pp of headline accuracy.
- **Publish the ceiling, not the setting that failed.** «hasta 3.0 m/s» became 2.5 m/s
  with the 0/2 at 3.0 stated inline. *Given up:* the larger number.
- **Same-backend deltas over cross-machine ones.** ROI is now +21.2 pp against the
  sweep's own full-frame control, not +22.6 pp against the Orin-deployed baseline.
  *Given up:* comparability with every earlier document that cites +22.6 pp — those are
  R-7's problem, and R-14 may still supersede both with an on-device measurement.
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

## P6.2 program — closed-loop significance slate (pre-registered 2026-07-23T23:05Z)

Record: `experiments/PART6-PROGRAM-warm-start-significance.md` + the five per-experiment READMEs.
Tracked as R-35/R-35b/R-36/R-37/R-38.

- ★ **CARLA `Town10HD_Opt` is the primary substrate; piloting a moving-target follow is the
  round's priority (author steer).** *Why:* reusable, controllable scenarios — the same seeded
  traffic re-run under different weather / time-of-day / camera angle — are far higher ROI than
  scavenging one-off UAV clips, and they make the *next* round (a condition-robustness sweep) a
  factor change on the same rig rather than a new capture campaign. *Given up:* real-imagery
  fidelity for the flight claims — bounded by the S5 honesty caveat (a sim PASS is a
  control-coupling claim only, never a real-imagery perception claim; P5.17 grounds 56/56 clean).
  Real-imagery perception/carry claims stay on UAV123 (R-36, P5.21, REG); CARLA cannot substitute.
- ★ **The R-35 build is a MERGE, not a port.** `run_phase_c.py` is the old Gazebo rig;
  `carla_render.py` (flies, no GT) and `carla_gt_bank.py` (has GT, no flight) are disjoint. R-35
  merges both into one async closed-loop harness at `run_phase_c.py`'s source-agnostic seams.
  *Given up:* the simpler "drop the select modules in" story — the WARM/COLD producers and a live
  idle-window ring buffer must be written new (Part V modules are replay-only; `idle_catchup_multi`
  re-walks past frames, impossible live). *Precedent for async:* the P6.1 decision above.
- **Target-exits-frame is a first-class COLD failure mode, engineered via CARLA controllability.**
  The point of the round is that ~4.85 s lock-in latency can leave the target *gone from frame*, not
  merely stale. The admission screen requires the target to move >=1 box-width during the acquire
  window; the per-flight record logs whether it is still in-frame at COLD delivery. *Given up:*
  scenarios where COLD merely lags — those are less informative and screened toward the exit case.
- **Weather/ToD/camera-angle are covariate diversity this round, a powered factor next round.**
  Each of the 25 distinct seeds draws one condition, so WARM>COLD is shown to hold across
  conditions without spending n on a factor. *Given up:* a robustness claim this round — deferred,
  not dropped, and named as the next round's starting point.
- **P6.3-LAT and P6.2-CEILING are descriptive companions, never inferential.** They ride the P6.2
  matrix but are reported as distribution + jitter band / bounded gap, not as a p-value — the E20
  false-precision lesson. *Given up:* two more Holm-family entries that would have been either
  tautological (CEILING vs its own oracle) or noise-dominated (LAT under SSH jitter).
- **P6.2 matrix runs the SAM2 carry on the 3090 rate-capped to the Jetson's measured 2.69 Hz, NOT
  literally over SSH — with one on-Jetson end-to-end showcase flight alongside** (decided
  2026-07-24, in response to an author question "why does the 3090 do SAM2 — that's not end-to-end
  on the Jetson"). *Why:* the faithful model of an on-board Jetson is (i) the box VALUES, which are
  device-identical by E1 mask parity 1.000, delivered at (ii) the on-device CADENCE, measured at
  2.69 Hz by R-16, with (iii) ~zero camera->compute transport (the Jetson is on the drone). 3090
  carry rate-capped to 2.69 Hz reproduces all three. Literally routing each frame Jetson-ward over
  the SSH tunnel (`jetson_carry_service.py`, which DOES exist and is reused for the showcase) would
  inject a per-frame round-trip latency the real on-board drone never pays — and P6.2 is a
  *delivery-timing* experiment, so that artifact lands squarely on the variable under test. Grounding
  stays on the Jetson unconditionally (device-specific: quantization changes the box; carry masks do
  not). *Given up:* a literal every-flight on-device run for the matrix — recovered as the single
  end-to-end showcase flight (real device + in-rig parity re-check + documented SSH-transport
  caveat), so the on-device capability is still demonstrated, just not as the 25x2 timing substrate.
  The carry backend is written swappable so redirecting the whole matrix to SSH-carry stays cheap.

### P6.2-DELIVERY — oracle target-designation scope (2026-07-24)

★ **Isolate the closed-loop delivery-timing variable via ORACLE target designation (operator
designation = GT box), dropping VLM grounding from the gating path.** Why: the G6 gate showed the
deployed q8_0 grounder is non-discriminative at the 45 m nadir geometry — it locks the target only
under a hand-picked spatial caption (`the car in the center`, IoU 0.329), grabs the wrong same-class
car under any generic phrase, and an off-center probe bank locked 0/8. Part VI's declared novelty is
the closed control loop, not grounding (that authority is Part V / E18-n25). Holding grounding
constant makes the WARM/COLD contrast a clean test of delivery-timing + control-coupling, which is
what P6.2 is for. *Given up:* a grounding+delivery joint claim — the nadir-grounding center-bias is
instead recorded as a documented limitation and the claim authority is narrowed to control-coupling
conditional on correct designation (S5). *Also decided:* RENDER_ALT 60 -> 45 m (cars render ~40 px,
inside SAM2's reliable carry band); PID gains tuned kp_lat 0.02 -> 0.05, max_v 3.0 -> 4.0 (the carry
*rate* stays pinned to the Jetson 2.69 Hz = device faithfulness; only the controller is tuned).
**Author-review flag:** the oracle scope is a deviation from the frozen pre-registration (which
specified `vlm_acquire` idle-window seeds); recorded openly here and in the experiment README, not
silently swapped. The result stands as a control-coupling claim; whether the thesis also wants an
on-device grounded closed-loop number is the author's call (the showcase flight is the seam for it).

### P6.2-COUPLING — decoupled arm built minimally in the matrix driver, not the pre-registered flag (2026-07-24)

**Build the DECOUPLED arm as a `--oracle-drive` control path in `run_p62_flight.py` plus a
`refly_decoupled` loop in `run_p62_matrix.py --coupling`, rather than the pre-registered
`run_p62_flight.py --arms decoupled`.** Why: the pre-registered command named a flag surface that did
not exist. The design is unchanged — same 25 seeds, warm perception byte-identical to the coupled arm,
only the PID input swaps warm-track → oracle `actor_box`. Recorded openly as a deviation. *Given up:*
nothing measurable; the *implementation path* differs, the experiment does not. *Also decided:* the
decoupled re-fly runs `build_grounding_carry(carry_only=True)` so it never boots a Jetson
`llama-server` — in `oracle_gt` mode the warm producer seeds from the GT box and never calls
`acquire`, so only SAM2 carry (3090, capped 2.69 Hz) + PID + CARLA render are exercised. Avoids a
pointless device dependency that could fail the re-fly for a component it does not use.

### P6.2-COUPLING — read the bounded null as a null, never as equivalence (2026-07-24)

**Report the non-significant Wilcoxon (p=0.596, CI within the noise band) as a *bounded null* — "any
coupling penalty is below the noise floor" — and never as "coupling proven harmless."** Why: the test
is two-sided and n=25 with a warm-arm noise band estimated from only 3 rep pairs (one of which,
seed1, carries the whole 6.70 px band while the other two are <1 px). Absence of a detected effect at
this power is not equivalence. The frozen gate anticipated exactly this and named it a bounded null.
*Given up:* a stronger "closed-loop coupling is free" headline the data cannot support. *Also
recorded:* the coupled/decoupled *mean* divergence is stochastic carry drift, not coupling — it fires
in the decoupled arm (no feedback loop), so attributing it to the loop would be a causal error the
median/signed-rank correctly avoid.

### EXP-1 — carry at image_size 640 by default (the elbow), 1024 size-gated fallback (2026-07-24)

**Adopt SAM2 track-res 640 as the default carry resolution — the measured elbow — keeping 1024 as a
size-gated fallback for small/few-pixel targets.** Why: the 7-point sweep shows carry IoU plateaus above
512 (640 = 0.811 vs 1024's 0.816, inside run-to-run noise) while on-device Hz is flat-high below 640
(~9–10 Hz, overhead-bound) then halves per size step — so 640 buys **2.5× throughput (5.76 vs 2.34 Hz)
for a −0.005 median-IoU cost**. The earlier 768-default call is superseded: 768 is past the knee (4.08
Hz for the same accuracy 640 gives at 5.76 Hz). *What was given up:* not a blanket low-res switch — 9/38
small/distant clips collapse below ~896 and only `held_frac` (not median IoU) exposes them, so a naive
global 640 trades a tail-risk of dropping sub-pixel targets. The size-gated fallback keeps both; below
512 is never worth it (speed saturates, IoU keeps dropping). *Also decided:* the "ground at 1080p /
track at 640" premise stays **shelved** on this data — 720p UAV123, VLM trained ≤1024, seed box
res-independent inside SAM2 — so the only live knob is track-res, which this maps. A true high-res-source
variant needs new ≥1080p footage (follow-up, out of scope).

### EXP-2 — keep NL referring-expression as the deployed select interface; the point-crop is an efficiency lever, not an accuracy fix (2026-07-24)

**Do not replace the NL referring expression with the operator point-crop as the primary select
interface on this evidence.** Why: at the deployed operating point (0.25-IoU delivery + on-device
SAM2 carry) PT and NL are statistically indistinguishable — WSEL 24/26 vs 22/26 and SWAP 26/26 vs
24/26, both McNemar MISS (b+c below the reachable floor at n=26). The carry closes whatever grounding
gap the pointer opens, so the pointer earns no extra delivered PASS. *What the pointer DOES buy,
recorded so it is not lost:* under a strict grounding-IoU criterion it grounds the target at **4×
lower VLM feed resolution** (PT@256 ≥ NL@1024) with better peak localization — a real compute and
precision win. So the point-crop is adopted as an **optional low-latency / low-res grounding path**
(useful when the VLM feed budget is tight or the target is a few pixels in a wide scene), not as the
default interface. *What was given up:* the stronger "language hurts select, the pointer fixes it"
claim — the data says grounding is symmetric (R-38 confirmed), the residual select failures are
carry/delivery, and the NL framing stands on its own. *Consistency:* every discordant leaned PT and
PT never lost a SWAP cell, so a larger-n follow-up could still surface a small PT edge — noted, not
claimed. All carry on the Orin (`machine=jetson`); the 3090 ran only the source frames' storage, no
tracker.

### Live demo panel — four orthogonal switches, and ORACLE designation as one of them (unnumbered infrastructure, 2026-07-25T14:24Z)

**`runners/carla_debug_ui.py` becomes the live demo of the whole deployed stack, structured as four
independent switches — PILOT `spectator|copter`, ACQUIRE `warm|cold`, DESIGNATE `vlm|oracle`, FOLLOW
`manual|assist|auto` — instead of a single scripted showcase.** Why: the thesis has four separate
claims (P6.1 pose-slaving, P5.1/P6.2-DELIVERY maintain-and-deliver, G6 grounding discrimination,
P6.2 control coupling) and a demo that fixes all four at once can only show the happy path. One
switch per claim means a viewer can *turn off* the thing being defended and watch it fail, which is
the only demonstration that carries information. Everything stays live in every combination — CARLA
on the 3090, SITL physics, both models on the Orin — so there is no replay path to drift from the
deployed system. *What was given up:* a shorter, always-impressive canned demo, and the option of a
recorded-run mode (rejected: a recorded number in a demo is indistinguishable from a live one on
screen, and this repo has already been burned by exactly that class of confusion).

**`DESIGNATE=oracle` deliberately puts the CARLA projected box into the seed, and the panel prints
that it did.** Why: at 45 m nadir the deployed q8_0 cannot discriminate a car (G6), so with `vlm`
designation *every* run fails at stage one and the carry+control half — the part P6.2-DELIVERY
actually measured — is unobservable. `oracle` reproduces the flagship's scope exactly. Measured the
same afternoon on one Town10HD_Opt at 45 m: `oracle` holds 231/234 carry steps with the copter under
its own AUTO control, `vlm` lands the box on a painted road marking and holds 0/417 (`DRIFT 82 s`)
with nothing downstream failing. *What was given up:* the appearance of an end-to-end autonomous
demo. Mitigations, because a GT seed in a demo is a real integrity hazard: the switch is named in the
on-screen mode strip every tick, `oracle` seeds only the *first* box (AUTO reads `track["box"]`,
never `track["actor"]`), and `runners/CARLA_DEBUG_UI.md` states in two places that an `oracle` run is
a carry+control claim only.

**Actor lifecycle: clear on every exit except hot reload, and offer scorched earth.** Why: leaked
actors do not merely accumulate, they *fabricate a scene*. Four unattended runs left 190 vehicles /
20 walkers / 3 orphaned cameras in Town10, re-spawned onto the same seeded points, interpenetrated
and physics-locked — and a lock rate measured against that pileup reads as a tracking result while
actually being a measurement of stationary duplicate cars. Every scene characterisation taken before
the fix is void. Reload keeps the fleet (that is the point of a reload); every other exit clears, and
`--clean-world` / "clear all" destroy every traffic actor and camera in the world, not just this
process's. *Also decided:* spawn points are sorted by distance to the camera and, in copter mode, the
spawn waits until after take-off — a correctly-cleaned world with cars spread over all of Town10 put
zero targets under the nadir footprint, which is the opposite failure and just as misleading.

**The panel's carry runs at `image_size` 512, not EXP-1's adopted 640.** Why: EXP-1 chose 640 as the
accuracy/throughput elbow for *measurement*; a live tool additionally needs the tracker to outrun the
5 Hz feed so the catch-up after a grounding call converges, and EXP-1's own sweep puts 512 at 8.71 Hz
against 640's 5.76 Hz (the panel measured 9.3 Hz / 107 ms at 512 on the Orin, in-tool). *What was
given up:* EXP-1's 512-vs-640 accuracy gap — median IoU 0.780 vs 0.811, i.e. 96% of 1024's accuracy
instead of 99.4% — plus the small/distant-target tail that the size-gated 1024 fallback protects.
Acceptable in a demo, not acceptable in a harness.
No measured number should be taken from this panel at 512; `runners/run_p62_matrix.py` remains the
place where a rate becomes a result.

### Live demo panel — the layout *is* the pipeline; guidance by badge, not by wizard (unnumbered infrastructure, 2026-07-25T15:35Z)

**The panel's chrome was rebuilt so its geometry encodes the operator's order of
operations: a header of five status lamps, a 340 px rail of five numbered stage cards
(WORLD, PILOT, DESIGNATE, DELIVER, FOLLOW) each carrying its own live number, one amber
`NEXT` line naming a single action, the flown view taking every remaining pixel, and the
verdict bar promoted to the largest text on screen.** Why: the previous build was six
full-width control rows of identical visual weight above the video, with the two lines
that carry the thesis — the per-stage timings and the mode echo — in the smallest,
lowest-contrast text on the panel. Nothing said what to press first, so the tool was
usable only by whoever had just written it, which fails its actual purpose (a supervisor
or an examiner driving the deployed stack unaided). Per-stage numbers moved *next to the
control that causes them* for the same reason: `ground 8500 ms` sitting inside the
DESIGNATE card is an argument; the same number in a strip at the bottom is telemetry.
*What was given up:* horizontal room for the video (a fixed 340 px column, permanently),
and the tidy two-tab Notebook that used to separate the click-designate and
caption-designate paths — deleted, because it read as two ways to do the same thing and
hid whichever one you were not on. Both are one card now, ordered by which one to reach
for at 45 m nadir (Shift-click point crop first, typed caption second).

**Guidance is one computed hint plus a per-stage badge colour, not a wizard and not
hiding.** Why: three cheap properties at once. Progressive disclosure by *disabling and
ordering* rather than by hiding costs no geometry pass — and the tick that would pay for
one is the same Tk thread that flies the camera (finding 8), so a layout that reflows on
state change buys confusion in the flight path. A wizard would also be wrong on the
merits: the four switches are *orthogonal by design* (the previous decision entry), and a
linear wizard implies an order they do not have. The `NEXT` hint is therefore computed
from the **last satisfied** stage, not the first unsatisfied one, so `spectator` — a legal
way to run the entire demo — does not pin the panel on "arm the copter" forever while it
is carrying a target. Mode switches became radiobuttons (state visible without opening
anything); comboboxes stay only where the widget picks a *value* (map name, the two
resolutions). *What was given up:* enforcement. Nothing stops an operator pressing stage 4
before stage 3; the badge just stays grey. Deliberate — this is a tool for provoking
failures, and a wizard that refuses out-of-order input would block exactly the
combinations worth trying.

**Every per-tick widget update goes through `setw()`, which memoises the last kwargs and
skips Tk when nothing changed.** Why: the redesign added ~15 widgets that are rewritten
every tick (5 lamps, 5 badges, 5 card values, the hint), and one Tk thread both paints the
frame and integrates the fly step, so display cost is fly cost — measured previously at
13.3 m/s against a 45 m/s slider before the display path was fixed. A no-op `.config()`
still schedules a redraw. *What was given up:* a global `_shown` dict keyed by `id(widget)`
— fine here because widgets live for the process, wrong in any code that destroys them.

**Layout is verified by screenshot, and the screenshot tool reads the window's own pixels
(`xwd -id`), never a screen region.** Why: `pack()` has no error path for "does not fit" —
the first build of the rail silently dropped an entire card and clipped another, exiting 0
with no warning, which is the same failure class as a black render and is why the repo has
a look-at-it rule. Two mechanical guards came out of it: `ui_shot.py` filters
`xdotool search` results to the real client window (`WM_STATE`, because the WM's frame
matches the same name and is the *larger* window — picking "largest" produced a black grab
with a title bar) and fails the run if >99% of the image is one colour. *What was given
up:* nothing. The earlier region-grab implementation was strictly worse: it captured
whatever was on top, and once captured the user's browser.

### Live demo panel — the numbers move into one column, and the freeze reports were one bug wearing two hats (unnumbered infrastructure, 2026-07-25T17:20Z)

Second round on the same panel, all of it driven by an operator using it live. The reports
were: the mode switches are unreadable, `g` is unexplained, the maintained box is invisible,
the Jetson view is useless, the numbers are in four places, `to origin` and `arm + takeoff`
freeze the view, and `wasd` fights the rotated view. Detail and pixels in
`runners/CARLA_DEBUG_UI_FINDINGS.md` (findings 17-20, `carla_ui_proof/ui-loop-closed.jpg`,
`ui-maintained-vs-delivered.jpg`).

**Every number in the panel lives in one 380 px instruments column; the rail carries
controls only.** Why: they were in the lamps, in each card's header, in a bar across the
bottom *and* in a telemetry block in the rail — four places to read one machine, which is
what "please centralize it" was reporting. The column's five per-stage lines are numbered
`1..5` to match the rail cards on the far side of the picture, so a stage's cost is one
horizontal glance from the control that produced it, and the lamps drop to colour plus one
word (a lamp answers *is it alive*, the column answers *how well*). Added at the same time,
because the operator asked for it and because none of the existing readouts showed a
*trend*: a 5 Hz x 240-sample sparkline (`draw_graph`, cv2 into a numpy array — matplotlib
in the tick that flies the camera is not an option) with a state ribbon over carry Hz, lag
frames and an on-target EMA. *What was given up:* one fact can no longer sit next to its
own control, and the graph is a fixed-height blit whose cost is paid at 5 Hz.

**The Jetson's own feed is no longer displayed at all.** Why: it is the *same camera* as
the flown view at a fifth of the pixels, so it showed nothing new while costing a resize
and a blit per feed frame. What the Jetson sees that the flown view cannot show is box
latency — and that is a number (`lag`), not a picture. *What was given up:* the visual
"these are two different machines" cue; the mode echo now carries that in words.

**`busy` splits into world ops and link ops, and long ops report progress.** Why: `fly()`
stood down for *any* background operation, so a ~40 s SITL boot + climb froze the render
tick and refused every button in silence — reported as "arm+takeoff freezes the world". A
world op (load, spawn, clear) invalidates the CARLA handles `fly()` steers and must still
stop it; a link op (arm, takeoff, land) touches only MAVLink. `arm_and_takeoff`/`wait_alt`
now take a `note` progress sink so the panel says `climbing 31/45 m`. *What was given up:*
one flag became two plus a string, and a link op can now overlap the render tick — safe
only because MAVLink and CARLA share no handles.

**`to origin` is a target owned by the control loop, not a blocking helper.** Why:
`reset_to_origin()` blocks up to 40 s *and* calls `recv_match("LOCAL_POSITION_NED")`
itself, stealing the pose the camera is slaved to (finding 15's starvation, from the other
side) — the copter kept flying and the view stopped following it. Split the non-blocking
half out as `sitl_fly_leg.send_position()` and let the tick that already flies resend it,
clearing on tolerance or timeout and reporting distance-to-go. *What was given up:* the
blocking version's guarantee that the copter *is* at the origin when the call returns;
callers that need that (the matrix harness) keep `reset_to_origin`.

**`wasd` is view-relative in copter mode.** Why: the nadir camera yaws with the arrow keys,
so world-absolute keys steer sideways on screen as soon as the view is rotated, which reads
as broken controls. `manual_velocity` rotates the key vector by the gimbal yaw. *What was
given up:* the ability to fly a known compass heading by key; the NED telemetry in the
instruments column is what shows heading now. The rotation is the **gimbal's** because SITL
never sends vehicle yaw (R-10).

**The maintained box is amber corner brackets, not a thin grey rectangle.** Why: "the first
track is grey and hard to see" — a distinction that only survives close inspection does not
do the job, and this one carries the whole warm-start claim (the system tracks things nobody
asked about). Amber is already the panel's "not yours yet" colour (the `NEXT` hint, the
maintaining badge, the ribbon). *What was given up:* nothing measurable; the test now
asserts colour, thickness *and* that the box stays open, since a closed rectangle would
pass a colour-only check.

### The N=1 scope of warm-start is stated, and "anticipatory grounding" is retired as a headline (R-51, 2026-07-25T19:05Z)

Raised by the author while driving the demo panel: *"if it only works for one object and
the user has to preselect it manually, is it a bit useless? I'm starting to doubt the
validity of warm vs cold."* The objection is half right, and the half that is right is a
scope statement the thesis had not made explicitly.

**"Anticipatory grounding" is retired as a framing.** Why: at N=1 the WARM arm's
information advantage *is* the target identity — the system was told which object to hold,
so it anticipates nothing, it holds. The mechanism that would have made the comparison
non-trivial (maintain K unnamed candidates, let the command pick) is the select arc, dead
across 8 runs with `c=0` throughout. Keeping the word would claim a capability the
apparatus never demonstrated. *What was given up:* the most attractive framing in the
project, and with it the narrative arc the Part V proposal was written around.

**The claim is restated provenance-agnostically.** Why: read what P6.2-DELIVERY measures —
`cold_target_exits_frame=0`, `on_target=0` in 23/25. Cold does not fail by picking wrong;
it fails because the box lands ~4.85 s (~146 frames) after the command. So the defensible
statement is *a box that exists **before** the command produces a followable lock; a box
**computed after** it does not — grounding cannot sit on the command path at 8 GB*, and it
holds whatever produced the box (click, prior track, pre-flight designation, an off-board
datalink). This is strictly weaker than the retired framing and strictly more robust: the
N=1 objection does not touch it. *What was given up:* an autonomy claim, in exchange for a
hardware-capability claim — which is the thesis's actual question.

**The cold arm is defended as a baseline, not softened.** Why: it is the system Parts II–IV
built and deployed (phrase to VLM to follow), measured on real UAV123 video in R-34 at
3/25. Calling it a strawman would require calling the project's own prior deliverable one.

**The forward implication is recorded as the reason to run the comparison at all.** Why:
the warm/cold pair localises the binding constraint to **acquire latency**, since
everything downstream of a correct box at command time is certified separately — P5.15
(the carry is not the fragile part, 24/25 vs floor 18, p=0.0016), P6.2-COUPLING (bounded
null under self-induced ego-motion), P6.2-SHOWCASE (24/24 at median IoU 0.92 on the Orin,
0.960 flight parity). An acquire pruned to ~1 s would put the deployed carry inside its
already-demonstrated envelope, bounded to the tested regime (nadir, daytime, UAV123/CARLA,
car or person) and with carry drift still owning the residual failure. *What was given up:*
nothing — this was true before and simply unstated.

**What was deliberately not done:** the energy cost of maintaining is still unmeasured, and
it is the sharper criticism (R-52, proposed). WARM burns SAM2 at 2.69 Hz for the whole idle
window to save 4.85 s once, and no watt figure in this repository says whether that trade
survives a long window.

Landed as caveat S6 on `P6.2-DELIVERY-warm-vs-cold-closedloop` with pointer caveats on
`P5.1-warm-vs-cold` and `P5.2a-warm-generalization`, regenerated into `stats-report.md`;
R-51/R-52 in `thesis/REMEDIATION.md`; finding 21 and the DESIGNATE card text in the panel.

### P6.7 — the SAM2 carry bridge is RESIDENT, not per-designation (2026-07-25T19:50Z)

**Adopt a pre-warmed, process-resident SAM2 carry bridge: spawn it once at panel start-up,
`init_state` per designation, never `Popen` per follow.** Why: the decomposition says
**80% of the 6.15 s designation-to-live-track seam is process start-up** — `ssh` spawn
0.301 s + `import torch`/`sam2` 2.846 s + `from_pretrained` 1.800 s = 4.95 s — and only
0.361 s is the tracker actually catching up to the present. (`warmup_init` 0.670 s is a
fourth start-up term but residency only shrinks it to 0.120 s, because `init_state` still
runs per designation.) None of those terms can be optimised on an Orin; they can only be
*already paid*. Residency
pays them once, at start-up, in the same window where the panel already prewarms
`llama-server` for exactly this reason. Measured effect: median `t_handoff` 6.311 s ->
0.515 s at the deployed 4.85 s grounding lag (12.3x), 6.148 s -> 0.299 s on the oracle
click (20.6x), all 25 pairs concordant, Wilcoxon p=1.228e-05 on the registered lag-4.85 arm
(5.96e-08 at lag 0).

*What was given up:* a resident SAM2 process holds GPU memory for the whole session on an
8 GB board that also holds `llama-server`. That was the pre-registered honest risk (G3) and
it was measured, not argued: a resident tracker costs the VLM **x1.000** (`ground_ms`
3791.1 -> 3791.2 ms over 25 paired requests) and leaves **1315 MB** of `MemAvailable`, with
zero `rc=-9` over 50 consecutive designations on one bridge. The second thing given up is
crash isolation: a per-designation process dies with its follow, a resident one carries a
bad CUDA state into the next designation. Mitigation is the existing one — the bridge is a
subprocess behind a length-framed pipe, so a non-zero `rc` is detectable and a respawn is a
cold start, i.e. exactly today's behaviour as the failure mode rather than the normal mode.

*Why this was never recorded before:* it never was a decision. Per-follow `Popen` is what
`orin_carry` happened to do, while `run_p62_flight.py`, `select_exp2.py`, `select_exp3.py`
and `carry_res_sweep.py` all already reuse one live bridge across cells. The offline
harnesses had the fast path and the live panel — the one an operator watches — had the slow
one, because nobody wrote down which was intended. This entry is that missing record.

*Where it landed:* `runners/carla_debug_ui.py` on `main` (R-53, closed 2026-07-25T20:20Z),
as its own commit after the campaign merged. The panel's own `catchup_s` then read
**0.343 s** on a live `--pilot copter --smoke` designation, against the 6.52 s median of
the 64 pre-change traces.

*Scope:* measured on the Orin at 15 W + `jetson_clocks`, `image_size=512`, over the CARLA
GT bank replayed from disk through the deployed ssh-stdio bridge. The link to live flight is
that the COLD arm reproduces the panel's own traces (`steps_to_live=3` matches 11 of 13
oracle traces; 6.148 s sits on the live 64-trace p25, live median 6.52 s). Carry resolution
is deliberately not swept here — EXP-1 owns that knob (R-46 open).

### P6.7 — `CATCHUP_JUMP` stays at 12; the backlog is not the knob to turn (2026-07-25T20:10Z)

*Decision:* leave `CATCHUP_JUMP = 12` alone. RQ-e swept it over {1, 12, 999} on 25 clips at
the 4.85 s grounding lag and no value gets both the sub-second handoff and the track.

*Why:* replaying every frame (`jump=1`) is the only setting that keeps a usable median IoU
(0.596, 17/25 clips on target) and it costs **5.312 s** — longer than the 4.85 s of world it
is crossing, which hands back the entire residency win and lands 5x over the G1 bar. In the
other direction, 12 and 999 are statistically the same policy (paired exact McNemar b=4,
c=2, p=0.6875; identical swap counts; median IoU 0.000 in both), so the deployed value is
already past the cliff — skipping 12 frames loses the identity as thoroughly as skipping the
whole backlog. There is no interior optimum to tune toward, only a monotone trade.

*What was given up:* the 17-of-25 track survival that `jump=1` demonstrably reaches. That is
a real number and it is being declined on latency grounds, because a 5.3 s handoff is the
problem this campaign exists to remove.

*What it redirects:* the residual failure is now located upstream of the bridge. The gap
exists because the seed box was drawn on a frame 4.85 s old; `jump=999` is the direct test of
"apply the stale box to the live frame" and it fails 17/25. So the next lever is grounding
latency itself, or a re-ground at the live frame once the tracker is already warm — not a
smarter way to cross a gap that should not be there.

*Scope:* WARM arm only, lag 4.85 s, `image_size=512`, Orin at 15 W + `jetson_clocks`, CARLA
GT bank replayed from disk. RQ-e was pre-registered without a gate; the McNemar values above
are descriptive, are not in `thesis/claims.json`, and are not Holm-corrected.

### Crop from the 960 display frame, not the native 1920 sensor frame (EXP-4, 2026-07-26)

*Chosen:* MODE 2's click-crop is cut from the same 960 frame `carla_debug_ui.py:on_image()`
already produces. `on_image` keeps its `INTER_AREA` downscale and the raw 1920 sensor buffer is
never plumbed through to the crop path.

*Why:* the pre-registered primary contrast measured it directly. C (native 1920, 512 window)
vs D (960 downscale, 256 window LANCZOS-upscaled to the same 512 feed at the same FOV) is
b=1, c=0 on hit@0.5 — one discordant pair against a 6-pair floor. S0 had shown the detail is
genuinely there (Laplacian-variance ratio 4.8-7.5x, visible by eye), so this is not "no
difference in the pixels"; it is that q8_0 at a 512 feed cannot convert that difference into a
grounding win. What it *can* convert is magnification: A vs D is b=1, c=8, p=0.039 with zoom as
the only change and no new detail at all.

*What was given up:* the +0.13 mean-IoU margin C holds over D (0.7651 vs 0.6350, Wilcoxon
p=0.0029). That is a real quality gap and it is being declined on plumbing grounds — carrying
the 1920 buffer to the crop site costs a second full-resolution copy per frame in the live UI
for a gain the binary metric cannot see.

*What it preserves:* the MODE 2 proposal itself. C vs A — the composed change against today's
deployed crop — is b=8, c=0, p=0.0078, hit@0.5 0.60 to 0.92. Cropping around the operator's
click is the lever; where the crop is cut from is not.

*Scope:* single-frame grounding only, no carry, q8_0 on the Orin at a 512 feed, 25 CARLA
`Town10HD_Opt` nadir targets at 61-221 px footprint. A larger feed or a stronger model could
reopen it; nothing here tests that.

### The bank caption is read off the rendered pixels, not the blueprint attribute (EXP-4)

*Chosen:* the operator phrase's colour word comes from the target's own vehicle-tagged pixels
inside the GT box — median hue when the body's median saturation clears 60, median lightness
otherwise.

*Why:* CARLA vans and trucks carry a fixed livery and ignore the blueprint `color` attribute.
The first bank captioned a van the renderer drew **white** as "the dark red van", and the model
correctly grounded a genuinely red van elsewhere in the crop. Every log in that run was clean;
the defect was found only by opening the C-loss overlay, which is the "look at it" rule paying
for itself. Medians rather than percentiles because a 90th-percentile rule then called a black
car white off its UBER lettering and a white car blue off a racing stripe.

*What was given up:* discriminative captions. Town10's fleet is 9 grey / 9 white / 6 red /
1 yellow across the bank, so many targets share a phrase and the absolute hit rates are capped
by ambiguity rather than by perception. The caption is identical in all four arms, so paired
contrasts are unaffected — but no absolute rate from this bank should be read as a grounding
ceiling.

---

### The degenerate-box guard is dropped, not retuned (EXP-5, 2026-07-26T22:55Z)

*Chosen:* ship the crop with **no** guard. The proposal's "ignore a box that grows 2.5x in one
frame" veto, plus the displacement veto added to catch P5.21's `car10` mechanism, are recorded
as a measured negative and removed from every downstream arm.

*Why:* the guard does not merely fail to help — it self-latches. On veto the pre-registered
policy holds the previous box, which freezes the reference the *next* step's ratio and
displacement are measured against, so the first veto makes the second more likely and the
sequence never recovers. Measured: `car13` under plain+guard fired 24 vetoes and 20 lost steps
for a median IoU of 0.000, on a clip the unguarded control held at 0.639; `bike3` under
crop+guard vetoed one genuine motion burst at area ratio 3.67 and then watched the ratio climb
3.10 -> 5.95 monotonically against the frozen box, ending at 0.000 where the unguarded crop
absorbed the same burst and finished at 0.92. Small boxes make it structural rather than
tunable — `disp_norm` divides by the previous box's long side, and `car13`'s box is 15x9 px, so
ordinary sub-pixel jitter clears any threshold. Retuning `D_MAX` moves the failure in the wrong
direction: a *tighter* threshold fires more often and latches sooner.

The threshold itself was also contaminated by its own pre-registered rule — it is the 99th
percentile of the CONTROL arm's displacement, and CONTROL's distribution contains the drift
events the veto exists to catch (ALL p99 4.206, TAIL 4.559, EASY 1.734). The run went out at
the pre-registered 4.2 rather than swapping in the EASY-only 1.7 post hoc, because honouring a
bad rule and recording why it was bad is worth more than a number that was chosen after seeing
the data. The verdict does not turn on it either way.

*What was given up:* the only protection against a genuinely degenerate box in the deployed
UI. Nothing replaces it — `carla_debug_ui.py`'s existing lost branch is now the sole recovery
path, and a box that blows up mid-flight will be carried until SAM2 itself returns `None`. That
is the status quo, not a regression; if a guard is wanted later it needs a reference that keeps
updating on veto (e.g. a decayed or motion-extrapolated `prev`), which is a different design,
not a different constant.

---

### EXP-6's treatment is a declared post-hoc promotion, with a held-out primary stratum (EXP-5, 2026-07-26T23:05Z)

*Chosen:* re-pre-register EXP-6 with **A4 (fixed 512 crop, dead-band re-centre, no guard)** as
TREATMENT, and make the **26 clips EXP-5 never touched** the primary stratum for the Wilcoxon,
with the 12 pilot clips reported separately and explicitly not load-bearing.

*Why:* EXP-5's pre-registered treatment was A5 (crop **+** guard) and it lost its kill gate.
A4 was a diagnostic arm that exists to attribute the effect, and it won. Carrying it forward is
selection on the pilot's own data, so the choice is either to bury it or to label it — and
burying a lever that recovered the tail at 2.7x the throughput of the deployed fallback would
be worse science than declaring the promotion. The held-out split is what keeps the declaration
from being cosmetic: the 12 pilot clips are the 8 hardest plus 4 near-ceiling controls, biased
in both directions, and 26 still clears the n>=25 floor on its own.

*What was given up:* statistical power on the stratum that matters, and probably the headline.
The held-out 26 are mostly at ceiling under plain carry@640, where a crop has little room to
add anything, so the pre-registered estimate is an honest p ~ 0.05-0.30 with a real chance the
primary comes back a TIE while the tail cut is a clear win. That is the correct trade — the
alternative is a p-value on 38 clips, 12 of which chose the arm.

### EXP-7 is not run, and the campaign closes at EXP-6 (2026-07-26T23:55Z)

*Chosen:* honour §9's entry gate literally — EXP-4 missed its primary, EXP-6 is a partial pass,
so the closed-loop composed run does not happen. Record it as a pre-registered non-run with
the reasoning, rather than quietly proceeding or quietly dropping it.

*Why:* the gate and the substance agree, which is the part that makes this easy. EXP-4
retired lever (a'), so MODE 2's crop-ground half is a crop of the 960 display frame — that is
`roi_reanchor`, already live at `carla_debug_ui.py:1901`. EXP-6 made the crop-carry half a
bounded null against the deployed carry (+0.0085 median IoU and zero PASS discordants on 26
held-out clips) everywhere
except the size-gated path. A composed TREATMENT built from "EXP-4's and EXP-6's winners" is
therefore the deployed CONTROL plus a null, and 25 live CARLA seeds would be spent measuring
the system against itself. The pre-registered estimate priced P(reaching EXP-7) at ~0.25 for
exactly this reason, so this is the planned branch, not a surprise.

*What was given up:* the one closed-loop number this campaign could have produced, and with
it any in-flight evidence for MODE 2 as a whole. The residual question — whether native
magnification pays somewhere the 960 path cannot reach — stays open and is *not* answered by
declining to run this design; S0's 40-px case is the regime where it would have to be asked,
and that needs a different experiment.

### crop512@640 replaces the size-gated 1024 carry fallback (EXP-6, 2026-07-26T23:55Z)

*Chosen:* the carry crop ships as the **fallback path only** — the operator's escalation for
small or distant targets becomes a fixed 512 native window carried at 640, instead of raising
`ORIN_CARRY_SIZE` to 1024 on the dropdown (`carla_debug_ui.py:2099-2101`). The default carry
stays plain@640, unchanged. **Implemented 2026-07-26T18:40Z** on its own branch off `main`,
not on the experiment branch — see the shipped-shape entry below.

*Why:* this is what EXP-6 actually licenses. Against plain@1024 the crop is statistically
indistinguishable on its pre-registered bounds (d_IoU -0.002 against 0.03, d_PASS -1 of 38
against 1 clip) at **2.7x** the on-device
rate — so on the escalation path it is strictly cheaper for the same accuracy. Against
plain@640 it is a null on the held-out 26 (zero PASS discordants), so promoting it to the default would be
shipping on a non-significant result and on 12 clips that chose the arm. Splitting the
decision along the stratum where the evidence differs keeps the deployed default resting on
its own measurement.

*What was given up:* the simpler story of one carry mode for everything, and the tail win on
targets the operator never escalates — the fallback is a manual dropdown, so a
resolution-gated target nobody flags stays on plain@640 and the crop never fires. Also: the
crop's failure mode (a slightly looser box, `exp6-loss.png`) now sits on the escalation path,
which is exactly where boxes are already hardest.

### EXP-3 is not a contradiction of EXP-2, and is killed rather than finished (R-47, 2026-07-26T16:20Z)

*Chosen:* close R-47 as **no contradiction**, and drop "finish EXP-3" from the candidate
slate instead of spending seeds on it. `ORIN_GROUND_RES` stays 512, but the comment
defending it is rewritten — the old rationale ("512, not EXP-2's 1024"; "256 starves colour
on a nadir car") had the mechanism wrong even though the value was right.

*Why:* EXP-3's `OPT`/`FULL` arms are not crop-vs-whole-frame. `select_exp3.py` varies exactly
one thing, `select_p55.ROI_RES = cfg["ground_res"]`; both arms crop the *same* 256 px native
window around the click. OPT feeds it at 256 (1.0x), FULL upscales it to 1024 (4x LANCZOS).
"FULL" means full *resolution*, not full *frame*. EXP-2's winning PT arm never overrides
`ROI_RES`, so it inherited 512 — a 2x upscale of that same window — and its NL baseline is
the whole frame at `MAX_SIDE = 1024`. EXP-3 therefore never re-ran EXP-2's configuration;
OPT sits one notch *below* EXP-2's operating point. Two runs measuring different knobs cannot
disagree. On the one axis they share — pixels on target fed to the encoder — all three
campaigns point the same way: EXP-2 crop > whole frame (hit@0.5 0.769 vs 0.654), EXP-3 4x >
1x on a fixed window, EXP-4 native-1920 crop > 960 feed crop (b=8, c=0). The colour claim is
also backwards: the rich caption more than doubles what the 256 crop finds (5/25 to 13/25 at
IoU 0.25), so colour is not starved — box precision is (mean IoU 0.229 vs 0.470). And the
headline "12 discordants to 0" is threshold-fragile: re-scored at IoU 0.25, the threshold
Parts V-VI use for delivered-PASS everywhere else, the rich leg is 13/25 vs 16/25, b=1/c=4,
**p=0.375** — a null. The effect needs a strict box threshold *and* a colour caption at once.

*What was given up:* the ~25 seeds and the tidy "we finished what we started" of completing
EXP-3 at n>=25. The question EXP-3 was actually asking — how far the upscale of a fixed crop
pays before latency eats it — is answered well enough for deployment by the latency alone
(median 9063 ms at 1024 vs 1017 ms at 256, 8.9x), and 1024 stays one dropdown away for an
operator who wants to pay it. Also given up: any right to cite EXP-3 as "crop hurts on CARLA".

### `grounding.contract` owns the deployed carry resolution and its rate (R-46, 2026-07-26T17:05Z)

*Chosen:* `CARRY_IMAGE_SIZE = 640`, `CARRY_FALLBACK_IMAGE_SIZE = 1024` and
`CARRY_HZ = 5.76` live in `grounding/contract.py`. `runners/carla_debug_ui.py` and
`runners/p62_producers.py` import them; the two files that run on the Orin outside the
repo (`carry_ssh_bridge.py`, `jetson_carry_service.py`) cite them in a comment and match
the value, and the bridge's default moves 1024 to 640. `CARRY_HZ` is re-derived at 640
from EXP-1 (5.76 Hz, Orin 15 W + jetson_clocks); the retired 2.69 is preserved as
`p62_producers.P62_ASRUN_CARRY_HZ`.

*Why:* four files each claimed to state the deployed carry resolution and gave three
answers, so any one of them read alone was misleading. The coupling was the live hazard,
not the untidiness: `CARRY_HZ = 2.69` is a *measured* constant at 1024, so moving the
default to 640 without re-deriving it rate-capped the replay carry against a resolution
nobody deploys — the producer would have modelled an on-board cadence 2.5x slower than the
real one. `contract.py` is the host because it already exists for exactly this failure
(Part I's prompt drifted across five copies), it is stdlib-only so the device service can
read it without torch, and every consumer already imports it. Note the 1024 rate itself is
double-measured — R-16 says 2.69 Hz, EXP-1 says 2.34 Hz on the same box — which is why the
two numbers now cited together (5.76 and 2.34) come from one campaign; mixing them would
make the 2.5x ratio meaningless.

*What was given up:* reproducing the published P6.2 matrix now needs `carry_hz=` passed
explicitly instead of inheriting the module default. That is the honest trade — the default
should describe the deployment, and the as-run cap is a property of that run, so it is
recorded next to it rather than left as the global. Also given up: keeping frozen
experiment scripts literal-free. They keep their own numbers on purpose — they record what
was measured, not what is deployed.

### The shipped carry crop is a checkbox, and its geometry moves into `grounding/roi.py` (2026-07-26T18:40Z)

*Chosen:* the escalation ships as a `crop 512` **checkbox** beside the carry dropdown, not as a
third value in it, and it applies to both follow paths (typed caption and Shift-click). The
window geometry — fixed side, slid inside the frame rather than clipped, re-centred only when
the box centre leaves the central 50% — is lifted out of EXP-5's as-run script into
`grounding.roi.fixed_window` / `outside_dead_band`, with `CARRY_CROP_SIDE = 512` and
`CARRY_CROP_DEAD_BAND = 0.5` owned by `grounding.contract` alongside `CARRY_IMAGE_SIZE`
(R-46). SAM2 is **not** re-seeded when the window moves: it keeps one state and simply sees a
shifted view, which is what EXP-6 measured. The crop is invisible downstream — the offset is
applied the moment the bridge answers, so `match_actor`, the overlay and the PID never learn
about it.

*Why:* a checkbox because it is a different lever from the dropdown. The dropdown sets
*pixels fed*; the crop sets *magnification at a fixed pixel budget*, and EXP-6's whole point is
that the second is the cheaper way to buy the first. Folding it in as a "512" entry would have
read as "carry at a lower resolution", which is the opposite of what it does. Re-seeding on a
window move was rejected without a measurement because P5.21 already priced it: a re-anchor
taken around an already-drifted box reinforces the drift (`car10`), and the dead band exists
precisely so the window follows the box lazily instead of chasing it. Sharing the geometry
through `roi.py` rather than copying `run_exp5.py:window` keeps one implementation on the
deployed path; the experiment scripts keep their own copies as the as-run record.

*What was given up:* the crop cannot fire automatically on a small/distant target — an operator
has to tick it, which is the tail the EXP-6 entry above already flags. And the dead-band
re-centre is only evaluated on frames where the carry returned a box, so a long run of lost
masks leaves the window where it was; that is deliberate (a window re-centred on nothing is
worse than a stale one) but it means a target that leaves the window during an occlusion is not
recovered by the crop path.

### EXP-1/EXP-2/EXP-6 are demoted to engineering measurements, not registered as claims (R-44, 2026-07-26T18:55Z)

*Chosen:* the three resolution/carry-mode campaigns stop publishing inferential numbers in the
ledgers and gain an explicit "engineering measurement, not a registered claim" label. The
p-values are **moved, not deleted** — they stay in the campaign READMEs, which are already the
source of truth while the ledgers are rollups. `thesis/claims.json` gains no entries, so Part
VI's Holm family stays at m=2. The alternative on the table was registering all three.

*Why:* each campaign was run to *choose an operating point* — a carry resolution, a grounding
feed resolution, a carry mode — and each stopped once the elbow was located; none was
pre-registered against a hypothesis. Two of them could not have supported a claim at their n
whichever way the numbers fell: EXP-2's design needs b+c>=6 discordant pairs deflated to 13
clips and produced 4 and 2, and EXP-6's primary stratum is at PASS ceiling in both arms with
zero discordant pairs. Registering them would have grown the family from m=2 to m=4 and
tightened Holm on P6.2-DELIVERY — a real cost on the flagship, paid to admit numbers that
decide nothing. Leaving them as published p-values outside the registry was the one option
ruled out: invisible to `run_stats.py`, to the family accounting and to every integrity test,
which is the R-39 recurrence hazard.

*What was given up:* the rhetorical convenience of "p<0.05" on the crop-mode parity gate, and
strict I1 provenance in the rollups — a reader now has to open the campaign README to see the
test that was run. Also given up, deliberately: consistency inside the crop-mode campaign.
EXP-4 has the same defect and is left as-is (R-55) because the scope asked for was these three,
so until R-55 lands `experiments/2026-07-26-crop-mode/` has one experiment labelled and one not.
### A contaminated repeat is excluded by name and re-run, not silently averaged in (P6.6, 2026-07-26T16:20Z)

*Chosen:* arm B repeat 2 is dropped from every reported P6.6 number and arm B re-run alone into a
second run dir (`runs/p66_b_clean`), so B is reported on three clean repeats. The exclusion is by
record name and lives in code, not prose: `make_proof.py --exclude p66_maintain_cost:B_r2`, which
is also the script's default, so a bare invocation reproduces the report. The contaminated record
stays in `results.json` and is tabulated in the README rather than deleted.

*Why:* the CARLA debug panel was started on the host mid-arm, and
`runners/carla_debug_ui.py:2827` prewarms the Orin at panel start-up — it boots `llama-server`
and spawns a SAM2 carry bridge on the device. That is a second GPU consumer inside a measurement
window, and it shows on three independent axes (`ram_max` 7460 vs 3243-3497 MB, achieved rate
5.987 vs 6.273-6.280 Hz, mean power up 0.09 W). Averaging it in would have pushed the headline
maintain figure the wrong way for a reason that has nothing to do with the carry. Re-running is
cheap — 6 minutes of device time — and the rerun landing within 0.03 W and 0.000 Hz of the two
clean repeats is itself the evidence that the exclusion was correct rather than convenient.

*What was given up:* strict "report the matrix as scheduled" purity — arm B's three repeats no
longer share one randomised order with the other arms, so its thermal position in the sequence
differs from the design. That is acceptable here because the cooldown gate (idle until `tj` is
within 2 C of the A0 median) removes the soak the randomisation was protecting against, and G1
shows no thermal trend to protect against anyway. Also kept, deliberately: the messier record.
-4.7% of the carry rate for one competing process is the only measurement in the repo of what
contention costs the maintain, and it would have been lost by deleting the row.

### The as-run driver is not patched after the run, even for an obvious fix (P6.6, 2026-07-26T16:20Z)

*Chosen:* `run_p66.py` writes `results.json` once, at the very end of the whole matrix. That is a
1.5 h single point of failure and the fix is one line (write after each arm). It is **not**
applied. The hazard is recorded in the README's *What did not work* and the fix is assigned to
whatever driver runs next.

*Why:* the committed script has to be the script that produced the numbers. Editing it after the
run — however harmlessly — breaks that correspondence, and the whole point of committing the
driver beside the record is that a reader can tell which code emitted which figure (HANDOFF I1).
An improvement that costs provenance is not free.

*What was given up:* the next run of this driver still risks the same loss. Partly mitigated
already: the per-arm `/tmp/p66_*.json` files on the device are the real recovery path and are now
archived into `runs/p66_maintain_cost/device_json/` — a fixture rebuilt from exactly those files
is how `make_proof.py` was developed before the matrix finished, so the recovery path is tested,
not hypothetical.

### 640 stays the deployed carry default, despite 512 winning on energy per frame (P6.6, 2026-07-26T16:20Z)

*Chosen:* no change to the deployed carry resolution. EXP-1's adopted 640 stands, and P6.6's
512-is-cheaper finding is recorded as a characterisation result plus a non-blocking follow-up, not
a deployment change.

*Why:* the energy axis is unambiguous — 512 runs 1.60x the rate at 0.15 W *less* draw, so joules
per carried frame falls 38% — but energy was never the reason 640 was chosen. EXP-1 picked it on
the accuracy elbow (99.4% of 1024's median IoU), and P6.6 measured no accuracy at all: it carried
frames to load the GPU, not to score IoU. Changing the default on an axis the accuracy campaign
did not evaluate would be trading a measured property for an unmeasured one. The two results
agree in direction, which is worth stating; that is not the same as a shipping gate.

*What was given up:* a 38%-cheaper carry that is sitting there, and the tidiness of the UI and the
adopted default agreeing (`carla_debug_ui.py` already runs 512, so the deployed panel and the
adopted default still differ). Re-checking 512 against EXP-1's accuracy staging is the follow-up
that would close it; it is cheap and nobody is blocked on it.

### `PRUNE_AFTER` 100 to 16, and D-R16.2's rationale is superseded by measurement (EXP-8 Stage 0, 2026-07-26T19:20Z)

*Chosen:* adopt `PRUNE_AFTER = 16` for the deployed carry. **D-R16.2's *decision* (don't change the
constant on a throughput bench) was right and is honoured — this is the gated change it asked for.
D-R16.2's *rationale* is superseded and should not be cited again.**

*Why:* D-R16.2 deferred the change because "the ring is a memory *horizon*, not just a buffer —
shortening it is a behavioural change to how long SAM2 can re-find an occluded target." EXP-8
measured that claim instead of reasoning about it, and it is false above 15 frames. At step *n*
SAM2 attends to mask memory from {*n*−`num_maskmem`+1 … *n*−1} and object pointers from
{*n*−(`max_obj_ptrs_in_encoder`−1) … *n*−1} ∪ {0}; `StreamCarry` has popped {*j* ≤ *n*−1−P}. Those
sets stop overlapping at **P ≥ 15**, and the run confirms it to the frame: all 360 steps
(3 clips × 120) are **sha1-identical to P=100** at P=15 and above, collapsing to 21.9% at P=14.
Not "equivalent within noise" — the same bytes. So above 15 the ring is not a horizon at all; it
cannot extend SAM2's, which is set by `max_obj_ptrs_in_encoder`. The behavioural risk D-R16.2
protected against does not exist in that range, and there is nothing left to gate.

16 rather than 15: one frame of margin against an off-by-one in a future stride or catch-up change,
for 18 MB. Below 15 the output does change, so 15 is a real cliff and sitting on it is not worth
saving one frame.

*What it buys:* ~670 MB of host RAM back, steady-state, on a board with 8 GB shared between CPU and
GPU (measured 8.1 MB per retained frame at `image_size=640`; growth over a 120-step run falls from
853.3 MB at P=100 to 182.3 MB at P=16). This is the memory D-R16.2 identified as the OOM cause at
n=2 candidates, now recovered with a measured guarantee of no behavioural change rather than a
throughput argument.

*What was given up:* nothing measurable — that is the unusual part. Accuracy is flat (median IoU
0.908–0.910 across every P tested, *including* P=8 where only 12.5% of steps are bit-identical) and
rate is flat (~173 ms/step across all P). The ring is not a speed/accuracy knob in either
direction; it is pure RAM. What is genuinely given up is head-room for a *future* change: any edit
that widens SAM2's read window — raising `max_obj_ptrs_in_encoder` above 16, or
`memory_temporal_stride_for_eval` above 1 — silently invalidates P=16 and must move the ring with
it. The bound is `P ≥ max_obj_ptrs_in_encoder − 1` (and `≥ num_maskmem − 1`), not the literal 15.

*Scope:* measured at `image_size=640`, K=7, M=16, stride 2, `sam2.1-hiera-tiny`. The identity
boundary is arithmetic and so resolution-independent; the 8.1 MB/frame is not (it scales with S²).
Detail and the pre-registered prediction: `experiments/2026-07-26-carry-memory-horizon/README.md`.

### K=7 and M=16 stay stock: a fired gate is rejected on the record, not retuned (EXP-8 Stage 1, 2026-07-26T22:20Z)

*Decision:* keep SAM2's `num_maskmem=7` and `max_obj_ptrs_in_encoder=16` at their stock values.
Neither memory-horizon lever is adopted. Separately and explicitly: **G2 as pre-registered fires for
K=1, and K=1 is rejected anyway** — the gate is recorded as mis-specified rather than rewritten to
match the outcome.

*Why (M):* it is inert. Across M=2..32 every arm is null on per-clip median IoU (p >= 0.259) with
**zero discordant pairs** — no clip anywhere in that range changes PASS status, so McNemar is
undefined rather than non-significant. There is nothing to adopt in either direction.

*Why (K):* the exchange rate. K is a genuine monotone effect (K2 and K1 survive Holm over the
9-comparison family), but `b=0` in all five arms — a shortened memory never once wins a clip — and
the aggressive end is a cliff: K=1 buys 11.2% of the step for -7.3% median-of-median IoU and **four
PASS clips**, three of them going to exactly 0.000. The comparison that settles it is EXP-1's
resolution lever: **2.46x the rate for -0.6% IoU** (1024 to 640) against K7-to-K1's **1.13x for
-7.3% plus four clips**. If the deployment needs latency, the knob to turn is resolution, and it has
already been turned.

*Why the gate is reported as fired-and-rejected:* G2 required the IoU delta CI to exclude -0.05,
re-find to be non-inferior, and a >=5% saving in ms or MB. K=1 satisfies all three
(CI [-0.0321, -0.0049]; re-find 10.9% vs base 2.3%; 11.2% of the step). The flaw is that the -0.05
margin was written against *median-of-median IoU*, which is by construction insensitive to a
minority of clips collapsing — the median clip barely moves while the tail dies — and PASS, the
metric the deployment actually cares about, was never in the gate. The alternative was to quietly
restate the threshold after seeing the data, which would have made the pre-registration decorative.
The lesson generalises: **a gate on a central-tendency statistic needs a tail condition beside it.**

*What was given up:* a real 11.2% of on-device step time that is genuinely available. Also the
Stage 2 interaction cell — pre-registration gates Stage 2 on "G2 or G3 fires", and with nothing
adopted its best-K x best-M cell *is* `base`, so it was not run (vacuous, and stated as a deviation
rather than skipped). That leaves the K/resolution interaction unmeasured: K was swept only at
`image_size=640`, so whether a shorter memory is cheaper or more forgiving at 1024 is open.

*Third mechanism note, because it changes how the failure should be described:* the pre-registration
expected a horizon lever to "fail by drifting". Verified on the overlays, it does not. It fails by
**mask leak onto a neighbour** (`building3` @ K5), **identity swap onto a same-class distractor**
(`car7` @ K1 — the box jumps to a different silver car, disjoint from GT, hence exactly 0.000), and
**mask collapse to empty** (`car13`, `truck3` @ K1). Dense recent memory is buying object *identity*,
not positional smoothness. Detail:
`experiments/2026-07-26-carry-memory-horizon/README.md`.

### The TensorRT fp16 encoder is adopted at 640; `hiera-small` and `base_plus` are not (EXP-9, 2026-07-26T22:30Z)

*What:* the deployed carry moves to the **TensorRT fp16 image encoder** at `image_size=640`
(`enc640.plan`, passed as `--trt-encoder`). The model stays **`sam2.1-hiera-tiny`**. `hiera-small`
and `hiera-base-plus` are measured and rejected. Stage 2 (INT8) is not run.

*Why TRT is in:* +19.5 % rate (173.7 -> 145.4 ms, 5.757 -> 6.879 Hz) for a paired median IoU delta of
**exactly 0.0000** [CI95 0.0000, +0.0007], PASS unchanged 32/38, and a flat per-clip delta on all 38
clips. G2 was written to require >= 1.15x *and* non-inferiority *and* PASS not down more than one
clip — the tail condition EXP-8's mis-specified G2 lacked — and all three hold. This is the second
lever after EXP-1's resolution elbow to buy rate without paying accuracy.

*Why small is out:* G3 required all four of a Wilcoxon surviving Holm, `c > b` on McNemar, fitting
co-resident, and >= 5 Hz. It gets the last two (547 MB, 5.38 Hz) and neither of the first: delta
+0.0003 [-0.0046, +0.0036] p=0.987, b=2/c=0. A tie is a keep-tiny by the pre-registered rule.
Stated precisely, because the honest form matters for whether anyone revisits it: at n=38 a
significant McNemar needs **6** discordant pairs and small produced **2**, so this is
**underpowered by construction, not a demonstrated equivalence** (I4).

*Why base_plus is out, and why the reason is not the expected one:* it **loads** co-resident with the
VLM and leaves 1059 MB of board headroom. P5.20 wrote it off on memory without measuring it. The
disqualifier is **rate — 241.8 ms = 4.14 Hz, under E1's >= 5 Hz co-resident gate**. Recording this
because "it does not fit" was an inherited assumption and is now known to be false.

*What was given up:* small's re-find advantage, which is real and the largest behavioural difference
in the campaign — 16/110 recoveries vs tiny's 3/129, ~6x, CI95 non-overlapping. Both PASS flips
(`person21`, `uav3`) come from it, and both land in the pre-specified same-class-distractor stratum.
The gate is on steady-state accuracy, so a recovery-from-loss win does not pay for +12 ms/step. If
recovery ever becomes the metric — a longer carry, an occlusion-heavy bank — this is the first thing
to re-open, and it needs a bank sized for it, not a re-read of these 38 clips.

*Deployment consequence, so it is not discovered later:* the engine is **shape-baked at 640**. The
size-gated **1024 fallback EXP-1 kept for small/distant targets has no engine** and stays on the
eager path until one is built. Both paths are selectable per-invocation, so the fallback keeps
working unchanged; it just does not get the 1.195x.

### A gate that compares two recursive carries measures chaos, not fidelity (EXP-9 G1, 2026-07-26T22:30Z)

*What:* G1 — TRT-vs-eager end-to-end mask parity, mean IoU >= 0.99, blocking for both TRT arms —
**FAILED** as written (tiny 0.8427, small 0.9866) and the TRT arms were run anyway, under an explicit
`--g1-override` whose reason is stored in `runs/exp9/carry_override.json`.

*Why that is not gate-shopping:* the missing control was written and run **before** any verdict.
`diag_g1.py` adds eager-vs-eager on the same clips and reports step-1 IoU alongside the 24-step mean.
Result: **eager-vs-eager is exactly 1.0000** on both models — the carry is deterministic, so the
instrument is sound and every bit of divergence is attributable to the runtime swap, not noise — and
**eager-vs-TRT is 1.0000 (tiny) / 0.9949 (small) at step 1**, before any state exists. A carry is
recursive: step `t`'s mask conditions step `t+1`'s memory, so one differing pixel compounds. The
engines are faithful and the recursion amplifies. Per-clip, the entire tiny failure is **one clip**
(`bike3`), which bifurcates at step 1 and ends at 0.0 — and *which runtime is right there* is a
ground-truth question G1 never asks, since it only asks whether two runs agree.

*What was explicitly not done:* **G2 was not relaxed.** Adoption still had to clear non-inferiority
against ground truth (CI95 lower bound > -0.05, PASS not down more than one clip) plus the >= 15 %
rate win. If fp16 genuinely degraded the carry, G2 is where it would show, measured against GT
instead of against another approximation — and `trt`'s per-clip delta is flat on all 38.

*The lesson, for any future runtime-swap experiment:* the blocking fidelity gate must be
**state-free** — step-1 mask parity — with recursive-trajectory agreement reported as a descriptive
diagnostic beside it. EXP-8's lesson was that a central-tendency gate needs a tail condition; this is
its sibling: **a gate on a recursive system needs a state-free reference.**

*Second mis-aimed gate in the same campaign, recorded for the same reason:* G3 demanded a Wilcoxon
**IoU** win from `hiera-small`, whose actual signal turned out to be **PASS and re-find**. It fails on
either reading at n=38 (b=2 against the 6 discordant pairs needed), so nothing changes — but the
gate was pointed at the wrong statistic and saying so is cheaper than a later reader inferring the
arm secretly won.

### The encoder is no longer where the carry's time is (EXP-9 H1, 2026-07-26T22:30Z)

*What:* Stage 2 / INT8 is a **planned skip** — G4 gates it on a capacity arm winning G3, which none
did — and it is now additionally skipped on **value**, with a measured ceiling rather than a guess.

*Why:* H1 pre-registered +52 % from a 2.31x fp16 encoder holding 60 % of the step (extrapolated from
E1's 768 measurements by pixel count). Measured: **+19.5 %**, which fires the pre-registered
"under +25 % -> the encoder-share model is wrong" branch. Back-solving the same arithmetic, a 2.31x
encoder saving 28.3 ms means the encoder is `28.3 / (1 - 1/2.31) = 49.9 ms`, i.e. **28.7 % of the 640
step**. Encoder cost does not scale with pixel count the way the estimate assumed; at 640 the step is
overhead-bound — memory attention, decoder, JPEG decode, protocol.

*What that buys without running anything:* a **free** encoder would cap the step at 123.8 ms
(+18 % over the adopted `trt` arm), and INT8 over fp16 — optimistically another 1.5x on an already
21.6 ms TRT encoder — buys 7.2 ms, **+5 % over `trt`**. A pre-registered arithmetic miss priced the
next lever for the cost of reading a number.

*What was given up:* the possibility that INT8 is worth more than this bound suggests, e.g. if it
changed memory pressure rather than compute. Nothing here measures that. Anything wanting a
materially faster carry at 640 has to attack memory attention or per-step overhead, and EXP-8 already
priced the memory ring at ~19.5 ms and rejected the trade. Detail:
`experiments/2026-07-26-encoder-runtime-capacity/README.md`.
