# Reglas de este experimento

Anulan el flujo de `/home/gara/jetson/CLAUDE.md` dentro de este directorio.

## Documentación: un fichero por evento en `notes/`

Sustituye a la regla anterior de "no documentar salvo petición" (vigente hasta 2026-08-01). Motivo
del cambio: el formato converge y ya no infla el README — el detalle vive en su propio fichero y el
README solo crece un párrafo por evento.

**Un evento = una tanda de dispositivo, o un análisis cerrado.** Se documenta cuando cierra, no
mientras corre. Los hallazgos parciales siguen yendo al chat.

`notes/NN-slug-descriptivo.md`, `NN` correlativo y nunca renumerado, slug en kebab-case que diga de
qué va (no "resultados-3"). Abre con:

```markdown
# Título

Parte de [`../README.md`](../README.md).

**Cuándo:** inicio -> fin, `YYYY-MM-DDThh:mmZ` en hora local de Madrid.
**Coste:** N corridas, **X h de dispositivo** — `sum(init_ms + frames * ms_p50)` sobre los JSON.
**Datos:** `raw/<dir>/`
**Código:** commits relevantes.
```

Después, secciones numeradas. Lo que tiene que aparecer:

- **Por qué existe la tanda** antes de los números. Un resultado sin su pregunta no es documentación.
- **El comando exacto** que produce cada tabla, indentado como bloque de código.
- **Estimación contra realidad** cuando hubo estimación previa. Una estimación fallada es contenido.
- **Cómo no sobreleer la tabla**: n por fila, conjuntos comunes que difieren, corrección por
  contrastes múltiples (Holm), nulo acotado en vez de "equivalentes".
- **Qué no se midió**, y en particular **si hubo verificación visual o no**. "Sin verificación
  visual de esta tanda" es una frase obligatoria cuando aplica.
- **Interpretación marcada como interpretación**, separada de la medida.

## El README es índice, no contenido

Por cada nota, una entrada al final de la bitácora:

```markdown
### NN. Título — [`notes/NN-slug.md`](notes/NN-slug.md) · X.XX h

4-8 líneas: el resultado, los números que lo sostienen, el contra.
```

Y se actualiza el coste total de la cabecera de la bitácora (horas y número de corridas). Nada más
del README se toca salvo que la plataforma o el diseño cambien.

## Corregir notas anteriores

Un resultado nuevo que invalida a uno viejo **no se edita en silencio**. La nota nueva lleva la
corrección explícita ("donde la sección N decía X, hay que leer Y") y la nota vieja o su entrada del
README gana un puntero de una línea. La cadena de razonamiento es el registro.

## Lo que sigue fuera

- **Los ledgers del proyecto** (`RESULTS`, `QUESTIONS`, `DECISIONS`, `SOURCES`) no se tocan salvo
  petición del autor. Este experimento puede no acabar en la tesis.
- `proof/` solo bajo petición.
- Los resultados en bruto (`raw/`) y el código se commitean sin preguntar.
- Nada de `git push`.
