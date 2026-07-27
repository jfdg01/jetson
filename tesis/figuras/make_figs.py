"""Genera las figuras de tesis.md.

    ../.venv-ft/bin/python make_figs.py          # todas
    ../.venv-ft/bin/python make_figs.py e2       # solo el módulo e2
    ../.venv-ft/bin/python make_figs.py e2-qwen  # solo esa figura

Cada módulo `e<n>.py` de este directorio declara sus figuras con `@figura("id")`
(ver `estilo.py`). Este script los descubre solos: para añadir una figura no hay
que tocar nada aquí. Los PNG no van a git — se regeneran con este comando.
"""

import importlib
import sys
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))

from estilo import REGISTRO, guardar  # noqa: E402  (necesita el sys.path de arriba)

MODULOS = sorted(p.stem for p in AQUI.glob("*.py") if p.stem not in {"estilo", "make_figs"})


def main(filtro: str | None) -> None:
    # Importar es barato (solo registra funciones) y así el filtro puede ser un
    # id de figura sin que haya que adivinar en qué módulo vive.
    for modulo in MODULOS:
        importlib.import_module(modulo)

    pendientes = {k: v for k, v in REGISTRO.items() if filtro in (None, k) or k.startswith(f"{filtro}-")}
    if not pendientes:
        raise SystemExit(f"sin figuras para «{filtro}». Disponibles: {', '.join(sorted(REGISTRO))}")

    for identificador, funcion in sorted(pendientes.items()):
        destino = guardar(funcion(), identificador)
        print(f"escrito {destino.name} ({destino.stat().st_size // 1024} kB)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
