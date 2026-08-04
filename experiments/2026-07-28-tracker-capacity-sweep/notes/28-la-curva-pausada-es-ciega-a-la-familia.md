# La curva pausada es ciega a la familia

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-08-04T14:00Z -> 2026-08-04T17:05Z, hora local de Madrid.
**Coste:** 281 corridas, **2.41 h de dispositivo** — `sum(init_ms + frames * ms_p50)` sobre los JSON.
**Datos:** `raw/xfam-pilot/`, `raw/xfam-unpaced-sam/`, `raw/xfam-unpaced-asymlt/`, `raw/xfam-30/`,
`raw/xfam-120/`.
**Código:** `analysis/cross_family.py`, `notes/PREREG-cross-family-pacing.md`; commits `2420381`,
`5f8c9b9`, `cf63ced`.

## 1. Por qué existe

La nota 27 cruzó de familia por primera vez y encontró que AsymTrack-B pausado le gana a
`sam2_c512` por un margen 2.8x mayor que cualquier eje interno de SAM2. Eso admite dos lecturas y la
nota 27 no puede separarlas:

- **Ley de coste.** Bajo pausa lo único que decide es cuántas respuestas por segundo entrega el
  brazo. La familia no entra. AsymTrack gana porque es 3.4x más barato, y cualquier otro brazo con
  el mismo coste ganaría lo mismo.
- **Ley de familia.** AsymTrack gana porque AsymTrack es distinto, y el coste es correlación.

Separarlas necesita brazos de **otra familia al coste de SAM2**, no por debajo. Eso es exactamente
lo que hay en el catálogo sin pausar: SAMURAI y DAM4SAM sobre `tiny` cuestan lo mismo que los
`sam2_c*` porque son el mismo backbone con otra política de memoria (notas 11, 12, 16). Si la ley de
coste vale, esos brazos tienen que caer **sobre la curva** de SAM2 pausada, no al lado.

Y la tanda cierra dos pendientes del registro: DAM4SAM y SAMURAI nunca se habían pausado, y
`asym_lt` — el brazo con reenganche de las notas 9, 14 y 15 — tampoco.

Pre-registrado en [`PREREG-cross-family-pacing.md`](PREREG-cross-family-pacing.md) con las cuatro
hipótesis, sus márgenes y la regla de falsación, sellado antes de lanzar nada.

## 2. Cómo corrió

Cinco pasadas en serie, una detrás de otra, porque dos drivers a la vez se pelean por la GPU y
corrompen justo la latencia sobre la que se apoya el protocolo pausado:

```
./jetson.py run --id xfam-pilot           --arms samurai_t640 dam4sam_t640 dam4sam_t960 asym_lt --seqs bike1 --fps 30
./jetson.py run --id xfam-unpaced-sam     --arms samurai_t640 --seqs <10 clips que faltaban> --fps 0
./jetson.py run --id xfam-unpaced-asymlt  --arms asym_lt      --seqs <30> --fps 0
./jetson.py run --id xfam-30              --arms samurai_t640 dam4sam_t640 dam4sam_t960 asym_lt --seqs <30> --fps 30
./jetson.py run --id xfam-120             --arms samurai_t640 dam4sam_t640 dam4sam_t960 asym_lt --seqs <30> --fps 120
```

Todo el análisis sale de un comando:

```
analysis/cross_family.py raw/full-sweep-30 raw/asym-repro raw/night-samurai raw/sam-full30 \
    raw/dam-full30b raw/asym-lt raw/xfam-unpaced-sam raw/xfam-unpaced-asymlt \
    raw/paced-sweep-30 raw/paced-family-30 raw/xfam-30 \
    raw/paced-grid-120 raw/paced-family-120 raw/xfam-120
```

**El piloto es una puerta, no un calentamiento.** Los cuatro brazos tenían que sobrevivir a `--fps
30` con una tasa de respuesta que cuadrase con su p50. Cuadra: `samurai_t640` 0.176 medida contra
0.176 predicha, `dam4sam_t640` 0.159 contra 0.156, `dam4sam_t960` 0.083 contra 0.084, `asym_lt`
0.908 con 56 fotogramas declarados perdidos — o sea que la maquinaria de reenganche sí dispara bajo
pausa y no está muerta.

El piloto también enseñó algo que no estaba previsto: **la p50 pausada no es la p50 sin pausar**.
`dam4sam_t960` mide 395.6 ms pausado contra 407.2 sin pausar, `t640` 214.0 contra 204.0. Las tasas
de respuesta se leen de la medición, nunca se predicen del coste sin pausar.

## 3. D1 y D2: los brazos de otra familia caen sobre la curva

Pareado por clip contra `sam2_c704`, que es el brazo SAM2 de coste equivalente, sobre los 25 clips
comunes (la puerta `upscales` quita los cinco de 720x480), Holm dentro de la familia de 8 contrastes
registrada:

| par | fps | salida | d mediana | gana | p Holm | dentro del margen |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| `samurai_t640 − sam2_c704` | 30 | ZOH | −0.003 | 9/25 | 5.7e−01 | sí |
| | 30 | FOH | −0.028 | 7/25 | 5.2e−03 | sí |
| | 120 | ZOH | +0.000 | 13/25 | 1.0e+00 | sí |
| | 120 | FOH | −0.004 | 10/25 | 1.0e+00 | sí |
| `dam4sam_t640 − sam2_c704` | 30 | ZOH | −0.018 | 3/25 | 4.6e−05 | sí |
| | 30 | FOH | −0.039 | 4/25 | 4.2e−05 | sí |
| | 120 | ZOH | −0.006 | 5/25 | 1.6e−03 | sí |
| | 120 | FOH | −0.030 | 6/25 | 1.5e−03 | sí |

**8 de 8 dentro.** La regla congelada declaraba falsada la ley de coste con >=19 de 25 clips del
mismo signo y Holm < 0.05 en >=2 de las 4 celdas de un par. Ninguna celda llega. Cambiar de familia
al mismo coste mueve la mIoU pausada como mucho 0.039, contra los 0.168 que la nota 27 midió
cambiando de coste.

**Cómo no sobreleerlo.** Esto es un **nulo acotado**, no una equivalencia. Lo que está medido es que
el efecto de familia cabe en un margen de ±0.05; no que sea cero. De hecho `dam4sam_t640` pierde de
forma consistente y con Holm < 0.05 en las cuatro celdas: gana 3, 4, 5 y 6 clips de 25. Es un efecto
real, y es pequeño. La lectura correcta es "la curva de coste predice, y la familia es un residuo",
no "da igual el brazo".

## 4. D3: la curva predice fuera de muestra, y la versión registrada estaba mal construida

D3 es la prueba dura. Se ajusta `mIoU = a·log(tasa) + b` **solo sobre los seis brazos SAM2**, y se
predice la mIoU de los tres brazos nuevos a partir de su tasa medida, sin haberlos visto:

| brazo | fps | tasa | predicha | medida | error |
| --- | ---: | ---: | ---: | ---: | ---: |
| `samurai_t640` | 30 | 0.179 | 0.304 | 0.295 | −0.009 |
| `dam4sam_t640` | 30 | 0.164 | 0.286 | 0.270 | −0.016 |
| `dam4sam_t960` | 30 | 0.086 | 0.145 | 0.161 | +0.016 |
| `samurai_t640` | 120 | 0.046 | 0.124 | 0.111 | −0.012 |
| `dam4sam_t640` | 120 | 0.042 | 0.114 | 0.117 | +0.003 |
| `dam4sam_t960` | 120 | 0.023 | 0.055 | 0.073 | +0.017 |

Ajuste: `+0.217·log(tasa) + 0.679` a 30 fps, `+0.101·log(tasa) + 0.433` a 120, R²=0.998 los dos.
Seis de seis dentro del ±0.05 registrado. Saber cuántas respuestas por segundo entrega un brazo
basta para predecir a 0.02 lo que puntúa, aunque el brazo sea de otra familia y no esté en el
ajuste.

**Corrección explícita sobre lo pre-registrado.** D3 se registró como medianas por brazo, y así
compara poblaciones distintas: los `c*` puntúan sobre 25 clips y los tres nuevos sobre 30. Corrido
tal cual, los seis errores salen **−0.068 / −0.065 / −0.062** a 30 fps y **−0.051 / −0.056 /
−0.057** a 120, todos fuera del margen, con R² 0.901 y 0.148. Mismo signo y misma magnitud en los
seis: eso no son seis fallos independientes, es un sesgo de construcción. Lo confirma D1, que sobre
el mismo par y el conjunto común da −0.003 donde la versión mixta daría −0.068. El analizador
imprime **las dos versiones** para que la corrección quede a la vista en vez de sustituida en
silencio.

**El contra, y es serio.** Son 6 puntos y 2 parámetros. Un R² de 0.998 con esa relación no es
evidencia de nada por sí mismo, y los seis brazos del ajuste comparten arquitectura. Lo que pesa
aquí es la predicción fuera de muestra sobre brazos que no entraron en el ajuste, no la bondad del
ajuste.

## 5. D4: `asym_lt` pierde, y la predicción registrada falla en la magnitud

Hipótesis secundaria, declarada como tal: `asym_lt` contra `asym_b`, mismo backbone, lo único que
cambia es la maquinaria de reenganche. Sobre los 30 clips, familia Holm propia:

| fps | salida | d mediana | gana | p Holm |
| ---: | --- | ---: | ---: | ---: |
| 30 | ZOH | −0.076 | 4/30 | 6.0e−06 |
| 30 | FOH | −0.096 | 3/30 | 4.8e−06 |
| 120 | ZOH | −0.003 | 8/30 | 7.3e−03 |
| 120 | FOH | −0.001 | 8/30 | 2.4e−02 |

Sin los cinco clips donde se ajustaron los umbrales `lt`: −0.075, −0.095, −0.005, −0.001 (n=25). La
fuga no mueve nada.

El sentido se acertó — pierde en las cuatro celdas — pero **la magnitud sale al revés de lo
registrado**. El pre-registro dice `|d|` **crece** con fps; crece hacia abajo: 0.076 a 30 fps contra
0.003 a 120. Y la noticia que el pre-registro marcaba como tal, que ganase bajo FOH a 120 fps, no
ocurre.

El mecanismo está en las declaraciones de pérdida. Fracción de fotogramas procesados que `asym_lt`
declara perdidos: 0.060 sin pausar, 0.031 a 30 fps, 0.014 a 120. `asym_b` a 30 fps: **0.000**, nunca
declara nada perdido. O sea que todo el hueco es `asym_lt` emitiendo `None` — que puntúa 0 bajo las
dos salidas — donde `asym_b` emite una caja que puede estar mal pero puntúa algo. Cuanto más agresiva
la pausa, menos fotogramas procesa `asym_lt` y menos ocasiones tiene de declararse perdido, así que
el castigo se diluye. No es que mejore: es que llega a menos sitios donde equivocarse.

## 6. `asym_lt` tiene dos regímenes de coste, no uno

Esto no estaba registrado y sale de mirar las p50 por clip. En 29 de los 30 clips `asym_lt` corre a
29-37 ms. En `bike2` corre a **178.9 ms, 5.6 fps, 429 de 553 fotogramas perdidos**. El
re-detector de 5 ventanas en ráster no se amortiza cuando el brazo se pasa el clip perdido: cada
fotograma perdido paga el barrido entero.

Importa más allá de `asym_lt`. La ley de coste de §3-§4 supone que el coste de un brazo es una
constante que no depende de si acierta. Un brazo con reenganche rompe ese supuesto: su tasa de
respuesta depende de si encuentra el objetivo, que es justo el acoplamiento que la ley asume
inexistente. Para los brazos de coste plano (todos los SAM2, AsymTrack-B, SAMURAI, DAM4SAM) la ley
se sostiene; para uno con re-detección, la tasa deja de ser un parámetro de diseño y pasa a ser una
salida.

## 7. D0: los controles sin pausar, y una corrección al catálogo

Con los 10 clips que le faltaban, la mIoU sin pausar de `samurai_t640` sobre los 30 clips es
**0.699**, no el **0.761** que estaba registrado. Aquel 0.761 salía de un subconjunto de 20 clips, y
queda medido que era el subconjunto fácil. Donde una nota anterior use 0.761 como número de
`samurai_t640` a n=30, hay que leer 0.699.

Pareado por clip, sin pausar, n=30: `samurai_t640 − sam2_c704` −0.026 (7/30, p=0.013);
`dam4sam_t640 − sam2_c704` −0.016 (8/30, p=0.005); `dam4sam_t960 − sam2_c704` +0.001 (15/30,
p=0.490); `asym_lt − asym_b` sobre n=53 −0.019 (10/53, p<0.001).

Los controles importan porque fijan la línea base: los tres brazos nuevos **ya perdían un poco**
contra `sam2_c704` sin pausar. La parte del déficit pausado de §3 que es atribuible a la pausa es la
que excede a esto, y en `samurai_t640` no excede nada — −0.026 sin pausar contra −0.003 pausado a 30
fps.

## 8. Estimación contra realidad

| | estimado | real |
| --- | ---: | ---: |
| corridas | 284 | 281 |
| dispositivo | ~1.9 h | **2.41 h** (+27%) |
| mIoU pausada 30 fps ZOH, `samurai_t640` | ~0.28 | 0.295 |
| `dam4sam_t640` | ~0.28 | 0.270 |
| `dam4sam_t960` | ~0.17 | 0.161 |
| `asym_lt` | ~0.64 | 0.483 |

Por pasada: `xfam-pilot` 4 corridas / 0.118 h, `xfam-unpaced-sam` 10 / 0.377 h,
`xfam-unpaced-asymlt` 30 / 0.306 h, `xfam-30` 120 / 1.166 h, `xfam-120` 117 / 0.443 h.

La desviación del coste está casi entera en `xfam-30` (1.17 h contra 1.00 estimada) y tiene la causa
identificada en §2: la p50 pausada de los DAM4SAM sale por encima de la sin pausar, así que estimar
con la p50 sin pausar subestima.

Las tres estimaciones de mIoU de los brazos nuevos aciertan dentro de 0.02 porque se hicieron **con
la curva**, que es circular — predecir con la curva lo que la curva va a predecir. La única
estimación independiente es la de `asym_lt`, y falla por 0.16: supuso tasa ~0.97 y la medida es
0.825.

**Tres corridas de las 284 no existen.** `dam4sam_t960` sobre `uav2`, `uav5` y `wakeboard7` a 120
fps aborta con `AssertionError: sequence too short to have any post-warmup frames` en
`code/run_arm.py:119`. A 120 fps esos flujos duran 1.1-1.7 s y el brazo necesita 7.3 s de arranque
más 0.4 s por inferencia: no llega a haber un solo fotograma posterior al calentamiento. Es un
límite estructural del protocolo, no un fallo. Las celdas no existen, no se perdieron. `uav2` y
`uav5` ya estaban fuera por la puerta `upscales`; el único que se cae de nuevo es `wakeboard7`, y
por eso el conjunto común a 120 fps es n=24 y no n=25.

## 9. Qué no se midió

**Sin verificación visual de esta tanda.** El pre-registro la hacía obligatoria solo si D1 o D2
salían falsadas, y no salieron. Sí corrió la aserción barata: ningún brazo devolvió la misma caja en
todos los fotogramas procesados de ningún clip, en ninguna de las dos velocidades — o sea que ningún
brazo se quedó congelado devolviendo la caja de inicialización.

Fuera del alcance: 15 y 60 fps para los brazos nuevos (solo 30 y 120); cualquier brazo de otra
familia **por debajo** del coste de SAM2 que no sea AsymTrack; y el régimen caro de `asym_lt` de §6,
que se ve en un solo clip y no se caracterizó.

## 10. Interpretación

Marcado como interpretación, no como medida.

Juntando esta nota con la 27: bajo pausa, lo que decide la puntuación es **cuántas respuestas por
segundo entrega el brazo**, y la identidad del brazo es un residuo de ±0.04. Eso es una mala noticia
para la elección de tracker y una buena para el diseño del sistema. Mala porque significa que la
campaña entera de las notas 11 a 18 — política de memoria, dtype, resolución, geometría de ventana —
mide efectos que la pausa borra. Buena porque reduce la decisión a un solo número medible en la
placa: la tasa sostenida.

El límite de esa lectura está en §6. La ley vale para brazos de coste plano. En cuanto un brazo
reacciona a su propio error — re-detectar, ampliar ventana, subir resolución bajo duda — su tasa deja
de ser un parámetro y la curva deja de ser una predicción.
