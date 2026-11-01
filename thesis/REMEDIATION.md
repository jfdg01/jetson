# REMEDIATION — the task ledger

Working state for the thesis-integrity programme. Rules and rationale are in
`HANDOFF.md`; this file is only *what is left to do and what proves it is done*.

This is a working document, not a thesis deliverable — it stays in English, like
`CLAUDE.md`. The chapters it produces are Spanish, with full diacritics.

**Protocol:** pick the first task that is not `DONE` whose preconditions are met.
Update `Status` and `Evidence` before the session ends. A task is `DONE` only when
its done-criterion is mechanically satisfied — not when it feels finished.

`AUTHOR` means the task is a judgement call reserved for the human and **must not
be resolved by an agent**. An agent may prepare the evidence; it may not pick.

## Closed waves — do not open unless auditing history

R-1..R-44, R-46, R-47, R-52, R-53 and R-54 are all `DONE`. Their full write-ups moved
out of this file on 2026-07-26 (they were 33k of its 46k tokens, re-read every session
for zero decision value). The outcomes live in `thesis/claims.json`,
`thesis/stats-report.md` and the `docs/` ledgers; the original task records are here:

| Wave | Items | Closed | Record |
|---|---|---|---|
| First | R-1..R-21 | 2026-07-21 | `thesis/remediation-archive/wave1.md` |
| Second + third | R-22..R-38 | 2026-07-23/24 | `thesis/remediation-archive/wave2-3.md` |
| Fourth (closed part) | R-39..R-44, R-46, R-47, R-52, R-53, R-54 | 2026-07-25/26 | `thesis/remediation-archive/wave4-closed.md` |

Everything below is open, blocked, or reserved for the author.

---

## Fourth wave — the open programme

Opened 2026-07-25. Different in kind from waves one to three: those were opened by an
audit that found the apparatus wrong. This one was opened by the apparatus running
**out of work** — R-1..R-38 all read `DONE`, so a session following the entry protocol
("pick the first task that is not `DONE`") finds nothing, while `HANDOFF.md`'s own
finish criterion — "the thesis chapters are written from the corrected claim set" —
has not been started.

The thesis writing lives in the GitHub map `Mapa: escribir y entregar la tesis` (#10).

**Superseded in part, 2026-07-27: scope is now confirmed** —
`thesis/SCOPE-2026-07-27-supervisor-steer.md`. Focus on tracking, a real-drone test that
includes the piloting, airframe chosen by September, target regime **200 km/h**. The evidence
programme stays live. Nothing was pre-registered — the author deferred Part VII the same day.


## Status board — R series (integrity; work these any time)

| ID | Task | Pri | Status |
|---|---|---|---|
| R-39 | Caveat prose must agree with the computed Holm verdict | **P0** | **DONE** 2026-07-25 |
| R-40 | Stale first-read surfaces (`CLAUDE.md`, ledger roots, PART6-PROGRAM, EXP READMEs) | P1 | **DONE** 2026-07-25 |
| R-41 | `README.md`: stale survivor count, and no Part VI number at all | P1 | **DONE** 2026-07-25 |
| R-42 | Borrador citation hygiene (cap08 pseudo-cites, I8 line numbers, cap01 count) | P1 | **DONE** 2026-07-25 |
| R-43 | EXP-3's only data was gitignored; its status header claimed "running" | P1 | **DONE** 2026-07-25 |
| R-44 | EXP-1/EXP-2 publish p-values outside `claims.json` | P1 | **DONE** 2026-07-26 — author picked *demote*: EXP-1/EXP-2/EXP-6 are labelled engineering measurements and the p-values moved to their campaign READMEs. **EXP-4 carries the same defect and was left as-is** (see R-55) |
| R-45 | EXP-1/2/3 break the frozen experiment-ID scheme | P2 | **AUTHOR** |
| R-46 | The "deployed" carry resolution is stated three different ways in code | P1 | **DONE** — `grounding.contract` owns `CARRY_IMAGE_SIZE`/`CARRY_FALLBACK_IMAGE_SIZE`/`CARRY_HZ`; `CARRY_HZ` re-derived at 640 (5.76) |
| R-47 | EXP-3's acquire data points the opposite way to EXP-2's crop elbow | **P1** | **RESOLVED** — no contradiction; `OPT`/`FULL` are one crop at 1x vs 4x upscale, and EXP-3 never ran EXP-2's `ROI_RES=512` |
| R-48 | The only ratchet is closed, so HANDOFF's finish criterion is vacuous | P2 | OPEN |
| R-49 | Branch clutter: 28 merged `experiment/*`, 3 unmerged carrying unique content | P3 | **AUTHOR** |
| R-50 | `tests/test_carla_lifecycle.py` never runs in `make test` | P3 | OPEN |
| R-55 | EXP-4 publishes p-values outside `claims.json`, exactly as R-44's EXP-1/EXP-2 did | P1 | OPEN — R-44's *demote* pick applies verbatim, but the scope asked for was EXP-1/EXP-2/EXP-6 |
| R-53 | The live panel cold-started a SAM2 bridge per designation (P6.7 measured the fix; panel now resident) | **P1** | DONE |

## R-45 — EXP-1/2/3 break the frozen experiment-ID scheme — **AUTHOR**

`CLAUDE.md`: "**Part V onward uses `P<part>.<n>`**", and the flat `E1..E23` scheme is
"frozen, do not renumber". These three landed in the Part VI ledgers as `EXP-1`, `EXP-2`,
`EXP-3` — a revival of the retired flat scheme. Either rename to `P6.3`/`P6.4`/`P6.5`
(and fix the ledger rows, READMEs and proof captions) or record an explicit amendment in
`DECISIONS.md`. Renaming is cheap now and gets more expensive with every citation.

## R-48 — The finish criterion is vacuous — OPEN P2

`HANDOFF.md`: "the programme is finished when `tests/test_thesis_integrity.py` has no
ratchets left above zero". There is exactly one ratchet, `MAX_CLAIMS_WITHOUT_MACHINE = 0`,
closed on 2026-07-21 and now a hard rule. So the criterion is **already satisfied and no
longer discriminates** — it must not be quoted to an examiner as evidence the programme
is finished.

Either retire the sentence and replace it with a criterion that still has teeth, or
promote a real ratchet. A candidate exists: `tests/test_harness_items.py` calls itself
"the ratchet" in prose but declares no ceiling constant, and 5 of the 11 Holm survivors
are still `data_status: counts_only` (`P1-S3.3-export-parity-catastrophe`, `P2-RQ2.1`,
`P2-RQ3.1`, `P2-RQ4.1`, `P3-ROI-M2.0-512`) — meaning an examiner cannot re-derive their
b/c from raw data. "Survivors without per-item evidence" is a number that should only
go down.

## R-49 — Branch clutter — **AUTHOR**

28 merged `experiment/*` branches were never deleted (safe to delete; they are in `main`).
Three are **unmerged and carry content that exists nowhere on main**, so deleting is a
decision, not cleanup:

- `experiment/direct-delivery-select` — 1 ahead, 169 behind. The P5.6 "direct-delivery
  select" pre-registration, superseded by P5.14 onward.
- `experiment/vlm-vision-unfreeze` — 1 ahead, 306 behind. A 47-line pre-draft.
- `v2/1-synth` — 3 ahead, 323 behind. "Synth tried, learned approach, frozen for now."

Each is a negative result or an abandoned direction, and CLAUDE.md says negative results
are content. Merging the *documents* to main and deleting the branches keeps the content
and drops the clutter.

## R-50 — The CARLA lifecycle test never runs — OPEN P3

`make test`'s single skip is `tests/test_carla_lifecycle.py` ("set `CARLA_LIFECYCLE_TEST=1`
-- boots a real CARLA"). Defensible — it needs a desktop GPU and a server — but it means
the renderer lifecycle, **the exact surface that produced the sky-camera scar and the
"look at it" rule**, is never exercised on any machine, so a regression there lands
green. At minimum, run it by hand before any Part VI result and record that you did.

## R-51 — S6: at N=1 the warm arm's advantage is the target identity — **DOCUMENTED**, framing is **AUTHOR**

Opened 2026-07-25 by the author, driving the live demo panel: *"if it only works for one
object and the user has to preselect it manually, is it a bit useless? I'm starting to
doubt the validity of warm vs cold — in theory of course it works, but in practice if
it's only n=1 it's not actually useful."*

**The objection is half right, and the half that is right is a scope statement.** With one
maintained candidate the WARM arm's information advantage *is* the target identity: the
system was told which object to hold, so it anticipates nothing, it holds. The mechanism
that would have made the comparison non-trivial — maintain K unnamed candidates and let
the command pick — is the select arc, dead across 8 runs with `c=0` throughout. So
**"anticipatory grounding" must be retired as a headline**, which is the framing decision
left to the author.

**What survives, and it is not small.** Read what P6.2-DELIVERY actually measures:
`cold_target_exits_frame=0`, `on_target=0` in 23/25. Cold does not fail by picking wrong,
it fails because the box arrives ~4.85 s (~146 frames) after the command. That makes the
finding **agnostic to the box's provenance** — click, prior track, pre-flight designation,
a datalink from another asset. The defensible statement is: *on this device, a box that
exists **before** the command produces a followable lock, and a box **computed after** it
does not; grounding cannot sit on the command path at 8 GB.* Nor is the cold arm a
strawman — it is the system Parts II–IV built and deployed, measured on real UAV123 video
in R-34 at 3/25.

**The forward implication the author asked to record.** The warm/cold pair localises the
binding constraint to **acquire latency**, because everything downstream of a correct box
at command time is certified separately: P5.15 (the carry is not the fragile part, 24/25
against a floor of 18, p=0.0016), P6.2-COUPLING (bounded null under self-induced
ego-motion), P6.2-SHOWCASE (24/24 at median IoU 0.92 on the Orin, 0.960 flight parity). So
an acquire pruned to ~1 s would put the deployed carry inside its already-demonstrated
envelope — bounded to the tested regime (nadir, daytime, UAV123/CARLA, car or person),
with carry drift still owning the residual failure. That is what makes warm/cold worth
running even at N=1: it is the measurement that says *which* component to spend hardware on.

**Landed:** the full S6 caveat on `P6.2-DELIVERY-warm-vs-cold-closedloop` and a pointer
caveat on `P5.1-warm-vs-cold` / `P5.2a-warm-generalization` in `claims.json`, regenerated
into `stats-report.md`; a DECISIONS entry under Part VI; finding 21 and the DESIGNATE card
text in the demo panel (`runners/CARLA_DEBUG_UI_FINDINGS.md`).
**Still open (author):** whether the thesis headline changes, and whether R-52 runs.
Retiring the framing means that no chapter title uses "Grounding anticipatorio", the phrase
this threat retires. A chapter title is an author decision, and the thesis must state S6 either way.

*Side observation, not fixed here:* the P6.2-DELIVERY and P6.2-COUPLING caveats are
ASCII-folded Spanish (`fisica`, `designacion`) — they were written after the 65-caveat
diacritics pass, so they drifted back. The S6 text added to them is properly accented; the
older prose around it is not, and one of them should be brought into line.

## R-55 — EXP-4 publishes p-values outside the registry — OPEN P1

Split out of R-54 on 2026-07-26: the ID `R-54` had been used twice, once on this open
task (status board) and once on P5.20's owed on-device capacity gate (`DONE`, EXP-9),
which would have archived an open P1 under a `DONE` heading.

Same defect R-44 fixed for EXP-1/EXP-2/EXP-6, in the same campaign directory as EXP-6
(`experiments/2026-07-26-crop-mode/`). R-44's author pick — *demote*: label the campaign
an engineering measurement and move the p-values into its README — applies verbatim; it
was not applied because the scope R-44 asked for named EXP-1/EXP-2/EXP-6 only.

**Done when:** EXP-4's p-values either enter `thesis/claims.json` as registered claims
(and take their place in the Part's Holm family, per R-39) or move to the campaign README
under the engineering-measurement label, with `make test` green either way.

## Explicitly NOT to be done

Recorded so a future session does not re-propose them:

- **Do not re-run T2/T3 as specified** — single Bernoulli draws. Widen the clip bank
  or leave them labelled as pilots.
- **Do not build bank v4.** The sim arc is correctly closed (P5.17).
- **Do not retrain to recover the lost safetensors checkpoint.** The deployed GGUF
  exists, is sha256-mirrored, and still serves. Declare the loss as a limitation.
- **Do not grow Part VI** beyond "infrastructure built, claim not yet made" until
  R-12/R-4/R-13/R-14 are done.
- **Do not port SAM2 in order to rescue P5.19.** See R-16.

---

## Candidate experiments, since the programme stays live

Not tasks — a slate to pick from. Ranked by what the evidence actually still lacks.

**1. P5.22 — abstention / confidence calibration.** The one residual in the whole arc
that has never had an experiment aimed at it. P5.19's grace precision is **2/4**, and
`docs/questions/part5-anticipatory.md` records the failure mode precisely: when wrong, it
"delivers confidently rather than abstaining". Every other Part V residual has been
attacked and closed — carry drift by capacity (P5.20, dead lever) and by ROI (P5.21,
measured negative), grounding by R-38 (symmetric, not the bottleneck). A system that
hands an operator a confident wrong box is worse than one that says nothing, so this is
both the open question and the one with an obvious operational argument behind it.

**2. Finish or kill EXP-3.** ~~See R-47 — it is half-run, and its existing data
*disagrees* with EXP-2.~~ **Motivation withdrawn 2026-07-26T16:05Z:** R-47 resolved, and
the disagreement this rested on does not exist — EXP-3 varies the crop *upscale* knob,
which EXP-2 never varied. Finishing it is still cheap (carry + score + overlays), but it
would now answer a question nothing depends on. **Kill is the recommended answer**, and
it belongs in `DECISIONS.md`.

**3. R-36 at real n — needs a data source that does not exist yet.** UAV123 is
structurally scene-starved for SWAP-hard pairs: hand-curating 10 fresh candidates
returned **8/10 single-target**, because the dataset follows one target and almost never
frames two co-visible same-class candidates. Three sim banks already failed to
discriminate (P5.10/P5.13/P5.17 — "sim-select discrimination CLOSED"). So this needs new
real footage or a purpose-built bank, and it is the most expensive item on the slate.
Related and equally data-bound: EXP-1 shelved its high-res-source variant because "a true
high-res-source variant needs new >=1080p footage".

Before opening any of these, re-read the dead-lever list in `PART6-PROGRAM` §6 — multi-candidate
select, bigger SAM2, Swin2SR, the caption lever, CLIP crop-scoring and the speed-sweep
motion-compensation reading are all closed, and re-proposing one costs a cycle.

**And note the standing cost, per R-39:** every new experiment registered inside a Part
tightens Holm for every claim already published in that Part. Part V is at m = 21 and has
already lost P5.15 that way. Part VI is at m = 2 and its flagship sits at 9.5e-07, so it
has room — but the check is now mechanical, and it will fail the suite rather than
silently rot a chapter.
