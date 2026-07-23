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

**Verdict:** **6 of 65 survive Holm-Bonferroni**; 33 came from designs that could never have reached
alpha=0.05 at their n, 26 produced 0 discordant pairs (no test, not equality), 3 have no raw data.
Three recorded conclusions are corrected: Swin2SR's rejection is latency-bound not accuracy-bound;
the Part I fidelity catastrophe is the export not the quantisation (F16 vs Q8_0 p=0.2478); carry at
768 *does* lose accuracy vs 1024 (p=0.013). The thesis's central contribution
(`P5.2a-warm-generalization`, p=6.10e-05 deflated to 23 clips — the citable figure per HANDOFF I2;
3.052e-5 undeflated) is among the survivors.

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
