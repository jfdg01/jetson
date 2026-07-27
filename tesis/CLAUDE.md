# tesis/ — reglas del registro de experimentos

Aplican a `tesis/tesis.md` y `tesis/tesis.bib`. No aplican al resto del repo.

## The single most important rule

You are a READ ONLY AGENT nothing in the tesis/ dir gets touched by you.

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

- Toda tabla lleva `<!-- caption: ... -->` encima, con el **`n`** y la configuración (modo de potencia, flags). `md-to-pdf` falla el build sin él.
- Unidades con espacio y símbolo correcto: `67°C`, `12.5W`, `3302MB` (prefiero las unidades juntas).
- Estimación no medida: marcarla como tal (`~6GB`), nunca presentarla como medida.

## Idioma y build

- Español con diacríticos completos: acentos, ñ, ¿ ¡. También en pies de tabla y figuras.
- Build: alias `tesis`. El PDF es regenerable.
