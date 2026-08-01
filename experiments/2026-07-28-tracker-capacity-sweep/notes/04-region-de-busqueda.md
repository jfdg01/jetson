# Región de búsqueda: el defecto común a los 6 brazos

Parte de [`../README.md`](../README.md).

## Región de búsqueda: el defecto común a los 6 brazos (2026-07-29T16:10Z)

Hallazgo que mató `uav123-hard` y reorientó el experimento. Dos partes: qué hace SAM2 por dentro y
qué hace la literatura.

**Dónde decide SAM2.** Verificado en el código vendorizado, no inferido del paper.
`sam2.1_hiera_t.yaml:98` tiene `use_high_res_features_in_sam: true` y
`backbone_channel_list: [768, 384, 192, 96]`, así que `num_feature_levels = 3`
(`sam2_base.py:103`) y las escalas son stride 4, 8 y 16. Pero la memory attention recibe **solo**
`current_vision_feats[-1]` (`sam2_base.py:655`, `668`, `691`), o sea el nivel de **stride 16**. Los
niveles 4 y 8 (`high_res_features`) van únicamente al upsampler del mask decoder
(`sam2_base.py:745` -> `357`). Consecuencia: **la decisión de "¿sigue estando aquí el objeto?" corre
sobre una rejilla de `image_size/16`; los strides 4 y 8 solo afinan el contorno.**

Corrige una afirmación anterior de esta sesión (que la decisión más fina era de 4 px de entrada).
La máscara sale a stride 4, la semántica no.

Para el objetivo mediano de 28 px sobre 1280x720:

| brazo | rejilla de memoria | 1 celda = px originales | objetivo de 28 px |
| --- | --- | --- | --- |
| `t640` (frame completo aplastado) | 40x40 | 32 horizontal / 18 vertical | **subcelular en anchura** |
| `c640` (crop nativo) | 40x40 | 16 x 16 | ~1.75 celdas |
| `t1024` | 64x64 | 20 x 11 | ~1.4 celdas |

Esto explica el hueco `t640` vs `c640` (0.678 vs 0.759) mejor que "capacidad": a `t640` el objetivo
no llega a una celda del mecanismo que decide si sigue ahí.

**Qué hace la literatura y nosotros no.** El *factor de búsqueda* es convención universal desde
SiamFC (2016: plantilla 127 px, `context_amount 0.5`, búsqueda 255 px = 2x, relleno con la **media
por canal** en los bordes del frame — ni cero ni replicado). OSTrack (ECCV'22) usa factor 2 para la
plantilla y **6** para la búsqueda, con el lado calculado como `sqrt(w*h)` de la caja. LoRAT
(ECCV'24) usa 4 a 224 de entrada y 5 a 378. La ablación de OSTrack: **factor 4 -> 6 da +6.1% AUC
(53.7 -> 59.8), y el 7 regresa** porque el objetivo ocupa relativamente menos del recorte.

Nuestro `c640` es un cuadrado de 640 px **fijo, independiente del tamaño del objetivo**. Es un frame
más pequeño, no una región de búsqueda. Adoptar una ventana escalada al objetivo, **a igual
cómputo** (misma entrada 640x640, mismos ~159 ms):

| diseño | ventana para objetivo de 28 px | objetivo en espacio del modelo | celdas de stride 16 |
| --- | --- | --- | --- |
| `c640` actual | 640 fijo | 28 px | 1.75 |
| factor 5 | 140 px | 128 px | **8** |
| factor 6 | 168 px | 107 px | **6.7** |

Interpolar una ventana de 140 px hasta 640 no añade información, pero cambia la razón
objetivo/stride, que es lo que determina si la memory attention puede ver el objetivo. La regla
por-eje "no ampliar" del autor es correcta para frames completos y **no** aplica a regiones de
búsqueda; autorizado el 2026-07-29 tras comprobar que la literatura coincide.

`image_size` se fija en construcción (`hydra_overrides_extra=["++model.image_size=N"]`) y no se puede
cambiar a mitad de stream, así que cualquier fallback crop<->full debe mantener una sola N y mover
solo la ventana. Eso sale gratis.

Ningún paper estratifica la curva de factor de búsqueda por tamaño ni por velocidad del objetivo.
Hueco confirmado.
