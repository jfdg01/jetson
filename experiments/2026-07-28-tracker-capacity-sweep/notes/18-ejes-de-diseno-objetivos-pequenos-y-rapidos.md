# Ejes de diseño para objetivos pequeños y rápidos

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-08-02T18:10Z -> 2026-08-02T21:40Z, hora local de Madrid.
**Coste:** 0 corridas nuevas, **0 h de dispositivo** — todo es reanálisis de trazas ya grabadas.
**Datos:** `raw/full-sweep-30/`, `raw/paced-smoke/`; `raw/paced-sweep-30/` en curso (136/210).

> Cerrado por [`19-paced-sweep-30-retencion-de-primer-orden.md`](19-paced-sweep-30-retencion-de-primer-orden.md):
> la retención de primer orden aguanta sobre 155 pares (+0.069 mediana pareada, no el 85% de
> recuperación que sugería el n=2 de aquí); `k` real es 1.20, no 0.90; y la predicción de la §6 de
> que `size_px` perdería peso bajo stream **es falsa** — sube.
**Código:** `3d2f8c5` (`analysis/motion.py`), `728b0d6` (`analysis/sweetspot.py`), `96d57da`
(`extrapolate` en `analysis/aggregate.py` + test).

Este fichero es un **diseño**, no una tanda. Documenta el espacio de configuraciones que hay que
barrer para contestar "cuál es la mejor configuración objetiva para detectar objetos pequeños y de
movimiento rápido", y en qué orden, antes de gastar dispositivo. Precedente de formato:
[`03-tercil-dificil-disenado-y-cancelado.md`](03-tercil-dificil-disenado-y-cancelado.md), que
también documenta un diseño y sobrevive a que la corrida se cancelara.

Un único resultado medido aparece aquí (sección 1) porque cambia el diseño de todo lo demás.

## 0. Por qué existe

El protocolo paced (`run_arm.py --fps`) hace que ser lento cueste, y eso reabre preguntas que la
paridad tenía cerradas. La escalera de resolución de
[`12-escalera-640-768-960-el-recorte-gana.md`](12-escalera-640-768-960-el-recorte-gana.md) era
monótona: más resolución, mejor mIoU. Bajo stream deja de serlo, porque más resolución es también
más latencia y la latencia se paga en deriva. Existe un óptimo intermedio y no está donde lo dejó la
paridad.

Pero al montar el diseño apareció que la magnitud de ese castigo depende de una decisión del
**consumidor** que nadie había declarado, y que la domina. Esa es la sección 1.

## 1. El eje que faltaba: qué hace el consumidor entre respuestas — MEDIDO

`sam2_c640` tarda 159 ms; el stream da un fotograma cada 33 ms. El brazo mira 1 de cada 5. En los
otros 4 el consumidor necesita una caja igual, y hasta ahora se asumía **retención de orden cero**:
congelar la última. Es una elección de implementación, no una ley, y no estaba declarada.

Dos respuestas consecutivas ya llevan la velocidad dentro. Extenderla al fotograma que se puntúa no
cuesta modelo ni GPU: es una resta y una multiplicación sobre cajas que el tracker ya entregó.
Implementado como `extrapolate()` en `analysis/aggregate.py`, expuesto como `--foh`, con
comprobación en `analysis/test_paced.py` (velocidad constante -> caja exacta, y el orden cero no lo
es, para que el test no sea vacuo). Estrictamente causal: solo usa respuestas ya aterrizadas.

    analysis/aggregate.py raw/paced-smoke
    analysis/aggregate.py raw/paced-smoke --foh

| clip | anch/f | paridad | orden 0 | orden 1 | @0.25 orden 0 -> 1 |
| --- | --- | --- | --- | --- | --- |
| `truck3` | 0.1010 | 0.773 | 0.297 | **0.699** | 0.643 -> 0.966 |
| `car9` | 0.0151 | 0.847 | 0.763 | **0.819** | 0.990 -> 0.991 |

`sam2_c640`, 15 W + `jetson_clocks`, 30 fps, `raw/paced-smoke`. La retención de primer orden
recupera ~85% del hueco que abrió el protocolo paced, a coste cero. En `car9` sube poco, que es lo
esperable: si el objetivo no se mueve, congelar ya era correcto.

**Interpretación (marcada como tal):** buena parte del desplome atribuido a "ser lento" era en
realidad artefacto de congelar. Si el consumidor puede navegar la caja, el coste de la latencia baja
mucho y el óptimo de resolución vuelve a subir. Por eso este eje se fija **antes** de barrer
resoluciones: si no, se elige la resolución óptima para un consumidor tonto.

**Lo que no está medido:** n = 2 clips, 1 brazo. La velocidad se estima de dos cajas separadas ~5
fotogramas; en un objetivo de 12 px eso es ruidoso y extrapolar ruido puede empeorar donde el objeto
cambia de dirección rápido. Los 210 pares de `paced-sweep-30` lo contestan sin coste adicional, y
hay que mirar **los clips donde pierde**, no solo la mediana. Sin verificación visual.

**Decisión abierta, no es mía:** si el sistema real puede cambiar el consumidor. Si el consumo de
cajas es código propio, esto es trivial y va dentro; si es una caja negra que solo congela, el
barrido correcto es el otro. Cambia el resultado del experimento entero.

### 1.1 La versión que sí cuesta dispositivo

La misma idea aplicada a la **entrada**: `sam2_c640` recorta alrededor de donde el objetivo estaba
en el último fotograma que miró, y con 159 ms de latencia el objetivo ya se movió cuando el recorte
se toma. Centrarlo donde va a estar cambia los píxeles que entran al modelo, o sea corrida nueva.

| | qué cambia | coste |
| --- | --- | --- |
| salida navegada (`--foh`) | lo que lee el consumidor | 0, repuntúa lo grabado |
| entrada adelantada | qué píxeles ve el modelo | corrida nueva |

Son experimentos distintos y no se mezclan. El primero además dice si el segundo merece la pena: si
navegar la salida ya recupera casi todo, adelantar la entrada tiene poco margen.

## 2. Representación de salida: máscara contra caja

En un objetivo de 12 px la máscara tiene ~140 px; el ruido de contorno domina y todo el aparato de
segmentación se paga sin que aporte. Nunca se ha contrastado bajo stream, y el registro de
`device/trackers.py` ya tiene las dos familias:

- **máscara**: `sam2_*`, `dam4sam_*`, `samurai_*`
- **caja**: `asym_b` (AsymTrack, `search_factor=4.0`), `cv_*` (KCF, CSRT, MOSSE de OpenCV)

Los `cv_*` son el control barato que nunca se ha corrido en serio: milisegundos contra los 159 de
`c640`. Bajo paced pueden ganar, y si un CSRT con retención de primer orden bate a SAM2 en el bloque
rápido, ese es el resultado del experimento — incómodo, y por eso vale. Corolario: si la máscara no
aporta, la salida correcta del sistema es caja y se simplifica todo aguas abajo.

## 3. Modo de feed: hay tres implementados y solo se han cruzado dos

| modo | familia | qué hace |
| --- | --- | --- |
| completo | `sam2_t*` | fotograma entero aplastado a `image_size` cuadrado, ignora aspecto |
| recorte fijo | `sam2_c*` | ventana cuadrada de lado fijo alrededor del objetivo, resolución nativa |
| ventana de búsqueda | `sam2_f*` | ventana dimensionada por el objetivo (`search_factor` x tamaño), remuestreada a `image_size` |

El tercero es el diseño estándar de la literatura de tracking y **no está en el barrido paced**.
Para objetivos pequeños tiene la física a favor: un objetivo de 28 px con factor 5 son 140 px
entrando a una entrada de 640, o sea upsampling sobre el objetivo en vez de sobre el fondo.
`sam2_f5_floor` existe y el factor nunca se ha barrido bajo stream. Es el candidato con más margen y
ya está escrito. Contexto obligatorio antes de sobreleerlo:
[`10-ventana-escalada-al-objeto-colapso-y-suelo.md`](10-ventana-escalada-al-objeto-colapso-y-suelo.md)
documenta que en paridad esta familia colapsa; la pregunta abierta es si bajo stream el ahorro de
latencia compensa.

Lo que no existe y añadiría:

- **cascada**: fotograma completo barato y frecuente, recorte caro solo cuando la confianza cae.
  Ataca latencia y calidad a la vez en vez de elegir.
- **recorte adelantado**: sección 1.1.
- **resolución por debajo de 512**: 384, 448. En paridad no tenían sentido; bajo stream la
  predicción de `sweetspot.py` los pone como candidatos serios. Rejilla legal = múltiplos de 32;
  los brazos de recorte topan en 704 porque UAV123 mide 720 de alto.

## 4. Los demás ejes, ordenados por relación valor/coste

**Coste cero, reanálisis del JSON existente:**

- **Descomponer el error en traslación contra escala.** En un objetivo de 12 px, ±1 px de tamaño
  mueve el IoU una barbaridad. Si el error es de escala, ninguna resolución lo arregla.
- **Taxonomía de fallo**: deriva, pérdida, salto a distractor. Configs distintas arreglan fallos
  distintos; sin esto se optimiza a ciegas.
- **Techo de ruido de anotación.** A 10 px, ±1 px de GT son varios puntos de IoU. Hay que estimar
  ese techo antes de perseguir diferencias por debajo de él; puede que la respuesta esté acotada por
  el dataset y no por el modelo.
- **Métrica alternativa**: error de centro normalizado por tamaño. El IoU sobre objetivos diminutos
  satura en el suelo y deja de discriminar; para "apuntar a algo pequeño" el centro es la cantidad
  operativa.

**Barato en dispositivo, brazos que ya existen y nunca se corrieron en paced:**

- **Memoria y modelo de movimiento**: `sam2` puro contra `dam4sam` (banco de memoria) contra
  `samurai` (Kalman). SAMURAI es un modelo de movimiento sobre SAM2, hecho para objetivos rápidos.
- **Presencia y abstención** (`heur="lt"`): en stream, perder el objetivo cuesta más porque
  recuperarlo tarda tiempo de reloj, no fotogramas. Los brazos LT no se han evaluado con esa
  contabilidad. Ver [`13-senal-de-presencia-drm-y-umbral-relativo.md`](13-senal-de-presencia-drm-y-umbral-relativo.md).
- **dtype/precisión**: bf16 mueve latencia sin tocar arquitectura, y bajo paced latencia **es**
  calidad. Es la palanca más aburrida y quizá la más rentable. Ver
  [`16-paridad-dam4sam-samurai-dtype-y-resolucion.md`](16-paridad-dam4sam-samurai-dtype-y-resolucion.md),
  que la midió bajo paridad y la dio por nula: bajo stream la pregunta no es la misma.

**Cerrado, no se vuelve a abrir:** barrer `--fps`. A 200 ms de presupuesto el brazo procesa 5 fps
tanto si la cámara da 10 como 600; el único efecto de `F` es cuantización del instante de captura,
de segundo orden, y solo ata por debajo de `1/ms`. Además está confundido: sobre vídeo grabado,
cambiar fps cambia la velocidad de reproducción, o sea la velocidad real del objetivo, así que sería
un experimento de velocidad de objetivo mal etiquetado como de tasa de sensor.

## 5. Población objetivo y datasets

"Pequeño y rápido" se cuantifica con `analysis/motion.py` (`3d2f8c5`), que expone en anchuras de
objeto por fotograma la misma cantidad que `analysis/difficulty.py` ya puntúa como eje `motion`
(mediana del paso del centro sobre `sqrt(w*h)`, solo entre fotogramas visibles consecutivos).

    analysis/motion.py --lag 5 --csv motion-todos.csv

Sobre UAV123:

| corte | n | fotogramas |
| --- | --- | --- |
| `size<=25 px`, `motion>=0.10` | 13 | 4717 |
| `size<=30 px`, `motion>=0.08` | 16 | 7000 |
| **`size<=40 px`, `motion>=0.06`** | **28** | **15664** |
| `size<=50 px`, `motion>=0.05` | 34 | 21340 |

El corte propuesto es `<=40 px, >=0.06`: n = 28, cumple el mínimo de 25 sin estirar la definición.

    bike2 bike3 bird1_1 building3 car11 car12 car13 car15 group2_2 group2_3
    person21 person22 truck2 truck3 truck4_1 uav1_1 uav1_2 uav1_3 uav2 uav3
    uav4 uav5 uav6 uav7 uav8 wakeboard6 wakeboard8 wakeboard9

**Dataset: UAV123 y solo UAV123.** TLP no tiene el fenómeno — mediana 103 px de tamaño y 0.0125
anch/f, cero clips bajo el corte, y ninguno de sus 18 llega a 0.35 anchuras de deriva ni con 5
fotogramas de retención. Correrlo aquí sería gastar dispositivo en la pregunta contraria. Si hace
falta más masa, lo honesto es UAVDT o VisDrone: descarga y autorización, no está en disco.

Detalle adicional de `motion.py` que importa si la heurística se lleva a TLP: tres clips
(`Billiards1`, `Billiards2`, `BreakfastClub`) tienen mediana de movimiento exactamente 0 y `p90` de
0.023-0.060. Un eje solo-mediana los rankea "fáciles" por no moverse un píxel entero en más de la
mitad de los fotogramas; ahí hay que usar `p90`. Dentro de UAV123 da igual: `motion` y `p90`
correlacionan 0.929.

## 6. Movimiento en la heurística de dificultad: ya está dentro, y en paridad no aporta

`analysis/difficulty.py` puntúa `AXES = ["size_px", "motion", "gap"]` y `motion` es exactamente esta
cantidad. Contra el mIoU mediano entre brazos de `raw/full-sweep-30` (paridad, n = 30, Spearman):

| eje | rho | p | índice | rho |
| --- | --- | --- | --- | --- |
| `motion` | -0.682 | <0.001 | `size+motion+gap` | -0.785 |
| `p90` | -0.697 | <0.001 | `size+p90+gap` | -0.783 |
| `size_px` | +0.632 | 0.0002 | `size+gap` | **-0.782** |
| `gap` | -0.628 | 0.0002 | `motion` solo | -0.682 |
| px/f crudo | -0.408 | 0.025 | | |

Quitar `motion` del índice mueve rho de -0.785 a -0.782: es ruido. La causa es que `motion`
correlaciona **-0.76 con `size_px`** en UAV123 — los objetivos rápidos *son* los pequeños, los
drones. El índice ya gasta ese rango. Concuerda con la nota ya registrada en `difficulty.py` sobre
`roam`, que cayó por la misma razón.

Queda medido de paso que normalizar por `sqrt(w*h)` era lo correcto: px/f en píxeles crudos predice
claramente peor (-0.408 contra -0.682).

**Predicción a comprobar cuando cierre `paced-sweep-30`:** bajo paced el término de error dominante
es `motion x lag`, así que `motion` debería subir y `size_px`/`gap` bajar. Si sale, la reponderación
se justifica con datos. Matiz: `lag` depende del brazo, así que el índice por clip sigue siendo
válido a priori y el brazo entra como interacción, no como factor del índice.

## 7. Modelo de cruce resolución-cadencia

`analysis/sweetspot.py` (`728b0d6`) predice el mIoU en stream a partir de la corrida en paridad:

    lag  = ms_p50 * fps / 1000 * k
    f    = motion * lag
    pred = mIoU_paridad * (1 - f) / (1 + f)

`(1-f)/(1+f)` es el IoU exacto de dos cuadrados iguales trasladados sobre un eje. La deriva real es
2-D y la caja además reescala, así que es **cota superior** del solape superviviente; `k` absorbe la
diferencia y se ajusta con `--check`, no se asume.

    analysis/sweetspot.py raw/full-sweep-30 --check raw/paced-smoke

Ajusta `k = 0.90` con RMSE 0.015 — sobre **2 pares**. Eso no es validación, es que el modelo no está
desmentido. Con `k = 0.90` y 30 fps predice que el orden de paridad se invierte: `c512` (0.461) por
delante de `c640` (0.382), `t1024` cae de 0.752 a 0.053, y `c512` gana en 20 de 30 clips. Todo eso
es **predicción con retención de orden cero** y la sección 1 ya avisa de que ese supuesto es el que
hay que fijar primero. El ajuste serio son los 210 pares de `paced-sweep-30`, y hay que mirar el
residual por brazo: si crece con la resolución, falta un término que no es deriva.

## 8. Cómo se ejecutaría, por etapas

1. **Reanálisis, 0 h de dispositivo.** Fijar el modo de retención sobre los 210 pares de
   `paced-sweep-30`, ajustar `k`, descomponer el error en traslación contra escala, estimar el techo
   de anotación. De aquí sale qué ejes merecen dispositivo.
2. **Cribado amplio, ~3-4 h.** Paced sobre ~20 clips generales cruzando representación
   (máscara/caja) x feed (completo/recorte/ventana) x 3 resoluciones, con brazos que ya existen. No
   factorial completo: una fracción elegida para separar efectos principales.
3. **Finalistas, ~1 h.** 3-4 configs contra `sam2_c640` sobre los 28 clips del corte, prerregistrado,
   Wilcoxon pareado con Holm sobre 3-4 contrastes. Coste: 15664 fotogramas / 30 = 522 s por brazo
   más ~5 s de init por clip, ~11 min por brazo. Paced sale barato justo porque topa al brazo lento.
4. **Lo que el cribado rompa.** Si falta un modo de feed (cascada, recorte adelantado), se escribe
   entonces y no antes.

La separación etapa 2 / etapa 3 es el punto entero: seleccionar la config y reportar su número en el
mismo conjunto sesga el resultado. El conjunto de cribado se quema y ningún número suyo se reporta.

## 9. Cómo no sobreleer nada de esto

- La sección 1 es n = 2 clips, 1 brazo. Todo lo demás de este fichero es diseño o predicción, no
  medida.
- **Los 28 clips no son 28 escenas.** `uav1_1/1_2/1_3` son cortes del mismo vídeo, igual `group2_*`
  y `bike*`. El n efectivo es menor y Wilcoxon asume independencia. O se agrupa por vídeo base
  (n ~ 20, ya por debajo del mínimo) o se declara el clustering como limitación. Se declara.
- **La muestra está sesgada dura por construcción.** Ningún número de esa tanda estima el
  rendimiento en UAV123. Misma limitación que
  [`03-tercil-dificil-disenado-y-cancelado.md`](03-tercil-dificil-disenado-y-cancelado.md), más
  fuerte aquí.
- **Efecto suelo.** `sweetspot.py` predice 0.000 en `bird1_3` y `uav2` con todos los brazos. Si
  media población va a cero, el contraste no discrimina. Hay que decidir **antes de correr** qué se
  reporta en ese caso — fracción de fotogramas con solape no nulo, o fotogramas hasta la primera
  pérdida — y no elegirlo al ver la tabla.
- `ms_p50` en `sweetspot.py` viene de la corrida en paridad. En paced el brazo procesa menos
  fotogramas y podría tener latencia distinta; se comprueba comparando `ms_p50` entre las dos
  corridas cuando aterrice `paced-sweep-30`.
- **Sin verificación visual de nada de este fichero.** Es aritmética sobre JSON ya grabados.
