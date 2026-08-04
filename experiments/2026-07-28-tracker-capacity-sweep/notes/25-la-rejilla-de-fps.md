# 25. La rejilla de fps: el orden de brazos no se mueve, y `lead` deja de estar acotado

Parte de [`../README.md`](../README.md). Cierra
[`PREREG-paced-fps-grid.md`](PREREG-paced-fps-grid.md), sellado el 2026-08-02T23:45Z.

**Cuándo:** tandas de dispositivo el 2026-08-03 — los tramos de 120 y 60 fps entre las ~01:40Z y las
02:55Z (commit `64c86f8`), el de 15 fps antes de las 12:05Z (commit `6aed9de`). El manifiesto no
sella hora, así que la ventana se acota por los commits, no se mide. Análisis 2026-08-04T09:20Z ->
11:10Z (hora local de Madrid).
**Coste:** 435 corridas, **3.30 h de dispositivo** — `sum(init_ms + frames * ms_p50)` sobre los JSON.
La columna de 30 fps se reutiliza de las notas 19 y 20 y ya está cobrada allí.
**Datos:** `raw/paced-grid-15/`, `raw/paced-grid-60/`, `raw/paced-grid-120/`, y de las notas
anteriores `raw/paced-sweep-30/`, `raw/paced-lead-30/`
**Código:** `analysis/fps_grid.py` (la columna `d/niv` se añade en el commit de esta nota).

## 1. Por qué existe

El barrido tenía las dos mitades sueltas y ninguna junta: sin pausar gana `sam2_c640` (nota 2) y
pausado a 30 fps gana `sam2_c512` (nota 19). Un único corte a 30 fps no es una curva, así que no se
sabía si el punto de operación se **mueve** con la velocidad del flujo o si la nota 19 era ruido de
un corte. Con `--fps F` el intervalo de descarte es `latencia x F` fotogramas, o sea que subir fps es
exactamente "el mismo dispositivo contra una escena que se mueve más rápido" — el régimen de la
Jetson a 15 W en vuelo.

```
analysis/fps_grid.py raw/paced-sweep-30 raw/paced-lead-30 \
                     raw/paced-grid-15 raw/paced-grid-60 raw/paced-grid-120
```

## 2. La rejilla

mIoU mediana, salida ZOH, n de clips entre paréntesis:

| brazo | 15 fps | 30 fps | 60 fps | 120 fps |
| --- | ---: | ---: | ---: | ---: |
| `sam2_c512` | 0.574 (25) | 0.439 (25) | 0.251 (25) | 0.146 (25) |
| `sam2_c512_lead` | 0.586 (25) | 0.443 (25) | 0.287 (25) | 0.141 (25) |
| `sam2_c640` | 0.511 (25) | 0.344 (25) | 0.191 (25) | 0.111 (25) |
| `sam2_c704` | — | 0.302 (25) | 0.160 (25) | 0.105 (25) |
| `sam2_t512` | — | 0.342 (30) | 0.156 (30) | 0.073 (30) |
| `sam2_t640` | — | 0.308 (25) | 0.168 (25) | 0.107 (25) |
| `sam2_t768` | — | 0.242 (25) | 0.116 (25) | 0.095 (25) |

Tasa de respuesta de `sam2_c512` (fotogramas procesados / fotogramas del flujo): 0.663, 0.332,
0.166, 0.084. A 120 fps el brazo contesta una vez cada doce fotogramas.

**La ordenación de brazos es la misma en las cuatro columnas**: `c512_lead` ~ `c512` > `c640` >
`c704` > `t640` > `t768`, y `t512` se descuelga al fondo salvo a 30 fps. El punto de operación
pausado **no se mueve entre 15 y 120 fps**; lo que se mueve es cuánto separa a unos de otros.

## 3. H1 — la ventaja de `c512` es real a las cuatro velocidades

`sam2_c512` menos `sam2_c640`, pareado por clip, ZOH:

| fps | n | d mediana | gana | p | d/niv |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 15 | 25 | +0.054 | 23/25 | 1.3e−03 | 9.5% |
| 30 | 25 | +0.060 | 22/25 | 1.3e−03 | 13.6% |
| 60 | 25 | +0.071 | 23/25 | 4.3e−04 | 28.4% |
| 120 | 25 | +0.035 | 22/25 | 2.5e−04 | 24.0% |

**Lo primero, y es lo que más importa: la nota 19 no era un corte de ruido.** El signo es positivo y
significativo en las cuatro velocidades, con 22-23 clips de 25 en todas. El resultado se sostiene
sobre un eje entero, no sobre un punto.

En absoluto la diferencia sube hasta 60 fps y **cae a 120**, que es una U invertida y no la subida
monótona que H1 predijo. Pero el nivel de mIoU se desploma por el camino (0.574 a 0.146), así que una
diferencia absoluta menor puede ser sólo la escala encogiendo. La columna `d/niv` — la diferencia
mediana dividida por el nivel mediano de `c512` a ese fps — deja 9.5%, 13.6%, 28.4%, 24.0%: **crece
hasta 60 fps y satura**, no se da la vuelta.

Veredicto: **H1 confirmada en dirección, corregida en forma.** La ventaja de bajar de resolución
crece con la velocidad del flujo, pero se agota alrededor de 60 fps en vez de seguir creciendo. Y la
otra mitad de la predicción — "a 15 fps se estrecha o se invierte hacia `c640`" — se estrecha (9.5%
contra 13.6%) pero **no se invierte**: a 15 fps `c512` sigue ganando 23 de 25. El cruce hacia `c640`
que la nota 2 mide sin pausar tiene que estar **por debajo de 15 fps**, y esta rejilla no lo alcanza.

## 4. H2 — FOH corrige retardo, pero no se apaga al bajar fps

FOH menos ZOH, pareado sobre todos los pares brazo-clip:

| fps | n | d mediana | gana | p | d/niv |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 15 | 75 | +0.047 | 57/75 | 1.2e−08 | 8.2% |
| 30 | 180 | +0.069 | 142/180 | 2.8e−22 | 15.6% |
| 60 | 180 | +0.072 | 151/180 | 5.7e−25 | 28.7% |
| 120 | 180 | +0.043 | 137/180 | 1.6e−21 | 29.4% |

Normalizado la serie es monótona y saturante: 8.2%, 15.6%, 28.7%, 29.4%. **La mitad de H2 que decía
"crece con fps" se confirma. La mitad que decía "baja hacia 0 a 15 fps" es falsa**: a 15 fps FOH
sigue recuperando el 8.2% del nivel con p=1.2e−08 sobre 75 pares. A 15 fps la tasa de respuesta es
0.663, o sea que aún se retienen 1.5 fotogramas por respuesta — hay retardo que corregir, poco pero
sistemático. La predicción de que se anulara asumía que a 15 fps el dispositivo ya alcanza el flujo,
y no lo alcanza: `sam2_c512` corre a ~10 Hz.

**H1 y H2 saturan las dos alrededor de 60 fps.** Interpretación, marcada como tal: a partir de ahí la
tasa de respuesta es <= 0.166 y el régimen está dominado por el retardo; añadir más retardo ya no
cambia ni la ordenación de brazos ni lo que una regla de consumidor puede recuperar. No es una
medida de que exista un codo — son cuatro puntos y el codo cae en uno interior.

## 5. H3 — `lead` sigue nulo a 120 fps: el nulo deja de estar acotado

`sam2_c512_lead` menos `sam2_c512`, pareado por clip. `salto px` es el desplazamiento mediano del
objetivo entre dos respuestas consecutivas:

| fps | salida | n | d mediana | gana | p | salto px |
| ---: | :--- | ---: | ---: | ---: | ---: | ---: |
| 15 | ZOH | 25 | +0.001 | 17/25 | 2.0e−01 | 2.2 |
| 15 | FOH | 25 | +0.000 | 13/25 | 7.3e−01 | — |
| 30 | ZOH | 25 | +0.001 | 15/25 | 3.1e−01 | 4.6 |
| 30 | FOH | 25 | −0.001 | 11/25 | 6.3e−01 | — |
| 60 | ZOH | 25 | +0.001 | 13/25 | 9.2e−01 | 9.0 |
| 60 | FOH | 25 | **−0.006** | 6/25 | 8.8e−03 | — |
| 120 | ZOH | 25 | −0.001 | 9/25 | 1.0e−01 | 16.9 |
| 120 | FOH | 25 | +0.000 | 13/25 | 7.1e−01 | — |

El salto entre respuestas crece 7.7x (2.2 a 16.9 px) y `lead` no despierta. La única celda
significativa es 60 fps bajo FOH, va **en contra** de `lead` (−0.006, 6/25) y no sobrevive a Holm
sobre las ocho celdas de la familia: 8 x 8.8e−03 = 7.0e−02. Magnitud −0.006 sobre un nivel de 0.251,
o sea 2.4%.

La firma de memoria envenenada tampoco aparece. Déficit de `lead` por tercio de clip, tercero menos
primero: −0.003 (15 fps, p=0.20), +0.001 (30, p=0.31), +0.001 (60, p=0.26), −0.003 (120, p=5.2e−02).
Ni significativo ni monótono, y del tamaño del redondeo.

**Corrección explícita a la nota 20.** Donde la nota 20 §8 dice que su nulo de `lead` está *acotado
al régimen de 30 fps*, hay que leer: el nulo se sostiene de 15 a 120 fps, con el salto entre
respuestas multiplicado por 7.7 y con las dos reglas de consumidor. Por el pre-registro §H3 —
"si `lead` sigue nulo a 120 fps, el nulo deja de estar acotado y pasa a ser un resultado" — **esto es
un resultado, no un nulo acotado**: predecir el movimiento para colocar la ventana de entrada no
compra precisión en este seguidor a ninguna velocidad de flujo medida. Sigue acotado a *esta* forma
de predicción (velocidad de las dos últimas respuestas) y a este seguidor.

La nota 20 §8 también decía "`lead` a fps más bajos, donde el intervalo de descarte crece", que está
al revés; el pre-registro ya lo corrigió antes de correr y la rejilla lo confirma: el intervalo de
descarte crece con fps **a la alza**.

## 6. Estimación contra realidad

| | estimado | real |
| --- | ---: | ---: |
| coste de dispositivo, 3 tramos | ~4.6 h (pre-registro, 7 brazos x 3 fps) | **3.30 h** con el tramo de 15 fps recortado a 3 brazos |
| reloj de pared, 3 tramos | ~7.6 h (desviación del 01:35Z) | no medido: el manifiesto no sella hora |

Las dos cifras estimadas eran de métricas distintas y ninguna es comparable directamente con la otra.
La del pre-registro (4.6 h) es `sum(init_ms + frames * ms_p50)`, tiempo de inferencia; la de la
desviación (7.6 h) es reloj de pared, que añade ~38 s fijos por corrida de arranque, montaje y
lectura. La comparable con las 3.30 h medidas es la primera, y el recorte del tramo de 15 fps a tres
brazos explica la mayor parte de la diferencia.

**El recorte se ejecutó como se pre-registró**: a 15 fps corrieron `c512`, `c640` y `c512_lead`, los
tres brazos que sostienen las tres hipótesis. La fila de `t512`/`t640`/`t768`/`c704` está completa a
30/60/120 y ausente a 15, y así hay que leer la tabla de la §2.

**Deuda encontrada:** `manifest.json` no guarda hora de inicio ni de fin, así que el reloj de pared
de una tanda sólo se puede acotar por los commits. Estimar con una métrica y medir con otra ya pasó
aquí una vez; sellar la hora en el manifiesto lo arregla de raíz. Anotado en `TODO.md`.

## 7. Cómo no sobreleer

- **Cuatro puntos no son una curva.** La saturación de H1 y H2 alrededor de 60 fps son cuatro
  medianas con el codo en un punto interior medido una vez. Es una forma, no una ley.
- **`d/niv` es un cociente de dos medianas** sobre los mismos clips, no una cantidad pareada, y no
  tiene intervalo. Mismo caveat que `% del techo` en la nota 24. Corrige escala a ojo, no sustituye a
  un modelo.
- **La fila `sam2_t512` tiene n=30, las demás n=25** — no pasa la puerta `upscales` porque su entrada
  no supera los 480 px de alto de los `uav*`. Su columna **no es comparable** con las otras filas de
  la tabla de la §2; los contrastes de H1/H2/H3 no la usan.
- **H2 empareja pares brazo-clip, no clips.** Los 180 pares son 7 brazos x 25 clips y **no son
  independientes**: el mismo clip aparece siete veces. El p de 5.7e−25 hay que leerlo como "esto pasa
  en todos los brazos", no como 180 observaciones independientes.
- **El tramo de 15 fps tiene 75 pares en H2, no 180**, porque sólo corrieron tres brazos.
- **La etiqueta "120 fps" es del arnés, no de la cámara.** Los clips son de 30 fps nativos; servirlos
  a 120 es la misma escena contra un dispositivo 4x más lento. Es la variable que interesa (cómputo
  contra movimiento), pero no es un objetivo real a 120 Hz.
- **Contrastes múltiples:** las tres hipótesis de arriba son las únicas pre-registradas. La única
  celda exploratoria que salió significativa (60 fps FOH en H3) se corrigió por Holm dentro de su
  familia de 8 y no sobrevive.

## 8. Qué no se midió

**Sin verificación visual de esta tanda.** Todo son cajas ya en disco puntuadas contra GT; no hay
aquí ninguna afirmación sobre lo que se ve en pantalla. (La verificación en píxeles de esta noche
está en la nota 26, que sí la necesitaba.)

No se midió: el cruce hacia `c640`, que está por debajo de 15 fps y haría falta un tramo a 5-10 fps
para verlo; el techo `GT(i)` por velocidad, así que no se sabe si el 51% que FOH recupera (nota 24)
se mueve con fps; los cuatro brazos que faltan en la columna de 15 fps; ningún fps entre 15 y 30 ni
entre 60 y 120, que es donde caen los dos codos que esta nota describe.
