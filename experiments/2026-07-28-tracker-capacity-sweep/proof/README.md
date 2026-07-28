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

## Modo crop (previsualización de geometría, sin modelo)

`truck3` completo (535 frames), GT en verde y la ventana de recorte en **naranja**, centrada en el
GT frame a frame. Ningún tracker interviene: es solo la geometría que vería el modelo si se le
alimentara el recorte en vez del frame completo.

| fichero | ventana pedida | ventana real | fracción del frame |
| --- | --- | --- | --- |
| `crop512_truck3.mp4` | 512 | 512×512 | 28% |
| `crop640_truck3.mp4` | 640 | 640×640 | 44% |
| `crop720_truck3.mp4` | 768 y 1024 | 720×720 | 56% |

La ventana se desliza para quedarse dentro del frame en vez de encogerse, de modo que la resolución
efectiva de entrada nunca cambia a lo largo de la secuencia. El único límite es la altura del
frame: con 1280×720, cualquier petición por encima de 720 se recorta a 720, así que **768 y 1024
dan el mismo vídeo byte a byte** y aquí solo se guarda una copia. El pie del vídeo dice el tamaño
real (`crop 720px`), no el pedido.

Reproducir: `analysis/render_overlay.py --seq truck3 --crop <N> --out proof/crop<N>_truck3.mp4`.
