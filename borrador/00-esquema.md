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

- **No había ni una sola prueba estadística en el repositorio.** Una búsqueda de `mcnemar|binomtest|scipy.stats|statsmodels|wilson|p-value` sobre todos los `.py` y `.md` devolvía cero ficheros. El único estadístico existente era un Spearman escrito a mano, sin p-valor ni intervalo. Varias afirmaciones con puerta descansaban sobre una o tres celdas de diferencia. **Resuelto el 2026-07-21**: el marco está en `grounding/stats.py`, se explica en el Cap. 3 (borrador en `thesis/01-metodo-estadistico.md`), y las afirmaciones con puerta re-analizadas están en `thesis/stats-report.md` (65 aquel día, **70** tras R-13, R-14 y R-16). El resultado de ese re-análisis está más abajo y **cambia lo que el TFM puede afirmar**.
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
- Esquema: este fichero. **Rebalanceado el 2026-07-23 (R-18)** contra la evidencia superviviente: reparto de páginas a suma cero, criterio de reparto declarado, orden de recorte con su coste declarado, y tres secciones nuevas para evidencia medida que no tenía capítulo.
- Texto: no empezado.
- Fecha límite: **sin fijar**. Es la variable que falta y la que ordena todo lo demás.

## Tesis defendida

Una sola frase, porque si no cabe en una frase no está clara:

> Cuando la orden del operador llega a mitad de vuelo y no en el instante cero, la
> ventana previa es cómputo gratuito: gastarla en mantener el objetivo vivo y
> limitarse a **entregar** la pista ya arrastrada elimina la latencia de
> adquisición que hace que un sistema de grounding sobre vídeo aéreo entregue una
> caja ya obsoleta; **seleccionar** entre varios candidatos mantenidos se queda en
> propuesta medida, porque el selector multi-candidato no cabe en un Orin Nano de
> 8 GB y, allí donde la memoria no ataba, la selección seguía fallando por deriva
> del arrastre y por ambigüedad de la expresión referencial.

**Decisión de autor (R-28, 2026-07-23).** La frase anterior defendía
«mantener + **seleccionar**» como una sola cosa demostrada. No lo está, y la
reformulación es del autor: *se intentó montar un selector y un arrastre; el
arrastre y la entrega funcionan y están certificados, el selector se quedó en
propuesta*. Lo que la evidencia sostiene y lo que no:

- **Sí, y es la única afirmación de la Parte V que sobrevive a Holm.** El brazo WARM de P5.2a *es* el sistema completo de mantener-y-entregar — semilla del VLM en la ventana previa, arrastre SAM2, entrega sin re-anclar — 21/25 frente a 5/25, p = 6,10e-05 deflactado a 23 clips, Holm 0,001831. «Ni el arrastre funcionó» sería falso contra el propio mejor resultado del proyecto.
- **La placa veta el selector, no el arrastre.** R-16 midió los dos candidatos co-residentes con el VLM en el Orin: a N = 2 con el anillo desplegado (`PRUNE_AFTER=100`) el proceso **muere por OOM**; con anillo 32 sobrevive a 0,540 Hz por candidato. La restricción vinculante es **memoria**, y aparece exactamente al segundo candidato — que es lo que un selector necesita por definición.
- **Pero el hardware no explica los fallos que sí se midieron.** Las celdas de selección corrieron en réplica sobre la 3090, donde la memoria nunca ató. P5.20 dio un SAM2 mayor gratis (26,3 frente a 26,4 min) y recuperó **0** celdas; P5.4 recortó la adquisición de 4,9 s a 2,08 s y movió el veredicto **cero celdas**. Las causas medidas son deriva del arrastre y ambigüedad referencial (P5.18, 17/26). Atribuirlo todo al hardware sería cómodo y falso.

De ahí salen tres afirmaciones subordinadas, y cada capítulo empírico existe para
sostener una de ellas:

<!-- caption: Las tres afirmaciones subordinadas, el capítulo que sostiene cada una y el límite de esa evidencia -->

| Afirmación | Cap. | Límite de la evidencia |
|---|---|---|
| Un VLM de 2B cuantizado hace grounding referencial útil sobre imagen aérea y cabe en un Orin Nano de 8 GB | 4-5 | Protocolo propio, más fácil que el benchmark publicado. La parte medida **en la placa** es el grounding de un frame (R-13, R-14); la precisión del arrastre nunca se midió allí |
| La adquisición en frío es el cuello de botella del sistema integrado, y no se arregla optimizando la adquisición | 6 | n = 6 clips, todas coches, sin vehículo en el lazo |
| Anticipar **mantener + entregar** sí lo arregla; **seleccionar** entre candidatos queda propuesto, no demostrado | 7 | Desigual, y esa es la tesis: mantener-y-entregar es inferencial (P5.2a, p = 6,10e-05, sobrevive a Holm) — el **refinamiento de la selección** no lo es, el único SÍ a n real (P5.19, 20/26) queda en p = 0,25 y en p = 0,5 al deflactar a 13 clips, y el selector multi-candidato ni siquiera cabe en la placa (R-16: OOM a N = 2) |

La Parte VI (Cap. 8) no sostiene ninguna de las tres todavía.

## Estructura propuesta

<!-- caption: Estructura de capítulos, origen del material y extensión estimada -->

| Cap. | Título | Material de origen | Págs. antes | Págs. |
|---|---|---|---|---|
| 1 | Introducción y motivación | `README.md`, propuestas de parte | 5 | 5 |
| 2 | Estado del arte | `SOURCES.md`, surveys, encuesta de datasets | 8 | 8 |
| 3 | Plataforma, método y métricas | `README.md`, `grounding/contract.py`, `01-metodo-estadistico.md`, `02-metodo-multiagente.md`, barrido de capacidad de la Parte I | 8 | **10** |
| 4 | Grounding de un solo frame | Partes I y II + R-13 | 10 | **11** |
| 5 | Permanencia de objeto | Parte III + E1 + R-14 + R-16 | 9 | **11** |
| 6 | El arco de la latencia de adquisición | Parte IV (E2-E23) | 10 | **8** |
| 7 | Grounding anticipatorio | Parte V (P5.1-P5.20) | 14 | **12** |
| 8 | Hacia el lazo cerrado | Parte VI (P6.0-P6.1) | 6 | **4** |
| 9 | Amenazas a la validez | transversal | 6 | **7** |
| 10 | Conclusiones y trabajo futuro | transversal | 4 | 4 |

Total: **80 páginas** de cuerpo, igual que antes — esto es un **reparto**, no una
ampliación. Los deltas suman cero: +2 +1 +2 −2 −2 −2 +1 = 0.

### El criterio de reparto, y por qué no es «páginas por p-valor»

El rebalanceo del 2026-07-23 no aplica la regla literal de «páginas
proporcionales a los supervivientes de Holm». Aplicada con uniformidad, esa regla
condena antes al Cap. 6 (cero supervivientes, cero significativos nominales, 14
de sus 15 afirmaciones a n efectivo <= 6) y al Cap. 8 (dos afirmaciones
descriptivas a n = 1) que al Cap. 7 — y además choca de frente con la directriz
del proyecto de que **un negativo bien medido es contenido**. Regla adoptada:

> Una página se justifica por **inferencia superviviente**, por un **negativo bien
> medido que cierra una palanca**, o por **caracterización determinista medida en
> la placa objetivo**. No se justifica por esfuerzo invertido ni por número de
> experimentos ejecutados.

Los tres movimientos que salen de ahí:

1. **Cap. 7, de 14 a 12.** Es el capítulo menos comprimido del esquema original
   (82 % de retención, frente al 35 % del Cap. 5) y descansa sobre **una sola
   prueba superviviente no definicional**, P5.2a. Baja, pero no baja a 8: son 29
   de las 76 afirmaciones del registro, doce de ellas negativos que **acotan la
   contribución** (P5.21 cierra la última palanca de carry no-de-capacidad; R-38
   aísla el grounding como simétrico, redirigiendo el fallo residual de select
   aguas abajo a carry/delivery),
   y P5.15 es el diseño mejor potenciado de la Parte V (24/25,
   n = 25, p = 0,0029) aunque no sobreviva a Holm (0,0756).
2. **Cap. 5, de 9 a 11.** Era el más comprimido del documento y es ahora el más
   fuerte en inferencia de placa: R-14 y R-16 aterrizaron después de escribirse
   este esquema.
3. **Cap. 3, de 8 a 10.** Absorbe la caracterización del dispositivo, que hoy
   tiene **cero páginas** pese a estar medida (ver más abajo).

Los agentes que inventariaron cada parte estiman 17 + 26 + 16 + 17 páginas solo
para los capítulos 4 a 7 si se contara todo, lo que confirma que el problema es de
recorte y no de material. Ese recorte ahora está declarado, no implícito: la
sección «Orden de recorte» dice qué se pierde en cada tijeretazo.

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

### Lo que la placa hace, medido (~1,5 pp) — NUEVA

La Parte I dejó un barrido de capacidad que **este esquema no colocaba en ningún
capítulo**: un `grep` de todo el documento por `tok/s`, `J/tok`, TTFT, térmica,
Gemma, Mistral o Phi no devolvía nada. Son 15 configuraciones medidas en la placa
a 15 W + `jetson_clocks` (`experiments/2026-06-13-model-capability-sweep/` y
`2026-06-14-gemma-family-sweep/`), con 84 ficheros crudos versionados.

**Enunciado exacto de la n, porque no es uniforme:** *15 configuraciones; caudal a
5 repeticiones, TTFT y potencia/térmica a una sola pasada.* Sólo `llama-bench`
corrió con `-r 5`; el TTFT es **una** llamada por modelo y la potencia es una
ventana continua de tegrastats a 1 Hz. Escribir «15 modelos x 5 repeticiones»
sería falso para tres de las cuatro familias de métrica. Además, 14 de las 15
produjeron caudal: `gemma-3-12b` **no cargó** (`cudaMalloc` al cargar, sin rescate
por descarga parcial), y ese fallo es el resultado, no una casilla vacía.

Qué se defiende con esto, y **solo** esto:

- El acantilado de los 8 GB es un **acantilado, no una pendiente**: los diez modelos Q4\_K\_M entran a `n_ctx` 4096 y el de 12B no entra en absoluto.
- **El prefill nunca es la restricción** en esta clase de carga: TTFT <= 204 ms.
- La placa está **limitada por ancho de banda en decodificación**: tg128 cae de 71,52 a 7,75 tok/s sobre una razón de 12,4x en bytes de pesos.
- **H4 queda falsificada**: se pre-registró que la energía por token tendría un óptimo en 2-3B, y sale monótonamente creciente (0,157 a 1,795 J/tok). Es un negativo pre-registrado y va con su nombre.
- Cero estrangulamiento térmico en todo el barrido.

Y qué **no** se defiende, porque sería sobrevender: estas 15 configuraciones son
LLM de **texto**, ninguna es el modelo desplegado, y **ninguna cifra de latencia
posterior de la tesis se deriva de este banco** — las de después salen del VLM
(R-14: prefill 3680 + decodificación 536 ms) y de SAM2 (R-16: 372,1 ms). Responde
a «qué LLM de texto cabe en 8 GB», que no es la pregunta que el sistema final
hace. Se cuenta como caracterización de plataforma y como el origen de la regla de
que el techo es de 15 W, no de silicio.

Cuatro defectos declarados que viajan con la sección: un único modo de potencia
(los brazos de 7 W y 25 W nunca se corrieron, luego **no hay curva de
compromiso**), la cuantización no se mantiene fija en las 15, el «±» del pp512 es
una dispersión entre agregados y no ruido de medida, y la fórmula de J/tok del
README de la campaña contradice sus propios números.

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

### El método de desarrollo, acotado

Subsección corta, con el material extenso en un **Anexo B**. Borrador completo en
`thesis/02-metodo-multiagente.md`. Se incluye porque casi todo el cuaderno lo
produjo una flota de agentes bajo revisión humana, y eso condicionó qué defectos
aparecieron y cuáles sobrevivieron meses: un lector que evalúe las cifras necesita
saberlo, igual que necesita saber el modo de potencia.

Se cuenta en las dos direcciones o no se cuenta. Encontró lo que el trabajo en
solitario no había encontrado (la auditoría de máquina sobre 76 campañas, los
cuatro números mal del `README.md`, el fallo de re-emparejamiento de ByteTrack).
Y produjo defectos con la misma firma —confiados, precisos y falsos— entre ellos
la cámara apuntando al cielo y un `b=39, c=7` salido de adivinar un esquema JSON.
La conclusión operativa es que **la verificación tiene que ser un artefacto
ejecutable y no un párrafo**: la regla «no te fíes de tu primera lectura» estaba
escrita, en mayúsculas, en el mismo fichero que contenía tres citas erróneas.

Amenaza a la validez que la propia sección declara: no hay grupo de control, luego
ninguna afirmación causal sobre el método es defendible. Solo el registro de
incidentes, y cada uno resuelve a un *commit*.

### Qué le hizo el re-análisis al cuaderno

Este es el material del Cap. 9 y conviene anticiparlo aquí, porque **el marco no
se escribió para adornar resultados sino porque cambió varios**.

<!-- caption: Resultado global del re-análisis retroactivo de las afirmaciones con puerta -->

| Categoría | N | Qué significa |
|---|---|---|
| Significativas tras Holm | 8 | Se pueden defender como efectos |
| Probadas, no significativas | 15 | Contraste real que no rechazó |
| Puerta pre-registrada **inalcanzable por diseño** | 12 | Ningún resultado posible habría bastado a esa n |
| Descriptivas, sin hipótesis | 12 | Nunca hubo nada que contrastar, por diseño |
| Sin puerta pre-registrada, sólo intervalo | 12 | Se reporta el Wilson y nada más |
| Pareadas sin un solo par discordante | 6 | Los brazos no se separaron en ninguna celda |
| Sin datos crudos | 3 | En cola de re-ejecución, no se defienden |
| Sólo sobreviven agregados | 2 | Se perdieron los valores por elemento |

Suman **70**, que es el total, porque las ocho categorías son **disjuntas**:
cada afirmación aparece exactamente una vez. Cuando dos podrían aplicar gana la
más específica — «la puerta era inalcanzable» dice algo del diseño y prevalece
sobre «la prueba no rechazó», que sólo dice algo del resultado. `run_stats.py`
las calcula y `tests/test_thesis_integrity.py` comprueba que suman el total, de
modo que la tabla no puede volver a descuadrarse en silencio.

> **Esta tabla tenía cuatro filas hasta el 2026-07-23 y sumaba 82.** Las
> categorías se solapaban: 29 afirmaciones se contaban dos veces, porque una
> pareada sin discordancia es además un diseño que no alcanza alfa. Y las dos
> filas grandes mentían sobre su contenido. «33 con 0 pares discordantes» era
> cierto de **cuatro**; el resto no eran diseños pareados siquiera. «38 diseños
> incapaces de alcanzar alfa» mezclaba **12** puertas genuinamente inalcanzables
> con 23 brazos que nunca tuvieron puerta que fallar y 12 descriptivos por
> intención. La corrección (**R-23**) no suaviza el diagnóstico: doce diseños con
> puerta que ningún resultado posible habría superado es la frase que el capítulo
> debe llevar. Es demoledora y es cierta. «38» se refuta en un minuto, y quien la
> refute deja de creerse el resto del capítulo.

Sobre las **76** afirmaciones del registro — no «76 afirmaciones con puerta»,
como decía este esquema hasta el 2026-07-23: **24 de ellas nunca tuvieron nada
que contrastar** (12 descriptivas por intención y 12 de un brazo sin puerta
pre-registrada), y ese es justamente uno de los hallazgos. Estas cifras se regeneran desde
`thesis/claims.json` y **se mueven cada vez que aterriza un brazo con puerta**:
no se citan de memoria, se leen de `thesis/stats-report.md`. El re-análisis
original del 2026-07-21 dio 6 sobre 65; R-13 y R-14 añadieron las dos
supervivientes nuevas el 2026-07-22, y ambas son de la Parte III y están medidas
**íntegramente en la Jetson**.

Las diez que sobreviven son la catástrofe de fidelidad de la Parte I, la escalera
de resolución y la puerta LoRA de la Parte II, la palanca ROI de la Parte III en
sus dos versiones —la original y la **confirmación en dispositivo a Q8\_0**
(R-14, p = 2,50e-14)—, la comparación contra el detector externo OWLv2 (R-13,
p = 2,26e-07), **el efecto de obsolescencia del anclaje frío de la Parte IV,
ahora con potencia** (R-34: `E18-...-n25`, ORACLE 23/25 vs COLD 3/25, p = 4,0e-05,
el número que lanzó la Parte V, promovido de p = 0,0625 con n=6 a confirmado con
n=25), la generalización del arranque en caliente (P5.2a), la
recalibración del banco (P5.12) y **el primer resultado de lazo cerrado de la
Parte VI** (P6.2-DELIVERY: un copter que vuela su propia salida de control, WARM
23/25 vs COLD 2/25, p = 9,5e-07, con alcance de designación por oráculo). **La
contribución central del TFM está entre ellas**, que es lo que hacía falta
comprobar.

Dos matices que hay que dar con la lista, o la lista miente por omisión. La
recalibración del banco (P5.12) sobrevive a Holm pero su propia salvedad la
llama *parcialmente definicional*: los suelos se recalibraron a partir de la
población de P5.11. Y de las ocho, solo **dos son inferenciales y de la placa a
la vez** —R-13 y R-14—, que es exactamente el flanco que el Cap. 9 declara.

Y tres correcciones que el re-análisis obliga a llevar al texto:

- **Swin2SR no pierde en precisión** (ver Cap. 5). El descarte es por latencia.
- **La catástrofe de la Parte I es la exportación, no la cuantización.** F16 contra Q8\_0 da b = 17, c = 10, p = 0,25: los 7 pp que el cuaderno atribuye al cuantizado no se distinguen del ruido. La brecha HF contra GGUF, en cambio, es significativa bajo **cualquier** emparejamiento compatible con los marginales (peor caso p = 1,3e-4), que es la forma correcta de defenderla cuando el brazo HF no dejó registro por elemento.
- **El arrastre a 768 no pierde precisión medible frente a 1024.** Por pista, 1024 gana 55 veces y 768 gana 31, p = 0,013 — pero las 186 pistas salen de 93 secuencias, y sobre esa unidad independiente la prueba de signos da b = 28, c = 16, **p = 0,096**, que Holm deja en 1. Un borrador anterior de este esquema afirmaba lo contrario (**corregido el 2026-07-21**, R-7): fue el propio re-análisis el que lo desmintió, porque las salvedades del registro se habían escrito antes de la deflación de R-4. La adopción de 768 nunca fue una afirmación de igualdad: era una cota de tamaño de efecto más una restricción de FPS, y hay que redactarla así.

### La topología real del banco

Esto es lo que más se malinterpreta al leer el cuaderno. En casi todas las
partes, **la Jetson ejecutó solo el VLM**, servido por SSH con un PNG en base64
cruzando el cable por llamada; el arrastre con SAM2, el replay de vídeo y el
scoring corrieron en una RTX 3090 de sobremesa. El capítulo debe presentar el
diagrama del banco antes de dar una sola cifra, porque de otro modo el lector
supone un sistema embarcado que nunca se midió como tal.

Aquí va **una tabla del coste del par desplegado** —VLM más arrastre, co-residentes
en la placa— y **nada más**: la medida, su descomposición y la corrección que
obliga son material del Cap. 5, donde vive la cifra que corrige (los 6,15 FPS de
E1). Se remite allí y no se repite, que es la regla del repositorio.

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

### Una línea base externa: detección de vocabulario abierto (~3,5 pp) — NUEVA

**Es la única comparación contra un sistema externo en todo el proyecto**, y es la
primera pregunta de un tribunal: ¿comparado con qué? Hasta R-13 (2026-07-22) la
respuesta no existía; todo lo demás del cuaderno es una ablación interna.

El montaje: OWLv2 [@minderer2023owlv2] fp16 contra el VLM desplegado a Q8\_0, **las
dos en el Orin**, sobre las mismas 439 muestras bien planteadas de RefDrone val y
con el mismo camino de puntuación. Cuatro brazos de detector, elegidos para **no**
montar un espantapájaros, y el registrado como titular es el más fuerte, no el más
favorable.

| Brazo | IoU@0,25 | Qué es |
|---|---|---|
| VLM desplegado | **63,10 %** | el sistema de la tesis |
| D-phrase | 47,38 % | sintagma nominal con adjetivos — el mejor brazo del detector |
| D-full | 25,74 % | la expresión referencial entera |
| D-head | 24,60 % | el núcleo nominal a secas |
| D-oracle | 90,43 % | **no es un sistema**: elige entre las diez primeras con la verdad-terreno |

Pareado y deflactado a 316 imágenes únicas, VLM contra D-phrase da p = 2,26e-07 y
**sobrevive a Holm**.

El resultado que importa no es la tasa sino la **descomposición**: el detector
propone bien y no sabe elegir. Su recall sube de 47,4 % en k = 1 a 88,8 % en
k = 10, y sólo 49 de 439 ítems (11,2 %) no tienen ninguna caja correcta entre las
diez. La distancia entre `recall@1` y `recall@10` **del mismo brazo D-phrase** es
de 41,5 pp — hay que enunciarlo así, porque puesto al lado del 90,43 % se lee como
la brecha del oráculo, que es otra cosa (27,3 pp). Su segunda propuesta ya empata
con el top-1 del VLM. Dos apoyos: el lenguaje relacional **perjudica** (D-full
está 21,6 pp por debajo de D-phrase, luego la cláusula se puntúa y arrastra el
emparejamiento fuera del objetivo), y los adjetivos de apariencia son toda la
aportación del detector (D-phrase menos D-head = 22,8 pp).

Un techo arquitectónico encontrado de paso: el codificador de texto de OWLv2 tiene
`max_position_embeddings = 16` y una consulta de 17 tokens **rompe** la pasada en
vez de degradarse. Las descripciones de RefDrone van de 7 a 27 tokens, así que 5
de 439 (1,1 %) exceden lo que el modelo puede representar.

**Y obliga a una corrección.** La campaña del 2026-06-14 cerró la bifurcación
«VLM extremo a extremo contra detector + selector» **por latencia y sin haber
medido un detector jamás**. Medido: OWLv2 es ~**16,0x más barato** por llamada
(263,5 ms de pasada contra 4216 ms de cómputo en placa del VLM) y ocupa ~5x menos.
El argumento de latencia estaba del revés. Lo que sí descarta la ruta descompuesta
es la brecha de selección, que es un argumento de **calidad**. La decisión
sobrevive; su justificación registrada, no.

Dos cautelas que van pegadas al 16,0x o la cifra miente: se compara contra
**cómputo en placa** (prefill 3680 + decodificación 536 ms) y no contra los 4319 ms
de reloj, que llevan ~103 ms de base64 por un túnel SSH — cargarle el cable al VLM
daría 16,4x, exactamente el defecto que el Cap. 6 obliga a advertir en sus «~4,85 s
incluyen cable». Y es **una pasada de detector contra un anclaje generativo
completo**: un sistema descompuesto necesitaría además la etapa de selección, que
nadie ha costeado, y si esa etapa fuese a su vez un VLM el ahorro desaparece.

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

- **Precisión:** 85,2 % IoU@0,25 — medido con pesos **HF bf16 en la RTX 3090**, no en la Jetson y no a Q8\_0. La confirmación en dispositivo estaba pre-registrada como "el único pendiente antes de cambiar el valor por defecto"; **se cerró el 2026-07-21** (R-14).
- **La cifra que ahora hay que citar como titular es la de R-14**, porque es la única que mide las dos ramas en la misma máquina y con el mismo runtime: sobre la Jetson a Q8\_0, frame completo @1024 da **63,10 %** y el recorte ROI M=2,0 @512 da **85,19 %**, es decir **+22,1 pp** pareados sobre n = 439 (b = 112, c = 15; deflactado a n efectivo = 316 imágenes únicas, **p = 2,50e-14**, sobrevive a Holm). Es una de las dos únicas afirmaciones del registro que son a la vez inferenciales y medidas por completo en la placa.
- **Delta:** el "+22,6 pp" del cuaderno comparaba 85,2 % (HF bf16, 3090) contra 62,6 % (Jetson Q8\_0, y además contra un checkpoint ya sustituido) — un compuesto entre máquinas. El control mismo-backend del barrido original era el brazo HF a frame completo, 64,0 %, que daba **+21,2 pp**. Ese era el número defendible **antes de R-14**; ahora lo es el +22,1 pp de una sola máquina y una sola cuantización, y el compuesto no debe reaparecer.
- **Latencia:** 2,7x de prefill (3691 ms a 1374 ms) frente a frame completo a 1024. La mitad de latencia sí es una medida Jetson Q8\_0.
- **Cadencia:** el anclaje a ~2,0 s no es una mejora de 3x. Frente a la constante original de frame completo a 512 (2,26 s) es marginal, porque un recorte de 512x512 lleva píxeles parecidos. La mejora real es contra la ruta desplegada a 1024: **4,81 s a 2,02 s, 2,4x**, extremo a extremo.

Y la referencia desplegada ya no es 62,6 %: el checkpoint terse mide **63,1 %** a
frame completo en la Jetson. Cualquier "+22,6 pp sobre el modelo desplegado" es
contra un modelo que ya no se despliega.

### Cifras de arrastre y de exportación

- Precisión del arrastre: 0,849 a `image_size` 1024 y 0,830 a 768, sobre 186 pistas de AerialMind — **en la 3090**. En la Jetson solo se midieron FPS y RAM. Sembrado además desde una caja de verdad-terreno del primer frame: siembra oráculo, no lenguaje.
- E1, encoder de SAM2 a TensorRT fp16 [@tensorrt]: **4,89 a 6,15 FPS en banco solo**. En el bucle integrado el mismo encoder da **5,0 FPS**, con n = 1, y despeja la puerta de >= 5 **exactamente**. El bucle pierde ~1,15 FPS en codificar/decodificar JPEG y en el túnel SSH.
- Antes de E1 la tasa co-residente era **4,1 FPS frente a la puerta de 5**: un fallo marginal registrado como tal.

### Lo que costaba de verdad el par desplegado (~1,5 pp) — NUEVA

**Este es el único sitio donde se cuenta R-16**; el Cap. 3 remite aquí. La cifra
de E1 de arriba es correcta y está mal usada, que es peor que estar mal: los
6,15 FPS se midieron con SAM2 a `image_size` **768**, y el sistema desplegado
arrastra a **1024**. Medido en la placa el 2026-07-22, el módulo desplegado da
**2,69 Hz** — una corrección de **2,30x**, que se descompone limpiamente en 1,83x
por el tamaño de imagen y 1,26x por haber perdido TensorRT en el camino. Ninguna
campaña de las Partes IV y V lo sabía: todas emularon 6,15.

Tres cosas más que salen de la misma medida y que no están en ningún otro sitio:

- **La co-residencia sí cuesta.** La Parte IV registró que no costaba FPS, medido contra un servidor **inactivo**. Con el servidor sirviendo la carga real de grounding, el arrastre paga ~2,3x y el VLM ~2x. Ambos se reparten un mismo bus de memoria y una misma iGPU; ninguno es inmune.
- **La constante desplegada no cabe.** `PRUNE_AFTER = 100` es un anillo medido en **fotogramas**, así que pasar de 768 a 1024 lo infló 1,78x en bytes sin que nadie tocara la constante. Dos candidatos más el VLM bajo carga **mueren por OOM**; a 32 el mismo trabajo sobrevive sin coste medible de tasa. No se ha aplicado: es el horizonte de memoria del arrastre, y quien lo gobierna es P5.15.
- **El arnés acertaba en lo otro.** Se sospechaba que dividir por N era optimista y es **exacto** (743,2 ms medidos contra 744,2 predichos a N = 2). Todo el error estaba en el tamaño de imagen.

Cómo se presenta, y esto importa: **no lleva p-valor ni intervalo**. Es
descriptiva, `n_efectivo = 1`, sin hipótesis pre-registrada. Su garantía no es
inferencial sino de **reproducción**: reprodujo el número publicado de E1 al
tercer decimal (6,190 contra 6,15) y repitió su propia celda entre un arranque
sucio y otro limpio. Se defiende como caracterización determinista, jamás como un
efecto medido.

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
- El arco completo E18-E23 es **n = 6 clips, todas coches, de un solo dataset**, con captions congeladas escritas a mano, n = 2 repeticiones por celda, **solo percepción** — sin actuación ni vehículo en el lazo — y con el arrastre en la 3090 limitado a 6,15 Hz como sustituto del Orin. Los veredictos son 1/6, 2/6 y 3/6: diferencias de una sola clip. La prueba **sí corre** —McNemar exacto bilateral sobre los seis pares— pero no puede llegar lejos: E18, el mejor caso del arco, vuelca cinco de los seis pares y se queda en **p = 0,0625**, porque a n = 6 el suelo bilateral exige los seis. E20, E21 y E23 quedan en p = 0,5 con dos pares discordantes, y E19 en p = 1,0 con uno. Ninguna cifra de este capítulo es inferencial; el capítulo se defiende por mecanismo, y la certificación llega en el capítulo 7 con P5.2a.
- E20 **no es autónomo**: exige que el operador dé una frase espacial correcta, y una pista **equivocada es peor que ninguna** (cobertura 0,000, plantilla de máscara envenenada, cero recuperación). El encuadre honesto es "un rodeo con humano en el lazo que resistió tres intentos de automatización", no "una solución".
- El techo de seguimiento de 2,5 m/s (3,0 con chase-hold) se midió en SITL contra un **renderizador nadir sintético** — una textura plana con un rover dibujado a 640x480 — no sobre imagen real, con n = 2 o 3 por peldaño. El propio repositorio contiene la refutación: E11 dio PASS a 3,5 m/s con 2/2 y **E12 lo revirtió** a n = 3.
- **E14 no replica.** Su "3/3, agujero de identidad cerrado" se convierte en **6/8, CUALIFICADO y explícitamente no fiable** en la replicación E16. El matiz atenuante, que merece decirse: 0 de 8 violaron la identidad, luego los dos fallos son de temporización aguas arriba de la puerta, no de la puerta.
- Los números de estrés de E15 están **registrados pero no reclamados**: falló su guarda de línea base, así que el veredicto es NO MEDIBLE.

### Lo que aquí se comprime, y con qué condición

El capítulo baja de 10 a 8 páginas comprimiendo **E2 a E17** — el trabajo de
controlador de seguimiento, la puerta de máscara y el arco de re-anclaje — de
narración a **una sola tabla**. E18 a E23 se conserva entero, porque es lo que
motiva la Parte V, y también sus seis advertencias, una a una.

La compresión tiene una condición y no es negociable: **la tabla lleva columna de
causa**. Sin ella el recorte sí destruye evidencia, porque lo que estos
experimentos aportan no es un recuento de fracasos sino su taxonomía — E11
revertido por E12 es un fallo de tamaño de muestra, E14 no replicado en E16 es un
fallo de temporización aguas arriba de una puerta que nunca se violó, y E15 es un
NO MEDIBLE por guarda de línea base. Tres causas distintas que un «0/3» borraría.

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

- **Mantener y entregar funciona, y es lo que se defiende.** P5.1 (5/6 frente a 1/6 en frío) y P5.2 (21/25 frente a 5/25 sobre 25 clips y 5 categorías). Es la única celda de la Parte V que sobrevive a Holm.
- **Seleccionar entre candidatos es donde duele.** P5.3, P5.4, P5.5, P5.10, P5.13 y P5.17: seis intentos sin separación o sin robustez, agrupados por causa y no por número.
- **Lo que sí lo desbloqueó.** P5.14 cambia el **contrato de entrega** — entregar la pista ya arrastrada en lugar de re-anclar al recibir la orden. P5.16 quita el oráculo de la semilla y cuesta una celda de doce.
- **Dónde está el límite.** P5.15 (el arrastre aguanta 24 s de espera, 24/25: **el arrastre no es la parte frágil** — descriptivo, no certificado; p = 0,002908, Holm 0,07852), P5.18 (a n = 26 el SWAP reforzado cae a 17/26), P5.19 (sube a 20/26) y P5.20 (un SAM2 mayor no recupera ninguna celda: palanca muerta).
- **Por qué el selector se queda en propuesta, y no es una sola razón.** La placa lo veta por arriba: R-16 (Cap. 5) mata por OOM el segundo candidato con el anillo desplegado, así que el multi-candidato no es desplegable. Y por abajo, en la réplica sobre la 3090 donde la memoria no ataba, la selección seguía fallando por **deriva del arrastre** y **ambigüedad referencial** — dos palancas de capacidad y de latencia (P5.20, P5.4) movieron cero celdas. El capítulo debe cerrar diciendo las dos cosas; quedarse solo con el hardware es la versión cómoda.

### El estadístico, ya calculado

Cifras generadas por `thesis/run_stats.py` desde `thesis/claims.json`, no
estimadas. McNemar **exacto bilateral**, que es el que se reporta en todo el
documento; el unilateral es la mitad y no se usa para decidir nada.

<!-- caption: Inferencia post-hoc sobre los resultados con puerta de la Parte V, generada desde los volcados por elemento -->

| Resultado | Discordancia | McNemar exacto | Lectura |
|---|---|---|---|
| P5.1 WARM 5/6 vs COLD 1/6 | b = 4, c = 0 | p = 0,125 | No significativo por sí solo |
| P5.2a WARM 21/25 vs COLD 5/25 | b = 15, c = 0 | **p = 6,10e-5** | **El ancla estadística de la parte**; sobrevive a Holm |
| P5.10 DD 24/24 vs RG 24/24 | b = 0, c = 0 | **indefinido** | No hubo prueba, no hubo empate demostrado |
| P5.13 y P5.17 | b = 0, c = 0 | **indefinido** | La única celda discordante se colapsa al agrupar por clip |
| P5.19 SWAP 20/26 vs P5.18 17/26 | b = 2, c = 0 | p = 0,5 | Compatible con el azar |

Todos los b/c de esta tabla son **posteriores a la deflación** por unidad
independiente (R-4): las cifras sin deflactar, mayores, están en
`thesis/stats-report.md` entre corchetes en cada fila, cuando difieren.

La fila de P5.1 decía `b = 2, c = 0, p = 0,5` hasta el 2026-07-23. Era un
artefacto de código, no una medida: la deflación pareada dividía dos veces las
celdas discordantes de siete afirmaciones que ya las registraban a escala de
clip (**R-22**). P5.1 tiene seis pares y seis clips, luego no hay nada que
deflactar: `b = 4, c = 0, p = 0,125`. El caveat escrito a mano en
`thesis/claims.json` llevaba la cifra correcta desde el principio, y era el
informe generado el que se contradecía a sí mismo. La conclusión no se mueve —
0,125 tampoco alcanza alfa — pero el número publicado sí.

La fila de P5.10 estaba mal agrupada en el borrador anterior de este esquema, y
la distinción importa. Sin deflactar, P5.13 y P5.17 **corrieron** una prueba que
no separó nada —una celda discordante, McNemar exacto bilateral p = 1,0—
mientras que P5.10, con cero pares discordantes en bruto, **no corrió ninguna**.
Al agrupar por clip las tres acaban en el mismo sitio, b = 0 y c = 0, y la
lectura publicada es "no hubo prueba". Reportar p = 1,0 como resultado habría
sido afirmar equivalencia demostrada, que es exactamente lo que un McNemar sin
discordancias no puede decir.

De aquí salen dos consecuencias narrativas:

- **P5.1 no puede ser el titular.** Es defendible solo porque P5.2 lo replica a n = 25 y cinco categorías. El titular es P5.2.
- **Los tres empates de simulación no demuestran equivalencia.** Con una sola celda discordante McNemar exacto bilateral da p = 1,0, y al deflactar por clip no queda ninguna: cero información en ambos casos. La afirmación correcta es "este banco no pudo discriminar los contratos", que es lo que dice el repositorio.

### Advertencia obligatoria sobre P5.19

P5.19 pasa su listón **exactamente**, 20/26 contra un listón de 20. Con tres
pares discordantes en una sola dirección, McNemar exacto bilateral da p = 0,25,
y el intervalo de Wilson al 95 % es [0,579, 0,890], que **cruza el listón de
0,769**. La mejora es compatible con el azar al tamaño de muestra usado: harían
falta **seis** pares discordantes en la misma dirección para alcanzar alfa a
n = 26, y hubo tres.

Y las 26 celdas no son 26 observaciones independientes: salen de **13 videoclips**.
Deflactada a esa unidad, la discordancia baja a b = 2, c = 0 y **p = 0,5**, y el
listón pre-registrado de 20/26 se convierte en 10/13 sobre una línea base de 8/13.
El valor p no empeora de significativo a no significativo — nunca fue significativo.
Lo que la deflación borra es el margen justo en la barra, que era precisamente el
argumento que el resultado hacía.

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
- **El arrastre nunca corrió en la Jetson en toda la Parte V**, y el presupuesto que el arnés emuló era peor de lo que nadie creía. Un borrador anterior de este esquema decía que el limitador era «~23 % optimista» comparando los 6,15 Hz del banco solo de E1 contra los 5,0 Hz del bucle integrado. **R-16 lo midió en la placa el 2026-07-22 y la cifra real es 2,30x**, no un 23 %: los 6,15 Hz se midieron con SAM2 a `image_size` 768, y el sistema desplegado corre a 1024, donde la misma placa da **2,69 Hz** (1,83x por el tamaño de imagen, 1,26x por haber perdido TensorRT). Co-residente con el VLM bajo carga real cae a 1,02 Hz con un candidato. Consecuencia concreta: `select_p53.py` muestreaba cada candidato cada 10 fotogramas a 30 fps, donde la placa permite uno cada 22 sin el VLM y uno cada 56 con él. En sentido contrario, R-16 **confirma** el otro supuesto del arnés: la división por N era exacta (743,2 ms medidos contra 744,2 predichos a N = 2), así que todo el error estaba en el tamaño de imagen.

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

### Un superviviente que se reporta aparte, y por qué (~0,5 pp)

**P5.12 sobrevive a la corrección de Holm.** Es una de las diez pruebas de todo
el registro que lo hacen, y aun así no puede ser un titular: es la recalibración
del banco de escenas, no un resultado de selección. Va en subsección propia
justamente por eso — enterrarlo dentro del párrafo del desvío de simulación
ocultaría un superviviente, y ascenderlo a la narración principal prometería algo
que no entrega.

Lo que dice: el mismo generador que pasaba 3 de 12 pasa **12 de 12** tras una
pantalla de admisión y dos suelos recalibrados, congelados antes de la ejecución,
y la predicción de frame limpio fuera de línea acierta con delta 0 en las doce,
incluidas las seis semillas no vistas.

Y la salvedad que **debe** viajar pegada: es **parcialmente definicional**. Los
suelos se recalibraron a partir de la propia población de P5.11, así que la parte
genuinamente fuera de muestra son las seis semillas nuevas, no las doce clips.
Un superviviente de Holm cuya hipótesis se ajustó a los datos que la ponen a
prueba se reporta con esa frase al lado o no se reporta.

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

- **P6.0**, puerta de capacidad: PASS. Encontró un fallo de re-emparejamiento en ByteTrack [@zhang2022bytetrack] que convertía el «coasting de Kalman» en un mantenedor de orden cero. Error de píxel 64,7 a 36,0.
- **P6.1**, cambio de renderizador: YES. 48,1 Hz —tasa del bucle de renderizado, sin percepción dentro de la ventana— con 40 vehículos autónomos siguiendo un vuelo GUIDED real (0 a 84,4 m a 60 m sobre el terreno), con la pila de control intacta.
- **Banco GT de CARLA** (2026-07-21): 25 clips, 30.000 frames con verdad-terreno por actor proyectada, puertas G-A PASS / G-B CERRADA / G-C PASS.

### Tres cifras de este capítulo que NO deben citarse

Es el capítulo con más métricas vacuas del proyecto. La auditoría R-10
(2026-07-21) las revisó una por una contra los artefactos y encontró que **la
razón que el cuaderno les atribuía era la equivocada en dos de las tres**. Esa
corrección es en sí misma contenido: una métrica se puede desautorizar por el
motivo incorrecto y seguir pareciendo bien auditada.

- **`slave_err` = 0,000 m.** La cámara es un `sensor.camera.rgb` sin `attach_to`: un actor cinemático sin dinámica, luego `get_transform()` devuelve exactamente lo que `set_transform()` le acaba de pasar. Tres matices que R-10 añade. Primero, **el 0,000 no está en el fichero**: el artefacto guarda `1,815e-06`, y el cero es el formato de impresión `:.3f`, de modo que quien busque la cifra publicada dentro del `results.json` no la encontrará. Segundo, la métrica sólo lee `.location`, así que **no compara la rotación** — y el guiñada del `pose_track` tiene **un único valor, 0,0, en los 600 ticks**, porque el sondeo `ATTITUDE` nunca entregó nada: el renderizador estaba esclavizado **en posición**, no en pose, y nadie lo vio precisamente porque la métrica es ciega a la rotación. Tercero, **sí existe un sustituto no vacuo y se calcula del artefacto ya comprometido**: los ticks que reutilizan una pose MAVLink caducada son el 60,4 %, el hueco máximo entre muestras frescas es 0,547 s y a 7,21 m/s eso son ~3,9 m de retraso de cámara en el peor caso. Es seis órdenes de magnitud mayor que la cifra publicada.
- **«0 pérdidas de pista» en P6.0.** El cuaderno lo atribuía al fallo de ByteTrack; **es falso**. El contador sólo se incrementa cuando el rastreador devuelve una lista vacía, lo que exige `MAX_LOST_FRAMES = 30` fotogramas a 20 Hz, es decir **1,5 s sin ninguna detección**, y esa rama era igual de alcanzable antes y después del arreglo. Lo que hace inútil el `0` es que la inyección a 1 Hz nunca produjo una sequía de 1,5 s, y la única ejecución diseñada para forzarla (`GAP_INJECT_RUN = 3`) nunca se lanzó. La prueba está en la propia tabla: la ejecución rota (40 IDs, 64,7 px) y la arreglada (7 IDs, 36,0 px) **reportan ambas 0**. Enunciado correcto: *0 pérdidas de pista significa que el suministro de detecciones nunca se cortó; no es evidencia de que el lazo mantuviera el objetivo.*
- **Los 48,1 Hz como tasa disponible para trabajo real.** Se midieron a 640x480, 40 vehículos, sin proyección de verdad-terreno ni escritura JPEG y **sin límite de potencia**, y sobre todo **sin percepción dentro de la ventana de medida**: ni VLM, ni SAM2, ni ByteTrack, ni PID. El banco GT, en el mismo servidor y mapa pero con 80 vehículos, proyección por actor, escritura JPEG y la GPU limitada a 200 W, sostiene **15,88 Hz**. No son comparables. Y el «2,4x la tasa de control» queda **retirado**: la ejecución fue en modo síncrono, 600 ticks de 0,05 s de tiempo simulado entregados en 12,46 s de reloj de pared, así que el simulador corrió 2,41x más rápido que el tiempo real mientras SITL, la fuente de pose, iba a reloj de pared. `48,08 / 19,93` y `30 / 12,46` son **el mismo 2,41**: la supuesta holgura era el desfase de reloj reenunciado.

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

### Lo que aquí se comprime

El capítulo baja de 6 a 4 páginas. Lo que se va es el **cómo** de la
infraestructura: la migración de renderizador Gazebo a CARLA, el detalle de la
puerta de capacidad y la construcción del banco GT pasan a un párrafo de
infraestructura habilitante más el anexo. Ninguna de esas páginas sostenía una
afirmación — P6.0 y P6.1 son puertas de capacidad a n = 1, exentas por decisión
declarada de la regla de n >= 25.

Lo que **no** se comprime, y es la mayor parte de lo que queda: las tres cifras
que no deben citarse con la auditoría R-10 que las desautoriza, la distinción
síncrono/asíncrono, y los dos fallos de abajo. En un capítulo sin resultados, lo
que tiene valor de tesis es el aparato para saber que no los hay.

### Dos fallos que merecen media página cada uno

Son aportación metodológica, no anécdota:

- **La cámara apuntaba al cielo.** Un pitch de `+pi/2` en Gazebo es **abajo**, no arriba. Durante toda una fase el log salía limpio, se escribían ficheros bien formados, y la conclusión asociada (RQ-S1.4) hubo que **retirarla**: se había medido a través de una imagen gris plana, 100 % de un solo color. Es el caso concreto que motivó la regla de verificación visual del proyecto. En trabajo de simulación, **un `exit 0` no es evidencia sobre píxeles**.
- **La métrica vacua, y el diagnóstico vacuo de la métrica vacua.** «0 pérdidas de pista» no medía nada, y el cuaderno lo desautorizó por el motivo equivocado: culpó al fallo de ByteTrack cuando el contador exigía 1,5 s sin detección alguna, algo que el arnés nunca produjo ni antes ni después del arreglo. La lección de segundo orden es la útil: **desautorizar una métrica no es lo mismo que entenderla**, y una nota de «no citar esta cifra» puede envejecer tan mal como la cifra.

## Capítulo 9 — Amenazas a la validez

Capítulo propio, no notas al pie. Estas son las que un tribunal encontraría.

### "Todo corre en la placa" no es lo que se midió

El eslogan del proyecto dice que todo corre en el borde sin nube. La realidad:
**el arrastre con SAM2 nunca se ejecutó en la Jetson en la Parte V**, y en las
partes anteriores la precisión del arrastre se midió siempre en la 3090 mientras
la placa aportaba solo FPS. Esta amenaza se **estrecha, pero no desaparece**, con
R-16 (2026-07-22): el arrastre desplegado corrió por fin en la placa, y además
co-residente con el VLM bajo carga real, pero **solo para tasa y memoria**. La
precisión del arrastre sigue sin haberse medido nunca en la Jetson. La
formulación correcta a partir de ahora es «tasa y memoria medidas en el
dispositivo; precisión del arrastre, solo en la 3090», y no «ya corre en la
placa». Lo que R-16 sí retira es la coartada opuesta: la Parte IV había
registrado que la co-residencia **no costaba FPS**, medido contra un servidor
*inactivo*; con el servidor sirviendo de verdad, el arrastre paga ~2,3x y el VLM
~2x. Y a la constante desplegada `PRUNE_AFTER = 100` no le caben dos candidatos
más el VLM en 8 GB: el núcleo mata el proceso. La única medida co-residente integrada dio 4,1 FPS
frente a su propia puerta de 5 antes de E1, y 5,0 FPS después — despejándola
exactamente, con n = 1. La formulación del `README.md` era más fuerte que la
evidencia; se corrigió el 2026-07-21 en `cd8cca6` (las tres frases «todo corre en
la placa», el compuesto de +22,6 pp, la precisión de arrastre de 1024 px citada
para un sistema que despliega 768 px, y el techo de seguimiento publicado como
3,0 m/s cuando 3,0 es el ajuste que falló).

La Parte VI **agrava** esto en lugar de resolverlo: ninguna de sus campañas tuvo
la Jetson en el lazo, porque el servidor de CARLA exige una GPU de sobremesa. El
arco de lazo cerrado se mide íntegramente en la 3090.

### Composiciones entre máquinas

Varias tablas del cuaderno emparejan una precisión medida en la 3090 con unos FPS
medidos en el Orin. Cada una de esas filas describe un sistema que nunca existió.
El TFM debe etiquetar la máquina en cada celda o separar las tablas.

### Tamaños de muestra e inferencia

Buena parte de las decisiones se tomaron con n de 2 a 6. El re-análisis del
2026-07-21 cuantifica el daño: de las **70** afirmaciones con puerta, **38 salen
de diseños que no podían alcanzar alfa = 0,05 con ningún resultado posible** y
solo **10 sobreviven a la corrección de Holm por Parte** —8 en familia global—
(eran 6 sobre 65 antes de que R-13 y R-14 aterrizaran, y 8 antes de que R-30
fijara la familia; las cifras se leen de `thesis/stats-report.md`, no de aquí). P5.18 ya lo había demostrado
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

### Una misma medida usada dos veces

De las diez afirmaciones que sobreviven a Holm, dos son **R-13** (el VLM contra
el detector de vocabulario abierto) y **R-14** (la confirmación en dispositivo del
recorte ROI), y **comparten un brazo**: el 63,10 % de IoU@0,25 del VLM sin recorte
es el mismo volcado leído dos veces, una como línea base del detector y otra como
brazo A de la rejilla ROI. La corrección de Holm supone una familia de contrastes
distintos; dos que comparten una medida no son independientes, así que el recuento
de supervivientes está por su lado optimista, aunque cada prueba por separado sea
válida. Reutilizar el volcado fue **deliberado y correcto** —volver a medir el
mismo brazo en la misma placa habría gastado horas de GPU para producir ruido—
pero hay que decirlo donde se citen los dos números juntos.

### El re-análisis es post-hoc, y la deflación es una decisión

Ninguna de las 72 afirmaciones se pre-registró con su contraste. La familia sobre
la que corre Holm se ensambló **retroactivamente**, en julio de 2026, sobre
experimentos ya ejecutados: eso protege contra la comparación múltiple, no contra
la selección del contraste una vez vistos los datos.

Y la deflación a n efectivo, que es la corrección más agresiva de todo el marco,
empezó siendo un **juicio**: agrupar por videoclip cuando dos celdas comparten
vídeo fuente es defendible, pero era una elección tomada después de existir los
datos, y otra unidad de agrupación daría otro p. R-29 (2026-07-23) cerró esa
grieta a medias y hay que decir cuál mitad: el **grado** de agrupación ya no se
elige, se mide —correlación intraclase por conglomerado, deflactando con su
límite superior al 95 %— pero **cuál es el conglomerado** sigue siendo el juicio
de antes. La calibración no recuperó ningún superviviente, y el valor colapsado
se publica como suelo de sensibilidad en `icc.collapsed_floor`, así que la
defensa sigue siendo la misma: está sesgada hacia no afirmar.

### El instrumento cambió durante el proyecto

Casi todas las latencias de VLM del documento son **tiempos de pared** medidos
desde la estación de trabajo, con la imagen en base64 cruzando un túnel SSH hasta
la placa. Cuánto de esa cifra es transporte y cuánto es cómputo solo se
caracterizó al final, en R-13: unos **103 ms** de los 4319 ms, es decir el cómputo
en dispositivo son 4216 ms. La corrección es pequeña en proporción y por eso no
invalida ningún veredicto, pero significa que **toda cifra de latencia anterior a
R-13 lleva una componente de transporte sin medir**, incluidos los ~4,85 s de E18
que sostienen el capítulo pivote — donde además quedan ~450 ms sin atribuir. Un
despliegue con cámara a bordo no pagaría ese transporte.

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
- Está acotada: se sostiene sobre cinco categorías de UAV123 con **p = 6,10e-05** en el resultado de generalización (McNemar exacto **bilateral**, deflactado a 23 clips independientes), y el refinamiento de selección queda en una señal a replicar. Un borrador anterior citaba aquí «p ~ 1,5e-5», que es el **unilateral sin deflactar** — precisamente las dos cosas que el Cap. 7 de este mismo esquema declara que no se usan para decidir nada. El bloqueo residual es la deriva del arrastre entre objetos de la misma clase, no el grounding ni la entrega.
- **Comparada por fin contra algo externo:** un detector de vocabulario abierto propone bien y no sabe elegir (recall@10 88,8 % frente a 47,4 % en k = 1), lo que sitúa el valor del VLM en la **selección**, no en la localización. La ruta descompuesta queda como trabajo futuro y **no como ruta recomendada**: su etapa de selección está sin costear, y la propia medida advierte de que si ese selector fuese a su vez un VLM el ahorro desaparece.
- Y está pendiente de la prueba que importa: nada se ha medido todavía con el vehículo cerrando su propio lazo.

## Deuda de evidencia

Trabajo que hay que hacer **antes** de redactar, ordenado por lo que bloquea a
más capítulos. No es redacción; es generar evidencia que no existe.

<!-- caption: Deuda de evidencia previa a la redacción, con el capítulo que bloquea cada partida -->

| Partida | Bloquea | Esfuerzo |
|---|---|---|
| ~~Calcular McNemar exacto y Wilson para todo brazo con puerta~~ | Cap. 3, 6, 7, 9 | **HECHO** 2026-07-21: `grounding/stats.py`, `thesis/claims.json`, `thesis/stats-report.md`, dos figuras |
| Re-ejecutar las 3 afirmaciones sin datos crudos (T2, T3, Fase C) | Cap. 5, 9 | Ver `thesis/rerun-backlog.md` |
| Generar la figura de la rejilla ROI (M x resolución) desde `sweep_summary.json` | Cap. 5 | Bajo — **sigue pendiente**. R-14 aportó tres figuras en dispositivo (`paired-iou`, `prefill-vs-tokens`, `discordant-examples`) que son un resultado pareado de dos brazos, **no** la rejilla del barrido; no la sustituyen |
| Generar las figuras de las Partes I-II (brecha de fidelidad, bake-off) | Cap. 4 | Medio — no hay `proof/`, hay que reconstruir de logs |
| Generar la figura cuantitativa del arco de adquisición | Cap. 6 | Medio |
| Justificar por escrito el umbral IoU@0,25 y reportar el IoU medio | Cap. 3, y todo lo demás | Bajo, pero es un flanco abierto |
| Verificar las entradas `% VERIFICAR` de `refs.bib` | Bibliografía | Bajo |
| ~~Corregir el `README.md` raíz: "todo en la placa" y la puerta de FPS~~ **HECHO** `cd8cca6` | Cap. 9 | — |
| ~~Decidir si se cierra la confirmación en dispositivo del ROI a Q8\_0~~ | Cap. 5 | **HECHO** 2026-07-21 (R-14): se cerró, 85,19 % contra 63,10 % en la placa, p = 2,50e-14 |
| Redactar la sección de caracterización del dispositivo que no existe | Cap. 3, 4 | Bajo — los datos están medidos y sin usar: 15 configuraciones de la Parte I más R-16 |

Todo lo marcado como bajo desbloquea la mitad del documento y no exige GPU.
**Dos partidas se cerraron entre el 2026-07-21 y el 2026-07-22** y ninguna exigió
redactar: la estadística (R-9) y la confirmación en dispositivo del ROI (R-14).
La figura de la rejilla ROI **no** se cerró con ella y la fila sigue abierta: las
tres figuras de R-14 son un resultado pareado de dos brazos, no el barrido
M x resolución. La única partida que aún obliga a volver a ejecutar algo son
las tres afirmaciones sin datos crudos, y es opcional: se puede escribir el
Cap. 5 declarando el pendiente en lugar de cerrándolo. La partida nueva es de
signo contrario a las demás — no falta evidencia, **sobra evidencia medida que el
esquema no coloca en ningún capítulo** (ver más abajo).

## Anexos previstos

<!-- caption: Anexos previstos, con el fichero del repositorio que provee cada uno -->

| Anexo | Contenido | Origen |
|---|---|---|
| A | Registro de afirmaciones con su prueba exacta, su máquina y sus matices | `thesis/stats-report.md`, `thesis/claims.json` |
| B | Registro de incidentes de desarrollo multiagente | `thesis/02-metodo-multiagente.md` |
| C | Cola de re-ejecuciones pendientes y qué afirmación desbloquea cada una | `thesis/rerun-backlog.md` |

## Orden de recorte

Si el documento no cabe, se recorta en este orden y no en otro. **Cada partida
declara qué se pierde**, porque un recorte sin su coste declarado se lee como que
no costó nada:

- **El desvío de simulación baja de 2 páginas a ~0,75.** Se pierde la construcción del generador de escenas de Gazebo (P5.7-P5.9, P5.11) como pieza de ingeniería: tres campañas de esfuerzo real con rendimiento probatorio nulo, porque el banco nunca llegó a discriminar los contratos. Sobreviven la conclusión metodológica y el defecto de orden de profundidad que P5.13 encontró mirando.
- **Los seis NO de selección pasan de narración a tabla.** La tabla **debe llevar columna de causa** (match-bound, resolution-bound, carry-bound, scene-bound) o el recorte sí destruye evidencia: la taxonomía de por qué cada intento falló de forma distinta es el contenido intelectual de los fracasos, no el adorno.
- **E9-E17 pasa de narración a tabla** en el Cap. 6. Se pierde el trabajo de controlador de seguimiento en SITL, reducido a un techo de 2,5 m/s con su advertencia de que se midió contra una textura nadir sintética plana. La reversión E11-E12 y la no-replicación E14-E16 dejan de leerse como historias, pero reaparecen en el Cap. 9 como evidencia del daño de los n pequeños: la pérdida es de tono, no de evidencia.
- **El bake-off de backbone pasa a apéndice.** No se pierde nada probatorio: sus brazos no comparten ni backend ni n, y sólo sostenían «ningún brazo desplazó al titular».
- **Las etapas de grounding de la Parte I bajan a ~1,5 pp.** Aquí sí se pierde el detalle diagnóstico del colapso de modo de la Etapa 2 (2/200) y de la transferencia COCO a aéreo (1/50). Se conservan la catástrofe de fidelidad —que sobrevive a Holm y es la razón de existir de la Parte II— y el par de medidas discrepantes de -23 pp y -16 pp.
- **P6.0 y P6.1 dejan de narrarse como resultados** y quedan en un párrafo de infraestructura habilitante. Se pierde el cómo de la migración Gazebo a CARLA; sobrevive el porqué. Ninguna de esas páginas sostenía una afirmación.
- **La subsección de método multiagente baja a un párrafo** y el Anexo B se conserva entero.
- **Las palancas descartadas del Cap. 5 pasan a una tabla única.**

**No se recorta:** la advertencia de P5.19, la corrección de signo del Cap. 4,
ninguna amenaza del Cap. 9, ni ninguna de las salvedades que viajan pegadas a una
cifra. Tampoco **P5.2b** —el resultado plano en velocidad— porque es lo único que
impide leer la frase-tesis como compensación de movimiento, ni **P5.1**, que es el
enunciado del mecanismo. **P5.12** se reporta aparte, en su propia subsección: es
un superviviente de Holm y su salvedad de «parcialmente definicional» necesita más
palabras, no menos, precisamente porque se le retira el titular.

La exención en bloque del Cap. 6 queda **retirada**: era la única protegida
entera, y es el capítulo sin un solo resultado significativo. Lo que se protege
son sus advertencias, una a una, no su extensión.

Recortar una amenaza convierte una afirmación honesta en una afirmación falsa.

## Siguientes pasos

- Fijar fecha de entrega. Es la única variable que falta y ordena el resto.
- Atacar las partidas baratas de la deuda de evidencia. La de estadística ya está cerrada (R-9); las que quedan baratas son el umbral IoU@0,25 por escrito, las entradas `% VERIFICAR` de `refs.bib` y la sección de caracterización del dispositivo, cuyos datos ya están medidos.
- Empezar a redactar por el Cap. 6, que es el pivote y fija el tono de los demás.
