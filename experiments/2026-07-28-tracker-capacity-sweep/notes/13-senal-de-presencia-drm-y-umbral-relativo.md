# Señal de presencia, DRM y umbral relativo

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-07-31T00:03Z -> 2026-08-01T01:19Z (sello de los ficheros traídos, o sea el final de cada corrida).  
**Coste:** 192 corridas, **12.66 h de dispositivo** — estimación, `sum(init_ms + frames * ms_p50)` sobre los JSON; no incluye tiempo muerto entre etapas.  
**Datos:** `raw/dam-conf-smoke/`, `raw/dam-conf33/`, `raw/lt-controls33/`, `raw/sam2-t768-control/`, `raw/sam2-t768-fix/`, `raw/parity-smoke/`


## Presencia y reenganche en DAM4SAM (2026-07-31T21:20Z)

Cuatro cosas encadenadas: dar señal de presencia a las familias que no la tenían, medir si esa
señal es mejor que la de SAM2 pelado, ajustar el umbral de la máquina de estados fuera de muestra
y comprobar en la Jetson que la simulación no mentía.

### 1. `conf` para DAM4SAM y SAMURAI (commits `efdb8a3`, `02817e5`)

El punto 6 de la sección anterior dejaba el eje de presencia **sin medir** para DAM4SAM: el
plumbing de `conf` cubría SAM2 y AsymTrack, no las familias vendorizadas después, y
`analysis/presence.py` moría con `no arm in raw/dam-full30b recorded a conf signal`. Ambas familias
envuelven el mismo predictor de SAM2, así que la señal ya existía dentro: `object_score_logits`, la
cabeza de oclusión **entrenada**. Solo había que sacarla del wrapper.

### 2. `lt-controls33`: el DRM no mejora la señal de presencia (93 corridas, `raw/lt-controls33/`)

Controles a 33 secuencias con hueco: `sam2_t640` (SAM2 pelado, sin DRM), `samurai_t640` y
`sam2_f5_floor`. Con `raw/dam-conf33` ya en disco, quedan cinco brazos comparables.

    analysis/presence.py raw/lt-controls33 raw/dam-conf33 --vs sam2_t640

| brazo | n | secs con hueco | presence_auc mediana | f_lt | auc < 0.5 |
| --- | --- | --- | --- | --- | --- |
| `dam4sam_t640` | 33 | 33 | 0.979 | 0.973 | 1/33 |
| `dam4sam_t768` | 33 | 33 | 0.984 | 0.982 | 0/33 |
| `sam2_t640` | 27 | 27 | 0.962 | 0.924 | 1/27 |
| `samurai_t640` | 33 | 33 | 0.956 | 0.928 | 1/33 |
| `sam2_f5_floor` | 33 | 33 | 0.925 | 0.825 | 2/33 |

`sam2_t640` sale con 27 y no 33 porque la puerta `upscales` (`device/trackers.py`) veta las seis
secuencias de 720x480 (`uav1_*`, `uav2`, `uav6`, `uav7`) — a `family="sam2"` la regla es
`n*n > w*h`. Comparar una mediana de 33 contra una de 27 es exactamente el error que la tabla de
medianas invita a cometer, así que **el contraste es pareado** sobre las 27 comunes, Wilcoxon:

| brazo vs `sam2_t640` | n | d presence_auc | p | d f_lt | p | d maxgm | p |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `dam4sam_t640` | 27 | +0.000 | 0.6109 | +0.004 | 0.0280 | +0.000 | 0.5506 |
| `dam4sam_t768` | 27 | +0.013 | 0.0009 | +0.033 | 0.0000 | +0.000 | 0.3809 |
| `samurai_t640` | 27 | +0.002 | 0.1855 | +0.000 | 0.7982 | +0.000 | 0.0150 |
| `sam2_f5_floor` | 27 | -0.000 | 0.6617 | +0.001 | 0.3674 | -0.000 | 0.0245 |

**El DRM no mejora la señal de presencia a 640.** La mediana pareada es exactamente 0.000 con
p = 0.61. Lo que hace es **barajar** qué secuencias funcionan: gana `car7` 0.447 -> 0.891,
`person16` 0.632 -> 0.991, `car14` 0.701 -> 0.994, `bird1_2` 0.908 -> 0.997, `group2_1`
0.900 -> 0.984; y pierde `person19_3` 0.991 -> 0.562, `bike2` 0.507 -> 0.284, `car1_3`
0.913 -> 0.846, `group2_3` 0.933 -> 0.867, `group3_2` 0.927 -> 0.877. La señal es de la cabeza de
oclusión de SAM2, no del banco de memoria. El único brazo significativo en AUC es `dam4sam_t768`,
y está **confundido con resolución** — de ahí el control `sam2_t768` (más abajo).

Nota de lectura: la columna `maxgm` de esta tabla es la vieja, la que sustituye p por la tasa de
silencio; para un brazo que nunca se abstiene vale 0 por construcción. Es degenerada y no se usa
para decidir nada. Lo que decide es `gm_ox` en `analysis/lt_sim.py`.

### 3. `analysis/lt_sim.py`: por qué evaluar el largo plazo no cuesta GPU

`Dam4SamLtArm.step` llama a `inner.step(frame)` **en todos los frames** y solo decide si devuelve
la caja o no. Nada de lo que decide la máquina de estados llega al tracker: no hay re-init, ni
edición de memoria, ni movimiento de la ventana de búsqueda. El lazo está **abierto**. Consecuencia
práctica: la máscara de respuesta es una función pura de la traza `(box, conf)` por frame que ya
está escrita en `raw/*.json`. Cambiar tau vuelve a filtrar un JSON; no calcula un solo píxel. Un
barrido de ~1.900 configuraciones sale en segundos en el portátil.

Lo que **no** es simulable, y por qué: el re-detector de cinco sondas de `AsymLtArm` mueve la
ventana de búsqueda, así que la entrada del frame siguiente depende del estado — lazo cerrado.
Igual pasa con suprimir la escritura en memoria mientras `LOST` (ver `TODO.md`): cambia lo que ve
el modelo. Eso se corre en la Jetson o no se mide.

Métrica de decisión: **`gm_ox`**, el MaxGM publicado de OxUvA para una política fija,
`max_p sqrt((1-p) TPR ((1-p) TNR + p))`. En forma cerrada con u = 1-p da `u* = 1/(2(1-TNR))`
recortado a 1, así que con TNR >= 0.5 colapsa a `sqrt(TPR TNR)`. Exige HIT (IoU > 0) para contar
TPR, que es lo que impide que "abstenerse siempre" gane.

### 4. Umbral fijo contra umbral relativo

El umbral fijo es un tau global, y asume que `object_score_logits` está calibrado **entre**
secuencias. No lo está. Ajustado sobre las 17 secuencias pares de `raw/dam-conf33` y evaluado en
las 16 impares, `lo 5.719 hi 6.120 k 1` cuesta 0.10 de f_lt y 0.20 de TPR sobre frames PRESENTES,
y **cinco de las seis peores secuencias ya tenían presence_auc >= 0.86**: el orden dentro del clip
estaba bien, lo que estaba mal era el punto de corte.

La alternativa es cortar en `mu - a sigma` sobre los últimos `w` frames que el brazo cree
on-target. Es **causal** — solo mira frames ya emitidos — que es lo que la hace desplegable y no un
mero ajuste offline mejor. Los primeros `w` frames siempre responden: el operador acaba de designar
el objetivo, la misma suposición que hace el `init` del propio tracker. Consecuencia que conviene
saber: una secuencia más corta que `w` nunca se abstiene y el brazo es exactamente `dam4sam_t640`.

`analysis/lt_sim.py raw/dam-conf33 --arm dam4sam_t640` — mejor fijo `lo 5.719 hi 6.120 k 1`, mejor
relativo `a 4.0 b 2.0 k 1 w 300 movil`:

| | gm_ox | f_lt | tpr | tnr | silencio | sil. en hueco |
| --- | --- | --- | --- | --- | --- | --- |
| fit fijo | 0.810 | 0.801 | 0.671 | 1.000 | 0.350 | 1.000 |
| fit rel | 0.813 | 0.918 | 0.926 | 0.956 | 0.111 | 0.956 |
| fit plain | 0.707 | 0.918 | 0.978 | 0.737 | 0.058 | 0.737 |
| EVAL fijo | 0.862 | 0.863 | 0.797 | 1.000 | 0.220 | 1.000 |
| **EVAL rel** | **0.869** | **0.964** | **0.949** | 0.903 | 0.122 | 0.903 |
| EVAL plain | 0.606 | 0.968 | 0.992 | 0.521 | 0.037 | 0.521 |
| todas 33 fijo | 0.816 | 0.811 | 0.687 | 1.000 | 0.261 | 1.000 |
| todas 33 rel | 0.851 | 0.959 | 0.937 | 0.926 | 0.111 | 0.926 |
| todas 33 plain | 0.630 | 0.962 | 0.983 | 0.600 | 0.049 | 0.600 |

Contra el brazo sin abstención, fuera de muestra: `fijo` gana 11/16, mediana +0.216, **peor -0.294**,
d f_lt -0.022; `rel` gana 10/16, mediana +0.078, **peor -0.037**, d f_lt **-0.001**. El relativo
gana menos por secuencia y **pierde muchísimo menos en la peor**, que es la propiedad que importa
en un lazo de control. En `dam4sam_t768` la lectura se repite: fijo `lo 5.438 hi 5.495 k 3` EVAL
0.919 peor -0.206, relativo `a 2.0 b 2.0 k 5 w 30 movil` EVAL **0.947** peor -0.034.

**`asym_b` va al revés** (`raw/asym-conf`): fijo `lo 0.427 hi 0.595 k 1` EVAL gm_ox 0.625 contra
relativo `a 1.5 b 0.0 k 2 w 100 movil` 0.594. Con presence_auc 0.711 el **orden** dentro del clip
ya es malo, así que normalizar la escala solo mueve ruido. El umbral relativo no arregla una señal
mala; explota una señal buena mal calibrada.

### 5. `dam4sam_lt` registrado, y el humo de paridad (`raw/parity-smoke/`)

`dam4sam_lt` = `dam4sam_t640` + umbral relativo `a=4.0 b=2.0 k=1 w=300`, el argmax de la mediana de
`gm_ox` sobre la mitad de ajuste. La afirmación "la simulación reproduce el brazo real" es
verificable y por tanto se verifica: se corrió el brazo real en la Jetson sobre `car2` y se comparó
frame a frame contra `run_machine_rel` replicado desde `raw/dam-conf33/dam4sam_t640__car2.json`.

    conf identico brazo real vs base: True
    frames que responde: real 1293  simulado 1293  de 1321
    discrepancias: 0

La primera línea es la premisa (el wrapper no perturba al tracker), la tercera es la conclusión.
Latencia `dam4sam_lt` p50 **215.1 ms** contra ~204 ms del brazo pelado: abstenerse es gratis, como
debe ser, porque el trabajo se hace igual. En la misma tanda se rehizo `dam4sam_t768 x car2` sin
contención: p50 **282.0 ms** (la medida previa salió de una máquina compartida y se descarta).

Las dos máquinas de estados tienen self-check ejecutable: `python device/trackers.py --self-check`
y el bloque final de `analysis/lt_sim.py`. Ambos incluyen la aserción que justifica el diseño — la
misma traza desplazada +1000 debe dar **la misma** máscara.

### 6. `sam2-t768-control`: el control que separa resolución de memoria

`dam4sam_t768` es el único brazo significativo del pareado de arriba y está confundido: sube
resolución **y** añade DRM. `sam2_t768` sobre las mismas 33 secuencias con hueco (27 tras la puerta
`upscales`) desempata.

**Un error de operación que conviene dejar escrito, porque el modo de fallo es silencioso.** Se dio
el primer intento por muerto y se relanzó con el **mismo `--id`**. No estaba muerto. El diagnóstico
se apoyó en dos señales, y las dos eran malas:

- `pgrep -c "[d]river.py"` devolvió 0. Sin `-f`, `pgrep` compara contra el **nombre** del proceso,
  que es `python`; el patrón vive en los argumentos. Nunca iba a coincidir. Con `pgrep -af` el
  proceso estaba ahí.
- El directorio de run tenía solo `manifest.json`. Es lo normal: cada resultado se escribe al
  **terminar** su secuencia, y `bird1_3` (job 1/27, 865 frames) seguía en vuelo.

El resultado fueron dos drivers escribiendo el mismo directorio. Se nota en `ps`: dos `run_arm.py`
sobre `group3_2` con el mismo `--out`, y dos `DONE` en un único `driver.log`. Tres ficheros salieron
con dos documentos JSON concatenados (`Extra data: line 1 column 717134`) — `group2_2`,
`person17_1`, `person19_2` — y el resto de la carrera se ganó por orden de llegada. El daño es
limitado y detectable (`json.load` revienta), pero **nada en el arnés lo impidió**: `driver.py` no
toma un lock sobre el directorio de run. Los tres se borraron y se relanzaron aparte
(`sam2-t768-fix`); los 24 restantes son válidos.

Lección de arnés, no de tracking: un `--id` repetido debe fallar en seco. Implementado en
`jetson.py cmd_run` (commit `1ee38e9`): antes de lanzar, `pgrep -f "driver.py --run-dir <rd>"` y si
hay un driver vivo sobre ese directorio, `SystemExit`. Los tres resultados se fusionaron y el
pareado a tres bandas está en el punto 7.

**Las tres formas en que `pgrep` ha mentido en este experimento.** Las tres salen con código 0 y se
leen como una respuesta correcta, que es por lo que cuestan horas:

1. **Se encuentra a sí mismo.** `pgrep -f PATRON` casa con su propia línea de comando siempre que el
   patrón viaje dentro de ella. Un vigía `until ! ssh jetson 'pgrep -f "bash night.sh"'; do sleep
   300; done` esperó 9.6 h de más a las etapas de la noche del 2026-07-31: ssh ejecuta el comando
   vía `bash -c`, y el `pgrep` remoto encontraba ese envoltorio. Remedio: un corchete —
   `"[b]ash night.sh"`. `cmd_status` ya lo hace bien; la trampa es el sitio de llamada nuevo.
2. **Sin `-f` casa el NOMBRE del proceso, no los argumentos.** `pgrep python` no distingue dos
   trabajos de python. Así se declaró muerto un run vivo, con el segundo driver escribiendo sobre el
   mismo directorio.
3. **Filtrar la salida lo vuelve a esconder.** `pgrep -af X | grep -v pgrep` descarta cualquier
   proceso real cuya línea de comando contenga la palabra `pgrep` — que es justo el aspecto que
   tiene un bucle de vigilancia.

### 7. Cierre del control: la resolución no compra presencia, el DRM sí, y solo a 768

27 secuencias (las mismas que pasan la puerta `upscales`), tres contrastes pareados:

    analysis/presence.py raw/lt-controls33 raw/dam-conf33 raw/sam2-t768-control --vs sam2_t768

| brazo | n | presence_auc mediana | f_lt |
| --- | --- | --- | --- |
| `sam2_t640` | 27 | 0.962 | 0.924 |
| `sam2_t768` | 27 | 0.973 | 0.939 |
| `dam4sam_t640` | 33 | 0.979 | 0.973 |
| `dam4sam_t768` | 33 | 0.984 | 0.982 |

| contraste pareado | n | d presence_auc | p | d f_lt | p |
| --- | --- | --- | --- | --- | --- |
| `sam2_t768` vs `sam2_t640` (solo resolución) | 27 | +0.000 | 0.8040 | +0.001 | 0.1919 |
| `dam4sam_t640` vs `sam2_t640` (solo DRM, a 640) | 27 | +0.000 | 0.6109 | +0.004 | 0.0280 |
| `dam4sam_t768` vs `sam2_t768` (solo DRM, a 768) | 27 | **+0.007** | **0.0007** | +0.017 | 0.0039 |

Tres lecturas, en orden de confianza:

**1. La resolución no compra nada en el eje de presencia.** 640 -> 768 sobre el mismo tracker da
mediana pareada exactamente 0.000, p = 0.80. Esto es un negativo limpio y contrasta con el eje de
mIoU, donde el mismo escalón valía +0.042 con p = 0.0087 (sección anterior). **Píxeles compran
cajas, no saber si el objeto está.** Coherente con que la señal salga de una cabeza entrenada: lo
que la limita es su entrenamiento, no la entrada.

**2. El DRM sí, pero solo a 768.** +0.007 con p = 0.0007 a 768; +0.000 con p = 0.61 a 640. Es una
interacción, no un efecto principal, y con n=27 y un solo dataset no está medida — está insinuada.

**3. El tamaño del efecto es marginal aunque el p sea pequeño.** +0.007 de AUC sobre 0.973. Lo que
mueve el número es la **cola**: `sam2_t768` tiene 0/27 secuencias por debajo de 0.5 y `sam2_t640`
tenía 1 (`bike2` 0.51, en el filo). El pareado detecta un desplazamiento consistente y pequeño; no
justifica por sí solo los +72 ms de 768.

Esto cierra la pregunta que abría el punto 2: la significancia de `dam4sam_t768` **no** era
resolución disfrazada. Pero tampoco es el DRM en general — a 640, la resolución que se desplegaría,
el DRM no aporta señal de presencia sobre SAM2 pelado.
