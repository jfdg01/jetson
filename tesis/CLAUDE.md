# tesis/ — reglas del registro de experimentos

Aplican a `tesis/tesis.md` y `tesis/tesis.bib`. No aplican al resto del repo.

## The single most important rule

You are a READ ONLY AGENT nothing in the tesis/ dir gets touched by you UNLESS EXPLICITELY INSTRUCTED **IN THAT PARTICULAR TURN** BY THE USER BY A CLEAR "WRITE/CHANGE/ETC" OPERATION, THEN YOU ARE BACK TO READ ONLY.

## Qué es este documento

`tesis.md` es la **narrativa derivada** de los experimentos, escrita para servir como documento principal de la tesis. Toda la información viene de `experiments/<campaña>/README.md`, es una reescritura que condensa lo imporate para la tesis

## Plantilla por experimento — invariable

Mismos encabezados, mismo orden, en todos. Una sección sin contenido se deja con indicadores de no apicabilidad: "Sin negativos", "Idem a contexto", etc, nunca se borra.

```markdown
# E<n> - <título corto>

Resumen de: `experiments/<campaña>`, realizado <YYYY-MM-DDThh:mmZ>.

## Introducción

## Preguntas / Hipótesis

## Entorno

## Método

## Resultados

## Resultados negativos

## Conclusiones
```

- `#` para el experimento, `##` para sus secciones. `# Contexto` va una sola vez al principio y no se repite.
- **`Entorno`** declara solo la desviación respecto de `## Contexto` ("Idem a contexto" si no la hay). El Contexto envejece; sin esta línea, un experimento antiguo se lee como si hubiera corrido en la pila actual.
- **`Método`** incluye el comando exacto en bloque de código, con sus flags. "se ejecutó `llama-bench`" no es reproducible.

## Identificadores

Preguntas y resultados van **prefijados con el experimento**: `E1.P1`, `E1.R1`. Sin prefijo colisionan en cuanto haya un E2 y no se puede citar "esto contradice R2" desde otro capítulo.

Cada `E<n>.R<k>` responde al `E<n>.P<k>` del mismo número. Una pregunta cuyos datos no la resuelven se responde **"no determinado"** con lo que faltaría para determinarla. Eso es contenido, no un hueco.

## Citas

- Bibliografía: `tesis.bib`, declarado en el front matter (`bibliography: tesis.bib`, `citation_style: numeric`).
- Citar con `[@clave]` en el cuerpo. Varias juntas: `[@a; @b]`, no se numera a mano, pues vienen linkeadas del .bib.
- Entrada sin verificar contra la fuente primaria: marcarla `% VERIFICAR` en el `.bib`. Antes que omitirla, que la falta se vea.

## Tablas y cifras

- Toda tabla, figura y bloque de código lleva `<!-- caption: ... -->` encima. `md-to-pdf` falla el build sin él.
- **El pie nunca es la fuente de la verdad de ningún dato.** Todo lo que dice tiene que estar ya en el cuerpo, en `Método` o en el registro de la campaña; el pie lo repite o lo referencia, nunca lo estrena. Un dato que solo vive en un pie no se puede citar, no lo ve quien lee el cuerpo y desaparece el día que la tabla se convierte en figura.
- **El pie da contexto, no explicación.** Qué se mide, el **`n`** y la configuración (modo de potencia, flags, ctx) — lo justo para leer la tabla o la figura sin volver atrás. Lo que los datos *significan* — la tendencia, la anomalía, por qué una curva se despega de su referencia — va en el cuerpo.
- Figuras: el pie no describe los ejes ni enumera los paneles. Eso ya está dibujado. Lo que la figura dibuja y el cuerpo no menciona (una línea de referencia, un umbral) se introduce en el cuerpo **antes** de la figura.
- **Todo número que tenga unidad la lleva.** Sin excepción por repetición ni por contexto: `Qwen2.5 (14.91 tok/s) y Llama (14.60 tok/s)`, nunca `(14.91) y (14.60)`. Un número desnudo obliga a buscar de qué magnitud hablaba, y al recortarlo para citarlo deja de significar nada. En tablas, la unidad va en la cabecera de la columna y entonces las celdas no la repiten.
- Unidades con espacio y símbolo correcto `67 °C`, `12.5 W`, `3302 MB`.
- Estimación no medida: marcarla como tal (`~6 GB`), nunca presentarla como medida.

## Idioma y build

- Español con diacríticos completos: acentos, ñ, ¿ ¡. También en pies de tabla y figuras.
- Build: alias `tesis`. El PDF es regenerable.
- Figuras: código en `figuras/`, un módulo `e<n>.py` por experimento, cada figura decorada con `@figura("e<n>-<tema>")` (ver `figuras/estilo.py`). Los PNG **no** van a git; se regeneran con `.venv-ft/bin/python figuras/make_figs.py [id]` antes de compilar.

## Guía de escritura

- No usar la voz pasiva.
- No usar em-dashes ni similares.
- No traducir expresiones técnicas al español, por ejemplo: evitar cosas como "Caché KV", preferir "KV cache".
- No usar las expresiones siguientes: 
  - "punto dulce"