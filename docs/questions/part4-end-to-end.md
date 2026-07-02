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

### 2026-07-02 — Temporal acquire-carry, Phase 1 ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

- **RQ-T.5 (skeleton — closed-loop follow under injected acquire cost):** **PASS at 0.25 and
  0.5 m/s** (in-FOV 1.000, occlusion relock ~4.2–4.5 s). The ceiling is 1.0 m/s and it is set by
  the **REGROUND blind window** (LossGate 3 s + acquire ~4.3 s ≈ 7.3 s, target exits the 10 m-AGL
  footprint), not by first acquire or PID tracking. Full RQ-T.5 (real perception) is Phase 3.

### 2026-07-02 — Temporal acquire-carry, Phase 2 ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

- **RQ-T.2 (SAM2 carry FPS on the Orin Nano @ 15 W, ≥5 FPS with ≤5 pp accuracy cost):**
  **marginal FAIL at OP=768** — accuracy holds (IoU@0.25 0.830 vs 0.849 @1024) but 4.89 FPS
  misses the ≥5 gate by 2.2%; 640 clears FPS (7.24 co-resident) but misses the accuracy bar by
  1.2 pp (0.787). No eager-PyTorch size passes both; TensorRT campaign is the named fix.
- **RQ-T.3 (VLM Q8_0 + SAM2 co-residency in 8 GB):** **PASS** — zero FPS cost at 1024/768/640,
  peak RAM 6963/7607 MB @1024 (6144 @640); no load-on-demand needed. The pre-registered
  "likely does not fit" estimate was wrong — recorded as such.

### 2026-07-02 — Temporal acquire-carry, Phase 3 ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

- **RQ-T.4 (occlusion recovery, integrated):** **PASS** — LossGate → validated REGROUND relocks
  after a real 5 s visual occlusion (relock wall ~14 s: the size prior correctly rejects 5
  hallucinated/sliver boxes until the target actually clears the bridge). Run 3a-1 falsified
  *unvalidated* reground: the VLM returns a plausible visible object (road dash) when the target
  is hidden — the accept/reject step is load-bearing.
- **RQ-T.5 (end-to-end follow @0.25 m/s, real perception):** **PASS on host carry (3a: in-FOV
  1.000); on-device (3b @OP=768): behavioral legs PASS (in-FOV 1.000, relock), rate leg marginal
  FAIL (carry-phase 4.1 vs ≥5 FPS)** — the campaign criterion is one TensorRT export short of
  fully met; E1 (`2026-07-02-carry-trt-export`) is the named fix.

### 2026-07-02 — E1 Carry TensorRT encoder export ([`experiments/2026-07-02-carry-trt-export/`](../../experiments/2026-07-02-carry-trt-export/README.md))

- **RQ-E1 (does a TensorRT fp16 export of the SAM2.1-tiny image encoder lift carry FPS past the
  ≥5 co-resident gate without breaking mask parity?):** **YES** — 768 carry 4.89 → 6.15 FPS
  co-resident (+26%, clears ≥5), host mask parity IoU 1.000, on-device fp16 IoU@0.25 unchanged
  (1.000, mean IoU marginally higher). Resolves parent open decisions #1 (keep SAM2.1-tiny, EdgeTAM
  not needed) and #2 (export path = TensorRT). This clears the parent campaign's only marginal-FAIL
  leg (3b carry-phase 4.1 < 5 FPS at OP=768) — 3b re-run at OP=768 with the TRT encoder is next.

### 2026-07-02 — Phase 3b re-run with E1 TRT encoder ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

- **RQ-T.5 (end-to-end follow @0.25 m/s, on-device, revisited):** now **fully PASS**. Re-ran the 3b
  SITL harness at OP=768 with the E1 TRT encoder wired into the carry service — carry-phase rate
  4.1 → **5.0 FPS**, clearing the ≥5 gate (behavioral legs unchanged: in-FOV 1.000, recovered after
  occlusion). The rate leg that was one TensorRT export short is now met; the parent campaign's
  criterion is fully satisfied. Margin is thin (5.0 exactly): the solo E1 bench was 6.15 FPS but the
  integrated loop pays ~1.15 FPS in per-frame JPEG + ssh-tunnel wire transfer.

### 2026-07-02 — E2 speed ceiling with levers on ([`experiments/2026-07-02-follow-speed-ceiling/`](../../experiments/2026-07-02-follow-speed-ceiling/README.md))

- **RQ-E2 (do the occlusion levers move the measured follow ceiling — from Phase 1's 1.0 m/s to
  what?):** **NO — they move it *down*, to < 0.5 m/s.** All three levers-on trials FAIL (in-FOV
  0.484 / 0.076 / 0.051 at 0.5 / 1.0 / 1.5). The levers (size-prior validation, dead-reckoning,
  time-based LossGate) target the REGROUND blind window Phase 1 named, but with real (not oracle)
  carry two earlier failure modes bind first and the levers touch neither: at 0.5 m/s SAM2
  confident-latches the occluder and returns a non-`None` box, so the `box is None`-gated DR and
  REGROUND never fire (copter parks, gap 3→24 m); at 1.0/1.5 m/s the copter never even acquires
  (frozen at home, car leaves FOV at t≈6 s before the ~5 s acquire + stale-box init can lock,
  31/32 re-acquires rejected). So Phase 1's oracle-box ceiling (1.0) overstates the integrated
  real-pipeline ceiling. Both binding modes are fixable (confidence/staleness loss test;
  velocity-extrapolated acquire box) — deferred, named in the campaign README.

### 2026-07-02 — E3 twin-distractor identity test ([`experiments/2026-07-02-twin-distractor/`](../../experiments/2026-07-02-twin-distractor/README.md))

- **RQ-E3a (does CARRY hold the bound target through a same-appearance crossing?):** **YES.** One
  SITL crossing run at 0.25 m/s with an identical white car passing at 3 m (continuously in-frame,
  its pixel down to ~175 px from the tracked box): ID-switch **0.0 s**, 0.0% of 968 boxed frames
  ever closer to the distractor, ends 0.27 m to true vs 25.94 m to the departed distractor. SAM2
  memory (appearance + position) is not fooled by a twin when the true target was never lost.
- **RQ-E3b (does REGROUND re-lock the wrong twin when the true car is occluded?):** **YES —
  wrong-lock 3/3.** All three decoy runs fired a real REGROUND (`n_regrounds=1`, so the E2
  confident-latch amendment does not apply — measurable), and every re-lock's first box landed on
  the parked decoy: the size-prior lever is identity-blind and cannot reject an identical twin by
  construction. The follow then collapses into a static-latch (E2 mode, post-reground) and the true
  car escapes — the accidental same-lane crossing that briefly transfers the box back to the true
  car does not rescue it. This is the pre-registered honest negative; it motivates the reserved
  appearance-embedding gate on reground acceptance (E3b CLIP cosine gate — not run this session).
- **AerialMind cross-check:** distractor *density* alone does not degrade Phase 0 zero-shot carry —
  the distractor-heavy quartile is marginally better (IoU@0.25 +0.011, ID-consistency +0.006), not
  the estimated 2-8 pp worse. The identity failure is specific to occlusion + a same-appearance
  in-lane decoy during REGROUND, not to crowding.

### 2026-07-02 — E4 follow hardening ([`experiments/2026-07-02-follow-hardening/`](../../experiments/2026-07-02-follow-hardening/README.md))

- **RQ-E4a (does a trust-aware loss gate make REGROUND fire under occlusion at 0.5 m/s, recovering
  the follow?):** **YES the follow recovers (0.5 goes FAIL→PASS, in-FOV 1.000), but NOT via the
  gate.** The operative fix was Fix B (always-on submit-frame carry init + gap replay): the `none`
  control passed identically to `motion` (both in-FOV 1.000, relock ~9.3-9.4 s, `n_regrounds=1`),
  so the loss gate was inert at 0.5 — Fix B landing the *initial* lock on the true car (not the ~2.5-5 s
  stale VLM box) is what killed E2's confident-latch. The `score` gate actively *hurt*
  (FAIL, `recovered=false`): SAM2 `object_score_logits` *does* separate occlusion cleanly (occluded
  mean −3.23 vs clear +8.61) but its clear-frame tail dips to −3.94, so at tau=0 it over-fires on
  clean-track noise and the relock is never confirmed. Chosen gate = `motion` by the mechanical rule
  (only qualifying candidate), kept as a harmless backstop, not the fix.
- **RQ-E4b (does submit-frame init + replay lift the ≥1.0 m/s trials off the E2 floor?):** **NO.**
  1.0 in-FOV 0.073 (E2 0.076), 1.5 in-FOV 0.051 (E2 0.051) — both pinned to the floor. At 1.0 carry
  *does* lock (5.01 s) and reground 4×, but the car escapes the FOV during the ~5 s **first-acquire
  hover** — before any lock exists to seed the replay/DR — and the subsequent locks chase a target
  already gone; 1.5 never locks at all. Replay only helps *after* a first lock, so it cannot fix the
  initial hover. First-acquire hover (hold a guessed chase velocity from t=0) is the named remaining
  ceiling, deliberately out of E4 scope. **New follow ceiling: 0.5 m/s** (E2 was `< 0.5`).
