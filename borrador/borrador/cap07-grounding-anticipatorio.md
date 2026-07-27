## Grounding anticipatorio

<!-- Guion de capítulo. Cada viñeta -> un párrafo. Tablas/figuras/código ya colocados. -->

### El planteamiento anticipatorio y la tesis del capítulo

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — El problema que cierra la Parte IV.** Establecer el cuello de botella heredado: la adquisición en frío de ~4,85 s aterriza una caja obsoleta sobre objetivos en movimiento (E18, Cap. 6), y todas las automatizaciones sub-2 s fracasaron; ese retardo de entrega es lo que la Parte V ataca. Enlazar con Parte IV sin re-narrarla.
- **P2 — La premisa del cómputo libre.** La orden del operador llega a mitad de vuelo, no en el frame 0: el flujo previo a la orden es cómputo gratuito. En vez de adquirir en frío bajo presión temporal, se mantiene el objeto saliente arrastrado sobre la ventana ociosa y se selecciona al recibir la orden. Citar la reformulación `experiments/PART5-PROPOSAL-anticipatory-grounding.md`.
- **P3 — Los dos contratos en tensión.** Distinguir **mantener-y-entregar** (arrastrar el objetivo nombrado y entregar la pista ya viva) de **seleccionar-entre-candidatos** (nombrar uno de varios y vincularlo en el instante de la orden). El capítulo defiende el primero y entrega el segundo como propuesta medida, no como resultado.
- **P4 — La frase-tesis del capítulo.** Enunciar sin ambigüedad: mantener-y-entregar es **inferencial** (descansa en P5.2a, la única celda no-definicional de la Parte V que sobrevive a Holm); el refinamiento de selección **no** lo es; y el selector multi-candidato **ni siquiera cabe en la placa** (R-16, Cap. 5). Pila técnica bajo prueba: VLM Qwen2-VL-2B q8_0 desplegado [@wang2024qwen2vl] + arrastre SAM2 [@ravi2024sam2] + ByteTrack [@zhang2022bytetrack], sobre clips UAV123 [@mueller2016uav123].
- **P5 — El mapa de los cuatro hilos.** Anticipar la estructura: (i) mantener-y-entregar funciona; (ii) seleccionar es donde duele; (iii) lo que sí lo desbloqueó (el contrato de entrega directa); (iv) dónde está el límite. Más dos cierres: por qué el selector se queda en propuesta, el desvío de simulación, y un superviviente que se reporta aparte (P5.12). No se narran veinte experimentos en orden: se narran los hilos.
- **P6 — Disciplina de máquina, declarada una vez.** Advertir que casi todo número de la Parte V es `machine = ambas`: el anclaje del VLM corrió en la **Jetson Orin Nano 8 GB (15 W + jetson_clocks)** y el arrastre de SAM2 corrió en la **RTX 3090** con tope de tasa; "todo corre en la placa" es **falso**. Toda tabla que mezcle precisión-3090 con tasa-Jetson etiqueta la máquina por celda.

### Mantener y entregar funciona: lo que se defiende

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — El mecanismo, P5.1.** La semilla-VLM de la ventana ociosa + puesta-al-día de SAM2 + selección-a-la-orden aterriza **5/6** en los clips `car*` de UAV123 donde la adquisición en frío bloqueante aterriza **1/6**, e **iguala exactamente** al oráculo con semilla de verdad-terreno. McNemar exacto bilateral b=4, c=0, **p=0,125**, n efectivo 6. Verdict `YES [carry-bound]` [ver claim P5.1-warm-vs-cold] [ver Tabla McNemar].
- **P2 — Por qué P5.1 no puede ser el titular.** El p=0,125 no alcanza alfa por sí solo: con n=6 harían falta seis discordantes en una dirección y hubo cuatro. Lo que hace defendible la afirmación no es el conteo sino la **comprobación estructural de superconjunto** pre-registrada (el conjunto PASS de WARM contiene el de COLD) más la coincidencia exacta con el oráculo. La certificación la aporta P5.2. Marcar como mecanismo, no como prueba.
- **P3 — El titular, P5.2a.** Barrido de 25 clips x 5 categorías: **WARM 21/25 vs COLD 5/25**. Deflactado a **23 clips independientes**: b=15, c=0, **McNemar exacto bilateral p=6,10e-05**, y **sobrevive a Holm** por Parte (0,001282) y global (0,002258). Sin deflactar era b=16, c=0, p=3,05e-05. Es la única celda no-definicional de la Parte V que sobrevive a Holm: **el ancla estadística del capítulo** [ver claim P5.2a-warm-generalization]. Citar la cifra deflactada (invariante I2 del HANDOFF).
- **P4 — La salvedad que viaja con el titular.** De las cuatro perdidas de WARM, **dos son degeneradas**: el objetivo no está en el frame de entrega, así que el oráculo también falla. Sobre el conjunto no degenerado la cifra correcta es **21/23 = 91%**, y ese calificador debe viajar pegado a la cifra siempre.
- **P5 — Por qué gana: eliminación del retardo, no compensación de movimiento.** P5.2b: la brecha WARM-COLD es **plana en la velocidad del objetivo en pantalla** (Spearman **rho = -0,06**). Es una hipótesis direccional pre-registrada (exigia rho > 0) que salió nula. Salvedad obligatoria: el barrido **no tiene p-valor ni intervalo**, así que sostiene "no se observa dependencia de la velocidad", **no** "es plano" [ver claim P5.2b-speed-sweep]. Consecuencia mecanística: la victoria del warm-start es **eliminación del retardo de entrega**, no compensación de movimiento; el frío falla en general con independencia de la velocidad.
- **P6 — La tabla inferencial de la Parte V.** Introducir la tabla McNemar como el resumen estadístico del capítulo: solo P5.2a alcanza y sobrevive; P5.1 no por sí solo; P5.10/P5.13/P5.17 no corrieron prueba útil; P5.19 es compatible con el azar. Todos los b/c son **posteriores a la deflación** por unidad independiente (R-4).

<!-- caption: Inferencia post-hoc sobre los resultados con puerta de la Parte V, generada desde los volcados por elemento -->

| Resultado | Discordancia | McNemar exacto | Lectura |
|---|---|---|---|
| P5.1 WARM 5/6 vs COLD 1/6 | b = 4, c = 0 | p = 0,125 | No significativo por sí solo |
| P5.2a WARM 21/25 vs COLD 5/25 | b = 15, c = 0 | **p = 6,10e-5** | **El ancla estadística de la parte**; sobrevive a Holm |
| P5.10 DD 24/24 vs RG 24/24 | b = 0, c = 0 | **indefinido** | No hubo prueba, no hubo empate demostrado |
| P5.13 y P5.17 | b = 0, c = 0 | **indefinido** | La única celda discordante se colapsa al agrupar por clip |
| P5.19 SWAP 20/26 vs P5.18 17/26 | b = 2, c = 0 | p = 0,5 | Compatible con el azar |

![P5.2a titular: rejilla WARM 21/25 vs COLD 5/25 sobre cinco categorías de UAV123, un panel por clip](../experiments/2026-07-04-warm-start-generalization/proof/generalization_grid.png)

![P5.2b: la brecha WARM-COLD es plana en la velocidad del objetivo en pantalla (Spearman rho = -0,06)](../experiments/2026-07-04-warm-start-generalization/proof/gap_vs_speed.png)

> **[CLIP]** ../experiments/2026-07-04-warm-start-acquire/proof/car10_warm_vs_cold.mp4 — la caja obsoleta a 135 frames: warm-start entrega la pista viva mientras la adquisición en frío aterriza una caja caducada sobre el coche ya desplazado.

### Seleccionar entre candidatos es donde duele

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Seis intentos, agrupados por causa y no por número.** Establecer que la selección-entre-candidatos fracasó seis veces (P5.3, P5.4, P5.5, P5.10, P5.13, P5.17) y que el interés está en la **causa** de cada fallo, no en la secuencia. Introducir la tabla como el mapa de causas. Todas las celdas son `machine = ambas` (VLM en Jetson, arrastre/render en 3090); ninguna mezcla FPS con precisión.
- **P2 — Las tres primeras: puerta inalcanzable, no evidencia de que la selección no funcione.** P5.3/P5.4/P5.5 corrieron un diseño de un brazo contra un nulo 0,8 donde **incluso 5/5 da p=0,33**: ningún resultado posible podía limpiar la puerta 4/5 en sentido inferencial. Son paradas de ingeniería legítimas, no pruebas de que seleccionar no funcione [claims P5.3/P5.4/P5.5]. P5.4 además arrastra sesgo de piloto (3/5 escenas ya vistas); su única pata sólida es la latencia (adquisición 4,9 s -> 2,08 s), determinista y válida aparte.
- **P3 — P5.5 aporta el mecanismo, no la inferencia.** El re-anclaje ocioso disparó y fue aceptado en **16/16** celdas, y aun así **dos NO_MATCH por deriva de arrastre sobrevivieron** — coches de la misma clase. Ese diagnóstico, no el conteo, es lo que motivó el cambio de contrato de entrega del hilo siguiente [claim P5.5-select-generalization].
- **P4 — Las tres de simulación: empates sin prueba.** P5.10/P5.13/P5.17 empataron los contratos DD (entrega directa) y RG (re-anclaje) en el banco Gazebo. Con **0 pares discordantes** (P5.10) o **uno** (P5.13/P5.17), McNemar es indefinido o p=1,0: **no demuestran equivalencia**, solo que el banco no pudo discriminar. Se desarrollan en el desvío de simulación (7.7). Adelantar la conclusión: la ventaja del contrato bueno vive en la fragilidad ante imagen real, y un render limpio la borra.

<!-- caption: Los seis intentos de selección-entre-candidatos de la Parte V, agrupados por causa; McNemar exacto bilateral y n deflactado; Máquina = ambas en toda la tabla (VLM en Jetson, arrastre/render en RTX 3090) -->

| Resultado | Contraste (aciertos) | McNemar / n_ef | Máquina | Causa | Lectura |
|---|---|---|---|---|---|
| P5.3 multi-candidate | WSEL 3/5, SWAP 2/5 (puerta 4/5) | binomial, n_ef=4, p=0,973 | ambas | match-bound | puerta inalcanzable: incluso 5/5 da p=0,33 contra el nulo 0,8 |
| P5.4 crop-select | VSEL 3/5, VSWP 3/5 | binomial, n_ef=4, p=0,973 | ambas | match/resolution-bound | sesgo de piloto; la latencia 4,9 s -> 2,08 s se sostiene aparte |
| P5.5 select-generalization | WSEL 4/5, SWAP 3/5 | binomial, n_ef=3, p=0,896 | ambas | match/carry-bound | re-anclaje aceptado 16/16, pero 2 NO_MATCH por deriva sobreviven |
| P5.10 simbank-select | DD 24/24 vs RG 24/24 | McNemar b=0 c=0, indefinido | ambas | scene-bound | 0 discordantes: no hubo prueba, no equivalencia |
| P5.13 dd-vs-rg | DD 24/24 vs RG 23/24 | McNemar b=1 c=0, p=1,0, n_ef=15 | ambas | scene-bound | 1 discordante; defecto de orden de profundidad |
| P5.17 dd-vs-rg n=56 | DD 56/56 vs RG 55/56 | McNemar b=1 c=0, p=1,0, n_ef=41 | ambas | scene-bound | de 24 a 56 no dio potencia; discriminación sim CERRADA |

### Lo que sí lo desbloqueó: el contrato de entrega directa

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — El cambio de contrato, P5.14.** El desbloqueo no fue un modelo mayor sino cambiar **el contrato de entrega**: entregar la pista **ya arrastrada** en vez de re-anclar al recibir la orden. Primer YES de selección sobre video real: WSEL **5/5** con `acquire_s = 0,00` frente a **4,51 s** del re-anclaje [claim P5.14-wsel].
- **P2 — La salvedad definicional obligatoria.** `acquire_s = 0,00 s` es **definicional, no medido**: no hay paso de adquisición que cronometrar porque la tubería ya corría. Es válido como enunciado del contrato, pero decir "hicimos la adquisición 4,5 s más rapida" **sin** añadir que el coste se trasladó a la tubería que corre continuamente durante la espera es engañoso. Pegar esta frase al 0,00.
- **P3 — Y por qué la cifra de P5.14 no se cita.** 5/5 contra un nulo 0,8 da p=0,33: la puerta no se limpió inferencialmente a este n. P5.18 re-corrió la afirmación a n=26 y halló la tasa real cerca de 0,85 (WSEL) y 0,65 (SWAP): **se cita P5.18, no P5.14**. La celda SWAP 4/5 daba p=0,74, literalmente lo que predice el nulo [claims P5.14-wsel, P5.14-swap].
- **P4 — Quitar el oráculo de la semilla, P5.16.** Se elimina la semilla de verdad-terreno: WSEL cuesta **exactamente una celda de doce** (4/5). Pero el número que importa no es ese 4/5, sino **24/24 descubrimientos VLM de la ventana ociosa aceptados**, que hace la tubería **GT-free de extremo a extremo** — una afirmación de capacidad con denominador limpio [claim P5.16-autodisc-wsel].
- **P5 — P5.16 no es un resultado vigente.** Advertir de entrada que su 4/5 fue **derribado por P5.18** con el mismo arnés byte a byte: la tasa real es 17/26 = 0,65. Se presenta como un paso cuyos números no sobrevivieron, no como un logro. Encadena directamente con el hilo del límite.

### Dónde está el límite: el arrastre, la entrega y las palancas muertas

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — La pregunta del hilo.** Si mantener-y-entregar funciona y seleccionar duele, ¿dónde está exactamente el límite? Adelantar la respuesta: el arrastre **no** es la parte frágil (aguanta 24 s), la entrega a tamaño real deja un residuo (SWAP), y todas las palancas de capacidad y de recorte para el arrastre están **muertas**.

#### El arrastre aguanta: P5.15, P5.20 y P5.21 cierran las palancas de carry

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — El arrastre no es la parte frágil, P5.15.** Un arrastre cálido **no mantenido** sobrevive una ventana ociosa de 24 s en **24/25** clips, contra el suelo pre-registrado de 18/25 (0,72): p exacta unilateral **0,002908**. Salvedad estadística pegada: bajo Holm por Parte sube a **0,05525 — NO sobrevive**, y bajo la familia global a **0,09887, tampoco**. Registrar por qué cambió: sí sobrevivía por los pelos (0,04653) mientras la Parte V tenía m = 18; al registrarse R-36, R-38 y P5.21 el 2026-07-24 la familia creció a m = 21, el umbral de Holm se estrechó y la afirmación cayó al otro lado. Es el precio previsto de corregir por Parte, y se deja escrito porque no es intuitivo: seguir corriendo experimentos dentro de una Parte encarece retroactivamente las afirmaciones ya publicadas de esa misma Parte. Lo que se sostiene es descriptivo y sigue siendo carga útil: Wilson [0,80, 0,99], **el arrastre no es la parte frágil**, lo que redirige el análisis de fallo hacia entrega y selección. El YES inferencial de la Parte V es P5.2a, no este [claim P5.15-plain-carry-survival].
- **P2 — El re-anclaje ocioso es una regresión neta, retirado.** P5.15 también midió la palanca desplegada: PLAIN 24/25 vs MAINT 22/25 a los 16 s, b=3 c=1, **p=0,625**. La regresión **no** está establecida estadísticamente; lo honesto es que el mantenimiento no compró nada medible y costó cómputo. El mecanismo (100/100 re-anclajes aceptados sin suelo de IoU, causando intercambios de identidad entre objetos de la misma clase) es la evidencia diagnóstica que justifica retirar la palanca [claim P5.15-maint-vs-plain].
- **P3 — Un SAM2 mayor recupera cero, P5.20.** Palanca de capacidad: SAM2 hiera-small (46M) **recupera 0 celdas de selección y regresa 1** (b=0, c=1, p=1,0). No es evidencia de que la capacidad no ayude, sino de que este diseño no vio efecto en ninguna dirección; lo que hace defendible "palanca muerta" es el **mecanismo**: el mismo bloqueo de deriva entre coches de la misma familia aparece en ambos brazos [claim P5.20-carry-capacity]. "Usar un tracker más grande" es una palanca muerta.
- **P4 — La ultima palanca de carry no-de-capacidad, P5.21 (nuevo).** El re-anclaje ROI-crop + lanczos (MARGIN 2.0 / RES 512 / LANCZOS4), adoptado para el prefill de adquisición, se prueba **por primera vez como contraste de resultado de arrastre** en secuencias duras: **plain 28/34 vs ROI 26/34**, McNemar b=1, c=3, **p=0,625, dirección CONTRA ROI** (c>b). b+c=4 < el suelo de 6 discordantes: ninguna prueba alcanza alfa, Holm moot. Piloto retenido 5/8 = 0,62 (headroom real, no artefacto de banco facil). Arrastre limitado a la tasa desplegada **2,69 Hz** (R-16; stride 11) para no clavar ambos brazos al techo [claim P5.21-roi-carry].
- **P5 — El refuerzo de deriva materializado.** El fallo pre-registrado de refuerzo de deriva ocurrio: en **car10** el re-anclaje recortó alrededor de una caja ya desviada, el VLM on-device fundamentó fuera de objetivo y la pista se perdió mientras plain aguantaba (IoU 0,86). Un único acierto del lado b (car14: ROI recupera un coche pequeño que plain perdió) queda superado 3 a 1. Conclusión: **ROI se queda solo para el prefill de adquisición**; no es una mejora de arrastre. Consistente con P5.15 (el arrastre no es frágil) y P5.20 (un SAM2 mayor no recupera nada): **la ultima palanca de carry no-de-capacidad queda medida y cerrada**. Nota de máquina: la re-anclaje ROI del brazo B fundamentó en la **Jetson** (q8_0, JetsonBackend); el arrastre SAM2 corrió en la 3090; el PASS/McNemar es independiente de máquina (IoU final vs GT).

![P5.15: el arrastre cálido aguanta hasta ~24 s de espera ociosa (24/25); no es la parte frágil](../experiments/2026-07-19-carry-horizon/proof/p515_decay.png)

![P5.20: un SAM2 mayor (hiera-small, 46M) recupera 0 celdas de selección y regresa 1: palanca muerta](../experiments/2026-07-20-carry-capacity/proof/ab_counts.png)

![P5.21: el re-anclaje ROI-crop no bate al arrastre plano de SAM2 (plain 28/34 vs ROI 26/34); dispersión de IoU final por secuencia](../experiments/2026-07-23-p521-roi-carry/proof/p521_per_seq_iou.png)

![P5.21: refuerzo de deriva en car10 - recortar alrededor de una caja ya desviada lleva a perder la pista mientras plain aguanta](../experiments/2026-07-23-p521-roi-carry/proof/p521_drift_reinforcement.png)

#### El listón de la entrega a tamaño real: P5.18 y la advertencia de P5.19

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — La entrega a n real, P5.18.** Re-corrida a n=26: **WSEL 22/26 = 0,846** contra el listón 0,8 — limpia **descriptivamente** (p exacta 0,37, Wilson [0,67, 0,94] contiene la puerta), la frase correcta es "compatible con la tasa pre-registrada", no "la supera". Pero **SWAP reforzado cae a 17/26 = 0,65 y no llega** [claims P5.18-n25-wsel, P5.18-n25-swap].
- **P2 — El repositorio cazando su propio error.** El detalle más valioso del re-análisis: en las 5 celdas compartidas P5.18 reproduce P5.16 **exactamente** (4/5, cero cambios); todo el vuelco viene de las **21 celdas nuevas**, donde SWAP es 13/21 = 0,62. Demostración directa y medida de que **el 4/5 de P5.16 era optimismo de n pequeño** — la tasa real de SWAP es 0,65. Esta es la figura que obliga a poner P5.18 [ver Figura de trayectoria con Wilson].
- **P3 — El rescate de entrada tardía, P5.19.** Dedup alineado (el guardia de P5.18 estaba desalineado por frame y disparó 0/108) + entrega con gracia acotada (0,37-0,60 s vs 4,68 s en frío) voltean SWAP **17/26 -> 20/26** con cero regresión de WSEL (22/26 -> 22/26, ninguna celda cambia). b=3, c=0 [claims P5.19-swap-late-entry-rescue, P5.19-wsel-no-regressión].

> **[FIGURA POR GENERAR]** Trayectoria de la afirmación de selección de P5.14 a P5.20 CON intervalos de Wilson al 95% por punto (WSEL y SWAP), marcando el listón 0,8/0,769 y como el intervalo lo cruza en P5.18/P5.19; la figura que obliga a poner P5.18 sobre P5.14/P5.16. | fuente: runs Parte V results.json (P5.14/P5.16/P5.18/P5.19/P5.20) | script: make_proof.py

![P5.18: a n=26 el SWAP reforzado cae a 17/26 = 0,65; matriz de PASS por celda WSEL vs SWAP](../experiments/2026-07-20-n25-select/proof/pass_matrix.png)

![P5.19: SWAP 17->20/26 con la entrega con gracia; los tres pares que voltean fail->pass y ninguno al revés (pasa el listón exacto)](../experiments/2026-07-20-late-entry-rescue/proof/paired_flip.png)

##### Advertencia obligatoria sobre P5.19

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Pasa el listón exactamente, y eso no basta.** P5.19 alcanza **20/26 contra un listón de 20**. Con tres pares discordantes en una sola dirección, McNemar exacto bilateral da **p=0,25**, y el intervalo de Wilson al 95% es **[0,579, 0,890]**, que **cruza el listón de 0,769**. La mejora es compatible con el azar al tamaño usado: harían falta **seis** discordantes en la misma dirección a n=26, y hubo tres [claim P5.19-swap-late-entry-rescue].
- **P2 — La deflación borra justo el margen.** Las 26 celdas salen de **13 videoclips**. Deflactada a esa unidad la discordancia baja a b=2, c=0, **p=0,5**, y el listón 20/26 se vuelve 10/13 sobre una línea base 8/13. El p nunca fue significativo; lo que la deflación borra es el margen justo en la barra, que era precisamente el argumento del resultado.
- **P3 — Se defiende por replicación, no por p.** Se presenta como una **señal a replicar**. El argumento fuerte no es el contraste: que **P5.20 reprodujera P5.19 celda por celda, cero cambios en 52 pares**, es mejor evidencia de que el efecto es real que cualquier prueba a este n. Eso certifica **repetibilidad**, una propiedad distinta de la significancia [claim P5.20-replication-of-P5.19].
- **P4 — El peor modo de fallo: la caja confiada sobre el objeto equivocado.** La precisión de la entrega con gracia es **2/4** (Wilson [0,15, 0,85]: casi ninguna información sobre la precisión real). Lo que importa es el **modo de fallo**: cuando falla, **entrega una caja ajustada y confiada sobre el objeto equivocado** (IoU 0,679 y 0,865) en vez de abstenerse. En despliegue no hay verdad-terreno que lo detecte: es un **fallo silencioso**, el peor modo posible para algo que pilota. Falsifico además su propia predicción de "suelo de regresión ~0" [claim P5.19-grace-precisión].

### Por qué el selector se queda en propuesta, y no por una sola razon

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — La placa lo veta por arriba, R-16.** El multi-candidato **no es desplegable**: R-16 (Cap. 5) mata por OOM el segundo candidato con el anillo desplegado (`PRUNE_AFTER=100`), y el arrastre real es **2,69 Hz** en solitario a `image_size` 1024 — no los retirados 6,15 FPS — cayendo a 1,02 Hz co-residente con el VLM bajo carga con un candidato. Cerrar la puerta del hardware es necesario, pero es la versión cómoda del argumento.
- **P2 — Y por abajo, donde la memoria no ataba, sigue fallando.** En la réplica sobre la 3090 donde la memoria no ataba, la selección seguía fallando por **deriva del arrastre** y **ambigüedad referencial**: dos palancas, de capacidad (P5.20) y de latencia/recorte (P5.4), movieron **cero celdas**. El capítulo debe cerrar diciendo las dos cosas; quedarse solo con el hardware ocultaría que el selector tampoco funciona donde sí cabe.
- **P3 — El grounding NO es el cuello de botella, R-38 (nuevo).** Aislando la etapa de grounding: sobre el **mismo fotograma de la orden** el VLM desplegado fundamenta la frase-objetivo y una frase-distractor arbitraria, cada caja contra su propia GT (nunca cruzada). Resultado **simétrico**: **target 13/14 vs distractor 12/14**, McNemar b=2, c=1, **p=1,0**, n=14. El fallo de select **no vive en el grounding** [claim R-38-REG-grounding-isolation].
- **P4 — Lo que R-38 refuta y a dónde redirige el fallo.** El piloto (solo brazo distractor) dio **12/14 = 0,857**, muy por encima del 0,65 de extremo a extremo de P5.18 -> ese 0,65 **no era grounding**, confundía carry+delivery. La lectura OOD de "colapso a lo saliente" queda **refutada al mirar**: la caja del distractor cae **sobre el objeto distractor** (car9 = el pórtico de señales, car10 = un coche distante distinto, wakeboard8 = el barco), no sobre el target. Excluyendo person13 (GT de distractor mal colocada sobre suelo vacío) -> b=1/c=1, aun más simétrico. Conclusión: el fallo residual de select **se redirige aguas abajo a carry/delivery**, lo que apoya mantener-y-entregar (el grounding resuelve ambos referentes con competencia; la dificultad es **mantener** la pista). Descomposición dependiente de R-36, misma familia Holm (no se doble-cuenta).
- **P5 — El techo potenciado del negativo de select, R-36 (nuevo).** El contraste pareado mantener-vs-seleccionar a n alcanzable: **b=5, c=0, n=14, p=0,0625** (banco audit-clean). Titular = **escasez de escenas**, no una tasa: curar a mano 10 candidatos frescos de UAV123 dio **8/10 de un solo objetivo** — el encuadre "el dron sigue a un objetivo" casi nunca muestra dos candidatos co-visibles de la misma clase, así que la escena SWAP-dura apenas existe. Rama MISS pre-registrada [claim R-36-maintain-vs-select].
- **P6 — La dirección consistente que apoya la tesis.** Las tres lecturas de R-36 (n=13 b=4 c=0 p=0,125; **n=14 b=5 c=0 p=0,0625 REGISTRADA**; n=15 b=6 c=0 p=0,03125 que limpia la puerta mecanicamente pero **se retira** en la auditoria visual por descansar en una celda con GT defectuosa) comparten **c=0 en todas partes**: select **nunca gana una discordante**. Underpowered para rechazar H0, pero la dirección apoya inequivocamente **mantener-y-entregar**, no select. Es el techo honesto del negativo de selección, no una corrida fallida.

![R-38: grounding simétrico - target 13/14 vs distractor 12/14 en el mismo frame de la orden; rejilla de resultado por clip](../experiments/2026-07-23-reg-grounding-isolation/proof/reg_per_clip_outcome.png)

![R-36: UAV123 escaso en pares SWAP-duros - 8/10 candidatos curados son de un solo objetivo](../experiments/2026-07-23-r36-maintain-vs-select/proof/r36_scarcity.png)

> **[CLIP]** ../experiments/2026-07-19-realvid-dd-select/proof/p514_swap_car7_460_deliver_OFFOBJECT.png — la deriva de arrastre entre coches de la misma clase: el fotograma de entrega con la caja aterrizada FUERA del objeto, el bloqueo residual de select que R-38 redirige a carry/delivery. (Sustituye al clip `car7_460_SWAP_MC_driftNOMATCH.mp4` del esquema, que no existe.)

### El desvío de simulación: un negativo metodológico en dos páginas

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Por qué se construyó el banco.** P5.7 a P5.13 y P5.17 construyen un banco de escenas sintéticas en Gazebo [@gazebo2024harmonic] para conseguir los cruces y oclusiones que UAV123 no da. Justificar en dos párrafos, no diez: era la ruta para separar los contratos DD y RG donde el video real no ofrecía cruces.
- **P2 — Terminan en un NO por render demasiado limpio.** El VLM ancla **56 de 56 renders limpios** (P5.17), los contratos empatan siempre y el banco no discrimina. Ir de 24 a 56 celdas **no dio potencia**: cayó la tasa de fallo (RG fallo 1 de 56, el SEP_MARGIN pre-registrado pedía 7), no apareció el efecto. La discriminación sim-select queda **CERRADA**: no proponer banco v4 [claim P5.17-dd-vs-rg-tie-n56].
- **P3 — La conclusión útil es metodológica.** La ventaja del contrato bueno vive en la **fragilidad ante imagen real**, y un render limpio la borra: el VLM que ancla 56/56 renders sintéticos es el mismo cuya fragilidad ante imagen real es el residuo de select. Es un enunciado sobre el instrumento, no sobre la hipótesis.
- **P4 — El defecto que P5.13 encontro mirando.** Merece mención el defecto de **orden de profundidad**: el coche blanco era el más cercano en **0 de 300 frames** de todas las clips — profundidad constante, y ninguna puerta lo cubría. Es el caso concreto para el que se escribió la regla "mira el frame": el banco pasaba las puertas mecánicas y aun así no podía separar los contratos.

### Un superviviente que se reporta aparte: P5.12

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Un superviviente de Holm que no puede ser titular.** P5.12 **sobrevive a la corrección de Holm** — una de las ~10 pruebas de todo el registro que lo hacen — y aun así no puede encabezar nada: es la **recalibración del banco de escenas**, no un resultado de selección. Va en subsección propia justamente por eso: enterrarlo en el desvío de simulación ocultaría un superviviente; ascenderlo a la narración principal prometería algo que no entrega. Máquina: **RTX 3090** [claim P5.12-bankv21-recal].
- **P2 — Lo que dice.** El mismo generador que pasaba **3 de 12** pasa **12 de 12** tras una pantalla de admisión y dos suelos recalibrados (G6c 60 -> 40, G8b 0,55 -> 0,40), congelados antes de la ejecución, y la predicción de frame limpio fuera de línea acierta con **delta 0 en las doce**, incluidas las seis semillas no vistas.
- **P3 — La salvedad que debe viajar pegada: parcialmente definicional.** Los suelos se recalibraron a partir de la **propia población de P5.11**, así que bajar un umbral y luego reportar que más celdas lo limpian **no es un efecto**. La parte genuinamente **fuera de muestra** son las **seis semillas nuevas**, no las doce clips. Se presenta como una **corrección de calibración**, nunca como una mejora 4x, y un superviviente de Holm cuya hipótesis se ajustó a los datos que la ponen a prueba se reporta con esa frase al lado o no se reporta.

![P5.12: la recalibración de suelos de admisión lleva el mismo generador de 3/12 a 12/12; rejilla de puertas por semilla, parcialmente definicional](../experiments/2026-07-17-bankv21-recal/proof/p512_gate_grid.png)

### Síntesis: que se defiende, que se propone, que no cabe

<!-- Guion de párrafos. Sustituir cada viñeta por prosa. -->
- **P1 — Lo que se defiende, inferencialmente.** Mantener-y-entregar elimina el retardo de entrega que capaba el arco de la Parte IV, y está certificado: **P5.2a, WARM 21/25 vs COLD 5/25, p=6,10e-05 deflactado, sobrevive a Holm** — la única celda no-definicional de la Parte V que lo hace. La victoria es eliminación del retardo, no compensación de movimiento (P5.2b, rho=-0,06).
- **P2 — Lo que se propone, no se prueba.** El refinamiento de selección **no es inferencial**: los YES pequeños (P5.14/P5.16) fueron optimismo de n; P5.18 los corrige (SWAP 0,65); P5.19 pasa el listón exacto pero compatible con el azar (p=0,25) y se defiende por replicación (P5.20), con un fallo silencioso residual (gracia 2/4). R-36 lo confirma como techo underpowered que apoya mantener-y-entregar (c=0 siempre).
- **P3 — Lo que no cabe, y dónde no vive el fallo.** El selector multi-candidato **ni cabe en la placa** (R-16 OOM al segundo candidato), y donde la memoria no ataba sigue fallando por deriva de arrastre y ambigüedad referencial. R-38 aisla el grounding como **simétrico**: el fallo residual **no vive en el grounding** sino aguas abajo en carry/delivery. Las palancas de arrastre (capacidad P5.20, recorte ROI P5.21) están medidas y cerradas. El capítulo entrega la selección como propuesta medida, no como resultado.
