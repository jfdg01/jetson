# RESULTS — Jetson Orin Nano Edge-LLM Benchmarks (index)

> Running ledger, split per Part so a thesis session loads only the relevant chapter.
> Full metric tables + per-campaign pointers live in the per-Part file. Append, never overwrite.
> See `CLAUDE.md` for required fields. Companion: `QUESTIONS.md` (RQs) · `DECISIONS.md` (choices) · `SOURCES.md` (citations).

**Global config (all llama.cpp runs):** Jetson Orin Nano 8 GB · 15 W locked (`nvpmodel -m 0` + `jetson_clocks`) · llama.cpp `57fe1f0` CUDA sm_87 · Q4_K_M · ngl=99 · n_ctx=4096 · pp512/tg128 · 5 reps each.
**Idle baseline:** ~5.2 W · ~1820 MB RAM · ~11–50 MB swap (zram; "swap hit" = growth >50 MB over idle).

| Part | File | Scope |
|---|---|---|
| I | [`docs/results/part1-exploratory.md`](docs/results/part1-exploratory.md) | device benchmarks + grounding Stages 1–4 |
| II | [`docs/results/part2-rebuild.md`](docs/results/part2-rebuild.md) | v2 single-frame grounding, Phases 0–4 |
| III | [`docs/results/part3-permanence.md`](docs/results/part3-permanence.md) | v3 persistent tracking, T0–T4 + latency levers |
| IV | [`docs/results/part4-end-to-end.md`](docs/results/part4-end-to-end.md) | **in progress** — end-to-end workflow refinement |

---

## Campaign catalog (headline pointers)

### Part I — Exploratory → [`docs/results/part1-exploratory.md`](docs/results/part1-exploratory.md)
- llamacpp-upper-bound (2026-06-13) — Llama-3.2-3B Q4_K_M @15W: 14.5 tok/s, ~13.6 W
- model-capability-sweep (2026-06-14) — 10 models 0.5–8B; +Gemma-family sweep; +VLM grounding Phase A (zero-shot)
- toy-nl-demo (2026-06-15) — NL pipeline mechanics work; zero-shot grounding fails (expected)
- phase-b-sitl / phase-c-vlm (2026-06-15) — oracle SITL PASS; zero-shot VLM branch negative
- Stage 2 SmolVLM finetune (2026-06-16) — IoU@0.25 1.0% mode collapse (text-only LoRA limit)
- Stage 3 RefCOCO finetune (2026-06-17) — IoU@0.25 82.5% HF, but −30pp export gap FAIL
- Stage 4 RefCOCO→RefDrone curriculum (2026-06-17) — IoU@0.25 19.5% (narrow miss)

### Part II — Principled rebuild (v2) → [`docs/results/part2-rebuild.md`](docs/results/part2-rebuild.md)
- Phase 0 backend-fidelity (2026-06-17) — spine gate: Qwen2-VL-2B chosen
- Phase 1 dataset audit (2026-06-17) — 33% well-posed; median aerial object ≈16 px @512
- Phase 2 resolution (2026-06-17) — max_side=1024 elbow (4.1%→38.7% no training)
- Phase 3 LoRA (2026-06-17/18) — IoU@0.25 59.5%
- Phase 4 export & deploy (2026-06-18) — Jetson Q8_0 62.6%, no fidelity loss

### Part III — Object permanence (v3) → [`docs/results/part3-permanence.md`](docs/results/part3-permanence.md)
- T0 cadence (2026-06-18) → T4 on-Orin deploy (2026-06-24) — all GATE PASS
- terse re-LoRA (2026-06-26) — decode −45%, IoU 63.1%
- ROI-crop anchor (2026-06-26) — 2.7× prefill AND +22.6pp (85.2%)
- ROI demo tab / shrink-spiral fix / SR-upscale negative (2026-06-26→30)

### Part IV — End-to-end workflow refinement (v4) → [`docs/results/part4-end-to-end.md`](docs/results/part4-end-to-end.md)
- _No campaigns recorded yet._
