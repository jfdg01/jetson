# bf16 y la geometría de la ventana

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-07-29T00:05Z -> 2026-07-29T01:53Z (sello de los ficheros traídos, o sea el final de cada corrida).  
**Coste:** 23 corridas, **0.80 h de dispositivo** — estimación, `sum(init_ms + frames * ms_p50)` sobre los JSON; no incluye tiempo muerto entre etapas.  
**Datos:** `raw/smoke-truck3/`, `raw/smoke-truck3-bf16/`, `raw/res-truck3/`, `raw/crop-truck3/`, `raw/bird1_1-res-crop/`, `raw/wakeboard1-res-crop/`


## Smoke test (2026-07-29)

Un arm, una secuencia, para validar el rig extremo a extremo antes del sweep:
`sam2_t1024 × truck3` (535 frames, 1280×720), inicializado con la caja GT del frame 0 y
**propagación pura** después, sin re-anclar nunca.

| Precisión | p50 | p95 | fps | init | wall | RSS pico | GPU pico |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fp32 (bug) | 1449.9 ms | 1473.7 ms | 0.69 | 6766 ms | 785 s | 2717 MB | 724 MB |
| bf16 autocast | 432.6 ms | 436.5 ms | 2.31 | 5425 ms | 243 s | 2557 MB | 644 MB |

Exactitud (bf16, 535/535 frames puntuados): **IoU medio 0.779, IoU@0.25 0.944, IoU@0.5 0.908,
0 frames perdidos**.

**Lo que no funcionó, y por qué importa.** La primera versión de `Sam2Arm` no envolvía la
inferencia en `torch.autocast("cuda", bfloat16)`. `StreamCarry` lleva `@torch.inference_mode()`
pero **no** hace autocast por dentro: son los seis llamadores validados del proyecto los que lo
aportan. El arm corría en fp32 en silencio — 3.4× más lento y en una precisión que el proyecto no
despliega. No dio ningún error: solo iba lento. Por eso la precisión pasa a ser variable fija
declarada y queda registrada en el manifest.

Segundo fallo, menor: el driver capturaba el stdout del hijo, así que las líneas de progreso no
aparecían hasta que el arm terminaba. Corregido heredando stdout; todo cae en `driver.log`.

Deliverable: `proof/smoke_truck3_bf16.mp4` — GT en verde al 60% de alfa, salida del modelo en azul
claro, IoU por frame quemado en la imagen.

## Los tres pilotos n=1 (`res-truck3`, `crop-truck3`, `wakeboard1-res-crop`, `bird1_1-res-crop`, 2026-07-29)

Superados por `full-sweep-30` y por la base pareada de 53 secuencias; se conservan por los fallos
que destaparon y por lo que fijaron de geometría. Datos completos en `raw/`.

**Escalera de resolución en frame completo (`truck3`, 535 fr).** Latencia y memoria escalan con el
área (512 a 1024 es 4x píxeles y 3.5x tiempo); la inicialización cuesta ~5.1 s en las cuatro, o sea
que la domina la carga del checkpoint. La exactitud **no** es monótona: 512 da 0.661 mIoU, 640 se
hunde a 0.190 con 171 frames perdidos, 768 sube a 0.766 y 1024 a 0.779 (434 ms). El hundimiento de
640 está verificado en píxeles: a frame 110 la máscara ya está detrás del camión sobre asfalto
vacío, a 116 se vacía y no recupera. Es deriva, no error de forma.

**Fallo corregido:** `image_size` hay que fijarlo en construcción con el override de Hydra
`++model.image_size=N`. Asignar `predictor.image_size` tras `from_pretrained` deja
`sam_image_embedding_size` en el defecto del checkpoint y cualquier tamaño distinto de 1024 muere en
`assert backbone_features.size(2) == self.sam_image_embedding_size`. Con 1024 coincidía por
casualidad, que es por qué el smoke test lo ocultó. Tras el cambio 1024 reproduce (434.0 vs 432.6).

**Modo crop.** Al modelo se le da solo una ventana de N x N centrada en el objetivo, a píxeles
nativos (`image_size == N`, sin reescalar), persiguiendo la **propia predicción anterior del arm**,
nunca GT — en el dispositivo no hay GT más allá del frame 0. Un frame perdido mantiene la ventana.
Desacopla resolución de entrada de tamaño aparente del objetivo: el camión de `truck3` (~26x16 px)
pasa a ~10x6 al encoger el frame a 512, y se queda a 26x16 dentro de un recorte de 512.

Decisiones de geometría que siguen vigentes:

- La ventana **se desliza** para quedarse dentro del frame, no se recorta: recortarla cambiaría en
  silencio la resolución efectiva y el número dejaría de ser comparable. Comprobación en
  `analysis/render_overlay.py --self-check`.
- **704, no 720.** 720 no es entrada legal de Hiera — el pos-embed de ventana se tesela a
  `image_size/4` en bloques de 8, luego `image_size` debe ser múltiplo de 32, y 720 muere con
  `The size of tensor a (180) must match the size of tensor b (176)`. 704 es el mayor que cabe en un
  frame de 720 de alto: en clips 720p no hay crop a 768 ni a 1024.
- Los vídeos enseñan la **entrada real**: `device/run_arm.py` registra el `(x, y, s)` exacto que
  recortó el arm y el render dibuja el panel desde ese valor en vez de rederivarlo (campo
  `win_checked`, verificado frame a frame en cada ejecución).

**Crop contra frame completo, `truck3` y `wakeboard1`.** El crop gana en exactitud y en latencia a
la vez. `sam2_c512` (100.5 ms) supera a `sam2_t1024` (434 ms) en IoU@0.25 y @0.5 en las dos
secuencias, con 4.3x menos latencia; ningún arm de crop pierde un frame, incluido 640, que en frame
completo perdía 171. Recortar 512x512 sale más barato que reescalar 1280x720. En `wakeboard1` los
tres crops quedan agrupados en 0.81-0.82 mIoU — ahí la resolución dentro del crop casi no importa —
y el frame completo empeora al subir (768: 0.647, 1024: 0.637).

Lectura honesta de entonces, ya resuelta por el pareado de 53 secuencias más abajo: n=1, y no separa
las dos causas posibles (objetivo más grande en espacio de modelo **y** fondo distractor eliminado).

**`bird1_1`: el clip no prueba lo que se buscaba.** Se eligió por su hueco de GT (frames 115-173,
salida de campo) y se hunden los siete arms, ninguno pasa de 0.12 en IoU@0.5. Verificado en píxeles
(frames 0, 5, 12, 30): es metraje FPV con **HUD de telemetría superpuesto** y la línea de horizonte
artificial pasa justo sobre el pájaro; la máscara se derrama por ella y en el frame 12 mide 196x130
contra un GT de 48x33. Fuga de máscara hacia un gráfico sintético, no deriva ni falta de resolución.
Lo único legible: durante el hueco los siete devuelven **cero cajas** (0/59), que es lo correcto, y
ninguno recupera al reaparecer — en `sam2_c512` el pájaro reaparece **dentro** de la ventana
congelada (frame 210) y aun así no hay caja, luego el fallo de reenganche es de SAM2, no de la
geometría. `bird1_3` es del mismo metraje FPV y no sirve de repuesto.
