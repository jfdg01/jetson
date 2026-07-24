# QUESTIONS — Part VI (v6 Closed-loop flight)

> Every Part V number was measured on replayed video the system could not influence. Does the
> warm-start select survive when the pixels are a consequence of the system's own control output —
> self-induced ego-motion, real wall-clock latency, and a controller actually consuming the box?
> Index: [`../../QUESTIONS.md`](../../QUESTIONS.md).
> Companion docs: `RESULTS.md` (numbers) · `DECISIONS.md` (choices) · `SOURCES.md` (citations).
> RQ ids preserved from each experiment's pre-registration; `Q-*` ids formulated here for runs with no explicit RQ.

---

<!-- append one RQ + one-line verdict per campaign below -->

### P6.0 — flight-rig capability gate (2026-07-20)

**Not a research question — a capability gate.** No RQ verdict; the gate result is in
`../results/part6-flight.md`. Recorded here because it retracts a Part I answer.

**Q-P6.0 (gate):** does the Phase B/C rig still fly, render, and close the perception→control loop
at rate, so Part VI can be built on it?

**Verdict: PASS, after two fixes.** G1 autopilot leg (connect → GUIDED → arm → 10 m takeoff →
20 Hz loop → LAND → disarm, unattended) · G2 camera renders a real scene (mid-run frame dominant
colour 0.751, frame viewed) · G3 loop holds the target (19.93 Hz mean, 100% track coverage,
0.25% of ticks under 15 Hz; the "0 track losses" that also appeared here is withdrawn as
evidence — R-10 found it only detects a >1.5 s detection drought, which this run never had) · G4 module self-tests green. Both fixes were found
*by the gate*, not before it: the camera pointed at the sky, and ByteTrack never re-found a lost
track. Post-fix mean pixel error 36.0 px vs 64.7 px pre-fix, same flight, same control rate.

**→ RQ-S1.4 (Part I) is RETRACTED to UNANSWERED.** "Replacing oracle with best zero-shot VLM: how
much does tracking degrade?" was answered by Phase C Branch-2, which ran with the camera aimed at
the sky — SmolVLM-500M was grounding an NL expression in a flat gray image (100.0% one colour).
The recorded degradation is a measurement of a broken render, not of the model. Not re-run
(SmolVLM-500M was eliminated in the Part IV bake-off), so the question stays open. Detail:
`../../experiments/2026-06-14-stage1-baseline/phase-c-vlm.md` (caveat block) and
`part1-exploratory.md`.

**Methodological note worth keeping.** The defect survived a month because no frame from that run
was ever saved or viewed, *and* the degraded metrics matched the pre-registered **expected**
outcome. A broken render was indistinguishable from a confirmed hypothesis. Pre-registered
negative expectations are the most dangerous place for a silent failure to hide — the "Look at it"
rule (`03d37bb`) was added a month after this run and would have caught it on day one.

### P6.1 — CARLA renderer swap (2026-07-20)

**Not a research question — a capability gate.** No RQ verdict; the gate result is in
`../results/part6-flight.md`.

**Q-P6.1 (gate):** can the renderer be swapped from Gazebo to CARLA without touching the physics
or the control stack, giving Part VI a world that actually contains targets?

**Verdict: YES.** G1 server (0.9.16 both ends, `Town10HD_Opt`) · G2 render (dominant-colour
fraction 0.007–0.026, frames viewed) · G3 pose slaving (0 → 84.4 m north under live GUIDED control
at a held 60.0 m, nadir sign confirmed against a viewed frame) · G4 traffic (40/40 autonomous
vehicles) · G5 rate (48.1 Hz mean render-loop throughput with no perception in the window; the "2.4x the
P6.0 control rate" reading is withdrawn by R-10 as an artefact of the sync-mode clock skew). SITL remains the physics, the
renderer remains position-slaved (yaw was never slaved — R-10), `run_phase_c.py` / `bytetrack.py` / the PID are untouched.

**G6 stays open.** "Does the deployed Qwen2-VL-2B ground CARLA frames worse than the 56/56 it
managed on Gazebo but better than on UAV123?" was pre-registered as a non-gating observation and is
**NOT RUN**. The prediction stands untested and is carried into its own n>=25 arm.

**Correction 2026-07-20T20:10Z:** the reason first recorded for G6 being unrunnable was wrong. The
deployed model was on the Jetson all along as `phase3-terse100eos-1024-q8_0.gguf` + `mmproj`, at
exactly the paths `grounding/deploy/video.py:48-52` points at, and **P5.17 grounded through those
same files** via `JetsonBackend` (`select_p517.py:397-403`). The error was searching for
`.safetensors` — the deployed artifact is a `.gguf`, so a negative search result read as "the model
is gone" when the search term itself encoded a stale assumption about format. Only the merged
HF/safetensors *training* directory is genuinely lost. **P6.2 is not blocked.**

**Why this gate existed at all.** P5.17 closed sim-select discrimination at n=56 with RG's VLM
grounding **56/56 clean Gazebo renders** — the recorded reading was that the sim is too *easy*.
The flight world was worse than easy: `iris_runway.sdf` has four entities and no targets of any
kind, confirmed live by flying to `XYZ [141.237 216.871 100.192]` and getting nothing but sky at
every commanded gimbal pitch (frames viewed, `proof/gaz-empty-world-*.png`). The cause was not the
camera — at Y=216 m the copter was 167 m past the edge of the only surface in the world.

## Q-STATS.1 — Cross-cutting (2026-07-21T13:30Z)

**RQ:** Of the 65 gated claims this repo defends across Parts I-VI, how many survive an exact test
with a multiplicity correction, and which recorded conclusions does the re-analysis overturn?

**Verdict** (as run; superseded counts below): **6 of 65 survive Holm-Bonferroni**; 33 came from designs that could never have reached
alpha=0.05 at their n, 26 produced 0 discordant pairs (no test, not equality), 3 have no raw data.
Three recorded conclusions are corrected: Swin2SR's rejection is latency-bound not accuracy-bound;
the Part I fidelity catastrophe is the export not the quantisation (F16 vs Q8_0 p=0.2478); carry at
768 *does* lose accuracy vs 1024 (p=0.013). The thesis's central contribution
(`P5.2a-warm-generalization`, p=6.10e-05 deflated to 23 clips — the citable figure per HANDOFF I2;
3.052e-5 undeflated) is among the survivors.

**Update 2026-07-24:** the registry has since grown to 75 claims (R-13, R-14, R-34, P6.2-DELIVERY,
P6.2-COUPLING, R-36, P5.21), the
Holm family was fixed at the Part (R-30) and the clustering deflation was calibrated
against a measured ICC (R-29). Current counts: **12 survive per-Part Holm, 10 global**
(P6.2-COUPLING is a bounded null — a real two-sided Wilcoxon that did not reject, not a survivor);
38 designs unreachable. `P5.2a-warm-generalization` is still among the survivors and
the three corrected conclusions still stand. R-34 added the Part IV survivor
`E18-...-n25` (the cold-acquire staleness effect, ORACLE 23/25 vs COLD 3/25 at n=25,
p=4.0e-05), promoting the number that launched Part V from p=0.0625 at n=6. Live
figures: `thesis/stats-report.md`.

## Q-MACH.1 — Cross-cutting (2026-07-21T18:05Z)

**RQ:** Across the 76 experiment campaigns in this repo, which machine produced each number, does
the campaign's own record say so, and does any published result need re-measuring on the Jetson?

**Verdict:** **61 of 76 campaigns state their host, 9 leave it inferable-only, 6 leave it
unstated.** Claim A («the deployed system runs on-device») is **confirmed** — E1 measured the VLM
and the SAM2 carry co-resident on the Orin at 6.15 FPS, mask parity 1.000. Claim B («every
experiment ran on-device») is **false and need not be true**: 29 campaigns had no VLM on the Jetson
and most of those correctly had no VLM at all. The defect is disclosure, not location — except for
one new substantive finding (M1): the 6.15 Hz rate cap that every Part IV/V campaign uses to
emulate the device budget was measured at image_size **768**, while those campaigns run the carry
at **1024**, a size E1 explicitly never speed-gated. The emulated stride is therefore optimistic by
a factor E1's own arithmetic puts near 1.9×, which biases every carry-dependent PASS in the
favourable direction; folded into R-16 as a required measurement axis. Record: `experiments/2026-07-21-machine-disclosure/README.md`.
## CARLA GT capture bank (unnumbered infrastructure, 2026-07-21)

This campaign asks no research question and claims no number. It builds the artifact P6.2 needs
and answers three build gates plus four API questions. **Gate verdicts are not results.**

**Q-BANK-1 — Is `EnvironmentObject.bounding_box` world-space or object-local?** **WORLD.**
`get_world_vertices()` takes `carla.Transform()` (the identity); passing the object's own transform
doubles every coordinate. An *Actor*'s box is the opposite — local, and does take
`get_transform()`. The two buckets need different calls, and the wrong guess is silent: all 29
parked-car boxes land somewhere plausible. Settled live, `runners/carla_probe_gt.py`, committed
`2d0917a`.

**Q-BANK-2 — In synchronous mode, does the image delivered for a tick carry that tick's frame id?**
**Yes, delta 0 on 40/40**, and now asserted every frame in `grab()` rather than trusted. An
off-by-one would make every GT box one frame stale — the exact defect P5.13 was charged with, and
invisible in any log.

**Q-BANK-3 — Does 0.9.16 offer any occlusion or depth test?** **Yes, `world.cast_ray` exists** and
returns labelled hits, so slate hazard 2.3c is buildable rather than merely deferrable. Not used
tonight: the cheaper stand-in is a semantic-segmentation camera at the same pose, whose per-row
`veh_fill` column says what fraction of each GT box is actually vehicle pixels.

**G-A — does the projected GT land on the target?** **PASS, by looking.** Overlays at 25/40/60/85/
120 m were opened with the Read tool; the reference box sits on the car at every altitude, all 8
vertices project, and the measured pixel area matches the analytic nadir prediction to within
1.02-1.11x while decreasing monotonically. The gate was deliberately strengthened past the slate's
own rule first — see DECISIONS, monotonic shrink alone passes a misplaced box.

**G-B — do static parked meshes exist outside `get_actors()`?** **Yes, 29 of them, CLOSED before
the run.** `world.get_environment_objects(carla.CityObjectLabel.Car)` returns 29 `Car` meshes that
`get_actors().filter('vehicle.*')` never sees, so a mask drifting onto a parked car is a *loss*,
not a *swap*, and the taxonomy needs the fourth bucket. The bank writes both buckets into every
`gt.jsonl` row with a `kind` field, so the distinction is available to any consumer rather than
being re-derived.

**G-C — does pairing survive an environment-object toggle?** **PASS, and the more useful answer is
that CARLA's traffic *is* reproducible.** Toggle-restore frame difference 0.084 against a
same-config repeat baseline of 0.142, both ~60x under the 8.0 floor, and all 40 Traffic Manager
vehicle positions identical across `load_world` at a fixed seed. Byte-identical was deliberately
*not* the bar — TAA, motion blur and auto-exposure carry state, so it fails for reasons unrelated
to layers and then gets softened until it stops gating.

The gate first reported **FAIL against its own same-config repeat**, which determinism cannot
explain and which was therefore a bug in the gate: it keyed each vehicle on `v.id`, and
server-assigned actor ids do not restart at a fixed value across `load_world`. Re-keyed on spawn
index, it passes. Recorded as run, this campaign would have answered "no, CARLA traffic is not
reproducible" on the strength of a broken dictionary key — see RESULTS.

**What the night actually taught, which no gate asked.** The first bank was **well-formed and
empty**: 25 clips' worth of correct actor counts, passing blank-render and dead-feed asserts, and
77-80% of frames with no on-screen target at all. G-A could not catch it, because G-A aims the
camera at a known reference car and is therefore blind to whether the *sampling policy* finds cars.
The fix (anchor each clip on a vehicle) matters less than the guard: **target coverage is now a
measured, asserted per-clip field**. The general form is this repo's standing rule — a check that
only verifies the pixels are *valid* will not notice that they are *uninteresting*.

### P6.2-DELIVERY — closed-loop delivery-timing (2026-07-24)

**RQ-P6.2-DELIVERY:** on a copter that flies its own control output, does warm-start
maintain-and-deliver land a usable, followable lock on a moving target where a cold blocking acquire
lands stale or off-frame?

**Verdict: YES [oracle-designation scope, control-coupling only].** WARM 23/25 vs COLD 2/25, exact
McNemar b=21 c=0, **p=9.5e-07** (reachable, survives Holm); WARM Wilson95 [0.750, 0.978]. The
~4.85 s cold lock-in latency, now paid in real wall-clock while both copter and target move, leaves
cold hovering blind through the lag then delivering a stale box off-target (`cold_target_exits_frame=0`
— staleness, not exit). Self-induced ego-motion does not rescue cold; the closed loop **amplifies**
the E18-n25 delivery-lag finding rather than narrowing it. Grounding was held constant via oracle
target designation (the deployed q8_0 is non-discriminative at 45 m nadir, G6), so the verdict is a
control-coupling claim conditional on correct designation — it does **not** license a
grounding+delivery claim. Two WARM residuals are carry-drift / non-lock (seeds 8, 13), not delivery.

### P6.2-COUPLING — does closing the loop degrade the maintained track? (2026-07-24)

**RQ-P6.2-COUPLING (C1):** does letting the warm-maintained track *drive* the copter — so the pixels
become a consequence of its own control output — degrade the maintained track, versus feeding the
same warm perception while an oracle drives?

**Verdict: BOUNDED NULL (frozen gate ii) — "warm carry survives self-induced ego-motion."** Wilcoxon
two-sided **p=0.596 (n.s.)**, median paired diff **−0.42 px**, bootstrap 95% CI **[−4.56, +4.08] px**
lying within the warm-arm schedule-noise band (±6.70 px). Closing the control loop does **not**
systematically degrade the track vs oracle-driven; any coupling penalty is below the noise floor.
This is a bounded null, **not** proven equivalence (two-sided by design). The coupled/decoupled *mean*
gap (26.8 vs 63.2 px) is stochastic SAM2 carry drift firing on different seeds per run — it appears
in the arm with no feedback loop, so it is run-specific carry variance, not a coupling penalty; the
outlier-robust signed-rank sees no difference. Scope: control-coupling on this rig's ego-motion (S5),
does not transfer to real-imagery perception.

### P6.2-SHOWCASE — can the maintained track drive a closed-loop flight with carry ON the Jetson? (2026-07-24)

**RQ-P6.2-SHOWCASE (qualitative, NOT in the Holm family):** run one on-Jetson end-to-end closed-loop
flight — SAM2 carry routed *literally* to the Orin — and does the loop hold a lock on the moving
target, with the on-device carry reproducing the parity-checked 3090 carry in-rig?

**Verdict: PASS (qualitative demonstration).** One WARM flight, carry stepped ON the Orin over
ssh-stdio, a 3090 twin scored in lockstep. The copter (flying its own PID output) held a police
charger through a 28 s flight incl. a road curve: **post-prompt coverage 0.495 (202/560 lock frames)**.
The **in-rig parity gate PASSES — Jetson-carried vs 3090-twin median IoU 0.960** (min 0.805, 90% of 52
in-loop steps ≥ 0.9), transport ~2 ms on ~422 ms carry compute — so E1's mask parity 1.000 holds live
in the loop. The follow is honest not perfect: the 2.69 Hz carry against a 20 Hz GT sawtooths the
delivered IoU (peaks ~0.5–0.6). Demonstrates on-device capability; not an inferential claim. Harness:
`run_p62_matrix.py --showcase`. Detail: `experiments/2026-07-24-p62-showcase/README.md`.
