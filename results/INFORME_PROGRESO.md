---
title: LLMs y VLMs locales en hardware de borde
subtitle: Resumen técnico de progreso para la tesis de máster
author: Javier F. Dibo Gómez
comment: Jetson Orin Nano 8 GB — Partes I, II y III · 25 de junio de 2026
locale: es
code_theme: github-dark
---

## 1. Resumen ejecutivo

Este informe resume el estado de una tesis de máster sobre **ejecución de modelos de
lenguaje y de visión-lenguaje (VLM) localmente en hardware de borde** — una NVIDIA
Jetson Orin Nano con solo 8 GB de memoria unificada, a 15 W con relojes fijados. El
trabajo se organiza como un cuaderno de laboratorio en tres partes, cada una con
puertas (*gates*): ninguna fase empieza hasta que la anterior está en verde y
documentada.

Los resultados de cabecera son tres:

- **Envolvente de rendimiento del borde:** caracterización completa de 0,5 B a 8 B de
  parámetros — de **71,5 a 7,7 tok/s** de decodificación, con la energía y la térmica
  medidas. Los 8 GB son el límite duro de capacidad (un modelo de 12 B da OOM).
- **Anclaje de lenguaje desplegado:** un modelo de *grounding* aéreo de una sola imagen,
  **Qwen2-VL-2B Q8_0, IoU@0,25 = 62,6 %** ejecutándose en el propio dispositivo —
  ~3,1× el resultado exploratorio previo (19,5 %) sobre la misma tarea.
- **Seguimiento persistente con permanencia de objeto:** lock sobre un objetivo en
  movimiento a través de oclusiones, validado en bucle cerrado (Parte III, T0–T4 todas
  GATE PASS).

La contribución metodológica central es haber **identificado y eliminado una brecha de
fidelidad de despliegue** (−23 pp ocultos en la capa de *runtime*, no en la
cuantización) que aparecía solo *después* de entrenar.

<!-- caption: Las tres partes del cuaderno de un vistazo. -->
| Parte | Pregunta | Estado | Resultado de cabecera |
|---|---|---|---|
| I — Exploratoria | ¿Qué aguanta el dispositivo? ¿Se puede *groundear*? | Congelada | Envolvente 0,5–8 B + Stages 1–4 |
| II — Reconstrucción v2 | ¿Dónde está el objeto que nombra la frase, en esta imagen? | Completa | IoU@0,25 = 62,6 % desplegado |
| III — Permanencia v3 | ¿Mantengo el lock sobre ese objeto en movimiento? | Completa | 71,5 % cobertura en SITL en vivo |

Todas las medidas: **Jetson Orin Nano 8 GB, 15 W con relojes fijados
(`nvpmodel -m 0` + `jetson_clocks`), llama.cpp commit `57fe1f0`, CUDA sm_87.**

## 2. Parte I — Exploratoria (congelada)

La Parte I estableció la envolvente de rendimiento del hardware y un primer intento de
*grounding* con VLM. Es el registro histórico, ya congelado.

### 2.1 Campañas de benchmark del dispositivo

Un barrido de 10 modelos (0,5 B – 8 B, todos Q4_K_M, relojes fijados) midió la
decodificación, el prefill, la energía y la térmica con `tegrastats` durante toda la
ventana de inferencia.

<!-- caption: Extracto del barrido de 10 modelos (decodificación, eficiencia, térmica). -->
| Modelo / cuant. | Params | pp512 tok/s | tg128 tok/s | tok/s·W⁻¹ | Pico °C |
|---|---|---|---|---|---|
| Qwen2.5-0.5B Q4_K_M | 0,5 B | 3027 | 71,52 | 11,77 | 59,9 |
| Llama-3.2-3B Q4_K_M | 3,0 B | 570 | 14,60 | 2,00 | 65,1 |
| Mistral-7B-v0.3 Q4_K_M | 7,2 B | 253 | 8,39 | 0,98 | 67,3 |
| Meta-Llama-3.1-8B Q4_K_M | 8,0 B | 245 | 7,75 | 0,89 | 67,4 |

La eficiencia recorre **11,8 → 0,9 tok/s·W⁻¹** y el pico de temperatura del SoC se
mantiene en ≤ 67 °C sin *throttling* térmico observado. Un **resultado negativo**
documentado: **Gemma-3-12B QAT no carga — OOM de CUDA** (pesos ~7,7 GiB > VRAM libre).
Esto fija los 8 GB de memoria unificada como el límite de capacidad vinculante.

### 2.2 Fine-tune de *grounding* con VLM (Stages 1–4)

Tarea: expresión referente → caja delimitadora (un *box* por frase).

- **Stage 2 (RefDrone):** colapso de modo (IoU@0,25 ≈ 1 %), causado por un dataset mal
  planteado.
- **Stage 3 (RefCOCO, metodología corregida):** **PASS, IoU@0,25 = 82,5 %** (HF bf16).
- **Stage 4 (currículo RefDrone):** **fallo por poco, 19,5 %** frente a una puerta del
  20 % — una frontera de capacidad/presupuesto, no un colapso.

El hallazgo clave de la Parte I se convierte en una **restricción vinculante**: una
*brecha de fidelidad de despliegue*. La habilidad exportada cayó HF bf16 85 % → GGUF
F16 62 % → Q8_0 55 %. La pérdida de **−23 pp es una divergencia del preprocesado de
imagen Idefics3 en llama.cpp (runtime)**; solo −7 pp son cuantización. La penalización
del *runtime* domina y se descubrió *después* de entrenar.

## 3. Parte II — Reconstrucción principista v2 (completa)

Una reconstrucción deliberada del *grounding* de una sola imagen, diseñada **hacia
atrás desde el despliegue** y organizada en torno a **un único contrato compartido**: el
prompt, el parser y la métrica IoU/`center_std` viven en un solo fichero
(`contract.py`) e se importan en todas partes, de modo que prompt/parser/métrica nunca
pueden volver a divergir. Cadena de herramientas gestionada: `uv` con *lockfile* fijado,
manifiestos por ejecución, contrato bloqueado con `pytest` y commit de llama.cpp fijado.

Cinco fases con puerta, **todas PASS**:

<!-- caption: Las cinco fases v2 y su veredicto. -->
| Fase | Qué hace | Veredicto |
|---|---|---|
| 0 — fidelidad primero | Elegir el *spine* por los números, no por opinión | Qwen2-VL-2B (fidelidad ~8× mejor que SmolVLM) |
| 1 — auditoría de datos | Distribución de cajas/tamaños antes de gastar GPU | PASS |
| 2 — resolución | Resolución como variable pre-registrada | PASS |
| 3 — entrenamiento | Un único LoRA dirigido por config | IoU@0,25 = 59,5 % (3× la puerta) |
| 4 — export y despliegue | GGUF Q8_0 en la Jetson | **IoU@0,25 = 62,6 %** |

Lo decisivo de la Fase 4: el modelo **desplegado supera** a la referencia HF
(la brecha de *runtime*/preprocesado pasa a ser neta positiva: −2,7 pp runtime,
−0,5 pp cuantización). **La catástrofe de fidelidad de la Parte I queda eliminada.**

<!-- caption: Predicciones reales del modelo Q8_0 desplegado frente a verdad-terreno. -->
| Frase | Caja predicha | Caja verdad-terreno | Solape |
|---|---|---|---|
| "Los coches negros en el cruce." | [266, 476, 346, 644] | [268, 481, 343, 652] | IoU ≈ 0,9 |
| "Los coches azules a la izquierda de la calle." | [324, 267, 341, 299] | [325, 263, 342, 294] | IoU ≈ 0,9 |

El producto de la Parte II es un **anclaje** (*anchor*) de lenguaje desplegable que
corre en la propia Orin.

## 4. Parte III — Seguimiento persistente / permanencia de objeto v3 (completa)

La Parte III pasa de un *fotograma* a un *flujo de vídeo*: mantener el lock sobre un
objetivo en movimiento a través de oclusión, cambio de escala, *motion blur* y salidas
breves del encuadre, lo bastante bien como para cerrar un bucle de seguimiento de dron.
Las métricas de cabecera pasan a ser **temporales** (continuidad de pista, cambios de
identidad, re-adquisición, cobertura, error de seguimiento en bucle cerrado).

### 4.1 La arquitectura forzada por el hardware

Una pasada del VLM en la Orin es de ~0,3–1,2 Hz, pero un bucle de seguimiento necesita
~20 Hz — una brecha estructural de 20–60×. Por eso v3 ejecuta un **tracker rápido por
fotograma a 20 Hz que sostiene el lock**, con el **VLM como anclaje semántico asíncrono y
esporádico** para adquisición y re-adquisición.

### 4.2 Las cinco puertas temporales (T0–T4, todas PASS)

<!-- caption: Resultado de cada fase de la Parte III. -->
| Fase | Qué resuelve | Resultado |
|---|---|---|
| T0 — cadencia y dinámica | Medir antes de diseñar; elegir el *spine* del ancla | Qwen2-VL-2B Q8_0 @512, re-adq. por evento |
| T1 — contrato temporal | Clips SITL + métricas temporales bloqueadas en pytest | PASS |
| T2 — permanencia | Memoria de apariencia contra el re-lock del objeto equivocado | ID sw 1→0, pureza 0,725→1,000 |
| T3 — bucle cerrado | Batir el negativo de la Phase-C sobre objetivo móvil | ≈0 % → 71,5 % SITL en vivo |
| T4 — despliegue en Orin | Verificar ambas capas sobre el metal | tracker 20 Hz, ancla 0,44 Hz, 100 % parse |

La **T2 es la pieza genuinamente novedosa**: el *ByteTrack* base es un Kalman de
velocidad constante **sin memoria de apariencia**, así que re-engancha el objeto
*equivocado* tras una oclusión. Añadiendo un descriptor de apariencia en la adquisición
y re-adquiriendo por mínima distancia de descriptor, los cambios de identidad pasan de
**1 a 0** y la pureza de identidad de **0,725 a 1,000** por encima del codo de
separabilidad.

La **T3** bate directamente el resultado negativo de la Parte I (la Phase-C daba
cobertura ≈ **0 %** sobre un objetivo en movimiento) elevándola a **97,6 % cinemático /
71,5 % en SITL ArduCopter en vivo**.

El producto de la Parte III es seguimiento persistente de objetivo móvil con permanencia
de objeto, validado de extremo a extremo en SITL y en el dispositivo. Una GUI de demo de
tres pestañas ejecuta el pipeline real de dos capas (subir vídeo + frase → salida
*trackeada* en la Orin).

## 5. Las dos contribuciones transversales

El arco de la tesis se sostiene sobre dos hallazgos que cruzan las tres partes.

- **Brecha de fidelidad de despliegue.** Una habilidad VLM exportada puede perder
  silenciosamente ~23 pp en la capa de *runtime*/preprocesado, con independencia de la
  cuantización. Se descubrió tarde en la Parte I, se convirtió en una puerta medida
  *antes* de gastar GPU en la Parte II, y se eliminó.
- **Permanencia de objeto bajo desajuste de tasa impuesto por el hardware.** La brecha
  de 20–60× entre el VLM y el bucle de control fuerza la división ancla-esporádica +
  tracker-rápido, y la memoria de apariencia es necesaria para sostener la *identidad* a
  través de la oclusión. Este es el resultado novedoso de la Parte III.

<!-- caption: Cifras de cabecera para presentar. -->
| Eje | Resultado |
|---|---|
| Envolvente del borde | 71,5 → 7,7 tok/s (0,5–8 B); 8 GB es el muro de capacidad |
| Grounding de una imagen, desplegado | Qwen2-VL-2B Q8_0, IoU@0,25 = 62,6 % |
| Problema de fidelidad | identificado (−23 pp) y luego **eliminado** |
| Permanencia de objeto | pureza 0,725 → 1,000, cambios de ID → 0 |
| Seguimiento en bucle cerrado | Phase-C ≈ 0 % → 71,5 % cobertura SITL en vivo |
