# Pre-registro: la rejilla brazo x fps bajo protocolo pausado

Escrito **2026-08-02T23:45Z, antes de lanzar nada**. Se convierte en nota numerada al cerrar; hasta
entonces vive aquí para que las hipótesis tengan fecha anterior a los datos.

## Por qué

La nota 5 confirma el hueco de literatura: **no hay curva publicada de resolución / precisión /
latencia en Orin Nano**. El barrido tiene las dos mitades por separado y ninguna junta:

- **Sin pausar** (nota 2, 210 corridas): `sam2_c640` es el punto de operación, mIoU 0.759. Cada brazo
  ve todos los fotogramas, así que la latencia no cuesta precisión — es el límite superior de
  cómputo ilimitado.
- **Pausado a 30 fps** (nota 19, 155 corridas): con descarte a la última, `sam2_c512` pasa a ser el
  mejor brazo de recorte. El punto de operación **ya se movió** al meter el reloj.

Falta el eje: **cómo se mueve el punto de operación según el flujo adelanta al dispositivo**. Un
único corte a 30 fps no es una curva. Con `--fps` el intervalo de descarte es
`latencia x fps` fotogramas (`next_frame`: `nxt = max(i + 1, int(t * fps))`), así que subir fps es
exactamente "el mismo dispositivo contra una escena que se mueve más rápido" — que es el régimen de
la Jetson a 15 W en vuelo, no el de la GPU de escritorio de los papers.

**Corrección de paso:** la nota 20 §8 dice "`lead` a fps más bajos, donde el intervalo de descarte
crece". Está al revés. `nxt = max(i + 1, int(t * fps))`: el intervalo de descarte crece con fps **a
la alza**, no a la baja. La condición de reapertura que la nota 20 quería es fps **alto**.

## Diseño

Rejilla completa: **7 brazos x 3 fps**, mismos 30 clips que `paced-sweep-30`, misma puerta
`upscales` (que dejará la mayoría en 25).

```
brazos  sam2_t512 sam2_t640 sam2_t768 sam2_c512 sam2_c640 sam2_c704 sam2_c512_lead
fps     15   60   120
```

`sam2_t1024` se cae solo por la puerta. Se añade `sam2_c512_lead` porque su nulo (nota 20) está
explícitamente acotado al régimen de 30 fps.

**Coste estimado.** Bajo protocolo pausado el coste de una pasada es la duración del flujo, no la
velocidad del brazo: las siete pasadas de `paced-sweep-30` cuestan 0.271-0.295 h **cada una**. Con
25543 fotogramas, una pasada a fps F cuesta ~`25543 / F` segundos:

| fps | h por pasada | 7 pasadas |
| ---: | ---: | ---: |
| 15 | 0.47 | 3.3 h |
| 60 | 0.12 | 0.8 h |
| 120 | 0.06 | 0.4 h |

**Total estimado: ~4.6 h de dispositivo**, ~525 corridas. Presupuesto de la noche: 10 h.

## Hipótesis, antes de los datos

- **H1 — el punto de operación baja de resolución al subir fps.** Sin pausar gana `c640`; a 30 fps
  gana `c512`. Predicción: a 60 y 120 la ventaja de `c512` sobre `c640` **crece**, y a 15 fps se
  estrecha o se invierte hacia `c640`. Si el orden de brazos no se mueve con fps, H1 es falsa y el
  resultado de la nota 19 era ruido de un solo corte.
- **H2 — la ganancia de FOH crece con fps.** FOH recupera el retardo de la caja entregada; a más fps
  más fotogramas retenidos por respuesta, luego más que recuperar. Predicción: +0.069 pareado a 30
  fps sube a 60/120 y baja hacia 0 a 15. Si FOH gana lo mismo a 15 que a 120, no está corrigiendo
  retardo y la interpretación de la nota 19 es falsa.
- **H3 — el nulo de `lead` se rompe a fps alto.** A 30 fps el salto mediano entre respuestas es de
  5.9 px contra ~230 px de margen (2.5%), y `lead` da rho=+0.027, p=0.90. A 120 fps el salto se
  cuadruplica. Predicción: `lead` deja de ser indiferente cuando el salto se acerca al margen — y si
  aparece daño, la firma de memoria envenenada (déficit creciente por tercio de clip) debería salir
  con él. Si `lead` sigue nulo a 120 fps, el nulo deja de estar acotado y pasa a ser un resultado.

## Cómo no sobreleer, escrito ya

- Los clips son de 30 fps nativos. Servirlos a 120 fps **no es un objetivo real a 120 Hz**: es la
  misma escena contra un dispositivo 4x más lento. Es la variable que interesa (cómputo contra
  movimiento) pero la etiqueta "120 fps" es del arnés, no de la cámara.
- Puntuación por índice de fotograma contra GT, como en toda la campaña. A fps alto se puntúan
  muchos fotogramas retenidos por cada respuesta — eso **es** el efecto bajo medida, no un sesgo.
- Los `uav*` (720x480) se caen en los brazos de 640+; los conjuntos comunes se comparan por pares
  como en las notas 19 y 20, nunca entre n distintos.
- 3 puntos de fps no son una curva continua. Una tendencia monótona en 3 puntos es una tendencia,
  no una ley.
- Contrastes múltiples: 7 brazos x 3 fps invita a pescar. Las tres hipótesis de arriba son las
  únicas pre-registradas; cualquier otra cosa que salga se marca como exploratoria y se corrige por
  Holm dentro de su familia.

## Desviación registrada, 2026-08-03T01:35Z: el tramo de 15 fps se recorta a tres brazos

El coste estimado (0.47 h por pasada a 15 fps, ~4.6 h en total) estaba mal. Medido sobre el tramo de
120 fps en vuelo — 80 resultados en ~62 min — el coste real es

    pared ~= n_corridas * 38 s  +  27276 s / fps  por pasada de brazo

es decir un **coste fijo por corrida de ~38 s** que la estimación no tenía (sólo contaba
`init_ms + frames * ms_p50`, que es tiempo de inferencia, no de arranque, montaje ni lectura de
fotogramas). Con eso: 120 fps ~2.4 h, 60 fps ~2.8 h, y **15 fps a 7 brazos ~5.5 h**. Los tres tramos
más el 2x2 de ventana contra entrada no caben en la noche.

Recorte: a 15 fps corren **`sam2_c512`, `sam2_c640`, `sam2_c512_lead`** (~2.4 h), que son
exactamente los brazos que sostienen las tres hipótesis — H1 es `c512` contra `c640`, H3 es `lead`
contra `c512`, y H2 (FOH contra ZOH) se prueba sobre los pares brazo-clip que haya, con n >= 25 en
todos los casos. Lo que se pierde es la fila de `t512/t640/t768/c704` **sólo en el punto de 15 fps**:
la tabla de mIoU por brazo tendrá tres columnas completas a 30/60/120 y una parcial a 15, y así hay
que leerla.

Esto se escribe antes de correr el tramo, no después de verlo.
