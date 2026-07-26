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

**Author steer, 2026-07-25: the thesis text is NOT started yet.** It waits on
supervisor confirmation of scope. Until then the evidence programme stays live and
experiments continue. Everything below is therefore split by whether it can be worked
*while experimenting* (the R series, yes) or only *once writing begins* (the W series).


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

## Status board — W series (the writing programme; BLOCKED on the supervisor)

W-3, W-5, W-6, W-7, W-8 and W-9 are **not** blocked — they are preparation that makes
the writing possible and can be done at any time. Only W-1, W-2 and W-4 need the
go-ahead.

| ID | Task | Blocked? | Status |
|---|---|---|---|
| W-1 | Write the 287 paragraphs (cap01–cap10) | yes | BLOCKED |
| W-2 | cap04 is the weakest chapter and needs the most work | yes | BLOCKED |
| W-3 | Reconstruct the Part I–III figures — those campaigns have no `proof/` | **no** | OPEN |
| W-4 | cap08's scaffold is ~2x its page budget | yes | BLOCKED |
| W-5 | `00-esquema.md` has no chapter plan for cap01 or cap02 | **no** | OPEN |
| W-6 | The two finished method documents are not in the assembly | **no** | OPEN |
| W-7 | cap01 carries a bracket that breaks pandoc's citation parser | **no** | OPEN |
| W-8 | Two competing claim-reference forms across chapters | **no** | OPEN |
| W-9 | cap03's mean-IoU figure has never been computed | **no** | OPEN |

---


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
Concretely, retiring the framing touches a chapter *title*: `cap07-grounding-anticipatorio.md`
("Grounding anticipatorio", plus `00-esquema.md` §Capítulo 7) is named after the phrase this
threat retires. Not renamed here — a chapter title is an author decision, and the honest
minimum (the S6 section in cap09) is landed either way.

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

## The writing programme, W-1..W-9

### The one number that matters

`thesis/borrador/` holds ten chapters, 33,005 words, 40 tables, 38 figures that all
resolve on disk, 3 code listings, 27 bib keys all cited and all present — and **287
paragraph specs with zero paragraphs of written body prose.** Every chapter carries
`Guion de párrafos. Sustituir cada viñeta por prosa.` and consists of bullets of the form
`- **P1 — El titular.**`. The outline's own status line, `Texto: no empezado.`, is
literally accurate.

The scaffold is unusually load-bearing, which is the good news: the remaining work is
genuinely *writing*, not deciding. Estimate ~3–4 weeks at ~5 paragraphs/hour with
number-checking against `claims.json` — mark that as an estimate.

### W-1 — Write the 287 paragraphs — BLOCKED

Blocked on supervisor confirmation of scope. Do not start chapters before that
confirmation: the scope decision changes the page budgets, and W-4 shows the budgets are
already wrong.

### W-2 — cap04 is the weakest chapter — BLOCKED

Thinnest scaffold against the largest budget: 2,930 words / 26 paragraph specs for an
11-page target (2.4 specs per page, against 4.2 in cap07 and 7.0 in cap08). It also
carries the most pending figures — three `[FIGURA POR GENERAR]`, including the Part I
fidelity gap and the backbone bake-off. Its only three embedded images come from the R-13
OWLv2 comparison, i.e. from Part III, not from Parts I–II which the chapter is about.
Depends on W-3.

### W-3 — Reconstruct the Part I–III figures — OPEN, **not blocked**

**49 of 89 campaign directories have a `proof/`; the earliest is `2026-07-03-chase-acquire`.**
Every campaign before that date — all of Parts I–III — has none. That is the blocker
behind cap04's and cap05's pending figures: they must be reconstructed from raw logs.

This is the single most valuable thing that can be done *before* the go-ahead, because it
is data recovery, not prose, and it gets harder as memory of those runs fades. Per
CLAUDE.md DoD-7 the figures come from a committed `make_proof.py`-style script
reproducible from the run data, saved as PNG.

### W-4 — cap08 overshoots its page budget — BLOCKED

`00-esquema.md` budgets cap08 at **4** pages and says "P6.0 y P6.1 dejan de narrarse como
resultados". cap08 is now the second-largest scaffold: 4,204 words, 28 specs, 9 figures,
6 tables — about 8–9 pages. The outline was rebalanced *before* P6.2-DELIVERY landed and
became a Holm survivor. Either the budget moves or the content is cut; that is a scope
decision, hence blocked.

### W-5 — cap01 and cap02 have no chapter plan — OPEN, not blocked

`00-esquema.md` contains per-chapter design sections for **Capítulo 3 through Capítulo 10
only**. cap01 and cap02 exist solely as rows in the structure table, so their scaffolds
were generated without the outline's evidence-mapping discipline. cap02 is the thinnest
literature scaffold (22 specs / 8 pages) and is the only chapter that states it defends
nothing.

### W-6 — The finished method documents are not in the assembly — OPEN, not blocked

`thesis/01-metodo-estadistico.md` (3,676 words) and `thesis/02-metodo-multiagente.md`
(2,090 words) are **the only written Spanish prose in `thesis/`** — real text, not
scaffolds. Neither appears in `thesis/borrador/assemble.py`'s `CHAPTERS` list, so neither reaches
`TFM-borrador.pdf`, despite both being planned as annexes. Add annex targets to the
assembler and reconcile them against the two cap03 sections that summarise them.

### W-7 — A bracket that breaks pandoc — OPEN, not blocked, cheap

`cap01-introduccion.md` ends a bullet with `[@dosovitskiy2017carla no aplica aquí]`. The
key is real, but the free text inside the bracket breaks pandoc's citation parser, and
the citation is meaningless there — it sits on a paragraph about the Orin Nano's 15 W
ceiling. It reads like a leftover editorial marker. Delete the bracket.

### W-8 — Two competing claim-reference forms — OPEN, not blocked, cheap

cap04 and cap08 use the backticked `` [claim `ID`] `` (12 + 22 occurrences); cap06 (11)
and cap07 (14) use the bare `[claim ID]`. Pick one — the backticked form is now the
majority — and normalise the other 25.

### W-9 — cap03's mean-IoU figure was never computed — OPEN, not blocked

`cap03-plataforma-metodo-metricas.md` retains a genuine evidence-debt note: "no hay un
valor de IoU medio registrado todavía ... hay que calcularla antes de cerrar el
capítulo". This is a real open measurement, not a stale-number defect.

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
