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

- **`res640_drift_truck3.png`** — cuatro recortes ampliados alrededor del objetivo (frames 110,
  113, 116, 130) del arm de 640. Muestra la deriva de cerca: a 110 y 113 la caja azul ya está
  detrás del camión sobre asfalto vacío, a 116 la máscara se vacía y no recupera. Prueba de que el
  hundimiento de 640 es deriva de seguimiento y no un error de forma del modelo.
- **`smoke_truck3_bf16_frame268.png`** — frame 268/535 del smoke test previo
  (`smoke-truck3-bf16`, misma config que `t1024`), extraído a mitad de secuencia y nunca el frame
  0, que suele salir negro en renders fallidos. Verificación visual del rig antes de dar por bueno
  ningún número.

Reproducir: `analysis/render_overlay.py raw/res-truck3/sam2_t<N>__truck3.json --out <mp4>`.

## Modo crop (previsualización de geometría, sin modelo)

- **`crop512_truck3.mp4`** — `truck3` completo (535 frames), GT en verde y la ventana de recorte de
  512×512 en **naranja**, centrada en el GT frame a frame. Ningún tracker interviene: es solo la
  geometría que vería el modelo si se le alimentara el recorte en vez del frame completo. La ventana
  se desliza para quedarse dentro del frame en vez de encogerse, de modo que la resolución efectiva
  de entrada nunca cambia; en un frame de 720 de alto una ventana de más de 720 sí se recorta.
- **`crop512_truck3.mid.png`** — frame 268/535 del mismo vídeo, verificación visual.

Reproducir: `analysis/render_overlay.py --seq truck3 --crop 512 --out proof/crop512_truck3.mp4`.
