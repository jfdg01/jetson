# PRE-REGISTRO: ventana contra entrada, la descomposición de `c512` vs `c640`

Parte de [`../README.md`](../README.md). **Sellado antes de correr nada**; se convierte en nota
numerada al cerrar, con estimación contra realidad.

**Cuándo:** escrito 2026-08-03T01:05Z (hora local de Madrid). Corre después de la rejilla
`paced-grid-*`, para que las dos tandas no se peleen por la GPU.
**Código:** `2840898` (`Sam2CropArm(image_size=...)`, brazos `sam2_w640_i512` y `sam2_w512_i640`,
puerta `upscales` sobre `crop`), `analysis/test_wingrid.py`.

## 1. Por qué existe

Toda la campaña compara `sam2_c512` contra `sam2_c640` y **cambia dos cosas a la vez**: la ventana
de recorte y la entrada del modelo estaban atadas por construcción (`Sam2CropArm(ck, N)` ponía
`image_size = N` y ventana `N`). Así que "640 gana" (nota 2, sin pausar) y "512 gana" (nota 19,
pausado a 30 fps) son ambos resultados sobre una diagonal, no sobre un plano.

Las dos cosas que cambian:

- **contexto** — cuánta escena entra en la ventana. Con un objetivo de 302 px de alto, una ventana
  de 512 deja ~105 px de margen y una de 640 deja 169.
- **píxeles** — cuántos ve el modelo, y por tanto el coste. Es lo único que separa 0.27 h de 0.27 h
  pausado, pero 0.86 h de 1.25 h sin pausar.

La nota 22 dejó la hipótesis del contexto **sin probar**: en `person18`, `sam2_c512` da mIoU 0.238 y
sigue las piernas durante 1393 fotogramas mientras los otros cinco brazos dan 0.642-0.710. La
explicación propuesta fue que el recorte apretado deja a SAM2 sin contexto para decidir dónde acaba
la persona. Esa frase no se puede sostener sin separar las dos variables.

`Sam2CropArm(size, image_size=N)` las separa: SAM2 remuestrea el recorte a su entrada de todos
modos, así que la off-diagonal es gratis de implementar y no toca nada de los brazos existentes
(`analysis/test_wingrid.py` lo fija).

|                     | entrada 512      | entrada 640      |
| ---                 | ---              | ---              |
| **ventana 512**     | `sam2_c512`      | `sam2_w512_i640` |
| **ventana 640**     | `sam2_w640_i512` | `sam2_c640`      |

## 2. Diseño

Los mismos 30 clips de siempre; la puerta `upscales` deja **n=25** (los cinco `uav*` son 720x480 y
cualquier ventana de 512+ inventaría píxeles — la puerta ahora mira `crop`, no `image_size`, y el
test fija que ningún veto previo se mueve).

Dos regímenes, porque la pregunta se hace distinta en cada uno:

- **sin pausar** (`full-sweep-30` es el control): cada fotograma se procesa, el coste no se paga en
  retardo. Es donde `c640` gana.
- **pausado a 30 fps** (`paced-sweep-30` es el control): el brazo salta lo que no puede seguir, así
  que los píxeles de más se pagan en fotogramas perdidos. Es donde `c512` gana.

**Controles reutilizados, no recorridos.** `c512` y `c640` ya están en `full-sweep-30` y
`paced-sweep-30`, mismo protocolo y mismos clips, y el commit de hoy no toca su ruta de código.
Para no dar eso por bueno, la tanda incluye **una celda de control repetida** (`sam2_c512` sobre
`person18`) y se compara contra el JSON viejo; si no coincide, los controles se recorren y esta
reutilización se documenta como fallida.

## 3. Coste estimado

Del `sum(init_ms + frames * ms_p50)` de los controles, escalado a 25 clips:

| tanda | brazos | estimación |
| --- | --- | ---: |
| sin pausar | `w640_i512` (computo de 512), `w512_i640` (computo de 640) | ~1.6 h |
| pausado 30 | los mismos dos | ~0.55 h |
| **total** | | **~2.2 h** |

Contra la rejilla `paced-grid-*` (~5.7 h) suma ~7.9 h de las 10 disponibles.

## 4. Hipótesis, antes de ver nada

- **W1 — el contexto es la variable.** `w640_i512` recupera la mayor parte de `c640 − c512` sin
  pausar, y en `person18` sale del pozo (0.238 hacia ~0.69). Si no lo hace, la explicación de la
  nota 22 §2 es falsa y hay que escribirlo.
- **W2 — los píxeles son la variable.** El que recupera la diferencia es `w512_i640`. Compatible con
  la lectura de resolución de la nota 2, e incompatible con W1.
- **W3 — aditividad.** `(w640_i512 − c512) + (w512_i640 − c512)` contra `c640 − c512`. Si suman, son
  dos palancas independientes; si no, son la misma palanca vista dos veces y la campaña ha estado
  midiendo un único eje con dos nombres.
- **W4 — el punto de operación pausado.** Ésta es la de rendimiento: si el contexto es lo que vale
  (W1) y el coste es lo que hace perder fotogramas (nota 19), entonces `w640_i512` debería ganar
  **en los dos regímenes** — el contexto de `c640` al precio de `c512`. Sería un punto de operación
  desplegable nuevo, no una explicación. Si sale, se verifica con píxeles antes de afirmarlo.

## 5. Cómo no sobreleer, escrito ya

- n=25 en todo, pareado por clip, Wilcoxon. Cuatro contrastes en la familia (W1, W2, W3, W4) —
  Holm dentro de la familia; nada de esto es confirmatorio a n=25 salvo que el efecto sea grande.
- `person18` es **un clip**. Sirve para falsar la explicación de la nota 22, no para sostener una.
- El 2x2 es de dos puntos por eje. Que el contexto gane entre 512 y 640 no dice dónde está el óptimo
  ni que sea monótono; la rejilla fina de tamaños de ventana sigue sin correrse.
- `w512_i640` remuestrea el recorte 1.25x hacia arriba. Es el diseño de región de búsqueda de la
  literatura (LoRAT, OSTrack), pero sigue siendo interpolación: si gana, gana inventando píxeles y
  hay que decirlo así.
- Sin verificación visual salvo que W4 dispare; entonces es obligatoria antes de cualquier
  afirmación sobre lo que el brazo hace en pantalla.
