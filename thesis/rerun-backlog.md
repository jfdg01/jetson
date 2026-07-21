---
title: Cola de re-ejecución
subtitle: Afirmaciones cuyos datos crudos no sobreviven, y lo que costaría recuperarlas
author: Javier Francisco Dibo Gómez
comment: Derivado de thesis/claims.json, 2026-07-21T13:25Z
locale: es
---

## Por qué existe este fichero

`thesis/01-metodo-estadistico.md` clasifica cada afirmación por lo que sobrevive
en disco. Las de nivel `missing` **no se defienden en el TFM**: se re-ejecutan o
se retiran. Este documento es esa lista, con el comando exacto de cada una para
que una sesión futura no tenga que reconstruir el contexto.

Son **tres** sobre 65, lo cual es una buena noticia y conviene decirla: la regla
de cuaderno de laboratorio del proyecto — un `runs/<id>/results.json` por
ejecución — funcionó. Lo que falla no es el almacenamiento sino su cobertura, y
falla justo donde el aparato aún no existía (Parte I) o donde el resultado se
anotó en prosa del README sin volcado (Parte III, T2 y T3).

## Las tres

<!-- caption: Afirmaciones sin datos por elemento, con lo que falta y el coste de recuperarlas -->

| Afirmación | Qué falta | Coste | Comando |
|---|---|---|---|
| `P3-T2-permanence-reid` | Puntuaciones por clip; solo sobrevive la prosa del README | ~1 h en la 3090; clips y scorer versionados | `.venv-ft/bin/python -m grounding.eval.score_clips --clips experiments/2026-06-18-t1-temporal-contract/clips --arms memoryless,reid` |
| `P3-T3-closedloop-coverage` | Registros por vuelo; solo prosa del README | ~2 h; necesita n >= 10 vuelos por brazo para decir algo sobre una tasa | `runners/run_phase_c.py --arms memoryless,reid --reps 10` (renderizador CARLA) |
| `P1-S1.4-phaseC-vlm-closed-loop` | Píxeles válidos — la medida es inválida en origen | Superado; se re-pregunta en la Parte VI | `runners/run_phase_c.py` con CARLA, tras corregir el pitch de cámara |

## Lo que hay que entender de cada una antes de re-ejecutarla

### T2 — permanencia por re-identificación

El registro dice que la re-identificación lleva los cambios de identidad de 1 a 0
y la pureza de 0,725 a 1,000. **Recuperar el fichero no arregla el problema de
fondo.** Todo el PASS descansa sobre una única clip guionizada en la que un
cambio de identidad ocurre o no ocurre: una sola realización de Bernoulli, sin
intervalo y sin prueba. La segunda clip es un control que está en el techo por
diseño y no puede discriminar nada.

Re-ejecutarla tal cual reproduce el número y no mejora la afirmación. Si se va a
gastar la hora, hay que gastarla ampliando el banco de clips, no regenerando el
volcado.

### T3 — cobertura en lazo cerrado

Es **la n más exagerada del repositorio**. El salto de 49,2 % a 97,6 % son
fracciones de frames dentro de **un** vuelo de **un** escenario guionizado, y en
un lazo cerrado la salida del controlador en t determina los píxeles en t+1: una
divergencia temprana se propaga a todos los frames posteriores. Miles de frames
correlacionados no son miles de observaciones.

Por eso el comando pide `--reps 10`. Regenerar el vuelo único no hace la
afirmación defendible; solo la haría citable, que es distinto y peor.

### Fase C — seguimiento en lazo cerrado con VLM

Caso aparte: **hay datos y están deliberadamente sin extraer.** Sobreviven 13 CSV
de la Fase C con columnas completas por frame. No se tocan porque los píxeles de
entrada eran un frame de cielo en blanco — un pitch de `+pi/2` en Gazebo apunta
**abajo**, no arriba — y extraerlos produciría números bien formados sobre nada.

Es el caso concreto que motivó la regla de verificación visual del proyecto, y la
decisión correcta es dejarlo retirado y volver a hacer la pregunta sobre el rig de
CARLA de la Parte VI, no rescatar el número.

## Una cuarta categoría que no es re-ejecución

Hay dos afirmaciones marcadas `counts_only` cuyo p-valor **no se puede
reconstruir** aunque los datos existan en algún sentido, y que no van a esta cola
porque re-ejecutarlas no es lo que hace falta:

- **P5.2b**, el barrido de velocidad: sobrevive el rho = -0,06 pero no los valores por clip con los que calcular su p-valor. No importa mucho — el resultado es un nulo, y un nulo con rho prácticamente cero a n = 25 no cambia de lectura con un intervalo.
- **E20-acquire-latency**: `acquire_s` es esencialmente una función determinista del área del recorte (número de tokens de prefill); r1 y r2 coinciden a 0,00 s en 5 de 6 clips. **No debe llevar intervalo nunca.** Es un modelo de coste, no una muestra ruidosa, y la presentación honesta es el mecanismo más las dos medianas.

La distinción importa: la primera es una pérdida de datos y la segunda es una
propiedad del fenómeno. Solo la primera es deuda.
