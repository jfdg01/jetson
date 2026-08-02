# 20. `lead`: la predicción de movimiento en la entrada no compra nada

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-08-02T22:16Z -> 22:34Z (hora local de Madrid).
**Coste:** 25 corridas, **0.27 h de dispositivo** — `sum(init_ms + frames * ms_p50)` sobre los JSON.
**Datos:** `raw/paced-lead-30/`
**Código:** `42d64c5` (`Sam2CropArm(lead=True)` y el registro del brazo), `analysis/lead.py`,
`analysis/test_lead.py`.

## 1. Por qué existe la tanda

La nota 19 cerró que bajo protocolo pausado (`--fps 30`, descarte a la última) la caja que llega al
consumidor está vieja: el brazo salta los fotogramas que no pudo seguir, así que su última respuesta
tiene un intervalo de descarte de antigüedad. Retención de primer orden (FOH) corrige eso **en la
salida** y gana +0.069 pareado sobre 155 pares.

El autor puso la objeción correcta: FOH no mejora el seguidor, solo la caja entregada. Como medida
de calidad del seguidor es cosmética; como medida de **entrega** es real, porque el sistema en vuelo
persigue usando esas cajas y un retardo es error de control, no de estética. Es la misma distinción
que la Parte VI traza entre *grounding* y *delivery*.

De ahí la pregunta de esta tanda: **la misma estimación de velocidad, ¿vale más puesta en la
entrada?** `lead=True` centra la ventana de recorte donde se *predice* que estará el objetivo, en
vez de donde se vio por última vez. A diferencia de FOH, esto cuesta tiempo de dispositivo y una
predicción mala **se escribe en el banco de memoria de SAM2**, así que no es reversible fotograma a
fotograma.

El 2x2 bajo prueba: {entrada plana, entrada `lead`} x {salida ZOH, salida FOH}.

Tres diagnósticos pre-registrados antes de correr:

- `lead`+ZOH **>** `c512`+ZOH: la predicción vale puesta en la entrada.
- `lead`+FOH **~** `c512`+FOH: entrada y salida son la misma corrección aplicada dos veces.
- `lead`+ZOH **<** `c512`+ZOH: la predicción es ruido; entonces mirar si la degradación **crece con
  el índice de fotograma** (firma de memoria envenenada).

## 2. Cómo corrió

```
./jetson.py run --id paced-lead-30 --arms sam2_c512_lead --fps 30 --seqs <las 30 de paced-sweep-30>
```

15 W + `jetson_clocks`, `nvpmodel` 0, governor `schedutil`, L4T R36.5.0, `sam2==1.1.0`,
`torch==2.8.0`. Térmicas 60.0 -> 67.8 C tj, sin estrangulamiento.

**25 corridas, no 30.** El manifiesto lista 5 trabajos vetados
(`sam2_c512_lead__uav{1_2,2,3,5,7}`): esos clips son 720x480 y un brazo de 512 inventaría píxeles.
Es la misma puerta `upscales` de `device/trackers.py` que dejó `paced-sweep-30` en 155 y no 210. El
control se filtra al mismo conjunto, así que los pares son de 25 y son los mismos clips.

**Estimación contra realidad:** estimé ~0.3 h; salió 0.27 h. Sin divergencia.

## 3. Comprobación de fontanería, antes de los números

El nulo salió tan limpio que había que descartar que `lead` fuese un no-op silencioso.

`analysis/test_lead.py` es una prueba solo de geometría: sustituye el SAM2 interior por un oráculo
que siempre encuentra el objetivo, y mide el desfase con signo entre el centro de la ventana y el
centro del objetivo. Con ZOH la ventana va siempre **detrás** (`< -STEP/2` en los 6 primeros pasos,
antes de que `crop_window` empiece a recortar contra el borde); con `lead` y velocidad constante la
predicción es exacta y la ventana queda **centrada** (`|desfase| < 1e-6` del paso 2 al 6; el paso 1
coincide con ZOH porque hacen falta dos aciertos para que exista una velocidad).

    analysis/test_lead.py

La palanca funciona. Lo que pasa es que lo que mueve es pequeño contra lo que hay alrededor:

```
seq           salto/paso px  tam px   % del margen (256-tam/2)
bird1_1                62.3      37                     26.3%
bird1_3                46.2      41                     19.6%
wakeboard1             12.5      75                      5.7%
car12                  11.2      32                      4.7%
person20                8.9     241                       6.6%
car9                    1.5      46                      0.6%
MEDIANA                 5.9                              2.5%
```

Una ventana de 512 alrededor de un objetivo de 40 px deja ~230 px de margen por lado. El salto
mediano entre respuestas consecutivas es de 5.9 px: **2.5% de ese margen**.

## 4. El 2x2

```
analysis/lead.py raw/paced-sweep-30 raw/paced-lead-30
```

```
                                     ZOH               FOH
brazo                     mIoU      @0.5    mIoU      @0.5
sam2_c512                0.439     0.459   0.634     0.796   n=25
sam2_c512_lead           0.443     0.419   0.620     0.782   n=25

pareado, lead menos control
salida     n  d mediana     gana         p
ZOH       25     +0.001   15/25    3.1e-01
FOH       25     -0.001   11/25    6.3e-01
```

Nulo en las dos salidas. Ninguno de los tres diagnósticos dispara en su forma fuerte: cae en el
tercero pero en versión débil — la predicción en la entrada **no es ni valiosa ni ruido, es
indiferente**.

## 5. Memoria envenenada: no aparece

```
deficit de `lead` por tercio del clip, ZOH, n=25
               1o       2o       3o
mediana    +0.000   +0.002   +0.000
media      +0.000   +0.002   +0.017
3o menos 1o: mediana +0.001, p=3.1e-01
```

Plano, no creciente. El riesgo que el autor señaló es real por construcción — SAM2 escribe cada
fotograma propagado en su banco de memoria, así que un recorte mal encuadrado sí ensucia estado
persistente — pero a estas magnitudes de desplazamiento no llega a materializarse. **Es un nulo
acotado a este régimen, no una demostración de que `lead` sea seguro en general.**

## 6. El hallazgo real: a SAM2 le da igual dónde caiga dentro de la ventana

Si el desplazamiento fuera la variable que manda, los clips que más se mueven tendrían el mayor
efecto. No lo tienen:

```
Spearman salto vs delta(lead-control): rho=+0.027, p=0.90, n=25

bird1_1      62.3 px/paso   -0.003
bird1_3      46.2 px/paso   +0.037
person18      9.0 px/paso   +0.141
car9          1.5 px/paso   -0.000
```

`bird1_1` mueve 62 px por paso, un 26% del margen, y da −0.003. El mayor efecto positivo
(`person18`, +0.141) está en un clip de salto medio. La correlación es nula.

Interpretación (marcada como interpretación): **centrar el recorte no es una palanca**. Mientras el
objetivo caiga dentro de la ventana, a SAM2 le da igual dónde. Lo que sí importaba era el retardo de
la caja *entregada*, y eso lo coge FOH gratis.

## 7. Cómo no sobreleer

- n=25, no 30 — los cinco `uav*` están vetados por resolución, en ambos brazos.
- Un nulo con n=25 y p=0.31 es un **nulo acotado**, no equivalencia probada. Lo que se puede decir
  es que si `lead` tiene un efecto, es menor que lo que 25 pares detectan.
- La comparación por fotograma entre las dos corridas es débil por construcción: bajo protocolo
  pausado cada brazo salta fotogramas distintos (en `truck2`, 129 procesados contra 130, solo 19
  comunes). Por eso el veredicto se apoya en mIoU pareado por clip, no en diferencias por fotograma.
- El régimen es UAV123 a 30 fps con brazo de 512. Un objetivo que se saliera de la ventana entre
  respuestas invertiría el argumento entero — no hay ninguno aquí.
- `bird1_1` es el caso más rápido del conjunto (0.38 anchuras de objeto por fotograma). No lo
  cubrimos con un régimen más rápido todavía.

## 8. Qué no se midió

**Sin verificación visual de esta tanda.** Ninguna superposición de `lead` abierta, ningún fotograma
suyo leído. El veredicto es de JSON contra JSON, y así se queda: un nulo no tiene nada que enseñar
en pantalla. Lo que sí se verificó ese día fue FOH contra ZOH — ver §9.

Tampoco se midió: `lead` sobre otras resoluciones (solo 512, elegido porque es el mejor brazo de
recorte bajo el protocolo pausado según la nota 19); `lead` a fps más bajos, donde el intervalo de
descarte crece y el desplazamiento por respuesta se acerca al margen; ni `lead` con la velocidad
estimada sobre más de dos aciertos.

> **Corregido el 2026-08-02 (ver `notes/PREREG-paced-fps-grid.md`):** "a fps más bajos" está al
> revés. `device/run_arm.py:next_frame` es `nxt = max(i + 1, int(t * fps))`, así que el intervalo de
> descarte es `latencia x fps` y **crece con el fps a la alza**. La condición de reapertura de este
> nulo es fps **alto**, no bajo, y es lo que mide la rejilla brazo x fps.

## 9. Consecuencia

La corrección de movimiento va en la **salida**, no en la entrada. FOH cuesta cero tiempo de
dispositivo, es reversible fotograma a fotograma, no toca ningún píxel que el modelo vea y no
escribe nada en el banco de memoria. `lead` costó una tanda entera para un nulo. El brazo se queda
registrado (`sam2_c512_lead`) porque el veredicto está acotado al régimen y la pregunta reabre sola
en cuanto baje el fps.

Pendiente heredado de la nota 19 §8, **cerrado el mismo día**: la verificación visual de ZOH contra
FOH está en `proof/foh__truck2.mp4` y `proof/foh__boat3.mp4`, descritos en `proof/README.md`. En
`truck2` se ve la geometría entera — rojo (ZOH) atrás, azul (FOH) adelantado sobre el verde. Sigue
sin cubrirse `person18` (cambio de dirección) ni `bird1_*` (caja perdida). De `lead` no hay clip:
un nulo no tiene nada que enseñar.
