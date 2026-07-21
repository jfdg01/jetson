---
title: Grounding visual anticipatorio para seguimiento de objetivos desde UAV en hardware de borde
subtitle: Esquema del TFM y mapa de evidencia
author: Javier Francisco Dibo Gomez
comment: Borrador de estructura, 2026-07-21T12:45Z
locale: es
bibliography: refs.bib
---

## Proposito de este documento

Este no es el TFM. Es el esquema del TFM y, sobre todo, el **mapa entre cada
afirmacion que se quiere defender y la evidencia que existe en el repositorio
para sostenerla** — incluidos los casos, que son muchos, en los que esa evidencia
es mas debil de lo que sugiere la nota de laboratorio.

Se escribe ahora porque el proyecto tiene el problema contrario al habitual: no
falta material, sobra. Seis partes, mas de sesenta experimentos registrados, del
orden de 272.000 palabras de notas. Un TFM admite unas 60-80 paginas. Eso es una
compresion cercana a 10:1, y una compresion de ese factor no se hace escribiendo:
se hace **decidiendo que se tira**. Este documento toma esas decisiones por
adelantado y las deja auditables.

### El hallazgo que cambia el plan

Al levantar el inventario aparecieron dos problemas que no son de redaccion:

- **No habia ni una sola prueba estadistica en el repositorio.** Una busqueda de `mcnemar|binomtest|scipy.stats|statsmodels|wilson|p-value` sobre todos los `.py` y `.md` devolvia cero ficheros. El unico estadistico existente era un Spearman escrito a mano, sin p-valor ni intervalo. Varias afirmaciones con puerta descansaban sobre una o tres celdas de diferencia. **Resuelto el 2026-07-21**: el marco esta en `grounding/stats.py`, se explica en el Cap. 3 (borrador en `thesis/01-metodo-estadistico.md`), y las 65 afirmaciones con puerta re-analizadas estan en `thesis/stats-report.md`. El resultado de ese re-analisis esta mas abajo y **cambia lo que el TFM puede afirmar**.
- **Las Partes I, II y III no tienen ni un solo directorio `proof/`.** La regla de entregables por campana se introdujo en julio y no se aplico retroactivamente. El resultado individual mas fuerte del proyecto — la palanca ROI, que gana en las dos dimensiones a la vez — **no tiene ninguna figura**: existe solo como un JSON de barrido.

Es decir: el trabajo pendiente antes de redactar no es escribir, es **generar la
evidencia grafica que falta y calcular los estadisticos que nunca se calcularon**.
Eso esta en la Seccion "Deuda de evidencia".

### Reglas que se aplican a si mismo

- Toda cifra citada aqui lleva la maquina en la que se midio. La composicion "precision del 3090 + FPS de la Jetson" en una misma tabla aparece varias veces en el cuaderno y no puede repetirse en el TFM sin decirlo.
- Ninguna figura se planifica sin comprobar si el material existe. Si no existe, se marca **POR GENERAR** y cuesta tiempo, no cero.
- Las advertencias no son opcionales: son las condiciones bajo las cuales las afirmaciones son ciertas. Si una desaparece del texto final, la afirmacion correspondiente se vuelve indefendible.
- Se prefiere un resultado negativo bien medido a un resultado positivo mal delimitado.

### Estado

- Bibliografia: `thesis/refs.bib` creada, con las entradas sin verificar marcadas `% VERIFICAR`.
- Esquema: este fichero.
- Texto: no empezado.
- Fecha limite: **sin fijar**. Es la variable que falta y la que ordena todo lo demas.

## Tesis defendida

Una sola frase, porque si no cabe en una frase no esta clara:

> Cuando la orden del operador llega a mitad de vuelo y no en el instante cero,
> la ventana previa a la orden es computo gratuito; gastarla en mantener
> candidatos vivos y limitarse a **seleccionar** al recibir la orden elimina la
> latencia de adquisicion que hace que un sistema de grounding sobre video aereo
> entregue una caja ya obsoleta.

De ahi salen tres afirmaciones subordinadas, y cada capitulo empirico existe para
sostener una de ellas:

<!-- caption: Las tres afirmaciones subordinadas, el capitulo que sostiene cada una y el limite de esa evidencia -->

| Afirmacion | Cap. | Limite de la evidencia |
|---|---|---|
| Un VLM de 2B cuantizado hace grounding referencial util sobre imagen aerea y cabe en un Orin Nano de 8 GB | 4-5 | Protocolo propio, mas facil que el benchmark publicado |
| La adquisicion en frio es el cuello de botella del sistema integrado, y no se arregla optimizando la adquisicion | 6 | n = 6 clips, todas coches, sin vehiculo en el lazo |
| Anticipar (mantener + seleccionar) si lo arregla, acotado por la calidad del arrastre | 7 | El unico SI a n real cae justo en el liston, p = 0,125 |

La Parte VI (Cap. 8) no sostiene ninguna de las tres todavia.

## Estructura propuesta

<!-- caption: Estructura de capitulos, origen del material y extension estimada -->

| Cap. | Titulo | Material de origen | Pags. (est.) |
|---|---|---|---|
| 1 | Introduccion y motivacion | `README.md`, propuestas de parte | 5 |
| 2 | Estado del arte | `SOURCES.md`, surveys, encuesta de datasets | 8 |
| 3 | Plataforma, metodo y metricas | `README.md`, `grounding/contract.py` | 8 |
| 4 | Grounding de un solo frame | Partes I y II | 10 |
| 5 | Permanencia de objeto | Parte III + E1 | 9 |
| 6 | El arco de la latencia de adquisicion | Parte IV (E2-E23) | 10 |
| 7 | Grounding anticipatorio | Parte V (P5.1-P5.20) | 14 |
| 8 | Hacia el lazo cerrado | Parte VI (P6.0-P6.1) | 6 |
| 9 | Amenazas a la validez | transversal | 6 |
| 10 | Conclusiones y trabajo futuro | transversal | 4 |

Total estimado: **80 paginas** de cuerpo. Los agentes que inventariaron cada parte
estiman 17 + 26 + 16 + 17 paginas solo para los capitulos 4 a 7 si se contara todo,
lo que confirma que el problema es de recorte y no de material.

## Capitulo 3 — Plataforma, metodo y metricas

Capitulo corto pero **necesario antes que los empiricos**, porque tres decisiones
de medida condicionan todas las cifras posteriores y ninguna es obvia.

### El umbral IoU@0,25

Toda la precision del proyecto se reporta a IoU@0,25. El estandar de la
literatura de comprension de expresiones referenciales es IoU@0,5. **No existe
justificacion registrada en ningun sitio del repositorio** para haber elegido
0,25: `grounding/contract.py` declara la constante y apunta a la puerta, sin
razon. El TFM tiene que justificarlo explicitamente — presumiblemente porque el
objeto aereo mediano ronda los 16 px y a 0,5 la metrica es inestable — y
reportar el IoU medio al lado, que es mucho mas sobrio.

Escribir este capitulo sin resolver esto deja un flanco abierto en la primera
pregunta del tribunal.

### La placa y su techo

- Jetson Orin Nano 8 GB, **15 W + `jetson_clocks`**. El modo de 25 W no existe en esta placa: el firmware expone solo 15 W y 7 W, y desbloquearlo exigiria un flasheo de bootloader que se decidio no intentar. Toda cifra de rendimiento es un techo de 15 W, no un techo de silicio.
- Una etiqueta anterior del cuaderno decia "MAXN\_SUPER" y **era falsa**; se corrigio el 2026-07-03. No debe reaparecer en el TFM.
- La potencia medida es `VDD_IN` de tegrastats: entrada total de placa, incluido un suelo de plataforma en reposo de ~5,2 W. No es potencia de modulo ni de SoC.

### El marco de inferencia

**Seccion obligatoria y probablemente la mas defendible del capitulo.** Borrador
completo en `thesis/01-metodo-estadistico.md`; aqui va el resumen y alli el
detalle, porque un tribunal preguntara por el metodo antes que por los numeros.

Lo que hay que explicar, en este orden:

1. **Que prueba corresponde a que diseno**, y que la eleccion la fija el diseno y nunca el p-valor que sale. Todo exacto: McNemar exacto, binomial exacta, Fisher, Wilcoxon. Ninguna aproximacion normal — con estos n, Wald da [0, 0] para un 0/6 y un limite superior mayor que 1 para un 24/25.
2. **`n_effective` frente a `n_rows`.** Seis clips por dos repeticiones deterministas son seis observaciones. Diez ensayos SITL del mismo fallo determinista son uno. 439 captions sobre 316 imagenes no son 439 observaciones independientes. Cada afirmacion declara las dos cifras y la razon por la que difieren.
3. **La deflacion a n efectivo.** Cuando el denominador cuenta filas y no observaciones independientes, la proporcion se conserva y el denominador se sustituye por `n_effective` antes de calcular nada. Es una correccion por efecto de diseno con deff = n / n_effective, deliberadamente tosca: solo ensancha el intervalo y solo debilita el p-valor, luego no puede fabricar un resultado. El caso que la motivo es E17, cuyo 0/10 daba un intervalo [0, 0,28] sobre diez repeticiones de **un** fallo determinista, y ahora da [0, 0,79] sobre n = 1.
4. **Disenos que no podian responder a su pregunta.** Una comparacion pareada de cinco elementos no alcanza p < 0,05 aunque los cinco volteen: el suelo es 0,0625. Se calcula desde n **solo**, sin mirar el resultado, que es lo que lo hace legitimo a posteriori.
5. **Empates y pruebas que no existen.** Cero pares discordantes devuelve `NaN`, no p = 1,0.
6. **Multiplicidad**: Holm-Bonferroni sobre la familia de afirmaciones con puerta, con las pruebas indefinidas fuera de la familia.
7. **Los tres niveles de estado de los datos** (`per_item`, `counts_only`, `missing`) y la regla de que una afirmacion en `missing` no se defiende: se re-ejecuta o se retira.

### Que le hizo el re-analisis al cuaderno

Este es el material del Cap. 9 y conviene anticiparlo aqui, porque **el marco no
se escribio para adornar resultados sino porque cambio varios**.

<!-- caption: Resultado global del re-analisis retroactivo de las 65 afirmaciones con puerta -->

| Categoria | N | Que significa |
|---|---|---|
| Significativas tras Holm | 6 | Se pueden defender como efectos |
| Sin prueba posible (0 discordantes o solo agregados) | 26 | No hubo contraste, en ninguna direccion |
| Diseno incapaz de alcanzar alfa | 33 | Ningun resultado posible habria bastado |
| Sin datos crudos | 3 | En cola de re-ejecucion, no se defienden |

Las seis que sobreviven son la catastrofe de fidelidad de la Parte I, la escalera
de resolucion y la puerta LoRA de la Parte II, la palanca ROI de la Parte III, la
generalizacion del arranque en caliente (P5.2a) y la recalibracion del banco
(P5.12). **La contribucion central del TFM esta entre ellas**, que es lo que
hacia falta comprobar.

Y tres correcciones que el re-analisis obliga a llevar al texto:

- **Swin2SR no pierde en precision** (ver Cap. 5). El descarte es por latencia.
- **La catastrofe de la Parte I es la exportacion, no la cuantizacion.** F16 contra Q8\_0 da b = 17, c = 10, p = 0,25: los 7 pp que el cuaderno atribuye al cuantizado no se distinguen del ruido. La brecha HF contra GGUF, en cambio, es significativa bajo **cualquier** emparejamiento compatible con los marginales (peor caso p = 1,3e-4), que es la forma correcta de defenderla cuando el brazo HF no dejo registro por elemento.
- **El arrastre a 768 si pierde precision frente a 1024** (55 pistas contra 31, p = 0,013). La adopcion de 768 nunca fue una afirmacion de igualdad: era una cota de tamano de efecto mas una restriccion de FPS, y hay que redactarla asi.

### La topologia real del banco

Esto es lo que mas se malinterpreta al leer el cuaderno. En casi todas las
partes, **la Jetson ejecuto solo el VLM**, servido por SSH con un PNG en base64
cruzando el cable por llamada; el arrastre con SAM2, el replay de video y el
scoring corrieron en una RTX 3090 de sobremesa. El capitulo debe presentar el
diagrama del banco antes de dar una sola cifra, porque de otro modo el lector
supone un sistema embarcado que nunca se midio como tal.

## Capitulo 4 — Grounding de un solo frame

Cubre Parte I (exploratoria, congelada) y Parte II (reconstruccion principiada).

### Que se cuenta

La Parte I se cuenta **como fracaso metodologico**, no como resultado. Produjo
una catastrofe de fidelidad: lo medido en el banco no era lo que ocurria en el
dispositivo. La Parte II existe porque esa leccion obligo a reconstruir la
evaluacion desde cero con fases con puerta y con manifiestos por ejecucion (SHA
de git, hash del lockfile, hash del dataset) que la Parte I no tiene.

Sin ese arco, la Parte II parece burocracia. Con el, es la respuesta a un fallo
concreto: "cinco copias divergieron en silencio".

### Cifras que se citan, con su matiz

- Espina dorsal: Qwen2-VL-2B [@wang2024qwen2vl], cuantizado a Q8\_0 con llama.cpp [@llamacpp].
- Fase 3, LoRA [@hu2022lora]: **59,5 %** IoU@0,25 sobre RefDrone [@refdrone] a n = 439. No citar el 65,0 % en bucle (n = 200) como titular.
- Fase 4: 59,5 % (HF) a 62,2 % (F16) a **62,6 %** (Q8\_0 en la Jetson).

### La correccion de signo mas importante del documento

El cuaderno etiqueta ese ultimo salto como "-2,7 pp" y lo repite en cuatro
sitios. **Es una convencion de magnitud de brecha, no una perdida.** Las cifras
suben: el artefacto cuantizado puntua por encima de la referencia HF. La lectura
honesta, que el propio README de la campana ya recoge, es que una inversion de
~3 pp sobre n = 439 esta dentro del ruido de muestreo y significa **"sin perdida
medible por el runtime"** — nunca "la cuantizacion mejora el modelo". Escribirlo
como perdida seria un error; escribirlo como mejora seria peor.

Lo mismo pasa con la brecha original de la Parte I: hay **dos medidas del mismo
fenomeno y no coinciden** (85,0 a 62,0 a 55,0, es decir -23 pp; frente a la
re-medida de la Fase 0b sobre el mismo checkpoint, 85,0 a 69,0 a 67,0, -16 pp).
La diferencia se atribuye a decodificacion voraz frente a muestreada y a n = 100
frente a n = 200. El TFM debe dar el par y la explicacion, no elegir el numero
mas dramatico.

### Advertencia obligatoria sobre RefDrone

El 62,6 % **no es comparable con la tabla de RefDrone**. El benchmark publicado
mide **F1 multi-objetivo a IoU >= 0,5** (una expresion puede mapear de 0 a 242
cajas); el estado del arte alli es 34,44 F1 y el techo humano 58,14. Lo que aqui
se mide es **una caja, IoU@0,25**, sobre el 30,9 % de las captions de validacion
que tienen exactamente una caja real (n = 439 de 1.421). Se descartan
precisamente los casos multi-objetivo y los negativos, que son para lo que
RefDrone fue construido.

Es un protocolo distinto y mas facil. Poner el 62,6 % al lado del 34,44 sin esa
frase seria una tergiversacion.

### Licencias

Las anotaciones de RefDrone son CC BY 4.0 pero reutilizan imagen de VisDrone2019-DET
bajo CC BY-NC-SA 3.0, de uso academico. Vale para un TFM y **hay que declararlo**:
la etiqueta permisiva de aguas abajo no anula la cadena de aguas arriba.

### Figuras

Ninguna existe. **Todas por generar** desde `runs/*/results.json`.

- POR GENERAR: barras banco-vs-dispositivo con las dos medidas discrepantes de la brecha de la Parte I, que es la figura que justifica la existencia de la Parte II.
- POR GENERAR: rejilla cualitativa de aciertos y fallos de grounding sobre imagen aerea.
- POR GENERAR: bake-off de backbone [@opengvlab2025internvl3; @qwen2025qwen25vl; @google2024paligemma2; @microsoft2024florence2; @hf2025smolvlm2]. Cuidado: los brazos **no comparten backend ni n** (A y C en HF a n = 200; el titular y B en Jetson Q8\_0 a n = 439; D cancelado sin ejecutar). Sostiene "ningun brazo desplazo al titular", no una clasificacion.

## Capitulo 5 — Permanencia de objeto

Parte III (T0-T4) mas la exportacion E1.

### Que se cuenta

Un grounding por frame no es seguimiento. Aqui entra el arrastre temporal: SAM2
[@ravi2024sam2] mantiene la mascara entre anclajes y el VLM solo se invoca para
re-anclar.

### La palanca ROI, dicha con precision

Es el mejor resultado del proyecto y el mas facil de exagerar.

- **Precision:** 85,2 % IoU@0,25 — medido con pesos **HF bf16 en la RTX 3090**, no en la Jetson y no a Q8\_0. La confirmacion en dispositivo estaba pre-registrada como "el unico pendiente antes de cambiar el valor por defecto" y **nunca se cerro**.
- **Delta:** el "+22,6 pp" compara 85,2 % (HF bf16, 3090) contra 62,6 % (Jetson Q8\_0, y ademas contra un checkpoint ya sustituido). El control mismo-backend medido en el mismo barrido es el brazo HF a frame completo, 64,0 %, lo que da un delta comparable de **+21,2 pp**. Ese es el numero defendible.
- **Latencia:** 2,7x de prefill (3691 ms a 1374 ms) frente a frame completo a 1024. La mitad de latencia si es una medida Jetson Q8\_0.
- **Cadencia:** el anclaje a ~2,0 s no es una mejora de 3x. Frente a la constante original de frame completo a 512 (2,26 s) es marginal, porque un recorte de 512x512 lleva pixeles parecidos. La mejora real es contra la ruta desplegada a 1024: **4,81 s a 2,02 s, 2,4x**, extremo a extremo.

Y la referencia desplegada ya no es 62,6 %: el checkpoint terse mide **63,1 %** a
frame completo en la Jetson. Cualquier "+22,6 pp sobre el modelo desplegado" es
contra un modelo que ya no se despliega.

### Cifras de arrastre y de exportacion

- Precision del arrastre: 0,849 a `image_size` 1024 y 0,830 a 768, sobre 186 pistas de AerialMind — **en la 3090**. En la Jetson solo se midieron FPS y RAM. Sembrado ademas desde una caja de verdad-terreno del primer frame: siembra oraculo, no lenguaje.
- E1, encoder de SAM2 a TensorRT fp16 [@tensorrt]: **4,89 a 6,15 FPS en banco solo**. En el bucle integrado el mismo encoder da **5,0 FPS**, con n = 1, y despeja la puerta de >= 5 **exactamente**. El bucle pierde ~1,15 FPS en codificar/decodificar JPEG y en el tunel SSH.
- Antes de E1 la tasa co-residente era **4,1 FPS frente a la puerta de 5**: un fallo marginal registrado como tal.

### Dos formulaciones que hay que evitar

- **"Se rechazo EdgeTAM frente a SAM2"** es falso. EdgeTAM era una alternativa condicional pre-registrada a la que nunca se llego, porque SAM2 + TensorRT despejo la puerta en el paso anterior. Nunca se midio, en ningun hardware. Se escribe "no hizo falta el plan B", jamas "gano la comparacion".
- **"7,6 Hz de tasa del sistema"** esta inflado por fases ciegas. La tasa del sistema es la de la fase de arrastre.

### La palanca de super-resolucion, descartada

Swin2SR [@conde2022swin2sr] sobre el recorte ROI **no compra nada medible** por
+1331 ms. Y aqui el re-analisis **corrige la nota de laboratorio**: la campana lo
registro como "pierde tambien en IoU", pero sobre los datos por elemento
(n = 429) ningun brazo se separa de otro. Frente a LANCZOS, b = 21 y c = 14,
**p = 0,31**; frente a bicubico, b = 22 y c = 12, **p = 0,12**; y el propio
bicubico contra el nativo da p = 0,26. El descarte es correcto y se sostiene
**por latencia**, que es determinista y enorme; escribir que Swin2SR "pierde en
precision" seria afirmar mas de lo que hay. Con dos matices mas: la prueba uso un recorte oraculo
de 400x400 centrado en la verdad-terreno (mide el techo que la SR podria ofrecer,
no el extremo a extremo) y n = 429, habiendo descartado 10 muestras por una razon
no aleatoria — los objetos mas grandes no caben en 400 px. La literatura de SR en
teledeteccion [@survey2025rssr; @xiao2023ediffsr] no transfiere a este recorte.

### Figuras

Parte III tampoco tiene `proof/`. Existen dos GIF sueltos (`permanence.gif`,
`closedloop.gif`) y tres clips del demo, todos versionados y reutilizables.

- POR GENERAR y **prioritaria**: la rejilla ROI (M x resolucion de salida) con los dos ejes, precision y prefill. Es el mejor resultado del proyecto y hoy no tiene imagen.
- Reutilizable: `experiments/2026-06-24-t2-permanence/permanence.gif` y `.../t3-closed-loop/closedloop.gif`.

## Capitulo 6 — El arco de la latencia de adquisicion

Parte IV, E2 a E23. **El capitulo pivote.**

### Que se cuenta

Con el sistema integrado sobre video real de UAV123 [@mueller2016uav123] aparece
un fallo que ningun experimento por componentes veia: la adquisicion en frio
tarda ~4,85 s y sobre un objetivo en movimiento **la caja se entrega obsoleta**.
El sistema no falla al encontrar el objeto; falla al encontrarlo donde ya no esta.

Luego se cuentan los intentos de arreglarlo por la via directa:

- **E20**, pista de recorte tomada de la frase del operador: 1,85 s, la unica adquisicion sub-2 s que funciona. Voltea 3 de 6.
- **E21** (segunda pasada del VLM), **E22** (prior en CPU) y **E23** (celda mas ancha): los tres fallan al automatizar la pista.

### La inferencia que arrastra el resto del documento

Cuatro intentos independientes, tres fracasos y un exito que **no es autonomo**.
La conclusion no es "hay que optimizar mas", es que el problema esta mal
planteado: si la orden llega en t y la respuesta en t + 4,85, ninguna
optimizacion sobrevive a un objetivo que se mueve. Hay que cambiar **cuando
empieza** el computo, no cuanto dura.

Eso es la Parte V.

### Advertencias que acompanan a cada cifra de este capitulo

- Los ~4,85 s **incluyen cable**: se midieron con un PNG sin perdidas en base64 cruzando un tunel SSH desde la estacion de trabajo hasta la Jetson, sobrecarga que un despliegue con camara a bordo no pagaria. El instrumento `transfer_ms` construido para exactamente esta pregunta nunca se ejecuto sobre la cifra titular de E18. Quedan ademas ~450 ms sin atribuir entre el `t_lock` de 4,85 s y la mediana instrumentada de 4400 ms.
- El arco completo E18-E23 es **n = 6 clips, todas coches, de un solo dataset**, con captions congeladas escritas a mano, n = 2 repeticiones por celda, **solo percepcion** — sin actuacion ni vehiculo en el lazo — y con el arrastre en la 3090 limitado a 6,15 Hz como sustituto del Orin. Los veredictos son 1/6, 2/6 y 3/6: diferencias de una sola clip, sin prueba estadistica posible.
- E20 **no es autonomo**: exige que el operador de una frase espacial correcta, y una pista **equivocada es peor que ninguna** (cobertura 0,000, plantilla de mascara envenenada, cero recuperacion). El encuadre honesto es "un rodeo con humano en el lazo que resistio tres intentos de automatizacion", no "una solucion".
- El techo de seguimiento de 2,5 m/s (3,0 con chase-hold) se midio en SITL contra un **renderizador nadir sintetico** — una textura plana con un rover dibujado a 640x480 — no sobre imagen real, con n = 2 o 3 por peldano. El propio repositorio contiene la refutacion: E11 dio PASS a 3,5 m/s con 2/2 y **E12 lo revirtio** a n = 3.
- **E14 no replica.** Su "3/3, agujero de identidad cerrado" se convierte en **6/8, CUALIFICADO y explicitamente no fiable** en la replicacion E16. El matiz atenuante, que merece decirse: 0 de 8 violaron la identidad, luego los dos fallos son de temporizacion aguas arriba de la puerta, no de la puerta.
- Los numeros de estres de E15 estan **registrados pero no reclamados**: fallo su guarda de linea base, asi que el veredicto es NO MEDIBLE.

### Figuras

Casi todo son clips `.mp4`, que es lo correcto cuando el comportamiento es el
argumento. Solo hay dos figuras (E22 y E23).

- Reutilizable, **la figura titular de la Parte IV**: `experiments/2026-07-03-real-video-replay/proof/car9_A_vs_B.mp4`, la adquisicion real contra su control.
- Reutilizable, **la prueba de fragilidad de E20**: `.../2026-07-04-prompt-scoped-acquire/proof/wrong_car10_r1_wrongprobe.mp4`, donde una pista erronea hace que el VLM alucine.
- POR GENERAR: no existe ninguna figura cuantitativa del arco de latencias (4,85 a 1,85 a 2,73 a 2,80 s) ni de la escalera de velocidades. Hay que hacerlas.

## Capitulo 7 — Grounding anticipatorio

Parte V, P5.1 a P5.20. El capitulo mas largo y el que contiene la contribucion.

### Estructura interna propuesta

No se narran veinte experimentos en orden. Se narran cuatro hilos:

- **El arranque en caliente funciona.** P5.1 (5/6 frente a 1/6 en frio) y P5.2 (21/25 frente a 5/25 sobre 25 clips y 5 categorias).
- **Seleccionar entre candidatos es donde duele.** P5.3, P5.4, P5.5, P5.10, P5.13 y P5.17: seis intentos sin separacion o sin robustez, agrupados por causa y no por numero.
- **Lo que si lo desbloqueo.** P5.14 cambia el **contrato de entrega** — entregar la pista ya arrastrada en lugar de re-anclar al recibir la orden. P5.16 quita el oraculo de la semilla y cuesta una celda de doce.
- **Donde esta el limite.** P5.15 (el arrastre aguanta 24 s de espera, 24/25: **el arrastre no es la parte fragil**), P5.18 (a n = 26 el SWAP reforzado cae a 17/26), P5.19 (sube a 20/26) y P5.20 (un SAM2 mayor no recupera ninguna celda: palanca muerta).

### El estadistico, ya calculado

Cifras generadas por `thesis/run_stats.py` desde `thesis/claims.json`, no
estimadas. McNemar **exacto bilateral**, que es el que se reporta en todo el
documento; el unilateral es la mitad y no se usa para decidir nada.

<!-- caption: Inferencia post-hoc sobre los resultados con puerta de la Parte V, generada desde los volcados por elemento -->

| Resultado | Discordancia | McNemar exacto | Lectura |
|---|---|---|---|
| P5.1 WARM 5/6 vs COLD 1/6 | b = 4, c = 0 | p = 0,125 | No significativo por si solo |
| P5.2a WARM 21/25 vs COLD 5/25 | b = 16, c = 0 | **p = 3,05e-5** | **El ancla estadistica de la parte**; sobrevive a Holm |
| P5.10 DD 24/24 vs RG 24/24 | b = 0, c = 0 | **indefinido** | No hubo prueba, no hubo empate demostrado |
| P5.13 y P5.17 | b = 1, c = 0 | p = 1,0 | No informativo en ninguna direccion |
| P5.19 SWAP 20/26 vs P5.18 17/26 | b = 3, c = 0 | p = 0,25 | Compatible con el azar |

La fila de P5.10 estaba mal agrupada en el borrador anterior de este esquema, y
la distincion importa: P5.13 y P5.17 **corrieron** una prueba que no separo nada,
mientras que P5.10, con cero pares discordantes, **no corrio ninguna**. Reportar
p = 1,0 alli habria sido afirmar equivalencia demostrada.

De aqui salen dos consecuencias narrativas:

- **P5.1 no puede ser el titular.** Es defendible solo porque P5.2 lo replica a n = 25 y cinco categorias. El titular es P5.2.
- **Los tres empates de simulacion no demuestran equivalencia.** Con una sola celda discordante, McNemar da p = 0,5, que es literalmente ninguna informacion. La afirmacion correcta es "este banco no pudo discriminar los contratos", que es lo que dice el repositorio.

### Advertencia obligatoria sobre P5.19

P5.19 pasa su liston **exactamente**, 20/26 contra un liston de 20. Con tres
pares discordantes en una sola direccion, McNemar exacto bilateral da **p = 0,25**,
y el intervalo de Wilson al 95 % es [0,579, 0,890], que **cruza el liston de
0,769**. La mejora es compatible con el azar al tamano de muestra usado: harian
falta **seis** pares discordantes en la misma direccion para alcanzar alfa a
n = 26, y hubo tres.

Se presenta como una senal a replicar, no como significativa. Y se argumenta
**por replicacion, no por p**: que P5.20 reprodujera P5.19 celda por celda, sin
un solo cambio, es mejor evidencia de que el efecto es real que cualquier
contraste a este n.

Ademas, la precision de la entrega con gracia es **2/4**, y cuando falla
**entrega una caja ajustada y confiada sobre el objeto equivocado** (IoU 0,679 y
0,865) en vez de abstenerse. En despliegue no hay verdad-terreno que lo detecte:
es un fallo silencioso, y es el peor modo posible para algo que pilota. Falsifico
ademas su propia prediccion de "suelo de regresion ~0".

### Matices que viajan con los numeros

- **`acquire_s` = 0,00 s del contrato de entrega directa es definicional, no medido.** No hay paso de adquisicion que cronometrar. Es valido como enunciado del contrato, pero decir "hicimos la adquisicion 4,5 s mas rapida" sin anadir que el coste se traslado a la tuberia que corre continuamente durante la espera es enganoso.
- **De las cuatro perdidas de P5.2, dos son degeneradas**: el objetivo no esta en el frame de entrega, asi que el oraculo tambien falla. El repositorio reporta correctamente 21/23 = 91 % sobre el conjunto no degenerado, y ese calificador debe viajar con la cifra.
- **El rho = -0,06 del barrido de velocidad no tiene p-valor ni intervalo.** Sostiene "no se observa dependencia de la velocidad", no "es plano".
- **P5.16 no es un resultado vigente.** Su 4/5 fue derribado por P5.18 con el mismo arnes byte a byte: la tasa real es 17/26 = 0,65. Se presenta como un paso cuyos numeros no sobrevivieron.
- **El arrastre nunca corrio en la Jetson en toda la Parte V.** El presupuesto de 6,15 Hz es ademas el banco solo de E1; el integrado da 5,0 Hz, luego el limitador es ~23 % optimista respecto al sistema desplegado.

### El desvio de simulacion

P5.7 a P5.13 y P5.17 construyen un banco de escenas sinteticas en Gazebo
[@gazebo2024harmonic] para conseguir los cruces y oclusiones que UAV123 no da.
Terminan en un **no**: el VLM ancla 56 de 56 renders limpios, los contratos
empatan siempre y el banco no discrimina.

La conclusion util es metodologica: la ventaja del contrato bueno vive en la
**fragilidad ante imagen real**, y un render limpio la borra. Dos paginas, no
diez. Merece mencion el defecto que P5.13 encontro mirando: el coche blanco era
el mas cercano en 0 de 300 frames de todas las clips — orden de profundidad
constante, y ninguna puerta lo cubria.

### Figuras

Es la parte mejor documentada: `proof/` existe en todas las campanas.

- Reutilizable: `.../warm-start-generalization/proof/generalization_grid.png` (P5.2a, el titular) y `gap_vs_speed.png` (P5.2b, la figura que refuta la explicacion intuitiva del propio resultado).
- Reutilizable: `.../warm-start-acquire/proof/car10_warm_vs_cold.mp4`, el clip de la caja obsoleta a 135 frames.
- Reutilizable: `.../select-generalization/proof/car7_460_SWAP_MC_driftNOMATCH.mp4`, la deriva de arrastre que es el bloqueo residual.
- POR GENERAR: la trayectoria de la afirmacion de seleccion de P5.14 a P5.20 **con intervalos de Wilson**, que es la figura que obliga a poner P5.18.

## Capitulo 8 — Hacia el lazo cerrado

Parte VI, P6.0 y P6.1. Corto y **honesto sobre lo que aun no demuestra**.

### Que se cuenta

Todas las cifras de la Parte V se midieron sobre video grabado que el sistema no
podia influir. No habia vehiculo en el lazo. La Parte VI pone la seleccion
delante de un copter volando — ArduCopter SITL [@ardupilot] como fisica, CARLA
0.9.16 [@dosovitskiy2017carla] como renderizador esclavo de pose — para que los
pixeles pasen a ser consecuencia de la propia salida de control. Es la etapa SIL
del marco de [@jiang2025dronepipeline].

- **P6.0**, puerta de capacidad: PASS. Encontro un fallo de re-emparejamiento en ByteTrack [@zhang2022bytetrack] que convertia el "coasting de Kalman" en un mantenedor de orden cero y hacia **vacua** la cifra de "0 perdidas de pista". Error de pixel 64,7 a 36,0.
- **P6.1**, cambio de renderizador: YES. 48,1 Hz con 40 vehiculos autonomos siguiendo un vuelo GUIDED real (0 a 84,4 m a 60 m sobre el terreno), con la pila de control intacta.
- **Banco GT de CARLA** (2026-07-21): 25 clips, 30.000 frames con verdad-terreno por actor proyectada, puertas G-A PASS / G-B CERRADA / G-C PASS.

### Tres cifras de este capitulo que NO deben citarse

Es el capitulo con mas metricas vacuas del proyecto, y todas lo son por la misma
razon: miden un numero contra si mismo.

- **`slave_err` = 0,000 m.** La camara libre de CARLA es un actor cinematico, luego `get_transform()` devuelve exactamente lo que `set_transform()` le acaba de pasar. Se conservo en el `results.json` y se excluyo deliberadamente de la figura para que nadie la confunda con evidencia. Lo que si evidencia el esclavizado es que la **fuente** de pose recorrio 84,4 m bajo control del autopiloto.
- **"0 perdidas de pista" antes del arreglo de P6.0.** Una pista nunca moria: se sustituia continuamente por un ID nuevo. El par antes/despues debe presentarse junto o el lector lee el 100 % previo como salud.
- **Los 48,1 Hz como tasa disponible para trabajo real.** Se midieron a 640x480, 40 vehiculos, sin proyeccion de verdad-terreno ni escritura JPEG y **sin limite de potencia**. El banco GT, en el mismo servidor y mapa pero con 80 vehiculos, proyeccion por actor, escritura JPEG y la GPU limitada a 200 W, sostiene **15,88 Hz**. No son comparables.

### Sincrono contra asincrono: la distincion que hay que declarar siempre

El banco GT corre en modo **sincrono** y el banco de vuelo en **asincrono**.
Coexisten por decision deliberada y **cada resultado debe nombrar cual lo
produjo**, porque en modo sincrono una adquisicion de 4,5 s cuesta **cero
segundos de simulacion**: el retardo de entrega que las Partes IV y V existen
para medir sencillamente deja de existir. Mezclar ambos conjuntos de cifras
invalidaria justamente lo que el TFM defiende.

Corolario: el banco GT es determinista, pero **la Parte VI de vuelo pierde el
determinismo** que toda la Parte V tenia. SITL corre en tiempo real y no se puede
avanzar frame a frame, asi que los ensayos de vuelo son estocasticos; la
mitigacion es estadistica (semilla de escena + n >= 25 + reportar la banda de
ruido de planificacion), no exacta.

### Lo que este capitulo NO afirma

- **P6.2 no se ha ejecutado.** La Parte VI ha producido una puerta de capacidad, un cambio de renderizador y un banco instrumentado: infraestructura habilitante, no la afirmacion. Sus tres premisas — que el arrastre sobrevive a la ego-motion que el propio sistema induce, que el presupuesto de latencia sobrevive al reloj de pared, y que el contrato de seleccion es entregable a un controlador — siguen **sin falsar, porque ningun experimento ha podido falsarlas todavia**.
- **G6 no se ha ejecutado**, luego el renderizador CARLA **no esta validado para la etapa de grounding**. Su prediccion (peor que los 56/56 de Gazebo, mejor que UAV123) esta sin probar.
- **Ninguna campana de la Parte VI tuvo la Jetson en el lazo.** Las detecciones de P6.0 se inyectan geometricamente; el servidor de CARLA exige una GPU de sobremesa y no corre en el Orin. Ninguna cifra de la Parte VI es una cifra de despliegue.
- **Ninguna taxonomia de identidad o de deriva salida de este banco es fiable todavia.** El emparejador de actores de `runners/carla_debug_ui.py` tiene seis modos de fallo silencioso verificados, entre ellos una superposicion normalizada por la caja menor que da 1,0 a una mascara sobre un retrovisor.
- **Las tres "regiones" de `track_gain`** que una nota anterior de la campana describia estan **retiradas** a n = 25: solo la ganancia 1,0 es un regimen limpio, y las otras dos se solapan.
- **CARLA no es comparable con el banco de Gazebo** de la Parte V. Los 56/56 de P5.17 son un contraste, no una linea base. Fue un coste aceptado y registrado del cambio.
- **Ni tiempo atmosferico ni hora del dia** se ejercitaron: todos los frames son mediodia despejado, y la camara es **nadir fija**, mientras que el video real de UAV y el banco de la Parte V son **oblicuos**. Una afirmacion de fidelidad que solo vale al mediodia y desde arriba es una afirmacion estrecha.

### Dos limitaciones del artefacto, para quien lo reutilice

- Los identificadores de actor del `gt.jsonl` los asigna el servidor y **CARLA no los reproduce entre cargas de mundo**. Valen dentro de una clip y no pueden usarse para emparejar identidades entre ejecuciones, que es exactamente lo que querria un A/B pareado sobre la misma semilla. La clave estable por indice de spawn exige una recaptura de 36,5 min y no se ha anadido.
- Sobreviven **19 cajas degeneradas de anchura cero** en 897.864 (2,1e-05), lascas de borde de frame serializadas a dos decimales. Un consumidor que calcule IoU divide por cero. El arreglo de serializacion llego despues de la captura y el banco no se recapturo: hay que filtrarlas.

### Dos fallos que merecen media pagina cada uno

Son aportacion metodologica, no anecdota:

- **La camara apuntaba al cielo.** Un pitch de `+pi/2` en Gazebo es **abajo**, no arriba. Durante toda una fase el log salia limpio, se escribian ficheros bien formados, y la conclusion asociada (RQ-S1.4) hubo que **retirarla**: se habia medido a traves de una imagen gris plana, 100 % de un solo color. Es el caso concreto que motivo la regla de verificacion visual del proyecto. En trabajo de simulacion, **un `exit 0` no es evidencia sobre pixeles**.
- **La metrica vacua.** El fallo de ByteTrack producia "0 perdidas de pista" precisamente porque las pistas perdidas nunca se re-emparejaban. Una metrica puede ser perfecta por estar rota.

## Capitulo 9 — Amenazas a la validez

Capitulo propio, no notas al pie. Estas son las que un tribunal encontraria.

### "Todo corre en la placa" no es lo que se midio

El eslogan del proyecto dice que todo corre en el borde sin nube. La realidad:
**el arrastre con SAM2 nunca se ejecuto en la Jetson en la Parte V**, y en las
partes anteriores la precision del arrastre se midio siempre en la 3090 mientras
la placa aportaba solo FPS. La unica medida co-residente integrada dio 4,1 FPS
frente a su propia puerta de 5 antes de E1, y 5,0 FPS despues — despejandola
exactamente, con n = 1. La formulacion del `README.md` es mas fuerte que la
evidencia y se corrige aqui (lineas 3, 47, 48 y 50).

La Parte VI **agrava** esto en lugar de resolverlo: ninguna de sus campanas tuvo
la Jetson en el lazo, porque el servidor de CARLA exige una GPU de sobremesa. El
arco de lazo cerrado se mide integramente en la 3090.

### Composiciones entre maquinas

Varias tablas del cuaderno emparejan una precision medida en la 3090 con unos FPS
medidos en el Orin. Cada una de esas filas describe un sistema que nunca existio.
El TFM debe etiquetar la maquina en cada celda o separar las tablas.

### Tamanos de muestra e inferencia

Buena parte de las decisiones se tomaron con n de 2 a 6. El re-analisis del
2026-07-21 cuantifica el dano: de 65 afirmaciones con puerta, **33 salen de
disenos que no podian alcanzar alfa = 0,05 con ningun resultado posible** y solo
**6 sobreviven a la correccion de Holm**. P5.18 ya lo habia demostrado
empiricamente: un 4/5 se convirtio en 17/26 al medirlo bien. E12 revirtio a E11
por la misma razon.
El proyecto adopto despues una regla de n >= 25 para todo brazo con puerta, que
**post-data a las Partes I a IV completas**. Los resultados anteriores se
presentan con su n visible y, donde importe, con su intervalo de Wilson.

La regla admite ademas una excepcion declarada: P6.0 y P6.1 son puertas de
capacidad con **n = 1** — dos vuelos unicos — y la exencion se tomo a proposito,
porque una puerta de capacidad pregunta "existe la carretera", no "cuanto se
tarda". P6.0 tampoco se pre-registro. Sirven para desbloquear P6.2 y **no
soportan ninguna afirmacion de rendimiento**.

### El sim no es el mundo

Un PASS sobre render de Gazebo o CARLA no sostiene una afirmacion sobre imagen
real, y la Parte V lo demostro por la via dura: el VLM acierta el 100 % de los
renders limpios y de ahi no sale ninguna discriminacion. El techo de seguimiento
de la Parte IV se midio ademas contra una textura plana con un rover dibujado.

### Resultados retirados

Los numeros de seguimiento en lazo cerrado de la Fase C de la Parte I estan
**retirados** (2026-07-20): se midieron a traves de una camara que apuntaba al
cielo. Si el TFM los menciona es como caso de fallo metodologico, con las cifras
tachadas y RQ-S1.4 declarada sin responder.

Retirada tambien la nota de la campana del banco GT que describia **tres
regimenes distintos de `track_gain`**: a n = 25 solo la ganancia 1,0 es un
regimen limpio y los otros dos se solapan. `track_gain` no es un factor valido y
no debe aparecer como eje de ninguna figura.

### Irreproducibilidad de los pesos

El directorio de entrenamiento HF/safetensors fusionado se perdio y no sobrevive
ningun adaptador LoRA. Los GGUF desplegados **no se pueden re-exportar**: un
reentrenamiento daria un modelo distinto y romperia la comparabilidad celda a
celda de las Partes II a V. Existe copia verificada por sha256 en
`/home/gara/grounding-checkpoint-backup/`, pero es una copia en la misma maquina.
Ademas, las ejecuciones de la Parte I **no llevan manifiesto** (SHA de git, hash
del lockfile, hash del dataset), porque preceden a ese aparato: su garantia de
reproducibilidad es estrictamente mas debil, y arreglar eso fue un objetivo
declarado de la Parte II.

## Capitulo 10 — Conclusiones

- La contribucion es el **replanteamiento**, no una arquitectura: cuando la orden es asincrona, el instante en que empieza el computo importa mas que su duracion.
- Esta acotada: se sostiene sobre cinco categorias de UAV123 con p ~ 1,5e-5 en el resultado de generalizacion, y el refinamiento de seleccion queda en una senal a replicar. El bloqueo residual es la deriva del arrastre entre objetos de la misma clase, no el grounding ni la entrega.
- Y esta pendiente de la prueba que importa: nada se ha medido todavia con el vehiculo cerrando su propio lazo.

## Deuda de evidencia

Trabajo que hay que hacer **antes** de redactar, ordenado por lo que bloquea a
mas capitulos. No es redaccion; es generar evidencia que no existe.

<!-- caption: Deuda de evidencia previa a la redaccion, con el capitulo que bloquea cada partida -->

| Partida | Bloquea | Esfuerzo |
|---|---|---|
| ~~Calcular McNemar exacto y Wilson para todo brazo con puerta~~ | Cap. 3, 6, 7, 9 | **HECHO** 2026-07-21: `grounding/stats.py`, `thesis/claims.json`, `thesis/stats-report.md`, dos figuras |
| Re-ejecutar las 3 afirmaciones sin datos crudos (T2, T3, Fase C) | Cap. 5, 9 | Ver `thesis/rerun-backlog.md` |
| Generar la figura de la rejilla ROI desde `sweep_summary.json` | Cap. 5 | Bajo, y es el mejor resultado sin imagen |
| Generar las figuras de las Partes I-II (brecha de fidelidad, bake-off) | Cap. 4 | Medio — no hay `proof/`, hay que reconstruir de logs |
| Generar la figura cuantitativa del arco de adquisicion | Cap. 6 | Medio |
| Justificar por escrito el umbral IoU@0,25 y reportar el IoU medio | Cap. 3, y todo lo demas | Bajo, pero es un flanco abierto |
| Verificar las entradas `% VERIFICAR` de `refs.bib` | Bibliografia | Bajo |
| Corregir el `README.md` raiz (lineas 3, 47, 48, 50): "todo en la placa" y la puerta de FPS | Cap. 9 | Bajo |
| Decidir si se cierra la confirmacion en dispositivo del ROI a Q8\_0 | Cap. 5 | Alto — es una ejecucion, no una figura |

Todo lo marcado como bajo desbloquea la mitad del documento y no exige GPU. La
ultima partida es la unica que obliga a volver a ejecutar algo, y es opcional: se
puede escribir el Cap. 5 declarando el pendiente en lugar de cerrandolo.

## Orden de recorte

Si el documento no cabe, se recorta en este orden y no en otro:

- El desvio de simulacion baja de 2 paginas a un parrafo.
- La Parte I baja a media pagina de contexto.
- El bake-off de backbone pasa a apendice.
- Las palancas descartadas del Cap. 5 pasan a una tabla unica.

**No se recorta:** el Cap. 6 completo, la advertencia de P5.19, la correccion de
signo del Cap. 4, ni ninguna amenaza del Cap. 9. Recortar una amenaza convierte
una afirmacion honesta en una afirmacion falsa.

## Siguientes pasos

- Fijar fecha de entrega. Es la unica variable que falta y ordena el resto.
- Atacar las partidas baratas de la deuda de evidencia, empezando por el script de estadistica, que toca tres capitulos.
- Empezar a redactar por el Cap. 6, que es el pivote y fija el tono de los demas.
