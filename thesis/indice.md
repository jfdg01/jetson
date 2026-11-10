---
title: Índice de la tesis (borrador)
locale: es
cover: false
toc: false
numbering: false
figure_index: false
table_index: false
code_index: false
acronym_index: false
---

El índice sigue los apartados que los criterios de la EPSJ piden a un trabajo experimental: Introducción, Antecedentes, Objetivos, Material y Métodos, Resultados y Discusión, Conclusiones, Anexos y Bibliografía. Las páginas preliminares salen de la carátula obligatoria, de la documentación para CREA y de `declaracion-ia.md`.

Cada sección lleva su fuente en el repo y uno de estos estados:

- **vacía**: la sección no tiene texto.
- **semilla**: un texto del repo sirve de base a la sección, y todavía no está escrito para la tesis.
- **preliminar**: el texto de la sección está escrito y editado por el autor, y espera la confirmación del tutor.
- **aprobada**: el tutor confirmó el texto. Es el estado final.

## Páginas preliminares

- Carátula de máster de la EPSJ. **vacía**
- Primera página: los datos de la carátula, la firma del autor y el visto bueno del tutor. **vacía**
- Resumen y *summary*, de 150 palabras como máximo cada uno. **vacía**
- Declaración de uso de herramientas de IA. Fuente: `declaracion-ia.md`. **preliminar**
- Índice general, índice de figuras, índice de tablas e índice de bloques de código. Se generan.

## 1. Introducción

- 1.1 La motivación: un dron que sigue un objetivo descrito en lenguaje natural, con todo el cómputo a bordo. **vacía**
- 1.2 El problema: un VLM en una placa *edge* tarda segundos, y el objetivo se mueve mientras tanto. **vacía**
- 1.3 Las contribuciones. Depende de la tesis central. **vacía**
- 1.4 La estructura del documento. Se escribe al final. **vacía**

## 2. Antecedentes

- 2.1 Los LLM y los VLM locales, y la cuantización. **vacía**
- 2.2 El *grounding* visual de una expresión, y los conjuntos de datos aéreos: RefDrone y UAV123. **vacía**
- 2.3 El seguimiento de objetos: ByteTrack y SAM2. **vacía**
- 2.4 La simulación de vuelo: ArduCopter SITL, MAVLink, Gazebo y CARLA. **vacía**

## 3. Objetivos

- 3.1 El objetivo general. **vacía**
- 3.2 Los objetivos específicos, uno por pregunta de investigación. Fuente: `docs/questions/`. **vacía**

## 4. Material y métodos

- 4.1 La plataforma: la Jetson, JetPack, el modo de 15 W y `jetson_clocks`. Semilla: `notas/parte1-01-puesta-en-marcha.md`, sección «Configuración de la Jetson». **semilla**
- 4.2 La pila de *software*: llama.cpp, los modelos y sus cuantizaciones, SAM2. **vacía**
- 4.3 Los datos: RefDrone, UAV123 y las escenas de CARLA. **vacía**
- 4.4 Las métricas: IoU@0,25, la latencia de la adquisición y la entrega. **vacía**
- 4.5 El banco de vuelo en lazo cerrado: `runners/run_phase_c.py`. **vacía**
- 4.6 El método estadístico: la unidad de independencia, las familias de Holm y el registro de *claims*. Semilla: `01-metodo-estadistico.md`. **semilla**
- 4.7 El preregistro de los experimentos. **vacía**

## 5. Resultados y discusión

Una sección por Parte, en orden cronológico. Cada sección abre con su pregunta, su método propio y su veredicto, y cada número sale de `claims.json` y de `stats-report.md`.

- 5.1 La exploración de la placa y el primer ajuste fino (Parte I). Semilla: `notas/parte1-01-puesta-en-marcha.md`, sección «Primera toma de contacto». **semilla**
- 5.2 El *grounding* de un solo *frame* (Parte II). **vacía**
- 5.3 La permanencia del objeto (Parte III). **vacía**
- 5.4 El flujo completo y el arco de la latencia de la adquisición (Parte IV). **vacía**
- 5.5 El *grounding* anticipatorio y el arranque en caliente (Parte V). **vacía**
- 5.6 El vuelo en lazo cerrado (Parte VI). **vacía**
- 5.7 La discusión de conjunto: mantener y entregar, no seleccionar. **vacía**
- 5.8 Las amenazas a la validez. **vacía**

## 6. Conclusiones

- 6.1 La respuesta a cada objetivo específico. **vacía**
- 6.2 Las limitaciones. **vacía**
- 6.3 El trabajo futuro: la selección como propuesta medida y la prueba en un dron real. **vacía**

## Anexos

- A. La reproducibilidad: los comandos, las versiones y el entorno. **vacía**
- B. El registro estadístico completo. Fuente: `claims.json` y `stats-report.md`. **vacía**

## Bibliografía

Fuente: `refs.bib`.
