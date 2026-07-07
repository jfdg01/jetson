# DR-02 — Small / deformable-target recall in aerial video on edge

## Context (assume no prior knowledge)
I ground natural-language target descriptions in UAV video on a **Jetson Orin Nano 8 GB** (15 W)
and carry the target with SAM2. A 2B VLM (Qwen2-VL-2B, Q8_0) does the grounding; a key trick is
**ROI cropping**: cropping the region and LANCZOS-upscaling it to 512 px turns a downscaled small
target into a legible one — this alone lifted grounding IoU@0.25 from 62.6 % to 85.2 %. The
mechanism is a hard *resolution ceiling* of the small VLM: it is limited by *where* the box is at
low pixel counts, not by texture (learned super-resolution was tested and lost to free bicubic).

**The concrete failure:** in my warm-start experiments, the idle-window proposer *misses* small
or deformable targets outright — a distant car, a person, a wakeboarder — so no candidate box is
ever created for them. On the clips where a target is small at the moment the operator's command
arrives, both the proposer and the grounding VLM under-recall. This is the dominant remaining
error mode ("detection-bound").

## Research question
What techniques (2023–2026) most improve **recall of small and deformable targets in aerial /
drone video** under a strict edge compute budget (Jetson Orin Nano 8 GB, few Hz, co-resident with
other models) — spanning tiling/slicing inference, resolution strategies, small-object-specialised
architectures, and temporal aggregation?

## Sub-questions to cover
- **Slicing / tiling inference** (e.g. SAHI and successors): measured accuracy gain vs latency
  cost on aerial small objects; is it viable at a few Hz on Orin-class HW?
- Resolution ceilings of small VLMs / detectors — what input-resolution and patch strategies the
  small-object-detection literature recommends, and how that squares with my ROI-crop finding.
- Small-object-specialised detectors and aerial benchmarks (VisDrone, DOTA, UAVDT): which
  architectures lead on *small* AP and which are edge-deployable.
- **Temporal** recall: using motion / multi-frame accumulation over the idle window to surface a
  target that is invisible in any single frame (track-before-detect, small-target motion cues).
- Deformable / articulated targets (person, wakeboarder) specifically — what helps beyond generic
  small-object methods.

## Constraints / priorities
- Must fit an 8 GB Orin Nano co-resident with a 2B VLM + SAM2-tiny; few-Hz streaming.
- Recall of the target existing *at all* as a candidate matters more than tight boxes (a
  downstream tracker + VLM refine the box).
- Aerial/oblique viewpoints, moving camera, targets from ~10 px to large.

## Explicitly out of scope (already ruled out)
- Learned single-image super-resolution of the crop (Swin2SR tested and rejected).
- Any method requiring a second large (>1 B) always-on model — no memory headroom.

## Desired output
Prioritised techniques with expected small-object recall gain vs edge cost, at least one that
exploits the **idle-window temporal signal** (not just single-frame), and pointers to aerial
small-object benchmarks/leaderboards I can use to sanity-check candidates. Citations throughout.
