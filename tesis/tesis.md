---
title: Registro de experimentos
subtitle: Grounding + tracking
author: Javier Francisco Dibo Gómez
comment: Borrador, 2026-07-27T12:00Z
locale: es
bibliography: tesis.bib
citation_style: numeric
---

# Contexto

Placa Jetson Orin Nano 8 GB Developer Kit

- Cómputo: CPU de 6 núcleos + GPU integrada en el SoC
- Memoria: 7607 MB de memoria unificada, libres unos ~6 GB después del overhead del SO + escritorio (medido en 1735 MB).
- Temperatura: temperaturas pico registradas en 67 °C, thermal throttle reportado a 99.5 °C [@nvidia2024orinpower]
- Consumo: La placa tiene un rango de consumo de 5 W en idle hasta 15 W como máximo, con clocks bloqueados para evitar throttling dinámico.
- Infra: `llama.cpp` compilada en la Jetson a `aarch64`, fijada al commit `57fe1f0`, JetPack: 6.2.2+b24, L4T: R36.5.0, CUDA: 12.6, cmake: 3.22.1

# E1 - LLM de referencia sobre la Jetson

Resumen de: `experiments/2026-06-13-llamacpp-upper-bound`, realizado 2026-06-13T14:10Z.

## Introducción

El primer experimento es de reconocimiento, y consiste en establecer las dependencias y sistemas para verificar el funcionamiento correcto y adecuado del sistema. Para ello se ejecuta un LLM directamente sobre la Jetson.

La placa tiene dos modos, uno de 7 W y otro de 15 W. Para todos los experimentos (este y todos los futuros) el modo seleccionado es el de 15 W.

Para comenzar se compiló `llama.cpp` en la Jetson, arquitectura `aarch64`, para evitar problemas de compilación cruzada; esta es la versión de llama utilizada a lo largo de la experimentación y es la que siempre corre en la placa, fijada al commit `57fe1f0` desde el repositorio de llama para ser reproducible.

El modelo elegido es `Llama-3.2` [@bartowski2024llama32gguf], un modelo de 3B de parámetros, cuantizado a 4 bits, utilizando el `k-quant` medio de llama.cpp, que cuantiza en bloques en lugar de forma uniforme, teóricamente mejorando la precisión respecto de una cuantización normal, en su versión `GGUF` compatible con `llama.cpp`.

## Preguntas / Hipótesis

**E1.P1**: ¿Qué rendimiento tiene la placa para un LLM pequeño?

**E1.P2**: ¿Cuál es el principal cuello de botella?

**E1.P3**: ¿Cómo responde el hardware en términos de temperatura, consumo, etc.?

## Entorno

Idem a contexto

## Método

Para el test de rendimiento en LLM se ha ejecutado `llama-bench` repetido 5 veces, que carga el modelo y corre dos fases:

1. **prefill**: que mide la velocidad de procesamiento del prompt, medido en `tok/s`. P. ej.: pp512 representa procesar 512 tokens de prompt.

2. **decode**: que mide la velocidad de generación, medido en `tok/s`. P. ej.: tg128 representa generar 128 tokens de salida.

Antes de cualquier medida se fija el modo de potencia y se bloquean los relojes, para que ninguna cifra dependa del escalado dinámico de frecuencia:

<!-- caption: Fijado del modo de potencia 15W (ID=0) y bloqueo de relojes, previo a toda medida -->

```bash
sudo nvpmodel -m 0 && sudo jetson_clocks
```

El caudal se mide con dos pasadas de `llama-bench`: la primera cubre prefill y decode (`pp512`, `tg128`) con 5 repeticiones, la segunda el decode sostenido (`tg512`) con 3.

<!-- caption: Caudal, prefill y decode, n=5 repeticiones. Llama-3.2-3B-Instruct Q4_K_M, 15 W + jetson_clocks, ngl 99 (offload completo a GPU) -->

```bash
export LD_LIBRARY_PATH=~/llama.cpp/build/bin
~/llama.cpp/build/bin/llama-bench -m ~/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf \
  -ngl 99 -p 512 -n 128 -r 5 -o csv
```

<!-- caption: Decode sostenido, n=3 repeticiones. Misma configuración que la pasada anterior -->

```bash
~/llama.cpp/build/bin/llama-bench -m ~/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf \
  -ngl 99 -n 512 -r 3 -o csv
```

Para el test de consumo, se ha ejecutado `tegrastats`, preinstalada en la Jetson, nos ofrece uso de RAM (MB), CPU % por núcleo, GPU %, frecuencias (MHz), temperaturas (°C) y consumos (mW).

<!-- caption: Telemetría de consumo y temperatura, ventana continua a 1 Hz, n=1 -->

```bash
tegrastats --interval 1000 --logfile /tmp/tegra.log
```

## Resultados

<!-- caption: Rendimiento de llama-bench para Llama 3.2 -->

| Test                        | tok/s (avg ± std_dev) |
| --------------------------- | --------------------- |
| Prefill (pp512)             | 570.0 ± 2.4           |
| Decode (tg128)              | 14.61 ± 0.00          |
| Decode sostenido (tg512 ×3) | 14.53 ± 0.02          |

Idle definido como: escritorio + OS, GPU idle. Decode medio reducido por la carga del modelo + espacios de repetición, comportamiento pico durante decode.

<!-- caption: Consumo medido con tegrastats -->

| Modo   | Media | Pico  |
| ------ | ----- | ----- |
| Idle   | 5.24 W | 5.28 W |
| Decode | 12.5 W | 13.6 W |

Temperatura máxima de la unión del SoC: 67 °C. Como comparación, la temperatura máxima permitida antes de la disminución de rendimiento se reporta en 99.5 °C según NVIDIA [@nvidia2024orinpower], lo que da un margen de 32 °C.

<!-- caption: Eficiencia energética durante la generación de tokens (decode) -->

| Métrica           | Total      |
| ----------------- | ---------- |
| tok/s por W       | 1.1        |
| Energía por token | 0.94 J/tok |

La ocupación de la GPU se planta en 99 % durante decode, mientras que la CPU se mantiene al 4 %. En cuanto a memoria, pasamos de 1735 MB (idle) a 3457 MB (pico de decode).

## Resultados negativos

Sin negativos

## Conclusiones

Para este modelo, hemos recogido datos relevantes, especialmente el consumo y la temperatura, que nos dan una idea de las capacidades edge del dispositivo, sabemos que tenemos un margen de temperatura amplio y que el principal cuello de botella parece ser el ancho de banda, debido al uso de GPU al 99%.

**E1.R1**: La placa tiene un rendimiento aceptable para el LLM probado, generando ~14 tok/s sostenidos, suficiente para saturar la velocidad de lectura humana.

**E1.R2**: El ancho de banda de GPU es el principal cuello de botella plantado en 99 %, mientras que el uso de CPU, memoria o energía no se satura.

**E1.R3**: Favorablemente, margen de ~32 °C en temperatura respecto del thermal throttle, ~4 GB de memoria libres en el pico de uso y margen de 1.4 W sobre el máximo.

# Experimento 2
