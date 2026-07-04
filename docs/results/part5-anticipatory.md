# RESULTS — Part V · Anticipatory grounding / warm-start acquire (v5)

Index: [`../../RESULTS.md`](../../RESULTS.md) · Companion: [`../questions/`](../questions/) (research questions) · [`../decisions/`](../decisions/) (what was chosen & why).
Per-campaign detail lives in `experiments/<campaign>/README.md`. Append, never overwrite.

---

## Part V — Anticipatory grounding / warm-start acquire (v5)

Goal: the operator's prompt does not arrive at frame 0 — the drone streams video for seconds
before the operator speaks, so the pre-prompt window is free compute. Instead of a cold
blocking acquire at prompt time (which lands stale, Part IV E18–E23), keep salient objects
already tracked over the idle window and **select on command**. Reframe origin:
`experiments/PART5-PROPOSAL-anticipatory-grounding.md`.

<!-- append one result row per campaign below -->
