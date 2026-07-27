## Grounding de un solo frame

<!-- Guion de capítulo. Cada viñeta -> un párrafo. Tablas/figuras/código ya colocados. -->

Este capítulo cubre la Parte I (exploratoria, congelada) y la Parte II (reconstrucción principiada). La Parte I se narra **como fracaso metodológico**, no como resultado: es la lección que obliga a reconstruir la evaluación desde cero. La Parte II es la respuesta a ese fallo.

### Parte I: la catástrofe de fidelidad

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — La Parte I se cuenta como un fracaso metodológico, no como un resultado.** Establece que lo medido en el banco (la RTX 3090) no era lo que ocurría en el dispositivo (la Jetson Orin Nano): cinco copias del modelo divergieron en silencio y ninguna herramienta del cuaderno permitía saber cuál era la desplegada. Sin este arco la Parte II parece burocracia; con él es la respuesta a un fallo concreto. [ver Figura banco-vs-dispositivo]
- **P2 — La cascada de fases con puerta que fue fallando.** Recorre los tres tropiezos previos a la catástrofe con sus cifras exactas y sus matices estadísticos: el *fine-tune* de la Etapa 2 colapsa a 2/200 en IoU@0,25 contra una puerta del 30 % (el diagnóstico de *mode collapse* se apoya en 5 predicciones inspeccionadas a mano, no es en sí una afirmación medida) [claim `P1-S2.1-stage2-mode-collapse`]; un modelo ajustado en RefCOCO transfiere a lo aéreo a 1/50, cuyo IC de Wilson al 95 % es ≈[0,001, 0,106], de modo que la lectura defendible es «como mucho ~10 %», no «suelo de acierto aleatorio» [claim `P1-S3.4-coco-to-aerial-domain-shift`]; y la Etapa 4 se queda a un ítem, 39/200 = 19,5 % contra una puerta del 20 %, un fallo que el intervalo de Wilson [0,146, 0,257] hace **estadísticamente indefensible** — hay que presentarlo como una decisión de ingeniería, no como una medida [claim `P1-S4.1-stage4-narrow-miss`, máquina rtx-3090].
- **P3 — La catástrofe central es la EXPORTACIÓN (HF → GGUF), no la cuantización.** Enuncia el resultado individual más fuerte de la Parte I: la exportación cuesta 30,0 pp de acierto de grounding contra una puerta de fidelidad de 5 pp, con McNemar exacta pareada en el peor emparejamiento compatible con los datos (b=45, c=15) que aún da p = 1,3e-04 y **sobrevive a Holm** — la catástrofe es significativa bajo todo emparejamiento [claim `P1-S3.3-export-parity-catastrophe`, máquina *both*]. Deja fijado desde ya que la pérdida vive en el paso de exportación a GGUF, no en la cuantización de 8 bits (se demuestra en §«La corrección de signo»).
- **P4 — Hay DOS medidas del mismo fenómeno y no coinciden; se da el par, no el número más dramático.** Presenta las dos lecturas de la brecha banco→dispositivo: la original 85,0 → 62,0 → 55,0 (−23 pp en el tramo de exportación) frente a la re-medida de la Fase 0b sobre el mismo *checkpoint*, 85,0 → 69,0 → 67,0 (−16 pp). La divergencia se atribuye a decodificación voraz frente a muestreada y a n = 100 frente a n = 200. El TFM debe dar el par y su explicación, no elegir la cifra más aparatosa. [ver Figura banco-vs-dispositivo]
- **P5 — La lección que obliga a la Parte II.** Cierra: el fallo no fue una cifra baja sino la **imposibilidad de saber qué se estaba midiendo**. La Parte II existe porque esto obliga a reconstruir la evaluación con fases con puerta y manifiestos por ejecución (SHA de git, *hash* del *lockfile*, *hash* del *dataset*) que la Parte I no tiene. Transición al siguiente apartado.

> **[FIGURA POR GENERAR]** Barras banco-vs-dispositivo con las DOS medidas discrepantes de la brecha de la Parte I (85,0→62,0→55,0 = −23 pp, y la re-medida Fase 0b 85,0→69,0→67,0 = −16 pp); es la figura que justifica la existencia de la Parte II. | fuente: runs Parte I / logs Fase 0b | script: make_proof.py

### La reconstrucción principiada: fases con puerta y manifiestos

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Qué cambia respecto de la Parte I.** Establece los dos mecanismos que la Parte I no tenía: fases con puerta (cada etapa pasa un umbral pre-registrado o no se avanza) y **manifiestos por ejecución** (SHA de git, *hash* del *lockfile*, *hash* del *dataset*), que hacen imposible la divergencia silenciosa de «cinco copias». Esta es la infraestructura, no el resultado.
- **P2 — Selección de espina dorsal: Qwen2-VL-2B.** Da la comparación cero-*shot* que fija el modelo base: Qwen2-VL-2B ancla 15/100 donde SmolVLM-500M ancla 0/100 [claim `P2-RQ0.3-spine-selection`, máquina rtx-3090] [@wang2024qwen2vl]. Salvedad pegada: la decisión se apoyó TAMBIÉN en una pata de fidelidad de exportación de −2 pp (Qwen) frente a −16 pp (SmolVLM), pero el −2 pp es 15/100 frente a 14/100, una diferencia de UN SOLO ítem presentada como propiedad de fidelidad — esa pata **no está respaldada**; la pata 15/100 vs 0/100 sí lo está.
- **P3 — Bien-planteamiento del dataset RefDrone.** Fija el conjunto de evaluación de toda la Parte II: solo 439 de 1.421 captions de validación llevan exactamente una caja real (30,9 %), muy por debajo de una barra de bien-planteamiento de 0,95, de modo que el crudo es *ill-posed* (puerta FAIL) y se adopta el subconjunto filtrado [claim `P2-RQ1.1-dataset-well-posedness`]. Es un censo completo, no una muestra, así que un IC sería un error de categoría; su peso está aguas abajo: estas mismas 439 captions sobre **316 imágenes únicas** son el conjunto de TODOS los números de la Parte II, y por eso el agrupamiento por imagen se propaga por toda la parte. [@refdrone]

### Las cifras del grounding, con su matiz

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — La escalera de resolución despeja la puerta de pre-entrenamiento aéreo.** Da la cifra: 133/439 = 30,3 % a `max_side=1024` contra una barra del 20 %, binomial exacta p = 7,77e-06, **significativa tras Holm** [claim `P2-RQ2.1-resolution-ladder-1024`, máquina rtx-3090]. El «codo» de la escalera no tiene barra numérica y es un juicio a ojo: preséntalo como decisión de diseño, no como hallazgo.
- **P2 — El LoRA alcanza el 59,5 % — y NO se titula con el 65,0 %.** Establece el número correcto: el *fine-tune* LoRA llega a 261/439 = **59,5 %** IoU@0,25 contra una puerta del 20 % [claim `P2-RQ3.1-lora-aerial-gate`, máquina rtx-3090] [@hu2022lora]. Advertencia obligatoria: NO citar en bucle el 65,0 % (n = 200) como titular — esa evaluación en-bucle es un subconjunto reusado cada época, así que 0,63/0,65/0,65 son tres medidas solapadas sobre un modelo cambiante, no tres muestras independientes. El titular es 59,5 % a n = 439.
- **P3 — El despliegue en la Jetson: 59,5 → 62,2 → 62,6 %, etiquetando la máquina por celda.** Da la cadena de la Fase 4 con su artefacto por columna: 59,5 % (HF, 261/439) → 62,2 % (F16, 273/439) → **62,6 %** (Q8\_0 en la Jetson, 275/439), contra un presupuesto de fidelidad del 57,5 % [claim `P2-RQ4.1-deploy-fidelity`, máquina *both*] [@llamacpp]. Es el número estrella de la Parte II y la eliminación de la catástrofe de la Parte I. La lectura del signo de este último salto se corrige en el apartado siguiente.
- **P4 — Verificación cualitativa y bake-off de espina.** Cierra con las dos figuras por generar: una rejilla cualitativa de aciertos y fallos sobre imagen aérea (los objetivos de RefDrone ocupan un pequeño porcentaje del ancho de frame, hay que recortar al objeto), y el bake-off de *backbone* que sostiene «ningún brazo desplazó al titular» — **no** una clasificación, porque los brazos no comparten *backend* ni n.

<!-- caption: Fase 4 — acierto de grounding IoU@0,25 por artefacto, con la máquina de cada celda -->
| Artefacto | Aciertos / n | IoU@0,25 | Máquina | Runtime |
|---|---|---|---|---|
| HF (referencia) | 261/439 | 59,5 % | RTX 3090 | transformers/PyTorch |
| F16 (GGUF) | 273/439 | 62,2 % | RTX 3090 | llama.cpp |
| **Q8\_0 (desplegado)** | 275/439 | **62,6 %** | **Jetson Orin Nano (15 W)** | llama.cpp |

> **[FIGURA POR GENERAR]** Rejilla cualitativa de aciertos y fallos de grounding sobre imagen aérea (recortada al objeto: los objetivos son un pequeño % del ancho de frame). | fuente: runs/*/results.json Parte II | script: make_proof.py

> **[FIGURA POR GENERAR]** Bake-off de espina dorsal. AVISO: los brazos **no comparten backend ni n** — A y C en HF a n = 200; el titular y B en Jetson Q8\_0 a n = 439; D cancelado sin ejecutar. Sostiene «ningún brazo desplazó al titular», no un ranking. | fuente: 2026-06-30-vlm-backbone-bakeoff | script: make_proof.py [@opengvlab2025internvl3; @qwen2025qwen25vl; @google2024paligemma2; @microsoft2024florence2; @hf2025smolvlm2]

### La corrección de signo: sin pérdida medible por el runtime

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — El «−2,7 pp» es convención de magnitud de brecha, NO una pérdida.** Establece la corrección más importante del documento: el cuaderno etiqueta el último salto (a Q8\_0) como «−2,7 pp» y lo repite en cuatro sitios, pero es una convención de magnitud de brecha. Las cifras **suben**: el artefacto cuantizado (275/439) puntúa por encima de la referencia HF (261/439), y una inversión de ~3 pp sobre n = 439 está dentro del ruido de muestreo. La lectura honesta es **«sin pérdida medible por el runtime»** — nunca «la cuantización mejora el modelo». Escribirlo como pérdida es un error; como mejora, peor.
- **P2 — Dónde vive de verdad la pérdida: la exportación, no la cuantización de 8 bits.** Aporta la prueba nueva calculada por primera vez en el análisis estadístico: F16 62/100 frente a Q8\_0 55/100 sobre la parada de paridad de la Parte I da b=17, c=10, McNemar p = 0,248 — el hueco de 7 pp NO se distingue del ruido [claim `P1-S3.3-quantisation-is-not-the-cost`, máquina *both*]. Por tanto la pérdida de fidelidad está en la EXPORTACIÓN (HF → GGUF), no en la cuantización; toda frase de la tesis que atribuya parte de la caída a Q8\_0 debe matizarse.
- **P3 — Por qué la Parte II elimina la catástrofe de la Parte I.** Cierra el hilo: la Parte II supera la catástrofe porque los brazos de runtime (F16 273, Q8\_0 275) quedan POR ENCIMA de la referencia HF (261), no porque la cuantización ayude — esa diferencia de 14 ítems está dentro de lo que el emparejamiento podría producir por azar [claim `P2-RQ4.1-deploy-fidelity`]. La afirmación defendible es «no hay pérdida medible en la exportación», no «la exportación la mejoró».

### Una línea base externa: OWLv2 frente al VLM (R-13)

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Por qué existe: la primera pregunta de un tribunal es «¿comparado con qué?».** Establece que R-13 (2026-07-22) es la **única comparación contra un sistema externo** en todo el proyecto; hasta entonces la respuesta no existía y todo lo demás del cuaderno era una ablación interna. Cualquiera de las dos respuestas es contenido: o la arquitectura queda justificada, o la tesis se convierte en «¿cuándo merece un VLM su coste?».
- **P2 — El montaje, elegido para no montar un espantapájaros.** Describe la prueba: OWLv2 (`google/owlv2-base-patch16-ensemble`) en fp16 contra el VLM desplegado a Q8\_0, **las dos en el Orin**, sobre las mismas 439 muestras bien planteadas de RefDrone val y con el mismo camino de puntuación `grounding/contract.py` [@minderer2023owlv2]. El detector recibe cuatro brazos ordenados de más a menos caritativo; el registrado como titular es el más fuerte (D-phrase), no el más favorable, y se añadió D-phrase antes de puntuar precisamente para no infravalorar al detector. [ver Tabla de brazos]
- **P3 — El resultado principal: el VLM gana a todo brazo que sea un sistema.** Da la cifra pareada: VLM 63,10 % frente al mejor brazo del detector D-phrase 47,38 %; deflactado a 316 imágenes únicas, McNemar exacta p = 2,26e-07 y **sobrevive a Holm** [claim `P3-R13-owlv2-vs-vlm`, máquina jetson-orin-nano-8gb]. Matiz de n efectivo: R-29 recalibra por ICC el n efectivo a 417 (con el suelo colapsado de 316 conservado como análisis de sensibilidad conservador). [ver Tabla de brazos]
- **P4 — El resultado que IMPORTA es la descomposición: propone bien, no sabe elegir.** Enuncia el recall@k del brazo D-phrase, que sube de **47,4 % en k = 1 a 88,8 % en k = 10**; su segunda propuesta ya empata con el top-1 del VLM (63,0 % vs 63,1 %), y solo 49/439 (11,2 %) no tienen ninguna caja correcta entre las diez. Hay que enunciar la distancia como **41,5 pp entre `recall@1` y `recall@10` del mismo brazo** — no confundirla con el 90,43 % del D-oracle, que es otra cosa (brecha del oráculo de 27,3 pp). Deja claro que D-oracle NO es un sistema: elige entre las diez primeras usando la verdad-terreno, es una cota superior y nunca debe citarse como resultado de OWLv2. [ver Figura recall@k] [ver Tabla de brazos]
- **P5 — Dos apoyos de la descomposición.** Aporta las dos ablaciones: el lenguaje relacional **perjudica** — D-full (25,74 %) queda 21,6 pp por debajo de D-phrase, luego la cláusula se puntúa y arrastra el emparejamiento fuera del objetivo; y los adjetivos de apariencia son **toda** la aportación del detector — D-phrase menos D-head = 22,8 pp. [ver Figura barras por brazo]
- **P6 — Un techo arquitectónico encontrado de paso: 16 tokens.** Da el hallazgo: el codificador de texto de OWLv2 tiene `max_position_embeddings = 16` y una consulta de 17+ tokens **rompe** la pasada (`size of tensor a (17) must match tensor b (16)`) en vez de degradarse. Las descripciones de RefDrone van de 7 a 27 tokens, así que 5/439 (1,1 %) exceden lo que el modelo puede representar — una afirmación sobre la aptitud de la arquitectura para expresiones referenciales, no una molestia.
- **P7 — Y obliga a una corrección: la bifurcación se cerró por latencia SIN medir un detector.** Establece que la campaña de 2026-06-14 cerró la bifurcación «VLM extremo a extremo contra detector + selector» **por latencia y sin haber medido jamás un detector**. Medido: OWLv2 es ~**16,0x más barato** por llamada (263,5 ms de pasada frente a 4216 ms de cómputo en placa del VLM) y ocupa ~5x menos. El argumento de latencia estaba del revés; lo que descarta la ruta descompuesta es la brecha de **selección** (calidad, 41,5 pp), no el coste. **La decisión sobrevive; su justificación registrada, no.**
- **P8 — Dos cautelas que van pegadas al 16,0x o la cifra miente.** Fija las condiciones: (a) se compara contra **cómputo en placa** (prefill 3680 + decodificación 536 ms) y no contra los 4319 ms de reloj, que llevan ~103 ms de base64 por un túnel SSH — cargarle el cable al VLM daría 16,4x; (b) es **una pasada de detector contra un anclaje generativo completo**: un sistema descompuesto necesitaría además una etapa de selección que nadie ha costeado, y si esa etapa fuese a su vez un VLM el ahorro desaparece. Añade que OWLv2 corrió en fp16 con transformers/PyTorch mientras el VLM corrió en Q8\_0 con llama.cpp, así que la razón cruza dos motores de ejecución: es una observación de sistema, no una medición controlada de eficiencia.
- **P9 — Nota de no-independencia con R-14.** Advierte que el brazo VLM de esta comparación (63,10 %, arm A) **es el mismo** brazo A de R-14 del Capítulo 5, no una re-ejecución: los dos resultados comparten una medición, lo que introduce una dependencia dentro de la familia de corrección múltiple. Cómo se trata esa dependencia se detalla en el Capítulo 9 (marco estadístico). [ver Cap 9]

<!-- caption: R-13 - IoU@0,25 por brazo del detector frente al VLM desplegado, ambos en el Orin (verbatim del esquema) -->
| Brazo | IoU@0,25 | Qué es |
|---|---|---|
| VLM desplegado | **63,10 %** | el sistema de la tesis |
| D-phrase | 47,38 % | sintagma nominal con adjetivos — el mejor brazo del detector |
| D-full | 25,74 % | la expresión referencial entera |
| D-head | 24,60 % | el núcleo nominal a secas |
| D-oracle | 90,43 % | **no es un sistema**: elige entre las diez primeras con la verdad-terreno |

<!-- caption: R-13 - recall@k del brazo D-phrase (fracción de items con caja que pasa la puerta en el top-k) -->
| k | 1 | 2 | 3 | 5 | 10 |
|---|---|---|---|---|---|
| D-phrase recall@k | 47,4 % | 63,0 % | 72,4 % | 81,5 % | **88,8 %** |

![IoU@0,25 por brazo: VLM desplegado vs D-phrase/D-full/D-head/D-oracle](../experiments/2026-07-21-detector-baseline/proof/arms-bar.png)

![recall@k del detector (47,4%@1 -> 88,8%@10) y la brecha del oráculo](../experiments/2026-07-21-detector-baseline/proof/oracle-gap.png)

![rejilla cualitativa VLM vs detector sobre imagen aerea](../experiments/2026-07-21-detector-baseline/proof/qualitative-grid.png)

### Comparabilidad con RefDrone y licencias

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Advertencia obligatoria: el 62,6 % NO es comparable con la tabla publicada de RefDrone.** Establece la diferencia de protocolo: el benchmark publicado mide **F1 multi-objetivo a IoU >= 0,5** (una expresión puede mapear de 0 a 242 cajas), con estado del arte 34,44 F1 y techo humano 58,14. Lo que aquí se mide es **una caja, IoU@0,25**, sobre el 30,9 % de las captions de validación con exactamente una caja real (n = 439 de 1.421) — se descartan precisamente los casos multi-objetivo y los negativos, para los que RefDrone fue construido. Es un protocolo distinto y más fácil; poner el 62,6 % al lado del 34,44 sin esta frase sería una tergiversación. [@refdrone]
- **P2 — Licencias: la etiqueta permisiva aguas abajo no anula la cadena aguas arriba.** Declara la cadena de licencias: las anotaciones de RefDrone son CC BY 4.0 pero reutilizan imagen de VisDrone2019-DET bajo **CC BY-NC-SA 3.0**, de uso académico. Vale para un TFM y hay que declararlo explícitamente. [@refdrone; @zhu2021visdrone]
