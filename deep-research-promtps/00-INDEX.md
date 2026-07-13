# Deep-research prompts — Jetson edge-VLM UAV grounding thesis

Ten self-contained prompts for an external deep-research agent (no repo context assumed).
Each targets a weak point / open thread in the repo and asks: *what information would guide
improving this aspect?* Grouped by where the project is actually stuck.

Weighted toward the current live binder (Part V warm-start seed recall), then the
thesis-defense soft spots (sim-to-real, eval validity, novelty framing).

| # | File | Weak point it attacks |
|---|---|---|
| 01 | `01-warmstart-candidate-proposal.md` | Warm-start seed is now **detection-bound** — need high-recall always-on candidate proposal on 8 GB co-resident with the VLM |
| 02 | `02-small-target-detection-aerial.md` | Seed misses **small/deformable** targets (person, distant car) — small-object recall in aerial video |
| 03 | `03-phrase-to-track-selector.md` | The NL **selector**: bind an operator phrase to one of ~5 warm tracks without a cold full-frame grounding pass |
| 04 | `04-reid-identity-disambiguation.md` | Identity wall — size/motion/colour are identity-blind; disambiguate near-identical targets + survive occlusion |
| 05 | `05-longterm-streaming-tracking.md` | Multi-second idle-window carry — SAM2 memory drift, loss, re-detection over long windows |
| 06 | `06-8gb-coresidency-engineering.md` | Fitting a **third** model on an 8 GB Orin Nano co-resident — memory/thermal/TensorRT budget |
| 07 | `07-small-grounding-vlm-frontier.md` | Model frontier refresh — is Q8_0 Qwen2-VL-2B still best; INT4/AWQ effect on **box** accuracy |
| 08 | `08-sim-to-real-gap-uav.md` | Whole loop is SITL + replay, never flown — what breaks in real flight; HIL practice |
| 09 | `09-eval-datasets-protocols.md` | Eval rests on UAV123/RefDrone (n=1, single-object) — datasets/protocols for referring + anticipatory acquisition |
| 10 | `10-anticipatory-grounding-related-work.md` | Novelty framing — prior art on anticipatory / always-on-then-select perception for the thesis' related-work |
| 11 | `11-closed-decision-readjudication.md` | **Debt audit** — was the early-stopped VLM bake-off a fair adjudication or premature closure of competitor arms |

## Note on closed-decision debt (added after review)

01–10 fence off the closed dead-ends (`DECISIONS.md`) to save research runs. On review, only
**11** is genuinely web-researchable debt (the bake-off). The two *most* load-bearing thin calls
are **internal re-analysis, not deep research**, and are NOT covered by any prompt here:

- **P5.2 "win = delivery-lag, not motion-comp"** (n=1, ρ=−0.06, 2 structural clips in denom) —
  redirects Part V phase 2. Needs: bootstrap CI over clips, check the speed axis wasn't
  range-restricted, verify the ~135-frame delivery-lag causal story.
- **"Carry perfect once seeded"** (E18 oracle, n=6) — the whole warm-start premise. Needs: oracle
  expansion beyond 6 clips + longer idle windows (SAM2 long-horizon lit = prompt 05).

Pay these down with an internal re-run, not a research prompt.
