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

| fichero | entrada | Hz medio | mIoU | IoU@0.5 | perdidos |
| --- | --- | --- | --- | --- | --- |
| `crop_truck3_c512.mp4` | crop 512 nativo | 9.9 | 0.761 | 0.929 | 0 |
| `crop_truck3_c640.mp4` | crop 640 nativo | 6.3 | 0.773 | 0.957 | 0 |
| `crop_truck3_c704.mp4` | crop 704 nativo | 5.2 | 0.791 | 0.953 | 0 |

Comparar `crop_truck3_c640.mp4` con `res_truck3_t640.mp4` es el par más elocuente: mismo
`image_size`, mismo checkpoint, y uno pierde el camión 171 frames mientras el otro no lo pierde
nunca.

Reproducir: `analysis/render_overlay.py raw/crop-truck3/sam2_c<N>__truck3.json --out <mp4>`.
