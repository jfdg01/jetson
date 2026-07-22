# R-13 — the missing detector baseline: OWLv2 vs the 2B VLM, both on the Orin

**Status:** COMPLETE · **Opened:** 2026-07-21T20:05Z · **Closed:** 2026-07-22T22:40Z · **Branch:** `main`
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

## A fourth arm, added before the run (declared, not silent)

The pre-registration named three arms. A fourth, **D-phrase**, was added while writing the runner
and before any scoring: the noun phrase with its adjectives kept (`"the white vans near the
intersection"` → `"white vans"`), sitting between D-full and D-head.

The reason is that D-head as specified throws away the appearance words OWLv2 is *built* to score
— colour, size, type. A detector evaluated only on `"vans"` could be dismissed as strawmanned, and
`"white vans"` is what a real decomposed system's parser would actually emit. It costs one extra
forward pass per sample. **It turned out to be the detector's best arm by 21.6 pp**, so adding it
was load-bearing, not cosmetic: without it this campaign would have understated OWLv2 badly.

## Install log (record every install, per CLAUDE.md)

The Jetson has torch 2.8.0 + CUDA in `~/sam2-bench/.venv` (the JetPack aarch64 wheel — do **not**
let a package manager replace it). `transformers` was absent; installed with `uv` into that venv
so the JetPack wheel was never touched:

```bash
ssh jetson '~/.local/bin/uv pip install --python ~/sam2-bench/.venv/bin/python transformers'
# -> transformers 5.14.1, plus regex / safetensors / tokenizers. torch 2.8.0 unchanged.
```

Weights: `google/owlv2-base-patch16-ensemble`, fp16, fetched once to the board's HF cache.

## Commands

```bash
ssh jetson 'sudo nvpmodel -m 0 && sudo jetson_clocks'
scp experiments/2026-07-21-detector-baseline/{run_r13_device.py,samples.jsonl} jetson:~/r13/
ssh jetson 'cd ~/r13 && nohup ~/sam2-bench/.venv/bin/python run_r13_device.py \
    --manifest samples.jsonl --out owlv2.jsonl --root data > run.log 2>&1 &'
scp jetson:~/r13/owlv2.jsonl jetson:~/r13/owlv2.meta.json experiments/2026-07-21-detector-baseline/raw/
PYTHONPATH=. .venv-ft/bin/python experiments/2026-07-21-detector-baseline/score_r13.py
PYTHONPATH=. .venv-ft/bin/python experiments/2026-07-21-detector-baseline/make_proof.py
```

**The device script does not score anything.** It dumps raw boxes in original pixel coordinates;
`score_r13.py` normalises them on the host through `grounding/contract.py`, the single scoring
path for every number in the thesis. That split is deliberate — it keeps the detector arm from
quietly acquiring its own metric — and it caught a real bug (below).

## Results

Run 2026-07-22T22:13Z. Jetson Orin Nano 8 GB, 15 W + `jetson_clocks`, fp16, `transformers` 5.14.1,
torch 2.8.0. 439 samples × 3 forwards = 1317 forward passes in **459.9 s**.

| arm | k | n | IoU@0.25 | mean IoU | center_std | latency ms (median) |
|---|---|---|---|---|---|---|
| VLM Q8_0 full-frame @1024 (from R-14 arm A) | 277 | 439 | **63.10%** | 0.4767 | 21.888 | 4319 (wall) |
| D-oracle (OWLv2, best of top-10 vs GT) | 397 | 439 | **90.43%** | 0.7887 | 22.531 | — (not a system) |
| D-phrase (OWLv2, noun phrase) | 208 | 439 | 47.38% | 0.4138 | 23.683 | 263.5 (forward) |
| D-full (OWLv2, full expression) | 113 | 439 | 25.74% | 0.2283 | 21.922 | 263.5 (forward) |
| D-head (OWLv2, head noun) | 108 | 439 | 24.60% | 0.2187 | 22.749 | 263.5 (forward) |

`center_std` is flat across all arms (21.9–23.7) — no arm mode-collapsed, so none of the rates is
an artefact of a detector parking its box in the middle of the frame.

**Paired McNemar, VLM vs each arm, deflated to `n_effective` = 316 unique images:**

| comparison | b (VLM only) | c (det only) | b,c deflated | p (deflated) | direction |
|---|---|---|---|---|---|
| VLM vs D-full | 186 | 22 | 134, 16 | 2.18e-24 | VLM wins |
| VLM vs D-phrase | 100 | 31 | 72, 22 | 2.26e-07 | VLM wins |
| VLM vs D-head | 181 | 12 | 130, 9 | 1.26e-28 | VLM wins |
| VLM vs D-oracle | 1 | 121 | 1, 87 | 5.75e-25 | **oracle wins** |

**Recall@k, the load-bearing number.** For the D-phrase arm, the fraction of items with a
gate-passing box somewhere in its top-k:

| k | 1 | 2 | 3 | 5 | 10 |
|---|---|---|---|---|---|
| D-phrase recall@k | 47.4% | 63.0% | 72.4% | 81.5% | **88.8%** |

OWLv2's **second** proposal already ties the deployed VLM's top-1 (63.0% vs 63.1%). By k=10 it has
the right box on 88.8% of items and cannot say which one it is. Only 49/439 (11.2%) of items have
no correct box anywhere in the phrase arm's proposals.

**Cost.** OWLv2 forward: 263.5 ms median (p90 264.1 — a flat, input-independent cost, unlike a
generative decode). Peak CUDA 415.3 MB. Model load 3.6 s. Against the VLM's **4216 ms of on-device
compute** (prefill 3680 + decode 536, R-14 arm A) this is **16.0× cheaper per call and ~5× smaller
in peak memory**. The like-for-like comparator is compute, not the 4319 ms wall: the wall carries
~103 ms of base64 over an ssh tunnel, and R-14's own record states that prefill and decode are
Orin compute while the wall is not. Billing the cable to the VLM would read 16.4×.

### The architectural ceiling found on the way

OWLv2's text encoder has `max_position_embeddings = 16`. A query of 17+ tokens does not degrade —
it **crashes the forward pass** (`size of tensor a (17) must match tensor b (16)`), which is how
the first full run died. RefDrone captions run 7–27 tokens (median 10), so **5/439 (1.1%) exceed
what this detector can represent at all** and are truncated. That is a finding about the
architecture's fitness for referring expressions, not a nuisance: the model has a hard 16-token
budget for a task whose inputs are sentences.

### Estimate vs actual (pre-registered — 2 of 7 landed)

| quantity | estimate | actual | verdict |
|---|---|---|---|
| VLM comparator | ~63% | 63.10% | hit |
| D-full | 15–35% | 25.74% | hit |
| D-head | 30–50% | 24.60% | **below** — the head noun is *worse* than the full expression |
| D-oracle | 55–75% | 90.43% | **far above** — a much better proposer than expected |
| OWLv2 latency | 0.4–1.2 s | 0.264 s | **below** — the interval called "most likely to be embarrassing" was |
| peak memory | 2.5–4 GB | 0.415 GB | **6× below** |
| runtime | ~1.5 h | 7.7 min | **12× below** |

Every miss is in the same direction: **OWLv2 is a far cheaper and far better proposer than
predicted, and a worse selector.** The pre-registered qualitative prediction — *"D-oracle lands
high and D-full lands low, i.e. the detector is a competent proposer and a hopeless selector"* —
is exactly what happened, which is the one thing worth more than the numeric estimates.

## Research questions — answers

**RQ-R13.1 (primary): does the deployed VLM beat OWLv2 at referring-expression grounding on the
Orin? — YES, decisively, against every non-oracle arm.** 63.10% vs 25.74% end-to-end
(p = 2.18e-24 deflated), and it still wins against the detector's *strongest* configuration,
D-phrase, 63.10% vs 47.38% (p = 2.26e-07). Both survive any reasonable multiplicity correction.
The architecture choice the thesis rests on is justified — but see RQ-R13.3 for the reason it was
originally justified being wrong.

**RQ-R13.2 (the decomposition): the failure is selection, not localisation.** D-oracle reaches
90.43%, beating the VLM itself (p = 5.75e-25 in the detector's favour), and D-phrase recall@10 is
88.8%. The object is in the proposals; the language cannot pick it out. Two supporting splits:

- **Relational language actively hurts.** D-full (25.74%) is 21.6 pp *below* D-phrase (47.38%).
  Handing OWLv2 `"the white vans near the intersection"` is worse than handing it `"white vans"` —
  the relational clause is not ignored, it is scored, and it drags the match off the target.
- **Adjectives are what carry it.** D-phrase (47.38%) − D-head (24.60%) = 22.8 pp. Appearance
  words are the detector's whole contribution; strip them and it is at chance-like class-level
  localisation.

So the honest conclusion is **not** "OWLv2 is worse". It is that the decomposed architecture needs
a **selection stage** the 2026-06-14 campaign never costed — and that stage is precisely the hard
part, because the proposals are already there. `qualitative-grid.png` shows the shape of it: in
six cases the correct box sits at rank 7–10 while ranks 1–3 are other, equally valid instances of
the same class scattered across the frame.

**RQ-R13.3 (cost): the 2026-06-14 decision was right for the wrong reason.** That campaign closed
the decomposed fork **on latency grounds alone, without measuring a detector**. OWLv2 is 16.0×
*faster* than the VLM per call (263.5 ms vs 4216 ms of on-device compute) and needs 5× less
memory. The latency argument was backwards. What actually rules the decomposed path out is the
41.5 pp selection gap — a quality argument, not a cost one.

This does not overturn the architecture; it re-grounds it. **Two caveats on the 16.0×.** First,
use compute and not the 4319 ms wall: the wall includes ~103 ms of base64 over an ssh tunnel and
the detector figure is a synchronised device forward, so a wall-vs-forward ratio would read 16.4×
and would bill the cable to the VLM — the same defect R-14's record calls out. Second, it compares
one detector forward against one full generative anchor. A decomposed system would need the
missing selection stage on top, and if that stage is itself a VLM the saving evaporates — which is
the argument the thesis should be making, and could not make before this run.

## Proof deliverables

Under `proof/`, all three from the committed `make_proof.py` (reproducible from
`results.json` + `raw/owlv2.jsonl`):

1. **`arms-bar.png`** — the five arms with Wilson 95% intervals computed on `n_effective` = 316
   unique images, not the 439 rows. Shows the VLM above every real detector arm and below the
   GT-using oracle. The oracle bar is hatched to mark it as a bound, not a system.
2. **`oracle-gap.png`** — recall@k for all three detector arms against the VLM's top-1 line. The
   D-phrase curve crosses the VLM at **k=2** and flattens at 88.8%; the 41.5 pp arrow between
   recall@1 and recall@10 *is* the "proposer, not selector" result in one picture.
3. **`qualitative-grid.png`** — six frames, zoomed to the box union (RefDrone targets are a few
   percent of frame width; full-frame renders them as invisible dots — this bit the R-14 figures
   first). GT in green, VLM top-1 in blue, OWLv2's top-3 in red, and **the correct OWLv2 proposal
   at its true rank in magenta**. The magenta box lands on the GT in all six panels while the red
   ones sit on other cars/people elsewhere in the scene: the detector saw it and ranked it 7th–10th.
   The first draft drew only the top-3 and so left the figure's own claim unshown — caught by
   opening it, per the "look at it" rule.

## What broke, and what it cost

- **Coordinate-space contamination, caught by a smoke test at n=8.** Every IoU came back 0.000.
  OWLv2 returns pixels; the project's GT and every VLM number live in `contract.py`'s 0–100
  normalised space. Spotted because a `gt=[32, 26, 34, 29]` on a 960×540 image would be a 2×3-pixel
  box. This is the same bug class as the 0–1000 checkpoint contamination of 2026-06-25, and it is
  the reason scoring is a separate host-side script rather than a convenience function on the device.
- **Head-noun extraction leaked verbs.** `"the gray van parks on the right"` → head `"parks"`.
  Fixed by adding verb stems to the cut list. Then the naive suffix generator produced
  non-words — `"drive"+"ing"` = `"driveing"`, which matches nothing, so `"red cars driving"` still
  came back as `"driving"`. Fixed with `_forms()` (e-dropping, y→ies). Final extraction is 99.3%
  clean object nouns (436/439), audited by dumping `text.{full,phrase,head}` per item.
- **The 16-token crash**, above.

None of these would have been visible from the run log. Two of the three were caught only because
something was inspected — the IoU column and the extracted nouns — rather than because a process
exited non-zero.

## Status / next step

**COMPLETE.** Registry claim `P3-R13-owlv2-vs-vlm` (paired-binary, `machine: jetson-orin-nano-8gb`,
n_effective 316). Ledger entries under Part III. No follow-up run is proposed: the selection-stage
question this opens is a design question for the discussion chapter, not another measurement —
and building an OWLv2 + selector stack would be a new thesis, not a missing experiment.
