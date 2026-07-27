"""Estilo común y registro de figuras de la tesis.

Una figura se declara decorando una función con `@figura("<id>")`. El id es el
nombre del PNG y el que se cita desde `tesis.md`; por convención `e<n>-<tema>`.

    from estilo import NARANJA, figura, nuevo

    @figura("e2-qwen")
    def qwen():
        fig, ax = nuevo()
        ax.plot(...)
        return fig

La función devuelve la figura y nada más: `make_figs.py` se encarga del
`tight_layout`, del guardado, del dpi y de la comprobación de que el PNG no
salió vacío. Así los 300 ficheros de figura no repiten esas cuatro líneas ni
pueden divergir en resolución.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SALIDA = Path(__file__).parent
DPI = 400
BYTES_MINIMOS = 60_000  # un PNG por debajo de esto salió vacío o en blanco

# El PDF escala las figuras al ancho de página: con la tipografía por defecto de
# matplotlib el texto acaba en ~5 pt e ilegible.
plt.rcParams.update({"font.size": 13, "axes.titlesize": 15})

AZUL, NARANJA, VERDE, ROJO, GRIS = "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#999999"

# id -> función que devuelve la figura. Lo llena el decorador `figura`.
REGISTRO: dict[str, callable] = {}


def figura(identificador: str):
    """Registra la función como generadora de `<identificador>.png`."""

    def decorador(funcion):
        if identificador in REGISTRO:
            raise ValueError(f"identificador de figura duplicado: {identificador}")
        REGISTRO[identificador] = funcion
        return funcion

    return decorador


def nuevo(filas: int = 1, columnas: int = 1, ancho: float = 7.5, alto: float = 4.8):
    """`plt.subplots` con el tamaño por defecto que cabe en el ancho de página."""
    return plt.subplots(filas, columnas, figsize=(ancho, alto))


def eje_log(ax, valores, etiquetas=None, cual: str = "x") -> None:
    """Marcas fijas en un eje logarítmico.

    Sin esto matplotlib mezcla marcas mayores y menores y las etiquetas se
    solapan (`2×10²`, `3×10²`, ...) en cuanto el rango pasa de una década.
    """
    etiquetas = etiquetas or [str(v) for v in valores]
    fijar, poner = (ax.set_xticks, ax.set_xticklabels) if cual == "x" else (ax.set_yticks, ax.set_yticklabels)
    fijar(valores)
    fijar([], minor=True)
    poner(etiquetas)


def rejilla(*ejes) -> None:
    """Rejilla discreta y por debajo de los datos, igual en todas las figuras."""
    for ax in ejes:
        ax.grid(True, which="major", ls=":", alpha=0.45)
        ax.set_axisbelow(True)


def guardar(fig, identificador: str) -> Path:
    destino = SALIDA / f"{identificador}.png"
    fig.tight_layout()
    fig.savefig(destino, dpi=DPI)
    plt.close(fig)
    # Comprobación mínima: el PNG no puede salir vacío ni en blanco.
    assert destino.stat().st_size > BYTES_MINIMOS, f"figura sospechosamente pequeña: {destino}"
    return destino
