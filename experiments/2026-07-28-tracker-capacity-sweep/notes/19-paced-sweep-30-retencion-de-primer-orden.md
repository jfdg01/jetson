# El barrido a ritmo real, y la retención de primer orden sobre 155 pares

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-08-02T20:03Z -> 2026-08-02T21:52Z (tanda), análisis hasta 2026-08-03T00:20Z.
**Coste:** 155 corridas, **1.66 h de dispositivo** — `sum(init_ms + frames * ms_p50)` sobre los JSON.
**Datos:** `raw/paced-sweep-30/`
**Código:** `820609b` (modo paced), `3d2f8c5` (`motion.py`), `728b0d6` (`sweetspot.py`), `96d57da`
(`extrapolate` + `--foh` + test).

## 1. Por qué existe la tanda

Todo el barrido anterior corrió en **paridad**: el brazo ve todos los fotogramas, cueste lo que
cueste. Eso mide calidad de máscara y nada más. El sistema real recibe lo que hay vivo cuando acaba
el paso anterior, así que un brazo lento paga dos veces — menos actualizaciones, y cada una ya
caduca al llegar. `run_arm.py --fps 30` reproduce eso (`820609b`) y `raw/paced-smoke` lo comprobó
sobre 2 clips. Esta tanda lo lleva a la rejilla de resolución completa sobre los 30 clips.

La pregunta que se contesta aquí no es solo "cuánto cuesta la latencia" sino la que abrió la nota
18: **si el consumidor puede navegar la caja retenida en vez de congelarla, ¿sigue siendo caro ser
lento?** La nota 18 lo medía sobre n=2. Aquí son 155 pares.

## 2. Cómo corrió

```
./jetson.py run paced-sweep-30 --arms sam2_t512 sam2_t640 sam2_t768 sam2_t1024 \
    sam2_c512 sam2_c640 sam2_c704 --seqs raw/full-sweep-30 --fps 30
```

15 W, `schedutil`, L4T R36.5.0, `sam2==1.1.0`, `torch==2.8.0`, semilla 0, `fps_stream = 30.0`.
Térmicas 59.7 -> 68.1 °C de CPU, sin estrangulamiento.

**7 brazos x 30 clips = 210 trabajos, pero salen 155.** No es un fallo: la puerta `upscales` de
`device/trackers.py` descarta 55 trabajos donde el brazo inventaría píxeles. Tumba `sam2_t1024`
**entero** (1024 > 720 de alto en UAV123, en los 30 clips) y los 5 clips de 720x480 (`uav1_2`,
`uav2`, `uav3`, `uav5`, `uav7`) para todo brazo de 640 o más. Por eso n=25 en cinco filas y n=30
solo en `sam2_t512`. La lista exacta está en `manifest.json["gated"]`.

**El conjunto común difiere por brazo.** Cualquier comparación entre dos filas de la tabla de abajo
está comparando medianas sobre poblaciones distintas; los contrastes serios de §4 son pareados.

## 3. Retención de orden cero: lo que cuesta la latencia

```
analysis/aggregate.py raw/paced-sweep-30
```

| brazo | n | p50 ms | visto% | mIoU | @0.25 | @0.5 | AUC | mIoU paridad |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `sam2_c512` | 25 | 100.5 | 33.2% | **0.439** | 0.834 | 0.459 | 44.9 | 0.679 |
| `sam2_c640` | 25 | 159.3 | 21.0% | 0.344 | 0.674 | 0.292 | 41.0 | 0.759 |
| `sam2_c704` | 25 | 190.7 | 17.6% | 0.302 | 0.661 | 0.219 | 38.5 | 0.762 |
| `sam2_t512` | 30 | 122.3 | 27.2% | 0.342 | 0.666 | 0.234 | 36.2 | 0.591 |
| `sam2_t640` | 25 | 180.8 | 18.6% | 0.308 | 0.676 | 0.161 | 37.2 | 0.678 |
| `sam2_t768` | 25 | 252.0 | 13.4% | 0.242 | 0.448 | 0.157 | 33.2 | 0.704 |

`lost%` es 0.0% en las seis filas: ningún brazo se queda sin responder, el daño es todo deriva.

**El orden se invierte respecto a paridad.** En paridad `c704` (0.762) y `c640` (0.759) ganaban y
`c512` (0.679) era el peor de los crop; bajo stream `c512` gana y `c704` es el peor. La resolución
que compra mejor máscara compra también más retraso, y a 30 fps el retraso pesa más. Esto es el
cruce que `sweetspot.py` predecía y aquí se mide.

## 4. Retención de primer orden: el resultado

```
analysis/aggregate.py raw/paced-sweep-30 --foh
```

En vez de congelar la última respuesta, la caja navega su propia velocidad — estimada de las dos
últimas respuestas aterrizadas, en píxeles por **índice de fotograma**, y extendida al fotograma que
se puntúa. Estrictamente causal, sin modelo, sin GPU, **sin tiempo de dispositivo**: cambia el
consumidor, no el tracker. Por eso se calcula sobre los JSON ya grabados.

| brazo | n | mIoU ZOH | mIoU FOH | @0.25 FOH | @0.5 FOH | AUC FOH |
| --- | --- | --- | --- | --- | --- | --- |
| `sam2_c512` | 25 | 0.439 | **0.634** | 0.960 | 0.796 | 53.8 |
| `sam2_c640` | 25 | 0.344 | 0.604 | 0.929 | 0.734 | 52.3 |
| `sam2_c704` | 25 | 0.302 | 0.550 | 0.876 | 0.651 | 50.2 |
| `sam2_t512` | 30 | 0.342 | 0.506 | 0.792 | 0.604 | 41.8 |
| `sam2_t640` | 25 | 0.308 | 0.525 | 0.812 | 0.643 | 46.5 |
| `sam2_t768` | 25 | 0.242 | 0.506 | 0.768 | 0.585 | 43.8 |

Pareado sobre los mismos 155 pares (brazo x clip), Wilcoxon:

| brazo | n | d mediana | gana | p |
| --- | --- | --- | --- | --- |
| todos | 155 | +0.069 | 121/155 | 4.9e-19 |
| `sam2_c512` | 25 | +0.071 | 21/25 | 2.2e-05 |
| `sam2_c640` | 25 | +0.097 | 21/25 | 2.2e-05 |
| `sam2_c704` | 25 | +0.085 | 21/25 | 1.8e-05 |
| `sam2_t512` | 30 | +0.037 | 21/30 | 5.5e-04 |
| `sam2_t640` | 25 | +0.068 | 19/25 | 4.3e-04 |
| `sam2_t768` | 25 | +0.069 | 18/25 | 3.3e-04 |

Seis contrastes, Holm al 0.05 exige 0.0083 en el mayor: los seis pasan con margen de dos órdenes.

**Dónde pierde.** 34 pares de 155, ninguno por más de 0.042. Tres poblaciones, todas explicables:

- **objetivo casi quieto** — `boat3` (0.0052 anchuras/fotograma, mIoU ya 0.92): la velocidad
  estimada es ruido de anotación y la extrapolación lo amplifica. Media −0.021 sobre 6 brazos.
- **cambio de dirección más rápido que el paso de retención** — `person18` (−0.020), `person20`
  (−0.006): peatones. La velocidad pasada deja de predecir la futura.
- **la caja ya estaba mal** — `bird1_1`, `bird1_3`, `bike2`, todos con mIoU 0.01-0.07: extrapolar
  una caja equivocada la aleja más. Pérdidas de 0.003 a 0.033 sobre una base ya perdida.

Gana donde el movimiento es lineal y rápido: `truck2` +0.376, `truck3` +0.336, `wakeboard8` +0.244,
`car1_3` +0.226, `wakeboard1` +0.217.

**El hueco entre resoluciones se estrecha.** ZOH `c512 − c640` = 0.095; FOH = 0.030. Es la
predicción de la nota 18 §1: si la deriva se devuelve, ser lento cuesta menos y el óptimo de
resolución vuelve a subir. No llega a invertirse con esta rejilla — `c512` sigue ganando bajo ambas
retenciones — pero el margen que sostiene esa elección pasa de holgado a marginal.

## 5. Cómo no sobreleer

- **La mediana del agregado no es la ganancia típica de un clip.** `c512` salta +0.195 en la tabla
  de §4 y solo +0.071 en el pareado. Lo primero es un desplazamiento de la distribución alrededor
  de la mediana (muchos clips a 0.4-0.5 se mueven mucho), no el efecto que esperar en un clip nuevo.
  La cifra a citar es la pareada.
- **n=25 por brazo, no 30**, y conjuntos comunes distintos entre filas — ver §2.
- **Los 30 clips no son independientes**: `car*` comparten escena, `wakeboard*` también, `uav*` son
  el mismo tipo de vuelo. Los p son optimistas.
- **La muestra está sesgada a difícil** por construcción del corte de 30.
- **UAV123 solo.** TLP no entra: la nota 18 §5 midió que ni tiene el fenómeno (mediana 103 px,
  0.0125 anchuras/fotograma).
- **`--foh` es una hipótesis sobre el consumidor.** Si el sistema real no puede cambiar cómo
  sostiene la caja entre respuestas, toda la §4 es inaplicable y manda la §3. Esa pregunta sigue
  abierta y decide qué configuración es óptima.
- **Sin verificación visual de esta tanda.** Ninguna caja de FOH se ha dibujado sobre un fotograma
  y mirado. Todo lo de arriba es aritmética sobre JSON.

## 6. Lo que la tanda cierra de la nota 18

**`ms_p50` es idéntico entre paridad y paced** (|d| <= 0.3 ms en los seis brazos, mediana pareada
por clip). La nota 18 §9 lo listaba como suposición no verificada — queda verificada: el coste por
paso no depende del protocolo, que es lo que debía pasar y no estaba comprobado.

**El modelo de `sweetspot.py` ajusta `k = 1.20` sobre los 155 pares, RMSE 0.075** (antes 0.90 sobre
2 pares; la nota 18 §7 lo marcaba como "no refutado", no validado). Reproduce el orden observado
bajo ZOH: predicho `c512` 0.406 > `t512` 0.319 > `c640` 0.312 > `t640` 0.256 > `c704` 0.251 >
`t768` 0.148, observado 0.439 > 0.342 ≈ 0.344 > 0.308 > 0.302 > 0.242. El sesgo **no crece con la
resolución** (−0.019, +0.006, −0.003, −0.022, −0.011, −0.028), así que no falta un término que
escale con ella. El RMSE alto de `c512` (0.117 contra 0.053-0.080 del resto) son dos clips, `car9`
(−0.463) y `car12` (−0.239), donde el modelo castiga una deriva que el tracker recupera: el modelo
no sabe que la caja vuelve.

**El índice de dificultad bajo stream**, Spearman contra la mediana entre brazos, n=30:

| eje | paridad | paced ZOH | paced FOH |
| --- | --- | --- | --- |
| `motion` | −0.682 | **−0.942** | −0.844 |
| `size_px` | +0.632 | +0.767 | +0.699 |
| `gap` | −0.628 | −0.543 | −0.628 |
| `roam` | −0.298 | −0.356 | −0.256 |
| índice | −0.765 | −0.945 | −0.900 |

La predicción de la nota 18 §6 era que bajo stream `motion` sube y `size_px` con `gap` bajan.
**Acierta en `motion`** (−0.682 a −0.942, casi determinista) y **falla en `size_px`**, que sube en
vez de bajar — el objetivo pequeño no solo es más difícil de segmentar, además es el que más se
mueve en anchuras propias, y bajo stream ambas penalizaciones se suman en vez de solaparse. FOH
deshace parte de la inflación de `motion` (−0.942 a −0.844), que es literalmente su trabajo:
devolver la deriva que el protocolo introduce.

## 7. Interpretación

Bajo paridad la pregunta de este barrido era "qué resolución segmenta mejor". Bajo el protocolo a
ritmo real la pregunta cambia: **la política de retención del consumidor mueve el resultado más que
cualquier salto de resolución de la rejilla.** +0.069 de mediana pareada a coste cero contra
+0.030-0.095 entre resoluciones vecinas que cuestan 60-90 ms por paso. Si hay una sola cosa que
llevar al sistema real de esta tanda, es esa, no un número de resolución.

El contra honesto: es una mejora del **puntuador**, y solo vale si el consumidor real puede
implementarla. Y no está verificada visualmente.

**Corregido por la [nota 20](20-lead-prediccion-en-la-entrada.md) §1.** Donde esta sección deja FOH
como "mejora del puntuador" sin más, hay que leer la distinción completa: como medida de calidad del
**seguidor** es cosmética, pero como medida de **entrega** es real, porque el sistema en vuelo
persigue usando esas cajas y un retardo es error de control. Es la separación que la Parte VI traza
entre *grounding* y *delivery*. La nota 20 además cierra el punto 2 de la sección siguiente: la
misma predicción puesta en la **entrada** (`lead`) es nula (+0.001 ZOH, p=0.31, n=25).

## 8. Qué sigue

1. Preguntar al autor si el sistema real puede cambiar el consumidor (retención de primer orden).
   Decide qué tabla manda, §3 o §4, y por tanto qué resolución se fija.
2. Verificación visual: superponer ZOH contra FOH sobre `truck2` (donde gana +0.376) y sobre
   `boat3` (donde pierde) y mirarlo. Sin eso, §4 es aritmética sin píxeles.
3. Descomponer el error de `sweetspot.py` en traslación contra escala; `car9` sugiere que falta un
   término de recuperación.
4. La variante que sí cuesta dispositivo (nota 18 §1.1): centrar el recorte de entrada en la
   posición **predicha**, no en la última vista. Eso no se puede reanalizar, hay que correrlo.
