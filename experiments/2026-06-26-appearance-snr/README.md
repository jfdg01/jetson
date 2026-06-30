# Appearance-SNR vs range — validating the T2 permanence assumption on real aerial pixels

**Status:** PRE-REGISTERED (not yet run). **Branch:** `v3/object-permanence`.
**Part:** III (object permanence). **Date registered:** 2026-06-25.
**venv:** `.venv-ft` (numpy + PIL). No GPU, no anchor, no Jetson — pure CPU eval.
**Independence:** orthogonal to the two latency follow-ons running now (terse re-LoRA,
ROI-crop sweep). Different axis (permanence, not speed), different hardware (no 3090,
no Orin), so it can run concurrently without contending for either.

---

## 1. Why this experiment exists (the honest gap in T2)

T2 (`experiments/2026-06-24-t2-permanence/`) reported **GATE PASS**, but with a fence
around it:

> ✅ GATE PASS — **within the separable regime (appearance SNR ≳ 1).**

The whole T2 result rests on a **synthetic scalar appearance descriptor**. From
`runners/sitl/reid_policy.py`:

> *"Pixels aren't rendered yet (T1 decision), so appearance is modelled as a
> per-instance scalar descriptor whose observation noise scales with crop size...
> That `snr` knob ties the mechanism directly to the T0d separability-vs-range
> frontier."*

The mechanism (store target descriptor at acquisition, match on it at re-acq, **refuse
to lock** when nothing matches) works in simulation — *but the `snr` knob is a free
parameter nobody measured*. The T2 table shows the result is a cliff, not a plateau:

| snr | success | id-switch | re-acq frames |
|----:|--------:|----------:|--------------:|
| ≥1.2 | 1.000 | 0 | 0.13 |
| 0.8  | 0.751 | 1 | 67.7 |

So the entire permanence chapter hinges on one unmeasured number: **what is the real
appearance SNR of an aerial target vs. a nearby same-class decoy, and at what crop size
(range) does it fall below ~1.0?** Above ~1, T2 holds and a cheap descriptor is enough.
Below ~1 at operating range, the synthetic PASS is optimistic and permanence needs a
stronger signal (learned embedding or VLM re-verification — constraint #2's hard case).

This experiment **measures that number on real aerial pixels** so the T2 gate can be
restated as "passes at the *measured* SNR" instead of "passes if SNR ≳ 1."

## 2. Data: VisDrone-MOT (not SOT)

SOT was the obvious candidate (IDEAS.md parked it for T1/T2) but it labels **only the
single target** and its attribute flags are **sequence-level** — there are no
same-class decoy boxes, which is exactly what an SNR-vs-decoy measurement needs.

**VisDrone-MOT** (`./VisDrone/MOT/`, local) is the right fit: per-frame multi-object
boxes with **track IDs** (permanence ground truth), **object category** (→ real
same-class decoys), and a per-frame **occlusion** flag (→ the re-acquisition moment).

Annotation format (one line per detection):
```
frame, target_id, x, y, w, h, score, category, truncation, occlusion
```
- `category`: 1=pedestrian 2=people 3=bicycle 4=car 5=van 6=truck 7=tricycle
  8=awning-tricycle 9=bus 10=motor 11=others (0=ignored, dropped).
- `occlusion`: 0=none, 1=partial(1–50%), 2=heavy(>50%).
- `truncation`: 0=none, 1=partial (out-of-view proxy).

Splits available locally: train 56, val 7, test-dev 17, test-challenge 16 sequences.
**Use `val` (7 seqs) for the headline** (small, fast, has GT); report `train` as a
larger-N confirmation. Pre-registering the split avoids cherry-picking.

## 3. RQs (pre-registered)

- **RQ1 — the number.** What is the appearance SNR between an aerial target track and
  its **nearest same-class decoy**, measured on real crops?
- **RQ2 — the curve.** How does SNR vary with **crop area** (range proxy)? At what crop
  area does SNR cross the T2-critical **~1.0**?
- **RQ3 — the verdict.** Across the SITL follow target's operating crop-size range
  (oracle_bbox target boxes are typically a few ×10²–10³ px²; AREA_REF=3000 px² in
  reid_policy is the pivot) — is real SNR **above or below 1.0**?
- **RQ4 — descriptor sufficiency (the lazy gate).** Does a stdlib HSV color histogram
  already separate target from decoy? If yes, the learned-embedding rung is YAGNI.

## 4. Method

For each MOT sequence, for each labeled target track `T` (category ≠ 0, ≥ `MIN_LEN`
visible frames):

1. **Reference descriptor.** Crop `T` on its **least-occluded** frames (occlusion=0),
   compute the appearance descriptor, average → `ref_T`.
2. **Intra-target distance** (signal floor): `d(crop(T_t), ref_T)` over other
   un-occluded frames of `T` — how much the *same* object drifts across time/scale.
3. **Decoy distance** (the gap to beat): per frame, the **nearest same-category** other
   track by center distance (the hardest decoy); `d(crop(D_t), ref_T)`.
4. **SNR** = `mean(decoy distance) / mean(intra-target distance)`. SNR ≫ 1 → decoy
   looks clearly different (re-ID easy); SNR ≈ 1 → indistinguishable (the T2 collapse
   regime).
5. **Bucket by crop area** of the target box (range proxy) to build the SNR-vs-area
   curve (RQ2).
6. **Occlusion slice.** Repeat the decoy distance specifically on frames straddling an
   occlusion event (occ 0→2→0) — that is the actual re-acquisition decision T2 makes.

**Descriptor (ladder, take the first rung that holds):**
- **Rung 1 — HSV color histogram**, 4×4×4 = 64 bins, L1-normalized, **Bhattacharyya
  distance**. numpy `histogramdd` + PIL crop/resize. No model, no GPU, fully
  reproducible. *Try this first (RQ4).*
- **Rung 2 — only if rung 1 is degenerate** (curve flat / SNR ≈ 1 everywhere *and*
  visibly-distinct objects are not separated): a tiny embedding. Escalate only on
  evidence, documented.

## 5. Metrics / outputs

- **Headline:** SNR-vs-crop-area table + the **critical area** where SNR crosses 1.0.
- **One-number verdict (RQ3):** at AREA_REF=3000 px², is real SNR `>1` or `<1`?
- **Feed-back:** drop the measured SNR(area) into `reid_policy.py`'s `_observe` knob and
  **re-run the existing T2 harness** → restate T2 as "PASS at measured SNR S" (or FAIL).
- **Occlusion-event SNR** vs. clear-frame SNR (does the decision get harder exactly when
  it matters?).

## 6. Gate / decision rule (pre-registered, so the result can't be rationalized after)

- **SNR ≳ 1.2 across operating range** → T2 mechanism **validated on real pixels**; the
  HSV histogram suffices; learned embedding is YAGNI (RQ4 = no). T2 PASS stands
  unconditionally; record the measured S.
- **SNR ~1 (0.8–1.2)** at operating range → T2 is **marginal**; permanence needs the
  refuse-to-lock + VLM re-verification path, not appearance alone. Honest amber.
- **SNR < 0.8** at operating range → appearance histogram **insufficient**; either
  escalate to rung-2 embedding or conclude (honest negative, thesis content) that aerial
  same-class re-ID at range is not solvable by cheap appearance and **must** route
  through the sparse VLM anchor — which loops back to why the latency levers matter.

Any outcome is a publishable result: it converts T2's assumed knob into a measured one.

## 7. Threats to validity (state up front)

- **Bhattacharyya on color only** ignores shape/texture — a deliberate floor, not the
  ceiling. If color fails, rung 2 is the answer, not a louder color histogram.
- **MOT ≠ SITL render** — VisDrone is real RGB aerial; the SITL loop is currently
  oracle/unrendered. This measures the *real-world* SNR the eventual rendered loop would
  face, which is the conservative (harder) number — appropriate for a gate.
- **Nearest-center decoy** may occasionally pick a partially-occluded decoy; mitigated by
  dropping occlusion=2 decoy frames from the mean (kept for the occlusion-slice only).

## 8. Deliverables (atomic commit when run)

- `score_appearance_snr.py` (this dir) — the scorer (HSV histogram, numpy+PIL).
- `results.json` + the SNR-vs-area table appended to this README under `## Results`.
- A row in root `RESULTS.md`; a `## Decisions` entry here (descriptor rung chosen, split,
  verdict); a `DECISIONS.md` entry only if the verdict changes the T2 gate status.
