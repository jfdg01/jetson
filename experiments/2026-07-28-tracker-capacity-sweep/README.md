# Tracker capacity sweep — catálogo de candidatos

**Estado:** catálogo, **no pre-registrado**. Este documento fija *qué* modelos son candidatos y *por qué*
cada grupo entra. No fija el comando, ni el n, ni las estimaciones — eso llega si y cuando la campaña
se pre-registre según el workflow de `CLAUDE.md`.

- **Creado:** 2026-07-28T18:41Z
- **Parte:** VI (candidato)
- **Plataforma:** Jetson Orin Nano 8 GB, 15 W (`nvpmodel` mode 0), `jetson_clocks`
- **Entorno de referencia en dispositivo:** `~/sam2-bench/.venv` — Python 3.10.12, torch 2.8.0 (CUDA OK),
  TensorRT 10.3.0, OpenCV 4.11.0 headless (`cv2.cuda` **no** compilada), `sam2` instalado.
  Ausentes: `ultralytics`, `onnxruntime`, `torch2trt`, `cv2.legacy`.

## Motivación

Nunca se ha barrido la capacidad de *tracking* de la plataforma. Lo que sí existe es medición puntual:

| Ya medido | Dónde |
| --- | --- |
| SAM2.1-tiny solo, FPS en Orin @ 15 W (512/1024) | `experiments/2026-07-01-temporal-acquire-carry/jetson_carry_bench.py` |
| `CARRY_HZ = 5.76` — tasa solo @640 | `grounding/contract.py:57` |
| Barrido de resolución, codo en 640, 1024 como fallback size-gated | `experiments/2026-07-24-resolution-decoupled-carry/` (EXP-1) |
| hiera-small y hiera-base-plus rechazados (cero mejora sobre tiny) | P5.20, `SOURCES.md:79-93` |
| SAM2 + VLM co-residentes | `experiments/2026-07-22-sam2-coresidency/cores_bench.py` |
| ByteTrack latencia CPU-only (0.051 ms mediana, p99 0.103 ms) | `runners/run_t0_cadence.py:307` |

Los huecos que este catálogo pretende cubrir:

1. La matriz completa variante × resolución nunca se cerró sobre la misma rejilla.
2. El eje *backend* está a medias: los `.plan` de TensorRT cubren solo el **encoder**, nunca la
   propagación end-to-end. No hay comparación torch fp16 vs TRT fp16.
3. Ningún tracker fuera de SAM2 y ByteTrack tiene resultados. CSRT/MIL aparecen solo en
   `grounding/deploy/video.py:85` para la demo de vídeo, sin números en Partes IV/V.
4. No se ha medido el techo multi-objeto: cuántos objetos aguanta el banco de memoria de SAM2 antes
   de caer bajo tiempo real.

Restricción de diseño: **6 integraciones para 27 arms**. Se eligen familias donde un solo repositorio
aporta varios checkpoints, en vez de 27 repos independientes.

## Artefactos ya presentes en la Jetson

| Artefacto | Ruta en dispositivo | Tamaño |
| --- | --- | --- |
| SAM2.1 hiera-tiny | `~/.cache/huggingface/hub/models--facebook--sam2.1-hiera-tiny` | ~150 MB |
| SAM2.1 hiera-small | `~/sam2-quarantine-20260727/models--facebook--sam2.1-hiera-small` | 352 MB |
| SAM2.1 hiera-base-plus | `~/sam2-quarantine-20260727/models--facebook--sam2.1-hiera-base-plus` | 618 MB |
| Encoder ONNX + plan TRT @640 (tiny) | `~/sam2-bench/enc640.onnx` / `.plan` | 109 / 56 MB |
| Encoder ONNX + plan TRT @768 (tiny) | `~/sam2-bench/enc768.onnx` / `.plan` | 109 / 56 MB |
| Encoder ONNX + plan TRT @640 (small) | `~/sam2-quarantine-20260727/enc640_small.*` | 132 / 68 MB |
| OWLv2-base (detector, no tracker) | `~/.cache/huggingface/hub/models--google--owlv2-base-patch16-ensemble` | — |

Estado del dispositivo verificado el 2026-07-28T18:41Z tras matar `llama-server`: cero procesos
>100 MB, 5.9 GB de RAM disponibles de 7.6, 126 GB de disco libre.

---

## Tier A — SAM2.1, la escala del backbone deployado

**Razonamiento.** Es la familia que ya está en producción, así que fija el eje de referencia contra el
que se lee todo lo demás. Tres de los cuatro checkpoints ya están en disco: coste de integración cero.
El cuarto (large) cierra la escala por arriba y sirve para localizar el techo de la plataforma, no para
deployarse.

| # | Modelo | Params | Estado |
| --- | --- | --- | --- |
| 1 | `facebook/sam2.1-hiera-tiny` | 38.9M | en caché HF |
| 2 | `facebook/sam2.1-hiera-small` | 46M | en cuarentena |
| 3 | `facebook/sam2.1-hiera-base-plus` | 80.8M | en cuarentena |
| 4 | `facebook/sam2.1-hiera-large` | 224M | descargar (~900 MB) |

**Advertencia.** hiera-large a 1024 con banco de memoria largo puede no caber en 8 GB. Si no cabe, eso
*es* el resultado: marca el techo de la plataforma y se documenta como negativo, no como fallo de run.

**Aviso de solapamiento.** P5.20 ya midió small y base-plus en su punto de operación y los rechazó
(cero mejora sobre tiny). El valor aquí no es re-litigar ese veredicto sino tener las cuatro variantes
sobre la **misma rejilla de resolución y backend**, que es lo que nunca se hizo.

---

## Tier B — derivados eficientes de SAM2

**Razonamiento.** Dos preguntas distintas viven en este grupo, y conviene no mezclarlas:

- **5-7 cambian el backbone** manteniendo el paradigma de memoria. Miden si existe un encoder más
  barato que Hiera-tiny con la misma calidad de propagación — la pregunta que P5.20 no pudo responder
  porque solo escaló *hacia arriba* dentro de Hiera.
- **8-9 no cambian el backbone en absoluto**: son *training-free* y reusan los pesos de tiny que ya
  están en disco. Aíslan el coste de la **política de memoria** del coste del encoder. Ese aislamiento
  es exactamente el residuo que P5.20 dejó abierto, y sale casi gratis.

| # | Modelo | Qué aporta |
| --- | --- | --- |
| 5 | **EdgeTAM** (`facebook/EdgeTAM`) | SAM2 destilado con Spatial Perceiver 2D, diseñado explícitamente para edge/móvil. El competidor directo de tiny. |
| 6 | **EfficientTAM-ti** | backbone ViT plano en vez de Hiera jerárquico — otra ruta al mismo objetivo |
| 7 | **EfficientTAM-s** | escalón siguiente del mismo, para tener pendiente y no un punto suelto |
| 8 | **SAMURAI** (sobre tiny) | SAM2 + selección de memoria *motion-aware* con Kalman, training-free |
| 9 | **SAM2Long** (sobre tiny) | memoria en árbol restringido, training-free |

---

## Tier C — OpenCV 4.11 nativo

**Razonamiento.** Coste de integración prácticamente nulo: ya están compilados en el `cv2` del venv y
solo necesitan su ONNX (pocos MB). Aportan el **suelo** de la curva coste-calidad, sin el cual el sweep
no tiene escala inferior y los números de SAM2 no se pueden contextualizar.

Corren **en CPU** — `cv2.cuda.getCudaEnabledDeviceCount()` devuelve 0 en esta build. Eso no es un
defecto para nuestro caso: un tracker que no toca la GPU deja el acelerador entero para el VLM, que es
justo la tensión que Partes V y VI llevan midiendo.

| # | Tracker | Nota |
| --- | --- | --- |
| 10 | `cv2.TrackerNano` (NanoTrackV2) | ~1M params, el suelo de latencia |
| 11 | `cv2.TrackerVit` | ViT-tracker ONNX |
| 12 | `cv2.TrackerDaSiamRPN` | Siamese clásico |
| 13 | `cv2.TrackerGOTURN` | regresión directa, referencia histórica |
| 14 | `cv2.TrackerMIL` | sin pesos — el suelo absoluto de calidad |

**Nota.** `cv2.legacy` no existe en esta build, así que CSRT/KCF/MOSSE **no** están disponibles sin
instalar `opencv-contrib-python`. CSRT sí se instaló en su día para la demo de vídeo
(`archive/DECISIONS.md:184`), pero no en este venv.

---

## Tier D — PyTracking

**Razonamiento.** La mejor relación arms/integración de todo el sweep: **un solo repositorio y una sola
API de inferencia** dan seis puntos en la curva calidad-coste, cubriendo dos generaciones de
correlation-filter profundo. Sin este grupo, el sweep salta de trackers de ~1M a transformers de ~90M
sin nada en medio.

| # | Modelo |
| --- | --- |
| 15 | ATOM |
| 16 | DiMP-18 |
| 17 | DiMP-50 |
| 18 | PrDiMP-50 |
| 19 | ToMP-50 |
| 20 | KeepTrack |

---

## Tier E — SOT transformer moderno

**Razonamiento.** Representa el estado del arte en *single object tracking* por caja. Entra porque sin
él la tesis no puede afirmar nada sobre dónde queda SAM2 frente a lo que la literatura de tracking
considera fuerte hoy.

**Es el grupo caro y el candidato a recortar.** Tres repositorios de investigación, cada uno con su
propio `lib/`, dependencias pinneadas a versiones antiguas de torch y preprocesado propio. En aarch64
con torch 2.8 hay probabilidad real de que alguno no arranque sin parches. Criterio: si uno se atasca,
se documenta como **negativo de portabilidad** (contenido válido de tesis) y se sigue — no bloquea.

| # | Modelo |
| --- | --- |
| 21 | OSTrack-256 (ViT-B) |
| 22 | MixFormerV2-S |
| 23 | HiT-Small |

---

## Tier F — detector + asociación

**Razonamiento.** Paradigma **distinto**: no es template tracking con caja en frame 0, es detección por
frame más asociación. Entra porque es la alternativa arquitectónica real al warm-start de Parte V, y
porque `ultralytics` exporta a TensorRT de forma directa — el único camino barato al eje *backend* que
hoy falta.

**Se reporta como sub-familia separada.** Meter estos arms en la misma tabla de ranking que Tiers A-E
sería comparar cosas que no resuelven la misma tarea.

| # | Arm |
| --- | --- |
| 24 | YOLO11n + ByteTrack |
| 25 | YOLO11s + ByteTrack |
| 26 | YOLO11n + BoT-SORT |
| 27 | ByteTrack propio + detecciones oracle (`runners/sitl/bytetrack.py`) — suelo de coste de asociación pura |

---

## Terreno común propuesto (no pre-registrado)

UAV123 ya está en el proyecto y es un benchmark SOT nativo: caja en frame 0, caja por frame. Encaja con
el arco E18-E23 y es el terreno común exacto que el sweep necesita.

- **Por arm:** FPS de propagación, latencia p50/p99, RAM pico, IoU/AUC sobre el mismo subconjunto.
- **Adaptación de salida:** SAM2 y derivados devuelven máscara → bbox del contorno.
- **Condiciones:** 15 W, `jetson_clocks`, nada más cargado, `n>=25` secuencias por arm.
- **Ejes secundarios**, solo sobre los arms que sobrevivan al primer corte (no sobre los 27):
  resolución 512/640/768/1024, backend torch fp16 vs TRT fp16.

## Estado / siguiente paso

Catálogo cerrado. Siguiente paso: decidir si la campaña se pre-registra como experimento de Parte VI.
Hasta entonces no hay comando, ni estimaciones, ni tabla de resultados — y este documento **no** genera
entradas en RESULTS / QUESTIONS / DECISIONS.
