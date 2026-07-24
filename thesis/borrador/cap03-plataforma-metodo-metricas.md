## Plataforma, método y métricas

<!-- Guion de capítulo. Cada viñeta -> un párrafo. Tablas/figuras/código ya colocados. -->

### Orientación: por qué este capítulo va antes que los empíricos

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Un capítulo corto pero necesario.** Establecer que tres decisiones de medida condicionan todas las cifras posteriores y ninguna es obvia: el umbral `IoU@0,25`, el techo de potencia de la placa (15 W) y qué máquina midió cada número. Justificar el orden: van antes de los capítulos empíricos porque un tribunal pregunta por el método y por la instrumentación antes que por los resultados.
- **P2 — El diagrama del banco va antes que la primera cifra.** Anticipar la sección de topología y su regla: el capítulo presenta el diagrama del banco de pruebas *antes* de dar una sola cifra, porque de otro modo el lector supone un sistema embarcado que nunca se midió como tal. Es la razón de que la topología abra el capítulo y no lo cierre.

### El banco de pruebas: qué máquina midió qué

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — La topología real, dicha sin rodeos.** Fijar el hecho que más se malinterpreta al leer el cuaderno: en casi todas las partes **la Jetson ejecutó solo el VLM** (Qwen2-VL-2B Q8_0 sobre `llama.cpp`), servido por SSH con un PNG en base64 cruzando el cable por llamada; el arrastre con SAM2, el replay de vídeo y el *scoring* corrieron en una RTX 3090 de sobremesa. [cita @wang2024qwen2vl] [cita @ravi2024sam2] [cita @llamacpp] [ver Figura 3.1].
- **P2 — La auditoría de máquina que lo destapó.** Reportar las cifras de la revelación de composiciones (`experiments/2026-07-21-machine-disclosure/`): en la auditoría de las 76 campañas (`2c7f7a3`), de las 65 afirmaciones con puerta del registro **solo 3 se midieron íntegramente en la placa** y 47 son compuestos entre la Orin y la 3090; el `README.md` decía «todo corre en la placa, sin nube» en tres sitios y se corrigió en `cd8cca6`. Dar la cifra **vigente** del registro actual: **seis afirmaciones se midieron íntegramente en la placa, y dos de ellas son inferenciales** — `P3-ROI-M2.0-512-ondevice` y `P3-R13-owlv2-vs-vlm`. [ver Figura 3.2].
- **P3 — El host del VLM, parte por parte.** Explicar que `ambas` es la respuesta honesta y mayoritaria en las Partes IV-V (el anclaje del VLM en la Jetson, el arrastre de SAM2 en la 3090 con un tope de tasa), y que por eso ninguna cifra de esas partes puede citarse como «embarcada» sin la etiqueta de máquina. [ver Figura 3.3].
- **P4 — El coste del par desplegado, y nada más.** Presentar la tabla del coste del par co-residente en la placa —VLM más arrastre— como única cifra cuantitativa de esta sección [ver Tabla 3.1]. Citar `P4-R16-carry-rate-1024`: la constante `CARRY_HZ = 6.15` que todo replay de las Partes IV-V emulaba es **2,30x optimista** para la pila desplegada (tasa real de arrastre **2,69 Hz** en solitario a `image_size` 1024), y la restricción vinculante con dos candidatos es la **memoria** (`PRUNE_AFTER = 100` muere por OOM), no la tasa. Remitir la medida, su descomposición (1,83x tamaño x 1,26x runtime) y la corrección que obliga al Cap. 5, donde vive la cifra que corrige (los 6,15 FPS de E1) — no se repite aquí.
- **P5 — La regla de etiquetado por celda.** Enunciar la norma que gobierna todo el documento: cualquier tabla que mezcle precisión medida en la 3090 con FPS medidos en la Jetson **etiqueta la máquina por celda**; una resta entre máquinas (como el 85,2 % HF-3090 menos el 62,6 % Q8_0-Orin del ROI original) no es una medición y se marca como tal.

<!-- caption: Figura 3.1 — Diagrama del banco: la Jetson sirve solo el VLM por SSH (PNG base64); SAM2, replay y scoring en la 3090 -->
> **[FIGURA POR GENERAR]** Diagrama del banco de pruebas — Jetson Orin Nano 8 GB (VLM Qwen2-VL-2B Q8_0, servido por SSH con PNG en base64 por llamada) ⇄ RTX 3090 de sobremesa (arrastre SAM2, replay de vídeo, scoring). Etiquetar cada bloque con lo que corre y la dirección del cable. | fuente: experiments/2026-07-21-machine-disclosure/README.md | script: make_proof.py

![Reparto de qué máquina midió qué, por Parte (revelación de composiciones entre máquinas)](../experiments/2026-07-21-machine-disclosure/proof/disclosure-by-part.png)

<!-- caption: Figura 3.2 — Reparto de qué máquina midió qué, por Parte -->

![Host del VLM por Parte](../experiments/2026-07-21-machine-disclosure/proof/vlm-host-by-part.png)

<!-- caption: Figura 3.3 — Host del VLM por Parte -->

<!-- caption: Tabla 3.1 — Coste del par desplegado (VLM + arrastre) co-residente en la placa; la máquina va por celda -->

| Componente | Coste medido (en la placa) | Máquina | Fuente |
|---|---|---|---|
| VLM — anclaje generativo | prefill 3680 ms + decodificación 536 ms = 4216 ms | Jetson Orin Nano 8 GB, Q8_0, `llama.cpp` | R-14 |
| Arrastre SAM2 — por fotograma | 372,1 ms → 2,69 Hz en solitario a `image_size` 1024 | Jetson Orin Nano 8 GB, TensorRT fp16 | R-16 (`P4-R16-carry-rate-1024`) |
| Par co-residente — restricción vinculante | memoria (OOM a N=2 con `PRUNE_AFTER = 100`), no la tasa | Jetson Orin Nano 8 GB | R-16 |

<!-- caption: nota de la Tabla 3.1: la cifra `CARRY_HZ = 6.15` (E1) queda RETIRADA; la corrección 2,30x y su descomposición son material del Cap. 5. -->

### El umbral IoU@0,25

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — La elección y su flanco abierto.** Establecer que toda la precisión del proyecto se reporta a `IoU@0,25`, frente al estándar de la literatura de comprensión de expresiones referenciales que es `IoU@0,5` [cita @refdrone]. Declarar el problema sin adornarlo: **no existe justificación registrada en ningún sitio del repositorio** — `grounding/contract.py` declara la constante y apunta a la puerta, sin razón. [ver Código 3.1].
- **P2 — La justificación por escrito, que este TFM debe dar.** Argumentar la elección: el objeto aéreo mediano ronda los **~16 px** y a `IoU@0,5` la métrica es inestable (un desplazamiento de pocos píxeles hunde el solape de una caja diminuta), de modo que 0,25 mide capacidad de localización sin castigar el ruido de cuantización de coordenadas. Reportar **el IoU medio al lado** como cifra más sobria — [VERIFICAR: no hay un valor de IoU medio registrado todavía; es la partida «Justificar por escrito el umbral IoU@0,25 y reportar el IoU medio» de la deuda de evidencia, y hay que calcularla antes de cerrar el capítulo].
- **P3 — La semántica exacta de la puerta.** Precisar qué es la puerta: `IOU_GATE_THRESHOLD = 0.25`, y PASS significa que **≥ 20 % de las muestras** superan ese solape (decisión de la Parte II). Distinguir el umbral de solape por muestra (0,25) de la fracción de muestras que deben superarlo (0,20) — son dos cosas y el cuaderno las confunde con facilidad. [ver Código 3.1].
- **P4 — El flanco de tribunal, dicho explícitamente.** Cerrar reconociendo que escribir este capítulo sin resolver la justificación deja un flanco abierto en la primera pregunta del tribunal; el TFM lo cierra por escrito en lugar de heredar la constante sin defenderla.

<!-- caption: Código 3.1 — La constante de la puerta y la métrica IoU, ambas en grounding/contract.py -->
```python
IOU_GATE_THRESHOLD = 0.25   # IoU@0.25 ≥ 20% of samples = PASS (see DECISIONS Part II)

def iou(a: Sequence[float], b: Sequence[float]) -> float:
    """Intersection-over-union of two [x1,y1,x2,y2] boxes (same coordinate space)."""
    ix1 = max(a[0], b[0]); iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2]); iy2 = min(a[3], b[3])
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (a[2]-a[0]) * (a[3]-a[1])
    area_b = (b[2]-b[0]) * (b[3]-b[1])
    return inter / (area_a + area_b - inter)
```

### La placa y su techo de 15 W

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — La placa y su techo real.** Fijar el hardware: Jetson Orin Nano 8 GB, **15 W + `jetson_clocks`**. El modo de 25 W **no existe** en esta placa: el firmware expone solo 15 W y 7 W, y desbloquearlo exigiría un flasheo de bootloader que se decidió no intentar. La consecuencia que hay que llevar al texto: toda cifra de rendimiento del TFM es un **techo de 15 W, no un techo de silicio**.
- **P2 — La etiqueta MAXN, que era falsa.** Registrar la corrección como negativo documentado: una etiqueta anterior del cuaderno decía `MAXN_SUPER`, era falsa, y se corrigió el 2026-07-03. No debe reaparecer en el TFM.
- **P3 — Qué mide exactamente la potencia.** Precisar la instrumentación: la potencia medida es `VDD_IN` de `tegrastats` — entrada total de placa, **incluido un suelo de plataforma en reposo de ~5,2 W**. No es potencia de módulo ni de SoC, y toda lectura de J/tok o de vatios arrastra ese suelo.

### Lo que la placa hace, medido: el barrido de capacidad de la Parte I

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Un barrido medido que el esquema no colocaba.** Situar la sección: la Parte I dejó **15 configuraciones** medidas en la placa a 15 W + `jetson_clocks` (`experiments/2026-06-13-model-capability-sweep/` y `experiments/2026-06-14-gemma-family-sweep/`), con **84 ficheros crudos versionados**, que ningún capítulo recogía. Es evidencia medida y sin usar, no evidencia que falte.
- **P2 — El enunciado exacto de la n, porque no es uniforme.** Dar la n con precisión: *15 configuraciones; caudal a 5 repeticiones, TTFT y potencia/térmica a una sola pasada.* Solo `llama-bench` corrió con `-r 5`; el TTFT es **una** llamada por modelo y la potencia es una ventana continua de `tegrastats` a 1 Hz. Advertir que escribir «15 modelos x 5 repeticiones» sería falso para tres de las cuatro familias de métrica. [cita @llamacpp].
- **P3 — `gemma-3-12b` no carga, y el fallo es el resultado.** Reportar que 14 de las 15 produjeron caudal y una no: `gemma-3-12b` **no cargó** (`cudaMalloc` al cargar, sin rescate por descarga parcial). Ese fallo es el resultado medido, no una casilla vacía.
- **P4 — El acantilado de los 8 GB es un acantilado, no una pendiente.** Defender la primera conclusión: los diez modelos Q4_K_M entran a `n_ctx` 4096 y el de 12B no entra en absoluto — el límite de memoria es un borde, no una degradación gradual. [ver Figura 3.4].
- **P5 — El prefill nunca es la restricción.** Defender la segunda: en esta clase de carga el prefill nunca liga — **TTFT ≤ 204 ms** en las 14 configuraciones que cargaron.
- **P6 — Limitada por ancho de banda en decodificación.** Defender la tercera: la placa está limitada por ancho de banda al decodificar — `tg128` cae de **71,52 a 7,75 tok/s** sobre una razón de **12,4x** en bytes de pesos. [ver Figura 3.4].
- **P7 — H4 queda falsificada (negativo pre-registrado).** Reportar el negativo con su nombre: se pre-registró (H4) que la energía por token tendría un óptimo en 2-3B, y sale **monótonamente creciente, 0,157 → 1,795 J/tok**. Es un negativo pre-registrado y va etiquetado como tal. [ver Figura 3.4].
- **P8 — Cero estrangulamiento térmico.** Cerrar la lista de lo positivo: no hubo *thermal throttling* en todo el barrido, de modo que las cifras son de placa fría-a-caliente sostenida, no de un pico recortado por temperatura.
- **P9 — Qué NO se defiende, para no sobrevender.** Acotar el alcance: estas 15 configuraciones son LLM de **texto**, ninguna es el modelo desplegado, y **ninguna cifra de latencia posterior de la tesis se deriva de este banco** — las de después salen del VLM (R-14: prefill 3680 + decodificación 536 ms) y de SAM2 (R-16: 372,1 ms). Responde a «qué LLM de texto cabe en 8 GB», que no es la pregunta que hace el sistema final; se cuenta como caracterización de plataforma y como el origen de la regla de que el techo es de 15 W, no de silicio.
- **P10 — Cuatro defectos declarados que viajan con la sección.** Enumerar las limitaciones sin esconderlas: (1) un único modo de potencia — los brazos de 7 W y 25 W nunca se corrieron, luego **no hay curva de compromiso**; (2) la cuantización no se mantiene fija en las 15; (3) el «±» del `pp512` es una dispersión entre agregados y no ruido de medida; (4) la fórmula de J/tok del README de la campaña contradice sus propios números.

<!-- caption: Figura 3.4 — Barrido de capacidad del dispositivo: tg128 (tok/s) frente a bytes de pesos (el acantilado de los 8 GB) y J/tok monótona (H4 falsificada) -->
> **[FIGURA POR GENERAR]** Dos paneles. Panel A: `tg128` (tok/s) frente a bytes de pesos del modelo, marcando el acantilado de los 8 GB (Q4_K_M entran a `n_ctx` 4096; `gemma-3-12b` no carga) y la caída 71,52 → 7,75 tok/s sobre 12,4x. Panel B: energía por token (J/tok) frente a tamaño de parámetros, monótona 0,157 → 1,795, sin el óptimo en 2-3B que predecía H4. | fuente: experiments/2026-06-13-model-capability-sweep/ y experiments/2026-06-14-gemma-family-sweep/ | script: make_proof.py

### El marco de inferencia

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Por qué existe y qué NO es.** Enmarcar la sección obligatoria (borrador completo en `thesis/01-método-estadístico.md`, detalle en el **Anexo A**): el proyecto se llevó como cuaderno de laboratorio — se pre-registraba una puerta, se corría el brazo, se comparaba a ojo. Una búsqueda por `mcnemar|binomtest|scipy.stats|statsmodels|wilson|p-value` sobre el repositorio devolvía **cero ficheros** antes de este trabajo. Aclarar que el marco **no** convierte NOs en YESes: añade la incertidumbre que siempre debió acompañar a las puertas, y buena parte de él son reglas de rechazo, no de cálculo.
- **P2 — Punto 1: qué prueba corresponde a qué diseño, todo exacto.** Resumir la regla: McNemar exacto (pareado), binomial exacta + Wilson (un brazo contra puerta), Fisher (no pareado), Wilcoxon de rangos con signo (continuo pareado). Ninguna aproximación normal — con estos n, Wald da `[0, 0]` para un 0/6 y un límite superior mayor que 1 para un 24/25. La elección la fija el **diseño**, nunca el p-valor que sale.
- **P3 — Punto 2: `n_effective` frente a `n_rows`.** Explicar la distinción con los ejemplos del registro: seis clips por dos repeticiones deterministas son **seis** observaciones; diez ensayos SITL del mismo fallo determinista son **uno**; 439 *captions* sobre 316 imágenes no son 439 observaciones independientes. Cada afirmación declara las dos cifras y la razón por la que difieren.
- **P4 — Punto 3: la deflación a n efectivo.** Resumir `deflate_to_effective()`: se conserva la proporción y se sustituye el denominador por `n_effective` (corrección por efecto de diseño, `deff = n_rows / n_effective`), que **solo ensancha el intervalo y debilita el p-valor**, nunca al revés, luego no puede fabricar un resultado — E17 pasa de `[0, 0,28]` a `[0, 0,79]` sobre n = 1. Añadir la regla de independencia: la unidad es el **videoclip**, no la escena (P5.18: 26 escenas con puerta salen de **13 clips**, luego `n_effective = 13`), y que la calibración por ICC (R-29, límite superior al 95 %) **no recuperó ni un superviviente**. [ver Código 3.2].
- **P5 — Punto 4: diseños que no podían responder a su pregunta.** Enunciar el aporte más incómodo del marco: una comparación pareada de 5 elementos **no puede** alcanzar p < 0,05 bilateral aunque los cinco volteen — el suelo es 0,0625 — y se calcula desde n **solo**, sin mirar el resultado. La consecuencia dura: un NO salido de un diseño de n = 5 no es evidencia de ausencia de efecto, es **evidencia de ausencia de experimento**. [ver Tabla 3.2] [ver Figura 3.5].
- **P6 — Punto 5: empates y pruebas que no existen.** Cero pares discordantes devuelve `NaN`, no p = 1,0 — «indefinido» significa que no hubo prueba, no «brazos equivalentes». Ilustrar con los tres empates de simulación (24/24 vs 24/24, 24/24 vs 23/24, 56/56 vs 55/56).
- **P7 — Punto 6: multiplicidad (Holm).** Resumir la corrección: Holm-Bonferroni sobre la familia de afirmaciones con puerta, con las pruebas indefinidas (`NaN`) fuera de la familia. Declarar la convención de autor (R-30): **la familia es la Parte**, y la familia global se reporta en columna contigua como análisis de sensibilidad declarado, no se esconde.
- **P8 — Punto 7: los tres estados de los datos.** Cerrar con la clasificación por lo que sobrevive en disco — `per_item`, `counts_only`, `missing` — y la regla: una afirmación en `missing` **no se defiende** en el TFM; se re-ejecuta o se retira (cola en `thesis/rerun-backlog.md`).

<!-- caption: Tabla 3.2 — Cuántos pares discordantes en una sola dirección hacen falta para alcanzar alpha = 0,05 bilateral -->

| Pares (n) | Discordantes necesarios | Se puede alcanzar |
|---|---|---|
| 5 | — | **No, con ningún resultado** |
| 6 | 6 (todos) | Solo si es perfecto |
| 12 | 6 | Sí |
| 25 / 26 | 6 | Sí |
| 56 | 6 | Sí |

![Potencia por diseño: discordantes mínimos necesarios frente a observados (en rojo, los diseños que no podían alcanzar significación con ningún resultado)](proof/stats-power.png)

<!-- caption: Figura 3.5 — Diseños pareados por n efectivo; en rojo los que no podían alcanzar alpha con ningún resultado -->

<!-- caption: Código 3.2 — Deflación a n efectivo y McNemar exacto (0 discordantes = NaN, no p=1,0), en grounding/stats.py -->
```python
def deflate_to_effective(k: int, n: int, n_effective: int) -> tuple[int, int]:
    if n_effective >= n or n <= 0:
        return k, n
    n_eff = max(1, int(n_effective))
    return min(n_eff, round(k * n_eff / n)), n_eff

def mcnemar(b: int, c: int, alternative: Alternative = "two-sided") -> float:
    if b < 0 or c < 0:
        raise ValueError("discordant counts must be non-negative")
    n_disc = b + c
    if n_disc == 0:
        return float("nan")   # 0 pares discordantes: no hay prueba, NO p = 1,0
    return float(stats.binomtest(b, n_disc, 0.5, alternative=alternative).pvalue)
```

### El método de desarrollo multiagente, acotado

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Por qué aparece en un TFM de Edge-AI.** Justificar la inclusión y su ubicación (subsección corta aquí, material extenso en el **Anexo B**, borrador en `thesis/02-método-multiagente.md`): no es un TFM sobre desarrollo asistido por IA, pero la práctica totalidad del código, los experimentos y la documentación los produjo una flota de agentes bajo revisión humana, y eso condicionó qué defectos aparecieron y cuáles sobrevivieron meses. Un lector que evalúe las cifras necesita saberlo, igual que necesita saber el modo de potencia.
- **P2 — Se cuenta en las dos direcciones o no se cuenta.** Fijar la regla del apartado: un informe que solo cuente los aciertos del método es publicidad; se reportan los hallazgos **y** los defectos producidos.
- **P3 — Lo que el método encontró y el trabajo en solitario no.** Dar las cifras trazables a *commit*: la auditoría de máquina sobre 76 campañas (3 de 65 en la placa; `2c7f7a3`), cuatro números mal en el `README.md` (la precisión de arrastre de 1024 px 0,849 citada donde la desplegada es la de 768 px 0,830; «hasta 3,0 m/s» como techo cuando 3,0 m/s es exactamente el ajuste que **falló** — 3/3 a 2,5 m/s, 0/2 a 3,0; `cd8cca6`), el fallo de re-emparejamiento de ByteTrack (`px_err` 64,7 → 36,0; `f1e58e9`) y el propio re-análisis estadístico (33 de 65 diseños inalcanzables por diseño). [cita @zhang2022bytetrack].
- **P4 — Lo que el método produjo, con la misma firma.** Reportar los defectos que introdujo el mismo sistema —*confiados, precisos y falsos*—: la cámara de Gazebo apuntando al **cielo** durante semanas (`+pi/2` es abajo, no arriba; RQ-S1.4 retirada; `5426ed0`, regla en `03d37bb`), un `b=39, c=7` en lugar de `b=4, c=2` por adivinar nombres de campos JSON, y tres anclajes por número de línea erróneos escritos el mismo día en el fichero que exige no fiarse de la primera lectura.
- **P5 — Por qué la mitigación que funcionó fue mecánica.** Enunciar la aportación metodológica: **en un flujo multiagente la verificación tiene que ser un artefacto ejecutable, no un párrafo** — la regla «no te fíes de tu primera lectura» estaba escrita, en mayúsculas, en el mismo fichero con tres citas erróneas. Lo que funcionó fue externo al agente: `tests/test_thesis_integrity.py`, el patrón de trinquete, la regla «míralo» y el protocolo de traspaso. [ver Tabla 3.3].
- **P6 — Amenaza a la validez de la propia sección.** Cerrar con la salvedad obligatoria: **no hay grupo de control** — no existe una versión de este TFM hecha por una persona sola con la que comparar — así que ninguna afirmación causal sobre el método («el multiagente mejoró X») es defendible. Solo el registro de incidentes lo es, y cada uno resuelve a un *commit*.

<!-- caption: Tabla 3.3 — La asimetría flota de agentes / persona sola, dicha sin adornos -->

| | Flota de agentes | Persona sola |
|---|---|---|
| Amplitud (auditar 76 campañas) | minutos | días, y no se hace |
| Profundidad en un problema conocido | buena, con coste invisible | buena |
| Autoverificación | **mala**: repite su error con más confianza | mala, pero más lenta y con más dudas |
| Coste de un defecto silencioso | alto: se propaga a la documentación al instante | alto, pero se propaga más despacio |
| Sensibilidad a instrucciones escritas | baja bajo carga | media |
| Sensibilidad a una prueba que falla | **total** | total |

### Qué le hizo el re-análisis al cuaderno

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — El marco cambió resultados, no los adornó.** Anticipar el material del Cap. 9: el marco no se escribió para adornar resultados sino porque **cambió varios**, y por eso conviene presentar aquí el resultado global del re-análisis retroactivo antes de entrar en los capítulos empíricos.
- **P2 — El reparto global en ocho categorías disjuntas.** Presentar la tabla de resultado global [ver Tabla 3.4]: las 76 afirmaciones del registro repartidas en ocho categorías **disjuntas** que suman 76 (cada afirmación aparece exactamente una vez; cuando dos podrían aplicar, gana la más específica). Registrar el negativo de método: esta tabla tenía cuatro filas y sumaba 82 hasta el 2026-07-23, con 29 afirmaciones contadas dos veces, y la corrección (R-23) no suaviza el diagnóstico — **doce diseños con puerta que ningún resultado posible habría superado** es la frase que el capítulo debe llevar.
- **P3 — Cuántas sobreviven a Holm.** Dar la cifra vigente leída de `thesis/stats-report.md`: **sobreviven 11 por Parte frente a 10 en familia global** (la única que solo sobrevive por Parte es `P2-RQ4.1-deploy-fidelity`). [VERIFICAR: el esquema `00-esquema.md` dice todavía «diez que sobreviven» y su tabla marcaba 8; `02-método-multiagente.md` cita el histórico «6 sobre 65» del re-análisis original — usar el vigente 11/10 de `stats-report.md`]. Nombrar las once: `P1-S3.3-export-parity-catastrophe`, `P2-RQ2.1-resolution-ladder-1024`, `P2-RQ3.1-lora-aerial-gate`, `P2-RQ4.1-deploy-fidelity`, `P3-ROI-M2.0-512`, `P3-ROI-M2.0-512-ondevice`, `P3-R13-owlv2-vs-vlm`, `E18-cold-acquire-vs-warm-oracle-n25`, `P5.2a-warm-generalization`, `P5.12-bankv21-recal`, `P6.2-DELIVERY-warm-vs-cold-closedloop`, y declarar que **la contribución central del TFM está entre ellas**. [ver Figura 3.6].
- **P4 — Los dos matices que la lista no puede omitir.** Dar las dos condiciones que acompañan a la lista: `P5.12` sobrevive a Holm pero su propia salvedad la llama *parcialmente definicional* (los suelos se recalibraron a partir de la población de P5.11); y de las supervivientes **solo dos son inferenciales y de la placa a la vez** — `P3-R13-owlv2-vs-vlm` (R-13, p = 2,205e-09) y `P3-ROI-M2.0-512-ondevice` (R-14, p = 6,384e-18) — que es exactamente el flanco que el Cap. 9 declara.
- **P5 — Las tres correcciones que el re-análisis obliga a llevar al texto.** Enumerar las tres, cada una con su salvedad pegada: (1) **Swin2SR no pierde en precisión** — el descarte es por latencia (+1331 ms), no por IoU (cita @conde2022swin2sr); (2) **la catástrofe de la Parte I es la exportación, no la cuantización** — F16 contra Q8_0 da b=17, c=10, p=0,248 (los 7 pp atribuidos al cuantizado no se distinguen del ruido), mientras que HF contra GGUF es significativa bajo cualquier emparejamiento compatible con los marginales (peor caso p = 1,3e-04); (3) **el arrastre a 768 no pierde precisión medible frente a 1024** — por pista 1024 gana 55 y 768 gana 31 (p=0,013), pero sobre las 93 secuencias independientes la prueba de signos da b=28, c=16, **p=0,096** (Holm la deja en 1), luego la adopción de 768 fue una cota de tamaño de efecto más una restricción de FPS, no una afirmación de igualdad (corregido el 2026-07-21, R-7). [ver Figura 3.6].

<!-- caption: Tabla 3.4 — Resultado global del re-análisis retroactivo de las afirmaciones con puerta (recuentos vigentes de thesis/stats-report.md, ocho categorías disjuntas que suman 76) -->

| Categoría | N | Qué significa |
|---|---|---|
| Significativas tras Holm | 11 | Se pueden defender como efectos |
| Probadas, no significativas | 23 | Contraste real que no rechazó |
| Puerta pre-registrada **inalcanzable por diseño** | 10 | Ningún resultado posible habría bastado a esa n |
| Descriptivas, sin hipótesis | 12 | Nunca hubo nada que contrastar, por diseño |
| Sin puerta pre-registrada, sólo intervalo | 12 | Se reporta el Wilson y nada más |
| Pareadas sin un solo par discordante | 3 | Los brazos no se separaron en ninguna celda |
| Sin datos crudos | 3 | En cola de re-ejecución, no se defienden |
| Sólo sobreviven agregados | 2 | Se perdieron los valores por elemento |

![Forest plot de las afirmaciones con puerta y su intervalo de Wilson al 95 %; la barra roja marca la puerta pre-registrada](proof/stats-forest.png)

<!-- caption: Figura 3.6 — Proporciones observadas con intervalo de Wilson al 95 %; la barra roja marca la puerta pre-registrada -->
