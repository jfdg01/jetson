# Deliverables

- **`smoke_truck3_bf16.mp4`** — `sam2_t1024 × truck3`, run `smoke-truck3-bf16`, bf16 autocast,
  15 W mode 0. GT en verde al 60% de alfa, salida del modelo en azul claro, IoU por frame en el
  pie. Inicializado con la caja GT del frame 0 y propagación pura después: el modelo no vuelve a
  ver GT en ningún momento. Muestra que el rig funciona extremo a extremo y que el arm mantiene el
  camión durante los 535 frames (IoU medio 0.779, 0 pérdidas).
- **`smoke_truck3_bf16_frame268.png`** — frame 268/535 del mismo run, extraído a mitad de
  secuencia (nunca el frame 0, que suele salir negro en renders fallidos). Verificación visual
  obligatoria antes de afirmar nada sobre los píxeles.

Reproducir: `analysis/render_overlay.py raw/smoke-truck3-bf16/sam2_t1024__truck3.json --out <mp4>`.
