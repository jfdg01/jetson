# Pre-registro: la familia barata contra la rejilla pausada

Parte de [`../README.md`](../README.md). **Sellado: 2026-08-04T13:05Z** (hora local de Madrid).
**Estado: CERRADO 2026-08-04T13:28Z. A1 NO gana (ZOH 4/4, FOH 2/4; hacían falta >=3 por salida).**
Resultado completo en [`27-la-familia-barata-bajo-pausa.md`](27-la-familia-barata-bajo-pausa.md).

## 1. Por qué existe, y por qué es un fallo de diseño de la campaña

Las notas 19, 20, 23, 24, 25 y 26 son unas 7 h de dispositivo sobre el protocolo pausado, y **todas
comparan SAM2 contra SAM2**. La conclusión que han ido construyendo es que bajo pausa la ordenación
de brazos es **por coste**: la nota 25 la ve idéntica de 15 a 120 fps, y la nota 26 la descompone y
encuentra que el eje `c512`-`c640` es un eje de coste y no de contexto.

Si la ordenación pausada es por coste, la pregunta que sigue no es qué resolución de SAM2 elegir. Es
por qué se está pausando la familia cara. Latencia mediana por fotograma sin pausar, medida sobre los
JSON que ya están en `raw/`:

| brazo | ms p50 | fps sostenidos | mIoU mediana sin pausar |
| --- | ---: | ---: | ---: |
| `asym_b` (AsymTrack-B) | **29.6** | **33.8** | 0.687 |
| `sam2_c512` | 100.9 | 9.9 | 0.679 |
| `sam2_c640` | 159.3 | 6.3 | 0.758 |

**AsymTrack-B empata con `sam2_c512` sin pausar y cuesta 3.4x menos.** Pareado sobre los 30 clips
comunes, `asym_b − sam2_c512` da mediana **−0.009 (14/30)**: un empate. Y es el único brazo del
catálogo entero que sostiene más de 30 fps en esta placa, así que **a 30 fps no tiene déficit de
pausa que corregir**: su mIoU pausado debería ser su mIoU sin pausar.

El control `sam2_c512` pausado a 30 fps vale 0.435. La diferencia que esto predice es de orden
**+0.25**, contra el +0.06 que es el efecto más grande medido en todo el eje de resolución de SAM2.
Si sale, "el punto de operación pausado es `sam2_c512`" deja de ser un enunciado sobre la placa y
pasa a ser un enunciado sobre una familia — que es el mismo error de alcance que la nota 26 acaba de
corregir en el otro eje.

Descartado para esta tanda: bajar la entrada del modelo por debajo de 512 (`w512_i384`, `w512_i256`).
Es la extrapolación directa de la nota 26 y está en `TODO.md`, pero el efecto esperado es de orden
+0.06 dentro de la familia cara y la nota 04 ya predice su forma (la atención de memoria solo ve el
nivel de stride 16, así que un objeto de 28 px a entrada 512 cae a 0.875 celdas a entrada 256 — el
colapso subcelular que ya explica `t640` contra `c640`). Este eje es 4x más grande y ataca la validez
de todo el arco, no la extiende.

## 2. Cómo va a correr

```
S="bike1 bike2 bird1_1 bird1_3 boat3 boat6 building5 car12 car1_3 car16_1 car8_2 car9 \
   group1_2 group2_3 person18 person19_3 person20 person21 person4_1 truck2 truck3 \
   uav1_2 uav2 uav3 uav5 uav7 wakeboard1 wakeboard5 wakeboard7 wakeboard8"

./jetson.py run --id paced-family-pilot --arms asym_b --seqs bike1 --fps 30

for F in 15 30 60 120; do
  ./jetson.py run --id paced-family-$F --arms asym_b --seqs $S --fps $F
done
```

(Las notas 19 y 20 escriben el `--seqs` en taquigrafía, `raw/full-sweep-30` / `<las 30 de ...>`;
son los 30 clips de arriba, que es lo que `--seqs` come de verdad — una lista de nombres.)

15 W mode 0 + `jetson_clocks`, `schedutil`, L4T R36.5.0, semilla 0, un proceso por (brazo, clip),
orden barajado. Controles `sam2_c512`: **ya en disco**, `raw/paced-grid-15/`, `raw/paced-sweep-30/`,
`raw/paced-grid-60/`, `raw/paced-grid-120/`. No se recorren: la nota 26 §5 midió la reproducibilidad
del protocolo pausado entre dos sesiones (rho 0.995/0.999, `|d|` mediana 0.002, sin sesgo), así que
la reutilización está validada por una medida y no por una suposición. La celda de cheque será
`bike1` y **no** `person18` — la nota 26 §5 dejó dicho que la celda de cheque se elige por
estabilidad conocida y `person18` es el único clip bimodal del conjunto.

**Piloto antes de las cuatro tandas.** `asym_b` se registró antes de que existiera el protocolo
pausado y nunca ha corrido con `--fps`. Un clip a 30 fps primero; si la tasa de respuesta no sale
≈1.0 o el brazo peta, la tanda se para y el piloto es el resultado.

## 3. El conjunto de clips, y el sesgo que trae

`sam2_c512` pausado solo existe sobre **25 clips**: la puerta `upscales` tumba los cinco de 720x480
(`uav1_2`, `uav2`, `uav3`, `uav5`, `uav7`) porque una ventana de 512 sobre 480 de alto inventaría
píxeles. `asym_b` no recorta y corre los 30, así que el contraste pareado es **n=25 por
construcción**.

**Esto favorece a `asym_b` y hay que decirlo antes de mirar.** Cuatro de sus cinco peores clips de
todo el conjunto son `uav*` (`uav5` 0.06, `uav3` 0.14, `uav7` 0.22), o sea que la puerta le quita
justo donde es malo. La n=25 es la única comparación pareada posible, pero el mIoU absoluto de
`asym_b` sobre los cinco `uav*` se reporta aparte, sin control y etiquetado como tal, para que la
tabla no se lea como si el brazo fuera bueno en toda la placa.

## 4. Hipótesis y umbrales

Familia Holm pre-registrada: **8 contrastes** — `asym_b − sam2_c512` pareado por clip, a 15/30/60/120
fps, bajo las dos reglas de consumidor (ZOH y FOH). Wilcoxon, n=25.

- **A1 (la principal).** `asym_b` gana al punto de operación pausado. Se declara ganada si la mediana
  es > 0 con **>= 19 de 25** clips y Holm < 0.05 en **>= 3 de las 4 velocidades bajo ZOH y >= 3 de las
  4 bajo FOH**. Exigir las dos salidas es deliberado: la nota 26 §8 acaba de medir que FOH aplana el
  eje de coste a la mitad, así que ZOH es el mejor caso para un brazo barato y ganar solo ahí sería
  un artefacto del consumidor congelador, no un resultado.
- **A2 (la forma).** La ventaja crece con fps mientras `asym_b` siga en tiempo real y se satura o cae
  cuando él también empieza a tirar fotogramas — el codo está en sus 33.8 fps sostenidos, o sea entre
  30 y 60. Descriptiva, sin contraste propio: la sostienen las cuatro medianas de A1.
- **A3 (el mecanismo, cheque duro del protocolo).** La tasa de respuesta debe seguir
  `min(1, fps_sostenidos / F)`. Ese modelo predice la tasa medida de `sam2_c512` con cuatro cifras
  (predice 0.660 / 0.330 / 0.165 / 0.083 contra 0.663 / 0.332 / 0.166 / 0.084 medidas), así que para
  `asym_b` predice **1.00 / 1.00 / 0.56 / 0.28**. Si la tasa medida se desvía más de 0.05 de eso, la
  latencia p50 no describe el protocolo para este brazo y **A1 no se interpreta** hasta entender por
  qué.
- **A0 (el control, ya en disco).** Sin pausar el contraste es un empate (mediana −0.009, 14/30). Es
  lo que hace que cualquier ventaja pausada sea atribuible al coste y no a que AsymTrack sea mejor
  seguidor.

**Qué falsa esto.** Que `asym_b` pierda bajo FOH. Sería la lectura contraria: la ventaja del brazo
barato existe solo cuando el consumidor congela, un consumidor que interpola la recupera, y entonces
el arco SAM2 de las notas 19-26 se sostiene tal cual.

## 5. Estimaciones (son estimaciones)

| tanda | corridas | coste estimado |
| --- | ---: | ---: |
| 4 velocidades x 30 clips | 120 | **~0.9 h** |
| piloto | 1 | ~0.01 h |

`sum(init_ms + frames * ms_p50)` sobre 27276 fotogramas a 29.6 ms = 0.22 h por pasada. Es cota
superior: bajo pausa el brazo procesa menos fotogramas de los que tiene el clip, así que a 60 y 120
fps el coste real debería salir por debajo. Reloj de pared esperado bastante mayor que el coste
modelado (la nota 25 midió `pared ~= n_corridas * 38 s + 27276 s / fps` por pasada).

Números esperados, **estimados** desde la tasa de respuesta y el mIoU sin pausar de 0.687:

| fps | `sam2_c512` medido | `asym_b` estimado | d estimada |
| ---: | ---: | ---: | ---: |
| 15 | 0.574 | ~0.69 | ~+0.11 |
| 30 | 0.435 | ~0.69 | ~+0.25 |
| 60 | 0.251 | ~0.60 | ~+0.35 |
| 120 | 0.146 | ~0.50 | ~+0.35 |

## 6. Verificación visual

No es precondición de A1: el contraste es numérico y pareado, y la nota 26 §6 ya dejó dicho que las
afirmaciones sobre píxeles necesitan píxeles mirados. **Se vuelve obligatoria si A1 gana**, y sobre
un clip elegido antes de mirar los resultados: `person20` (objeto grande, sin huecos de GT, el clip
donde los dos brazos deberían estar sanos) más el peor clip común de `asym_b` dentro de los 25. Sin
eso no se afirma nada sobre lo que el brazo hace en pantalla.

## 7. Resultados (TBD)

| fps | salida | n | d mediana | gana | p | p Holm | tasa `asym_b` | tasa predicha |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 15 | ZOH | 25 | +0.068 | 19/25 | 9.6e−03 | **3.9e−02** | 0.993 | 1.000 |
| 15 | FOH | 25 | +0.050 | 16/25 | 7.1e−02 | 7.3e−02 | — | — |
| 30 | ZOH | 25 | +0.168 | 20/25 | 6.3e−04 | **3.9e−03** | 0.972 | 1.000 |
| 30 | FOH | 25 | +0.082 | 20/25 | 1.1e−02 | **3.9e−02** | — | — |
| 60 | ZOH | 25 | +0.151 | 19/25 | 5.6e−04 | **3.9e−03** | 0.521 | 0.569 |
| 60 | FOH | 25 | +0.071 | 18/25 | 3.7e−02 | 7.3e−02 | — | — |
| 120 | ZOH | 25 | +0.167 | 22/25 | 6.6e−06 | **5.2e−05** | 0.245 | 0.284 |
| 120 | FOH | 25 | +0.095 | 19/25 | 2.8e−03 | **1.4e−02** | — | — |

- **A0** cumplido: sin pausar −0.009, 14/30, p=0.97.
- **A3** cumplido: desvío máximo 0.048 sobre el 0.05 registrado, sistemático y explicado (§4 de la nota).
- **A1 NO gana:** ZOH 4/4, FOH 2/4. Las ocho medianas positivas y seis de ocho con Holm < 0.05, pero
  la regla congelada pedía >= 3 de 4 en cada salida. No se dobla.
- **A2 falla como estaba escrita:** la ventaja no crece con fps, es un escalón entre 15 y 30, y el
  codo no está donde `asym_b` empieza a tirar fotogramas sino donde deja de estar topado a 1.0.
- **Coste:** 0.85 h medidas contra 0.9 h estimadas. Efecto a 30 fps +0.168 contra ~+0.25 estimado —
  la estimación restaba medianas de brazo sobre poblaciones distintas.
