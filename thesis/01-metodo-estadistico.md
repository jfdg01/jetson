---
title: Metodo estadistico retroactivo
subtitle: Como se decide que numeros del cuaderno de laboratorio son defendibles
author: Javier Francisco Dibo Gomez
comment: Marco de inferencia, 2026-07-21T13:10Z
locale: es
bibliography: refs.bib
---

## El problema que resuelve este documento

El proyecto se llevo como un cuaderno de laboratorio. Cada campana pre-registraba
una puerta ("WSEL debe despejar 4/5"), ejecutaba el brazo, comparaba el recuento
con la puerta a ojo y anotaba un YES o un NO. Como forma de dirigir un programa
de investigacion es legitima y funciono: encontro la palanca del contrato de
entrega, descarto la super-resolucion, mato la palanca de capacidad.

Como forma de defender una afirmacion en un TFM no vale. Una busqueda por
`mcnemar|binomtest|scipy.stats|statsmodels|wilson|p-value` sobre el repositorio
completo devolvia **cero ficheros** antes de este trabajo. Habia decisiones
tomadas con n entre 2 y 6, sin intervalo de confianza, sin correccion por
multiplicidad y sin una sola prueba de hipotesis.

Este documento define el marco con el que se re-analizan esas campanas. La
implementacion esta en `grounding/stats.py` y su comportamiento esta fijado por
`tests/test_stats.py`.

### Lo que este marco NO es

No es un intento de convertir NOs en YESes. Anadir p-valores a posteriori es
barato y casi siempre inutil. **La parte dificil, y la razon de que este modulo
exista, es negarse a calcular los que enganarian.** Buena parte de lo que sigue
son reglas de rechazo, no de calculo.

Tampoco es un re-analisis exploratorio. Las puertas ya estaban pre-registradas;
lo que se anade es la incertidumbre que siempre debio acompanarlas, no una
segunda oportunidad de encontrar un efecto.

## Tres modos de fallo que el marco vigila

### Diseno equivocado

McNemar exige que los **mismos elementos** se midan bajo ambos brazos. Aplicarlo
a dos grupos independientes infla la significacion. La implementacion recibe
unicamente los recuentos discordantes, de modo que un conjunto no pareado no
puede llegar a la funcion por descuido; y `discordant_counts()` **descarta** los
elementos que solo aparecen en un brazo, porque contar una ejecucion que fallo
como un fracaso del brazo es como una caida se convierte en un resultado.

### Pseudo-replicacion

"6 clips x 2 repeticiones" son 6 observaciones, no 12. Cinco celdas recortadas
del mismo video no son cinco ensayos independientes. Miles de frames
consecutivos de un unico vuelo son **un** vuelo: estan autocorrelacionados, y
tratarlos como n = 30.000 es la forma clasica de fabricar significacion a partir
de un solo ensayo. Toda afirmacion lleva `n_effective` separado de `n_rows`, y
el informe imprime los dos junto con la razon por la que difieren.

Separarlos no basta: hay que **usar** el que corresponde. Un intervalo calculado
sobre `n_rows` y etiquetado con `n_effective` es peor que no dar intervalo,
porque reclama una precision que nunca se compro. Ocurrio durante la propia
redaccion de este marco — E17 imprimia `n = 1` junto a un IC de [0,000, 0,278]
construido con 10 filas de un mismo fallo determinista — y de ahi sale
`deflate_to_effective()`:

<!-- caption: Correccion por efecto de diseno aplicada antes de cualquier intervalo o p-valor -->

    k, n = deflate_to_effective(k_observado, n_filas, n_effective)

Conserva la proporcion y sustituye el denominador por `n_effective`. Es una
correccion por efecto de diseno con `deff = n_rows / n_effective`, y es
deliberadamente tosca: **solo puede ensanchar el intervalo y debilitar el
p-valor, nunca al reves**, de modo que no puede fabricar un resultado. Con la
correccion aplicada, E17 pasa a [0,000, 0,793] sobre n = 1, que es lo que
realmente sostiene una unica observacion. El informe marca cada caso afectado con
`[deflated from k/n]` para que la deflacion sea visible y no un ajuste
silencioso.

### Disenos que nunca pudieron responder a su pregunta

Es el aporte principal del marco y el mas incomodo.

Una comparacion pareada de 5 elementos **no puede** alcanzar p < 0,05 bilateral
aunque los cinco pares volteen a favor: el suelo es p = 0,0625. Un n = 6 llega
justo, y solo si el resultado es perfecto (6 de 6 discordantes en la misma
direccion, p = 0,031).

<!-- caption: Cuantos pares discordantes en una sola direccion hacen falta para alcanzar alpha = 0,05 bilateral -->

| Pares (n) | Discordantes necesarios | Se puede alcanzar |
|---|---|---|
| 5 | — | **No, con ningun resultado** |
| 6 | 6 (todos) | Solo si es perfecto |
| 12 | 6 | Si |
| 25 / 26 | 6 | Si |
| 56 | 6 | Si |

La consecuencia es dura y hay que decirla: **un NO salido de un diseno de n = 5
no es evidencia de ausencia de efecto, es evidencia de ausencia de experimento.**
`min_discordant_for_significance()` lo calcula a partir de n **solo**, sin mirar
el resultado, que es lo que lo hace legitimo a posteriori — a diferencia de la
"potencia observada", que no es mas que el p-valor recalculado.

El mismo argumento vale para las puertas de una sola proporcion. Con n = 25, una
puerta pre-registrada del **90 %** es inalcanzable en terminos estadisticos: un
25/25 perfecto da p = 0,9^25 = 0,072. Una puerta asi solo puede despejarse
descriptivamente.

## Que prueba se aplica a que diseno

La eleccion la fija el **diseno**, nunca el p-valor que sale.

<!-- caption: Regla de seleccion de prueba por diseno experimental -->

| Diseno | Prueba | Por que esta y no otra |
|---|---|---|
| Binario pareado (mismos clips, dos brazos) | McNemar exacto | Exacto y no ji-cuadrado: con b + c <= 5, que es lo habitual aqui, la aproximacion no vale |
| Binario de un brazo contra una puerta | Binomial exacta + intervalo de Wilson | La puerta es una probabilidad, no un recuento |
| Binario no pareado | Fisher exacta | Grupos independientes |
| Continuo pareado (latencias, IoU, error de pixel) | Wilcoxon de rangos con signo + IC bootstrap | Las latencias tienen cola derecha y n es pequeno: la normalidad de una t haria un trabajo que no se ha ganado |
| Sin hipotesis pre-registrada | Solo intervalo de Wilson | Descriptivo, y etiquetado como tal |

Todo exacto. Ninguna aproximacion normal: con estos n, ni la McNemar
ji-cuadrado ni el intervalo de Wald serian correctos, y las versiones exactas no
cuestan nada. Wald ademas falla justo donde vive este repositorio — en 24/25 da
un limite superior por encima de 1, y en 0/6 colapsa a [0, 0], afirmando certeza
absoluta a partir de seis observaciones.

### Una trampa que el marco bloquea explicitamente

Sobre las cifras de P5.2 la prueba **no pareada** de Fisher da un p **menor**
(1,2e-05) que la McNemar pareada (3,1e-05), porque McNemar descarta los 9 clips
concordantes y saca toda su potencia de los 16 discordantes. Es tentador
reportar Fisher.

Seria p-hacking por seleccion de prueba. Los 25 clips se midieron bajo ambos
brazos, luego las observaciones estan pareadas y la prueba se deduce del diseno.
`tests/test_stats.py` fija esta relacion con una asercion para que una sesion
posterior no pueda cambiar en silencio al p-valor mas bonito y llamarlo mejora.

## Empates y pruebas que no existen

Tres campanas de simulacion terminaron en empate casi perfecto (24/24 contra
24/24, 24/24 contra 23/24, 56/56 contra 55/56). Devolver p = 1,0 en el caso del
empate exacto se leeria como "probado, brazos equivalentes". No lo es: son **0
pares discordantes**, es decir, ausencia de prueba en cualquier direccion.
`mcnemar(0, 0)` devuelve `NaN` a proposito y el informe lo imprime como
`undefined`.

Un unico par discordante — el caso de 23/24 y 55/56 — da exactamente p = 0,5. Es
la demostracion mas limpia posible de que esas campanas no podian separar los
brazos, con independencia de lo que hubiera salido.

## Cuando solo sobreviven los marginales

A veces se conserva el total de cada brazo pero no el pareo elemento a elemento,
de modo que b y c no son recuperables. La salida facil seria descartar la
afirmacion; la correcta es **acotarla**.

Los marginales fijan `b - c`. Basta recorrer todos los pares (b, c) compatibles
con esa diferencia y quedarse con el **peor** para la significacion: el p-valor
resultante es una cota superior valida bajo cualquier pareo consistente con los
datos. Si esa cota ya cae por debajo de alfa, la conclusion no depende del pareo
perdido.

Es lo que rescata el resultado mas fuerte de la Parte I. En HF contra GGUF los
marginales dan `b - c = 30`, luego `c` esta en [0, 15]; el peor caso, `c = 15` y
`b = 45`, todavia da **p = 1,3e-04**. La catastrofe de exportacion es
significativa se pareara como se pareara. En `claims.json` se almacenan los b y c
del peor caso precisamente para que el numero publicado sea la cota, nunca la
version favorable.

## Multiplicidad

El repositorio corrio decenas de comparaciones con puerta a lo largo de seis
partes. Reportarlas todas sin corregir invita a la objecion evidente: una de
cada veinte despeja por azar. Se aplica **Holm-Bonferroni** sobre la familia de
afirmaciones con puerta.

Holm y no Bonferroni porque es uniformemente mas potente al mismo error por
familia; y no Benjamini-Hochberg porque estas son puertas confirmatorias y no un
cribado. Las pruebas indefinidas (`NaN`) quedan **fuera** de la familia: una
prueba que no ocurrio no puede consumir alfa.

## Estado de los datos: tres niveles

Cada afirmacion se clasifica por lo que sobrevive en disco, y la clasificacion
determina lo que puede decirse de ella.

<!-- caption: Niveles de disponibilidad de datos y que permite afirmar cada uno -->

| Nivel | Significa | Que permite |
|---|---|---|
| `per_item` | Existe un registro por elemento con su resultado, y se abrio | Prueba pareada real, IC, recuentos discordantes b y c |
| `counts_only` | Solo sobrevive el agregado del README | Prueba a partir de recuentos si el pareo es conocido; sin IC por elemento |
| `missing` | No hay datos crudos | **Ninguna.** Va a la cola de re-ejecucion |

Una afirmacion en `missing` no se defiende en el TFM. Se declara como pendiente
y se re-ejecuta, o se retira. El registro de re-ejecucion vive en
`thesis/rerun-backlog.md` con el comando exacto de cada una.

## Reproducir el analisis

<!-- caption: Comandos que regeneran el analisis completo desde el registro de afirmaciones -->

    .venv-ft/bin/python -m grounding.stats            # auto-comprobacion del modulo
    .venv-ft/bin/python -m pytest tests/test_stats.py # 33 aserciones de regresion
    .venv-ft/bin/python thesis/run_stats.py           # regenera el informe y la figura

El informe es un derivado: se regenera del registro de afirmaciones y no se
edita a mano.
