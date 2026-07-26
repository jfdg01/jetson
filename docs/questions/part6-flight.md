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

### EXP-1 — where is the SAM2 carry-resolution elbow on the Orin? (2026-07-24)

**RQ-EXP1 (elbow):** sweep SAM2 track `image_size` 256→1024 — where does carry IoU stop paying for
the throughput it costs? **Verdict: the elbow is 512–640.** IoU plateaus above 512 (0.675→0.780 over
256→512, then only +0.036 to 1024); on-device Hz is flat-high (~9–10 Hz, overhead-bound) below 640
then halves per step. **640 delivers 99.4% of 1024's IoU (0.811 vs 0.816) at 2.5× throughput (5.76 vs
2.34 Hz)**; 512 = 96% at 3.7×; below 512 speed saturates so it is pure IoU loss. Paired 768-vs-1024
holds (delta −0.0086, CI95 [−0.0135,−0.0017]; 3 of 38 clips lose PASS at 768, none gain).
**Engineering measurement, not a registered claim (R-44)** — an operating-point choice, not in
`thesis/claims.json`, no Holm entry; the paired test is in the README, not here. **Tail caveat:** 9/38
small/distant clips collapse at low res and recover only by 896–1024, so `held_frac` keeps climbing
to 1024 even after median IoU plateaus. Deploy: 640 default, 1024 size-gated fallback for small
targets. The "ground high / track low" framing collapses on 720p UAV123 (VLM trained ≤1024, seed
res-independent inside SAM2) — this maps the track-res knob only. Machine `jetson`. Detail:
`experiments/2026-07-24-resolution-decoupled-carry/README.md`.

### EXP-2 — does an operator point-crop beat NL referring expression for select? (2026-07-24)

**RQ-EXP2a (delivered PASS):** on the 26 P5.18 cells (13 clips), does PT (operator point → crop
→ VLM grounds crop → SAM2 carry) deliver more PASSes than NL (whole-frame referring expression)?
**Verdict: MISS — not separable at n=26.** WSEL NL 22/26 vs PT 24/26 (b=1 c=3); SWAP NL 24/26 vs
PT 26/26 (b=0 c=2); both deflate to 13 clips, `min_discordant`=6 so b+c=4 and 2 are below the
reachable floor — the MISS is the design's, and no p-value is quoted because none could have been
informative (**engineering measurement, not a registered claim, R-44**). Every discordant leans PT (7 PT-only vs 1 NL-only) and
PT never loses a SWAP cell, but underpowered. This is the R-38 prediction: at the lenient 0.25-IoU
delivery threshold the SAM2 carry rescues NL's rougher boxes, so the pointer buys no extra PASS.
**RQ-EXP2b (grounding elbow):** sweeping the VLM feed resolution under a strict IoU≥0.5 grounding
criterion, **PT@256px (hit 0.769) out-grounds NL@1024px (hit 0.654)** — the point-crop concentrates
the VLM's effective resolution onto the target, hitting its ceiling at a 256px crop while NL climbs
to a lower plateau at 896–1024. **The point-crop's win is grounding efficiency + localization
precision (same/better accuracy at 4× lower feed res), not delivered PASS at the deployed
threshold.** Supports maintain-and-deliver: NL grounding is not the select bottleneck; the pointer
is an ergonomics/compute lever, not an accuracy fix. Visual audit: 8/8 pass cells confirmed
genuine, 0 downgrades. Machine `jetson`. Detail:
`experiments/2026-07-24-point-crop-select/README.md`.

### P6.7 — what does it cost to go from "locked in" to a live track, and can it be cut? (2026-07-25)

**RQ-P6.7a (decomposition):** where do the ~6.5 s between designation and a live SAM2 track
actually go? **Verdict: 80% is process start-up, not catch-up.** COLD medians at lag 0:
`ssh_spawn` 0.301 s, `import` (torch + sam2) **2.846 s**, `weights` 1.800 s, `warmup_init`
0.670 s, `drain` 0.361 s, `t_handoff` **6.148 s**. `import torch` alone exceeds everything
else combined; only 0.36 s is the tracker catching up to the present. This retires the
panel's `catchup_s` as a name: it differs by 0.06 s between a 0-frame oracle click and a
~21-frame caption follow, so it was measuring cold start, not backlog. Substrate check: COLD
`steps_to_live=3` reproduces 11 of the panel's 13 live oracle traces and 6.148 s sits on the
live 64-trace p25 (live median 6.52 s).

**RQ-P6.7b (the lever, G1):** does a pre-warmed resident bridge cut median `t_handoff` below
1.0 s? **Verdict: YES, PASS at both lags.** 6.148 s -> **0.299 s** at lag 0 (20.6x) and
6.311 s -> **0.515 s** at the deployed 4.85 s grounding lag (12.3x); 25/25 pairs concordant
in both, Wilcoxon two-sided p=5.96e-08 at lag 0 (= 2/2^25, the exact floor at n=25) and
p=1.228e-05 at lag 4.85, where two clips share an identical paired difference and the tie in
`|d|` sends scipy's default method to the normal approximation (`method="exact"` on the same
numbers returns the same 5.96e-08 floor). Registered as
`P6.7-HANDOFF-warm-vs-cold-bridge` on the lag-4.85 arm (deployed path, conservative median).

**RQ-P6.7c (quality, G2):** does the fast path deliver a worse track? **Verdict: NO — PASS,
and at lag 0 WARM is strictly better.** Median IoU 0.000 -> 0.674 (paired delta +0.049,
CI95 [+0.006, +0.502], p=0.00021), box-present fraction delta 0.000 [0.000, +0.010], identity
swaps 79 vs 68 (delta 0 [−1, 0], no increase). At lag 4.85 all three deltas are 0.000 with
medians of 0.000 in **both** arms — that row passes over a floor and is uninformative, not
reassuring. **Not pre-registered, and the sharper finding:** COLD does not merely delay the
track, it **loses** it — on-target clips 11/24 vs 20/25 at lag 0, exact McNemar b=8 c=0,
**p=0.0078**, altitude-gated (4/5 at 40 m down to 1/5 at 100 m). Mechanism: `CATCHUP_JUMP=12`
at `CAM_HZ=5` makes one SAM2 step cross 2.4 s of world, so a 6.15 s boot hands the tracker a
~31-frame backlog whose first hop is that 2.4 s.

**RQ-P6.7d (residency, G3, the kill condition):** does keeping SAM2 resident starve the VLM
on an 8 GB board? **Verdict: NO — PASS, and not narrowly.** `ground_ms` median 3791.1 ->
3791.2 ms over 25 paired requests (**x1.000**, limit +15%), 0/50 `rc=-9` over consecutive
designations on one bridge, `MemAvailable` floor 1315 MB. The pre-registered fallback arm
`PIPELINE` was not run. This was called the honest risk up front and it was wrong in the
direction that makes the lever deployable.

**RQ-P6.7e (catch-up policy, no gate):** can `CATCHUP_JUMP` be tuned to get both the latency
and the track? **Verdict: NO — the two axes trade monotonically and 12 is already past the
cliff.** 25 clips x {1, 12, 999} at lag 4.85 s: replay-every-frame 5.312 s / IoU 0.596 /
17-of-25 on target, deployed 12 at 0.517 s / 0.000 / 10-of-25, jump-to-live 0.314 s / 0.000 /
8-of-25. Paired exact McNemar `j1` vs `j999` b=11, c=2, p=0.0225; `j12` vs `j999` b=4, c=2,
p=0.6875 — descriptive, unregistered, not Holm-corrected. The deployed 12 is indistinguishable
from skipping the backlog entirely, so the identity is already gone by 12 frames, and the only
setting that keeps the track spends longer crossing the gap than the gap itself. Redirects the
residual upstream: the fix is to not have a 4.85 s stale seed, not a smarter way to cross one.

Machine `jetson-orin-nano-8gb` (SAM2 on the Orin, 15 W + `jetson_clocks`, `image_size=512`);
the 3090 was not used. Detail: `experiments/2026-07-25-handoff-latency/README.md`.

**RQ-EXP-4 (MODE 2 click-crop, lever a'):** at matched magnification, does a crop cut from the
native 1920 sensor frame ground better than the same-FOV crop cut from the 960 display
downscale — and how much of any crop gain is magnification alone? **Verdict: NO on native
source (lever a' retired) / YES on magnification.** 25 CARLA nadir targets, four arms all fed
at 512. Primary C (1920/512) vs D (960/256 upscaled): b=1, c=0 — b+c=1 against a pre-registered
6-pair floor, so the binary gate cannot fire and the native-1920 plumbing is dead. The
secondaries are where the effect lives: A vs D b=1, c=8, p=0.039 isolates zoom with no new
detail and it wins on its own; C vs A (MODE 2 against today's deployed crop) is b=8, c=0,
p=0.0078 with +0.3308 median IoU, and hit@0.5 goes 0.60 to 0.92. A vs B is the sanity null and
holds (b=4, c=2, p=0.6875) — the 1920-to-960 `INTER_AREA` chain is not lossy. MODE 2's premise
survives; its "cut from the native frame" sub-claim does not, so `on_image` is never touched
and the crop keeps coming off the 960 frame. C's remaining 8% is referring-expression
ambiguity, arm-invariant, and lands on the same downstream residual R-38 already located.

Machine: grounding on `jetson-orin-nano-8gb` (15 W + `jetson_clocks`, q8_0, feed 512), CARLA on
the 3090 at 200 W. Not registered in `thesis/claims.json`; the p-values above are not
Holm-corrected. Detail: `experiments/2026-07-26-crop-mode/README.md` §6.

---

### EXP-5 — is a native-resolution crop around the carried box a real carry lever, and does a degenerate-box guard make it safe? (2026-07-26)

**RQ-EXP-5:** on the resolution-gated clips where SAM2 carry fails at `image_size=640`, does
cropping a fixed native-resolution window around the current box recover them — and does the
proposal's degenerate-box guard (area ratio outside [0.4, 2.5], or centre travel beyond
`D_MAX` box-lengths) protect the crop from drift reinforcement?

**Verdict: NO as pre-registered (KILL) / the crop alone is YES, the guard is a measured
negative.** 12 UAV123 clips x 6 arms on the Orin, exploratory, no test. Kill gate 3 fires: the
pre-registered treatment A5 (crop + guard @640) recovers 5/8 tail clips while A2 — plain
carry at `image_size=1024`, a config flag already deployed as the size-gated fallback —
recovers 8/8. The proceed gate also fails, and was unreachable by construction (only 4 tail
clips could move, so it demanded 4/4; `uav3` moves for no crop arm).

The six arms separate the levers. **The crop works and is free** — A4 (fixed 512 window, no
guard) takes the tail from 4/8 to 7/8 and the tail median from 0.223 to 0.703 with no easy-clip
regression, at 6.30 Hz against A1's 5.75 and A2's 2.34. **The guard is harmful, structurally**
— "hold the previous box on veto" freezes the reference the next veto is measured against, so
the first veto latches all the rest: it turned `car13` (0.639 under A1) and `bike3` (0.92 under
A4) into 0.000, and cost A4 two tail clips while buying none. **FIXED beats SCALED** — a
box-scaled window re-enters the `roi.py:60-65` shrink spiral and killed an *easy* control
(`car18`, 0.921 -> 0.000). So the answer to the proposal's guard sub-question is no, and it is
no for a reason no threshold fixes.

Machine: SAM2 on `jetson-orin-nano-8gb` (15 W + `jetson_clocks`) via `carry_ssh_bridge.py`; no
CARLA, no 3090. Not in `thesis/claims.json`; exploratory, no p-values to correct. EXP-6 is
re-pre-registered around A4 as a declared post-hoc promotion. Detail:
`experiments/2026-07-26-crop-mode/README.md` §7.

### EXP-6 — at gate scale, does the carry crop beat plain carry@640, and does it reach plain@1024's accuracy at >= 2x the rate? (2026-07-26)

**RQ-EXP-6:** does a fixed native-resolution crop around the carried box beat plain carry at
`image_size=640` on per-clip median IoU, and does it match plain@1024 (the deployed size-gated
fallback) within 0.03 IoU and 1 PASS clip at >= 2x its on-device rate?

**Verdict: PARTIAL — NO on the accuracy half, YES on the throughput-matched parity half.**
38 UAV123 clips x 3 arms, SAM2 on the Orin, Wilcoxon on the held-out 26 with the 12 EXP-5
pilot clips excluded from the primary. Against plain@640 the crop is directionally right but
does not clear its gate: +0.0085 median difference, 16 wins / 7 losses / 3 ties, delivered-PASS
24/24 in both arms so there is not one discordant pair. That stratum is
at ceiling — both arms sit at ~0.83 — which is precisely what the pre-registration predicted
and why it warned the primary would likely come back a tie. Against plain@1024 the crop is
**indistinguishable on the pre-registered bounds** (d_IoU -0.002 against a 0.03 bound, d_PASS -1
clip against a 1-clip bound) at **2.7x** the rate (6.31 vs 2.34 Hz), so the parity gate passes on
all three. **Engineering measurement, not a registered claim (R-44)** — the signed-rank p-values
for both contrasts are in the campaign README, deliberately not in this ledger.

The crop's value is therefore real but *scoped*: it is a cheaper way to buy the 1024
fallback's accuracy, not a replacement for the default carry. Its whole effect lives in the
resolution-gated tail (median IoU 0.703 vs 0.223, PASS 7/4 of 8) — a descriptive n=8 cut, not
a claim. Two nulls were checked rather than assumed: the crop's higher lost-step count is
confined to the three clips that read 0.000 in every arm, and the 720x480 subgroup is
uninformative because at that frame size a 512 window is barely a crop.

Machine: SAM2 on `jetson-orin-nano-8gb` (15 W + `jetson_clocks`) via `carry_ssh_bridge.py`; no
CARLA, no 3090. Not in `thesis/claims.json` — a null primary plus an engineering parity gate,
so no Holm entry. Detail: `experiments/2026-07-26-crop-mode/README.md` §8.

### EXP-7 — does composed MODE 2 beat MODE 1 in closed loop? (NOT RUN, 2026-07-26)

**RQ-EXP-7:** does MODE 2 (crop-ground + crop-carry) beat MODE 1 on delivered-PASS with the
copter flying its own control output?

**Verdict: NOT RUN — unanswered by design, gate not met.** §9 pre-registered "runs only if
EXP-4 and EXP-6 both pass"; EXP-4 missed its primary and EXP-6 is partial. Beyond the letter
of the gate, the two upstream results emptied the contrast: EXP-4 retired the native-1920
source so the ground half of MODE 2 is the already-deployed `roi_reanchor`, and EXP-6 made the
carry half a bounded null except on the size-gated path. The experiment would have measured
the deployed system against itself. It is recorded as a pre-registered non-run rather than
dropped; reopening it requires re-pre-registration against a contrast that is not already
deployed. Detail: `experiments/2026-07-26-crop-mode/README.md` §9.
