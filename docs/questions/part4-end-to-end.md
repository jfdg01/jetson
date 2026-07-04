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

### 2026-07-03 — E5 pursuit-chase ([`experiments/2026-07-02-pursuit-chase/`](../../experiments/2026-07-02-pursuit-chase/README.md))

- **RQ-E5 (does position-seeking pursuit DR — command = est. velocity + 0.5·(dead-reckoned position
  − copter position), 2.5 m/s cap — lift the follow ceiling from 0.5 to ≥1.0 m/s without regressing
  0.5?):** **NO. Ceiling stays 0.5 m/s.** p-0.5 held in-FOV 1.000 (no regression; pursuit near-inert
  when the deficit is small). But p-1.0 FAILed 0.076 and p-1.5 FAILed 0.051 — **not** because
  pursuit couldn't close the deficit, but because **neither run ever locked** (`first_lock = None`,
  31/32 acquires rejected). With `hist` never seeded, pursuit never engages (empty history →
  ACQUIRE hover), so it was never actually exercised at 1.0. The failure mode surfaced this run is
  the **stochastic first-acquire rejection** (the E4 1.5 audit flag), not the deficit pursuit
  targets. This overturns the E4-audit premise that at 1.0 "the first lock lands while the car is in
  FOV" — that was an n=1 accident; here 1.0 patterned with 1.5's never-lock.
- **RQ-E5 sub — does pursuit hold a target once seeded?** **YES, at 1.5 m/s.** p-1.5b (repeat of
  p-1.5) had its t=0 submit-frame attempt *accepted* (lock @4.66 s) and pursuit then held the car at
  in-FOV 0.927 through 2 regrounds/relocks (6.89, 6.92 s) — a PASS at 1.5 m/s. Identical config,
  opposite first-acquire outcome to p-1.5 → **1.5 = SPLIT (stochastic)**, confirming the audit flag
  and overturning E4's "1.5 never acquires" (at least one of two did). **The binding constraint is
  now the acquire lottery, not the chase controller** → next lever is making the first acquire
  reliable (e.g. retry/relaxed-validate on the t=0 submit frame), which pursuit cannot substitute for.

### 2026-07-03 — E6 first-acquire ([`experiments/2026-07-03-first-acquire/`](../../experiments/2026-07-03-first-acquire/README.md))

- **RQ-E6 (does a pre-first-lock motion-hold — servo the PID on the ego-motion-compensated
  frame-diff blob so the car stays in FOV across VLM draws — lift the follow ceiling past 0.5 m/s by
  fixing first-acquire reliability?):** **YES. Ceiling lifts from 0.5 to at least 1.0 m/s.** mh-0.5
  PASS (no regression) and 1.0 PASS 3/3 (gate: in-FOV ≥0.90 AND recovered) → RQ-E6 = YES per the
  pre-registered rule. 1.5 also PASS 3/3 (reported; does not affect the RQ). The mechanism is
  confirmed by the now-captured acquire_log: at 1.5 m/s the VLM rejected 8-17 draws before the first
  accept, yet **in_fov_frac = 1.000 every run** — the motion-hold servo kept the car in frame across
  all those car-in-FOV rejected draws until a repeatable accept landed. This directly overturns E5's
  "acquire lottery" (p-1.0 exited FOV after ≤2 draws, in-FOV 0.076, never locked): the hold converts
  "few draws before the car leaves" into "unlimited draws on a car-in-FOV frame". The size prior was
  never relaxed — every rejected box was a genuine dash/false box (Stage-0's finding), and the hold
  simply buys the time for a correct draw. **The binding constraint reframed by E5 (first-acquire
  reliability, not the chase controller) is now resolved for ≤1.5 m/s.** Residual at 1.5: slower
  *relock* after occlusion (23-28 s vs ~7 s at 1.0) — a next-lever candidate, not first-acquire.

### 2026-07-03 — E7 reground-gate ([`experiments/2026-07-03-reground-gate/`](../../experiments/2026-07-03-reground-gate/README.md))

- **RQ-E7 (does a motion-consistency gate on REGROUND acceptance — accept a size-passing VLM
  box only if it sits on the ego-compensated mover blob — convert E3-S2's decoy wrong-lock
  into a relock on the true car, without regressing plain-occlusion relock at 0.5 and 1.0
  m/s?):** **NO.** mg-decoy a/b/c all FAIL (`relock_on[0] == "distractor"`, `final_d_true`
  4.05-4.32 m > 2.0). The gate fires (6-8 REGROUND rejects vs 0 control) and delays relock,
  but the true car drives past the parked decoy and transiently co-locates it with the mover
  blob, so a decoy box eventually passes → wrong-lock persists 3/3. Regression legs held
  (mg-reg-0.5/-1.0/-1.5 all PASS, in-FOV 1.000, recovered), so no plain-occlusion regression.
  Motion consistency is necessary-not-sufficient against a same-lane parked distractor on the
  target's own path. Reground acceptance remains identity-unsafe for this scenario; a moving
  or on-path same-appearance distractor is out of reach of any purely-geometric gate.

### 2026-07-03 — E8 reground-selfcorrect ([`experiments/2026-07-03-reground-selfcorrect/`](../../experiments/2026-07-03-reground-selfcorrect/README.md))

- **RQ-E8 (given a 150 s trial — 2x E7's 75 s — does the already-deployed E4 stillness
  loss-gate + E7 reground motion-gate self-correct off the E7 decoy wrong-lock onto the true
  car, using clock time alone and no new mechanism?):** **NO.** All three gated legs
  (mg-decoy-a/b/c-long) FAIL every PASS gate: last `relock_on == "distractor"`,
  `closest_at_end == "distractor"`, `final_d_true` ~26.5 m > 2.0, in-FOV ~0.49 < 0.90. Not a
  dead-mechanism failure — the E4 loss-gate fired (`n_regrounds` 2 gated / 5 control) and the
  E7 gate actively rejected the still decoy (29-32 reground rejects vs 0 control). The binding
  constraint is upstream of both: by the time the loss-gate forces a reground (~67-69.5 s),
  the true car has driven ~26.5 m downstream and out of frame, so the only salient near-camera
  car the VLM can propose is the parked decoy — extra time cannot help with no true-car box to
  reacquire. Control (loss-gate alone) also ends on the decoy, so attribution is unchanged from
  E7. Adds a **durability caveat** to E7's NO (geometry-only correction has a ceiling; once the
  target leaves frame during the wrong-lock, more clock time alone can't recover it — confirms
  search/identity, E7's own named next lever, is required) rather than reversing it.

### 2026-07-03 — E9 retarget-switch ([`experiments/2026-07-03-retarget-switch/`](../../experiments/2026-07-03-retarget-switch/README.md))

- **RQ-E9 (with all deployed levers on, can the two-tier loop execute a mid-follow
  natural-language target switch — CARRY on "the white car", then at t=50 s command "the blue
  car" — locking the new target within 15 s and following it to trial end, 3/3 at 0.5 m/s,
  without breaking the control leg?):** **YES.** Precondition color smoke PASS (white 10/10,
  blue 10/10 — the deployed VLM color-discriminates on synthetic top-down frames; the
  pre-registered blue open question did not bite). ctl PASS (escort present, no retarget →
  in-FOV 1.000, `closest_at_end == "true"`; the blue car alone does not break the white-car
  follow). rt-a/b/c all PASS all 7 criteria: switch wall **2.35 s** (<= 15), last
  `switch_on == "distractor"`, `closest_at_end == "distractor"`, `final_d_dist` 0.41-0.43 m
  (<= 2.0), `frac_box_closer_dist_post` 1.00 (>= 0.80), `dist_in_fov_frac_post` 1.00 (>= 0.90),
  whole-trial in-FOV 1.000 (>= 0.90). The switch reuses the not-CARRY acquire/relock path
  already validated at 0.5 m/s; the first post-switch VLM draw returned the blue escort
  directly (single draw, no white-car false-accept). Closes the second half of the north-star
  sentence ("switch to that blue truck") — the retarget verb, untested in E1-E8, works at the
  E6 follow ceiling. Post-switch the escort ("distractor" label) IS the commanded target, so
  the twin metrics' PASS values are the sign-flipped intended ones, and `id_switch_s` ~22.3 s
  is correctly ignored on rt legs. n=3 real (distinct md5s, n_frames 1378/1313/1319).

### 2026-07-03 — E10 fast-follow-ceiling ([`experiments/2026-07-03-fast-follow-ceiling/`](../../experiments/2026-07-03-fast-follow-ceiling/README.md))

- **RQ-E10 (does the deployed lever stack — Fix B + motion loss-gate + pursuit DR + motion
  acquire-hold — hold a follow at 2.0 m/s once the two rig artifacts, the 140 m world edge and
  the 2.5 m/s DR speed cap, are removed? Falsifiable: with `--vmax 4.0` + auto-extended world,
  >= 2/3 legs at 2.0 m/s pass `in_fov_frac >= 0.90 AND recovered_after_occlusion`, AND the
  1.5 m/s regression leg still passes):** **YES.** reg-1.5 PASS (in_fov 1.000, recovered,
  first_lock 16.57 s — confirms no ≤1.5 behavior change from parameterizing the caps) and s2.0
  3/3 PASS (in_fov 1.000, first_lock 2.30 s). **Measured ceiling = 2.5 m/s** (s2.5 3/3 PASS);
  s3.0 0/2 FAIL. The old E2 "< 0.5 m/s" ceiling was a **rig artifact** (140 m world edge + the
  pursuit 2.5 / hist_vel ±2.5 / PID 3.0 caps), not physics — the loop tracks to 5x that once
  they are removed. **Above 2.5 the binding constraint flips to first-acquire, not tracking:**
  both 3.0 legs never locked (in_fov 0.052, 31/32 acquires rejected, first_lock None — the
  E5/E6 acquire-lottery, a standing-start copter can't get a repeatable VLM draw before a
  3.0 m/s car crosses the FOV); once locked at 2.0/2.5, carry+pursuit hold in_fov 1.000 to
  trial end. So the lever to raise the ceiling past 2.5 is first-acquire reliability at speed,
  not the pursuit controller or carry FPS. Latency signature (secondary): relock wall-time
  *falls* with speed (25.9→13.9→6.8 s) and carry px error rises modestly (80→128 px), both
  benign while in_fov stays 1.000. n=3 at 2.0 and 2.5, n=2 at 3.0.

### 2026-07-03 — E11 chase-acquire ([`experiments/2026-07-03-chase-acquire/`](../../experiments/2026-07-03-chase-acquire/README.md))

- **RQ-E11 (does upgrading the pre-first-lock hold from a positional servo to a blob-pursuit
  chase — `--acquire-hold chase`, pre-lock blob track feeds the existing `hist_vel`→`pursuit_vel`
  DR — make first-acquire reliable at 3.0 m/s and raise the ceiling to >= 3.0? YES iff reg-2.5
  passes the standard gate AND >= 2/3 s3.0 legs pass):** **YES.** reg-2.5 PASS (first_lock
  2.30 s, in_fov 1.000 — no chase-regression, byte-identical to E10 s2.5) **and** s3.0 **3/3**
  PASS (in_fov 1.000, first_lock ~9.2 s). Where E10's `motion` hold left s3.0 never-locked
  (in_fov 0.052, first_lock None — the car escaped the FOV by draw 2 and the P-servo hovered
  on blob loss), chase-hold keeps the 3.0 m/s car in-frame across draws (15 acquire attempts,
  13 rejected on s3.0a/b) until the VLM locks at ~9.2 s, then carry+pursuit hold in_fov 1.000
  to trial end. **The binding constraint was car-in-frame time under a hover-on-blob-loss
  control law, not VLM draw repeatability** — the chase reuses the already-validated DR/pursuit
  machinery, changes nothing about the VLM or carry, and is off by default. **New measured
  ceiling >= 3.5 m/s** (NOT pinned): the stretch probe s3.5 passed **2/2** at `--vmax 5.0`
  (in_fov 0.96, recovered through occlusion), so the real ceiling is above 3.5 and E11 did not
  find it — the follow ceiling moved 2.5 → at least 3.5 m/s in one lever (7x the E2-era "< 0.5").
  Chase over-performed every estimate (s3.0 est 50-60% → 3/3, s3.5 est ~20% → 2/2; no
  garbage-blob DR runaway). n=1 reg, n=3 at 3.0, n=2 at 3.5.

### 2026-07-03 — E12 late-command ([`experiments/2026-07-03-late-command/`](../../experiments/2026-07-03-late-command/README.md))

- **RQ-E12 (does the E11 follow ceiling hold at 3.5 m/s once the t=0 "gift frame" is removed —
  i.e. is the pre-lock chase itself, not an easy spawn, what carries 3.5?):** **NO.** With
  `--acquire-delay 3.0` blocking any lock before t=3 s, d3.5 fails **0/3** (never-locked,
  first_lock None, in_fov ~0.03) while the d3.0 control still PASSes (in_fov 1.000, locks 12.17 s
  ≈3 s later than E11's gift-frame 9.2 s). E11's ">= 3.5" was a draw-1 easy-spawn artifact — the
  s3.5 locks landed at 2.30 s on a car that had already left the FOV at 2.25 s, so the blind chase
  was never exercised at 3.5; s3.0 were genuine. **Honest chase-validated follow ceiling = 3.0
  m/s** (6x the E2-era "< 0.5"). Above 3.0 the binding mode is the pre-lock blind DR chase failing
  to re-close on a target that outruns the FOV before the first legal draw — the next lever is
  pre-lock chase reach (DR gain / faster first draw), not the tracker.

### 2026-07-03 — E13 identity-gate ([`experiments/2026-07-03-identity-gate/`](../../experiments/2026-07-03-identity-gate/README.md))

- **RQ-E13 (does an appearance-template gate on REGROUND acceptance — bind a body-colour
  descriptor at NL grounding, accept a size-passing reground box only if its crop matches
  within tau — convert the E3-S2 decoy wrong-lock into a relock on the true car 3/3 at 0.25 m/s,
  without regressing plain relock at 0.5, the E12 3.0 m/s ceiling, or the E9 retarget switch?):**
  **NO.** ap-decoy **0/3** (all end latched on the decoy, true car escaped to ~26.5 m,
  in-FOV ~0.49). The gate is real and fires hard — template correctly bound to `[245,245,245]`,
  14-26 REGROUND rejects/leg (reason `gate`) of clean decoy boxes vs 0 in control — but is
  defeated by a **blend box**: when the true car emerges co-located with the parked decoy the VLM
  draws a two-car box (`[268.8,0,428.8,441.6]`), whose brightest quartile is dominated by the 245
  true-car pixels so it passes tau=12, yet the box centres on the decoy → SAM2 latches the decoy.
  A bright-pixel colour statistic over a loose box is not spatially bound to the tracked instance,
  so it is defeated the same way the size prior (E3) and the motion gate (E7) were — a global crop
  cue cannot enforce identity on a two-car blend. Regression clean: ap-reg-0.5, ap-reg-3.0 (E12
  hard-spawn config), and ap-rt (E9 switch, 2.35 s, 7/7) all PASS — the gate, off by default and
  consulted only on REGROUND, touches nothing else. Precondition smoke PASS 10/10 (the shade-215
  decoy is still boxed as "the white car"; descriptor gap 0.0 vs 30.0 as measured offline). This
  extends the E3/E7/E8 identity-hole arc: three cues now fail it (size E3, motion E7, colour E13),
  all for the same reason — none is bound to the tracked instance. Named next lever: an embedding
  computed on the SAM2 *mask* (not the box crop), and/or rejecting blend/oversized boxes at
  REGROUND before the descriptor is consulted. n=3 decoy, n=1 each regression.

- **RQ-E14 (does binding the REGROUND identity gate to the instance SAM2 actually latches — the
  per-channel *median* BGR over the frame-0 mask of a throwaway StreamCarry init on the proposed
  box, L-inf ≤ tau 12 vs the template bound at NL grounding — defeat the two-car blend box that
  defeated E13's crop gate, i.e. end the 215-decoy leg on the TRUE car 3/3 at 0.25 m/s with no
  regression on 0.5 relock, the E12 3.0 m/s ceiling, or the E9 retarget?):** **YES.** mk-decoy
  **3/3** (relock_on `[true]`, closest_at_end true, final_d_true 0.21-0.22 m, in_fov 1.000, template
  `[245,245,245]`); mk-reg-0.5, mk-reg-3.0, mk-rt all PASS (retarget rebinds the template to the
  blue escort `[230,90,40]`, E9 7/7). This is the **first identity cue to close the hole** — where
  size (E3), motion (E7), and E13's crop-colour all failed on the two-car blend box, the mask median
  succeeds because it is a majority vote over the pixels SAM2 *actually segments*: while the true car
  is co-located with the decoy the reground box straddles both, the latch is majority-decoy, the
  median reads 215 and is rejected (11-13 rejects/leg); once the cars physically separate the VLM
  draws a clean true-car box (t≈86 s), the mask median reads 245, and SAM2 locks the true car.
  Win path = **reject-until-separated**, not first-frame accept; the pre-registered *identity-
  preserving no-relock* failure branch did not occur. The mechanism is structural (not a shade-215
  artifact) — the design-time GPU probe predicted the blend median [215,215,215] exactly. Regression
  clean: the gate is off by default and consulted only on REGROUND after the size prior, so the
  single-car legs recorded 0 rejects and the follow ceiling is untouched. n=3 decoy, n=1 each
  regression. Next open question: robustness under harder ambiguity (near-identical shades, >2
  distractors, partial re-occlusion during separation) and porting the gate to the 3b remote-carry
  path (currently local-carry only).

- **RQ-E15 (is the E14 mask-median REGROUND gate robust to the win-path geometry — a second
  same-shade decoy 7 m north with no clean window (`--decoy2 7.0`), and a second occlusion over
  t[82,92] covering E14's observed accept at t=86.25 (`--occ2 82 10`) — or did E14's 3/3 depend on
  its single favourable accept window?):** **NOT-MEASURABLE.** The pre-registered patch-regression
  guard fired: **reg-e14** — E14's byte-for-byte mk-decoy config re-run under the E15 patched code —
  FAILed with identity-preserving no-relock (gate rejected all 12 reground boxes, never re-accepted,
  DR-coasted to 3.41 m from the true car; `closest=true, in_fov=1.000`, so it did NOT wrong-lock the
  decoy — it missed the accept window), where E14 converged to 0.21 m 3/3. Per the rule, reg-e14 FAIL
  forces NOT-MEASURABLE and halts stress-family attribution. Both controls reproduced (ctl-dd/ctl-ro
  latched the decoy ~26.6 m from true) so the geometries are valid traps. **The load-bearing
  observation for the next audit:** the EASIEST leg (reg-e14) failed to accept while 5/6 HARDER stress
  legs accepted clean true boxes late (t≈100–114, ≤0.53 m) — this fits stochastic win-path fragility
  (E14's "3/3" being three catches of one narrow accept window, missable on an independent draw) more
  than a systematic patch break (which would kill accepts uniformly). This QUALIFIES E14's "identity
  hole closed 3/3" — the gate's *rejection* is solid, but the *reject-until-separated win path* may be
  stochastic. Cannot decide E15-patch-perturbation vs E14-fragility this cycle (the `np.array_equal`
  selfcheck proves render identity, not timing identity across the code deltas). Recorded stress
  outcomes (NOT claimed): dd 2/3 (dd-c verified-but-lost to decoy-2), ro 3/3. Next lever: re-run
  reg-e14 at n≥3 on E14's merged code (no E15 patch) to isolate whether the failure is the patch or
  the rig — before any further hardening or the 3b remote-carry port.

- **RQ-E16 (2026-07-03) — Is E14's "identity hole closed 3/3" a reliable behaviour or a stochastic
  win path? Re-run E14's byte-identical mask-gate config n=8 on current main (fixed code) and read
  the relock-on-true rate: RELIABLE iff <=1 FAIL/8, QUALIFIED iff 5-6/8, FRAGILE iff <=4/8):**
  **QUALIFIED (r=6/8).** Six of eight reps relocked the true car (final 0.12-0.21 m, in_fov 1.000,
  accepts t=81.30-133.90 s); the two FAILs are DIFFERENT modes and neither is an identity breach —
  rep-5 is the reg-e14 mode exactly (no-relock: gate rejects 11 + size rejects 40, the VLM never
  offered a clean post-separation box, DR-coasted to 26.85 m staying closest=true), rep-1 relocked
  the true car early at t=71.88 s before full separation then drifted to the decoy side (wrong-end,
  closest=distractor 18.15 m). No rep ever relocked on the decoy (no GATE-BREACH). ctl (no gate)
  REPRODUCES the wrong-lock (26.71 m, closest=distractor), so the rig is valid. **This settles the
  E15 anomaly:** E15's reg-e14 FAIL was a genuine draw from a ~0.75 rate, NOT an E15 code regression;
  E14's 3/3 was the favourable tail of a QUALIFIED behaviour. The gate's *rejection* of the blended
  box is solid (0 identity breaches in 8), but the *reject-until-separated re-acquire* succeeds only
  ~75% of the time — bounded by an upstream event (the VLM offering a clean box in the accept window),
  not by the gate. Also corrects E15's README misstatement that E14 accepted "at t=86.25 in all
  three" (actual E14 accepts were 76.55/81.38/86.25 — E14 already varied under fixed code).

- **RQ-E17 (2026-07-03) — Does `--reground-hold chase` (E11's pre-lock blob-chase extended to
  REGROUND blind phases) lift the mask-gate relock rate above E16's 6/8, with zero identity breaches
  and no regression at the 3.0 m/s honest ceiling? (LIFTS/YES iff 0 FAILs over >=8 reps; PARTIAL/
  QUALIFIED iff 1 FAIL; NO-LIFT/NO iff >=2):** **NO (r=0/10).** The lever REGRESSED the rate from
  6/8 to 0/10 — every rep FAILed no-relock [HOLD-MISS], rg_fov 0.025 (predicted >=0.95, exactly
  backwards). Mechanism: during a REGROUND blind phase the blob-chase servos onto the nearest blob,
  which is the 215 decoy (not the lost true car), and drives the drone ~82 m off (final_d_true
  81.2-83.7 m vs E16's worst DR-coast 26.85 m); the true car leaves frame at once (in_fov 0.23), the
  VLM never offers a clean box, the mask gate is never consulted (gate_rejects 0, size_rejects ~52).
  No GATE-BREACH (no rep relocked the decoy — it never re-acquired at all). Guards guard-a/b both
  PASS at 3.0 m/s (in_fov 1.000, recovered, first_lock 9.86-12.17 s) -> NO-REGRESSION at the honest
  follow ceiling; the harm is specific to the slow-mover REGROUND regime. **Directional finding:**
  E11's chase-hold does NOT transfer from pre-first-lock acquisition (one blob = the target) to
  post-loss REGROUND (the decoy is the dominant blob); the failure mode inverts. E16's *passive*
  DR-coast (6/8) is strictly better than the *active* chase (0/10) for re-acquisition. Lever rejected;
  `--reground-hold` stays off by default. This closes the identity arc: the mask gate (E14/E16) is
  the standing answer — identity-safe (0 breaches) at a ~0.75 re-acquire rate bounded by the VLM's
  clean-box offer, and that upstream bound is NOT fixable by a pursuit-side chase lever.

### 2026-07-03 — E18 real-video-replay ([`experiments/2026-07-03-real-video-replay/`](../../experiments/2026-07-03-real-video-replay/README.md))

- **RQ-E18 (does the deployed stack genuinely lock and hold a real target on real aerial footage at
  wall-clock cadence, vs dataset GT?):** **NO [grounding-bound].** On 6 UAV123 car sequences replayed
  at 30 fps (frames dropped during inference), the full stack PASSes 1/6 clips (car10 only; PASS =
  genuine_lock AND coverage ≥ 0.50, better of n=2). The oracle-init carry control (leg B) PASSes 6/6
  (coverage 0.92–1.00), so the carry tier is real-video-ready and the binder is the acquire tier —
  hence [grounding-bound]. **But the mechanism is acquire *latency*, not *accuracy*:** the ~4.85 s
  full-frame VLM acquire computes a correct box (SAM2 latches the right car; carry then holds at
  cov 0.90–0.99 on the three loss-free clips), but by the time it returns the target has moved ~146
  frames, so `genuine_lock` — scored at the arrival frame — misses on 5/6. car10 passes only because
  its target is slow at t=0 so a frame-0 box still overlaps GT ~4.85 s later. Secondary finding:
  REGROUND inherits the same staleness and the appearance-only E14/E16 mask gate cannot catch a
  stale-but-right-colour re-acquire (car7: carry cov collapses 0.99→0.28 after its occlusion trips a
  loss, gate_rej=0). This is the sim-to-real gap measured: carry crosses to real footage, the
  deployed single-blocking-acquire cadence does not. Estimate (3–5/6 PASS) inverted — it assumed the
  risk was grounding accuracy; the real wall is acquire latency vs target motion. Next threads (out
  of scope): motion-compensated acquire (project forward by measured latency), faster/ROI acquire, a
  position-aware REGROUND gate. No UNRULED legs.

### 2026-07-04 — E19 motion-comp-acquire ([`experiments/2026-07-04-motion-comp-acquire/`](../../experiments/2026-07-04-motion-comp-acquire/README.md))

- **RQ-E19 (does motion-compensating the acquire/REGROUND box for its own ~4.85 s latency lift
  E18's A-full from 1/6 to >= 4/6 on the same clips/captions/scoring?): PARTIAL [flow-fragile].**
  Best arm FLOW = 2/6 (car3 flipped to PASS at ncc 0.87, car10 held); BUF = 1/6. ctl reproduced
  E18's signature (D4 guard PASS). The [flow-fragile] suffix fires on 4 clips (rule: >= 2): car9
  refused (ncc 0.32) and car14/car18/car7 confidently wrong-matched (ncc 0.51-0.64, shifted IoU
  0.000 at arrival, unshifted same-or-better). Mechanism findings: FLOW's arrival-frame init is
  catastrophic when the match is wrong OR refused — it discards E18's submit-frame-correct init,
  latches the wrong object, and poisons the E14 mask-gate template so REGROUND rejects genuine
  relocks (coverage 0.000, strictly below the no-MC baseline 0.285-0.993). BUF cannot flip
  genuine_lock in principle under the frozen scorer (its first emitted box is still the raw box at
  arrival) but its catch-up converges as designed (3.09 s, gap < 12 f on 12/12 runs) and repairs
  coverage: car7 0.285 -> 0.934 (the E18 REGROUND-drift mode eliminated), car18 0.711 -> 0.914.
  Verdict band: motion compensation bolted onto a ~4.85 s acquire is not the lever; the binder
  remains raw acquire latency (faster/ROI acquire), or a buf-style submit-frame init re-scored at
  convergence — which the frozen metric deliberately does not credit. No UNRULED legs.

- **RQ-E20 (does prompt-scoped cell-crop acquire cut acquire latency enough to flip E18's stale
  locks into genuine arrival-frame locks, unchanged E18 metric?): PARTIAL [hint-fragile].**
  cell = 3/6 (car9 + car14 flipped to PASS, car10 held; E18 A baseline 1/6); cellbuf identical
  3/6. The latency lever itself worked exactly as estimated: mean scoped acquire 1.85 s vs
  ~4.85 s full-frame (padded 3x3 cells, 173k-262k px vs 590k), backlog ~146 -> 47-62 frames, no
  coverage regression (car7 0.285 -> 0.997, car18 0.711 -> 0.981 from the earlier lock alone).
  The residual 3 FAILs are target-size-bound, not latency-bound: small targets (car3 16x41 px)
  displace more than their own footprint even in ~1.8 s, so arrival-frame IoU pins ~0 while
  coverage sits at 0.98+ — the frozen lock metric is now the conservative bound and the honest
  next axis is lock scoring (convergence-scored lock) or even-smaller crops (resolution axis,
  D7's E21). [hint-fragile] fired 2/2: a wrong hint makes the VLM hallucinate the caption in the
  empty crop, the wrong lock poisons the E14 mask-gate template, and all 10 genuine REGROUND
  re-offers get rejected — a deployment needs a hint-escape (full-frame + fresh template after N
  gate rejects). No UNRULED legs.
