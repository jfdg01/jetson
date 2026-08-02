# 23. De qué está hecho el déficit: pausar cuesta posición, no forma

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-08-03T02:10Z -> 02:55Z (hora local de Madrid).
**Coste:** 0 h de dispositivo — aritmética sobre las cajas ya commiteadas.
**Datos:** `raw/full-sweep-30/`, `raw/paced-sweep-30/`, `raw/paced-lead-30/`
**Código:** `dee75a1` (`analysis/errors.py`).

## 1. Por qué existe

Toda tabla de esta campaña puntúa mIoU, y mIoU dice **cuánto** salió mal sin decir **de qué** está
hecho. La taxonomía de la nota 21 (`person18` es escala, `bird1_1` revienta la máscara, `bike2` se
engancha a otro objeto) se leyó de tres fotogramas a ojo, y esa lectura a ojo ya falló una vez: la
nota 19 §4 atribuyó `person18` a un cambio de dirección desde un covariante, sin mirar.

`analysis/errors.py` lo calcula, fotograma a fotograma, con dos contrafactuales baratos:

- **centrado** — la caja predicha movida al centro del GT. Es lo que sobreviviría si la traslación
  fuese gratis.
- **reescalado** — una caja del tamaño del GT en el centro de la predicha. Lo que sobreviviría si la
  escala fuese gratis.

Ambas son **condicionales a que el brazo haya contestado**; la pérdida se reporta aparte, en su
columna. Mezclar los dos convenios es lo que hizo que `person18` saliera "bajo en las dos" en la
primera pasada. En las tandas pausadas se descompone la **caja entregada** (`aggregate.held`), no la
respondida: si no, se estaría describiendo un seguidor que nadie consume.

```
analysis/errors.py --selftest
analysis/errors.py raw/full-sweep-30  --arm sam2_c512 --arm sam2_c640
analysis/errors.py raw/paced-sweep-30 --arm sam2_c512 --arm sam2_c640
analysis/errors.py raw/paced-sweep-30 --arm sam2_c512 --foh
analysis/errors.py raw/paced-lead-30  --arm sam2_c512_lead
```

## 2. El resultado: el coste de pausar es traslación

Medianas sobre los **25 clips comunes** a las dos tandas, brazo `sam2_c512`:

| régimen | IoU | base | centrado | reescalado |
| --- | ---: | ---: | ---: | ---: |
| sin pausar | 0.761 | 0.783 | 0.825 | 0.836 |
| pausado 30 fps, ZOH | 0.439 | 0.448 | **0.809** | 0.463 |
| pausado 30 fps, FOH | 0.634 | 0.655 | **0.809** | 0.685 |

Pareado por clip, pausado menos sin pausar (Wilcoxon, n=25):

| columna | d mediana | p |
| --- | ---: | ---: |
| base | **−0.194** (23/25 pierden) | 8.2e−06 |
| **centrado** | **−0.004** (16/25) | 5.9e−02 |
| reescalado | −0.208 | 8.2e−06 |

Pausar destroza el solape (−0.194) y **no toca la forma de la caja**: recentrar la caja entregada
la devuelve al nivel de la tanda sin pausar (0.809 contra 0.825, d=−0.004, no significativo). El
déficit de pausar es, casi entero, **posición**: la caja que el consumidor tiene en la mano es la
correcta con retardo.

Eso es exactamente lo que FOH ataca, y los números lo cierran: FOH recupera **+0.071** de base
mediana (21/25) y deja `centrado` **idéntico hasta el tercer decimal** (`max |d| = 0.000` sobre los
25 clips). No es un accidente, es la comprobación interna: FOH solo mueve centros, así que un
contrafactual que anula la traslación tiene que ser invariante bajo FOH. Lo es.

`sam2_c512_lead` (predicción en la entrada, nota 20) da base 0.448 y centrado 0.801 — el mismo punto
que `c512` sin `lead`. Su nulo no solo se confirma: se explica. La palanca del retardo está en el
consumidor, no en qué fotograma se le da al modelo.

## 3. La taxonomía de la nota 21, ahora calculada

Sin pausar, `sam2_c512`, los cuatro peores clips:

| clip | IoU | perdidos | base | centrado | reescalado | lectura |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `bird1_1` | 0.061 | 0.284 | 0.085 | 0.105 | 0.134 | las dos bajas: máscara reventada |
| `car12` | 0.087 | **0.888** | **0.783** | 0.853 | 0.826 | ni traslación ni escala: **pérdida** |
| `bike2` | 0.091 | 0.000 | 0.091 | **0.643** | 0.093 | traslación pura: otro objeto |
| `person18` | 0.239 | 0.293 | 0.337 | 0.374 | **0.475** | escala |

Las tres lecturas de la nota 21 se **corroboran por cálculo** — no se corrige nada de esa nota. Lo
que añade esta es `car12`: mIoU 0.087 con solape condicional 0.783 sobre el 11% de fotogramas en que
contesta. Su problema no es una caja mala, es no haber caja, y ninguna tabla de mIoU de la campaña
lo distinguía de `bird1_1`, que sí tiene la caja rota. Son dos arreglos distintos.

En pausado, `person18` con `c640` sube a base 0.689 / centrado 0.773 / reescalado 0.732: la
patología de `c512` de la nota 22 se ve también como hueco de solape **condicional**, no solo
puntuado, así que no es un artefacto de fotogramas perdidos.

## 4. Cómo no sobreleer

- `centrado` y `reescalado` son **cotas superiores de recuperación**, no arreglos. Nadie tiene el
  centro del GT en tiempo de vuelo. Dicen dónde está el error, no que sea removible.
- Los dos contrafactuales no son ortogonales: una caja del tamaño correcto en el sitio correcto
  puntúa alto en las dos. Se leen por su **diferencia**, no por su nivel.
- `base`/`centrado`/`reescalado` son condicionales a respuesta; con `perdidos` alto describen una
  minoría de fotogramas (`car12`, 11%). La columna `perdidos` va siempre al lado.
- El régimen pausado es 30 fps sobre este dispositivo y esta potencia (15 W, `jetson_clocks`). Que
  el déficit sea traslación a 30 fps no dice qué pasa a 120; la rejilla `paced-grid-*` está corriendo
  para eso y esta descomposición se le pasará encima cuando aterrice.
- n=25 pareado, un brazo (`c512`) para el contraste principal. `c640` se movió igual (base pausado
  0.344, centrado 0.815) pero no se ha probado que la conclusión sea de todos los brazos.

## 5. Qué no se midió

**Sin verificación visual de este análisis.** No hace falta ni la sustituye: no hay ninguna
afirmación aquí sobre lo que se ve en pantalla, solo aritmética sobre cajas que ya estaban en disco
y cuya verificación visual es la de la nota 21. Cualquier lectura de esta nota que hable de píxeles
está fuera de lo medido.

No se midió: si el déficit de traslación es retardo puro (la caja correcta N fotogramas tarde) o
además deriva — separarlos pide comparar contra el GT desplazado en el tiempo, y no se ha hecho; ni
si `reescalado` mejora bajo brazos con más contexto, que es lo que la rejilla ventana-contra-entrada
(`notes/PREREG-window-vs-input.md`) va a responder por otra vía.
