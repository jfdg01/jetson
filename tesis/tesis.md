---
title: Registro de experimentos
subtitle: Grounding + tracking
author: Javier Francisco Dibo Gómez
comment: Borrador
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

<!-- caption: Rendimiento de llama-bench para Llama-3.2-3B-Instruct, n=5 repeticiones para pp512 y tg128, n=3 para tg512. Q4_K_M, 15 W + jetson_clocks, ngl 99 -->

| Test                        | tok/s (avg ± std_dev) |
| --------------------------- | --------------------- |
| Prefill (pp512)             | 570.0 ± 2.4           |
| Decode (tg128)              | 14.61 ± 0.00          |
| Decode sostenido (tg512 ×3) | 14.53 ± 0.02          |

Idle definido como: escritorio + OS, GPU idle. Decode medio reducido por la carga del modelo + espacios de repetición, comportamiento pico durante decode.

<!-- caption: Consumo medido con tegrastats -->

| Modo   | Media  | Pico   |
| ------ | ------ | ------ |
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

# E2 - Barrido de LLMs

Resumen de: `experiments/2026-06-13-model-capability-sweep`, realizado 2026-06-14T12:45Z.

## Introducción

Este experimento es una comparativa de un conjunto diverso de LLMs. E1 midió un solo modelo; aquí se barre el eje del tamaño para saber qué clase de modelo cabe y a qué velocidad corre en la placa. El principal indicador medido es el caudal (throughput), definido en tok/s.

El barrido es de **modelo**, la única variable independiente. Todo lo demás se mantiene fijo: cuantización `Q4_K_M`, offload completo a GPU (`-ngl 99`), `n_ctx = 4096`, mismo prompt, mismas repeticiones.

Los diez modelos cubren tres niveles de tamaño (A,B y C) y cuatro familias. Dentro de ellos, Qwen2.5 aparece en 0.5 B, 1.5 B, 3.1 B y 7.6 B, cuatro puntos de la misma familia dan la curva de escalado más limpia posible, sin que la arquitectura contamine la comparación. Llama-3.2-3B se repite respecto de E1.

El recuento de parámetros de la tabla no es el nombre comercial del modelo sino el campo `model_n_params` del propio fichero GGUF. La distinción importa porque es la métrica principal estudiada en E2.P1: las filas de Llama-3.2 y de Qwen2.5-3B llevaban el nombre comercial (1.0 B, 3.0 B, 3.0 B), y las dos de Llama eran justamente las que parecían anómalas frente a la tendencia `1/(bytes de pesos)`; con el valor medido (1.2 B, 3.1 B, 3.2 B) la anomalía desaparece.

<!-- caption: Los diez modelos del barrido, todos Q4_K_M con -ngl 99. Parámetros según model_n_params del GGUF, tamaño de pesos según el fichero descargado, ordenada por número de parámetros -->

| # | Modelo | Parámetros | Peso | Nivel | Papel en el diseño | GGUF |
| --- | --- | --- | --- | --- | --- | --- |
| 01 | Qwen2.5-0.5B-Instruct | 0.5 B | ~380 MB | A | suelo de caudal; Qwen 1 de 4 | [@bartowski2024qwen05b] |
| 02 | Llama-3.2-1B-Instruct | 1.2 B | ~770 MB | A | 1B de otra familia | [@bartowski2024llama32-1b] |
| 03 | Qwen2.5-1.5B-Instruct | 1.5 B | ~940 MB | A | Qwen 2 de 4 | [@bartowski2024qwen15b] |
| 04 | Gemma-2-2B-it | 2.6 B | ~1.63 GB | B | 2B de otra familia (Gemma) | [@bartowski2024gemma2-2b] |
| 05 | Qwen2.5-3B-Instruct | 3.1 B | ~1.84 GB | B | Qwen 3 de 4 | [@bartowski2024qwen3b] |
| 06 | Llama-3.2-3B-Instruct | 3.2 B | ~2.02 GB | B | ancla: mismo modelo que E1 | [@bartowski2024llama32gguf] |
| 07 | Phi-3.5-mini-instruct | 3.8 B | ~2.28 GB | B | ~4B de otra familia (Phi) | [@bartowski2024phi35mini] |
| 08 | Mistral-7B-Instruct-v0.3 | 7.2 B | ~4.17 GB | C | 7B de otra familia | [@bartowski2024mistral7b] |
| 09 | Qwen2.5-7B-Instruct | 7.6 B | ~4.47 GB | C | Qwen 4 de 4 | [@bartowski2024qwen7b] |
| 10 | Meta-Llama-3.1-8B-Instruct | 8.0 B | ~4.69 GB | C | sonda del muro de memoria | [@bartowski2024llama31-8b] |

Los diez GGUF salen del mismo publicador en Hugging Face, `bartowski`, lo que elimina el empaquetado como variable oculta entre unidades. La unidad 06 no se volvió a descargar: reutiliza el fichero local de E1, que viene de ese mismo repositorio. El SHA256 de cada fichero queda registrado en el registro de la campaña.

## Preguntas / Hipótesis

**E2.P1**: ¿Cómo escala el decode con el número de parámetros? _Hipótesis_: el decode está limitado por ancho de banda, luego escala como `1/(bytes de pesos)`, no con el número de parámetros en sí.

**E2.P2**: ¿Dónde está el muro de memoria? _Hipótesis_: los modelos de 7–8 B en `Q4_K_M` con `n_ctx` grande caen en swap u OOM (Out Of Memory), y lo hacen de golpe; no como una degradación gradual.

**E2.P3**: ¿Cómo escala la eficiencia energética con el tamaño? _Hipótesis_: la curva no es monótona y tiene su óptimo de Pareto en el nivel de 2–3 B, porque el consumo de plataforma (~5.2 W) penaliza a los modelos pequeños.

**E2.P4**: ¿Cómo escala la latencia hasta el primer token (TTFT) con el tamaño del modelo?

**E2.P5**: A igualdad de tamaño, ¿cuánto pesa la arquitectura frente al tamaño de los pesos?

## Entorno

Idem a contexto.

## Método

Diez unidades independientes, una por modelo, con el mismo procedimiento y arrancando cada una desde idle frío para que ninguna herede la temperatura elevada de la anterior. La secuencia por unidad, con el modelo como única variable (aquí, la unidad 05):

<!-- caption: Fijado del modo de potencia y arranque de telemetría, previo a cada unidad. 15 W (ID=0), relojes bloqueados -->

```bash
ssh jetson 'sudo nvpmodel -m 0 && sudo jetson_clocks'
ssh jetson 'nohup tegrastats --interval 1000 --logfile /tmp/msweep05_tegra.log >/dev/null 2>&1 &'
```

Modelo descargado con `wget`.

<!-- caption: Adquisición del GGUF y registro de su hash, n=1 por unidad -->

```bash
ssh jetson 'wget -c -O ~/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf \
   "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf"'
ssh jetson 'sha256sum ~/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf'
```

El caudal se mide igual que en E1: una pasada de prefill + decode (`pp512`, `tg128`) con 5 repeticiones y una segunda de decode sostenido (`tg512`) con 3.

<!-- caption: Caudal, prefill y decode, n=5 repeticiones, más decode sostenido con n=3. Q4_K_M, 15 W + jetson_clocks, ngl 99, n_ctx 4096 -->

```bash
export LD_LIBRARY_PATH=~/llama.cpp/build/bin:/usr/local/cuda/lib64
~/llama.cpp/build/bin/llama-bench -m ~/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf \
  -ngl 99 -p 512 -n 128 -r 5 -o csv
~/llama.cpp/build/bin/llama-bench -m ~/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf \
  -ngl 99 -n 512 -r 3
```

El TTFT sale de una generación única cronometrada, con el mismo prompt en los diez modelos:

<!-- caption: TTFT, una generación por modelo (n=1), prompt idéntico en las diez unidades -->

```bash
~/llama.cpp/build/bin/llama-completion -m ~/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf \
  -ngl 99 -c 4096 -n 128 -no-cnv \
  -p "Explain what an edge AI accelerator is in two sentences."
```

Al cierre de la unidad se recogen memoria pico, estado de swap y la telemetría, y se para el log:

<!-- caption: Cierre de unidad: memoria, swap y telemetría -->

```bash
ssh jetson 'free -m; cat /proc/swaps; tail -n 5 /tmp/msweep05_tegra.log'
ssh jetson 'pkill -f tegrastats || true'
```

Las dos magnitudes derivadas se calculan sobre la potencia **pico** de la ventana de decode, y **no comparten base**, por lo que no son recíprocas (`1/2.02 ≠ 0.824`):

- `tok/s·W⁻¹ = tg128 / (W_pico − W_idle)` — **neta de plataforma**: descuenta el idle de la propia unidad para separar el coste del cómputo del coste de tener la placa encendida. Unidad 01: `71.52 / (11.25 − 5.17) = 11.77`.
- `J/tok = W_pico / tg128` — **placa completa**, sin descontar idle. Unidad 01: `11.25 / 71.52 = 0.157`.

## Resultados

Las diez unidades completaron el 2026-06-14 sin OOM ni caída, y ninguna llegó al throttle térmico.

La figura recoge las cinco magnitudes del barrido contra el número de parámetros, con dos referencias trazadas: los 7607 MB de memoria unificada de la placa, declarados en el contexto, y el umbral de 250 ms por debajo del cual la respuesta se percibe como interactiva.

<!-- caption: Barrido completo, n=5 repeticiones para pp512 y tg128, n=1 para TTFT. Todos Q4_K_M, 15 W + jetson_clocks, ngl 99, n_ctx 4096. Las etiquetas son el número de unidad de la tabla de modelos -->

![Barrido de las diez unidades frente al número de parámetros.](figuras/e2-barrido.png)

El ancla funciona, comparando lo mismo con lo mismo: Llama-3.2-3B da aquí tg128 = 14.60 tok/s frente a 14.61 tok/s en E1 (−0.07 %) y tg512 = 14.54 tok/s frente a 14.53 tok/s (+0.08 %). La placa reproduce entre experimentos muy por debajo del 0.1 %.

Ninguna unidad tocó el techo térmico. La potencia pico va de 11.25 W (unidad 01) a 13.92 W (unidad 10), y la temperatura de unión pico de 59.9 °C a 67.4 °C — el máximo del barrido coincide con el de E1 y deja los mismos ~32 °C de margen.

La familia Qwen2.5 aporta los cuatro puntos que permiten leer el escalado sin que la arquitectura contamine la comparación. La referencia discontinua de la figura siguiente es el caudal que daría un escalado exacto `1/parámetros`, anclado en la unidad de 0.5 B: la curva medida la sigue hasta 3.1 B y se despega a partir de ahí.

<!-- caption: Escalado dentro de la familia Qwen2.5, decode tg128, n=5. Q4_K_M, misma configuración que la figura anterior -->

![Escalado del decode dentro de la familia Qwen2.5.](figuras/e2-qwen.png)

El decode está limitado por ancho de banda: de 0.5 B a 8 B el caudal cae 9× (de 71.52 tok/s a 7.75 tok/s), siguiendo de cerca la razón de ~12× en tamaño de pesos. Los saltos de 0.5 B a 3 B se ajustan bien a la predicción; el de 3 B a 7.6 B se queda corto (9.1× frente a 11.8× de razón de pesos), lo que apunta a que la KV cache y el espacio de trabajo de CUDA recortan el ancho de banda efectivo de la LPDDR5 en el extremo pesado.

La arquitectura pesa poco frente al tamaño. En el nivel de 3 B, Qwen2.5 (14.91 tok/s) y Llama (14.60 tok/s) quedan dentro del 2 %; en el de 7–8 B, Mistral, Qwen2.5 y Llama caben en un 8 %.

## Resultados negativos

**La hipótesis de eficiencia (E2.P3) queda falsada.** Se predijo una curva no monótona con óptimo en 2–3 B; lo medido es una eficiencia que decrece de forma monótona con el tamaño, de 11.77 tok/s·W⁻¹ a 0.89 tok/s·W⁻¹. El consumo de plataforma (~5.2 W) no es lo bastante grande como para penalizar a los modelos pequeños y crear el pico previsto.

**El muro de memoria no aparece.** Ningún modelo dio OOM a `n_ctx = 4096`. El margen más fino es el de Llama-3.1-8B, con 5953 MB de pico y 1654 MB libres. La hipótesis de acantilado (E2.P2) no queda ni confirmada ni refutada: para localizarlo hace falta un sub-barrido de contexto, `n_ctx ∈ {2048, 4096, 8192, 16384}`, que queda pendiente.

**Gemma-2-2B es una anomalía de memoria.** Con ~1.63 GB de pesos consume 5818 MB de pico, por encima de Mistral-7B (5488 MB) y Qwen2.5-7B (5465 MB), modelos con casi tres veces más parámetros. La causa probable es su atención alternada local/global: la parte global mantiene una KV cache grande a `n_ctx = 4096`, más un espacio de trabajo CUDA amplio. La consecuencia de despliegue es directa: a igualdad aproximada de parámetros, Qwen2.5-3B (3180 MB) es mucho más eficiente en memoria que Gemma-2-2B.

**Ningún modelo escapa a la presión de zram.** Los diez activan la bandera de swap, pero es zram — swap comprimido en RAM, sin E/S a disco — que ya está parcialmente activo en idle (~11 MB), así que la bandera por sí sola no distingue una unidad de otra. Los picos de swap sí: ~206 MB en el nivel A, 406 MB en Gemma-2-2B, 419 MB en Mistral-7B y 460 MB en Llama-3.1-8B. En las demás unidades el crecimiento sobre idle no se extrajo por separado y el dato queda solo en la telemetría cruda. No hay disco de por medio, pero los ciclos de CPU de compresión son sobrecarga real.

## Conclusiones

El barrido informa lo que la placa puede correr. La lectura de despliegue es que el nivel de 3 B es el tamaño adecuado: ~14.5 tok/s sostenidos con ~3.2 GB de pico en el caso de Qwen2.5-3B, mientras que subir a 7–8 B cuesta la mitad del caudal y deja menos de 1.7 GB de margen de memoria.

**E2.R1**: El decode está limitado por ancho de banda y escala como `1/(bytes de pesos)` — 9× de caída entre 0.5 B y 8 B frente a 12× de razón de pesos. La hipótesis se confirma como efecto dominante, con una desviación secundaria en el extremo pesado (3 B a 7.6 B rinde 9.1× frente a 11.8× previsto), atribuible a la KV cache y espacio de trabajo de CUDA.

**E2.R2**: **No determinado.** No hubo OOM a `n_ctx = 4096`, luego el barrido no llega a tocar el muro; el margen más estrecho es de 1654 MB en Llama-3.1-8B. Para determinarlo hace falta el sub-barrido de contexto sobre ese mismo modelo.

**E2.R3**: Hipótesis falsada. La eficiencia decrece de forma monótona con el tamaño; no hay óptimo de Pareto en 2–3 B. El mejor valor bruto es el de 0.5 B (11.77 tok/s·W⁻¹ neto), y el mejor compromiso entre capacidad y coste sigue siendo el nivel de 3 B (~14.5 tok/s a ~2.0 tok/s·W⁻¹).

**E2.R4**: El TTFT va de 38 ms (0.5 B) a 204 ms (8 B). Los diez modelos responden por debajo de 250 ms, dentro del umbral interactivo, pero con la salvedad de arriba: es un prompt de 12–14 tokens, es decir una cota inferior. Para prompts largos queda pendiente el mismo sub-barrido de contexto.

**E2.R5**: A tamaño fijo la arquitectura es secundaria: 2 % de diferencia en el nivel de 3 B y 8 % en el de 7–8 B. Lo que manda es el tamaño de los pesos. La excepción no es de velocidad sino de memoria.
