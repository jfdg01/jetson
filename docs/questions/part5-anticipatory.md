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
