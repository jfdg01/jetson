---
title: Resultados estadísticos retroactivos
subtitle: Cada afirmación con puerta de las Partes I-VI, re-analizada
author: Javier Francisco Dibo Gómez
comment: Generado por thesis/run_stats.py, 2026-07-21T17:48Z
locale: es
---

## Cómo leer esta tabla

Generada por `thesis/run_stats.py` desde `thesis/claims.json`. No se edita
a mano. El método y las reglas de rechazo están en
`thesis/01-metodo-estadistico.md`.

`p` indefinido no significa 'sin efecto': significa que no hubo prueba,
casi siempre por 0 pares discordantes. `alcanzable = no` significa que el
diseño no podía llegar a alpha = 0,05 con ningún resultado posible.

<!-- caption: Re-análisis exacto de las afirmaciones con puerta, con corrección de Holm-Bonferroni -->

| Afirmación | Parte | Diseño | n efectivo | Prueba | p | p (Holm) | Alcanzable | Lectura |
|---|---|---|---|---|---|---|---|---|
| P1-S1.2-zeroshot-smolvlm | I | binario de un brazo | 47 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo [deflactado desde 0/50: ver independence_note] |
| P1-S2.1-stage2-mode-collapse | I | binario de un brazo | 200 | binomial exacta | 1 | 1 | sí | 2/200 contra puerta 0.30; hacían falta >=72/200 para alpha=0,05 |
| P1-S3.3-export-parity-catastrophe | I | binario pareado | 100 | McNemar exacta | 0.0001345 | 0.003766 | sí | significativa (b=45, c=15) |
| P1-S3.3-quantisation-is-not-the-cost | I | binario pareado | 100 | McNemar exacta | 0.2478 | 1 | sí | no significativa (b=17, c=10); hacían falta >=6 discordantes en una dirección, hubo 17 |
| P1-S3.4-coco-to-aerial-domain-shift | I | binario de un brazo | 47 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo [deflactado desde 1/50: ver independence_note] |
| P1-S4.1-stage4-narrow-miss | I | binario de un brazo | 200 | binomial exacta | 0.5981 | 1 | sí | 39/200 contra puerta 0.20; hacían falta >=50/200 para alpha=0,05 |
| P1-S1.3-phaseB-control-stack | I | binario de un brazo | 1 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo [deflactado desde 3/3: ver independence_note] |
| P1-S1.4-phaseC-vlm-closed-loop | I | binario pareado | 0 | ninguna | indefinido | — | **no** | SIN DATOS - no se defiende; en cola de re-ejecución |
| P2-RQ0.3-spine-selection | II | binario de un brazo | 100 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo |
| P2-RQ1.1-dataset-well-posedness | II | descriptivo | 1421 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| P2-RQ2.1-resolution-ladder-1024 | II | binario de un brazo | 316 | binomial exacta | 7.771e-06 | 0.0002331 | sí | 133/439 contra puerta 0.20; hacían falta >=76/316 para alpha=0,05 [deflactado desde 133/439: ver independence_note] |
| P2-RQ3.1-lora-aerial-gate | II | binario de un brazo | 316 | binomial exacta | 3.679e-53 | 1.177e-51 | sí | 261/439 contra puerta 0.20; hacían falta >=76/316 para alpha=0,05 [deflactado desde 261/439: ver independence_note] |
| P2-RQ4.1-deploy-fidelity | II | binario de un brazo | 316 | binomial exacta | 0.0355 | 0.8874 | sí | 275/439 contra puerta 0.57; hacían falta >=197/316 para alpha=0,05 [deflactado desde 275/439: ver independence_note] |
| P3-wholeframe-resolution-knee | III | descriptivo | 316 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis [deflactado desde 277/439] |
| P3-ROI-M2.0-512 | III | binario de un brazo | 316 | binomial exacta | 7.235e-19 | 2.243e-17 | sí | 374/439 contra puerta 0.63; hacían falta >=213/316 para alpha=0,05 [deflactado desde 374/439: ver independence_note] |
| P3-ROI-drift-robustness | III | descriptivo | 316 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis [deflactado desde 326/439] |
| P3-SR-swin2sr-accuracy | III | binario pareado | 312 | McNemar exacta | 0.4244 | 1 | sí | no significativa (b=15, c=10); hacían falta >=6 discordantes en una dirección, hubo 15 [deflactado desde b=21, c=14] |
| P3-carry-OP768-accuracy | III | binario pareado | 93 | McNemar exacta | 0.09614 | 1 | sí | no significativa (b=28, c=16); hacían falta >=6 discordantes en una dirección, hubo 28 [deflactado desde b=55, c=31] |
| P3-E1-TRT-fps | III | descriptivo | 1 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| P3-E1-TRT-mask-parity | III | descriptivo | 1 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| P3-T1-memoryless-baseline | III | descriptivo | 1 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| P3-T2-permanence-reid | III | binario pareado | 1 | ninguna | indefinido | — | **no** | SIN DATOS - no se defiende; en cola de re-ejecución |
| P3-T3-closedloop-coverage | III | binario pareado | 1 | ninguna | indefinido | — | **no** | SIN DATOS - no se defiende; en cola de re-ejecución |
| P3-T0a-anchor-cadence | III | descriptivo | 1 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| P3-T4a-tracker-cost | III | descriptivo | 1 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| E18-cold-acquire-vs-warm-oracle | IV | binario pareado | 6 | McNemar exacta | 0.5 | 1 | sí | no significativa (b=2, c=0); hacían falta >=6 discordantes en una dirección, hubo 2 [deflactado desde b=5, c=0] |
| E18-A-vs-gate | IV | binario de un brazo | 6 | binomial exacta | 0.9986 | 1 | **no** | 1/6 contra puerta 0.67; ningún k habría alcanzado alpha |
| E20-operator-crop-hint | IV | binario pareado | 6 | McNemar exacta | 1 | 1 | sí | no significativa (b=1, c=0); hacían falta >=6 discordantes en una dirección, hubo 1 [deflactado desde b=2, c=0] |
| E20-acquire-latency | IV | continuo pareado | 6 | ninguna | indefinido | — | **no** | solo sobreviven estadísticos agregados; hacen falta los valores por elemento para una prueba |
| E19-motion-compensated-acquire | IV | binario pareado | 6 | McNemar exacta | indefinido | — | sí | 0 pares discordantes - los brazos son indistinguibles con estos datos. No es equivalencia; es ausencia de prueba. [deflactado desde b=1, c=0] |
| E21-coarse-to-fine | IV | binario pareado | 6 | McNemar exacta | 1 | 1 | sí | no significativa (b=1, c=0); hacían falta >=6 discordantes en una dirección, hubo 1 [deflactado desde b=2, c=0] |
| E22-cv-prior-phase0 | IV | binario de un brazo | 6 | binomial exacta | 0.9822 | 1 | **no** | 2/6 contra puerta 0.67; ningún k habría alcanzado alpha |
| E23-tolerant-cells | IV | binario pareado | 6 | McNemar exacta | 1 | 1 | sí | no significativa (b=0, c=1); hacían falta >=6 discordantes en una dirección, hubo 1 [deflactado desde b=0, c=2] |
| E16-relock-replication | IV | binario de un brazo | 8 | binomial exacta | 0.9327 | 1 | **no** | 6/8 contra puerta 0.88; ningún k habría alcanzado alpha |
| E17-reground-chase | IV | binario de un brazo | 1 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo [deflactado desde 0/10: ver independence_note] |
| E14-identity-hole | IV | binario de un brazo | 1 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo [deflactado desde 3/3: ver independence_note] |
| E13-colour-gate | IV | binario de un brazo | 1 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo [deflactado desde 0/3: ver independence_note] |
| E9-retarget-switch | IV | binario de un brazo | 1 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo [deflactado desde 3/3: ver independence_note] |
| E10-fast-follow-ceiling | IV | descriptivo | 4 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| P5.1-warm-vs-cold | V | binario pareado | 6 | McNemar exacta | 0.5 | 1 | sí | no significativa (b=2, c=0); hacían falta >=6 discordantes en una dirección, hubo 2 [deflactado desde b=4, c=0] |
| P5.2a-warm-generalization | V | binario pareado | 23 | McNemar exacta | 6.104e-05 | 0.00177 | sí | significativa (b=15, c=0) [deflactado desde b=16, c=0] |
| P5.2b-speed-sweep | V | continuo pareado | 23 | ninguna | indefinido | — | **no** | solo sobreviven estadísticos agregados; hacen falta los valores por elemento para una prueba |
| P5.3-multi-candidate-select | V | binario de un brazo | 4 | binomial exacta | 0.9728 | 1 | **no** | 3/5 contra puerta 0.80; ningún k habría alcanzado alpha [deflactado desde 3/5: ver independence_note] |
| P5.4-crop-select | V | binario de un brazo | 4 | binomial exacta | 0.9728 | 1 | **no** | 3/5 contra puerta 0.80; ningún k habría alcanzado alpha [deflactado desde 3/5: ver independence_note] |
| P5.5-select-generalization | V | binario de un brazo | 4 | binomial exacta | 0.9728 | 1 | **no** | 3/5 contra puerta 0.80; ningún k habría alcanzado alpha [deflactado desde 3/5: ver independence_note] |
| P5.9-kerbsafe-scenebank | V | binario de un brazo | 15 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo |
| P5.10-simbank-select | V | binario pareado | 12 | McNemar exacta | indefinido | — | sí | 0 pares discordantes - los brazos son indistinguibles con estos datos. No es equivalencia; es ausencia de prueba. |
| P5.12-bankv21-recal | V | binario no pareado | 12 | Fisher exacta | 0.0003365 | 0.009086 | sí | 12/12 contra 3/12 (grupos independientes) |
| P5.13-dd-vs-rg-tie | V | binario pareado | 12 | McNemar exacta | indefinido | — | sí | 0 pares discordantes - los brazos son indistinguibles con estos datos. No es equivalencia; es ausencia de prueba. [deflactado desde b=1, c=0] |
| P5.14-wsel | V | binario de un brazo | 3 | binomial exacta | 0.512 | 1 | **no** | 5/5 contra puerta 0.80; ningún k habría alcanzado alpha [deflactado desde 5/5: ver independence_note] |
| P5.14-swap | V | binario de un brazo | 3 | binomial exacta | 0.896 | 1 | **no** | 4/5 contra puerta 0.80; ningún k habría alcanzado alpha [deflactado desde 4/5: ver independence_note] |
| P5.14-shadow-rg-disagreement | V | binario pareado | 3 | McNemar exacta | 1 | 1 | **no** | n=3 pares no alcanzan alpha=0,05 bilateral ni volteando todos. Diseño sin potencia por construcción. [deflactado desde b=3, c=0] |
| P5.15-plain-carry-survival | V | binario de un brazo | 25 | binomial exacta | 0.002908 | 0.07561 | sí | 24/25 contra puerta 0.72; hacían falta >=23/25 para alpha=0,05 |
| P5.15-maint-vs-plain | V | binario pareado | 25 | McNemar exacta | 0.625 | 1 | sí | no significativa (b=3, c=1); hacían falta >=6 discordantes en una dirección, hubo 3 |
| P5.16-autodisc-wsel | V | binario de un brazo | 3 | binomial exacta | 0.896 | 1 | **no** | 4/5 contra puerta 0.80; ningún k habría alcanzado alpha [deflactado desde 4/5: ver independence_note] |
| P5.18-n25-wsel | V | binario de un brazo | 13 | binomial exacta | 0.5017 | 1 | **no** | 22/26 contra puerta 0.80; ningún k habría alcanzado alpha [deflactado desde 22/26: ver independence_note] |
| P5.18-n25-swap | V | binario de un brazo | 13 | binomial exacta | 0.97 | 1 | **no** | 17/26 contra puerta 0.80; ningún k habría alcanzado alpha [deflactado desde 17/26: ver independence_note] |
| P5.19-swap-late-entry-rescue | V | binario pareado | 13 | McNemar exacta | 0.5 | 1 | sí | no significativa (b=2, c=0); hacían falta >=6 discordantes en una dirección, hubo 2 [deflactado desde b=3, c=0] |
| P5.19-wsel-no-regression | V | binario pareado | 13 | McNemar exacta | indefinido | — | sí | 0 pares discordantes - los brazos son indistinguibles con estos datos. No es equivalencia; es ausencia de prueba. |
| P5.19-grace-precision | V | binario de un brazo | 4 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo |
| P5.20-carry-capacity | V | binario pareado | 13 | McNemar exacta | indefinido | — | sí | 0 pares discordantes - los brazos son indistinguibles con estos datos. No es equivalencia; es ausencia de prueba. [deflactado desde b=0, c=1] |
| P5.20-replication-of-P5.19 | V | binario pareado | 13 | McNemar exacta | indefinido | — | sí | 0 pares discordantes - los brazos son indistinguibles con estos datos. No es equivalencia; es ausencia de prueba. |
| P5.17-dd-vs-rg-tie-n56 | V | binario pareado | 28 | McNemar exacta | indefinido | — | sí | 0 pares discordantes - los brazos son indistinguibles con estos datos. No es equivalencia; es ausencia de prueba. [deflactado desde b=1, c=0] |
| P6.0-flight-rig-gate | VI | descriptivo | 1 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| P6.1-carla-renderer | VI | descriptivo | 1 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |

## Qué sobrevive

- **Significativas tras corrección de Holm (6):** P1-S3.3-export-parity-catastrophe, P2-RQ2.1-resolution-ladder-1024, P2-RQ3.1-lora-aerial-gate, P3-ROI-M2.0-512, P5.2a-warm-generalization, P5.12-bankv21-recal
- **Sin prueba posible, 0 pares discordantes (30):** P1-S1.2-zeroshot-smolvlm, P1-S3.4-coco-to-aerial-domain-shift, P1-S1.3-phaseB-control-stack, P2-RQ0.3-spine-selection, P2-RQ1.1-dataset-well-posedness, P3-wholeframe-resolution-knee, P3-ROI-drift-robustness, P3-E1-TRT-fps, P3-E1-TRT-mask-parity, P3-T1-memoryless-baseline, P3-T0a-anchor-cadence, P3-T4a-tracker-cost, E20-acquire-latency, E19-motion-compensated-acquire, E17-reground-chase, E14-identity-hole, E13-colour-gate, E9-retarget-switch, E10-fast-follow-ceiling, P5.2b-speed-sweep, P5.9-kerbsafe-scenebank, P5.10-simbank-select, P5.13-dd-vs-rg-tie, P5.19-wsel-no-regression, P5.19-grace-precision, P5.20-carry-capacity, P5.20-replication-of-P5.19, P5.17-dd-vs-rg-tie-n56, P6.0-flight-rig-gate, P6.1-carla-renderer
- **Diseño incapaz de alcanzar alpha (35):** P1-S1.2-zeroshot-smolvlm, P1-S3.4-coco-to-aerial-domain-shift, P1-S1.3-phaseB-control-stack, P2-RQ0.3-spine-selection, P2-RQ1.1-dataset-well-posedness, P3-wholeframe-resolution-knee, P3-ROI-drift-robustness, P3-E1-TRT-fps, P3-E1-TRT-mask-parity, P3-T1-memoryless-baseline, P3-T0a-anchor-cadence, P3-T4a-tracker-cost, E18-A-vs-gate, E20-acquire-latency, E22-cv-prior-phase0, E16-relock-replication, E17-reground-chase, E14-identity-hole, E13-colour-gate, E9-retarget-switch, E10-fast-follow-ceiling, P5.2b-speed-sweep, P5.3-multi-candidate-select, P5.4-crop-select, P5.5-select-generalization, P5.9-kerbsafe-scenebank, P5.14-wsel, P5.14-swap, P5.14-shadow-rg-disagreement, P5.16-autodisc-wsel, P5.18-n25-wsel, P5.18-n25-swap, P5.19-grace-precision, P6.0-flight-rig-gate, P6.1-carla-renderer
- **Sin datos crudos, en cola de re-ejecución (3):** P1-S1.4-phaseC-vlm-closed-loop, P3-T2-permanence-reid, P3-T3-closedloop-coverage

## Salvedades por afirmación

Las 65 afirmaciones con salvedad registrada, **literales**
desde `thesis/claims.json`. Una salvedad limita lo que su fila de la tabla
puede sostener: léase junto al valor p, nunca en su lugar. Varias retiran
por completo la lectura ingenua del número.

**P1-S1.2-zeroshot-smolvlm** — Ambos brazos están clavados en el suelo con 0 aciertos, de modo que una prueba pareada entre ellos es degenerada (b=c=0). El intervalo de Wilson sobre 0/50 es todo el contenido: [0, 0.071]. Eso basta para justificar el abandono del spine y es la forma correcta de enunciarlo.

**P1-S2.1-stage2-mode-collapse** — 2/200 frente a un umbral del 30% queda tan por debajo que ninguna corrección por agrupamiento podría cambiar el veredicto. El DIAGNÓSTICO de 'mode collapse', en cambio, se apoya en 5 predicciones inspeccionadas a mano y no es en sí mismo una afirmación medida.

**P1-S3.3-export-parity-catastrophe** — El brazo HF NO tiene fichero por ítem, así que b y c no son directamente recuperables. En su lugar están ACOTADOS: las marginales fijan b - c = 30, lo que deja c en [0, 15]. El PEOR caso para la significación es c=15, b=45, y aun así da p = 1.3e-04. Los b/c almacenados aquí son ese peor caso, de modo que el valor p reportado es una cota superior y la catástrofe es significativa bajo todo emparejamiento compatible con los datos. Este es el resultado individual más fuerte de la Parte I.

**P1-S3.3-quantisation-is-not-the-cost** — Calculado aquí por primera vez: b=17, c=10, p=0.248. La pérdida de fidelidad está en la EXPORTACIÓN, no en la cuantización de 8 bits. Toda frase de la tesis que atribuya parte de la caída a Q8_0 debe matizarse.

**P1-S3.4-coco-to-aerial-domain-shift** — Pre-registrado como descriptivo y sin barra. El intervalo al 95% sobre 1/50 es aproximadamente [0.001, 0.106], de modo que '2.0% está en el suelo de acierto aleatorio' no es una afirmación que los datos puedan sostener — solo lo es 'como mucho en torno al 10%'.

**P1-S4.1-stage4-narrow-miss** — La puerta más instructiva de la Parte I. 39/200 frente a un umbral de 40/200 está dentro de una sola extracción de Bernoulli, y el intervalo de Wilson al 95% [0.146, 0.257] abarca holgadamente el 20%. Los datos no pueden distinguir 'incumplida' de 'cumplida'. El NARROW MISS registrado es una decisión de ingeniería defendible y una decisión estadística indefendible; la tesis debe presentarlo como lo primero.

**P1-S1.3-phaseB-control-stack** — Una puerta de capacidad, no una medición muestreada. 3/3 en un único escenario demuestra que la pila PUEDE cerrar el lazo; no dice nada sobre una tasa a lo largo de escenarios. El recuento de fotogramas no debe usarse nunca como n.

**P1-S1.4-phaseC-vlm-closed-loop** — Existen 13 CSVs de phase-c con todas las columnas por fotograma y deliberadamente NO se extrajeron: los píxeles de entrada eran un fotograma de cielo vacío (el pitch +pi/2 de la cámara de gz es HACIA ABAJO, no hacia arriba). Extraerlos produciría números bien formados sobre nada. Este es el caso que motivó, en el propio repositorio, la regla 'look at it'.

**P2-RQ0.3-spine-selection** — La decisión de spine se apoya TAMBIÉN en una comparación de fidelidad de exportación de -2 pp (Qwen) frente a -16 pp (SmolVLM). La cifra de -2 pp es 15/100 frente a 14/100 - una diferencia de UN SOLO ítem presentada como una propiedad de fidelidad. Esa pata del argumento no está respaldada; la pata de 15/100 frente a 0/100 sí lo está.

**P2-RQ1.1-dataset-well-posedness** — Ninguna prueba es apropiada: esto es una enumeración completa, de modo que un intervalo de confianza sería un error de categoría. Su peso inferencial está aguas abajo: estos mismos 439 son el conjunto de evaluación de TODOS los números de la Parte II, y por eso la agrupación de las 316 imágenes únicas se propaga por toda la parte.

**P2-RQ2.1-resolution-ladder-1024** — El umbral se supera con un margen amplio, de modo que el agrupamiento por imagen no amenaza el veredicto. El 'codo' de RQ-2.3 no tiene barra numérica y es un juicio a ojo — debe presentarse como una decisión de diseño, no como un hallazgo.

**P2-RQ3.1-lora-aerial-gate** — 261 es el único entero compatible con el 0.595 redondeado y está corroborado por el gate_hits acumulado del log de evaluación (260 en i=435). El margen sobre la puerta es enorme; el agrupamiento no puede alterar el veredicto.

**P2-RQ4.1-deploy-fidelity** — El número estrella de la Parte II. Los brazos de runtime (F16 273, Q8_0 275) quedan POR ENCIMA de la referencia HF (261), lo que el registro interpreta como una victoria de fidelidad; con estos marginales, esa diferencia de 14 ítems está dentro de lo que el emparejamiento podría producir por azar, de modo que la afirmación defendible es «no hay pérdida medible en la exportación», no «la exportación la mejoró».

**P3-wholeframe-resolution-knee** — No se pre-registró ningún umbral numérico — un barrido de caracterización cuya función era establecer la línea base contra la que se mide la palanca ROI. Cuatro ejecuciones SMOKE de n=6 están en el mismo directorio runs/ y no deben confundirse con los brazos de n=439.

**P3-ROI-M2.0-512** — Los recuentos se reconstruyeron a partir de las tasas almacenadas y caen exactamente en enteros, así que son exactos. La puerta se supera con un margen enorme y sobrevive a cualquier corrección por agrupamiento plausible. La SELECCIÓN de M=2.0 @512 como pico frente a M=1.5 @512 (368/439) es una diferencia de 6 ítems sobre ítems compartidos y debe presentarse como 'una meseta, y tomamos un punto sobre ella'.

**P3-ROI-drift-robustness** — Sin barra numérica pre-registrada. Como la dirección de la deriva es una sola extracción, los números por nivel de desplazamiento arrastran error muestral en la PERTURBACIÓN además de en los ítems, y solo el primero está cuantificado. El peor nivel (1.0, M=2.0) sigue superando la línea base del 62.6%, que es la forma honesta de la afirmación.

**P3-SR-swin2sr-accuracy** — CORRIGE UNA CONCLUSIÓN YA REGISTRADA. Los pares discordantes se calculan aquí por primera vez: lanczos vs swin2sr b=21 c=14 p=0.31; bicubic vs swin2sr b=22 c=12 p=0.12; bicubic vs native p=0.26. NINGUNA diferencia de exactitud en este sondeo es significativa. El rechazo es correcto, pero debe justificarse por LATENCIA (+1331 ms por recorte, determinista y enorme), no por exactitud. Cualquier frase que diga que Swin2SR 'pierde' en IoU carece de respaldo; la frase respaldada es que no aporta nada medible a cambio de 1.3 s.

**P3-carry-OP768-accuracy** — Una prueba de signos sobre la comparación pareada por track: 1024 gana a 768 en 55 tracks, 768 gana a 1024 en 31, 100 empates. p exacto = 0.014, así que 1024 SÍ es significativamente más preciso que 768. La adopción de 768 nunca fue una afirmación de igualdad - la regla congelada era un listón de TAMAÑO DEL EFECTO (dentro de 5 pp de la referencia de 1024) más una restricción de FPS. La tesis debe enunciarlo así: se eligió 768 pese a un coste de precisión real, pequeño y detectable.

**P3-E1-TRT-fps** — No hay intervalo calculable y no debe citarse ninguno. Los fotogramas de una misma sesión comparten el estado térmico y el estado del gobernador de reloj. La afirmación es defendible como demostración de capacidad en este dispositivo y en esta sesión, que es lo que necesita una tesis de despliegue en el borde; no es defendible como tasa esperada.

**P3-E1-TRT-mask-parity** — Una comprobación de equivalencia numérica, no una afirmación de exactitud muestreada, y es el tipo de evidencia adecuado para lo que se le pide mostrar: la exportación a fp16 no cambió la aritmética. Citar '100 fotogramas' como n sería pseudo-replicación de la clase más evidente.

**P3-T1-memoryless-baseline** — No se pre-registró ningún umbral; T1 fue un entregable de harness. Sus números son la referencia contra la que se compara el brazo de re-ID, y solo UNO de los dos clips puede discriminar en absoluto.

**P3-T2-permanence-reid** — NO HAY FICHERO CRUDO EN DISCO: los números solo sobreviven en el README y en el registro. Incluso si se recuperaran, todo el PASS descansa sobre un único clip guionizado en el que un cambio de ID ocurre o no ocurre: una sola extracción de Bernoulli, sin intervalo, sin prueba.

**P3-T3-closedloop-coverage** — EL n MÁS EXAGERADO DEL REPOSITORIO. No hay ningún archivo en disco; solo prosa del README. Las diferencias de fracción de fotogramas procedentes de vuelos únicos no deben presentarse nunca como si tuvieran error de muestreo entre vuelos.

**P3-T0a-anchor-cadence** — La comparación que importa (2.26 s frente a 1.5 s) es un cociente de dos cantidades deterministas con una dispersión mín-máx de 1.3 ms sobre 8 repeticiones. No hace falta ninguna prueba ni es posible; la conclusión arquitectónica se sigue de las magnitudes.

**P3-T4a-tracker-cost** — Pseudorreplicación que no importa: la afirmación supera su presupuesto por dos órdenes de magnitud, de modo que ninguna corrección por dependencia podría invertirla. Vale la pena declararlo explícitamente en lugar de citar n=1180 en silencio.

**E18-cold-acquire-vs-warm-oracle** — EL NÚMERO QUE LANZÓ LA PARTE V, y se queda en p = 0.0625 — justo fuera de alfa, porque con n=6 hacen falta LOS SEIS pares para volcar y solo volcaron cinco. El efecto es casi con seguridad real (el mecanismo es un retardo de entrega medido de 4.85 s, no un lanzamiento de moneda), pero el EXPERIMENTO no pudo certificarlo. Seis clips eran un clip de menos.

**E18-A-vs-gate** — La dirección del fallo es lo que un diseño de 6 ítems SÍ puede establecer: 1/6 frente a una tasa de 2/3 tiene un p unilateral de 0.10. Sigue sin llegar a alpha, pero la brecha descriptiva es grande y el mecanismo se comprende.

**E20-operator-crop-hint** — Exactamente DOS pares discordantes sostienen toda la afirmación: p = 0.50. La mitad de E20 relativa a la tasa de PASS no es evidencia. La mitad relativa a la LATENCIA es otra cosa —véase E20-acquire-latency— y es esa mitad la que debe sostener la narrativa de la Parte IV.

**E20-acquire-latency** — Nunca debe ponerse un intervalo de confianza sobre esto. Es un modelo de coste determinista, no una muestra ruidosa, y la presentación honesta es el mecanismo (menos tokens de prefill) más las dos medianas. Una reducción de latencia de 2.6x con una causa conocida no necesita valor p; afirmar uno sería falsa precisión.

**E19-motion-compensated-acquire** — UN solo par discordante: p = 1.0. El brazo BUF es estadísticamente vacuo frente a la línea base E18-A - b=0, c=0, McNemar indefinido. Ninguno de los dos brazos es evidencia de nada; ambos quedan correctamente registrados como fracasos en alcanzar la puerta, lo cual es una afirmación distinta y más débil que 'la compensación de movimiento no funciona'.

**E21-coarse-to-fine** — Emparejado contra el brazo de celda de E20: b=2, c=0, p=0.50. El mecanismo de apoyo es más fuerte que el recuento de resultados: la propia votación gruesa de celda solo acierta 2/6, de modo que la automatización falla en un paso intermedio medible y no de forma misteriosa.

**E22-cv-prior-phase0** — El tipo adecuado de pre-filtro barato: mató una matriz antes de ejecutarla. Las dos abstenciones en t=10 s están estructuralmente correlacionadas (mismo mecanismo de fallo), así que incluso 6 es generoso.

**E23-tolerant-cells** — b=0, c=2 frente al brazo de celdas de E20: p=0.50. La evidencia más fuerte aquí es el barrido de contención OFFLINE - la contención en el peor caso con HW*=0.38 se mantiene en 6/6 clips y 19/19 formulaciones - que es un cálculo geométrico determinista y no necesita inferencia. La regresión en dispositivo cierra el arco; el barrido de contención explica por qué ensanchar no puede ayudar.

**E16-relock-replication** — La regla pre-registrada exigía 7/8 para «fiable». Esa barra es estadísticamente INALCANZABLE con n=8: incluso un 8/8 perfecto frente a una hipótesis nula de 0.875 da p = 0.34. El veredicto QUALIFIED fue la decisión correcta y el intervalo de Wilson [0.36, 0.89] es el resumen honesto: la verdadera tasa de reenganche podría estar en cualquier punto entre el lanzamiento de una moneda y la práctica certeza.

**E17-reground-chase** — n=10 parece la muestra más fuerte de la Parte IV y es la más débil. Informar del intervalo Wilson sobre 0/10 ([0, 0.28]) implicaría diez extracciones independientes; hubo una. La afirmación correcta es mecanicista — la palanca no se aplica a esta ruta de código — y está bien respaldada por las trazas idénticas.

**E14-identity-hole** — 3/3 tiene una cota inferior de Wilson de en torno a 0.44 incluso si los tres fueran independientes, y no lo son. E15 falló después en esa misma pata de regresión 0/1, lo que obligó a ejecutar E16 para zanjarlo - y E16 encontró 6/8, es decir, el arreglo es real pero NO determinista. E14 por sí solo lo sobrevaloró.

**E13-colour-gate** — Un 0/3 determinista. Afirmación mecanicista, no probabilística: la puerta nunca se dispara en este escenario. Que los tres tramos de regresión pasen 3/3 es lo que hace interpretable el resultado negativo: el cambio estaba activo y no hizo nada.

**E9-retarget-switch** — Una demostración de capacidad sobre un único escenario. La prueba de humo de color (blanco 10/10, azul 10/10) es una pata distinta y mejor respaldada porque varía la entrada en lugar de repetir la ejecución.

**E10-fast-follow-ceiling** — Un barrido de búsqueda de umbral, y las repeticiones deterministas son en realidad una VIRTUD aquí: establecen que la frontera entre 2.5 y 3.0 es una propiedad del controlador y no de la extracción. Presentarlo como '3/3 frente a 0/2' invita a una prueba que carecería de sentido; presentarlo como un techo medido con cuatro configuraciones es lo correcto.

**P5.1-warm-vs-cold** — p = 0.125. El primer YES de la Parte V no es estadísticamente significativo: n=6 exige que se inviertan los seis pares y se invirtieron cuatro. La condición pre-registrada de superconjunto (el conjunto de PASS de WARM contiene el de COLD) es una comprobación estructural más fuerte que el recuento y se cumplió: eso, más la coincidencia exacta con el oráculo, es la forma defendible de la afirmación. P5.2 es lo que realmente lo certifica.

**P5.2a-warm-generalization** — EL RESULTADO CON MÁS POTENCIA ESTADÍSTICA DE LA PARTE V Y CON EL QUE LA TESIS DEBERÍA ABRIR. b=16, c=0, McNemar exacto p = 3.05e-05, y sobrevive a la corrección de Holm en toda la familia. 16 clips vuelcan de fallo a éxito y ninguno vuelca de vuelta. Esta es la afirmación del warm-start, debidamente certificada.

**P5.2b-speed-sweep** — Una hipótesis direccional pre-registrada (se exigía rho > 0) que salió en rho = -0.06, cuyo p bilateral con n=25 ronda 0.78 - es decir, ninguna asociación en absoluto, no una débil. Este es un negativo genuino e IMPORTA: dice que la ganancia del warm-start es la eliminación del retardo de entrega, no compensación de movimiento. Un nulo que remodela el mecanismo vale más que la mayoría de los positivos de aquí.

**P5.3-multi-candidate-select** — LA PUERTA PRE-REGISTRADA ERA ESTADÍSTICAMENTE INALCANZABLE. Frente a una hipótesis nula de 0.8, incluso un 5/5 perfecto da p = 0.33, de modo que ningún resultado posible de este diseño podría haber superado 4/5 en ningún sentido inferencial. El NO es una parada de ingeniería legítima; no es evidencia de que el select-on-command no funcione.

**P5.4-crop-select** — El README revela un SESGO DE PILOTO: 3 de las 5 escenas del veredicto se usaron en el piloto. Combinada con el umbral inalcanzable, esta celda no informa nada sobre la exactitud del select. La pata de LATENCIA (4.9 s -> 2.08 s) es determinista y se sostiene por sí sola.

**P5.5-select-generalization** — Tercer NO de select consecutivo sobre un diseño cuya puerta ningún resultado podía superar. El contenido genuinamente informativo es diagnóstico, no inferencial: el re-anclaje en reposo se disparó y fue aceptado en las 16 celdas, y dos fallos NO_MATCH por deriva de carry sobrevivieron a ello. Eso es un mecanismo, y es lo que motivó el cambio del contrato de entrega.

**P5.9-kerbsafe-scenebank** — Una puerta de construcción, tratada correctamente como tal. 12/12 tiene un intervalo de Wilson de [0.76, 1.0]: el generador es bueno, no está demostrado que sea perfecto. Las 12 celdas proceden de un único generador con un único conjunto de activos, de modo que esto mide el artefacto, no una población de escenas.

**P5.10-simbank-select** — CERO pares discordantes: McNemar queda INDEFINIDO, no 1.0. Esta campaña no encontró que los brazos fueran iguales; no ejecutó ninguna prueba. Ambos brazos están en el techo, de modo que el diseño no tenía margen para separar nada — que es exactamente lo que dice el diagnóstico 'scene-bound' del registro, y la estadística coincide.

**P5.12-bankv21-recal** — EL CAVEAT MÁS IMPORTANTE DEL ARCO DE SIMULACIÓN DE LA PARTE V. La mejora es en parte DEFINICIONAL: los suelos (G6c 60 -> 40, G8b 0.55 -> 0.40) se recalibraron a partir de la propia población registrada de P5.11. Bajar un umbral y luego informar de que más celdas lo superan no es un efecto. Lo que SÍ es legítimo es que los suelos se congelaron ANTES de la ejecución y que 6 semillas no vistas también lo superaron, y que el delta de predicción de frame limpio offline fue 0 en las 12. Preséntese como una corrección de calibrado, nunca como una mejora de 4x.

**P5.13-dd-vs-rg-tie** — UN solo par discordante: p = 1.0 bilateral. El SEP_MARGIN pre-registrado de 4 estaba él mismo por debajo del efecto mínimo detectable: alcanzar alfa requería 6 discordantes en un solo sentido. Y DD está en 24/24, de modo que el rango observable de DD-RG queda acotado por arriba por el único fallo de RG. «Los contratos son equivalentes» no está respaldado; «este diseño no tenía potencia para distinguirlos», sí.

**P5.14-wsel** — 5/5 frente a una hipótesis nula de 0.8 da p = 0.33 — el umbral no pudo superarse inferencialmente con esta n. P5.18 volvió a ejecutar después esta afirmación con n=26 y encontró una tasa WSEL real cercana a 0.85, coherente con 5/5 y, con razón, menos llamativa. Cítese P5.18, no P5.14.

**P5.14-swap** — 4/5 frente a 0.8 es p = 0.74 - literalmente lo que predice la hipótesis nula. P5.18 halló la tasa real de SWAP en 0.65 (17/26), así que esta celda fue optimismo de n pequeño y el propio trabajo posterior del repositorio lo dice.

**P5.14-shadow-rg-disagreement** — p = 0.25. Los tres desacuerdos son RG devolviendo NO_MATCH: no llegó a seleccionar en absoluto, en lugar de seleccionar de otro modo. Esa asimetría es más informativa que el recuento: sobre imagen real el contrato de re-grounding no se limita a perder, se abstiene. Contrástese con los bancos de simulación (P5.10/13/17), donde RG consigue el grounding de casi todo: la diferencia es la fragilidad ante imagen real.

**P5.15-plain-carry-survival** — 24/25 frente al suelo pre-registrado de 18/25 da un valor p exacto unilateral de 0.0016, y el intervalo Wilson es [0.80, 0.99]. ESTE ES UN RESULTADO DEBIDAMENTE CERTIFICADO y es portante: el carry no es la parte frágil, lo que redirige todo el análisis de fallos hacia la entrega y la selección.

**P5.15-maint-vs-plain** — p = 0.625. La regresión NO está estadísticamente establecida, y la afirmación honesta es que el mantenimiento no compró nada medible mientras costaba cómputo. El mecanismo (100/100 re-anclajes aceptados sin suelo de IoU, que provocan intercambios de identidad dentro de la misma clase) es evidencia diagnóstica que un recuento de 25 clips no puede aportar, y es la razón por la que retirar la palanca seguía siendo correcto.

**P5.16-autodisc-wsel** — El número IMPORTANTE de P5.16 no es el 4/5: es 24/24 descubrimientos del VLM en la ventana ociosa aceptados, lo que hace que el pipeline sea GT-free de extremo a extremo. Esa es una afirmación de capacidad con un denominador limpio; la tasa de select con n=5 no lo es.

**P5.18-n25-wsel** — 22/26 = 0.846 frente a una barra de 0.8: p exacto = 0.37, de modo que se supera DESCRIPTIVAMENTE pero no inferencialmente. El intervalo Wilson [0.67, 0.94] contiene el umbral. La frase correcta es 'coherente con la tasa pre-registrada', no 'la supera'. CORRECCIÓN R-4: la n efectiva baja de 26 a 13 porque las 26 celdas proceden de sólo 13 videoclips distintos. La proporción se conserva (11/13 = 0,846) y el intervalo se ensancha; la lectura «coherente con la tasa pre-registrada, no la supera» no cambia, sólo se refuerza.

**P5.18-n25-swap** — EL RESULTADO MÁS VALIOSO DEL RE-ANÁLISIS ESTADÍSTICO. En las 5 celdas compartidas, P5.18 reproduce P5.16 EXACTAMENTE (4/5, cero inversiones); todo el vuelco procede de las 21 celdas nuevas, donde SWAP es 13/21 = 0.62. Esta es una demostración directa y medida de que los veredictos de n pequeño eran optimistas - y es el repositorio detectando su propio error, que es la forma más fuerte que la tesis puede presentar. CORRECCIÓN R-4: n efectiva 26 → 13 (13 videoclips distintos). El fallo se mantiene: 8/13 = 0,615 frente a la barra de 0,8. Una deflación sólo puede ensanchar el intervalo, de modo que no puede rescatar un NO.

**P5.19-swap-late-entry-rescue** — b=3, c=0, p = 0.25. EL YES JUSTO EN LA BARRA NO ES SIGNIFICATIVO. Tres celdas pasan de fallo a acierto y ninguna vuelve atrás, que es la FORMA correcta para un arreglo real, pero tres es la mitad de los seis cambios en un solo sentido que alfa exigiría con esta n. El mecanismo de apoyo es fuerte (el guardián de P5.18 estaba desalineado respecto al fotograma y se disparó 0/108 veces; la entrega de gracia cuesta 0.37-0.60 s frente a 4.68 s en frío) y P5.20 reprodujo de forma independiente el brazo T celda por celda. Preséntese así: una mejora explicada mecánicamente y del signo correcto, todavía no certificada. CORRECCIÓN R-4: n efectiva 26 → 13 (13 videoclips distintos). Ésta es la afirmación a la que la omisión beneficiaba, así que conviene decir con precisión qué cambia y qué no. El valor p NO empeora de significativo a no significativo: ya era p = 0,25 con la n completa, nunca fue significativo. Lo que la deflación elimina es el margen justo en la barra: la puerta pre-registrada de 20/26 celdas pasa a ser 10/13 sobre una línea base de 8/13. Enunciado correcto: no pudimos distinguir los brazos; la puerta se superó con un margen que no sobrevive al agrupamiento por clip.

**P5.19-wsel-no-regression** — Cero pares discordantes, así que no existe prueba alguna. Aquí el empate es el resultado DESEADO y su interpretación es segura de un modo en que la de P5.10 no lo es: ni una sola de las 26 celdas cambió de estado, lo que acota estrechamente cualquier regresión incluso sin un valor p. Enúnciese como 'ninguna celda cambió', nunca como 'demostrado inocuo'. CORRECCIÓN R-4: n efectiva 26 → 13. Sin efecto aquí: con cero discordantes no hay prueba ni antes ni después. La cota útil sigue siendo la observación en bruto —ninguna de las 26 celdas cambió de estado—, que no depende de cuántas unidades independientes haya.

**P5.19-grace-precision** — El intervalo de Wilson sobre 2/4 es [0.15, 0.85] - esta medición no aporta esencialmente ninguna información sobre la precisión real. Se registra como un residuo abierto y ese es el único uso defendible. Lo que importa cualitativamente es el MODO DE FALLO: los disparos erróneos entregan una caja con confianza en lugar de abstenerse, que es la dirección peligrosa para un sistema de cara al operador.

**P5.20-carry-capacity** — b=0, c=1: p = 1.0. No es evidencia de que la capacidad no ayude, es evidencia de que este diseño no vio efecto alguno en ninguna dirección. Lo que hace defendible lo de «palanca muerta» no es el recuento sino el MECANISMO: el mismo bloqueo de deriva de la familia de coches aparece en ambos brazos, de modo que los fallos no están limitados por la capacidad. Una n mayor tendría que justificarse con un mecanismo plausible, y ninguno sobrevive. CORRECCIÓN R-4: n efectiva 26 → 13 (13 videoclips distintos). El único par discordante (c=1) se redondea a cero al deflactar, de modo que la lectura pasa de p = 1,0 a NO HAY PRUEBA. Las dos lecturas son no significativas y la segunda es la más honesta: con 13 unidades independientes nunca hubo resolución para ver un solo cambio. El argumento de «palanca muerta» se sostiene sobre el mecanismo, no sobre el recuento, y eso no cambia.

**P5.20-replication-of-P5.19** — Cero discordantes, así que formalmente no hay prueba — pero este es el 'indefinido' más valioso del registro. Una re-ejecución independiente que reproduce las 52 celdas exactamente establece que la medición de P5.19 es estable y no una extracción afortunada. Certifica la REPETIBILIDAD, que es una propiedad distinta de la significación y que la tesis debería reclamar explícitamente porque la mayoría de las campañas de aquí no pueden. CORRECCIÓN R-4: n efectiva 26 → 13. La repetibilidad que esta entrada certifica no depende de la n efectiva: «las 52 celdas se reprodujeron exactamente» es una afirmación sobre determinismo de la medición, no una inferencia sobre una población.

**P5.17-dd-vs-rg-tie-n56** — LA DEMOSTRACIÓN MÁS CLARA DEL REPOSITORIO DE QUE n NO ERA LA RESTRICCIÓN VINCULANTE. Pasar de 24 a 56 celdas no aumentó la potencia, porque lo que cayó fue la TASA de fallo en vez de aparecer el efecto: b=1, c=0, p=1.0, exactamente igual que con n=24. El SEP_MARGIN pre-registrado de 7 exigía que RG fallara 7 celdas; RG falló 1 en toda la matriz. La conclusión correcta es que el simulador renderiza demasiado limpio para separar los contratos, lo cual es una afirmación sobre el instrumento, no sobre la hipótesis.

**P6.0-flight-rig-gate** — n=1 es CORRECTO aquí y la tesis debería decir por qué: una puerta de capacidad pregunta «¿puede este montaje cerrar el lazo siquiera?», y una sola demostración lo responde. La mejora de px_err 64.7 -> 36.0 es un antes/después sobre un único vuelo y no debe citarse como error esperado. La afirmación retirada de px_err de Phase-C Branch-1 es el ejemplo aleccionador.

**P6.1-carla-renderer** — Una afirmación de capacidad medida una sola vez, correctamente. EL ÚNICO NÚMERO QUE NO DEBE CITARSE: slave_err = 0.000 m es vacuo — la cámara libre de CARLA es un actor cinemático, de modo que get_transform() devuelve exactamente lo que se le acaba de pasar a set_transform(). No mide nada sobre la fidelidad del pose-slaving.

## Cola de re-ejecución

Afirmaciones cuyos datos por elemento no sobreviven. No se defienden en
el TFM hasta que se re-ejecuten.

<!-- caption: Trabajo de re-ejecución necesario para hacer defendible cada afirmación sin datos -->

| Afirmación | Qué falta | Coste | Comando |
|---|---|---|---|
| P1-S1.4-phaseC-vlm-closed-loop | píxeles válidos — la medida es inválida en origen | superado; el rig de CARLA (P6.1) es el sitio correcto para volver a preguntarlo | `runners/run_phase_c.py con el renderizador CARLA, tras corregir el pitch de cámara` |
| P3-T2-permanence-reid | puntuaciones por clip; solo sobrevive la prosa del README | ~1 h en la 3090; los clips y el scorer están versionados | `.venv-ft/bin/python -m grounding.eval.score_clips --clips experiments/2026-06-18-t1-temporal-contract/clips --arms memoryless,reid` |
| P3-T3-closedloop-coverage | registros por vuelo; solo prosa del README | ~2 h; necesita n>=10 vuelos por brazo para decir algo sobre una tasa | `runners/run_phase_c.py --arms memoryless,reid --reps 10 (renderizador CARLA)` |

## Figuras

<!-- caption: Diseños pareados por n efectivo; en rojo los que no podían alcanzar significación con ningún resultado -->

![](proof/stats-power.png)

<!-- caption: Proporciones observadas con intervalo de Wilson al 95 %; la barra roja marca la puerta pre-registrada -->

![](proof/stats-forest.png)

