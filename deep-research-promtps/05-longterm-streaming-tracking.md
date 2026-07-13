# DR-05 — Long-duration streaming carry: memory drift, loss, and re-detection over multi-second windows

## Context (assume no prior knowledge)
UAV target tracking on a **Jetson Orin Nano 8 GB**. I carry targets with **SAM2.1-hiera-tiny**
(TensorRT fp16 encoder, ~6 Hz co-resident with a 2B VLM): a box/mask prompt seeds SAM2's memory,
which then propagates per-frame. In my "warm-start" design this carry must run over the **entire
idle window before the operator commands** — potentially many seconds to minutes — for *several*
candidate tracks at once, so that each candidate is still correct and current when the command
lands. SAM2 was designed and benchmarked mostly for short video segments; I am asking it to hold
multiple tracks over long, unprompted windows with a moving aerial camera. I need to know its real
long-horizon failure modes and how to mitigate them.

## Research question
What is known (2024–2026) about the **long-duration robustness of memory-based / streaming video
segmentation and tracking** (SAM2 and its variants especially), and what memory-management and
re-detection strategies keep multiple tracks correct over long, moving-camera aerial windows on an
8 GB edge device?

## Sub-questions to cover
- SAM2 **long-video failure modes**: memory-bank growth and drift, error accumulation, behaviour
  under target disappearance/reappearance, and any published fixes (SAM2-Long, DAM4SAM/SAMURAI,
  streaming/online SAM2 variants, memory-management papers) — with measured effects.
- **Loss detection**: how to tell a track has drifted or died (mask-quality / IoU-stability /
  confidence signals) so it can be dropped or re-seeded rather than silently tracking background.
- **Re-detection after loss** in long-term single-object tracking (GlobalTrack, long-term VOT
  practice) and how it would compose with a VLM/detector re-seed here.
- **Multi-track memory cost** on 8 GB: how SAM2 memory scales with number of concurrent tracks and
  window length; practical caps and pruning strategies for a co-resident edge deployment.
- Edge-oriented streaming trackers positioned as SAM2 alternatives for long horizons — but note I
  already compared EdgeTAM and kept SAM2, so I want *long-horizon* evidence, not a generic swap.

## Constraints / priorities
- 8 GB Orin Nano, co-resident with a 2B VLM; several concurrent tracks; second-to-minute windows.
- Moving aerial camera, small targets, frequent partial occlusion.
- Prefer methods with measured long-video numbers and an ONNX/TensorRT or lightweight path.

## Explicitly out of scope (already ruled out)
- A straight swap to EdgeTAM as the tracker (already evaluated; SAM2 kept). Long-horizon
  *evidence* about any tracker is welcome; a generic "use X instead" is not.

## Desired output
A concrete list of SAM2 long-duration failure modes with mitigations (memory pruning, loss
detection, re-seed policy), a recommended **track-health + re-detection** loop I could implement
around SAM2, and an estimate of the per-track memory/compute cost for N concurrent tracks on 8 GB.
Citations throughout.
