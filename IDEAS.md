# IDEAS

para mitigar la perdida del sujeto:
* pasarle a la VLM donde estaba el objeto justo antes de lanzarse
* hacer la VLM más rápida

para avanzar:
* engacharlo a un simulador (unity?)
* reentrenar en dataset más especifico (SOT)
  → **VisDrone-SOT** (local en `./VisDrone/`): NO sirve para reentrenar el anchor
    (sin lenguaje, sin clase). Solo serviría como eval real de permanencia en T1/T2
    (86 secs aéreas + flags oclusión/out-of-view). Idea aparcada, no es el reentreno.

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
1. **Recortar decode (~0.5 s, barato pero NO gratis — exige reentrenar).** La salida es un
   bbox = 4 números pero cuesta ~24 tokens, casi todo andamiaje JSON: `{"bbox": [x1, y1, x2,
   y2]}` (`contract.py:62`). Ojo: los coords **ya son enteros** 0–1000, no hay decimales que
   recortar — la palanca es quitar el JSON (formato terso tipo `123 456 234 567`): ~24 → ~10
   tok, decode 1.1 s → ~0.6 s (estimado, no medido). Llega a ~1.7 s, **no** sub-1 por sí solo.
   **Corrección importante:** *no* "toca solo `contract.py` sin modelo ni GPU". El modelo
   desplegado aprendió a emitir esa cadena exacta (`trainer.py:96` supervisa `json.dumps({"bbox"
   : ...})` y enmascara lo demás), así que cambiar el prompt + `parse_bbox` no ahorra ni un
   token por sí solo — el modelo seguiría escribiendo el JSON largo. Bajar el decode de verdad
   = cambiar el target de entrenamiento → **re-LoRA (Phase 3) en la 3090 → re-export GGUF
   (Phase 4) → re-deploy**. Rompe el test byte-identical del contrato. Si se paga un re-LoRA,
   meter en el mismo ciclo cualquier otro cambio de formato/resolución pendiente.
   → Plan completo y contexto para arrancar en conversación nueva:
   `results/2026-06-25-terse-output-retrain/README.md`.
2. **Prefill sobre ROI (solo re-anchor, sí llega a sub-1).** En un re-anchor ya tienes la
   última caja del tracker. Pasar a la VLM un recorte (~256 px) en vez del frame completo
   640×480 → prefill se desploma. ~0.3 s prefill + ~0.5 s decode ≈ **0.8 s**. Pero: solo
   re-anchor (no adquisición en frío); un recorte no puede re-encontrar un objeto que salió
   del ROI — justo el caso de oclusión/re-ID que T2 resuelve. Choca con el problema difícil.
   **Bonus inesperado:** el recorte fed al presupuesto 512 = super-resolución sobre el target
   → ataca el techo de resolución (Part II constraint #2), puede *subir* IoU, no solo bajar
   latencia. Sin reentreno (transformación de imagen + coords, no toca modelo).
   → ✅ **VALIDADO (2026-06-26, GATE PASS).** No es trade-off: el recorte tight (M=2.0) fed a
   512 es **2.7× más barato en prefill (1374 vs 3691 ms Orin Q8_0) Y +22.6 pp más preciso
   (85.2% vs 62.6%)**. El "bonus" era el efecto dominante — el frame completo *bajado* a 512 se
   desploma a 15.9% (el techo de resolución, medido directo). Decode sin cambios (~964 ms, se
   apila con el terse). Robusto a drift del prior ≤0.5·caja. Config deploy: M=2.0 @512.
   → Resultados: `results/2026-06-25-roi-crop-anchor/README.md`.
3. **Modelo ancla más pequeño.** SmolVLM-500M ya iba a ~1.2 Hz (0.83 s) — sub-1 de fábrica.
   Pero Part II eligió Qwen2-VL-2B *por precisión* (62.6% IoU). Cambiarlo sacrifica el número
   titular. Medible, no gratis.

**Experimento limpio para la tesis si pica el gusanillo:** medir la palanca #1
(recorte de decode) — resultado honesto "cortamos tokens de salida, decode bajó X%, coste
en precisión Y". Documenta la palanca sin comprometer el loop.

# GUI

* mejorar la ux
