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

- `2026-07-30T01:05Z` — cola escrita. `asym-conf` en 100/123. Matada una espera zombi de
  `crop-truck3` que llevaba 24 h consultando la Jetson cada 20 s (`jetson.py status` no imprime
  `NOT-RUNNING` para un run-id que ya no conoce, así que el `grep` nunca casaba).
