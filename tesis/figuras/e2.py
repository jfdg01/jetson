"""Figuras de E2 - Barrido de LLMs.

Datos de `experiments/2026-06-13-model-capability-sweep/README.md`; la campaña no
dejó CSV crudo de llama-bench, así que las cifras se transcriben del registro.
"""

from estilo import AZUL, GRIS, NARANJA, ROJO, VERDE, eje_log, figura, nuevo, rejilla

# Todos Q4_K_M, 15 W + jetson_clocks, ngl 99, n_ctx 4096.
# (id, nombre, parámetros B, pp512 tok/s, tg128 tok/s, TTFT ms, RAM pico MB,
#  tok/s·W⁻¹ neto, J/tok)
BARRIDO = [
    ("01", "Qwen2.5-0.5B", 0.5, 3027, 71.52, 38, 2637, 11.77, 0.157),
    ("02", "Llama-3.2-1B", 1.2, 1534, 35.07, 49, 3497, 4.35, 0.380),
    ("03", "Qwen2.5-1.5B", 1.5, 1098, 26.56, 59, 2872, 4.17, 0.444),
    ("04", "Gemma-2-2B", 2.6, 728, 15.98, 85, 5818, 2.02, 0.824),
    ("05", "Qwen2.5-3B", 3.1, 559, 14.91, 91, 3180, 2.04, 0.842),
    ("06", "Llama-3.2-3B", 3.2, 570, 14.60, 85, 3719, 2.00, 0.863),
    ("07", "Phi-3.5-mini", 3.8, 432, 13.15, 114, 4693, 1.68, 0.995),
    ("08", "Mistral-7B", 7.2, 253, 8.39, 190, 5488, 0.98, 1.639),
    ("09", "Qwen2.5-7B", 7.6, 266, 7.89, 202, 5465, 0.92, 1.749),
    ("10", "Meta-Llama-3.1-8B", 8.0, 245, 7.75, 204, 5953, 0.89, 1.795),
]

PARAMETROS = [u[2] for u in BARRIDO]
RAM_TOTAL_MB = 7607  # memoria unificada de la placa, declarada en el contexto
UMBRAL_TTFT_MS = 250
EJE_PARAMETROS = ("parámetros (miles de millones)", [0.5, 1, 2, 4, 8])


def _columna(indice):
    return [u[indice] for u in BARRIDO]


def _etiquetar(ax, valores, dy=1.06):
    """Rotula cada punto con su número de unidad."""
    for unidad, x, y in zip(BARRIDO, PARAMETROS, valores):
        ax.annotate(unidad[0], (x, y * dy), fontsize=9, ha="center", color="#444")


@figura("e2-barrido")
def barrido():
    fig, axes = nuevo(3, 2, ancho=9, alto=10.5)
    (a, b), (c, d), (e, sobra) = axes
    sobra.axis("off")

    prefill = _columna(3)
    a.loglog(PARAMETROS, prefill, "o-", color=AZUL)
    _etiquetar(a, prefill, dy=0.80)
    a.set_ylim(180, 4500)
    eje_log(a, [250, 500, 1000, 2000, 4000], cual="y")
    a.set_ylabel("pp512 (tok/s)")
    a.set_title("(a) Caudal de prefill")

    decode = _columna(4)
    b.loglog(PARAMETROS, decode, "s-", color=NARANJA)
    _etiquetar(b, decode, dy=0.80)
    b.set_ylim(5.5, 110)
    eje_log(b, [8, 16, 32, 64], cual="y")
    b.set_ylabel("tg128 (tok/s)")
    b.set_title("(b) Caudal de decode")

    ttft = _columna(5)
    c.semilogx(PARAMETROS, ttft, "o-", color=AZUL)
    _etiquetar(c, ttft)
    c.axhline(UMBRAL_TTFT_MS, ls="--", lw=1, color=GRIS)
    c.text(0.5, UMBRAL_TTFT_MS + 8, f"umbral interactivo {UMBRAL_TTFT_MS} ms", fontsize=10, color="#666")
    c.set_ylim(0, 300)
    c.set_ylabel("TTFT (ms)")
    c.set_title("(c) Latencia de primer token")

    ram = _columna(6)
    d.semilogx(PARAMETROS, ram, "o-", color=AZUL)
    _etiquetar(d, ram)
    d.axhline(RAM_TOTAL_MB, ls="--", lw=1, color=ROJO)
    d.text(0.5, RAM_TOTAL_MB - 420, f"memoria total {RAM_TOTAL_MB} MB", fontsize=10, color=ROJO)
    d.annotate(
        "Gemma-2-2B: anomalía\n(caché KV local/global)",
        xy=(2.6, 5818),
        xytext=(0.55, 6100),
        fontsize=10,
        color="#666",
        arrowprops=dict(arrowstyle="->", color=GRIS, lw=0.8),
    )
    d.set_ylim(0, 8200)
    d.set_ylabel("RAM pico (MB)")
    d.set_title("(d) Memoria")

    eficiencia = _columna(7)
    e.semilogx(PARAMETROS, eficiencia, "o-", color=VERDE)
    _etiquetar(e, eficiencia)
    e.set_ylabel("tok/s·W⁻¹ (neto de idle)", color=VERDE)
    e.tick_params(axis="y", labelcolor=VERDE)
    julios = e.twinx()
    julios.semilogx(PARAMETROS, _columna(8), "s--", color=NARANJA)
    julios.set_ylabel("J/tok (placa completa)", color=NARANJA)
    julios.tick_params(axis="y", labelcolor=NARANJA)
    e.set_title("(e) Eficiencia energética")

    etiqueta_x, marcas_x = EJE_PARAMETROS
    for ax in (a, b, c, d, e):
        ax.set_xlabel(etiqueta_x)
        eje_log(ax, marcas_x)
    rejilla(a, b, c, d, e)
    return fig


@figura("e2-qwen")
def qwen():
    """Escalado del decode dentro de Qwen2.5, la única familia con cuatro puntos."""
    puntos = [(u[2], u[4]) for u in BARRIDO if u[1].startswith("Qwen2.5")]
    parametros = [p for p, _ in puntos]
    decode = [d for _, d in puntos]
    base_p, base_tg = parametros[0], decode[0]

    fig, ax = nuevo()
    # Referencia: caudal que daría un escalado exacto 1/parámetros desde la unidad base.
    ax.loglog(
        parametros,
        [base_tg * base_p / x for x in parametros],
        "--",
        color=GRIS,
        lw=1.2,
        label="ideal 1/parámetros",
    )
    ax.loglog(parametros, decode, "o-", color=NARANJA, ms=8, label="medido (tg128)")

    for x, y in zip(parametros, decode):
        ax.annotate(
            f"{y:.2f} tok/s\n{y / base_tg:.2f}×",
            (x, y),
            textcoords="offset points",
            xytext=(9, 6),
            fontsize=10,
            color="#333",
        )

    eje_log(ax, parametros)
    eje_log(ax, [8, 16, 32, 64], cual="y")
    ax.set_xlim(0.42, 12)
    ax.set_ylim(5.5, 110)
    ax.set_xlabel(EJE_PARAMETROS[0])
    ax.set_ylabel("tg128 (tok/s)")
    ax.legend(fontsize=11)
    rejilla(ax)
    return fig
