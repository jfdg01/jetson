# QUESTIONS — Part V (v5 Anticipatory grounding / warm-start acquire)

> The operator's prompt arrives mid-flight, not at frame 0 — the pre-prompt stream is free
> compute. Can we keep salient objects tracked over the idle window and SELECT on command,
> approaching the E18 B-oracle ceiling (6/6) instead of the cold-acquire floor (E18-A 1/6)?
> Index: [`../../QUESTIONS.md`](../../QUESTIONS.md).
> Companion docs: `RESULTS.md` (numbers) · `DECISIONS.md` (choices) · `SOURCES.md` (citations).
> RQ ids preserved from each experiment's pre-registration; `Q-*` ids formulated here for runs with no explicit RQ.

---

<!-- append one RQ + one-line verdict per campaign below -->

### P5.1 — warm-start acquire (2026-07-04)

**RQ-P5.1:** does seeding the carry from a real VLM detection during the idle pre-prompt window
(WARM) and selecting on command at t_p=8 s beat the cold blocking acquire (COLD, E18-A shifted to
t_p), reaching the GT-seed ceiling (ORACLE)?

**Verdict: YES [carry-bound].** WARM 5/6 vs COLD 1/6, WARM's PASS set ⊇ COLD's (5/6 ≥ 4, 5 > 1,
superset holds). WARM matches the ORACLE ceiling exactly (5/6, identical PASS set) — the real
idle-window seed is as good as GT, zero detection headroom lost. The one shared failure (car7) is
an occlusion at the prompt frame (`gt[240]` absent), so it is carry/occlusion-bound, not a
detection miss — hence the `[carry-bound]` suffix. Warm-start removes the ~135-frame (~4.5 s)
COLD delivery staleness that killed 5/6 moving targets in Part IV. `[ready-only]` regime
(t_p > acquire); early-prompt fallback out of scope. Detail:
[`../../experiments/2026-07-04-warm-start-acquire/README.md`](../../experiments/2026-07-04-warm-start-acquire/README.md).

### P5.2 — warm-start generalization + on-screen-speed sweep (2026-07-04)

**RQ-P5.2a (generalization):** does the P5.1 warm-start win hold across object *categories*
(person, boat, wakeboard, bike — not just cars)?

**Verdict: YES.** WARM 21/25 vs COLD 5/25 (≥18, 21 > 5), passing in **all 5** categories
(car, person, boat, wakeboard, bike). The 6 P5.1 car anchors reproduce; 2 of the 4 WARM misses are
`[deliver-occluded]` structural fails (car7, person10 — GT absent at deliver frame, fail ORACLE
too), so 21/23 = 91% on the non-degenerate set. Unlike P5.1 (WARM==ORACLE), P5.2 opens a 2-clip
`[detection-bound]` headroom (person18, car17: ORACLE passes, the idle-window VLM seed misses) —
the seed is no longer free on every category, itself a finding for small/deformable targets.

**RQ-P5.2b (speed dependence):** does the WARM−COLD advantage grow with on-screen target speed
(the Part V staleness premise: a blocking acquire lands stale because the target moves during it)?

**Verdict: NO [flat-in-speed].** Spearman ρ(gap, speed) = **−0.06** (not > 0); per-bin mean
WARM−COLD gap slow **+0.42** / med **+0.76** / fast **+0.62** — large and positive in every bin,
not rising with speed. The staleness-grows-with-speed story is refuted: the payoff is a flat offset
because COLD's ~135-frame *delivery* lag sinks it broadly (5/25), and its survivors are
deliver-frame geometry accidents, not slow targets. Warm-start beats cold because cold's delivery
is stale full stop — not because faster targets move further during the acquire. Detail:
[`../../experiments/2026-07-04-warm-start-generalization/README.md`](../../experiments/2026-07-04-warm-start-generalization/README.md).

### P5.3 — multi-candidate select-on-command (2026-07-14)

**RQ-P5.3a (select works):** when two same-class candidates are warm-carried through the idle
window, does the operator's phrase, late-bound by IoU-matching the stale VLM box to the carried
boxes, deliver the *named* target's live track? (PASS = selection==target AND genuine_lock IoU≥0.25
at deliver AND coverage≥0.5; RQ PASS at ≥4/5 scenes.)

**Verdict: FAIL (WSEL 3/5).** car10:240, car9:300, car7:460 lock the target at deliver IoU
0.81-0.87 (cov 0.96-1.00) — the mechanism *works* when the VLM boxes a carried candidate. But
car10:615 NO_MATCH (VLM boxed neither carry) and car3:200 selected the white-car distractor for
"the red car" (tiny ~16×40 px target). 3/5 < 4/5.

**RQ-P5.3b (the phrase drives it):** swapping to the distractor phrase swaps the selection?
(PASS = selection==distractor AND delivered box off the target, IoU<0.25 vs target GT; ≥4/5.)

**Verdict: FAIL (SWAP 2/5).** car9:300 and car3:200 correctly flip to the distractor track; the
other 3 scenes NO_MATCH — the deployed VLM could not ground the distractor captions ("the black
car", "the white van") onto a carried candidate at the prompt frame. 2/5 < 4/5.

**Overall P5.3 = NO** (YES needs both). The failure is not the IoU-match rule or carry drift — it
is the deployed VLM's raw grounding accuracy at the single prompt frame: selection succeeds iff the
VLM boxes a carried candidate, and NO_MATCH (4 of 7 non-passes) fires when it does not. Late-binding
phrase-select is sound-but-not-robust on the deployed VLM; the next lever is crop-scoring over the
carried candidate crops (bypassing free-frame VLM grounding), pre-registered as a deep-research
target. Detail:
[`../../experiments/2026-07-14-multi-candidate-select/README.md`](../../experiments/2026-07-14-multi-candidate-select/README.md).

### P5.4 — ROI-constrained select-on-command (2026-07-14)

- **RQ-P5.4a (ROI select works):** with the VLM fired on the candidates-union ROI crop (union of
  the two carried boxes, margin 1.5, min_side 256, LANCZOS@512 — the deployed Part III lever),
  does the target phrase deliver the named target's live track? PASS iff VSEL >= 4/5. **Verdict:
  NO** (VSEL 3/5) — cell-for-cell identical to P5.3's full-frame WSEL 3/5. The ROI crop cut
  acquire latency ~2.3x (4.5-4.9s -> 2.08s median) but did NOT move the select verdict: car10:615
  still NO_MATCH (the VLM grounds an in-crop third object *between* the two carries — NO_MATCH is
  reduced 4->3, not eliminated by construction), and car3:200's ~16x40 px target still mis-grounds
  despite the 2-5x upscale (resolution ceiling).
- **RQ-P5.4b (the phrase drives it):** does the distractor phrase flip the selection? PASS iff VSWP
  >= 4/5. **Verdict: NO** (VSWP 3/5) — up from P5.3 SWAP 2/5 (car10:240 now grounds the distractor
  caption inside the crop). Remaining fails: car10:615 (same in-crop third object) and car7:460
  (pre-registered carry-drift cell, `carry_suspect=['distractor']` — carry maintenance, not select).
- **Overall P5.4 = NO [match-bound, resolution-bound].** The ROI lever is a real latency win
  (~2.08s, transfers from Part III as predicted) but the binding constraint stays the deployed VLM's
  grounding at the prompt: select succeeds iff the VLM boxes a carried candidate, and the ROI crop
  helps that only marginally (VSWP +1, VSEL +0). The in-crop-third-object and small-object failure
  modes are not addressed by cropping; CLIP crop-scoring (circlectx, non-gating 7/10) would not have
  rescued them either. Detail:
  [`../../experiments/2026-07-14-crop-select/README.md`](../../experiments/2026-07-14-crop-select/README.md).

### P5.5 — Maintained-candidate select-on-command (2026-07-14)

- **RQ-P5.5a (maintenance + unique captions lift WSEL to >= 4/5):** does per-candidate idle-window
  ROI re-anchor of the distractor carry plus referentially-unique captions raise warm select-on-command
  to >= 4/5 (P5.3 baseline 3/5)? PASS iff MC WSEL >= 4/5. **Verdict: YES** (4/5) — car10:240, car9:300,
  car7:460, car9:560 lock; only car10:615 fails NO_MATCH. But the win is **maintenance, not captions**:
  the M-arm (old captions) is cell-for-cell identical, so the unique-caption lever contributed nothing.
- **RQ-P5.5b (same treatment lifts SWAP to >= 4/5):** PASS iff MC SWAP >= 4/5 (P5.3 baseline 2/5).
  **Verdict: NO** (3/5) — maintenance flipped car10:615 SWAP but car10:240 and car7:460 still fail
  **carry-drift NO_MATCH** *after two accepted ROI re-anchors*: the re-anchor fires and is accepted, yet
  the carried distractor box and the select-time full-frame VLM box do not overlap (IoU 0.000).
- **Overall P5.5 = NO [match/carry-bound]** (YES iff both; SWAP 3/5). The caption lever is falsified as
  a select-fix (M == MC). This is the third consecutive select-on-command NO — the bottleneck is not
  captioning (P5.5), not ROI-crop-select (P5.4), not the late-binding IoU match itself (P5.3), but the
  agreement between the carried SAM2 box and the deployed full-frame VLM grounding at the prompt.
  Idle-window maintenance helps (SWAP 2/5 -> 3/5, WSEL 3/5 -> 4/5) but does not clear the bar. Detail:
  [`../../experiments/2026-07-14-select-generalization/README.md`](../../experiments/2026-07-14-select-generalization/README.md).

### P5.7 — Simulator scene-generator capability gate (select-arena v1) (2026-07-17)

- **RQ-P5.7 (can the Gazebo rig act as a deterministic on-demand scene generator?):** two same-class
  colour-distinct vehicles, UAV-style moving camera, per-frame GT boxes + stable track IDs, meeting
  G1 render-alive, G2 GT-on-vehicle, G3 co-visibility, G4a cross-session same-seed determinism,
  G4b seed diversity, G5 >= 0.5 fps, plus the mandatory visual gate V. **Verdict: NO [`infra` FAIL:
  gz-transport service flake]** — not a gate reading but the pre-registered abort rule: the rig cannot
  produce a 240-frame clip **at all**. `seed101_A` crashed mid-clip twice (127/240 and 108/240), each
  on a fresh server session, each on a `gz service` CLI call timing out while the **server stayed
  alive**; per the rule (INVALID -> re-run once -> fails again -> `infra` FAIL and stop), B/C/D never
  ran. `verdict_p57.py` prints INCOMPLETE (exit 2); every gate is unmeasured and **V is uncomputable**
  (overlays are finalize-time artifacts, so none of the 12 required PNGs exist — recorded INVALID, not
  a log-inferred pass). Cause: `scenegen.py` makes **2 `gz service` subprocess calls per frame**
  (~480/run) and the server intermittently cannot route a response back to those ephemeral transport
  nodes (`RecvSrvRequest() ... Host unreachable`); at ~0.42%/call (ESTIMATE, n=2) a 240-frame run has
  ~13% odds of completing and the 4-run matrix ~0.03% — unrunnable as designed, so re-running it
  unchanged is not worth the compute. The fix is a design change (persistent node / batched stepping /
  retry-on-timeout) and is deferred to Fable, not implemented here.
- **Not a verdict, but the answer to the pre-registered open risk:** G4a's frame half looks
  **excellent** — the two INVALID seed-101 attempts (fresh sessions) are **108/108 byte-identical,
  mean |diff| = 0.000000** against a 2.0 gate. GPU AA/shadow nondeterminism did not materialise; the
  `<sky>` removal + puppeteer-lockstep design appear to buy exact frame determinism. The scene itself
  renders correctly (two colour-distinct cars, correct UAV aim, no black frames, 1.48 fps = on
  estimate), so **the capability is blocked on transport plumbing, not on the scene design** — the
  premise that a sim can author colour-attributed same-class pairs with per-frame GT is undamaged and
  worth one more cycle. P5.6 (`experiment/direct-delivery-select`) stays PARKED as pre-registered.
  Detail:
  [`../../experiments/2026-07-17-sim-scenegen/README.md`](../../experiments/2026-07-17-sim-scenegen/README.md).

### P5.8 — Scene-generator transport fix (persistent requester) + capability gate re-run (2026-07-17)

- **RQ-P5.8 (does moving per-frame service calls from ephemeral `gz service` CLI subprocesses to one
  persistent gz-transport requester node — plus a reply-lost-aware retry layer — let the select-arena
  rig complete the 4-run matrix and pass the unchanged P5.7 capability gates?):** gates G0 completion
  (new), G1 render-alive, G2 GT-on-vehicle, G3 co-visibility, G4a cross-session same-seed determinism,
  G4b seed diversity, G5 >= 0.5 fps, plus the mandatory visual gate V. **Verdict: NO [G4b — seed
  diversity], but the transport question underneath it is YES.** The P5.7 blocker is gone: **G0 PASS
  4/4 at 240/240 frames with 0 retries / 0 lost replies / 0 proxy restarts** across 1920 gating
  service calls (P5.7: 0/2 runs finished, dying inside ~240 calls with the server alive), at **8.34 fps
  vs 1.48 (5.6x)**. G1/G2/G3/G5 PASS 4/4 and **V PASS 4/4** (12/12 overlays viewed: two colour-distinct
  cars, boxes tight on the vehicles, motion visible). **G4a — pre-registered as "the one genuinely open
  gate" — PASS and stronger than estimated:** GT byte-identical and frames `mean |diff| = 0.0`,
  `frac(|diff|>8) = 0.0` across **all 240** frames on fresh sessions, so the feared late-clip shadow/AA
  divergence does not exist; P5.7's 108/240 probe now extends to a full clip. The sole failure is
  **G4b: min pairwise target-f0 distance 0.216 m < 1.0 m** on the pre-registered triple {101, 202, 303}
  (all three pairs under gate). Diagnosed as **gate calibration, not a generator defect**: recorded GT
  reproduces `author_scenario()` exactly, target f0 spreads ~8 m x 7 m over 120 seeds, and **74.6% of
  2000 random 3-seed triples pass G4b** (median min-pairwise 1.52 m) — 3 seeds give 3 pairs, so
  near-collisions are a birthday effect and the gate has a ~25% false-failure rate on an arbitrary
  triple; {101, 202, 303} landed in that 25%. The seeds differ materially on every other axis
  (distractor f0 ~5 m apart, v_target 3.6-5.8 m/s, standoff 17.8-21.4 m, alt 16.3-21.6 m). Verdict
  applied literally per the pre-registered rule (`YES iff ... AND G4b`) — threshold, seeds and code
  untouched; **the next cycle rules on G4b's definition** (widen target spawn / pre-screen the triple /
  measure trajectory divergence instead of a single f0 point), not the executor.
- **Scene-quality defect found by the visual gate, not by any metric:** in seed 101 the blue
  distractor spawns near the median kerb (lat y = 0.596) and **clips into the kerb geometry** — by
  f0180 it renders as two disconnected blue blobs with the mid-body sunk below the kerb surface. The
  GT box still bounds the model and tracks the car (no float/lag), so it passed G2 (pur1 = 0.472 vs a
  0.30 gate) and is recorded as V PASS-with-caveat rather than a V FAIL — but **a half-sunk distractor
  is not a fair grounding target** and should be fixed before this generator feeds a select experiment.
  This is exactly the class of silent sim failure the mandatory-visual rule exists to catch.
- **P5.6 (`experiment/direct-delivery-select`) stays PARKED** as pre-registered — still the live select
  lever, still the n=5-starved test this generator exists to unblock. The generator is now one
  gate-definition fix away from being usable for it: transport, determinism, render health, GT
  fidelity and co-visibility are all demonstrated.
  Detail:
  [`../../experiments/2026-07-17-scenegen-transport/README.md`](../../experiments/2026-07-17-scenegen-transport/README.md).

### P5.9 — kerb-safe scene bank (2026-07-17)

**RQ-P5.9:** with spawn bands clamped to the calibrated kerb-safe corridor and G4b redefined to
whole-scenario divergence, does the generator pass the full capability gate (including the new
rendered-integrity gate G6) AND produce a 12-clip pre-registered scene bank with zero clipping —
the dataset the select arc needs?

**Verdict: YES.** Full capability gate 16/16 (G0,G1,G2,G3,G5,G6 all PASS), G4a byte-identical PASS,
G4b (redefined) PASS at 1.36 m ≥ 1.0, **12/12 bank cells clean**, **V PASS 16/16** on all 28 opened
overlays. Zero clipping: the P5.8 seed101 kerb-clip (blue distractor rendered as two disconnected
blobs at f0180) is fixed — same seed/frame now renders one connected body clear of the median. G6
has teeth and margin (min p10 0.9967 vs 0.95 gate; the P5.8 clip scored 0.666); notably the residual
sub-1.0 p10 is now the white *target* (self-occlusion), not the blue distractor, so the old defect
class is gone. **No V-vs-G6 disagreement** in either direction. First-attempt matrix: 0 INVALID / 0
INFRA / 0 retries in 1920 calls. **The 12-clip bank is usable as a select dataset** (per-object
white/blue phrases + GT, co-visible ≥ 80%, both cars intact). Independent corroboration of the G4b
redefinition: under the OLD statistic the bank scores 0.135 m (would have failed the retired 1.0 m
gate) while diverging 1.36 m scenario-wide — the exact single-frame-coincidence artefact the
redefinition targets. **P5.6 (`experiment/direct-delivery-select`) unblocks next cycle on this bank.**
Detail: [`../../experiments/2026-07-17-kerbsafe-scenebank/README.md`](../../experiments/2026-07-17-kerbsafe-scenebank/README.md).

### P5.10 — select on the scene bank: direct delivery vs prompt-time re-ground (2026-07-17)

**RQ-P5.10:** on the P5.9 12-clip sim bank (two colour-distinct cars, exact dual per-frame GT), with
both candidates carried from oracle f0 seeds under the two-candidate SAM2 budget, does the
**direct-delivery contract** (phrase→carried candidate by stored caption, deliver its carried box at
the prompt, no VLM, acquire 0 s) select correctly at n=12 (RQ-a: ≥ 10/12 each leg) **and beat the
P5.3 re-ground contract** (full-frame VLM at prompt + IoU-match + measured latency) by a
pre-registered margin (RQ-b: DD_total ≥ RG_total + 4), evaluated paired on identical carries?

**Verdict: RQ-P5.10a YES, RQ-P5.10b NO → OVERALL NO (interpretation branch 2).** DD 24/24 (white
12/12, blue 12/12) — clears RQ-a easily. But RG also hit ceiling: 24/24, `vlm_on = named` on all 24
cells, 0 NO_BOX / 0 NO_MATCH / 0 OVERRUN — so the margin is 0 (< 4) and RQ-b fails. **The
pre-registered sim-gap NO_BOX sweep did NOT happen**: the RefDrone-fine-tuned Qwen2-VL-2B grounded
every clean Gazebo render on the first call. Reading (branch 2): the P5.3/4/5 select NOs are
**scene-bound** (UAV123 same-class attribute murk + one hand-annotated distractor frame), *not*
contract-bound — on a clean two-attribute scene the old re-ground contract works fine, so DD's real
advantage over RG here is **latency only** (0 s vs mean 4.37 s acquire), not accuracy. **Visual gate
V PASS** (16/16 opened overlays show green on the named car; no contradiction). Honest-negative
caveat baked into the pre-reg: bank v1 is too easy to *separate* the contracts (2 colour-distinct
cars, no crossings, max GT-GT IoU 0.000, 3 s idle) — a YES was structurally guarded against and did
not materialise; this does not claim real-video select is solved. **Next levers (pre-registered):**
either unpark P5.6 (direct delivery on real UAV123, where RG is known to fail — the A/B that would
actually separate the contracts) or harden the bank to v2 (crossings/occlusion, longer idle) to
exercise the under-tested carry-drift / ID-switch failure modes. DD's 0-s delivery + carried-track
accuracy is validated on clean scenes at n=12; the contract *separation* claim is not.
Detail: [`../../experiments/2026-07-17-simbank-select/README.md`](../../experiments/2026-07-17-simbank-select/README.md).

**RQ-P5.11:** can the P5.9 scene generator author + record a **12-clip bank v2** where the two
candidates actually cross — sustained designed occlusion (white recorded ≥50% occluded for ≥25
frames, GT-GT IoU peak ≥0.20) inside a doubled idle window (prompt f150 = 6.0 s, clip 12.0 s) —
while every clip still passes render-integrity gates that mechanically separate a designed occlusion
from a render defect (occl-partitioned G2c/G6c on CLEAR frames + G8 occluder/z-order on OCCLUDED
frames + G9 crossing shape), on 4/4 gate runs (G0–G6c, G4a determinism, G4b seed diversity) and
≥11/12 bank cells?

**Verdict: NO** [G4b FAIL; bank 3/12 pass]. `verdict_p511.py`: 4/4 gate runs pass G0–G6c, G4a PASS
(byte-perfect determinism, mean\|diff\| 0.0), but **G4b FAIL** (min pairwise scenario divergence
0.77 m < 1.0 at seed pair 9,14) and only **3/12 bank cells** pass all gates (bank01/03/04). The
crossing itself renders correctly: G9 = 12/12 (peak IoU 0.22–0.35 pre-prompt, tail ≤0.15 post-prompt)
and **visual gate V PASS** — all 12 crossing-peak overlays + 3 post-prompt + 2 gate mid-run + the
montage were opened with the Read tool; every one is a genuine designed occlusion (blue occluder in
front of intact white target, overlapping GT boxes, on the start line), **zero render defects**, V
does not downgrade. The NO is **integrity-threshold-bound, not scene-render-bound**: G6c fails on 7
cells because the n_clear floor (60, from the single seed-1 probe's 80) is too tight for the seed
population (deep/long crossings leave <60 CLEAR frames on cells that visually render valid), G8b
fails on 3 shallow-occlusion seeds (white roof stays prominent — a real depth property), and the
offline crossing screen admitted near-duplicate seeds 9 & 14 for lack of a diversity constraint. All
three are NEW-pre-registration fixes (recalibrate n_clear to the population, add a seed-diversity
constraint, re-derive G8b for shallow seeds), not threshold nudges. The generator's crossing
*capability* is validated (12/12 crossings render + separate as designed); the bank *build gate*
fails its own calibration. Blocks the pre-registered **P5.12 v2-discrimination A/B** until a v2.1
bank passes. Detail: [`../../experiments/2026-07-17-bankv2-crossing/README.md`](../../experiments/2026-07-17-bankv2-crossing/README.md).

**RQ-P5.12:** was P5.11's `NO` **gate-calibration-bound rather than render-bound**? Re-run the
identical 16-run v2 record matrix over a **v2.1 seed bank** chosen by an offline screen that enforces
the two properties P5.11's gates measured after the fact (per-clip clear-frame supply, pairwise seed
diversity), against gates recalibrated **once, from the P5.11 recorded population** — and does that
bank now clear ≥11/12?

**Verdict: YES** [12/12 bank cells pass; V PASS]. `verdict_p512.py`: 4/4 gate runs pass G0–G6c, G4a
PASS (byte-exact determinism across fresh server sessions, mean\|diff\| 0.0), **G4b PASS** (min
pairwise scenario divergence 1.11 m ≥ 1.0 at pair 2,29 — the constraint that failed P5.11 at 0.77 m),
new **G7 PASS** (the screen re-run at verdict time reproduces the pinned bank byte-for-byte, so no
generator/screen drift between pre-registration and grading), and **12/12 bank cells** pass all gates
including G8/G9, with 0 INFRA and 0 present-but-failing cells — against P5.11's 3/12 on the *same
untouched generator*. **Visual gate V PASS**: all 12 crossing-peak overlays, all 12 post-prompt
overlays, 2 gate mid-run frames and the 3 proof figures were opened with the Read tool; every
crossing peak is a genuine designed occlusion (blue occluder drawn in front of an intact white
target, overlapping GT boxes, cars on the road surface), **zero render defects**, V does not
downgrade. The answer to the RQ is therefore **yes, calibration-bound**: nothing about the renders
changed, only which seeds were admitted and where two floors sat, and both floors are demonstrably
load-bearing rather than fitted — bank02 (n_clear 57) and bank05 (bdom 0.488) are visually flawless
clips that P5.11's floors rejected, and 0.488 is the exact value that failed P5.11's G8b. The
strongest single result is the **S6 transfer table: predicted vs recorded `n_clear` matches with
delta 0 on 12/12 cells**, including all six seeds (17, 28, 29, 33, 40, 56) never previously
rendered — a pure-projection statistic reproducing the recorded pool exactly, which is what
legitimises the screen as pre-selection rather than post-hoc filtering, and which answers the
pre-registered hypothesis under test (does the offline screen predict render integrity on unseen
seeds?) affirmatively. Honest caveat surfaced only by looking: bank05 (seed 6) and bank06 (seed 14)
are visibly shallower occlusions with fragmented occlusion windows — gate-passing but lower
occlusion stress than the bank average, and the first suspects if P5.13 fails to separate. Unblocks
the deferred **P5.13 v2-discrimination A/B** (P5.10's DD-vs-RG matrix on this bank at prompt frame
150), which consumes this bank unchanged.
Detail: [`../../experiments/2026-07-17-bankv21-recal/README.md`](../../experiments/2026-07-17-bankv21-recal/README.md).

### P5.13 — v2 discrimination A/B: DD vs RG on the bank v2.1 crossing bank (2026-07-19)

**RQ-P5.13a (primary, gating).** On a scene bank whose clips contain a *designed crossing/occlusion*
between the two candidate cars, do the two delivery contracts — DD (direct delivery of the carried
track, no VLM at prompt time) and RG (prompt-time re-grounding through the VLM plus IoU match) —
**separate**, i.e. is `|DD_total - RG_total| >= 4` of 24 cells?
**RQ-P5.13b (secondary, diagnostic, non-gating).** Is any separation driven by the designed
occlusion, i.e. is `blue_DD - white_DD >= 3` of 12? (White is the occluded target in 12/12 clips,
blue is never occluded, so the legs are an internal control.)

**Verdict: NO** [branch 3; no separation, both contracts >= 20/24]. **DD 24/24, RG 23/24, |diff| 1 <
4.** RQ-P5.13b also NO (12 - 12 = 0), which is uninformative here because DD ceilinged on both legs.
The pre-registered prediction ran the *other* way — RG > DD, on the theory that DD must carry
identity through the ~f81 crossing while RG sees a clean scene at the f150 prompt frame — and it was
**wrong**: SAM2's carry survived every designed crossing, 0/24 DD fails, no `CARRY_LOST`, no
`CARRY_SWITCH`, `ddIoU` in a tight 0.462-0.643 band. This is why the margin was pre-registered
symmetric (`|DD - RG| >= 4`) rather than P5.10's directional `DD >= RG + 4`: the threshold had to be
able to fire in the direction the experimenter did *not* expect, and in the event it fired in
neither. RG's single loss (`bank09_white`) is **not** a grounding loss — `vlm_on=named`,
`vlm_iou_named` 0.735, `match_ious` {track0 0.665, track1 0.0}, `selection` 0, all correct — the cell
fails `DELIVERY_DRIFT` because the delivered mask leaks from `[560,292,629,342]` to
`[560,292,1248,615]` over RG's 109-frame delivery lag, i.e. it is a *carry* failure inside the RG
leg, charged to RG only because RG delivers later. Corrected for that, both contracts are effectively
at ceiling and the honest reading is DD == RG for the second campaign running (P5.10: 24/24 vs 24/24
on bank v1). Per the frozen branch-3 caveat, the two pre-registered explanations in order: (i)
crossing-peak uniformity + constant z-order — white-box centre y std 6.1 px, and **white is the
nearer car in 0/300 frames in every clip**, so the bank never renders the target *in front* and every
"occlusion" is the target being occluded from a near-constant screen position; then (ii) bank05/bank06's
weaker occlusion stress (peak GT-GT IoU 0.217/0.251 vs 0.352 for bank07). The evidence does not
localise to (ii) — the two weakest-crossing clips passed exactly like the strongest, and DD had zero
fails bank-wide — so (i) is where it points, and (i) is the one property with no gate on it. No third
explanation is derived post-hoc, as pre-registered. **Visual gate V: PASS (non-operative, since V can
only downgrade a YES)** — 3 proof PNGs and 4 per-cell overlays opened with the Read tool; genuine
Gazebo renders, delivered/GT/VLM boxes on the cars not on empty road, no black or duplicate frames.
Operationally clean: 0 INFRA cells, 0 VLM reboots, 24/24 in one pass, ~3.4 min against a 6-12 min
estimate. Standing implication: **three banks in (v1, v2, v2.1) the contract question is still not
separable by scene data of this kind**; the next lever is a property of the scene the bank has never
varied (z-order / target-in-front) or a move off synthetic banks entirely, not another recalibration.
Detail: [`../../experiments/2026-07-19-v2disc-select/README.md`](../../experiments/2026-07-19-v2disc-select/README.md).

### RQ-P5.14a / RQ-P5.14b — does changing the *delivery contract* fix select-on-command on real video?

**Question.** Under the direct-delivery (DD) contract — the operator phrase binds to a warm-carried
candidate by its stored caption, and that candidate's carried box at the prompt frame is delivered
directly, with no prompt-time VLM call and no IoU match — does select-on-command pass on the same
real UAV123 scenes where three re-grounding (RG) campaigns failed? **RQ-P5.14a (WSEL, select the
target):** >= 4/5 gating scenes. **RQ-P5.14b (SWAP, select the distractor):** >= 4/5 under a
*strengthened* rule (delivered box IoU < 0.25 vs target GT **and** >= 0.25 vs the hand-annotated
distractor GT — junk cannot pass). YES iff both.

**Verdict: YES — WSEL 5/5, SWAP 4/5 (strengthened), visual gate V PASS, no downgrade.**

This is the **first select-on-command YES in Part V** after three straight NOs (P5.3 match-bound,
P5.4 match/resolution-bound, P5.5 match/carry-bound) and two synthetic-bank ties (P5.10, P5.13). The
lever is the contract, not the model, the prompt, or the scene: nothing about the VLM, the carry, or
the scenes changed from P5.5 — only *what gets delivered at the prompt*. The thresholds were frozen
2026-07-14, four campaigns before the sim results that motivated unparking this run, so the bar was
not moved to fit. The strengthened SWAP rule is strictly harder than the historical bar (P5.3 2/5,
P5.5 MC 3/5 under the weaker off-target-only rule), so the YES is not scoring drift: under the weak
rule DD scores 6/6, under the strong rule 5/6, and the flattered cell is exactly the one that fails.

**Where the win comes from, measured on the same frames.** The non-gating shadow re-ground ran
alongside DD on every cell and **disagreed on 4/12** — 3x NO_MATCH and 1x wrong-object selection —
on cells whose carried track was on the right object and whose DD cell passed. That is the P5.3/P5.5
failure mode reproduced live, next to a contract that does not have it. **Latency:** DD `acquire_s`
is 0.00 s by construction on all 12 cells against a 4.51 s mean full-frame re-ground. The
`car3:200` control that RG failed in three campaigns as "resolution-bound" flips to PASS under DD
(0.7256) — that fail family was a re-grounding artifact, not a carry limit, which retires a
standing explanation.

**What the NO cell means.** The one failure, `car7:460` SWAP, is `carry-off-object`: the carried
distractor box had drifted onto empty kerb before the prompt, so DD delivered junk. This was
predicted by name in the pre-registration and is the honest ceiling of the contract — **DD cannot
be better than its carry.** Where RG could hide a bad carry behind a NO_MATCH (and score a weak-rule
pass), DD fails it directly and visibly. The next binding constraint for this arc is therefore
**carry quality on real video**, not selection: the marginal `car9:560` cell (0.2843 against a 0.25
floor) says a small carry regression flips a second cell.

**Visual gate V: PASS.** All 24 `viz_early/viz_late` PNGs opened with the Read tool, plus 3
deliver-frame overlays extracted where the late frames were ambiguous. Every scored PASS is
corroborated on the pixels (box on the named vehicle, real aerial scenes, no black/duplicate
frames) and the one scored FAIL is visibly off-object. A wording gap was found and recorded rather
than resolved silently: `viz_late` is sampled 5–6 s *after* the deliver frame, by which time a
correctly-delivered distractor may have driven to the frame edge — a future pre-registration should
gate on the deliver frame itself.
Detail: [`../../experiments/2026-07-19-realvid-dd-select/README.md`](../../experiments/2026-07-19-realvid-dd-select/README.md).

### RQ-P5.15a / RQ-P5.15b — does a warm carry survive a long idle window, and does the deployed re-anchor lever extend it? (2026-07-19)

**RQ-P5.15a (gating): YES — decisively, not marginally.** An unmaintained SAM2 carry seeded
at GT[0] and stepped at the deployed 6.15 Hz idle budget is still on-target (IoU >= 0.25 vs
UAV123 GT) on **24 of 25** clips at a 16 s idle horizon — floor was 18/25 — and on **24/25**
at 24 s, three times the longest idle any prior Part V result used. Surviving cells are at
IoU 0.6–0.97, so the margin is real rather than threshold-hugging. The single failure,
`car7`, dies at f270 in a palm-occluded roundabout and never recovers. **Consequence for the
arc:** the carry is *not* the fragile component over a long idle window, which retires the
assumption underneath P5.14's "carry quality on real video is the next binding constraint"
and the assumption that P5.2's WARM 21/25 at ~8 s was carry-bound — those four losses were in
select/delivery, not the tracker. Long idle windows are therefore cheap, which unblocks the
deferred auto-discovery cycle (dropping P5.14's oracle seeds) that needs one.

**RQ-P5.15b: N/A by the pre-registered ceiling** (PLAIN@24s 24 >= 22, no headroom). The
non-gating measurement is the interesting one and is negative: **the deployed idle re-anchor
lever makes long-idle carry worse**, 22/25 vs 24/25 at both 16 s and 24 s. All 100 re-anchor
rounds were accepted (the P5.5 accept rule carries no IoU floor) and they cost `car10`,
`car3` and `person10` while rescuing `car7` — net -2. P5.5's "accepted 16/16, never harmed a
cell" was true only over an 8 s window; given enough rounds, generic-caption re-grounding with
no identity constraint lands on some *other* object of the class.

**Visual gate: PASS.** All 25 `PLAIN_*/h16.png` (the RQ-a claim frames — the rig dumps the
scoring frames themselves, closing the P5.14 `viz_late` gap), all 5 `death.png`, and all 4
MAINT/PLAIN h24 disagreement frames were opened with the Read tool. Every alive/dead flag
matches its pixels; the identity-swap mechanism was *seen* (green box on a different car /
a different person beside the red GT box), not inferred from IoU.
Detail: [`../../experiments/2026-07-19-carry-horizon/README.md`](../../experiments/2026-07-19-carry-horizon/README.md).

### P5.16 — autodisc-select (2026-07-19T15:03Z) — **YES**

**RQ-P5.16a** — With candidate seeds discovered by the deployed VLM during the idle window
instead of taken from ground truth, does WSEL still pass on >= 4 of the 5 gating scenes?
**YES, 4/5.**

**RQ-P5.16b** — Does SWAP still pass the strengthened rule (delivered box IoU < 0.25 vs target
GT AND >= 0.25 vs distractor GT) on >= 4 of the 5 gating scenes? **YES, 4/5.**

**OVERALL: YES.** The P5.14 select result was **not oracle-propped.** Replacing GT seeding with
autonomous idle-window discovery costs exactly **one cell out of twelve** (`car7:460` WSEL);
the other ten gating/control cells are unchanged, including the `car3:200` control that was
pre-registered as likely to flip back to FAIL and did not. Discovery itself never failed
mechanically: 24/24 calls accepted at 4.51 s mean latency, both captions fitting the ~2-slot
budget in all 12 cells. This removes the largest external-validity asterisk on the Part V
headline — the warm-start select arc now runs end-to-end with **no ground truth anywhere in the
loop**, at `acquire_s = 0.00` against a 4.5 s re-ground that disagrees with it on 4/12 cells.

The one loss is instructive and is **not** a carry or delivery failure: at the discovery frame
`car7:460` has two adjacent silver cars, "the silver car" is genuinely ambiguous, the VLM
grounds the wrong one (`seed_iou_gt` 0.0), and that carry is lost during idle. The next binding
constraint for this arc is therefore **referring-expression disambiguation at discovery time**,
not tracking. Note the mechanical fail class (`lost-track`) mislabels this — future
pre-registrations should classify on seed correctness before track outcome.

**Visual gate: PASS.** All 24 gating PNGs (12 `deliver.png` + 12 `discovery_<selected>.png`)
opened with the Read tool. Every scored PASS is corroborated by the pixels, both FAILs show the
failure mode their class claims, no degenerate frame (max single-colour fraction 0.009). The
wrong-object discovery on `car7:460` was *seen*, not inferred.
Detail: [`../../experiments/2026-07-19-autodisc-select/README.md`](../../experiments/2026-07-19-autodisc-select/README.md).

## RQ-P5.17 (2026-07-20) — bankv3-select

**RQ-P5.17a (gating):** on a sim bank engineered so the ~4.4 s prompt-time re-ground lag is
*geometrically costly* (GT box at the deliver frame has IoU <= 0.20 with the prompt-frame box,
both cars, every clip) and that carries all three P5.13-mandated diversity gates, do the two
delivery contracts separate by >= 7 cells of 56?
**Verdict: NO [branch 3 — contracts-equivalent].** DD 56/56 vs RG 55/56, |diff| = 1; both
clear the health floor 45.

**RQ-P5.17b (diagnostic, non-gating):** are DD failures concentrated on the far leg (named car
was the occluded one)? **Verdict: NO** — asymmetry 0; DD is 28/28 in both roles, so there are
no DD failures to attribute to the occlusion aftermath.

This is the **third consecutive sim tie** (P5.10, P5.13, P5.17), and this time both levers the
P5.13 audit blamed were supplied and *measured*: staleness is realized (median ZOH IoU 0.08 at
delivery, vs 0.79 in bank v2.1) and the crossings are designed (max GT–GT IoU 0.28–0.44). The
contracts still do not separate. Per the pre-registered branch-3 text, **sim-select
discrimination is CLOSED**: the DD advantage measured on real video (P5.14, shadow RG
disagreeing on 4/12 real cells) is attributed to **real-imagery VLM fragility that clean Gazebo
renders cannot reproduce** — here RG's VLM grounded the named car correctly on 56/56 cells.
Select levers move to real video; the v3 bank is retained for stack-level questions (carry
through occlusion, mask-quality gates, tracker swaps) where clean deterministic renders with
exact GT are an asset rather than the confound.

Negative result, and a decisive one: it closes a fork the loop had returned to four times.

**Visual gate: PASS.** 19 "looked at" lines — 5 rank-sampled crossing peaks, 5 f150/f225
recession pairs, the 3 proof figures, 5 select cell triplets and the single failing cell — all
opened with the Read tool. Every sampled PASS looks like a pass; the one mechanical FAIL looks
like a real failure.
Detail: [`../../experiments/2026-07-20-bankv3-select/README.md`](../../experiments/2026-07-20-bankv3-select/README.md).
