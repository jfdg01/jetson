# DR-10 — Related-work and novelty framing for "anticipatory grounding / always-on-then-select"

## Context (assume no prior knowledge)
My master's thesis contribution is a reframe of natural-language target acquisition for UAVs.
The standard framing assumes the operator's command arrives cold, at frame 0, and triggers a
blocking perception pass — which, on a moving target with a slow edge VLM (~4.5 s), lands *stale*.
My reframe ("warm-start" / "anticipatory grounding"): the command actually arrives **mid-flight**,
so the pre-command video stream is **free compute** — continuously track all salient objects during
the idle window, then at command time **select** the matching track instead of acquiring cold. I
showed this removes a delivery-lag failure (warm 21/25 vs cold 5/25 on aerial clips). For the
thesis I need to **position this against prior art** and state honestly what is and isn't novel —
the mechanism feels intuitive, so I must find who has done adjacent things and frame my
contribution precisely.

## Research question
What is the prior art (across robotics, HRI, perception, and video understanding, ~2015–2026) for
**anticipatory / pre-emptive / always-on perception that is later resolved by a command** — i.e.
"track everything continuously, then select on the operator's referring expression" — and how
should I frame the novelty and limits of my warm-start acquisition contribution against it?

## Sub-questions to cover
- **Proactive / anticipatory perception & robotics**: pre-emptive attention, anticipatory tracking,
  "perceive before you're asked," predictive perception for latency hiding — closest named paradigms
  and their claims.
- **Human-robot / operator interaction latency**: work that treats *command latency* or
  *think-time* as a resource, pre-computation during idle operator time, mixed-initiative
  select-from-candidates interfaces.
- **Open-vocabulary "track everything then query"** systems: track-anything / segment-anything-in-video
  pipelines, open-world tracking, and referring-video systems where a query selects among maintained
  tracks — how they differ from acquiring on demand.
- **Streaming / online referring** and query-at-time-t formulations in video understanding — anyone
  who explicitly models the query arriving mid-stream.
- Honest **novelty delta**: given the above, what precisely is new here (edge budget? the specific
  select-on-warm-track mechanism? the staleness/delivery-lag analysis showing the win is lag-removal
  not motion-compensation?) and what is prior art I should cite rather than claim.

## Constraints / priorities
- Goal is a defensible **related-work section + a crisp novelty statement**, not a system.
- Span robotics/HRI + CV/video-understanding; surface the *closest* prior art even if from another
  domain, so I don't overclaim.
- Note where my contribution is "engineering integration on edge" vs "conceptually new."

## Desired output
An organised related-work map (paradigm → key papers → how mine differs), a candidate one-paragraph
**novelty statement** grounded in that map, and an explicit list of "must-cite so I don't overclaim"
works. Citations throughout.
