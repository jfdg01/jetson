# TODO — pendientes del barrido

Cosas identificadas y aparcadas a propósito. No son hallazgos; son deuda. El autor decide cuáles
se ejecutan.

## Reenganche / redetección

- **Diseño completo de la literatura** (LTMU, SPLT, SiamSTA): disparo por EMA adaptativa del score,
  redetector barato separado, pesado de apariencia 0.9 reciente / 0.1 original. Aquí solo se va a
  construir la versión perezosa (ventana que crece), no la entrenada.
- **SAM2 como verificador ocasional de AsymTrack.** SAM2 tiene `object_score_logits`, una cabeza de
  oclusión *entrenada*; AsymTrack no tiene nada. Combinación ausente de la literatura (ningún
  participante de Anti-UAV usa SAM2). Coste 158 ms, así que solo cabe a baja frecuencia.
- **Señal de oclusión por área de máscara.** Si el área de la máscara de SAM2 cae de golpe, algo se
  ha metido delante. Es información real que llevamos toda la tesis tirando a la basura.
  **Bloqueado en**: no confiamos en la precisión de la máscara de SAM2 lo bastante como para montar
  una heurística sobre ella a ~5 Hz. Hace falta medir primero la estabilidad del área en secuencias
  sin oclusión (si el área ya oscila sola, la heurística es ruido). Nota: 5 Hz es un régimen de
  trabajo válido — es el que se ha usado toda la tesis.

## Geometría de ventana

- **Padding por media de canal** (SiamFC) en vez de ceros. Es una perilla medible, no una obviedad.
- **Factor 6 en AsymTrack aislado.** Entrenado a 4.0, así que 6 es fuera de distribución: mide
  degradación por desajuste entrenamiento/inferencia, no capacidad.
- **Los brazos de frame completo (`family="sam2"`) aplastan** anisótropamente donde la literatura
  hace letterbox (SAM1, SAM2-image, YOLO). Confunde capacidad con distorsión de aspecto.

## Datos

- **TLP** (Track Long and Prolong): las 3 R (re-detección, recuperación, robustez) y las secuencias
  mutiladas. Es el dataset diseñado para lo que aquí se quiere medir; UAV123 solo tiene 2.38% de
  frames ausentes.
- **`dataset.txt` del tercil duro (37 clips)** para el barrido de ventana.

## Retrospectiva

- **`sam2_f5` como brazo de medida**: única forma de contestar si Partes II-VI estaban
  *mal configuradas* en vez de faltas de capacidad. Aplazado por decisión del autor (2026-07-30):
  menos útil que avanzar con los modelos nuevos.
