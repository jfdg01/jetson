---
title: Método estadístico retroactivo
subtitle: Cómo se decide qué números del cuaderno de laboratorio son defendibles
author: Javier Francisco Dibo Gómez
comment: Marco de inferencia, 2026-07-21T13:10Z
locale: es
bibliography: refs.bib
---

## El problema que resuelve este documento

El proyecto se llevó como un cuaderno de laboratorio. Cada campaña pre-registraba
una puerta ("WSEL debe despejar 4/5"), ejecutaba el brazo, comparaba el recuento
con la puerta a ojo y anotaba un YES o un NO. Como forma de dirigir un programa
de investigación es legítima y funcionó: encontró la palanca del contrato de
entrega, descartó la super-resolución, mató la palanca de capacidad.

Como forma de defender una afirmación en un TFM no vale. Una búsqueda por
`mcnemar|binomtest|scipy.stats|statsmodels|wilson|p-value` sobre el repositorio
completo devolvía **cero ficheros** antes de este trabajo. Había decisiones
tomadas con n entre 2 y 6, sin intervalo de confianza, sin corrección por
multiplicidad y sin una sola prueba de hipótesis.

Este documento define el marco con el que se re-analizan esas campañas. La
implementación está en `grounding/stats.py` y su comportamiento está fijado por
`tests/test_stats.py`.

### Lo que este marco NO es

No es un intento de convertir NOs en YESes. Añadir p-valores a posteriori es
barato y casi siempre inútil. **La parte difícil, y la razón de que este módulo
exista, es negarse a calcular los que engañarían.** Buena parte de lo que sigue
son reglas de rechazo, no de cálculo.

Tampoco es un re-análisis exploratorio. Las puertas ya estaban pre-registradas;
lo que se añade es la incertidumbre que siempre debió acompañarlas, no una
segunda oportunidad de encontrar un efecto.

## Tres modos de fallo que el marco vigila

### Diseño equivocado

McNemar exige que los **mismos elementos** se midan bajo ambos brazos. Aplicarlo
a dos grupos independientes infla la significación. La implementación recibe
únicamente los recuentos discordantes, de modo que un conjunto no pareado no
puede llegar a la función por descuido; y `discordant_counts()` **descarta** los
elementos que solo aparecen en un brazo, porque contar una ejecución que falló
como un fracaso del brazo es cómo una caída se convierte en un resultado.

### Pseudo-replicación

"6 clips x 2 repeticiones" son 6 observaciones, no 12. Cinco celdas recortadas
del mismo vídeo no son cinco ensayos independientes. Miles de frames
consecutivos de un único vuelo son **un** vuelo: están autocorrelacionados, y
tratarlos como n = 30.000 es la forma clásica de fabricar significación a partir
de un solo ensayo. Toda afirmación lleva `n_effective` separado de `n_rows`, y
el informe imprime los dos junto con la razón por la que difieren.

Separarlos no basta: hay que **usar** el que corresponde. Un intervalo calculado
sobre `n_rows` y etiquetado con `n_effective` es peor que no dar intervalo,
porque reclama una precisión que nunca se compró. Ocurrió durante la propia
redacción de este marco — E17 imprimía `n = 1` junto a un IC de [0,000, 0,278]
construido con 10 filas de un mismo fallo determinista — y de ahí sale
`deflate_to_effective()`:

<!-- caption: Corrección por efecto de diseño aplicada antes de cualquier intervalo o p-valor -->

    k, n = deflate_to_effective(k_observado, n_filas, n_effective)

Conserva la proporción y sustituye el denominador por `n_effective`. Es una
corrección por efecto de diseño con `deff = n_rows / n_effective`, y es
deliberadamente tosca: **solo puede ensanchar el intervalo y debilitar el
p-valor, nunca al revés**, de modo que no puede fabricar un resultado. Con la
corrección aplicada, E17 pasa a [0,000, 0,793] sobre n = 1, que es lo que
realmente sostiene una única observación. El informe marca cada caso afectado con
`[deflactado desde k/n]` para que la deflación sea visible y no un ajuste
silencioso.

#### La unidad de independencia es el videoclip, no la escena

La regla anterior sólo es operativa si se fija **cuál** es la unidad
independiente, y aquí lo es el vídeo de origen. Dos escenas recortadas del mismo
clip comparten cámara, iluminación, altitud, comportamiento del objetivo y —lo
que más pesa en este sistema— el mismo par objetivo/distractor recurrente. Si el
seguimiento falla por deriva sobre ese par, falla en las dos escenas por la misma
causa, y contarlas como dos observaciones independientes duplica la evidencia sin
haber grabado nada nuevo.

El ejemplo trabajado es el banco de escenas de P5.18
(`experiments/2026-07-20-n25-select/scenes_p518.json`), que es también el que
usan P5.19 y P5.20. Contiene 27 escenas, 26 con puerta, y proceden de **13
videoclips distintos**:

<!-- caption: Composición del banco P5.18: 26 escenas con puerta sobre 13 clips de origen -->

| Clip | Escenas con puerta |
|---|---|
| `bike1` | 6 |
| `car9` | 4 |
| `car10` | 3 |
| `wakeboard8` | 3 |
| `wakeboard6` | 2 |
| 8 clips restantes | 1 cada uno |

De modo que `n_effective = 13`, no 26. Una lectura aún más estricta —`wakeboard6`
y `wakeboard8` son el mismo par surfista/lancha grabado dos veces— daría 10; se
adopta 13 porque el clip distinto es la unidad **mecánicamente comprobable**, y
`tests/test_thesis_integrity.py` la deriva del propio banco en lugar de confiar
en que la prosa diga la verdad.

**Y aquí hay que confesar algo, porque el patrón importa más que la cifra.** La
regla estaba aplicada en 49 de las afirmaciones del registro y **omitida
exactamente en las cuatro donde costaba un titular**: P5.18 y P5.19 figuraban
como 26 → 26, y sus notas de independencia discutían un problema de
independencia *distinto* (el solapamiento con las celdas de P5.16) sin mencionar
nunca el agrupamiento por clip. P5.20 deflactaba 52 → 26 por el emparejamiento
de dos tramos y se detenía justo antes de la regla del clip. Si fue motivado o
sólo desatento no es determinable y tampoco cambia nada: la forma del sesgo
apunta en la dirección que nos favorece, y un tribunal que lo descubra antes de
que nosotros lo declaremos lo leerá como ocultación. Se declara aquí.

Qué cambia al aplicarla, con precisión y sin dramatizar:

- **P5.18 WSEL** pasa de 22/26 a 11/13. La proporción es la misma (0,846) y el
  intervalo se ensancha a [0,58; 0,96]. Aparece además un hecho que la n inflada
  escondía: contra una puerta de 0,8 y con 13 unidades, **ningún resultado
  posible** alcanza alfa = 0,05, ni siquiera 13/13 (0,8¹³ = 0,055).
- **P5.18 SWAP** pasa de 17/26 a 8/13 y sigue fallando la puerta. Una deflación
  nunca puede rescatar un NO, porque sólo ensancha.
- **P5.19 SWAP**, la afirmación a la que la omisión beneficiaba, merece la frase
  exacta. El p-valor **no** cae de significativo a no significativo: con la n
  completa ya era p = 0,25, nunca fue significativo. Lo que la deflación elimina
  es el margen justo en la barra: la puerta pre-registrada de 20/26 celdas se
  convierte en 10/13 sobre una línea base de 8/13. El enunciado defendible es
  «no pudimos distinguir los brazos; la puerta se superó con un margen que no
  sobrevive al agrupamiento por clip», no «YES».
- **P5.20** exhibe una propiedad de la deflación que conviene enunciar antes de
  que la descubra un lector: su único par discordante (`c = 1` sobre 52) se
  redondea a cero al reescalar a 13, con lo que la lectura pasa de `p = 1,0` a
  *no hay prueba*. Las dos lecturas son igual de no significativas, y la segunda
  es la más honesta: con 13 unidades independientes nunca hubo resolución para
  ver un solo cambio. Le ocurre también a P5.13, P5.17 y E19.

Ninguno de los seis casos afectados tenía un resultado significativo que perder.
Ése es justamente el motivo por el que la corrección se hace sin regatear: no
cuesta ningún hallazgo y compra la única cosa que un capítulo de método puede
comprar, que es que sus reglas se apliquen igual cuando el resultado gusta y
cuando no.

#### Calibrar el agrupamiento en lugar de colapsarlo

Colapsar 26 celdas a 13 clips es correcto sólo bajo un supuesto que nadie midió:
que dos celdas del mismo clip son **la misma** observación. Ese supuesto tiene
nombre y valor — correlación intraclase ICC = 1 — y es el extremo del rango. La
corrección general por efecto de diseño es

<!-- caption: Corrección por efecto de diseño con la correlación intraclase medida -->

    deff = 1 + (n0 - 1) * ICC
    n_effective = n_rows / deff

con `n0` el tamaño medio de conglomerado. Colapsar es esa fórmula evaluada en
ICC = 1; ignorar el agrupamiento es evaluarla en ICC = 0. Ninguno de los dos es
una medición.

**Decisión de autor (R-29, 2026-07-23): medir el ICC.** Un ANOVA de un factor de
efectos aleatorios sobre el resultado por celda, agrupado por clip de origen, en
las 14 afirmaciones cuya deflación era **por agrupamiento**. Las deflactadas por
**determinismo** se quedan intactas — E18 («2 repeticiones idénticas»), P4-R16
(«un único banco de pruebas»), E13 (`id_switch_s` = 4,16 / 4,16 / 4,17): ahí el
ICC vale 1 de verdad, no por supuesto, y calibrarlo sería inventar réplicas.

**Dónde se rompe esto, y cuál es la salvaguarda.** Con 13 conglomerados y
diferencias pareadas casi constantes, el ICC puntual sale 0,000 en varias
afirmaciones, y usarlo tal cual deshace R-4 entero: P3-R13 volvería de 316 a 439
y el techo sombra de P5.18 de 13 a 48. Un ICC puntual de cero medido sobre pocos
conglomerados no es evidencia de independencia, es ruido. Por eso la deflación
**no** usa el estimador puntual sino el **límite superior del intervalo de
confianza al 95 %** del ICC (Searle), que es el valor conservador: pocos
conglomerados dan un intervalo ancho, el límite superior queda cerca de 1 y
`n_effective` se queda cerca del colapso. La calibración sólo se aleja del
colapso cuando los datos **descartan** una correlación alta, no cuando
simplemente no la ven.

Es la única operación de este marco que puede **subir** `n_effective`, y eso
contradice de frente la invariante I2 de `HANDOFF.md` («`n_effective` sólo puede
deflactar»). Se admite bajo cuatro condiciones, las cuatro comprobables:

1. la regla es mecánica y se aplica a las 14 afirmaciones agrupadas por igual, no
   a la que convenía;
2. deflacta con el límite superior, nunca con el estimador puntual;
3. el valor colapsado se publica como `collapsed_floor` y sigue siendo el
   análisis de sensibilidad conservador de cada afirmación;
4. `tests/test_thesis_integrity.py::test_icc_calibrated_n_effective_is_derived_not_chosen`
   recalcula `n_effective` a partir del ICC almacenado, de modo que la cifra es
   aritmética y no gusto: no se puede editar a mano sin romper la suite.

<!-- caption: Las 14 afirmaciones recalibradas: ICC puntual, límite superior al 95 % y n efectivo antes y después -->

| Afirmación | n filas | Conglom. | ICC | ICC sup. 95 % | deff | n ef. previo | n ef. |
|---|---:|---:|---:|---:|---:|---:|---:|
| P3-ROI-M2.0-512-ondevice | 439 | 316 | 0,039 | 0,226 | 1,09 | 316 | 404 |
| P3-R13-owlv2-vs-vlm | 439 | 316 | 0,000 | 0,138 | 1,05 | 316 | 417 |
| P3-SR-swin2sr-accuracy | 429 | 312 | 0,000 | 0,110 | 1,04 | 312 | 412 |
| P3-carry-OP768-accuracy | 186 | 93 | 0,185 | 0,373 | 1,37 | 93 | 135 |
| P5.2a-warm-generalization | 25 | 23 | 0,000 | 0,747 | 1,06 | 23 | 24 |
| P5.5-select-generalization | 5 | 3 | 0,000 | 0,901 | 1,54 | 4 | **3** |
| P5.13-dd-vs-rg-tie | 24 | 12 | 0,000 | 0,548 | 1,55 | 12 | 15 |
| P5.17-dd-vs-rg-tie-n56 | 56 | 28 | 0,000 | 0,365 | 1,37 | 28 | 41 |
| P5.18-n25-wsel | 26 | 13 | 0,454 | 0,795 | 1,72 | 13 | 15 |
| P5.18-n25-swap | 26 | 13 | 0,254 | 0,695 | 1,63 | 13 | 16 |
| P5.18-shadow-rg-ceiling | 48 | 13 | 0,000 | 0,354 | 1,89 | 13 | 25 |
| P5.19-swap-late-entry-rescue | 26 | 13 | 0,418 | 0,778 | 1,70 | 13 | 15 |
| P5.19-shadow-rg-ceiling | 50 | 13 | 0,086 | 0,445 | 2,18 | 13 | 23 |
| P5.20-carry-capacity | 52 | 13 | 0,000 | 0,150 | 1,42 | 13 | 37 |

Y el resultado que hace defendible la operación: **no recupera ni un
superviviente**. Diez antes, diez después; ninguna afirmación gana la corrección
de Holm y ninguna la pierde. Lo que sí cambia es de tres tipos:

- **Dos puertas dejan de ser inalcanzables por diseño.** P5.18 WSEL y SWAP
  corrían contra una puerta que ningún resultado posible superaba a n = 13; a
  n = 15 y n = 16 sí existe uno que la supera (15/15 y 16/16). Es exactamente lo
  que R-29 sostenía: parte de la inalcanzabilidad la había fabricado la
  deflación, no el diseño.
- **Tres lecturas «no hay prueba» vuelven a ser pruebas.** El artefacto denunciado
  arriba —el único par discordante de P5.20 redondeado a cero al reescalar—
  desaparece: P5.13, P5.17 y P5.20 vuelven a dar p = 1. Siguen sin ser
  significativas, pero ahora lo dice una prueba y no una división. El caso de E19
  no se toca: su deflación es por determinismo.
- **Dos resultados de la Parte III se refuerzan sin cambiar de bando.** P3-ROI en
  el dispositivo pasa de 2,50e-14 a 6,38e-18 y P3-R13 de 2,26e-07 a 2,21e-09. Ya
  sobrevivían a Holm y siguen sobreviviendo.

Hay además un caso que se **aprieta** en lugar de aflojarse: P5.5 baja de 4 a 3.
El registro le había asignado `n_effective = 4` sobre 3 clips reales — un defecto
de R-4 que la calibración destapó al exigir `collapsed_floor <= n_effective`. Y
un caso frontera que conviene enunciar antes de que lo encuentre un lector:
P3-carry-OP768 pasa de p = 0,096 a p = 0,030, significativo sin corregir; Holm
por Parte lo deja en 0,060 y sigue sin sobrevivir, así que se cita como no
significativo.

La regla de diseño que se lleva hacia adelante, y que ninguna calibración
sustituye: **la n cuenta conglomerados, no celdas.** Calibrar el ICC recupera
parte de la potencia que el colapso tiraba, pero la potencia que nunca se grabó
no la recupera nadie. Todo brazo futuro muestrea primero secuencias de origen
distintas y sólo después añade celdas dentro de una misma secuencia.

### Diseños que nunca pudieron responder a su pregunta

Es el aporte principal del marco y el más incómodo.

Una comparación pareada de 5 elementos **no puede** alcanzar p < 0,05 bilateral
aunque los cinco pares volteen a favor: el suelo es p = 0,0625. Un n = 6 llega
justo, y solo si el resultado es perfecto (6 de 6 discordantes en la misma
dirección, p = 0,031).

<!-- caption: Cuántos pares discordantes en una sola dirección hacen falta para alcanzar alpha = 0,05 bilateral -->

| Pares (n) | Discordantes necesarios | Se puede alcanzar |
|---|---|---|
| 5 | — | **No, con ningún resultado** |
| 6 | 6 (todos) | Solo si es perfecto |
| 12 | 6 | Sí |
| 25 / 26 | 6 | Sí |
| 56 | 6 | Sí |

La consecuencia es dura y hay que decirla: **un NO salido de un diseño de n = 5
no es evidencia de ausencia de efecto, es evidencia de ausencia de experimento.**
`min_discordant_for_significance()` lo calcula a partir de n **solo**, sin mirar
el resultado, que es lo que lo hace legítimo a posteriori — a diferencia de la
"potencia observada", que no es más que el p-valor recalculado.

El mismo argumento vale para las puertas de una sola proporción. Con n = 25, una
puerta pre-registrada del **90 %** es inalcanzable en términos estadísticos: un
25/25 perfecto da p = 0,9^25 = 0,072. Una puerta así solo puede despejarse
descriptivamente.

## Qué prueba se aplica a qué diseño

La elección la fija el **diseño**, nunca el p-valor que sale.

<!-- caption: Regla de selección de prueba por diseño experimental -->

| Diseño | Prueba | Por qué esta y no otra |
|---|---|---|
| Binario pareado (mismos clips, dos brazos) | McNemar exacto | Exacto y no ji-cuadrado: con b + c <= 5, que es lo habitual aquí, la aproximación no vale |
| Binario de un brazo contra una puerta | Binomial exacta + intervalo de Wilson | La puerta es una probabilidad, no un recuento |
| Binario no pareado | Fisher exacta | Grupos independientes |
| Continuo pareado (latencias, IoU, error de píxel) | Wilcoxon de rangos con signo + IC bootstrap | Las latencias tienen cola derecha y n es pequeño: la normalidad de una t haría un trabajo que no se ha ganado |
| Sin hipótesis pre-registrada | Solo intervalo de Wilson | Descriptivo, y etiquetado como tal |

Todo exacto. Ninguna aproximación normal: con estos n, ni la McNemar
ji-cuadrado ni el intervalo de Wald serían correctos, y las versiones exactas no
cuestan nada. Wald además falla justo donde vive este repositorio — en 24/25 da
un límite superior por encima de 1, y en 0/6 colapsa a [0, 0], afirmando certeza
absoluta a partir de seis observaciones.

### Una trampa que el marco bloquea explícitamente

Sobre las cifras de P5.2 la prueba **no pareada** de Fisher da un p **menor**
(1,2e-05) que la McNemar pareada (3,1e-05), porque McNemar descarta los 9 clips
concordantes y saca toda su potencia de los 16 discordantes. Es tentador
reportar Fisher.

Sería p-hacking por selección de prueba. Los 25 clips se midieron bajo ambos
brazos, luego las observaciones están pareadas y la prueba se deduce del diseño.
`tests/test_stats.py` fija esta relación con una aserción para que una sesión
posterior no pueda cambiar en silencio al p-valor más bonito y llamarlo mejora.

## Empates y pruebas que no existen

Tres campañas de simulación terminaron en empate casi perfecto (24/24 contra
24/24, 24/24 contra 23/24, 56/56 contra 55/56). Devolver p = 1,0 en el caso del
empate exacto se leería como "probado, brazos equivalentes". No lo es: son **0
pares discordantes**, es decir, ausencia de prueba en cualquier dirección.
`mcnemar(0, 0)` devuelve `NaN` a propósito y el informe lo imprime como
`indefinido`.

Un único par discordante — el caso de 23/24 y 55/56 — da exactamente p = 0,5. Es
la demostración más limpia posible de que esas campañas no podían separar los
brazos, con independencia de lo que hubiera salido.

## Cuando solo sobreviven los marginales

A veces se conserva el total de cada brazo pero no el pareo elemento a elemento,
de modo que b y c no son recuperables. La salida fácil sería descartar la
afirmación; la correcta es **acotarla**.

Los marginales fijan `b - c`. Basta recorrer todos los pares (b, c) compatibles
con esa diferencia y quedarse con el **peor** para la significación: el p-valor
resultante es una cota superior válida bajo cualquier pareo consistente con los
datos. Si esa cota ya cae por debajo de alfa, la conclusión no depende del pareo
perdido.

Es lo que rescata el resultado más fuerte de la Parte I. En HF contra GGUF los
marginales dan `b - c = 30`, luego `c` está en [0, 15]; el peor caso, `c = 15` y
`b = 45`, todavía da **p = 1,3e-04**. La catástrofe de exportación es
significativa se pareara como se pareara. En `claims.json` se almacenan los b y c
del peor caso precisamente para que el número publicado sea la cota, nunca la
versión favorable.

## Multiplicidad

El repositorio corrió decenas de comparaciones con puerta a lo largo de seis
partes. Reportarlas todas sin corregir invita a la objeción evidente: una de
cada veinte despeja por azar. Se aplica **Holm-Bonferroni** sobre la familia de
afirmaciones con puerta.

Holm y no Bonferroni porque es uniformemente más potente al mismo error por
familia; y no Benjamini-Hochberg porque estas son puertas confirmatorias y no un
cribado. Las pruebas indefinidas (`NaN`) quedan **fuera** de la familia: una
prueba que no ocurrió no puede consumir alfa.

**Qué es «la familia» es una convención, no un cálculo, y cambia el recuento.**
Decisión de autor (R-30, 2026-07-23): **la familia es la Parte**. Holm se aplica
dentro de cada capítulo empírico y no sobre el registro entero, porque cada Parte
es una pregunta de investigación distinta, pre-registrada con meses de diferencia,
y ninguna afirmación se eligió comparando Partes entre sí. El contraargumento es
fuerte y se registra: con m entre 2 y 15 en casi todas las Partes, Holm por Parte
apenas corrige, y una corrección que casi nunca cambia nada compra credibilidad
que no ha ganado. Por eso la familia global se reporta **en una columna contigua
del informe** como análisis de sensibilidad declarado, no se esconde. El autor
vio ambos números antes de elegir, y decirlo forma parte de la elección. Los
tamaños de familia, las dos afirmaciones que cambian de bando y las dos
dependencias que inflan m en cualquiera de las dos versiones están en
`thesis/stats-report.md`, sección «La familia de corrección».

## Estado de los datos: tres niveles

Cada afirmación se clasifica por lo que sobrevive en disco, y la clasificación
determina lo que puede decirse de ella.

<!-- caption: Niveles de disponibilidad de datos y qué permite afirmar cada uno -->

| Nivel | Significa | Qué permite |
|---|---|---|
| `per_item` | Existe un registro por elemento con su resultado, y se abrió | Prueba pareada real, IC, recuentos discordantes b y c |
| `counts_only` | Solo sobrevive el agregado del README | Prueba a partir de recuentos si el pareo es conocido; sin IC por elemento |
| `missing` | No hay datos crudos | **Ninguna.** Va a la cola de re-ejecución |

Una afirmación en `missing` no se defiende en el TFM. Se declara como pendiente
y se re-ejecuta, o se retira. El registro de re-ejecución vive en
`thesis/rerun-backlog.md` con el comando exacto de cada una.

## Reproducir el análisis

<!-- caption: Comandos que regeneran el análisis completo desde el registro de afirmaciones -->

    .venv-ft/bin/python -m grounding.stats            # auto-comprobación del módulo
    .venv-ft/bin/python -m pytest tests/test_stats.py # 33 aserciones de regresión
    .venv-ft/bin/python thesis/run_stats.py           # regenera el informe y la figura

El informe es un derivado: se regenera del registro de afirmaciones y no se
edita a mano.
