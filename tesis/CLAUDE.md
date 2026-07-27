# tesis/ — reglas del registro de experimentos

Aplican a `tesis/experiments.md` y `tesis/experiments.bib`. No aplican al resto
del repo.

## Qué es este documento

`experiments.md` es la **narrativa derivada** de los experimentos, escrita para
ser leída de seguido. La fuente de verdad sigue siendo
`experiments/<campaña>/README.md`. Por tanto: aquí se resume y se interpreta,
no se inventa. Toda cifra tiene que existir ya en el registro de campaña; si no
está allí, no entra aquí.

## Plantilla por experimento — invariable

Mismos encabezados, mismo orden, en todos. Una sección sin contenido se deja
con "Sin negativos" / "Idem a contexto", nunca se borra.

```markdown
## E<n> - <título corto>

Resumen de: `experiments/<campaña>`, realizado <YYYY-MM-DDThh:mmZ>.

### Introducción
### Preguntas / Hipótesis
### Entorno
### Método
### Resultados
### Resultados negativos
### Conclusiones
```

- `##` para el experimento, `###` para sus secciones. `## Contexto` va una sola
  vez al principio y no se repite.
- **`Entorno`** declara solo la desviación respecto de `## Contexto`
  ("Idem a contexto" si no la hay). El Contexto envejece; sin esta línea, un
  experimento antiguo se lee como si hubiera corrido en la pila actual.
- **`Método`** incluye el comando exacto en bloque de código, con sus flags.
  "se ejecutó `llama-bench`" no es reproducible.

## Identificadores

Preguntas y resultados van **prefijados con el experimento**: `E1.P1`, `E1.R1`.
Sin prefijo colisionan en cuanto haya un E2 y no se puede citar
"esto contradice R2" desde otro capítulo.

Cada `E<n>.R<k>` responde al `E<n>.P<k>` del mismo número. Una pregunta cuyos
datos no la resuelven se responde **"no determinado"** con lo que faltaría para
determinarla. Eso es contenido, no un hueco.

## Citas

- Bibliografía: `experiments.bib`, declarado en el front matter
  (`bibliography: experiments.bib`, `citation_style: numeric`).
- Citar con `[@clave]` en el cuerpo. Varias juntas: `[@a; @b]`.
- **Prohibida la sección `## Fuentes` local y la numeración `[1]`, `[2]` a
  mano.** `md-to-pdf` genera "Referencias" al final, solo con lo citado, y
  numera globalmente. Numerar a mano rompe en cuanto dos experimentos citan.
- `experiments.bib` es **independiente** de `borrador/refs.bib` (bibliografía
  del TFM). No se fusionan ni se comparten claves.
- **Toda entrada lleva enlace y fecha de acceso**: `url` (o `\url{...}` dentro
  de `howpublished`, o `doi`) más `urldate`. `md-to-pdf` escribe el enlace
  completo y le añade "(accedido el …)". Sin `urldate` no hay fecha, y una
  fuente web sin fecha de consulta no es citable.
- Entrada sin verificar contra la fuente primaria: marcarla `% VERIFICAR` en el
  `.bib`. Antes que omitirla, que la falta se vea.
- Fuente externa nueva: añadirla también a `SOURCES.md` (regla del repo).

## Tablas y cifras

- Toda tabla lleva `<!-- caption: ... -->` encima, con el **`n`** y la
  configuración (modo de potencia, flags). `md-to-pdf` falla el build sin él.
- Unidades con espacio y símbolo correcto: `67 °C`, `12.5 W`, `3302 MB`.
- Estimación no medida: marcarla como tal (`~6 GB`), nunca presentarla como
  medida.
- Una afirmación causal ("el cuello de botella es X") necesita evidencia que la
  distinga de la alternativa. Ocupación al 99 % no distingue *compute-bound* de
  *memory-bound*: si no hay medida que separe las dos, el resultado dice
  "no determinado".

## Idioma y build

- Español con diacríticos completos: acentos, ñ, ¿ ¡. También en pies de tabla
  y figuras.
- Build: `md-to-pdf tesis/experiments.md`. El PDF es artefacto regenerable —
  no se commitea.
