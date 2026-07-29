# Tracker capacity sweep — catálogo de candidatos

Sin preregistrar. Experimento para analizar el comporamiento de la placa dado un conjunto de modelos estilo sam2. Creado: 2026-07-28T18:41Z

## Estado

Estado del dispositivo verificado el 2026-07-28T18:41Z tras matar `llama-server`: cero procesos

> 100 MB, 5.9 GB de RAM disponibles de 7.6, 126 GB de disco libre.

## Modelos a probar

1. `facebook/sam2.1-hiera-tiny`
2. `facebook/sam2.1-hiera-small`
3. `facebook/sam2.1-hiera-base-plus`
4. `facebook/sam2.1-hiera-large`
5. EdgeTAM
6. EfficientTAM-ti
7. EfficientTAM-s
8. SAMURAI (sobre tiny)
9. SAM2Long (sobre tiny)
10. `cv2.TrackerNano`
11. `cv2.TrackerVit`
12. `cv2.TrackerDaSiamRPN`
13. `cv2.TrackerGOTURN`
14. `cv2.TrackerMIL`
15. ATOM
16. DiMP-18
17. DiMP-50
18. PrDiMP-50
19. ToMP-50
20. KeepTrack
21. OSTrack-256
22. MixFormerV2-S
23. HiT-Small
24. YOLO11n + ByteTrack
25. YOLO11s + ByteTrack
26. YOLO11n + BoT-SORT
27. ByteTrack propio + detecciones oracle

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

## Smoke test (2026-07-29)

Un arm, una secuencia, para validar el rig extremo a extremo antes del sweep:
`sam2_t1024 × truck3` (535 frames, 1280×720), inicializado con la caja GT del frame 0 y
**propagación pura** después, sin re-anclar nunca.

| Precisión | p50 | p95 | fps | init | wall | RSS pico | GPU pico |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fp32 (bug) | 1449.9 ms | 1473.7 ms | 0.69 | 6766 ms | 785 s | 2717 MB | 724 MB |
| bf16 autocast | 432.6 ms | 436.5 ms | 2.31 | 5425 ms | 243 s | 2557 MB | 644 MB |

Exactitud (bf16, 535/535 frames puntuados): **IoU medio 0.779, IoU@0.25 0.944, IoU@0.5 0.908,
0 frames perdidos**.

**Lo que no funcionó, y por qué importa.** La primera versión de `Sam2Arm` no envolvía la
inferencia en `torch.autocast("cuda", bfloat16)`. `StreamCarry` lleva `@torch.inference_mode()`
pero **no** hace autocast por dentro: son los seis llamadores validados del proyecto los que lo
aportan. El arm corría en fp32 en silencio — 3.4× más lento y en una precisión que el proyecto no
despliega. No dio ningún error: solo iba lento. Por eso la precisión pasa a ser variable fija
declarada y queda registrada en el manifest.

Segundo fallo, menor: el driver capturaba el stdout del hijo, así que las líneas de progreso no
aparecían hasta que el arm terminaba. Corregido heredando stdout; todo cae en `driver.log`.

Deliverable: `proof/smoke_truck3_bf16.mp4` — GT en verde al 60% de alfa, salida del modelo en azul
claro, IoU por frame quemado en la imagen.

## Barrido de resolución sobre truck3 (run `res-truck3`, 2026-07-29)

Mismo clip, mismo checkpoint (`sam2.1-hiera-tiny`), bf16, 15 W. Solo cambia `image_size`.

| arm | p50 | p95 | fps | mIoU | IoU@0.25 | IoU@0.5 | perdidos | RSS pico | GPU pico |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `sam2_t512` | 122.7 ms | 124.4 ms | 8.15 | 0.661 | 0.966 | 0.818 | 1 | 1911 MB | 424 MB |
| `sam2_t640` | 179.9 ms | 181.9 ms | 5.56 | 0.190 | 0.264 | 0.247 | **171** | 2057 MB | 494 MB |
| `sam2_t768` | 252.0 ms | 254.3 ms | 3.97 | 0.766 | 0.953 | 0.931 | 0 | 2214 MB | 553 MB |
| `sam2_t1024` | 434.0 ms | 437.9 ms | 2.30 | 0.779 | 0.944 | 0.908 | 0 | 2650 MB | 644 MB |

Latencia y memoria escalan limpiamente con la resolución; la latencia va casi con el número de
píxeles (512 → 1024 es 4× el área y 3.5× el tiempo). La inicialización cuesta ~5.1 s en las cuatro,
o sea que la domina la carga del checkpoint, no la resolución.

**La exactitud NO es monótona y 640 se hunde.** Verificado en píxeles, no inferido del log: a
frame 110 la máscara de 640 ya está detrás del camión sobre asfalto vacío, a frame 116 se queda
vacía y no recupera en los 419 frames restantes. No es un error de forma (no lanza excepción), es
deriva de seguimiento. 512, con el objetivo aún más pequeño en espacio de modelo, aguanta.

Cuidado al leerlo: **una secuencia, un objetivo, n=1**. `truck3` tiene un blanco diminuto (~416 px
de área, ~26×16 en 1280×720), justo el régimen donde el proyecto ya despliega gating por tamaño
(EXP-1: 640 por defecto, 1024 como respaldo para objetivos pequeños o lejanos). Este resultado es
consistente con ese gating pero **no lo mide**: si 640 es frágil en general o solo aquí lo decide
el barrido de 30 secuencias, no este clip.

**Fallo encontrado y corregido.** `image_size` hay que fijarlo *en construcción* con el override de
Hydra `++model.image_size=N`, como hace el resto del proyecto. Asignar `predictor.image_size`
después de `from_pretrained` deja `sam_image_embedding_size` y el prompt encoder en el valor por
defecto del checkpoint, y cualquier tamaño distinto de 1024 muere con
`assert backbone_features.size(2) == self.sam_image_embedding_size`. Con 1024 coincidía por
casualidad, que es por qué el smoke test pasó y ocultó el bug. Tras el cambio, 1024 reproduce el
número anterior (434.0 vs 432.6 ms p50), así que las dos rutas son equivalentes en el default.

## Modo crop (activable, 2026-07-29)

Modo opcional del renderer: en vez de dar el frame completo, se recorta una ventana cuadrada de
`N` px centrada en el objetivo. La idea es desacoplar dos cosas que hasta ahora iban juntas —
resolución de entrada del modelo y tamaño aparente del objetivo. A 1024 el camión de `truck3` ocupa
~26x16 px; en un recorte de 512 ocupa lo mismo en píxeles pero el doble de fracción de la entrada.

De momento **solo geometría, sin modelo**: `analysis/render_overlay.py --seq <clip> --crop N --out
<mp4>` pinta la ventana en naranja sobre el vídeo original, con GT en verde, para ver qué encuadre
recibiría el modelo. No toca ninguna de las rutas existentes: sin `--crop` el renderer se comporta
exactamente igual que antes, y `--seq` es un modo GT-only que no necesita resultado de tracker.

Decisión de geometría: la ventana **se desliza** para quedarse dentro del frame, no se recorta.
Si se recortase, un objetivo pegado al borde cambiaría en silencio la resolución efectiva de
entrada y el número no sería comparable con el resto. Solo un frame más pequeño que `N` fuerza una
ventana menor (720 de alto lo hace para N=1024). Comprobación en
`analysis/render_overlay.py --self-check`.

Entregables: `proof/crop{512,640,720}_truck3.mp4`, 535 frames cada uno. Verificados abriendo el
frame 268 de cada render: la caja naranja está centrada en el camión y dentro del frame.

**Techo de 720 px.** Con clips de 1280x720, cualquier ventana por encima de 720 se recorta a la
altura del frame, así que 768 y 1024 producen el mismo vídeo byte a byte y solo se guarda uno
(`crop720`). Consecuencia para el experimento: en UAV123 a 720p el modo crop solo tiene tres
puntos útiles, y por encima de 720 recortar no aporta nada sobre el frame completo. La fracción
del frame que ocupa la ventana va de 28% (512) a 56% (720).

Pendiente: alimentar el recorte al tracker y medir; eso todavía no está hecho.

## Crop alimentado al modelo (run `crop-truck3`, 2026-07-29)

Arms `sam2_c<N>`: al modelo se le da **solo** una ventana de N×N alrededor del objetivo, a píxeles
nativos (`image_size == N`, sin reescalar). Mismo cómputo que el arm de frame completo al mismo
`image_size`; lo que cambia es qué se sacrifica. El arm de frame completo encoge el objetivo
(el camión de 26×16 px pasa a ~10×6 a 512); el arm de crop lo deja a 26×16 y sacrifica contexto.

La ventana persigue la **propia predicción anterior del arm**, nunca GT — en el dispositivo no
existe GT más allá del frame 0. Un frame perdido mantiene la ventana anterior.

| arm | entrada | p50 | fps | mIoU | IoU@0.25 | IoU@0.5 | perdidos |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `sam2_c512` | crop 512 nativo | 100.5 ms | 9.95 | 0.761 | 0.972 | 0.929 | 0 |
| `sam2_t512` | frame completo → 512 | 122.7 ms | 8.15 | 0.661 | 0.966 | 0.818 | 1 |
| `sam2_c640` | crop 640 nativo | 159.2 ms | 6.28 | **0.773** | **0.991** | **0.957** | 0 |
| `sam2_t640` | frame completo → 640 | 179.9 ms | 5.56 | 0.190 | 0.264 | 0.247 | 171 |
| `sam2_c704` | crop 704 nativo | 190.3 ms | 5.25 | **0.791** | 0.987 | 0.953 | 0 |
| `sam2_t1024` | frame completo → 1024 | 434.0 ms | 2.30 | 0.779 | 0.944 | 0.908 | 0 |

**El crop gana en las dos dimensiones a la vez.** `sam2_c512` supera a `sam2_t1024` en IoU@0.25 y
en IoU@0.5 con **4.3× menos latencia**. Ninguno de los tres arms de crop pierde un solo frame,
incluido 640, que en frame completo se hundía a 171 perdidos. El crop también es más rápido que su
homólogo de frame completo al mismo `image_size` (100.5 vs 122.7 ms a 512): recortar 512×512 sale
más barato que reescalar 1280×720.

Lectura honesta: esto **no** separa las dos causas posibles. El objetivo es más grande en espacio
de modelo *y* el fondo distractor desaparece, y con una secuencia no se puede decir cuál manda. Y
sigue siendo **n=1**, un solo clip, un solo objetivo, sin oclusión larga ni salida de campo.

Techo conocido, sin resolver: el banco de memoria de SAM2 ve un marco de referencia que se traslada
cada frame y nadie se lo dice. Aquí no ha hecho daño; con movimiento más rápido puede.

**704, no 720.** 720 no es una entrada legal de Hiera: el pos-embed de ventana se tesela a
`image_size/4` en bloques de 8, así que `image_size` tiene que ser múltiplo de 32 y 720 muere con
`The size of tensor a (180) must match the size of tensor b (176)`. 704 es el mayor que cabe en un
frame de 720 de alto. Sin arm de crop a 768 o 1024 en clips 720p: no caben.

Comprobación de geometría y del viaje de ida y vuelta de coordenadas, sin GPU:
`python device/trackers.py --self-check`. Verificado además en píxeles (frame 268 de `sam2_c512`,
ampliado 4×): la máscara cae sobre el camión en el frame completo, sin desfase de mapeo.

**Los vídeos enseñan la entrada real, no una reconstrucción.** `device/run_arm.py` registra en cada
fila el `(x, y, s)` exacto que el arm recortó, y el render dibuja el panel derecho a partir de ese
valor en vez de volver a derivarlo. Sobre el frame completo, el interior de la ventana se restaura
a píxeles crudos, el recuadro naranja se traza por fuera del borde y el pie va en una franja aparte
—a 704 el texto caía dentro de la ventana—, así que lo que se ve dentro del naranja es lo que vio
el modelo. `analysis/render_overlay.py` verifica en cada ejecución que las 533 ventanas del
dispositivo coinciden con su propia geometría (campo `win_checked`); la identidad de píxeles del
panel está comprobada en el frame 268 de los tres tamaños.

## Segunda secuencia: wakeboard1 (run `wakeboard1-res-crop`, 2026-07-29)

`truck3` es n=1. Segunda secuencia elegida por contraste, no por conveniencia: `wakeboard1`, 421
frames, 1280×720, objetivo de área mediana 5568 px (13× el camión) que **encoge de forma monótona**
(tendencia de escala −0.96, la más negativa de las 30), sobre agua y espuma en vez de asfalto, y
sin huecos de GT. Mismos 7 arms, mismo checkpoint `sam2.1-hiera-tiny`, bf16, 15 W.

| arm | entrada | p50 | Hz medio | mIoU | IoU@0.25 | IoU@0.5 | perdidos |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `sam2_c512` | crop 512 nativo | 101.3 ms | 9.8 | **0.823** | **1.000** | **1.000** | 0 |
| `sam2_t512` | frame completo → 512 | 122.2 ms | 8.1 | 0.679 | 0.803 | 0.795 | 36 |
| `sam2_c640` | crop 640 nativo | 159.6 ms | 6.2 | 0.817 | 0.993 | 0.993 | 0 |
| `sam2_t640` | frame completo → 640 | 181.1 ms | 5.5 | 0.701 | 0.831 | 0.829 | 0 |
| `sam2_c704` | crop 704 nativo | 190.8 ms | 5.2 | 0.814 | 0.995 | 0.988 | 0 |
| `sam2_t768` | frame completo → 768 | 252.0 ms | 4.0 | 0.647 | 0.762 | 0.732 | 0 |
| `sam2_t1024` | frame completo → 1024 | 433.7 ms | 2.3 | 0.637 | 0.739 | 0.720 | 0 |

**Se replica el patrón de `truck3`, y más marcado.** El crop más barato gana a todos los arms de
frame completo en las tres métricas de exactitud a la vez que es el más rápido: `sam2_c512` da
IoU@0.5 = 1.000 sobre los 421 frames a 9.8 Hz, contra 0.720 de `sam2_t1024` a 2.3 Hz — **4.3× más
rápido y 0.28 más de IoU@0.5**. Los tres arms de crop quedan agrupados en 0.81–0.82 mIoU: aquí la
resolución dentro del crop casi no importa, lo que importa es recortar.

**El frame completo vuelve a no ser monótono, y esta vez baja.** 512 → 640 sube, pero 768 y 1024
empeoran (0.647 y 0.637), peor que la resolución más baja que no pierde el objetivo. Dos
secuencias, dos formas distintas de romperse en frame completo (`truck3`: hundimiento aislado en
640; `wakeboard1`: degradación a partir de 640), pero la misma conclusión: subir `image_size` no
compra exactitud.

Cautela de lectura: el mIoU de `sam2_t512` (0.679) está calculado solo sobre los 385 frames en los
que devolvió caja, así que **le favorece** — los 36 frames perdidos no puntúan como 0. El resto de
arms puntúan sobre los 421.

Verificado en píxeles (frame 211, `crop_wakeboard1_c512.mid.png` y `res_wakeboard1_t512.mid.png`):
el objetivo es el wakeboarder, no la lancha, y la caja del panel de crop cae sobre él tras
deshacer el desplazamiento de la ventana. `win_checked: 419` en los tres arms de crop.

## Tercera secuencia: bird1_1, salida de campo (run `bird1_1-res-crop`, 2026-07-29)

Elegida para probar el modo de fallo que `truck3` y `wakeboard1` no tocaron: el pájaro **sale del
encuadre** y vuelve. 253 frames, hueco de GT continuo en los frames 115–173 (59 frames sin objetivo),
y luego reaparece. Mismos 7 arms.

| arm | p50 | mIoU | IoU@0.5 | perdidos | frames puntuados |
| --- | --- | --- | --- | --- | --- |
| `sam2_t512` | 122.1 ms | 0.078 | 0.006 | 82 | 171 |
| `sam2_t640` | 180.2 ms | 0.133 | 0.017 | 81 | 172 |
| `sam2_t768` | 251.7 ms | 0.108 | 0.029 | 79 | 174 |
| `sam2_t1024` | 433.0 ms | 0.192 | 0.118 | 143 | 110 |
| `sam2_c512` | 100.7 ms | 0.085 | 0.007 | 114 | 139 |
| `sam2_c640` | 159.3 ms | 0.085 | 0.012 | 82 | 171 |
| `sam2_c704` | 190.7 ms | 0.087 | 0.012 | 83 | 170 |

**Se hunden los siete.** Ningún arm pasa de 0.12 en IoU@0.5. El crop no rescata nada aquí y el
frame completo tampoco: la ventaja del crop, replicada en dos secuencias, **desaparece por
completo** en la tercera. El menos malo es `sam2_t1024`, y es inservible igual.

**El clip no llega a probar lo que se buscaba.** Todos los arms se rompen entre los frames 1 y 16,
cien frames *antes* del hueco. Verificado en píxeles (frames 0, 5, 12, 30 de `sam2_c512`): `bird1_1`
es metraje de gafas FPV con **HUD de telemetría superpuesto**, y la línea de horizonte artificial
pasa justo por encima del pájaro. La máscara se derrama por esa línea: en el frame 12 la predicción
mide 196×130 px contra un GT de 48×33. No es deriva de seguimiento ni falta de resolución, es fuga
de máscara hacia un gráfico sintético pegado al objetivo.

Lo que sí se puede leer del hueco, con esa reserva: durante los 59 frames sin objetivo **los siete
arms devuelven cero cajas** (0/59), que es el comportamiento correcto. Y ninguno recupera de verdad
al reaparecer el pájaro. En `sam2_c512` la ventana se queda congelada en (768, 208) — sin predicción
no hay dónde recentrarse — pero el pájaro reaparece **dentro** de esa ventana (frame 210) y el
modelo sigue sin devolver caja. Es decir: aquí el fallo de recuperación es del propio SAM2, no de la
geometría de la ventana. Con la fuga de máscara de por medio, esto no cierra la pregunta.

Efecto colateral útil: la comprobación `win_checked` del render reventaba con `TypeError` en un
frame perdido, porque asumía que siempre hay caja previa de la que derivar la ventana. Corregido —
en frame perdido la ventana esperada es la anterior, que es lo que hace el arm.

Pendiente si se quiere cerrar la pregunta de salida de campo: una secuencia con hueco de GT y sin
HUD superpuesto. `bird1_3` es del mismo metraje FPV, así que no sirve; los candidatos del subconjunto
con huecos son `bike2`, `car12`, `car1_3`, `group2_3`, `person19_3` y `uav1_2`.

## Barrido completo: 30 secuencias x 7 arms (run `full-sweep-30`, lanzado 2026-07-29T23:50Z)

Lo que los tres clips piloto no pueden dar: n. `truck3` y `wakeboard1` dicen que el crop gana,
`bird1_1` dice que no gana nada, y con n=3 elegidos a mano eso no es un resultado. Este run pasa
las **30 secuencias del subconjunto** por los **7 arms** que ya estaban caracterizados.

Arms: `sam2_t512`, `sam2_t640`, `sam2_t768`, `sam2_t1024` (frame completo reescalado) y
`sam2_c512`, `sam2_c640`, `sam2_c704` (crop a píxeles nativos). Todos `sam2.1-hiera-tiny`, bf16
autocast, 15 W mode 0, caja GT solo en el frame 0.

```
./jetson.py stage <las 30>
./jetson.py run --id full-sweep-30 \
  --arms sam2_t512 sam2_t640 sam2_t768 sam2_t1024 sam2_c512 sam2_c640 sam2_c704 \
  --seqs bike1 bike2 bird1_1 bird1_3 boat3 boat6 building5 car12 car16_1 car1_3 car8_2 car9 \
         group1_2 group2_3 person18 person19_3 person20 person21 person4_1 truck2 truck3 \
         uav1_2 uav2 uav3 uav5 uav7 wakeboard1 wakeboard5 wakeboard7 wakeboard8
```

210 jobs, 27276 frames por arm. **Sin vídeos**: este run mide, no ilustra. Los renders saldrán
después y solo de los casos que valga la pena mirar.

Estimaciones (a contrastar con lo real):

- Runtime: 27276 frames x 1.438 s (suma de los p50 de los 7 arms) = **10.9 h**, mas ~15 s de carga
  de modelo por job (210 jobs, ~53 min) = **~11.8 h**. El driver salta los JSON que ya existen, así
  que un corte no obliga a repetir nada.
- Disco: 30 secuencias ocupan ~2.5 GB en `~/tracker-sweep/data`; había 126 GB libres.

Reserva conocida, a comprobar en los resultados: 5 de las 30 (`uav1_2`, `uav2`, `uav3`, `uav5`,
`uav7`) son de 720x480. Ahí `crop_window` no puede dar una ventana de 512/640/704 y la recorta a
480x480, que SAM2 luego **escala hacia arriba** hasta `image_size`. En esos 5 clips los tres arms
de crop dejan de ser "píxeles nativos" y no son comparables sin más con los otros 25.

### Resultados (210/210, 2026-07-29T00:01Z -> 12:06Z UTC)

Mediana por secuencia (n=30 en todas las filas), no media sobre frames. `FP hueco` = frames donde
GT es NaN (objetivo fuera de campo) y el brazo contestó igual: suma sobre las 30, no mediana.

| arm | entrada | p50 | mIoU | IoU@0.25 | IoU@0.5 | perdidos | FP hueco |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `sam2_c512` | crop 512 | 100.9 ms | 0.679 | 0.956 | 0.861 | 0.0% | 150 |
| `sam2_c640` | crop 640 | 159.4 ms | **0.759** | 0.990 | 0.957 | 0.0% | 576 |
| `sam2_c704` | crop 704 | 190.7 ms | 0.762 | 0.988 | 0.956 | 0.0% | 259 |
| `sam2_t512` | frame 512 | 122.3 ms | 0.591 | 0.774 | 0.708 | 0.2% | 429 |
| `sam2_t640` | frame 640 | 180.6 ms | 0.678 | 0.948 | 0.833 | 0.0% | 385 |
| `sam2_t768` | frame 768 | 251.9 ms | 0.704 | 0.948 | 0.904 | 0.0% | 254 |
| `sam2_t1024` | frame 1024 | 434.0 ms | 0.752 | 0.952 | 0.917 | 0.0% | 267 |

Lecturas:

- **`sam2_c640` es el punto de operación.** Iguala a `c704` (-0.003 mIoU) por 31 ms menos, y bate a
  `t1024` (0.759 vs 0.752) a **2.7x su velocidad**. El crop compra resolución efectiva mucho más
  barato que subir `image_size`.
- El crop deja de pagar por encima de 640: 512 -> 640 son +0.080 de mIoU, 640 -> 704 son +0.003.
- Contrapartida de `c640`: la **peor** cuenta de falsos positivos en hueco (576) con 0% de frames
  perdidos, es decir, nunca dice "no está". Con la ventana pegada al objetivo siempre encuentra
  *algo*. Es justo lo que la heurística `coast` evita por diseño y lo que `edge` podría empeorar.
- Runtime real 12.1 h frente a las 11.8 h estimadas (+2.5%). Térmicas 58 -> 68 C, sin throttling.

La reserva de los 5 clips 720x480 (`uav1_2`, `uav2`, `uav3`, `uav5`, `uav7`) sigue en pie: ahí el
crop se recorta a 480x480 y SAM2 lo escala hacia arriba, así que esos brazos no son "píxeles
nativos". No se ha separado el análisis por ese eje.

## Barrido difícil: UAV123-hard, 49 secuencias x 6 arms (run `uav123-hard`, MATADO 2026-07-29)

**Este run se mató a mitad y sus resultados se borraron del dispositivo.** Se conserva la sección
porque el diseño del dataset (tercil difícil completo + controles de banda emparejados por
categoría) sigue vigente y lo reutilizan los experimentos de abajo. Motivo del corte: el análisis
de geometría de la sección "Región de búsqueda" mostró que los 6 brazos comparten el mismo defecto
—ventana de tamaño fijo, no escalada al objetivo—, así que el barrido medía seis variantes de una
sola decisión equivocada. Ninguna cifra de este run existe.


Las 30 de `full-sweep-30` se eligieron para cubrir el rango de dificultad. Este run va al otro lado:
concentra el presupuesto donde los brazos se separan. Con mIoU de 0.68-0.76 en la muestra ancha, la
mayoría de clips ya están saturados y no discriminan; el tercil difícil es donde queda señal.

**Dataset `UAV123-hard`** (`dataset.txt`, construido por `analysis/difficulty.py` sobre las 123):

- **41 clips = el tercil difícil entero.** No una muestra del tercil: el tercil completo, así que no
  hay selección que explicar.
- **4 MEDIO + 4 FACIL como control de banda**, uno por categoría y elegidos solo entre categorías
  que también aparecen en la banda difícil. Sin ese emparejamiento, "difícil vs fácil" sería en
  parte "uav vs boat" — el índice y la categoría están confundidos en UAV123 (10/10 `uav` caen en
  difícil, 0/9 `boat`).
- 49 clips, 41461 frames anotados. Categorías: uav 10, car 10, person 7, group 6, wakeboard 6,
  truck 4, bird 3, bike 3.

**Solo se corren 27 clips.** Los otros 22 ya tienen resultados en `full-sweep-30` con estos mismos
brazos y el mismo código (`code_sha256` sin cambios), y `driver.py` salta los JSON que ya existen.
Los 27 nuevos suman 21603 frames.

**6 arms, sin `sam2_t1024`.** Se descartó por coste: 434 ms de p50 sin ganar a nadie. Wilcoxon
pareado sobre las 30 secuencias de `full-sweep-30`, mIoU de `t1024` menos la del rival —
`c640` p=0.79 (delta -0.017), `c704` p=0.30 (-0.036), `t768` p=0.12 (+0.014), `t640` p=0.064
(+0.050). Contra los dos brazos de crop el signo es negativo: paga 2.3-2.7x de latencia para ir
por detrás. **Nulo acotado, no equivalencia probada** — n=30 no descarta diferencias pequeñas.

```
./jetson.py stage <los 27 nuevos>
./jetson.py run --id uav123-hard \
  --arms sam2_t512 sam2_t640 sam2_t768 sam2_c512 sam2_c640 sam2_c704 \
  --seqs uav6 car11 uav4 uav1_3 bird1_2 uav8 truck4_1 uav1_1 wakeboard9 group2_2 wakeboard6 \
         car1_2 group2_1 car13 group3_4 wakeboard3 car2 car15 person10 group3_2 truck4_2 car14 \
         person12_2 person14_1 person22 bike3 car3
```

162 jobs. Sin vídeos. Estimación de runtime: 21603 frames x 1.006 s (suma de los p50 de los 6 arms
en `full-sweep-30`) = 6.0 h, mas ~15 s de carga de modelo por job (~41 min) = **~6.7 h**.

Limitaciones declaradas antes de correr:

- **41 vs 4 vs 4 no da contraste inferencial entre bandas.** Los 8 controles sirven para mirar si el
  índice ordena, no para un test difícil-vs-fácil; con n=4 por banda ningún estadístico llega. Subir
  a ~15 por banda costaría unas 4 h más y no se ha hecho.
- La muestra está sesgada a difícil por construcción, así que **ninguna cifra de este run es una
  estimación del rendimiento en UAV123**. Es una comparación entre brazos bajo carga.
- 10 de los 49 son 720x480 (`uav1_1`, `uav1_2`, `uav1_3`, `uav2`, `uav3`, `uav4`, `uav5`, `uav6`,
  `uav7`, `uav8`) — todos de la misma categoría, la más representada en la banda difícil. Ahí el
  crop no es a píxeles nativos (ver la reserva de `full-sweep-30`), y el sesgo cae entero sobre una
  categoría.

### Resultados (TBD)

| arm | entrada | p50 | mIoU | IoU@0.25 | IoU@0.5 | perdidos | FP hueco |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | |

Estado: en curso (4.9 fps en el primer job). Siguiente paso: `./jetson.py fetch uav123-hard`,
agregación sobre los 49 (los 27 nuevos mas los 22 de `full-sweep-30`) y estratificación por banda
del índice y por categoría.

## Heurísticas de recuperación (implementadas, sin correr, 2026-07-29T14:20Z)

Dos formas de recuperar un objetivo perdido en modo crop. Cada una en su **propio brazo** para poder
atribuir cualquier diferencia; `sam2_c640` sin tocar es el control. Solo sobre 640, el mejor crop.

`sam2_c640_coast` — al perder el objetivo, la ventana sigue deslizándose en la dirección reciente en
vez de congelarse. Velocidad = **mediana** del paso de centro de los últimos 7 aciertos (una caja
mala no puede lanzar la ventana al otro lado) y solo pares de frames consecutivos (un salto sobre un
hueco es un teletransporte, no una velocidad). Mueve la **ventana**, no emite caja: una caja
extrapolada durante una oclusión real es un falso positivo garantizado y `aggregate.py` los cuenta.
Presupuesto: deja de deslizar cuando ha recorrido un ancho de ventana — sin constante que ajustar.
Ataca el fallo medido en `car12`, donde una pérdida congela la ventana y el brazo no vuelve a ver el
objetivo (450/499 frames perdidos).

`sam2_c640_edge` — si el último avistamiento estaba a menos de un tamaño-de-objetivo del borde
**real** del frame y luego se pierde, pasa a frame completo hasta reenganchar. Cerca del borde una
pérdida suele significar que el objetivo salió de campo, y la ventana está mirando justo el único
sitio donde no puede estar. Frame completo = el mismo predictor sin recortar (o sea, el
comportamiento de `sam2_t640`), no se carga un segundo modelo. El enganche ocurre un frame después
de la pérdida: el recorte se elige antes de correr el modelo, así que es lo más pronto posible.

Riesgo declarado en `edge`: el memory bank de SAM2 va lleno de features encuadradas en recorte y el
salto de encuadre es brusco. Eso es exactamente lo que mediría el experimento.

Verificación sin GPU en `device/trackers.py --self-check`: geometría del coast (incluido `coast=0`
como control de congelación) y el enganche de borde, con un `Scripted` inner que puede perder a
voluntad. `render_overlay.py` solo asserta ya los frames derivables — tras una pérdida la ventana
depende de estado que el host no ve — y en modo full encuadra el frame entero en lugar de dibujar un
recorte que el modelo no recibió.

Estado: implementadas y commiteadas, **sin lanzar**. Guardadas para más adelante.

## Auditoría del índice de dificultad (2026-07-29T14:20Z)

`analysis/index_search.py` audiciona 14 ejes candidatos solo-GT y busca subconjuntos, validando por
leave-one-out contra la mIoU mediana cross-arm de las 30 secuencias de `full-sweep-30`.

Resultado: **no hay mejora barata**. El índice actual (`size_px+motion+gap`) da rho=-0.743 sin haber
seleccionado nada. La mejor búsqueda libre llega a -0.793 en muestra pero **-0.694 en LOO**; una
familia acotada a size x motion x gap (27 combinaciones) llega a -0.777 pero **-0.734 en LOO**. Toda
selección valida peor que no seleccionar. Los tres ejes correlan 0.5-0.8 entre sí, así que un cuarto
eje no aporta grados de libertad, solo ruido.

Descartados por no aportar: `roam` (-0.288, p=0.12), `scale_range`, `scale_jitter`, `aspect_jitter`.
`gap` y `gap_max` correlan 1.00 en rango: la variante da igual. `edge_frac` sale con signo invertido
(+0.375) — más contacto con el borde es *más fácil*, porque son los objetivos grandes los que lo
tocan.

Único cambio con argumento a priori: `size_px` -> `size_min` (un tracker falla en el peor momento del
clip, no en el mediano), rho -0.743 -> -0.771, gana en 78% de remuestreos pero IC95 bootstrap
[-0.128, +0.065] cruza cero y solo mueve 1 clip de 41 del tercil difícil. **No adoptado**: dentro del
ruido y obligaría a retocar un dataset ya en cola.

Salvedad: n=30 y muestra sesgada a difícil, así que el rango restringido comprime rho. Reevaluar con
los 49 de `UAV123-hard`.

## Región de búsqueda: el defecto común a los 6 brazos (2026-07-29T16:10Z)

Hallazgo que mató `uav123-hard` y reorientó el experimento. Dos partes: qué hace SAM2 por dentro y
qué hace la literatura.

**Dónde decide SAM2.** Verificado en el código vendorizado, no inferido del paper.
`sam2.1_hiera_t.yaml:98` tiene `use_high_res_features_in_sam: true` y
`backbone_channel_list: [768, 384, 192, 96]`, así que `num_feature_levels = 3`
(`sam2_base.py:103`) y las escalas son stride 4, 8 y 16. Pero la memory attention recibe **solo**
`current_vision_feats[-1]` (`sam2_base.py:655`, `668`, `691`), o sea el nivel de **stride 16**. Los
niveles 4 y 8 (`high_res_features`) van únicamente al upsampler del mask decoder
(`sam2_base.py:745` -> `357`). Consecuencia: **la decisión de "¿sigue estando aquí el objeto?" corre
sobre una rejilla de `image_size/16`; los strides 4 y 8 solo afinan el contorno.**

Corrige una afirmación anterior de esta sesión (que la decisión más fina era de 4 px de entrada).
La máscara sale a stride 4, la semántica no.

Para el objetivo mediano de 28 px sobre 1280x720:

| brazo | rejilla de memoria | 1 celda = px originales | objetivo de 28 px |
| --- | --- | --- | --- |
| `t640` (frame completo aplastado) | 40x40 | 32 horizontal / 18 vertical | **subcelular en anchura** |
| `c640` (crop nativo) | 40x40 | 16 x 16 | ~1.75 celdas |
| `t1024` | 64x64 | 20 x 11 | ~1.4 celdas |

Esto explica el hueco `t640` vs `c640` (0.678 vs 0.759) mejor que "capacidad": a `t640` el objetivo
no llega a una celda del mecanismo que decide si sigue ahí.

**Qué hace la literatura y nosotros no.** El *factor de búsqueda* es convención universal desde
SiamFC (2016: plantilla 127 px, `context_amount 0.5`, búsqueda 255 px = 2x, relleno con la **media
por canal** en los bordes del frame — ni cero ni replicado). OSTrack (ECCV'22) usa factor 2 para la
plantilla y **6** para la búsqueda, con el lado calculado como `sqrt(w*h)` de la caja. LoRAT
(ECCV'24) usa 4 a 224 de entrada y 5 a 378. La ablación de OSTrack: **factor 4 -> 6 da +6.1% AUC
(53.7 -> 59.8), y el 7 regresa** porque el objetivo ocupa relativamente menos del recorte.

Nuestro `c640` es un cuadrado de 640 px **fijo, independiente del tamaño del objetivo**. Es un frame
más pequeño, no una región de búsqueda. Adoptar una ventana escalada al objetivo, **a igual
cómputo** (misma entrada 640x640, mismos ~159 ms):

| diseño | ventana para objetivo de 28 px | objetivo en espacio del modelo | celdas de stride 16 |
| --- | --- | --- | --- |
| `c640` actual | 640 fijo | 28 px | 1.75 |
| factor 5 | 140 px | 128 px | **8** |
| factor 6 | 168 px | 107 px | **6.7** |

Interpolar una ventana de 140 px hasta 640 no añade información, pero cambia la razón
objetivo/stride, que es lo que determina si la memory attention puede ver el objetivo. La regla
por-eje "no ampliar" del autor es correcta para frames completos y **no** aplica a regiones de
búsqueda; autorizado el 2026-07-29 tras comprobar que la literatura coincide.

`image_size` se fija en construcción (`hydra_overrides_extra=["++model.image_size=N"]`) y no se puede
cambiar a mitad de stream, así que cualquier fallback crop<->full debe mantener una sola N y mover
solo la ventana. Eso sale gratis.

Ningún paper estratifica la curva de factor de búsqueda por tamaño ni por velocidad del objetivo.
Hueco confirmado.

## Revisión de literatura: tracking en edge y contra-UAS (2026-07-29T16:40Z)

Seis agentes sobre literatura reciente, más tres de verificación dirigida (código, pesos, cifras
exactas). Se documenta porque **descarta candidatos que estaban en la lista de "Modelos a probar"**
de arriba y porque las razones son reutilizables.

### Lo que descarta, con motivo

| candidato | veredicto | motivo verificado |
| --- | --- | --- |
| **FocusTrack** (TGRS 2025, arXiv 2504.13604) | **fuera** | Entrenado solo en AntiUAV410 (**térmico IR**); no hay variante RGB ni una sola cifra en benchmark de luz visible. Y los 143/44 FPS son en **RTX 3090**, no en edge: ViT-B con búsqueda 256. Muerto por dominio y por coste. |
| **SRRT** (arXiv 2207.04438) | **fuera** | "Code and models will be released" — nunca se liberó. Sin repo. |
| **Detector-Augmented SAMURAI** (WACVW 2026, arXiv 2601.04798) | **fuera como modelo** | Sin código público. Su detector **YOLO-FEDER FusionNet** tampoco tiene repo ni pesos, y el dataset con el que lo preentrenan (SynDroneVision) sigue sin enlace vivo. |
| **LAF-YOLOv10** (arXiv 2602.13378) | **fuera** | No es un detector anti-dron: entrena en **VisDrone-DET2019 y UAVDT**, o sea cámara *montada en* un dron detectando coches y peatones en el suelo. Sin pesos ni código. Sus 24.3 FPS en Orin Nano / 65.4 en AGX Orin (Tabla 8, FP16, TensorRT 8.6) son reales pero de otra tarea. |
| **DAM4SAM** (IJCV 2026, arXiv 2509.13864) | **fuera por licencia** | Es el **único** tracker basado en SAM2 que reporta UAV123 (Tabla 11: SAM2.1 68.8 AUC -> DAM4SAM 70.9). Pero el repo no declara licencia (`"license": null`, sin fichero LICENSE) = todos los derechos reservados por defecto. Y es Hiera-L a 1024: ~2.8 s/frame estimados en esta placa, ~88 h para UAV123 completo. |
| **SAM2Long** | **fuera** | Ramificación en árbol de memoria; el presupuesto de 15 W no lo aguanta. |
| **EdgeTAM** | **fuera por ahora** | Sin puerto medido a Jetson/TensorRT. 16 FPS en iPhone 15 Pro Max, que no traduce. Días de ingeniería antes de la primera cifra. |
| **SAMURAI / HiM2SAM** | **vivos, pero sin ancla** | Apache-2.0 los dos, plug-ins training-free sobre los pesos SAM2.1 que ya tenemos. Pero **ninguno reporta UAV123** (LaSOT, LaSOT-ext, GOT-10k, VOT-LT). No hay contra qué validarlos en nuestro dataset. HiM2SAM además necesita CoTracker3 (público, vía `torch.hub`). |

### Lo que la literatura sí resuelve

- **El recorte cuadrado no es un capricho de SAM2.** La entrada cuadrada es casi universal (position
  embeddings de ViT), pero la *ruta* a cuadrado difiere: SAM1 y SAM2-imagen hacen letterbox
  (redimensionar lado largo + padding); YOLO hace letterbox; los trackers siamés/transformer recortan
  un cuadrado alrededor del objetivo con relleno de color medio. **Solo el video predictor de SAM2
  aplasta anisotrópicamente.** Nuestra familia `t*` es la rara.
- **El híbrido propuesto por el autor (búsqueda local + reenganche global al perder) es el diseño
  dominante** en long-term tracking: GlobalTrack, Siam R-CNN, LTMU, SPLT, y todos los ganadores de
  Anti-UAV tienen rama explícita de re-detección. Tres correcciones que impone la literatura:
  (a) el disparo debe ser **adaptativo**, no umbral fijo — TCDI mide desviación contra una media
  móvil exponencial de calidad por secuencia, y el campo señala explícitamente que los umbrales fijos
  no generalizan; (b) la re-detección debe ser barata y separada, no una segunda pasada a coste
  completo; (c) **pesar la apariencia reciente muy por encima de la plantilla original** — SiamSTA,
  ganador del 1º y 2º Anti-UAV, usa 0.9 reciente / 0.1 original.
- **Política de disparo completamente especificada** en el paper WACVW, o sea reimplementable sin su
  código: confianza del detector > 0.75, **o** CIoU(tracker, detector) > 0.7, **o** consistencia de
  trayectoria (IoU > 0.8 o distancia de centros normalizada < 0.05); más un **suelo duro de prompting
  forzado cada 30 frames** (~1 s a 30 fps) condicionado a que haya detección fiable.
- **Nuestro régimen es IRSTD, no COCO-small.** 28 px de mediana (p10 11, p90 41) cae en la banda
  "tiny/small" de AI-TOD y coincide con la media de 23 px de Anti-MUAV15. El benchmark UAV-Anti-UAV
  (1810 secuencias, ~1.05M frames, "small" = <22x22 px) mide 50 trackers con mACC media 0.272 y mejor
  0.44, frente a >0.6 típico en LaSOT.
- **Protocolos que premian abstenerse**, y que deberíamos usar porque el mIoU no mide lo que importa
  aquí: **VOT-LT F-score** (una caja confiada durante una ausencia puntúa IoU 0 pero sigue contando
  en el denominador de precisión), **OxUvA MaxGM** = `max_p sqrt((1-p)*TPR*((1-p)*TNR+p))`, y las
  **"3 R's" de TLP** (borrar un tramo intermedio de la secuencia y medir: si recupera en 200 frames,
  si recupera rápido en 30 frames ~1 s, y frames medios hasta recuperar).
- **La contaminación del memory bank de SAM2 está documentada** (SAM2Long, HiM2SAM, SAM2Plus): la
  cola FIFO (<=7 recientes + los frames con prompt) **no tiene mecanismo de corrección** — una máscara
  mala escrita una vez "es incorregible y desviará la segmentación posterior".

### Huecos confirmados en la literatura (contenido de tesis, no fallos de búsqueda)

- Ningún tracker SOT medido en **Orin Nano**. Todas las cifras "edge" de 55-61 FPS son **AGX
  Xavier** (HiT-Base 61, MixFormerV2-S 55) o **AGX Orin**. Factor de conversión medido, del propio
  LAF-YOLOv10 con el mismo modelo en ambas placas: **2.7x** AGX Orin -> Orin Nano. Consistente con el
  ancho de banda de memoria (68 GB/s frente a 137 de AGX Xavier y 205 de AGX Orin). Derating
  **estimado** de HiT-Base a esta placa: ~20-25 FPS.
- No existe **curva resolución-precisión-latencia** publicada para ningún tracker en Orin Nano.
- Nadie cuantiza el bloque de memory attention de SAM2.
- Ningún participante de los retos Anti-UAV ha usado SAM2 (lo dice explícitamente el survey
  CVPR2025W).
- Sin cuantificación específica de tracking de la penalización por destruir el aspect ratio en
  objetivos diminutos.
- Sin penalización medida por **cambiar la ventana espacial a mitad de stream** — que es justo el
  riesgo del brazo `edge` ya implementado.
- **Aviso INT8:** dos regresiones documentadas en Jetson — ViT-S+DPT vía TensorRT Model Optimizer
  INT8 es **2.7x más lento** en Orin Nano (foro NVIDIA), y DEIMv2 en Orin NX baja de 580 QPS FP16 a
  380 QPS INT8. bf16 es la opción segura.

## Decisión: AsymTrack-B como candidato principal (2026-07-29T17:05Z)

El autor levantó dos restricciones el 2026-07-29: (1) **la salida solo necesita ser dónde está el
objeto a lo largo del tiempo**, sin máscara y sin importar el método; (2) el coste y lo ya descargado
son irrelevantes. Eso desbloquea la familia de trackers de caja ligeros, que encajan tal cual en el
contrato `arm` existente (`step()` devuelve `(box, contours)` con `contours` opcional).

Nota de diseño que esto expone: el rig llama a `mask_to_box` y tira la máscara. **Pagamos
segmentación y consumimos detección.**

### Cifras en UAV123, que es lo que tenemos montado

| tracker | UAV123 AUC | params | plantilla/búsqueda | factor | licencia |
| --- | --- | --- | --- | --- | --- |
| **AsymTrack-B** (AAAI 2025, arXiv 2503.00516) | **66.5** | **3.36M** | 192 / 384 | no reportado | **MIT** |
| HiT-Base (ICCV 2023, arXiv 2308.06904) | 65.6 | 42.1M | 128 / 256 | 4x | — |
| MixFormerV2-S (NeurIPS 2023) | 65.4 | 16.2M | 112 / 224 | no reportado | — |
| SMAT (WACV 2024, arXiv 2309.03979) | 64.3 | 3.8M | 128 / 256 | 4x | — |
| SAM2.1 Hiera-L (según DAM4SAM Tabla 11) | 68.8 | ~224M | — / 1024 | sin factor | Apache-2.0 |

AsymTrack-T 64.6 y AsymTrack-S 65.6, ambos 128/256. La cifra de MixFormerV2-S tiene desacuerdo entre
papers (65.4 propio, 63.4 citado por SMAT, 65.8 citado por AsymTrack) — marcado, no usado.

Lee la primera fila y la última juntas: **3.36M parámetros contra ~224M, 66x, por 2.3 puntos de
AUC** — y el pequeño cabe en esta placa.

### Por qué AsymTrack-B y no otro

1. **Tiene el número exacto para validar el arnés.** 66.5 AUC en UAV123. Es el peldaño que con SAM2
   era inalcanzable: SAMURAI y HiM2SAM no reportan UAV123, y el único que sí (DAM4SAM) pide 88 h y no
   tiene licencia.
2. **Ya hace nativamente lo que falta.** Recorte escalado al objetivo, entrada 384, stride 16 =
   rejilla 24x24 sobre la región de búsqueda: ~5 celdas de decisión para un objetivo de 28 px, frente
   a **1.75** de `c640`.
3. **Barato.** 3.36M parámetros; UAV123 completo cabe en horas.
4. **MIT**, verificado en el fichero LICENSE del repo. Reutilizable en la tesis sin permisos.
5. Mismo autor principal que SRRT (Jiawen Zhu), el paper de regulación adaptativa de región de
   búsqueda cuyo código nunca salió.

Riesgo declarado: **PyTracking/LTR en aarch64**. AsymTrack, HiT y SMAT comparten linaje y superficie
de instalación. Plan B si ninguno instala: MixFormerV2, que es el outlier sin dependencia declarada
de PyTracking.

### Estado de instalación (verificado en dispositivo, 2026-07-29T17:05Z)

Riesgo de aarch64 **resuelto, mejor de lo estimado**:

- `find` de `setup.py` / `*.cu` / `*.cpp` en el repo: **vacío**. Sin extensiones CUDA que compilar.
- Venv **separado** `~/tracker-sweep/.venv-asym` para no contaminar el entorno que produjo los
  resultados ya commiteados (los manifests registran su propio `freeze`).
- `install_asymtrack.sh` pinea `torch==1.12.1+cu113`, que **no se usa**: en esta placa el único torch
  CUDA aarch64 viene de `pypi.jetson-ai-lab.io/jp6/cu126`. Instalado torch 2.8.0 + torchvision 0.23.0
  desde ahí, igual que el venv de SAM2. (El script tiene además una errata, `pip install numy=1.24`.)
- `timm==0.9.2` importa contra torch 2.8.0 sin queja.
- **Trampa numpy:** las deps arrastran numpy 2.2.6 y el wheel de torch de jetson-ai-lab está
  compilado contra numpy 1.x — `UserWarning: Failed to initialize NumPy`, cualquier `.numpy()` de un
  tensor rompe. Fijado a `numpy==1.26.4`, el mismo del venv de SAM2. Verificado después: tensor CUDA
  384x384 en "Orin" y roundtrip a numpy correctos.

### Dos tropiezos de integración (2026-07-29T19:20Z)

Ninguno es del tracker; los dos cuestan tiempo y se documentan para no repetirlos.

1. **`jetson.py sync` borró el clon.** El repo se había clonado en `~/tracker-sweep/code/ext/`, y
   `sync` empuja `device/` con `rsync --delete` sobre `code/`: la siguiente sincronización de código
   se llevó por delante el checkout y los pesos. Reubicado a `~/tracker-sweep/ext/AsymTrack`, fuera
   del árbol que `sync` gobierna, con el motivo escrito en el propio `trackers.py`. El venv
   `.venv-asym` ya vivía fuera y sobrevivió.
2. **Cuota de Google Drive.** Los pesos están en una carpeta de Drive que mezcla los tres
   checkpoints con los `raw_results` completos (miles de `.txt` por secuencia de LaSOT). Un
   `gdown --folder` los recorre todos y agota la cuota pública de la carpeta:
   `Cannot retrieve the public link of the file ... or have had many accesses`, que bloquea también
   la descarga por id individual. Lo correcto es sacar los ids del listado
   (`AsymTrack_ep0500.pth.tar` base = `1hHOzWsnT1n1FQESwUk-vttkrpqVgpBHB`, backbone
   `efficientMod/xxs/model_best.pth.tar` = `1MQt0A-XqFw2vY7oC1PvWoYFnSbFVCkf7`) y bajar solo esos
   dos. Con la cuota ya agotada queda un reintento en `~/tracker-sweep/ext/fetch_weights.sh`
   (bucle cada 30 min, log en `fetch_weights.log`). **Sin pesos no hay humo, así que `asym-repro`
   está bloqueado en este punto**, no por el código.

### Humo parcial sin pesos (2026-07-29T19:35Z)

Los pesos faltan pero la arquitectura no depende de ellos para construirse ni para cronometrarse:
las formas son las mismas con pesos aleatorios. Verificado en el Jetson, venv `.venv-asym`:

- `build_asymtrack(cfg)` + `switch_to_deploy()` + `.cuda()` construye sin error. **3.55 M
  parámetros** (el paper dice 3.36 M; la diferencia cabe en qué cuenta cada uno, no se ha
  investigado).
- Pasada completa `forward_backbone` + `forward_head` sobre un frame 1280x720 sintético:
  `pred_boxes` sale `[1, 1, 4]`, `resize_factor` 3.92 para una caja de 30x20 (ventana de
  4.0*sqrt(600) = 98 px reescalada a 384).
- **Latencia p50 = 26.7 ms, 37.5 FPS**, fp32, 35 iteraciones, 5 de calentamiento descartadas,
  incluyendo el `sample_target` y la vuelta del box a CPU. **Estimación, no medida de arnés**: es
  un bucle sintético con pesos aleatorios y sin decodificar JPEG, y no se ha reconfirmado el modo
  de potencia en esa ventana. Para comparar: `sam2_c640` marca 159.4 ms p50 en el barrido real,
  o sea **~6x**. Si sobrevive a la medición con el arnés, es el primer número de un tracker SOT
  sobre Orin Nano que hemos podido encontrar publicado o no (ver "huecos confirmados").

Deriva de aquí la estimación de runtime de `asym-repro`: ~113 k frames a ~27 ms es ~50 min de
cómputo de tracker, más decodificación, bastante por debajo de la horquilla 1.5-2.5 h que se
preregistró.

### Cambios de arnés que trae el candidato

- `analysis/aggregate.py` calcula ya el **AUC de curva de éxito** (21 umbrales, 0 a 1), la métrica
  del paper. Es la única columna en **media** sobre secuencias en vez de mediana: así la reportan
  los toolkits OPE y es la única forma de que nuestro número sea comparable con uno publicado.
  Sanidad sobre `full-sweep-30`: `c704` 65.7, `c640` 64.0, `t512` 51.0 — mismo orden que mIoU,
  rango plausible. (Esos 30 clips no son UAV123 completo, así que no se comparan con 66.5.)
- `device/driver.py` elige intérprete **por brazo** (`venv_python` en el registro, por defecto
  `sys.executable`) y escribe un `freeze` por intérprete usado. Un run que mezcle SAM2 y AsymTrack
  cruza dos venvs, y "qué paquetes produjeron este número" tiene que poder contestarse para ambos.
- Brazo `asym_b` en `device/trackers.py`: envuelve su propio `lib/test/tracker/AsymTrack.py`,
  convierte xyxy<->xywh y BGR<->RGB, y `contours` es siempre `None` (cabeza `CORNER`,
  `PREDICT_MASK: false`). Construye `TrackerParams` a mano en vez de llamar a su `parameters()`,
  que exige rellenar dos `local.py` con rutas de datasets ajenas. Registra `win`, la ventana
  cuadrada de búsqueda de cada frame, para poder dibujarla en los overlays.

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

## Experimento completo: `search-window` (preregistrado 2026-07-29T17:05Z)

Solo se lanza **si `asym-repro` valida**. Cuatro brazos sobre los **mismos 37 clips del tercil
difícil**, pareados clip a clip (mismos frames, misma caja de init), Wilcoxon pareado.

| brazo | qué es | qué aísla |
| --- | --- | --- |
| `sam2_c640` | control, lo desplegado hoy | línea base sin tocar |
| `sam2_f5` | SAM2 con ventana `5 * sqrt(w*h)` de la última caja, relleno de color medio en los bordes, misma entrada 640x640 | **la geometría sola**: mismo modelo, mismo cómputo, mismos ~159 ms; la única diferencia es que la ventana escala con el objetivo |
| `asym_b` | AsymTrack-B tal cual | **el modelo solo**: 3.36M contra ~224M en régimen de 11-41 px |
| `asym_b_redet` | AsymTrack-B + re-detección global **agnóstica de clase**, disparada por confianza con suelo duro de 30 frames | **el reenganche solo** |

**Por qué la re-detección es agnóstica de clase y no un detector de drones.** UAV123 mezcla: los
`uav*` y `bird*` son objetivos aéreos, pero `car9`, `person21`, `truck3`, `group2_3`, `wakeboard5` y
`bike1` son objetos de suelo filmados desde un dron. Un YOLO entrenado en Drone-vs-Bird no ve un
wakeboard, así que un detector específico de dron sería inútil en buena parte del tercil y obligaría
a restringir el n por debajo de la regla de n>=25. La alternativa elegida es la tercera etapa de
SiamSTA: **búsqueda global por apariencia sobre la plantilla acumulada**, ponderando 0.9 apariencia
reciente / 0.1 plantilla original. No necesita pesos de nadie, no necesita clase, y conserva la
estructura de disparo del paper WACVW quitándole la única pieza que no se puede descargar.

Pesos abiertos de detectores de dron localizados, por si el eje se retoma restringido al subconjunto
aéreo: `doguilmak/Drone-Detection-YOLOv11x` (MIT, `best.pt`, mAP@50 0.905, ~8.9 ms/img) y
`FardadDadboud/Drone_YOLOv5_Detector` (GPL-3.0, Drone-vs-Bird + Det-Fly). Ambos solo-dron.

**Métricas.** Además de mIoU y AUC, las que miden lo que importa en contra-UAS y que el mIoU no ve:

- **tasa de falsos negativos** (frames con objetivo presente y sin caja emitida),
- **falsos positivos en hueco** (caja emitida con GT ausente), ya instrumentado en `aggregate.py`,
- **"3 R's" de TLP**: borrar un tramo intermedio y medir si recupera en 200 frames, si recupera en 30
  (~1 s), y frames medios hasta recuperar.

**Sale gratis, y no existe publicado:** la curva P/R de `object_score_logits` como detector de
pérdida. Ya está instrumentado (`device/stream_carry.py:92` guarda `last_score`, asignado en la línea
142 desde `current_out["object_score_logits"]`). SAM2 lo entrena con cross-entropy y pesos de pérdida
máscara:IoU:oclusión:otros = 20:1:1:1, supervisado incluso en frames sin máscara GT, pero **no hay
umbral publicado ni precisión/recall publicados como detector de pérdida**.

**Estimaciones (marcadas como estimaciones):** tercil difícil = 37 clips, 30001 frames. SAM2 @640 =
**1.33 h/brazo** (medido: p50 159 ms). AsymTrack-B = **0.25-0.5 h/brazo** (estimado). Total de los 4
brazos: **3.2-3.7 h**.

**Limitaciones declaradas antes de correr:**

- `asym_b` frente a `sam2_c640` confunde dos cosas: modelo y geometría de ventana. Por eso está
  `sam2_f5` en medio — es el único brazo que cambia la geometría manteniendo el modelo. Sin él, un
  resultado a favor de AsymTrack no se podría atribuir.
- La muestra está sesgada a difícil por construcción: **ninguna cifra de este run estima el
  rendimiento en UAV123**. Es comparación entre brazos bajo carga. La estimación poblacional sale de
  `asym-repro`.
- 10 de los clips son 720x480 y todos de la categoría `uav`, la más representada en la banda difícil.
  El sesgo de resolución cae entero sobre una categoría.
- El factor 5 se fija a priori desde la ablación de OSTrack (4->6 gana, 7 regresa). **No se barre el
  factor en este run**: barrer f3/f4/f5/f6 multiplicaría por 4 el coste del brazo SAM2 y añadiría
  comparaciones múltiples a una familia que ya tiene 4 brazos. Si `sam2_f5` gana, el barrido del
  factor es el run siguiente y ahí sí con la curva completa.
- Sigue sin medirse la penalización por cambiar la ventana a mitad de stream, que afecta a
  `asym_b_redet`. Es el riesgo declarado, y también lo que el brazo mediría.
