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
| R-1 | Scope + disclosure decision on which machine ran what | R-2, R-6 | TODO |
| R-2 | `machine` field on all 65 claims | R-6, R-9 | TODO |
| R-3 | Fix `paired-binary` skipping deflation in `grounding/stats.py` | R-9 | **DONE** |
| R-4 | Apply the pseudo-replication rule to `n_effective` | R-9 | TODO |
| R-5 | Shadow-RG re-analysis + Chapter 7 rewording | — | TODO |
| R-6 | Correct `README.md` | — | TODO |
| R-7 | Claim-provenance sweep of every published number | R-9 | TODO |
| R-8 | Merge or retire `experiment/carla-gt-bank` | — | TODO |
| R-9 | Regenerate `stats-report.md` from the corrected registry | — | TODO |
| R-10 | Vacuous-metric audit | R-7 | TODO |
| R-11 | Thesis section: multi-agent development as method | — | TODO |
| R-12 | Render `caveats` into `stats-report.md` | R-9 | **DONE** `5b6f7ab` |
| R-13 | Detector baseline (OWLv2 on the Orin) | — | TODO |
| R-14 | ROI on-device Q8_0 re-run | R-9 | TODO |
| R-15 | Per-item jsonl in `grounding/eval/harness.py` | R-14 | TODO |
| R-16 | SAM2 co-residency characterisation (reframed campaign) | — | TODO |
| R-17 | Fix E2–E4 rig prose | R-7 | TODO |
| R-18 | Rebalance `thesis/00-esquema.md` to the surviving evidence | R-9 | TODO |
| R-19 | Stale-verdict sweep of the first-read surfaces | after R-4 | TODO |
| R-20 | Translate the 65 `caveats` to Spanish | R-12 | **DONE** |

R-12..R-18 come from the sufficiency audit (`wf_b81c3191-d12`, 6 agents,
2026-07-21T21:05Z). **Verdict: the thesis is sufficient — YES, without running a
single new experiment.** Six defensible contributions survive the correction, four
measured on the Orin. What is not sufficient is `thesis/00-esquema.md`, which gives
14 pages to anticipatory grounding (now resting on one surviving test) and half a
page to Part I (the only large body of evidence measured wholly on target hardware).
The work is a rewrite plus three targeted runs, not a rescue.

---

## R-1 — Scope + disclosure decision

The thesis says the system runs on the Jetson. Part V ran its tracker on the RTX
3090. Both facts are fine; the gap between them is not documented, and until it is,
every downstream correction is guesswork about what the claim even is.

Two separable claims, and they need separate answers:

- **A. The deployed system runs on-device.** Probably already true — E1 measured
  SAM2-TensorRT at 6.15 FPS co-resident with the VLM on the Jetson. Needs
  confirmation, not a port.
- **B. Every experiment ran on-device.** False, and does not need to be true.
  Ablations on a workstation are ordinary practice. Undisclosed ones are not.

**Expected output:** `experiments/2026-07-2x-machine-disclosure/README.md` — a
per-Part table of which machine measured what, the decision on whether any Part V
result needs re-measuring on-device, and the rationale for whatever is *not*
re-measured.
**Done when:** that README exists and every Part has a row.

## R-2 — `machine` field on all 65 claims

`thesis/claims.json` has no way to say where a number came from, which is exactly
how "todo corre en la placa" survived in `README.md`.

**Precondition:** R-1 (the per-Part table is the input).
**Expected output:** every claim in `thesis/claims.json` carries `machine` ∈
`{jetson-orin-nano-8gb, rtx-3090, both, n/a}`, and
`MAX_CLAIMS_WITHOUT_MACHINE` in `tests/test_thesis_integrity.py` is lowered to 0.
**Done when:** `make test` is green with the ceiling at 0.

Partial credit counts — lower the ceiling to whatever you reach and commit. That is
what the ratchet is for.

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

## R-4 — Pseudo-replication rule for `n_effective` — HIGHEST PRIORITY

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

## R-7 — Claim-provenance sweep

Every number in `README.md`, `RESULTS.md` and the per-Part ledgers traced to the
artifact that produced it and tagged **VERIFIED** / **UNVERIFIED** / **CONTRADICTED**
/ **MISLEADING**. The four defects in R-6 were found by hand; there is no reason to
believe they are the only four.

**Expected output:** `thesis/provenance-sweep.md` — one row per published number:
where it appears, the artifact, the tag, and the fix if it is not VERIFIED.
**Done when:** every number in the ledgers appears in that table with a tag.

## R-8 — `experiment/carla-gt-bank`

28 commits unmerged, with an orphan directory left on `main`. Either it lands or it
is retired; leaving it is how a fresh session rediscovers it as a mystery.

**Expected output:** merged, or a note in `DECISIONS.md` recording the retirement
and what was given up. Orphan directory removed either way.
**Done when:** `git branch --no-merged main` does not list it.

## R-9 — Regenerate `stats-report.md`

The report is derived. Once R-2/R-3/R-4/R-7 have changed the inputs, it must be
regenerated rather than hand-patched.

**Precondition:** R-2, R-3, R-4, R-7.
**Expected output:** `thesis/stats-report.md` + `.pdf` rebuilt from `run_stats.py`,
with the Holm family recomputed.
**Done when:** rebuilt from the current registry with no manual edits, and the
surviving-claim count is restated in `00-esquema.md`.

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
