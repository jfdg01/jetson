# Guía de estilo de la tesis

Esta guía fija la forma de la prosa de la tesis: cada nota de `thesis/notas/` y cada capítulo del documento. El formato de la página (los márgenes, la portada, la extensión) sale de la normativa del máster, y queda fuera de esta guía.

## La voz

- La prosa va en forma impersonal o en pasiva refleja con «se»: «se midió el *decode*», «se eligió Q4_K_M». No lleva «yo» ni plural de modestia.
- La pasiva con «ser» («el modelo fue medido») no se usa, porque es un calco del inglés.
- Una cita marca el trabajo ajeno. Lo que no lleva cita es aportación del autor.

## Los tiempos verbales

- El pasado narra lo que se hizo: «se midió», «se descartó».
- El presente dice lo que sigue siendo verdad («el *decode* depende del ancho de banda») y lo que muestra una figura («la Figura 1.3 muestra»).

## Las palabras

- Un concepto tiene un solo nombre en todo el documento.
- Una sigla se define en su primer uso: «el *time to first token* (TTFT)». CPU y GPU no se definen, porque son de uso general.
- Un extranjerismo va en cursiva (*prefill*, *throughput*), salvo que tenga una traducción fija en la tesis.
- Un adjetivo de valor («muy bueno», «potente») se quita.
- Se evitan el gerundio de posterioridad («se midió, obteniendo 14 tok/s»), «en base a», «a nivel de» y «de cara a».

## La prudencia

- Una afirmación lleva su dato o su cita.
- Una estimación se marca como estimación.

## Los números y los signos

- El separador decimal es la coma: 14,6 tok/s.
- Los millares se separan con un punto en un número de cuatro cifras o más: 5.818 MB.
- La unidad es del SI, y va separada del número por un espacio: 15 W, 66,9 °C, 25 %.
- Las comillas son las angulares «», después las inglesas “ ” y después las simples ‘ ’.

## Los títulos, las figuras, las tablas y los bloques de código

- Un título lleva mayúscula solo en la primera palabra y en los nombres propios: «Puesta en marcha de la placa».
- Cada figura, tabla y bloque de código lleva encima una leyenda con su identificador y una descripción corta que se entiende sin el texto.
- La leyenda describe lo que muestra el elemento, y no lo explica. La explicación va en la prosa.
- La leyenda no repite lo que dice la prosa. Si no tiene nada que añadir, lleva solo el identificador y la descripción corta.
- El identificador es el número de la sección de primer nivel y el orden dentro de ella: la primera tabla de la sección 1 es la «Tabla 1.1», y la segunda es la «Tabla 1.2».
- Las figuras, las tablas y los bloques de código se numeran por separado: un bloque de código después de esas dos tablas es el «Bloque de código 1.1».
- El documento tiene un índice de figuras, un índice de tablas y un índice de bloques de código.
- El texto cita cada figura, tabla y bloque de código por su identificador, con mayúscula, antes de que aparezca: «la Tabla 2.1 muestra».

## Las referencias

Las referencias siguen el estilo IEEE: un número entre corchetes en el texto, [1], y la lista al final en el orden de la primera cita. Las fuentes viven en `thesis/refs.bib`.

Cada URL de la lista de referencias es un enlace que se abre con un clic desde el PDF.

## La revisión

- El agente comprueba cada nota contra esta guía antes de su commit. Señala cada fallo con su línea y su regla, y no reescribe la prosa: el autor corrige.
- Al cierre de la lectura de cada Parte, el autor relee esta guía. Una regla que no sirve se cambia o se quita, y una regla nueva entra.
