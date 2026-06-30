# QUESTIONS — Part III (v3 Object Permanence)

> Persistent moving-target tracking on `v3/object-permanence`, T0–T4 + latency levers. Index: [`../../QUESTIONS.md`](../../QUESTIONS.md).
> Companion docs: `RESULTS.md` (numbers) · `DECISIONS.md` (choices) · `SOURCES.md` (citations).
> RQ ids preserved from each experiment's pre-registration; `Q-*` ids formulated here for runs with no explicit RQ.

---

### Q-charter-1 — What architecture does persistent, language-conditioned single-object tracking on an 8 GB Orin actually force, and can it be built from existing assets?   [Part III · charter]
- **Answer:** A two-tier split is forced by hardware — a sparse VLM semantic anchor (~0.3–1.2 Hz) re-seeding a fast 20 Hz per-frame tracker — because the ~20–60× rate gap is structural, not closable by a faster VLM; Parts I/II supply the plumbing (ByteTrack, oracle labels, the 62.6% Qwen2-VL-2B Q8_0 anchor) so Part III's only new work is *object permanence* (identity through absence).
- **Why it matters:** Frames the entire thesis chapter — the contribution is memory + correct re-anchor, not rebuilding a stack, and it pre-registers the two binding constraints (cadence-vs-dynamics budget; identity through absence).
- **More:** `experiments/2026-06-18-part3-charter/`

### Q-charter-2 — Is Gemma 4 the right anchor model for this hardware, as requested?   [Part III · charter]
- **Answer:** No foregone choice — native-video Gemma 4 is 26B/31B only (won't fit 8 GB), the E2B/E4B that fit are image-only and were the *slowest* candidates measured (0.49 / 0.34 Hz, slower than SmolVLM-500M's 1.2 Hz); it enters T0 as the slow incumbent-to-beat with its token-budget lever untested, not a default.
- **Why it matters:** Keeps spine selection "by the numbers" (Part II discipline) and prevents banking a "good fit" claim before measurement.
- **More:** `experiments/2026-06-18-part3-charter/`

### RQ-T0a — What is the deployed Qwen2-VL-2B Q8_0 end-to-end anchor rate on the Orin (15 W) across 512/768/1024 long-edge, split into prefill vs decode?   [Part III · T0]
- **Answer:** 0.44 / 0.27 / 0.16 Hz (2265 / 3644 / 6416 ms wall); decode is ~constant (~1.1 s, 21.6 tok/s) while prefill (image encode) dominates and scales ~linearly with pixels (1113→5111 ms) — so prefill is the cadence lever. Operating point chosen = 512 (2.27 s/anchor), since the 640×480 source means 768/1024 give no fidelity, only latency.
- **Why it matters:** Sets the real anchor cadence the whole loop budget rests on and names prefill as the thing to attack (later: ROI-crop).
- **More:** `experiments/2026-06-18-t0-cadence/`

### RQ-T0b — Does the per-frame ByteTrack tracker fit the 20 Hz (50 ms) budget, with headroom for an added re-ID model?   [Part III · T0]
- **Answer:** Yes, trivially — `ByteTracker.update()` median 0.051 ms (p99 0.103 ms) on the dev box, ~1000× headroom; an appearance/re-ID memory is computationally free.
- **Why it matters:** Proves constraint #2 (permanence) is an accuracy problem, not a compute one — there's room for the memory mechanism.
- **More:** `experiments/2026-06-18-t0-cadence/`

### RQ-T0c — How fast does an aerial target move in pixels between anchors, and does that break the tracker?   [Part III · T0]
- **Answer:** Per-frame motion peaks at 27.7 px/frame (10 m × 10 m/s) — tiny vs the 110–222 px box, so 20 Hz frame-to-frame association is never the bottleneck; the binding tension is instead recovery-after-loss, because the 2.27 s anchor period exceeds the 1.5 s coast horizon → re-acquisition must be event-triggered (fire on loss), not timer-only.
- **Why it matters:** Quantifies the cadence-vs-dynamics budget and pre-registers the event-triggered re-acquisition design for T2/T3.
- **More:** `experiments/2026-06-18-t0-cadence/`

### RQ-T0d — Is the target crop large enough at follow altitude for an appearance/re-ID memory to have signal?   [Part III · T0]
- **Answer:** Comfortably at 10–20 m (≥55 px short side, above the ~32–64 px floor), marginal at 30 m (37 px) — so appearance memory is viable low/mid-altitude and motion-continuity must backstop high altitude; the embedding-separability half is deferred to T1/appearance-SNR.
- **Why it matters:** Says appearance re-ID is on the table for T2 and bounds where it can be trusted.
- **More:** `experiments/2026-06-18-t0-cadence/`

### RQ-T1.1 — Can the §6 temporal metric suite be expressed as pure, deterministic, pytest-locked functions over a per-frame `(pred_box, gt_box, visible, locked_id)` stream?   [Part III · T1]
- **Answer:** Yes — all nine metrics (SOT success/precision, success-plot AUC, ID switches, identity purity, re-acquisition time, oracle-coverage, following error, track-loss events) added to `grounding/contract.py` stdlib-only and pytest-locked, `make test` green.
- **Why it matters:** Turns "keep a lock on the white van" into numbers a gate can read, with no GPU/renderer cost.
- **More:** `experiments/2026-06-18-t1-temporal-contract/`

### RQ-T1.2 — Does the SITL clip recorder produce a deterministic, replayable scored dataset whose oracle-GT metrics reproduce across re-runs at fixed seed?   [Part III · T1]
- **Answer:** Yes — `clip_recorder.py` (stdlib+numpy, no renderer) emits `labels.jsonl`+`manifest.json` for two clips (`crossing_occlusion`, `clean_follow`) with reproducible scoring; the scorable artifact is the GT label stream, not pixels, so RGB rendering is deferred to T2.
- **Why it matters:** Gives a reproducible eval set + a validated scorer, closing the T1 gate with zero GPU/renderer.
- **More:** `experiments/2026-06-18-t1-temporal-contract/`

### RQ-T1.3 — Do the clips actually contain the four permanence stressors at measurable severity, and does the memoryless baseline visibly fail on them?   [Part III · T1]
- **Answer:** Yes — on `crossing_occlusion` the memoryless ByteTrack re-locks the wrong same-class object after occlusion: identity purity 0.725, 1 ID switch, 1 of 2 re-acquisitions failed, oracle-coverage 0.575 (vs near-perfect on the control), making constraint #2 numeric.
- **Why it matters:** Establishes the exact bar (the baseline numbers) that the T2 permanence mechanism must beat.
- **More:** `experiments/2026-06-18-t1-temporal-contract/`

### Q-t2-1 — Does an appearance-memory re-ID with a refuse-to-lock gate beat memoryless ByteTrack on identity through occlusion, and at what range/SNR does it hold?   [Part III · T2]
- **Answer:** Yes above the separability knee (appearance SNR ≳ 1) — identity purity 0.725→1.000, ID switches 1→0, failed re-acq 1→0, following error 67.7→0.13 px, coverage 0.575→0.695 (the visible-frame ceiling); below snr≈0.8 it honestly degrades back to the baseline (0.751 purity).
- **Why it matters:** Solves the headline permanence problem but explicitly bounds the win by the (still-unmeasured) appearance-SNR/range frontier — the gap the appearance-SNR experiment then targets.
- **More:** `experiments/2026-06-24-t2-permanence/`

### Q-t3-1 — When the lock *drives the camera* (closed loop), does appearance memory still hold the true target through an occlusion/crossing where the memoryless policy gets steered off?   [Part III · T3]
- **Answer:** Yes — true-target oracle-coverage 49.2%→97.6% (deterministic kinematic A/B) and 53.7%→71.5% (live ArduCopter SITL); both policies crush the Phase-C ~0% negative on a moving target, and the gap between them shows the win is the permanence mechanism, not just a faster loop.
- **Why it matters:** Confirms permanence survives the harder closed-loop regime where a wrong re-lock compounds (camera steers off → target lost) — in real flight dynamics too.
- **More:** `experiments/2026-06-24-t3-closed-loop/`

### Q-t4-1 — Does the integrated two-tier loop fit the T0 cadence budget on the actual Orin (not the dev box)?   [Part III · T4]
- **Answer:** Yes — fast tier 0.143 ms median (p99 0.291 ms, ~350× under the 50 ms budget) on the Orin CPU, real in-loop VLM anchor 2264 ms / 0.44 Hz / 100% bbox parse (−0.03% vs T0a), anchor period 2.26 s > 1.5 s coast → event-triggered re-acq confirmed on metal; `deploys_within_t0_budget = True`.
- **Why it matters:** Closes the deployment gate honestly — the only material sim-to-device gap (2.8× slower tracker) is immaterial against the budget, so the device can host the loop.
- **More:** `experiments/2026-06-24-t4-deployment/`

### Q-demo-1 — Can the two-tier architecture be shown running live end-to-end on real aerial video with real on-Orin VLM anchors?   [Part III · system-demo]
- **Answer:** Yes — a live 2/3-tab `grounding/deploy/gui.py` where tab 2 runs real Orin VLM anchors (~2.26 s cadence) seeding a real CSRT tracker that coasts between anchors on VisDrone clips; the honest seam is that closed-loop *following* stays sim-only (no actuation on a pre-recorded clip — that's the T3 result).
- **Why it matters:** Makes the architecture tangible for the thesis/defense without faking the one tier (closed loop) that real video can't exercise.
- **More:** `experiments/2026-06-25-system-demo/`

### RQ1 (terse) — Does a terse output format cut decode tokens/wall-time on the Orin as predicted (~24→~10 tok, ~1.1→~0.6 s)?   [Part III · terse]
- **Answer:** Yes, but only with all three pieces (drop JSON + 0–100 precision + EOS supervision) — decode 24→12 tokens, decode −45% (967→531 ms), anchor wall −24% (1807→1372 ms) on real images at 512; the first attempt (bare ints @0–1000) saved only −7% because the model clung to brackets.
- **Why it matters:** Halves decode toward the sub-1 s anchor, and exposed a real latent training bug (targets never supervised to emit EOS).
- **More:** `experiments/2026-06-25-terse-output-retrain/`

### RQ2 (terse) — What is the accuracy cost of the terse re-LoRA vs the JSON deploy model?   [Part III · terse]
- **Answer:** None — it's a strict upgrade: Orin Q8_0 IoU@0.25 = 63.1% vs JSON deploy 62.6% (+0.5 pp), HF +2.5 pp (62.0% vs 59.5%), center_std healthy.
- **Why it matters:** Lets the terse artifact replace the JSON deploy with better accuracy *and* nearly half the decode.
- **More:** `experiments/2026-06-25-terse-output-retrain/`

### RQ3 (terse) — Does the bracket-free terse format hurt parse rate / introduce silent-corruption failure modes?   [Part III · terse]
- **Answer:** Not after the fix — 100% parse on real images once EOS was supervised; without EOS the bare format rambled (`27 48 34 65 65 65…` to the token cap, parse 5%), and bare-@0–1000 also risked silent dropped-comma corruption, motivating a range-checked 4-int parser.
- **Why it matters:** Confirms the robustness risk the pre-registration flagged was real and resolved.
- **More:** `experiments/2026-06-25-terse-output-retrain/`

### RQ1 (ROI-crop) — Does feeding a tight ROI crop at native size drop on-Orin prefill ~3× as the area model predicts, with decode unchanged?   [Part III · ROI-crop]
- **Answer:** Yes — crop@512 prefill 2.7× cheaper (3691→1374 ms) and crop@384 4.2× (→885 ms) vs full-frame@1024, prefill ≈ linear in prompt tokens; decode unchanged (~964 ms, same output format).
- **Why it matters:** Attacks the dominant half of the anchor latency (prefill) without touching decode.
- **More:** `experiments/2026-06-25-roi-crop-anchor/`

### RQ2 (ROI-crop) — Does a tight crop fed at the 512 budget *raise* RefDrone IoU@0.25 above 62.6% by beating the resolution ceiling, and where does context loss bite?   [Part III · ROI-crop]
- **Answer:** Yes, dramatically — M=2.0 @512 = 85.2% (+22.6 pp), M=1.5 = 83.8%; the crop *upscaled* to 512 is super-resolution on the target, while downscaling the full frame to 512 collapses 64.0%→15.9% (constraint #2 measured directly); context loss starts hurting past M≈2 (M=5 = 78.6%).
- **Why it matters:** Identifies the resolution ceiling as the dominant accuracy lever all along, beatable for free with no retraining.
- **More:** `experiments/2026-06-25-roi-crop-anchor/`

### RQ3 (ROI-crop) — Is there a config that is both prefill-faster AND at least as accurate as full-frame (the deploy point)?   [Part III · ROI-crop]
- **Answer:** Yes, emphatically — crop M=2.0 @512 wins on *both* axes (2.7× cheaper prefill AND +22.6 pp), not a tradeoff; adopted as the re-anchor deploy config (M=2.0 @384 = 4.2× at 82.5% for a tighter budget).
- **Why it matters:** Picks the deploy config and makes the sub-1 s anchor reachable when stacked with the terse decode lever.
- **More:** `experiments/2026-06-25-roi-crop-anchor/`

### RQ4 (ROI-crop) — How fast does accuracy fall as the crop prior is perturbed (real tracker drift, not an oracle prior)?   [Part III · ROI-crop]
- **Answer:** Robust — flat 82–85% up to half-a-box drift, and even a full-box drift stays well above the 62.6% baseline (M=2.0 = 74.3%, looser M=3.0 = 79.7%); the win is genuine localization, not a center-bias artifact.
- **Why it matters:** Shows the lever survives realistic tracker drift, so it's safe for the re-anchor deploy path; M=3.0 is the safer margin under hard drift.
- **More:** `experiments/2026-06-25-roi-crop-anchor/`

### RQ1 (appearance-SNR) — What is the real appearance SNR between an aerial target and its nearest same-class decoy, on real crops?   [Part III · appearance-SNR]
- **Answer:** Not yet measured — pre-registered (2026-06-25) against VisDrone-MOT with a stdlib HSV-histogram + Bhattacharyya scorer; no result recorded yet.
- **Why it matters:** Would convert T2's assumed `snr ≳ 1` knob into a measured number, deciding whether cheap color appearance suffices or permanence must route through the VLM anchor.
- **More:** `experiments/2026-06-26-appearance-snr/`

### RQ2 (appearance-SNR) — How does that SNR vary with crop area (range), and at what crop area does it cross the T2-critical ~1.0?   [Part III · appearance-SNR]
- **Answer:** Not yet measured — pre-registered as the SNR-vs-crop-area curve with a "critical area" crossing; no data yet.
- **Why it matters:** Defines the operating range over which appearance memory is trustworthy vs collapses (T2's cliff).
- **More:** `experiments/2026-06-26-appearance-snr/`

### RQ3 (appearance-SNR) — Across the SITL follow target's operating crop-size range (≈AREA_REF 3000 px²), is real SNR above or below 1.0?   [Part III · appearance-SNR]
- **Answer:** Not yet measured — the pre-registered one-number verdict (T2 PASS "at measured SNR" vs marginal vs fail) is pending the run.
- **Why it matters:** Directly restates the T2 gate as validated-on-real-pixels or honestly amber/negative.
- **More:** `experiments/2026-06-26-appearance-snr/`

### RQ4 (appearance-SNR) — Does a stdlib HSV color histogram already separate target from decoy (making a learned embedding YAGNI)?   [Part III · appearance-SNR]
- **Answer:** Not yet measured — pre-registered "lazy gate": HSV histogram is rung 1, escalate to a tiny embedding only on evidence; no result yet.
- **Why it matters:** Decides whether the cheap descriptor is enough or the learned-embedding rung is needed for re-ID.
- **More:** `experiments/2026-06-26-appearance-snr/`

### Q-demotab-1 — Does the ROI-crop prefill lever transfer to the deployed terse Q8_0 live on-device?   [Part III · ROI-demo-tab]
- **Answer:** Yes qualitatively — ROI re-anchor prefill pinned at ~1375 ms (matching the offline 1374 ms) vs full-frame 3042–4034 ms = 2.2–2.9× live, boxes preserved/tightened; a cadence re-measure also corrected the demo constant (ROI re-anchor ~2.0 s, cold acquire ~4.8 s, not 2.26 s). Quantified on-device Q8_0 IoU@0.25 remains the open follow-up.
- **Why it matters:** On-device confirmation that the latency lever (and the two levers stacked) is real outside the offline HF sweep.
- **More:** `experiments/2026-06-26-roi-demo-tab/`

### Q-spiral-1 — Is the ROI re-anchor (crop around the previous box) stable when the cadence is pushed fast, or does it feed back?   [Part III · ROI-spiral]
- **Answer:** Negative result — an unbounded shrink-and-drift spiral: crop = 4×box fed native with no floor means box shrinks → crop shrinks → fewer pixels/context → smaller/drifted box (observed 195 px box → 0×21 px, locking onto a wrong white car); fixed with a one-line `ROI_MIN_CROP = 384` floor (eval default unchanged). On-device re-confirm still pending.
- **Why it matters:** Documents a real failure mode of the headline lever and its minimal fix — thesis content on why ROI re-anchor needs a crop floor.
- **More:** `experiments/2026-06-27-roi-shrink-spiral/`

### Q-srupscale-1 — Does a learned super-resolver (Swin2SR) beat classical interpolation for grounding tiny aerial targets at equal fed resolution?   [Part III · ROI-SR]
- **Answer:** Preliminary (smoke n=5 only; full n=429 run was still in progress) — no advantage: at crop 400→feed 1024, all methods hit 60% IoU@0.25, with mean IoU lanczos 0.500 > bicubic/swin2sr 0.457 > native 0.361, and Swin2SR adds ~1350 ms; early signal is "classical (lanczos) is already maxed, learned SR doesn't help and costs latency," but this is not yet the full-set verdict.
- **Why it matters:** Tests whether the ROI upscale step should switch from LANCZOS to a learned SR; preliminary answer is no, keeping the cheap classical path.
- **More:** `experiments/2026-06-30-roi-sr-upscale/`

### Q-wholeframe-1 — What is the accuracy-vs-latency tradeoff of feeding the whole frame at higher max_side on the Orin?   [Part III · whole-frame]
- **Answer:** In progress (512 and 1024 arms done; 1536/1920 still running) — 512: IoU@0.25 31.4%, mean IoU 0.187, prefill 241 tok/816 ms, wall 1424 ms; 1024: IoU@0.25 63.1%, mean IoU 0.477, prefill 837 tok/3712 ms, wall 4400 ms — accuracy roughly doubles 512→1024 at ~3× wall (prefill ~linear in fed megapixels), confirming the resolution ceiling, but the higher arms aren't measured yet.
- **Why it matters:** Quantifies, per sample, exactly how much detail on tiny targets a bigger whole-frame buys vs its prefill cost — the baseline the ROI-crop lever is meant to beat.
- **More:** `experiments/2026-06-30-whole-frame-resolution/`
</content>
