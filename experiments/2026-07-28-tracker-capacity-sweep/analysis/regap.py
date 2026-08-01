"""Reenganche tras hueco: lo que mIoU esconde y el recorte podría estar pagando.

mIoU promedia sobre todos los frames presentes, así que un hueco de 20 frames en una secuencia de
900 pesa nada aunque el brazo salga de él perdido para siempre. La objeción estructural al recorte
es exactamente eso: la ventana solo ve alrededor de donde el objetivo estaba, así que si el objetivo
sale de frame y vuelve por otro sitio, el brazo recortado no puede ni mirar allí. Este script mide
esa transición y solo esa.

Un "hueco cerrado" es una tirada maximal de frames con GT None que tiene GT presente antes Y
después; los huecos que llegan al final de la secuencia no cuentan porque no hay reenganche que
medir. Para cada uno se puntúan los K frames siguientes al regreso:

  reenganche  = algún frame de los K tiene IoU > 0.5   (¿lo recupera?)
  iou_post    = IoU medio sobre esos K frames          (¿cómo de bien?)
  frames_a_re = frames hasta el primero con IoU > 0.5, None si nunca  (¿cuánto tarda?)

La comparación entre brazos es pareada por hueco, no por secuencia: dos brazos ven exactamente los
mismos huecos porque los define el GT, no el brazo.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import uav123
from aggregate import iou


def gaps(gt: list) -> list[int]:
    """Índice del primer frame presente tras cada hueco cerrado."""
    out, in_gap, seen = [], False, False
    for i, g in enumerate(gt):
        if g is None:
            in_gap = seen  # un hueco que empieza antes del primer GT no es un hueco cerrado
        else:
            if in_gap:
                out.append(i)
            in_gap, seen = False, True
    return out


def score_one(path: Path, k: int) -> list[dict]:
    res = json.loads(path.read_text())
    meta, rows = res["meta"], {r["i"]: r for r in res["rows"]}
    gt = uav123.boxes(meta["seq"])
    out = []
    for start in gaps(gt):
        win = [(i, gt[i]) for i in range(start, min(start + k, len(gt))) if gt[i] is not None]
        if len(win) < k // 2:  # el hueco siguiente llega demasiado pronto para juzgar
            continue
        ious = [0.0 if rows.get(i, {}).get("box") is None else iou(g, rows[i]["box"])
                for i, g in win]
        hit = [j for j, v in enumerate(ious) if v > 0.5]
        out.append({"arm": meta["arm"], "seq": meta["seq"], "start": start,
                    "reenganche": bool(hit), "iou_post": float(np.mean(ious)),
                    "frames_a_re": hit[0] if hit else None})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", nargs="+")
    ap.add_argument("--k", type=int, default=60, help="frames tras el regreso que se puntúan")
    ap.add_argument("--vs", metavar="ARM")
    args = ap.parse_args()

    per = [r for d in args.run_dir for p in sorted(Path(d).glob("*.json"))
           if p.stem != "manifest" for r in score_one(p, args.k)]
    assert per, "sin huecos cerrados en estos run dirs"

    by: dict = {}
    for r in per:
        by.setdefault(r["arm"], {})[(r["seq"], r["start"])] = r

    print(f"{len(per)} huecos cerrados puntuados, k={args.k}\n")
    print(f"{'arm':16s} {'huecos':>6s} {'reengancha':>11s} {'iou_post':>9s} {'frames a re':>12s}")
    for a in sorted(by):
        v = list(by[a].values())
        re = [x["frames_a_re"] for x in v if x["frames_a_re"] is not None]
        print(f"{a:16s} {len(v):6d} {sum(x['reenganche'] for x in v):5d}/{len(v):<5d} "
              f"{np.median([x['iou_post'] for x in v]):9.3f} "
              f"{(f'{np.median(re):.0f}' if re else '-'):>12s}")

    if args.vs:
        from scipy.stats import wilcoxon
        ref = args.vs
        assert ref in by, f"{ref} no está entre {sorted(by)}"
        print(f"\npareado por hueco contra {ref}, iou_post")
        print(f"{'arm':16s} {'n':>3s} {'d mediana':>10s} {'d media':>9s} {'gana':>7s} {'p':>8s} "
              f"{'re gana/pierde':>15s}")
        for a in sorted(by):
            if a == ref:
                continue
            common = sorted(set(by[a]) & set(by[ref]))
            if len(common) < 5:
                continue
            d = np.array([by[a][c]["iou_post"] - by[ref][c]["iou_post"] for c in common])
            p = wilcoxon(d).pvalue if np.any(d) else 1.0
            rw = sum(by[a][c]["reenganche"] and not by[ref][c]["reenganche"] for c in common)
            rl = sum(by[ref][c]["reenganche"] and not by[a][c]["reenganche"] for c in common)
            print(f"{a:16s} {len(common):3d} {np.median(d):+10.3f} {np.mean(d):+9.3f} "
                  f"{sum(1 for x in d if x > 0):3d}/{len(d):<3d} {p:8.4f} {rw:7d} /{rl:6d}")


if __name__ == "__main__":
    main()
