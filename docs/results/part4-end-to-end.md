# RESULTS — Part IV · End-to-end workflow refinement (v4)

Index: [`../../RESULTS.md`](../../RESULTS.md) · Companion: [`../questions/`](../questions/) (research questions) · [`../decisions/`](../decisions/) (what was chosen & why).
Per-campaign detail lives in `experiments/<campaign>/README.md`. Append, never overwrite.

---

## Part IV — End-to-end workflow refinement (v4)

Goal: the two-tier follow loop passed T0–T4 in isolation, but the integrated NL→ground→track→fly pipeline does not hold up end-to-end. Part IV hardens it.

### 2026-06-30 — VLM backbone bake-off ([`experiments/2026-06-30-vlm-backbone-bakeoff/`](../../experiments/2026-06-30-vlm-backbone-bakeoff/README.md))

FT: LoRA r=16/α=32 bf16, vision frozen, eff. batch 16, lr swept {1e-4, 2e-4, 4e-4}, ≤3 epochs,
RefDrone well-posed (4101/439), RTX 3090. Deploy rows: Jetson Orin Nano 8 GB @ 15 W, llama.cpp
`57fe1f0` Q8_0 ngl=99. **Campaign early-stopped 2026-07-02** — decision determined before arms D /
E-legs-2-3 (see README Findings).

| Arm | best lr | path | parse | IoU@0.25 | mean IoU | wall/anchor | verdict |
|---|---|---|---|---|---|---|---|
| baseline Qwen2-VL-2B (deployed) | — | WF@1024 / ROI M=2.0@512 | 100% | 63.1% / 85.2% | 0.477 / — | 4400 / ≈2000 ms | **incumbent, kept** |
| A InternVL3-2B | 4e-4 | WF@1024 (HF, n=200) | 100% | 48.5% | 0.298 | N/A — GGUF export blocked @`57fe1f0` | eliminated |
| B Qwen2.5-VL-3B | 2e-4 | WF@1024 / ROI M=2.0@512 (Jetson Q8_0, n=439) | 100% | 53.1% / **33.0% (ROI collapse)** | 0.399 / 0.170 | 5990 / 2817 ms | eliminated |
| C PaliGemma2-3B@448 | 2e-4 | WF@448 (HF, n=200) | 100% | 56.0% | 0.391 | not measured (moot) | eliminated |
| E SmolVLM2-500M | 1e-4 (leg 1 only) | WF@512 (in-loop val) | 100% | **5.5% (capacity collapse)** | 0.038 | not deployed | eliminated |
| D Florence-2-large | — | — | — | cancelled un-run | — | — | cancelled |
