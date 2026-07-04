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
