# Validación cruzada de las constantes del brazo LT

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-08-01T15:40Z -> 2026-08-01T17:22Z (diseño, implementación y corrida del análisis).
**Coste:** **0 h de dispositivo** — todo se resuelve re-filtrando `raw/dam-conf33/` en el portátil.
**Datos:** `raw/dam-conf33/` (traza `(box, conf)` de `dam4sam_t640` sobre las 33 con hueco).
**Código:** `analysis/lt_sim.py --cv`, commit `142d0e5`.


## Por qué este análisis existe (2026-08-01T18:05Z)

El brazo `dam4sam_lt` de la sección 14 lleva cuatro constantes — `a=4.0`, `b=2.0`, `k=1`, `w=300`,
ventana móvil — elegidas barriendo 312 candidatos sobre la mitad par de las 33 secuencias con hueco
y reportando sobre la impar. Eso es metodológicamente correcto, pero es **una sola partición**: el
número fuera de muestra que respalda el brazo es una muestra de tamaño uno de la distribución de
particiones posibles. Con 312 candidatos y 33 secuencias, la pregunta que hay que hacerse no es si
el procedimiento fue honesto sino si sobrevive al remuestreo.

La sección 14 dejó además abierta la duda operativa: `gm_ox` es la única métrica que respalda el
brazo, y `gm_ox` es exactamente la que el barrido optimizó.

**Leave-one-sequence-out (LOO)** contesta las dos: se repite el procedimiento completo 33 veces,
apartando una secuencia distinta cada vez, eligiendo constantes con las otras 32 y puntuando la
apartada. Cada secuencia queda fuera de muestra exactamente una vez, y de paso se ve **si las
constantes elegidas cambian de un pliegue a otro**, que es información que una sola partición no
puede dar.

Barato por la misma razón que la sección 14: `Dam4SamLtArm.step` llama a `inner.step(frame)` en
todos los frames y solo decide si **publicar** la caja, así que la política se simula sobre la traza
grabada sin tocar la GPU. La matriz (candidato × secuencia) de `gm_ox` se calcula **una vez**
(312 × 33, 3 min 26 s) y cada pliegue es después una mediana sobre columnas.

**Solo se valida la rejilla relativa.** Los umbrales fijos son percentiles de los propios logits del
pliegue de ajuste, así que compartir esa rejilla entre pliegues metería la secuencia apartada dentro
del conjunto de candidatos — fuga. Las constantes relativas son adimensionales y no filtran nada.


## 1. Las constantes no son estables; dos de las cuatro sí

    analysis/lt_sim.py raw/dam-conf33 --arm dam4sam_t640 --cv

| constantes elegidas | pliegues |
| --- | --- |
| `a 4.0 b 2.0 k 1 w 100` móvil | 16/33 |
| `a 3.0 b 2.0 k 3 w 100` móvil | 11/33 |
| `a 3.0 b 2.0 k 2 w 30` móvil | 3/33 |
| `a 3.0 b 1.0 k 3 w 100` móvil | 1/33 |
| `a 3.0 b 1.0 k 5 w 100` móvil | 1/33 |
| **`a 4.0 b 2.0 k 1 w 300` móvil** (el desplegado) | **1/33** |

Lo estable: **`b = 2.0` en 30/33**, **ventana móvil en 33/33**, `a` siempre en [3, 4]. Lo inestable:
`k` recorre 1, 2, 3 y 5, y `w` prefiere 100 en 29/33 pliegues mientras el brazo desplegado usa 300.

Es decir: **la mitad de los parámetros del brazo no están determinados por los datos**. Presentar
los cuatro como "ajustados" afirma de más. Lo que los datos sí dicen es que hay que volver
tarde a contestar (`b=2`) y que la referencia debe seguir al vídeo (móvil).

Contrapeso importante para no sobreleer la tabla: ordenando los 312 candidatos por su mediana
global, el desplegado queda **10/312**. Cae en la meseta del óptimo, no en un pico afortunado; que
casi ningún pliegue lo elija significa que hay un empate ancho arriba, no que sea una mala elección.


## 2. Fuera de muestra, el brazo LT es un nulo

Delta de `gm_ox` contra el brazo que nunca se abstiene (`plain`):

| lectura | gana | mediana | media | peor | p |
| --- | --- | --- | --- | --- | --- |
| **LOO, fuera de muestra** | 18/33 | +0.009 | +0.072 | -0.251 | **0.0577** |
| desplegado, sobre las 33 | 17/33 | +0.005 | +0.105 | -0.037 | 0.0005 |

La segunda fila es la de la sección 14 y está **inflada**: 17 de esas 33 secuencias participaron en
elegir las constantes. La primera es la honesta, y **no cruza 0.05**.

Corrección explícita al veredicto de la sección 14: donde decía `gm_ox` +0.105, p = 0.0005, hay que
leer *el procedimiento completo, remuestreado, da p = 0.058*. El brazo LT no es una mejora medida.
No es tampoco un negativo — es un nulo al n disponible, y el peor pliegue (-0.251) muestra que la
política puede hacer daño real cuando las constantes le vienen de otras secuencias.


## 3. Pero el efecto es de cola, y eso cambia qué hacer con él

Media +0.072 con mediana +0.009 no es ruido de redondeo: significa que en el clip típico el brazo no
hace nada y en unos pocos hace muchísimo.

| pliegue | delta | constantes que eligieron las otras 32 |
| --- | --- | --- |
| `uav1_2` | -0.251 | `a 4.0 b 2.0 k 1 w 100` |
| `person12_2` | -0.190 | `a 3.0 b 2.0 k 2 w 30` |
| `car12` | -0.116 | `a 4.0 b 2.0 k 1 w 100` |
| `bird1_3` | -0.080 | `a 3.0 b 2.0 k 2 w 30` |
| `group3_4` | +0.402 | `a 3.0 b 2.0 k 3 w 100` |
| `car2` | +0.482 | `a 3.0 b 2.0 k 3 w 100` |
| `person17_1` | +0.483 | `a 3.0 b 2.0 k 3 w 100` |

Tres secuencias concentran casi toda la ganancia y cuatro casi todo el daño. La conclusión operativa
no es "el brazo LT no sirve" sino **"no se activa siempre"**: es una palanca condicionada, de la
misma clase que el 1024 con puerta de tamaño de la Parte VI, no un comportamiento por defecto. Qué
detecta la puerta —y si es detectable causalmente— no se ha medido aquí.


## 4. Lo que esto obliga a decir sobre `asym_lt`

`asym_lt` fija sus umbrales (`tau_lo = 0.3920`, `tau_hi = 0.7293`) con **la misma partición única y
las mismas 33 secuencias**. El sesgo es idéntico, y su número fuera de muestra hereda la misma
duda.

La diferencia es que **no se puede corregir barato**: el re-detector de rastreo de cinco sondas de
`AsymLtArm` mueve la ventana de búsqueda, así que cambia lo que el modelo ve y el brazo **cierra el
lazo**. No es simulable sobre una traza grabada; validarlo cruzadamente cuesta GPU real, 33
secuencias × cada candidato. Mientras eso no se pague, **el número de `asym_lt` es "as-run", no
fuera de muestra**, y así hay que citarlo.


## 5. Limitación de fondo: 33 secuencias no soportan 312 candidatos

Con 312 candidatos y 33 puntos, algún candidato queda arriba por azar. Las dos salidas, ninguna
corrida todavía:

- **Encoger la rejilla a lo que resultó estable** — fijar `b = 2` y ventana móvil, barrer solo `a`
  (3, 4) y `w`: quedan ~15 candidatos, y la selección deja de ser el problema dominante. Coste cero,
  se re-corre el mismo script.
- **Más secuencias con hueco.** UAV123 solo tiene 33; subir de ahí exige otro dataset (TLP está en
  `TODO.md` por esto mismo).

Sin verificación visual en esta tanda: es análisis puro sobre JSON ya grabados, no genera píxeles.
Los overlays que respaldan la traza de origen son los de `raw/parity-smoke/` sobre `car2`, ya
mirados en la sección 14.
