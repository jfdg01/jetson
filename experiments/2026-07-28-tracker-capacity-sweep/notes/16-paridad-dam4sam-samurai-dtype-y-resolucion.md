# Paridad DAM4SAM contra SAMURAI: precisión y resolución

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-08-01T12:07Z -> 2026-08-01T18:45Z (sello de los ficheros traídos).
**Coste:** 92 corridas, **6.38 h de dispositivo** — estimación, `sum(init_ms + frames * ms_p50)`
sobre los JSON; no incluye tiempo muerto entre etapas.
**Datos:** `raw/sam-dtype-smoke/` (2 corridas), `raw/sam-parity30/` (90 corridas).
**Código:** perilla de dtype y brazo `samurai_b640`, commit `ac18a4d`; datos, commit `3ba21ac`.


## El problema: la comparación entre familias tenía dos confundidos (2026-08-01T18:50Z)

DAM4SAM y SAMURAI son **el mismo modelo**: SAM2.1 `hiera_tiny`, mismos pesos, ninguno reentrenado.
Lo único que cambia es la política de memoria — DAM4SAM guarda los frames donde una máscara
alternativa contradice a la elegida (registro del distractor); SAMURAI usa un filtro de Kalman sobre
la caja para elegir entre las máscaras candidatas y como puerta de admisión a la memoria. Comparar
las dos familias debería ser comparar exactamente esas dos políticas.

No lo era, por dos razones:

1. **Precisión numérica.** `dam4sam_t*` corría bf16 (`device/trackers.py`) y `samurai_t*` fp16, que
   es lo que despliega la demo publicada de SAMURAI. Cualquier delta entre familias era política de
   memoria **más** aritmética de 16 bits, sin forma de separarlas.
2. **Resolución sin parear.** DAM4SAM tenía 640/768/960 sobre las 30 secuencias de `dam-full30b`;
   SAMURAI solo tenía 640 con potencia (la escalera `sam-full30` se canceló a los 3 trabajos).
   Comparar a una sola resolución mide cada familia en un punto arbitrario de **su propia** curva.

Este evento mata los dos.


## 1. La perilla de dtype, y por qué no se hizo el 2x2 completo

`SamuraiArm` gana un parámetro `amp` y `_amp()` deja de tener el dtype cableado:

```python
def _amp(self):
    return self.torch.autocast("cuda", dtype=getattr(self.torch, {"fp16": "float16",
                                                                  "bf16": "bfloat16"}[self.amp]))
```

fp16 sigue siendo el **defecto**, deliberadamente: es la precisión de la implementación publicada y
el gating de Kalman lee las puntuaciones de máscara, así que la aritmética del cabezal de score es
parte del método, no un detalle de despliegue. El brazo nuevo `samurai_b640` es `samurai_t640` con
esa única línea cambiada.

**No se corrió el brazo simétrico `dam4sam` en fp16.** Si mover el dtype dentro de SAMURAI no hace
nada, la comparación entre familias ya queda libre del confundido y el otro medio 2x2 es gasto
inútil; solo si saliera no-nulo haría falta.

Smoke en `uav2` (`raw/sam-dtype-smoke/`, 2 corridas) antes de gastar la noche: el brazo arranca, la
diferencia es pequeña, el barrido merece la pena.


## 2. Descubrimiento durante el diseño: 640 ya estaba pareado

Al montar la corrida apareció que `samurai_t640` ya cubría las 30 secuencias de `dam-full30b`
repartidas entre tres directorios (`night-samurai` 17, `lt-controls33` 33, `sam-full30` 3;
29 de las 30 tras la unión). Faltaban solo 768 y 960.

`sam-parity30` quedó por tanto en 3 brazos × 30 secuencias = **90 corridas**, 27276 frames:
`samurai_b640` (el control de dtype), `samurai_t768` y `samurai_t960` (los peldaños que faltaban).

**Advertencia de procedencia:** las 29 secuencias de `samurai_t640` vienen de tres tandas de noches
distintas, agrupadas por `aggregate.py` en un solo brazo (el diccionario `by[arm][seq]` sobrescribe
duplicados, gana el último directorio de la línea de comandos). Misma definición de brazo y mismo
venv, y la determinación del stack se midió en `raw/asym-determ/`, pero no es una tanda única.

### Estimación contra realidad

La latencia se predijo escalando desde los brazos DAM4SAM equivalentes. Acertó:

| brazo | p50 predicho | p50 real | error |
| --- | --- | --- | --- |
| `samurai_b640` | 189.0 ms | 190.4 ms | +0.7% |
| `samurai_t768` | 255.7 ms | 253.5 ms | -0.9% |
| `samurai_t960` | 377.5 ms | 381.2 ms | +1.0% |

Coste total estimado 6.24 h, real 6.38 h (+2%).


## 3. Confundido 1 muerto: el dtype no explica nada

`samurai_b640` (bf16) contra `samurai_t640` (fp16), pareado sobre las 29 comunes:

| métrica | d mediana | d media | gana | p |
| --- | --- | --- | --- | --- |
| mIoU | +0.000 | +0.015 | 15/29 | 0.481 |
| AUC | -0.000 | +0.012 | 14/29 | 0.579 |
| falsos positivos en hueco | 0 | -2.2 | 3/29 | 0.686 |

Nulo en las tres. Es un **nulo acotado**, no equivalencia demostrada — pero el margen que podría
esconderse (media +0.015 de mIoU) es menor que cualquier delta que decida algo aquí.

Consecuencia: **la comparación entre familias es limpia y el 2x2 completo no hace falta.**


## 4. Confundido 2 muerto: la ventaja de DAM4SAM existe solo a 960

Con las dos familias en 640/768/960 sobre las mismas 30 secuencias. DAM4SAM menos SAMURAI, misma
resolución, Wilcoxon pareado de mIoU:

| resolución | n | d mediana | d media | gana | p | p tras Holm (4 contrastes) |
| --- | --- | --- | --- | --- | --- | --- |
| 640 | 29 | -0.005 | -0.023 | 11/29 | 0.205 | 0.61 |
| 768 | 30 | -0.001 | +0.004 | 15/30 | 0.465 | 0.61 |
| 960 | 30 | +0.008 | +0.029 | 21/30 | 0.0087 | **0.035** |

AUC replica el patrón (a 960: mediana +0.008, media +0.023, 19/30, p = 0.012).

**El nulo anterior era cierto solo en su punto.** A 640 y a 768 las dos políticas de memoria dan lo
mismo; la separación aparece a 960 y sobrevive a Holm sobre la familia de cuatro contrastes de este
evento (los tres de familia más el de dtype).

Lectura del mecanismo, y hay que marcarla como **interpretación, no medida**: la memoria que
resuelve distractores necesita píxeles para distinguir al distractor del objetivo, y a 640 el
detalle no da para eso, así que la política deja de importar. Es coherente con el resultado central
del barrido — a 640 el cuello de botella es la geometría de la ventana, no el modelo — pero aquí no
se ha aislado la causa.

Coste de esa ventaja: `dam4sam_t960` va a **407.2 ms** contra **381.2 ms** de `samurai_t960`, un 7%
más de latencia por +0.008 de mediana. Es la comparación más cercana a iso-latencia que existe en
los datos, y aun así no está pareada en milisegundos.

Falsos positivos en hueco, pareado a 960: DAM4SAM comete menos (media -2.6, 1/30, p = 0.028), pero
la mediana es 0 y ninguno de los dos se abstiene nunca — el `lost%` es 0.0 en los seis brazos. La
diferencia son frames de máscara vacía, no una decisión de presencia.


## 5. Lo que esto no cambia

Nada de esto mueve al incumbente. `sam2_c640` corre a ~159 ms; el peldaño donde DAM4SAM gana está a
407 ms, **2.6x** más caro, por una mediana de +0.008 de mIoU contra su propio rival y sin comparación
pareada contra el recorte a esa latencia. La decisión de despliegue la sigue tomando la geometría de
la ventana (sección 12), no la familia de memoria.

Sin verificación visual en esta tanda: no se ha abierto ningún overlay de `sam-parity30`. Todo lo de
arriba son números de `raw/*.json`, y así hay que citarlo.
