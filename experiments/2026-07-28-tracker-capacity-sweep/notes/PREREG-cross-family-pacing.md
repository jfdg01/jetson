# Pre-registro: la curva pausada, ¿es ciega a la familia?

Parte de [`../README.md`](../README.md). **Sellado: 2026-08-04T14:05Z** (hora local de Madrid).
**Estado: CORRIDO Y CERRADO** el 2026-08-04T17:05Z. Resultados en §7 y lectura en
[`28-la-curva-pausada-es-ciega-a-la-familia.md`](28-la-curva-pausada-es-ciega-a-la-familia.md).

## 1. Por qué existe

La nota 27 cerró con una frase que no autoriza nada: *"hay una familia entera sin explorar donde la
campaña supuso que no la había"*. El arco pausado entero (notas 19-26) es SAM2 contra SAM2, y la
nota 27 solo añadió un AsymTrack. DAM4SAM y SAMURAI —las dos familias que la campaña midió sin
pausar y nunca pausó— siguen fuera.

Y hay una razón para pensar que la respuesta no es obvia. Sin pausar, **el catálogo entero empata**,
pareado por clip sobre el conjunto de 30:

| par sin pausar | n | d mediana | gana | p |
| --- | ---: | ---: | ---: | ---: |
| `samurai_t640 − dam4sam_t640` | 20 | +0.002 | 11/20 | 0.99 |
| `samurai_t640 − sam2_c512` | 20 | −0.007 | 8/20 | 0.65 |
| `samurai_t640 − asym_b` | 20 | −0.014 | 8/20 | 0.73 |
| `dam4sam_t640 − sam2_c512` | 30 | −0.006 | 11/30 | 0.43 |
| `samurai_t640 − sam2_c704` | 20 | **−0.027** | 3/20 | 0.001 |
| `dam4sam_t640 − sam2_c704` | 30 | **−0.016** | 8/30 | 0.005 |

Cuatro familias, de 29 a 407 ms de coste, y ninguna diferencia pareada pasa de 0.03. **Sin pausar,
la familia no importa.** Nótese de paso que la lectura por medianas de brazo dice otra cosa
(`samurai_t640` 0.761 contra `dam4sam_t640` 0.678) — es el mismo espejismo de poblaciones distintas
que estropeó la estimación de la nota 27: samurai solo tiene 20 de los 30 clips, y son los fáciles.

Pausando, en cambio, el catálogo se abre en abanico. A 30 fps, medido:

| brazo | ms p50 | tasa | mIoU pausada (ZOH) | n |
| --- | ---: | ---: | ---: | ---: |
| `asym_b` | 30.3 | 0.972 | 0.673 | 30 |
| `sam2_c512` | 100.5 | 0.332 | 0.439 | 25 |
| `sam2_t512` | 122.3 | 0.272 | 0.342 | 30 |
| `sam2_c640` | 159.3 | 0.210 | 0.344 | 25 |
| `sam2_t640` | 180.8 | 0.186 | 0.308 | 25 |
| `sam2_c704` | 190.7 | 0.176 | 0.302 | 25 |
| `sam2_t768` | 252.0 | 0.134 | 0.242 | 25 |

De 0.68 a 0.24 con brazos que sin pausar se distinguen en menos de 0.03. **El protocolo pausado
convierte una diferencia de coste en una diferencia de calidad, y esa es la única variable que
parece quedar.** La pregunta que eso deja abierta es si la curva es una propiedad del protocolo —de
la placa— o si está trazada con puntos de una sola familia y otra familia la cruzaría por otro
sitio.

**RQ.** ¿La mIoU pausada de un brazo depende solo de su tasa de respuesta, o la familia deja huella
por encima del coste?

Descartado para esta tanda: `samurai_b640` (el gemelo bf16). La nota de registro
(`device/trackers.py:999`) dice que cualquier delta SAMURAI-DAM4SAM mezcla precisión con política,
y es cierto — por eso el contraste principal de aquí **no** es samurai contra dam4sam, sino cada uno
contra el brazo SAM2 de su mismo coste. Precio de la precisión: en `TODO.md`, no aquí.

## 2. Cómo va a correr

```
S="bike1 bike2 bird1_1 bird1_3 boat3 boat6 building5 car12 car1_3 car16_1 car8_2 car9 \
   group1_2 group2_3 person18 person19_3 person20 person21 person4_1 truck2 truck3 \
   uav1_2 uav2 uav3 uav5 uav7 wakeboard1 wakeboard5 wakeboard7 wakeboard8"

M="bike2 bird1_1 bird1_3 car1_3 group2_3 person19_3 truck3 uav1_2 uav2 uav7"
A="samurai_t640 dam4sam_t640 dam4sam_t960 asym_lt"

./jetson.py run --id xfam-pilot          --arms $A            --seqs bike1 --fps 30
./jetson.py run --id xfam-unpaced-sam    --arms samurai_t640  --seqs $M
./jetson.py run --id xfam-unpaced-asymlt --arms asym_lt       --seqs $S
./jetson.py run --id xfam-30             --arms $A            --seqs $S --fps 30
./jetson.py run --id xfam-120            --arms $A            --seqs $S --fps 120
```

15 W mode 0 + `jetson_clocks`, `schedutil`, L4T R36.5.0, semilla 0, un proceso por (brazo, clip),
orden barajado. **Las cuatro tandas van en serie, una detrás de otra**: dos drivers a la vez se
disputan la GPU y corrompen la latencia sobre la que descansa el protocolo (la nota 27 corrió así
por la misma razón).

Los cuatro brazos van **en la misma tanda por velocidad**, no en cuatro tandas separadas: el driver
baraja los trabajos (`device/driver.py:119`), así que la deriva térmica queda decorrelacionada de la
identidad del brazo. Cada familia trae su propio venv (`.venv-samurai`, `.venv-dam4sam`,
`.venv-asym`) y el driver ya sabe lanzarlos mezclados.

Controles pausados **ya en disco**, no se recorren: `raw/paced-sweep-30/` (30 fps) y
`raw/paced-grid-120/` (120 fps) traen los seis brazos SAM2, y `raw/paced-family-{30,120}/` trae
`asym_b`. La nota 26 §5 midió la reproducibilidad del protocolo entre sesiones (rho 0.995/0.999,
`|d|` mediana 0.002), así que reutilizar está validado por una medida.

Controles **sin pausar** que sí hay que correr: `samurai_t640` solo tiene 20 de los 30 clips
(`raw/night-samurai` + `raw/sam-full30`), faltan los 10 de `$M`; y `asym_lt` solo tiene 10 de los 30
(`raw/asym-lt`, que es otro conjunto). Sin ellos, ningún efecto pausado es atribuible al protocolo.

**Piloto antes de las cuatro tandas.** Ninguno de los tres brazos nuevos ha corrido nunca con
`--fps`: el protocolo pausado se escribió después. Un clip a 30 fps con los cuatro; si alguno peta o
su tasa de respuesta no cae donde predice su p50, la tanda se para y el piloto es el resultado.

## 3. Los conjuntos, y los sesgos que traen

- **n=30** para todo contraste que no toque un brazo SAM2 con recorte: `samurai_t*`, `dam4sam_t*` y
  los AsymTrack llevan `image_size=None`, así que la puerta `upscales` no les aplica y corren los 30.
- **n=25** en cuanto entra `sam2_c704` (o cualquier `c*`): la puerta tumba los cinco clips de
  720x480 (`uav1_2`, `uav2`, `uav3`, `uav5`, `uav7`). Es la misma n=25 de la nota 27 y el mismo sesgo
  declarado: cuatro de los cinco peores clips de `asym_b` son `uav*`.
- **Fuga de ajuste en `asym_lt`.** Sus umbrales (`tau_lo=0.3920`, `tau_hi=0.7293`) son la salida de
  `analysis/presence.py raw/asym-conf --thresholds`, ajustada sobre las 17 secuencias con hueco de
  índice par. De los 30 clips, **cinco están en la mitad de ajuste** (`bike2`, `car1_3`, `uav1_2`,
  `uav2`, `uav7`). Se declara antes de mirar y D4 se reporta también sobre los 25 restantes.
- **Precisión.** `samurai_t640` corre fp16 y `dam4sam_t640` bf16. No se comparan entre sí por eso.

## 4. Hipótesis y umbrales

Familia Holm pre-registrada: **8 contrastes** — D1 (4) y D2 (4). Wilcoxon pareado por clip. D4 lleva
su **propia** familia de 4 y se reporta etiquetada como secundaria.

- **D1 (la principal).** `samurai_t640 − sam2_c704`, n=25, a 30 y 120 fps, bajo ZOH y FOH. Los dos
  brazos cuestan 189.1 y 190.7 ms — **0.8% de diferencia**, el par de coste más ajustado que existe
  entre familias en todo el catálogo. Sin pausar el par vale **−0.027**. La ley de coste predice que
  pausar es una transformación de tasa y nada más, o sea que **la diferencia pausada se queda donde
  estaba**: se declara compatible con la ley si `|d_pausada − (−0.027)| <= 0.05` en las cuatro
  celdas. **Se declara FALSADA** si alguna celda se sale de ese margen con `>= 19/25` en el mismo
  sentido y Holm < 0.05, en **>= 2 de las 4** celdas. Un nulo acotado es un nulo acotado: no se
  escribirá "equivalentes".
- **D2 (el segundo par).** `dam4sam_t640 − sam2_c704`, n=25, mismas cuatro celdas. 204.0 contra
  190.7 ms (+7% de coste) y **−0.016** sin pausar. La curva de §1 da ~0.01 de mIoU por ese salto de
  tasa, así que la ley predice `d_pausada` en **[−0.08, +0.02]**. Fuera de ahí, con `>= 19/25` y
  Holm < 0.05 en >= 2 de 4, la familia deja huella.
- **D3 (la curva, fuera de muestra, descriptiva).** Se ajusta mIoU pausada contra `log(tasa)` **solo
  con los seis brazos SAM2** a 30 fps y se predicen los tres brazos nuevos. La ley se sostiene si los
  tres caen dentro de **±0.05** de la predicción. Sin contraste propio: es la forma agregada de D1 y
  D2 y se reporta como descriptiva. `asym_b` (tasa 0.972) queda **fuera** del cheque: su tasa está a
  tres veces del rango ajustado (0.134-0.332) y eso sería extrapolación, no validación.
- **D4 (secundaria — la deuda que la nota 27 dejó abierta).** `asym_lt − asym_b`, n=30, a 30 y 120
  fps, ZOH y FOH, familia Holm propia de 4. La nota 27 §6 midió que lo que hunde a `asym_b` es
  **pérdida de identidad**, no retraso, y `asym_lt` es exactamente el brazo que añade detección de
  pérdida y re-detección amortizada. Sin pausar y sobre los 10 clips comunes que hay hoy, `asym_lt`
  **pierde** (−0.033, 3/10, p=0.25). Predicción: sigue perdiendo, y `|d|` **crece** con fps, porque
  más movimiento entre respuestas produce más pérdidas de identidad y eso amplifica el intercambio
  en las dos direcciones. **Lo que sería noticia**: que gane bajo FOH a 120 fps. Ahí la maquinaria de
  recuperación estaría comprando justo lo que la nota 27 dijo que faltaba.
- **D0 (los controles sin pausar).** `samurai_t640` sobre los 10 que faltan y `asym_lt` sobre los 30.
  Sin ellos las diferencias pausadas no son atribuibles al protocolo.

**Qué falsa la ley de coste.** Que D1 o D2 se salgan de su margen. Eso diría que la curva pausada
está trazada con puntos de SAM2 y que otra familia la cruza por otro sitio — y entonces "el punto de
operación pausado" vuelve a ser un enunciado sobre una familia, que es el error de alcance que la
nota 26 corrigió en el eje ventana/entrada y la nota 27 un nivel más arriba.

## 5. Estimaciones (son estimaciones)

| tanda | corridas | coste estimado |
| --- | ---: | ---: |
| piloto (4 brazos x 1 clip) | 4 | ~0.02 h |
| `xfam-unpaced-sam` (10 clips a 189 ms) | 10 | ~0.37 h |
| `xfam-unpaced-asymlt` (30 clips a 30 ms) | 30 | ~0.23 h |
| `xfam-30` (4 brazos x 30 clips) | 120 | ~1.00 h |
| `xfam-120` (4 brazos x 30 clips) | 120 | ~0.25 h |
| **total** | **284** | **~1.9 h** |

Una pasada pausada cuesta lo que dura el flujo, no lo que cuesta el brazo: bajo pausa el brazo
procesa sin parar durante toda la secuencia, así que 27276 fotogramas a 30 fps son 0.25 h de
dispositivo **para cualquier brazo**, y a 120 fps son 0.06 h. Reloj de pared bastante mayor: unos
15-20 s de arranque por corrida (init 4.8-7.4 s más el proceso y el venv), o sea **~3.5 h estimadas**
de principio a fin.

Números esperados, **estimados** desde la curva de §1 y la tasa que predice el p50. Se estiman con
la curva y **no** restando medianas de brazo, que es la trampa que estropeó la estimación de la nota
27:

| brazo | ms p50 | tasa a 30 fps | mIoU pausada estimada |
| --- | ---: | ---: | ---: |
| `samurai_t640` | 189.1 | 0.176 | ~0.28 |
| `dam4sam_t640` | 204.0 | 0.163 | ~0.28 |
| `dam4sam_t960` | 407.2 | 0.082 | ~0.17 |
| `asym_lt` | ~30.5 | ~0.97 | ~0.64 |

## 6. Verificación visual

**Obligatoria si D1 o D2 salen falsadas**, y sobre clips elegidos antes de mirar los resultados:
`truck3` (el mismo clip de la nota 27 §6, para que la comparación sea continua con lo ya mirado) y
`person20` (objeto grande, sin huecos de GT, el clip donde todos los brazos deberían estar sanos).
Overlay con `analysis/render_foh.py`, PNG abierto con la herramienta Read antes de afirmar nada
sobre lo que pasa en pantalla. Sin imagen, no hay afirmación sobre píxeles.

Aserción barata en el propio análisis: si un brazo nuevo devuelve la misma caja en todos los
fotogramas procesados de un clip, el brazo no está siguiendo nada y la celda es INVÁLIDA, no un 0.

## 7. Resultados

| par | fps | salida | n | d mediana | gana | p | p Holm | margen | dentro |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 `samurai_t640 − sam2_c704` | 30 | ZOH | 25 | −0.003 | 9/25 | 1.9e−01 | 5.7e−01 | [−0.077, +0.023] | sí |
| D1 | 30 | FOH | 25 | −0.028 | 7/25 | 1.3e−03 | 5.2e−03 | [−0.077, +0.023] | sí |
| D1 | 120 | ZOH | 25 | +0.000 | 13/25 | 9.2e−01 | 1.0e+00 | [−0.077, +0.023] | sí |
| D1 | 120 | FOH | 25 | −0.004 | 10/25 | 6.0e−01 | 1.0e+00 | [−0.077, +0.023] | sí |
| D2 `dam4sam_t640 − sam2_c704` | 30 | ZOH | 25 | −0.018 | 3/25 | 6.6e−06 | 4.6e−05 | [−0.080, +0.020] | sí |
| D2 | 30 | FOH | 25 | −0.039 | 4/25 | 5.2e−06 | 4.2e−05 | [−0.080, +0.020] | sí |
| D2 | 120 | ZOH | 25 | −0.006 | 5/25 | 3.3e−04 | 1.6e−03 | [−0.080, +0.020] | sí |
| D2 | 120 | FOH | 25 | −0.030 | 6/25 | 2.5e−04 | 1.5e−03 | [−0.080, +0.020] | sí |

**8 de 8 celdas dentro del margen.** Ninguna celda fuera, así que ni D1 ni D2 falsan la ley de
coste. Es un **nulo acotado**: la diferencia entre familias a igual coste cabe en el margen
registrado, no está demostrado que sea cero.

D3, **corregido sobre el conjunto común** — la versión pre-registrada comparaba medianas por brazo
y eso cruza poblaciones (los `c*` se caen en los cinco clips 720x480 y puntúan sobre 25, los tres
nuevos sobre 30). Se dan las dos:

| D3 fuera de muestra | fps | tasa | n | predicha | medida | error | dentro de ±0.05 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `samurai_t640` | 30 | 0.179 | 25 | 0.304 | 0.295 | −0.009 | sí |
| `dam4sam_t640` | 30 | 0.164 | 25 | 0.286 | 0.270 | −0.016 | sí |
| `dam4sam_t960` | 30 | 0.086 | 25 | 0.145 | 0.161 | +0.016 | sí |
| `samurai_t640` | 120 | 0.046 | 24 | 0.124 | 0.111 | −0.012 | sí |
| `dam4sam_t640` | 120 | 0.042 | 24 | 0.114 | 0.117 | +0.003 | sí |
| `dam4sam_t960` | 120 | 0.023 | 24 | 0.055 | 0.073 | +0.017 | sí |

Ajuste sobre los seis brazos SAM2: `mIoU = +0.217·log(tasa) + 0.679`, R²=0.998 a 30 fps;
`+0.101·log(tasa) + 0.433`, R²=0.998 a 120. **Tal como se registró** (medianas por brazo, n
distinto) los seis errores salían −0.068/−0.065/−0.062 y −0.051/−0.056/−0.057: mismo signo y misma
magnitud en los seis, que es la firma de un sesgo de construcción y no de seis fallos.

| D4 `asym_lt − asym_b` | fps | salida | n | d mediana | gana | p | p Holm |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| | 30 | ZOH | 30 | −0.076 | 4/30 | 2.0e−06 | 6.0e−06 |
| | 30 | FOH | 30 | −0.096 | 3/30 | 1.2e−06 | 4.8e−06 |
| | 120 | ZOH | 30 | −0.003 | 8/30 | 3.6e−03 | 7.3e−03 |
| | 120 | FOH | 30 | −0.001 | 8/30 | 2.4e−02 | 2.4e−02 |

Sin los cinco clips que ajustaron sus umbrales: −0.075, −0.095, −0.005, −0.001 (n=25). La fuga no
mueve nada.

**La predicción de D4 sale falsada en la magnitud.** Se registró que `|d|` **crece** con fps;
crece al revés: 0.076 a 30 fps y 0.003 a 120. El sentido sí se acertó — `asym_lt` pierde en las
cuatro celdas — y la noticia registrada (que ganase bajo FOH a 120) no ocurre.

- **D0** (controles sin pausar, pareado por clip, n=30): `samurai_t640 − sam2_c704` −0.026 (7/30,
  p=0.013); `dam4sam_t640 − sam2_c704` −0.016 (8/30, p=0.005); `dam4sam_t960 − sam2_c704` +0.001
  (15/30, p=0.49). `asym_lt − asym_b` sobre n=53: −0.019 (10/53, p<0.001). Con los 10 clips que
  faltaban, la mIoU sin pausar de `samurai_t640` cae de **0.761 (n=20) a 0.699 (n=30)** — queda
  medido que aquel 0.761 era el subconjunto fácil, que es justo lo que §1 supuso sin poder medirlo.
- **Coste:** **2.41 h de dispositivo en 281 corridas**, contra ~1.9 h estimadas (+27%). Tres
  corridas de las 284 no existen: `dam4sam_t960` sobre `uav2`, `uav5` y `wakeboard7` a 120 fps
  aborta con `AssertionError: sequence too short to have any post-warmup frames` — el flujo dura
  1.1-1.7 s y el brazo necesita 7.3 s de arranque más 0.4 s por inferencia. Límite del protocolo,
  no fallo del brazo. La desviación del coste está casi entera en `xfam-30` (1.17 h contra 1.00
  estimada): la p50 pausada de los brazos DAM4SAM sale por encima de la sin pausar (214.0 contra
  204.0 ms en `t640`), o sea que la estimación por p50 sin pausar subestima.
- **Números esperados contra medidos** (mIoU pausada a 30 fps, ZOH, sobre los 25 comunes):
  `samurai_t640` ~0.28 estimada / 0.295 medida; `dam4sam_t640` ~0.28 / 0.270; `dam4sam_t960` ~0.17 /
  0.161. Estimar con la curva en vez de restando medianas de brazo acertó dentro de 0.02 en los
  tres. `asym_lt` ~0.64 estimada / 0.483 medida sobre 30 — ahí la estimación falla, y falla porque
  supuso tasa ~0.97 cuando la medida es 0.825.
- **Aserción barata:** ningún brazo devolvió la misma caja en todos los fotogramas procesados de
  ningún clip, en ninguna de las dos velocidades.
