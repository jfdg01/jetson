# Los ejes del sistema, y cuál queda sin tocar

**Escrito:** 2026-08-05T11:09Z (Madrid). **Coste:** 0 h de dispositivo. Inventario, no experimento.

**Alcance:** el sistema entero (Partes I-VI), no una campaña. Responde una pregunta de diseño:
**¿cuál es la palanca más ortogonal disponible?** Ortogonal respecto de todo lo que este proyecto ya
ha medido, y disponible con los rigs que ya existen.

No hay ningún número nuevo aquí. Es una clasificación, y una clasificación la sostiene su criterio,
no un contraste. El criterio está en el §2, escrito antes de aplicarlo en el §5.

## 1. El sistema, por etapas

Estrella polar: un operador dice "sigue ese coche blanco" sobre el vídeo de un dron y el dron lo
hace. Las etapas por las que pasa esa frase:

```
frase NL --> [grounding: Qwen2-VL-2B Q8_0] --> caja
caja --> [mantenimiento: SAM2 tiny 640, TRT fp16, K7/M16/anillo 16] --> caja por fotograma
caja --> [entrega: warm-start maintain-and-deliver] --> objetivo vivo
objetivo --> [control: PID en cascada --> MAVLink --> ArduCopter] --> el copter se mueve
el copter se mueve --> [render esclavo de pose: CARLA] --> píxeles nuevos
```

El lazo se cierra en la última flecha: los píxeles son consecuencia del propio control.

## 2. El criterio, escrito antes de aplicarlo

Una palanca es **ortogonal** si cumple las dos:

- **(a)** No mueve ninguna perilla que un eje ya medido moviera. Independencia de diseño.
- **(b)** Su modo de fallo no es uno que un eje ya medido ya explique. Independencia de mecanismo.
  Sin (b), "ortogonal" degenera en "lo mismo con otro nombre".

Y es **disponible** si se mide con los rigs, datos y modelos que ya existen, sin construir nada
nuevo.

Ortogonal **no** significa importante. Es una propiedad de la información que produce, no de su
valor. El §6 separa las dos cosas a propósito.

## 3. Los ejes que el proyecto ya movió

| eje | qué perilla mueve | dónde se midió | estado |
| --- | --- | --- | --- |
| **S1** modelo de grounding | qué VLM | Parte I Stage 1, bake-off de la Parte IV (2026-06-30), Parte II | elegido y congelado (Qwen2-VL-2B Q8_0, IoU@0.25 62.6%) |
| **S2** modelo de seguimiento | qué tracker | Parte III, EXP-9 (tiny/small/base_plus), barrido 2026-07-28 | agotado; `tiny` se queda |
| **S3** resolución y geometría del recorte | cuántos píxeles, y de dónde se cortan | E20-E23, EXP-1, EXP-4, EXP-5, EXP-6, barrido E2/E3 | **el eje más trabajado del proyecto**; 640 desplegado, 1024 con puerta de tamaño |
| **S4** memoria del seguidor | K, M, anillo P | EXP-8, P5.20 | cerrado con adopción (anillo 16, 670 MB liberados); K y M inertes |
| **S5** runtime y cuantización | fp16 / TRT / Q8_0 / INT8 | E1, EXP-9a, Parte II | TRT fp16 adoptado (+19.5%); INT8 acotado por aritmética a ~+5%, no corrido |
| **S6** latencia y ritmo de entrega | cuándo llega la caja | E18, E18-n25, P6.7, P6.2-DELIVERY, barrido E4 | **aquí vive el resultado insignia** |
| **S7** control | ganancias, acoplamiento del lazo | P6.2-COUPLING, P6.2-DELIVERY | **delgado: un nulo acotado y nada más** |
| **S8** presencia / abstención | cuándo declarar que el objetivo se fue | Parte V, barrido E6 (25 de 57 notas) | muerto; ninguna receta transfiere |
| **S9** interfaz del operador | frase NL contra clic | E20, EXP-2 | tocado y sin potencia (MISS a n=26) |
| **S10** dominio y escena | UAV123 / TLP / CARLA | P6.1, banco P5.9-P5.13, nota 31 del barrido | tocado |

## 4. Los ejes que nadie ha movido

| eje | qué perilla mueve | por qué está sin tocar |
| --- | --- | --- |
| **S11** la designación dentro del lazo | oráculo -> VLM real volando | RQ-S1.4 está **RETRACTADA a UNANSWERED**; P6.2-DELIVERY lo excluye por escrito |
| **S12** telemetría dentro de la percepción | información **no visual** del propio vehículo | ninguna Parte, nunca |

**S11** no es un descuido: es el límite declarado del resultado insignia. P6.2-DELIVERY dice, literal,
que "grounding was held constant via oracle target designation (the deployed q8_0 is
non-discriminative at 45 m nadir, G6), so the verdict is a control-coupling claim conditional on
correct designation — it does **not** license a grounding+delivery claim". Y RQ-S1.4 ("replacing the
oracle with the best zero-shot VLM: how much does tracking degrade?") se retractó a UNANSWERED
cuando se descubrió que su respuesta original se midió con la cámara apuntando al cielo.

**S12** tampoco es descuido, pero sí es invisible: **todas** las señales que este proyecto ha medido
en seis Partes se derivan de píxeles. `conf`, `conf_cos`, la deformación de caja, el IoU, el error en
píxeles del control — todas. No hay una sola medida de percepción que use la actitud, la velocidad o
la posición que el propio autopiloto conoce con exactitud.

## 5. La determinación

| candidato | (a) independiente | (b) mecanismo propio | disponible | veredicto |
| --- | --- | --- | --- | --- |
| **S12 telemetría** | **sí** — cambia la *fuente de información*, no la perilla | **sí** — nada medido explica un residuo de ego-movimiento | **sí, y ya está grabada** | **la más ortogonal** |
| S11 designación real | parcial — el eje (grounding) sí está medido, aislado; lo que falta es la composición | parcial — el fallo esperado es el 37% de designaciones malas que la Parte II ya cuantificó | sí | **la de más valor**, no la más ortogonal |

**La palanca más ortogonal disponible es S12: meter la telemetría dentro de la percepción.**

Disponible no es una estimación: `runners/carla_render.py:177` **ya acumula `poses` por fotograma**,
alimentado por `MavlinkPose`, que drena mensajes `ATTITUDE` en `runners/sitl/offboard.py:274`. La
pose exacta de la cámara en cada fotograma ya está registrada. Hoy solo sirve para **colocar** la
cámara; nunca para **comprobar** lo que la cámara ve.

## 6. Qué desbloquea, y por qué no es solo un hueco

Un eje puede estar intacto por irrelevante. Este no:

1. **Rompe el bloqueo de S8.** La nota 50 del barrido cerró el eje de presencia con un argumento de
   disponibilidad, no de señal: *en vuelo no hay etiquetas*, así que ninguna banda se puede calibrar.
   La telemetría **se etiqueta sola**: dado el movimiento propio conocido y suelo plano, se predice a
   dónde debería moverse un punto estático del mundo; el residuo entre eso y el movimiento observado
   de la caja no necesita verdad fundamental ni umbral por secuencia.
2. **Es el vigilante que el arco del clamp no encontró.** Las notas 54 a 57 midieron que `conf_cos`
   ve el descarrilamiento con AUC 0.963 y que aun así **ningún corte transfiere** entre secuencias.
   Un residuo geométrico tiene unidades físicas (píxeles de desajuste contra píxeles predichos), no
   una escala por objetivo: es la clase de cantidad que sí admite un umbral fijo.
3. **Engorda S7,** que es el eje más flaco del sistema: un solo contraste, y encima un nulo acotado.

## 7. Los tres contras, antes de que los encuentre nadie

1. **El render es esclavo de la pose.** En este rig la telemetría y los píxeles son consistentes
   **por construcción**: la cámara se coloca exactamente donde dice el autopiloto. El residuo de
   ego-movimiento en simulación es, por tanto, sin ruido. Cualquier número que salga es un **techo**,
   no una transferencia: el vuelo real trae brazo de palanca, desfase de marcas de tiempo y
   vibración. Esto se pre-registra como límite, no se descubre después.
2. **Circularidad en lazo cerrado.** Si la caja conduce al copter, la pose del copter es en parte
   consecuencia de la caja, y comprobar una con otra no es independiente. El diseño tiene que
   romperlo: tramo con el oráculo conduciendo, o pose escriptada, que es justo lo que
   `scripted_pose` ya ofrece.
3. **Compensar no es lo mismo que verificar, y compensar ya está medido como nulo.** La nota 20 del
   barrido midió que predecir el movimiento en la *entrada* no compra nada (a SAM2 le da igual dónde
   caiga el objetivo dentro de la ventana), y P6.2-COUPLING midió que el ego-movimiento autoinducido
   **no** degrada el carry (nulo acotado). Las dos cierran la lectura de S12 como **compensador**.
   Lo que queda abierto, y es lo que se propone, es S12 como **verificador**. Si alguien lee esta
   nota como "compensar el movimiento de cámara", está leyendo el eje muerto.

## 8. Cómo no sobreleer esto

- **Ortogonal no es prometedor.** Significa que su resultado no está ya implícito en lo medido. S12
  puede salir nulo, y el §7.3 da dos razones medidas para esperarlo.
- **S11 es más importante que S12.** Es la exposición mayor de la tesis: el resultado insignia se
  apoya en una designación que el modelo desplegado no sabe producir a 45 m nadir. Que no gane aquí
  es porque el criterio pregunta por ortogonalidad, no por valor. Si la pregunta fuera "qué medir
  ahora", la respuesta sería S11.
- **Los ejes son un corte, no una verdad.** Otra persona los parte en otro sitio. El criterio del §2
  está escrito para que se pueda atacar.
- **Nada de esto está medido.** No hay brazo, ni pre-registro, ni corrida. Es un inventario.

## 9. Qué no se miró

- **Sin verificación visual.** No hay píxeles nuevos: es lectura de las ledgers y del código.
- No se cronometró qué cuesta leer y alinear la telemetría por fotograma.
- No se comprobó si el desfase entre la marca de tiempo de `ATTITUDE` y la del fotograma renderizado
  es despreciable; en un rig esclavo de pose debería serlo, pero "debería" no es una medida.
- S11 no se diseñó. Solo se ubicó.

## 10. Interpretación, marcada como interpretación

Lectura mía: el proyecto tiene un sesgo de eje bien identificable. S3 (resolución y recorte) y S6
(latencia) concentran la mayoría del esfuerzo reciente porque son baratos de mover y dan números
limpios. S7 y S11 están flacos porque son caros. Y S12 está vacío por una razón distinta y más
interesante: **nadie lo vio**, porque seis Partes de trabajo en percepción han asumido tácitamente
que percibir es mirar. El vehículo sabe cosas de sí mismo que no están en la imagen, ese
conocimiento ya se está grabando en cada corrida, y ninguna medida del proyecto lo usa.
