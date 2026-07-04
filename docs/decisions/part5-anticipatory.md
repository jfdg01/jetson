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
