# DR-04 — Appearance re-identification to survive occlusion and disambiguate near-identical targets

## Context (assume no prior knowledge)
UAV target-follow on a **Jetson Orin Nano 8 GB**. I track a single commanded target with SAM2
(memory-carry mask propagation) and periodically re-ground with a 2B VLM. A persistent failure
wall across many experiments: when two similar objects interact (two cars merge into one blend
box, a target passes behind an occluder and re-emerges, a target crosses another), my system
**loses identity**. I proved that size priors, motion priors, and colour priors are all
*identity-blind* — they cannot separate a two-car blend or re-pick the right car after a cross.
The only cue that helped was a mask-median re-grounding gate, and even that holds only ~75 % of
the time; a "chase the dominant blob" heuristic actively regressed (servos onto the wrong object).

I need a **lightweight appearance signature** to (a) re-identify *the same* target after occlusion
/ track loss and (b) disambiguate the commanded target from near-identical distractors — all
within the edge budget, co-resident with the VLM + SAM2.

## Research question
What are the best (2023–2026) **lightweight appearance re-identification / instance-embedding**
techniques for keeping a *single* commanded target's identity through occlusion, crossing, and
near-identical distractors in aerial video, deployable on an 8 GB Orin Nano co-resident with other
models?

## Sub-questions to cover
- Edge-deployable **ReID / appearance-embedding** backbones (OSNet, lightweight ReID, DINOv2/DINOv3
  patch features as instance descriptors) — dims, latency when quantized, discriminative power on
  near-identical vehicles.
- How modern **tracking-by-detection MOT** frameworks fuse appearance + motion for identity
  (e.g. BoT-SORT, Deep-OC-SORT, StrongSORT, and 2024–2026 successors) and which parts port to a
  single-target, memory-carry (SAM2) setting.
- **Occlusion / re-detection**: recovering the correct target after it is fully occluded — memory
  banks, appearance re-matching on re-emergence, long-term tracker practice (how SOTA long-term
  trackers re-acquire after loss).
- Distinguishing **near-identical** instances (two same-colour cars) — what appearance/geometry
  cues actually separate them when colour/size/motion do not; evidence on how hard this really is.
- Fusing an appearance gate with SAM2 mask propagation and a periodic VLM re-ground, and how to
  set an accept/reject threshold that is more reliable than the ~0.75 mask gate I have now.

## Constraints / priorities
- 8 GB Orin Nano, co-resident; the appearance model must be small (ideally <300 MB, few-ms/inference).
- Single-target identity preservation is the goal (not full multi-object association), but
  distractor rejection is essential.
- Aerial/oblique views, low resolution per object, moving camera.

## Explicitly out of scope (already ruled out)
- Size / motion / colour-only priors as the identity cue (all proven identity-blind here).
- "Chase the dominant blob" re-ground behaviour (regressed — servos onto the wrong object).

## Desired output
A ranked set of appearance-ReID options with edge cost and expected discriminative power on
near-identical aerial targets, a recommended fusion with SAM2 + periodic VLM re-ground, and a
principled accept/reject threshold design. Note honestly where the near-identical case is
genuinely unsolved. Citations throughout.
