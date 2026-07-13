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

### P5.2 — warm-start generalization + on-screen-speed sweep (2026-07-04)

Detail: [`../../experiments/2026-07-04-warm-start-generalization/README.md`](../../experiments/2026-07-04-warm-start-generalization/README.md).
Config identical to P5.1 (Q8_0 terse acquire, SAM2.1-tiny TRT fp16 6.15 Hz, mask gate app-τ=12.0,
t_p=8 s, 10 s window, Jetson 15 W + jetson_clocks). Extends P5.1's 6 cars to **25 clips × 5
categories × a data-driven on-screen-speed sweep** (0.00–15.62 %frame-diag/s), clips selected from
UAV123 GT via `profiles.py` (measured, not eyeballed). n=1 (P5.1 was bit-identical across reps);
75 legs, 0 INVALID. Metric unchanged: genuine_lock at deliver-frame AND coverage ≥ 0.50.

| leg | PASS | mechanism |
|---|---|---|
| WARM (idle-window VLM seed, select at t_p) | **21/25** | fresh carry still locked at prompt; 5 categories (car/person/boat/wakeboard/bike) |
| COLD (cold acquire at prompt, delivered stale) | 5/25 | ~135-frame stale box; survivors are deliver-frame geometry accidents, not slow clips |
| ORACLE (GT[0] seed, ceiling) | 22/25 | GT-seed ceiling; 2-clip detection headroom over WARM at scale |

WARM 4 misses: car7, person10 `[deliver-occluded]` (GT absent at deliver frame 240 → fail ORACLE
too; 21/23 = 91% on the non-degenerate set); person18, car17 `[detection-bound]` (ORACLE passes,
idle-window VLM seed is the binder). WARM *beats* ORACLE on wakeboard2 (cov 0.677 > 0.443).

**Speed sweep (RQ-P5.2b):** per-clip WARM−COLD coverage gap vs on-screen speed — Spearman
ρ = **−0.06** (flat). Per-bin mean gap: slow **+0.42**, med **+0.76**, fast **+0.62** — large and
positive in every bin, NOT rising with speed. The staleness-grows-with-speed prediction is
refuted: warm-start's payoff is a flat offset (COLD's *delivery* lag sinks it broadly, independent
of motion). Full per-clip table in the experiment README. Proof: `proof/gap_vs_speed.png` (the
thesis figure — ρ + per-bin means), `proof/generalization_grid.png` (PASS by category),
`proof/person20_warm_vs_cold.mp4` (fast non-car money shot: fresh WARM tracks, stale COLD misses).

### P5.3 — multi-candidate select-on-command (late-binding phrase select, 2026-07-14)

Detail: [`../../experiments/2026-07-14-multi-candidate-select/README.md`](../../experiments/2026-07-14-multi-candidate-select/README.md).
First Part V test of the *selection* stage (P5.1/P5.2 all had one dominant target, so select was
trivially satisfied). Two same-class candidates carried through the idle window (target = oracle
GT[f0] seed, distractor = hand box); at t_p the deployed VLM (Qwen2-VL-2B q8_0 terse, max_side 1024,
Jetson 15 W + jetson_clocks) fires on the prompt frame, and its stale box is **matched by IoU
against the candidates' carried boxes at the prompt frame** (`argmax IoU`, NO_MATCH floor 0.10) —
then the matched *track's live box* is delivered. 5 car scenes × 3 legs (WSEL / SWAP / CSEL), n=1
deterministic, 15/15 ran clean (exit 0), no abort. Same-frame delivery for all legs (isolates the
late-binding claim from the delivery-lag win already proven in P5.1/P5.2).

| leg | PASS | mechanism |
|---|---|---|
| WSEL (target phrase → matched live track) | **3/5** | car10:240, car9:300, car7:460 lock at IoU 0.81-0.87; car10:615 + car3:200 fail |
| SWAP (distractor phrase → should flip selection) | **2/5** | car9:300, car3:200 flip correctly; other 3 NO_MATCH on the distractor caption |
| CSEL (cold deployed baseline, non-gating) | **1/5** genuine_lock | car10:240 only — cold stays broadly stale, consistent with COLD 5/25 (P5.2) |

**Verdict: NO** (RQ-P5.3a FAIL 3/5 < 4; RQ-P5.3b FAIL 2/5 < 4). **Dominant failure = NO_MATCH**
(4 of 7 non-passes): the stale VLM box at the prompt frame overlapped neither carried candidate
(max IoU ~0.000), i.e. the deployed VLM grounded the caption onto an object outside both tracks
(third in-frame cars; type/colour phrase ambiguity for the distractor captions). **Not a match-rule
bug** — the 3 WSEL passes deliver the correct live track at IoU 0.81-0.87 whenever the VLM boxes a
carried candidate. The late-binding IoU-match mechanism is *sound but not robust*: it is bottlenecked
by the deployed VLM's raw grounding accuracy at the prompt frame, not by carry drift or the match
rule. Motivates the crop-scoring family (CLIP crop-text / VLM multiple-choice over the carried
candidate crops directly) as the next deep-research target. Proof: `proof/p53_pass_grid.png`
(outcome grid), `proof/p53_deliver_iou.png` (WSEL matched 0.81-0.87 vs CSEL stale ~0 same frame),
`proof/car9_300_WSEL.mp4` + `proof/car9_300_SWAP.mp4` (phrase flips the selected track in one scene).
