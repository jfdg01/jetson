# proof — TLP, estructura de ausencia

Parte de [`../README.md`](../README.md). Renderizado 2026-08-02T19:10Z (Madrid) sobre las 18
secuencias de TLP que ya estaban en disco (van 50).

Solo GT, sin tracker: todavía no se ha corrido ningún brazo sobre TLP. Verde = caja de GT; borde
rojo y `AUSENTE (isLost=1)` = el GT dice que el objetivo no está.

## Los 18 clips completos — `tlp_gt__<Seq>.mp4`

```
analysis/render_tlp_all.py            # 18 clips, ~95 s en total
```

Cada clip recorre la secuencia **entera**, pero acelerada: 245k fotogramas son 2.3 h de vídeo, así
que cada uno se reduce a ~900 fotogramas dibujados (30 s a 30 fps) con `--stride`, 640 px de ancho.
El stride **no es ciego**: dentro de cada grupo de N prefiere un fotograma ausente, así que un hueco
más corto que el stride sigue apareciendo en vez de saltarse. Comprobado: el único hueco de
Aquarium1 (12 fotogramas, stride 8) sale en 3 fotogramas del clip. El pie de imagen lleva siempre el
**número absoluto** de fotograma, no el del clip.

| Secuencia | Frames | Huecos | Hueco máx | Obj. mediano (px) | Ausente |
| --- | ---: | ---: | ---: | ---: | ---: |
| Billiards2 | 20070 | 29 | 453 | 39 | 6.36% |
| Billiards1 | 20375 | 36 | 450 | 27 | 9.02% |
| Badminton1 | 15240 | 5 | 145 | 165 | 2.55% |
| BreakfastClub | 22600 | 2 | 97 | 104 | 0.63% |
| CarChase3 | 22860 | 20 | 78 | 123 | 3.21% |
| IceSkating | 8125 | 4 | 67 | 102 | 1.14% |
| CarChase2 | 14010 | 23 | 59 | 135 | 4.69% |
| Bike | 4192 | 4 | 42 | 137 | 2.22% |
| Jet1 | 7403 | 1 | 28 | 55 | 0.38% |
| CarChase1 | 8932 | 7 | 28 | 153 | 1.46% |
| Aquarium1 | 7337 | 1 | 12 | 69 | 0.16% |
| Bharatanatyam | 15936 | 0 | 0 | 53 | 0.00% |
| Basketball | 17970 | 0 | 0 | 82 | 0.00% |
| Aquarium2 | 8182 | 0 | 0 | 85 | 0.00% |
| Badminton2 | 16920 | 0 | 0 | 99 | 0.00% |
| Boxing3 | 19590 | 0 | 0 | 151 | 0.00% |
| Boat | 6234 | 0 | 0 | 201 | 0.00% |
| Alladin | 8992 | 0 | 0 | 231 | 0.00% |

Las 6 de cero huecos no sobran: son el control que separa la deriva del re-enganche. Un brazo que
pierde el objetivo en Alladin (231 px, siempre visible) lo pierde por deriva, no por ausencia.

Lo que se ve al abrirlos, y que la tabla no dice:

- **Jet1** son ocho aviones idénticos en formación (`.mid.png`, f3705). No es un objetivo pequeño
  sobre cielo vacío: es el peor caso de distractores del conjunto.
- **CarChase1/2/3** es el dominio de la tesis — vídeo aéreo, coche de ~130 px sobre autopista con
  decenas de coches iguales (`tlp_gt__CarChase3.mid.png`, f11426).
- **Billiards1/2** tiene los objetivos más pequeños (27 y 39 px) y los huecos más largos.
- **Alladin**, **BreakfastClub** y **Bharatanatyam** son teatro/danza: objetivo grande, fondo oscuro,
  varias personas con la misma silueta.

Cada `.mp4` va con su `.mid.png`, el fotograma central que se abrió para verificar el render (no el
frame 0, que suele salir negro). Se abrieron Bike, Billiards2, CarChase3, Jet1, Alladin y
BreakfastClub, más un fotograma ausente extraído del `.mp4` de Aquarium1 para comprobar que el borde
rojo sobrevive al stride.

## Dos clips a resolución y ritmo reales

Los de arriba están acelerados; estos dos van fotograma a fotograma sobre una ventana concreta, para
ver el hueco tal cual ocurre.

```
python analysis/render_overlay.py --seq <Seq> --frames A:B --out proof/<fichero>.mp4
```

### `tlp_gt__Billiards1_f12950-14250.mp4` — el régimen que UAV123 no tiene

1301 frames, **934 ausentes (72%)**, cuatro huecos seguidos: 227, 80, 177 y 450 frames. El objetivo
es una bola de billar de ~27 px que se pierde detrás de jugadores y de otras bolas.

Contra qué compararlo: el hueco más largo de **todo** UAV123 son 182 frames, y la mediana es de 2
huecos por secuencia. Aquí hay cuatro en 1300 frames y el mayor dobla al récord de UAV123. `.mid.png`
es f13600, el último frame del tercer hueco — la bola reaparece en f13601.

### `tlp_gt__CarChase2_f11600-12700.mp4` — el mismo fenómeno en el dominio de la tesis

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

Faltan 32 secuencias por bajar. Los nombres describen la escena, no la dificultad: `Basketball`
tiene 17970 fotogramas y **cero** huecos.
