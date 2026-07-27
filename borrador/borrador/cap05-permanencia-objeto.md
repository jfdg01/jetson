## Permanencia de objeto

<!-- Guion de capítulo. Cada viñeta -> un párrafo. Tablas/figuras/código ya colocados. -->

### Un grounding por frame no es seguimiento

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Grounding por frame no es seguimiento.** Establece la tesis del capítulo: invocar el VLM en cada fotograma no es seguir un objetivo, es re-detectarlo desde cero cada vez, y a ~4,3 s de pared por llamada en la placa eso es inviable en vídeo. La permanencia de objeto (Parte III, T0-T4) separa dos trabajos: mantener la identidad del objetivo y volver a fundamentarlo en lenguaje. [@ravi2024sam2]
- **P2 — El reparto de trabajo: SAM2 arrastra, el VLM re-ancla.** Aquí entra el arrastre temporal: SAM2 [@ravi2024sam2] mantiene la máscara del objetivo entre anclajes y el VLM (Qwen2-VL-2B [@wang2024qwen2vl]) solo se invoca para re-anclar, es decir para pasar de una frase a una caja. Ese reparto es lo que hace viable un VLM de 2B en la placa: no se paga el prefill del VLM por fotograma, solo en cada re-anclaje.
- **P3 — Evidencia visual, no de log.** La permanencia y el lazo cerrado son afirmaciones sobre píxeles y por tanto exigen mirar el vídeo, no leer el log. Remite a los dos GIF versionados como prueba: la máscara persiste entre anclajes y el seguidor cierra el lazo sobre un objetivo en movimiento (demo de la Parte III).
> **[CLIP]** ../experiments/2026-06-24-t2-permanence/permanence.gif — permanencia de máscara entre anclajes
> **[CLIP]** ../experiments/2026-06-24-t3-closed-loop/closedloop.gif — seguimiento en lazo cerrado (demo Parte III)

### La palanca ROI, dicha con precisión

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — El mejor resultado del proyecto, y el más fácil de exagerar.** La cifra titular es la de R-14, porque es la única que mide las dos ramas en la misma máquina y con el mismo runtime: sobre la Jetson a Q8\_0, frame completo @1024 da **63,10 %** IoU@0,25 y el recorte ROI M=2,0 @512 da **85,19 %**, es decir **+22,1 pp** pareados sobre n = 439 (b = 112, c = 15; deflactado a n efectivo = 316 imágenes únicas → b = 81, c = 11, **p = 2,50e-14**, sobrevive a Holm). Es la afirmación `P3-ROI-M2.0-512-ondevice`, una de las dos únicas del registro que son a la vez inferenciales y medidas por completo en la placa. [ver Tabla 1][ver Figura R-14 pareada]
- **P2 — Qué NO decir: el compuesto "+22,6 pp".** El "+22,6 pp" del cuaderno comparaba 85,2 % (HF bf16, en la 3090, y contra un checkpoint ya sustituido) contra 62,6 % (Q8\_0 en la Orin): un compuesto entre máquinas y entre cuantizaciones que no debe reaparecer. El control mismo-backend del barrido original era el brazo HF a frame completo, 64,0 %, que daba +21,2 pp — ese era el número defendible antes de R-14; ahora lo es el +22,1 pp de una sola máquina y una sola cuantización. La afirmación original `P3-ROI-M2.0-512` (GATE PASS - deployed) queda **superada** por `P3-ROI-M2.0-512-ondevice`.
- **P3 — El control es válido (RQ-R14.2).** El brazo A cayó en **63,10 %** (277/439) contra el 63,1 % publicado en dispositivo a frame completo (iter-2b, n = 439), exacto a la precisión reportada. Que el control reproduzca el número existente es lo que garantiza que el +22,1 pp mide la intervención y no un cambio de arnés.
- **P4 — Salvedad pegada: el prior es un oráculo, luego es cota superior.** El prior ROI es la caja de verdad-terreno inflada 2,0x y cuadrada, idéntica al oráculo que usó el 85,2 % original, así que la comparación es como-por-como; pero el número resultante es una **cota superior** de lo que el re-anclaje desplegado saca de una caja arrastrada y derivada. El decaimiento por drift lo cuantificó el RQ4 de la campaña original (85,2 % a 0 drift → 74,3 % a un drift de caja completa) y no se re-ejecuta aquí.
- **P5 — Latencia: 2,7x de prefill, y esta mitad sí es Jetson Q8\_0.** El recorte baja el prefill 2,7x (3691 → 1374 ms medidos a n = 10 en 2026-06-26; confirmado a **2,68x** en R-14, 3680 → 1371 ms de mediana, sobre n = 878 llamadas de ambos brazos). El recorte corta los megapíxeles alimentados 0,6 → 0,3 y el prompt de 837 → 385 tokens de mediana, y el prefill es visiblemente lineal en tokens. La mitad de latencia sí es una medida Jetson Q8\_0, a diferencia de la precisión original. [ver Figura prefill vs tokens]
- **P6 — Cadencia: 2,4x extremo a extremo, NO 3x.** El anclaje a ~2,0 s no es una mejora de 3x. Frente a la constante original de frame completo a 512 (2,26 s) es marginal, porque un recorte de 512x512 lleva píxeles parecidos. La mejora real es contra la ruta desplegada a 1024: **4,81 s → 2,02 s, 2,4x**, extremo a extremo.
- **P7 — El mecanismo del b-cell, mirado.** La figura de discordantes muestra que el brazo de frame completo no falla por unos píxeles: fundamenta la **instancia equivocada** de la escena (una carretera contigua, otro coche), mientras el ROI cae sobre el objetivo plausible. Es el mecanismo del b = 112 hecho visible, y explica por qué el efecto es tan grande. [ver Figura discordantes]
- **P8 — No-independencia con el Cap 4 (remite a Cap 9).** El brazo de frame completo a 63,10 % es el **mismo** número que comparte R-13 (la línea base VLM del detector OWLv2 del Cap 4): las dos afirmaciones no son independientes y no pueden contar como dos supervivientes de la corrección de familia. La deflación por dependencia se trata de forma centralizada en el Cap 9.

<!-- caption: Tabla 1. Resultado pareado en dispositivo (R-14), ambas ramas Jetson Orin Nano 8 GB a Q8_0, una sola sesión de llama-server, checkpoint desplegado phase3-terse100eos-1024, n=439. -->

| brazo | k | n | IoU@0,25 | parse | IoU media | center\_std | prefill ms (med) | decode ms (med) | pared ms (med) | tokens prompt (med) |
|---|---|---|---|---|---|---|---|---|---|---|
| A — frame completo @1024 | 277 | 439 | **63,10 %** | 1,00 | 0,477 | 21,9 | 3680 | 536 | 4319 | 837 |
| B — ROI M=2,0 @512 | 374 | 439 | **85,19 %** | 1,00 | 0,681 | 23,0 | 1371 | 533 | 1939 | 385 |

Pareado: b (ROI acierta, frame completo falla) = 112, c = 15, n = 439; deflactado a n efectivo = 316 → b = 81, c = 11; McNemar p\_raw = 1,58e-19, **p\_deflactado = 2,50e-14**.

![IoU pareado en dispositivo: frame completo 63.10% vs ROI M=2.0 85.19% (R-14)](../experiments/2026-07-21-roi-ondevice/proof/paired-iou.png)

![prefill vs tokens: el recorte ROI baja el coste de prefill](../experiments/2026-07-21-roi-ondevice/proof/prefill-vs-tokens.png)

![ejemplos discordantes del test pareado R-14](../experiments/2026-07-21-roi-ondevice/proof/discordant-examples.png)

> **[FIGURA POR GENERAR]** rejilla ROI (M x resolución de salida) con los dos ejes, precisión y prefill — es el mejor resultado del proyecto y hoy no tiene imagen (prioritaria) | fuente: experiments/2026-06-25-roi-crop-anchor/sweep_summary.json | script: make_proof.py

### El recorte ROI, en código

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Cómo se construye el recorte.** El núcleo de la palanca es `roi_window` en `grounding/roi.py`: infla la caja del prior por el factor `margin` (la M), la cuadra sobre `max(bw, bh)`, aplica un suelo `min_side` que rompe la espiral de zoom cuando la caja se encoge, y recorta y fija a los bordes del fotograma; `margin=inf` recupera el frame completo, que es el punto de control gratuito del mismo barrido. La predicción vuelve a coordenadas de imagen completa con solo la ventana de recorte (`map_to_full`), un mapeo métricamente seguro. El extracto muestra la inflación-y-recorte verbatim.

<!-- caption: grounding/roi.py:67-87 — inflación por el factor M, cuadrado, suelo min_side y recorte fijado al fotograma. -->
```python
    x1, y1, x2, y2 = (c / COORD_SCALE for c in bbox_norm)
    bw = max(1.0, (x2 - x1) * img_w) * scale
    bh = max(1.0, (y2 - y1) * img_h) * scale
    cx = (x1 + x2) / 2 * img_w
    cy = (y1 + y2) / 2 * img_h
    if shift:
        r = rng or random
        ang = r.uniform(0, 2 * math.pi)
        d = shift * max(bw, bh)
        cx += d * math.cos(ang)
        cy += d * math.sin(ang)

    if not math.isfinite(margin):
        return (0, 0, img_w, img_h)
    half = max(margin * max(bw, bh), min_side) / 2.0
    x0 = int(round(cx - half)); y0 = int(round(cy - half))
    x3 = int(round(cx + half)); y3 = int(round(cy + half))
    # Clamp to frame (edges go non-square at the border — accepted, realistic).
    x0 = max(0, min(x0, img_w - 1)); y0 = max(0, min(y0, img_h - 1))
    x3 = max(x0 + 1, min(x3, img_w)); y3 = max(y0 + 1, min(y3, img_h))
    return (x0, y0, x3, y3)
```

### Cifras de arrastre y exportación, cada una con su máquina

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Precisión del arrastre: en la 3090, y sembrada por oráculo.** La precisión del arrastre es 0,849 a `image_size` 1024 y 0,830 a 768, sobre 186 pistas de AerialMind, **en la RTX 3090** — en la Jetson solo se midieron FPS y RAM. Está además sembrada desde una caja de verdad-terreno del primer frame: siembra oráculo, no lenguaje. La afirmación `P3-carry-OP768-accuracy` adopta OP=768 por la regla congelada, y su salvedad es que 768 se eligió **por FPS** con una barra de efecto (dentro de 5 pp del 1024 de referencia), no por igualdad: el coste de precisión, si lo hay, es pequeño y estos datos no lo separan del azar (sign test pareado por pista p = 0,013 sin deflactar, pero sobre las 93 secuencias independientes b = 28, c = 16, **p = 0,096**, y Holm lo deja en 1).
- **P2 — E1, SAM2 → TensorRT: en banco solo.** El encoder de SAM2 exportado a TensorRT fp16 [@tensorrt] sube el arrastre de **4,89 a 6,15 FPS en banco solo** (n = 1); en el bucle integrado el mismo encoder da **5,0 FPS** y despeja la puerta de ≥ 5 exactamente, perdiendo ~1,15 FPS en codificar/decodificar JPEG y en el túnel SSH. Antes de E1 la tasa co-residente era **4,1 FPS** frente a la puerta de 5: un fallo marginal registrado como tal. La afirmación `P3-E1-TRT-fps` es PASS a `image_size`=768 contra un servidor **inactivo**, y queda **superada** por R-16 (siguiente sección).
- **P3 — Paridad de máscara del export.** La exportación fp16 no cambió la aritmética: `P3-E1-TRT-mask-parity` es PASS. Su salvedad es que se trata de una comprobación de equivalencia numérica, no de una afirmación de precisión muestreada — citar "100 frames" como n sería pseudo-replicación de la clase más clara.

### Lo que costaba de verdad el par desplegado (R-16)

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — El único sitio donde se cuenta R-16, y qué retira.** Este es el único sitio del texto donde se cuenta R-16 (el Cap. 3 remite aquí), y lo que retira es grande: los **6,15 FPS quedan retirados de todas las campañas de las Partes IV y V**, que emularon esa constante. La cifra de E1 es correcta y está mal usada, que es peor que estar mal: se midió con SAM2 a `image_size` **768** con encoder TensorRT, y el sistema desplegado arrastra a **1024** en PyTorch eager. La afirmación es `P4-R16-carry-rate-1024`.
- **P2 — La corrección 2,30x, descompuesta limpiamente.** Medido en la placa el 2026-07-22, el módulo desplegado da **2,688 Hz** (2,69 Hz) — una corrección de **2,30x** sobre 6,15, que se descompone en **1,83x** por el tamaño de imagen (768 → 1024, eager, 4,906 → 2,688 Hz) y **1,26x** por haber perdido TensorRT en el camino (TRT → eager a 768, 6,190 → 4,906 Hz). La reproducción de E1 es exacta: 6,190 Hz contra los 6,15 publicados, así que el hueco no es deriva de la placa sino que 6,15 se midió en una configuración que nunca se desplegó. [ver Tabla 2][ver Figura descomposición 2,30x]
- **P3 — La co-residencia sí cuesta.** La Parte IV registró que la co-residencia no costaba FPS, pero lo midió contra un servidor **inactivo**, que solo prueba memoria. Con el servidor sirviendo la carga real de grounding, el arrastre paga un **~2,3x** notablemente uniforme (2,32x, 2,22x, 2,29x, 2,26x) y el VLM paga **~2x** (pared 3753 → 7298-8379 ms de mediana). Ninguno de los dos es inmune: comparten un mismo bus de memoria y una misma iGPU. [ver Tabla 3][ver Figura co-residencia]
- **P4 — `PRUNE_AFTER = 100` no cabe.** El anillo del arrastre está medido en **fotogramas**, así que pasar de 768 a 1024 lo infló 1,78x en bytes sin que nadie tocara la constante. Dos candidatos más el VLM bajo carga **mueren por OOM** al anillo desplegado; a `PRUNE_AFTER = 32` el mismo trabajo sobrevive a 0,540 Hz por candidato sin coste medible de tasa (2,383 vs 2,368 Hz sin servidor) y retira 2,8 GB de swap. No se ha aplicado: cambiar una constante desplegada tiene su propia puerta (¿re-encuentra un objetivo tras oclusión con un horizonte de 32 fotogramas?), cuya evidencia es P5.15 y no esta campaña; es prerrequisito de P6.2.
- **P5 — La división por N era exacta; todo el error estaba en el tamaño.** Se sospechaba que dividir por N era optimista, y es **exacto**: 743,2 ms medidos contra 744,2 predichos a N = 2 (0,14 %), y 1116,3 predichos contra 1111,6 a N = 3 (0,4 %). Todo el error de `CAND_HZ` estaba en el tamaño de imagen, no en la división. La puerta G0 confirmó además que el batching de N `obj_id` en un estado es **bit-idéntico** a N estados separados (IoU de máscara 1,000 en las 500 object-frames), y amortiza el encoder: 1,37x más rápido a n = 2, 1,56x a n = 3. [ver Tabla 4][ver Figura escalado y batching]
- **P6 — Cómo se presenta: sin p-valor ni intervalo.** No lleva p-valor ni intervalo: es descriptiva, `n_efectivo = 1`, sin hipótesis pre-registrada. Su garantía no es inferencial sino de **reproducción** — reprodujo el número publicado de E1 al tercer decimal y repitió su propia celda entre un arranque sucio y otro limpio; se defiende como caracterización determinista, jamás como un efecto medido. Dos salvedades del registro: el brazo 1024+TensorRT quedó **NO EJECUTADO** (el `enc768.plan` de la placa no sirve a 1024), así que la descomposición descansa en tres celdas y no en las cuatro de un factorial completo; y la carga VLM es un cliente cerrado reenviando una imagen y un prompt, que mide contención de memoria e iGPU, no un patrón de peticiones realista.

<!-- caption: Tabla 2. Descomposición de la tasa de arrastre por candidato (R-16, M1, n=1, en la Jetson Orin Nano 8 GB): tamaño de imagen x runtime. -->

| config | image\_size | encoder | tick ms (p50) | Hz por candidato | pico CUDA MB | MemAvailable tras estado |
|---|---|---|---|---|---|---|
| reproducción de E1 | 768 | TRT fp16 | 161,5 | **6,190** | 533 | 4173 |
| ablación de tamaño | 768 | eager | 203,9 | 4,906 | 612 | 4340 |
| **desplegado** | **1024** | **eager** | **372,1** | **2,688** | 725 | 3839 |
| stretch | 1024 | TRT fp16 | NO EJECUTADO | - | - | - |

<!-- caption: Tabla 3. Co-residencia bajo carga real de grounding (R-16, M3, en la Jetson): coste de arrastre ~2,3x, VLM ~2x, OOM a N=2 con anillo 100. -->

| celda | tick p50, sin servidor | tick p50, bajo carga | coste arrastre | VLM pared p50 | swap consumido |
|---|---|---|---|---|---|
| n=1, 1024, anillo 100 | 422,3 ms (2,368 Hz) | 979,2 ms (1,021 Hz) | **2,32x** | 7298 ms | **+2923 MB** |
| n=1, 1024, anillo 32 | 419,7 ms (2,383 Hz) | 930,7 ms (1,074 Hz) | **2,22x** | 8129 ms | +140 MB |
| n=1, 768, anillo 100 | 240,0 ms (4,166 Hz) | 549,4 ms (1,820 Hz) | **2,29x** | 7454 ms | +701 MB |
| n=2, 1024, anillo 100 | 825,5 ms (1,211 Hz) | **OOM-KILLED** | - | - | - |
| n=2, 1024, anillo 32 | 819,7 ms (1,220 Hz) | 1850,4 ms (0,540 Hz) | **2,26x** | 8379 ms | +1287 MB |

<!-- caption: Tabla 4. Escalado por N candidatos a 1024 (R-16, M2, en la Jetson): la división por N es exacta; el batching de un estado amortiza el encoder. -->

| n | mode | tick ms (p50) | Hz por candidato | medido / (n·rate(1)) | pico CUDA MB |
|---|---|---|---|---|---|
| 1 | sep | 372,1 | 2,688 | - | 725 |
| 2 | sep | 743,2 | 1,346 | **0,999x** (744,2 predicho) | 868 |
| 3 | sep | 1111,6 | 0,900 | **0,996x** (1116,3 predicho) | 1012 |
| 2 | bat | 541,9 | 1,845 | 1,37x más rápido que sep | 801 |
| 3 | bat | 711,9 | 1,405 | 1,56x más rápido que sep | 879 |

![descomposición 2.30x de la tasa de arrastre (tamaño de imagen x TensorRT)](../experiments/2026-07-22-sam2-coresidency/proof/rate-decomposition.png)

![coste real de co-residencia VLM+SAM2 bajo carga](../experiments/2026-07-22-sam2-coresidency/proof/coresidency.png)

![escalado por N candidatos y horizonte de memoria (OOM a N=2 con anillo 100)](../experiments/2026-07-22-sam2-coresidency/proof/scaling-and-batching.png)

### Dos formulaciones que hay que evitar

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — "Se rechazó EdgeTAM frente a SAM2" es falso.** EdgeTAM era una alternativa condicional pre-registrada a la que nunca se llegó, porque SAM2 + TensorRT despejó la puerta en el paso anterior; nunca se midió, en ningún hardware. La formulación correcta es "no hizo falta el plan B", jamás "ganó la comparación".
- **P2 — "7,6 Hz de tasa del sistema" está inflado por fases ciegas.** Esa cifra promedia fases en las que el objetivo no se estaba fundamentando; la tasa del sistema es la de la fase de arrastre, que R-16 fija en 2,69 Hz solo y 0,540 Hz por candidato con el VLM sirviendo.

### La palanca de super-resolución, descartada por latencia

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Swin2SR se descarta por latencia, no compra nada medible.** Swin2SR [@conde2022swin2sr] sobre el recorte ROI **no compra nada medible** por +1331 ms por recorte. La afirmación `P3-SR-swin2sr-accuracy` (medida **en la 3090**) es NO — rechazada — y el rechazo es correcto pero debe justificarse sobre la latencia, que es determinista y enorme, no sobre la precisión.
- **P2 — Corrige la nota de laboratorio: no "pierde en IoU".** El re-análisis corrige la nota de laboratorio: la campaña lo registró como "pierde también en IoU", pero sobre los datos por elemento (n = 429) ningún brazo se separa de otro. Frente a LANCZOS, b = 21 y c = 14, **p = 0,31**; frente a bicúbico, b = 22 y c = 12, **p = 0,12**; el propio bicúbico contra el nativo da p = 0,26. Escribir que Swin2SR "pierde en precisión" sería afirmar más de lo que hay. [ver Tabla 5]
- **P3 — Salvedades del probe.** Dos matices más pegados a la afirmación: la prueba usó un recorte oráculo de 400x400 centrado en la verdad-terreno, así que mide el techo que la SR podría ofrecer y no el extremo a extremo; y n = 429 tras descartar 10 muestras por una razón **no aleatoria** — los objetos más grandes no caben en 400 px. La literatura de super-resolución en teledetección [@survey2025rssr; @xiao2023ediffsr] no transfiere a este recorte.

<!-- caption: Tabla 5. Prueba pareada por elemento de la super-resolución (P3-SR-swin2sr-accuracy, en la 3090, n=429): ningún brazo se separa; el descarte es por latencia (+1331 ms). -->

| comparación | b | c | p (McNemar exacto) |
|---|---|---|---|
| LANCZOS vs Swin2SR | 21 | 14 | 0,31 |
| bicúbico vs Swin2SR | 22 | 12 | 0,12 |
| bicúbico vs nativo | - | - | 0,26 |
