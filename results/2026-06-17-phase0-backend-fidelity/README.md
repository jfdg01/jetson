# Phase 0 — Backend-fidelity harness

**Part II (v2) · branch `v2/principled-rebuild` · started 2026-06-17**

The first gated phase of the v2 rebuild. v2 is designed *backwards from deployment*
and *de-risks cheaply before spending GPU*: before any training, stand up a
**backend-agnostic eval spine** (HF / GGUF / Jetson behind one interface, all
importing the shared `grounding.contract`) and **measure the deployment-fidelity
gap as a known quantity** rather than discovering it after training (the Part-I
failure: HF bf16 85% → GGUF F16 62% (−23pp) → Q8_0 55% (−7pp), found only post-hoc).

This phase also settles the **model-spine question by data, not opinion**: run the
same parity probe on the incumbent SmolVLM-500M *and* one grounding-native candidate
and let the numbers pick the spine.

## Pre-registered research questions

| RQ | Question | Pass / metric | Source |
|---|---|---|---|
| **RQ-0.1** (anchor) | Does the v2 contract path (refcoco loader + `HFBackend` + `harness`, all via `contract.py`) reproduce the validated Part-I in-domain number? | IoU@0.25 within sampling noise of the Part-I Stage-3 reference **82.5%** (n=200); parse_rate ≥ 90%; `center_std` non-degenerate (≫ 0) | `python -m grounding.eval.run --backend hf` on `smolvlm_ft3`, seed-42 RefCOCO val |
| **RQ-0.2** (parity) ✅ | How large is the HF↔GGUF fidelity gap on the *same* checkpoint and prompt? | **PASS** — runtime gap −16pp ≫ quant gap −2pp; Part-I structure (runtime ≫ quant) reproduced | `eval/parity.py`, same RefCOCO val subset |
| **RQ-0.3** (spine) | Which model spine should v2 train on? | spine chosen *by the parity numbers* (in-domain IoU **and** fidelity gap), not by opinion | parity probe on SmolVLM-500M + one grounding-native candidate |

## Controlled variables

- **Eval set:** RefCOCO `validation`, seed-42 deterministic shuffle, first N — the
  *same* subset construction as the Part-I Stage-3 trainer (`load_refcoco` lifts the
  flatten + shuffle + cap behaviour verbatim), so the anchor is directly comparable.
- **Prompt / parser / metric:** the verbatim `grounding.contract` (single source of
  truth) — identical across every backend by construction.
- **Inference path:** PIL load → long-edge resize to `IMAGE_SIZE=512` → `GROUNDING_PROMPT.format`
  → chat template → greedy decode (`do_sample=False`, `max_new_tokens=64`) → decode
  new tokens only. Lifted verbatim from the validated `run_stage3_finetune.evaluate()`.
- **Metrics:** IoU@0.25 pass-rate (over all n; unparseable = miss), mean IoU (over
  parsed), parse_rate, `center_std` (mode-collapse sentinel).

## Provenance

Every run emits a manifest under `runs/<id>/` (git SHA + dirty flag, pinned
llama.cpp commit `57fe1f0`, lockfile sha256, full config, contract metrics) — see
`DECISIONS.md` (Part II, 2026-06-17 toolchain entry).

---

## 0a/0.1 — HF anchor self-check ✅ PASS (2026-06-17)

**Goal:** prove the v2 contract path reproduces the Part-I in-domain number *before*
any cross-backend comparison — i.e. the rebuild's eval spine measures the same thing
the validated Part-I trainer did.

**Command** (`.venv-ft`, local RTX 3090):

```bash
source .venv-ft/bin/activate
python -m grounding.eval.run --backend hf --model ./smolvlm_ft3 --n 100 \
  --note "Phase-0 harness self-check: reproduce Part-I in-domain IoU on smolvlm_ft3"
```

**Configuration:** backend HF (`AutoModelForImageTextToText`, bf16, cuda); checkpoint
`smolvlm_ft3` (the Part-I Stage-3 G2-PASS merged RefCOCO checkpoint); RefCOCO
validation, seed-42, n=100; greedy decode.

**Result:**

| Metric | Value | Part-I Stage-3 reference | Verdict |
|---|---|---|---|
| **IoU@0.25 pass-rate** | **85.0%** | 82.5% (n=200) | ✅ within sampling noise |
| parse_rate | 100.0% | — (≥ 90% bar) | ✅ |
| mean IoU (parsed) | 0.567 | — | — |
| `center_std` | 187.8 | ~211 (Stage 3/4 healthy) | ✅ non-degenerate |

**Manifest:** `runs/20260617T115913Z/` (git SHA `3a3352c`, dirty; llama.cpp `57fe1f0`).

**Reading.** 85.0% (n=100) vs the Part-I 82.5% (n=200) is well within sampling
spread for a binomial at this n — the v2 contract path (the new `refcoco` loader,
`HFBackend`, and `harness`, all importing `contract.py`) reproduces the validated
Part-I path. parse_rate 100% and `center_std` 187.8 confirm the harness reads
healthy, input-dependent predictions (not a parser artefact, not collapse). The HF
**fidelity reference** is now established; every other backend (GGUF, Jetson) will be
reported as a delta from this number.

**Gate status:** RQ-0.1 green. Proceed to 0b (GGUF backend + `eval/parity.py`,
reproduce the HF↔GGUF gap).

## 0b/0.2 — GGUF parity self-check ✅ PASS (2026-06-17)

**Goal:** reproduce, on the *same* `smolvlm_ft3` checkpoint and the *same* seed-42
RefCOCO val subset, the Part-I deployment-fidelity finding — that exporting the HF
skill to GGUF loses accuracy, and that the **runtime/preprocessing** loss (HF →
GGUF-F16, the llama.cpp Idefics3 image-path divergence) **dominates** the
**quantization** loss (F16 → Q8_0). This is the instrument the whole phase exists to
calibrate before it is used to pick the v2 spine (0c).

**Build (this session):** CPU-only llama.cpp at the pinned commit `57fe1f0`
(`-DGGML_CUDA=OFF -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release`) → `llama-server` +
`llama-mtmd-cli`; the multimodal projector `mmproj-SmolVLM-500M-Instruct-f16.gguf`
`scp`'d from the Jetson (`/home/jfdg/models/`). CPU is sound here because the gap is
an *image-preprocessing* divergence, not a compute one — it measures identically on
CPU and GPU (see `DECISIONS.md`, Part II, 2026-06-17 CPU-build entry).

**Commands** (`.venv-ft`; `GGUFBackend` boots a local CPU `llama-server` per run):

```bash
source .venv-ft/bin/activate
python -m grounding.eval.run --backend gguf --model ./smolvlm_ft3_f16.gguf \
  --mmproj ./mmproj-SmolVLM-500M-Instruct-f16.gguf --n 100 --ngl 0
python -m grounding.eval.run --backend gguf --model ./smolvlm_ft3_q8_0.gguf \
  --mmproj ./mmproj-SmolVLM-500M-Instruct-f16.gguf --n 100 --ngl 0
python -m grounding.eval.parity --checkpoint smolvlm_ft3 \
  --hf runs/20260617T115913Z --f16 runs/20260617T121539Z --q8 runs/20260617T121756Z
```

**Configuration:** identical resized pixels across arms (PIL load → 512 long-edge
`_resize_keep_aspect` → **lossless PNG** → base64 to the OpenAI `/v1/chat/completions`
endpoint), verbatim `GROUNDING_PROMPT`, `max_tokens=64`, `cache_prompt=False`.
**Greedy** (`temperature=0`) — a deliberate small departure from the Part-I GGUF arm's
server-default sampling, for harness determinism; the gap is preprocessing-dominated so
this does not move the conclusion (documented in `backends.py`).

**Result (parity table):**

| Backend | n | IoU@0.25 | mean IoU | parse_rate | center_std |
|---|---|---|---|---|---|
| HF bf16 (reference) | 100 | **85.0%** | 0.567 | 100.0% | 187.8 |
| GGUF F16 | 100 | **69.0%** | 0.393 | 100.0% | 149.7 |
| GGUF Q8_0 | 100 | **67.0%** | 0.389 | 100.0% | 148.0 |

- **Runtime/preprocessing gap (HF → GGUF-F16): −16.0 pp**
- **Quantization gap (GGUF-F16 → Q8_0): −2.0 pp**

**Manifests:** F16 `runs/20260617T121539Z/`, Q8_0 `runs/20260617T121756Z/`
(both git SHA `32ec67a`, dirty; llama.cpp `57fe1f0`).

**Reading.** The **qualitative Part-I finding reproduces cleanly**: the GGUF export
costs real accuracy, and the runtime/preprocessing loss (−16pp) **dominates** the
quant loss (−2pp) by 8×. This is the binding v2 constraint confirmed on independent
machinery (local CPU build, v2 contract path), so the harness is trusted to attribute
gaps in 0c.

The **magnitudes are smaller** than Part-I's −23pp / −7pp split. Two known,
non-confounding causes: (1) **greedy vs sampled decode** — the v2 arms are
deterministic, the Part-I GGUF arm used server-default sampling; (2) **n=100 vs n=200**
— binomial spread at this n is several points. The direction, the dominance ordering,
and the order of magnitude all match; the self-check is about *reproducing the
structure of the gap*, which it does. (We do **not** re-fit the exact −23pp number;
that was measured under different decode settings and is not the claim under test.)
`center_std` stays healthy (148–188) and parse_rate 100% across all three arms — no
collapse, no parser artefact introduced by the GGUF path.

**Gate status:** RQ-0.2 green — fidelity gap quantified and attributed
(runtime ≫ quant). Proceed to 0c (spine selection by the parity numbers).

## 0c — Spine selection (pending)

Parity probe on SmolVLM-500M + one grounding-native candidate; pick by the numbers.

## 0c — Spine selection (pending)

Parity probe on SmolVLM-500M + one grounding-native candidate; pick by the numbers.
