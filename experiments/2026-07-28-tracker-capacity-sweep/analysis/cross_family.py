#!/usr/bin/env python3
"""Is the paced cost -> mIoU curve blind to the family an arm comes from?

`notes/PREREG-cross-family-pacing.md`. Unpaced the whole catalogue ties -- every paired difference
between AsymTrack, SAM2, DAM4SAM and SAMURAI is under 0.03 across 29-407 ms of cost. Paced it fans
out from 0.68 to 0.24. So under pacing cost is the only variable left, and the curve that says so
has only ever been drawn with SAM2 points.

    analysis/cross_family.py raw/full-sweep-30 raw/asym-repro raw/night-samurai raw/sam-full30 \
        raw/dam-full30b raw/asym-lt raw/xfam-unpaced-sam raw/xfam-unpaced-asymlt \
        raw/paced-sweep-30 raw/paced-family-30 raw/xfam-30 \
        raw/paced-grid-120 raw/paced-family-120 raw/xfam-120

D1  samurai_t640 - sam2_c704   189.1 vs 190.7 ms, the tightest cross-family cost pair there is
D2  dam4sam_t640 - sam2_c704   204.0 vs 190.7 ms, +7% of cost
D3  fit mIoU on log(rate) with the SAM2 arms ALONE, predict the three new arms out of sample
D4  asym_lt - asym_b           the note-27 debt, its own Holm family, declared secondary

D1 and D2 share one Holm family of 8. The margins are pre-registered around the UNPACED difference
of each pair: pacing is claimed to be a rate transformation and nothing else, so an equal-cost pair
should keep the difference it already had.

Self-check: fed only the unpaced dirs it prints section D0 alone, which must reproduce the ties the
pre-registration was built on -- `samurai_t640 - sam2_c704` = -0.027 over the 20 clips that existed
before this run, and `dam4sam_t640 - sam2_c704` = -0.016 over 30.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fps_grid import by_seq, jsons, load, paired  # noqa: E402
from wingrid import holm  # noqa: E402

SAM, DAM, DAM960 = "samurai_t640", "dam4sam_t640", "dam4sam_t960"
C704, ASYM, ASYM_LT = "sam2_c704", "asym_b", "asym_lt"
NEW = [SAM, DAM, DAM960]
# the SAM2 arms the curve is fitted on. `asym_b` is deliberately NOT here: its rate is 0.97, three
# times outside the fitted range, so scoring it would be extrapolation dressed up as validation.
FIT = ["sam2_c512", "sam2_t512", "sam2_c640", "sam2_t640", C704, "sam2_t768"]
# the five clips whose gap sequences fitted `asym_lt`'s thresholds -- D4 is reported without them too
LEAK = ["bike2", "car1_3", "uav1_2", "uav2", "uav7"]


def rate(rows: dict, arm: str, keep: set | None = None) -> float:
    """Median fraction of stream frames the arm answered on."""
    d = by_seq(rows, arm)
    v = [r["proc"] / r["frames"] for s, r in d.items() if keep is None or s in keep]
    return float(np.median(v)) if v else float("nan")


def level(rows: dict, arm: str, keep: set | None = None) -> tuple[float, int]:
    d = by_seq(rows, arm)
    v = [r["mean_iou"] for s, r in d.items() if keep is None or s in keep]
    return (float(np.median(v)), len(v)) if v else (float("nan"), 0)


def frozen(dirs: list[str], arm: str) -> list[str]:
    """Clips where every answer carried the same box. A tracker that never moves is not scoring 0
    honestly, it is broken, and the cell is INVALID rather than a data point. Reads the raw files
    instead of the scored rows because `score_one` keeps no pointer back to its source."""
    bad = []
    for p in jsons(dirs, f"{arm}__*.json"):
        boxes = [tuple(r["box"]) for r in json.loads(p.read_text())["rows"] if r.get("box")]
        if len(boxes) > 5 and len(set(boxes)) == 1:
            bad.append(p.stem.split("__")[1])
    return bad


def family(cells: list, res: list, margins: dict) -> None:
    """Print one Holm-adjusted family and whether each cell landed inside its registered margin."""
    adj = holm([r[3] for r in res])
    print(f"{'par':32s}{'fps':>6s}{'salida':>7s}{'n':>5s}{'d mediana':>12s}{'gana':>9s}"
          f"{'p':>10s}{'p Holm':>10s}{'margen':>18s}{'':>9s}")
    for (name, f, t), (n, m, w, p), a in zip(cells, res, adj):
        lo, hi = margins[name]
        inside = lo <= m <= hi
        # outside the margin only counts against the law if the direction is consistent and it survives Holm
        hard = (not inside) and w >= 19 and a < 0.05
        print(f"{name:32s}{f:6g}{t:>7s}{n:5d}{m:+12.3f}{w:5d}/{n:<3d}{p:10.1e}{a:10.1e}"
              f"{f'[{lo:+.3f}, {hi:+.3f}]':>18s}"
              f"{'  dentro' if inside else ('  FUERA-dura' if hard else '  fuera')}")
    return adj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", help="run dirs, any order; fps is read from the results")
    args = ap.parse_args()

    runs: dict[float, list[str]] = {}
    for d in args.dirs:
        # the unpaced dirs predate the paced protocol and carry no `fps_stream` key at all
        f = json.loads(jsons([d])[0].read_text())["meta"].get("fps_stream") or 0.0
        runs.setdefault(f, []).append(d)
    zoh = {f: load(runs[f], False) for f in sorted(runs)}
    foh = {f: load(runs[f], True) for f in sorted(runs)}
    paced = [f for f in sorted(runs) if f]
    src = {"ZOH": zoh, "FOH": foh}

    # ---- D0: the unpaced controls. Without them no paced difference is attributable to pacing.
    print("D0  sin pausar, pareado por clip. Es lo que hace atribuible cualquier efecto pausado")
    if 0.0 in zoh:
        for x, y in ((SAM, C704), (DAM, C704), (DAM960, C704), (ASYM_LT, ASYM)):
            n, m, w, p = paired(by_seq(zoh[0.0], x), by_seq(zoh[0.0], y))
            print(f"    {x:14s} - {y:12s} n={n:2d}  {m:+.3f}  {w:2d}/{n:<2d}  p={p:.3f}")
        print(f"    {'brazo':16s}{'ms p50':>9s}{'mIoU':>8s}{'n':>4s}")
        for a in FIT + NEW + [ASYM, ASYM_LT]:
            v = list(by_seq(zoh[0.0], a).values())
            if v:
                print(f"    {a:16s}{np.median([r['ms_p50'] for r in v]):9.1f}"
                      f"{np.median([r['mean_iou'] for r in v]):8.3f}{len(v):4d}")
    else:
        print("    (faltan los directorios sin pausar)")
    if not paced:
        return

    # ---- the cheap assert: a tracker that never moved did not score 0, it broke
    for f in paced:
        for a in NEW + [ASYM_LT]:
            if bad := frozen(runs[f], a):
                print(f"\n!!! {a} a {f:g} fps devuelve la misma caja en todo el clip: {bad} -> INVALIDO")

    # ---- levels, both rules
    print("\nmIoU mediana pausada (n entre parentesis)")
    print(f"{'brazo':16s}{'salida':>7s}" + "".join(f"{f'{f:g} fps':>14s}" for f in paced))
    for a in FIT + NEW + [ASYM, ASYM_LT]:
        for t in ("ZOH", "FOH"):
            line = ""
            for f in paced:
                m, n = level(src[t][f], a)
                line += f"{m:9.3f} ({n:2d})" if n else f"{'--':>14s}"
            if line.strip("- "):
                print(f"{a:16s}{t:>7s}{line}")

    # ---- D1 + D2: one Holm family of 8, margins registered around the unpaced difference
    print("\nD1 + D2  familia Holm de 8. El margen sale del par SIN pausar: si pausar es solo una")
    print("         transformacion de tasa, un par de igual coste conserva la diferencia que tenia")
    margins = {f"D1 {SAM} - {C704}": (-0.077, 0.023),
               f"D2 {DAM} - {C704}": (-0.080, 0.020)}
    cells = [(name, f, t) for name, (x, y) in
             ((f"D1 {SAM} - {C704}", (SAM, C704)), (f"D2 {DAM} - {C704}", (DAM, C704)))
             for f in paced for t in ("ZOH", "FOH")]
    pairs = {f"D1 {SAM} - {C704}": (SAM, C704), f"D2 {DAM} - {C704}": (DAM, C704)}
    res = [paired(by_seq(src[t][f], pairs[name][0]), by_seq(src[t][f], pairs[name][1]))
           for name, f, t in cells]
    adj = family(cells, res, margins)
    for name in margins:
        lo, hi = margins[name]
        hard = sum(1 for (nm, f, t), (n, m, w, _), a in zip(cells, res, adj)
                   if nm == name and not (lo <= m <= hi) and w >= 19 and a < 0.05)
        print(f"    {name}: {hard}/4 celdas fuera del margen con >=19/25 y Holm<0.05 -> "
              f"{'LEY FALSADA' if hard >= 2 else 'compatible con la ley (nulo acotado, no equivalencia)'}")

    # ---- D3: fit the curve on SAM2 alone, predict the new arms out of sample
    #
    # CORRECCION sobre lo pre-registrado. D3 se registro como medianas por brazo, y eso compara
    # poblaciones distintas: los brazos `c*` se caen en los cinco clips 720x480 y puntuan sobre 25,
    # los tres nuevos sobre 30. Corrido asi, los tres errores salian -0.068/-0.065/-0.062, mismo
    # signo y misma magnitud -- la firma de un sesgo de construccion, no de tres fallos. Se reporta
    # sobre el conjunto comun a todos los brazos implicados, y ademas tal como se registro, para
    # que la correccion quede a la vista en vez de sustituida en silencio.
    print("\nD3  curva ajustada SOLO con los brazos SAM2, brazos nuevos predichos fuera de muestra")
    for f in paced:
        sets = [set(by_seq(zoh[f], a)) for a in FIT + NEW]
        keep = set.intersection(*[s for s in sets if s])
        print(f"  {f:g} fps   conjunto comun a los {len(FIT + NEW)} brazos: n={len(keep)}")
        for tag, k in (("comun", keep), ("como se registro", None)):
            x = [rate(zoh[f], a, k) for a in FIT]
            y = [level(zoh[f], a, k)[0] for a in FIT]
            ok = [i for i, (u, v) in enumerate(zip(x, y))
                  if np.isfinite(u) and np.isfinite(v) and u > 0]
            if len(ok) < 3:
                continue
            b, c = np.polyfit(np.log([x[i] for i in ok]), [y[i] for i in ok], 1)
            r = np.corrcoef(np.log([x[i] for i in ok]), [y[i] for i in ok])[0, 1]
            print(f"    [{tag}] mIoU = {b:+.3f}*log(tasa) {c:+.3f}   R2={r * r:.3f}   "
                  f"n_ajuste={len(ok)} brazos SAM2")
            print(f"    {'brazo':16s}{'tasa':>8s}{'n':>4s}{'predicha':>10s}{'medida':>9s}{'error':>9s}")
            for a in NEW:
                u, (v, n) = rate(zoh[f], a, k), level(zoh[f], a, k)
                if not np.isfinite(u) or not n:
                    continue
                pred = b * np.log(u) + c
                print(f"    {a:16s}{u:8.3f}{n:4d}{pred:10.3f}{v:9.3f}{v - pred:+9.3f}"
                      f"{'   dentro' if abs(v - pred) <= 0.05 else '   FUERA de 0.05'}")

    # ---- D4: the note-27 debt, its own family, secondary
    print("\nD4  asym_lt - asym_b, familia Holm propia de 4, SECUNDARIA (no entra en la de arriba)")
    d4 = [(f, t) for f in paced for t in ("ZOH", "FOH")]
    r4 = [paired(by_seq(src[t][f], ASYM_LT), by_seq(src[t][f], ASYM)) for f, t in d4]
    a4 = holm([r[3] for r in r4])
    print(f"{'fps':>6s}{'salida':>7s}{'n':>5s}{'d mediana':>12s}{'gana':>9s}{'p':>10s}{'p Holm':>10s}")
    for (f, t), (n, m, w, p), a in zip(d4, r4, a4):
        print(f"{f:6g}{t:>7s}{n:5d}{m:+12.3f}{w:5d}/{n:<3d}{p:10.1e}{a:10.1e}")
    print("    sin los 5 clips que ajustaron sus umbrales (bike2 car1_3 uav1_2 uav2 uav7):")
    for f, t in d4:
        a_, b_ = by_seq(src[t][f], ASYM_LT), by_seq(src[t][f], ASYM)
        n, m, w, p = paired({k: v for k, v in a_.items() if k not in LEAK},
                            {k: v for k, v in b_.items() if k not in LEAK})
        print(f"    {f:6g}{t:>7s}  n={n:2d}  {m:+.3f}  {w:2d}/{n:<2d}  p={p:.3f}")


if __name__ == "__main__":
    main()
