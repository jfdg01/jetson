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
