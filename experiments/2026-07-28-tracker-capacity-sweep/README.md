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

## Variables controladas

Sensores verificados en dispositivo el 2026-07-28: INA3221 en `1-0040` (raíles `VDD_IN`, `VDD_CPU_GPU_CV`, `VDD_SOC`), 8 zonas térmicas en `/sys/devices/virtual/thermal/`, zram activo (6 × 634 MB), 6 cores, governor `schedutil`, L4T R36.5.0.

### Fijas — plataforma

| Variable | Valor | Cómo se fija / verifica |
| --- | --- | --- |
| Power mode | 15 W, mode 0 | `nvpmodel -m 0`; `nvpmodel -q` al inicio de cada arm |
| Relojes | pinneados al máximo | `jetson_clocks`; sin DVFS → elimina jitter de frecuencia |
| Governor CPU | fijado por `jetson_clocks` (no `schedutil`) | leer `scaling_governor` post-fijado |
| Cores online | 6/6 | `nproc` |
| Ventilador | perfil fijo, mismo para todos | `pwm-fan` en modo fijo, no adaptativo |
| Carga concurrente | cero | `ps` sin procesos >100 MB antes de cada arm; sin `llama-server` |
| Escritorio | apagado | `multi-user.target` — quita Xorg + gnome-shell |
| Red | inactiva | descargas hechas antes; run lanzado con `nohup`, sin ssh vivo durante la medición |
| Almacenamiento | NVMe | modelos y dataset en `/dev/nvme0n1p1`, nunca USB |
| Swap | zram debe quedar quieto | muestrear `/proc/meminfo`; **un arm que toca swap se invalida** |
| Temperatura de arranque | por debajo de umbral | gate de enfriamiento entre arms; abortar si hay throttle |

### Fijas — software

| Variable | Valor |
| --- | --- |
| Venv | `~/sam2-bench/.venv`, congelado durante toda la campaña |
| Versiones | Python 3.10.12, torch 2.8.0, TensorRT 10.3.0, cv2 4.11.0, L4T R36.5.0 |
| Hilos | `torch.set_num_threads` y `OMP_NUM_THREADS` fijados — crítico para los arms de CPU |
| `cudnn.benchmark` | mismo valor en todos los arms |
| Precisión matmul / TF32 | fijada, misma en todos |
| `torch.compile` | desactivado |
| Semillas | fijadas donde el modelo muestrea |
| Aislamiento | **un proceso nuevo por arm** — sin contaminación de allocator ni de caché cuDNN |

### Fijas — tarea y datos

| Variable | Valor |
| --- | --- |
| Dataset | mismo subconjunto de UAV123, mismas secuencias, mismo orden |
| Caja inicial | GT del frame 0, idéntica para todos los arms |
| Decodificación | frames **pre-decodificados a disco** y precargados; el decode queda **fuera** del bucle medido |
| Longitud | mismo número de frames por secuencia |
| Objetos | 1 por secuencia (multi-objeto es eje manipulado, no ruido) |
| Reinicialización | pasada única, sin re-init tras pérdida — misma política para todos |
| Salida | caja por frame; máscara → bbox del contorno en SAM2 y derivados |

### Fijas — protocolo de medida

| Variable | Valor |
| --- | --- |
| Warm-up | N frames descartados antes de cronometrar (JIT, autotune cuDNN, primer kernel) |
| Reloj | `time.monotonic` con `torch.cuda.synchronize()` antes y después; idéntico en todos |
| Granularidad | latencia **por frame**, no media global |
| Repeticiones | k repeticiones por arm, mediana entre repeticiones |
| Orden de arms | **aleatorizado / contrabalanceado** — descorrelaciona la deriva térmica de la identidad del arm |
| Muestreo de recursos | mismo intervalo y mismo sampler para RAM, GPU, potencia y temperatura |

### Manipuladas

| Eje | Niveles | Alcance |
| --- | --- | --- |
| Arm (modelo) | 27 | eje primario |
| Resolución | 512 / 640 / 768 / 1024 | solo sobre supervivientes del primer corte |
| Backend | torch fp16 / TRT fp16 | solo sobre los exportables |
| Objetos simultáneos | 1, 2, 4, ... | eje de capacidad, sobre supervivientes |

### Medidas

| Métrica | Nota |
| --- | --- |
| FPS de propagación en régimen | tras warm-up |
| Latencia p50 / p95 / p99 | por frame |
| Latencia de inicialización | separada — es un coste distinto al de propagación |
| RAM host pico | RSS |
| Memoria GPU pico | — |
| Potencia media y **energía por frame (J/frame)** | vía INA3221; métrica de hardware edge, no derivada |
| Temperatura máxima y eventos de throttle | 8 zonas térmicas |
| Exactitud | IoU (consistente con el resto del proyecto) + AUC del success plot |

### No controlables — confusores declarados

| Confusor | Mitigación |
| --- | --- |
| Deriva térmica a lo largo del sweep | orden aleatorizado + gate de enfriamiento + registrar temperatura por arm |
| Fragmentación de memoria en runs largos | proceso nuevo por arm |
| Datos y receta de entrenamiento distintos entre modelos | **irreducible** — se declara: el sweep compara modelos tal como se publican, no arquitecturas en igualdad de entrenamiento |
| Dificultad desigual entre secuencias | mismo conjunto para todos → análisis **pareado** por secuencia |

### Aviso estadístico

27 arms no pueden ser todos inferenciales. Con la familia Holm del proyecto, corregir sobre 27 contrastes deja cualquier diferencia sin poder a `n>=25`. Postura propuesta para cuando esto se pre-registre: el sweep es **caracterización descriptiva** de la placa, no una claim gating, con **uno o dos contrastes inferenciales declarados de antemano**. Cualquier otra cosa que salga es exploratoria y se etiqueta como tal.
