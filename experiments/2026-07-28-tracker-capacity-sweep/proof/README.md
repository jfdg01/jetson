# Deliverables

Vacío ahora mismo. Los 21 vídeos de los tres clips piloto (`truck3`, `wakeboard1`, `bird1_1`) se
borraron el 2026-07-29 antes de lanzar el barrido completo de 30 secuencias: eran renders de tres
clips elegidos a mano y las cifras que sostenían ya están en `../README.md`. Los JSON crudos siguen
en `../raw/`, así que cualquiera de esos vídeos se reconstruye con:

```
analysis/render_overlay.py raw/<run>/<arm>__<seq>.json --out proof/<nombre>.mp4
```

Los deliverables definitivos saldrán del run `full-sweep-30`.
