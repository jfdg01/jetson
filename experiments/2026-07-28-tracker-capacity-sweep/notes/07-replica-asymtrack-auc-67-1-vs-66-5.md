# Réplica de AsymTrack: AUC 67.1 contra 66.5 publicado

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-07-29T18:50Z -> 2026-07-29T20:29Z (sello de los ficheros traídos, o sea el final de cada corrida).  
**Coste:** 126 corridas, **1.14 h de dispositivo** — estimación, `sum(init_ms + frames * ms_p50)` sobre los JSON; no incluye tiempo muerto entre etapas.  
**Datos:** `raw/asym-repro/`, `raw/asym-determ/`


## Experimento previo de confirmación: `asym-repro` (preregistrado 2026-07-29T17:05Z)

**Propósito: validar el arnés, no medir el tracker.** Si nuestro `aggregate.py`, nuestro protocolo de
inicialización o nuestro cálculo de IoU tienen un sesgo, ninguna cifra posterior es interpretable y
la comparación SAM2-vs-AsymTrack mediría nuestro bug, no los modelos. Este paso es el peldaño 2 de la
escalera de replicación y hasta ahora era inalcanzable: es la primera vez que un candidato publica un
número en el benchmark que tenemos montado.

**Hipótesis preregistrada.** AsymTrack-B sobre **UAV123 completo, las 123 secuencias**, protocolo del
paper (init con la caja GT del primer frame, one-pass, sin reinicio), reproduce **AUC = 66.5 ± 1.0**.

**Criterios, fijados antes de correr:**

- |nuestro AUC − 66.5| <= 1.0 -> **arnés validado**, seguir al experimento completo.
- 1.0 < delta <= 3.0 -> **investigar antes de seguir**. Sospechosos por orden: protocolo de init,
  tratamiento de los frames con GT ausente (`NaN`), definición de AUC (curva de success sobre umbrales
  0:0.05:1 frente a nuestro mIoU), y bf16 frente al fp32 del paper.
- delta > 3.0 -> **arnés o port roto**. No se corre nada más hasta cerrarlo.

**Métrica.** El paper reporta **AUC de la curva de success** (área bajo la curva de tasa de éxito
sobre umbrales de IoU), que **no es** nuestro `mean_iou`. Hay que añadir AUC a `analysis/aggregate.py`
para que la comparación sea la misma cantidad. Nuestro mIoU se sigue reportando en paralelo para
poder enlazar con los runs anteriores.

**Estimaciones (marcadas como estimaciones):**

- UAV123 completo: 123 secuencias, ~113k frames anotados.
- Latencia: sin medir en esta placa. Estimación por derating desde AGX Xavier (HiT-Base 61 FPS,
  factor 2.7 medido) y por tamaño relativo (3.36M frente a los 42M de HiT-Base): **30-60 ms/frame**,
  o sea 17-33 FPS. Muy incierta — es exactamente el número que no existe en la literatura.
- Runtime: **1.0-1.9 h** a esa latencia, más ~10 s de carga de modelo por secuencia (~20 min).
  Estimación total **1.5-2.5 h**.

**Limitaciones declaradas antes de correr:**

- UAV123 completo **no es** nuestro régimen de interés: mezcla objetivos fáciles y grandes. Ese es el
  punto — hay que correr donde está el número publicado, no donde nos conviene.
- La cifra publicada es de los autores en su hardware con su código de evaluación. Una diferencia
  puede venir de nuestro arnés **o** de su implementación; la validación es de coherencia, no una
  auditoría de ellos.
- bf16 en esta placa frente a lo que use el paper. Si el delta cae en la banda de investigación, es
  el segundo sospechoso a descartar.
- Un solo pase, sin repeticiones: el tracker es determinista dada la caja de init, así que la
  varianza run-a-run debería ser cero. **Verificarlo** re-corriendo 3 secuencias, no asumirlo.

### Resultados (123/123, corrido 2026-07-29T20:05Z -> 21:35Z, `raw/asym-repro/`)

Jetson a 15 W, governor `schedutil`, mismo estado de potencia registrado en el manifiesto de
`full-sweep-30`. Un pase, init con caja GT del frame 1, sin reinicio.

| métrica | publicado | medido | delta |
| --- | --- | --- | --- |
| **AUC UAV123** (convención OPE) | **66.5** | **67.1** | **+0.6** |
| precisión | no reportado | — | — |
| mIoU (nuestro, mediana por secuencia) | — | 0.775 | — |
| IoU@0.25 / IoU@0.5 | — | 0.997 / 0.974 | — |
| p50 ms/frame (mediana de secuencias) | 30-60 (estimado) | **29.3** | fuera por debajo |
| frames perdidos | — | 0.0 % | — |
| falsos positivos en hueco de GT | — | 2683 (2.4 % de frames sin GT) | — |
| pico de GPU | — | 51.6 MB | — |

**Veredicto: |67.1 − 66.5| = 0.6 <= 1.0 -> arnés validado.** Se puede seguir al experimento completo.

**Lo que decidió el veredicto no fue el modelo, fue la convención de la métrica.** El primer agregado
dio **68.9**, es decir +2.4, dentro de la banda "investigar antes de seguir". La sospecha
preregistrada nº 2 (tratamiento de los frames con GT ausente) y la nº 3 (definición de AUC) eran las
correctas, y las dos a la vez. Convención de la casa: excluir los frames sin GT y contar aciertos con
`>=`. Convención de los toolkits OPE, verificada leyendo el fuente de `pytracking`
(`analysis/extract_results.py`, no de memoria):

- `err_overlap[~valid] = -1.0` y `exclude_invalid_frames=False` por defecto, así que el denominador es
  la **longitud completa** de la secuencia: un frame sin GT es un fallo en todos los umbrales, no un
  frame excluido.
- El test es `>` **estricto**, no `>=`, así que un frame con IoU 0 falla incluso en el umbral 0 y la
  curva no arranca en 1.0.
- 21 umbrales, `arange(0, 1.05, 0.05)`.

Bajo esa convención el mismo run lee 67.1. La diferencia (1.3 puntos) es mayor que la tolerancia de
replicación de ±1.0, o sea que confundirlas habría sido el veredicto entero. `auc_ope()` en
`analysis/aggregate.py` implementa la convención publicada y lleva esto escrito en su docstring; es
la única columna que es **media** sobre secuencias en vez de mediana, por el mismo motivo.

**Efecto secundario: cambia también toda la columna AUC de SAM2.** Reagregado `full-sweep-30` con
`auc_ope`: `c704` 62.6, `c640` 61.3, `t1024` 59.7, `t768` 58.4, `c512` 56.2, `t640` 54.6, `t512` 48.7
(antes 65.7 / 64.0 / 62.4 / 61.1 / 59.4 / 57.7 / 51.0 con la convención de la casa). **No** son
comparables con el 66.5 publicado: son 30 clips, no UAV123 completo.

**Estimación frente a real.**

| | preregistrado | real |
| --- | --- | --- |
| latencia | 30-60 ms (derating desde AGX Xavier) | 29.3 ms mediana, 40.4 ms máximo |
| runtime total | 1.5-2.5 h | ~1.5 h |

La estimación de latencia se queda corta por debajo: el derating 2.7x desde AGX Xavier era la parte
conservadora y el modelo es 12x más pequeño que HiT-Base, lo que evidentemente pesa más. Sale del
techo optimista, no del pesimista. **Esta es la cifra que la revisión de literatura marcó como
inexistente**: ningún tracker SOT publicado tiene número en Orin Nano.

**Dónde falla.** 14 secuencias con AUC < 30 sobre 123. Las 8 peores:

| secuencia | AUC | mIoU | frames |
| --- | --- | --- | --- |
| uav5 | 5.9 | 0.058 | 139 |
| car11 | 6.9 | 0.074 | 337 |
| uav4 | 7.7 | 0.052 | 157 |
| uav8 | 8.8 | 0.088 | 301 |
| bird1_2 | 10.3 | 0.121 | 703 |
| car12 | 10.8 | 0.107 | 499 |
| car15 | 11.6 | 0.117 | 469 |
| bike2 | 13.7 | 0.149 | 553 |

Todas aéreas y de objetivo pequeño: es el tercil difícil otra vez, el mismo régimen donde SAM2 se
cae. El candidato no arregla ese régimen por ser candidato — lo que arregla, si algo, es el coste.

**Verificación visual (obligatoria, no inferida del log).** Overlay renderizado de `uav5` frame
70/139, abierto con `Read`: la caja GT (verde) está sobre el objetivo diminuto junto al muro, la
predicción (azul) se ve en el panel de entrada arriba a la derecha, y la ventana de búsqueda naranja
(101 px de lado) está desplazada al borde derecho del frame, lejos del objetivo. IoU 0.00. Es deriva
real del tracker, no un fallo de render: el frame tiene contenido, el objetivo existe y el modelo
está mirando a otro sitio. En `bike1` el mismo overlay muestra el ciclista encajado con IoU 0.90 y
ventana de 322 px, así que el pipeline de render está sano en ambos extremos.

**Comparación directa en `bike1`** (misma clip, mismo protocolo):

| arm | mIoU | p50 ms |
| --- | --- | --- |
| `asym_b` | 0.882 | 29.7 |
| `sam2_c640` | 0.916 | 159.1 |
| `sam2_t1024` | 0.884 | 434.0 |

Iguala a `t1024` con **14.6x menos latencia** y 51.6 MB de pico de GPU.

**Determinismo: verificado, no asumido** (`raw/asym-determ/`). Re-corridas `uav5`, `bike1` y `car11`
en un proceso nuevo y comparadas caja a caja contra `raw/asym-repro/`: **0 cajas distintas de 3561
frames**. La latencia sí varía, como debe (p50 27.8 vs 28.3, 29.9 vs 29.6, 28.4 vs 28.7 ms), o sea
que la varianza run-a-run de las métricas de calidad es exactamente cero y un solo pase basta. Los
tests de significancia del experimento completo se parean, por tanto, sobre clips, no sobre pases.
