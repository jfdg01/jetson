# Preregistro: separar geometría, modelo y reenganche

Parte de [`../README.md`](../README.md).

**Coste:** sin corridas de dispositivo — análisis, diseño o lectura.


## Experimento completo: `search-window` (preregistrado 2026-07-29T17:05Z)

Cuatro brazos sobre el tercil difícil, pareados clip a clip, para separar tres causas que
`asym_b` contra `sam2_c640` confunde: control `sam2_c640`; `sam2_f5` (SAM2 con ventana
`5*sqrt(w*h)` de la última caja y relleno de color medio, misma entrada 640x640 y mismos ~159 ms)
aísla **la geometría sola**; `asym_b` aísla **el modelo solo** (3.36M contra ~224M); y
`asym_b_redet` (re-detección global agnóstica de clase, disparada por confianza con suelo duro de
30 frames) aísla **el reenganche solo**. Se ejecutó por partes: `sam2_f5`/`sam2_f5_floor` y los
brazos LT están más abajo; `asym_b_redet` nunca se corrió.

**Por qué la re-detección es agnóstica de clase.** UAV123 mezcla objetivos aéreos (`uav*`, `bird*`)
con objetos de suelo filmados desde un dron (`car9`, `person21`, `truck3`, `wakeboard5`, `bike1`),
así que un YOLO de Drone-vs-Bird sería inútil en buena parte del tercil y obligaría a bajar del
n>=25. La alternativa es la tercera etapa de SiamSTA: búsqueda global por apariencia sobre la
plantilla acumulada, 0.9 apariencia reciente / 0.1 plantilla original. Sin pesos de nadie y sin
clase. Pesos abiertos localizados por si el eje se retoma restringido al subconjunto aéreo:
`doguilmak/Drone-Detection-YOLOv11x` (MIT, mAP@50 0.905, ~8.9 ms/img) y
`FardadDadboud/Drone_YOLOv5_Detector` (GPL-3.0). Ambos solo-dron.

**Métricas** más allá de mIoU y AUC, porque en contra-UAS el mIoU no las ve: tasa de falsos
negativos, falsos positivos en hueco (ya en `aggregate.py`) y las "3 R's" de TLP (borrar un tramo y
medir recuperación en 200 frames, en 30, y frames medios hasta recuperar). Sale gratis y **no
existe publicado**: la curva P/R de `object_score_logits` como detector de pérdida — SAM2 lo
entrena con cross-entropy en frames sin máscara GT incluidos, pero no hay umbral ni P/R publicados.

**El factor 5 se fija a priori** desde la ablación de OSTrack (4 a 6 gana, 7 regresa); barrer
f3/f4/f5/f6 multiplicaría por 4 el coste y añadiría comparaciones múltiples a una familia que ya
tiene 4 brazos.

Limitaciones declaradas antes de correr: la muestra está sesgada a difícil, luego ninguna cifra de
aquí estima el rendimiento en UAV123 (esa sale de `asym-repro`); 10 clips son 720x480 y todos `uav`,
así que el sesgo de resolución cae entero sobre una categoría; y sigue sin medirse la penalización
por cambiar la ventana a mitad de stream, que es a la vez el riesgo y el objeto de `asym_b_redet`.

---
