---
title: Parte I: puesta en marcha
locale: es
---

La primera campaña del proyecto fue una toma de contacto. 

El dispositivo de interés es la NVIDIA Jetson Orin Nano Developer Kit, con 8 GB de memoria unificada (de aquí en adelante «la Jetson»).

## Configuración de la Jetson

Al recibirse, la Jetson no estaba configurada. Se instaló el *firmware* `L4T R36.5.0` y el sistema operativo (SO) `JetPack 6.2.2+b24`, utilizando el proceso manual de reseteo que involucra puentear el inicio para hacerla entrar en modo *Force Recovery* a través de USB, tal y como describe la guía de NVIDIA [1].

El *software* *flasheado* en la Jetson permite la elección de dos modos de consumo: 7 W y 15 W [2]. Todas las ejecuciones sobre la Jetson se produjeron con la configuración de 15 W. Para minimizar la variabilidad en las ejecuciones se fijaron los relojes de la Jetson usando el *script* `jetson_clocks` a sus máximos [2]: 6 núcleos de CPU a 1,51 GHz, GPU a 624,75 MHz y *External Memory Controller* (EMC) a 2.133 MHz. Tras la instalación del SO la Jetson tenía disponibles 7,4 GiB de memoria y más de 200 GB de almacenamiento NVMe.

## Primera toma de contacto

El primer experimento realizado buscaba responder a la pregunta: ¿Cuántos tokens por segundo da un *large language model* (LLM) en la Jetson, y con qué potencia?

Su resultado da un techo de referencia para los experimentos posteriores.

Se ejecutó el modelo Llama-3.2-3B-Instruct, cuantizado a Q4_K_M, sobre llama.cpp [3] en su *commit* `57fe1f0`, compilado sobre la Jetson para CUDA `sm_87`. Con la herramienta `llama-bench` [4] se midieron las dos fases del proceso de generación: *prefill* (a 512 tokens) y *decode* (a 128 tokens), en 5 repeticiones. La potencia y la temperatura se obtuvieron con la herramienta `tegrastats` [5]. La [[tab-2-1]] muestra los resultados.

<!-- caption: Rendimiento, potencia y temperatura de Llama-3.2-3B-Instruct Q4_K_M en la Jetson, a 15 W con jetson_clocks, sobre llama.cpp 57fe1f0 con el modelo entero en la GPU (ngl 99). El rendimiento es la media ± la desviación típica de llama-bench. La potencia es la de la placa entera (VDD_IN), medida por tegrastats cada segundo. -->
| Medida | Valor |
|---|---|
| *Prefill* (512 tokens) | 570,0 ± 2,4 tok/s |
| *Decode* (128 tokens) | 14,61 ± 0,00 tok/s |
| *Decode* sostenido (512 tokens) | 14,53 ± 0,02 tok/s |
| Potencia en reposo, media | 5,24 W |
| Potencia en *decode*, media | 12,5 W |
| Potencia en *decode*, pico | 13,6 W |
| Temperatura de la unión del SoC, pico | 66,9 °C |
| Eficiencia, con la potencia de pico | 1,1 tok/s·W⁻¹ (0,94 J/token) |


