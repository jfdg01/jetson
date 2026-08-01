# Barrido 30x7: `c640` es el punto de operación

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-07-29T02:04Z -> 2026-07-29T14:06Z (sello de los ficheros traídos, o sea el final de cada corrida).  
**Coste:** 210 corridas, **11.50 h de dispositivo** — estimación, `sum(init_ms + frames * ms_p50)` sobre los JSON; no incluye tiempo muerto entre etapas.  
**Datos:** `raw/full-sweep-30/`


## Barrido completo: 30 secuencias x 7 arms (run `full-sweep-30`, lanzado 2026-07-29T23:50Z)

Lo que los tres clips piloto no pueden dar: n. `truck3` y `wakeboard1` dicen que el crop gana,
`bird1_1` dice que no gana nada, y con n=3 elegidos a mano eso no es un resultado. Este run pasa
las **30 secuencias del subconjunto** por los **7 arms** que ya estaban caracterizados.

Arms: `sam2_t512`, `sam2_t640`, `sam2_t768`, `sam2_t1024` (frame completo reescalado) y
`sam2_c512`, `sam2_c640`, `sam2_c704` (crop a píxeles nativos). Todos `sam2.1-hiera-tiny`, bf16
autocast, 15 W mode 0, caja GT solo en el frame 0.

```
./jetson.py stage <las 30>
./jetson.py run --id full-sweep-30 \
  --arms sam2_t512 sam2_t640 sam2_t768 sam2_t1024 sam2_c512 sam2_c640 sam2_c704 \
  --seqs bike1 bike2 bird1_1 bird1_3 boat3 boat6 building5 car12 car16_1 car1_3 car8_2 car9 \
         group1_2 group2_3 person18 person19_3 person20 person21 person4_1 truck2 truck3 \
         uav1_2 uav2 uav3 uav5 uav7 wakeboard1 wakeboard5 wakeboard7 wakeboard8
```

210 jobs, 27276 frames por arm. **Sin vídeos**: este run mide, no ilustra. Los renders saldrán
después y solo de los casos que valga la pena mirar.

Estimaciones (a contrastar con lo real):

- Runtime: 27276 frames x 1.438 s (suma de los p50 de los 7 arms) = **10.9 h**, mas ~15 s de carga
  de modelo por job (210 jobs, ~53 min) = **~11.8 h**. El driver salta los JSON que ya existen, así
  que un corte no obliga a repetir nada.
- Disco: 30 secuencias ocupan ~2.5 GB en `~/tracker-sweep/data`; había 126 GB libres.

Reserva conocida, a comprobar en los resultados: 5 de las 30 (`uav1_2`, `uav2`, `uav3`, `uav5`,
`uav7`) son de 720x480. Ahí `crop_window` no puede dar una ventana de 512/640/704 y la recorta a
480x480, que SAM2 luego **escala hacia arriba** hasta `image_size`. En esos 5 clips los tres arms
de crop dejan de ser "píxeles nativos" y no son comparables sin más con los otros 25.

### Resultados (210/210, 2026-07-29T00:01Z -> 12:06Z UTC)

Mediana por secuencia (n=30 en todas las filas), no media sobre frames. `FP hueco` = frames donde
GT es NaN (objetivo fuera de campo) y el brazo contestó igual: suma sobre las 30, no mediana.

| arm | entrada | p50 | mIoU | IoU@0.25 | IoU@0.5 | perdidos | FP hueco |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `sam2_c512` | crop 512 | 100.9 ms | 0.679 | 0.956 | 0.861 | 0.0% | 150 |
| `sam2_c640` | crop 640 | 159.4 ms | **0.759** | 0.990 | 0.957 | 0.0% | 576 |
| `sam2_c704` | crop 704 | 190.7 ms | 0.762 | 0.988 | 0.956 | 0.0% | 259 |
| `sam2_t512` | frame 512 | 122.3 ms | 0.591 | 0.774 | 0.708 | 0.2% | 429 |
| `sam2_t640` | frame 640 | 180.6 ms | 0.678 | 0.948 | 0.833 | 0.0% | 385 |
| `sam2_t768` | frame 768 | 251.9 ms | 0.704 | 0.948 | 0.904 | 0.0% | 254 |
| `sam2_t1024` | frame 1024 | 434.0 ms | 0.752 | 0.952 | 0.917 | 0.0% | 267 |

Lecturas:

- **`sam2_c640` es el punto de operación.** Iguala a `c704` (-0.003 mIoU) por 31 ms menos, y bate a
  `t1024` (0.759 vs 0.752) a **2.7x su velocidad**. El crop compra resolución efectiva mucho más
  barato que subir `image_size`.
- El crop deja de pagar por encima de 640: 512 -> 640 son +0.080 de mIoU, 640 -> 704 son +0.003.
- Contrapartida de `c640`: la **peor** cuenta de falsos positivos en hueco (576) con 0% de frames
  perdidos, es decir, nunca dice "no está". Con la ventana pegada al objetivo siempre encuentra
  *algo*. Es justo lo que la heurística `coast` evita por diseño y lo que `edge` podría empeorar.
- Runtime real 12.1 h frente a las 11.8 h estimadas (+2.5%). Térmicas 58 -> 68 C, sin throttling.

La reserva de los 5 clips 720x480 (`uav1_2`, `uav2`, `uav3`, `uav5`, `uav7`) sigue en pie: ahí el
crop se recorta a 480x480 y SAM2 lo escala hacia arriba, así que esos brazos no son "píxeles
nativos". No se ha separado el análisis por ese eje.
