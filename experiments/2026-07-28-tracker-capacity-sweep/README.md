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

---

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

## Tercer peldaño de la escalera: `sam2_f5` (run `f5-30`, 2026-07-30T06:40Z)

Ventana `5*sqrt(w*h)` escalada al objeto, rellenada, misma entrada 640x640. Sobre las mismas 25:

| brazo | AUC | mIoU | @0.25 | @0.5 | FP en hueco | p50 ms |
| --- | --- | --- | --- | --- | --- | --- |
| `sam2_c640` | **65.0** | 0.785 | — | 0.983 | 542 | 159.3 |
| `sam2_f5` | 57.9 | 0.759 | **0.999** | **0.987** | **59** | 159.6 |

Menos 7 puntos de AUC, pero @0.25, @0.5 y falsos positivos en hueco son los mejores de todo el
barrido. **Bimodal**, no degradado uniformemente:

- gana: `wakeboard5` 0.674 vs 0.525, `building5` 0.821 vs 0.728, `truck2` 0.838 vs 0.789,
  `bike2` 0.176 vs 0.120, `car1_3` 0.632 vs 0.558.
- se hunde: `car12` 0.028 vs 0.671, `car9` 0.355 vs 0.847, `person18` 0.268 vs 0.766,
  `person19_3` 0.193 vs 0.752, `bird1_3` 0.013 vs 0.094.

**Mecanismo: colapso de escala con realimentación positiva.** La ventana la dimensiona la caja que
produce el propio brazo, así que una caja que encoge encoge la ventana, que quita contexto, que
encoge más la caja. Sin suelo. Medido: `car9` 647 px -> 52 px, `person19_3` 173 -> 32, `wakeboard5`
448 -> 18, `car12` arranca en 97 y no se recupera. Un lado de 52 px entrando en 640 son 12x de
interpolación — justo lo que la compuerta `upscales` no filtra para los brazos de factor.

Verificación visual (`raw/f5-30/f5_collapse.png`, `car9`): frame 301 ventana 274 px IoU 0.77; frame
701 226 px IoU 0.88; frame 801 la ventana ya son 52 px **enganchada al pórtico de señalización** y en
`LOST`; frame 1001 sigue en el pórtico con el coche (verde) a 200 px. Terminal: con 52 px de ventana
no puede volver a ver el coche.

### `sam2_f5_floor` (run `f5floor`, 2026-07-30T09:05Z)

Misma geometría con el lado de la ventana **acotado por abajo a su valor del frame 0**. Aísla el
colapso de la geometría escalada. Prohíbe que un objeto que se aleja de verdad encoja su ventana, y
eso solo es asumible porque `c640` ya demuestra que una ventana de más no cuesta nada aquí.

**Estimación a priori** (escrita antes del resultado): si el colapso lo explica todo, `f5_floor` queda
**por encima de 65.0**; si queda **entre 58 y 63**, la geometría escalada al objeto tiene además un
problema propio.

*Nota de ejecución: el run se lanzó por primera vez a las 06:40Z y no llegó a arrancar — el
lanzamiento heredó el cwd `device/` de un self-check anterior y `../../.venv-ft/bin/python` no
resolvió. La Jetson estuvo parada ~1.5 h. Relanzado desde la raíz.*

**Resultado: AUC 62.0** — dentro de la banda 58-63 de la estimación a priori, que decía
*"la geometría escalada al objeto tiene además un problema propio"*. El suelo recupera 4.1 de los
7.1 puntos perdidos; quedan 3 sin explicar por el colapso.

| brazo | p50 ms | mIoU | @0.25 | @0.5 | FP en hueco | AUC |
| --- | --- | --- | --- | --- | --- | --- |
| `sam2_c640` | 159.3 | 0.785 | 0.998 | 0.983 | 542 | **65.0** |
| `sam2_c640_pad` | 159.4 | 0.787 | 0.998 | 0.983 | 482 | 64.8 |
| `sam2_c704` | 190.7 | 0.785 | 0.997 | 0.981 | 228 | 66.9 |
| `sam2_f5` | 159.6 | 0.759 | **0.999** | **0.987** | **59** | 57.9 |
| `sam2_f5_floor` | 160.6 | 0.783 | 0.998 | 0.983 | 115 | 62.0 |

El suelo funciona mecánicamente — el lado mínimo iguala exactamente el del frame 0 en las 25
secuencias. Y donde el colapso era la causa, la recuperación es completa:

| seq | lado f5 (frame0 -> min) | lado floor | mIoU `f5` | mIoU `floor` | mIoU `c640` |
| --- | --- | --- | --- | --- | --- |
| `car9` | 647 -> 52 | 647 | 0.355 | **0.816** | 0.847 |
| `person19_3` | 173 -> 32 | 173 | 0.193 | **0.777** | 0.752 |
| `wakeboard5` | 448 -> 18 | 448 | 0.674 | — | 0.525 |
| `bike2` | — | — | 0.176 | **0.246** | 0.120 |
| `bird1_3` | — | — | 0.013 | 0.135 | 0.094 |

**Dos clips no se recuperan, por dos motivos distintos:**

- `car12` 0.028 -> 0.027. El suelo es 97 px porque el objeto ya es pequeño en el frame 0; 97 px
  entrando en 640 son 6.6x de interpolación desde el primer frame. Aquí el colapso nunca fue el
  problema: **la geometría escalada al objeto le da al objetivo pequeño una ventana pequeña para
  siempre**, y el suelo no puede arreglar lo que hereda.
- `person18` 0.268 -> 0.282, con el suelo en **787 px** — ventana más grande que la de `c640`, y aun
  así 0.282 contra 0.766. No es colapso ni ventana pequeña. **Sin explicar**: pendiente de mirar el
  overlay antes de afirmar mecanismo.

Lo que sí queda establecido: a igualdad de latencia (160.6 vs 159.3 ms) y de mIoU (0.783 vs 0.785),
`f5_floor` emite **115 falsos positivos en hueco contra 542** del incumbente, 4.7x menos. La
geometría escalada con suelo no mejora la AUC, pero cambia el perfil de error hacia callarse cuando
no hay objeto.

## DAM4SAM: candidato principal (runs `dam-smoke3` y `dam-5x3`, 2026-07-30T12:55Z)

DAM4SAM (Videnovic et al., *Distractor-Aware Memory for Visual Object Tracking with SAM2*, CVPR
2025 / IJCV 2026) es SAM2.1 con una **memoria que resuelve distractores** (DRM): mismo checkpoint
`sam2.1_hiera_tiny`, cero entrenamiento, solo una política distinta de qué frames entran en la
memoria y con qué peso. Es decir, **no es un modelo nuevo: es una política de memoria** montada
sobre el mismo peso que ya lleva desplegado toda la tesis.

### Instalación (verificada en dispositivo)

- Clon `~/trackers/DAM4SAM` (rama `master`). **No se instala con pip**: el repo lleva su propio
  fork de `sam2` que chocaría con el `sam2 1.1.0` del venv principal. Se alcanza por `sys.path`,
  igual que AsymTrack.
- Venv propio `~/tracker-sweep/.venv-dam4sam` (uv, py3.10): `torch==2.8.0`, `torchvision==0.23.0`,
  `numpy==1.26.4`, `hydra-core==1.3.3`, `iopath`, `omegaconf`, `opencv-python-headless`, `pillow`,
  `tqdm`, y **`vot-toolkit==0.7.1`** (`--index-strategy unsafe-best-match --extra-index-url
  https://pypi.jetson-ai-lab.io/jp6/cu126`).
- El brazo llega al intérprete correcto por `venv_python` en el registro; `driver.py` ya lo soporta,
  no hizo falta tocar el arnés.

**Tropiezo 1 — `vot-toolkit`.** uv resolvió `0.8.1`, que ya no exporta `RegionType`:
`ImportError: cannot import name 'RegionType' from 'vot.region'`. El freeze del repo (inusable como
requirements) pinea `0.7.1`; con ese pin exacto el modelo construye.

**Tropiezo 2 — la compuerta `upscales`.** El wrapper fija la entrada a 1024, y `1024*1024 >
1280*720`, así que la compuerta vetaba **todos** los clips de UAV123 antes de correr nada. Se
registra con `image_size=None`, el mismo trato que los brazos AsymTrack: la compuerta existe para
mantener honesta *nuestra* escalera de resolución, no para prohibir un modelo de entrada fija.

**El tamaño de entrada no era una perilla y se ha abierto.** `dam4sam_tracker.py` fija
`self.input_image_size = 1024` y construye el predictor sin overrides. Los dos extremos tienen que
moverse juntos — `input_image_size` (lo que redimensiona `_prepare_image`) y `model.image_size` (lo
que fija `sam_image_embedding_size`) — o SAM2 muere en
`assert backbone_features.size(2) == self.sam_image_embedding_size`. Se parchea
`build_sam2_video_predictor` dentro del namespace del wrapper para inyectar
`++model.image_size=N`, se restaura en un `finally`, y se comprueba con un assert. Resultó importar:
640 corre a 198 ms contra 431 ms.

### Humo con verificación visual (`raw/dam-smoke3/`, bike2 @1024)

p50 431.0 ms, mIoU 0.023, 66 frames perdidos, init 7.5 s, pico GPU 1026 MB. Overlay de 3 frames
abierto: frame 0 la predicción sobre el GT, frame 60 ya sobre **otro peatón** a la izquierda, frame
300 sigue equivocada. Deriva por distractor real, no fontanería.

### 5 clips x 3 resoluciones (`raw/dam-5x3/`, 15 jobs, todos completos)

Clips: `bike2`, `car12`, `group2_3`, `bird1_3`, `truck3`. Barrido de 30 clips **cancelado a
propósito**: a 431 ms/frame @1024 no es barrible; se cambió por 5 clips interesantes y se abrió la
resolución. Los incumbentes se reagregaron **sobre esos mismos 5 clips**, no sobre las 25.

| brazo | p50 ms | mIoU | @0.25 | @0.5 | perdidos | FP en hueco | AUC | pico GPU |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `sam2_c640_pad` (incumbente) | 159.5 | 0.666 | 0.832 | 0.746 | 11.4% | 449 | 41.9 | — |
| `sam2_f5_floor` | 158.6 | 0.246 | 0.475 | 0.255 | 54.6% | 57 | 33.7 | — |
| `dam4sam_t512` | 146.8 | 0.116 | 0.076 | 0.033 | 40.2% | 190 | 24.9 | 422-495 MB |
| `dam4sam_t640` | 197.9 | 0.665 | **0.919** | **0.815** | **5.8%** | 229 | 39.0 | 523-644 MB |
| `dam4sam_t1024` | 431.3 | **0.709** | **0.937** | **0.901** | 11.9% | 164 | **43.1** | 983-1296 MB |

mIoU por secuencia (`c640_pad` / `f5_floor` / 512 / 640 / 1024):

| seq | c640_pad | f5_floor | dam512 | dam640 | dam1024 |
| --- | --- | --- | --- | --- | --- |
| `bike2` | 0.122 | 0.246 | 0.000 | 0.023 | 0.023 |
| `bird1_3` | 0.237 | 0.135 | 0.116 | 0.133 | 0.276 |
| `car12` | 0.670 | 0.027 | 0.024 | 0.690 | 0.744 |
| `group2_3` | 0.666 | 0.722 | 0.608 | 0.665 | 0.709 |
| `truck3` | 0.779 | 0.754 | 0.640 | 0.755 | 0.817 |

`init_ms` es ~7.1-7.3 s en las 15 corridas, plano en resolución: es carga de modelo, no del clip.

**Tres lecturas.**

1. **512 colapsa.** Por debajo de la resolución de entrenamiento del checkpoint el modelo deja de
   funcionar (mIoU 0.116, @0.25 = 0.076). No es una resolución barata: es una resolución rota.
2. **640 empata al incumbente en mIoU (0.665 vs 0.666) por +38 ms**, y le gana en todo lo demás:
   @0.5 0.815 vs 0.746, perdidos 5.8% vs 11.4%, FP en hueco 229 vs 449. Misma latencia de orden,
   mejor perfil de error.
3. **`bike2` — el clip de distractores, justo lo que DRM debía arreglar — es el desastre de
   DAM4SAM a todas las resoluciones** (0.000 / 0.023 / 0.023, contra 0.246 de `f5_floor`). El
   mecanismo publicado falla exactamente en su caso de uso declarado aquí.

**Verificación visual.** 7 overlays renderizados y entregados al autor: `car12`@640, `car12`@1024,
`bike2`@640, `bird1_3`@640, `group2_3`@640, `truck3`@640, `truck3`@512. Dos mid-frames abiertos:
`car12_640` IoU 0.84 en frame 250/499, `truck3_512` IoU 0.83 en frame 268/535.

### Decisión: candidato principal (autor, 2026-07-30T12:55Z)

DAM4SAM pasa a **contendiente principal**, por delante de AsymTrack-B y del incumbente `c640_pad`,
con dos configuraciones vivas: **640 como punto de operación** (latencia comparable al incumbente,
mejor @0.5 y menos pérdidas) y **1024 como techo de calidad** (mIoU 0.709, AUC 43.1, pero 431 ms).

**Advertencia que va con el número: n=5 clips.** No es una muestra con potencia; es una lectura
descriptiva sobre clips elegidos por interesantes, no al azar. Nada de esto entra en
`thesis/claims.json` hasta el barrido completo.

**Lo que se da por bueno y lo que no:**

- Bueno: la integración (venv, checkpoint, perilla de resolución, verificación visual) y la forma
  de la curva latencia/calidad en resolución.
- No: cualquier comparación con el incumbente a n=5, y en particular la ventaja en @0.5 y en
  perdidos, que es la que motiva el barrido completo.

**Siguiente:** SAMURAI con los mismos 5 clips x 3 resoluciones, y después barrido completo de los
dos. Pendiente de documentar cuando el autor lo pida: entrada en `SOURCES.md` (DAM4SAM y SAMURAI) y
los ledgers.

## Barrido completo de DAM4SAM: la escalera 640/768/960 (run `dam-full30b`, 2026-07-30T22:20Z)

90 corridas: 30 secuencias x 3 resoluciones, 27.276 frames, 7 h 20 min de dispositivo. Es el
barrido que la sección anterior dejaba pendiente, y **corrige a la baja** su lectura a n=5.

### Por qué 768 y 960 en vez de 1024 (decisión del autor, 2026-07-30T15:40Z)

1024 es una resolución que no se desplegaría: 431 ms en la Jetson, y el redimensionado cuadrado
**sube** el eje vertical (720 -> 1024) mientras baja el horizontal (1280 -> 1024). Se sustituye por
una escalera 640/768/960. Hiera solo exige que `image_size` sea múltiplo de 32 — 704, 768, 896 y
960 son todos legales.

La latencia es lineal en **píxeles**, no en el lado. Ajuste sobre los tres puntos ya medidos
(512 -> 146.8, 640 -> 197.9, 1024 -> 431.3 ms): `p50 ~ 56 + 0.357*n^2/1000 ms`, que reproduce los
tres dentro de 3 ms. Predijo 768 -> 267 ms y 960 -> 385 ms.

**Humo de las dos resoluciones nuevas** (`raw/dam-sz-smoke/`, `truck3`), que valida el ajuste antes
de gastar 7 h:

| brazo | p50 medido | p50 predicho | mIoU | @0.5 | AUC |
| --- | --- | --- | --- | --- | --- |
| `dam4sam_t512` | 147.5 | 146 | 0.640 | 0.783 | 63.2 |
| `dam4sam_t768` | 262.1 | 267 | 0.770 | 0.931 | 75.6 |
| `dam4sam_t960` | 393.2 | 385 | 0.828 | 1.000 | 81.1 |

### Resultado

Medianas sobre las 30 secuencias, salvo AUC (media, como el resto del documento). Se añade la
**media** de mIoU porque es la que casa con los contrastes pareados de abajo.

| brazo | p50 ms | mIoU med | mIoU media | @0.25 | @0.5 | perdidos | FP en hueco | AUC | init | pico GPU |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `dam4sam_t640` | 204.0 | 0.678 | 0.597 | 0.966 | 0.846 | 0.0% | 336 | 56.9 | 7.3 s | 413-1283 MB |
| `dam4sam_t768` | 275.9 | 0.744 | 0.639 | 0.988 | 0.950 | 0.0% | 246 | 60.8 | 7.4 s | 496-1747 MB |
| `dam4sam_t960` | 407.2 | 0.770 | 0.674 | 0.996 | 0.961 | 0.0% | 277 | 63.5 | 7.4 s | 653-2603 MB |

La escalera es monótona y significativa. Wilcoxon pareado sobre las 30 secuencias:

| paso | delta medio | delta mediano | gana / pierde / empata | p |
| --- | --- | --- | --- | --- |
| 640 -> 768 | +0.042 | +0.015 | 19 / 6 / 5 | 0.0087 |
| 768 -> 960 | +0.035 | +0.015 | 18 / 5 / 7 | 0.0010 |
| 640 -> 960 | +0.077 | +0.035 | 23 / 6 / 1 | <0.0001 |

mIoU por secuencia:

| seq | 640 | 768 | 960 |
| --- | --- | --- | --- |
| `bike1` | 0.896 | 0.908 | 0.908 |
| `bike2` | 0.023 | 0.064 | 0.045 |
| `bird1_1` | 0.077 | 0.098 | 0.372 |
| `bird1_3` | 0.133 | 0.097 | 0.364 |
| `boat3` | 0.904 | 0.893 | 0.889 |
| `boat6` | 0.803 | 0.799 | 0.783 |
| `building5` | 0.456 | 0.424 | 0.552 |
| `car12` | 0.690 | 0.714 | 0.742 |
| `car16_1` | 0.862 | 0.878 | 0.883 |
| `car1_3` | 0.608 | 0.624 | 0.640 |
| `car8_2` | 0.939 | 0.942 | 0.950 |
| `car9` | 0.823 | 0.835 | 0.850 |
| `group1_2` | 0.826 | 0.815 | 0.819 |
| `group2_3` | 0.665 | 0.726 | 0.705 |
| `person18` | 0.586 | 0.770 | 0.770 |
| `person19_3` | 0.322 | 0.771 | 0.770 |
| `person20` | 0.844 | 0.842 | 0.836 |
| `person21` | 0.000 | 0.196 | 0.258 |
| `person4_1` | 0.808 | 0.807 | 0.806 |
| `truck2` | 0.733 | 0.760 | 0.782 |
| `truck3` | 0.755 | 0.770 | 0.828 |
| `uav1_2` | 0.572 | 0.680 | 0.668 |
| `uav2` | 0.659 | 0.588 | 0.642 |
| `uav3` | 0.220 | 0.220 | 0.245 |
| `uav5` | 0.595 | 0.697 | 0.750 |
| `uav7` | 0.176 | 0.310 | 0.322 |
| `wakeboard1` | 0.812 | 0.824 | 0.846 |
| `wakeboard5` | 0.604 | 0.564 | 0.587 |
| `wakeboard7` | 0.807 | 0.822 | 0.842 |
| `wakeboard8` | 0.703 | 0.728 | 0.770 |

### Lecturas

**1. La media miente sobre la forma: la ganancia es bimodal, no un gradiente.** En 22 de las 30
secuencias, subir de 640 a 960 mueve la mIoU **+0.036** — ruido caro, 203 ms por él. Toda la señal
está en las 8 donde 640 **colapsa** (mIoU < 0.5: `bike2`, `bird1_1`, `bird1_3`, `building5`,
`person19_3`, `person21`, `uav3`, `uav7`), donde el delta medio es **+0.190**. La resolución no
está afinando cajas; está evitando que el tracker suelte el objeto.

**2. Pero rescata poco.** De esas 8 colapsadas, 960 solo sube **2** por encima de 0.5. `bike2`
sigue en 0.045, `uav3` en 0.245, `uav7` en 0.322. La resolución convierte algún fallo catastrófico
en fallo parcial y no toca el resto.

**3. La mediana de la tabla exagera el escalón 768 -> 960.** 0.744 -> 0.770 parece +0.026 limpio,
pero el delta mediano pareado es +0.015 y cinco secuencias empeoran.

**4. El tamaño del objetivo no explica quién gana.** La hipótesis obvia — objetivos pequeños
necesitan más píxeles — no aguanta: Spearman entre área mediana de GT y ganancia 640 -> 960,
rho = -0.30, p = 0.10. `person18` mide 36.608 px de mediana y gana +0.184; `uav2` mide 104 px y
pierde -0.018. La partición útil es *colapsa / no colapsa*, no *pequeño / grande*.

**5. Coste.** 768 cuesta +72 ms sobre 640 y entrega +0.042; 960 cuesta +131 ms más y entrega
+0.035: la mitad de eficiente. Si hay que elegir un punto, **768 es el codo** — p50 276 ms, @0.5 de
0.950 frente a 0.846 en 640, y 131 ms más barato que 960.

**6. Ningún brazo se abstiene nunca.** `perdidos` es 0.0% en los tres y los FP en hueco
(336 / 246 / 277) no bajan monótonamente con la resolución. DAM4SAM emite caja en **todos** los
frames de ausencia — el mismo fallo ya anotado para `asym_b`. La resolución no compra nada en el
eje de presencia. Y como estos brazos **no emiten `conf`** (el plumbing de presencia cubrió SAM2 y
AsymTrack, no las familias añadidas después), `analysis/presence.py` falla sobre este run con
`no arm in raw/dam-full30b recorded a conf signal`: ese eje sigue **sin medir** para DAM4SAM.

**7. Frente al incumbente, la lectura de n=5 no sobrevive.** Sobre las 25 secuencias comunes con
`c640pad` (`sam2_c640_pad` es un brazo *recortado*, así que es indicativa, no pareada en geometría):

| brazo | mIoU media | mIoU mediana |
| --- | --- | --- |
| `sam2_c640_pad` (incumbente) | 0.682 | 0.787 |
| `dam4sam_t640` | 0.627 | 0.733 |
| `dam4sam_t768` | 0.667 | 0.770 |
| `dam4sam_t960` | 0.704 | 0.782 |

**DAM4SAM a frame completo no bate al incumbente recortado hasta 960**, y ahí lo hace por +0.022 de
media a costa de 2x la latencia. A n=5 empataba a 640; lo que ganaba entonces era en buena parte la
selección de clips. El titular del proyecto se mantiene: **el recorte compra más que los píxeles**.

### `bike2`: no hay ganador, y es geometría

24 corridas medidas sobre `bike2` en todo el barrido. La mejor es `sam2_f5_floor` con mIoU 0.246 y
@0.25 = 0.475 — el menos malo, no un ganador. Le siguen `sam2_f5` 0.176, `asym_b` 0.149,
`sam2_c704` 0.123, `sam2_c640_pad` 0.122; DAM4SAM aparece en 0.064 (768) y 0.045 (960), y
`sam2_t1024` cierra en 0.040.

El GT explica por qué: el objetivo mide **11 x 14.5 px de mediana** (área 143 px, mínimo 52) sobre
un frame de 1280x720, y se desplaza 1.0 px por frame; 35 de los 553 frames son ausencia. Metido
cuadrado en 640 queda en ~5.5 x 12.9 px. Dentro de los brazos de frame completo la mIoU **baja**
monótonamente al subir resolución (768 -> 0.064, 960 -> 0.045, 1024 -> 0.040): con el objeto a 5 px
cualquier distractor del fondo gana el mapa de máscara, y más resolución le da más textura al
distractor. `bike2` es un caso para brazo recortado con re-anclaje, no una pregunta de resolución.

### Verificación visual

10 overlays renderizados desde `raw/dam-full30b/` y entregados al autor: los tres rescates pareados
640 vs 960 (`person19_3`, `bird1_1`, `person21`), tres fallos duros a 960 (`bike2`, `uav3`,
`uav2`) y un control (`car8_2`@960). Cinco mid-frames abiertos y comprobados:
`person19_3`@640 marca `LOST` en el frame 784/1567 mientras `person19_3`@960 va con IoU 0.88 en ese
mismo frame; `bike2`@960 da IoU 0.00 en 277/553 con la predicción anclada en la orilla;
`person21`@640 marca `LOST` en 244/487; `uav2`@960 es un clip de 720x480 sobreexpuesto, dron blanco
sobre cielo blanco. De los otros cinco solo se afirman los números, no lo que se ve.

### Estado de SAMURAI

`raw/sam-5x3/` (5 clips x 3 resoluciones) está corrido y sin documentar. El barrido completo
`sam-full30` se lanzó con la misma escalera 640/768/960 y **el autor lo canceló a los 3 jobs**;
los tres resultados parciales quedan en `raw/sam-full30/`. Los brazos `samurai_t768` y
`samurai_t960` ya están registrados y sincronizados.

## Presencia y reenganche en DAM4SAM (2026-07-31T21:20Z)

Cuatro cosas encadenadas: dar señal de presencia a las familias que no la tenían, medir si esa
señal es mejor que la de SAM2 pelado, ajustar el umbral de la máquina de estados fuera de muestra
y comprobar en la Jetson que la simulación no mentía.

### 1. `conf` para DAM4SAM y SAMURAI (commits `efdb8a3`, `02817e5`)

El punto 6 de la sección anterior dejaba el eje de presencia **sin medir** para DAM4SAM: el
plumbing de `conf` cubría SAM2 y AsymTrack, no las familias vendorizadas después, y
`analysis/presence.py` moría con `no arm in raw/dam-full30b recorded a conf signal`. Ambas familias
envuelven el mismo predictor de SAM2, así que la señal ya existía dentro: `object_score_logits`, la
cabeza de oclusión **entrenada**. Solo había que sacarla del wrapper.

### 2. `lt-controls33`: el DRM no mejora la señal de presencia (93 corridas, `raw/lt-controls33/`)

Controles a 33 secuencias con hueco: `sam2_t640` (SAM2 pelado, sin DRM), `samurai_t640` y
`sam2_f5_floor`. Con `raw/dam-conf33` ya en disco, quedan cinco brazos comparables.

    analysis/presence.py raw/lt-controls33 raw/dam-conf33 --vs sam2_t640

| brazo | n | secs con hueco | presence_auc mediana | f_lt | auc < 0.5 |
| --- | --- | --- | --- | --- | --- |
| `dam4sam_t640` | 33 | 33 | 0.979 | 0.973 | 1/33 |
| `dam4sam_t768` | 33 | 33 | 0.984 | 0.982 | 0/33 |
| `sam2_t640` | 27 | 27 | 0.962 | 0.924 | 1/27 |
| `samurai_t640` | 33 | 33 | 0.956 | 0.928 | 1/33 |
| `sam2_f5_floor` | 33 | 33 | 0.925 | 0.825 | 2/33 |

`sam2_t640` sale con 27 y no 33 porque la puerta `upscales` (`device/trackers.py`) veta las seis
secuencias de 720x480 (`uav1_*`, `uav2`, `uav6`, `uav7`) — a `family="sam2"` la regla es
`n*n > w*h`. Comparar una mediana de 33 contra una de 27 es exactamente el error que la tabla de
medianas invita a cometer, así que **el contraste es pareado** sobre las 27 comunes, Wilcoxon:

| brazo vs `sam2_t640` | n | d presence_auc | p | d f_lt | p | d maxgm | p |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `dam4sam_t640` | 27 | +0.000 | 0.6109 | +0.004 | 0.0280 | +0.000 | 0.5506 |
| `dam4sam_t768` | 27 | +0.013 | 0.0009 | +0.033 | 0.0000 | +0.000 | 0.3809 |
| `samurai_t640` | 27 | +0.002 | 0.1855 | +0.000 | 0.7982 | +0.000 | 0.0150 |
| `sam2_f5_floor` | 27 | -0.000 | 0.6617 | +0.001 | 0.3674 | -0.000 | 0.0245 |

**El DRM no mejora la señal de presencia a 640.** La mediana pareada es exactamente 0.000 con
p = 0.61. Lo que hace es **barajar** qué secuencias funcionan: gana `car7` 0.447 -> 0.891,
`person16` 0.632 -> 0.991, `car14` 0.701 -> 0.994, `bird1_2` 0.908 -> 0.997, `group2_1`
0.900 -> 0.984; y pierde `person19_3` 0.991 -> 0.562, `bike2` 0.507 -> 0.284, `car1_3`
0.913 -> 0.846, `group2_3` 0.933 -> 0.867, `group3_2` 0.927 -> 0.877. La señal es de la cabeza de
oclusión de SAM2, no del banco de memoria. El único brazo significativo en AUC es `dam4sam_t768`,
y está **confundido con resolución** — de ahí el control `sam2_t768` (más abajo).

Nota de lectura: la columna `maxgm` de esta tabla es la vieja, la que sustituye p por la tasa de
silencio; para un brazo que nunca se abstiene vale 0 por construcción. Es degenerada y no se usa
para decidir nada. Lo que decide es `gm_ox` en `analysis/lt_sim.py`.

### 3. `analysis/lt_sim.py`: por qué evaluar el largo plazo no cuesta GPU

`Dam4SamLtArm.step` llama a `inner.step(frame)` **en todos los frames** y solo decide si devuelve
la caja o no. Nada de lo que decide la máquina de estados llega al tracker: no hay re-init, ni
edición de memoria, ni movimiento de la ventana de búsqueda. El lazo está **abierto**. Consecuencia
práctica: la máscara de respuesta es una función pura de la traza `(box, conf)` por frame que ya
está escrita en `raw/*.json`. Cambiar tau vuelve a filtrar un JSON; no calcula un solo píxel. Un
barrido de ~1.900 configuraciones sale en segundos en el portátil.

Lo que **no** es simulable, y por qué: el re-detector de cinco sondas de `AsymLtArm` mueve la
ventana de búsqueda, así que la entrada del frame siguiente depende del estado — lazo cerrado.
Igual pasa con suprimir la escritura en memoria mientras `LOST` (ver `TODO.md`): cambia lo que ve
el modelo. Eso se corre en la Jetson o no se mide.

Métrica de decisión: **`gm_ox`**, el MaxGM publicado de OxUvA para una política fija,
`max_p sqrt((1-p) TPR ((1-p) TNR + p))`. En forma cerrada con u = 1-p da `u* = 1/(2(1-TNR))`
recortado a 1, así que con TNR >= 0.5 colapsa a `sqrt(TPR TNR)`. Exige HIT (IoU > 0) para contar
TPR, que es lo que impide que "abstenerse siempre" gane.

### 4. Umbral fijo contra umbral relativo

El umbral fijo es un tau global, y asume que `object_score_logits` está calibrado **entre**
secuencias. No lo está. Ajustado sobre las 17 secuencias pares de `raw/dam-conf33` y evaluado en
las 16 impares, `lo 5.719 hi 6.120 k 1` cuesta 0.10 de f_lt y 0.20 de TPR sobre frames PRESENTES,
y **cinco de las seis peores secuencias ya tenían presence_auc >= 0.86**: el orden dentro del clip
estaba bien, lo que estaba mal era el punto de corte.

La alternativa es cortar en `mu - a sigma` sobre los últimos `w` frames que el brazo cree
on-target. Es **causal** — solo mira frames ya emitidos — que es lo que la hace desplegable y no un
mero ajuste offline mejor. Los primeros `w` frames siempre responden: el operador acaba de designar
el objetivo, la misma suposición que hace el `init` del propio tracker. Consecuencia que conviene
saber: una secuencia más corta que `w` nunca se abstiene y el brazo es exactamente `dam4sam_t640`.

`analysis/lt_sim.py raw/dam-conf33 --arm dam4sam_t640` — mejor fijo `lo 5.719 hi 6.120 k 1`, mejor
relativo `a 4.0 b 2.0 k 1 w 300 movil`:

| | gm_ox | f_lt | tpr | tnr | silencio | sil. en hueco |
| --- | --- | --- | --- | --- | --- | --- |
| fit fijo | 0.810 | 0.801 | 0.671 | 1.000 | 0.350 | 1.000 |
| fit rel | 0.813 | 0.918 | 0.926 | 0.956 | 0.111 | 0.956 |
| fit plain | 0.707 | 0.918 | 0.978 | 0.737 | 0.058 | 0.737 |
| EVAL fijo | 0.862 | 0.863 | 0.797 | 1.000 | 0.220 | 1.000 |
| **EVAL rel** | **0.869** | **0.964** | **0.949** | 0.903 | 0.122 | 0.903 |
| EVAL plain | 0.606 | 0.968 | 0.992 | 0.521 | 0.037 | 0.521 |
| todas 33 fijo | 0.816 | 0.811 | 0.687 | 1.000 | 0.261 | 1.000 |
| todas 33 rel | 0.851 | 0.959 | 0.937 | 0.926 | 0.111 | 0.926 |
| todas 33 plain | 0.630 | 0.962 | 0.983 | 0.600 | 0.049 | 0.600 |

Contra el brazo sin abstención, fuera de muestra: `fijo` gana 11/16, mediana +0.216, **peor -0.294**,
d f_lt -0.022; `rel` gana 10/16, mediana +0.078, **peor -0.037**, d f_lt **-0.001**. El relativo
gana menos por secuencia y **pierde muchísimo menos en la peor**, que es la propiedad que importa
en un lazo de control. En `dam4sam_t768` la lectura se repite: fijo `lo 5.438 hi 5.495 k 3` EVAL
0.919 peor -0.206, relativo `a 2.0 b 2.0 k 5 w 30 movil` EVAL **0.947** peor -0.034.

**`asym_b` va al revés** (`raw/asym-conf`): fijo `lo 0.427 hi 0.595 k 1` EVAL gm_ox 0.625 contra
relativo `a 1.5 b 0.0 k 2 w 100 movil` 0.594. Con presence_auc 0.711 el **orden** dentro del clip
ya es malo, así que normalizar la escala solo mueve ruido. El umbral relativo no arregla una señal
mala; explota una señal buena mal calibrada.

### 5. `dam4sam_lt` registrado, y el humo de paridad (`raw/parity-smoke/`)

`dam4sam_lt` = `dam4sam_t640` + umbral relativo `a=4.0 b=2.0 k=1 w=300`, el argmax de la mediana de
`gm_ox` sobre la mitad de ajuste. La afirmación "la simulación reproduce el brazo real" es
verificable y por tanto se verifica: se corrió el brazo real en la Jetson sobre `car2` y se comparó
frame a frame contra `run_machine_rel` replicado desde `raw/dam-conf33/dam4sam_t640__car2.json`.

    conf identico brazo real vs base: True
    frames que responde: real 1293  simulado 1293  de 1321
    discrepancias: 0

La primera línea es la premisa (el wrapper no perturba al tracker), la tercera es la conclusión.
Latencia `dam4sam_lt` p50 **215.1 ms** contra ~204 ms del brazo pelado: abstenerse es gratis, como
debe ser, porque el trabajo se hace igual. En la misma tanda se rehizo `dam4sam_t768 x car2` sin
contención: p50 **282.0 ms** (la medida previa salió de una máquina compartida y se descarta).

Las dos máquinas de estados tienen self-check ejecutable: `python device/trackers.py --self-check`
y el bloque final de `analysis/lt_sim.py`. Ambos incluyen la aserción que justifica el diseño — la
misma traza desplazada +1000 debe dar **la misma** máscara.

### 6. `sam2-t768-control`: el control que separa resolución de memoria

`dam4sam_t768` es el único brazo significativo del pareado de arriba y está confundido: sube
resolución **y** añade DRM. `sam2_t768` sobre las mismas 33 secuencias con hueco (27 tras la puerta
`upscales`) desempata.

Primer intento **muerto sin traza**: el driver se detuvo en `550/865` de `bird1_3`, sin traceback,
dejando solo `manifest.json`. No se pudo confirmar OOM — `dmesg` en la Jetson pide contraseña y
`journalctl -k` no devolvió nada. Hipótesis principal es presión de memoria: 7,6 GB de RAM, dos
procesos de `run_arm.py` a ~2,1 GB de RSS y 126 MB libres con 3 GB en caché durante la corrida.
Relanzado sin cambios, `bird1_3` pasó y el run siguió. Queda anotado como caída no explicada, no
como fallo reproducible.

Pendiente: cerrar el run, y con él el pareado a tres bandas `sam2_t640` / `sam2_t768` /
`dam4sam_t768`.
