# IDEAS

para mitigar la perdida del sujeto:
* pasarle a la VLM donde estaba el objeto justo antes de lanzarse
* hacer la VLM más rápida

para avanzar:
* engacharlo a un simulador (unity?)
* reentrenar en dataset más especifico (SOT)

# VLM speed — sub-1-sec anchor (¿merece la pena?)

Medido en el Orin (15 W, 512 long-edge, deploy real): **2.27 s/anchor**, partido casi
a la mitad:
* prefill 1113 ms — CLIP image encode, escala ~lineal con píxeles
* decode 1106 ms — 24 tokens de salida @ 21.7 tok/s, independiente de resolución

Sub-1-sec = 2.27 s → <1.0 s ≈ **2.3× en ambas mitades**. Ninguna mitad sola llega.

**Veredicto honesto:** la arquitectura v3 existe *porque* la VLM es lenta (tracker 20 Hz
sostiene el lock, VLM ancla de forma dispersa). T3/T4 ya PASAN con re-anchor por evento a
2.27 s. La latencia es la *premisa* del capítulo, no un bug. **Recomendación: no hacerlo**
salvo que aparezca una necesidad concreta.

Palancas, de menos a más esfuerzo:
1. **Recortar decode (~0.5 s, lo más barato).** La salida es un bbox = 4 números pero
   cuesta 24 tokens. Formato más corto / menos decimales → corte casi lineal: 1.1 s → ~0.6 s.
   Toca solo `contract.py` (prompt + `parse_bbox`), sin modelo ni GPU. Rompe el test
   byte-identical del contrato. Llega a ~1.7 s, **no** sub-1 por sí solo.
2. **Prefill sobre ROI (solo re-anchor, sí llega a sub-1).** En un re-anchor ya tienes la
   última caja del tracker. Pasar a la VLM un recorte (~256 px) en vez del frame completo
   640×480 → prefill se desploma. ~0.3 s prefill + ~0.5 s decode ≈ **0.8 s**. Pero: solo
   re-anchor (no adquisición en frío); un recorte no puede re-encontrar un objeto que salió
   del ROI — justo el caso de oclusión/re-ID que T2 resuelve. Choca con el problema difícil.
3. **Modelo ancla más pequeño.** SmolVLM-500M ya iba a ~1.2 Hz (0.83 s) — sub-1 de fábrica.
   Pero Part II eligió Qwen2-VL-2B *por precisión* (62.6% IoU). Cambiarlo sacrifica el número
   titular. Medible, no gratis.

**Experimento limpio para la tesis si pica el gusanillo:** medir la palanca #1
(recorte de decode) — resultado honesto "cortamos tokens de salida, decode bajó X%, coste
en precisión Y". Documenta la palanca sin comprometer el loop.

# GUI

* mejorar la ux
