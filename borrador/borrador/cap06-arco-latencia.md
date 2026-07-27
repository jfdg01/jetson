## El arco de la latencia de adquisición

<!-- Guion de capítulo. Cada viñeta -> un párrafo. Tablas/figuras/código ya colocados. -->

### El fallo que solo aparece con el sistema integrado

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — El fallo emergente de la integración.** Establecer que, con el proceso completo NL->ground->track->fly integrado sobre vídeo real de UAV123 [@mueller2016uav123], aparece un fallo que ningún experimento por componentes veía: la adquisición en frío tarda ~4,85 s y sobre un objetivo en movimiento **la caja se entrega obsoleta**. La frase-tesis del capítulo, literal: «el sistema no falla al encontrar el objeto; falla al encontrarlo donde ya no está». Marcar este como **el capítulo pivote** (Parte IV, E2 a E23).
- **P2 — Por qué es invisible por componentes.** Explicar que cada pieza pasa en aislamiento: el grounding (Qwen2-VL-2B [@wang2024qwen2vl]) acierta en el fotograma que vio, el arrastre SAM2 [@ravi2024sam2] mantiene bien, y el seguidor ByteTrack [@zhang2022bytetrack] funciona. El fallo es una propiedad de temporización del sistema, no de un módulo: la caja es correcta para el fotograma 0 pero se entrega en el fotograma ~146, cuando el objetivo móvil ya la ha abandonado. Solo el sistema integrado lo expone.
- **P3 — El mecanismo: retardo de entrega, no exactitud.** Establecer el *binder* del capítulo: los ~4,85 s de adquisición real en la Jetson descartan **~146 fotogramas** mientras `WallClockVideo` avanza; la caja (correcta en el fotograma que vio) se entrega **obsoleta** y siembra desde ahí el arrastre. No es un fallo de exactitud del grounding, que acierta. Esta distinción —entrega frente a exactitud— es la tesis del capítulo y lo que R-34 certifica después.

### La cifra inferencial del capítulo: E18 a n = 25 (R-34)

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Reconciliación con el esquema: la cifra dejó de ser descriptiva.** Decir sin rodeos que el propio mapa del capítulo (`00-esquema.md`, §«Advertencias que acompañan a cada cifra de este capítulo») afirmaba «Ninguna cifra de este capítulo es inferencial; el capítulo se defiende por mecanismo, y la certificación llega en el capítulo 7 con P5.2a» porque E18 a n = 6 quedaba en **p = 0,0625** —justo fuera de alfa, con b = 5, c = 0, cuando el suelo bilateral exigía volcar los seis pares y solo volcaron cinco [claim E18-cold-acquire-vs-warm-oracle]. Esta sección **sustituye** esa línea: R-34 (posterior al esquema) lo cambió.
- **P2 — El diseño de R-34.** Detallar la re-ejecución con potencia: los **dos mismos brazos** que E18, onset en el fotograma 0, sobre las **25 secuencias de UAV123** de P5.2a (5 clases: coche, barco, persona, ciclista, wakeboarder), **una celda por clip** (regla R-29: n cuenta clústeres, no celdas; sin repeticiones intra-clip para inflar n). Brazo **COLD** (frío) = una pasada de grounding a fotograma completo en el fotograma 0, que bloquea ~4,85 s de tiempo de pared **real de Jetson** (`JetsonBackend`, q8_0 terse, 15 W + `jetson_clocks`), descarta ~146 fotogramas y siembra el arrastre con la caja obsoleta. Brazo **ORACLE** = SAM2 sembrado desde la caja GT del fotograma 0, sin VLM, REGROUND deshabilitado. **Etiqueta de máquina (obligatoria):** `machine = both` — el arrastre corrió en la 3090, pero la capa de anclaje en frío es tiempo de pared **real de Jetson** vía `JetsonBackend`.
- **P3 — El resultado y su certificación.** Dar las cifras exactas: **ORACLE 23/25 vs COLD 3/25; b = 21, c = 1**. Deflación R-29: solo `car3`/`car3_s` y `person1`/`person1_s` comparten vídeo de origen y ambos clústeres son internamente concordantes, así que el ICC superior 95 % = 1,0 los colapsa por completo -> **n_eff = 23** (b = 19, c = 1). **McNemar exacta: p = 1,10e-05 cruda / 4,01e-05 deflactada / 3,61e-04 Holm (Parte IV) / 1,36e-03 Holm (global)** — sobrevive a Holm por Parte y global [claim E18-cold-acquire-vs-warm-oracle-n25] [ver Tabla y Fig. rejilla-PASS].
- **P4 — Qué significa la promoción.** Enunciar el titular del capítulo: E18 pasa de «negativo sin potencia que motivó la Parte V» (p = 0,0625, n = 6) a **confirmado a n = 25**. Es el **único superviviente inferencial de la Parte IV** y el 9.º superviviente de Holm global del registro. El número que lanzó la Parte V ya se sostiene sobre inferencia, no solo sobre mecanismo.
- **P5 — El binder es entrega, no exactitud, y no se atenúa.** Cerrar el caso: COLD quedó en **3/25**, no en el ≥10/25 pre-registrado como sorpresa —en el conjunto amplio el efecto **no se atenuó, se reforzó**. La única celda a favor de COLD es `car1_s` (cobertura ORACLE 0,41 < 0,50 por **deriva del arrastre**, no una victoria del brazo frío). Corroboración independiente ya en disco: P5.2a corrió estos mismos brazos con onset a mitad de vuelo (t_p = 8 s) dando **ORACLE 22/25 vs COLD 5/25 (b = 17)** —segundo régimen de onset que concuerda, **no contado dos veces**. El retardo de entrega (~146 fotogramas) es idéntico en los tres regímenes, luego el desplazamiento de onset es inmaterial (P5.2b: efecto plano en velocidad) [ver Fig. efecto-3regímenes].
- **P6 — Verificación visual del par discordante (regla «mírala»).** Cerrar con la evidencia de píxeles: `bike1` fotograma 300 —ORACLE mantiene la caja verde sobre el ciclista (enganchada, PASS); COLD lee `LOST` con solo la caja GT roja, porque la semilla obsoleta del fotograma ~141 nunca se recuperó [ver Fig. discordante-bike1].

<!-- caption: E18-n25 (R-34): resultado pareado ORACLE vs COLD sobre 25 secuencias de UAV123, onset en el fotograma 0; carry en 3090, anclaje en frío en tiempo de pared real de Jetson (machine = both) -->
| Brazo | PASS | McNemar (crudo -> deflactado) | p exacta | tras Holm |
|---|---|---|---|---|
| **ORACLE** (seed GT fotograma 0) | **23/25** | b = 21, c = 1 -> b = 19, c = 1 (n_eff = 23) | **4,01e-05** (deflactada; 1,10e-05 cruda) | 3,61e-04 (Parte IV) / 1,36e-03 (global) |
| **COLD** (anclaje en frío ~4,85 s) | **3/25** | — | — | — |

![matriz de PASS por clip a n=25: ORACLE 23/25 vs COLD 3/25 (R-34)](../experiments/2026-07-23-e18-n25-replication/proof/pass-grid.png)

![efecto por regimen de velocidad del objetivo](../experiments/2026-07-23-e18-n25-replication/proof/effect-3regimes.png)

![celda discordante ejemplo (bike1): frío obsoleto vs oráculo fresco](../experiments/2026-07-23-e18-n25-replication/proof/discordant-bike1.png)

### Intentos de arreglarlo por la vía directa: E19-E23

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — E20: la única sub-2 s que funciona, pero no es autónoma.** Pista de recorte tomada de la frase del operador: adquisición **1,85 s**, una reducción de latencia **2,6x** frente a los 4,85 s, con causa determinista (menos tokens de prefill) y por tanto sin valor p —modelo de coste, no muestra ruidosa [claim E20-acquire-latency, «measured, not gated»]. En tasa de PASS **voltea 3/6** frente a 1/6 de la base (b = 2, c = 0, p = 0,50): la mitad de latencia es real, la mitad de tasa **no es evidencia** [claim E20-operator-crop-hint, PARTIAL hint-fragile].
- **P2 — E19: compensación de movimiento.** Adquisición con compensación de movimiento (búfer de flujo óptico): **PARTIAL [flow-fragile]**, con **un solo par discordante** (b = 1, c = 0, p = 1,0) —estadísticamente vacuo frente a la línea base E18-A; registrado como fallo en alcanzar la puerta, no como «la compensación de movimiento no funciona» [claim E19-motion-compensated-acquire].
- **P3 — E21/E22/E23: automatizar la pista, tres fracasos con causa medible.** Enumerar los tres: **E21** coarse-to-fine (segunda pasada del VLM) **NO**, b = 2, c = 0, p = 0,50, con la votación gruesa de celda acertando solo 2/6 —falla en un paso intermedio medible [claim E21-coarse-to-fine]. **E22** prior de visión clásica en CPU (Phase 0) **NO [prior-insufficient]**, mató la matriz antes de correrla con 2 abstenciones estructuralmente correlacionadas en t = 10 s [claim E22-cv-prior-phase0, `machine = rtx-3090`]. **E23** celda más ancha **NO (REGRESSIVE)**, b = 0, c = 2, p = 0,50, con el barrido de contención offline (HW* = 0,38 se mantiene en 6/6 clips y 19/19 formulaciones) que explica por qué ensanchar no puede ayudar [claim E23-tolerant-cells].
- **P4 — El arco de latencias.** Recoger la escalera cuantitativa: **4,85 s (E18 frío) -> 1,85 s (E20) -> 2,73 s (E21/E22) -> 2,80 s (E23)**, y la escalera de velocidades del objetivo. Es el eje del capítulo y hoy no tiene figura [ver Figura por generar].

> **[FIGURA POR GENERAR]** figura cuantitativa del arco de latencias (4,85 -> 1,85 -> 2,73 -> 2,80 s) y la escalera de velocidades del objetivo | fuente: runs Parte IV E18-E23 | script: make_proof.py

> **[CLIP]** ../experiments/2026-07-03-real-video-replay/proof/car9_A_vs_B.mp4 — LA figura titular de la Parte IV: la adquisición real contra su control (frío obsoleto vs fresco).

> **[CLIP]** ../experiments/2026-07-04-prompt-scoped-acquire/proof/wrong_car10_r1_wrongprobe.mp4 — fragilidad de E20: una pista espacial equivocada hace alucinar al VLM (cobertura 0,000).

### La inferencia que arrastra el resto del documento

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Cuatro intentos, tres fracasos, un éxito no autónomo.** El recuento: E19, E21, E22 y E23 fallan al automatizar la pista; E20 funciona pero exige una frase espacial correcta del operador. La conclusión **no** es «hay que optimizar más».
- **P2 — El problema está mal planteado.** El razonamiento que arrastra el resto del documento: si la orden llega en t y la respuesta en t + 4,85, ninguna optimización sobrevive a un objetivo que se mueve. Hay que cambiar **cuándo empieza** el cómputo, no cuánto dura. Eso es la Parte V.
- **P3 — El puente a la Parte V.** Anticipar la reformulación: el flujo previo a la orden (pre-prompt) es cómputo gratis; mantener los objetos salientes arrastrados sobre la ventana ociosa y **seleccionar al recibir la orden**, en vez de adquirir en frío bajo presión de tiempo. El hallazgo de retardo de entrega de E18-n25 es exactamente lo que el warm-start elimina, y P5.2a (Cap. 7) es lo que certifica esa victoria.

### Las advertencias que siguen vigentes para el arco n = 6

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — El cable: los ~4,85 s incluyen SSH y base64.** Advertir que los ~4,85 s se midieron con un PNG sin pérdidas en base64 cruzando un túnel SSH desde la estación de trabajo hasta la Jetson —sobrecarga que un despliegue con cámara a bordo no pagaría. El instrumento `transfer_ms`, construido para esta pregunta, nunca se ejecutó sobre la cifra titular de E18, y quedan **~450 ms sin atribuir** entre el `t_lock` de 4,85 s y la mediana instrumentada de 4400 ms. (Nota: la pata COLD de R-34 sí usa tiempo de pared real de Jetson vía `JetsonBackend`; el cable afecta a la descomposición de los 4,85 s, no al veredicto n = 25.)
- **P2 — El arco E19-E23 sigue siendo descriptivo/por-mecanismo.** Precisar que, salvo E18 (ya inferencial vía R-34), el resto del arco es **n = 6 clips, todas coches, un solo dataset**, con captions congeladas a mano, n = 2 repeticiones por celda, **solo percepción** (sin actuación ni vehículo en el lazo) y con el arrastre en la 3090 limitado a 6,15 Hz como sustituto del Orin —**cifra retirada por R-16**: la tasa desplegada es **2,69 Hz** a `image_size` 1024; los 6,15 Hz se midieron a 768 e son inmateriales al binder de retardo de entrega. Los veredictos son 1/6, 2/6 y 3/6 (diferencias de una sola clip); la prueba corre —McNemar exacta— pero no llega: E20/E21/E23 en p = 0,50 (2 discordantes), E19 en p = 1,0 (1 discordante).
- **P3 — E20 no es autónomo, y una pista equivocada es peor que ninguna.** Repetir el matiz clave: E20 exige una frase espacial correcta, y una pista **equivocada** envenena la plantilla de máscara (cobertura 0,000, cero recuperación). El encuadre honesto es «un rodeo con humano en el lazo que resistió tres intentos de automatización», no «una solución» [ver el clip `wrong_car10` arriba].
- **P4 — El techo de 2,5 m/s se midió contra render nadir sintético.** Advertir que el techo de seguimiento de **2,5 m/s (3,0 con chase-hold)** se midió en SITL contra un renderizador nadir sintético (textura plana, rover dibujado a 640x480), no sobre imagen real, con n = 2 o 3 por peldaño. El propio repositorio lo refuta: E11 dio PASS a 3,5 m/s con 2/2 y **E12 lo revirtió** a n = 3 [claim E10-fast-follow-ceiling, ceiling 2,5 m/s].
- **P5 — E14 no replica; E15 es NO MEDIBLE.** Cerrar las salvedades: el «3/3, agujero de identidad cerrado» de E14 [claim E14-identity-hole, YES] se convierte en **6/8 CUALIFIED y explícitamente no fiable** en la replicación E16 —la puerta pre-registrada 7/8 era estadísticamente inalcanzable a n = 8 (Wilson [0,36, 0,89]) [claim E16-relock-replication, QUALIFIED 6/8]. Matiz atenuante: **0 de 8 violaron la identidad**, así que los dos fallos son de temporización aguas arriba de la puerta, no de la puerta. Y los números de estrés de E15 quedan registrados pero **no reclamados**: falló su guarda de línea base, veredicto **NO MEDIBLE**.

### Lo que se comprime: E2-E17 en una sola tabla

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — La compresión y su condición no negociable.** Justificar el recorte: el capítulo baja de 10 a 8 páginas comprimiendo **E2 a E17** —el controlador de seguimiento, la puerta de máscara y el arco de re-anclaje— de narración a **una sola tabla**. E18-E23 se conserva entero porque motiva la Parte V. La condición es no negociable: **la tabla lleva columna de causa** (`match/carry/timing/no-medible`). Sin ella el recorte destruye evidencia, porque lo que estos experimentos aportan no es un recuento de fracasos sino su **taxonomía**. (Los legs más tempranos E2-E8 son la construcción del controlador de seguimiento y no llevan afirmación inferencial propia en el registro.)
- **P2 — Lo que la columna de causa preserva.** Señalar que un «0/3» borraría tres causas distintas: **E11 revertido por E12** es un fallo de tamaño de muestra; **E14 no replicado en E16** es un fallo de temporización aguas arriba de una puerta que nunca se violó (0/8); **E15** es un NO MEDIBLE por guarda de línea base. Esa taxonomía es el contenido, no el recuento.

<!-- caption: E2-E17 comprimido: controlador de seguimiento, puerta de mascara y arco de re-anclaje, con columna de causa obligatoria (match/carry/timing/no-medible). Etiqueta de máquina por fila -->
| ID | Qué probó | Veredicto | n | Máquina | Causa del límite |
|---|---|---|---|---|---|
| E9-retarget-switch | conmutación de re-objetivo | YES | 3/3 | ambas | — (mecanismo válido) |
| E10-fast-follow-ceiling | techo de velocidad de seguimiento | techo 2,5 m/s (3,0 chase-hold) | 4 config. | ambas | carry/control |
| E11 | seguimiento a 3,5 m/s | PASS 2/2 — revertido por E12 | 2 | SITL [VERIFICAR] | muestra (n insuficiente) |
| E12 | replicación de E11 a n = 3 | REVIERTE E11 | 3 | SITL [VERIFICAR] | muestra |
| E13-colour-gate | puerta de color | NO | 0/3 | ambas | match |
| E14-identity-hole | cierre del agujero de identidad | YES (3/3) — no replica | 3 | ambas | timing (aguas arriba) |
| E15 | prueba de estrés | NO MEDIBLE (falló guarda de línea base) | — | [VERIFICAR] | no-medible |
| E16-relock-replication | replicación de E14 | QUALIFIED 6/8 (0/8 violan identidad) | 8 | ambas | timing (aguas arriba de una puerta no violada) |
| E17-reground-chase | re-grounding + chase-hold | NO (0/10) | 10 | ambas | carry |
