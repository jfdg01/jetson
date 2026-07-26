#!/usr/bin/env python3
"""Concatenate the per-chapter scaffolds into one md-to-pdf document.

Front matter + chapters in order -> thesis/TFM-borrador.md (lives in thesis/,
so image paths of the form ../experiments/... and proof/... resolve correctly).
Run: make borrador          (regenerate the committed artifact)
     make borrador-check    (fail if it is stale; also run by `make test`)
"""
import sys
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

<!-- GENERATED FILE — do not edit. Source: thesis/borrador/cap*.md + assemble.py.
     Edit the chapter scaffold, then run `make borrador`. Hand edits here are
     silently destroyed on the next regeneration. -->
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

def build():
    parts, missing = [FRONT], []
    for slug in CHAPTERS:
        f = HERE / f"{slug}.md"
        if not f.exists():
            missing.append(slug)
            parts.append(f"\n## [PENDIENTE] {slug}\n\n> Capítulo no generado.\n")
            continue
        parts.append("\n" + f.read_text(encoding="utf-8").rstrip() + "\n")
    return "\n".join(parts), missing


if __name__ == "__main__":
    text, missing = build()
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            sys.exit(f"STALE: {OUT} does not match thesis/borrador/*.md. Run `make borrador`.")
        print(f"{OUT.name} is up to date")
    else:
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT}  ({len(missing)} missing)")
    if missing:
        print("MISSING:", ", ".join(missing))
