#!/usr/bin/env python3
"""Regenerate the retroactive statistics report and its figure.

    .venv-ft/bin/python thesis/run_stats.py

Reads the claim registry at thesis/claims.json, runs the test each claim's
DESIGN calls for (see grounding/stats.py), and writes:

    thesis/stats-report.md          the table, with Holm-corrected p-values
    thesis/proof/stats-power.png    which designs could ever have reached alpha
    thesis/proof/stats-forest.png   effect sizes with 95% Wilson intervals

The report is a derived artifact. Edit claims.json, never the report.

Every claim in the registry carries `data_status`. Claims marked `missing` are
not tested; they are listed in the backlog section with the command that would
regenerate them. That list is the honest output of this script and the reason it
prints a non-zero count at the end.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from grounding.stats import (  # noqa: E402
    Claim, deflate_to_effective, evaluate, holm_bonferroni,
    min_discordant_for_significance, wilson_ci,
)

THESIS = Path(__file__).resolve().parent
REGISTRY = THESIS / "claims.json"
PROOF = THESIS / "proof"

# The registry keys stay English and code-like so they are stable identifiers;
# only the rendered table is Spanish. A Spanish table with English cells reads
# as a translation someone abandoned halfway.
MACHINE_ES = {
    "jetson-orin-nano-8gb": "Jetson",
    "rtx-3090": "3090",
    "both": "**ambas**",
    "n/a": "—",
}

DESIGN_ES = {
    "paired-binary": "binario pareado",
    "single-arm-binary": "binario de un brazo",
    "unpaired-binary": "binario no pareado",
    "paired-continuous": "continuo pareado",
    "descriptive": "descriptivo",
}

# R-23. The report used to print four overlapping buckets that summed to 88 over
# 70 claims, because "no defined p" and "could never reach alpha" are the same
# claims twice for 29 of them. Worse, both labels were wrong about their own
# contents: "33 had 0 discordant pairs" was true of 4, and "38 designs could
# never reach alpha" folded twelve genuinely-unreachable gates together with 23
# arms that never had a gate at all and 12 that were descriptive by intent.
# Twelve gated designs that no outcome could have cleared is the damning, true
# sentence; 38 is refutable in a minute and takes the framework down with it.
#
# So: ONE bucket per claim, assigned by the first rule that fires, and the order
# below IS the semantics. Specific beats generic — "the gate was unreachable"
# outranks "the test did not reject", because it says something about the design
# rather than about the result.
BUCKETS = [
    ("sin-datos", "Sin datos crudos, en cola de re-ejecución",
     "No hay fichero por elemento. No se defienden."),
    ("holm", "Significativas tras corrección de Holm",
     "Se pueden defender como efectos."),
    ("puerta-inalcanzable", "Puerta pre-registrada inalcanzable por diseño",
     "Corrió una prueba contra una puerta que NINGÚN resultado posible habría "
     "superado a esa n. El fallo es del diseño, no del sistema."),
    ("probada-no-sig", "Probadas, no significativas",
     "La prueba corrió y no rechazó. Es el resultado honesto de un contraste real."),
    ("sin-discordancia", "Pareadas sin un solo par discordante",
     "Los brazos no se separaron en ninguna celda, luego no hubo contraste. "
     "No es equivalencia demostrada: es ausencia de prueba."),
    ("descriptiva", "Descriptivas, sin hipótesis pre-registrada",
     "Nunca hubo nada que contrastar, por diseño. Se citan como medidas."),
    ("sin-puerta", "Sin puerta pre-registrada; sólo intervalo",
     "Se reporta el intervalo de Wilson y nada más. Un umbral elegido después "
     "de ver el número no es una puerta."),
    ("solo-agregados", "Sólo sobreviven agregados",
     "Los valores por elemento se perdieron; ninguna prueba es posible."),
]


_NUM_ES = {0: "Ninguna", 1: "Una", 2: "Dos", 3: "Tres", 4: "Cuatro", 5: "Cinco",
           6: "Seis", 7: "Siete", 8: "Ocho", 9: "Nueve", 10: "Diez"}


def _spell(n: int) -> str:
    """Small counts read better spelled out in Spanish prose; big ones as digits."""
    return _NUM_ES.get(n, str(n))


def bucket_of(claim: Claim, outcome, rejected: bool) -> str:
    """Which single bucket this claim belongs to. See BUCKETS for the order."""
    if claim.data_status == "missing":
        return "sin-datos"
    if rejected:
        return "holm"
    has_p = outcome.p_value == outcome.p_value  # not NaN
    if has_p:
        return "probada-no-sig" if outcome.could_ever_reach_alpha else "puerta-inalcanzable"
    if claim.design == "descriptive":
        return "descriptiva"
    if claim.design == "single-arm-binary" and claim.gate_p is None:
        return "sin-puerta"
    if claim.design == "paired-binary":
        return "sin-discordancia"
    return "solo-agregados"


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%MZ")


# R-26. The front-door README carried a hand-typed machine table and a hand-typed
# claim count. R-6 swept them once on 2026-07-21 and no task owned the re-sweep, so
# by 23 July it said "65 afirmaciones" against a registry of 70 and 47/13/3/2
# against a real 47/15/6/2 — under-reporting the wholly-on-device claims by half,
# which is the exact axis the first remediation wave was about. Generated now, with
# a test that fails if the block drifts from the registry.
MACHINE_ROWS = [
    ("both", "**ambas** (anclaje VLM en la Orin, arrastre SAM2 en la 3090 con tope de tasa)"),
    ("rtx-3090", "RTX 3090 (ablaciones, referencia de fidelidad HF bf16, simulador, generación de escenas)"),
    ("jetson-orin-nano-8gb", "Jetson Orin Nano, íntegramente"),
    ("n/a", "sin máquina (sin datos)"),
]
MACHINE_BEGIN = "<!-- BEGIN generated: machine-table -->"
MACHINE_END = "<!-- END generated: machine-table -->"


def machine_table(claims: list[Claim]) -> str:
    """The README machine table, rendered from the registry."""
    counts = {key: sum(1 for c in claims if c.machine == key) for key, _ in MACHINE_ROWS}
    other = len(claims) - sum(counts.values())
    assert other == 0, f"{other} claims carry a machine value MACHINE_ROWS does not list"
    rows = [f"| {label} | {counts[key]} |" for key, label in MACHINE_ROWS]
    return "\n".join([
        f"| Máquina que produjo la cifra | Afirmaciones (de {len(claims)}) |",
        "|---|---|", *rows,
    ])


def sync_readme(claims: list[Claim], readme: Path) -> bool:
    """Rewrite the generated block in README.md. Returns True if it changed."""
    text = readme.read_text()
    i, j = text.index(MACHINE_BEGIN), text.index(MACHINE_END)
    block = f"{MACHINE_BEGIN}\n\n{machine_table(claims)}\n\n"
    new = text[:i] + block + text[j:]
    if new == text:
        return False
    readme.write_text(new)
    return True


def load_claims() -> tuple[list[Claim], list[dict]]:
    reg = json.loads(REGISTRY.read_text())
    # `caveats_en` is the pre-translation English original, kept in the registry so a
    # later audit can diff it against the Spanish without git archaeology (R-20). It is
    # provenance, not report content, so it never reaches Claim.
    drop = {"rerun", "caveats_en"}
    claims = [Claim(**{k: v for k, v in c.items() if k not in drop}) for c in reg["claims"]]
    backlog = [c for c in reg["claims"] if c.get("rerun")]
    return claims, backlog


def figure_power(claims: list[Claim], outcomes: dict) -> Path:
    """Which designs could ever have reached alpha, plotted against their n.

    This is the figure that makes the point no table makes as fast: a wall of
    campaigns sitting at n <= 6, below the line where significance becomes
    reachable at all.
    """
    paired = [c for c in claims if c.design == "paired-binary"]
    paired.sort(key=lambda c: c.n_effective)
    if not paired:
        return None

    fig, ax = plt.subplots(figsize=(9, max(3.5, 0.32 * len(paired))))
    ys = range(len(paired))
    colors = ["#c0392b" if min_discordant_for_significance(c.n_effective) is None
              else "#27ae60" for c in paired]
    ax.barh(list(ys), [c.n_effective for c in paired], color=colors, height=0.62)
    ax.axvline(6, color="#2c3e50", ls="--", lw=1.4)
    # Anchored to the axes, not to the data, so a long claim list cannot push
    # the label on top of a bar.
    ax.text(0.99, 0.02, "línea: n = 6, el mínimo con el que alpha = 0,05 es alcanzable",
            transform=ax.transAxes, fontsize=8, ha="right", va="bottom", color="#2c3e50",
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#bdc3c7", alpha=0.9))
    ax.set_yticks(list(ys))
    ax.set_yticklabels([c.id for c in paired], fontsize=8)
    # Log scale or the n <= 6 wall - the whole point of the figure - is a smear
    # of invisible stubs next to the n = 312 bar.
    ax.set_xscale("log")
    ax.set_xlim(0.8, 400)
    ax.set_xticks([1, 2, 3, 6, 12, 25, 50, 100, 300])
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_xlabel("pares independientes (n efectivo, escala logarítmica)")
    ax.set_title("Diseños pareados: cuáles podían alcanzar significación\n"
                 "rojo = imposible con cualquier resultado", fontsize=10)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    out = PROOF / "stats-power.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def figure_forest(claims: list[Claim], outcomes: dict) -> Path:
    """Point estimates with 95% Wilson intervals, for every claim with counts."""
    # Only claims with a pre-registered gate. Plotting all 63 arms produced a
    # legible wall that answered nothing; the question this figure exists for is
    # "did the interval clear the bar", and that needs a bar.
    rows = []
    for c in claims:
        if c.data_status == "missing" or c.gate_p is None:
            continue
        k, n = c.counts.get("k"), c.counts.get("n")
        if k is None or not n:
            continue
        ke, ne = deflate_to_effective(k, n, c.n_effective)
        rows.append((f"{c.id}  ({k}/{n})", k / n, wilson_ci(ke, ne), c.gate_p))
    if not rows:
        return None

    fig, ax = plt.subplots(figsize=(9, max(3.5, 0.34 * len(rows))))
    for i, (label, est, (lo, hi), gate) in enumerate(rows):
        ax.plot([lo, hi], [i, i], color="#34495e", lw=1.6)
        ax.plot([est], [i], "o", color="#2980b9", ms=5)
        if gate is not None:
            ax.plot([gate], [i], "|", color="#c0392b", ms=14, mew=2)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_xlabel("proporción de éxito (IC 95 % de Wilson)")
    ax.set_title("Puertas pre-registradas contra la incertidumbre real\n"
                 "punto = proporción observada; barra roja = puerta; IC al 95 % sobre n efectivo",
                 fontsize=10)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    out = PROOF / "stats-forest.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def main() -> int:
    PROOF.mkdir(exist_ok=True)
    claims, backlog = load_claims()
    outcomes = {c.id: evaluate(c) for c in claims}
    holm = holm_bonferroni({cid: o.p_value for cid, o in outcomes.items()})

    on_device = [c for c in claims if c.machine == "jetson-orin-nano-8gb"]
    on_device_sig = [c.id for c in on_device if holm[c.id]["reject"]]

    lines = [
        "---",
        "title: Resultados estadísticos retroactivos",
        "subtitle: Cada afirmación con puerta de las Partes I-VI, re-analizada",
        "author: Javier Francisco Dibo Gómez",
        f"comment: Generado por thesis/run_stats.py, {stamp()}",
        "locale: es",
        "---",
        "",
        "## Cómo leer esta tabla",
        "",
        "Generada por `thesis/run_stats.py` desde `thesis/claims.json`. No se edita",
        "a mano. El método y las reglas de rechazo están en",
        "`thesis/01-metodo-estadistico.md`.",
        "",
        "`p` indefinido no significa 'sin efecto': significa que no hubo prueba,",
        "casi siempre por 0 pares discordantes. `alcanzable = no` significa que el",
        "diseño no podía llegar a alpha = 0,05 con ningún resultado posible.",
        "",
        "La columna **Máquina** dice qué hardware produjo el número. `ambas` es la",
        "respuesta honesta y mayoritaria en las Partes IV-V: el anclaje del VLM corrió",
        "en la Jetson mientras el arrastre de SAM2 corría en la RTX 3090 con un tope",
        # R-25. This sentence carried a literal "Seis" -- and before 71b0128 it
        # carried "Solo tres", changed by hand under a commit message saying a
        # generated document should not carry a hand-counted constant. Derived now.
        f"de tasa. {_spell(len(on_device))} afirmaciones se midieron íntegramente en la placa,",
        f"y {_spell(len(on_device_sig)).lower()} de ellas {'son' if len(on_device_sig) != 1 else 'es'}",
        "inferencial" + ("es" if len(on_device_sig) != 1 else "") + ": "
        + ", ".join(on_device_sig) + ". La derivación por afirmación está en",
        "`experiments/2026-07-21-machine-disclosure/README.md`.",
        "",
        "<!-- caption: Re-análisis exacto de las afirmaciones con puerta, con corrección de Holm-Bonferroni -->",
        "",
        "| Afirmación | Parte | Diseño | Máquina | n efectivo | Prueba | p | p (Holm) | Alcanzable | Lectura |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in claims:
        o = outcomes[c.id]
        p = "indefinido" if o.p_value != o.p_value else f"{o.p_value:.4g}"
        ph = holm[c.id]["p_holm"]
        ph_s = "—" if ph != ph else f"{ph:.4g}"
        lines.append(
            f"| {c.id} | {c.part} | {DESIGN_ES.get(c.design, c.design)} | {MACHINE_ES.get(c.machine, c.machine or '—')} | {c.n_effective} | {o.test} | "
            f"{p} | {ph_s} | {'sí' if o.could_ever_reach_alpha else '**no**'} | {o.reading} |"
        )

    # --- what survives -----------------------------------------------------
    # R-23: a partition, not four overlapping filters. Every claim appears once.
    members: dict[str, list[str]] = {key: [] for key, _, _ in BUCKETS}
    for c in claims:
        members[bucket_of(c, outcomes[c.id], holm[c.id]["reject"])].append(c.id)
    assert sum(len(v) for v in members.values()) == len(claims)

    survives = members["holm"]
    missing = members["sin-datos"]

    lines += [
        "",
        "## Qué sobrevive",
        "",
        f"Las {len(claims)} afirmaciones, repartidas en ocho categorías **disjuntas**:",
        "cada afirmación aparece exactamente una vez, y los recuentos suman",
        f"{len(claims)}. Cuando dos categorías podrían aplicar, gana la más",
        "específica — «la puerta era inalcanzable» dice algo del diseño y prevalece",
        "sobre «la prueba no rechazó», que sólo dice algo del resultado.",
        "",
    ]
    for key, label, meaning in BUCKETS:
        ids = members[key]
        lines.append(f"- **{label} ({len(ids)}).** {meaning} "
                     + (", ".join(ids) if ids else "*(ninguna)*"))
    lines.append("")

    # --- caveats ------------------------------------------------------------
    # These are the most honest text in the project and the report used to drop
    # every one of them, which reads as concealment to anyone diffing the
    # registry against this file. Rendered verbatim; never summarise them here.
    with_caveats = [c for c in claims if (c.caveats or "").strip()]
    if with_caveats:
        lines += [
            "## Salvedades por afirmación",
            "",
            f"Las {len(with_caveats)} afirmaciones con salvedad registrada, **literales**",
            "desde `thesis/claims.json`. Una salvedad limita lo que su fila de la tabla",
            "puede sostener: léase junto al valor p, nunca en su lugar. Varias retiran",
            "por completo la lectura ingenua del número.",
            "",
        ]
        for c in with_caveats:
            lines += [f"**{c.id}** — {c.caveats.strip()}", ""]

    if backlog:
        lines += [
            "## Cola de re-ejecución",
            "",
            "Afirmaciones cuyos datos por elemento no sobreviven. No se defienden en",
            "el TFM hasta que se re-ejecuten.",
            "",
            "<!-- caption: Trabajo de re-ejecución necesario para hacer defendible cada afirmación sin datos -->",
            "",
            "| Afirmación | Qué falta | Coste | Comando |",
            "|---|---|---|---|",
        ]
        for b in backlog:
            r = b["rerun"]
            cmd = f"`{r['command']}`" if r.get("command") else "sin comando registrado"
            lines.append(f"| {b['id']} | {r['missing']} | {r['cost']} | {cmd} |")
        lines.append("")

    f1 = figure_power(claims, outcomes)
    f2 = figure_forest(claims, outcomes)
    if f1 or f2:
        lines += ["## Figuras", ""]
        if f1:
            lines += ["<!-- caption: Diseños pareados por n efectivo; en rojo los que no podían alcanzar significación con ningún resultado -->",
                      "", f"![]({f1.relative_to(THESIS)})", ""]
        if f2:
            lines += ["<!-- caption: Proporciones observadas con intervalo de Wilson al 95 %; la barra roja marca la puerta pre-registrada -->",
                      "", f"![]({f2.relative_to(THESIS)})", ""]

    (THESIS / "stats-report.md").write_text("\n".join(lines) + "\n")
    if sync_readme(claims, THESIS.parent / "README.md"):
        print("  README.md machine table updated")

    print(f"[{stamp()}] {len(claims)} claims analysed")
    for key, label, _ in BUCKETS:
        print(f"  {label:52s}: {len(members[key])}")
    for c in claims:
        print("  " + outcomes[c.id].line())
    return 0


if __name__ == "__main__":
    sys.exit(main())
