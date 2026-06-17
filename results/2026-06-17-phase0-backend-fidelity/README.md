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
| **RQ-0.2** (parity) | How large is the HF↔GGUF fidelity gap on the *same* checkpoint and prompt? | report ΔIoU@0.25 (HF bf16 → GGUF F16 → Q8_0); reproduce the Part-I −23pp / −7pp split as a self-check | `eval/parity.py`, same RefCOCO val subset |
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

## 0b — GGUF parity self-check (pending)

Blocked on a local llama.cpp build at the pinned commit `57fe1f0` + an
`mmproj-SmolVLM-500M-Instruct-f16.gguf` (the Jetson copy is at
`/home/jfdg/models/mmproj-SmolVLM-500M-Instruct-f16.gguf`). `GGUFBackend` and
`eval/parity.py` are filled at 0b startup; the self-check is reproducing the Part-I
−23pp (F16) / −7pp (Q8_0) split on the `smolvlm_ft3` artifacts.

## 0c — Spine selection (pending)

Parity probe on SmolVLM-500M + one grounding-native candidate; pick by the numbers.
