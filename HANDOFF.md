# HANDOFF: la entrada de cada sesión

Lee este archivo antes de cualquier trabajo.

El trabajo de la tesis dura meses y cruza muchas conversaciones. Una conversación se compacta o termina a mitad de una tarea, y una sesión nueva vuelve a discutir una decisión cerrada. El repo es la memoria, y el chat no.

| Capa | Archivo | Guarda |
|---|---|---|
| Ideales | `HANDOFF.md` | los invariantes y la entrada de una sesión |
| Comprobación | `tests/test_thesis_integrity.py` | los invariantes que una máquina comprueba |

Un doc pide, y un test se niega a pasar. Un invariante que una máquina puede comprobar pasa al test.

El estado del trabajo vive en el mapa `Mapa: escribir y entregar la tesis` (#10). `CLAUDE.md` es el mapa del repo y las reglas del cuaderno.

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

**I8 — Cita por un texto entre comillas, no por un número de línea.** Un número de línea se pudre en silencio con la edición siguiente. Una sesión futura pierde tiempo antes de ver que la cita está rota, y no el archivo.

**I7 — Do not trust your first read of someone else's schema.** Guessing a JSON
field name yields a confident, precise, wrong number. Verified in this repo: an
attempt to recompute the shadow-RG arm guessed `shadow.pass` and `target_id`,
neither of which exist, and produced `b=39, c=7` instead of the true `b=4, c=2`.
Print the schema first. A number you cannot re-derive twice is not a number.

## La sesión

1. Lee este archivo.
2. Corre `make test`. Una suite en verde es la condición para empezar.
3. Abre el mapa (#10), y trabaja un ticket con `/wayfinder`.
4. Haz el commit de cada cambio con la skill `flujo-git`. Un cambio sin commit no sobrevive a la sesión.
5. Escribe un bloqueo en su ticket. Un bloqueo sin escribir se descubre otra vez desde cero.
