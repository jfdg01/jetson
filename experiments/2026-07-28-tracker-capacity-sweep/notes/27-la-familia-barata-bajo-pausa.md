# La familia barata bajo pausa: AsymTrack-B contra el punto de operación

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-08-04T12:10Z -> 2026-08-04T13:28Z, hora local de Madrid.
**Coste:** 121 corridas, **0.85 h de dispositivo** — `sum(init_ms + frames * ms_p50)` sobre los JSON.
**Datos:** `raw/paced-family-pilot/`, `raw/paced-family-{15,30,60,120}/`; controles reutilizados de
`raw/full-sweep-30/`, `raw/asym-repro/`, `raw/paced-grid-15/`, `raw/paced-sweep-30/`,
`raw/paced-grid-60/`, `raw/paced-grid-120/`.
**Código:** `analysis/paced_family.py`, `notes/PREREG-paced-family.md`.

## 1. Por qué existe

Las notas 19 a 26 son unas 7 h de dispositivo sobre el protocolo pausado y **todas comparan SAM2
contra SAM2**. Lo que fueron construyendo es que bajo pausa la ordenación de brazos es por coste: la
nota 25 la ve idéntica de 15 a 120 fps, la nota 26 la descompone y encuentra que el eje `c512`-`c640`
es de coste y no de contexto.

Si eso es cierto, la pregunta que sigue no es qué resolución de SAM2 elegir. Es por qué se está
pausando la familia cara. AsymTrack-B cuesta 29.3 ms por fotograma contra los 100.9 de `sam2_c512`,
sostiene 34.1 fps contra 9.9 en esta placa, y **sin pausar es un empate**: pareado sobre los 30
clips comunes, `asym_b − sam2_c512` da mediana −0.009, gana 14/30, p=0.97. Ese empate es lo que hace
interpretable cualquier ventaja pausada — no es que AsymTrack siga mejor, es que llega antes.

Pre-registrado en [`PREREG-paced-family.md`](PREREG-paced-family.md), sellado a las 13:05Z antes de
lanzar nada.

## 2. Cómo corrió

```
S="bike1 bike2 bird1_1 bird1_3 boat3 boat6 building5 car12 car1_3 car16_1 car8_2 car9 \
   group1_2 group2_3 person18 person19_3 person20 person21 person4_1 truck2 truck3 \
   uav1_2 uav2 uav3 uav5 uav7 wakeboard1 wakeboard5 wakeboard7 wakeboard8"

./jetson.py run --id paced-family-pilot --arms asym_b --seqs bike1 --fps 30
for F in 15 30 60 120; do
  ./jetson.py run --id paced-family-$F --arms asym_b --seqs $S --fps $F
done
```

15 W mode 0 + `jetson_clocks`, `schedutil`, L4T R36.5.0, semilla 0, un proceso por (brazo, clip). Las
cuatro pasadas **en serie**: dos drivers a la vez en la placa se disputan la GPU y corrompen la
latencia sobre la que está montado todo el protocolo.

Los controles `sam2_c512` no se recorrieron. La nota 26 §5 midió la reproducibilidad del protocolo
pausado entre dos sesiones (rho 0.995/0.999, `|d|` mediana 0.002, sin sesgo), así que la
reutilización está validada por una medida y no por una suposición.

**Piloto.** `asym_b` se registró antes de que el protocolo pausado existiera y nunca había corrido
con `--fps`. En `bike1` a 30 fps: 3021 de 3085 fotogramas del flujo = tasa 0.979, `p50` 31.7 ms, cero
caídas. El brazo corre pausado sin tocarle nada.

**Taquigrafía corregida.** Las notas 19 y 20 escriben `--seqs raw/full-sweep-30` y `--seqs <las 30 de
paced-sweep-30>`. El flag come una lista de nombres, no una ruta; el bloque de arriba lleva los 30
reales y es copiable.

## 3. El conjunto de clips, y el sesgo que trae

`sam2_c512` pausado solo existe sobre **25 clips**: la puerta `upscales` tumba los cinco de 720x480
(`uav1_2`, `uav2`, `uav3`, `uav5`, `uav7`) porque una ventana de 512 sobre 480 de alto inventaría
píxeles. `asym_b` no recorta (`image_size=None`, la puerta no le aplica) y corre los 30, así que el
contraste pareado es **n=25 por construcción**.

**Esto favorece a `asym_b`, y se dijo en el pre-registro antes de mirar nada.** Cuatro de sus cinco
peores clips del conjunto entero son `uav*`, o sea que la puerta le quita justo donde es malo. Su
mIoU absoluto ahí, sin control porque no existe ninguno:

| clip | sin pausar | 15 fps | 30 fps | 60 fps | 120 fps |
| --- | ---: | ---: | ---: | ---: | ---: |
| `uav1_2` | 0.429 | 0.345 | 0.385 | 0.219 | 0.271 |
| `uav2` | 0.437 | 0.274 | 0.214 | 0.151 | 0.066 |
| `uav3` | 0.143 | 0.276 | 0.129 | 0.008 | 0.007 |
| `uav5` | 0.058 | 0.445 | 0.450 | 0.007 | 0.069 |
| `uav7` | 0.217 | 0.172 | 0.157 | 0.005 | 0.005 |

Tres de los cinco caen por debajo de 0.01 a 60 fps. **No es degradación: es pérdida total.** La
tabla de §4 no ve nada de esto.

## 4. A3 primero: el protocolo hace lo que dice

Registrado como cheque duro, y se mira antes que el resultado porque si falla el resultado no se
interpreta. La tasa de respuesta debe seguir `min(1, fps_sostenidos / F)`:

| fps | medida | predicha | desvío |
| ---: | ---: | ---: | ---: |
| 15 | 0.993 | 1.000 | −0.007 |
| 30 | 0.972 | 1.000 | −0.028 |
| 60 | 0.521 | 0.569 | −0.048 |
| 120 | 0.245 | 0.284 | −0.040 |

Dentro del 0.05 registrado en las cuatro, pero **con el 60 fps rozándolo**, y el desvío es sistemático
y negativo. La causa está medida: el `p50` de `asym_b` sube de 29.3 ms sin pausar a 30.4 ms bajo
pausa, porque decodificar con salto cuesta. Con esa constante las predicciones son 1.000 / 1.000 /
0.547 / 0.275 y el desvío cae a −0.007 / −0.028 / −0.026 / −0.030. O sea: el modelo es correcto y la
constante venía de la corrida sin pausar. **No se toca el umbral** — el registrado se cumple; esto es
la explicación del residuo, no un rescate.

## 5. A1: el resultado, y no gana

```
analysis/paced_family.py raw/full-sweep-30 raw/asym-repro \
    raw/paced-grid-15 raw/paced-sweep-30 raw/paced-grid-60 raw/paced-grid-120 \
    raw/paced-family-15 raw/paced-family-30 raw/paced-family-60 raw/paced-family-120
```

`asym_b − sam2_c512`, pareado por clip, n=25, familia Holm de 8 contrastes:

| fps | salida | d mediana | gana | p | p Holm |
| ---: | --- | ---: | ---: | ---: | ---: |
| 15 | ZOH | +0.068 | 19/25 | 9.6e−03 | **3.9e−02** |
| 15 | FOH | +0.050 | 16/25 | 7.1e−02 | 7.3e−02 |
| 30 | ZOH | +0.168 | 20/25 | 6.3e−04 | **3.9e−03** |
| 30 | FOH | +0.082 | 20/25 | 1.1e−02 | **3.9e−02** |
| 60 | ZOH | +0.151 | 19/25 | 5.6e−04 | **3.9e−03** |
| 60 | FOH | +0.071 | 18/25 | 3.7e−02 | 7.3e−02 |
| 120 | ZOH | +0.167 | 22/25 | 6.6e−06 | **5.2e−05** |
| 120 | FOH | +0.095 | 19/25 | 2.8e−03 | **1.4e−02** |

Umbral registrado: mediana > 0, gana >= 19/25, Holm < 0.05, en **>= 3 de 4 velocidades bajo cada
salida**. Sale **ZOH 4/4, FOH 2/4**.

**A1 NO gana.** Aplicación mecánica de la regla congelada, sin doblarla. Falla en 15 fps FOH (16/25,
Holm 0.073) y en 60 fps FOH (18/25, Holm 0.073) — las dos por el conteo de victorias *y* por Holm,
así que no es un caso límite de un solo criterio.

**Y no es un nulo.** Las ocho medianas son positivas, las ocho p sin corregir son < 0.08, y la más
grande, +0.168 a 30 fps bajo ZOH, es **2.8 veces el efecto más grande que la campaña había medido en
cualquier eje** (el +0.060 de `c512` sobre `c640`, nota 19). Lo que la regla rechaza es la fuerza que
se registró, no el signo.

Exigir las dos salidas fue deliberado y es lo que ha mordido. Venía de la §8 de la nota 26: FOH
aplana el eje de coste a la mitad, así que ganar solo bajo ZOH sería un artefacto del consumidor
congelador. Aquí FOH lo aplana exactamente igual — las medianas pasan de +0.068/+0.168/+0.151/+0.167
a +0.050/+0.082/+0.071/+0.095, **entre el 47% y el 74%**. La predicción de la nota 26 se cumple sobre
un eje que no era el suyo.

Los niveles, restringiendo `asym_b` a los mismos 25 clips para que las columnas sean comparables:

| fps | `asym_b` ZOH | `c512` ZOH | `asym_b` FOH | `c512` FOH |
| ---: | ---: | ---: | ---: | ---: |
| 15 | 0.729 | 0.574 | 0.737 | 0.685 |
| 30 | 0.713 | 0.439 | 0.733 | 0.634 |
| 60 | 0.525 | 0.251 | 0.616 | 0.529 |
| 120 | 0.364 | 0.146 | 0.549 | 0.334 |

Leídas por columnas: `asym_b` a 120 fps bajo ZOH (0.364) queda entre `sam2_c512` a 30 (0.439) y a 60
(0.251), o sea que el brazo barato con el flujo a 120 fps va como el caro con el flujo entre 30 y 60.
Bajo FOH lo mismo pero más apretado: 0.549 a 120 contra 0.529 de `c512` a 60.

## 6. Por qué FOH se come la ventaja: verificación visual

Esto es la parte que los números no daban, y es un mecanismo, no una interpretación de tabla.
`truck3` a 120 fps, el peor clip común de `asym_b` — elegido por la regla del pre-registro (§6: el
peor común), no por lo que enseña:

```
analysis/render_foh.py raw/paced-family-120/asym_b__truck3.json --out ... --frames 300:420
analysis/render_foh.py raw/paced-grid-120/sam2_c512__truck3.json --out ... --frames 300:420
```

Fotogramas abiertos y mirados, no inferidos del log.

- **`sam2_c512`, f360:** ZOH 0.00, FOH 0.79. La caja retenida en rojo está un ancho de caja por
  detrás del camión; la azul, la misma respuesta navegada a su propia velocidad, cae encima. El déficit
  de `c512` bajo pausa es **retardo**, y el retardo es justo lo que FOH corrige.
- **`asym_b`, f360:** ZOH 0.00, FOH 0.00, y las dos cajas coinciden en el borde izquierdo del
  fotograma, sobre un vehículo distinto, mientras el objetivo está arriba a la derecha. El déficit de
  `asym_b` aquí es **pérdida de identidad**, y no hay velocidad que navegar porque la caja está
  parada sobre lo que no es.

Ahí está por qué FOH aplana la comparación: **le devuelve a `c512` lo que perdía por llegar tarde, y
no le devuelve a `asym_b` lo que pierde por irse a otro objeto.** AsymTrack no tiene redetección
—`TODO.md` lo lleva anotado desde el brazo `asym_lt`— así que una vez se engancha a otra cosa bajo
pausa alta, se queda ahí el resto del clip. Es el mismo mecanismo que hace que tres de los cinco
`uav*` de §3 caigan por debajo de 0.01.

En `person20` (registrado como el clip donde los dos deberían estar sanos) los dos lo están: `asym_b`
ZOH 0.81 / FOH 0.78, `sam2_c512` ZOH 0.78 / FOH 0.80, cajas encima del objetivo en ambos. El control
visual hace de control.

## 7. A2: la forma, y una estimación fallada

Registrada como descriptiva: la ventaja debía crecer con fps hasta que `asym_b` empezara a tirar
fotogramas, con el codo entre 30 y 60. **Lo que sale no es eso.** Bajo ZOH la ventaja salta de +0.068
a +0.168 entre 15 y 30 fps y luego se queda plana (+0.151, +0.167) pese a que la tasa de respuesta se
desploma de 0.97 a 0.25. La forma es un escalón, no una rampa.

**El escalón tiene mecanismo, y está medido.** Lo que le compra la ventaja a `asym_b` no es su tasa
de respuesta sino la **razón** entre las dos tasas, y esa razón se satura en cuanto los dos brazos
tiran fotogramas:

| fps | tasa `asym_b` | tasa `c512` | razón |
| ---: | ---: | ---: | ---: |
| 15 | 0.993 | 0.663 | **1.50** |
| 30 | 0.972 | 0.332 | 2.93 |
| 60 | 0.521 | 0.166 | 3.13 |
| 120 | 0.245 | 0.084 | 2.92 |

A 15 fps `asym_b` está topado: no puede responder más que a cada fotograma, así que por rápido que
sea solo saca 1.5x al control y la ventaja es la pequeña, +0.068. De 30 en adelante los dos caen
juntos y la razón se clava en ~2.9-3.1 — que es el cociente de sus latencias, 100.9/30.4 = 3.3 — y la
ventaja se clava con ella. **El escalón de la ventaja es el escalón de la razón de tasas**, y el codo
que el pre-registro puso entre 30 y 60 estaba en realidad entre 15 y 30: no en el punto donde
`asym_b` empieza a tirar fotogramas, sino en el punto donde deja de estar topado por arriba.

**Estimación contra realidad.** El pre-registro esperaba ~+0.25 a 30 fps y una ventaja creciente
hasta ~+0.35 a 120. Sale +0.168 y plana. El fallo tiene causa localizable: estimé restando medianas
de brazo (0.687 sin pausar contra 0.435 de `c512`), y esas dos medianas están sobre poblaciones
distintas —30 clips contra 25— que es exactamente la trampa contra la que avisa la nota 19 §2. Sobre
los 25 comunes la diferencia de niveles a 30 fps es 0.713 − 0.439 = 0.274, y la mediana **pareada**
es +0.168: la diferencia de medianas no es la mediana de diferencias, y con clips tan dispares la
brecha entre ambas es grande. El coste sí salió bien: 0.85 h medidas contra 0.9 h estimadas.

## 8. Qué dice esto, y marcado como interpretación

**La medida:** bajo pausa, un seguidor de otra familia 3.4x más barato bate a `sam2_c512` en las ocho
celdas, con Holm < 0.05 en seis de ocho, y falla el umbral registrado por dos celdas FOH.

**La interpretación:** la frase "bajo pausa la ordenación es por coste" de las notas 25 y 26 estaba
enunciada sobre una familia y se comporta como si fuera sobre la placa. Sigue siendo cierta —
`asym_b` es el más barato y gana— pero su alcance es más grande de lo que se midió, y el arco pausado
entero optimizó dentro de la familia cara sin haber comprobado que fuera la familia correcta. Ése es
el mismo error de alcance que la nota 26 §8 corrigió en el otro eje, cometido un nivel más arriba.

**Lo que no autoriza:** cambiar el punto de operación. El brazo que gana en la tabla es el que pierde
el objetivo entero en tres de los cinco clips que la puerta le quitó, y la comparación que gana está
construida sobre exactamente esos 25 que le quedan bien. Con redetección esto sería otra
conversación; sin ella, lo medido es que **hay una familia entera sin explorar donde la campaña
supuso que no la había**, no que haya que mudarse a ella.

## 9. Cómo no sobreleer la tabla

- **n=25, no 30**, y los 5 que faltan favorecen a `asym_b`. Las dos tablas no se mezclan nunca.
- **Los niveles de §5 están sobre los 25 comunes**; la salida cruda de `analysis/paced_family.py`
  imprime `asym_b` sobre 30 y `c512` sobre 25, y esas dos columnas **no** son comparables.
- **Holm sobre 8, no sobre 4.** Registrar las dos salidas dobla la familia y encarece cada celda; es
  el precio de no poder elegir consumidor después.
- **A1 no gana no es "no hay efecto".** Es que la fuerza registrada no se alcanzó. Nulo acotado bajo
  FOH a 15 y 60 fps, nunca equivalencia.
- **Los controles son de otra sesión** (notas 19 y 25). Validado por la medida de reproducibilidad de
  la nota 26 §5, no supuesto.

## 10. Qué no se midió

- **`asym_lt` pausado.** El brazo con envoltorio de largo plazo es el candidato obvio dado el
  mecanismo de §6, y quedó fuera a propósito: un eje por tanda. Ahora tiene una hipótesis concreta
  detrás en vez de ser una casilla más.
- **Redetección de ningún tipo.** §6 dice qué falta, no que se haya probado.
- **DAM4SAM y SAMURAI pausados.** Siguen sin una sola corrida pausada, igual que `asym_b` hasta hoy.
- **Dónde está el codo de §7.** Las tasas dicen que cae entre 15 y 30 fps, pero no hay ninguna
  velocidad medida ahí en medio, así que "entre 15 y 30" es todo lo que sostienen los datos.
- **Sin verificación visual de las celdas a 15, 30 y 60 fps.** Los dos clips mirados son de la pasada
  a 120. Que el mecanismo de §6 sea el mismo a velocidades menores es interpretación, no medida.
