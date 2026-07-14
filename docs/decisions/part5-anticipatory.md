# DECISIONS — Part V (v5 Anticipatory grounding / warm-start acquire)

> Decision log for the warm-start / select-on-command reframe (v5). Index: [`../../DECISIONS.md`](../../DECISIONS.md).
> Per-experiment decisions also live in `experiments/<campaign>/README.md`. ★ = headline decision.
> **Append** — add each new decision at the bottom (chronological, oldest first; matches RESULTS/QUESTIONS).

---

<!-- append decisions below -->

### P5.1 — warm-start acquire (2026-07-04)

★ **Adopt warm-start (idle-window seed + select-on-command) as the Part V acquire path; retire the
cold blocking acquire for the mid-flight-prompt case.** P5.1 shows WARM 5/6 == ORACLE ceiling 5/6
vs COLD 1/6, and WARM==ORACLE with zero detection headroom lost. *Given up:* nothing on quality —
the real VLM seed matched GT; the cost is keeping a carry warm over the idle window (free compute,
the whole premise). *Why not push COLD harder:* Part IV (E18–E23) exhausted cold-acquire speedups;
warm-start sidesteps the ~4.5 s staleness entirely rather than shaving it.

- **Score the lock AT the prompt frame (t_p), not from t_lock over the whole clip.** This is what
  exposed car7's occlusion-at-prompt (E18-B's whole-clip coverage hid it). Keeps the metric honest
  about "is the target actually there when the operator asks?". *Given up:* comparability with the
  E18-B number — deliberate; the t_p-anchored metric is the point of Part V.
- **Froze t_p=8.0 s (single prompt time).** Simplifies the matrix and puts every clip in the
  `[ready-only]` regime (t_p > acquire). *Given up:* the early-prompt / cold-fallback regime
  (t_p < acquire) — a separate future experiment, not conflated here.
- **Single-salient-target clips only (selection is trivial).** P5.1 isolates seed-quality-at-t_p,
  not candidate disambiguation. The multi-candidate phrase-selector (twin-distractor) is the next
  experiment, kept out to avoid confounding the warm-vs-cold result.

### P5.2 — warm-start generalization + on-screen-speed sweep (2026-07-04)

★ **Reframe the warm-start mechanism: the win is delivery-lag removal, not motion-compensation.**
RQ-P5.2b measured the WARM−COLD gap vs on-screen speed and found it **flat** (Spearman ρ=−0.06;
gap large in every speed bin, slow +0.42 / med +0.76 / fast +0.62). The Part V premise assumed cold
staleness scales with target motion during the ~4.5 s acquire; it does not — COLD's ~135-frame
*delivery* lag sinks it broadly regardless of speed. *Consequence for Part V direction:* future
warm-start work should target seed quality and the early-prompt (t_p < acquire) fallback, NOT a
speed-adaptive acquire — there is no speed axis to adapt to. *Given up:* the speed-sweep thesis
figure as a positive result; kept as a clean documented negative (a wrong estimate is content).

- **Data-driven clip selection from GT (`profiles.py`), not eyeballed.** On-screen speed = median
  centroid displacement in %frame-diagonal/s, computed over consecutive valid GT frames; bins are
  the eligible-set tertiles. Makes the speed axis measured and reproducible. *Given up:* nothing —
  the alternative (hand-picking "fast-looking" clips) would have confounded the RQ-P5.2b axis.
- **Restrict to the 36 whole UAV123 sequences with their own frame dir; drop group/uav (segments)
  and truck/bird (no ≥700-frame clip).** The replay rig zips `sorted(*.jpg)` with anno 1:1 and
  cannot resolve frame-offset segments. *Given up:* two categories and the segment clips —
  a real dataset constraint, recorded not worked around; 5 categories still clears the ≥4 bar.
- **n=1 (P5.1 was bit-identical across reps).** Greedy decode + deterministic rig; n=2 bought
  nothing on P5.1's 36 legs. *Given up:* stochastic-variance measurement — none exists here.
- **Keep the 2 `[deliver-occluded]` clips (car7, person10) in the /25 denominator.** They fail
  `genuine_lock` on all legs (GT absent at deliver frame), so they are structural not detection
  misses; kept for P5.1 comparability and reported flagged with window coverage. *Given up:* a
  flattering 21/23; the honest denominator is /25 = 21/25, with the /23=91% stated alongside.

### P5.3 — multi-candidate select-on-command (2026-07-14)

★ **Late-binding IoU-match chosen over crop-scoring for the first select test — and the FAIL now
promotes crop-scoring to the next deep-research target.** P5.3 selected candidates by firing the
deployed phrase-grounding VLM on the prompt frame and matching its (stale) box by IoU to the
carried candidate boxes, then delivering the matched track's live box. *Why chosen:* it reuses only
deployed, already-validated components (the Part II RefDrone-fine-tuned VLM is a referring-expression
model by lineage; the IoU match is `replay_source.iou` + existing carry) — no new method, no new
citation, runnable immediately. *Rejected:* CLIP crop-text similarity / VLM multiple-choice over the
candidate crops — lower-latency and they score the *carried candidates directly* (no free-frame
grounding), but neither is grounded in repo code or cited work, so each needs a deep-research cycle
first. *Outcome / consequence:* P5.3 FAILED on the match mechanism (NO_MATCH 4/7 non-passes — the
VLM's prompt-frame box misses both carried candidates), exactly the pre-registered trigger to
promote the crop-scoring family. *Given up (for now):* sub-acquire-latency selection; the next
Part V select experiment should be a deep-research cycle on crop-scoring, landing SOURCES citations
before designing.

- **Oracle-seeded 2-candidate set (target = GT[f0], distractor = hand box), enumeration out of
  scope.** Candidate *discovery/maintenance* over the idle window is charter backlog item 2; P5.3
  isolates the *select* stage given a known candidate set, justified by P5.1/P5.2 where WARM matched
  ORACLE. *Given up:* end-to-end realism — but it cleanly separates "can the phrase pick the right
  carried track" from "can we find the candidates", so the NO_MATCH finding is unambiguously a
  grounding-accuracy result, not a seeding artifact.
- **Car scenes only; person/K>2 dropped.** The downloaded UAV123 person subset has no ≥8 s
  co-visible same-class distractor pair (person13/person20 ~5-6 s); K>2 is future work. *Given up:*
  category breadth for the select test — recorded as a negative curation result, not worked around.
- **Same-frame delivery for all legs (WSEL/SWAP/CSEL all deliver at prompt+acquire).** Differs from
  P5.1's earlier warm delivery — deliberately removes the delivery-lag advantage so P5.3 measures
  *only* the late-binding select claim (delivery-lag removal already proven in P5.1/P5.2). *Given
  up:* showing warm's full end-to-end win again; kept the experiment a clean single-variable test.

### P5.4 — ROI-constrained select-on-command (2026-07-14)

- **ROI-constrained late-binding select over CLIP crop-scoring as the gating mechanism.** P5.3
  pre-registered CLIP crop-scoring as the next deep-research target; a deep-research cycle was run
  this cycle (ReCLIP IPS, red-circle visual prompting -> SOURCES) and then a design-time pilot
  *falsified* CLIP as a gate on 16-100 px aerial crops: vanilla IPS is size-biased (picked the
  larger silver target for "the black car" at 0.963) and the best of 5 variants (circlectx, red
  ellipse + 2.5x context, ViT-L/14) reached only 5/6 with near-tie margins. *Chosen instead:*
  reuse the deployed Part III ROI-crop lever (validated, +22.6pp, ~2.0s) to constrain *where the
  VLM looks*, keeping the P5.3 IoU-match unchanged. *Given up:* pre-registering a verdict on CLIP
  crop-scoring — demoted to a recorded non-gating secondary arm (`clip_select`, 7/10) so the
  crop-scoring question is settled as documented evidence, not a burned cycle on a predictable FAIL.
- **In-run outcome: the ROI pivot is a latency win but not a select win.** Post-hoc, the ROI crop
  cut acquire ~2.3x (2.08s) but left the VSEL verdict at 3/5 (identical to P5.3). The two select
  failures survive cropping — an in-crop third object (NO_MATCH by construction of the union window)
  and a sub-resolution target the upscale can't rescue. *Recorded for the next cycle:* cropping to
  the candidate union does not fix grounding when a distractor sits *between* the carries; the next
  lever must either (a) crop per-candidate (single-carry windows, disambiguating by which crop the
  phrase scores highest — closer to the falsified CLIP arm but with the ROI upscale) or (b) accept
  the VLM grounding ceiling and change the contract. Do NOT re-propose union-crop select.
