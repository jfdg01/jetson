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
