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
