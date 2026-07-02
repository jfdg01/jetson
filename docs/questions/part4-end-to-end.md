# QUESTIONS — Part IV (v4 End-to-End Workflow Refinement)

> Hardening the integrated NL→ground→track→fly pipeline. The two-tier loop passed T0–T4 in
> isolation, but doesn't hold up end-to-end yet. Index: [`../../QUESTIONS.md`](../../QUESTIONS.md).
> Companion docs: `RESULTS.md` (numbers) · `DECISIONS.md` (choices) · `SOURCES.md` (citations).
> RQ ids preserved from each experiment's pre-registration; `Q-*` ids formulated here for runs with no explicit RQ.

---

### 2026-06-30 — VLM backbone bake-off ([`experiments/2026-06-30-vlm-backbone-bakeoff/`](../../experiments/2026-06-30-vlm-backbone-bakeoff/README.md))

- **RQ-B.1 (Pareto winner):** **the incumbent Qwen2-VL-2B** — no contender reached its accuracy at
  any speed; the Pareto front is the baseline alone.
- **RQ-B.2 (beat baseline on both axes):** **No.** Best challenger (PaliGemma2-3B) −6.6pp on
  accuracy; Qwen2.5-VL-3B slower AND less accurate on both paths; the rest worse.
- **RQ-B.3 (compression vs recall):** **collapse confirmed** — aggressive pixel-shuffle (SmolVLM2,
  5.5%) cannot learn aerial boxes; fixed-res (PaliGemma2, 56.0%) trains cleanly but loses. Bonus
  negative: the ROI-crop lever *inverted* on Qwen2.5-VL-3B (33.0% < its 53.1% WF) — the lever is
  backbone-specific, not architectural.
- **RQ-B.4 (health):** parse=100% on every arm; center_std ≈ GT 22.9 for A/B/C (healthy);
  E's 12.7–18.6 flagged its collapse exactly as the gate was designed to.

### 2026-07-02 — Temporal acquire-carry, Phase 0 ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

- **RQ-T.1 (zero-shot carry — make-or-break):** **PASS** — SAM2.1-tiny carries aerial targets
  zero-shot: IoU@0.25 0.849, ID-consistency 0.891 over 186 AerialMind tracks; the temporal
  training lever stays unpulled. Occlusion re-association is the weak tier (32.9% over 70 gap
  events) — that budget belongs to the REGROUND trigger, whose mechanics (plus RETARGET) the
  committed demo already exercises on real Jetson acquire.
