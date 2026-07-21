---
title: Grounding visual anticipatorio para seguimiento de objetivos desde UAV en hardware de borde
subtitle: Esquema del TFM y mapa de evidencia
author: Javier Francisco Dibo Gómez
comment: Borrador de estructura, 2026-07-21T12:45Z
locale: es
bibliography: refs.bib
---

## Propósito de este documento

Este no es el TFM. Es el esquema del TFM y, sobre todo, el **mapa entre cada
afirmación que se quiere defender y la evidencia que existe en el repositorio
para sostenerla** — incluidos los casos, que son muchos, en los que esa evidencia
es más débil de lo que sugiere la nota de laboratorio.

Se escribe ahora porque el proyecto tiene el problema contrario al habitual: no
falta material, sobra. Seis partes, más de sesenta experimentos registrados, del
orden de 272.000 palabras de notas. Un TFM admite unas 60-80 páginas. Eso es una
compresión cercana a 10:1, y una compresión de ese factor no se hace escribiendo:
se hace **decidiendo qué se tira**. Este documento toma esas decisiones por
adelantado y las deja auditables.

### El hallazgo que cambia el plan

Al levantar el inventario aparecieron dos problemas que no son de redacción:

- **No había ni una sola prueba estadística en el repositorio.** Una búsqueda de `mcnemar|binomtest|scipy.stats|statsmodels|wilson|p-value` sobre todos los `.py` y `.md` devolvía cero ficheros. El único estadístico existente era un Spearman escrito a mano, sin p-valor ni intervalo. Varias afirmaciones con puerta descansaban sobre una o tres celdas de diferencia. **Resuelto el 2026-07-21**: el marco está en `grounding/stats.py`, se explica en el Cap. 3 (borrador en `thesis/01-metodo-estadistico.md`), y las 65 afirmaciones con puerta re-analizadas están en `thesis/stats-report.md`. El resultado de ese re-análisis está más abajo y **cambia lo que el TFM puede afirmar**.
- **Las Partes I, II y III no tienen ni un solo directorio `proof/`.** La regla de entregables por campaña se introdujo en julio y no se aplicó retroactivamente. El resultado individual más fuerte del proyecto — la palanca ROI, que gana en las dos dimensiones a la vez — **no tiene ninguna figura**: existe solo como un JSON de barrido.

Es decir: el trabajo pendiente antes de redactar no es escribir, es **generar la
evidencia gráfica que falta y calcular los estadísticos que nunca se calcularon**.
Eso está en la Sección "Deuda de evidencia".

### Reglas que se aplican a sí mismo

- Toda cifra citada aquí lleva la máquina en la que se midió. La composición "precisión del 3090 + FPS de la Jetson" en una misma tabla aparece varias veces en el cuaderno y no puede repetirse en el TFM sin decirlo.
- Ninguna figura se planifica sin comprobar si el material existe. Si no existe, se marca **POR GENERAR** y cuesta tiempo, no cero.
- Las advertencias no son opcionales: son las condiciones bajo las cuales las afirmaciones son ciertas. Si una desaparece del texto final, la afirmación correspondiente se vuelve indefendible.
- Se prefiere un resultado negativo bien medido a un resultado positivo mal delimitado.

### Estado

- Bibliografía: `thesis/refs.bib` creada, con las entradas sin verificar marcadas `% VERIFICAR`.
- Esquema: este fichero.
- Texto: no empezado.
- Fecha límite: **sin fijar**. Es la variable que falta y la que ordena todo lo demás.

## Tesis defendida

Una sola frase, porque si no cabe en una frase no está clara:

> Cuando la orden del operador llega a mitad de vuelo y no en el instante cero,
> la ventana previa a la orden es cómputo gratuito; gastarla en mantener
> candidatos vivos y limitarse a **seleccionar** al recibir la orden elimina la
> latencia de adquisición que hace que un sistema de grounding sobre vídeo aéreo
> entregue una caja ya obsoleta.

De ahí salen tres afirmaciones subordinadas, y cada capítulo empírico existe para
sostener una de ellas:

<!-- caption: Las tres afirmaciones subordinadas, el capítulo que sostiene cada una y el límite de esa evidencia -->

| Afirmación | Cap. | Límite de la evidencia |
|---|---|---|
| Un VLM de 2B cuantizado hace grounding referencial útil sobre imagen aérea y cabe en un Orin Nano de 8 GB | 4-5 | Protocolo propio, más fácil que el benchmark publicado |
| La adquisición en frío es el cuello de botella del sistema integrado, y no se arregla optimizando la adquisición | 6 | n = 6 clips, todas coches, sin vehículo en el lazo |
| Anticipar (mantener + seleccionar) sí lo arregla, acotado por la calidad del arrastre | 7 | El único SÍ a n real cae justo en el listón, p = 0,125 |

La Parte VI (Cap. 8) no sostiene ninguna de las tres todavía.

## Estructura propuesta

<!-- caption: Estructura de capítulos, origen del material y extensión estimada -->

| Cap. | Título | Material de origen | Págs. (est.) |
|---|---|---|---|
| 1 | Introducción y motivación | `README.md`, propuestas de parte | 5 |
| 2 | Estado del arte | `SOURCES.md`, surveys, encuesta de datasets | 8 |
| 3 | Plataforma, método y métricas | `README.md`, `grounding/contract.py` | 8 |
| 4 | Grounding de un solo frame | Partes I y II | 10 |
| 5 | Permanencia de objeto | Parte III + E1 | 9 |
| 6 | El arco de la latencia de adquisición | Parte IV (E2-E23) | 10 |
| 7 | Grounding anticipatorio | Parte V (P5.1-P5.20) | 14 |
| 8 | Hacia el lazo cerrado | Parte VI (P6.0-P6.1) | 6 |
| 9 | Amenazas a la validez | transversal | 6 |
| 10 | Conclusiones y trabajo futuro | transversal | 4 |

Total estimado: **80 páginas** de cuerpo. Los agentes que inventariaron cada parte
estiman 17 + 26 + 16 + 17 páginas solo para los capítulos 4 a 7 si se contara todo,
lo que confirma que el problema es de recorte y no de material.

## Capítulo 3 — Plataforma, método y métricas

Capítulo corto pero **necesario antes que los empíricos**, porque tres decisiones
de medida condicionan todas las cifras posteriores y ninguna es obvia.

### El umbral IoU@0,25

Toda la precisión del proyecto se reporta a IoU@0,25. El estándar de la
literatura de comprensión de expresiones referenciales es IoU@0,5. **No existe
justificación registrada en ningún sitio del repositorio** para haber elegido
0,25: `grounding/contract.py` declara la constante y apunta a la puerta, sin
razón. El TFM tiene que justificarlo explícitamente — presumiblemente porque el
objeto aéreo mediano ronda los 16 px y a 0,5 la métrica es inestable — y
reportar el IoU medio al lado, que es mucho más sobrio.

Escribir este capítulo sin resolver esto deja un flanco abierto en la primera
pregunta del tribunal.

### La placa y su techo

- Jetson Orin Nano 8 GB, **15 W + `jetson_clocks`**. El modo de 25 W no existe en esta placa: el firmware expone solo 15 W y 7 W, y desbloquearlo exigiría un flasheo de bootloader que se decidió no intentar. Toda cifra de rendimiento es un techo de 15 W, no un techo de silicio.
- Una etiqueta anterior del cuaderno decía "MAXN\_SUPER" y **era falsa**; se corrigió el 2026-07-03. No debe reaparecer en el TFM.
- La potencia medida es `VDD_IN` de tegrastats: entrada total de placa, incluido un suelo de plataforma en reposo de ~5,2 W. No es potencia de módulo ni de SoC.

### El marco de inferencia

**Sección obligatoria y probablemente la más defendible del capítulo.** Borrador
completo en `thesis/01-metodo-estadistico.md`; aquí va el resumen y allí el
detalle, porque un tribunal preguntará por el método antes que por los números.

Lo que hay que explicar, en este orden:

1. **Qué prueba corresponde a qué diseño**, y que la elección la fija el diseño y nunca el p-valor que sale. Todo exacto: McNemar exacto, binomial exacta, Fisher, Wilcoxon. Ninguna aproximación normal — con estos n, Wald da [0, 0] para un 0/6 y un límite superior mayor que 1 para un 24/25.
2. **`n_effective` frente a `n_rows`.** Seis clips por dos repeticiones deterministas son seis observaciones. Diez ensayos SITL del mismo fallo determinista son uno. 439 captions sobre 316 imágenes no son 439 observaciones independientes. Cada afirmación declara las dos cifras y la razón por la que difieren.
3. **La deflación a n efectivo.** Cuando el denominador cuenta filas y no observaciones independientes, la proporción se conserva y el denominador se sustituye por `n_effective` antes de calcular nada. Es una corrección por efecto de diseño con deff = n / n_effective, deliberadamente tosca: solo ensancha el intervalo y solo debilita el p-valor, luego no puede fabricar un resultado. El caso que la motivó es E17, cuyo 0/10 daba un intervalo [0, 0,28] sobre diez repeticiones de **un** fallo determinista, y ahora da [0, 0,79] sobre n = 1.
4. **Diseños que no podían responder a su pregunta.** Una comparación pareada de cinco elementos no alcanza p < 0,05 aunque los cinco volteen: el suelo es 0,0625. Se calcula desde n **solo**, sin mirar el resultado, que es lo que lo hace legítimo a posteriori.
5. **Empates y pruebas que no existen.** Cero pares discordantes devuelve `NaN`, no p = 1,0.
6. **Multiplicidad**: Holm-Bonferroni sobre la familia de afirmaciones con puerta, con las pruebas indefinidas fuera de la familia.
7. **Los tres niveles de estado de los datos** (`per_item`, `counts_only`, `missing`) y la regla de que una afirmación en `missing` no se defiende: se re-ejecuta o se retira.

### Qué le hizo el re-análisis al cuaderno

Este es el material del Cap. 9 y conviene anticiparlo aquí, porque **el marco no
se escribió para adornar resultados sino porque cambió varios**.

<!-- caption: Resultado global del re-análisis retroactivo de las 65 afirmaciones con puerta -->

| Categoría | N | Qué significa |
|---|---|---|
| Significativas tras Holm | 6 | Se pueden defender como efectos |
| Sin prueba posible (0 discordantes o solo agregados) | 26 | No hubo contraste, en ninguna dirección |
| Diseño incapaz de alcanzar alfa | 33 | Ningún resultado posible habría bastado |
| Sin datos crudos | 3 | En cola de re-ejecución, no se defienden |

Las seis que sobreviven son la catástrofe de fidelidad de la Parte I, la escalera
de resolución y la puerta LoRA de la Parte II, la palanca ROI de la Parte III, la
generalización del arranque en caliente (P5.2a) y la recalibración del banco
(P5.12). **La contribución central del TFM está entre ellas**, que es lo que
hacía falta comprobar.

Y tres correcciones que el re-análisis obliga a llevar al texto:

- **Swin2SR no pierde en precisión** (ver Cap. 5). El descarte es por latencia.
- **La catástrofe de la Parte I es la exportación, no la cuantización.** F16 contra Q8\_0 da b = 17, c = 10, p = 0,25: los 7 pp que el cuaderno atribuye al cuantizado no se distinguen del ruido. La brecha HF contra GGUF, en cambio, es significativa bajo **cualquier** emparejamiento compatible con los marginales (peor caso p = 1,3e-4), que es la forma correcta de defenderla cuando el brazo HF no dejó registro por elemento.
- **El arrastre a 768 sí pierde precisión frente a 1024** (55 pistas contra 31, p = 0,013). La adopción de 768 nunca fue una afirmación de igualdad: era una cota de tamaño de efecto más una restricción de FPS, y hay que redactarla así.

### La topología real del banco

Esto es lo que más se malinterpreta al leer el cuaderno. En casi todas las
partes, **la Jetson ejecutó solo el VLM**, servido por SSH con un PNG en base64
cruzando el cable por llamada; el arrastre con SAM2, el replay de vídeo y el
scoring corrieron en una RTX 3090 de sobremesa. El capítulo debe presentar el
diagrama del banco antes de dar una sola cifra, porque de otro modo el lector
supone un sistema embarcado que nunca se midió como tal.

## Capítulo 4 — Grounding de un solo frame

Cubre Parte I (exploratoria, congelada) y Parte II (reconstrucción principiada).

### Qué se cuenta

La Parte I se cuenta **como fracaso metodológico**, no como resultado. Produjo
una catástrofe de fidelidad: lo medido en el banco no era lo que ocurría en el
dispositivo. La Parte II existe porque esa lección obligó a reconstruir la
evaluación desde cero con fases con puerta y con manifiestos por ejecución (SHA
de git, hash del lockfile, hash del dataset) que la Parte I no tiene.

Sin ese arco, la Parte II parece burocracia. Con él, es la respuesta a un fallo
concreto: "cinco copias divergieron en silencio".

### Cifras que se citan, con su matiz

- Espina dorsal: Qwen2-VL-2B [@wang2024qwen2vl], cuantizado a Q8\_0 con llama.cpp [@llamacpp].
- Fase 3, LoRA [@hu2022lora]: **59,5 %** IoU@0,25 sobre RefDrone [@refdrone] a n = 439. No citar el 65,0 % en bucle (n = 200) como titular.
- Fase 4: 59,5 % (HF) a 62,2 % (F16) a **62,6 %** (Q8\_0 en la Jetson).

### La corrección de signo más importante del documento

El cuaderno etiqueta ese último salto como "-2,7 pp" y lo repite en cuatro
sitios. **Es una convención de magnitud de brecha, no una pérdida.** Las cifras
suben: el artefacto cuantizado puntúa por encima de la referencia HF. La lectura
honesta, que el propio README de la campaña ya recoge, es que una inversión de
~3 pp sobre n = 439 está dentro del ruido de muestreo y significa **"sin pérdida
medible por el runtime"** — nunca "la cuantización mejora el modelo". Escribirlo
como pérdida sería un error; escribirlo como mejora sería peor.

Lo mismo pasa con la brecha original de la Parte I: hay **dos medidas del mismo
fenómeno y no coinciden** (85,0 a 62,0 a 55,0, es decir -23 pp; frente a la
re-medida de la Fase 0b sobre el mismo checkpoint, 85,0 a 69,0 a 67,0, -16 pp).
La diferencia se atribuye a decodificación voraz frente a muestreada y a n = 100
frente a n = 200. El TFM debe dar el par y la explicación, no elegir el número
más dramático.

### Advertencia obligatoria sobre RefDrone

El 62,6 % **no es comparable con la tabla de RefDrone**. El benchmark publicado
mide **F1 multi-objetivo a IoU >= 0,5** (una expresión puede mapear de 0 a 242
cajas); el estado del arte allí es 34,44 F1 y el techo humano 58,14. Lo que aquí
se mide es **una caja, IoU@0,25**, sobre el 30,9 % de las captions de validación
que tienen exactamente una caja real (n = 439 de 1.421). Se descartan
precisamente los casos multi-objetivo y los negativos, que son para lo que
RefDrone fue construido.

Es un protocolo distinto y más fácil. Poner el 62,6 % al lado del 34,44 sin esa
frase sería una tergiversación.

### Licencias

Las anotaciones de RefDrone son CC BY 4.0 pero reutilizan imagen de VisDrone2019-DET
bajo CC BY-NC-SA 3.0, de uso académico. Vale para un TFM y **hay que declararlo**:
la etiqueta permisiva de aguas abajo no anula la cadena de aguas arriba.

### Figuras

Ninguna existe. **Todas por generar** desde `runs/*/results.json`.

- POR GENERAR: barras banco-vs-dispositivo con las dos medidas discrepantes de la brecha de la Parte I, que es la figura que justifica la existencia de la Parte II.
- POR GENERAR: rejilla cualitativa de aciertos y fallos de grounding sobre imagen aérea.
- POR GENERAR: bake-off de backbone [@opengvlab2025internvl3; @qwen2025qwen25vl; @google2024paligemma2; @microsoft2024florence2; @hf2025smolvlm2]. Cuidado: los brazos **no comparten backend ni n** (A y C en HF a n = 200; el titular y B en Jetson Q8\_0 a n = 439; D cancelado sin ejecutar). Sostiene "ningún brazo desplazó al titular", no una clasificación.

## Capítulo 5 — Permanencia de objeto

Parte III (T0-T4) más la exportación E1.

### Qué se cuenta

Un grounding por frame no es seguimiento. Aquí entra el arrastre temporal: SAM2
[@ravi2024sam2] mantiene la máscara entre anclajes y el VLM solo se invoca para
re-anclar.

### La palanca ROI, dicha con precisión

Es el mejor resultado del proyecto y el más fácil de exagerar.

- **Precisión:** 85,2 % IoU@0,25 — medido con pesos **HF bf16 en la RTX 3090**, no en la Jetson y no a Q8\_0. La confirmación en dispositivo estaba pre-registrada como "el único pendiente antes de cambiar el valor por defecto" y **nunca se cerró**.
- **Delta:** el "+22,6 pp" compara 85,2 % (HF bf16, 3090) contra 62,6 % (Jetson Q8\_0, y además contra un checkpoint ya sustituido). El control mismo-backend medido en el mismo barrido es el brazo HF a frame completo, 64,0 %, lo que da un delta comparable de **+21,2 pp**. Ese es el número defendible.
- **Latencia:** 2,7x de prefill (3691 ms a 1374 ms) frente a frame completo a 1024. La mitad de latencia sí es una medida Jetson Q8\_0.
- **Cadencia:** el anclaje a ~2,0 s no es una mejora de 3x. Frente a la constante original de frame completo a 512 (2,26 s) es marginal, porque un recorte de 512x512 lleva píxeles parecidos. La mejora real es contra la ruta desplegada a 1024: **4,81 s a 2,02 s, 2,4x**, extremo a extremo.

Y la referencia desplegada ya no es 62,6 %: el checkpoint terse mide **63,1 %** a
frame completo en la Jetson. Cualquier "+22,6 pp sobre el modelo desplegado" es
contra un modelo que ya no se despliega.

### Cifras de arrastre y de exportación

- Precisión del arrastre: 0,849 a `image_size` 1024 y 0,830 a 768, sobre 186 pistas de AerialMind — **en la 3090**. En la Jetson solo se midieron FPS y RAM. Sembrado además desde una caja de verdad-terreno del primer frame: siembra oráculo, no lenguaje.
- E1, encoder de SAM2 a TensorRT fp16 [@tensorrt]: **4,89 a 6,15 FPS en banco solo**. En el bucle integrado el mismo encoder da **5,0 FPS**, con n = 1, y despeja la puerta de >= 5 **exactamente**. El bucle pierde ~1,15 FPS en codificar/decodificar JPEG y en el túnel SSH.
- Antes de E1 la tasa co-residente era **4,1 FPS frente a la puerta de 5**: un fallo marginal registrado como tal.

### Dos formulaciones que hay que evitar

- **"Se rechazó EdgeTAM frente a SAM2"** es falso. EdgeTAM era una alternativa condicional pre-registrada a la que nunca se llegó, porque SAM2 + TensorRT despejó la puerta en el paso anterior. Nunca se midió, en ningún hardware. Se escribe "no hizo falta el plan B", jamás "ganó la comparación".
- **"7,6 Hz de tasa del sistema"** está inflado por fases ciegas. La tasa del sistema es la de la fase de arrastre.

### La palanca de super-resolución, descartada

Swin2SR [@conde2022swin2sr] sobre el recorte ROI **no compra nada medible** por
+1331 ms. Y aquí el re-análisis **corrige la nota de laboratorio**: la campaña lo
registró como "pierde también en IoU", pero sobre los datos por elemento
(n = 429) ningún brazo se separa de otro. Frente a LANCZOS, b = 21 y c = 14,
**p = 0,31**; frente a bicúbico, b = 22 y c = 12, **p = 0,12**; y el propio
bicúbico contra el nativo da p = 0,26. El descarte es correcto y se sostiene
**por latencia**, que es determinista y enorme; escribir que Swin2SR "pierde en
precisión" sería afirmar más de lo que hay. Con dos matices más: la prueba usó un recorte oráculo
de 400x400 centrado en la verdad-terreno (mide el techo que la SR podría ofrecer,
no el extremo a extremo) y n = 429, habiendo descartado 10 muestras por una razón
no aleatoria — los objetos más grandes no caben en 400 px. La literatura de SR en
teledetección [@survey2025rssr; @xiao2023ediffsr] no transfiere a este recorte.

### Figuras

Parte III tampoco tiene `proof/`. Existen dos GIF sueltos (`permanence.gif`,
`closedloop.gif`) y tres clips del demo, todos versionados y reutilizables.

- POR GENERAR y **prioritaria**: la rejilla ROI (M x resolución de salida) con los dos ejes, precisión y prefill. Es el mejor resultado del proyecto y hoy no tiene imagen.
- Reutilizable: `experiments/2026-06-24-t2-permanence/permanence.gif` y `.../t3-closed-loop/closedloop.gif`.

## Capítulo 6 — El arco de la latencia de adquisición

Parte IV, E2 a E23. **El capítulo pivote.**

### Qué se cuenta

Con el sistema integrado sobre vídeo real de UAV123 [@mueller2016uav123] aparece
un fallo que ningún experimento por componentes veía: la adquisición en frío
tarda ~4,85 s y sobre un objetivo en movimiento **la caja se entrega obsoleta**.
El sistema no falla al encontrar el objeto; falla al encontrarlo donde ya no está.

Luego se cuentan los intentos de arreglarlo por la vía directa:

- **E20**, pista de recorte tomada de la frase del operador: 1,85 s, la única adquisición sub-2 s que funciona. Voltea 3 de 6.
- **E21** (segunda pasada del VLM), **E22** (prior en CPU) y **E23** (celda más ancha): los tres fallan al automatizar la pista.

### La inferencia que arrastra el resto del documento

Cuatro intentos independientes, tres fracasos y un éxito que **no es autónomo**.
La conclusión no es "hay que optimizar más", es que el problema está mal
planteado: si la orden llega en t y la respuesta en t + 4,85, ninguna
optimización sobrevive a un objetivo que se mueve. Hay que cambiar **cuándo
empieza** el cómputo, no cuánto dura.

Eso es la Parte V.

### Advertencias que acompañan a cada cifra de este capítulo

- Los ~4,85 s **incluyen cable**: se midieron con un PNG sin pérdidas en base64 cruzando un túnel SSH desde la estación de trabajo hasta la Jetson, sobrecarga que un despliegue con cámara a bordo no pagaría. El instrumento `transfer_ms` construido para exactamente esta pregunta nunca se ejecutó sobre la cifra titular de E18. Quedan además ~450 ms sin atribuir entre el `t_lock` de 4,85 s y la mediana instrumentada de 4400 ms.
- El arco completo E18-E23 es **n = 6 clips, todas coches, de un solo dataset**, con captions congeladas escritas a mano, n = 2 repeticiones por celda, **solo percepción** — sin actuación ni vehículo en el lazo — y con el arrastre en la 3090 limitado a 6,15 Hz como sustituto del Orin. Los veredictos son 1/6, 2/6 y 3/6: diferencias de una sola clip, sin prueba estadística posible.
- E20 **no es autónomo**: exige que el operador dé una frase espacial correcta, y una pista **equivocada es peor que ninguna** (cobertura 0,000, plantilla de máscara envenenada, cero recuperación). El encuadre honesto es "un rodeo con humano en el lazo que resistió tres intentos de automatización", no "una solución".
- El techo de seguimiento de 2,5 m/s (3,0 con chase-hold) se midió en SITL contra un **renderizador nadir sintético** — una textura plana con un rover dibujado a 640x480 — no sobre imagen real, con n = 2 o 3 por peldaño. El propio repositorio contiene la refutación: E11 dio PASS a 3,5 m/s con 2/2 y **E12 lo revirtió** a n = 3.
- **E14 no replica.** Su "3/3, agujero de identidad cerrado" se convierte en **6/8, CUALIFICADO y explícitamente no fiable** en la replicación E16. El matiz atenuante, que merece decirse: 0 de 8 violaron la identidad, luego los dos fallos son de temporización aguas arriba de la puerta, no de la puerta.
- Los números de estrés de E15 están **registrados pero no reclamados**: falló su guarda de línea base, así que el veredicto es NO MEDIBLE.

### Figuras

Casi todo son clips `.mp4`, que es lo correcto cuando el comportamiento es el
argumento. Solo hay dos figuras (E22 y E23).

- Reutilizable, **la figura titular de la Parte IV**: `experiments/2026-07-03-real-video-replay/proof/car9_A_vs_B.mp4`, la adquisición real contra su control.
- Reutilizable, **la prueba de fragilidad de E20**: `.../2026-07-04-prompt-scoped-acquire/proof/wrong_car10_r1_wrongprobe.mp4`, donde una pista errónea hace que el VLM alucine.
- POR GENERAR: no existe ninguna figura cuantitativa del arco de latencias (4,85 a 1,85 a 2,73 a 2,80 s) ni de la escalera de velocidades. Hay que hacerlas.

## Capítulo 7 — Grounding anticipatorio

Parte V, P5.1 a P5.20. El capítulo más largo y el que contiene la contribución.

### Estructura interna propuesta

No se narran veinte experimentos en orden. Se narran cuatro hilos:

- **El arranque en caliente funciona.** P5.1 (5/6 frente a 1/6 en frío) y P5.2 (21/25 frente a 5/25 sobre 25 clips y 5 categorías).
- **Seleccionar entre candidatos es donde duele.** P5.3, P5.4, P5.5, P5.10, P5.13 y P5.17: seis intentos sin separación o sin robustez, agrupados por causa y no por número.
- **Lo que sí lo desbloqueó.** P5.14 cambia el **contrato de entrega** — entregar la pista ya arrastrada en lugar de re-anclar al recibir la orden. P5.16 quita el oráculo de la semilla y cuesta una celda de doce.
- **Dónde está el límite.** P5.15 (el arrastre aguanta 24 s de espera, 24/25: **el arrastre no es la parte frágil**), P5.18 (a n = 26 el SWAP reforzado cae a 17/26), P5.19 (sube a 20/26) y P5.20 (un SAM2 mayor no recupera ninguna celda: palanca muerta).

### El estadístico, ya calculado

Cifras generadas por `thesis/run_stats.py` desde `thesis/claims.json`, no
estimadas. McNemar **exacto bilateral**, que es el que se reporta en todo el
documento; el unilateral es la mitad y no se usa para decidir nada.

<!-- caption: Inferencia post-hoc sobre los resultados con puerta de la Parte V, generada desde los volcados por elemento -->

| Resultado | Discordancia | McNemar exacto | Lectura |
|---|---|---|---|
| P5.1 WARM 5/6 vs COLD 1/6 | b = 4, c = 0 | p = 0,125 | No significativo por sí solo |
| P5.2a WARM 21/25 vs COLD 5/25 | b = 16, c = 0 | **p = 3,05e-5** | **El ancla estadística de la parte**; sobrevive a Holm |
| P5.10 DD 24/24 vs RG 24/24 | b = 0, c = 0 | **indefinido** | No hubo prueba, no hubo empate demostrado |
| P5.13 y P5.17 | b = 1, c = 0 | p = 1,0 | No informativo en ninguna dirección |
| P5.19 SWAP 20/26 vs P5.18 17/26 | b = 3, c = 0 | p = 0,25 | Compatible con el azar |

La fila de P5.10 estaba mal agrupada en el borrador anterior de este esquema, y
la distinción importa: P5.13 y P5.17 **corrieron** una prueba que no separó nada,
mientras que P5.10, con cero pares discordantes, **no corrió ninguna**. Reportar
p = 1,0 allí habría sido afirmar equivalencia demostrada.

De aquí salen dos consecuencias narrativas:

- **P5.1 no puede ser el titular.** Es defendible solo porque P5.2 lo replica a n = 25 y cinco categorías. El titular es P5.2.
- **Los tres empates de simulación no demuestran equivalencia.** Con una sola celda discordante, McNemar da p = 0,5, que es literalmente ninguna información. La afirmación correcta es "este banco no pudo discriminar los contratos", que es lo que dice el repositorio.

### Advertencia obligatoria sobre P5.19

P5.19 pasa su listón **exactamente**, 20/26 contra un listón de 20. Con tres
pares discordantes en una sola dirección, McNemar exacto bilateral da **p = 0,25**,
y el intervalo de Wilson al 95 % es [0,579, 0,890], que **cruza el listón de
0,769**. La mejora es compatible con el azar al tamaño de muestra usado: harían
falta **seis** pares discordantes en la misma dirección para alcanzar alfa a
n = 26, y hubo tres.

Se presenta como una señal a replicar, no como significativa. Y se argumenta
**por replicación, no por p**: que P5.20 reprodujera P5.19 celda por celda, sin
un solo cambio, es mejor evidencia de que el efecto es real que cualquier
contraste a este n.

Además, la precisión de la entrega con gracia es **2/4**, y cuando falla
**entrega una caja ajustada y confiada sobre el objeto equivocado** (IoU 0,679 y
0,865) en vez de abstenerse. En despliegue no hay verdad-terreno que lo detecte:
es un fallo silencioso, y es el peor modo posible para algo que pilota. Falsificó
además su propia predicción de "suelo de regresión ~0".

### Matices que viajan con los números

- **`acquire_s` = 0,00 s del contrato de entrega directa es definicional, no medido.** No hay paso de adquisición que cronometrar. Es válido como enunciado del contrato, pero decir "hicimos la adquisición 4,5 s más rápida" sin añadir que el coste se trasladó a la tubería que corre continuamente durante la espera es engañoso.
- **De las cuatro pérdidas de P5.2, dos son degeneradas**: el objetivo no está en el frame de entrega, así que el oráculo también falla. El repositorio reporta correctamente 21/23 = 91 % sobre el conjunto no degenerado, y ese calificador debe viajar con la cifra.
- **El rho = -0,06 del barrido de velocidad no tiene p-valor ni intervalo.** Sostiene "no se observa dependencia de la velocidad", no "es plano".
- **P5.16 no es un resultado vigente.** Su 4/5 fue derribado por P5.18 con el mismo arnés byte a byte: la tasa real es 17/26 = 0,65. Se presenta como un paso cuyos números no sobrevivieron.
- **El arrastre nunca corrió en la Jetson en toda la Parte V.** El presupuesto de 6,15 Hz es además el banco solo de E1; el integrado da 5,0 Hz, luego el limitador es ~23 % optimista respecto al sistema desplegado.

### El desvío de simulación

P5.7 a P5.13 y P5.17 construyen un banco de escenas sintéticas en Gazebo
[@gazebo2024harmonic] para conseguir los cruces y oclusiones que UAV123 no da.
Terminan en un **no**: el VLM ancla 56 de 56 renders limpios, los contratos
empatan siempre y el banco no discrimina.

La conclusión útil es metodológica: la ventaja del contrato bueno vive en la
**fragilidad ante imagen real**, y un render limpio la borra. Dos páginas, no
diez. Merece mención el defecto que P5.13 encontró mirando: el coche blanco era
el más cercano en 0 de 300 frames de todas las clips — orden de profundidad
constante, y ninguna puerta lo cubría.

### Figuras

Es la parte mejor documentada: `proof/` existe en todas las campañas.

- Reutilizable: `.../warm-start-generalization/proof/generalization_grid.png` (P5.2a, el titular) y `gap_vs_speed.png` (P5.2b, la figura que refuta la explicación intuitiva del propio resultado).
- Reutilizable: `.../warm-start-acquire/proof/car10_warm_vs_cold.mp4`, el clip de la caja obsoleta a 135 frames.
- Reutilizable: `.../select-generalization/proof/car7_460_SWAP_MC_driftNOMATCH.mp4`, la deriva de arrastre que es el bloqueo residual.
- POR GENERAR: la trayectoria de la afirmación de selección de P5.14 a P5.20 **con intervalos de Wilson**, que es la figura que obliga a poner P5.18.

## Capítulo 8 — Hacia el lazo cerrado

Parte VI, P6.0 y P6.1. Corto y **honesto sobre lo que aún no demuestra**.

### Qué se cuenta

Todas las cifras de la Parte V se midieron sobre vídeo grabado que el sistema no
podía influir. No había vehículo en el lazo. La Parte VI pone la selección
delante de un copter volando — ArduCopter SITL [@ardupilot] como física, CARLA
0.9.16 [@dosovitskiy2017carla] como renderizador esclavo de pose — para que los
píxeles pasen a ser consecuencia de la propia salida de control. Es la etapa SIL
del marco de [@jiang2025dronepipeline].

- **P6.0**, puerta de capacidad: PASS. Encontró un fallo de re-emparejamiento en ByteTrack [@zhang2022bytetrack] que convertía el "coasting de Kalman" en un mantenedor de orden cero y hacía **vacua** la cifra de "0 pérdidas de pista". Error de píxel 64,7 a 36,0.
- **P6.1**, cambio de renderizador: YES. 48,1 Hz con 40 vehículos autónomos siguiendo un vuelo GUIDED real (0 a 84,4 m a 60 m sobre el terreno), con la pila de control intacta.
- **Banco GT de CARLA** (2026-07-21): 25 clips, 30.000 frames con verdad-terreno por actor proyectada, puertas G-A PASS / G-B CERRADA / G-C PASS.

### Tres cifras de este capítulo que NO deben citarse

Es el capítulo con más métricas vacuas del proyecto, y todas lo son por la misma
razón: miden un número contra sí mismo.

- **`slave_err` = 0,000 m.** La cámara libre de CARLA es un actor cinemático, luego `get_transform()` devuelve exactamente lo que `set_transform()` le acaba de pasar. Se conservó en el `results.json` y se excluyó deliberadamente de la figura para que nadie la confunda con evidencia. Lo que sí evidencia el esclavizado es que la **fuente** de pose recorrió 84,4 m bajo control del autopiloto.
- **"0 pérdidas de pista" antes del arreglo de P6.0.** Una pista nunca moría: se sustituía continuamente por un ID nuevo. El par antes/después debe presentarse junto o el lector lee el 100 % previo como salud.
- **Los 48,1 Hz como tasa disponible para trabajo real.** Se midieron a 640x480, 40 vehículos, sin proyección de verdad-terreno ni escritura JPEG y **sin límite de potencia**. El banco GT, en el mismo servidor y mapa pero con 80 vehículos, proyección por actor, escritura JPEG y la GPU limitada a 200 W, sostiene **15,88 Hz**. No son comparables.

### Síncrono contra asíncrono: la distinción que hay que declarar siempre

El banco GT corre en modo **síncrono** y el banco de vuelo en **asíncrono**.
Coexisten por decisión deliberada y **cada resultado debe nombrar cuál lo
produjo**, porque en modo síncrono una adquisición de 4,5 s cuesta **cero
segundos de simulación**: el retardo de entrega que las Partes IV y V existen
para medir sencillamente deja de existir. Mezclar ambos conjuntos de cifras
invalidaría justamente lo que el TFM defiende.

Corolario: el banco GT es determinista, pero **la Parte VI de vuelo pierde el
determinismo** que toda la Parte V tenía. SITL corre en tiempo real y no se puede
avanzar frame a frame, así que los ensayos de vuelo son estocásticos; la
mitigación es estadística (semilla de escena + n >= 25 + reportar la banda de
ruido de planificación), no exacta.

### Lo que este capítulo NO afirma

- **P6.2 no se ha ejecutado.** La Parte VI ha producido una puerta de capacidad, un cambio de renderizador y un banco instrumentado: infraestructura habilitante, no la afirmación. Sus tres premisas — que el arrastre sobrevive a la ego-motion que el propio sistema induce, que el presupuesto de latencia sobrevive al reloj de pared, y que el contrato de selección es entregable a un controlador — siguen **sin falsar, porque ningún experimento ha podido falsarlas todavía**.
- **G6 no se ha ejecutado**, luego el renderizador CARLA **no está validado para la etapa de grounding**. Su predicción (peor que los 56/56 de Gazebo, mejor que UAV123) está sin probar.
- **Ninguna campaña de la Parte VI tuvo la Jetson en el lazo.** Las detecciones de P6.0 se inyectan geométricamente; el servidor de CARLA exige una GPU de sobremesa y no corre en el Orin. Ninguna cifra de la Parte VI es una cifra de despliegue.
- **Ninguna taxonomía de identidad o de deriva salida de este banco es fiable todavía.** El emparejador de actores de `runners/carla_debug_ui.py` tiene seis modos de fallo silencioso verificados, entre ellos una superposición normalizada por la caja menor que da 1,0 a una máscara sobre un retrovisor.
- **Las tres "regiones" de `track_gain`** que una nota anterior de la campaña describía están **retiradas** a n = 25: solo la ganancia 1,0 es un régimen limpio, y las otras dos se solapan.
- **CARLA no es comparable con el banco de Gazebo** de la Parte V. Los 56/56 de P5.17 son un contraste, no una línea base. Fue un coste aceptado y registrado del cambio.
- **Ni tiempo atmosférico ni hora del día** se ejercitaron: todos los frames son mediodía despejado, y la cámara es **nadir fija**, mientras que el vídeo real de UAV y el banco de la Parte V son **oblicuos**. Una afirmación de fidelidad que solo vale al mediodía y desde arriba es una afirmación estrecha.

### Dos limitaciones del artefacto, para quien lo reutilice

- Los identificadores de actor del `gt.jsonl` los asigna el servidor y **CARLA no los reproduce entre cargas de mundo**. Valen dentro de una clip y no pueden usarse para emparejar identidades entre ejecuciones, que es exactamente lo que querría un A/B pareado sobre la misma semilla. La clave estable por índice de spawn exige una recaptura de 36,5 min y no se ha añadido.
- Sobreviven **19 cajas degeneradas de anchura cero** en 897.864 (2,1e-05), lascas de borde de frame serializadas a dos decimales. Un consumidor que calcule IoU divide por cero. El arreglo de serialización llegó después de la captura y el banco no se recapturó: hay que filtrarlas.

### Dos fallos que merecen media página cada uno

Son aportación metodológica, no anécdota:

- **La cámara apuntaba al cielo.** Un pitch de `+pi/2` en Gazebo es **abajo**, no arriba. Durante toda una fase el log salía limpio, se escribían ficheros bien formados, y la conclusión asociada (RQ-S1.4) hubo que **retirarla**: se había medido a través de una imagen gris plana, 100 % de un solo color. Es el caso concreto que motivó la regla de verificación visual del proyecto. En trabajo de simulación, **un `exit 0` no es evidencia sobre píxeles**.
- **La métrica vacua.** El fallo de ByteTrack producía "0 pérdidas de pista" precisamente porque las pistas perdidas nunca se re-emparejaban. Una métrica puede ser perfecta por estar rota.

## Capítulo 9 — Amenazas a la validez

Capítulo propio, no notas al pie. Estas son las que un tribunal encontraría.

### "Todo corre en la placa" no es lo que se midió

El eslogan del proyecto dice que todo corre en el borde sin nube. La realidad:
**el arrastre con SAM2 nunca se ejecutó en la Jetson en la Parte V**, y en las
partes anteriores la precisión del arrastre se midió siempre en la 3090 mientras
la placa aportaba solo FPS. La única medida co-residente integrada dio 4,1 FPS
frente a su propia puerta de 5 antes de E1, y 5,0 FPS después — despejándola
exactamente, con n = 1. La formulación del `README.md` es más fuerte que la
evidencia y se corrige aquí (líneas 3, 47, 48 y 50).

La Parte VI **agrava** esto en lugar de resolverlo: ninguna de sus campañas tuvo
la Jetson en el lazo, porque el servidor de CARLA exige una GPU de sobremesa. El
arco de lazo cerrado se mide íntegramente en la 3090.

### Composiciones entre máquinas

Varias tablas del cuaderno emparejan una precisión medida en la 3090 con unos FPS
medidos en el Orin. Cada una de esas filas describe un sistema que nunca existió.
El TFM debe etiquetar la máquina en cada celda o separar las tablas.

### Tamaños de muestra e inferencia

Buena parte de las decisiones se tomaron con n de 2 a 6. El re-análisis del
2026-07-21 cuantifica el daño: de 65 afirmaciones con puerta, **33 salen de
diseños que no podían alcanzar alfa = 0,05 con ningún resultado posible** y solo
**6 sobreviven a la corrección de Holm**. P5.18 ya lo había demostrado
empíricamente: un 4/5 se convirtió en 17/26 al medirlo bien. E12 revirtió a E11
por la misma razón.
El proyecto adoptó después una regla de n >= 25 para todo brazo con puerta, que
**post-data a las Partes I a IV completas**. Los resultados anteriores se
presentan con su n visible y, donde importe, con su intervalo de Wilson.

La regla admite además una excepción declarada: P6.0 y P6.1 son puertas de
capacidad con **n = 1** — dos vuelos únicos — y la exención se tomó a propósito,
porque una puerta de capacidad pregunta "existe la carretera", no "cuánto se
tarda". P6.0 tampoco se pre-registró. Sirven para desbloquear P6.2 y **no
soportan ninguna afirmación de rendimiento**.

### El sim no es el mundo

Un PASS sobre render de Gazebo o CARLA no sostiene una afirmación sobre imagen
real, y la Parte V lo demostró por la vía dura: el VLM acierta el 100 % de los
renders limpios y de ahí no sale ninguna discriminación. El techo de seguimiento
de la Parte IV se midió además contra una textura plana con un rover dibujado.

### Resultados retirados

Los números de seguimiento en lazo cerrado de la Fase C de la Parte I están
**retirados** (2026-07-20): se midieron a través de una cámara que apuntaba al
cielo. Si el TFM los menciona es como caso de fallo metodológico, con las cifras
tachadas y RQ-S1.4 declarada sin responder.

Retirada también la nota de la campaña del banco GT que describía **tres
regímenes distintos de `track_gain`**: a n = 25 solo la ganancia 1,0 es un
régimen limpio y los otros dos se solapan. `track_gain` no es un factor válido y
no debe aparecer como eje de ninguna figura.

### Irreproducibilidad de los pesos

El directorio de entrenamiento HF/safetensors fusionado se perdió y no sobrevive
ningún adaptador LoRA. Los GGUF desplegados **no se pueden re-exportar**: un
reentrenamiento daría un modelo distinto y rompería la comparabilidad celda a
celda de las Partes II a V. Existe copia verificada por sha256 en
`/home/gara/grounding-checkpoint-backup/`, pero es una copia en la misma máquina.
Además, las ejecuciones de la Parte I **no llevan manifiesto** (SHA de git, hash
del lockfile, hash del dataset), porque preceden a ese aparato: su garantía de
reproducibilidad es estrictamente más débil, y arreglar eso fue un objetivo
declarado de la Parte II.

## Capítulo 10 — Conclusiones

- La contribución es el **replanteamiento**, no una arquitectura: cuando la orden es asíncrona, el instante en que empieza el cómputo importa más que su duración.
- Está acotada: se sostiene sobre cinco categorías de UAV123 con p ~ 1,5e-5 en el resultado de generalización, y el refinamiento de selección queda en una señal a replicar. El bloqueo residual es la deriva del arrastre entre objetos de la misma clase, no el grounding ni la entrega.
- Y está pendiente de la prueba que importa: nada se ha medido todavía con el vehículo cerrando su propio lazo.

## Deuda de evidencia

Trabajo que hay que hacer **antes** de redactar, ordenado por lo que bloquea a
más capítulos. No es redacción; es generar evidencia que no existe.

<!-- caption: Deuda de evidencia previa a la redacción, con el capítulo que bloquea cada partida -->

| Partida | Bloquea | Esfuerzo |
|---|---|---|
| ~~Calcular McNemar exacto y Wilson para todo brazo con puerta~~ | Cap. 3, 6, 7, 9 | **HECHO** 2026-07-21: `grounding/stats.py`, `thesis/claims.json`, `thesis/stats-report.md`, dos figuras |
| Re-ejecutar las 3 afirmaciones sin datos crudos (T2, T3, Fase C) | Cap. 5, 9 | Ver `thesis/rerun-backlog.md` |
| Generar la figura de la rejilla ROI desde `sweep_summary.json` | Cap. 5 | Bajo, y es el mejor resultado sin imagen |
| Generar las figuras de las Partes I-II (brecha de fidelidad, bake-off) | Cap. 4 | Medio — no hay `proof/`, hay que reconstruir de logs |
| Generar la figura cuantitativa del arco de adquisición | Cap. 6 | Medio |
| Justificar por escrito el umbral IoU@0,25 y reportar el IoU medio | Cap. 3, y todo lo demás | Bajo, pero es un flanco abierto |
| Verificar las entradas `% VERIFICAR` de `refs.bib` | Bibliografía | Bajo |
| Corregir el `README.md` raíz (líneas 3, 47, 48, 50): "todo en la placa" y la puerta de FPS | Cap. 9 | Bajo |
| Decidir si se cierra la confirmación en dispositivo del ROI a Q8\_0 | Cap. 5 | Alto — es una ejecución, no una figura |

Todo lo marcado como bajo desbloquea la mitad del documento y no exige GPU. La
última partida es la única que obliga a volver a ejecutar algo, y es opcional: se
puede escribir el Cap. 5 declarando el pendiente en lugar de cerrándolo.

## Orden de recorte

Si el documento no cabe, se recorta en este orden y no en otro:

- El desvío de simulación baja de 2 páginas a un párrafo.
- La Parte I baja a media página de contexto.
- El bake-off de backbone pasa a apéndice.
- Las palancas descartadas del Cap. 5 pasan a una tabla única.

**No se recorta:** el Cap. 6 completo, la advertencia de P5.19, la corrección de
signo del Cap. 4, ni ninguna amenaza del Cap. 9. Recortar una amenaza convierte
una afirmación honesta en una afirmación falsa.

## Siguientes pasos

- Fijar fecha de entrega. Es la única variable que falta y ordena el resto.
- Atacar las partidas baratas de la deuda de evidencia, empezando por el script de estadística, que toca tres capítulos.
- Empezar a redactar por el Cap. 6, que es el pivote y fija el tono de los demás.
