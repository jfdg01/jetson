#!/usr/bin/env python3
"""AsymTrack-B against the paced operating point: is `sam2_c512` the answer, or just the cheapest
SAM2?

`notes/PREREG-paced-family.md`. Every paced run in the campaign compares SAM2 with SAM2, so the
conclusion "under pacing the ordering is by cost" has never been tested against an arm from a
cheaper family. `asym_b` ties `sam2_c512` unpaced at 3.4x less cost, which under pacing should be
worth far more than anything the resolution axis produced.

    analysis/paced_family.py raw/full-sweep-30 raw/asym-repro \
        raw/paced-grid-15 raw/paced-sweep-30 raw/paced-grid-60 raw/paced-grid-120 \
        raw/paced-family-15 raw/paced-family-30 raw/paced-family-60 raw/paced-family-120

`full-sweep-30` holds the unpaced `sam2_c512`, `asym-repro` the unpaced `asym_b` (over all 123 UAV123
clips; the pairing takes the 30 in common). Both predate the paced protocol and carry no
`fps_stream` key, so they land in the unpaced bucket together.

Family: `asym_b - sam2_c512` at 4 speeds x 2 consumer rules = 8 contrasts, Holm within the family.
n=25 by construction -- the `upscales` gate keeps the five 720x480 clips out of every paced
`sam2_c512` run, and four of them are where `asym_b` is worst, so section `uav*` prints its absolute
score there with no control and says so.

Self-check: fed only `raw/full-sweep-30` it prints the A0 control alone, which must be the unpaced
tie -- `asym_b - sam2_c512` = -0.009 over 30 clips, 14/30.
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

ASYM, C512 = "asym_b", "sam2_c512"
UAV = ["uav1_2", "uav2", "uav3", "uav5", "uav7"]  # 720x480, gated out of every 512+ crop arm


def sustained(rows: dict, arm: str) -> float:
    """Median frames per second the arm holds on this board, from its own per-frame p50."""
    v = [r["ms_p50"] for r in by_seq(rows, arm).values()]
    return 1000.0 / float(np.median(v)) if v else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", help="run dirs, any order; fps is read from the results")
    args = ap.parse_args()

    runs: dict[float, list[str]] = {}
    for d in args.dirs:
        # `full-sweep-30` predates the paced protocol and has no `fps_stream` key at all
        f = json.loads(jsons([d])[0].read_text())["meta"].get("fps_stream") or 0.0
        runs.setdefault(f, []).append(d)
    zoh = {f: load(runs[f], False) for f in sorted(runs)}
    foh = {f: load(runs[f], True) for f in sorted(runs)}
    paced = [f for f in sorted(runs) if f]

    # ---- A0: the control that makes any paced advantage attributable to cost
    print("A0  sin pausar, asym_b menos sam2_c512, pareado por clip")
    if 0.0 in zoh:
        n, m, w, p = paired(by_seq(zoh[0.0], ASYM), by_seq(zoh[0.0], C512))
        print(f"    n={n}  d mediana {m:+.3f}  gana {w}/{n}  p={p:.2f}   "
              f"asym_b {sustained(zoh[0.0], ASYM):.1f} fps, sam2_c512 "
              f"{sustained(zoh[0.0], C512):.1f} fps sostenidos")
        print("    empate = la ventaja pausada es del coste, no de que AsymTrack siga mejor")
    else:
        print("    (falta raw/full-sweep-30)")
    if not paced:
        return
    base = sustained(zoh[0.0], ASYM) if 0.0 in zoh else float("nan")

    # ---- mIoU levels, both rules
    print("\nmIoU mediana (n de clips entre parentesis)")
    print(f"{'brazo':16s}{'salida':>7s}" + "".join(f"{f'{f:g} fps':>14s}" for f in paced))
    for arm in (ASYM, C512):
        for tag, src in (("ZOH", zoh), ("FOH", foh)):
            line = ""
            for f in paced:
                v = [r["mean_iou"] for r in by_seq(src[f], arm).values()]
                line += f"{np.median(v):9.3f} ({len(v):2d})" if v else f"{'--':>14s}"
            print(f"{arm:16s}{tag:>7s}{line}")

    # ---- A3: the protocol check. If the measured rate leaves the model, A1 is not interpreted.
    print("\nA3  tasa de respuesta medida contra min(1, fps_sostenidos / F)")
    print(f"{'fps':>6s}{'medida':>10s}{'predicha':>10s}{'desvio':>9s}")
    ok = True
    for f in paced:
        v = list(by_seq(zoh[f], ASYM).values())
        if not v:
            continue
        got = float(np.median([r["proc"] / r["frames"] for r in v]))
        pred = min(1.0, base / f)
        ok &= abs(got - pred) <= 0.05
        print(f"{f:6g}{got:10.3f}{pred:10.3f}{got - pred:+9.3f}")
    print(f"    {'dentro de 0.05 en todas: el p50 describe el protocolo' if ok else 'FUERA de 0.05: A1 NO se interpreta'}")

    # ---- A1: the family
    print("\nA1  asym_b menos sam2_c512, pareado por clip, familia Holm de 8 contrastes")
    cells = [(f, tag) for f in paced for tag in ("ZOH", "FOH")]
    res = [paired(by_seq({"ZOH": zoh, "FOH": foh}[t][f], ASYM),
                  by_seq({"ZOH": zoh, "FOH": foh}[t][f], C512)) for f, t in cells]
    adj = holm([r[3] for r in res])
    print(f"{'fps':>6s}{'salida':>7s}{'n':>5s}{'d mediana':>12s}{'gana':>9s}{'p':>10s}{'p Holm':>10s}")
    for (f, t), (n, m, w, p), a in zip(cells, res, adj):
        print(f"{f:6g}{t:>7s}{n:5d}{m:+12.3f}{w:5d}/{n:<3d}{p:10.1e}{a:10.1e}")
    win = {t: sum(1 for (f, tt), (n, m, w, _), a in zip(cells, res, adj)
                  if tt == t and m > 0 and w >= 19 and a < 0.05) for t in ("ZOH", "FOH")}
    print(f"    umbral: d>0, gana>=19/25, Holm<0.05 en >=3 de 4 por salida. "
          f"ZOH {win['ZOH']}/4, FOH {win['FOH']}/4 -> "
          f"{'A1 GANA' if win['ZOH'] >= 3 and win['FOH'] >= 3 else 'A1 NO gana'}")

    # ---- the gated clips: asym_b alone, no control exists
    print("\nuav*  los 5 clips de 720x480 que la puerta quita al control. SIN CONTROL, no comparar")
    print(f"{'clip':12s}{'sin pausar':>12s}" + "".join(f"{f'{f:g} fps':>10s}" for f in paced))
    for s in UAV:
        r0 = by_seq(zoh[0.0], ASYM).get(s) if 0.0 in zoh else None
        line = f"{r0['mean_iou']:12.3f}" if r0 else f"{'--':>12s}"
        for f in paced:
            r = by_seq(zoh[f], ASYM).get(s)
            line += f"{r['mean_iou']:10.3f}" if r else f"{'--':>10s}"
        print(f"{s:12s}{line}")


if __name__ == "__main__":
    main()
