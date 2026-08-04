#!/usr/bin/env python3
"""The arm x fps grid: how the operating point moves as the stream outruns the device.

Notes 2 and 19 hold the two halves and never the axis between them -- unpaced (`c640` wins) and one
paced slice at 30 fps (`c512` wins). This prints the three pre-registered tests
(`notes/PREREG-paced-fps-grid.md`), one section each:

    H1  the operating point drops in resolution as fps rises   (c512 minus c640, paired, per fps)
    H2  FOH's gain grows with fps                              (FOH minus ZOH, paired, per fps)
    H3  `lead`'s null breaks at high fps                       (lead minus c512, paired, per fps)

Under `--fps F` the drop interval is `latency * F` frames (`device/run_arm.py:next_frame`), so fps
is the knob for "same device, faster scene" -- the Jetson-at-15W regime, not the desktop one.

    analysis/fps_grid.py raw/paced-grid-15 raw/paced-sweep-30 raw/paced-lead-30 \
                         raw/paced-grid-60 raw/paced-grid-120

Self-check: fed only the 30 fps dirs it must reprint the published numbers -- H1 +0.060 (22/25,
p=1.3e-3, nota 19), H2 +0.069 (142/180, p=2.8e-22, nota 19), H3 +0.001 (15/25, p=0.31, nota 20).
Anything else means the grid code and the notes disagree, and the notes were checked first.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aggregate import score_one  # noqa: E402
from lead import thirds  # noqa: E402

LEAD = "sam2_c512_lead"


def jsons(dirs: list[str], pattern: str = "*.json") -> list[Path]:
    """Several dirs can share an fps -- `paced-sweep-30` holds the control, `paced-lead-30` the
    lead arm, same protocol, same clips. Keyed by (arm, seq), so merging them is safe."""
    return [p for d in dirs for p in sorted(Path(d).glob(pattern)) if p.stem != "manifest"]


def load(dirs: list[str], foh: bool) -> dict:
    """(arm, seq) -> scored row, for every result in the run dirs."""
    out = {}
    for p in jsons(dirs):
        r = score_one(p, foh)
        out[(r["arm"], r["seq"])] = r
    return out


def paired(a: dict, b: dict, key="mean_iou") -> tuple:
    """Median difference over the clips both sides have. Returns (n, median, wins, p)."""
    common = sorted(set(a) & set(b))
    if not common:
        return 0, float("nan"), 0, 1.0
    d = np.array([a[s][key] - b[s][key] for s in common])
    p = wilcoxon(d).pvalue if np.any(d) else 1.0
    return len(d), float(np.median(d)), int((d > 0).sum()), float(p)


def by_seq(rows: dict, arm: str) -> dict:
    return {s: r for (a, s), r in rows.items() if a == arm}


def step_px(dirs: list[str], arm: str) -> float:
    """Median centre displacement between consecutive ANSWERS -- what `lead` has to predict."""
    out = []
    for p in jsons(dirs, f"{arm}__*.json"):
        rows = json.loads(p.read_text())["rows"]
        c = [((r["box"][0] + r["box"][2]) / 2, (r["box"][1] + r["box"][3]) / 2)
             for r in rows if r.get("box")]
        out += [float(np.hypot(c[i][0] - c[i - 1][0], c[i][1] - c[i - 1][1]))
                for i in range(1, len(c))]
    return float(np.median(out)) if out else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", help="run dirs, any order; fps is read from the results")
    args = ap.parse_args()

    runs: dict[float, list[str]] = {}  # fps -> dirs
    for d in args.dirs:
        f = json.loads(jsons([d])[0].read_text())["meta"]["fps_stream"]
        runs.setdefault(f, []).append(d)
    fps_list = sorted(runs)
    zoh = {f: load(runs[f], False) for f in fps_list}
    foh = {f: load(runs[f], True) for f in fps_list}
    arms = sorted({a for r in zoh.values() for a, _ in r})

    print("mIoU mediana por brazo y fps, salida ZOH (n de clips entre parentesis)")
    print(f"{'brazo':16s}" + "".join(f"{f'{f:g} fps':>14s}" for f in fps_list))
    for arm in arms:
        line = ""
        for f in fps_list:
            v = [r["mean_iou"] for r in by_seq(zoh[f], arm).values()]
            line += f"{np.median(v):9.3f} ({len(v):2d})" if v else f"{'--':>14s}"
        print(f"{arm:16s}{line}")

    print("\nfotogramas procesados / fotogramas del flujo (tasa de respuesta), sam2_c512")
    print(f"{'':16s}" + "".join(f"{f'{f:g} fps':>14s}" for f in fps_list))
    line = ""
    for f in fps_list:
        v = by_seq(zoh[f], "sam2_c512").values()
        line += f"{np.median([r['proc'] / r['frames'] for r in v]):14.3f}" if v else f"{'--':>14s}"
    print(f"{'tasa':16s}{line}")

    # `d` alone is not comparable across fps: the whole mIoU scale collapses from 0.57 at 15 fps to
    # 0.15 at 120, so a shrinking absolute gap can be a floor effect rather than a real turn. `d/niv`
    # divides by the median level of `sam2_c512` at that fps. Ratio of two medians over the same
    # clips, NOT a paired quantity -- same caveat as `% del techo` in nota 24; no interval on it.
    def level(f: float) -> float:
        return float(np.median([r["mean_iou"] for r in by_seq(zoh[f], "sam2_c512").values()]))

    # ---- H1: does the operating point drop in resolution as fps rises?
    print("\nH1  sam2_c512 menos sam2_c640, pareado por clip, ZOH")
    print(f"{'fps':>6s}{'n':>5s}{'d mediana':>12s}{'gana':>9s}{'p':>10s}{'d/niv':>9s}")
    for f in fps_list:
        n, m, w, p = paired(by_seq(zoh[f], "sam2_c512"), by_seq(zoh[f], "sam2_c640"))
        print(f"{f:6g}{n:5d}{m:+12.3f}{w:5d}/{n:<3d}{p:10.1e}{m / level(f):8.1%}")
    print("  positivo y creciente con fps = H1. Plano = el resultado de la nota 19 era un corte.")

    # ---- H2: does FOH's gain grow with fps?
    print("\nH2  FOH menos ZOH, pareado sobre TODOS los pares brazo-clip")
    print(f"{'fps':>6s}{'n':>5s}{'d mediana':>12s}{'gana':>9s}{'p':>10s}{'d/niv':>9s}")
    for f in fps_list:
        n, m, w, p = paired(foh[f], zoh[f])
        print(f"{f:6g}{n:5d}{m:+12.3f}{w:5d}/{n:<3d}{p:10.1e}{m / level(f):8.1%}")
    print("  creciente = FOH corrige retardo. Plano = no es retardo lo que corrige.")

    # ---- H3: does `lead`'s null break at high fps?
    print("\nH3  sam2_c512_lead menos sam2_c512, pareado por clip")
    print(f"{'fps':>6s}{'salida':>7s}{'n':>5s}{'d mediana':>12s}{'gana':>9s}{'p':>10s}"
          f"{'salto px':>10s}")
    for f in fps_list:
        s = step_px(runs[f], "sam2_c512")
        for tag, src in (("ZOH", zoh), ("FOH", foh)):
            n, m, w, p = paired(by_seq(src[f], LEAD), by_seq(src[f], "sam2_c512"))
            print(f"{f:6g}{tag:>7s}{n:5d}{m:+12.3f}{w:5d}/{n:<3d}{p:10.1e}"
                  f"{s if tag == 'ZOH' else float('nan'):10.1f}")

    print("\n  memoria envenenada: deficit de `lead` por tercio del clip, ZOH")
    print(f"{'fps':>6s}{'n':>5s}{'1o':>9s}{'2o':>9s}{'3o':>9s}{'3o-1o':>9s}{'p':>10s}")
    for f in fps_list:
        led = {p.stem.split("__")[1]: p for p in jsons(runs[f], f"{LEAD}__*.json")}
        ctl = {p.stem.split("__")[1]: p for p in jsons(runs[f], "sam2_c512__*.json")}
        pairs = [(led[s], ctl[s]) for s in sorted(set(led) & set(ctl))]
        if not pairs:
            continue
        dt = np.array([np.array(thirds(x, False)) - np.array(thirds(y, False)) for x, y in pairs])
        sl = dt[:, 2] - dt[:, 0]
        p = wilcoxon(sl).pvalue if np.any(sl) else 1.0
        print(f"{f:6g}{len(dt):5d}" + "".join(f"{v:+9.3f}" for v in np.median(dt, 0))
              + f"{np.median(sl):+9.3f}{p:10.1e}")
    print("  negativo y significativo = el deficit CRECE con el clip, firma de memoria envenenada")


if __name__ == "__main__":
    main()
