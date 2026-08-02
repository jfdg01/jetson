# Tracker capacity sweep — catálogo de candidatos

Sin preregistrar. Experimento para analizar el comporamiento de la placa dado un conjunto de modelos estilo sam2. Creado: 2026-07-28T18:41Z

## Estado

Estado del dispositivo verificado el 2026-07-28T18:41Z tras matar `llama-server`: cero procesos

> 100 MB, 5.9 GB de RAM disponibles de 7.6, 126 GB de disco libre.

## Modelos a probar

Catálogo inicial, 27 candidatos (de estos solo llegaron a correr SAM2.1-tiny, SAMURAI, AsymTrack-B
y DAM4SAM; el resto quedó descartado por la revisión de literatura más abajo):

1. SAM2.1-hiera `tiny` / `small` / `base-plus` / `large`
2. EdgeTAM, EfficientTAM-ti, EfficientTAM-s
3. SAMURAI y SAM2Long, ambos sobre tiny
4. OpenCV: `TrackerNano`, `TrackerVit`, `TrackerDaSiamRPN`, `TrackerGOTURN`, `TrackerMIL`
5. PyTracking: ATOM, DiMP-18, DiMP-50, PrDiMP-50, ToMP-50, KeepTrack
6. Transformer: OSTrack-256, MixFormerV2-S, HiT-Small
7. Detector + asociación: YOLO11n/YOLO11s + ByteTrack, YOLO11n + BoT-SORT, ByteTrack con
   detecciones oráculo

## Clips

30 secuencias de las 123 de UAV123, elegidas por max-min voraz sobre features z-normalizadas
(duración, área mediana, rango y tendencia de escala, fracción y número de huecos sin GT,
velocidad relativa al tamaño, contacto con el borde, aspect ratio y su variación, los 12
atributos UAV123 a peso 0.5) con tope de 5 por categoría. Selector: `analysis/select_sequences.py`.

```
bike1       bike2       bird1_1     bird1_3     boat3       boat6
building5   car12       car16_1     car1_3      car8_2      car9
group1_2    group2_3    person18    person19_3  person20    person21
person4_1   truck2      truck3      uav1_2      uav2        uav3
uav5        uav7        wakeboard1  wakeboard5  wakeboard7  wakeboard8
```

n=30, 27276 frames (24% del total), media 909 frames — la media poblacional es 915, así que el
subconjunto no queda sesgado en duración pese a no balancearla explícitamente. Rango 133
(`uav2`) a 3085 (`bike1`). Área mediana del objeto de 104 px (`uav2`) a 57962 px (`person20`),
557×. Tendencia de escala de −0.96 (`wakeboard1`, encoge monótono) a +0.90 (`person4_1`, crece).
10 de las 33 secuencias con huecos de GT. 25 clips a 1280×720 y 5 a 720×480 (los `uav*` son el
único grupo de baja resolución). Las 10 categorías presentes, los 12 atributos cubiertos; los
más flojos son BC (7 de 21) y FM (8 de 28).

Orden de columnas de atributos en `anno/UAV123/att/`: `SV ARC LR FM FOC POC OV BC IV VC CM SOB`,
según la cabecera de `DatasetAnnotation.pdf` — **no es alfabético**. Verificado: FOC concuerda
1.00 con "tiene frames NaN", que es su definición.

## Variables controladas

Sensores verificados en dispositivo el 2026-07-28: INA3221 en `1-0040` (raíles `VDD_IN`, `VDD_CPU_GPU_CV`, `VDD_SOC`), 8 zonas térmicas en `/sys/devices/virtual/thermal/`, zram activo (6 × 634 MB), 6 cores, governor `schedutil`, L4T R36.5.0. Nota: en esta placa
`jetson_clocks` **no** cambia el governor, que sigue en `schedutil` después de aplicarlo; lo que
fija son las frecuencias, y eso es lo que se comprueba, no el nombre del governor. El manifest
registra ~422 MB de swap en uso de forma residual (repartidos por igual entre los 6 zram, ya
presentes antes de arrancar); la invalidación por swap se juzga por el *delta* durante el arm.

**Fijas.** *Plataforma:* 15 W mode 0 y `jetson_clocks` (sin DVFS), 6/6 cores, ventilador en perfil
fijo, escritorio apagado (`multi-user.target`), red inactiva durante la medida, todo en NVMe, cero
procesos >100 MB. Se verifica por arm; **un arm que toca swap o entra en throttle se invalida**.
*Software:* venv propio `~/tracker-sweep/.venv` congelado (Python 3.10.12, torch 2.8.0+cu126,
cv2 4.11.0), **precisión bf16 vía `torch.autocast`** en todos los arms SAM2 (es la que despliega
el resto del proyecto; en fp32 el mismo arm va 3.4× más lento, ver smoke test),
hilos, `cudnn.benchmark`, TF32 y semillas fijados, `torch.compile` desactivado,
**un proceso nuevo por arm** (sin contaminación de allocator ni de caché cuDNN). *Tarea:* mismas
30 secuencias en el mismo orden, caja inicial = GT del frame 0, frames pre-decodificados a disco
con el decode **fuera** del bucle medido, 1 objeto por secuencia, pasada única sin re-init tras
pérdida, salida = caja por frame (máscara → bbox del contorno en SAM2 y derivados). *Protocolo:*
warm-up descartado, `time.monotonic` con `torch.cuda.synchronize()`, latencia por frame y no media
global, k repeticiones con mediana entre ellas, **orden de arms aleatorizado** para descorrelacionar
la deriva térmica de la identidad del arm, mismo sampler de recursos para todos.

**Manipuladas.** Arm (27 modelos, eje primario); resolución 512/640/768/1024, backend torch fp16 vs
TRT fp16 y objetos simultáneos 1/2/4 solo sobre los supervivientes del primer corte.

**Medidas.** FPS en régimen; latencia p50/p95/p99 por frame; latencia de inicialización aparte (es
un coste distinto); RAM host pico (RSS) y memoria GPU pico; potencia media y **energía por frame
(J/frame)** vía INA3221 — métrica de hardware edge, no derivada; temperatura máxima y eventos de
throttle; exactitud por IoU + AUC del success plot.

**Confusores declarados.** Deriva térmica → orden aleatorizado, gate de enfriamiento y temperatura
registrada por arm. Fragmentación de memoria → proceso nuevo por arm. Dificultad desigual entre
secuencias → mismo conjunto para todos y análisis **pareado** por secuencia. Datos y receta de
entrenamiento distintos entre modelos → **irreducible**, se declara: el sweep compara modelos tal
como se publican, no arquitecturas en igualdad de entrenamiento.

**Aviso estadístico.** 27 arms no pueden ser todos inferenciales: con la familia Holm del proyecto,
corregir sobre 27 contrastes deja cualquier diferencia sin poder a `n>=25`. Postura propuesta para
cuando esto se pre-registre — el sweep es **caracterización descriptiva** de la placa, no una claim
gating, con **uno o dos contrastes inferenciales declarados de antemano**; lo demás es exploratorio
y se etiqueta como tal.

## Rig y comunicación con la Jetson

Todo el experimento es autocontenido en este directorio, sin reutilizar scripts ni entornos de
campañas anteriores. El repo es la fuente de verdad; `~/tracker-sweep` en la Jetson es un espejo
que nunca se edita a mano.

| Pieza | Rol |
| --- | --- |
| `jetson.py` | único punto que habla con el dispositivo: `setup`, `sync`, `stage`, `run`, `status`, `fetch` |
| `device/driver.py` | escribe el manifest, luego un **proceso nuevo por (arm, secuencia)**, orden barajado |
| `device/run_arm.py` | un arm sobre una secuencia; decode cronometrado aparte y excluido de la latencia |
| `device/trackers.py` | registro de arms con API uniforme `init(frame, box)` / `step(frame)` |
| `device/stream_carry.py` | copia vendorizada byte a byte de la de Part V |
| `analysis/uav123.py` | acceso a UAV123 (solo host): `configSeqs.m`, cajas, atributos |
| `analysis/select_sequences.py` | selección de las 30 secuencias |
| `analysis/render_overlay.py` | puntúa contra GT y renderiza el overlay |

Decisiones del rig y su porqué:

- **Venv nuevo desde cero** en el dispositivo (`~/tracker-sweep/.venv`, Python 3.10) en vez de
  reusar `~/sam2-bench/.venv`: el objetivo es aislar de contaminación previa. Los wheels CUDA
  aarch64 solo existen en `https://pypi.jetson-ai-lab.io/jp6/cu126`.
- **Streaming obligatorio, nunca el camino batch.** `init_state` sobre un directorio precarga el
  clip entero a GPU (535 frames a 1024 ≈ 6.7 GB) y en 8 GB compartidos muere con
  `NVML_SUCCESS == r INTERNAL ASSERT FAILED at CUDACachingAllocator.cpp:1131`. Además el camino
  streaming es el que se despliega en el resto del proyecto.
- **Runs desacoplados** (`setsid nohup`): un ssh caído no puede matar un sweep de horas.
- **El dispositivo nunca ve GT más allá de la caja del frame 0.** La puntuación ocurre en el host,
  así que es estructuralmente imposible que un arm consulte GT que no debería tener.

## Bitácora: un fichero por evento

El detalle completo de cada tanda vive en `notes/`. Aquí queda el resumen y el puntero; los números
de cada tabla, las verificaciones visuales y los tropiezos están en el fichero enlazado. Cada fichero
abre con su fecha, su rango horario y su coste de dispositivo.

**Coste total del barrido: ~53.9 h de dispositivo** sobre la Jetson a 15 W, 1333 corridas (la nota
18 no añade ninguna: es reanálisis). Es una
estimación, `sum(init_ms + frames * ms_p50)` sobre los JSON de `raw/`; no incluye el tiempo muerto
entre etapas ni los renders de overlay, así que el reloj de pared es mayor.

### 1. bf16 y la geometría de la ventana — [`notes/01-bf16-y-geometria-de-ventana.md`](notes/01-bf16-y-geometria-de-ventana.md) · 0.80 h

`torch.autocast` faltaba y no fallaba: fp32 1449.9 ms contra bf16 432.6 ms p50, 3.4x regalado. Tres
pilotos de una secuencia fijaron la geometría del barrido antes de gastar horas: recortar gana a
subir resolución, la ventana se **desliza** para caber (no se recorta), 704 en vez de 720 porque
Hiera exige múltiplo de 32, y la regla de provenance `win_checked`. Diagnóstico de fuga de máscara
por el HUD en `bird1_1`.

### 2. Barrido 30x7: `c640` es el punto de operación — [`notes/02-barrido-30x7-punto-de-operacion-c640.md`](notes/02-barrido-30x7-punto-de-operacion-c640.md) · 11.50 h

210/210 corridas, 12.1 h. **`sam2_c640` es el punto de operación**: mIoU 0.759 a 159.4 ms, por
encima de `t1024` (0.752) a 2.7x menos latencia. Recortar deja de pagar por encima de 640. Contra:
`c640` es el peor en falsos positivos en hueco (576) y nunca se abstiene.

### 3. El tercil difícil, diseñado y cancelado — [`notes/03-tercil-dificil-disenado-y-cancelado.md`](notes/03-tercil-dificil-disenado-y-cancelado.md) · 0 h

El barrido difícil se **mató** antes de correr; sobrevive su diseño de dataset (41 clips del tercil
difícil + 4 MEDIO + 4 FÁCIL pareados por categoría, 49 clips / 41.461 frames) y sus limitaciones
declaradas. Incluye las heurísticas de recuperación implementadas y nunca corridas, y la auditoría
del índice de dificultad.

### 4. Rejilla de stride 16: el objetivo es subcelular — [`notes/04-rejilla-stride-16-objetivo-subcelular.md`](notes/04-rejilla-stride-16-objetivo-subcelular.md) · 0 h

El defecto común a los seis brazos, en una cuenta: la atención de memoria solo recibe
`current_vision_feats[-1]`, stride 16, así que la decisión "¿sigue aquí?" corre sobre una rejilla de
`image_size/16`. Un objetivo de 28 px es **subcelular** en `t640`, 1.75 celdas en `c640`, y serían 8
celdas con el factor 5 de la literatura.

### 5. Literatura: tracking en edge y contra-UAS — [`notes/05-literatura-edge-y-contra-uas.md`](notes/05-literatura-edge-y-contra-uas.md) · 0 h

Qué se descarta y por qué (FocusTrack solo IR y RTX 3090, SRRT sin código, LAF-YOLOv10 otra tarea,
SAM2Long demasiado pesado, EdgeTAM sin portar), qué sí resuelve la literatura, y los huecos
confirmados: **ningún tracker SOT publicado tiene número en Orin Nano**, no hay curva publicada de
resolución/precisión/latencia, y las regresiones INT8 en Jetson.

### 6. AsymTrack-B: elección e integración — [`notes/06-asymtrack-b-eleccion-e-integracion.md`](notes/06-asymtrack-b-eleccion-e-integracion.md) · 0 h

Por qué él: 66.5 de AUC en UAV123 con 3.36 M de parámetros, MIT, 192/384. Instalación, dos
tropiezos de integración (`rsync --delete` se llevó el clon; numpy 2.2.6 contra la rueda de torch de
jetson-ai-lab, pineado a 1.26.4), humo parcial sin pesos y los cambios de arnés que trajo.

### 7. Réplica de AsymTrack: AUC 67.1 contra 66.5 — [`notes/07-replica-asymtrack-auc-67-1-vs-66-5.md`](notes/07-replica-asymtrack-auc-67-1-vs-66-5.md) · 1.14 h

Peldaño 2 de la escalera de replicación, sobre UAV123 completo. **AUC 67.1 contra 66.5 publicado,
delta 0.6 <= 1.0: arnés validado.** Lo que decidió el veredicto fue la convención de la métrica, no
el modelo — la convención de la casa daba 68.9; `auc_ope()` copia la de `pytracking` y la diferencia
(1.3 puntos) es mayor que la tolerancia. p50 29.3 ms, por debajo de la estimación 30-60. Determinismo
verificado: 0 cajas distintas de 3561.

### 8. Preregistro: separar geometría, modelo y reenganche — [`notes/08-preregistro-geometria-modelo-reenganche.md`](notes/08-preregistro-geometria-modelo-reenganche.md) · 0 h

El diseño de cuatro brazos que separaba geometría, modelo y reenganche. Se ejecutó por partes y
`asym_b_redet` nunca se corrió; sobrevive el razonamiento: re-detección agnóstica de clase estilo
SiamSTA (0.9/0.1), el factor 5 fijado a priori desde la ablación de OSTrack, y las métricas de
contra-UAS que el mIoU no ve.

### 9. Presencia por `conf`, borde de ventana y `asym_lt` — [`notes/09-presencia-conf-borde-de-ventana-y-asym-lt.md`](notes/09-presencia-conf-borde-de-ventana-y-asym-lt.md) · 3.11 h

Q1: `conf` como señal de presencia da `presence_auc` 0.711 — zona gris del preregistro. Q2: deslizar
o rellenar el borde es **indiferente** (`c640` contra `c640_pad`), luego lo que separa a `f5` es el
tamaño de ventana. Q3: `asym_lt` es **negativo en todo** — precisión de abstención 26.7%, de
reenganche 24.7%, por debajo de lo que los brazos SAM2 recuperaban pasivamente. El verificador coseno
llega al mismo techo: falta una cabeza de score entrenada, no otra heurística.

### 10. Ventana escalada al objeto: colapso y suelo — [`notes/10-ventana-escalada-al-objeto-colapso-y-suelo.md`](notes/10-ventana-escalada-al-objeto-colapso-y-suelo.md) · 2.85 h

Ventana `5*sqrt(w*h)` escalada al objeto: pierde 7.1 puntos de AUC pero saca los mejores @0.25, @0.5
y falsos positivos en hueco del barrido. La causa es **colapso de escala con realimentación
positiva** (`car9` 647 px a 52 px). Con suelo en el lado del frame 0 recupera 4.1 de los 7.1 puntos y
emite 115 FP en hueco contra 542 del incumbente, a la misma latencia y la misma mIoU.

### 11. DAM4SAM: integración y perilla de resolución — [`notes/11-dam4sam-integracion-y-perilla-de-resolucion.md`](notes/11-dam4sam-integracion-y-perilla-de-resolucion.md) · 1.70 h

SAM2.1 con memoria consciente de distractores (DRM): mismo checkpoint, cero entrenamiento. Venv
propio, `vot-toolkit` pineado a 0.7.1, y el tamaño de entrada abierto como perilla (640 corre a 198
ms contra 431 a 1024). Lectura a n=5: 640 empata al incumbente en mIoU con mejor perfil de error,
1024 es el techo de calidad. El autor lo declara **candidato principal**, con la advertencia de que
n=5 no es una muestra con potencia.

### 12. Escalera 640/768/960: el recorte gana — [`notes/12-escalera-640-768-960-el-recorte-gana.md`](notes/12-escalera-640-768-960-el-recorte-gana.md) · 7.06 h

90 corridas, 7 h 20 min, y **corrige a la baja** la lectura a n=5. La escalera es monótona y
significativa, pero la ganancia es bimodal: en 22 de 30 secuencias subir a 960 vale +0.036 por 203
ms, y toda la señal está en las 8 que colapsan a 640. 768 es el codo. Ningún brazo se abstiene
jamás. Frente al incumbente recortado, DAM4SAM a frame completo no gana hasta 960 y a 2x la
latencia: **el recorte compra más que los píxeles**. `bike2` es geometría, no resolución.

### 13. Señal de presencia, DRM y umbral relativo — [`notes/13-senal-de-presencia-drm-y-umbral-relativo.md`](notes/13-senal-de-presencia-drm-y-umbral-relativo.md) · 12.66 h

`object_score_logits` — la cabeza de oclusión entrenada — sacada del wrapper para DAM4SAM y SAMURAI.
**El DRM no mejora la señal de presencia a 640** (mediana pareada 0.000, p = 0.61); baraja qué
secuencias funcionan. El control `sam2_t768` cierra el confundido: **píxeles compran cajas, no saber
si el objeto está**. El lazo abierto hace que barrer políticas LT no cueste GPU (`lt_sim.py`), y el
umbral **relativo** (`mu - a*sigma`, causal) gana al fijo por la peor secuencia, no por la mediana.
Aquí vive también el error del `--id` repetido y las tres formas en que `pgrep` ha mentido.

### 14. Base pareada a 123 secuencias y el brazo LT — [`notes/14-base-pareada-123-secuencias-y-brazo-lt.md`](notes/14-base-pareada-123-secuencias-y-brazo-lt.md) · 4.72 h

90 corridas nuevas en cuatro etapas encadenadas. **El titular sobrevive al pareado** sobre 123
secuencias: a igual resolución el recorte gana (`c640_pad` bate a `t640` 32/45, p = 0.0005), y
`t768`/`t1024` son indistinguibles del recorte a 640 que cuesta 159 ms. Los brazos DAM4SAM son un
**nulo acotado**, no equivalencia. Paridad de `dam4sam_lt` exacta (0 frames, 0 cajas de 30.747). El
brazo LT sube `gm_ox` +0.105 y baja mIoU -0.016, las dos con p < 0.001: **propuesta medida, no
resultado**. Sin verificación visual de esta tanda. El +0.105 queda corregido en la sección 15, y el nulo de los brazos DAM4SAM frente al recorte, matizado en la 17.

### 15. Validación cruzada de las constantes LT — [`notes/15-validacion-cruzada-de-las-constantes-lt.md`](notes/15-validacion-cruzada-de-las-constantes-lt.md) · 0 h

Leave-one-sequence-out sobre los 312 candidatos de umbral relativo, sin GPU (la política se simula
sobre la traza grabada). **Fuera de muestra el brazo LT es un nulo: p = 0.058**, contra el 0.0005 de
la sección 14, que estaba inflado por reportar en parte sobre las secuencias que fijaron las
constantes. Solo `b = 2` y la ventana móvil son estables entre pliegues; `k` y `w` bailan, o sea que
**la mitad de los parámetros no está determinada por los datos**. El efecto es de cola — tres clips
concentran la ganancia — así que es una palanca condicionada, no un comportamiento por defecto. El
mismo sesgo afecta a `asym_lt`, que **no** se puede validar así porque cierra el lazo.

### 16. Paridad DAM4SAM/SAMURAI: precisión y resolución — [`notes/16-paridad-dam4sam-samurai-dtype-y-resolucion.md`](notes/16-paridad-dam4sam-samurai-dtype-y-resolucion.md) · 6.38 h

92 corridas que matan los dos confundidos de la comparación entre familias. **La precisión no
importa**: bf16 contra fp16 dentro de SAMURAI es nulo en mIoU, AUC y falsos positivos (p = 0.48,
0.58, 0.69), así que no hizo falta el 2x2 completo. **Pareando la resolución, la ventaja de DAM4SAM
existe solo a 960** (mediana +0.008, 21/30, p = 0.0087, sobrevive a Holm); a 640 y 768 las dos
políticas de memoria son indistinguibles. Cuesta un 7% más de latencia y el peldaño entero está a
2.6x del incumbente `c640`. Sin verificación visual de esta tanda.

### 17. Reenganche tras hueco: lo que mIoU esconde — [`notes/17-reenganche-tras-hueco-lo-que-miou-esconde.md`](notes/17-reenganche-tras-hueco-lo-que-miou-esconde.md) · 0 h

Reanálisis sin GPU de las trazas ya grabadas, pareado **por hueco** en vez de por secuencia: se
puntúan los K frames siguientes a cada regreso del objetivo. **La objeción al recorte no se sostiene
en UAV123** — el frame completo no reengancha mejor que el recorte a igual resolución (p = 0.14 /
0.12 / 0.08 a K = 30/60/120), porque el dron sigue al objetivo y este vuelve por donde se fue. Lo que
sí aparece es que **mIoU escondía a DAM4SAM**: `t768` y `t960` baten al incumbente en IoU tras hueco
(+0.011 y +0.016 a K=60, p = 0.003 y 0.0007, sobreviven a Holm) donde mIoU decía nulo. Por debajo de
640 el brazo directamente no redetecta. Los huecos no son independientes, así que los p son
optimistas. Sin verificación visual.

### 18. Ejes de diseño para objetivos pequeños y rápidos — [`notes/18-ejes-de-diseno-objetivos-pequenos-y-rapidos.md`](notes/18-ejes-de-diseno-objetivos-pequenos-y-rapidos.md) · 0 h

Diseño, no tanda: el espacio de configuraciones a barrer bajo el protocolo paced y en qué orden.
Lleva dentro un resultado medido que reordena el resto — **la retención de primer orden recupera el
85% del desplome** que el paced había atribuido a la latencia (`truck3` 0.297 -> 0.699, `car9` 0.763
-> 0.819 con `aggregate.py --foh`), a coste cero, porque cambia el consumidor y no el tracker. Con
eso, "ser lento" cuesta mucho menos y el óptimo de resolución vuelve a subir, así que ese eje se fija
antes de barrer nada. Los otros ejes: máscara contra caja (`cv_*` y `asym_b` nunca corridos en
paced), los tres modos de feed de los que la ventana escalada al objeto sigue sin cruzarse, y la
población objetivo cuantificada — 28 clips de UAV123 bajo `<=40 px` y `>=0.06` anchuras/fotograma,
con TLP descartado por no tener el fenómeno. n = 2 en lo medido; el resto es predicción. Sin
verificación visual.

### 19. El barrido a ritmo real, y la retención de primer orden — [`notes/19-paced-sweep-30-retencion-de-primer-orden.md`](notes/19-paced-sweep-30-retencion-de-primer-orden.md) · 1.66 h

155 corridas a 30 fps con caída al último fotograma. Bajo stream **el orden de paridad se invierte**:
`c704`/`c640` ganaban (0.762/0.759) y ahora pierden contra `c512` (0.439 contra 0.302/0.344), porque
la resolución que compra máscara compra retraso. El resultado que manda es otro: **navegar la caja
retenida en vez de congelarla vale +0.069 de mIoU mediana pareada sobre los 155 pares** (121/155
ganan, p = 4.9e-19, los seis brazos pasan Holm) **a coste cero de dispositivo**, más que cualquier
salto de resolución de la rejilla. Pierde en 34 pares y en ninguno por más de 0.042: objetivo casi
quieto (`boat3`), peatón que cambia de dirección (`person18`) o caja ya perdida (`bird1_*`). Cierra
dos suposiciones de la nota 18: `ms_p50` es idéntico entre paridad y paced, y el modelo de
`sweetspot.py` ajusta k = 1.20 con RMSE 0.075 sin sesgo creciente con la resolución. `sam2_t1024`
no aparece: la puerta `upscales` lo tumbó en los 30 clips. Vale solo si el consumidor real puede
cambiarse — pregunta abierta. Sin verificación visual.

### 20. `lead`: la predicción de movimiento en la entrada no compra nada — [`notes/20-lead-prediccion-en-la-entrada.md`](notes/20-lead-prediccion-en-la-entrada.md) · 0.27 h

La misma estimación de velocidad que la nota 19 gasta en la salida (FOH), puesta ahora en la
**entrada**: `sam2_c512_lead` centra la ventana de recorte donde se predice que estará el objetivo.
**Nulo en las dos políticas de salida** — ZOH +0.001 (15/25, p=0.31), FOH −0.001 (11/25, p=0.63),
n=25 (los cinco `uav*` los veta la puerta `upscales`). Tampoco aparece el envenenamiento del banco
de memoria que se temía: déficit por tercio de clip +0.000 / +0.002 / +0.000, pendiente 3º−1º
p=0.31. El hallazgo real es por qué: el salto mediano entre respuestas es de 5.9 px contra ~230 px
de margen de recorte, y `salto` contra `delta` da rho=+0.027, p=0.90 — `bird1_1`, que mueve 62 px
por paso (26% del margen), da −0.003. **A SAM2 le da igual dónde caiga el objetivo dentro de la
ventana mientras caiga dentro.** La corrección de movimiento va en la salida, no en la entrada.
Nulo acotado a este régimen, y sin verificación visual.

### 21. Los tres clips difíciles: FOH no es la causa de ninguno — [`notes/21-los-tres-clips-dificiles.md`](notes/21-los-tres-clips-dificiles.md) · 0 h

La verificación visual de la nota 19 se cerró con el mejor caso (`truck2`, +0.258) y una pérdida
trivial (`boat3`, −0.020). Aquí se miran los tres donde FOH pierde de verdad, y los fotogramas
**contradicen la taxonomía de la nota 19 §4**: `person18` (−0.016) no es un cambio de dirección sino
un error de escala — alto pred/GT mediano **0.45**, ancho 0.91, la caja cubre solo las piernas
durante 990 fotogramas; `bird1_1` (−0.012) tiene la máscara reventada a **7.63×** el ancho del
objetivo, una banda que cruza el fotograma; `bike2` (−0.014) mantiene el tamaño correcto (1.14,
0.97) sobre un objeto a **12.94 anchuras** de distancia. Tres modos de fallo distintos con tres
arreglos distintos, donde la nota 19 veía dos. Lo que sí sobrevive: en los tres, FOH resta entre
0.012 y 0.016 sobre una base ya rota — **no causa ninguno de los fallos**, y el +0.069 agregado no
depende de ellos. Clips en `proof/foh__{person18,bird1_1,bike2}.mp4`. Sin cubrir: `person20`.
Corregida en parte por la nota 22.

### 22. `person18` no falla en SAM2: falla en `c512` — [`notes/22-person18-es-un-fallo-de-c512-no-de-sam2.md`](notes/22-person18-es-un-fallo-de-c512-no-de-sam2.md) · 0 h

El fallo de escala de la nota 21 se midió sobre `sam2_c512` y se le atribuyó a SAM2. Descompuesto
por brazo: **cinco de seis siguen a ese señor con la caja exacta 1393 fotogramas** (alto pred/GT
1.00, mIoU 0.64-0.71); solo `c512` se queda en la mitad inferior (0.238, razón 0.45). No es un
desplome progresivo — cae en la **primera respuesta propagada** (0.82 en `i=0` con la caja GT dada,
0.61 en `i=1`) y se queda en 0.58 el resto del clip: un equilibrio estable equivocado. Es una
**patología de capacidad del brazo de 512**, que es el objeto de la campaña, y no un fallo de SAM2;
llega justo cuando la nota 19 coronaba a `c512` como el mejor brazo de recorte pausado. Hipótesis
sin probar: el objetivo ocupa el 59% del alto de la ventana de 512 y el 47% de la de 640, y el
recorte apretado deja a SAM2 sin contexto. Cierra de paso `person20`, que `c512` hace bien (0.750) —
la clase "persona" no es el problema. Verificado en píxeles contra la nota 21, mismo fotograma f697.

### 23. De qué está hecho el déficit: pausar cuesta posición, no forma — [`notes/23-de-que-esta-hecho-el-deficit.md`](notes/23-de-que-esta-hecho-el-deficit.md) · 0 h

mIoU dice cuánto salió mal, no de qué. `analysis/errors.py` descompone cada fotograma en pérdida,
traslación y escala con dos contrafactuales (la caja recentrada en el GT, y una caja del tamaño del
GT en el centro de la predicha). Pareado sobre 25 clips, `c512`: pausar a 30 fps cuesta **−0.194** de
solape condicional (23/25, p=8e−06) y **−0.004** de solape recentrado (no significativo). El déficit
de pausar es casi todo **posición**: la caja entregada es la correcta con retardo. FOH recupera
+0.071 de esos y deja el recentrado invariante hasta el tercer decimal (`max |d| = 0.000`), que es la
comprobación interna de que solo mueve centros; el nulo de `lead` (nota 20) queda además explicado —
la palanca del retardo está en el consumidor, no en la entrada del modelo. Corrobora por cálculo las
tres lecturas a ojo de la nota 21 y añade una cuarta: `car12` puntúa 0.087 con solape condicional
**0.783** sobre el 11% de fotogramas en que contesta — pérdida, no caja mala. Y con `--lag`: la caja
entregada puntúa 0.485 contra el GT del fotograma que se consume y **0.811 contra el del fotograma
que miró**, con 5 de retardo; `c640` da 0.368 / **0.816** con 8. Los dos brazos producen cajas
igual de buenas y solo difieren en cuándo llegan, así que la ordenación pausada de la nota 19 es
retardo, no calidad. Sin verificación visual: no hay aquí ninguna afirmación sobre píxeles.
