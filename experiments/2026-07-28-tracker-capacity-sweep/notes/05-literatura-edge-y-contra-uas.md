# Literatura: tracking en edge y contra-UAS

Parte de [`../README.md`](../README.md).

**Coste:** sin corridas de dispositivo — análisis, diseño o lectura.


## Revisión de literatura: tracking en edge y contra-UAS (2026-07-29T16:40Z)

Seis agentes sobre literatura reciente, más tres de verificación dirigida (código, pesos, cifras
exactas). Se documenta porque **descarta candidatos que estaban en la lista de "Modelos a probar"**
de arriba y porque las razones son reutilizables.

### Lo que descarta, con motivo

| candidato | veredicto | motivo verificado |
| --- | --- | --- |
| **FocusTrack** (TGRS 2025, arXiv 2504.13604) | **fuera** | Entrenado solo en AntiUAV410 (**térmico IR**); no hay variante RGB ni una sola cifra en benchmark de luz visible. Y los 143/44 FPS son en **RTX 3090**, no en edge: ViT-B con búsqueda 256. Muerto por dominio y por coste. |
| **SRRT** (arXiv 2207.04438) | **fuera** | "Code and models will be released" — nunca se liberó. Sin repo. |
| **Detector-Augmented SAMURAI** (WACVW 2026, arXiv 2601.04798) | **fuera como modelo** | Sin código público. Su detector **YOLO-FEDER FusionNet** tampoco tiene repo ni pesos, y el dataset con el que lo preentrenan (SynDroneVision) sigue sin enlace vivo. |
| **LAF-YOLOv10** (arXiv 2602.13378) | **fuera** | No es un detector anti-dron: entrena en **VisDrone-DET2019 y UAVDT**, o sea cámara *montada en* un dron detectando coches y peatones en el suelo. Sin pesos ni código. Sus 24.3 FPS en Orin Nano / 65.4 en AGX Orin (Tabla 8, FP16, TensorRT 8.6) son reales pero de otra tarea. |
| **DAM4SAM** (IJCV 2026, arXiv 2509.13864) | **fuera por licencia** | Es el **único** tracker basado en SAM2 que reporta UAV123 (Tabla 11: SAM2.1 68.8 AUC -> DAM4SAM 70.9). Pero el repo no declara licencia (`"license": null`, sin fichero LICENSE) = todos los derechos reservados por defecto. Y es Hiera-L a 1024: ~2.8 s/frame estimados en esta placa, ~88 h para UAV123 completo. |
| **SAM2Long** | **fuera** | Ramificación en árbol de memoria; el presupuesto de 15 W no lo aguanta. |
| **EdgeTAM** | **fuera por ahora** | Sin puerto medido a Jetson/TensorRT. 16 FPS en iPhone 15 Pro Max, que no traduce. Días de ingeniería antes de la primera cifra. |
| **SAMURAI / HiM2SAM** | **vivos, pero sin ancla** | Apache-2.0 los dos, plug-ins training-free sobre los pesos SAM2.1 que ya tenemos. Pero **ninguno reporta UAV123** (LaSOT, LaSOT-ext, GOT-10k, VOT-LT). No hay contra qué validarlos en nuestro dataset. HiM2SAM además necesita CoTracker3 (público, vía `torch.hub`). |

### Lo que la literatura sí resuelve

- **El recorte cuadrado no es un capricho de SAM2.** La entrada cuadrada es casi universal (position
  embeddings de ViT), pero la *ruta* a cuadrado difiere: SAM1 y SAM2-imagen hacen letterbox
  (redimensionar lado largo + padding); YOLO hace letterbox; los trackers siamés/transformer recortan
  un cuadrado alrededor del objetivo con relleno de color medio. **Solo el video predictor de SAM2
  aplasta anisotrópicamente.** Nuestra familia `t*` es la rara.
- **El híbrido propuesto por el autor (búsqueda local + reenganche global al perder) es el diseño
  dominante** en long-term tracking: GlobalTrack, Siam R-CNN, LTMU, SPLT, y todos los ganadores de
  Anti-UAV tienen rama explícita de re-detección. Tres correcciones que impone la literatura:
  (a) el disparo debe ser **adaptativo**, no umbral fijo — TCDI mide desviación contra una media
  móvil exponencial de calidad por secuencia, y el campo señala explícitamente que los umbrales fijos
  no generalizan; (b) la re-detección debe ser barata y separada, no una segunda pasada a coste
  completo; (c) **pesar la apariencia reciente muy por encima de la plantilla original** — SiamSTA,
  ganador del 1º y 2º Anti-UAV, usa 0.9 reciente / 0.1 original.
- **Política de disparo completamente especificada** en el paper WACVW, o sea reimplementable sin su
  código: confianza del detector > 0.75, **o** CIoU(tracker, detector) > 0.7, **o** consistencia de
  trayectoria (IoU > 0.8 o distancia de centros normalizada < 0.05); más un **suelo duro de prompting
  forzado cada 30 frames** (~1 s a 30 fps) condicionado a que haya detección fiable.
- **Nuestro régimen es IRSTD, no COCO-small.** 28 px de mediana (p10 11, p90 41) cae en la banda
  "tiny/small" de AI-TOD y coincide con la media de 23 px de Anti-MUAV15. El benchmark UAV-Anti-UAV
  (1810 secuencias, ~1.05M frames, "small" = <22x22 px) mide 50 trackers con mACC media 0.272 y mejor
  0.44, frente a >0.6 típico en LaSOT.
- **Protocolos que premian abstenerse**, y que deberíamos usar porque el mIoU no mide lo que importa
  aquí: **VOT-LT F-score** (una caja confiada durante una ausencia puntúa IoU 0 pero sigue contando
  en el denominador de precisión), **OxUvA MaxGM** = `max_p sqrt((1-p)*TPR*((1-p)*TNR+p))`, y las
  **"3 R's" de TLP** (borrar un tramo intermedio de la secuencia y medir: si recupera en 200 frames,
  si recupera rápido en 30 frames ~1 s, y frames medios hasta recuperar).
- **La contaminación del memory bank de SAM2 está documentada** (SAM2Long, HiM2SAM, SAM2Plus): la
  cola FIFO (<=7 recientes + los frames con prompt) **no tiene mecanismo de corrección** — una máscara
  mala escrita una vez "es incorregible y desviará la segmentación posterior".

### Huecos confirmados en la literatura (contenido de tesis, no fallos de búsqueda)

- Ningún tracker SOT medido en **Orin Nano**. Todas las cifras "edge" de 55-61 FPS son **AGX
  Xavier** (HiT-Base 61, MixFormerV2-S 55) o **AGX Orin**. Factor de conversión medido, del propio
  LAF-YOLOv10 con el mismo modelo en ambas placas: **2.7x** AGX Orin -> Orin Nano. Consistente con el
  ancho de banda de memoria (68 GB/s frente a 137 de AGX Xavier y 205 de AGX Orin). Derating
  **estimado** de HiT-Base a esta placa: ~20-25 FPS.
- No existe **curva resolución-precisión-latencia** publicada para ningún tracker en Orin Nano.
- Nadie cuantiza el bloque de memory attention de SAM2.
- Ningún participante de los retos Anti-UAV ha usado SAM2 (lo dice explícitamente el survey
  CVPR2025W).
- Sin cuantificación específica de tracking de la penalización por destruir el aspect ratio en
  objetivos diminutos.
- Sin penalización medida por **cambiar la ventana espacial a mitad de stream** — que es justo el
  riesgo del brazo `edge` ya implementado.
- **Aviso INT8:** dos regresiones documentadas en Jetson — ViT-S+DPT vía TensorRT Model Optimizer
  INT8 es **2.7x más lento** en Orin Nano (foro NVIDIA), y DEIMv2 en Orin NX baja de 580 QPS FP16 a
  380 QPS INT8. bf16 es la opción segura.
