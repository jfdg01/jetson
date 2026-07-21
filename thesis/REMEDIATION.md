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
| R-3 | Fix `paired-binary` skipping deflation in `grounding/stats.py` | R-9 | TODO |
| R-4 | Apply the pseudo-replication rule to `n_effective` | R-9 | TODO |
| R-5 | Shadow-RG re-analysis + Chapter 7 rewording | — | TODO |
| R-6 | Correct `README.md` | — | TODO |
| R-7 | Claim-provenance sweep of every published number | R-9 | TODO |
| R-8 | Merge or retire `experiment/carla-gt-bank` | — | TODO |
| R-9 | Regenerate `stats-report.md` from the corrected registry | — | TODO |
| R-10 | Vacuous-metric audit | R-7 | TODO |
| R-11 | Thesis section: multi-agent development as method | — | TODO |

Tasks derived from the sufficiency audit (`wf_b81c3191-d12`, 4/5 auditors returned
at time of writing) get appended as R-12+ when it lands.

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

## R-4 — Pseudo-replication rule for `n_effective`

Twenty-seven scenes drawn from thirteen distinct clips is not n=27. The registry
does not currently encode the rule that decides this.

**Expected output:** the rule written into `thesis/01-metodo-estadistico.md` (in
Spanish, with the worked example), and `n_effective` + `independence_note` updated
for every claim it touches.
**Done when:** `test_deflated_claims_explain_themselves` passes and every claim
whose rows share a source clip has `n_effective < n_rows`.

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

Known defects, all in the Spanish front matter:

| Line | Text | Problem |
|---|---|---|
| 3 | "Todo corre en la placa, sin nube" | false as written — see R-1 |
| 17 | "enteramente on-device" | same |
| 42 | "Todo corre en una Jetson Orin Nano 8 GB a 15 W, sin nube" | same |
| 46 | "solo −7 pp son cuantización" | b=17, c=10, p=0.2478 — not distinguishable from zero |
| 47 | "+22.6 pp" | cross-machine; the same-backend figure is +21.2 pp |
| 47 | "Latencia del tracker: 0.14 ms/frame" | true (`ByteTracker.update`, CPU) but sits beside the SAM2 carry line at ~160 ms/frame — invariant I6 |

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
