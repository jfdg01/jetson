# AsymTrack-B: elección e integración

Parte de [`../README.md`](../README.md).

**Coste:** sin corridas de dispositivo — análisis, diseño o lectura.


## Decisión: AsymTrack-B como candidato principal (2026-07-29T17:05Z)

El autor levantó dos restricciones el 2026-07-29: (1) **la salida solo necesita ser dónde está el
objeto a lo largo del tiempo**, sin máscara y sin importar el método; (2) el coste y lo ya descargado
son irrelevantes. Eso desbloquea la familia de trackers de caja ligeros, que encajan tal cual en el
contrato `arm` existente (`step()` devuelve `(box, contours)` con `contours` opcional).

Nota de diseño que esto expone: el rig llama a `mask_to_box` y tira la máscara. **Pagamos
segmentación y consumimos detección.**

### Cifras en UAV123, que es lo que tenemos montado

| tracker | UAV123 AUC | params | plantilla/búsqueda | factor | licencia |
| --- | --- | --- | --- | --- | --- |
| **AsymTrack-B** (AAAI 2025, arXiv 2503.00516) | **66.5** | **3.36M** | 192 / 384 | no reportado | **MIT** |
| HiT-Base (ICCV 2023, arXiv 2308.06904) | 65.6 | 42.1M | 128 / 256 | 4x | — |
| MixFormerV2-S (NeurIPS 2023) | 65.4 | 16.2M | 112 / 224 | no reportado | — |
| SMAT (WACV 2024, arXiv 2309.03979) | 64.3 | 3.8M | 128 / 256 | 4x | — |
| SAM2.1 Hiera-L (según DAM4SAM Tabla 11) | 68.8 | ~224M | — / 1024 | sin factor | Apache-2.0 |

AsymTrack-T 64.6 y AsymTrack-S 65.6, ambos 128/256. La cifra de MixFormerV2-S tiene desacuerdo entre
papers (65.4 propio, 63.4 citado por SMAT, 65.8 citado por AsymTrack) — marcado, no usado.

Lee la primera fila y la última juntas: **3.36M parámetros contra ~224M, 66x, por 2.3 puntos de
AUC** — y el pequeño cabe en esta placa.

### Por qué AsymTrack-B y no otro

1. **Tiene el número exacto para validar el arnés.** 66.5 AUC en UAV123. Es el peldaño que con SAM2
   era inalcanzable: SAMURAI y HiM2SAM no reportan UAV123, y el único que sí (DAM4SAM) pide 88 h y no
   tiene licencia.
2. **Ya hace nativamente lo que falta.** Recorte escalado al objetivo, entrada 384, stride 16 =
   rejilla 24x24 sobre la región de búsqueda: ~5 celdas de decisión para un objetivo de 28 px, frente
   a **1.75** de `c640`.
3. **Barato.** 3.36M parámetros; UAV123 completo cabe en horas.
4. **MIT**, verificado en el fichero LICENSE del repo. Reutilizable en la tesis sin permisos.
5. Mismo autor principal que SRRT (Jiawen Zhu), el paper de regulación adaptativa de región de
   búsqueda cuyo código nunca salió.

Riesgo declarado: **PyTracking/LTR en aarch64**. AsymTrack, HiT y SMAT comparten linaje y superficie
de instalación. Plan B si ninguno instala: MixFormerV2, que es el outlier sin dependencia declarada
de PyTracking.

### Estado de instalación (verificado en dispositivo, 2026-07-29T17:05Z)

Riesgo de aarch64 **resuelto, mejor de lo estimado**:

- `find` de `setup.py` / `*.cu` / `*.cpp` en el repo: **vacío**. Sin extensiones CUDA que compilar.
- Venv **separado** `~/tracker-sweep/.venv-asym` para no contaminar el entorno que produjo los
  resultados ya commiteados (los manifests registran su propio `freeze`).
- `install_asymtrack.sh` pinea `torch==1.12.1+cu113`, que **no se usa**: en esta placa el único torch
  CUDA aarch64 viene de `pypi.jetson-ai-lab.io/jp6/cu126`. Instalado torch 2.8.0 + torchvision 0.23.0
  desde ahí, igual que el venv de SAM2. (El script tiene además una errata, `pip install numy=1.24`.)
- `timm==0.9.2` importa contra torch 2.8.0 sin queja.
- **Trampa numpy:** las deps arrastran numpy 2.2.6 y el wheel de torch de jetson-ai-lab está
  compilado contra numpy 1.x — `UserWarning: Failed to initialize NumPy`, cualquier `.numpy()` de un
  tensor rompe. Fijado a `numpy==1.26.4`, el mismo del venv de SAM2. Verificado después: tensor CUDA
  384x384 en "Orin" y roundtrip a numpy correctos.

### Dos tropiezos de integración (2026-07-29T19:20Z)

Ninguno es del tracker; los dos cuestan tiempo y se documentan para no repetirlos.

1. **`jetson.py sync` borró el clon.** El repo se había clonado en `~/tracker-sweep/code/ext/`, y
   `sync` empuja `device/` con `rsync --delete` sobre `code/`: la siguiente sincronización de código
   se llevó por delante el checkout y los pesos. Reubicado a `~/tracker-sweep/ext/AsymTrack`, fuera
   del árbol que `sync` gobierna, con el motivo escrito en el propio `trackers.py`. El venv
   `.venv-asym` ya vivía fuera y sobrevivió.
2. **Cuota de Google Drive.** Los pesos están en una carpeta de Drive que mezcla los tres
   checkpoints con los `raw_results` completos (miles de `.txt` por secuencia de LaSOT). Un
   `gdown --folder` los recorre todos y agota la cuota pública de la carpeta:
   `Cannot retrieve the public link of the file ... or have had many accesses`, que bloquea también
   la descarga por id individual. Lo correcto es sacar los ids del listado
   (`AsymTrack_ep0500.pth.tar` base = `1hHOzWsnT1n1FQESwUk-vttkrpqVgpBHB`, backbone
   `efficientMod/xxs/model_best.pth.tar` = `1MQt0A-XqFw2vY7oC1PvWoYFnSbFVCkf7`) y bajar solo esos
   dos. Con la cuota ya agotada queda un reintento en `~/tracker-sweep/ext/fetch_weights.sh`
   (bucle cada 30 min, log en `fetch_weights.log`). **Sin pesos no hay humo, así que `asym-repro`
   está bloqueado en este punto**, no por el código.

### Humo parcial sin pesos (2026-07-29T19:35Z)

Los pesos faltan pero la arquitectura no depende de ellos para construirse ni para cronometrarse:
las formas son las mismas con pesos aleatorios. Verificado en el Jetson, venv `.venv-asym`:

- `build_asymtrack(cfg)` + `switch_to_deploy()` + `.cuda()` construye sin error. **3.55 M
  parámetros** (el paper dice 3.36 M; la diferencia cabe en qué cuenta cada uno, no se ha
  investigado).
- Pasada completa `forward_backbone` + `forward_head` sobre un frame 1280x720 sintético:
  `pred_boxes` sale `[1, 1, 4]`, `resize_factor` 3.92 para una caja de 30x20 (ventana de
  4.0*sqrt(600) = 98 px reescalada a 384).
- **Latencia p50 = 26.7 ms, 37.5 FPS**, fp32, 35 iteraciones, 5 de calentamiento descartadas,
  incluyendo el `sample_target` y la vuelta del box a CPU. **Estimación, no medida de arnés**: es
  un bucle sintético con pesos aleatorios y sin decodificar JPEG, y no se ha reconfirmado el modo
  de potencia en esa ventana. Para comparar: `sam2_c640` marca 159.4 ms p50 en el barrido real,
  o sea **~6x**. Si sobrevive a la medición con el arnés, es el primer número de un tracker SOT
  sobre Orin Nano que hemos podido encontrar publicado o no (ver "huecos confirmados").

Deriva de aquí la estimación de runtime de `asym-repro`: ~113 k frames a ~27 ms es ~50 min de
cómputo de tracker, más decodificación, bastante por debajo de la horquilla 1.5-2.5 h que se
preregistró.

### Cambios de arnés que trae el candidato

- `analysis/aggregate.py` calcula ya el **AUC de curva de éxito** (21 umbrales, 0 a 1), la métrica
  del paper. Es la única columna en **media** sobre secuencias en vez de mediana: así la reportan
  los toolkits OPE y es la única forma de que nuestro número sea comparable con uno publicado.
  Sanidad sobre `full-sweep-30`: `c704` 65.7, `c640` 64.0, `t512` 51.0 — mismo orden que mIoU,
  rango plausible. (Esos 30 clips no son UAV123 completo, así que no se comparan con 66.5.)
- `device/driver.py` elige intérprete **por brazo** (`venv_python` en el registro, por defecto
  `sys.executable`) y escribe un `freeze` por intérprete usado. Un run que mezcle SAM2 y AsymTrack
  cruza dos venvs, y "qué paquetes produjeron este número" tiene que poder contestarse para ambos.
- Brazo `asym_b` en `device/trackers.py`: envuelve su propio `lib/test/tracker/AsymTrack.py`,
  convierte xyxy<->xywh y BGR<->RGB, y `contours` es siempre `None` (cabeza `CORNER`,
  `PREDICT_MASK: false`). Construye `TrackerParams` a mano en vez de llamar a su `parameters()`,
  que exige rellenar dos `local.py` con rutas de datasets ajenas. Registra `win`, la ventana
  cuadrada de búsqueda de cada frame, para poder dibujarla en los overlays.
