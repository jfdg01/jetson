# 22. `person18` no falla en SAM2: falla en `c512`

Parte de [`../README.md`](../README.md).

**Cuándo:** 2026-08-03T00:00Z -> 00:20Z (hora local de Madrid).
**Coste:** 0 h de dispositivo — reanálisis por brazo de `raw/paced-sweep-30/` + dos renders.
**Datos:** `raw/paced-sweep-30/`, clips en `proof/foh__person18_c640.mp4` y `proof/foh__person20.mp4`
**Código:** `b188ee6` (`analysis/render_foh.py`).

> **Acotada por la nota 26** (2026-08-04): la explicación por contexto de recorte se confirma en
> `person18` (0.239 -> 0.782 ensanchando solo la ventana, con la misma entrada de 512, con
> verificación visual) y **no** se sostiene en agregado sobre los 25 clips. Ver
> [`26-ventana-contra-entrada.md`](26-ventana-contra-entrada.md) §4 y §6.

## 1. Por qué existe

La nota 21 cerró que `person18` es un fallo de **escala**: la caja cubre las piernas, alto pred/GT
mediano 0.45. Se midió sobre `sam2_c512` y se atribuyó a SAM2. La nota 21 §4 dejó a `person20` sin
mirar. Las dos cosas se cierran aquí, y la primera resulta estar mal atribuida.

## 2. Los seis brazos sobre `person18`

```
analysis/aggregate.py raw/paced-sweep-30   # o el bucle de score_one por brazo
```

| brazo | mIoU ZOH | FOH | delta | alto pred/GT por quinto del clip |
| --- | ---: | ---: | ---: | --- |
| `sam2_c512` | **0.238** | 0.222 | −0.016 | **0.54 0.41 0.43 0.45 0.46** |
| `sam2_c640` | 0.689 | 0.664 | −0.026 | 1.04 1.00 1.00 0.99 0.98 |
| `sam2_c704` | 0.682 | 0.658 | −0.025 | 1.03 1.00 1.01 0.99 0.98 |
| `sam2_t512` | 0.710 | 0.690 | −0.020 | 1.04 1.00 1.01 0.99 0.98 |
| `sam2_t640` | 0.700 | 0.676 | −0.025 | 1.01 1.01 1.01 0.99 0.98 |
| `sam2_t768` | 0.642 | 0.634 | −0.008 | 1.04 1.01 1.01 1.00 0.99 |

**Cinco brazos de seis siguen a este señor con la caja exacta durante 1393 fotogramas.** Solo
`c512` se queda en la mitad inferior. Verificado en píxeles: `proof/foh__person18_c640.mp4`, mismo
fotograma f697 que el de la nota 21, cuerpo entero con sombrero y las tres cajas ajustadas, contra
`proof/foh__person18.mp4` donde a esa misma altura la caja acaba en la cintura.

**No es un desplome progresivo.** Las primeras respuestas de `c512`:

```
     i  alto pred  alto GT   razon    IoU
     0      249.0    302.0    0.82   0.69
     1      185.0    302.0    0.61   0.59
     5      226.0    306.0    0.74   0.66
    14      182.0    313.0    0.58   0.47
    20      183.0    310.0    0.59   0.46
    39      184.0    313.0    0.59   0.43
```

Cae en la **primera respuesta propagada** y se queda ahí. No hay realimentación que se desboque: es
un **equilibrio estable equivocado**, alcanzado en menos de medio segundo de flujo y mantenido 1393
fotogramas. Nótese también que en `i=0`, con la caja GT dada, la máscara ya devuelve 0.82 del alto —
el recorte de 512 empieza mal antes de propagar nada.

**Hipótesis, marcada como hipótesis:** el objetivo mide 302 px de alto y la ventana de `c512` mide
512, así que ocupa el 59% de su alto y deja ~105 px de margen; en `c640` ocupa el 47% y deja 169. El
recorte apretado deja a SAM2 sin contexto para decidir dónde acaba la persona, y se queda con la
parte de abajo. **Sin probar** — haría falta un barrido de tamaño de ventana sobre este clip.

## 3. La corrección a la nota 21

Donde la **nota 21 §2** dice, sobre `person18`:

> SAM2 segmenta las piernas y pierde el torso y el sombrero.

hay que leer: **`sam2_c512` segmenta las piernas.** SAM2 con una ventana de 640 o más, y SAM2 a
fotograma completo a cualquier resolución, siguen al señor entero. La medida de la nota 21 (alto
pred/GT 0.45, ancho 0.91) es correcta y sigue en pie; lo que estaba mal es el sujeto de la frase.

Esto cambia de qué va el hallazgo. No es "SAM2 tiene un fallo de escala en peatones": es **una
patología de capacidad del brazo de 512**, que es exactamente el objeto de esta campaña. Y llega
justo cuando la nota 19 acababa de coronar a `c512` como el mejor brazo de recorte bajo protocolo
pausado: lo es en mediana, y aun así se come una pérdida de 0.45 de mIoU en un clip donde su
hermano de 640 no tiene ningún problema.

## 4. `person20`, el clip que faltaba

```
analysis/render_foh.py raw/paced-sweep-30/sam2_c512__person20.json --zoom 512 --out proof/foh__person20.mp4
```

`person20` es el mismo tipo de escena (peatón, cámara cenital-oblicua, plaza) y `c512` lo hace
**bien**: mIoU 0.750, cuerpo entero con sombrero, las tres cajas ajustadas en f892
(`proof/foh__person20.mid.png`). La patología de `c512` no es de la clase "persona".

Y FOH ahí **gana**, al revés de lo que la nota 19 §4 le atribuía (−0.006):

```
person20        ZOH -> FOH
  sam2_c512   0.750 -> 0.756   +0.006
  sam2_c640   0.695 -> 0.698   +0.003
  sam2_c704   0.668 -> 0.670   +0.002
  sam2_t512   0.706 -> 0.686   -0.020
  sam2_t640   0.651 -> 0.630   -0.021
  sam2_t768   0.609 -> 0.605   -0.004
```

Los tres brazos de recorte ganan, los tres de fotograma completo pierden. El −0.006 de la nota 19
era la media entre familias tapando un **cambio de signo**.

**Y no generaliza:** sobre los 155 pares de la tanda entera las dos familias ganan con FOH, el
recorte más.

```
familia               n   d mediana     gana         p
fotograma completo   80      +0.057   58/80    5.0e-09
recorte              75      +0.085   63/75    2.4e-11
```

Así que el cambio de signo es **de `person20`**, no de la familia. Se registra como observación de
un clip, no como resultado.

## 5. Cómo no sobreleer

- Un clip, y **contado**: uno de 25. `c512` contra la mediana de los otros cinco brazos, por clip:

  ```
  n=25  mediana +0.099  gana en 22/25  peor -0.451 (person18)  mejor +0.190 (car9)
  el resto de la cola negativa: building5 -0.076, bird1_3 -0.004
  ```

  El perfil es el que importa para desplegar: **la ventaja de `c512` es ancha y su pasivo está
  concentrado**. Gana en 22 de 25 clips por márgenes de 0.02 a 0.19, y todo lo que pierde está en
  un solo clip que pierde por 0.45 — seis veces la siguiente desviación en ese lado. La mediana que
  lo corona en la nota 19 es real y es exactamente la estadística que esconde esto.
- La hipótesis del contexto (§2) no se ha probado. Es la explicación más simple compatible con los
  seis brazos, y nada más.
- La tabla por familia de §4 es **exploratoria**: no estaba pre-registrada, y partir 155 pares por
  una covariable elegida después de ver un resultado es pesca. Los dos signos son iguales y ambos
  p<1e-8, así que la conclusión que se saca es la conservadora ("no hay cambio de signo por
  familia"), que es la que va contra la pesca, no a favor.
- Nada de esto toca los agregados de la nota 19: `c512` sigue siendo el mejor brazo de recorte en
  mediana bajo protocolo pausado, y FOH sigue dando +0.069.

## 6. Qué no se midió

Verificación visual: **sí**, `proof/foh__person18_c640.mid.png` y `proof/foh__person20.mid.png`
abiertos y leídos, comparados contra `proof/foh__person18.mid.png` de la nota 21.

No se midió: el barrido de tamaño de ventana sobre `person18` que probaría la hipótesis del
contexto; cuántos clips más tienen la patología; ni si `c512` la tiene también sin pausar (esta
tanda es toda `--fps 30`).
