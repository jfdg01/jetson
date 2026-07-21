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
DESIGN_ES = {
    "paired-binary": "binario pareado",
    "single-arm-binary": "binario de un brazo",
    "unpaired-binary": "binario no pareado",
    "paired-continuous": "continuo pareado",
    "descriptive": "descriptivo",
}


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%MZ")


def load_claims() -> tuple[list[Claim], list[dict]]:
    reg = json.loads(REGISTRY.read_text())
    claims = [Claim(**{k: v for k, v in c.items() if k != "rerun"}) for c in reg["claims"]]
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
        "<!-- caption: Re-análisis exacto de las afirmaciones con puerta, con corrección de Holm-Bonferroni -->",
        "",
        "| Afirmación | Parte | Diseño | n efectivo | Prueba | p | p (Holm) | Alcanzable | Lectura |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for c in claims:
        o = outcomes[c.id]
        p = "indefinido" if o.p_value != o.p_value else f"{o.p_value:.4g}"
        ph = holm[c.id]["p_holm"]
        ph_s = "—" if ph != ph else f"{ph:.4g}"
        lines.append(
            f"| {c.id} | {c.part} | {DESIGN_ES.get(c.design, c.design)} | {c.n_effective} | {o.test} | "
            f"{p} | {ph_s} | {'sí' if o.could_ever_reach_alpha else '**no**'} | {o.reading} |"
        )

    # --- what survives -----------------------------------------------------
    survives = [c.id for c in claims if holm[c.id]["reject"]]
    undefined = [c.id for c in claims if outcomes[c.id].p_value != outcomes[c.id].p_value
                 and c.data_status != "missing"]
    unreachable = [c.id for c in claims if not outcomes[c.id].could_ever_reach_alpha
                   and c.data_status != "missing"]
    missing = [c.id for c in claims if c.data_status == "missing"]

    lines += [
        "",
        "## Qué sobrevive",
        "",
        f"- **Significativas tras corrección de Holm ({len(survives)}):** "
        + (", ".join(survives) if survives else "ninguna"),
        f"- **Sin prueba posible, 0 pares discordantes ({len(undefined)}):** "
        + (", ".join(undefined) if undefined else "ninguna"),
        f"- **Diseño incapaz de alcanzar alpha ({len(unreachable)}):** "
        + (", ".join(unreachable) if unreachable else "ninguna"),
        f"- **Sin datos crudos, en cola de re-ejecución ({len(missing)}):** "
        + (", ".join(missing) if missing else "ninguna"),
        "",
    ]

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

    print(f"[{stamp()}] {len(claims)} claims analysed")
    print(f"  significant after Holm : {len(survives)}")
    print(f"  no test possible       : {len(undefined)}")
    print(f"  design could not reach : {len(unreachable)}")
    print(f"  missing raw data       : {len(missing)}")
    for c in claims:
        print("  " + outcomes[c.id].line())
    return 0


if __name__ == "__main__":
    sys.exit(main())
