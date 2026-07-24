#!/usr/bin/env python3
"""Concatenate the per-chapter scaffolds into one md-to-pdf document.

Front matter + chapters in order -> thesis/TFM-borrador.md (lives in thesis/,
so image paths of the form ../experiments/... and proof/... resolve correctly).
Run: python3 thesis/borrador/assemble.py  (from repo root)
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent          # thesis/borrador
THESIS = HERE.parent                            # thesis
OUT = THESIS / "TFM-borrador.md"

FRONT = """---
title: Grounding visual anticipatorio para seguimiento de objetivos desde UAV en hardware de borde
subtitle: Borrador de redacción — guion de párrafos por capítulo
author: Javier Francisco Dibo Gómez
comment: Guion generado 2026-07-24. Cada viñeta P1/P2/… es un párrafo por escribir; tablas, figuras y código ya colocados.
locale: es
bibliography: refs.bib
toc_depth: 4
---
"""

CHAPTERS = [
    "cap01-introduccion",
    "cap02-estado-del-arte",
    "cap03-plataforma-metodo-metricas",
    "cap04-grounding-un-frame",
    "cap05-permanencia-objeto",
    "cap06-arco-latencia",
    "cap07-grounding-anticipatorio",
    "cap08-lazo-cerrado",
    "cap09-amenazas-validez",
    "cap10-conclusiones",
]

parts = [FRONT]
missing = []
for slug in CHAPTERS:
    f = HERE / f"{slug}.md"
    if not f.exists():
        missing.append(slug)
        parts.append(f"\n## [PENDIENTE] {slug}\n\n> Capítulo no generado.\n")
        continue
    parts.append("\n" + f.read_text(encoding="utf-8").rstrip() + "\n")

OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"wrote {OUT}  ({sum(1 for c in CHAPTERS if not (HERE/f'{c}.md').exists() )} missing)")
if missing:
    print("MISSING:", ", ".join(missing))
