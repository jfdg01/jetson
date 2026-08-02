# 24. El consumidor está agotado con FOH: la mitad del techo, y no hay segunda mitad barata

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-08-03T03:25Z -> 04:20Z (hora local de Madrid).
**Coste:** 0 h de dispositivo — reglas de consumidor sobre las cajas ya commiteadas.
**Datos:** `raw/paced-sweep-30/`, `raw/paced-lead-30/`
**Código:** `analysis/consumer.py` (commit de esta nota).

## 1. Por qué existe

La nota 23 §3 midió el techo: la caja entregada puntúa 0.485 contra el fotograma que se consume y
0.811 contra el que miró, así que ~0.33 de mIoU es **retardo puro**. FOH (nota 19) cobra parte de
eso sin gastar dispositivo. La pregunta obvia, y barata, es cuánto queda: si la segunda mitad del
techo se coge con una regla algo mejor en el consumidor, es la mejora más rentable de la campaña,
porque no cuesta ni un milisegundo de Jetson.

Cinco reglas, todas estrictamente causales (solo respuestas ya aterrizadas):

| regla | qué hace |
| --- | --- |
| `zoh` | congela la última respuesta — la línea base publicada |
| `foh` | avanza a la velocidad de las dos últimas respuestas (`aggregate.extrapolate`) |
| `foh3`, `foh5` | igual, con la velocidad promediada sobre 3 y 5 huecos |
| `fohs` | `foh` más el **tamaño** avanzado al mismo ritmo, no solo el centro |
| `acc` | aceleración constante: la parábola por los tres últimos centros, evaluada en `j` |
| `techo` | la misma caja puntuada contra `GT(i)`. **No es una regla**, es la cota |

`analysis/consumer.py --selftest` fija que `coast(k=2)` es exactamente `aggregate.extrapolate`, para
que la generalización no cambie en silencio el número publicado.

```
analysis/consumer.py raw/paced-sweep-30 --arm sam2_c512
analysis/consumer.py raw/paced-sweep-30 --arm sam2_c640
analysis/consumer.py raw/paced-lead-30  --arm sam2_c512_lead
```

## 2. El resultado: FOH coge la mitad, y nada más lo mejora

mIoU medio sobre 25 clips, pausado a 30 fps, `sam2_c512`. `% del techo` es la fracción del hueco
`techo − zoh` que la regla recupera:

| regla | mIoU | d vs `zoh` | gana | p | % del techo |
| --- | ---: | ---: | ---: | ---: | ---: |
| `zoh` | 0.462 | — | — | — | 0% |
| `foh` | 0.559 | +0.097 | 21/25 | 2.2e−05 | **51%** |
| `foh3` | 0.562 | +0.100 | 21/25 | 1.0e−05 | 52% |
| `foh5` | 0.553 | +0.091 | 21/25 | 3.3e−06 | 47% |
| `fohs` | 0.543 | +0.080 | 19/25 | 9.1e−04 | 42% |
| `acc` | 0.482 | +0.020 | 13/25 | 2.6e−01 | **10%** |
| `techo` | 0.654 | +0.192 | 24/25 | 1.8e−07 | 100% |

**FOH ya está en el codo.** Promediar la velocidad sobre tres huecos añade +0.003 (dentro del ruido
de estos n) y sobre cinco resta; extrapolar además el tamaño resta 0.017. `c640` da la misma forma
(`foh` 45% del techo, `foh3` 44%, `fohs` 38%) y `c512_lead` también (48%, 50%, 40%). Tres brazos,
mismo codo.

Y subir el orden **empeora mucho**: `acc` (aceleración constante, que es lo que un Kalman con modelo
de aceleración hace en el límite sin ruido y en régimen) se queda en el 10% del techo y ni siquiera
es significativo (p=0.26; en `c640`, 15% y p=0.08). Ajustar una parábola a tres centros medidos con
ruido amplifica el ruido más de lo que gana en curvatura, sobre un horizonte de 5 fotogramas.

Junto con `foh3`/`foh5`, que mueven el estimador de velocidad en la otra dirección y tampoco compran
nada, el cuadro es consistente: **el cuello de botella no es el orden del estimador, es que el
movimiento no es predecible a ese horizonte**. Esto es un **nulo acotado, no una imposibilidad** —
un Kalman con ruido de proceso ajustado por clip, o el propio seguidor prediciendo, siguen sin
probarse — pero la familia obvia de arreglos de consumidor está barrida en las dos direcciones.

## 3. El efecto secundario: la ordenación pausada depende del consumidor

Pareado por clip, `c640 − c512`, n=25:

| consumidor | d medio | d mediana | gana | p |
| --- | ---: | ---: | ---: | ---: |
| `zoh` | −0.043 | −0.060 | 3/25 | 1.3e−03 |
| `foh` | −0.018 | −0.024 | 6/25 | 1.2e−02 |
| `techo` | **+0.037** | +0.003 | 17/25 | 4.5e−02 |

Bajo ZOH gana `c512` con holgura — es el resultado de la nota 19. Bajo FOH la ventaja se reduce a
menos de la mitad. Bajo el techo **cambia de signo**: si el retardo se compensara del todo, el brazo
grande sería el mejor, que es lo que la nota 2 mide sin pausar.

Lectura: *el punto de operación pausado no es una propiedad del seguidor, es una propiedad de la
pareja seguidor + consumidor.* "512 gana pausado" es cierto **para el consumidor que teníamos**.

## 4. Cómo no sobreleer

- La fila `techo` es imposible por construcción: usa el GT del fotograma que la caja miró. Sirve como
  denominador, no como objetivo alcanzable.
- El cambio de signo bajo el techo es **débil**: mediana +0.003 y p=4.5e−02 sin corregir (con Holm
  sobre los tres contrastes sigue por debajo de 0.05, pero apenas). Es una señal de dirección, no un
  resultado. No se despliega nada por esto.
- `% del techo` es un cociente de medias sobre los mismos 25 clips, no una cantidad pareada; su
  intervalo no se ha calculado.
- Todo a 30 fps. El techo crece con fps (más retardo por respuesta), así que la fracción que FOH
  recupera puede moverse; la rejilla `paced-grid-*` da las otras tres velocidades.
- `fohs` es una implementación concreta de escala coasteada (tasa observada entre dos respuestas,
  alrededor del centro avanzado). Que ésta empeore no cierra la idea, cierra esta versión.

## 5. Qué no se midió

**Sin verificación visual.** No hay ninguna afirmación aquí sobre lo que se ve en pantalla, solo
aritmética sobre cajas ya en disco. Si alguna de estas reglas se propusiera para despliegue, la
verificación en píxeles sería obligatoria antes.

No se midió: un Kalman de verdad (con ruido de proceso y de medida ajustados, no el límite sin ruido
que `acc` representa); ni el efecto
de las reglas sobre un lazo de control real, que es donde el jitter que `foh5` suaviza podría
importar más que el mIoU; ni si el cambio de signo del techo sobrevive a la rejilla de fps.
