# Cola de la noche — 2026-07-29/30

Trabajo ordenado para ejecutar sin el autor delante. Cada entrada lleva comando exacto, coste
estimado y criterio de terminado. Los hallazgos van al chat; esta cola solo dice qué hacer.

Regla que no se rompe: **nada de `git push`**. Todo se commitea en `feat/asymtrack-candidate` y se
queda ahí.

Dispositivo serializado: un run a la vez en la Jetson. El orden está elegido para que la Jetson no
se quede parada mientras yo escribo código.

---

## Q1 — `asym-conf`: la señal de presencia sobre las 123 secuencias

**Estado: corriendo**, 100/123 al cerrar la sesión con el autor. ~15 min restantes.

```
python jetson.py status asym-conf
python jetson.py fetch  asym-conf
python analysis/presence.py raw/asym-conf
```

Mide `presence_auc` (ROC AUC del corner-peak como clasificador de "GT presente"), `f_lt` y `maxgm`,
mediana sobre las **33** secuencias con huecos (30747 frames, 2683 ausentes).

**Lectura pre-registrada** (escrita antes de ver el número, en el docstring de `analysis/presence.py`):

| `presence_auc` | Qué se hace |
| --- | --- |
| >= 0.75 | El sustituto sirve. Q3 se construye sobre él. |
| 0.65 – 0.75 | Zona gris. Q3 se construye igual **y además** un verificador coseno para comparar. |
| < 0.65 | Muerto. Q3 no se construye sobre esto; hace falta verificador aparte o un tracker con cabeza de score entrenada. |

Referencia del smoke de 2 secuencias: 0.722 (car12 0.67, bird1_3 0.77). n=2, no se sobreinterpreta.

**Hecho cuando**: la tabla de `presence.py` está en el chat y la rama de decisión elegida está
anotada aquí.

---

## Q2 — `sam2_c640_pad`: separar el tamaño de ventana del tratamiento del borde

Arreglo del confundido que detectó el autor. `c640` **desliza** la ventana para que quepa en el
frame; `f5` **rellena** con ceros. Compararlos mezcla dos cambios. Y no es un caso raro: un frame de
UAV123 es 1280x720, así que una ventana de 640 solo cabe en vertical si el centro del objeto está en
una banda de 80 px de 720 — `c640` está deslizado en vertical **casi siempre**.

Escalera resultante: `c640` (desliza) -> `c640_pad` (rellena, mismo tamaño) -> `f5` (rellena, tamaño
escalado al objeto). Cada peldaño cambia una cosa.

Implementación: bandera `pad` en `Sam2CropArm` que usa `crop_pad` en vez de `crop_window`. `crop_pad`
ya existe y ya está cubierta por `analysis/test_geometry.py`. Es un brazo nuevo, no un cambio en
`c640`: **`c640` se queda congelado como incumbente**.

```
python analysis/test_geometry.py          # tiene que seguir diciendo geometry OK
python jetson.py sync
python jetson.py run --arms sam2_c640_pad --seqs <las 30 de full-sweep-30> --id c640pad
```

**Coste**: ~70 min (SAM2 a ~158 ms/frame sobre 30 secuencias).

**Estimación a priori**: si el borde no importa, `c640_pad` cae dentro de +-1 punto de AUC de `c640`
y el salto real está entre `c640_pad` y `f5`. Si `c640_pad` se hunde, entonces parte de lo que
`c640` ganaba era el deslizamiento, y eso reabre la interpretación de todo el barrido de crop.

**Hecho cuando**: fila de AUC/latencia de los tres brazos en el chat, y un overlay leído con Read
que muestre la ventana rellenada en un frame donde el objeto está pegado al borde (obligatorio:
sin imagen vista no hay veredicto sobre geometría).

---

## Q3 — `asym_lt`: el reenganche. La pieza que interesa.

Lo medido esta tarde sobre `raw/full-sweep-30`: **ningún** brazo reengancha. Frame completo a
máxima resolución (`t1024`) recupera 3 de 13 pérdidas; crop (`c704`) recupera 5 de 13. El banco de
memoria de SAM2 propaga, no busca. AsymTrack ni se entera de que se ha perdido, porque
`clip_box(..., margin=10)` le obliga a devolver caja siempre.

Así que el reenganche es una **envoltura**, no un modelo. LTMU dice exactamente eso. Se construye
una sola vez y sirve para los dos modelos.

### Diseño pre-registrado

Cinco piezas, ninguna red nueva:

1. **Tracker local**: AsymTrack tal cual, 1 ventana, ~29-40 ms.
2. **Verificador**: `conf` = pico del corner-softmax (Q1 dice si vale).
3. **Máquina de estados con histéresis**: `tracking` -> `lost` tras **k=3** frames con
   `conf < tau_lo`; `lost` -> `tracking` en cuanto un candidato pasa `conf >= tau_hi`. Dos umbrales
   distintos a propósito: con uno solo oscila.
4. **Redetector = el propio AsymTrack sobre varias ventanas.** En `lost`, además de la ventana
   local, se evalúan **N=5 ventanas candidatas** por frame de un barrido ráster del frame a la
   escala del último objeto conocido; se toma el argmax de `conf`. El barrido se **amortiza**: no
   hay pico de latencia, se cubre el frame en ~8 frames (~1.6 s). El presupuesto sale de los 5 Hz
   que el autor confirma como régimen de trabajo real: 200 ms/frame, AsymTrack gasta 29, caben 5
   ventanas más.
5. **Template**: el del frame 0, congelado. Verificado en el código del device — `self.template` se
   asigna una vez en `initialize()` y no se reasigna en todo el fichero. **No se toca nunca**, y
   menos estando perdido: ahí es donde se memoriza al distractor.

Salida: **caja solo en estado `tracking`**; `None` mientras está perdido. Ese es el punto — MaxGM
premia abstenerse y `asym_b` puntúa mal justo ahí (2683 frames sin objeto, 2683 respuestas).

### Cómo se fijan `tau_lo` y `tau_hi` sin hacer trampa

De la distribución de `conf` de Q1, **no** ajustando contra el resultado de Q3:

- `tau_lo` = el `conf` al 90% de TPR (deja pasar casi todo lo presente; solo dispara cuando está claro).
- `tau_hi` = el `conf` al 5% de FPR (para volver hace falta evidencia fuerte).

Ajustados sobre las secuencias con huecos de **índice par**, evaluados sobre las de **índice impar**.
Con 33 secuencias sale ~16/17. Es poca cosa, pero es la diferencia entre un umbral y un umbral
elegido para que salga bien. El número que se reporta es el del conjunto de evaluación, y se dice
que n=17.

### Ejecución

```
python jetson.py sync
python jetson.py run --arms asym_b,asym_lt --seqs <las 33 con huecos> --id asym-lt
python analysis/presence.py raw/asym-lt      # f_lt y maxgm de los dos
python analysis/aggregate.py raw/asym-lt     # AUC OPE, para ver qué cuesta abstenerse
```

**Coste**: AsymTrack sobre las 33 son ~20 min por brazo con 1 ventana. Peor caso absoluto de
`asym_lt` (perdido en todos los frames, 6 ventanas): ~92 min. Dos brazos, presupuesto ~2 h.

**Estimaciones a priori** (que se comparan con el resultado, un fallo de estimación es contenido):

- `maxgm` sube claramente. Es casi por construcción: abstenerse en 2683 frames donde no hay nada
  puntúa mejor que responder, y es la métrica diseñada para eso. Si **no** sube, la máquina de
  estados no está entrando en `lost` y hay que mirar los umbrales, no la idea.
- `f_lt` sube menos, o nada. La precisión mejora al callarse pero el recall baja si el estado `lost`
  se atasca.
- **AUC OPE baja un poco.** El convenio OPE cuenta los frames sin respuesta como fallo, así que
  abstenerse se penaliza. Esperado y aceptable: es la métrica equivocada para esto, y decirlo
  explícitamente es parte del resultado.
- Recuperación tras pérdida: la referencia a batir es el ~35-40% medido en los brazos SAM2.

**Hecho cuando**: tabla `asym_b` vs `asym_lt` (`maxgm`, `f_lt`, AUC OPE, p50, p95) en el chat, más
**un clip** de una secuencia donde entra en `lost`, barre y reengancha — el comportamiento es el
punto, así que toca clip y no figura. Visto con Read antes de afirmar nada.

---

## Fuera de la cola a propósito

- `README.md`, ledgers y `proof/` no se escriben: el `CLAUDE.md` de este directorio lo prohíbe hasta
  que el autor lo pida. Cuando lo pida se escribe todo de golpe.
- No se toca `sam2_f5` como brazo retrospectivo: aplazado por el autor.
- Todo lo demás vive en `TODO.md`, que no es una cola sino deuda.

## Bitácora de la noche

Se anota aquí lo que pase, con hora Madrid. Un run que falla se anota igual: un negativo es
contenido.

- `2026-07-30T05:10Z` — **Q2 cerrado: el borde no importa.** `sam2_c640_pad` sobre las mismas 25
  secuencias que el incumbente: AUC 64.8 vs 65.0 de `c640`, mIoU 0.787 vs 0.785, @0.5 0.983 en
  ambos, latencia idéntica (159.4 vs 159.3 ms). Dentro del +-1 punto que decía la estimación a
  priori, así que **deslizar o rellenar es indiferente** y lo que separa `c640` de `f5` tiene que
  ser el tamaño de ventana escalado al objeto, no el tratamiento del borde. Lanzado `f5-30` para
  cerrar el tercer peldaño sobre las mismas secuencias.
  Verificado a ojo (`scratchpad/q2_tile.png`, `car1_3` frame 307, el coche pegado al borde
  superior): arriba `c640_pad` con la ventana centrada saliéndose del frame y el panel de entrada
  **negro en la banda superior** — el relleno de ceros, visible; abajo `c640` con la misma ventana
  deslizada hacia dentro y el panel lleno. IoU 0.79 vs 0.75 en ese frame.
  Dos cosas más que salieron de aquí:
  - **5 secuencias quedaron fuera por la compuerta `upscales`**: `uav1_2,uav2,uav3,uav5,uav7` son
    720x480 y una ventana de 640 no cabe en 480. La compuerta es correcta. Lo incómodo es que
    `full-sweep-30` es anterior a ella y **sí** tiene esas 5 celdas para `c640`/`c704`: los números
    publicados del incumbente incluyen 5 clips que la regla actual del propio proyecto declara
    inválidos por interpolación. Las comparaciones de arriba están hechas sobre las 25 comunes.
  - `render_overlay` no sabía re-derivar la ventana del brazo `pad` (la re-derivaba deslizada y
    reventaba con `AssertionError: (2, [46, -199, 640], [46, 0, 640])`); origen negativo es
    justamente el tratamiento bajo prueba. Arreglado.
- `2026-07-30T03:45Z` — **Q3 cerrado: `asym_lt` no gana en ninguna métrica.** 33 secuencias con
  huecos, dos brazos. Mitad de evaluación (16 impares, la que cuenta): `maxgm` 0.492 vs 0.493 de
  `asym_b` — plano, no sube; `f_lt` 0.770 vs 0.883 — baja; AUC OPE 45.4 vs 52.0 sobre las 33.
  Latencia idéntica (p50 30.5 vs 30.4 ms): el ráster amortizado no cuesta nada, esa parte del
  diseño sí funciona. La estimación a priori decía "`maxgm` sube claramente, es casi por
  construcción"; falso, y el porqué es el resultado.
  El desglose: 3737 abstenciones, solo 998 sobre frames realmente vacíos — **precisión de
  abstención 26.7%**. Se calla en 2739 frames CON objeto para acertar 998 sin él. Y reengancha
  peor de lo que se pierde: 162 episodios de pérdida, 40 vuelven con IoU > 0.3 = **24.7%**, por
  debajo del 35-40% que recuperaban pasivamente los brazos SAM2. El coste es asimétrico — `car7`
  cae de mIoU 0.740 a 0.003 porque reengancha sobre un distractor y ya no vuelve; `bike2`
  0.149 a 0.013.
  Diagnóstico: la máquina de estados es mecánicamente correcta (se ve en el clip), el verificador
  no. Con `presence_auc = 0.711` el redetector elige mal el candidato y el `tau_hi` no deja volver
  a tiempo. No es un problema de umbrales que se arregle moviéndolos: subir `tau_hi` empeora las
  2739 abstenciones falsas, bajarlo empeora los 122 reenganches malos.
  **Verificador coseno: tampoco.** `cos_auc` 0.714 sobre las 33 (0.770 en la mitad impar) contra
  0.711 (0.720) del pico del corner-softmax. Dos verificadores independientes, el mismo techo
  mediocre. La rama gris del pre-registro está agotada: lo que falta es una cabeza de score
  entrenada, no otra heurística sobre las features de AsymTrack.
  Clip: `person17_1` 570-645 (`scratchpad/p17_reattach.mp4`), leído con Read en 4 frames. 579
  responde con el objeto ausente, 591 y 616 en `LOST` con la ventana de 205 px barriendo, 632
  reengancha con IoU 0.76. El frame 616 es el hallazgo visual: la persona está **visible y dentro
  de la ventana** y el brazo sigue en `LOST` — las 2739 abstenciones falsas en una imagen.
- `2026-07-30T02:45Z` — smoke de `asym_lt` (car12, bird1_3) con un fallo encontrado **mirando el
  overlay**, que es exactamente para lo que está la regla. La máquina de estados funciona
  mecánicamente: frame 117/123 en `LOST`, ventana barriendo otra zona del frame, frame 125
  reenganche con IoU 0.67 sobre el coche. Pero la ventana de sondeo ponía `entrada 508px` mientras
  el brazo trackeaba con 154-196px: `self.size` se actualizaba en **todos** los frames de
  `tracking`, incluidos los k de confianza baja previos a la pérdida, donde la caja ya está
  reventada. La escala del ráster salía de la caja rota. Corregido: solo actualiza escala un frame
  por encima de `tau_lo`. Añadida la aserción al self-check. Re-smoke lanzado.
  De paso, dos fallos preexistentes de `render_overlay` (no causados por `asym_lt`, `asym_b` fallaba
  igual): la re-derivación exacta de la ventana no puede cumplirse para los brazos AsymTrack porque
  el device la construye desde el `state` float y la fila guarda la caja truncada a int — se
  comprueba el centro; y la rama "un frame perdido congela la ventana" se aplicaba a `asym_lt`,
  cuyo objetivo es precisamente moverla.
- `2026-07-30T02:20Z` — Q1 cerrado. `presence_auc = 0.711` sobre las 33 secuencias con huecos:
  **zona gris**, así que se construye Q3 **y** el verificador coseno (`AsymArm.conf_cos`, NCC de
  media cero contra el parche template del frame 0, ~0.3 ms, sin red nueva). `f_lt` y `maxgm`
  estaban medianados sobre las 123 secuencias, y en las 90 sin huecos un tracker que siempre
  responde saca `f_lt = 1` por construcción; corregido a solo las 33: `f_lt 0.826`, `maxgm 0.482`.
  Ese 0.482 es la referencia a batir, no el 0.385 que salía antes. Umbrales ajustados sobre las 17
  pares: `tau_lo = 0.3920`, `tau_hi = 0.7293`, sin aviso de solape — la histéresis es real.
  5 de 33 secuencias con `presence_auc < 0.5` (uav6 0.34 está anticorrelada): el sustituto no es
  solo débil, en algunas secuencias engaña.
- `2026-07-30T01:05Z` — cola escrita. `asym-conf` en 100/123. Matada una espera zombi de
  `crop-truck3` que llevaba 24 h consultando la Jetson cada 20 s (`jetson.py status` no imprime
  `NOT-RUNNING` para un run-id que ya no conoce, así que el `grep` nunca casaba).
