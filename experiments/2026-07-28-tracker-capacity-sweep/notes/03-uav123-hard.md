# Barrido difícil UAV123-hard (matado), heurísticas y auditoría del índice

Parte de [`../README.md`](../README.md).

## Barrido difícil: UAV123-hard, 49 secuencias x 6 arms (run `uav123-hard`, MATADO 2026-07-29)

**Este run se mató a mitad y sus resultados se borraron del dispositivo. Ninguna cifra suya
existe.** Motivo del corte: el análisis de la sección "Región de búsqueda" mostró que los 6 brazos
comparten el mismo defecto —ventana de tamaño fijo, no escalada al objetivo—, así que el barrido
medía seis variantes de una sola decisión equivocada. Se conserva la sección porque el **diseño del
dataset** sigue vigente y lo reutilizan los experimentos de abajo.

**Dataset `UAV123-hard`** (`dataset.txt`, construido por `analysis/difficulty.py` sobre las 123):
41 clips = el tercil difícil **entero**, no una muestra, así que no hay selección que explicar; más
**4 MEDIO + 4 FÁCIL como control de banda**, uno por categoría y solo entre categorías que también
aparecen en la banda difícil — sin ese emparejamiento, "difícil contra fácil" sería en parte "uav
contra boat", porque índice y categoría están confundidos en UAV123 (10/10 `uav` caen en difícil,
0/9 `boat`). Total 49 clips, 41461 frames anotados: uav 10, car 10, person 7, group 6, wakeboard 6,
truck 4, bird 3, bike 3.

**Sin `sam2_t1024`,** descartado por coste: 434 ms de p50 sin ganar a nadie. Wilcoxon pareado sobre
las 30 de `full-sweep-30`, mIoU de `t1024` menos la del rival — `c640` p=0.79 (-0.017), `c704`
p=0.30 (-0.036), `t768` p=0.12 (+0.014), `t640` p=0.064 (+0.050). Contra los dos brazos de crop el
signo es negativo: paga 2.3-2.7x de latencia para ir por detrás. **Nulo acotado, no equivalencia.**

Limitaciones que se declararon antes de correr y que siguen aplicando a cualquier reutilización del
dataset: 41 contra 4 contra 4 **no da contraste inferencial entre bandas** (los 8 controles sirven
para mirar si el índice ordena, no para un test); la muestra está sesgada a difícil por
construcción, así que ninguna cifra sacada de aquí estima el rendimiento en UAV123; y 10 de los 49
son 720x480, todos de la categoría `uav`, la más representada en la banda difícil — ahí el crop no
es a píxeles nativos y el sesgo cae entero sobre una categoría.

## Heurísticas de recuperación (implementadas, sin correr, 2026-07-29T14:20Z)

Dos formas de recuperar un objetivo perdido en modo crop. Cada una en su **propio brazo** para poder
atribuir cualquier diferencia; `sam2_c640` sin tocar es el control. Solo sobre 640, el mejor crop.

`sam2_c640_coast` — al perder el objetivo, la ventana sigue deslizándose en la dirección reciente en
vez de congelarse. Velocidad = **mediana** del paso de centro de los últimos 7 aciertos (una caja
mala no puede lanzar la ventana al otro lado) y solo pares de frames consecutivos (un salto sobre un
hueco es un teletransporte, no una velocidad). Mueve la **ventana**, no emite caja: una caja
extrapolada durante una oclusión real es un falso positivo garantizado y `aggregate.py` los cuenta.
Presupuesto: deja de deslizar cuando ha recorrido un ancho de ventana — sin constante que ajustar.
Ataca el fallo medido en `car12`, donde una pérdida congela la ventana y el brazo no vuelve a ver el
objetivo (450/499 frames perdidos).

`sam2_c640_edge` — si el último avistamiento estaba a menos de un tamaño-de-objetivo del borde
**real** del frame y luego se pierde, pasa a frame completo hasta reenganchar. Cerca del borde una
pérdida suele significar que el objetivo salió de campo, y la ventana está mirando justo el único
sitio donde no puede estar. Frame completo = el mismo predictor sin recortar (o sea, el
comportamiento de `sam2_t640`), no se carga un segundo modelo. El enganche ocurre un frame después
de la pérdida: el recorte se elige antes de correr el modelo, así que es lo más pronto posible.

Riesgo declarado en `edge`: el memory bank de SAM2 va lleno de features encuadradas en recorte y el
salto de encuadre es brusco. Eso es exactamente lo que mediría el experimento.

Verificación sin GPU en `device/trackers.py --self-check`: geometría del coast (incluido `coast=0`
como control de congelación) y el enganche de borde, con un `Scripted` inner que puede perder a
voluntad. `render_overlay.py` solo asserta ya los frames derivables — tras una pérdida la ventana
depende de estado que el host no ve — y en modo full encuadra el frame entero en lugar de dibujar un
recorte que el modelo no recibió.

Estado: implementadas y commiteadas, **sin lanzar**. Guardadas para más adelante.

## Auditoría del índice de dificultad (2026-07-29T14:20Z)

`analysis/index_search.py` audiciona 14 ejes candidatos solo-GT y busca subconjuntos, validando por
leave-one-out contra la mIoU mediana cross-arm de las 30 secuencias de `full-sweep-30`.

Resultado: **no hay mejora barata**. El índice actual (`size_px+motion+gap`) da rho=-0.743 sin haber
seleccionado nada. La mejor búsqueda libre llega a -0.793 en muestra pero **-0.694 en LOO**; una
familia acotada a size x motion x gap (27 combinaciones) llega a -0.777 pero **-0.734 en LOO**. Toda
selección valida peor que no seleccionar. Los tres ejes correlan 0.5-0.8 entre sí, así que un cuarto
eje no aporta grados de libertad, solo ruido.

Descartados por no aportar: `roam` (-0.288, p=0.12), `scale_range`, `scale_jitter`, `aspect_jitter`.
`gap` y `gap_max` correlan 1.00 en rango: la variante da igual. `edge_frac` sale con signo invertido
(+0.375) — más contacto con el borde es *más fácil*, porque son los objetivos grandes los que lo
tocan.

Único cambio con argumento a priori: `size_px` -> `size_min` (un tracker falla en el peor momento del
clip, no en el mediano), rho -0.743 -> -0.771, gana en 78% de remuestreos pero IC95 bootstrap
[-0.128, +0.065] cruza cero y solo mueve 1 clip de 41 del tercil difícil. **No adoptado**: dentro del
ruido y obligaría a retocar un dataset ya en cola.

Salvedad: n=30 y muestra sesgada a difícil, así que el rango restringido comprime rho. Reevaluar con
los 49 de `UAV123-hard`.
