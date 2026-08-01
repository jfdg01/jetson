# DAM4SAM: integración y perilla de resolución

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-07-30T11:52Z -> 2026-07-30T14:30Z (sello de los ficheros traídos, o sea el final de cada corrida).  
**Coste:** 35 corridas, **1.70 h de dispositivo** — estimación, `sum(init_ms + frames * ms_p50)` sobre los JSON; no incluye tiempo muerto entre etapas.  
**Datos:** `raw/dam-smoke3/`, `raw/dam-5x3/`, `raw/dam-sz-smoke/`, `raw/sam-smoke2/`, `raw/sam-5x3/`


## DAM4SAM: candidato principal (runs `dam-smoke3` y `dam-5x3`, 2026-07-30T12:55Z)

DAM4SAM (Videnovic et al., *Distractor-Aware Memory for Visual Object Tracking with SAM2*, CVPR
2025 / IJCV 2026) es SAM2.1 con una **memoria que resuelve distractores** (DRM): mismo checkpoint
`sam2.1_hiera_tiny`, cero entrenamiento, solo una política distinta de qué frames entran en la
memoria y con qué peso. Es decir, **no es un modelo nuevo: es una política de memoria** montada
sobre el mismo peso que ya lleva desplegado toda la tesis.

### Instalación (verificada en dispositivo)

- Clon `~/trackers/DAM4SAM` (rama `master`). **No se instala con pip**: el repo lleva su propio
  fork de `sam2` que chocaría con el `sam2 1.1.0` del venv principal. Se alcanza por `sys.path`,
  igual que AsymTrack.
- Venv propio `~/tracker-sweep/.venv-dam4sam` (uv, py3.10): `torch==2.8.0`, `torchvision==0.23.0`,
  `numpy==1.26.4`, `hydra-core==1.3.3`, `iopath`, `omegaconf`, `opencv-python-headless`, `pillow`,
  `tqdm`, y **`vot-toolkit==0.7.1`** (`--index-strategy unsafe-best-match --extra-index-url
  https://pypi.jetson-ai-lab.io/jp6/cu126`).
- El brazo llega al intérprete correcto por `venv_python` en el registro; `driver.py` ya lo soporta,
  no hizo falta tocar el arnés.

**Tropiezo 1 — `vot-toolkit`.** uv resolvió `0.8.1`, que ya no exporta `RegionType`:
`ImportError: cannot import name 'RegionType' from 'vot.region'`. El freeze del repo (inusable como
requirements) pinea `0.7.1`; con ese pin exacto el modelo construye.

**Tropiezo 2 — la compuerta `upscales`.** El wrapper fija la entrada a 1024, y `1024*1024 >
1280*720`, así que la compuerta vetaba **todos** los clips de UAV123 antes de correr nada. Se
registra con `image_size=None`, el mismo trato que los brazos AsymTrack: la compuerta existe para
mantener honesta *nuestra* escalera de resolución, no para prohibir un modelo de entrada fija.

**El tamaño de entrada no era una perilla y se ha abierto.** `dam4sam_tracker.py` fija
`self.input_image_size = 1024` y construye el predictor sin overrides. Los dos extremos tienen que
moverse juntos — `input_image_size` (lo que redimensiona `_prepare_image`) y `model.image_size` (lo
que fija `sam_image_embedding_size`) — o SAM2 muere en
`assert backbone_features.size(2) == self.sam_image_embedding_size`. Se parchea
`build_sam2_video_predictor` dentro del namespace del wrapper para inyectar
`++model.image_size=N`, se restaura en un `finally`, y se comprueba con un assert. Resultó importar:
640 corre a 198 ms contra 431 ms.

### Humo con verificación visual (`raw/dam-smoke3/`, bike2 @1024)

p50 431.0 ms, mIoU 0.023, 66 frames perdidos, init 7.5 s, pico GPU 1026 MB. Overlay de 3 frames
abierto: frame 0 la predicción sobre el GT, frame 60 ya sobre **otro peatón** a la izquierda, frame
300 sigue equivocada. Deriva por distractor real, no fontanería.

### 5 clips x 3 resoluciones (`raw/dam-5x3/`, 15 jobs, todos completos)

Clips: `bike2`, `car12`, `group2_3`, `bird1_3`, `truck3`. Barrido de 30 clips **cancelado a
propósito**: a 431 ms/frame @1024 no es barrible; se cambió por 5 clips interesantes y se abrió la
resolución. Los incumbentes se reagregaron **sobre esos mismos 5 clips**, no sobre las 25.

| brazo | p50 ms | mIoU | @0.25 | @0.5 | perdidos | FP en hueco | AUC | pico GPU |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `sam2_c640_pad` (incumbente) | 159.5 | 0.666 | 0.832 | 0.746 | 11.4% | 449 | 41.9 | — |
| `sam2_f5_floor` | 158.6 | 0.246 | 0.475 | 0.255 | 54.6% | 57 | 33.7 | — |
| `dam4sam_t512` | 146.8 | 0.116 | 0.076 | 0.033 | 40.2% | 190 | 24.9 | 422-495 MB |
| `dam4sam_t640` | 197.9 | 0.665 | **0.919** | **0.815** | **5.8%** | 229 | 39.0 | 523-644 MB |
| `dam4sam_t1024` | 431.3 | **0.709** | **0.937** | **0.901** | 11.9% | 164 | **43.1** | 983-1296 MB |

mIoU por secuencia (`c640_pad` / `f5_floor` / 512 / 640 / 1024):

| seq | c640_pad | f5_floor | dam512 | dam640 | dam1024 |
| --- | --- | --- | --- | --- | --- |
| `bike2` | 0.122 | 0.246 | 0.000 | 0.023 | 0.023 |
| `bird1_3` | 0.237 | 0.135 | 0.116 | 0.133 | 0.276 |
| `car12` | 0.670 | 0.027 | 0.024 | 0.690 | 0.744 |
| `group2_3` | 0.666 | 0.722 | 0.608 | 0.665 | 0.709 |
| `truck3` | 0.779 | 0.754 | 0.640 | 0.755 | 0.817 |

`init_ms` es ~7.1-7.3 s en las 15 corridas, plano en resolución: es carga de modelo, no del clip.

**Tres lecturas.**

1. **512 colapsa.** Por debajo de la resolución de entrenamiento del checkpoint el modelo deja de
   funcionar (mIoU 0.116, @0.25 = 0.076). No es una resolución barata: es una resolución rota.
2. **640 empata al incumbente en mIoU (0.665 vs 0.666) por +38 ms**, y le gana en todo lo demás:
   @0.5 0.815 vs 0.746, perdidos 5.8% vs 11.4%, FP en hueco 229 vs 449. Misma latencia de orden,
   mejor perfil de error.
3. **`bike2` — el clip de distractores, justo lo que DRM debía arreglar — es el desastre de
   DAM4SAM a todas las resoluciones** (0.000 / 0.023 / 0.023, contra 0.246 de `f5_floor`). El
   mecanismo publicado falla exactamente en su caso de uso declarado aquí.

**Verificación visual.** 7 overlays renderizados y entregados al autor: `car12`@640, `car12`@1024,
`bike2`@640, `bird1_3`@640, `group2_3`@640, `truck3`@640, `truck3`@512. Dos mid-frames abiertos:
`car12_640` IoU 0.84 en frame 250/499, `truck3_512` IoU 0.83 en frame 268/535.

### Decisión: candidato principal (autor, 2026-07-30T12:55Z)

DAM4SAM pasa a **contendiente principal**, por delante de AsymTrack-B y del incumbente `c640_pad`,
con dos configuraciones vivas: **640 como punto de operación** (latencia comparable al incumbente,
mejor @0.5 y menos pérdidas) y **1024 como techo de calidad** (mIoU 0.709, AUC 43.1, pero 431 ms).

**Advertencia que va con el número: n=5 clips.** No es una muestra con potencia; es una lectura
descriptiva sobre clips elegidos por interesantes, no al azar. Nada de esto entra en
`thesis/claims.json` hasta el barrido completo.

**Lo que se da por bueno y lo que no:**

- Bueno: la integración (venv, checkpoint, perilla de resolución, verificación visual) y la forma
  de la curva latencia/calidad en resolución.
- No: cualquier comparación con el incumbente a n=5, y en particular la ventaja en @0.5 y en
  perdidos, que es la que motiva el barrido completo.

**Siguiente:** SAMURAI con los mismos 5 clips x 3 resoluciones, y después barrido completo de los
dos. Pendiente de documentar cuando el autor lo pida: entrada en `SOURCES.md` (DAM4SAM y SAMURAI) y
los ledgers.
