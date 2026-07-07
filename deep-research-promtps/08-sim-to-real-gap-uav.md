# DR-08 — Sim-to-real gap for a UAV vision-follow pipeline: what breaks off the bench, and how to de-risk it

## Context (assume no prior knowledge)
My thesis builds a natural-language → ground → track → follow pipeline for a UAV, running on a
**Jetson Orin Nano 8 GB**. Crucially, **the whole loop has only ever been validated in simulation
and on recorded video**: grounding/tracking on pre-recorded UAV123 clips (replay), and the follow
controller in ArduPilot **SITL** (software-in-the-loop). The closed loop has *never* run against
real, live VLM latency and real flight dynamics simultaneously — my SITL follow tests used a
near-instant oracle detector, and my perception tests used offline video. This is my biggest
thesis-defense exposure: reviewers will ask "does any of this survive contact with a real drone?"
I want to know, from the literature and real deployments, exactly *what breaks* crossing from
SITL+replay to real flight, and how to de-risk it before (or instead of) a full flight campaign.

## Research question
What does the literature and field-deployment experience (2022–2026) say about the **sim-to-real /
bench-to-flight gap for UAV vision-based target-following pipelines** — which effects dominate the
failure, and what hardware-in-the-loop and staged-validation practices most cheaply de-risk it?

## Sub-questions to cover
- **Image-domain gap in flight**: motion blur, rolling-shutter, vibration/jello, auto-exposure and
  dynamic range, compression artifacts, variable lighting — quantified effects on detection/
  grounding/tracking accuracy, and mitigations.
- **Latency & timing gap**: real end-to-end perception latency and jitter (vs an instant oracle),
  control-loop delay, and how latency destabilises a visual-servo follow loop; latency-compensation
  / prediction techniques for following a moving target.
- **HIL / staged validation** practice: hardware-in-the-loop with a real Jetson + real camera into
  SITL, log-replay-in-the-loop, tethered/handheld pre-flight tests, gimbal rigs — the cheap rungs
  between "SITL + replay" and "free flight," and what each actually catches.
- **Control-side sim-to-real** for ArduPilot/PX4 follow modes: known SITL-vs-real discrepancies
  (wind, GPS/EKF noise, actuator lag) for target-following/guided modes.
- Reported case studies of vision-follow UAV projects that crossed to real flight — what surprised
  them, ordered by severity.

## Constraints / priorities
- Focus on the **target-following** use case (track a moving ground target), not mapping/racing.
- Jetson-class onboard compute; small VLM + tracker in the loop.
- Emphasise *cheap* de-risking rungs a solo master's student can actually run.

## Desired output
A ranked list of the failure modes most likely to bite this pipeline in real flight (severity ×
likelihood), each with a mitigation and a **validation rung** that would expose it before a full
flight test, ending with a recommended staged HIL → tethered → free-flight validation ladder.
Citations / case studies throughout.
