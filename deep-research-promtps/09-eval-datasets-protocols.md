# DR-09 — Evaluation datasets and protocols for referring + anticipatory acquisition in aerial video

## Context (assume no prior knowledge)
My thesis evaluates a natural-language UAV target-acquisition system on a **Jetson Orin Nano**. My
current evaluation rests on two datasets: **RefDrone** (drone referring-expression grounding, used
for single-frame IoU@0.25) and **UAV123** (single-object aerial tracking, used for a wall-clock
"replay" where I inject a command at time t and score the resulting lock). The exposure: UAV123 is
**single-object** with generic (non-linguistic) targets, my replay runs are **n=1** per clip, and
my headline "warm-start" claim (keep salient objects tracked, then *select* on command) has **no
purpose-built benchmark** — I improvised a protocol (choose a prompt-arrival time t_p>0, run the
warm machinery over [0,t_p], score the lock at t_p). I need to know what better datasets and
evaluation protocols exist so the thesis eval is defensible.

## Research question
What datasets and evaluation protocols (2022–2026) best support evaluating **language-conditioned,
multi-target, temporally-aware target acquisition in aerial/drone video** — specifically for a
"warm-start / select-on-command" setting where a referring command arrives *mid-stream* — and how
should I design the metrics and statistics to make such a claim rigorous?

## Sub-questions to cover
- **Aerial referring / RMOT** datasets beyond RefDrone: referring multi-object tracking (Refer-KITTI
  and aerial analogues), AerialMind, VisDrone-derived referring sets, drone RSVG/visual-grounding
  datasets — coverage, licensing, and whether they support *temporal* + *linguistic* + *multi-target*
  evaluation together.
- **Protocols for command-at-time-t / anticipatory** evaluation: is there prior art on evaluating
  systems where the query arrives mid-video (online/streaming referring, "when does it lock" latency
  metrics)? How do people score acquisition *latency* + *correctness* jointly?
- **Metrics** for acquisition quality under motion: beyond IoU@0.25 — success/precision plots,
  time-to-lock, identity-preservation, and staleness-aware metrics; which are standard and defensible.
- **Statistical rigor** on small clip sets: my runs are near-deterministic n=1 — what variance
  sources exist (seed, sampling, clip selection bias) and how to report honestly (bootstrap over
  clips, per-category breakdown, effect sizes) for a thesis.
- Building a **small custom benchmark** if none fits: minimal defensible design (clip selection,
  annotation, command scripting) to test warm-start vs cold acquire fairly.

## Constraints / priorities
- Aerial / oblique UAV viewpoints; moving camera; small targets.
- Must support *language-conditioned* acquisition and, ideally, *multi-target* + *temporal* at once.
- License must permit academic thesis use (note NC / VisDrone-chain restrictions where relevant).

## Desired output
A ranked shortlist of datasets (modality · language? · multi-target? · temporal? · license · fit
for warm-start eval), a recommended **evaluation protocol + metric set** for command-mid-stream
acquisition, and a minimal design for a custom benchmark if the existing ones fall short. Citations
throughout.
