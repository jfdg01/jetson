#!/usr/bin/env python3
"""The window-vs-input 2x2: is `c640`'s advantage context, pixels, or both?

`notes/PREREG-window-vs-input.md`. Every arm here is the same tiny checkpoint; what changes is the
crop window in full-frame pixels and what the model is fed:

                     entrada 512        entrada 640
    ventana 512      sam2_c512          sam2_w512_i640
    ventana 640      sam2_w640_i512     sam2_c640

Controls come from the run dirs already on disk, so pass them alongside the new one -- rows are
keyed by (arm, seq) and a dir contributes whatever arms it holds:

    analysis/wingrid.py raw/full-sweep-30 raw/wingrid-full            # sin pausar
    analysis/wingrid.py raw/paced-sweep-30 raw/wingrid-30 --foh       # pausado, salida FOH

Self-check: fed only the control dir, the two new arms are missing and it prints just the reference
row, which must be nota 19 negated -- `c640 - c512` = -0.060 sobre 25 clips, 3/25.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fps_grid import by_seq, load  # noqa: E402

C512, C640 = "sam2_c512", "sam2_c640"
W_CTX, W_PIX = "sam2_w640_i512", "sam2_w512_i640"  # more context / more pixels, one each
ARMS = [C512, W_CTX, W_PIX, C640]


def holm(ps: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p, same order in as out. Four contrasts in one family."""
    order = np.argsort(ps)
    adj, run = [0.0] * len(ps), 0.0
    for k, i in enumerate(order):
        run = max(run, (len(ps) - k) * ps[i])
        adj[i] = min(1.0, run)
    return adj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--foh", action="store_true", help="score the coasted delivery, not the held one")
    ap.add_argument("--clip", help="also print this clip on its own, per arm")
    args = ap.parse_args()

    rows = load(args.dirs, args.foh)
    per = {a: by_seq(rows, a) for a in ARMS}
    have = [a for a in ARMS if per[a]]
    assert C512 in have and C640 in have, "faltan los controles c512/c640"
    common = sorted(set.intersection(*(set(per[a]) for a in have)))
    assert common, "ningun clip en comun"
    v = {a: np.array([per[a][s]["mean_iou"] for s in common]) for a in have}
    cell = lambda a: f"{np.median(v[a]):16.3f}" if a in v else f"{'--':>16s}"  # noqa: E731

    print(f"mIoU mediana, salida {'FOH' if args.foh else 'ZOH'}, n={len(common)} clips comunes")
    print(f"{'':14s}{'entrada 512':>16s}{'entrada 640':>16s}")
    print(f"{'ventana 512':14s}{cell(C512)}{cell(W_PIX)}")
    print(f"{'ventana 640':14s}{cell(W_CTX)}{cell(C640)}")

    d_full = v[C640] - v[C512]
    print(f"\nreferencia  c640 - c512  {np.median(d_full):+.3f}  "
          f"{int((d_full > 0).sum())}/{len(d_full)}  n={len(common)}")
    if W_CTX not in v or W_PIX not in v:
        print("  brazos nuevos ausentes de estos dirs: solo la referencia")
        return
    d_ctx, d_pix = v[W_CTX] - v[C512], v[W_PIX] - v[C512]
    tests = [
        ("W1 contexto   w640_i512 - c512", d_ctx),
        ("W2 pixeles    w512_i640 - c512", d_pix),
        ("W3 aditividad (W1+W2) - (c640-c512)", d_ctx + d_pix - d_full),
        ("W4 operacion  w640_i512 - c640", v[W_CTX] - v[C640]),
    ]
    ps = [float(wilcoxon(d).pvalue) if np.any(d) else 1.0 for _, d in tests]
    print(f"\npareado por clip, n={len(common)}, Holm dentro de la familia de 4")
    print(f"{'contraste':38s}{'d mediana':>11s}{'gana':>9s}{'p':>10s}{'p Holm':>10s}")
    for (name, d), p, pa in zip(tests, ps, holm(ps)):
        print(f"{name:38s}{np.median(d):+11.3f}{int((d > 0).sum()):5d}/{len(d):<3d}{p:10.1e}{pa:10.1e}")
    print("  W1 grande y W2 nulo = el contexto es la variable. Al reves = son los pixeles.")
    print("  W3 nulo = dos palancas independientes. W4 positivo = punto de operacion nuevo.")

    if args.clip:
        print(f"\n{args.clip}")
        for a in ARMS:
            r = per[a].get(args.clip)
            print(f"  {a:16s}" + (f"{r['mean_iou']:8.3f}  {r['proc']}/{r['frames']} fotogramas"
                                  if r else "     --  (vetado o no corrido)"))


if __name__ == "__main__":
    main()
