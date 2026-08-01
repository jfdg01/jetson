# Barrido completo DAM4SAM: escalera 640/768/960

Parte de [`../README.md`](../README.md).

## Barrido completo de DAM4SAM: la escalera 640/768/960 (run `dam-full30b`, 2026-07-30T22:20Z)

90 corridas: 30 secuencias x 3 resoluciones, 27.276 frames, 7 h 20 min de dispositivo. Es el
barrido que la sección anterior dejaba pendiente, y **corrige a la baja** su lectura a n=5.

### Por qué 768 y 960 en vez de 1024 (decisión del autor, 2026-07-30T15:40Z)

1024 es una resolución que no se desplegaría: 431 ms en la Jetson, y el redimensionado cuadrado
**sube** el eje vertical (720 -> 1024) mientras baja el horizontal (1280 -> 1024). Se sustituye por
una escalera 640/768/960. Hiera solo exige que `image_size` sea múltiplo de 32 — 704, 768, 896 y
960 son todos legales.

La latencia es lineal en **píxeles**, no en el lado. Ajuste sobre los tres puntos ya medidos
(512 -> 146.8, 640 -> 197.9, 1024 -> 431.3 ms): `p50 ~ 56 + 0.357*n^2/1000 ms`, que reproduce los
tres dentro de 3 ms. Predijo 768 -> 267 ms y 960 -> 385 ms.

**Humo de las dos resoluciones nuevas** (`raw/dam-sz-smoke/`, `truck3`), que valida el ajuste antes
de gastar 7 h:

| brazo | p50 medido | p50 predicho | mIoU | @0.5 | AUC |
| --- | --- | --- | --- | --- | --- |
| `dam4sam_t512` | 147.5 | 146 | 0.640 | 0.783 | 63.2 |
| `dam4sam_t768` | 262.1 | 267 | 0.770 | 0.931 | 75.6 |
| `dam4sam_t960` | 393.2 | 385 | 0.828 | 1.000 | 81.1 |

### Resultado

Medianas sobre las 30 secuencias, salvo AUC (media, como el resto del documento). Se añade la
**media** de mIoU porque es la que casa con los contrastes pareados de abajo.

| brazo | p50 ms | mIoU med | mIoU media | @0.25 | @0.5 | perdidos | FP en hueco | AUC | init | pico GPU |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `dam4sam_t640` | 204.0 | 0.678 | 0.597 | 0.966 | 0.846 | 0.0% | 336 | 56.9 | 7.3 s | 413-1283 MB |
| `dam4sam_t768` | 275.9 | 0.744 | 0.639 | 0.988 | 0.950 | 0.0% | 246 | 60.8 | 7.4 s | 496-1747 MB |
| `dam4sam_t960` | 407.2 | 0.770 | 0.674 | 0.996 | 0.961 | 0.0% | 277 | 63.5 | 7.4 s | 653-2603 MB |

La escalera es monótona y significativa. Wilcoxon pareado sobre las 30 secuencias:

| paso | delta medio | delta mediano | gana / pierde / empata | p |
| --- | --- | --- | --- | --- |
| 640 -> 768 | +0.042 | +0.015 | 19 / 6 / 5 | 0.0087 |
| 768 -> 960 | +0.035 | +0.015 | 18 / 5 / 7 | 0.0010 |
| 640 -> 960 | +0.077 | +0.035 | 23 / 6 / 1 | <0.0001 |

mIoU por secuencia:

| seq | 640 | 768 | 960 |
| --- | --- | --- | --- |
| `bike1` | 0.896 | 0.908 | 0.908 |
| `bike2` | 0.023 | 0.064 | 0.045 |
| `bird1_1` | 0.077 | 0.098 | 0.372 |
| `bird1_3` | 0.133 | 0.097 | 0.364 |
| `boat3` | 0.904 | 0.893 | 0.889 |
| `boat6` | 0.803 | 0.799 | 0.783 |
| `building5` | 0.456 | 0.424 | 0.552 |
| `car12` | 0.690 | 0.714 | 0.742 |
| `car16_1` | 0.862 | 0.878 | 0.883 |
| `car1_3` | 0.608 | 0.624 | 0.640 |
| `car8_2` | 0.939 | 0.942 | 0.950 |
| `car9` | 0.823 | 0.835 | 0.850 |
| `group1_2` | 0.826 | 0.815 | 0.819 |
| `group2_3` | 0.665 | 0.726 | 0.705 |
| `person18` | 0.586 | 0.770 | 0.770 |
| `person19_3` | 0.322 | 0.771 | 0.770 |
| `person20` | 0.844 | 0.842 | 0.836 |
| `person21` | 0.000 | 0.196 | 0.258 |
| `person4_1` | 0.808 | 0.807 | 0.806 |
| `truck2` | 0.733 | 0.760 | 0.782 |
| `truck3` | 0.755 | 0.770 | 0.828 |
| `uav1_2` | 0.572 | 0.680 | 0.668 |
| `uav2` | 0.659 | 0.588 | 0.642 |
| `uav3` | 0.220 | 0.220 | 0.245 |
| `uav5` | 0.595 | 0.697 | 0.750 |
| `uav7` | 0.176 | 0.310 | 0.322 |
| `wakeboard1` | 0.812 | 0.824 | 0.846 |
| `wakeboard5` | 0.604 | 0.564 | 0.587 |
| `wakeboard7` | 0.807 | 0.822 | 0.842 |
| `wakeboard8` | 0.703 | 0.728 | 0.770 |

### Lecturas

**1. La media miente sobre la forma: la ganancia es bimodal, no un gradiente.** En 22 de las 30
secuencias, subir de 640 a 960 mueve la mIoU **+0.036** — ruido caro, 203 ms por él. Toda la señal
está en las 8 donde 640 **colapsa** (mIoU < 0.5: `bike2`, `bird1_1`, `bird1_3`, `building5`,
`person19_3`, `person21`, `uav3`, `uav7`), donde el delta medio es **+0.190**. La resolución no
está afinando cajas; está evitando que el tracker suelte el objeto.

**2. Pero rescata poco.** De esas 8 colapsadas, 960 solo sube **2** por encima de 0.5. `bike2`
sigue en 0.045, `uav3` en 0.245, `uav7` en 0.322. La resolución convierte algún fallo catastrófico
en fallo parcial y no toca el resto.

**3. La mediana de la tabla exagera el escalón 768 -> 960.** 0.744 -> 0.770 parece +0.026 limpio,
pero el delta mediano pareado es +0.015 y cinco secuencias empeoran.

**4. El tamaño del objetivo no explica quién gana.** La hipótesis obvia — objetivos pequeños
necesitan más píxeles — no aguanta: Spearman entre área mediana de GT y ganancia 640 -> 960,
rho = -0.30, p = 0.10. `person18` mide 36.608 px de mediana y gana +0.184; `uav2` mide 104 px y
pierde -0.018. La partición útil es *colapsa / no colapsa*, no *pequeño / grande*.

**5. Coste.** 768 cuesta +72 ms sobre 640 y entrega +0.042; 960 cuesta +131 ms más y entrega
+0.035: la mitad de eficiente. Si hay que elegir un punto, **768 es el codo** — p50 276 ms, @0.5 de
0.950 frente a 0.846 en 640, y 131 ms más barato que 960.

**6. Ningún brazo se abstiene nunca.** `perdidos` es 0.0% en los tres y los FP en hueco
(336 / 246 / 277) no bajan monótonamente con la resolución. DAM4SAM emite caja en **todos** los
frames de ausencia — el mismo fallo ya anotado para `asym_b`. La resolución no compra nada en el
eje de presencia. Y como estos brazos **no emiten `conf`** (el plumbing de presencia cubrió SAM2 y
AsymTrack, no las familias añadidas después), `analysis/presence.py` falla sobre este run con
`no arm in raw/dam-full30b recorded a conf signal`: ese eje sigue **sin medir** para DAM4SAM.

**7. Frente al incumbente, la lectura de n=5 no sobrevive.** Sobre las 25 secuencias comunes con
`c640pad` (`sam2_c640_pad` es un brazo *recortado*, así que es indicativa, no pareada en geometría):

| brazo | mIoU media | mIoU mediana |
| --- | --- | --- |
| `sam2_c640_pad` (incumbente) | 0.682 | 0.787 |
| `dam4sam_t640` | 0.627 | 0.733 |
| `dam4sam_t768` | 0.667 | 0.770 |
| `dam4sam_t960` | 0.704 | 0.782 |

**DAM4SAM a frame completo no bate al incumbente recortado hasta 960**, y ahí lo hace por +0.022 de
media a costa de 2x la latencia. A n=5 empataba a 640; lo que ganaba entonces era en buena parte la
selección de clips. El titular del proyecto se mantiene: **el recorte compra más que los píxeles**.

### `bike2`: no hay ganador, y es geometría

24 corridas medidas sobre `bike2` en todo el barrido. La mejor es `sam2_f5_floor` con mIoU 0.246 y
@0.25 = 0.475 — el menos malo, no un ganador. Le siguen `sam2_f5` 0.176, `asym_b` 0.149,
`sam2_c704` 0.123, `sam2_c640_pad` 0.122; DAM4SAM aparece en 0.064 (768) y 0.045 (960), y
`sam2_t1024` cierra en 0.040.

El GT explica por qué: el objetivo mide **11 x 14.5 px de mediana** (área 143 px, mínimo 52) sobre
un frame de 1280x720, y se desplaza 1.0 px por frame; 35 de los 553 frames son ausencia. Metido
cuadrado en 640 queda en ~5.5 x 12.9 px. Dentro de los brazos de frame completo la mIoU **baja**
monótonamente al subir resolución (768 -> 0.064, 960 -> 0.045, 1024 -> 0.040): con el objeto a 5 px
cualquier distractor del fondo gana el mapa de máscara, y más resolución le da más textura al
distractor. `bike2` es un caso para brazo recortado con re-anclaje, no una pregunta de resolución.

### Verificación visual

10 overlays renderizados desde `raw/dam-full30b/` y entregados al autor: los tres rescates pareados
640 vs 960 (`person19_3`, `bird1_1`, `person21`), tres fallos duros a 960 (`bike2`, `uav3`,
`uav2`) y un control (`car8_2`@960). Cinco mid-frames abiertos y comprobados:
`person19_3`@640 marca `LOST` en el frame 784/1567 mientras `person19_3`@960 va con IoU 0.88 en ese
mismo frame; `bike2`@960 da IoU 0.00 en 277/553 con la predicción anclada en la orilla;
`person21`@640 marca `LOST` en 244/487; `uav2`@960 es un clip de 720x480 sobreexpuesto, dron blanco
sobre cielo blanco. De los otros cinco solo se afirman los números, no lo que se ve.

### Estado de SAMURAI

`raw/sam-5x3/` (5 clips x 3 resoluciones) está corrido y sin documentar. El barrido completo
`sam-full30` se lanzó con la misma escalera 640/768/960 y **el autor lo canceló a los 3 jobs**;
los tres resultados parciales quedan en `raw/sam-full30/`. Los brazos `samurai_t768` y
`samurai_t960` ya están registrados y sincronizados.
