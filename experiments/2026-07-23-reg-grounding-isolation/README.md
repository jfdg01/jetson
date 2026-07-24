# REG — grounding isolation: target-phrase vs distractor-phrase on the same frame

**Pre-registered 2026-07-23T23:05Z (Madrid). Frozen before any run. Self-contained handoff.**
Spine: `experiments/PART6-PROGRAM-warm-start-significance.md` (S1-S7). Tracked as **R-38** in
`thesis/REMEDIATION.md`. Wave B (real-imagery, on-device). If this README and the program doc
disagree on the frozen gate, the program doc wins.

## Status / next step

- **DONE 2026-07-24 — SYMMETRIC [pre-registered branch]: grounding is NOT the bottleneck.** Pilot +
  paired matrix ran on-device (Jetson q8_0). See Results below. Verdict fed into `claims.json`
  (`R-38-REG-grounding-isolation`), the three Part-V ledgers, and REMEDIATION R-38.

## Question

RQ-REG: are the residual select failures a *grounding* asymmetry — the deployed VLM resolves the
target referent but not an arbitrary distractor phrase on the same frame — or does the failure live
downstream in carry / delivery? Isolates the grounding stage from the rest of the pipeline.

## Design (frozen)

- **Paired-binary, exact McNemar** (two-sided p<0.05), deflated, Part-V Holm.
- **Same prompt frame, two phrases.** Arm A = target phrase, correct = box IoU >= 0.25 vs target GT.
  Arm B = distractor phrase, correct = box IoU >= 0.25 vs distractor GT.
- **Unit = one distinct UAV123 clip** (shares the R-36 bank + its distractor_gt boxes). **n >= 28.**
- **Dependent decomposition** of the R-36 population -> declared in the **same Part-V Holm family**,
  NOT independent confirmation (S6). Stated so it is never double-counted.

### FROZEN GATE (verbatim)

Reject H0(grounding symmetric) at exact two-sided McNemar p<0.05, deflated, Part-V Holm. b =
(target-correct AND distractor-wrong); c = (target-wrong AND distractor-correct). b+c >= 6
one-directional. Directional expectation b >> c (grounding resolves the intended referent but not an
arbitrary distractor).

**Pre-registered symmetric branch:** b ~ c -> the select failure is **not isolable to grounding** ->
attribution redirects downstream to carry / delivery. Honest content either way.

**Reachability + pilot:** P5.18 end-to-end was target ~0.98 vs distractor ~0.65 -> asymmetry ~0.30
-> b ~ 8-9 at n=28. **But that 0.65 is END-TO-END (confounds carry+delivery)** — isolated grounding
on the prompt frame may be better or worse, so the distractor-grounding base rate is **piloted
before reachability is claimed**. If isolated grounding is near-symmetric, the symmetric branch is
the finding.

**OOD-prompt reading (pre-registered):** the VLM was fine-tuned on generic terse captions, not
discriminative referring expressions. If both phrases resolve to the salient object regardless
(distractor phrase still lands on the target), that is an OOD-prompt result about the training
distribution, reported as such — not a grounding-symmetry claim.

## Command (intended)

```bash
# pilot: isolated distractor-grounding rate on the prompt frames
.venv-ft/bin/python experiments/2026-07-23-reg-grounding-isolation/reg_isolate.py \
    --bank runs/r36/bank --arm distractor --pilot --out runs/reg/pilot
# paired on-device matrix (target phrase + distractor phrase, same frame)
.venv-ft/bin/python experiments/2026-07-23-reg-grounding-isolation/reg_isolate.py \
    --bank runs/r36/bank --arms target,distractor --out runs/reg
.venv-ft/bin/python experiments/2026-07-23-reg-grounding-isolation/verdict_reg.py runs/reg
```

## Environment / versions

**On-device.** Jetson Orin Nano 8 GB, deployed `phase3-terse100eos-1024-q8_0.gguf` + mmproj at
`/home/jfdg/grounding/`, via `JetsonBackend` over SSH; **power mode 15 W + jetson_clocks**;
`max_side=1024`. UAV123 clips (R-36 bank). Registered `machine='both'` (S6; the frozen 6-id on-device
set in the integrity test is not extended). Pins -> `runs/reg/env.json`.

## Reuse map

| Need | Symbol / file:line |
|---|---|
| VLM grounding call | `experiments/2026-07-04-warm-start-acquire/replay_e24.py:93` `vlm_acquire`; `grounding/eval/backends.py:344` `JetsonBackend` |
| GT + distractor_gt loader | `experiments/2026-07-20-n25-select/curate_p518.py:49` `load_gt` (distractor_gt boxes from the R-36 bank) |
| stats | `grounding/stats.py` `mcnemar` :114, `deflate_to_effective` :69 |

## Estimates (up front)

- Est target-phrase 27-28/28, distractor-phrase 18-24/28 (isolated, likely better than the 0.65
  end-to-end). Est b~5-9 => reachability hinges on the pilot; if isolated distractor grounding is
  strong (asymmetry small), the symmetric branch fires — itself the finding (failure not in
  grounding).
- Runtime (est): on-device over SSH, ~28 clips x 2 phrases x ~5 s = ~10 min compute + pilot ~5 min.
  Cheap; the value is the attribution, not the runtime.

## Decisions / rationale

- Declared in the Part-V Holm family as a **dependent decomposition** of R-36, not a second
  independent test — inflating the family with a correlated test would be p-hacking by multiplicity.
  Recorded in `docs/decisions/part5-anticipatory.md`.

## Results (RAN 2026-07-24)

| metric | target phrase | distractor phrase | note |
|---|---|---|---|
| pilot base rate (distractor arm only) | (n/a) | 12/14 = 0.857 | **>> P5.18's 0.65 end-to-end** — that 0.65 confounded carry+delivery, not grounding |
| correct (matrix, gating n=14) | 13/14 | 12/14 | IoU>=0.25 vs respective hand GT (never crossed) |
| McNemar b / c | — | b=2, c=1 | b=target-ok&distractor-miss; c=target-miss&distractor-ok |
| deflated p, n_eff | — | p=1.0, n_eff=14 | b+c=3 < floor 6 ⇒ no test reaches α; symmetric branch; Holm moot |

**Verdict: SYMMETRIC [pre-registered branch] — grounding is NOT the bottleneck.** The deployed q8_0
VLM resolves an arbitrary distractor phrase (12/14) nearly as well as the target phrase (13/14) on
the *same* frame, so the residual select failure is **not isolable to grounding**; attribution
redirects downstream to carry / delivery, supporting maintain-and-deliver. The OOD
"collapse-to-salient" reading is **refuted on looking**: the distractor box lands on the distractor
*object* (car9 = sign gantry, car10 = a distinct distant car, wakeboard8 = the boat). The 3
discordants on visual audit are IoU-floor near-misses on tiny objects (car10 distractor, wakeboard8
target) plus person13 — whose distractor GT is the mis-placed-on-empty-ground box R-36 already
flagged and withdrew; excluding it → b=1/c=1, even more symmetric.

### As-run deviations from the pre-registration

- **`--bank` path.** The intended CLI used `runs/r36/bank`; the bank actually lives under the R-36
  experiment dir. As-run: `--bank experiments/2026-07-23-r36-maintain-vs-select/runs/r36/bank`
  (`_load_scenes` globs `*scenes*.json` → `scenes_r36.json`). No repo-root `runs/` symlink exists.
- **n = 14, not the estimated 28.** The n>=28 estimate assumed a richer SWAP-hard population; R-36
  established UAV123 is scene-starved for it (14 gating scenes, all distinct base captures). The
  frozen gate (b+c>=6 one-directional) was still reachable at n_eff=14 — and the effect is genuinely
  symmetric, so power is not the binder here.
- **Verdict CLI.** Used `reg_isolate.py --verdict runs/reg` (the `verdict_reg.py` shim in the
  intended-command block was never authored; the `--verdict` subcommand in `reg_isolate.py` is the
  same computation).
- **Machine.** Registered `machine='both'` per S6; grounding boxes are Jetson-only (q8_0,
  15 W + jetson_clocks, max_side 1024), McNemar on host CPU. No SAM2 / carry / CARLA / 3090.

**Proof (2, committed):** (1) `proof/reg_landing.png` — the same prompt frame with the target-phrase
box and distractor-phrase box drawn against their own GTs, for one concordant clip + the 3
discordants, opened with the Read tool (distractor lands on the distractor object; discordants are
floor near-misses). (2) `proof/reg_per_clip_outcome.png` — per-clip target-vs-distractor outcome grid
with the frozen b/c/p annotated, reproducible from `runs/reg/results.json` via `make_proof.py`.
