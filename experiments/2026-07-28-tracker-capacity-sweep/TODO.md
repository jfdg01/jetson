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

- **Suprimir la escritura en memoria mientras el brazo está `LOST`.** Hoy `Dam4SamLtArm` solo tacha
  la salida: `inner.step` corre igual en todos los frames, así que el frame ocluido entra en el
  banco de memoria de DRM y contamina el condicionamiento de los siguientes. Suprimir la escritura
  es lo que hacen SAMURAI (gate por score de movimiento) y HiM2SAM. **Cuesta GPU y hay que
  testearlo**: a diferencia de la máquina de estados actual, esto cambia lo que ve el modelo, así
  que cierra el lazo y `analysis/lt_sim.py` deja de poder simularlo — se corre en la Jetson o no
  se mide. Necesita tocar el wrapper vendorizado de DAM4SAM (el `output_dict` /
  `memory_bank`), no basta con envolverlo desde fuera.

- **Encoger la rejilla del umbral relativo a ~15 candidatos.** La validación cruzada
  (`notes/15-...`) muestra que 33 secuencias no soportan seleccionar entre 312: solo `b = 2` y la
  ventana móvil salen estables, `k` y `w` bailan por pliegue. Fijar esos dos y barrer solo `a` y `w`
  deja la selección fuera del camino crítico. Coste cero de dispositivo, se re-corre
  `analysis/lt_sim.py`.
- **Puerta para el brazo LT.** El efecto es de cola (tres clips de 33 dan casi toda la ganancia), o
  sea que la política debería activarse condicionalmente, como el 1024 con puerta de tamaño de la
  Parte VI. Falta encontrar un predictor **causal** de "esta secuencia es de las que se benefician".

## Geometría de ventana

- **Padding por media de canal** (SiamFC) en vez de ceros. Es una perilla medible, no una obviedad.
- **Factor 6 en AsymTrack aislado.** Entrenado a 4.0, así que 6 es fuera de distribución: mide
  degradación por desajuste entrenamiento/inferencia, no capacidad.
- **Los brazos de frame completo (`family="sam2"`) aplastan** anisótropamente donde la literatura
  hace letterbox (SAM1, SAM2-image, YOLO). Confunde capacidad con distorsión de aspecto.

## Datos

- **TLP** (Track Long and Prosper): las 3 R (re-detección, recuperación, robustez) y las secuencias
  mutiladas. Es el dataset diseñado para lo que aquí se quiere medir; UAV123 solo tiene 2.38% de
  frames ausentes.

  **REVISAR 2026-08-03.** La cuota de Drive cedió el 2026-08-02 a las ~17:22Z tras 16 pasadas
  en vano, y las secuencias están bajando a ~40 MB/s. Demonio en tmux, sesión `tlp`:

  ```
  tmux attach -t tlp                                  # ver el bucle
  .venv-ft/bin/python experiments/2026-07-28-tracker-capacity-sweep/tools/fetch_tlp.py --status
  ```

  Relanzado 2026-08-02T19:45Z (Madrid), log en `data/TLP/_fetch.log`. Se para solo al
  completar las 50 o si el disco baja de 15 GB. **No sobrevive a un reinicio de la máquina**;
  si la sesión tmux no está, relanzar con
  `tmux new-session -d -s tlp -c <dir del experimento> '../../.venv-ft/bin/python tools/fetch_tlp.py --daemon'`.

  **Siete secuencias pasan de 4 GiB en V2 y `drive.usercontent` las topa**: anuncia
  `Content-Length: 4294967295` = 2^32-1 y sirve exactamente esos bytes; pedir el byte
  4294967295 da **416**, o sea que el servidor cree que el fichero mide eso. No es un corte de
  red — un tar mide siempre múltiplo de 512 y 2^32-1 es impar, así que lo servido no puede ser
  un tar entero nunca. Confirmado además desde dentro del archivo: el GT de `Basketball` lista
  17970 frames y solo llegan 16156 jpg. Afectadas, todas mostradas como "4.0G" en la página de
  aviso: **Basketball, Boxing1, Boxing2, ISS, Parakeet, PolarBear2, Puppies2**.

  **Resuelto con TLP V1** (2026-08-02). Los autores publican dos versiones: V2 (87.2 GB, la que
  apuntaba `tlp_files.json`) y V1 (39 GB, "the resolution is still the same but images are much
  sharper and have higher quality" según su gist). Las secuencias de V1 son `.zip` de 1.6-1.8 GB,
  muy por debajo del tope. `fetch_tlp.py` detecta el tope en la cabecera, **aborta antes de
  transferir** (reintentar costaba 4 GiB por secuencia y por pasada) y cae al `fallback_url` de
  V1; `valid_tar()` y `extract()` aceptan las dos formas y descartan `__MACOSX/`.

  Verificado sobre `Basketball` V1 bajado entero (1728371635 B): 17970 jpg a 1280x720, GT
  idéntico al de V2 byte a byte, PSNR V1 contra V2 25.8 dB con jpg de 105 KB frente a 305 KB.
  O sea, misma geometría y mismas etiquetas, más compresión. **Verificación visual hecha**: caja
  del frame 17951 (x=287,y=349,w=28,h=70) recortada y mirada, cae sobre el jugador.
  Consecuencia para la tesis: las siete van a entrar con calidad de imagen distinta al resto, y
  eso hay que decirlo en cualquier tabla que las mezcle.

  Descartado: usar lo truncado. El orden de los miembros del tar no es alfabético, así que los
  1814 frames que faltan están **repartidos**, no en la cola — no se puede recortar el GT a un
  prefijo. `Basketball.tar.bad` borrado.

  Al revisar, tres desenlaces:
  - **50/50 y `COMPLETO`**: el final bueno. Registrar el dataset en `SOURCES.md`.
  - **Parcial**: cada tar/zip es un clip completo, así que lo bajado sirve tal cual. Dejar el
    demonio a por el resto; reanuda por `Range` los `.part` a medias.
  - **Atascado otra vez en cuota**: es un racionamiento intermitente, no un bloqueo. Dejarlo
    corriendo, no hay nada que arreglar.

  Formato del GT, verificado sobre `Alladin` (8992 frames, 8992 líneas): seis columnas
  `frame,x,y,w,h,ausente`. **La sexta columna es la etiqueta de ausencia por frame** que pide
  `notes/17-...` §6 — es justo lo que UAV123 no da y por lo que se quería este dataset.

  Medido el 2026-08-02 y conviene no volver a tropezar: la cuota **no** dependía de la IP —
  sondeado desde 3090, jetson, garaserver y oracle (dos IP públicas, dos ASN), comportamiento
  idéntico. Y una petición con `Range` acotado de <= 1 MB devuelve 206 con bytes reales aunque
  la cuota esté agotada, así que "llegan los primeros KB" es un falso positivo: solo cuenta
  pedir el fichero entero.

  **Alternativa si esto se tuerce:** LaSOT en HuggingFace (`l-lt/LaSOT`), sin cuota, por
  categorías, con `full_occlusion.txt` + `out_of_view.txt`. Separa oclusión de salida de frame,
  cosa que TLP con una sola bandera no hace.
- **`dataset.txt` del tercil duro (37 clips)** para el barrido de ventana.

## Retrospectiva

- **`sam2_f5` como brazo de medida**: única forma de contestar si Partes II-VI estaban
  *mal configuradas* en vez de faltas de capacidad. Aplazado por decisión del autor (2026-07-30):
  menos útil que avanzar con los modelos nuevos.
