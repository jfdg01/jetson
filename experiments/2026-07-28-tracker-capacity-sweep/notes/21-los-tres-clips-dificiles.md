# 21. Los tres clips difíciles: FOH no es la causa de ninguno

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-08-02T23:30Z -> 23:55Z (hora local de Madrid).
**Coste:** 0 h de dispositivo — render y análisis sobre los JSON de `raw/paced-sweep-30/`.
**Datos:** `raw/paced-sweep-30/`, clips en `proof/foh__{person18,bird1_1,bike2}.mp4`
**Código:** `b188ee6` (`analysis/render_foh.py`).

## 1. Por qué existe

La verificación visual de la nota 19 se cerró con `truck2` (el mejor caso, +0.258) y `boat3` (una
pérdida trivial de −0.020 sobre un objetivo grande y quieto). El autor objetó lo evidente: son los
dos clips fáciles. Los que importan son los tres donde FOH **pierde** de verdad, que la nota 19 §4
había clasificado en tres poblaciones sin haber mirado ni un fotograma.

Aquí se miran. Y la clasificación de la nota 19 no sobrevive.

## 2. Lo que dicen los fotogramas

```
analysis/render_foh.py raw/paced-sweep-30/sam2_c512__person18.json --zoom 512 --out proof/foh__person18.mp4
analysis/render_foh.py raw/paced-sweep-30/sam2_c512__bird1_1.json  --zoom 384 --out proof/foh__bird1_1.mp4
analysis/render_foh.py raw/paced-sweep-30/sam2_c512__bike2.json    --zoom 256 --out proof/foh__bike2.mp4
```

| clip | ZOH | FOH | delta | alto pred/GT | ancho pred/GT | dist. centro (anchuras) | n |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `person18` | 0.238 | 0.222 | −0.016 | **0.45** | 0.91 | 0.51 | 990 |
| `bird1_1` | 0.027 | 0.015 | −0.012 | **3.17** | **7.63** | 2.74 | 194 |
| `bike2` | 0.069 | 0.055 | −0.014 | 1.14 | 0.97 | **12.94** | 496 |

Medianas sobre los fotogramas con GT y con caja retenida. Las tres filas son fallos **distintos**:

- **`person18` es un fallo de escala, no de dirección.** [**Corregido por la nota 22:** el sujeto es
  `sam2_c512`, no SAM2. Los otros cinco brazos siguen al señor entero, alto pred/GT 1.00.] En `.mid.png` (f697) se ve directamente: el
  GT verde cubre al señor entero, y la caja del seguidor cubre **solo los pantalones**. El ancho es
  correcto (0.91), el alto es la mitad (0.45). SAM2 segmenta las piernas y pierde el torso y el
  sombrero. Un mIoU de 0.238 con el objetivo perfectamente localizado y perfectamente encuadrado en
  horizontal.
- **`bird1_1` es una máscara reventada.** La caja mide 3.2 veces el alto y **7.6 veces el ancho** del
  pájaro: es una banda horizontal que cruza el fotograma entero. En `.mid.png` (f127) el zoom de 384
  px está enteramente dentro de la caja predicha — las líneas roja y azul son sus bordes superior e
  inferior. Está siguiendo la telemetría del HUD y el cielo, no el pájaro.
- **`bike2` es un enganche a otro objeto.** El tamaño es correcto (1.14 y 0.97) pero el centro está a
  **12.9 anchuras de objeto** del GT. En `.mid.png` (f277) el ciclista verde de 12 px está en mitad
  del encuadre y la caja del seguidor no aparece en la ventana de 256 px: se fue a otra parte de la
  escena hace rato.

## 3. La corrección a la nota 19

Donde la **nota 19 §4** dice, sobre los 34 pares en que FOH pierde:

> - **cambio de dirección más rápido que el paso de retención** — `person18` (−0.020), `person20`
>   (−0.006): peatones. La velocidad pasada deja de predecir la futura.
> - **la caja ya estaba mal** — `bird1_1`, `bird1_3`, `bike2`, todos con mIoU 0.01-0.07: extrapolar
>   una caja equivocada la aleja más.

hay que leer:

- **`person18` no es un cambio de dirección.** Es un error de escala persistente: media persona, 990
  fotogramas seguidos. La velocidad del centro está bien estimada; lo que está mal es la altura de
  la caja, y eso FOH ni lo toca ni lo puede tocar. La atribución de la nota 19 se hizo desde el
  covariante `motion` (0.012, bajo) sin mirar el clip, y era una inferencia, no una observación.
- **"la caja ya estaba mal" es correcto pero indistinto.** `bird1_1` y `bike2` comparten el mIoU
  bajo y nada más: uno revienta la máscara hasta cruzar el fotograma, el otro mantiene el tamaño
  correcto sobre el objeto equivocado. Son dos modos de fallo con dos arreglos distintos (control de
  área de máscara contra re-enganche), y meterlos en la misma línea los oculta.

Lo que **sí** sobrevive intacto de la nota 19: en los tres casos la pérdida de FOH es de 0.012 a
0.016 sobre una base ya rota. **FOH no causa ninguno de los tres fallos.** Extrapola una caja que ya
era mala y la empeora un pelo. El resultado agregado (+0.069 pareado sobre 155 pares) no depende de
esto.

## 4. Cómo no sobreleer

- Un fotograma central por clip, más las medianas sobre 194-990 fotogramas. La mediana de la razón
  de alturas no dice que el fallo sea constante — dice que es el comportamiento típico.
- Los tres clips son de `sam2_c512`. Que los otros cinco brazos fallen igual en los mismos clips es
  plausible (todos pierden en `person18`, `bird1_1` y `bike2`, ver nota 19 §4) pero no se ha mirado.
- **Esto explica pérdidas, no las arregla.** No se ha probado ningún control de área de máscara ni
  ningún re-enganche. `analysis/regap.py` y el brazo `coast` existen y no se han cruzado con esto.
- `person20` sigue sin mirarse; la nota 19 lo metía en la misma bolsa que `person18` y ahora esa
  bolsa está en duda.

## 5. Qué no se midió

Verificación visual: **sí**, tres `.mid.png` abiertos y leídos, más los clips completos escritos.
Es lo contrario del caso habitual — aquí el problema era que los números se habían interpretado sin
mirar.

No se midió: si el fallo de escala de `person18` depende de la resolución del brazo (un `c704` que
vea más contexto podría coger el torso); si `bird1_1` revienta desde el primer fotograma o degenera;
ni si `bike2` se engancha a un objeto concreto o deriva al fondo.

`person20` se cierra en la nota 22: `c512` lo hace bien (mIoU 0.750), así que la bolsa de la nota 19
§4 que lo juntaba con `person18` no existe.
