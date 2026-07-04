# QUESTIONS — Part V (v5 Anticipatory grounding / warm-start acquire)

> The operator's prompt arrives mid-flight, not at frame 0 — the pre-prompt stream is free
> compute. Can we keep salient objects tracked over the idle window and SELECT on command,
> approaching the E18 B-oracle ceiling (6/6) instead of the cold-acquire floor (E18-A 1/6)?
> Index: [`../../QUESTIONS.md`](../../QUESTIONS.md).
> Companion docs: `RESULTS.md` (numbers) · `DECISIONS.md` (choices) · `SOURCES.md` (citations).
> RQ ids preserved from each experiment's pre-registration; `Q-*` ids formulated here for runs with no explicit RQ.

---

<!-- append one RQ + one-line verdict per campaign below -->

### E24 — warm-start acquire (2026-07-04)

**RQ-E24:** does seeding the carry from a real VLM detection during the idle pre-prompt window
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
