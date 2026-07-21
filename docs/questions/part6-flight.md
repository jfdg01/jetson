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
0 track losses, 0.25% of ticks under 15 Hz) · G4 module self-tests green. Both fixes were found
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
fraction 0.005–0.026, frames viewed) · G3 pose slaving (0 → 84.4 m north under live GUIDED control
at a held 60.0 m, nadir sign confirmed against a viewed frame) · G4 traffic (40/40 autonomous
vehicles) · G5 rate (48.1 Hz mean, 2.4x the P6.0 control rate). SITL remains the physics, the
renderer remains pose-slaved, `run_phase_c.py` / `bytetrack.py` / the PID are untouched.

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
(`P5.2a-warm-generalization`, p=3.052e-5) is among the survivors.
