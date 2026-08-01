# Q1 presencia, Q2 borde de ventana, Q3 reenganche asym_lt

Parte de [`../README.md`](../README.md).

## Q1 — la señal de presencia de AsymTrack (run `asym-conf`, 123 secuencias, 2026-07-30T02:20Z)

AsymTrack no tiene cabeza de oclusión. El sustituto medido es `conf` = pico del corner-softmax.
Métricas medianadas **solo sobre las 33 secuencias con huecos** (30747 frames, 2683 ausentes): en las
90 sin huecos un tracker que siempre responde saca `f_lt = 1` por construcción.

| métrica | valor | lectura |
| --- | --- | --- |
| `presence_auc` | **0.711** | zona gris del pre-registro (0.65-0.75) |
| `f_lt` | 0.826 | — |
| `maxgm` | **0.482** | referencia a batir para Q3 |
| `presence_auc < 0.5` | 5 / 33 | `uav6` 0.34: anticorrelada |

Rama elegida por el pre-registro (`analysis/presence.py`, docstring escrito antes de ver el número):
zona gris = construir Q3 **y además** un verificador coseno independiente para comparar.
Implementado como `AsymArm.conf_cos`, NCC de media cero contra el parche template del frame 0,
~0.3 ms, sin red nueva.

Umbrales para Q3, ajustados sobre las 17 secuencias de índice par y evaluados sobre las 16 impares:
`tau_lo = 0.3920` (conf al 90% TPR), `tau_hi = 0.7293` (conf al 5% FPR). Sin aviso de solape — la
histéresis es real.

## Q2 — tamaño de ventana contra tratamiento del borde (run `c640pad`, 2026-07-30T05:10Z)

Confundido detectado por el autor: `c640` **desliza** la ventana para que quepa en el frame, `f5`
**rellena** con ceros. Compararlos mezcla dos cambios. `c640_pad` es el peldaño intermedio: mismo
tamaño fijo de 640, relleno en vez de deslizamiento. `c640` se queda congelado como incumbente.

Sobre las **25 secuencias comunes** (ver nota de la compuerta abajo):

| brazo | AUC | mIoU | @0.5 | p50 ms |
| --- | --- | --- | --- | --- |
| `sam2_c640` | 65.0 | 0.785 | 0.983 | 159.3 |
| `sam2_c640_pad` | **64.8** | 0.787 | 0.983 | 159.4 |
| `sam2_c704` | 66.9 | — | — | — |

Dentro del +-1 punto que decía la estimación a priori: **deslizar o rellenar es indiferente**. Luego
lo que separa `c640` de `f5` es el tamaño de ventana escalado al objeto, no el borde.

Verificación visual obligatoria (`raw/c640pad/q2_tile.png`, `car1_3` frame 307, coche pegado al borde
superior): arriba `c640_pad`, ventana centrada saliéndose del frame y panel de entrada **negro en la
banda superior** — el relleno de ceros, visible. Abajo `c640`, misma ventana deslizada hacia dentro y
panel lleno. IoU 0.79 vs 0.75 en ese frame.

Dos hallazgos laterales:

- **5 secuencias fuera por la compuerta `upscales`**: `uav1_2,uav2,uav3,uav5,uav7` son 720x480 y una
  ventana de 640 no cabe en 480. La compuerta es correcta. Incómodo: `full-sweep-30` es anterior a
  ella y **sí** tiene esas 5 celdas para `c640`/`c704`, así que los números publicados del incumbente
  incluyen 5 clips que la regla actual del proyecto declara inválidos por interpolación. Todas las
  comparaciones de esta sección están hechas sobre las 25 comunes. *(Decisión del autor 2026-07-30:
  no se relanza; se deja anotado.)*
- `render_overlay` no sabía re-derivar la ventana del brazo `pad` (la re-derivaba deslizada:
  `AssertionError: (2, [46, -199, 640], [46, 0, 640])`). Origen negativo es justamente el tratamiento
  bajo prueba. Arreglado.

## Q3 — el reenganche: `asym_lt` (run `asym-lt`, 33 secuencias x 2 brazos, 2026-07-30T03:45Z)

Envoltura estilo LTMU sobre AsymTrack, no un modelo nuevo: tracker local + verificador (`conf`) +
máquina de estados con histéresis (k=3 frames bajo `tau_lo` para declarar `LOST`) + redetector ráster
amortizado (N=5 ventanas/frame, cubre el frame en ~8 frames) + template del frame 0 congelado. Emite
caja **solo** en estado `tracking`.

**Negativo en todas las métricas.** Mitad de evaluación (16 impares) salvo donde se indica:

| métrica | `asym_lt` | `asym_b` |
| --- | --- | --- |
| `maxgm` | 0.492 | **0.493** |
| `f_lt` | 0.770 | **0.883** |
| AUC OPE (33) | 45.4 | **52.0** |
| mIoU (33) | 0.561 | **0.645** |
| p50 ms | 30.5 | 30.4 |

La estimación a priori decía "`maxgm` sube claramente, es casi por construcción". Falso, y el porqué
es el resultado:

- **Precisión de abstención 26.7%.** 3737 abstenciones, solo 998 sobre frames realmente vacíos. Se
  calla en 2739 frames CON objeto para acertar 998 sin él.
- **Precisión de reenganche 24.7%.** 162 episodios de pérdida, 40 vuelven con IoU > 0.3. Por debajo
  del 35-40% que los brazos SAM2 recuperaban **pasivamente**, sin máquina de estados.
- **Coste asimétrico**: `car7` cae de mIoU 0.740 a 0.003 (reengancha sobre un distractor y ya no
  vuelve), `bike2` 0.149 a 0.013.
- **Latencia idéntica**: el ráster amortizado no cuesta nada. Esa pieza del diseño sí funciona.

No es un problema de umbrales: subir `tau_hi` empeora las 2739 abstenciones falsas, bajarlo empeora
los 122 reenganches malos.

**El verificador coseno tampoco.** `cos_auc` 0.714 sobre las 33 (0.770 en la mitad impar) contra
0.711 (0.720) del pico del corner-softmax. Dos verificadores independientes, el mismo techo mediocre.
La rama gris del pre-registro queda agotada: **lo que falta es una cabeza de score entrenada, no otra
heurística sobre las features de AsymTrack.**

Verificación visual (`raw/asym-lt/p17_reattach.mp4` y `p17_tile.png`, `person17_1` 570-645): frame
579 responde con el objeto ausente; 591 y 616 en `LOST` con la ventana de 205 px barriendo; 632
reengancha con IoU 0.76. El frame 616 es el hallazgo: la persona está **visible y dentro de la
ventana** y el brazo sigue en `LOST` — las 2739 abstenciones falsas en una imagen.
