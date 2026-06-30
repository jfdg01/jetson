# QUESTIONS — Part II (v2 Principled Rebuild)

> Single-frame grounding, Phases 0–4 on `v2/principled-rebuild`. Index: [`../../QUESTIONS.md`](../../QUESTIONS.md).
> Companion docs: `RESULTS.md` (numbers) · `DECISIONS.md` (choices) · `SOURCES.md` (citations).
> RQ ids preserved from each experiment's pre-registration; `Q-*` ids formulated here for runs with no explicit RQ.

---

### RQ-0.1 — Does the v2 contract path (RefCOCO loader + HFBackend + harness, all via contract.py) reproduce the validated Part-I in-domain number?   [Part II · Phase 0 backend fidelity]
- **Answer:** Yes — v2 HF self-check hit 85.0% IoU@0.25 (n=100), within sampling noise of the Part-I Stage-3 reference 82.5%, with parse_rate 100% and non-degenerate center_std 187.8.
- **Why it matters:** Establishes the trusted HF fidelity reference every other backend (GGUF, Jetson) is reported as a delta from; without it no cross-backend gap is interpretable.
- **More:** `experiments/2026-06-17-phase0-backend-fidelity/`

### RQ-0.2 — How large is the HF↔GGUF fidelity gap on the same checkpoint and prompt, and does runtime/preprocessing loss dominate quantization loss?   [Part II · Phase 0 backend fidelity]
- **Answer:** The runtime/preprocessing gap (HF→GGUF-F16) is −16.0pp and dominates the quant gap (F16→Q8_0) of −2.0pp by ~8×, reproducing the Part-I structure (85.0% → 69.0% → 67.0%).
- **Why it matters:** Calibrates the instrument the whole phase exists for — confirming deployment loss is preprocessing-driven, the binding v2 constraint, before it is used to pick the spine.
- **More:** `experiments/2026-06-17-phase0-backend-fidelity/`

### RQ-0.3 — Which model spine should v2 train on?   [Part II · Phase 0 backend fidelity]
- **Answer:** Qwen2-VL-2B — it grounds zero-shot (15% IoU@0.25 vs SmolVLM-base 0%) and its deployment gap is only −2pp vs SmolVLM's −16pp, plus native dynamic resolution.
- **Why it matters:** Chooses the spine by deployment fidelity before any GPU spend, the decision that directly eliminated the Part-I fidelity catastrophe.
- **More:** `experiments/2026-06-17-phase0-backend-fidelity/`

### Q-phase0-1 — Can each candidate spine be served on the Jetson at all via the pinned llama.cpp backend, before any GPU is spent probing it?   [Part II · Phase 0 backend fidelity]
- **Answer:** Only SmolVLM-500M and Qwen2-VL-2B are deployable; PaliGemma 2 and Florence-2 are disqualified for free (no vision-projector or converter support at pinned commit 57fe1f0).
- **Why it matters:** Enforces the deploy-backwards principle — an undeployable spine is ruled out before training, avoiding the exact Part-I failure of discovering the gap post-hoc.
- **More:** `experiments/2026-06-17-phase0-backend-fidelity/`

### RQ-1.1 — Is the aerial target well-posed once filtered to one box per caption, and how much supervision survives that filter?   [Part II · Phase 1 dataset audit]
- **Answer:** No, raw RefDrone is ill-posed (mean 3.80 boxes/caption, fails the 0.95 bar at 0.332); only ~⅓ of captions are well-posed, giving a trainable budget of 4101 train / 439 val (one-box subset passes at 1.000).
- **Why it matters:** Reproduces the Stage-2 collapse killer for free before any GPU-hour and fixes the small supervision budget that favours RefCOCO warm-start.
- **More:** `experiments/2026-06-17-phase1-dataset-audit/`

### RQ-1.2 — What is the aerial object-size distribution, before and after the IMAGE_SIZE=512 long-edge resize?   [Part II · Phase 1 dataset audit]
- **Answer:** Tiny — post-512 √area median ~16 px with bottom quartile 6–10 px (p5≈6), confirming and sharpening the Part-I "2–11 px" claim, ~11× smaller than the RefCOCO control median of 172 px.
- **Why it matters:** Quantifies binding constraint #2 (the tiny-object resolution ceiling) in real numbers so Phase 2 chooses resolution against data, not memory.
- **More:** `experiments/2026-06-17-phase1-dataset-audit/`

### RQ-1.3 — Is RefCOCO (the warm-start corpus) well-posed by construction?   [Part II · Phase 1 dataset audit]
- **Answer:** Yes — 100% one-box-per-caption and large objects (median √area 172 px post-resize), isolating the aerial domain rather than the contract as the source of both problems.
- **Why it matters:** Validates the audit machinery and confirms the contract itself is sound, so fixes target the data, not the method.
- **More:** `experiments/2026-06-17-phase1-dataset-audit/`

### RQ-2.1 — Does increasing the input long edge raise aerial grounding accuracy on the Qwen2-VL-2B base model with no training?   [Part II · Phase 2 resolution]
- **Answer:** Yes, decisively — base-model IoU@0.25 swings 4.1% (512) → 38.7% (1280), a 9.4× gain with weights untouched, clearing the 20% gate at 1024 (30.3%) before any fine-tuning.
- **Why it matters:** Reframes the Part-I 19.5% miss as resolution-starved rather than a training failure, identifying resolution as the dominant lever.
- **More:** `experiments/2026-06-17-phase2-resolution/`

### RQ-2.2 — Does higher resolution keep the output well-formed and input-dependent (no degenerate behaviour)?   [Part II · Phase 2 resolution]
- **Answer:** Yes — center_std rises monotonically 129 → 196 (opposite of the ~61 collapse floor) and parse_rate stays ≥91.8% across the ladder.
- **Why it matters:** Confirms the resolution lever does not trade accuracy for collapse, so the chosen size is safe to train on.
- **More:** `experiments/2026-06-17-phase2-resolution/`

### RQ-2.3 — Where does the resolution ladder plateau, so Phase 3 trains at the smallest size capturing most of the gain?   [Part II · Phase 2 resolution]
- **Answer:** The elbow is at 1024 — the 768→1024 step is the dominant +19.6pp jump and 1024 captures ~78% of the 1280 IoU@0.25 ceiling while per-step return more than halves past it.
- **Why it matters:** Picks max_side=1024 as the deployment-aware sweet spot that Phase 3 trains at, balancing accuracy against Jetson cost.
- **More:** `experiments/2026-06-17-phase2-resolution/`

### RQ-3.1 — Does the Qwen2-VL-2B + RefDrone well-posed + max_side=1024 stack clear the aerial gate IoU@0.25 ≥ 20% after a LoRA fine-tune?   [Part II · Phase 3 train]
- **Answer:** Yes, decisively — 59.5% IoU@0.25 on full val (n=439), ~3.0× the 20% gate and ~3.1× Part-I Stage 4's 19.5%, cleared at epoch 1 without either reserved lever.
- **Why it matters:** The central v2 result proving the Part-I miss was a setup failure, not a training one — a clean well-posed target at adequate resolution clears the bar with margin.
- **More:** `experiments/2026-06-17-phase3-train/`

### RQ-3.2 — Is the fine-tuned output non-degenerate (parse_rate ≥ 90% and center_std far above the ~61 collapse floor)?   [Part II · Phase 3 train]
- **Answer:** Yes — parse_rate 100% (full val) and center_std 215 rising 212→227 in-loop, ~3.5× the collapse floor; the fine-tune also fixed base-model parse leakage (91.8% → 100%).
- **Why it matters:** Confirms the trained spine avoids the Stage-2 marginal-mean collapse signature that killed Part-I.
- **More:** `experiments/2026-06-17-phase3-train/`

### RQ-3.3 — How much of the result is resolution versus the fine-tune on top?   [Part II · Phase 3 train]
- **Answer:** Both roughly double the score independently — resolution lifts base 4.1%→30.3% (512→1024) and LoRA lifts 30.3%→59.5% on top; together they ~3× Part-I.
- **Why it matters:** Cleanly decomposes the 19.5%→59.5% gain into two pre-registered levers, attributing credit honestly for the thesis narrative.
- **More:** `experiments/2026-06-17-phase3-train/`

### RQ-4.1 — Does the deployed GGUF land within the Phase-0 fidelity budget of the HF reference (deployed IoU@0.25 ≥ 57.5%)?   [Part II · Phase 4 export & deploy]
- **Answer:** Yes, decisively — F16 (62.2%) and Q8_0 (62.6%) both clear the 57.5% floor by +4.7/+5.1pp and exceed the HF reference (59.5%) itself; no fidelity debt was spent.
- **Why it matters:** Closes the deployment loop the whole v2 design was built backwards from, proving the trained skill survives export to the Jetson.
- **More:** `experiments/2026-06-18-phase4-export-deploy/`

### RQ-4.2 — On the real fine-tuned model, what is the runtime/preprocessing gap (HF − GGUF-F16) — Part-I's −23pp or Phase-0c's predicted ≈−2pp?   [Part II · Phase 4 export & deploy]
- **Answer:** The −23pp Part-I gap does NOT reproduce — HF→F16 is −2.7pp (F16 slightly beats HF, within n=439 noise), vindicating the Phase-0c deployment-backwards spine choice.
- **Why it matters:** The central Phase-4 finding and payoff of the whole rebuild: choosing the spine by deployment fidelity eliminated the constraint that stalled Part I.
- **More:** `experiments/2026-06-18-phase4-export-deploy/`

### RQ-4.3 — What is the quantization gap (GGUF-F16 − GGUF-Q8_0), and is Q8_0 a safe half-size deployment artifact?   [Part II · Phase 4 export & deploy]
- **Answer:** Quant is effectively free — F16→Q8_0 is −0.5pp (within noise) vs Part-I's −7pp; Q8_0 is recommended at 1.65 GB vs 3.09 GB (≈½ weights) at indistinguishable accuracy.
- **Why it matters:** Confirms the recommended deployment artifact fits the 8 GB Orin Nano budget with headroom at no accuracy cost.
- **More:** `experiments/2026-06-18-phase4-export-deploy/`

### RQ-4.4 — Is the exported projector bit-equivalent to the base Qwen2-VL mmproj, given the vision tower was frozen during LoRA?   [Part II · Phase 4 export & deploy]
- **Answer:** Yes — exported mmproj is the same byte size (1334666400 B) with identical tensor payload (only GGUF metadata header differs), so one mmproj serves base and fine-tune.
- **Why it matters:** Removes the need to ship or version a separate projector, simplifying deployment.
- **More:** `experiments/2026-06-18-phase4-export-deploy/`
</content>
