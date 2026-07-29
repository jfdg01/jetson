# Deliverables

Los 21 vídeos de los tres clips piloto (`truck3`, `wakeboard1`, `bird1_1`) se borraron el
2026-07-29 antes de lanzar el barrido completo. Los JSON crudos siguen en `../raw/`, así que
cualquiera se reconstruye con `analysis/render_overlay.py`.

## Diez casos del barrido de 30 (run `full-sweep-30`, 2026-07-30)

Elegidos sobre los 161 de 210 resultados disponibles a media mañana, para cubrir modos de fallo
distintos, no para hacer un ranking. Tres son **pares del mismo clip** para que el contraste se vea
en el mismo metraje. GT en verde, predicción en azul claro, y en los arms de crop el vídeo va a dos
paneles: izquierda frame completo con la ventana en naranja, derecha lo que entra al modelo.

Aviso de lectura: el IoU quemado en el vídeo y el de estas notas **excluye los frames perdidos**,
que es lo que hace `render_overlay.py`. La tabla agregada de `../README.md` los cuenta como 0, así
que las cifras no coinciden y la del agregado es la honesta. `car12_c512` es el caso extremo: 0.783
sobre los 44 frames que contestó, 0.087 sobre los 499 del clip.

| # | fichero | mIoU (resp.) | qué muestra |
| --- | --- | --- | --- |
| 1 | `car9_c512.mp4` | 0.595 | **Cambio de identidad entre dos coches en fila.** Verificado en el frame 940: la predicción está sobre el coche blanco de delante y el GT sobre el gris de detrás |
| 2 | `car9_c640.mp4` | 0.848 | Mismo clip, +128 px de ventana: mantiene el coche correcto, IoU 0.85 en ese mismo frame 940 |
| 3 | `person21_t512.mp4` | 0.015 | **Cambio de identidad entre peatones.** Frame 244: la predicción está sobre otra persona a ~150 px del GT. IoU@0.5 = 0.000 en los 487 frames |
| 4 | `person21_c704.mp4` | 0.511 | Mismo clip y mismo frame 244: la predicción cae sobre el peatón correcto, IoU 0.47 |
| 5 | `uav2_t512.mp4` | 0.419 | **Objetivo diminuto sobre cielo**, 84 frames perdidos de 133. Frame 67: LOST, sin predicción |
| 6 | `uav2_c512.mp4` | 0.675 | Mismo clip y frame: IoU 0.66. Es 720×480, así que la ventana se recorta a 480 y se escala **hacia arriba** — el crop aquí aumenta, no conserva |
| 7 | `car12_c512.mp4` | 0.783 / **44 frames** | **El modo de fallo propio del crop.** Frame 250: la ventana naranja está congelada arriba a la izquierda mientras el coche va por la carretera al centro-derecha. Se pierde una vez, la ventana se queda donde estaba y ya no vuelve: 450 frames perdidos de 499 |
| 8 | `bird1_3_c640.mp4` | 0.095 | **Enganche a un glifo del HUD.** Metraje FPV con telemetría; frame 433, sin GT (el pájaro no está), y la predicción es una cajita sobre el texto del HUD. Devuelve caja en los 392 frames de hueco |
| 9 | `bike2_c704.mp4` | 0.124 | **Clip que rompe a los seis arms** (mIoU 0.04–0.12) y en el que los seis contestan en los 35 frames de hueco. Frame 277: GT y predicción son dos objetos diminutos distintos |
| 10 | `person18_t1024.mp4` | 0.499 | **La máscara se queda en una parte del cuerpo.** Frame 697: el arm más caro (434 ms) segmenta solo las piernas del peatón mientras el GT cubre la persona entera. IoU 0.34 |

Los 10 verificados en píxeles: cada `.mid.png` abierto y mirado antes de escribir estas notas. Los
PNG no se commitean.

Reproducir cualquiera:

```
analysis/render_overlay.py raw/full-sweep-30/<arm>__<seq>.json --out proof/<seq>_<arm corto>.mp4
```
