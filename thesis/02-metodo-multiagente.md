---
title: Desarrollo multiagente como método
subtitle: Qué cambia cuando el cuaderno de laboratorio lo escribe una flota de agentes bajo revisión humana
author: Javier Francisco Dibo Gómez
comment: Subsección del Capítulo 3 + Anexo B, 2026-07-21T21:10Z
locale: es
bibliography: refs.bib
---

## Por qué esto aparece en un TFM de Edge-AI

Este TFM no trata sobre desarrollo asistido por IA. Trata sobre ejecutar modelos
de lenguaje-visión en una Jetson Orin Nano. Si esta sección creciera hasta ser un
capítulo, invitaría a la objeción evidente: que el trabajo ha desplazado su centro
de gravedad hacia su propia metodología.

Se incluye igualmente, y acotada, por una razón que no es de moda sino de
**honestidad experimental**: la práctica totalidad del código, de los experimentos
y de la documentación de este proyecto se produjo con una flota de agentes bajo
revisión humana. Eso condicionó qué defectos aparecieron, cuáles se detectaron y
cuáles sobrevivieron meses. Un lector que evalúe la validez de las cifras del
cuaderno necesita saberlo, igual que necesita saber el modo de potencia de la
placa. Omitirlo sería la misma clase de omisión que el propio proyecto se pasó una
jornada corrigiendo (véase `experiments/2026-07-21-machine-disclosure/`).

**Decisión de ubicación, tomada antes de redactar:** subsección corta dentro del
Capítulo 3 (Plataforma, método y métricas) con el material extenso desplazado a un
Anexo B. *Se renuncia a:* la exposición que tendría como capítulo propio. *Se gana:*
que el centro de gravedad del documento siga siendo el problema de borde.
Confirmar con el tutor antes de ampliar.

## Qué es exactamente el método que se describe

No es «usar un asistente para escribir código». La unidad de trabajo fue un
**flujo orquestado**: un guion determinista reparte una tarea entre varios agentes
que trabajan en paralelo con contextos separados, cada uno devuelve una estructura
validada contra un esquema, y el hilo principal sintetiza. El humano fija el
objetivo, revisa la síntesis y decide qué se integra.

Tres propiedades importan para lo que sigue:

- **La amplitud es barata.** Barrer 76 directorios de campaña con cinco agentes en
  paralelo cuesta minutos. El barrido de divulgación de máquina (`wf_3704ea46-89b`)
  hizo 98 llamadas a herramientas y consumió 323.782 tokens de subagente en unos
  **237 segundos**. Ningún ser humano audita 76 campañas en cuatro minutos.
- **La profundidad no es barata, y el coste es invisible mientras ocurre.** Una
  pregunta de planificación lanzó 51 agentes y gastó 2,3 millones de tokens porque
  un `parallel` anidado dentro de un `pipeline` multiplicó el reparto sin que
  ningún número lo anunciara. La mitigación fue un tope explícito de ~6 agentes por
  flujo salvo petición contraria.
- **La autoverificación es el punto débil.** Un agente que se revisa a sí mismo
  reproduce su propio error con más confianza. Todo lo que funcionó en este
  proyecto para atrapar defectos fue *externo* al agente: una prueba, una regla
  mecánica, o un segundo agente con instrucciones adversariales.

## Lo que el método encontró y el trabajo en solitario no había encontrado

Estas son las cifras concretas, todas de este repositorio, todas trazables a un
*commit*.

- **La afirmación de portada era falsa tal y como estaba escrita.** Un barrido de
  cinco agentes sobre las 76 campañas (`2c7f7a3`) estableció que de las 65
  afirmaciones con puerta del registro, **solo 3 se midieron íntegramente en la
  placa**; 47 son compuestos entre la Orin y una RTX 3090. El `README.md` decía
  «todo corre en la placa, sin nube» en tres sitios distintos. La corrección está
  en `cd8cca6`.
- **Cuatro números publicados estaban mal, y dos de ellos no estaban en la lista de
  defectos conocidos** (`cd8cca6`): se citaba la precisión de arrastre de la
  configuración de 1024 px (0,849) cuando la desplegada es la de 768 px (0,830), y
  se publicaba «hasta 3,0 m/s» como techo de seguimiento cuando 3,0 m/s es
  exactamente el ajuste que **falló** (3/3 a 2,5 m/s, 0/2 a 3,0).
- **El re-análisis estadístico retroactivo** (`thesis/01-metodo-estadistico.md`)
  encontró que **33 de 65 diseños no podían alcanzar alfa = 0,05 con ningún
  resultado posible** y que solo **6 sobreviven a la corrección de Holm** (el
  registro creció después a 71 afirmaciones y los supervivientes a 11 por Parte;
  las cifras vigentes están en `thesis/stats-report.md`). Una
  búsqueda por `mcnemar|binomtest|scipy.stats` sobre el repositorio devolvía cero
  ficheros antes de ese trabajo.
- **Dos defectos silenciosos en la plataforma de vuelo**, encontrados por la puerta
  de capacidad P6.0 (`f1e58e9`). El más instructivo: ByteTrack solo re-emparejaba
  las pistas perdidas contra detecciones de puntuación baja, de modo que una pista
  perdida nunca se recuperaba — se sustituía por un identificador nuevo. La métrica
  «0 pérdidas de pista» quedó desautorizada de paso. El error de píxel pasó de
  64,7 a 36,0 al arreglarlo. La auditoría R-10 añadió después el segundo giro: la
  métrica era vacua, pero **no por el fallo** — sólo se dispara tras 1,5 s sin
  ninguna detección, y ese caso nunca se dio ni antes ni después. Un agente
  desautorizó la cifra correcta con el argumento equivocado, y hasta la
  auditoría eso se leía como diligencia.
- **Verdictos obsoletos en las superficies de lectura primera** (`751c504`):
  dieciséis memorias, el bloque de la Parte V de `CLAUDE.md` y trece secciones del
  libro de preguntas afirmaban como establecidos resultados que el re-análisis
  califica.

## Lo que el método produjo, que es la mitad que importa

Un informe que solo cuente los aciertos del método no es un informe, es publicidad.
Los defectos siguientes **los introdujo el mismo sistema**, y comparten una firma:
*son confiados, precisos y falsos*.

- **La cámara apuntaba al cielo durante semanas** (desde `5426ed0`). En Gazebo un
  cabeceo de `+pi/2` es *abajo*, no arriba. El log salía limpio, se escribían
  ficheros bien formados, el proceso terminaba con `exit 0`, y la conclusión
  asociada (RQ-S1.4) hubo que retirarla: se había medido a través de una imagen
  gris plana. Ningún agente miró un fotograma. De ahí salió la regla de
  verificación visual obligatoria del proyecto (`03d37bb`).
- **`b=39, c=7` en lugar de `b=4, c=2`.** Un intento de recalcular el brazo
  *shadow-RG* adivinó los nombres de dos campos JSON (`shadow.pass`, `target_id`)
  que no existen, y produjo un estadístico completamente equivocado sin ninguna
  señal de error. Un número que no se puede re-derivar dos veces no es un número.
- **Tres anclajes por número de línea, mal, escritos el mismo día en los dos
  documentos que una sesión nueva lee primero.** El propio documento que exige
  no fiarse de la primera lectura contenía tres citas que no resolvían. De ahí la
  regla de **citar por cadena entrecomillada, nunca por número de línea**: los
  números de línea se pudren en silencio con la siguiente edición.
- **Una tarea duplicada, a punto de abrirse dos veces.** Un hallazgo se redactó como
  «nueva tarea R-20» cuando R-20 ya existía y R-16 ya cubría el fondo. Segunda vez
  en el mismo programa. La mitigación es leer el tablero antes de añadir una fila,
  y está anotada en `thesis/REMEDIATION.md`.
- **La corrección equivocada de una cita correcta.** Al corregir el `README.md` se
  concluyó que la cifra «+21,2 pp» del tablero de remediación era aritmética sin
  respaldo, y se redactó una sustitución alrededor de otra línea base. Sí tenía
  respaldo: el control de fotograma completo del propio barrido da 64,0 % y
  85,2 − 64,0 = 21,2. **El tablero tenía razón y la lectura fresca no.** Un `grep`
  antes de confirmar lo detectó. La lección general no es «revisa la cita» sino
  «revisa también tu corrección de la cita».

## Por qué la mitigación que funcionó fue mecánica y no de redacción

La reacción intuitiva ante un agente que se equivoca es escribir una instrucción
mejor. En este proyecto **eso no funcionó de forma fiable** y hay evidencia
directa: la regla «no te fíes de tu primera lectura» estaba escrita, en mayúsculas,
en el fichero que contenía las tres citas erróneas. Una norma que pide amabilidad
no es un invariante.

Lo que sí funcionó fue convertir cada invariante en algo que falla solo:

- **`tests/test_thesis_integrity.py`** — 13 pruebas que fallan si una afirmación
  cita evidencia inexistente, si `n_effective` reclama más independencia que filas
  hay, si un número aparece sin la máquina que lo midió, o si un matiz del registro
  no llega al informe generado.
- **El patrón de trinquete.** Un invariante que aún no se cumple se escribe como un
  techo que solo puede bajar, de modo que `make test` sigue en verde mientras la
  remediación avanza. Una suite permanentemente en rojo enseña a ignorarla.
- **La regla «míralo»** (`03d37bb`): toda afirmación sobre lo que muestra un
  renderizado, una simulación o una superposición exige una imagen abierta de
  verdad. Un `exit 0` no es evidencia sobre píxeles.
- **La verificación de no-vacuidad.** Antes de dar por buena una prueba nueva se
  rompen los datos a propósito y se comprueba que falla. Una prueba que nunca ha
  fallado no se ha probado.
- **El protocolo de traspaso** (`431b090`): invariantes en `HANDOFF.md`, estado
  volátil en `thesis/REMEDIATION.md`, cumplimiento en las pruebas. Tres capas,
  porque un solo fichero de traspaso se desactualiza y nadie se entera.

La generalización defendible, y es la aportación metodológica de esta sección: **en
un flujo multiagente, la verificación tiene que ser un artefacto ejecutable, no un
párrafo.** El agente y el humano fallan de la misma manera — ambos leen un log
limpio y concluyen éxito — así que la única comprobación que sirve es la que no
depende de que ninguno de los dos se dé cuenta.

## La asimetría, dicha sin adornos

| | Flota de agentes | Persona sola |
|---|---|---|
| Amplitud (auditar 76 campañas) | minutos | días, y no se hace |
| Profundidad en un problema conocido | buena, con coste invisible | buena |
| Autoverificación | **mala**: repite su error con más confianza | mala, pero más lenta y con más dudas |
| Coste de un defecto silencioso | alto: se propaga a la documentación al instante | alto, pero se propaga más despacio |
| Sensibilidad a instrucciones escritas | baja bajo carga | media |
| Sensibilidad a una prueba que falla | **total** | total |

La conclusión operativa que este proyecto extrae: usar la flota para lo que la
flota hace bien —**barrer, enumerar, contrastar en paralelo**— y no pedirle nunca
que se certifique a sí misma. Cada resultado de un barrido entra en el repositorio
solo detrás de una comprobación mecánica o de una imagen que alguien abrió.

## Amenaza a la validez de esta propia sección

Esta sección la escribió el mismo sistema que evalúa, sobre un repositorio que ese
sistema produjo. No hay grupo de control: no existe una versión de este TFM hecha
por una persona sola con la que comparar, así que **ninguna afirmación de
«el método multiagente mejoró X» es una afirmación causal**. Lo que sí es
verificable, y es a lo que se limita el texto anterior, es el registro de
incidentes: cada defecto citado resuelve a un *commit* o a un README de campaña, y
cada mitigación resuelve a una prueba que hoy se ejecuta en `make test`.

## Anexo B — Registro de incidentes

<!-- caption: Incidentes de desarrollo multiagente citados en la subsección del Capítulo 3, con su evidencia -->

| Incidente | Signo | Evidencia |
|---|---|---|
| Cámara de Gazebo apuntando al cielo; RQ-S1.4 retirada | producido | `5426ed0`, regla en `03d37bb` |
| ByteTrack no re-emparejaba pistas perdidas; «0 pérdidas» vacua | encontrado | `f1e58e9` |
| `b=39, c=7` por adivinar un esquema JSON | producido | `HANDOFF.md`, invariante I7 |
| Tres anclajes por número de línea, erróneos, el mismo día | producido | `thesis/REMEDIATION.md`, R-6 |
| Tarea duplicada R-20/R-16 a punto de abrirse | producido | `thesis/REMEDIATION.md` |
| Corrección errónea de una cita correcta (+21,2 pp) | producido | `cd8cca6` |
| Auditoría de máquina sobre 76 campañas; 3 de 65 en la placa | encontrado | `2c7f7a3`, `5825b3a` |
| Cuatro números mal en el `README.md`, dos no listados | encontrado | `cd8cca6` |
| 33 de 65 diseños inalcanzables; 6 sobreviven a Holm | encontrado | `thesis/claims.json`, `1acb332` |
| 65 matices escritos y nunca renderizados en el informe | encontrado | `5b6f7ab` |
| Verdictos obsoletos en las superficies de lectura primera | encontrado | `751c504` |
| Flujo de 51 agentes y 2,3 M de tokens por un `parallel` anidado | producido | telemetría de sesión, fuera del repositorio — **la única fila de esta tabla que no resuelve a un *commit***; se cita porque motivó el tope de ~6 agentes por flujo |
