# 26. Ventana contra entrada: pausado, `c640` no pierde por contexto, pierde por píxeles

Parte de [`../README.md`](../README.md). Cierra
[`PREREG-window-vs-input.md`](PREREG-window-vs-input.md), sellado el 2026-08-03T01:05Z.

**Cuándo:** tandas de dispositivo el 2026-08-03, entre las ~03:00Z y las ~12:05Z (ventana acotada por
los commits `64c86f8` y `6aed9de`; el manifiesto no sella hora). Análisis y verificación visual
2026-08-04T10:20Z -> 11:40Z (hora local de Madrid).
**Coste:** 152 corridas, **3.17 h de dispositivo** — `sum(init_ms + frames * ms_p50)`. Desglose:
`wingrid-full` 2.03 h, `wingrid-30` 0.54 h, y **0.60 h de controles** (`wingrid-ctl-full` 0.04,
`wingrid-ctl-30` 0.01, `wingrid-ctl2-30` 0.55).
**Datos:** `raw/wingrid-full/`, `raw/wingrid-30/`, `raw/wingrid-ctl-full/`, `raw/wingrid-ctl-30/`,
`raw/wingrid-ctl2-30/`, y de notas anteriores `raw/full-sweep-30/`, `raw/paced-sweep-30/`
**Código:** `2840898` (`Sam2CropArm(image_size=...)`, brazos `sam2_w640_i512` y `sam2_w512_i640`,
puerta `upscales` sobre `crop`), `analysis/wingrid.py`, `analysis/test_wingrid.py`.

## 1. Por qué existe

Toda la campaña compara `sam2_c512` contra `sam2_c640` **cambiando dos cosas a la vez**: la ventana
de recorte y la entrada del modelo estaban atadas por construcción. "640 gana" (nota 2, sin pausar) y
"512 gana" (nota 19, pausado) son resultados sobre una diagonal, no sobre un plano. Y la nota 22
dejó una explicación sin probar: que `person18` se rompe con `c512` porque el recorte apretado deja a
SAM2 sin contexto. `Sam2CropArm(size, image_size=N)` desata las dos variables y completa el 2x2.

|  | entrada 512 | entrada 640 |
| --- | --- | --- |
| **ventana 512** | `sam2_c512` | `sam2_w512_i640` |
| **ventana 640** | `sam2_w640_i512` | `sam2_c640` |

```
analysis/wingrid.py raw/full-sweep-30   raw/wingrid-full --clip person18   # sin pausar
analysis/wingrid.py raw/wingrid-ctl2-30 raw/wingrid-30   --clip person18   # pausado a 30 fps
```

## 2. Las dos rejillas

mIoU mediana, salida ZOH, n=25 clips comunes (la puerta `upscales` deja fuera los cinco `uav*`):

| sin pausar | entrada 512 | entrada 640 | | pausado 30 fps | entrada 512 | entrada 640 |
| --- | ---: | ---: | --- | --- | ---: | ---: |
| **ventana 512** | 0.761 | 0.778 | | **ventana 512** | 0.435 | 0.310 |
| **ventana 640** | 0.699 | 0.785 | | **ventana 640** | 0.426 | 0.344 |

Sin pausar el plano **es plano**: 25 puntos de mIoU separan la mejor celda de la peor y la referencia
`c640 − c512` vale +0.003 pareado (16/25). Pausado el plano tiene una pendiente clara y va **en el
eje de la entrada**: las dos celdas de entrada 512 (0.435, 0.426) están por encima de las dos de
entrada 640 (0.310, 0.344), sin solaparse.

## 3. Los cuatro contrastes

Pareado por clip, n=25, Wilcoxon, Holm dentro de la familia de 4. Dos columnas de control, ver §5:

**Sin pausar** (referencia `c640 − c512` = +0.003, 16/25):

| contraste | | d mediana | gana | p | p Holm |
| --- | --- | ---: | ---: | ---: | ---: |
| W1 contexto | `w640_i512 − c512` | −0.009 | 9/25 | 2.0e−01 | 4.0e−01 |
| W2 píxeles | `w512_i640 − c512` | +0.003 | 17/25 | 4.8e−02 | 1.4e−01 |
| W3 aditividad | (W1+W2) − (c640−c512) | −0.006 | 10/25 | 6.3e−01 | 6.3e−01 |
| W4 operación | `w640_i512 − c640` | **−0.024** | 6/25 | 1.1e−02 | **4.6e−02** |

**Pausado a 30 fps** (referencia `c640 − c512` = −0.068, 3/25; entre paréntesis, el mismo contraste
con los controles reutilizados de `paced-sweep-30`):

| contraste | | d mediana | gana | p | p Holm |
| --- | --- | ---: | ---: | ---: | ---: |
| W1 contexto | `w640_i512 − c512` | −0.016 (−0.016) | 8/25 | 8.5e−02 | 1.7e−01 |
| W2 píxeles | `w512_i640 − c512` | **−0.059** (−0.070) | 5/25 | 4.9e−04 | **1.5e−03** |
| W3 aditividad | (W1+W2) − (c640−c512) | −0.019 (−0.020) | 9/25 | 3.1e−01 | 3.1e−01 |
| W4 operación | `w640_i512 − c640` | **+0.049** (+0.046) | 23/25 | 2.9e−04 | **1.1e−03** |

## 4. Qué dice esto

**W2 gana y W1 pierde, pausado. El eje `c512`-`c640` es un eje de coste, no de contexto.** El hueco
de referencia pausado es −0.068; mover **sólo los píxeles** (ventana 512 fija, entrada 640) reproduce
−0.059 de esos −0.068, y mover **sólo la ventana** (entrada 512 fija) deja −0.016 sin significación.
W3 es nulo, o sea que las dos palancas suman, y la suma la domina una sola. Traducido: bajo pausa,
subir la entrada del modelo de 512 a 640 cuesta ~0.06 de mIoU, y ese coste se paga en fotogramas
perdidos, no en peor visión. **W1 es la hipótesis del contexto de la nota 22 y no se sostiene en
agregado.**

**W4 es falsa como se escribió.** El pre-registro pedía que `w640_i512` ganara **en los dos
regímenes**. Gana pausado contra `c640` (+0.049, 23/25, Holm 1.1e−03) y **pierde sin pausar** contra
`c640` (−0.024, 6/25, Holm 4.6e−02): es la peor celda de la rejilla sin pausar. Y lo que gana
pausado lo gana **porque `c640` es caro**, no porque `w640_i512` sea bueno: contra el campeón pausado
`c512` se queda en −0.016 y no es significativo. **El punto de operación no se mueve.** Sigue siendo
`c640` sin pausar y `c512` pausado.

Exploratorio, no pre-registrado: `w640_i512` contra `c512` tiene la **misma media** en los dos
regímenes (+0.004 sin pausar, +0.001 pausado) y una dispersión enorme por clip — de +0.543 en
`person18` a −0.188 en otro. Ensanchar la ventana a entrada constante no mejora ni empeora: **cambia
qué clips se rompen**. No arregla la cola (`p10` 0.150 -> 0.119 sin pausar, 0.109 -> 0.100 pausado) y
los cuatro peores clips de `c512` siguen igual de rotos (`bird1_1` 0.06 -> 0.10, `car12` 0.09 ->
0.09, `bike2` 0.09 -> 0.04).

**Aclaración sobre la nota 2.** Aquí, pareado por clip, `c640 − c512` sin pausar da mediana +0.003
(19/30, p=0.061 sobre los 30 clips; +0.003, 16/25 con la puerta) mientras la **media** da +0.050. O
sea que "`c640` es el punto de operación sin pausar" es un efecto de **media sobre clips**, sostenido
por la cola, y no un efecto de mediana pareada. La nota 2 comparaba siete brazos con medias y la
frase es correcta en sus términos; lo que esta nota añade es que el mismo dato pareado por clip no
alcanza significación. No es una corrección, es una acotación de fuerza.

## 5. Los controles: la celda repetida falló, y por qué eso no rompe nada

El pre-registro §2 reutilizaba `c512` y `c640` de `full-sweep-30` y `paced-sweep-30`, con **una celda
de control repetida** (`c512` sobre `person18`) como cheque, y la regla "si no coincide, los
controles se recorren".

| régimen | original | repetición | d |
| --- | ---: | ---: | ---: |
| sin pausar | 0.2385 (1393/1393) | 0.2385 (1393/1393) | +0.0000 |
| pausado 30 | 0.2382 (463/1393) | 0.3671 (456/1393) | **+0.1289** |

Sin pausar reproduce a cuatro decimales — determinista, reutilización válida. **Pausado falló**, así
que se ejecutó lo pre-registrado y los dos controles se recorrieron enteros (`wingrid-ctl2-30`,
50 corridas, 0.55 h). Las dos columnas de la tabla de la §3 son ese antes y después: **coinciden en
los cuatro contrastes** (W4 +0.046 contra +0.049, W2 −0.070 contra −0.059, W1 idéntico, W3 idéntico)
y en el signo y la cuenta de todos.

Con los dos controles pausados completos se puede medir la reproducibilidad del protocolo pausado,
que nadie había medido en la campaña — dos sesiones independientes, mismos 25 clips:

| brazo | media sesión 1 | media sesión 2 | \|d\| mediana | \|d\| máx | rho | p (sesgo) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `sam2_c512` | 0.462 | 0.463 | 0.002 | 0.057 | 0.995 | 0.63 |
| `sam2_c640` | 0.420 | 0.418 | 0.001 | 0.016 | 0.999 | 0.21 |

Y el contraste pareado se reproduce: `c640 − c512` da −0.060 (3/25, p=1.3e−03) en una sesión y
−0.068 (3/25, p=9.1e−04) en la otra.

**O sea que el protocolo pausado es muy reproducible y la celda de cheque estaba mal elegida.** Cayó
justo sobre `person18`, el único clip bimodal del conjunto: tres corridas de la misma configuración
dan 0.238, 0.295 y 0.367 según si el brazo se engancha a las piernas o no, y la pausa decide cuál. La
lección no es "no reutilizar controles" — es que un cheque de una celda sobre un clip inestable no
mide lo que se quería medir. Elegir la celda de cheque por estabilidad conocida, no por interés.

## 6. `person18`: la explicación de la nota 22 es cierta en ese clip, y se ve

| brazo | sin pausar | pausado 30 |
| --- | ---: | ---: |
| `sam2_c512` | 0.239 | 0.238 / 0.295 |
| `sam2_w640_i512` | **0.782** | **0.732** |
| `sam2_w512_i640` | 0.284 | 0.290 |
| `sam2_c640` | 0.766 | 0.689 |

El clip separa las variables limpiamente: lo que arregla `person18` es **la ventana** (0.239 ->
0.782 a entrada constante 512), no los píxeles (`w512_i640` se queda en 0.284, tan roto como
`c512`).

**Verificación visual: sí**, obligatoria por el pre-registro §4 al dispararse W4. Los dos fotogramas
son el **mismo índice, f697 de 1393**, del mismo clip pausado a 30 fps, y están commiteados:

- `raw/wingrid-30/w4_person18_c512_f697.png` — IoU 0.37. La máscara cubre **sólo las piernas**. En el
  panel de recorte de la derecha se ve por qué: la ventana de 512, centrada sobre la caja anterior
  (que ya era de las piernas), ha bajado tanto que **el sombrero y los hombros quedan sobre el borde
  superior**. El brazo no puede recuperar la cabeza porque no la tiene delante.
- `raw/wingrid-30/w4_person18_w640_i512_f697.png` — IoU 0.91, mismo fotograma, **misma entrada de 512
  px al modelo**. La ventana de 640 mantiene a la persona entera dentro y la máscara la cubre entera.

Lo que se ve es más concreto que "contexto": es un **lazo de realimentación**. Una ventana apretada
centrada sobre una caja equivocada se lleva al objetivo fuera de su propio campo de visión, y a
partir de ahí el error se sostiene solo. La ventana ancha no da mejor visión, da margen para que un
error de caja no se convierta en pérdida de objetivo.

**Interpretación, marcada como tal:** esto explica por qué la palanca de la ventana es de cola y no
de media. Sólo compra algo en los clips donde la caja ya se ha desviado lo bastante como para que la
ventana se lleve el objetivo fuera; en los otros 24 clips no hay nada que rescatar y la ventana ancha
sólo diluye la resolución efectiva.

## 7. Estimación contra realidad

| tanda | estimado | real |
| --- | ---: | ---: |
| sin pausar, 2 brazos | ~1.6 h | 2.03 h |
| pausado 30, 2 brazos | ~0.55 h | 0.54 h |
| controles | no estimado (contingente) | 0.60 h |
| **total** | **~2.2 h** | **3.17 h** |

El tramo pausado clavó la estimación (0.54 contra 0.55). El tramo sin pausar se pasó un 27%, que es
donde el `sum(init_ms + frames * ms_p50)` de los controles subestima: `w512_i640` corre a entrada 640
sobre un recorte de 512, y su `ms_p50` real salió por encima del de `c640` que se usó para estimarlo.
Las 0.60 h de controles no estaban estimadas porque eran contingentes al cheque — y el cheque falló,
así que se pagaron.

## 8. Cómo no sobreleer

- **n=25, cuatro contrastes, Holm dentro de la familia.** Los dos que sobreviven pausado (W2 y W4)
  lo hacen con holgura (Holm 1.5e−03 y 1.1e−03) y con 23/25 y 5/25 clips; los otros dos no. W4 sin
  pausar sobrevive por poco (Holm 4.6e−02) y va en contra de la hipótesis.
- **W1 no es "no hay efecto de contexto".** Es un **nulo acotado**: −0.016 con p=0.085 a n=25, y con
  un clip donde el efecto vale +0.54. La distribución es bimodal, así que la mediana es exactamente
  el estadístico que no lo ve. No se ha medido la potencia para un efecto de cola.
- **El 2x2 es de dos puntos por eje.** Que la entrada domine entre 512 y 640 no dice dónde está el
  óptimo ni que sea monótono, y no se ha corrido ninguna entrada por debajo de 512.
- **`w512_i640` remuestrea el recorte 1.25x hacia arriba.** Es el diseño de región de búsqueda de la
  literatura (LoRAT, OSTrack), pero sigue siendo interpolación: pierde pausado **inventando píxeles y
  pagándolos**, que es la peor combinación posible y no dice nada sobre el diseño en un dispositivo
  que no vaya justo.
- **`person18` es un clip.** Falsa la explicación de la nota 22 como regla general y la confirma como
  descripción de ese clip. No se puede usar para sostener una política.
- **El análisis de cola de la §4 es exploratorio**, no pre-registrado, y no lleva corrección.
- **Todo a ZOH.** La nota 24 mostró que la ordenación pausada depende del consumidor; este 2x2 no se
  ha recorrido bajo FOH.

## 9. Qué no se midió

No se midió: ninguna entrada por debajo de 512 ni ninguna ventana por encima de 640, que es hacia
donde apunta el resultado de la §4; el 2x2 bajo FOH ni bajo el techo `GT(i)`; el 2x2 a otras
velocidades que 30 fps (la rejilla de la nota 25 sólo tiene la diagonal); y por qué `w640_i512` se
hunde a 0.699 sin pausar cuando `c640` está en 0.785 con la misma ventana — la entrada de 512 sobre
recorte de 640 pierde algo que este diseño no aísla.

La verificación visual cubre `person18` en los dos brazos de la §6 y **nada más**. Ninguna afirmación
de las §2-§5 se apoya en píxeles mirados.
