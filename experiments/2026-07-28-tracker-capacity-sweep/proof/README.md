# proof — TLP, estructura de ausencia

Parte de [`../README.md`](../README.md). Renderizado 2026-08-02T18:40Z (Madrid) sobre las 18
secuencias de TLP que ya estaban en disco (van 50).

Solo GT, sin tracker: todavía no se ha corrido ningún brazo sobre TLP. Verde = caja de GT; borde
rojo y `AUSENTE (isLost=1)` = el GT dice que el objetivo no está. Comando:

```
python analysis/render_overlay.py --seq <Seq> --frames A:B --out proof/<fichero>.mp4
```

Cada `.mp4` va con su `.mid.png`, el fotograma central que se abrió para verificar el render (no el
frame 0, que suele salir negro).

## `tlp_gt__Billiards1_f12950-14250.mp4` — el régimen que UAV123 no tiene

1301 frames, **934 ausentes (72%)**, cuatro huecos seguidos: 227, 80, 177 y 450 frames. El objetivo
es una bola de billar de ~27 px que se pierde detrás de jugadores y de otras bolas.

Contra qué compararlo: el hueco más largo de **todo** UAV123 son 182 frames, y la mediana es de 2
huecos por secuencia. Aquí hay cuatro en 1300 frames y el mayor dobla al récord de UAV123. `.mid.png`
es f13600, el último frame del tercer hueco — la bola reaparece en f13601.

## `tlp_gt__CarChase2_f11600-12700.mp4` — el mismo fenómeno en el dominio de la tesis

1101 frames, 163 ausentes (15%), cuatro huecos: 5, 59, 47 y 52 frames. Persecución policial desde
helicóptero, coche de ~135 px. Es el régimen aéreo de la tesis, con huecos cortos y repetidos en vez
de uno largo.

`.mid.png` es f11605, con la caja sobre el coche que huye (el patrulla va detrás). Dentro del clip,
f11695 muestra la otra cara: la cámara ha barrido y el objetivo está **fuera del encuadre**, no
tapado.

## Lo que estos clips también enseñan, y es un límite

`isLost` es **una sola bandera**. En f11695 el objetivo sale del encuadre; en Billiards1 lo tapa un
jugador. Las dos cosas se etiquetan igual. TLP **no** separa oclusión de salida de campo, igual que
el `NaN` de UAV123 tampoco. La distinción que pide [`../notes/17-...`](../notes) §6 sigue
necesitando LaSOT y sus `full_occlusion.txt` + `out_of_view.txt`.

Y la tasa de ausencia agregada de TLP (2.20% sobre las 18 bajadas) es **igual** a la de UAV123
(2.38%). Lo que TLP aporta no es más ausencia por frame, es más huecos por secuencia y huecos mucho
más largos, sobre secuencias 17 veces más largas.
