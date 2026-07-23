# REMEDIATION — the task ledger

Working state for the thesis-integrity programme. Rules and rationale are in
`HANDOFF.md`; this file is only *what is left to do and what proves it is done*.

This is a working document, not a thesis deliverable — it stays in English, like
`CLAUDE.md`. The chapters it produces are Spanish, with full diacritics.

**Protocol:** pick the first task that is not `DONE` whose preconditions are met.
Update `Status` and `Evidence` before the session ends. A task is `DONE` only when
its done-criterion is mechanically satisfied — not when it feels finished.

## Status board

| ID | Task | Blocks | Status |
|---|---|---|---|
| R-1 | Scope + disclosure decision on which machine ran what | R-2, R-6 | **DONE** |
| R-2 | `machine` field on all 65 claims | R-6, R-9 | **DONE** |
| R-3 | Fix `paired-binary` skipping deflation in `grounding/stats.py` | R-9 | **DONE** |
| R-4 | Apply the pseudo-replication rule to `n_effective` | R-9 | **DONE** `1acb332` |
| R-5 | Shadow-RG re-analysis + Chapter 7 rewording | — | **DONE** |
| R-6 | Correct `README.md` | — | **DONE** |
| R-7 | Claim-provenance sweep of every published number | R-9 | **DONE** (27 CONTRADICTED fixed; rest -> R-21) |
| R-8 | Merge or retire `experiment/carla-gt-bank` | — | **DONE** `f75b5de` |
| R-9 | Regenerate `stats-report.md` from the corrected registry | — | **DONE** |
| R-10 | Vacuous-metric audit | R-7 | DONE |
| R-11 | Thesis section: multi-agent development as method | — | **DONE** (draft) |
| R-12 | Render `caveats` into `stats-report.md` | R-9 | **DONE** `5b6f7ab` |
| R-13 | Detector baseline (OWLv2 on the Orin) | — | **DONE** (2026-07-22T22:40Z; claim `P3-R13-owlv2-vs-vlm`, survives Holm) |
| R-14 | ROI on-device Q8_0 re-run | R-9 | DONE (2026-07-21T20:21Z; claim P3-ROI-M2.0-512-ondevice) |
| R-15 | Per-item jsonl in `grounding/eval/harness.py` | R-14 | DONE (2026-07-21T20:21Z; items-{full,roi}.jsonl carry 439 rows each, paired the claim) |
| R-16 | SAM2 co-residency characterisation (reframed campaign) | — | **DONE** (2026-07-23T01:20Z; `experiments/2026-07-22-sam2-coresidency/`, claim `P4-R16-carry-rate-1024`) |
| R-17 | Fix E2–E4 rig prose | R-7 | **DONE** |
| R-18 | Rebalance `thesis/00-esquema.md` to the surviving evidence | R-9 | DONE |
| R-19 | Stale-verdict sweep of the first-read surfaces | after R-4 | **DONE** |
| R-20 | Translate the 65 `caveats` to Spanish | R-12 | **DONE** |
| R-21 | Work the 74 MISLEADING/UNVERIFIED rows from the R-7 sweep | R-7 | **DONE** (70 rewritten, 4 accepted; resolutions in `provenance-resolutions.json`) |

**Second wave, R-22..R-32.** Opened 2026-07-23T11:55Z from the arc audit
(`wf_3976b3e6-a4f`, 9 agents, 28 findings, all surviving an adversarial refutation
pass). The first wave fixed the *claims*; this wave fixes the *apparatus that
reports them*, which the first wave never audited because it was the thing doing
the auditing. Every P0 below was independently reproduced by hand before being
written down — the reproduction command is in the task.

| ID | Task | Pri | Blocks | Status |
|---|---|---|---|---|
| R-22 | Paired deflation uses the wrong denominator; report contradicts itself | **P0** | R-23 | **DONE** 2026-07-23 |
| R-23 | The four claim buckets overlap and are mislabelled | **P0** | — | **DONE** 2026-07-23 |
| R-24 | R-14 proof figure draws contract coords as pixels | **P0** | — | **DONE** 2026-07-23 |
| R-25 | Registry + module hygiene (`gate_p`, selfcheck, hand-counts) | **P0** | — | **DONE** 2026-07-23 |
| R-26 | `README.md` is stale against R-13/R-14/R-16 | **P0** | — | TODO |
| R-27 | `P3-E1-TRT-fps` never marked superseded by R-16 | **P0** | — | TODO |
| R-28 | The defended sentence claims *select*; nothing inferential carries it | P1 | — | **AUTHOR** |
| R-29 | `n_effective` = 13 vs the measured ICC | P1 | — | **AUTHOR** |
| R-30 | Holm family boundary + undisclosed dependencies | P1 | — | **AUTHOR** |
| R-31 | Retire or re-run P3-T2 / P3-T3; backlog commands are fiction | P1 | — | **AUTHOR** |
| R-32 | Spot-check the assertion-only DONEs (R-19, R-7, R-21) | P1 | — | TODO |

`AUTHOR` means the task is a judgement call reserved for the human and **must not
be resolved by an agent**. An agent may prepare the evidence; it may not pick.

The P0 set is mechanical, needs no GPU, no Jetson and no new measurement. It is
worth doing before any thesis text is written, because every one of these defects
is in a surface the text would quote.

R-12..R-18 come from the sufficiency audit (`wf_b81c3191-d12`, 6 agents,
2026-07-21T21:05Z). **Verdict: the thesis is sufficient — YES, without running a
single new experiment.** Six defensible contributions survive the correction, four
measured on the Orin. What is not sufficient is `thesis/00-esquema.md`, which gives
14 pages to anticipatory grounding (now resting on one surviving test) and half a
page to Part I (the only large body of evidence measured wholly on target hardware).
The work is a rewrite plus three targeted runs, not a rescue.

---

## R-1 — Scope + disclosure decision — DONE 2026-07-21T18:35Z

The thesis says the system runs on the Jetson. Part V ran its tracker on the RTX
3090. Both facts are fine; the gap between them is not documented, and until it is,
every downstream correction is guesswork about what the claim even is.

Two separable claims, and they need separate answers:

- **A. The deployed system runs on-device.** Probably already true — E1 measured
  SAM2-TensorRT at 6.15 FPS co-resident with the VLM on the Jetson. Needs
  confirmation, not a port.
- **B. Every experiment ran on-device.** False, and does not need to be true.
  Ablations on a workstation are ordinary practice. Undisclosed ones are not.

**Landed as** `experiments/2026-07-21-machine-disclosure/README.md`, with
`raw/machine-audit.json` (76 rows, one quoted evidence string each), two proof figures,
and ledger entries Q-MACH.1 / D-MACH.1 / a results block under Part VI.

**What landed, beyond the expected output.** Claim A is confirmed (E1: VLM + SAM2 carry
co-resident on the Orin, 6.15 FPS, mask parity 1.000). Claim B is false and stays false
on purpose. Coverage is better than feared — 61 of 76 campaigns state their host, and
Part I is 9/9 — so the fix is bookkeeping, not re-measurement, and **no Part V result is
re-run on the Jetson**; the reasoning is in D-MACH.1.

One new substantive finding (M1) changed another task rather than adding one: the
6.15 Hz cap is a 768 number applied to a 1024 carry, which makes every emulated stride
optimistic in a knowable direction. Folded into **R-16** as a required measurement axis.
Two more findings turned out to be tasks that already existed — M5 is R-17, M7 is R-8 —
which is the second time this programme has nearly opened a duplicate task; check the
board before adding one.

## R-2 — `machine` field on all 65 claims

`thesis/claims.json` has no way to say where a number came from, which is exactly
how "todo corre en la placa" survived in `README.md`.

**Precondition:** R-1 (the per-Part table is the input). — DONE 2026-07-21T18:55Z

**Landed.** All 65 claims carry `machine`; `MAX_CLAIMS_WITHOUT_MACHINE` is 0, so the
ratchet is now a hard rule. `stats-report.md` renders the value as a **Máquina**
column, which is what makes it readable rather than merely present.

Distribution, and it is the finding: **47 `both`, 13 `rtx-3090`, 3
`jetson-orin-nano-8gb`, 2 `n/a`.** Only three claims in the whole thesis were measured
wholly on the board — `P1-S1.2-zeroshot-smolvlm`, `P3-wholeframe-resolution-knee`,
`P3-E1-TRT-fps`. Everything in the Part IV/V arc is `both`, because the VLM anchor ran
on the Orin while the SAM2 carry ran on the 3090 under the rate cap. That is not a
scandal — see D-MACH.1 for why the split is sound — but «todo corre en la placa» cannot
survive it as written, which is exactly what R-6 has to fix.

Assignment was mechanical from `raw/machine-audit.json` except for 13 judgement calls
(the three `stage1-baseline` sub-phases on different hosts, the five Part II claims
that cite `runners/runs/` and so name no campaign, the two `missing` Part III claims,
and three where the off-device half was only an ssh driver). Each is listed with its
reason in the R-1 README.

`test_on_device_claims_really_are_on_device` pins the three-claim on-device set by name.
It is the value that carries the thesis premise, so it should not be able to grow
quietly.

## R-3 — `paired-binary` skips deflation

`grounding/stats.py:315` reads `b, c = claim.counts["b"], claim.counts["c"]` and
never calls `deflate_to_effective`, while `single-arm-binary` (`:334`) and
`descriptive` (`:370`) both do. Every paired McNemar p-value in the report is
therefore computed at full row count, ignoring the design effect — the p-values are
too small, in the direction that favours us.

**Expected output:** the deflation applied in the `paired-binary` branch, plus a
test in `tests/` that fails if any branch of the dispatch skips it.
**Done when:** that test exists and passes, and R-9 has regenerated the report.

**DONE.** `paired-binary` now deflates `b` and `c` onto the `n_effective` scale before
McNemar. Two further branches fixed defensively: `unpaired-binary` (no claim needs it today
— the single unpaired claim is 12 to 12 — but a branch that ignores `n_effective` is a trap
for the next claim that does) and `paired-continuous`, which now **refuses** when
`n_effective < n_rows`, because a rank test cannot be deflated by rescaling a count and
choosing which rows to drop would itself move the p-value.

`test_every_design_branch_honours_n_effective` is parametrised over every design that
consumes counts and asserts deflation moves the p-value or the interval. Verified
non-vacuous: against the pre-fix `grounding/stats.py` it fails on exactly the three broken
branches and passes on the two that already deflated.

**Impact: 20 claims moved, 0 headline changes.** The six Holm survivors are unchanged (they
sit at p ~ 1e-53 to 1e-6; no design-effect correction touches them). The real casualty is
`P3-carry-OP768-accuracy`, whose raw p goes 0.0127 to 0.0961 — nominally significant to not
— though it was never a Holm survivor. `P5.1-warm-vs-cold` goes 0.125 to 0.5 and
`E18-cold-acquire-vs-warm-oracle` 0.0625 to 0.5.

**A property worth knowing before R-4:** deflation can round a lone discordant pair to zero,
turning `p = 1` into *no test at all*. That is what moves "sin prueba posible" from 26 to 30
and it accounts for `P5.13`, `P5.17`, `P5.20` and `E19` — the contract-tie claims. It does
not manufacture a result (both readings are non-significant) and it is arguably the more
honest statement: at that many independent units there was never resolution to see a single
flip. It must be **said**, not left for a reader to discover.

## R-4 — Pseudo-replication rule for `n_effective` — DONE 2026-07-21T18:35Z

**This is the most damaging item in the repository.** Not because the correction is
large, but because of its shape.

Verified 2026-07-21, three ways:

1. `experiments/2026-07-20-n25-select/scenes_p518.json` holds 27 scenes drawn from
   **13 distinct clips**. `bike1` alone contributes 6; the wakeboard family
   contributes 7. The file's own `comment` field says so in as many words:
   "bike1 contributes 6 scenes of one recurring blue-vs-yellow rider pair".
2. Every comparable claim in the registry **is** deflated for exactly this:
   P5.14 5→3 ("cut from only THREE distinct UAV123 clips"), P5.16 5→3, P5.2a 25→23,
   P3-carry 186→93, P2 claims 439→316. Forty-nine claims carry a deflation.
3. P5.18 and P5.19 sit at **26→26**. Their `independence_note` discusses a
   *different* independence problem (re-measurement overlap with P5.16) and never
   mentions the clip clustering. P5.20 deflates 52→26 for the two-leg pairing and
   then also stops short of the clip rule.

So the rule was applied in 49 places and dropped in the 4 places where it would have
cost the headline. Whether that was motivated or merely inattentive is not
determinable and does not matter: the pattern is directionally self-serving, and an
examiner who finds it before we volunteer it will read it as concealment.
**Volunteer it in the text.**

**One correction to the audit, in our favour, and state it precisely.** The audit
says deflation makes P5.19's result "unreachable by construction". Checked: P5.19's
SWAP claim is `b=3, c=0`, which is `p=0.25` at the *full* n=26 — it was never
statistically significant, so deflation cannot demote it from significant to
non-significant. It was a **pre-registered gate** (20/26 cells), not a p-value. What
deflation removes is the bar-exact margin: 20/26 → 10/13, and 17/26 → 8/13.
Correct claim: "we could not distinguish the arms; the gate cleared at a margin that
does not survive the clip clustering."

**Expected output:** the rule written into `thesis/01-metodo-estadistico.md` (Spanish,
full diacritics, with the P5.18 bank as the worked example); `n_effective` corrected
to 13 for P5.18/P5.19/P5.20 with an honest `independence_note`; those three verdicts
and their ledger entries rewritten.
**Done when:** no claim in the registry has rows sharing a source clip without a
deflation, and a test asserts it.

### What landed (`1acb332` + follow-up)

`n_effective = 13` on six claims; `P5.19-grace-precision` **checked and left at 4**,
with the check written into its note — its four firings come from four different
clips, and "we looked and it did not need deflating" is invisible from an unchanged
number.

New `scene_set` field on `Claim`, pointing at the frozen bank. Prose can lie about
independence; this is the machine anchor, and
`test_n_effective_respects_the_distinct_clip_count` derives 13 from the bank itself
rather than hardcoding it. A second test refuses a claim drawn from a banked campaign
that omits the pointer — otherwise the first test is opt-out. Non-vacuity verified by
reverting P5.19 to 26: the check fails.

Registry `verdict` fields left as recorded (they are the historical ledger); the
corrections live in `caveats`, which the report now renders verbatim after R-12.
Ledger entries in `docs/{results,questions}/part5-anticipatory.md` and the three
experiment READMEs carry an inline correction block rather than an edit — an erased
wrong number is worse than a corrected one.

The rule and the confession are in `thesis/01-metodo-estadistico.md` under
"La unidad de independencia es el videoclip, no la escena", with the bank composition
table as the worked example, the 49-vs-4 pattern stated plainly, and the precise
statement of what deflation does and does not do to P5.19.

Two facts surfaced by the correction that were not in the original audit:

1. **P5.18 WSEL was never an inferential claim.** Against a 0.8 bar at 13 units, no
   possible result reaches alpha: `0.8^13 = 0.055` even at 13/13. The inflated n hid
   an unreachable design, not just an overstated one.
2. **Nothing significant was lost.** All six affected claims were already
   non-significant. That is the reason to make the correction without haggling: it
   costs no finding and buys the only thing a method chapter can buy, which is that
   its rules apply the same when the result is convenient and when it is not.

Still open and belongs to **R-19**: first-read surfaces (`README.md`, `CLAUDE.md`,
`HANDOFF.md`, the Part V proposal) still describe P5.19 as a YES.

## R-5 — Shadow-RG re-analysis

The shadow-RG arm was recorded and never analysed. It is now computed and should be
written up: **P5.18 n=50, b=4, c=2, p=0.6875 (44 agree); P5.19 n=52, b=3, c=2,
p=1.0 (47 agree).** Both arms agree; the contracts are statistically
indistinguishable on this data.

Note the failure mode that produced this number the first time, because it is the
reason the task exists at all: guessing the JSON field names (`shadow.pass`,
`target_id` — neither exists) gave `b=39, c=7`, a confident and completely wrong
result. Re-derive from the real schema (`meta.shadow = {acquire_s, vlm_box,
match_ious, selected}`, `selected` ∈ `{target, distractor}`) and respect leg
semantics: on the SWAP leg the *correct* pick is `distractor`.

**Expected output:** two new registry entries with these counts, and the Chapter 7
wording changed from a claimed DD-over-RG edge to "indistinguishable at this n".
**Done when:** the claims are in `claims.json` and the chapter no longer asserts a
difference the test does not support.

### What landed (2026-07-21T23:20Z) — and why the expected output was wrong too

`thesis/analyse_shadow_rg.py` re-derives everything from the committed
`results.json` files. It **reproduces the pre-recorded `b=4, c=2` (n=50) and
`b=3, c=2` (n=52) exactly**, so this correction is about definition, not
arithmetic — and the "indistinguishable at this n" wording the task asked for
would have been the third wrong answer to the same question.

1. **The pairing compares two different quantities.** DD `pass` folds in genuine
   lock, coverage, delivered IoU and carry survival; RG `selected` is selection
   only. Scoring one arm on a strictly harder criterion and calling the result a
   tie is the R-21 MISLEADING shape "two differently-defined quantities juxtaposed
   as a comparison". Not reported as a p-value anywhere.
2. **The like-for-like pairing is vacuous.** `select_p56.bind_by_caption` is string
   equality against the stored caption with an assert that exactly one matches, so
   **DD scores 48/48 and 50/50 on selection by construction** and cannot mis-select.
   That is a scope cut recorded in P5.14's README (the campaign isolates the
   delivery mechanism, not phrase understanding). No test can show DD "beating" RG
   at selection — RG fails at a task DD does not perform.
3. **What is defensible is one-directional and now registered:**
   `P5.18-shadow-rg-ceiling` **38/48** (9 of the 10 failures by abstention) and
   `P5.19-shadow-rg-ceiling` **42/50** (8 of 8 by abstention), both single-arm with
   a Wilson interval, both deflated to **n=13 clips** like every other claim on
   these cells. Wilson CI95 [0.497, 0.918] and [0.578, 0.957].
4. **It is a ceiling, not a rate.** Selecting correctly is necessary but not
   sufficient for an RG pass — the shadow never carries a track after its
   re-ground, so it is never charged coverage or IoU. RG's true pass rate is at
   most these numbers.
5. **The dropped rows are informative.** `meta.shadow` is written after the early
   `fail()` returns, so all 4 (P5.18) and 2 (P5.19) cells without one are DD
   failures. Conditioning on shadow-present drops DD's worst cells.
6. **RG is not an independent contract.** It matches its box against
   `cand_at_prompt` — DD's own maintained tracks — so its failures are re-ground
   failures plus inherited carry drift.

`P5.14-shadow-rg-disagreement` carries the same defect (`k1=10` is the
by-construction 10/10) and got the same caveat plus a corrected verdict, rather
than being deleted. Prose reworded in `docs/{results,questions,decisions}/part5-anticipatory.md`
and in the P5.14/P5.18/P5.19 experiment READMEs; `00-esquema.md` never asserted the
edge, so nothing there needed changing.

## R-6 — Correct `README.md`

Known defects. **Anchored by quoted string, not line number** — the first version of
this table cited three line numbers that did not resolve and attributed one quote to
the wrong file entirely. Corrected 2026-07-21 after the prune triage caught it; see
the note below, it is worth reading before you trust any citation in this document.

| File | Quoted text | Problem |
|---|---|---|
| `README.md` | "Todo corre en la placa, sin nube" | false as written — see R-1 |
| `README.md` | "enteramente on-device" | same |
| `README.md` | "Todo corre en una Jetson Orin Nano 8 GB a 15 W, sin nube" | same |
| `README.md` | "+22.6 pp sobre fotograma completo" | cross-machine composite (HF bf16 on the 3090 vs Q8_0 on the Orin); the same-backend figure is +21.2 pp. R-14 replaces it with a clean on-device number |
| `README.md` | "Latencia del tracker: 0.14 ms/frame" | true (`ByteTracker.update`, CPU) but sits directly below the SAM2 carry bullet at ~160 ms/frame — invariant I6 |
| `docs/_legacy/INFORME_PROGRESO.md` | "solo −7 pp son cuantización" | b=17, c=10, p=0.2478 — not distinguishable from zero. **Not in `README.md`**, which is where this table originally claimed it was |

**The note.** Three of the six anchors above were wrong when written, in the document
`HANDOFF.md` sends every new session to first. They were written from an earlier read
of `README.md` in the same session rather than re-checked at authoring time — which is
invariant **I7** ("do not trust your first read"), violated in the file that states it.
`HANDOFF.md`'s own I6 example carried the same wrong line number, copied between the
two files: the link-don't-duplicate rule in `CLAUDE.md` exists for exactly this.

Take the general lesson, not just the fix: **cite by quoted string.** Line numbers rot
silently on the next edit, and a wrong one costs a future session real time before it
concludes the citation, not the file, is broken.

**Precondition:** R-1, R-2.
**Expected output:** corrected `README.md`, full diacritics, each changed number
traceable to a claim ID.
**Done when:** every number in the front matter resolves to a registry claim.

### What landed (2026-07-21T19:40Z)

Every number in the front matter now carries its claim ID, and the block says up
front that it does. The six defects:

- The three "todo corre en la placa" sentences are **scoped, not deleted**. The
  deployed system genuinely does run on the board — E1 measured the VLM and the SAM2
  carry co-resident on the Orin at 6.15 FPS, 4980/7607 MB (`P3-E1-TRT-fps`, the one
  claim in the registry that is wholly `jetson-orin-nano-8gb` *and* load-bearing).
  What did not all run on the board is the *experimental* work. The README now says
  which is which, in a new **«Sobre las cifras»** section carrying the 47 / 13 / 3 / 2
  split and a pointer to R-1's audit and to D-MACH.1.
- `+22.6 pp` replaced with **`+21.2 pp`**, the same-backend within-sweep control
  (full-frame, no resize cap = 64.0 %, `experiments/2026-06-25-roi-crop-anchor/README.md`).
  The old figure subtracted the Orin-deployed 62.6 % baseline from a 3090-measured arm.
  R-14 can still replace it with a clean on-device number; it is no longer *wrong* in
  the meantime.
- The tracker bullet's I6 violation is fixed by stating the binding cost in the same
  breath: 0.143 ms is `ByteTracker.update` (`P3-T4a-tracker-cost`), while the carry
  step is ~162 ms (`bench.json:trt_768_cores`) and is what actually sets the cadence.
- Two defects **found while correcting, not on the list**: the carry bullet quoted
  **0.849**, which is the 1024 px number, while the *deployed* operating point is 768 px
  at **0.830** — and the registry records that gap as real (sign test, p = 0.014), so
  the README was quoting the accuracy of a configuration it does not ship. And the
  follow ceiling read "hasta **3.0 m/s**" when `E10-fast-follow-ceiling` is 3/3 at 2.5
  and **0/2 at 3.0**: the README had published the setting that failed. Both corrected.
- The HF bf16 comparison no longer reads as a win ("iguala o supera") but as
  «sin pérdida medible por la exportación», per `P2-RQ4.1-deploy-fidelity`'s caveat.

**I7, applied and worth recording.** While correcting the ROI bullet I concluded the
table's `+21.2 pp` was unsupported arithmetic and wrote a replacement around a
different baseline. It was not unsupported — the 64.0 % control is in the sweep's own
README. The table was right and the fresh read was wrong, which is the *inverse* of the
failure this section was written about. One grep before committing caught it. Re-check
the citation; also re-check your correction of the citation.

## R-7 — Claim-provenance sweep

Every number in `README.md`, `RESULTS.md` and the per-Part ledgers traced to the
artifact that produced it and tagged **VERIFIED** / **UNVERIFIED** / **CONTRADICTED**
/ **MISLEADING**. The four defects in R-6 were found by hand; there is no reason to
believe they are the only four.

**Expected output:** `thesis/provenance-sweep.md` — one row per published number:
where it appears, the artifact, the tag, and the fix if it is not VERIFIED.
**Done when:** every number in the ledgers appears in that table with a tag.

### What landed (2026-07-21T23:05Z)

Six audit agents, one per ledger (Part IV and Part V each got their own; Part V was
split at P5.12). **2320 numbers examined, 279 reported: 178 VERIFIED, 66 MISLEADING,
27 CONTRADICTED, 8 UNVERIFIED.** Frozen verbatim in `thesis/provenance-sweep.json`
and rendered by `thesis/make_provenance_sweep.py` into `thesis/provenance-sweep.md`.
The rule that made it worth running: a number is VERIFIED only against an artifact
the agent *opened*, never against another prose restatement of the same claim.

**All 27 CONTRADICTED are fixed in this pass.** The ones that cost something:

- **`P3-carry-OP768-accuracy` — my own R-6 error, and the worst of the set.** README
  said "esa diferencia es real (p = 0.014)". The deflated analysis says the opposite:
  186 tracks come from 93 sequences, so b=28, c=16, **p = 0.096**, Holm 1. The 0.014
  itself was never computable — the exact undeflated value is 0.013. Corrected in
  README.md, in the registry caveat, and in `part6-flight.md`, which had it in the
  raw-significant bucket. **R-4 deflated the numbers but nobody re-read the caveats
  written before it**, so the registry's own prose contradicted its own table.
- **E4 stage 1 was run twice and only the first run published** (`part4-end-to-end.md`).
  `stage2.log` re-ran all three gate legs before the ladder and overwrote every
  `s1-*/results.json`. Two of three legs *invert* between runs on an identical config
  (`none` PASS→FAIL, `score` FAIL→PASS), which means the run-to-run variance of one
  0.5 m/s SITL trial exceeds the effect the stage measured. Both runs now published;
  the "Fix B alone recovered 0.5" reading does not survive; `motion` is kept because
  it is the only leg that replicated, not because the rule discriminated.
- **Five stale p-values and two stale bucket sizes** in the retroactive-statistics
  section of `part6-flight.md` — written pre-R-4, quoting undeflated p. Fixed, with
  a line saying the values are post-deflation so the next reader knows which is which.
- Part I: two multipliers swapped, a tg512 figure sitting in a tg128 column, a
  tok/s·W paired with a J/tok on a different power basis, a global-config line false
  for most rows below it. Part V: a dedup mechanism credited for a flip its own
  `results.json` shows it never fired on, a service-call count off by 4x, an IoU
  floor that excluded a surviving cell, a denominator (7) present in no artifact.

**Not fixed here: the 66 MISLEADING and 8 UNVERIFIED rows.** They are the R-21 queue.
A MISLEADING row is a sentence to rewrite, not a digit to change, and several need a
decision (drop a vacuous column vs annotate it) rather than a patch. They are listed
in `thesis/provenance-sweep.md` with the fix each agent proposed.

## R-21 — The MISLEADING/UNVERIFIED queue from R-7

66 MISLEADING + 8 UNVERIFIED rows in `thesis/provenance-sweep.md`, each with the fix
its auditing agent proposed. These are sentences to rewrite, not digits to change,
and they cluster into four recurring shapes worth naming because they will recur:

1. **Cross-machine composite sold as one configuration** — e.g. "SAM2 @1024 rate-capped
   6.15 Hz" applies E1's *768* Orin measurement to a 1024 carry running on the 3090.
2. **Metric that cannot fail by construction** — `track_cov 100.0%` beside the already-
   disowned "0 track losses"; `slave_err_mean_m`; P5.12's predicted-vs-recorded n_clear.
3. **Count published without its independence unit** — cell-n headlines (P5.14 5/5,
   P5.16 4/5) where n_effective is 3, and gates no outcome could clear (P5.3/4/5).
4. **Two differently-defined quantities juxtaposed as a comparison** — 48.1 Hz renderer
   throughput vs a 20 Hz *set point* called "2.4x"; E20's 1.85 s vs E18's 4.85 s.

**Expected output:** each row either fixed in place or recorded in the sweep doc as
accepted-with-reason. **Done when:** no MISLEADING row is left unresolved in a file
the thesis cites.

## R-8 — `experiment/carla-gt-bank`

28 commits unmerged, with an orphan directory left on `main`. Either it lands or it
is retired; leaving it is how a fresh session rediscovers it as a mystery.

**Expected output:** merged, or a note in `DECISIONS.md` recording the retirement
and what was given up. Orphan directory removed either way.
**Done when:** `git branch --no-merged main` does not list it.

### What landed (2026-07-21T23:55Z) — merged, `f75b5de`

It lands rather than retires: the campaign is complete (README, runner,
`tests/test_carla_gt_bank.py`, four proof figures, ledger entries in all three
Part-VI docs) and it builds the artifact P6.2 needs. The orphan was the reverse of
the usual shape — the *artifacts* (`gt.jsonl` x25, the probe frame) were already on
`main` while the code and prose that explain them sat on the branch.

Conflicts were three-way appends in `docs/{results,questions,decisions}/part6-flight.md`:
the branch's GT-bank entries against `main`'s stats-framework and R-10 entries. Both
sides kept; nothing dropped. Verified before landing: full `pytest` green on the
merged tree, and `proof/bank-gt-overlay.png` **opened and looked at** — boxes on
real vehicles at 60 m nadir, green for high fill, blue for partially occluded, 21
on-screen targets as captioned.

**Left standing, deliberately:** three older unmerged branches, each 1–3 commits of
superseded pre-draft — `experiment/direct-delivery-select` (the P5.6 pre-reg, which
P5.14/P5.16 then ran and superseded), `experiment/vlm-vision-unfreeze` (a Part-II
draft, Part II is frozen), `v2/1-synth` ("frozen for now", Part II complete). They
are the same "fresh session rediscovers a mystery" hazard at lower stakes. Deleting
branches is not reversible from this repo alone, so it needs a human call; the
recommendation is to delete all three, since every one of them is a draft whose
question was later answered on `main`.

## R-9 — Regenerate `stats-report.md`

The report is derived. Once R-2/R-3/R-4/R-7 have changed the inputs, it must be
regenerated rather than hand-patched.

**Precondition:** R-2, R-3, R-4, R-7.
**Expected output:** `thesis/stats-report.md` + `.pdf` rebuilt from `run_stats.py`,
with the Holm family recomputed.
**Done when:** rebuilt from the current registry with no manual edits, and the
surviving-claim count is restated in `00-esquema.md`.

### What landed (2026-07-21T19:00Z)

`thesis/stats-report.md` and `.pdf` regenerated by `run_stats.py` with no hand
edits; the Holm family is recomputed over the R-7-corrected registry. Six claims
survive Holm, unchanged in membership.

`00-esquema.md` had drifted from the report in four places, all of them
pre-deflation values that the R-4 pass never propagated forward:

- The global table said 26 without-a-test and 33 unreachable-by-design. Post
  deflation they are **30** and **35**.
- The Part V post-hoc table quoted undeflated discordance for every row.
  P5.2a is b=15 c=0 p=6,10e-5 (not b=16 p=3,05e-5), P5.1 is b=2 (not 4),
  P5.19 is b=2 p=0,5 (not b=3 p=0,25), and P5.13/P5.17's single discordant cell
  collapses to zero, so their p goes from 1,0 to undefined. A line now states
  that the whole table is post-deflation and points at the report for the raw
  counts.
  > **Superseded in part by R-22 (2026-07-23).** The "P5.1 is b=2" edit above was
  > propagating a bug, not a correction. P5.1 records its discordants already at
  > clip scale (`counts["n"]=6`, `n_rows=12`), so R-3's deflation halved them a
  > second time. P5.1 is **b=4, c=0, p=0,125** — which is what its hand-written
  > caveat said all along. The other three rows in this bullet are unaffected.
- The "three corrections the re-analysis forces" list asserted that carry at 768
  **does** lose accuracy against 1024 at p=0,013. That is the same error R-7
  caught in README.md and the registry caveat: the 186 tracks come from 93
  sequences, and on that unit it is b=28, c=16, **p=0,096**, Holm 1. Rewritten,
  and the correction is dated in the text rather than silently swapped.
- The P5.19 mandatory-warning section argued from the undeflated bar-exact
  margin. It now carries the deflation: 26 cells are 13 clips, the gate becomes
  10/13 over a 8/13 baseline, and what the deflation removes is precisely the
  bar-exact margin the result was making its argument from.

Also added the missing `<!-- caption:` on the annex table, which was blocking the
`00-esquema.pdf` build outright.

## R-10 — Vacuous-metric audit

Three metrics currently report success by construction and prove nothing:

- P6.1 `slave_err_*` = 0.000 — the renderer is *told* the pose, so error cannot be
  nonzero. It measures the assignment, not the tracking.
- P6.0 "0 track losses" — was vacuous under the ByteTrack re-find bug; confirm it is
  still meaningful post-fix.
- P6.1 "48.1 Hz" — needs its measurement point stated (render loop? end-to-end?).

**Expected output:** each either given a non-vacuous definition and re-measured, or
struck from the ledger with a note saying why it could not have failed.
**Done when:** none of the three appears in the thesis without that treatment.

### What landed (2026-07-21T22:40Z)

All three were worse than the ledger said, and **two were disowned for the wrong
reason** — which is the finding worth keeping: a metric can be flagged "do not
cite" and still be misunderstood, and the flag reads as diligence either way.

1. **`slave_err_*` — vacuous, and three things the note missed.** The camera is an
   unattached `sensor.camera.rgb` (not "CARLA's free camera"), a kinematic actor, so
   the read-back is the write. Beyond that: (a) the published `0.000` **is not in the
   artifact** — `results.json` holds `1.815e-06`; the zero is the `:.3f` print format,
   so anyone grepping for the cited number fails to find it; (b) the metric reads only
   `.location`, so it is blind to rotation — and `pose_track` yaw has **one unique
   value (0.0) across all 600 ticks** because the `ATTITUDE` poll never delivered. The
   renderer was **position-slaved, not pose-slaved**, and the vacuous metric is exactly
   why nobody noticed.
2. **A non-vacuous replacement, no re-run needed.** `experiments/2026-07-20-p61-carla-renderer/pose_staleness.py`
   computes it from the committed `results.json`: consecutive identical `pose_track`
   rows are reused MAVLink samples. **60.4% of ticks (362/599) render a stale pose**,
   worst fresh-sample gap **0.547 s**, and at the observed **7.21 m/s** median that is
   **~3.9 m worst-case camera lag** (0.38 m typical). Six orders of magnitude above the
   published figure, and it fails in the right direction when the pose stream stalls.
   Ships with a `_selfcheck()` asserting the old metric is noise and the new one is not.
3. **"0 track losses" — vacuous, but NOT because of the ByteTrack bug.** The counter
   only increments when the tracker returns an empty list, needing `MAX_LOST_FRAMES=30`
   at 20 Hz = **1.5 s with no detection at all** — equally reachable before and after
   the fix, and the table proves it: the broken run (40 IDs, 64.7 px) and the fixed run
   (7 IDs, 36.0 px) **both report 0**. What makes it useless is that 1 Hz gap injection
   never produced a 1.5 s drought, and the run designed to force one (`GAP_INJECT_RUN = 3`)
   never fired under `--runs 1` — so Branch-1 is "not attempted", not "unsatisfiable".
4. **"48.1 Hz" and the withdrawn 2.4x.** Measurement point stated everywhere: render-loop
   wall throughput, 640x480, 40 vehicles, **no perception in the window** (no VLM, SAM2,
   ByteTrack or PID), no power cap, and the code has since been superseded. The
   "2.4x the P6.0 control rate" reading is **withdrawn**: sync mode delivered 600 x 0.05 s
   of sim time in 12.46 s wall, so `48.08/19.93` and `30/12.46` are the **same 2.41** —
   the clock skew restated, not headroom.

Landed in: `docs/{results,questions,decisions}/part6-flight.md`, both P6 experiment
READMEs, `thesis/00-esquema.md`, `thesis/02-metodo-multiagente.md`, the two P6
`claims.json` caveats (hence a `stats-report.md` regeneration), and `CLAUDE.md`.

## R-11 — Multi-agent development as method

The user wants the development method itself in the thesis: what changes when the
work is done by a fleet of agents under a human reviewer rather than one person.

The honest evidence is here and it cuts both ways, which is what makes it worth
writing:

- A 6-agent audit found, in one pass, provenance defects that months of solo work
  had shipped — including a headline claim that was false as written.
- The same tooling *produced* several of those defects. `b=39, c=7` came from an
  agent that guessed a schema. The Phase C camera pointed at the sky for weeks
  because logs read like success and nobody opened a frame.
- The mitigation that worked was not better prompting. It was mechanical:
  `tests/test_thesis_integrity.py`, and the "look at it" rule.

**Placement risk, decide before writing:** the TFM is about edge AI, not about
AI-assisted development. A chapter invites the objection that the thesis is about
its own methodology. A *methods subsection* plus an annex carries the same content
without moving the centre of gravity. Recommend the subsection; confirm with the
advisor before drafting long.

**Expected output:** a Spanish section (full diacritics) placed per that decision,
citing specific incidents from this repo with commit hashes, not generalities.
**Done when:** drafted, placed, and every incident it cites resolves to a commit or
an experiment README.

### What landed (2026-07-21T21:20Z)

`thesis/02-metodo-multiagente.md`. Placement went with the recommendation: a short
subsection inside Chapter 3 plus **Annex B**, not a chapter. `00-esquema.md` gained
the subsection stub, an *Anexos previstos* table (A/B/C — none existed before, and
the draft referred to "Anexo B" with nothing defining it), and the trim order now
says the subsection collapses to a paragraph before the annex is touched.

Twelve incidents, each resolving to a commit. **Eleven do; one does not** — the
51-agent / 2.3M-token fan-out lives in session telemetry outside the repo, and the
table says so in the row rather than dressing it up as evidence.

Two things the section refuses to do, both deliberate:

- **No causal claim.** There is no solo-developed control version of this thesis, so
  "multi-agent development improved X" is not defensible and the section says so
  under its own threats-to-validity heading. What is verifiable is the incident log.
- **No one-sided account.** Six incidents the method *found* and six it *produced*,
  in the same table, with a `signo` column. A section that only listed the wins would
  be advertising, and a tribunal would read it that way.

The load-bearing generalisation, and the reason this is method and not anecdote:
**verification has to be an executable artifact, not a paragraph.** The evidence is
that "do not trust your first read" was written, in capitals, in the same file that
carried three broken citations. Instructions degrade under load; a failing test does
not.

Also fixed while here: `00-esquema.md` cited `README.md` "líneas 3, 47, 48 y 50" in
two places — invariant I8 (cite by quoted string) violated in the planning document,
and stale within hours of R-6 editing those very lines.

---

## R-12 — Render `caveats` into the report

`thesis/run_stats.py` never reads the `caveats` field. Verified: `grep -c caveat
thesis/run_stats.py` returns **0**, and `grep -c definicional thesis/stats-report.md`
returns **0**. All 65 claims carry an author-written caveat — roughly 19k characters,
including "THE ONE NUMBER THAT MUST NOT BE CITED" and "lowering a threshold and then
reporting that more cells clear it is not an effect" — and **none of it reaches the
generated report.**

The disclosures were all written. The pipeline silently drops them. Anyone who diffs
`claims.json` against `stats-report.md` sees concealment where there is only a
rendering bug. ~20 lines to fix, and it is presentation-fatal until it is.

**Expected output:** caveats rendered per claim in `stats-report.md`; a test that
fails if any non-empty caveat is absent from the report.
**Done when:** that test passes.

**DONE** (`5b6f7ab`). Section `## Salvedades por afirmación` renders all 65 verbatim;
`test_every_caveat_reaches_the_report` fails if any goes missing again. Rendering them
verbatim rather than summarised is deliberate — a summary would reintroduce the same
defect in a form nobody would catch.

Landing it surfaced a second, separate defect, split out as **R-20**: the caveat text is
English inside a Spanish deliverable. That is a different bug with a different fix, so it
did not hold up the rendering.

## R-20 — Translate the 65 `caveats` to Spanish

`thesis/stats-report.md` carries `locale: es`, a Spanish title block, and a Spanish table;
as of R-12 it also carries 19,073 characters of English. Fixing this at render time was
rejected: a translation layer in `run_stats.py` means the registry and the deliverable
disagree about what the caveat says, and the registry is the source of truth. The
`caveats` fields in `thesis/claims.json` are translated in place instead.

This is the most sensitive prose in the repository — every caveat is an admission against
the claim it annotates. A translation that reads *softer* than the original is a worse
defect than the untranslated English, because the untranslated English is at least
honest. So the pass is translate-then-adversarially-verify against five named failure
modes (softening, dropped clauses, number/identifier drift, missing diacritics, meaning
inversion), not a bulk rewrite.

Numeric literals keep their `.` separator verbatim so they still match the registry counts
and the generated table; identifiers, paths, arm labels and model names stay untranslated.

**Expected output:** all 65 `caveats` in Spanish with full diacritics; the verifier's
defect list and its resolution recorded here.
**Done when:** `test_every_caveat_reaches_the_report` still passes after regeneration
(it compares registry text against report text, so a partial translation breaks it), and
an NFD fold over the report finds no unaccented Spanish.

**DONE** (`6d08507`+). 65/65 translated, three translator agents, three adversarial verifiers
on the five named failure modes.

*Verifier defects: 2, both minor, both applied.* `E14-identity-hole` — mode E, ungrammatical
`falló después esa misma pata` (missing preposition). `P5.5-select-generalization` — mode B,
the object pronoun in "two failures survived **it**" was dropped, which lost the load-bearing
point that the failures survived *the idle re-anchor* specifically. **Zero softening defects
(mode A) and zero number drift (mode C) were reported.**

*Independent mechanical checks, not delegated:* numeric-literal multisets identical
across all 65 pairs (0 drift); no `\d,\d` comma-decimal leak; length ratio ES/EN within
[0.85, 1.55] for all 65, so nothing was silently dropped or padded; a curated
unaccented-Spanish scan over the rendered report (`-ción`/`-sión` endings plus the usual
suspects, with code spans and paths stripped) returns none. `P5.18-n25-wsel` contains no
accented characters and is correct — none of its words take one.

The English originals are preserved as `caveats_en` in the registry so drift can be audited
later without git archaeology; `load_claims()` drops the field, so it is provenance and never
report content.

*Residual:* the translation was verified for meaning-preservation, not blessed by a native
reader. If a caveat later reads oddly in the defended text, `caveats_en` is the reference.

## R-13 — Detector baseline

**The premise gap, and it is worse than the SAM2 one.** Verified: a repo-wide search
for YOLO / OWLv2 / OWL-ViT / GroundingDINO across all `*.py` and `*.json` returns
**nothing**. Hits exist only in `SOURCES.md`, `archive/` and prose.

`experiments/2026-06-14-vlm-feasibility/README.md:7` opens the fork itself —
"end-to-end VLM vs. decomposed (YOLO grounding + LLM intent)" — and line 188 closes
it on latency grounds without ever building the YOLO arm. CLIP proposal scoring was
"falsified at design time", i.e. rejected without being run.

A thesis whose premise is that a 2B VLM is the right tool on a 15 W board never shows
it beats the cheap alternative at its own task. That is the first question an
external examiner asks.

Use OWLv2, not YOLOv8n — the task is referring-expression grounding, not fixed-class
detection, and YOLO would be a strawman. Both outcomes are content: either the
architecture is justified, or the thesis becomes "when is a VLM worth its cost",
which is a better thesis.

**Expected output:** an OWLv2 arm on the Orin over the P5.18 cells, same verdict
script, as a normal pre-registered campaign under `experiments/`.
**Done when:** the campaign meets the 7-item definition of done in `CLAUDE.md`.

## R-14 — ROI on-device Q8_0 re-run — best hour in the project

`P3-ROI-M2.0-512` is the largest effect in the project (85.2% IoU@0.25, p=7.2e-19)
**and the config actually deployed** — but it was measured with HF bf16 on the 3090
against a 62.6% baseline measured on the Orin at Q8_0. A cross-machine,
cross-quantisation composite standing as the headline number.

The record already flagged this: `experiments/2026-06-25-roi-crop-anchor/README.md:196-198`
names on-device Q8_0 ROI confirmation as "the one open follow-up before flipping the
deploy default". The default was flipped anyway.

`evaluate_roi` (`grounding/roi.py:125`) is already backend-agnostic; only `run_grid`
(`roi.py:201`) hardcodes the HF load. Both arms, n=439, ~51 minutes of Orin wall
time turns the headline into a paired on-device McNemar on the deployed
quantisation. `thesis/00-esquema.md:582` lists it as optional. It is not.

**Expected output:** both arms through `JetsonBackend` with per-item dumps; the
claim re-derived and `machine` set to `jetson-orin-nano-8gb`.
**Done when:** the registry entry is paired, on-device, and cites the new run.

## R-15 — Per-item jsonl in the eval harness

`grounding/eval/harness.py:34-80` writes aggregates only. That single gap is why 4 of
the 6 surviving claims are `counts_only` and cannot be re-paired or re-analysed.
~20 lines. Do it while inside R-14.

**Expected output:** per-item jsonl written by every harness run.
**Done when:** an R-14 run produces it and a claim is derived from it.

**Code landed 2026-07-21T22:35Z; DONE once the R-14 run consumed it the same day —
the done-criterion was an R-14 run, not the code, and `items-{full,roi}.jsonl`
(439 rows each) is what paired claim `P3-ROI-M2.0-512-ondevice`.**

- `EvalReport` grows `items: tuple[dict, ...]`, **always collected**, `repr=False`.
  Collection is not opt-in: a flag that defaults to off is how this gap reappears.
- `evaluate(...)` takes `items_path=` and writes jsonl there; `grounding/eval/run.py`
  pops `items` out of `asdict(report)` (so `results.json` stays aggregates-only) and
  writes `items.jsonl` beside the manifest.
- `grounding/roi.py::evaluate_roi` has its own scoring loop and needed the same
  treatment — it now emits rows carrying `win` and `pred_in_crop` alongside the
  mapped-to-full `pred`, and `run_grid` writes one `items.jsonl` per combo. Without
  this, R-14's ROI arm could not be paired against the full-frame arm at all.
- Pairing key is `image_path` + `caption`, never the index — two arms may run
  different limits or orders, and joining on position pairs the wrong rows silently.
- Unparseable predictions are **recorded, not dropped** (`pred: null`, `iou: 0.0`,
  `raw` kept). A miss that vanishes from the rows inflates any re-analysis.
- `tests/test_harness_items.py` (6 tests) is the ratchet: the rows must reconstruct
  every aggregate scalar, or the suite fails.

## R-16 — SAM2 co-residency characterisation

The audit confirmed the shape of the gap: `evaluate_roi` is backend-agnostic and
`JetsonBackend` genuinely boots `llama-server` over `ssh jetson`, so **the VLM half
has always run on the Orin.** Every P5.16/P5.18/P5.19 discovery call was real
on-device inference. The only simulated component in the whole select arc is the
SAM2 carry, rate-capped to a hardcoded constant (`replay_e18.py:46`,
`CARRY_HZ = 6.15`; `select_p53.py:84`, `CAND_HZ = CARRY_HZ / 2.0`).

**Do not do this to rescue the select result.** That result is not there to rescue —
see R-5. Re-measuring a dead claim on the right hardware buys nothing.

Do it because the on-device measurements are a first-class result:
- The `/2` assumption is wrong in the optimistic direction — two independent SAM2
  states run at **2.87 Hz per candidate, not 3.075**. Every published Part V select
  number was generated ~7% faster than the hardware delivers.
- **Memory, not rate, is the binding constraint.** llama-server holds 4.25 GB of
  7.6; each state's pruned 100-frame ring costs ~675 MB; two candidates leave
  **80 MB MemAvailable**, three leave 36 MB, swap grows 248→902 MB.
- Batching candidates as N `obj_id`s in one state gives `tick = 70 + 92n` ms against
  `162n` separate — 3.93 Hz at n=2, memory flat in n.
- E1's "co-residency costs 0 FPS" was measured against an *idle* server. Under real
  grounding load SAM2 is immune (255.0 vs 254.1 ms) but the VLM tail more than
  doubles (max 1513→3367 ms).

Reframe: not "re-run P5.19 on the Orin" but **"what does a 2B VLM plus a promptable
video tracker actually cost, co-resident, on 8 GB at 15 W?"** That is a
device-characterisation chapter in the style of the strongest existing work, and it
is publishable whichever way the numbers fall.

**Run the gate at image_size 1024, not 768** (added by R-1, finding M1). The 6.15 Hz
cap every Part IV/V campaign emulates is an E1 measurement at 768; those campaigns run
the carry at the stock SAM2.1 **1024** (`SAM2VideoPredictor.from_pretrained`, no
override). E1 recorded that 1024 «needs 1.9×» and never gated it, and E18 miscites the
cap's provenance as «640x480». So the deployed size and the evaluated size differ, and
each borrowed the favourable half of the other's measurement — 768 is the fast one,
1024 the accurate one (`P3-carry-OP768-accuracy`, exact p = 0.014). Measuring at 768
again would re-measure the wrong configuration.

**Gate it** on the batched-vs-separate mask-IoU parity test (~20 min) first: if SAM2
enforces cross-object mask constraints inside one state, the batching lever dies and
memory becomes the wall.

**These bench numbers are second-hand** — measured by an auditor in a session not
repeated. Re-measure before publishing any of them.

**Expected output:** a pre-registered campaign under `experiments/`, parity gate
first.
**Done when:** it meets the 7-item definition of done.

## R-17 — Fix the E2–E4 rig prose

The E2/E3/E4 READMEs claim "Jetson acquire not booted" / "Jetson not needed", but
`phase3_sitl.py:1203-1206` boots `JetsonBackend` unconditionally with no local-VLM
fallback. Those campaigns *did* ground through the Orin. The prose is wrong **in our
own disfavour** — but it reads as carelessness either way, and it is the same
provenance rot R-7 exists to find.

**Expected output:** corrected prose in the three READMEs, citing the line.
**Done when:** no experiment README asserts a backend the code contradicts.

### What landed (2026-07-21T19:20Z)

The root cause is a label, not three typos. In this rig `local-VLM` meant **local
carry** — `--remote-carry` off, so SAM2 stays on the 3090 — and it was read by
later READMEs as *the VLM is local*. From there E2 wrote "Jetson acquire not
booted", E3 "Jetson not needed", E4 "Jetson **not** needed", each citing the one
before it. E5 and E6 inherited the same label but happened to spell out what it
meant, which is why they are right and the first three are wrong.

`phase3_sitl.py` constructs `JetsonBackend(..., ssh_host="jetson")` with no
condition and no local fallback branch, and prints `[3] booting Jetson q8_0
server...` before every run. There is no `--remote` flag, so E2's pre-registered
instruction to "record which" path was used had exactly one possible answer.
`runs/speed-1.0/results.json` records `n_acquire_attempts: 32`, so inference ran.

Fixed in the three offending READMEs plus the four surviving ambiguous uses
(E3's and E5's config strings, E4's run line, and four lines of
`docs/results/part4-end-to-end.md`). Where the string is a *logged* config value
it is kept verbatim and annotated rather than rewritten, since the log says what
it says.

Worth keeping in the thesis: this error ran **against** us for three campaigns —
the anchor was on-device and we published that it was not.

### Outcome (2026-07-23T01:20Z) — DONE, and it corrected its own task description

Campaign: `experiments/2026-07-22-sam2-coresidency/`. Gate G0 PASS, M1/M2/M3/M4 measured on the
Orin, four proof figures, ledger rows under Part IV, registry claim `P4-R16-carry-rate-1024`.

**The headline: `CARRY_HZ = 6.15` is 2.30x optimistic**, decomposing as 1.83x image size
(768 -> 1024) x 1.26x runtime (TensorRT -> eager). Deployed per-candidate rate is **2.688 Hz**.
The E1 arm reproduces its published 6.15 exactly (6.190), so this is not drift — 6.15 described a
configuration that was never deployed. Consequence: `select_p53.py:84` sampled every 10th frame
where the board allows every 22nd offline, every 56th co-resident.

**Every numeric prediction in the section above was itself measured at 768**, and the measurements
at the deployed 1024 overturn three of them. This is worth stating plainly, because the section
was written to fix exactly this defect and then committed it:

| the audit above predicted | measured at the deployed 1024 | |
|---|---|---|
| two states run at 2.87 Hz/candidate, "not 3.075" — the `/2` is optimistic | **exactly `rate(1)/N`**: 743.2 ms vs 744.2 predicted (0.14%), 1111.6 vs 1116.3 at n=3 | **WRONG — the `/2` assumption was correct all along** |
| each 100-frame ring costs ~675 MB | **~1258 MB** (12.0 MB/frame/state measured, vs 12.58 MB for a float32 1024² frame) | wrong by 1.9x — 675 MB is the 768 figure |
| batching `tick = 70 + 92n` vs `162n` separate | `tick ~= 202 + 170n` vs `~372n` | same shape, 768 magnitudes |
| SAM2 is immune under real load (255.0 vs 254.1 ms) | **2.3x cost**, uniform across every size/ring/N | **FALSIFIED** |
| two candidates leave 80 MB MemAvailable | two candidates + VLM under load are **OOM-KILLED** at the deployed ring | worse than predicted |

So the entire error in `CAND_HZ` is the size mismatch, not the division — the opposite of what the
task said to go and confirm. And the one prediction that held qualitatively, "memory not rate is
the binding constraint", holds much harder than stated: it is not that memory gets tight at N=2,
it is that **N=2 does not run**. `PRUNE_AFTER = 32` makes the same workload survive for no measured
rate cost, which is the single most actionable output of this campaign and a **P6.2 prerequisite**
(see D-R16.2 for why it was deliberately not applied here).

**What this does NOT do:** it does not invalidate the Part IV/V select results. Those are mostly
negative, and an optimistic carry rate makes a negative harder to explain away, not easier — see
D-R16.1. R-5 already covers the select result's standing.

## R-18 — Rebalance the outline

`thesis/00-esquema.md` gives 14 pages to anticipatory grounding and half a page to
Part I. After the correction that ordering is inverted: Chapter 7 rests on **one**
surviving test (P5.2a), while Part I holds the only substantial body of evidence
measured wholly on target hardware — 15 models × 5 reps with tok/s, TTFT, J/tok and
thermals. Part I is correctly absent from `claims.json` (deterministic
characterisations, not gated proportions) but that is not a reason to under-weight it
in the document.

Also: **drop P5.12 from the survivor headline voluntarily.** Its own caveat says the
effect is "partly definicional". The headline becomes "five survive Holm, plus one
calibration correction reported separately" — and the smaller family marginally
strengthens the other five. Three auditors reached this independently.

The central argument, as the audit would write it, is a usable starting point:

> On an 8 GB Jetson Orin Nano at 15 W, the binding constraint on natural-language
> visual grounding for UAV target-following is not model accuracy but the deployment
> path and the prefill latency it induces: exporting a fine-tuned VLM to the edge
> runtime — not quantising it — costs ~30 pp of grounding accuracy, the ~4.6 s
> full-frame anchor that survives that export makes a cold acquire deliver an
> already-stale box, an ROI crop cuts that prefill 2.7× on-device, and starting the
> computation before the operator's command rather than after it removes the delivery
> lag outright (WARM 21/25 vs COLD 5/25, b=16, c=0, p=3.05e-5).

Note what it does not contain: the delivery-contract separation.

**Expected output:** a revised `00-esquema.md` whose page budget matches the
surviving evidence.
**Done when:** every chapter's length is justified by claims that survive R-9.

### Resolution (2026-07-23)

Done, but **not as written** — two of the task's three premises had expired by the
time it ran, and the deltas below say which and why.

**Premise 1, expired: "Part I holds the only substantial body measured wholly on
target hardware."** False as of 2026-07-22. R-13 and R-14 landed after this task
was drafted, and both are Holm-surviving paired results measured wholly on the
Orin (R-14 at n_effective = 316). R-16 added a deterministic on-device
characterisation of the deployed pair. So the pages freed from Ch. 7 go to **Ch. 5
(9 to 11), Ch. 4 (10 to 11) and Ch. 3 (8 to 10)** — not to Part I.

**Premise 2, rejected: "pages proportional to Holm survivors."** Applied
uniformly it condemns Ch. 6 (zero survivors, 14 of its 15 claims at n_eff <= 6)
and Ch. 8 before it touches Ch. 7, and it collides head-on with the project rule
that a well-measured negative is content. Replaced with a criterion written into
the outline: a page is justified by **a surviving inference**, by **a
well-measured negative that closes a lever**, or by **deterministic
characterisation measured on the target board** — never by effort spent or
experiments run.

**Premise 3, adopted:** P5.12 is dropped from the headline and **reported in its
own ~0.5 pp subsection** of Ch. 7, with its "partly definicional" caveat as the
subsection's point rather than a footnote. Burying a Holm survivor inside the
sim-detour paragraph was the alternative and it was worse.

The p-value quoted in the central argument above (`p=3.05e-5`) is the
**undeflated** one; the citable figure is **6.10e-05**, deflated to 23 independent
clips per invariant I2. Left in place because it is a record of what the audit
wrote, not a live surface.

**What actually changed in `00-esquema.md`** (945 lines, was 687):

- Page budget rewritten to 5/8/10/11/11/8/12/4/7/4 = **80**, unchanged total, with a "Págs. antes" column so every delta is visible. Deltas sum to zero.
- Six stale figures corrected against the post-R-13/R-14/R-16 record: 65 claims to 70, 6 survivors to 8, the ROI section's "never closed" to R-14's 85,19 % vs 63,10 % (+22,1 pp, p = 2,50e-14), the carry "~23 % optimistic" to R-16's measured **2,30x**, the Ch. 9 on-device threat narrowed to "rate and memory on the board; carry accuracy, only on the 3090", and the Ch. 10 P5.2 p-value off the forbidden one-sided undeflated 1,5e-5.
- **Three new sections for measured evidence that had no chapter.** Part I's 15-config device bench had **zero** pages despite being measured (~1,5 pp, Ch. 3, including H4 falsified and the 8 GB cliff); the OWLv2 external baseline had none (~3,5 pp, Ch. 4); R-16 had none (~1,5 pp, Ch. 5, its single home, cross-referenced from Ch. 3 rather than restated).
- **Cut order rewritten so every cut declares what is lost**, and the Ch. 6 blanket exemption **withdrawn** — it was the only chapter protected whole and it is the one without a significant result. What is protected there is its warnings, one by one. The E2-E17 compression carries a non-negotiable condition: the table keeps a **cause** column, or the cut destroys the taxonomy that is the intellectual content of those failures.
- Three new validity threats: R-13 and R-14 **share an arm** (the 63,10 % is one dump read twice, so the survivor count is optimistic); the whole re-analysis is **post-hoc** and the deflation is a judgement made after the data existed; and the instrument changed — every VLM latency before R-13 carries an uncharacterised transport component.
- Subordinate-claims table fixed: claim 3's limit said "p = 0,125", conflating the warm-start (inferential, 6,10e-05) with the select refinement (not, 0,25 / 0,5 deflated).
- Evidence-debt table: R-14's row closed, and the **ROI-grid figure row re-opened** — R-14's three figures are a two-arm paired result, not the M x resolution sweep, and do not substitute for it.

Ran as a 6-agent workflow (`wf_1cf9446a-969`, 4 inventory + 1 proposal + 1
adversarial critique, 655k subagent tokens, 0 errors). The critique returned
`NEEDS_FIXES` with 11 problems against the proposal; the fixes were adopted over
the proposal. Two of the critique's catches are worth keeping: the proposal
double-counted R-16 across Ch. 3 and Ch. 5 (~3,5 pp of duplicated figures,
against the repo's no-duplication rule), and its line numbers were unusable
because the file had already grown past them — every edit here was anchored on a
quoted string with `assert s.count(old) == 1` instead.

## R-19 — Stale-verdict sweep of the first-read surfaces

**Runs AFTER R-4, not in parallel.** R-4 changes what the verdicts say; sweeping
first means writing them twice.

Distinct from the file-prune triage, which hunts stale *instructions*. This hunts
stale *verdicts*: a recorded YES/NO that the statistical correction overturns, sitting
in a surface an agent reads before anything else and takes as settled.

The surfaces, in order of injection speed:

1. **The auto-memory index** — `~/.claude/projects/-home-gara-jetson/memory/`.
   Highest-value target and the one nothing else covers: it is outside the repo, so
   no repo sweep or test touches it, and it loads into **every** session
   automatically. Verified stale entries include P5.14 ("YES [WSEL 5/5, SWAP 4/5]",
   deflates 5→3), P5.16, P5.18/P5.19 ("clearing the bar exactly"). One reasoning
   error already corrected 2026-07-21: P5.20's cell-for-cell reproduction of P5.19
   was recorded as proving "that bar-exact YES was real" — reproduction establishes
   determinism, not truth.
2. **`CLAUDE.md`'s project-parts block** — read first by every agent, asserts Part V
   results verbatim.
3. **`docs/questions/part5-anticipatory.md`** one-line verdicts, and the matching
   RESULTS rows.

Do not delete the superseded verdicts. Each becomes "recorded as X at the time;
corrected to Y by R-4" — the correction is thesis content, and an erased wrong
verdict invites someone to re-derive it.

**Expected output:** every verdict on those three surfaces either matches the
post-R-4 registry or carries its correction inline.
**Done when:** a spot-check of 10 verdicts drawn at random across the three surfaces
finds no unqualified claim that `thesis/claims.json` contradicts.

### What landed (2026-07-21T20:25Z)

All three surfaces, correction-in-place, nothing deleted.

1. **Auto-memory** (`~/.claude/projects/-home-gara-jetson/memory/`, outside the repo and
   therefore outside every test and every future sweep — note that when you next wonder
   why a stale claim survived). Sixteen P5/P6 memories gained a
   `**CORRECTED 2026-07-21 (R-19 …)**` block; four `description:` lines were rewritten,
   because the description is what the recall index shows and a body correction under a
   headline that still says "YES" is not a correction. `MEMORY.md` gained a banner and
   six corrected hooks.
2. **`CLAUDE.md`** — the Part V block gained a *Statistical standing* paragraph naming
   the three failure shapes (never-inferential, unreachable-by-construction, no-test-ran)
   and pointing at the registry, immediately before the verdicts it qualifies.
3. **`docs/questions/part5-anticipatory.md`** — a read-this-first banner plus thirteen
   inline `> **Statistical standing (R-19)**` notes on the sections the registry
   materially contradicts.

**The shape of the defect, which is worth more than the list.** Almost nothing recorded
was factually wrong: the counts are right, the mechanisms are right, and the engineering
decisions taken on them were reasonable. What was wrong is that a **descriptive** result
was written down in the grammar of an **inferential** one — "YES", "clears", "the
contracts tie" — and then read back as settled by every later session. Three distinct
shapes: a gate no outcome could clear (P5.3/P5.4/P5.5, where even a perfect score gives
p = 0.33), a tie with zero discordant pairs (P5.10/P5.13/P5.17, where McNemar is
*undefined*, not 1.0, so no test ran at all), and a small-n win that a powered re-run
later corrected downward (P5.14/P5.16 to P5.18). The corrections say which shape each is
rather than just attaching a p-value.

**One result got stronger, and saying so is part of the job.** P5.2 (b=16, c=0,
p = 3.05e-05) survives Holm across the whole family. Every surface now points at it as
the claim the warm-start argument should rest on — a sweep that only ever downgrades
teaches the next session that statistics is a tax rather than a tool.

**Ledger `RESULTS.md` rows deliberately deferred** to R-7, which was sweeping those exact
files concurrently. Two agents editing one ledger is how a correction gets clobbered.

---

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

## In-flight at 2026-07-21T22:55Z (session ended on a token budget, not on completion)

Two jobs were running when this session stopped. Neither is finished; neither is lost.

**R-14 — RUNNING on the Orin.** Launched as:

```bash
PYTHONPATH=. nohup .venv-ft/bin/python experiments/2026-07-21-roi-ondevice/run_r14.py \
  > experiments/2026-07-21-roi-ondevice/raw/run.log 2>&1 &
```

Last seen at `84/439 parsed=84 gate_hits=60` on arm A (71% gate rate, consistent with the 63.1%
control expectation at this sample count). Arm A is ~4.3 s/sample, arm B ~2.0 s/sample, so the
whole thing is ~50 min from launch. Rows land incrementally in
`experiments/2026-07-21-roi-ondevice/raw/{items,calls}-{full,roi}.jsonl`, so a dropped tunnel
leaves a partial arm that is still analysable.

**To resume:** check `pgrep -f run_r14.py`. If the process is gone and
`experiments/2026-07-21-roi-ondevice/results.json` exists, the run completed — fill in that
campaign's `## Results (TBD)` table from it, answer RQ-R14.1/2/3, write `make_proof.py` plus the
three named figures, append RESULTS/QUESTIONS Part III, and add the registry entry. If the
process is gone and there is no `results.json`, the run died: kill any leaked
`ssh jetson 'pgrep -a llama-server'` and re-run from scratch. Do not patch a partial arm.

**R-21 — the 6-agent pass finished; its edits are committed but NOT reviewed by a second
pair of eyes.** All seven ledger files were rewritten (`README.md` plus `docs/results/part1..6`).
Five agents returned structured resolutions; the **part1 agent hit the structured-output retry
cap and returned nothing**, yet it had already edited `docs/results/part1-exploratory.md` — so
that file's 12 rows carry changes with no record of what was verified or why. Read its diff
before trusting it.

The reported corrections are substantive, not cosmetic: export deltas published with the sign
backwards (they were gains, not losses), a cross-machine ROI headline that subtracted an Orin
Q8_0 baseline from 3090 HF bf16 arms, an eyeballed "elbow" formatted as a passed gate, and two
contradictory magnitudes for the same checkpoint sitting unreconciled in one file. The agents
were instructed to verify against the artifact before rewriting and their summaries claim they
did, but **that is their own account of their work, not an audit of it**. Spot-check the
sign-flip and cross-machine claims against the `results.json` files they cite.

**CLOSED 2026-07-22.** `thesis/provenance-resolutions.json` now carries all 74 rows (70 fixed,
4 accepted with a stated reason) and `thesis/make_provenance_sweep.py` renders them in a
Resolutions section; the finding rows above them are left exactly as the agents wrote them,
because a dated audit that gets edited once its findings are fixed stops being evidence that
they were ever there. 62 resolutions were recovered from the workflow journal at
`~/.claude/projects/-home-gara-jetson/390e9ce7-d1a5-4d2c-8ca1-65a5b2caa9a6/subagents/workflows/wf_6029f03f-e03/journal.jsonl`.

The 12 part1 rows had no journal entry, so they were **reconstructed from the committed diff in
`95228e2` and the two load-bearing numbers re-derived independently** rather than taken on the
agent's word:

| check | recomputed | agent said | sweep said |
|---|---|---|---|
| Wilson 39/200 (G4 narrow miss) | [0.1461, 0.2554] | [0.146, 0.255] | [0.146, **0.257**] |
| McNemar b=17 c=10 (F16→Q8_0) | p=0.2478 | 0.248 | 0.248 |

The agent was right and it was the *sweep's own* interval that was slightly off — it recomputed
instead of copying the audit finding, which is what it was asked to do. That is evidence for the
part1 edits generally, not proof of all twelve; the other ten rows are recorded as
reconstructed-from-diff and are labelled as such in the JSON `source` field.

**R-13 — DONE 2026-07-22T22:40Z.** The VLM wins the primary comparison decisively (63.10% vs
D-full 25.74%, p=2.2e-24 deflated; vs the detector's strongest arm D-phrase 47.38%, p=2.3e-07),
so the architecture premise is now measured rather than assumed. Two findings beyond the gate:

1. **OWLv2's failure is selection, not localisation.** D-oracle 90.43% beats the VLM itself, and
   D-phrase recall@10 is 88.8% against 47.4% at top-1 — a 41.5 pp selection gap, with its rank-2
   proposal already tying the VLM's top-1. The decomposed architecture is missing a selection
   stage nobody costed, and that stage is the expensive part.
2. **The 2026-06-14 decision was right for the wrong reason.** That campaign closed this fork «on
   latency grounds alone» without running a detector. OWLv2 is 16.4x *cheaper* per call (263.5 ms
   vs 4319 ms) and 5x smaller. The rationale in that campaign is superseded by D-R13 in
   `docs/decisions/part3-permanence.md`; the decision itself stands, on quality grounds.

Recorded caveats: the registry counts use D-phrase (the strongest arm, added post-registration and
pre-scoring, declared in the README) not the weaker end-to-end D-full; D-oracle uses GT and is a
bound, never a system; the latency ratio crosses two runtimes (PyTorch fp16 vs llama.cpp Q8_0).

**Superseded pre-registration note:** `experiments/2026-07-21-detector-baseline/README.md` is
complete and committed: OWLv2 vs the deployed VLM on the Orin, with the D-full / D-head /
D-oracle decomposition that keeps it from being a strawman. It is blocked on R-14 (which supplies
the VLM comparator and is holding the board) and on installing `transformers` into the Jetson's
existing torch venv. The install path is recorded in that README; the constraint is that
`~/sam2-bench/.venv` holds the JetPack aarch64 torch wheel and no package manager may replace it.

---

# Second wave — the apparatus, R-22..R-32

Opened 2026-07-23T11:55Z. Wave one audited the claims; nobody audited the code that
computes and prints them. These are its defects.

## R-22 — Paired deflation uses the wrong denominator — DONE **P0** (2026-07-23T12:25Z)

`grounding/stats.py:333` deflates `b`/`c` against `claim.n_rows`. The single-arm
branch at `:355` deflates against `counts["n"]`. Seven paired claims record `b`/`c`
**already collapsed to the clip scale** (`counts["n"] = 6`, `n_rows = 12`, and the
`independence_note` says so: *"12 rows, 6 observations"*), so R-3's fix halves them a
second time.

Reproduce:

```
.venv-ft/bin/python -c "
import json,sys; sys.path.insert(0,'thesis')
from grounding.stats import deflate_to_effective, mcnemar
for x in json.load(open('thesis/claims.json'))['claims']:
    co = x.get('counts') or {}
    if x['design']!='paired-binary' or 'b' not in co or co.get('n') in (None, x['n_rows']): continue
    f=lambda d: mcnemar(*[deflate_to_effective(co[k], d, x['n_effective'])[0] for k in 'bc'])
    print(x['id'], 'as-is', f(x['n_rows']), 'correct', f(co['n']))"
```

| claim | report prints | correct |
|---|---|---|
| `E18-cold-acquire-vs-warm-oracle` | 0.5 | **0.0625** |
| `P5.1-warm-vs-cold` | 0.5 | **0.125** |
| `E19-motion-compensated-acquire` | *"0 pares discordantes"* (NaN) | **1.0**, b=1 |
| `E20`, `E21`, `E23` | 1.0 | 0.5 |

`thesis/stats-report.md` therefore **contradicts itself**: `:59` prints E18 at
`p=0.5, b=2, c=0` while `:171` says *"se queda en p = 0,0625 ... solo volcaron
cinco"*. The hand-written caveat is right; the generated table is wrong. Same at
`:74` vs `:201` for P5.1 — and `CLAUDE.md` has said 0.125 all along, so the repo has
been carrying both numbers.

E18 is the pivot claim of Chapter 6. p=0.5 reads *compatible with chance*; p=0.0625
reads *the floor a 6-pair design can reach — five of six flipped, six were needed*.

Blast radius, measured: **all 8 Holm survivors unchanged**; live family 34 -> 35.

`tests/test_stats.py:251` currently pins the bug — it must be corrected, not deleted.

**Done when:** the paired branch deflates against `counts["n"]` where present, the
regenerated `stats-report.md` prints 0.0625 for E18 in BOTH places, a test asserts
the table/prose agreement, and every doc quoting the six p-values is swept.

### Resolution (2026-07-23T12:25Z)

`grounding/stats.py` now reads `den = claim.counts.get("n", claim.n_rows)` in the
paired branch, with the whole diagnosis in the comment above it. Six p-values move,
exactly the six predicted: E18 0.5 -> 0.0625, P5.1 0.5 -> 0.125, E19 NaN -> 1.0, and
E20/E21/E23 1.0 -> 0.5. **All 8 Holm survivors are unchanged**, which is the point
worth stating plainly: this was a reporting defect, not a result that moved.

`DEFLATION_PROBES` was the wrong home for the regression. That list asserts deflation
**must move** the p-value, and R-22's property is the opposite — that it moves
*nothing* when b/c are already at clip scale. `tests/test_stats.py` gets a dedicated
`test_paired_deflation_measures_from_the_scale_bc_were_recorded_at` instead, pinning
both directions: `{"b": 5, "c": 0, "n": 6}` stays at 0.0625, and the same counts with
no `"n"` still deflate to 0.5 off `n_rows`.

**The fix exposed a second defect the bug had been hiding.** E19's caveat read *"UN
solo par discordante: p = 1.0 ... b=0, c=0, McNemar indefinido"* — self-contradictory
in a single sentence, and it had been in the registry for eight days. Rewritten in
both `caveats` and `caveats_en`, with the R-22 history stated rather than quietly
swapped.

**The doc sweep, in full.** Every claim's hand-written caveat was checked against its
recomputed counts, not just the six:

- The five other changed claims (E18, E20, E21, E23, P5.1) needed **no edit** — their
  caveats carried the correct numbers all along. That is the finding, not an aside:
  the prose was right and the code was wrong, for eight days, in a repository whose
  premise is that the generated artefact is the trustworthy one.
- `00-esquema.md` P5.1 row: `b = 2, c = 0, p = 0,5` -> `b = 4, c = 0, p = 0,125`, with
  a paragraph naming R-22 as the cause so the changed number is not silent.
- `00-esquema.md` Ch. 6 caveat list said the arc had *"sin prueba estadística
  posible"*. Overstated: the tests do run, they just cannot get far. Replaced with the
  actual four p-values and the reason (n = 6 needs all six pairs).
- `00-esquema.md` sim-tie prose said one discordant cell gives *"p = 0,5"*. That is
  the one-sided value in a document that reports two-sided everywhere; it is 1,0
  undeflated and undefined after deflation. Both spots rewritten.
- `00-esquema.md` bucket table 33 -> 32, with a note that the table still does not sum
  to 70 and that R-23 owns the partition.
- The R-19 resolution block above carries a `Superseded in part` note: its
  *"P5.1 is b=2 (not 4)"* edit was propagating this bug, not correcting anything.

**A test the Done-when asked for and did not get, deliberately.** A general
"caveat p-value must equal computed p-value" check flags **thirteen** claims and all
thirteen are legitimate — counterfactuals (*"even a perfect 5/5 would give p = 0.33"*),
sibling arms (P3-R13's D-full at 2.2e-24), undeflated values the same sentence goes on
to deflate, and numbers explicitly marked retired. That test would be noise with a
maintenance bill. What went into `tests/test_thesis_integrity.py` instead is the
unambiguous half:
`test_paired_caveats_do_not_contradict_their_own_discordant_counts` fails if a caveat
asserts zero discordance while the counts record some. It is exactly the shape of the
E19 defect and has no judgement call in it.

`make test`: 162 passed, 1 skipped.

## R-23 — The four claim buckets overlap and are mislabelled — DONE **P0** (2026-07-23T12:35Z)

`thesis/00-esquema.md` reports 8 + 33 + 38 + 3 over 70 claims. That sums to 82, and
recomputing from the registry gives 8 + 36 + 41 + 3 = **88** — because **29 claims
sit in two buckets at once**. A partition that double-counts 29 of 70 is not a
partition.

The labels are also wrong:

- *"33 tuvieron 0 pares discordantes"* — only **4** paired claims genuinely observed
  b=c=0 (`P1-S1.4`, `P5.10`, `P5.19-wsel-no-regression`, `P5.20-replication`). Of the
  36 with no defined p, **26 are not paired designs at all**. Four more had exactly
  one discordant pair that deflation rounded to zero, and print *"0 pares
  discordantes"* immediately followed by *"[deflactado desde b=1, c=0]"*.
- *"38 diseños no podían alcanzar alfa"* — of the 41 flagged, only **4** are gated
  paired designs no outcome could have cleared. 23 are `single-arm-binary` with no
  pre-registered gate (hardcoded `could_ever_reach_alpha=False` at `stats.py:358`,
  no power calculation), 12 are `descriptive` (`:411`, never a hypothesis by intent),
  2 are aggregate-only.

"Twelve gated designs could never have cleared" is damning and true. "38" is
refutable in a minute and takes the framework's credibility with it.

**Done when:** the buckets are disjoint and sum to exactly 70, each label says what
its bucket actually contains, `run_stats.py` computes them (no hand-counts), and a
test asserts the partition sums to `len(claims)`.

### Resolution (2026-07-23T12:35Z)

`run_stats.py` grows a `BUCKETS` list and a `bucket_of()` that returns **one** key
per claim, assigned by the first rule that fires. The order is the semantics:
specific beats generic, so *"the pre-registered gate was unreachable"* outranks
*"the test did not reject"* — the first says something about the design, the second
only about the result.

| bucket | n | what it actually contains |
|---|---|---|
| Significativas tras Holm | 8 | defensible as effects |
| Probadas, no significativas | 15 | a real contrast that did not reject |
| **Puerta pre-registrada inalcanzable por diseño** | **12** | a gate no possible outcome could clear at that n |
| Descriptivas, sin hipótesis | 12 | nothing to contrast, by design |
| Sin puerta pre-registrada, sólo intervalo | 12 | Wilson interval and nothing more |
| Pareadas sin un solo par discordante | 6 | the arms never separated in any cell |
| Sin datos crudos | 3 | in the re-run queue |
| Sólo sobreviven agregados | 2 | per-item values lost |

Sums to 70 exactly. `tests/test_thesis_integrity.py::test_the_claim_buckets_are_a_partition`
asserts the total and that the report prints each count, so the table cannot drift
from the registry again.

**One number in the task description above was itself wrong.** It said 23 claims
are `single-arm-binary` with no pre-registered gate. There are 30 single-arm claims
and **12** of them have `gate_p is None`. The 50-claim figure you get from counting
`gate_p is None` across all designs is meaningless, because paired designs never use
that field. Fixed here and in `00-esquema.md`, which had been about to inherit it.

`00-esquema.md` now carries the eight-row table, a note that the eight are disjoint
and why, and a boxed record of what the four-row version claimed. The framing that
matters is preserved rather than softened: **twelve gated designs that no outcome
could have cleared** is the sentence the chapter should carry. It is damning and
true, where "38" is refutable in a minute — and a reader who refutes it stops
believing the rest of the chapter.

The intro line *"Sobre 70 afirmaciones con puerta"* was also wrong on its face:
24 of the 70 never had anything to contrast. Corrected.

## R-24 — R-14 proof figure draws contract coords as pixels — DONE **P0** (2026-07-23T12:47Z)

`experiments/2026-07-21-roi-ondevice/make_proof.py:75-92` passes `gt` and `pred`
straight to `cv2.rectangle`. Those are contract-space [0, `COORD_SCALE`] values
(`grounding/contract.py:30`, `COORD_SCALE = 100`); the sibling `win` field is in
pixels, which is what makes the mistake invisible in the data. On a 1360x765
VisDrone frame a box at `[27, 48, 34, 65]` is a sliver in the top-left corner, and
the panel then *zooms to that sliver*.

Opened with the Read tool 2026-07-23T11:40Z. The committed
`proof/discordant-examples.png` shows: both boxes on a **tennis court** for *"The
yellow pedestrian is near the center of"*; a **grey blur** for *"The cars on the
road"*; a **blank building facade** for *"The pedestrians in red walk near the
center"*; a **flat cream gradient** for *"The yellow bus in left side"*. No green GT
box renders anywhere, though the title promises `green=GT`.

This is a live I5 violation inside the campaign that cites I5 by name, backing one
of the 8 Holm survivors. **The statistic is unaffected** — 85.19 % vs 63.10 %
re-derives from `raw/items-{full,roi}.jsonl`, 439 rows each. Only the deliverable is
dead.

Second, smaller defect: the six panels are `sort(key=roi_iou - full_iou)[:6]`, all
at delta exactly 1.0 — the best ~5 % of 112 discordant cells, captioned as a sample.

Inputs are all local: 548 frames under `data/VisDrone2019-DET/images/val/`. No GPU.

**Done when:** boxes are scaled to pixels, the regenerated figure is **opened with
the Read tool** and described in the README by what it actually shows, the panel
selection is either stated as best-case or made a stratified sample, and a mechanical
assert rejects a box whose coords are all <= COORD_SCALE on an image larger than that.

### Resolution (2026-07-23T12:47Z)

`make_proof.py` gains `to_pixels()` (contract -> pixels, `round(x * W / COORD_SCALE)`)
and two mechanical checks that run on every regeneration:

- `_assert_looks_like_pixels()` per box: fails if all four coordinates fit inside
  [0, COORD_SCALE] on a frame more than twice that size. Verified to fire on the
  exact box the old code drew — `[27, 48, 34, 65]` on 1360x765 — and to pass on its
  converted form `[367, 367, 462, 497]`.
- a flat-crop check per panel: `crop.std() > 1.0`. The old figure's cream-gradient
  panel would not have survived it.

Panel selection is now stratified: ranks 1, 23, 45, 68, 90 and 112 of the 112
discordant cells by ROI−full delta, each title carrying its rank and the suptitle
saying "stratified over all 112". The old `sort(delta)[:6]` was the top ~5 %, every
panel at delta exactly 1.0, captioned as a sample.

**Regenerated and opened with the Read tool at 2026-07-23T12:47Z.** It shows six real
aerial scenes: a crowded basketball court, two multi-lane roads, a parking row, a
crossroads, and a motion-blurred street. In four of the six the blue ROI box is on a
plausible target while the red full-frame box is on a *different object elsewhere in
the scene* — which is the b-cell mechanism made visible: the full-frame arm does not
miss by pixels, it grounds the wrong instance. Green GT appears as its own box only
where ROI IoU < 1.0; at 1.00 it is exactly under the blue box, which is the correct
appearance rather than the old failure to render. The README caption is rewritten to
this, with the retraction stated rather than the old text quietly swapped.

**The statistic never moved.** 85.19 % vs 63.10 % re-derives from
`raw/items-{full,roi}.jsonl`, 439 rows each; the drawing path was never in it. What
was dead was the deliverable, in the campaign that cites the "look at it" rule by
name, backing one of the eight Holm survivors — and its caption said "Verified by
opening the image".

## R-25 — Registry and module hygiene — DONE **P0** (2026-07-23T12:58Z)

Three small things, each of which makes a future session distrust the core:

- **`python -m grounding.stats` exits 1.** `stats.py:456` still asserts the English
  `"absence of a test"` after `eacf746` translated the reading to *"ausencia de
  prueba"*. `make test` stays green because `tests/test_stats.py` never enters that
  branch, so the module's own advertised self-check is the only thing that catches
  it, and it is broken.
- **Two Holm survivors store their achieved p-value in `gate_p`.**
  `P3-ROI-M2.0-512-ondevice` holds `2.501505063220086e-14` and `P3-R13-owlv2-vs-vlm`
  holds `2.2605981543610277e-07`, bit-identical to what `evaluate()` recomputes: the
  pre-registration was prose, so the result got written into the pre-registration
  field. Inert only because the paired branch never reads `gate_p`. Set both to null
  and add a test that no `paired-binary` claim carries one.
- **`thesis/run_stats.py:185` still hand-counts.** `71b0128` replaced *"Solo tres
  afirmaciones"* with *"Seis afirmaciones"* under a commit message saying a generated
  document should not carry a hand-counted constant. It still does; it just counts
  higher. Derive it.

**Done when:** the self-check exits 0, both `gate_p` are null with a test, and no
generated line contains a literal count.

### Resolution (2026-07-23T12:58Z)

All three, each with a test so it cannot rot back:

- **`python -m grounding.stats` exits 0.** The assertion now checks the Spanish
  *"ausencia de prueba"* and prints `o.reading` on failure.
  `test_the_stats_module_selfcheck_passes` runs it as a subprocess from the suite,
  which is the actual repair: the self-check was the only thing positioned to catch
  that drift, and nothing was positioned to catch the self-check.
- **Both `gate_p` are null.** `test_paired_claims_carry_no_gate_p` fails on any
  `paired-binary` claim that carries one. The field is inert for paired designs, so
  nothing in the numbers moves — the point is that a field meaning *"the bar we set
  in advance"* was holding *the number we got*, on two of the eight survivors.
- **The machine sentence is derived.** `on_device` and `on_device_sig` are computed
  from `claim.machine` and the Holm result, spelled through `_spell()`, and the two
  inferential ones are named by claim id instead of by a hand-typed *"(R-14) y
  (R-13)"*. `test_no_generated_report_line_hand_counts_the_registry` asserts the
  rendered sentence agrees with the registry.

## R-26 — `README.md` is stale against R-13/R-14/R-16 — TODO **P0**

The repo's front door. Last touched `95228e2` (2026-07-21); R-13, R-14 and R-16
landed 22-23 July and appear nowhere (`grep -c 'R-13\|R-14\|R-16\|OWLv2'` = 0).

- `:19` still says the 1024 carry rate *"no está medida ... plausiblemente por ~2x"*.
  R-16 measured it: 2.688 Hz, a 2.30x correction. The line also still leads with
  6.15 FPS, which R-16 retired.
- `:59` and `:91` say *"las 65 afirmaciones"*. The registry holds 70.
- The machine table at `:62-67` reads 47/13/**3**/2. The registry says 47/15/**6**/2
  — it under-reports the on-device claims by half, which is the exact axis the whole
  first wave was about.
- `:51` still leads with the superseded `P3-ROI-M2.0-512` and +21.2 pp, while
  `00-esquema.md:415` says the headline is now the on-device +22.1 pp.

R-6's done-criterion was *"every number in the front matter resolves to a registry
claim"*. It did, on 2026-07-21. No task owned the re-sweep after new claims landed.

**Done when:** every number in `README.md` resolves to a current registry claim, and
a test asserts the claim count and machine table are generated, not typed.

## R-27 — `P3-E1-TRT-fps` never marked superseded — TODO **P0**

R-14 wrote a supersede marker into the verdict of the claim it replaced. R-16 wrote
none. `P3-E1-TRT-fps` still reads headline *"TensorRT fp16 lifts the co-resident
carry rate 4.89 -> 6.15 FPS"*, verdict `PASS`, `machine: jetson-orin-nano-8gb`, and
is pinned by name in `tests/test_thesis_integrity.py:163` — for a configuration
(`image_size` 768, **idle** server) that R-16 proved was never deployed.
`experiments/2026-07-22-sam2-coresidency/README.md:278` states flatly: *"E1's
'co-residency costs 0 FPS' is falsified."*

The supersede marker went on the number that got better and not on the one that got
worse. That asymmetry is the part worth noticing.

**Done when:** the claim carries a supersede marker naming `P4-R16-carry-rate-1024`,
and a test asserts that a claim whose successor exists cannot read `PASS` unqualified.

## R-28 — The defended sentence claims *select* — **AUTHOR**

`thesis/00-esquema.md:53-57` defends spending the idle window to keep candidates
alive and *"limitarse a **seleccionar**"*. The maintain-and-deliver half is carried
by P5.2a (p=6.10e-05, survives Holm). The **select** half has produced no inferential
result in eight campaigns — and from P5.13 onward the DD arm *cannot mis-select by
construction*: `experiments/2026-07-19-realvid-dd-select/select_p56.py:87`
`bind_by_caption` is string equality plus `assert len(matches) == 1`.

That is a **disclosed** scope cut — the docstring says so, and
`thesis/analyse_shadow_rg.py:11` says *"DD cannot lose on selection"*. What never
happened is propagating it to the sentence the thesis defends.

Prepared recommendation, for the author to accept or reject: re-scope to *mantener y
entregar sin latencia de adquisición*. Everything surviving supports that; Chapter 7
becomes a well-measured negative about selection instead of a weak positive.

**Done when:** the author has decided, and the sentence and Chapter 7 framing match
the decision.

## R-29 — `n_effective` = 13 vs the measured ICC — **AUTHOR**

Collapsing P5.19's 26 cells to 13 clips assumes cells within a clip are perfectly
correlated. Measured, they are not: `bike1`'s six SWAP cells are `[1,1,0,1,0,1]`,
`car9`'s four are `[0,1,1,0]`. A one-way ANOVA ICC over the committed `results.json`
gives roughly 0.13-0.25, so deff ~ 1.1-1.5 and n_eff ~ 18-24, not 13. Only 5 clusters
are non-singleton, so the estimate is noisy — that caveat is part of the finding.

It has a consequence: `min_successes_for_gate(26, 0.8) = 25` is reachable while
`0.8^13` is not, so the deflation *created* the unreachability that `R-4` describes
as having been hidden by it.

Invariant I2 forbids moving to the less conservative number. The prepared
recommendation is therefore: **keep 13 as citable**, put the measured ICC in the
`independence_note`, and give the method chapter a paragraph. That turns the most
aggressive and most probe-able judgement in the framework from unexamined into
calibrated.

**Done when:** the author has decided whether to keep, calibrate or revise.

## R-30 — Holm family boundary + undisclosed dependencies — **AUTHOR**

Global family of 34 live p-values gives 8 survivors; per-Part families give 10. The
two extras are `P5.15-plain-carry-survival` (p=0.0029) and `P2-RQ4.1-deploy-fidelity`
(p=0.0355) — the latter being the claim that the Part I fidelity catastrophe is
eliminated. Counter-argument to record: at m=3..7 per part, per-Part Holm keeps every
uncorrected-significant claim, i.e. it barely corrects at all. Part V (m=15) is the
only family where it still bites.

Two dependencies inflate the family either way:

- `P3-ROI-M2.0-512` and its own declared on-device replacement are both counted.
- `P3-R13-owlv2-vs-vlm`'s VLM arm **is** R-14's arm A — the same `items-full.jsonl`,
  same k. Two of the 8 survivors share a measurement.

`00-esquema.md:794-804` discloses the R-13/R-14 shared arm. It does not disclose the
ROI double-count, and `stats-report.md` — the file the project's own rules point
readers at — discloses neither.

Prepared recommendation: keep the global family, state the choice in two sentences in
`01-metodo-estadistico.md`, report per-Part as a declared sensitivity analysis, and
render both dependency notes into `stats-report.md`.

**Done when:** the author has picked the family, and both dependencies appear in the
generated report.

## R-31 — Retire or re-run P3-T2 / P3-T3 — **AUTHOR**

Both are `GATE PASS` on prose alone, no raw data, and both are Chapter 5 spine.
`thesis/rerun-backlog.md` already argues against re-running: T2 is one scripted clip
= one Bernoulli draw, and *"regenerar el vuelo único no hace la afirmación
defendible; solo la haría citable, que es distinto y peor"*.

Separately, and this is a plain defect rather than a judgement: **all three backlog
commands are fiction.** `grounding.eval.score_clips` does not exist (`grounding/eval/`
holds `backends`, `harness`, `parity`, `run`); `runners/run_phase_c.py` has no
`--arms` and no `--reps` (its flag is `--runs`) and contains zero references to CARLA.
`rerun-backlog.md:16` also still says *"Son tres sobre 65"*.
`test_missing_claims_declare_a_rerun` asserts only that a `rerun` key is present —
never that it resolves.

**Done when:** the author has said retire-or-run; the commands either work or are
replaced by an honest "no runnable command exists, here is what would have to be
built"; and the test checks resolvability.

## R-32 — Spot-check the assertion-only DONEs — TODO P1

Eight of the 21 first-wave tasks are artifact-backed (R-1, R-2, R-3, R-5, R-8, R-9,
R-12, R-15) — the statistics and the survivor set reproduce. The rest are the agents'
word about their own work. Ranked by what breaks if the word was wrong:

1. **R-19** (`:987`). Its done-criterion is literally *"a spot-check of 10 verdicts
   drawn at random"*. No record of that spot-check exists. Run it and write the
   result into the row — it is the criterion the task chose for itself.
2. **R-7** (`:362`). *"Done when: every number in the ledgers appears in that table
   with a tag."* 279 rows delivered of 2320 numbers examined. 88 % were dropped as
   clean without being recorded as such.
3. **R-21** (`:420`, `:1080`). 74 rows closed: 62 recovered from a workflow journal,
   12 reconstructed from the diff, exactly 2 independently re-derived. The file itself
   says *"that is their own account of their work, not an audit of it"* three lines
   before declaring CLOSED. Re-derive 5 from the cited `results.json`.
4. **R-16 raw edited after DONE** (`81df727`). 30 rows across two committed
   `raw/*.jsonl` had their `carry` label rewritten *after* `6073cf5` recorded R-16
   DONE. Labels only, timings untouched — but raw files are supposed to be immutable
   evidence, and this is the second wave's own campaign.

**Done when:** each of the four has a recorded spot-check result, pass or fail.
