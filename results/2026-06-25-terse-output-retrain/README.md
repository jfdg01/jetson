# Terse-output re-LoRA: cut decode tokens to shrink anchor latency (Part II/III)

**Status:** ✅ trained + HF-evaluated (2026-06-26). On-Orin decode wall-time (RQ1 device leg) still TODO.
**Date opened:** 2026-06-25 · **Run:** 2026-06-26 · **Branch:** `v3/object-permanence`.
**Phase:** Part II re-train of the deployed anchor; motivated by Part III latency budget.

## Results (2026-06-26)

Re-LoRA on the terse format, **one variable changed** (output format); everything else held
identical to the 62.6% deploy run (Qwen2-VL-2B, RefDrone well-posed 4101/439, `--image-size
1024`, lr 2e-4, 3 epochs, bf16). Merged checkpoint `runs/v2/phase3-terse-1024/`, manifest
`runs/20260625T222753Z`. Log: `logs/train.log`.

| epoch | parse_rate | IoU@0.25 | mean_iou | center_std |
|---|---|---|---|---|
| 1 | 62.0% | 40.0% | 0.484 | 239 |
| 2 | 83.5% | 56.0% | 0.518 | 237 |
| **3** | **91.0%** | **60.5%** | 0.505 | 234 |

vs JSON Phase-3 HF baseline (`results/2026-06-17-phase3-train`): IoU@0.25 **59.5%**, parse **100%**.

- **RQ2 (accuracy) — PASS.** Terse **60.5%** vs JSON **59.5%** = **+1.0 pp** (within noise).
  The format change costs ~nothing in IoU; center_std 234 healthy (no collapse). Gate ≥−2pp cleared.
- **RQ3 (parse robustness) — measurable cost.** parse_rate **91.0%** vs JSON **100%** = **−9 pp**.
  The model takes all 3 epochs to learn the delimiter-free format (parse 62→83.5→91%); 9% of
  outputs still don't yield exactly-4 ints. This is the price of no brackets to anchor on — but
  the exactly-4 guard turns those into honest parse-fails, not silent corruption (RQ3 risk averted).
- **RQ1 (decode tokens) — premise confirmed locally, device leg TODO.** Qwen2-VL tokenizer:
  JSON target = **23 tok**, terse = **15 tok** → **−8 tok (−35%)**. The saving is *exactly* the
  8 JSON-scaffolding tokens (`{"bbox": [ … ] }`); the 4 numbers + spaces are irreducible. Smaller
  than the pre-reg ~24→~10 guess. At the measured 21.7 tok/s that's ~1.06s → ~0.69s decode
  (~0.37s off the 2.27s anchor ⇒ ~1.9s, **−16% total latency**). Actual on-Orin Q8_0 decode not
  yet measured — needs Phase-4 GGUF export + re-deploy.

**Decision:** provisional **KEEP** — accuracy free (+1pp), decode −35% tokens; pending on-device
confirmation. The −9pp parse_rate is the honest cost to log. See `DECISIONS.md` (Part III).

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
