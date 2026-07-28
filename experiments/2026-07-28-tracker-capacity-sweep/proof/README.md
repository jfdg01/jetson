# Deliverables

Todos del run `res-truck3` (2026-07-29): `sam2.1-hiera-tiny` sobre `truck3` (535 frames,
1280×720), bf16 autocast, 15 W mode 0. Caja GT solo en el frame 0 y propagación pura después: el
modelo no vuelve a ver GT en ningún momento. En todos los vídeos, GT en **verde** al 60% de alfa,
salida del modelo en **azul claro**, IoU por frame en el pie.

Barrido de `image_size`, un vídeo por resolución:

| fichero | image_size | mIoU | perdidos | p50 |
| --- | --- | --- | --- | --- |
| `res_truck3_t512.mp4` | 512 | 0.661 | 1 | 122.7 ms |
| `res_truck3_t640.mp4` | 640 | 0.190 | 171 | 179.9 ms |
| `res_truck3_t768.mp4` | 768 | 0.766 | 0 | 252.0 ms |
| `res_truck3_t1024.mp4` | 1024 | 0.779 | 0 | 434.0 ms |

Lo que muestran juntos: la exactitud no es monótona con la resolución. 512, 768 y 1024 mantienen el
camión de principio a fin; 640 lo pierde a mitad y no recupera.

La deriva de 640 está verificada en píxeles (frames 110/113/116/130: la caja azul se queda detrás
del camión sobre asfalto vacío y a 116 la máscara se vacía), pero es deriva de seguimiento, no un
error de forma del modelo. Se ve en el propio `res_truck3_t640.mp4`.

Reproducir: `analysis/render_overlay.py raw/res-truck3/sam2_t<N>__truck3.json --out <mp4>`.

En el pie de cada vídeo va la tasa **media** (Hz), no la mediana: `1000 / media(ms)` sobre los
frames post-warmup, así que incluye los frames lentos, que es lo que sufre un lazo de seguimiento.
Las tablas siguen usando p50.

## Crop alimentado al modelo (run `crop-truck3`)

Al modelo se le da solo una ventana de N×N a píxeles nativos, centrada en su **propia predicción
anterior** (nunca GT). Mismos colores y mismo pie.

Los vídeos van a dos paneles. **Izquierda:** el frame completo con la ventana en naranja; su
interior se deja intacto (el recuadro se dibuja por fuera del borde y el pie va en una franja
propia debajo) porque es literalmente lo que entra al modelo. **Derecha:** esa misma ventana,
recortada con los mismos enteros `(x, y, s)` que el arm registró en el propio JSON, con GT y
predicción encima. Verificado en píxeles en el frame 268 de las tres: el interior izquierdo es
idéntico al JPEG original, y el panel derecho solo difiere del recorte crudo dentro de las cajas
GT+predicción. El render además comprueba en cada ejecución que las 533 ventanas registradas por el
dispositivo coinciden con la geometría del host (`win_checked` en la salida).

| fichero | entrada | Hz medio | mIoU | IoU@0.5 | perdidos |
| --- | --- | --- | --- | --- | --- |
| `crop_truck3_c512.mp4` | crop 512 nativo | 9.9 | 0.761 | 0.929 | 0 |
| `crop_truck3_c640.mp4` | crop 640 nativo | 6.3 | 0.773 | 0.957 | 0 |
| `crop_truck3_c704.mp4` | crop 704 nativo | 5.2 | 0.791 | 0.953 | 0 |

Comparar `crop_truck3_c640.mp4` con `res_truck3_t640.mp4` es el par más elocuente: mismo
`image_size`, mismo checkpoint, y uno pierde el camión 171 frames mientras el otro no lo pierde
nunca.

Reproducir: `analysis/render_overlay.py raw/crop-truck3/sam2_c<N>__truck3.json --out <mp4>`.

## Segunda secuencia: wakeboard1 (run `wakeboard1-res-crop`)

421 frames, 1280×720, objetivo grande que encoge de forma monótona sobre agua. Mismos 7 arms que
en `truck3`, mismo formato: `res_*` a frame completo, `crop_*` a dos paneles.

| fichero | entrada | Hz medio | mIoU | IoU@0.5 | perdidos |
| --- | --- | --- | --- | --- | --- |
| `crop_wakeboard1_c512.mp4` | crop 512 nativo | 9.8 | 0.823 | 1.000 | 0 |
| `crop_wakeboard1_c640.mp4` | crop 640 nativo | 6.2 | 0.817 | 0.993 | 0 |
| `crop_wakeboard1_c704.mp4` | crop 704 nativo | 5.2 | 0.814 | 0.988 | 0 |
| `res_wakeboard1_t512.mp4` | frame → 512 | 8.1 | 0.679 | 0.795 | 36 |
| `res_wakeboard1_t640.mp4` | frame → 640 | 5.5 | 0.701 | 0.829 | 0 |
| `res_wakeboard1_t768.mp4` | frame → 768 | 4.0 | 0.647 | 0.732 | 0 |
| `res_wakeboard1_t1024.mp4` | frame → 1024 | 2.3 | 0.637 | 0.720 | 0 |

El par más elocuente: `crop_wakeboard1_c512.mp4` contra `res_wakeboard1_t1024.mp4`. El primero es
4.3× más rápido y no falla un solo frame por encima de IoU 0.5; el segundo se queda en 0.720.

## Tercera secuencia: bird1_1, salida de campo (run `bird1_1-res-crop`)

253 frames, hueco de GT en 115–173 (el pájaro sale del encuadre y vuelve). Los siete arms se hunden
por igual, mIoU 0.08–0.19, IoU@0.5 ≤ 0.12: `crop_bird1_1_c{512,640,704}.mp4` y
`res_bird1_1_t{512,640,768,1024}.mp4`.

Lo que muestran: la rotura empieza hacia el frame 10, mucho antes del hueco. Es metraje FPV con HUD
superpuesto y la máscara se derrama por la línea del horizonte artificial que cruza al pájaro. En el
hueco los siete devuelven cero cajas, correcto; ninguno recupera al reaparecer el objetivo.
