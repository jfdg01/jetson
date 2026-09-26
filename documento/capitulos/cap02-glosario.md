# 2. Glosario y vocabulario

Este capítulo fija el vocabulario del documento. Cada término se define una vez y se
usa con ese significado en todos los capítulos siguientes. Los términos técnicos se
escriben en inglés, que es como los nombra la literatura del campo, y se definen en
castellano.

El glosario se ordena en cuatro bloques y, dentro de cada bloque, alfabéticamente.
Los conceptos van primero porque los demás bloques los usan. Cuando el repositorio
de trabajo usó una misma palabra para dos cosas distintas, la entrada lleva una línea
`No es` que separa los dos sentidos. Esa ambigüedad es real y aparece en los registros
originales; la entrada la declara en vez de esconderla.

Los números decimales se escriben con punto en todo el documento, igual que en los
registros de los que salen. Las unidades se escriben con espacio y símbolo correcto:
`15 W`, `159.4 ms`, `67 °C`.

## 2.1 Conceptos

- **`abstención`**: la decisión del seguidor de no emitir caja en un fotograma porque
  estima que el objetivo no está presente. Un brazo que nunca se abstiene entrega
  siempre una caja, y por tanto produce falsos positivos durante los huecos.

- **`acquire`** (adquisición): la operación que convierte una orden en lenguaje natural
  en una primera caja sobre el objetivo. Es el arranque del seguimiento, no su
  mantenimiento.

- **`anchor`** / **`re-anchor`** (ancla, re-anclaje): una llamada al modelo de grounding
  que fija o corrige la caja del objetivo durante el seguimiento. El seguidor barato
  propaga entre anclas; el ancla es la que cuesta.

- **`arco`**: un conjunto de experimentos encadenados que persigue una misma pregunta
  hasta cerrarla, con resultado positivo o negativo. Este documento organiza los
  capítulos 5 a 11 por arcos.

- **`arm`** (brazo): una configuración concreta que se mide dentro de un experimento,
  identificada por un nombre corto como `sam2_c640` o `dam4sam_t960`. Los brazos de una
  misma tanda comparten protocolo, clips y orden, y solo se diferencian en la variable
  manipulada.

- **`carry`**: la propagación de la caja del objetivo entre anclas, hecha por un modelo
  de seguimiento barato que mantiene memoria del objeto. Es el mecanismo central de la
  Parte V: mantener candidatos vivos durante la ventana previa a la orden.
  *No es* la constante retirada `CARRY_HZ`, que nombraba una frecuencia de refresco y no
  el mecanismo.

- **`closed loop`** (lazo cerrado): el régimen en el que la caja que produce la percepción
  gobierna el control del vehículo, de modo que los píxeles del fotograma siguiente son
  consecuencia de la decisión anterior. Lo contrario es el **`lazo abierto`**, donde el
  vídeo está grabado y la salida del sistema no cambia lo que se ve.

- **`cold acquire`**: una adquisición que arranca sin ningún estado previo sobre la
  escena. Es el caso peor de latencia y el que motiva el warm start.

- **`consumidor`**: la parte del sistema que recibe las cajas del seguidor y las usa, por
  ejemplo un controlador de vuelo. Varias palancas de este trabajo actúan sobre el
  consumidor y no sobre el modelo, y por eso cuestan cero tiempo de dispositivo.

- **`coupling`** (acoplamiento): el efecto de cerrar el lazo sobre la calidad de la
  percepción. Se mide comparando el mismo seguidor con el control activo y con el
  control desacoplado.

- **`crop`** (recorte): una subimagen que se extrae del fotograma y se alimenta al modelo
  en lugar del fotograma completo. Aparece en dos sitios distintos y conviene no
  confundirlos: el `ROI crop` que abarata el prefill del modelo de grounding, y la
  `ventana de recorte` del seguidor, que acota dónde busca al objetivo.
  *No es* sinónimo de baja resolución: un recorte se alimenta a su tamaño nativo o
  escalado, y esas son dos perillas separadas.

- **`decode`**: la fase de generación de tokens de un modelo de lenguaje, después del
  prefill. Su coste crece con el número de tokens de salida y no con el tamaño de la
  imagen.

- **`delivery`** (entrega): la operación de devolver, cuando llega la orden, la caja del
  candidato que ya se venía manteniendo. Se opone a `select`, que además tiene que elegir
  entre varios candidatos.

- **`distractor`**: un objeto de la escena parecido al objetivo, y en el caso peor de la
  misma clase y el mismo color. Es la causa principal de los cambios de identidad.

- **`DRM`** (distractor-aware memory): la política de memoria de DAM4SAM, que separa la
  memoria del objetivo de la de los distractores. No necesita reentrenamiento: usa el
  mismo checkpoint de SAM2.1.

- **`drift`** (deriva): la degradación progresiva de la caja durante el seguimiento sin
  ancla, hasta que deja de cubrir el objetivo.

- **`FOH`** (first-order hold, retención de primer orden): la regla de consumidor que,
  entre dos respuestas del seguidor, navega la última caja con la velocidad estimada en
  vez de congelarla. Se opone a **`ZOH`** (zero-order hold), que la congela.

- **`gap`** (hueco): un tramo de fotogramas en el que el objetivo no aparece en el ground
  truth, por oclusión o por salida del campo de visión. El comportamiento al final del
  hueco es el reenganche.

- **`grounding`**: la tarea de localizar en una imagen el objeto que describe una
  expresión en lenguaje natural, y devolver su caja. Es el punto de entrada del sistema.

- **`ground truth`** (GT): la anotación de referencia contra la que se puntúa una
  predicción. En vídeo real viene del dataset; en simulación viene de la posición
  verdadera del actor.

- **`idle window`** (ventana de espera): el tramo de vídeo anterior a la orden del
  operador. La Parte V parte de que ese tramo es cómputo gratis, porque el sistema ya
  está en el aire y todavía no tiene nada que hacer.

- **`lead`**: la palanca que centra la ventana de recorte donde se predice que estará el
  objetivo, es decir, la corrección de movimiento aplicada a la **entrada** del modelo.
  Se opone a FOH, que aplica la misma estimación a la **salida**.

- **`lock`** / **`relock`** (enganche, reenganche): el enganche es el estado en el que el
  seguidor mantiene la identidad correcta del objetivo. El reenganche es la recuperación
  de ese estado después de un hueco o de una pérdida.

- **`LoRA`** (low-rank adaptation): la técnica de ajuste fino que entrena matrices de bajo
  rango añadidas al modelo y deja congelados los pesos originales. Es la única forma de
  ajuste fino usada en este trabajo.

- **`LT`** (long-term): un brazo de seguimiento que añade una política de ausencia y
  redetección sobre el seguidor base, de modo que puede declararse perdido y volver a
  encontrar el objetivo.

- **`maintain-and-deliver`**: la tesis central de la Parte V y la Parte VI. El sistema
  mantiene vivo el objetivo durante la ventana de espera y entrega la caja cuando llega
  la orden, en lugar de arrancar una adquisición fría en ese momento.

- **`object permanence`** (permanencia del objeto): la capacidad de sostener la identidad
  de un objetivo a través de una oclusión, un cruce o una salida temporal del campo de
  visión.

- **`oracle`** (oráculo): una fuente de información perfecta que sustituye a un módulo
  para aislar el resto del sistema. Un experimento con designación por oráculo mide el
  control sin el ruido del grounding, y su conclusión queda condicionada a que la
  designación sea correcta.

- **`paced`** (a ritmo real): el protocolo de medida en el que el vídeo avanza a su
  frecuencia real y el seguidor solo contesta a los fotogramas que le da tiempo a
  procesar. El fotograma que no se procesa cae. Se opone al protocolo de **`paridad`**,
  donde el seguidor ve todos los fotogramas y la latencia no penaliza.
  *No es* una medida de precisión pura: bajo `paced`, un modelo más lento pierde por
  llegar tarde aunque sus cajas sean mejores.

- **`pose-slaved renderer`** (renderizador esclavo de la pose): la arquitectura de la
  Parte VI. La física del vehículo la calcula el simulador de vuelo, y el renderizador
  solo coloca la cámara en la pose resultante. Esto es lo que permitió cambiar de
  renderizador sin tocar el control.

- **`prefill`**: la fase en la que un modelo de lenguaje procesa la entrada antes de
  generar el primer token. Su coste crece con el número de tokens de imagen, es decir,
  con la resolución.

- **`preregistro`**: la práctica de escribir el README del experimento, con su comando,
  sus hipótesis y sus criterios, antes de ejecutarlo. Impide que el diseño se ajuste al
  resultado.

- **`presencia`**: la señal que estima si el objetivo está o no está en el fotograma
  actual. Es distinta de la calidad de la caja: un brazo puede dar cajas buenas y no
  saber cuándo el objeto ha desaparecido.

- **`prompt`** / **`referring expression`**: la orden en lenguaje natural que designa al
  objetivo, por ejemplo `el coche rojo que gira a la izquierda`.

- **`quantization`** (cuantización): la reducción de la precisión numérica de los pesos
  para bajar memoria y latencia. Los formatos usados aquí son `Q8_0` y `Q4_K_M` sobre
  GGUF, y `fp16` y `bf16` en PyTorch y TensorRT.

- **`re-ID`** (reidentificación): la comparación de apariencia que decide si el objeto que
  reaparece es el mismo que se perdió.

- **`ROI`** (region of interest): la región del fotograma donde se espera encontrar al
  objetivo, normalmente derivada de la caja anterior.

- **`select`** (selección): la operación de elegir, cuando llega la orden, cuál de varios
  candidatos mantenidos corresponde a la expresión del operador.
  *No es* `delivery`: la entrega devuelve el candidato ya designado, la selección tiene
  además que discriminar. Este trabajo defiende la entrega como resultado y presenta la
  selección como propuesta medida.

- **`SOT`** (single object tracking): el seguimiento de un único objeto, inicializado con
  una caja en el primer fotograma y sin detector de clase. Es el régimen de los seguidores
  del capítulo 11.

- **`terse`**: el formato de salida corto del modelo de grounding, sin JSON ni corchetes,
  adoptado para recortar tokens de decode.

- **`upscales`** (puerta): el filtro que descarta una corrida cuando la resolución de
  entrada del modelo supera la resolución nativa del clip, porque en ese caso el brazo
  estaría puntuando sobre píxeles inventados. En UAV123 afecta a los cinco clips de
  720x480, que son los `uav*`.

- **`ventana`** (window) frente a **`entrada`** (input): la ventana es la región del
  fotograma que se recorta; la entrada es el tamaño al que se alimenta esa región al
  modelo. Un brazo llamado `c640` mueve las dos a la vez, y hacen falta brazos cruzados
  como `w640_i512` para separarlas.
  *No es* lo mismo que la resolución del modelo: en la familia SAM2 la etiqueta `FULL`
  de algunas campañas significa resolución completa, no fotograma completo.

- **`warm start`**: el arranque en caliente. El sistema empieza a mantener candidatos
  antes de que llegue la orden, de modo que la orden encuentra trabajo ya hecho.

## 2.2 Métricas

- **`AUC`** (área bajo la curva de éxito): la métrica estándar de SOT. Se recorre un umbral
  de IoU de 0 a 1 y se integra la fracción de fotogramas que lo superan. La convención
  importa: sobre la misma corrida, la convención de la casa daba `68.9` y la convención de
  `pytracking` daba `67.1`, y la tolerancia de replicación era `1.0`. Este documento usa
  siempre la convención de `pytracking`.

- **`center_std`**: la desviación típica de los centros predichos sobre un conjunto de
  evaluación. Sirve para detectar el colapso de modo: un modelo que devuelve siempre la
  misma caja tiene `center_std` cercana a cero.

- **`gm_ox`** (MaxGM de OxUvA): la media geométrica entre la tasa de localización correcta
  cuando el objetivo está y la tasa de rechazo correcto cuando no está. Es la métrica que
  premia a un brazo capaz de abstenerse, y la única que respalda los brazos LT.

- **`hit@0.5`**: la fracción de casos con IoU mayor o igual que `0.5`. Criterio estricto.

- **`IoU`** (intersection over union): el solape entre la caja predicha y la caja de
  referencia, dividido por su unión.

- **`IoU@0.25`**: la fracción de casos con IoU mayor o igual que `0.25`. Es el criterio de
  grounding aéreo de este trabajo, porque a esas escalas un solape de `0.25` ya identifica
  al objeto correcto.

- **`J/frame`** (julios por fotograma): la energía consumida por fotograma procesado,
  medida sobre los raíles del sensor INA3221 de la placa. Es una métrica de hardware, no
  una derivada de la latencia.

- **`mIoU`**: la media del IoU sobre todos los fotogramas de una secuencia, contando como
  cero los fotogramas sin respuesta. Bajo el protocolo `paced`, `mIoU` mezcla calidad de
  caja con retardo de entrega, y por eso no basta ella sola.

- **`p50`, `p95`, `p99`**: los percentiles de la latencia por fotograma. Se reportan en vez
  de la media porque la cola es la que rompe un lazo de control.

- **`parse rate`**: la fracción de respuestas del modelo de grounding de las que se puede
  extraer una caja bien formada.

- **`presence_auc`**: el área bajo la curva ROC de la señal de presencia tratada como
  clasificador de la pregunta `el objetivo está en este fotograma`.

- **`px_err`**: el error en píxeles entre el centro predicho y el centro de referencia.

- **`TTFT`** (time to first token): el tiempo hasta el primer token generado. Es el prefill
  más la primera pasada de decode, y es lo que percibe el operador como latencia de
  respuesta.

- **`tok/s`**: los tokens de decode por segundo.

- **`valid_rate`**: la fracción de llamadas que devuelven una caja utilizable aguas abajo.

- **`n`**: el número de unidades independientes de una comparación, normalmente clips o
  corridas. Este trabajo exige `n >= 25` en cualquier brazo del que dependa una decisión.

- **`mediana pareada`**: el estadístico que se usa en casi todas las comparaciones. Cada
  clip se puntúa con los dos brazos y se toma la mediana de las diferencias, lo que
  elimina la dificultad desigual entre clips.

- **`corrección de Holm`**: el ajuste por comparaciones múltiples que se aplica dentro de
  cada Parte. Un resultado que no sobrevive a Holm no se enuncia como conclusión.

## 2.3 Modelos y componentes de software

- **`AsymTrack-B`**: seguidor SOT asimétrico de 3.36 M de parámetros, licencia MIT. Es el
  brazo barato del capítulo 11: cuesta 3.4 veces menos que el punto de operación de SAM2 y
  empata con él sin pausar.

- **`ByteTrack`**: asociador de detecciones entre fotogramas, sin apariencia. Es el
  seguidor barato de las Partes I a IV, por debajo de las anclas del modelo de grounding.

- **`CLIP`**: modelo de imagen y texto usado como puntuador de recortes candidatos en los
  pilotos de selección.

- **`DAM4SAM`**: SAM2.1 con memoria consciente de distractores. Mismo checkpoint, cero
  entrenamiento, solo cambia la política de memoria.

- **`Florence-2-large`**: modelo de visión y lenguaje de Microsoft, brazo del bake-off de
  backbones que se canceló sin correr.

- **`Gemma`**: familia de modelos de lenguaje de Google, barrida en la Parte I en varias
  generaciones y cuantizaciones.

- **`GGUF`**: el formato de fichero de modelo de `llama.cpp`. Es el artefacto que se
  despliega en la placa.

- **`InternVL3-2B`**: modelo de visión y lenguaje, brazo del bake-off de backbones.

- **`llama.cpp`**: el motor de inferencia de modelos de lenguaje que corre en la placa,
  compilado en `aarch64` y fijado al commit `57fe1f0` durante todo el trabajo.

- **`Llama-3.2`**: modelo de lenguaje de 3B de parámetros usado como referencia inicial de
  la placa en la Parte I.

- **`MAVLink`**: el protocolo con el que el sistema envía las consignas al controlador de
  vuelo.

- **`OWLv2`**: detector de vocabulario abierto, usado como control externo frente al
  modelo de grounding propio.

- **`PaliGemma2-3B`**: modelo de visión y lenguaje de Google que emite coordenadas como
  tokens `<locXXXX>`. Brazo de la Parte I y del bake-off.

- **`PID`**: el controlador proporcional, integral y derivativo en cascada que convierte
  el error de la caja en consigna de velocidad.

- **`pytracking`**: la biblioteca de referencia cuya convención de AUC adopta este trabajo.

- **`Qwen2-VL-2B`**: el modelo de grounding desplegado. Ajustado con LoRA sobre RefDrone,
  exportado a GGUF y cuantizado a `Q8_0`.

- **`Qwen2.5-VL-3B-Instruct`**: brazo del bake-off de backbones.

- **`SAM2.1`**: modelo de segmentación con memoria de vídeo, en sus variantes `hiera-tiny`,
  `hiera-small` y `hiera-base-plus`. Es el mecanismo de carry de las Partes V y VI, y la
  familia de referencia del capítulo 11. Se usa siempre por su camino de streaming, nunca
  por el camino de lote, que no cabe en 8 GB.

- **`SAMURAI`**: variante de SAM2 con memoria guiada por movimiento, brazo de comparación
  entre políticas de memoria.

- **`SmolVLM`**: familia de modelos de visión y lenguaje pequeños, usada en las etapas
  iniciales de la Parte I.

- **`Swin2SR`**: super-resolución aprendida, evaluada como palanca para objetivos diminutos
  y descartada frente a la interpolación clásica.

- **`TensorRT`**: el compilador de inferencia de NVIDIA. Se usó para exportar el encoder de
  carry y medir si compraba frecuencia.

- **`vot-toolkit`**: la biblioteca de evaluación de seguimiento que arrastra DAM4SAM, fijada
  a la versión `0.7.1`.

## 2.4 Datasets, simuladores y hardware

- **`AerialMind`**: dataset aéreo con expresiones referenciales temporales, considerado como
  candidato y no adoptado.

- **`ArduCopter SITL`**: el simulador de vuelo por software que aporta la física del
  vehículo en la Parte VI. El renderizado no lo hace él.

- **`CARLA 0.9.16`**: el simulador urbano fotorrealista que actúa como renderizador esclavo
  de la pose en la Parte VI, en sustitución de Gazebo. Corre en la máquina de escritorio,
  no en la placa.

- **`Gazebo Sim 8.14.0`** (Harmonic): el simulador usado antes de CARLA, tanto para los
  clips de permanencia de la Parte III como para el generador de escenas de la Parte V.

- **`JetPack`** / **`L4T`**: la pila de software de NVIDIA para la placa. Las versiones
  fijas de todo el trabajo son `JetPack 6.2.2+b24` y `L4T R36.5.0`, con `CUDA 12.6`.

- **`jetson_clocks`**: la utilidad que fija las frecuencias de la placa para evitar el
  escalado dinámico. En esta placa no cambia el governor, que sigue en `schedutil`.

- **`Jetson Orin Nano 8 GB Developer Kit`**: la plataforma objetivo. CPU de 6 núcleos y GPU
  integrada, `7607 MB` de memoria unificada compartida entre las dos, de los que quedan unos
  `6 GB` libres tras el sistema operativo. Es una estimación, no una medida.

- **`nvpmodel`** / **`modo 15 W`**: el selector de modo de potencia. Todas las cifras de este
  documento se midieron en el modo de `15 W` con `jetson_clocks` aplicado. El modo
  `MAXN_SUPER` de `25 W` no existe en esta placa sin reflashear.

- **`RefCOCO`**: dataset de expresiones referenciales sobre imágenes cotidianas, usado como
  corpus de arranque del ajuste fino.

- **`RefDrone`**: dataset de expresiones referenciales sobre imágenes aéreas, usado para el
  ajuste fino y la evaluación de grounding de las Partes II y III.

- **`RTX 3090`**: la GPU de escritorio. En este trabajo entrena los modelos y ejecuta CARLA.
  El seguimiento y la inferencia desplegada corren siempre en la placa. El capítulo 12
  detalla el único punto del historial en el que esa frontera no se respetó.

- **`TLP`**: dataset de seguimiento de larga duración, examinado y descartado por no
  contener el fenómeno bajo estudio.

- **`UAV123`**: el banco de seguimiento aéreo de referencia, 123 secuencias con caja por
  fotograma a 30 fps. Es el vídeo real de este trabajo.

- **`VisDrone`**: dataset aéreo de detección, usado como fuente auxiliar de supervisión.

## 2.5 Convención de identificadores

Los experimentos conservan el identificador con el que se ejecutaron. No se renumeran,
porque los registros originales y los ficheros de datos los citan así.

| Prefijo | Parte | Ejemplo |
| --- | --- | --- |
| `Q-*`, `RQ-*` | todas | `RQ-2.1`, `Q-vlm-1` |
| `Phase 0` a `Phase 4` | Parte II | `Phase 3 train` |
| `T0` a `T4` | Parte III | `T2 permanence` |
| `E1` a `E23` | Parte IV | `E18 real-video-replay` |
| `P<parte>.<n>` | Partes V y VI | `P5.20`, `P6.2-DELIVERY` |
| `EXP-<n>` | Parte VI | `EXP-1` |
| `R-<n>` | transversal | `R-28` |
| `notes/<n>` | capítulo 11 | `notes/19` |

Los identificadores `EXP-<n>` rompen el esquema `P<parte>.<n>` de las Partes V y VI. Es
una inconsistencia conocida del registro, y se mantiene porque los datos ya están escritos
con ella.
