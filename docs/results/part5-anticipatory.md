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

### P5.1 — warm-start acquire (2026-07-04)

Detail: [`../../experiments/2026-07-04-warm-start-acquire/README.md`](../../experiments/2026-07-04-warm-start-acquire/README.md).
Config: Qwen2-VL-2B Q8_0 terse acquire on Jetson Orin Nano (15 W + jetson_clocks, `nvpmodel -m 0`,
no MAXN on this board); SAM2.1-hiera-tiny StreamCarry on RTX 3090 rate-capped 6.15 Hz; mask gate
app-τ=12.0; prompt t_p=8.0 s, 10 s coverage window; 6 clips × {WARM,COLD,ORACLE} × n=2 = 36 runs,
0 INVALID, 0 n=2 splits. Metric: genuine_lock at deliver-frame AND coverage ≥ 0.50 over the window,
best of n=2. Best-of-n from `runs/*/results.json` via `make_proof.py`.

| leg | PASS | passing clips | mechanism |
|---|---|---|---|
| WARM (idle-window VLM seed, select at t_p) | **5/6** | car3, car9, car10, car14, car18 | fresh carry still locked at prompt |
| COLD (E18-A cold acquire shifted to t_p) | 1/6 | car14 | ~135-frame (~4.5 s) stale box; only slow car14 still overlaps |
| ORACLE (GT[0] seed, same catch-up, ceiling) | 5/6 | car3, car9, car10, car14, car18 | GT-seed ceiling — identical PASS set to WARM |

Per-clip (WARM / COLD / ORACLE, genuine_lock·coverage·deliver_iou):
car3 T·1.00·.62 / F·.00·.00 / T·1.00·.66 · car7 F·.11·.00 / F·.00·.00 / F·.11·.00 ·
car9 T·1.00·.88 / F·.00·.06 / T·1.00·.88 · car10 T·1.00·.81 / F·.00·.00 / T·1.00·.81 ·
car14 T·.98·.69 / T·.95·.50 / T·.98·.73 · car18 T·.99·.90 / F·.00·.00 / T·.99·.94.

W=5/6, C=1/6, O=5/6. **WARM-vs-ORACLE gap = EMPTY** (real idle VLM seed == GT seed on every clip;
zero detection headroom). Sole failure car7 = occlusion at the prompt frame (`gt[240]` absent) →
carry-bound, also fails ORACLE. See `proof/warm_vs_cold_vs_oracle.png` (coverage + freshness) and
`proof/car10_warm_vs_cold.mp4` (fresh vs stale delivery).
