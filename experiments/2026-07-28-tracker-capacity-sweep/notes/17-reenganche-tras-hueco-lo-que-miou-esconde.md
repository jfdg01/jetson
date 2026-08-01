# Reenganche tras hueco: lo que mIoU esconde

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-08-01T19:10Z -> 20:05Z (hora local de Madrid).
**Coste:** 0 corridas nuevas, **0 h de dispositivo** — reanálisis de trazas ya grabadas.
**Datos:** `raw/full-sweep-30/`, `raw/dam-full30b/`, `raw/sam-parity30/`, `raw/sam-full30/`,
`raw/night-c640/`, `raw/night-c640pad/`, `raw/lt-controls33/`
**Código:** `analysis/regap.py`.

## 1. Por qué existe el análisis

Objeción del autor al incumbente recortado: el recorte quita contexto por construcción. La ventana
solo mira alrededor de donde el objetivo estaba, así que si el objetivo sale de frame y vuelve por
otro sitio, el brazo recortado ni siquiera puede mirar allí. Toda la campaña hasta aquí se ha
adjudicado con mIoU, y mIoU no puede ver eso: promedia sobre todos los frames presentes, así que un
hueco de 20 frames dentro de una secuencia de 900 pesa nada aunque el brazo salga de él perdido
para el resto del clip.

El análisis mide esa transición y solo esa.

## 2. Qué se mide

Un **hueco cerrado** es una tirada maximal de frames con GT ausente que tiene GT presente antes y
después. Los huecos que llegan al final de la secuencia no cuentan: no hay reenganche que medir. Se
puntúan los K frames siguientes al regreso:

- `reenganche` — algún frame de los K tiene IoU > 0.5.
- `iou_post` — IoU medio sobre esos K frames.
- `frames_a_re` — frames hasta el primero con IoU > 0.5.

La comparación es **pareada por hueco**, no por secuencia: los dos brazos ven exactamente los mismos
huecos porque los define el GT, no el brazo. K se barre a 30, 60 y 120 para comprobar que el signo
no depende de la ventana elegida.

```
python analysis/regap.py raw/full-sweep-30 raw/dam-full30b raw/sam-parity30 raw/sam-full30 \
    raw/night-c640 raw/night-c640pad raw/lt-controls33 --k 60 --vs sam2_c640
```

## 3. La objeción al recorte no se sostiene en UAV123

`sam2_t640` (frame completo) contra `sam2_c640` (recortado), misma resolución, 55-56 huecos comunes:

| K | d mediana `iou_post` | gana | p |
| --- | --- | --- | --- |
| 30 | +0.000 | 14/55 | 0.138 |
| 60 | -0.003 | 15/56 | 0.123 |
| 120 | -0.006 | 14/53 | 0.079 |

El frame completo **no** reengancha mejor que el recorte; si algo, la tendencia va al revés y crece
con K. En cuentas de reenganche binario el reparto es 7/7 a K=30 y 6/8 a K=60: nadie separa.

**Interpretación**, marcada como tal: en UAV123 el dron sigue al objetivo, así que el objetivo vuelve
cerca de donde se fue y la ventana recortada sigue estando encima. La objeción no queda refutada,
queda **sin poder ponerse a prueba con estos datos** — UAV123 tiene 2.38% de frames ausentes y sus
huecos son oclusiones cortas, no desapariciones reales.

## 4. Lo que sí aparece: mIoU escondía a DAM4SAM

Contra el incumbente `sam2_c640`, pareado por hueco:

| brazo | K=30 | K=60 | K=120 |
| --- | --- | --- | --- |
| `dam4sam_t768` | +0.010, 18/26, p = 0.011 | +0.011, 19/27, p = 0.0032 | +0.006, 16/24, p = 0.014 |
| `dam4sam_t960` | +0.022, 21/26, p = 0.0009 | +0.016, 21/27, p = 0.0007 | +0.012, 17/24, p = 0.0045 |
| `dam4sam_t640` | -0.006, 8/26, p = 0.32 | -0.010, 7/27, p = 0.26 | -0.012, 4/24, p = 0.063 |
| `sam2_t512` | -0.050, 3/26, p = 0.0006 | -0.188, 2/27, p = 0.0001 | -0.405, 1/24, p = 0.0002 |

`dam4sam_t960` gana además el reenganche binario 5/0 a K=60 (cinco huecos que recupera y el
incumbente no, ninguno al revés). El signo y el orden se mantienen en las tres ventanas, y los dos
p de DAM4SAM sobreviven a Holm sobre los 12 contrastes de la columna.

Donde la sección 14 leía a los brazos DAM4SAM como **nulo acotado** sobre mIoU (p = 0.19 frente al
recorte), hay que leer: **nulo en mIoU, positivo en reenganche tras hueco a 768 y 960**. No es una
contradicción, es que las dos métricas miden cosas distintas y mIoU diluye el evento. La sección 16
sigue en pie tal cual — comparaba DAM4SAM contra SAMURAI, no contra el recorte.

Al otro lado, `sam2_t512` y `sam2_c512` se hunden: por debajo de 640 el brazo no vuelve a enganchar
en absoluto (`iou_post` mediana 0.000, 3/26 reenganches). Ahí el suelo de resolución no es una
pérdida de precisión de caja, es pérdida de la capacidad de redetectar.

## 5. Cómo no sobreleer la tabla

- **Los huecos no son independientes.** Se agrupan a razón de ~1.5 por secuencia y el Wilcoxon los
  trata como muestras sueltas, así que los p son optimistas. El argumento fuerte aquí es la
  estabilidad del signo entre K, no el valor exacto de p.
- **n distinto por fila.** 55-56 huecos para los brazos de la base grande, 24-27 para los que solo
  corrieron sobre `dam-full30b`. Las filas no son comparables entre sí, solo cada una contra
  `sam2_c640`.
- `sam2_c640_pad` tiene 29 huecos comunes y no se separa de nada (p = 0.82 / 0.96 / 0.98). No dice
  que el padding dé igual; dice que con 29 huecos no se ve.
- **`iou_post` mediana por brazo baja con K pequeña** porque incluye los frames en los que el brazo
  aún no ha reenganchado. La columna de la tabla del brazo es descriptiva; la adjudicación es la
  pareada.

## 6. Qué no se midió

- **Sin verificación visual de este análisis.** Ningún reenganche se ha mirado en vídeo. La
  afirmación "DAM4SAM a 960 recupera cinco huecos que el recorte pierde" es una cuenta sobre
  `results.json`, no algo que se haya visto pasar.
- No se ha separado oclusión (algo se mete delante) de salida de frame. UAV123 no lo etiqueta
  aparte, y es exactamente la distinción que la objeción del autor necesita. Para eso hace falta un
  dataset con etiqueta de ausencia por frame — TLP, o LaSOT con sus `out_of_view.txt`.
- No se ha medido reenganche del brazo LT (`dam4sam_lt`), que es el que se abstiene a propósito
  durante el hueco: su `iou_post` mezcla abstención con fallo y necesita su propia métrica.
