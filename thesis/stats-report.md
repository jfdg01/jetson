---
title: Resultados estadísticos retroactivos
subtitle: Cada afirmación con puerta de las Partes I-VI, re-analizada
author: Javier Francisco Dibo Gómez
comment: Generado por thesis/run_stats.py, 2026-07-21T17:27Z
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
| P1-S3.3-export-parity-catastrophe | I | binario pareado | 100 | McNemar exacta | 0.0001345 | 0.004304 | sí | significativa (b=45, c=15) |
| P1-S3.3-quantisation-is-not-the-cost | I | binario pareado | 100 | McNemar exacta | 0.2478 | 1 | sí | no significativa (b=17, c=10); hacían falta >=6 discordantes en una dirección, hubo 17 |
| P1-S3.4-coco-to-aerial-domain-shift | I | binario de un brazo | 47 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo [deflactado desde 1/50: ver independence_note] |
| P1-S4.1-stage4-narrow-miss | I | binario de un brazo | 200 | binomial exacta | 0.5981 | 1 | sí | 39/200 contra puerta 0.20; hacían falta >=50/200 para alpha=0,05 |
| P1-S1.3-phaseB-control-stack | I | binario de un brazo | 1 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo [deflactado desde 3/3: ver independence_note] |
| P1-S1.4-phaseC-vlm-closed-loop | I | binario pareado | 0 | ninguna | indefinido | — | **no** | SIN DATOS - no se defiende; en cola de re-ejecución |
| P2-RQ0.3-spine-selection | II | binario de un brazo | 100 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo |
| P2-RQ1.1-dataset-well-posedness | II | descriptivo | 1421 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| P2-RQ2.1-resolution-ladder-1024 | II | binario de un brazo | 316 | binomial exacta | 7.771e-06 | 0.0002642 | sí | 133/439 contra puerta 0.20; hacían falta >=76/316 para alpha=0,05 [deflactado desde 133/439: ver independence_note] |
| P2-RQ3.1-lora-aerial-gate | II | binario de un brazo | 316 | binomial exacta | 3.679e-53 | 1.325e-51 | sí | 261/439 contra puerta 0.20; hacían falta >=76/316 para alpha=0,05 [deflactado desde 261/439: ver independence_note] |
| P2-RQ4.1-deploy-fidelity | II | binario de un brazo | 316 | binomial exacta | 0.0355 | 0.9939 | sí | 275/439 contra puerta 0.57; hacían falta >=197/316 para alpha=0,05 [deflactado desde 275/439: ver independence_note] |
| P3-wholeframe-resolution-knee | III | descriptivo | 316 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis [deflactado desde 277/439] |
| P3-ROI-M2.0-512 | III | binario de un brazo | 316 | binomial exacta | 7.235e-19 | 2.532e-17 | sí | 374/439 contra puerta 0.63; hacían falta >=213/316 para alpha=0,05 [deflactado desde 374/439: ver independence_note] |
| P3-ROI-drift-robustness | III | descriptivo | 316 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis [deflactado desde 326/439] |
| P3-SR-swin2sr-accuracy | III | binario pareado | 312 | McNemar exacta | 0.3105 | 1 | sí | no significativa (b=21, c=14); hacían falta >=6 discordantes en una dirección, hubo 21 |
| P3-carry-OP768-accuracy | III | binario pareado | 93 | McNemar exacta | 0.01267 | 0.3675 | sí | significativa (b=55, c=31) |
| P3-E1-TRT-fps | III | descriptivo | 1 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| P3-E1-TRT-mask-parity | III | descriptivo | 1 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| P3-T1-memoryless-baseline | III | descriptivo | 1 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| P3-T2-permanence-reid | III | binario pareado | 1 | ninguna | indefinido | — | **no** | SIN DATOS - no se defiende; en cola de re-ejecución |
| P3-T3-closedloop-coverage | III | binario pareado | 1 | ninguna | indefinido | — | **no** | SIN DATOS - no se defiende; en cola de re-ejecución |
| P3-T0a-anchor-cadence | III | descriptivo | 1 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| P3-T4a-tracker-cost | III | descriptivo | 1 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| E18-cold-acquire-vs-warm-oracle | IV | binario pareado | 6 | McNemar exacta | 0.0625 | 1 | sí | no significativa (b=5, c=0); hacían falta >=6 discordantes en una dirección, hubo 5 |
| E18-A-vs-gate | IV | binario de un brazo | 6 | binomial exacta | 0.9986 | 1 | **no** | 1/6 contra puerta 0.67; ningún k habría alcanzado alpha |
| E20-operator-crop-hint | IV | binario pareado | 6 | McNemar exacta | 0.5 | 1 | sí | no significativa (b=2, c=0); hacían falta >=6 discordantes en una dirección, hubo 2 |
| E20-acquire-latency | IV | continuo pareado | 6 | ninguna | indefinido | — | **no** | solo sobreviven estadísticos agregados; hacen falta los valores por elemento para una prueba |
| E19-motion-compensated-acquire | IV | binario pareado | 6 | McNemar exacta | 1 | 1 | sí | no significativa (b=1, c=0); hacían falta >=6 discordantes en una dirección, hubo 1 |
| E21-coarse-to-fine | IV | binario pareado | 6 | McNemar exacta | 0.5 | 1 | sí | no significativa (b=2, c=0); hacían falta >=6 discordantes en una dirección, hubo 2 |
| E22-cv-prior-phase0 | IV | binario de un brazo | 6 | binomial exacta | 0.9822 | 1 | **no** | 2/6 contra puerta 0.67; ningún k habría alcanzado alpha |
| E23-tolerant-cells | IV | binario pareado | 6 | McNemar exacta | 0.5 | 1 | sí | no significativa (b=0, c=2); hacían falta >=6 discordantes en una dirección, hubo 2 |
| E16-relock-replication | IV | binario de un brazo | 8 | binomial exacta | 0.9327 | 1 | **no** | 6/8 contra puerta 0.88; ningún k habría alcanzado alpha |
| E17-reground-chase | IV | binario de un brazo | 1 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo [deflactado desde 0/10: ver independence_note] |
| E14-identity-hole | IV | binario de un brazo | 1 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo [deflactado desde 3/3: ver independence_note] |
| E13-colour-gate | IV | binario de un brazo | 1 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo [deflactado desde 0/3: ver independence_note] |
| E9-retarget-switch | IV | binario de un brazo | 1 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo [deflactado desde 3/3: ver independence_note] |
| E10-fast-follow-ceiling | IV | descriptivo | 4 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| P5.1-warm-vs-cold | V | binario pareado | 6 | McNemar exacta | 0.125 | 1 | sí | no significativa (b=4, c=0); hacían falta >=6 discordantes en una dirección, hubo 4 |
| P5.2a-warm-generalization | V | binario pareado | 23 | McNemar exacta | 3.052e-05 | 0.001007 | sí | significativa (b=16, c=0) |
| P5.2b-speed-sweep | V | continuo pareado | 23 | ninguna | indefinido | — | **no** | solo sobreviven estadísticos agregados; hacen falta los valores por elemento para una prueba |
| P5.3-multi-candidate-select | V | binario de un brazo | 4 | binomial exacta | 0.9728 | 1 | **no** | 3/5 contra puerta 0.80; ningún k habría alcanzado alpha [deflactado desde 3/5: ver independence_note] |
| P5.4-crop-select | V | binario de un brazo | 4 | binomial exacta | 0.9728 | 1 | **no** | 3/5 contra puerta 0.80; ningún k habría alcanzado alpha [deflactado desde 3/5: ver independence_note] |
| P5.5-select-generalization | V | binario de un brazo | 4 | binomial exacta | 0.9728 | 1 | **no** | 3/5 contra puerta 0.80; ningún k habría alcanzado alpha [deflactado desde 3/5: ver independence_note] |
| P5.9-kerbsafe-scenebank | V | binario de un brazo | 15 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo |
| P5.10-simbank-select | V | binario pareado | 12 | McNemar exacta | indefinido | — | sí | 0 pares discordantes - los brazos son indistinguibles con estos datos. No es equivalencia; es ausencia de prueba. |
| P5.12-bankv21-recal | V | binario no pareado | 12 | Fisher exacta | 0.0003365 | 0.01043 | sí | 12/12 contra 3/12 (grupos independientes) |
| P5.13-dd-vs-rg-tie | V | binario pareado | 12 | McNemar exacta | 1 | 1 | sí | no significativa (b=1, c=0); hacían falta >=6 discordantes en una dirección, hubo 1 |
| P5.14-wsel | V | binario de un brazo | 3 | binomial exacta | 0.512 | 1 | **no** | 5/5 contra puerta 0.80; ningún k habría alcanzado alpha [deflactado desde 5/5: ver independence_note] |
| P5.14-swap | V | binario de un brazo | 3 | binomial exacta | 0.896 | 1 | **no** | 4/5 contra puerta 0.80; ningún k habría alcanzado alpha [deflactado desde 4/5: ver independence_note] |
| P5.14-shadow-rg-disagreement | V | binario pareado | 3 | McNemar exacta | 0.25 | 1 | **no** | n=3 pares no alcanzan alpha=0,05 bilateral ni volteando todos. Diseño sin potencia por construcción. |
| P5.15-plain-carry-survival | V | binario de un brazo | 25 | binomial exacta | 0.002908 | 0.08724 | sí | 24/25 contra puerta 0.72; hacían falta >=23/25 para alpha=0,05 |
| P5.15-maint-vs-plain | V | binario pareado | 25 | McNemar exacta | 0.625 | 1 | sí | no significativa (b=3, c=1); hacían falta >=6 discordantes en una dirección, hubo 3 |
| P5.16-autodisc-wsel | V | binario de un brazo | 3 | binomial exacta | 0.896 | 1 | **no** | 4/5 contra puerta 0.80; ningún k habría alcanzado alpha [deflactado desde 4/5: ver independence_note] |
| P5.18-n25-wsel | V | binario de un brazo | 26 | binomial exacta | 0.3833 | 1 | sí | 22/26 contra puerta 0.80; hacían falta >=25/26 para alpha=0,05 |
| P5.18-n25-swap | V | binario de un brazo | 26 | binomial exacta | 0.9768 | 1 | sí | 17/26 contra puerta 0.80; hacían falta >=25/26 para alpha=0,05 |
| P5.19-swap-late-entry-rescue | V | binario pareado | 26 | McNemar exacta | 0.25 | 1 | sí | no significativa (b=3, c=0); hacían falta >=6 discordantes en una dirección, hubo 3 |
| P5.19-wsel-no-regression | V | binario pareado | 26 | McNemar exacta | indefinido | — | sí | 0 pares discordantes - los brazos son indistinguibles con estos datos. No es equivalencia; es ausencia de prueba. |
| P5.19-grace-precision | V | binario de un brazo | 4 | IC de Wilson | indefinido | — | **no** | sin puerta pre-registrada; solo intervalo |
| P5.20-carry-capacity | V | binario pareado | 26 | McNemar exacta | 1 | 1 | sí | no significativa (b=0, c=1); hacían falta >=6 discordantes en una dirección, hubo 1 |
| P5.20-replication-of-P5.19 | V | binario pareado | 26 | McNemar exacta | indefinido | — | sí | 0 pares discordantes - los brazos son indistinguibles con estos datos. No es equivalencia; es ausencia de prueba. |
| P5.17-dd-vs-rg-tie-n56 | V | binario pareado | 28 | McNemar exacta | 1 | 1 | sí | no significativa (b=1, c=0); hacían falta >=6 discordantes en una dirección, hubo 1 |
| P6.0-flight-rig-gate | VI | descriptivo | 1 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |
| P6.1-carla-renderer | VI | descriptivo | 1 | descriptiva | indefinido | — | **no** | solo descriptiva - no se pre-registró ninguna hipótesis |

## Qué sobrevive

- **Significativas tras corrección de Holm (6):** P1-S3.3-export-parity-catastrophe, P2-RQ2.1-resolution-ladder-1024, P2-RQ3.1-lora-aerial-gate, P3-ROI-M2.0-512, P5.2a-warm-generalization, P5.12-bankv21-recal
- **Sin prueba posible, 0 pares discordantes (26):** P1-S1.2-zeroshot-smolvlm, P1-S3.4-coco-to-aerial-domain-shift, P1-S1.3-phaseB-control-stack, P2-RQ0.3-spine-selection, P2-RQ1.1-dataset-well-posedness, P3-wholeframe-resolution-knee, P3-ROI-drift-robustness, P3-E1-TRT-fps, P3-E1-TRT-mask-parity, P3-T1-memoryless-baseline, P3-T0a-anchor-cadence, P3-T4a-tracker-cost, E20-acquire-latency, E17-reground-chase, E14-identity-hole, E13-colour-gate, E9-retarget-switch, E10-fast-follow-ceiling, P5.2b-speed-sweep, P5.9-kerbsafe-scenebank, P5.10-simbank-select, P5.19-wsel-no-regression, P5.19-grace-precision, P5.20-replication-of-P5.19, P6.0-flight-rig-gate, P6.1-carla-renderer
- **Diseño incapaz de alcanzar alpha (33):** P1-S1.2-zeroshot-smolvlm, P1-S3.4-coco-to-aerial-domain-shift, P1-S1.3-phaseB-control-stack, P2-RQ0.3-spine-selection, P2-RQ1.1-dataset-well-posedness, P3-wholeframe-resolution-knee, P3-ROI-drift-robustness, P3-E1-TRT-fps, P3-E1-TRT-mask-parity, P3-T1-memoryless-baseline, P3-T0a-anchor-cadence, P3-T4a-tracker-cost, E18-A-vs-gate, E20-acquire-latency, E22-cv-prior-phase0, E16-relock-replication, E17-reground-chase, E14-identity-hole, E13-colour-gate, E9-retarget-switch, E10-fast-follow-ceiling, P5.2b-speed-sweep, P5.3-multi-candidate-select, P5.4-crop-select, P5.5-select-generalization, P5.9-kerbsafe-scenebank, P5.14-wsel, P5.14-swap, P5.14-shadow-rg-disagreement, P5.16-autodisc-wsel, P5.19-grace-precision, P6.0-flight-rig-gate, P6.1-carla-renderer
- **Sin datos crudos, en cola de re-ejecución (3):** P1-S1.4-phaseC-vlm-closed-loop, P3-T2-permanence-reid, P3-T3-closedloop-coverage

## Salvedades por afirmación

Las 65 afirmaciones con salvedad registrada, **literales**
desde `thesis/claims.json`. Una salvedad limita lo que su fila de la tabla
puede sostener: léase junto al valor p, nunca en su lugar. Varias retiran
por completo la lectura ingenua del número.

**P1-S1.2-zeroshot-smolvlm** — Both arms are floor-pinned at 0 successes, so a paired test between them is degenerate (b=c=0). The Wilson interval on 0/50 is the whole content: [0, 0.071]. That is enough to justify abandoning the spine and is the correct way to state it.

**P1-S2.1-stage2-mode-collapse** — 2/200 against a 30% gate is so far below that no clustering correction could change the verdict. The 'mode collapse' DIAGNOSIS, however, rests on 5 hand-inspected predictions and is not itself a measured claim.

**P1-S3.3-export-parity-catastrophe** — The HF arm has NO per-item file, so b and c are not directly recoverable. They are BOUNDED instead: the marginals fix b - c = 30, which leaves c in [0, 15]. The WORST case for significance is c=15, b=45, and that still gives p = 1.3e-04. The b/c stored here are that worst case, so the reported p is an upper bound and the catastrophe is significant under every pairing consistent with the data. This is the strongest single result in Part I.

**P1-S3.3-quantisation-is-not-the-cost** — Computed here for the first time: b=17, c=10, p=0.248. The fidelity loss is in the EXPORT, not in the 8-bit quantisation. Any thesis sentence attributing part of the drop to Q8_0 must be softened.

**P1-S3.4-coco-to-aerial-domain-shift** — Pre-registered as descriptive with no bar. The 95% interval on 1/50 is roughly [0.001, 0.106], so '2.0% is at the random-guess floor' is not a statement the data can carry - only 'at most about 10%' is.

**P1-S4.1-stage4-narrow-miss** — The most instructive gate in Part I. 39/200 vs a 40/200 threshold is within one Bernoulli draw, and the 95% Wilson interval [0.146, 0.257] straddles 20% comfortably. The data cannot distinguish 'missed' from 'met'. The recorded NARROW MISS is a defensible engineering decision and an indefensible statistical one; the thesis must present it as the former.

**P1-S1.3-phaseB-control-stack** — A capability gate, not a sampled measurement. 3/3 on one scenario shows the stack CAN close the loop; it says nothing about a rate over scenarios. The frame count must never be used as n.

**P1-S1.4-phaseC-vlm-closed-loop** — 13 phase-c CSVs with full per-frame columns exist and were deliberately NOT extracted: the input pixels were a blank sky frame (gz camera pitch +pi/2 is DOWN, not up). Extracting them would produce well-formed numbers about nothing. This is the repo's own motivating case for the 'look at it' rule.

**P2-RQ0.3-spine-selection** — The spine decision ALSO rests on an export-fidelity comparison of -2 pp (Qwen) vs -16 pp (SmolVLM). The -2 pp figure is 15/100 vs 14/100 - a ONE-ITEM difference presented as a fidelity property. That leg of the argument is not supported; the 15/100 vs 0/100 leg is.

**P2-RQ1.1-dataset-well-posedness** — No test is appropriate: this is a complete enumeration, so a confidence interval would be a category error. Its inferential weight is downstream - this same 439 is the evaluation set for EVERY Part II number, which is why the 316-unique-images clustering propagates through the whole part.

**P2-RQ2.1-resolution-ladder-1024** — The gate clears with a wide margin, so the image clustering does not threaten the verdict. The 'elbow' in RQ-2.3 has no numeric bar and is an eyeballed judgement - it should be presented as a design choice, not a finding.

**P2-RQ3.1-lora-aerial-gate** — 261 is the only integer consistent with the rounded 0.595 and is corroborated by the eval log's running gate_hits (260 at i=435). Margin over the gate is enormous; clustering cannot touch the verdict.

**P2-RQ4.1-deploy-fidelity** — The headline Part II number. The runtime arms (F16 273, Q8_0 275) sit ABOVE the HF reference (261), which the ledger reads as a fidelity win; on these marginals that 14-item difference is within what the pairing could produce by chance, so the defensible claim is 'no measurable export loss', not 'the export improved it'.

**P3-wholeframe-resolution-knee** — No numeric gate was pre-registered - a characterisation sweep whose job was to establish the baseline the ROI lever is measured against. Four n=6 SMOKE runs sit in the same runs/ directory and must not be confused with the n=439 arms.

**P3-ROI-M2.0-512** — Counts were reconstructed from stored rates and land exactly on integers, so they are exact. The gate is cleared with a huge margin and survives any plausible clustering correction. The SELECTION of M=2.0 @512 as the peak over M=1.5 @512 (368/439) is a 6-item difference on shared items and should be presented as 'a plateau, we took a point on it'.

**P3-ROI-drift-robustness** — No pre-registered numeric bar. Because the drift direction is one draw, the shift-level numbers carry sampling error in the PERTURBATION as well as in the items, and only the first is quantified. Worst level (1.0, M=2.0) still clears the 62.6% baseline, which is the honest form of the claim.

**P3-SR-swin2sr-accuracy** — CORRECTS A RECORDED CONCLUSION. Discordants computed here for the first time: lanczos vs swin2sr b=21 c=14 p=0.31; bicubic vs swin2sr b=22 c=12 p=0.12; bicubic vs native p=0.26. NO accuracy difference in this probe is significant. The rejection is correct but must be justified on LATENCY (+1331 ms per crop, deterministic and enormous), not on accuracy. Any sentence saying Swin2SR 'loses' on IoU is unsupported; the supported sentence is that it buys nothing measurable for 1.3 s.

**P3-carry-OP768-accuracy** — A sign test on the per-track paired comparison: 1024 beats 768 on 55 tracks, 768 beats 1024 on 31, 100 ties. Exact p = 0.014, so 1024 IS significantly more accurate than 768. The adoption of 768 was never a claim of equality - the frozen rule was an EFFECT-SIZE bar (within 5 pp of the 1024 reference) plus an FPS constraint. The thesis must state it that way: 768 was chosen despite a real, small, detectable accuracy cost.

**P3-E1-TRT-fps** — No interval is computable and none should be quoted. Frames inside one session share thermal state and clock governor state. The claim is defensible as a capability demonstration on this device in this session, which is what an edge-deployment thesis needs; it is not defensible as an expected rate.

**P3-E1-TRT-mask-parity** — A numerical-equivalence check, not a sampled accuracy claim, and it is the right kind of evidence for what it is asked to show: fp16 export did not change the arithmetic. Quoting '100 frames' as n would be pseudo-replication of the clearest kind.

**P3-T1-memoryless-baseline** — No threshold was pre-registered; T1 was a harness deliverable. Its numbers are the reference the re-ID arm is compared against, and only ONE of the two clips can discriminate at all.

**P3-T2-permanence-reid** — NO RAW FILE ON DISK - the numbers survive only in the README and the ledger. Even if recovered, the entire PASS rests on a single scripted clip in which one ID switch either happens or does not: one Bernoulli draw, no interval, no test.

**P3-T3-closedloop-coverage** — THE MOST OVERSTATED n IN THE REPOSITORY. No file on disk; README prose only. Frame-fraction differences from single flights must never be reported as if they had sampling error over flights.

**P3-T0a-anchor-cadence** — The comparison that matters (2.26 s vs 1.5 s) is a ratio of two deterministic quantities with a min-max spread of 1.3 ms over 8 reps. No test is needed or possible; the architectural conclusion follows from the magnitudes.

**P3-T4a-tracker-cost** — Pseudo-replication that does not matter: the claim clears its budget by two orders of magnitude, so no dependence correction could reverse it. Worth stating explicitly rather than silently quoting n=1180.

**E18-cold-acquire-vs-warm-oracle** — THE NUMBER THAT LAUNCHED PART V, and it lands at p = 0.0625 - just outside alpha, because n=6 needs ALL SIX pairs to flip and only five did. The effect is almost certainly real (the mechanism is a measured 4.85 s delivery lag, not a coin flip) but the EXPERIMENT could not certify it. Six clips was one clip too few.

**E18-A-vs-gate** — The failure direction is what a 6-item design CAN establish: 1/6 against a 2/3 rate has a one-sided p of 0.10. Still not alpha, but the descriptive gap is large and the mechanism is understood.

**E20-operator-crop-hint** — Exactly TWO discordant pairs carry the entire claim: p = 0.50. The PASS-rate half of E20 is not evidence. The LATENCY half is a different matter - see E20-acquire-latency - and that is the half the Part IV narrative should rest on.

**E20-acquire-latency** — No confidence interval should ever be put on this. It is a deterministic cost model, not a noisy sample, and the honest presentation is the mechanism (fewer prefill tokens) plus the two medians. A 2.6x latency reduction with a known cause needs no p-value; claiming one would be false precision.

**E19-motion-compensated-acquire** — ONE discordant pair: p = 1.0. The BUF arm is statistically vacuous against the E18-A baseline - b=0, c=0, McNemar undefined. Neither arm is evidence of anything; both are correctly recorded as failures to reach the gate, which is a different and weaker statement than 'motion compensation does not work'.

**E21-coarse-to-fine** — Paired against E20's cell arm: b=2, c=0, p=0.50. The supporting mechanism is stronger than the outcome count: the coarse cell-vote itself only hits 2/6, so the automation fails at a measurable intermediate step rather than mysteriously.

**E22-cv-prior-phase0** — The right kind of cheap pre-gate: it killed a matrix before it was run. The two t=10 s abstentions are structurally correlated (same failure mechanism), so even 6 is generous.

**E23-tolerant-cells** — b=0, c=2 against E20's cell arm: p=0.50. The stronger evidence here is the OFFLINE containment sweep - worst-case containment at HW*=0.38 holds on 6/6 clips and 19/19 phrasings - which is a deterministic geometric computation and needs no inference. The device regression closes the arc; the containment sweep explains why widening cannot help.

**E16-relock-replication** — The pre-registered rule needed 7/8 for 'reliable'. That bar is UNREACHABLE statistically at n=8: even a perfect 8/8 against a 0.875 null gives p = 0.34. The QUALIFIED verdict was the right call and the Wilson interval [0.36, 0.89] is the honest summary - the true relock rate could be anywhere from a coin flip to near-certain.

**E17-reground-chase** — n=10 looks like the strongest Part IV sample and is the weakest. Reporting the Wilson interval on 0/10 ([0, 0.28]) would imply ten independent draws; there was one. The correct claim is mechanistic - the lever does not apply to this code path - and it is well supported by the identical traces.

**E14-identity-hole** — 3/3 has a Wilson lower bound of about 0.44 even if the three were independent, and they are not. E15 then failed the same regression leg 0/1, which E16 had to be run to settle - and E16 found 6/8, i.e. the fix is real but NOT deterministic. E14 alone overstated it.

**E13-colour-gate** — A deterministic 0/3. Mechanistic claim, not probabilistic: the gate never fires on this scenario. The three regression legs passing 3/3 is what makes the negative interpretable - the change was live and did nothing.

**E9-retarget-switch** — A capability demonstration on one scenario. The colour smoke test (white 10/10, blue 10/10) is a separate and better-supported leg because it varies the input rather than repeating the run.

**E10-fast-follow-ceiling** — A threshold-finding sweep, and the deterministic repeats are actually a VIRTUE here: they establish that the boundary between 2.5 and 3.0 is a property of the controller and not of the draw. Presenting it as '3/3 vs 0/2' invites a test that would be meaningless; presenting it as a measured ceiling with four settings is correct.

**P5.1-warm-vs-cold** — p = 0.125. The first Part V YES is not statistically significant: n=6 requires all six pairs to flip and four did. The pre-registered superset condition (WARM's PASS set contains COLD's) is a stronger structural check than the count and it held - that, plus the exact match with the oracle, is the defensible form of the claim. P5.2 is what actually certifies it.

**P5.2a-warm-generalization** — THE BEST-POWERED RESULT IN PART V AND THE ONE THE THESIS SHOULD LEAD WITH. b=16, c=0, exact McNemar p = 3.05e-05, and it survives Holm correction across the whole family. 16 clips flip from fail to pass and not one flips back. This is the warm-start claim, properly certified.

**P5.2b-speed-sweep** — A pre-registered directional hypothesis (rho > 0 required) that came out at rho = -0.06, whose two-sided p at n=25 is around 0.78 - i.e. no association whatsoever, not a weak one. This is a genuine negative and it MATTERS: it says the warm-start win is delivery-lag removal, not motion compensation. A null that reshapes the mechanism is worth more than most of the positives here.

**P5.3-multi-candidate-select** — THE PRE-REGISTERED GATE WAS STATISTICALLY UNREACHABLE. Against a 0.8 null even a perfect 5/5 gives p = 0.33, so no possible outcome of this design could have cleared 4/5 in any inferential sense. The NO is a legitimate engineering stop; it is not evidence that select-on-command does not work.

**P5.4-crop-select** — The README discloses a PILOT BIAS: 3 of the 5 verdict scenes were used in the pilot. Combined with the unreachable gate this cell is uninformative about select accuracy. The LATENCY leg (4.9 s -> 2.08 s) is deterministic and stands on its own.

**P5.5-select-generalization** — Third consecutive select NO on a design whose gate no outcome could clear. The genuinely informative content is diagnostic, not inferential: the idle re-anchor fired and was accepted on all 16 cells, and two carry-drift NO_MATCH failures survived it. That is a mechanism, and it is what motivated the delivery-contract change.

**P5.9-kerbsafe-scenebank** — A build gate, correctly treated as one. 12/12 has a Wilson interval of [0.76, 1.0] - the generator is good, not proven perfect. All 12 cells come from one generator with one asset set, so this measures the artifact, not a scene population.

**P5.10-simbank-select** — ZERO discordant pairs: McNemar is UNDEFINED, not 1.0. This campaign did not find the arms equal; it ran no test. Both arms are at ceiling, so the design had no room to separate anything - which is exactly what the ledger's 'scene-bound' diagnosis says, and the statistics agree.

**P5.12-bankv21-recal** — THE MOST IMPORTANT CAVEAT IN PART V's SIM ARC. The improvement is partly DEFINITIONAL: the floors (G6c 60 -> 40, G8b 0.55 -> 0.40) were recalibrated from P5.11's own recorded population. Lowering a threshold and then reporting that more cells clear it is not an effect. What IS legitimate is that the floors were frozen BEFORE the run and 6 unseen seeds also cleared, and that the offline clear-frame prediction delta was 0 on all 12. Present it as a calibration correction, never as a 4x improvement.

**P5.13-dd-vs-rg-tie** — ONE discordant pair: p = 1.0 two-sided. The pre-registered SEP_MARGIN of 4 was itself below the minimum detectable effect - reaching alpha needed 6 one-way discordants. And DD sits at 24/24, so the observable range of DD-RG is bounded above by RG's single failure. 'The contracts are equivalent' is not supported; 'this design had no power to distinguish them' is.

**P5.14-wsel** — 5/5 against a 0.8 null gives p = 0.33 - the gate could not be cleared inferentially at this n. P5.18 later re-ran this claim at n=26 and found the true WSEL rate near 0.85, which is consistent with 5/5 and correctly less exciting. Cite P5.18, not P5.14.

**P5.14-swap** — 4/5 against 0.8 is p = 0.74 - literally what the null predicts. P5.18 found the true SWAP rate at 0.65 (17/26), so this cell was small-n optimism and the repo's own later work says so.

**P5.14-shadow-rg-disagreement** — p = 0.25. All three disagreements are RG returning NO_MATCH - it failed to select at all, rather than selecting differently. That asymmetry is more informative than the count: on real imagery the re-ground contract does not merely lose, it abstains. Contrast with the sim banks (P5.10/13/17) where RG grounds nearly everything - the difference is real-imagery fragility.

**P5.15-plain-carry-survival** — 24/25 against the pre-registered floor of 18/25 gives an exact one-sided p of 0.0016, and the Wilson interval is [0.80, 0.99]. THIS IS A PROPERLY CERTIFIED RESULT and it is load-bearing: the carry is not the fragile part, which redirects the whole failure analysis onto delivery and selection.

**P5.15-maint-vs-plain** — p = 0.625. The regression is NOT statistically established, and the honest statement is that maintenance bought nothing measurable while costing compute. The mechanism (100/100 re-anchors accepted with no IoU floor, causing same-class identity swaps) is diagnostic evidence that a 25-clip count cannot supply, and it is why removing the lever was still correct.

**P5.16-autodisc-wsel** — The IMPORTANT number in P5.16 is not the 4/5 - it is 24/24 idle-window VLM discoveries accepted, which makes the pipeline GT-free end-to-end. That is a capability claim with a clean denominator; the select rate at n=5 is not.

**P5.18-n25-wsel** — 22/26 = 0.846 against a 0.8 bar: exact p = 0.37, so it clears DESCRIPTIVELY but not inferentially. The Wilson interval [0.67, 0.94] contains the gate. The right sentence is 'consistent with the pre-registered rate', not 'exceeds it'.

**P5.18-n25-swap** — THE MOST VALUABLE RESULT IN THE STATISTICAL RE-ANALYSIS. On the 5 shared cells P5.18 reproduces P5.16 EXACTLY (4/5, zero flips); the entire overturn comes from the 21 new cells, where SWAP is 13/21 = 0.62. This is a direct, measured demonstration that the small-n verdicts were optimistic - and it is the repo catching its own error, which is the strongest form the thesis can present.

**P5.19-swap-late-entry-rescue** — b=3, c=0, p = 0.25. THE BAR-EXACT YES IS NOT SIGNIFICANT. Three cells flip fail-to-pass and none flip back, which is the right SHAPE for a real fix, but three is half of the six one-way flips alpha would require at this n. The supporting mechanism is strong (P5.18's guard was frame-misaligned and fired 0/108 times; grace delivery costs 0.37-0.60 s against 4.68 s cold) and P5.20 independently reproduced arm T cell-for-cell. Present as: a mechanically-explained improvement of the right sign, not yet certified.

**P5.19-wsel-no-regression** — Zero discordant pairs, so no test exists. Here the tie is the DESIRED outcome and its interpretation is safe in a way P5.10's is not: not one of 26 cells changed state, which bounds any regression tightly even without a p-value. State it as 'no cell changed', never as 'proved harmless'.

**P5.19-grace-precision** — The Wilson interval on 2/4 is [0.15, 0.85] - this measurement carries essentially no information about the true precision. It is recorded as an open residual and that is the only defensible use. What matters qualitatively is the FAILURE MODE: the wrong firings deliver a confident box instead of abstaining, which is the dangerous direction for an operator-facing system.

**P5.20-carry-capacity** — b=0, c=1: p = 1.0. Not evidence that capacity does not help - evidence that this design saw no effect either way. What makes 'dead lever' defensible is not the count but the MECHANISM: the same car-family drift block appears in both arms, so the failures are not capacity-limited. A larger n would have to be justified by a plausible mechanism, and none survives.

**P5.20-replication-of-P5.19** — Zero discordants, so formally no test - but this is the most valuable 'undefined' in the registry. An independent re-run reproducing all 52 cells exactly establishes that the P5.19 measurement is stable and not a lucky draw. It certifies REPEATABILITY, which is a different property from significance and one the thesis should claim explicitly because most campaigns here cannot.

**P5.17-dd-vs-rg-tie-n56** — THE CLEAREST DEMONSTRATION IN THE REPOSITORY THAT n WAS NOT THE BINDING CONSTRAINT. Going from 24 to 56 cells did not increase power, because the failure RATE fell rather than the effect appearing: b=1, c=0, p=1.0, exactly as at n=24. The pre-registered SEP_MARGIN of 7 needed RG to fail 7 cells; RG failed 1 in the whole matrix. The correct conclusion is that the simulator renders too cleanly to separate the contracts, which is a statement about the instrument, not the hypothesis.

**P6.0-flight-rig-gate** — n=1 is CORRECT here and the thesis should say why: a capability gate asks 'can this rig close the loop at all', and one demonstration answers it. The px_err improvement 64.7 -> 36.0 is a before/after on one flight and must not be quoted as an expected error. The withdrawn Phase-C Branch-1 px_err claim is the cautionary example.

**P6.1-carla-renderer** — A capability claim measured once, correctly. THE ONE NUMBER THAT MUST NOT BE CITED: slave_err = 0.000 m is vacuous - CARLA's free camera is a kinematic actor, so get_transform() returns exactly what set_transform() was just given. It measures nothing about pose-slaving fidelity.

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

