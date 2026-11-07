---
title: Parte I: puesta en marcha
locale: es
bibliography: ../refs.bib
---

La primera campaña del proyecto fue una toma de contacto.

El dispositivo de interés es la NVIDIA Jetson Orin Nano Developer Kit, con 8 GB de memoria unificada (de aquí en adelante «la Jetson»).

## Configuración de la Jetson

Al recibirse, la Jetson no estaba configurada. Se instaló JetPack `6.2.2+b24`, el paquete de *software* de NVIDIA para la Jetson. JetPack incluye el sistema operativo (SO) Jetson Linux, también llamado *Linux for Tegra* (L4T), en su versión `R36.5.0`. La instalación utilizó el proceso manual de reseteo que involucra puentear el inicio para hacerla entrar en modo *Force Recovery* a través de *Universal Serial Bus* (USB), tal y como describe la guía de NVIDIA [@nvidia2026quickstart].

El *software* *flasheado* en la Jetson define dos modos de consumo en `nvpmodel`: 7 W y 15 W. Todas las ejecuciones sobre la Jetson se produjeron con la configuración de 15 W. Para minimizar la variabilidad en las ejecuciones se fijaron los relojes de la Jetson usando el *script* `jetson_clocks` a sus máximos [@nvidia2026orinpower]: 6 núcleos de CPU a 1,51 GHz, GPU a 624,75 MHz y *External Memory Controller* (EMC) a 2.133 MHz. Tras la instalación del SO, CUDA detectaba 7.976 MB de memoria unificada, y la Jetson tenía más de 200 GB de almacenamiento *Non-Volatile Memory Express* (NVMe).

## Primera toma de contacto

El primer experimento realizado buscaba responder a la pregunta: ¿Cuántos *tokens* por segundo da un *large language model* (LLM) en la Jetson, y con qué potencia?

Su resultado da un techo de referencia para los experimentos posteriores.

Se ejecutó el modelo Llama-3.2-3B-Instruct, cuantizado a Q4_K_M, sobre llama.cpp [@llamacpp57fe1f0] en su *commit* `57fe1f0`, compilado sobre la Jetson para CUDA `sm_87`. Con la herramienta `llama-bench` [@llamabench57fe1f0] se midieron las dos fases del proceso de generación: *prefill* (a 512 *tokens*) y *decode* (a 128 *tokens*), en 5 repeticiones. Se midió también un *decode* sostenido de 512 *tokens*, en 3 repeticiones. La potencia y la temperatura se obtuvieron con la herramienta `tegrastats` [@nvidia2026tegrastats]. La [[tab-2-1]] muestra los resultados.

<!-- caption: Rendimiento, potencia y temperatura de Llama-3.2-3B-Instruct en la Jetson, con el modelo entero en la GPU (ngl 99). El rendimiento es la media ± la desviación típica. La potencia es la de la placa entera (VDD_IN), medida cada segundo. -->
| Medida | Valor |
|---|---|
| *Prefill* (512 *tokens*) | 570,0 ± 2,4 tok/s |
| *Decode* (128 *tokens*) | 14,61 ± 0,00 tok/s |
| *Decode* sostenido (512 *tokens*) | 14,53 ± 0,02 tok/s |
| Potencia en reposo, media | 5,24 W |
| Potencia en *decode*, media | 12,5 W |
| Potencia en *decode*, pico | 13,6 W |
| Temperatura de la unión del *System on Chip* (SoC), pico | 66,9 °C |
| Eficiencia, con el *decode* sostenido y la potencia de pico | 1,1 tok/s·W⁻¹ (0,94 J/token) |

