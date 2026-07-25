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
