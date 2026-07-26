# HANDOFF — how this project survives across sessions

Read this before doing anything else. Then read `thesis/REMEDIATION.md` and work
the first task that is not `DONE`.

`thesis/REMEDIATION.md` carries only the open work. The closed waves (R-1..R-44,
R-46, R-47, R-52..R-54) moved to `thesis/remediation-archive/wave*.md` on
2026-07-26 — open those only to audit history or to cite a closed task's original
write-up, never as part of the entry protocol.

This file exists because the remaining work is a **months-long programme across
many conversations**, and a conversation is not a durable medium. Context gets
compacted, sessions end mid-task, and a fresh session confidently re-litigates a
decision that was settled three weeks ago. The repository is the memory; a chat is
not.

## The three layers, and why it is not one file

| Layer | File | Changes | Holds |
|---|---|---|---|
| Ideals | `HANDOFF.md` (this file) | rarely | the invariants and the session protocol |
| State | `thesis/REMEDIATION.md` | every session | task list, status, what is next |
| Enforcement | `tests/test_thesis_integrity.py` | when a rule becomes checkable | the invariants that a machine can check |

They are split because they change at different rates. Mixing a stable
constitution with a volatile to-do list means the constitution gets churned in
every diff and stops being read. And the third layer is the one that actually
works: **a doc asks nicely, a test refuses to go green.** Anything that can be
moved from layer 1 to layer 3 should be.

`CLAUDE.md` remains the project map and the lab-notebook rules. This file does not
replace it; it governs the remediation programme specifically.

## Invariants

Numbered so a commit message or a task can cite one.

**I1 — No claim without provenance.** Every entry in `thesis/claims.json` points at
evidence that exists on disk, or is marked `data_status: missing` and carries the
command that would regenerate it. *Enforced:* `test_data_paths_exist`,
`test_missing_claims_declare_a_rerun`.

**I2 — `n_effective` may only ever deflate, and must explain itself.** Six clips
times two repetitions is six observations. If `n_effective < n_rows`, the reason is
written in `independence_note`. Inflating `n_effective` to reach significance is the
one thing `thesis/01-metodo-estadistico.md` forbids outright. *Enforced:*
`test_n_effective_never_exceeds_n_rows`, `test_deflated_claims_explain_themselves`.

**I2b — the one exception: a measured ICC may raise `n_effective`, and only
mechanically.** R-29 (author decision, 2026-07-23) replaced the collapse-to-clusters
rule with a design-effect correction `deff = 1 + (n0 - 1) * ICC` on the 14 claims
deflated for *clustering*. Deflation uses the **upper 95 % bound** on the ICC, never
the point estimate, so few clusters keep `n_effective` near the collapse; the
collapsed value stays published as `icc.collapsed_floor`; claims deflated for
*determinism* are untouched. This is survivable only because the number is arithmetic
rather than taste — do not hand-edit an `n_effective` that carries an `icc` block.
*Enforced:* `test_icc_calibrated_n_effective_is_derived_not_chosen`, which recomputes
it from the stored inputs.

**I3 — Every number records the machine that measured it.** The thesis premise is
edge deployment on a Jetson Orin Nano 8 GB at 15 W. A number measured on the RTX
3090 does not support that premise. Using the workstation for ablations is fine and
normal; **not saying so is not.** *Enforced:* `test_machine_field_coverage_ratchet`
(a ratchet — see below).

**I4 — An underpowered negative is not a finding.** A NO from a design that could
never have reached alpha is evidence of absence of *experiment*, not absence of
effect. `thesis/stats-report.md` marks reachability per claim; a claim whose design
was unreachable may not be written up as a result without that caveat attached.

**I5 — Look at it.** Any claim about what a render, sim, camera feed, overlay or
clip *shows* is unverified until a frame has been opened with the Read tool. This is
already a `CLAUDE.md` rule; it is repeated here because it has been violated before
and cost a retracted result (the Phase C camera pointed at the sky for weeks while
the logs read like success).

**I6 — True in isolation is not true in context.** Check the paragraph, not just the
number. `README.md` reports "Latencia del tracker: 0.14 ms/frame"; that figure is
correct (`ByteTracker.update`, on CPU) and sits one bullet below the SAM2 carry line,
which is roughly 160 ms/frame. Both numbers are honest. The passage they form is not.
When auditing, read the surrounding claim, not the cell.

**I8 — Cite by quoted string, not by line number.** Line numbers rot silently on the
next edit, and a stale one costs a future session real time before it works out that
the citation is broken rather than the file. This invariant was earned the hard way:
the first version of I6 above cited `README.md:47` for a line that is at 49, and
`thesis/REMEDIATION.md` R-6 attributed a quote to `README.md` that lives in
`docs/_legacy/INFORME_PROGRESO.md` — three bad anchors, written the same day, in the
two documents a new session reads first.

**I7 — Do not trust your first read of someone else's schema.** Guessing a JSON
field name yields a confident, precise, wrong number. Verified in this repo: an
attempt to recompute the shadow-RG arm guessed `shadow.pass` and `target_id`,
neither of which exist, and produced `b=39, c=7` instead of the true `b=4, c=2`.
Print the schema first. A number you cannot re-derive twice is not a number.

## Ratchets

Some invariants are not satisfied yet. Making them hard assertions today would leave
`make test` red, and a permanently red suite trains everyone to ignore it. Those are
written as **ratchets**: the test asserts the violation count has not grown past a
recorded ceiling, and *fails with a congratulation* when you have improved on it,
telling you to lower the ceiling.

Fix some, lower the number, commit. Never raise one — a rising ceiling is exactly
the regression the file exists to catch.

## Session protocol

**On entry**

1. Read this file and `thesis/REMEDIATION.md`.
2. Run `make test`. Green is the precondition for starting work, not a nice-to-have.
3. Pick the first task that is not `DONE` and whose preconditions are met. Do not
   re-plan the programme; if the plan looks wrong, say so and change it deliberately
   rather than drifting.

**On exit** (or when the context is about to compact)

1. Update the task's status and its `Evidence` cell in `thesis/REMEDIATION.md`.
   A task is `DONE` only when its stated done-criterion is mechanically satisfied.
2. Commit. An uncommitted improvement does not survive a session.
3. If blocked, write the blocker into the task row. A blocker discovered and not
   written down is rediscovered from scratch later, which has already happened here.

## What good looks like

The programme is finished when: every claim in the registry carries a machine and
resolves to evidence; every number in `README.md` and the ledgers is traceable;
the thesis chapters are written from the corrected claim set; and
`tests/test_thesis_integrity.py` has no ratchets left above zero.

**The last of those four no longer discriminates** (R-48, 2026-07-25): the only ratchet
ever written, `MAX_CLAIMS_WITHOUT_MACHINE`, was closed on 2026-07-21, so the condition is
already satisfied and proves nothing. Do not quote it as evidence the programme is done
until R-48 replaces it with a criterion that still has teeth.

**Where the work is, as of 2026-07-26.** R-1..R-44, R-46, R-47 and R-52..R-54 all read
`DONE`; the open tasks are R-45, R-48, R-49, R-50, R-51, R-55 and the W series, and they
are the whole of `thesis/REMEDIATION.md` now that the closed waves are archived. The third condition above —
writing the chapters — is **deliberately not started**: it waits on the supervisor
confirming the thesis scope. Experiments continue in the meantime, and note the standing
cost that R-39 exists to catch: every new experiment registered inside a Part re-runs
Holm over every claim already published in that Part, and one claim has already been
lost that way.
