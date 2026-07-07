# DR-03 — Binding an operator phrase to one of N warm tracks (the language selector)

## Context (assume no prior knowledge)
UAV target acquisition on a **Jetson Orin Nano 8 GB**. In my "warm-start" architecture, during the
idle pre-command window I already maintain a small set (~2–8) of **live tracked candidates** —
each a SAM2 mask/box with a coarse label, current at command time. When the operator finally says
a phrase ("the red car on the left", "the person near the boat"), I must **select** which existing
track it refers to — a *referring-expression matching over a handful of candidate crops*, not a
fresh full-frame grounding pass.

Today I re-run the 2B grounding VLM (Qwen2-VL-2B) cold on the whole frame, which is exactly the
latency/staleness I am trying to avoid. I want a lighter, more reliable **phrase → candidate**
matcher. An earlier experiment proved that collapsing candidates to prose ("left/center/right")
throws away the geometry and fails — so the matcher must operate over real image crops + boxes,
not a text index.

## Research question
What are the best (2023–2026) methods for **matching a natural-language referring expression to
one of a small set of candidate image regions** ("region-text retrieval" / referring-expression
comprehension as *selection over given proposals*), that are lightweight enough to run on an 8 GB
Orin Nano and robust to attributes (colour), spatial relations (left/near), and category?

## Sub-questions to cover
- **Region-text embedding** models usable as a similarity scorer over ~5 crops: CLIP / SigLIP /
  OpenCLIP variants, RegionCLIP, and their edge latency when quantized. Multiple-choice by cosine
  similarity vs a full grounding pass — accuracy/robustness trade-off.
- Using a small VLM as a **multiple-choice selector** ("which of these 5 crops is X?") vs
  open-ended grounding — is the multiple-choice framing more accurate and cheaper?
- Handling **spatial relations** ("leftmost", "near the boat") when candidates are separate crops
  that have lost global context — how to inject position/relation into the match.
- Robustness to distractors (two near-identical red cars) — how referring-expression selectors are
  evaluated on hard negatives; relevant benchmarks (RefCOCO/+/g, and any drone/aerial referring set).
- Calibration / abstention: detecting "none of these match" so the system can fall back to a cold
  grounding pass instead of confidently selecting the wrong track.

## Constraints / priorities
- Runs on 8 GB Orin Nano, co-resident with SAM2 (and ideally *replacing* a cold VLM pass, so it
  should be materially cheaper/faster than ~1.4 s + decode).
- Must consume real boxes/crops + a language phrase; geometry-preserving, not a prose index.

## Explicitly out of scope (already ruled out)
- Collapsing candidates to a text/prose scene description before matching (proven to fail — the
  3×3 "left/center/right" cell is not tight enough).

## Desired output
A comparison of 3–4 selector designs (region-text embedding similarity · VLM multiple-choice ·
hybrid) with edge cost, expected robustness on attributes/spatial-relations/distractors, an
abstention strategy, and the benchmarks I could evaluate each on. Citations throughout.
