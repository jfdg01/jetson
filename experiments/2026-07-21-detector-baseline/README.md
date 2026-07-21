# R-13 — the missing detector baseline: OWLv2 vs the 2B VLM, both on the Orin

**Status:** PRE-REGISTERED, not yet run · **Opened:** 2026-07-21T20:05Z · **Branch:** `main`
**Part:** III (it re-examines the premise behind the whole grounding stack) · **Task:** R-13
**Machine:** Jetson Orin Nano 8 GB, 15 W + `jetson_clocks`, both models.

## Why this exists (context to start cold)

The thesis premise is that a 2B vision-language model is the right tool for referring-expression
grounding on a 15 W board. **The repo never shows it beats the cheap alternative at that task.**
A repo-wide search for YOLO / OWLv2 / OWL-ViT / GroundingDINO across every `.py` and `.json`
returns nothing; the names appear only in `SOURCES.md`, `archive/` and prose.

The fork was opened and then closed without being run.
`experiments/2026-06-14-vlm-feasibility/README.md:7` states the choice as "end-to-end VLM vs.
decomposed (YOLO grounding + LLM intent)" and line 188 closes it **on latency grounds alone**,
with no measured detector arm. CLIP proposal scoring was, in that campaign's own words,
"falsified at design time" — rejected without being run.

This is the first question an external examiner asks, and either answer is content: the
architecture is justified, or the thesis becomes "when is a VLM worth its cost", which is a
better thesis than the one currently written.

**OWLv2, not YOLOv8n.** The task is *referring-expression* grounding — "the white van next to
the roundabout" — not fixed-class detection. A closed-vocabulary detector cannot accept the
input at all, so beating one proves nothing. OWLv2 (`google/owlv2-base-patch16-ensemble`) takes
free text, is open-vocabulary, and is roughly an order of magnitude smaller than the deployed
VLM. It is the strongest cheap alternative, which is the only kind worth measuring against.

## The comparison, and the trap in it

The naive experiment — feed OWLv2 the whole referring expression, take its best box — is rigged.
OWLv2 scores text against *object appearance*; it has no mechanism for "the left one" or "next
to the roundabout". It will fail on spatial and relational phrases by construction, and reporting
that as "the VLM wins" would be the strawman this campaign exists to avoid.

So the detector gets three arms, ordered from most to least charitable, and the gap **between**
them is the real result:

| arm | text given to OWLv2 | what a failure here means |
|---|---|---|
| **D-full** | the full referring expression | the honest end-to-end baseline |
| **D-head** | the head noun phrase only (`"the white van next to the roundabout"` → `"van"`) | the detector cannot even localise the object *class* |
| **D-oracle** | head noun phrase, then the **best of its top-k boxes scored against GT** | there is no selection rule that could have rescued it |

`D-oracle` is deliberately unwinnable-by-the-VLM: it is an upper bound that uses the ground
truth to pick among the detector's proposals, so it cannot be reported as a system. Its only job
is to split the failure into **"could not find it"** (D-oracle low) versus **"found it, could not
tell which one the phrase meant"** (D-oracle high, D-full low). If the split lands on the second,
the honest conclusion is not "OWLv2 is worse" but "the decomposed architecture needs a selection
stage the 2026-06-14 campaign never costed" — which is a different, and more interesting, thesis
sentence than the one currently in print.

The VLM comparator is **not re-run**: it is arm A of `../2026-07-21-roi-ondevice/`, the same 439
RefDrone val samples, on the same board, at the deployed quantisation, measured on 2026-07-21.
Same items, same metric, same machine. That campaign must land first.

## Design

- **Dataset:** RefDrone val well-posed, n=439 over 316 unique images — the same list
  `load_refdrone("val")` returns, in the same order, so the arms are paired item-by-item.
- **Metric:** the project contract, unchanged — IoU@0.25 pass rate, mean IoU over hits,
  `center_std` as the mode-collapse sentinel. `grounding/contract.py` is the single scoring path
  for every number in the thesis and this one is no exception.
- **Head-noun extraction (D-head):** deterministic and dumb on purpose — strip leading articles
  and trailing prepositional phrases (`" next to "`, `" on "`, `" in "`, `" behind "`, ...), keep
  the last noun of the remaining chunk. It is committed in the runner and its output is dumped
  per item so the extraction can be audited rather than trusted. **No LLM is used to extract it**;
  that would smuggle the expensive model back into the cheap arm.
- **Latency:** per-item wall, on-device, `torch.cuda.synchronize()` around the forward pass, at
  15 W with `jetson_clocks`, reported as a median with the 439-sample distribution kept.
  Model load time is excluded and reported separately.
- **Co-residency is not tested here.** OWLv2 and the VLM are measured in separate processes; the
  8 GB board cannot hold both plus SAM2, and pretending otherwise is the exact composite-metric
  defect R-10 was written to catch. What R-13 answers is per-task quality and cost, not whether
  a decomposed stack fits — that is R-16's territory.

## Research questions (pre-registered)

- **RQ-R13.1 (primary):** on RefDrone val, on the Orin, does the deployed Qwen2-VL-2B Q8_0 beat
  OWLv2-base on referring-expression grounding at IoU@0.25? **Test:** exact McNemar on the paired
  discordants (VLM vs D-full), deflated to `n_effective` = 316 unique images.
- **RQ-R13.2 (the decomposition):** how does OWLv2 split across D-full / D-head / D-oracle? A
  large D-oracle − D-full gap means the detector finds the object and cannot pick it; a low
  D-oracle means it does not find it at all.
- **RQ-R13.3 (cost):** what does the accuracy buy or cost in on-device latency and peak memory?
  The 2026-06-14 campaign closed this fork on latency without measuring it; this measures it.

## Estimates (pre-registered — record divergence)

| quantity | estimate | basis |
|---|---|---|
| VLM (comparator, arm A of R-14) | ~63% | published on-device figure, 63.1% n=439 |
| D-full IoU@0.25 | 15-35% | OWLv2 has no relational mechanism; RefDrone captions are heavily relational |
| D-head IoU@0.25 | 30-50% | class-level localisation of small aerial objects is the hard part |
| D-oracle (top-k=10) | 55-75% | if the object is anywhere in the proposals, this finds it |
| OWLv2 latency (Orin, 15 W) | 0.4-1.2 s/frame | ~150M params at 960x960; guess, not a measurement, and the widest interval here |
| peak host memory | 2.5-4 GB | fp16 on an 8 GB unified board |
| runtime | 439 x 3 arms, ~1.5 h | dominated by the forward passes |

**Prediction worth writing down because it may be wrong:** D-oracle lands high and D-full lands
low, i.e. the detector is a competent *proposer* and a hopeless *selector*. If instead D-oracle
is also low, the premise question is settled cleanly in the VLM's favour and this campaign is
short. The estimate most likely to be embarrassing is the latency one: nothing in this repo has
run a ViT-based detector on this board.

## Install log (record every install, per CLAUDE.md)

The Jetson has torch 2.8.0 + CUDA in `~/sam2-bench/.venv` (the JetPack aarch64 wheel — do **not**
let a package manager replace it) and no `transformers`, no `pip` in that venv. Plan:

```bash
# uv, into the existing venv, so the JetPack torch wheel is never touched
ssh jetson 'curl -LsSf https://astral.sh/uv/install.sh | sh'
ssh jetson '~/.local/bin/uv pip install --python ~/sam2-bench/.venv/bin/python transformers'
ssh jetson '~/sam2-bench/.venv/bin/python -c "import torch, transformers; print(torch.__version__, torch.cuda.is_available(), transformers.__version__)"'
```

Weights (~600 MB) are fetched once to the Jetson's HF cache; the exact revision hash goes in
this section when the run happens.

## Commands

```bash
ssh jetson 'sudo nvpmodel -m 0 && sudo jetson_clocks'
# (to be written) experiments/2026-07-21-detector-baseline/run_r13.py, driven over ssh
```

## Results (TBD)

| arm | k | n | IoU@0.25 | mean IoU | center_std | latency ms (median) |
|---|---|---|---|---|---|---|
| VLM Q8_0 full-frame @1024 (from R-14 arm A) | | 439 | | | | |
| D-full (OWLv2, full expression) | | 439 | | | | |
| D-head (OWLv2, head noun) | | 439 | | | | |
| D-oracle (OWLv2, best of top-k vs GT) | | 439 | | | | |

**Paired VLM vs D-full (TBD):** b = , c = , n_effective = 316, McNemar p = .

**RQ-R13.1:** TBD · **RQ-R13.2:** TBD · **RQ-R13.3:** TBD

## Proof deliverables (TBD)

Planned under `proof/`:

1. `arms-bar.png` — the four arms side by side with Wilson intervals on n_effective=316, not 439.
2. `oracle-gap.png` — D-full vs D-oracle per item, which is the "proposer not selector" claim in
   one picture.
3. `qualitative-grid.png` — six frames with the GT box, the VLM box and OWLv2's top-3 proposals
   drawn on. The "look at it" rule applies: a claim about *why* a detector fails is not
   established by a rate, and this is the deliverable that either shows relational failure or
   shows something else entirely.

## Status / next step

Pre-registered, blocked on `../2026-07-21-roi-ondevice/` finishing (it supplies the VLM
comparator and is currently holding the Orin). Next: install `transformers` on the board, write
`run_r13.py`, smoke-test at n=8, then run.
