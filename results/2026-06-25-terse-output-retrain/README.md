# Terse-output re-LoRA: cut decode tokens to shrink anchor latency (Part II/III)

**Status:** 🔄 iterating. Iter-1 fully measured (HF + on-Orin). Iter-2 collapsed → root-caused
(EOS bug) → iter-2b re-running with the fix.
**Date opened:** 2026-06-25 · **Runs:** 2026-06-26 · **Branch:** `v3/object-permanence`.
**Phase:** Part II re-train of the deployed anchor; motivated by Part III latency budget.

## The core finding (read this first)

Qwen2-VL **tokenizes digits one-per-token** (`266` → `2`,`6`,`6`). So the decode-token cost of
a bbox is dominated by **digit count**, and the JSON `{"bbox": …}` scaffolding is a *minority*
of the tokens:

| target string (what the model emits) | decode tokens |
|---|---|
| `{"bbox": [266, 476, 346, 644]}` (JSON, 0–1000) | 23 |
| `[266, 476, 346, 644]` (bracketed, 0–1000) | 20 |
| `266 476 346 644` (bare, 0–1000) | 15 |
| `[27, 48, 35, 64]` (bracketed, **0–100**) | 13–16 |
| `27 48 35 64` (bare, **0–100**) | **11** |

Two levers, measured: **(a)** drop the JSON wrapper (−3 tok, but the model clings to brackets);
**(b)** halve the digits via 0–100 precision (−4 tok, and 0% of RefDrone-val boxes — incl. tiny
aerial, n=93 — drop below the 0.25 IoU gate under 0–100 rounding). Lever (b) is the bigger,
prior-independent win.

## Iteration log

### Iter-1 — bare ints, 0–1000 precision (`runs/v2/phase3-terse-1024`, manifest `…222753Z`)

One variable vs the 62.6% deploy: JSON → `x1 y1 x2 y2`. 3 epochs, all else identical.

| arm | parse | IoU@0.25 | decode tok | notes |
|---|---|---|---|---|
| HF val (n=200) | 91.0% | 60.5% | — | center_std 234, healthy |
| **Orin Q8_0 val (n=439)** | **99.3%** | **61.0%** | — | manifest `…232748Z` |
| Orin decode @512 (n=8) | 100% | — | **21** | wall **2114 ms** vs JSON 2265 |

- **Accuracy held** — Orin 61.0% vs JSON deploy 62.6% = **−1.6 pp** (within noise; mean_iou
  0.462 vs 0.468). The format change is ~free on accuracy.
- **But the token saving largely evaporated on-device.** The model **reverted to its pretrained
  bracketed prior** — on real images it emits `[266, 476, 346, 644]` (not the trained bare
  `266 476 346 644`), occasionally `(406,330,486,375)`. So it only shed the `{"bbox": …}`
  wrapper: **21 decode tok vs JSON's ~24** = −3 tok, decode 963 ms vs 1106 ms, **wall 2114 ms
  vs 2265 = −6.7%** — far short of the −35% the *target-string* token count predicted.
- **Parse-robustness risk realized**: e.g. `(316,25 361,173)` (a dropped comma) — the lenient
  exactly-4-ints parser silently accepted it. The risk the pre-registration flagged.

**Verdict:** bare-ints-at-0–1000 fights the model's prior and loses; net −7% latency for the
trouble. Not worth shipping alone. Motivates iter-2 (attack digits, not brackets).

### Iter-2 — bare ints, 0–100 precision (`…phase3-terse100-1024`, manifest `…014126Z`) — COLLAPSED

Changed precision to 0–100 (2-digit coords). **HF eval E3: parse 5.0%, IoU@0.25 3.5%.**
Diagnosis (raw outputs): the model emits the **correct** coords then **never stops** —
`27 48 34 65 65 65 65 …` to the 64-token cap (gt was `[27,48,34,65]` — first 4 exact!).

**Root cause (a real latent bug the bracketless format exposed):** the training collate appended
the raw target with **no `<|im_end|>`/EOS** (`grounding/train/trainer.py` `full_texts = t + tj`).
The model was never *supervised* to stop. JSON/bracketed targets only stopped by luck — Qwen's
prior emits `<|im_end|>` after a closed `}`/`]`; **bare ints give no such cue**, so it rambles.
Fix: append `processor.tokenizer.eos_token` to every target.

### Iter-2b — bare ints, 0–100, **+ EOS fix** (`…phase3-terse100eos-1024`) — RUNNING

Same as iter-2 with the EOS supervision fix. Target = `27 48 35 64<|im_end|>` ≈ 11 decode tok
if it holds. Tests the user's bracketless route *and* the precision lever together. Results +
on-Orin decode pending.

## Why this exists (context to start cold)

We were costing the **sub-1-sec anchor** lever (`IDEAS.md` §VLM speed). The measured
on-Orin anchor is **2.27 s** (15 W, 512 long-edge): prefill 1113 ms + decode 1106 ms.
Decode is ~24 output tokens @ 21.7 tok/s, and **almost all of it is JSON scaffolding**, not
information — the answer is 4 integers.

**Lever #1 = shorten what the model emits.** Current contract output (`grounding/contract.py:62`):

```
{"bbox": [x1, y1, x2, y2]}   ← coords are ALREADY integers 0–1000 (no decimals to trim)
```

Terse target (proposed):

```
123 456 234 567             ← 4 ints, no JSON → ~24 tok ⇒ ~10 tok
```

Estimated decode 1.1 s → ~0.6 s. **Estimate, not measured.** This alone reaches ~1.7 s
total, NOT sub-1 (prefill still dominates — that's a separate lever, ROI-crop).

**The catch that makes this a real experiment, not a one-line edit:** the deployed
Qwen2-VL-2B Q8_0 (Part II Phase-3 LoRA) learned to emit the long JSON byte-for-byte. The
trainer supervises exactly `json.dumps({"bbox": s.bbox})` and masks everything else
(`grounding/train/trainer.py:96`). So changing the prompt + `parse_bbox` saves **zero
tokens** by itself — the model keeps writing JSON. Real savings require:

> **re-LoRA (Phase 3) on the 3090 → re-export GGUF (Phase 4) → re-deploy on Orin.**

This breaks the byte-identical contract test (`tests/test_contract.py`) on purpose.

**Data decision (settled, don't re-litigate):** re-train uses **RefDrone/RefCOCO** (the
sets that produced 62.6%). VisDrone does NOT help here — no referring language, no class
labels (see `IDEAS.md` note; VisDrone-SOT is an eval-for-tracking idea, a different track).

## Research questions (pre-registered)

- **RQ1** — Does the terse format cut decode tokens as predicted (~24 → ~10) and decode
  wall-time (~1.1 s → ~0.6 s) on the Orin @ 15 W, 512 long-edge?
- **RQ2** — What is the **accuracy cost**? Re-LoRA'd terse model vs current JSON model on
  RefDrone IoU@0.25 (current deploy = 62.6%). Honest headline: "decode −X%, IoU ±Y pp."
- **RQ3** — Does the terse format change parse_rate / failure modes (e.g. model dropping a
  coordinate when there's no bracket to anchor on)?

## Method / controlled variables

Change **one variable**: the output format. Hold base model (Qwen2-VL-2B-Instruct), LoRA
config, data (RefDrone/RefCOCO), resolution (512), quant (Q8_0) identical to the current
deploy so the delta is attributable to the format.

Concrete edits (the diff to prepare):
1. `grounding/contract.py` — `GROUNDING_PROMPT` (ask for "four space-separated integers"
   instead of JSON) + `parse_bbox` (parse 4 ints, no brace/bracket anchor). Keep
   `normalize_bbox`/`iou`/`center_std` unchanged.
2. `grounding/train/trainer.py:96` — `target_json` → the terse string (rename or keep field).
3. `tests/test_contract.py` — update the byte-identical prompt lock + parser cases to the
   new format (this test is *meant* to break; re-pin it deliberately).
4. Re-run Phase 3 → Phase 4 through the `Makefile`; write a run manifest as usual.

**Risk to watch:** a terse format with no delimiters/brackets gives the parser nothing to
anchor on — a dropped/extra integer becomes silent corruption instead of a parse-fail. Pick
a format the parser can validate (exactly 4 ints, range-check 0–1000); prefer a small,
robust delimiter over raw whitespace if parse_rate drops.

## Gate / decision

- **Keep terse** only if decode drops materially AND IoU@0.25 stays within an acceptable
  band of 62.6% (define the band before running — e.g. ≥ −2 pp). Otherwise revert; document
  the negative ("saved Z tokens, cost W pp — not worth it") — that's thesis content either way.
- Remember: this gets the anchor to ~1.7 s, not sub-1. Sub-1 needs the prefill/ROI lever
  too (`IDEAS.md` lever #2) — but that one collides with re-acquisition (can't re-find an
  object outside the ROI). Decide separately.

## Don't forget

- Switch to `v3/object-permanence` before doing work (currently `main`).
- Same gate rule: nothing ships without `results/` + `RESULTS.md` + `DECISIONS.md` in the
  same turn; log the format change in `DECISIONS.md` (Part II) with the accuracy tradeoff.
- All GPU/export work under `.venv-ft` via the `Makefile`. llama.cpp stays pinned.
