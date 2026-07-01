# DECISIONS — Part IV (v4 End-to-End Workflow Refinement)

> Decision log for hardening the integrated end-to-end follow pipeline (v4). Index: [`../../DECISIONS.md`](../../DECISIONS.md).
> Per-experiment decisions also live in `experiments/<campaign>/README.md`. ★ = headline decision.
> **Append** — add each new decision at the bottom (chronological, oldest first; matches RESULTS/QUESTIONS).

---

### 2026-07-02 — ★ Spine stays Qwen2-VL-2B; bake-off early-stopped

- **What:** keep Qwen2-VL-2B Q8_0 as the grounding spine; stop the bake-off before arm D and arm E
  legs 2–3; cancel Jetson latency measurement for arms A/C/D.
- **Why:** every measured challenger lost on accuracy (48.5 / 53.1 / 56.0 / 5.5% vs the 62.6–63.1%
  incumbent); arm B proved the deployed ROI lever (85.2%) does not transfer across backbones; and the
  pending acquire-once re-layer (`experiments/2026-07-01-temporal-acquire-carry/`) demotes anchor
  speed — the bake-off's criterion 1 — to a once-per-acquire cost, making accuracy the binding axis,
  which the incumbent wins outright. No remaining run could change the adoption decision.
- **Given up:** Florence-2's "speed-ceiling" datapoint; SmolVLM2 lr=2e-4/4e-4 legs; A/C/D latency
  numbers; the vision-tower-unfreeze follow-up (branch `experiment/vlm-vision-unfreeze` parked as a
  pre-draft).
- → [`experiments/2026-06-30-vlm-backbone-bakeoff/`](../../experiments/2026-06-30-vlm-backbone-bakeoff/README.md)
