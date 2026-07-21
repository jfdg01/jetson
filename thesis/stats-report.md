---
title: Resultados estadisticos retroactivos
subtitle: Cada afirmacion con puerta de las Partes I-VI, re-analizada
author: Javier Francisco Dibo Gomez
comment: Generado por thesis/run_stats.py, 2026-07-21T13:17Z
locale: es
---

## Como leer esta tabla

Generada por `thesis/run_stats.py` desde `thesis/claims.json`. No se edita
a mano. El metodo y las reglas de rechazo estan en
`thesis/01-metodo-estadistico.md`.

`p` indefinido no significa 'sin efecto': significa que no hubo prueba,
casi siempre por 0 pares discordantes. `alcanzable = no` significa que el
diseno no podia llegar a alpha = 0,05 con ningun resultado posible.

<!-- caption: Re-analisis exacto de las afirmaciones con puerta, con correccion de Holm-Bonferroni -->

| Afirmacion | Parte | Diseno | n efectivo | Prueba | p | p (Holm) | Alcanzable | Lectura |
|---|---|---|---|---|---|---|---|---|
| P1-S1.2-zeroshot-smolvlm | I | single-arm-binary | 47 | Wilson CI | indefinido | — | **no** | no pre-registered gate; interval only [deflated from 0/50: see independence_note] |
| P1-S2.1-stage2-mode-collapse | I | single-arm-binary | 200 | binomial exact | 1 | 1 | si | 2/200 vs gate 0.30; needed >=72/200 for alpha=0.05 |
| P1-S3.3-export-parity-catastrophe | I | paired-binary | 100 | McNemar exact | 0.0001345 | 0.004304 | si | significant (b=45, c=15) |
| P1-S3.3-quantisation-is-not-the-cost | I | paired-binary | 100 | McNemar exact | 0.2478 | 1 | si | not significant (b=17, c=10); needed >=6 one-way discordant, had 17 |
| P1-S3.4-coco-to-aerial-domain-shift | I | single-arm-binary | 47 | Wilson CI | indefinido | — | **no** | no pre-registered gate; interval only [deflated from 1/50: see independence_note] |
| P1-S4.1-stage4-narrow-miss | I | single-arm-binary | 200 | binomial exact | 0.5981 | 1 | si | 39/200 vs gate 0.20; needed >=50/200 for alpha=0.05 |
| P1-S1.3-phaseB-control-stack | I | single-arm-binary | 1 | Wilson CI | indefinido | — | **no** | no pre-registered gate; interval only [deflated from 3/3: see independence_note] |
| P1-S1.4-phaseC-vlm-closed-loop | I | paired-binary | 0 | none | indefinido | — | **no** | NO DATA - cannot be defended; queued for re-run |
| P2-RQ0.3-spine-selection | II | single-arm-binary | 100 | Wilson CI | indefinido | — | **no** | no pre-registered gate; interval only |
| P2-RQ1.1-dataset-well-posedness | II | descriptive | 1421 | descriptive | indefinido | — | **no** | descriptive only - no hypothesis was pre-registered |
| P2-RQ2.1-resolution-ladder-1024 | II | single-arm-binary | 316 | binomial exact | 7.771e-06 | 0.0002642 | si | 133/439 vs gate 0.20; needed >=76/316 for alpha=0.05 [deflated from 133/439: see independence_note] |
| P2-RQ3.1-lora-aerial-gate | II | single-arm-binary | 316 | binomial exact | 3.679e-53 | 1.325e-51 | si | 261/439 vs gate 0.20; needed >=76/316 for alpha=0.05 [deflated from 261/439: see independence_note] |
| P2-RQ4.1-deploy-fidelity | II | single-arm-binary | 316 | binomial exact | 0.0355 | 0.9939 | si | 275/439 vs gate 0.57; needed >=197/316 for alpha=0.05 [deflated from 275/439: see independence_note] |
| P3-wholeframe-resolution-knee | III | descriptive | 316 | descriptive | indefinido | — | **no** | descriptive only - no hypothesis was pre-registered [deflated from 277/439] |
| P3-ROI-M2.0-512 | III | single-arm-binary | 316 | binomial exact | 7.235e-19 | 2.532e-17 | si | 374/439 vs gate 0.63; needed >=213/316 for alpha=0.05 [deflated from 374/439: see independence_note] |
| P3-ROI-drift-robustness | III | descriptive | 316 | descriptive | indefinido | — | **no** | descriptive only - no hypothesis was pre-registered [deflated from 326/439] |
| P3-SR-swin2sr-accuracy | III | paired-binary | 312 | McNemar exact | 0.3105 | 1 | si | not significant (b=21, c=14); needed >=6 one-way discordant, had 21 |
| P3-carry-OP768-accuracy | III | paired-binary | 93 | McNemar exact | 0.01267 | 0.3675 | si | significant (b=55, c=31) |
| P3-E1-TRT-fps | III | descriptive | 1 | descriptive | indefinido | — | **no** | descriptive only - no hypothesis was pre-registered |
| P3-E1-TRT-mask-parity | III | descriptive | 1 | descriptive | indefinido | — | **no** | descriptive only - no hypothesis was pre-registered |
| P3-T1-memoryless-baseline | III | descriptive | 1 | descriptive | indefinido | — | **no** | descriptive only - no hypothesis was pre-registered |
| P3-T2-permanence-reid | III | paired-binary | 1 | none | indefinido | — | **no** | NO DATA - cannot be defended; queued for re-run |
| P3-T3-closedloop-coverage | III | paired-binary | 1 | none | indefinido | — | **no** | NO DATA - cannot be defended; queued for re-run |
| P3-T0a-anchor-cadence | III | descriptive | 1 | descriptive | indefinido | — | **no** | descriptive only - no hypothesis was pre-registered |
| P3-T4a-tracker-cost | III | descriptive | 1 | descriptive | indefinido | — | **no** | descriptive only - no hypothesis was pre-registered |
| E18-cold-acquire-vs-warm-oracle | IV | paired-binary | 6 | McNemar exact | 0.0625 | 1 | si | not significant (b=5, c=0); needed >=6 one-way discordant, had 5 |
| E18-A-vs-gate | IV | single-arm-binary | 6 | binomial exact | 0.9986 | 1 | **no** | 1/6 vs gate 0.67; no k could have reached alpha |
| E20-operator-crop-hint | IV | paired-binary | 6 | McNemar exact | 0.5 | 1 | si | not significant (b=2, c=0); needed >=6 one-way discordant, had 2 |
| E20-acquire-latency | IV | paired-continuous | 6 | none | indefinido | — | **no** | only summary statistics survive; per-item values needed for a test |
| E19-motion-compensated-acquire | IV | paired-binary | 6 | McNemar exact | 1 | 1 | si | not significant (b=1, c=0); needed >=6 one-way discordant, had 1 |
| E21-coarse-to-fine | IV | paired-binary | 6 | McNemar exact | 0.5 | 1 | si | not significant (b=2, c=0); needed >=6 one-way discordant, had 2 |
| E22-cv-prior-phase0 | IV | single-arm-binary | 6 | binomial exact | 0.9822 | 1 | **no** | 2/6 vs gate 0.67; no k could have reached alpha |
| E23-tolerant-cells | IV | paired-binary | 6 | McNemar exact | 0.5 | 1 | si | not significant (b=0, c=2); needed >=6 one-way discordant, had 2 |
| E16-relock-replication | IV | single-arm-binary | 8 | binomial exact | 0.9327 | 1 | **no** | 6/8 vs gate 0.88; no k could have reached alpha |
| E17-reground-chase | IV | single-arm-binary | 1 | Wilson CI | indefinido | — | **no** | no pre-registered gate; interval only [deflated from 0/10: see independence_note] |
| E14-identity-hole | IV | single-arm-binary | 1 | Wilson CI | indefinido | — | **no** | no pre-registered gate; interval only [deflated from 3/3: see independence_note] |
| E13-colour-gate | IV | single-arm-binary | 1 | Wilson CI | indefinido | — | **no** | no pre-registered gate; interval only [deflated from 0/3: see independence_note] |
| E9-retarget-switch | IV | single-arm-binary | 1 | Wilson CI | indefinido | — | **no** | no pre-registered gate; interval only [deflated from 3/3: see independence_note] |
| E10-fast-follow-ceiling | IV | descriptive | 4 | descriptive | indefinido | — | **no** | descriptive only - no hypothesis was pre-registered |
| P5.1-warm-vs-cold | V | paired-binary | 6 | McNemar exact | 0.125 | 1 | si | not significant (b=4, c=0); needed >=6 one-way discordant, had 4 |
| P5.2a-warm-generalization | V | paired-binary | 23 | McNemar exact | 3.052e-05 | 0.001007 | si | significant (b=16, c=0) |
| P5.2b-speed-sweep | V | paired-continuous | 23 | none | indefinido | — | **no** | only summary statistics survive; per-item values needed for a test |
| P5.3-multi-candidate-select | V | single-arm-binary | 4 | binomial exact | 0.9728 | 1 | **no** | 3/5 vs gate 0.80; no k could have reached alpha [deflated from 3/5: see independence_note] |
| P5.4-crop-select | V | single-arm-binary | 4 | binomial exact | 0.9728 | 1 | **no** | 3/5 vs gate 0.80; no k could have reached alpha [deflated from 3/5: see independence_note] |
| P5.5-select-generalization | V | single-arm-binary | 4 | binomial exact | 0.9728 | 1 | **no** | 3/5 vs gate 0.80; no k could have reached alpha [deflated from 3/5: see independence_note] |
| P5.9-kerbsafe-scenebank | V | single-arm-binary | 15 | Wilson CI | indefinido | — | **no** | no pre-registered gate; interval only |
| P5.10-simbank-select | V | paired-binary | 12 | McNemar exact | indefinido | — | si | 0 discordant pairs - the arms are indistinguishable on this data. Not equality; absence of a test. |
| P5.12-bankv21-recal | V | unpaired-binary | 12 | Fisher exact | 0.0003365 | 0.01043 | si | 12/12 vs 3/12 (independent groups) |
| P5.13-dd-vs-rg-tie | V | paired-binary | 12 | McNemar exact | 1 | 1 | si | not significant (b=1, c=0); needed >=6 one-way discordant, had 1 |
| P5.14-wsel | V | single-arm-binary | 3 | binomial exact | 0.512 | 1 | **no** | 5/5 vs gate 0.80; no k could have reached alpha [deflated from 5/5: see independence_note] |
| P5.14-swap | V | single-arm-binary | 3 | binomial exact | 0.896 | 1 | **no** | 4/5 vs gate 0.80; no k could have reached alpha [deflated from 4/5: see independence_note] |
| P5.14-shadow-rg-disagreement | V | paired-binary | 3 | McNemar exact | 0.25 | 1 | **no** | n=3 pairs cannot reach alpha=0.05 two-sided even if every pair flipped. Design is underpowered by construction. |
| P5.15-plain-carry-survival | V | single-arm-binary | 25 | binomial exact | 0.002908 | 0.08724 | si | 24/25 vs gate 0.72; needed >=23/25 for alpha=0.05 |
| P5.15-maint-vs-plain | V | paired-binary | 25 | McNemar exact | 0.625 | 1 | si | not significant (b=3, c=1); needed >=6 one-way discordant, had 3 |
| P5.16-autodisc-wsel | V | single-arm-binary | 3 | binomial exact | 0.896 | 1 | **no** | 4/5 vs gate 0.80; no k could have reached alpha [deflated from 4/5: see independence_note] |
| P5.18-n25-wsel | V | single-arm-binary | 26 | binomial exact | 0.3833 | 1 | si | 22/26 vs gate 0.80; needed >=25/26 for alpha=0.05 |
| P5.18-n25-swap | V | single-arm-binary | 26 | binomial exact | 0.9768 | 1 | si | 17/26 vs gate 0.80; needed >=25/26 for alpha=0.05 |
| P5.19-swap-late-entry-rescue | V | paired-binary | 26 | McNemar exact | 0.25 | 1 | si | not significant (b=3, c=0); needed >=6 one-way discordant, had 3 |
| P5.19-wsel-no-regression | V | paired-binary | 26 | McNemar exact | indefinido | — | si | 0 discordant pairs - the arms are indistinguishable on this data. Not equality; absence of a test. |
| P5.19-grace-precision | V | single-arm-binary | 4 | Wilson CI | indefinido | — | **no** | no pre-registered gate; interval only |
| P5.20-carry-capacity | V | paired-binary | 26 | McNemar exact | 1 | 1 | si | not significant (b=0, c=1); needed >=6 one-way discordant, had 1 |
| P5.20-replication-of-P5.19 | V | paired-binary | 26 | McNemar exact | indefinido | — | si | 0 discordant pairs - the arms are indistinguishable on this data. Not equality; absence of a test. |
| P5.17-dd-vs-rg-tie-n56 | V | paired-binary | 28 | McNemar exact | 1 | 1 | si | not significant (b=1, c=0); needed >=6 one-way discordant, had 1 |
| P6.0-flight-rig-gate | VI | descriptive | 1 | descriptive | indefinido | — | **no** | descriptive only - no hypothesis was pre-registered |
| P6.1-carla-renderer | VI | descriptive | 1 | descriptive | indefinido | — | **no** | descriptive only - no hypothesis was pre-registered |

## Que sobrevive

- **Significativas tras correccion de Holm (6):** P1-S3.3-export-parity-catastrophe, P2-RQ2.1-resolution-ladder-1024, P2-RQ3.1-lora-aerial-gate, P3-ROI-M2.0-512, P5.2a-warm-generalization, P5.12-bankv21-recal
- **Sin prueba posible, 0 pares discordantes (26):** P1-S1.2-zeroshot-smolvlm, P1-S3.4-coco-to-aerial-domain-shift, P1-S1.3-phaseB-control-stack, P2-RQ0.3-spine-selection, P2-RQ1.1-dataset-well-posedness, P3-wholeframe-resolution-knee, P3-ROI-drift-robustness, P3-E1-TRT-fps, P3-E1-TRT-mask-parity, P3-T1-memoryless-baseline, P3-T0a-anchor-cadence, P3-T4a-tracker-cost, E20-acquire-latency, E17-reground-chase, E14-identity-hole, E13-colour-gate, E9-retarget-switch, E10-fast-follow-ceiling, P5.2b-speed-sweep, P5.9-kerbsafe-scenebank, P5.10-simbank-select, P5.19-wsel-no-regression, P5.19-grace-precision, P5.20-replication-of-P5.19, P6.0-flight-rig-gate, P6.1-carla-renderer
- **Diseno incapaz de alcanzar alpha (33):** P1-S1.2-zeroshot-smolvlm, P1-S3.4-coco-to-aerial-domain-shift, P1-S1.3-phaseB-control-stack, P2-RQ0.3-spine-selection, P2-RQ1.1-dataset-well-posedness, P3-wholeframe-resolution-knee, P3-ROI-drift-robustness, P3-E1-TRT-fps, P3-E1-TRT-mask-parity, P3-T1-memoryless-baseline, P3-T0a-anchor-cadence, P3-T4a-tracker-cost, E18-A-vs-gate, E20-acquire-latency, E22-cv-prior-phase0, E16-relock-replication, E17-reground-chase, E14-identity-hole, E13-colour-gate, E9-retarget-switch, E10-fast-follow-ceiling, P5.2b-speed-sweep, P5.3-multi-candidate-select, P5.4-crop-select, P5.5-select-generalization, P5.9-kerbsafe-scenebank, P5.14-wsel, P5.14-swap, P5.14-shadow-rg-disagreement, P5.16-autodisc-wsel, P5.19-grace-precision, P6.0-flight-rig-gate, P6.1-carla-renderer
- **Sin datos crudos, en cola de re-ejecucion (3):** P1-S1.4-phaseC-vlm-closed-loop, P3-T2-permanence-reid, P3-T3-closedloop-coverage

## Cola de re-ejecucion

Afirmaciones cuyos datos por elemento no sobreviven. No se defienden en
el TFM hasta que se re-ejecuten.

<!-- caption: Trabajo de re-ejecucion necesario para hacer defendible cada afirmacion sin datos -->

| Afirmacion | Que falta | Coste | Comando |
|---|---|---|---|
| P1-S1.4-phaseC-vlm-closed-loop | valid pixels - the whole measurement is invalid at source | superseded; the CARLA rig (P6.1) is the correct place to re-ask this | `runners/run_phase_c.py with the CARLA renderer, after fixing the camera pitch` |
| P3-T2-permanence-reid | per-clip scores; only README prose survives | ~1 h on the 3090; the clips and scorer are committed | `.venv-ft/bin/python -m grounding.eval.score_clips --clips experiments/2026-06-18-t1-temporal-contract/clips --arms memoryless,reid` |
| P3-T3-closedloop-coverage | per-flight logs; README prose only | ~2 h; needs n>=10 flights per arm to say anything about a rate | `runners/run_phase_c.py --arms memoryless,reid --reps 10 (CARLA renderer)` |

## Figuras

<!-- caption: Disenos pareados por n efectivo; en rojo los que no podian alcanzar significacion con ningun resultado -->

![](proof/stats-power.png)

<!-- caption: Proporciones observadas con intervalo de Wilson al 95 %; la barra roja marca la puerta pre-registrada -->

![](proof/stats-forest.png)

