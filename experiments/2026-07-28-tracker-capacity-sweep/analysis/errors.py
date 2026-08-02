#!/usr/bin/env python3
"""What the deficit is MADE of: loss, translation, or scale.

Every table in this campaign scores mIoU, and mIoU says how bad a clip went without saying how. The
nota 21 taxonomy (`person18` cambia de direccion, `bird1_1` revienta la mascara, `bike2` se queda en
el objeto equivocado) was read off frames by eye, and nota 22 showed one of the three readings was
wrong. This computes it instead, per frame, from the boxes that are already on disk:

    IoU               what was scored -- losses count 0, the `aggregate.py` convention
    perdidos          fraction of GT-present frames with no answer
    IoU / centrado / reescalado, all three CONDITIONAL on an answer:
        IoU           the same overlap over answered frames only
        centrado      the prediction moved onto GT's centre -- what survives if translation is free
        reescalado    a GT-sized box at the prediction's centre -- what survives if scale is free

Splitting loss out is not cosmetic: `car12` scores 0.087 and answers on 11% of frames, and on those
it is at 0.783. Its problem is not a bad box, it is no box. Reading the two recovery columns:

    centrado alto, reescalado bajo   the box is the right size in the wrong place -> translation
    reescalado alto, centrado bajo   the box is in the right place at the wrong size -> scale
    both low                         it is on something else entirely, or the mask blew up

    analysis/errors.py raw/paced-sweep-30 --arm sam2_c512
    analysis/errors.py raw/full-sweep-30 --arm sam2_c512 --arm sam2_c640 --sort centrado
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data  # noqa: E402
from aggregate import extrapolate, held  # noqa: E402
from render_overlay import iou  # noqa: E402


def recentre(p: list, g: list) -> list:
    """`p`'s size, `g`'s centre."""
    w, h = p[2] - p[0], p[3] - p[1]
    cx, cy = (g[0] + g[2]) / 2, (g[1] + g[3]) / 2
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]


def resize(p: list, g: list) -> list:
    """`g`'s size, `p`'s centre."""
    return recentre(g, p)


def decompose(res_path: Path, foh: bool = False) -> dict:
    res = json.loads(res_path.read_text())
    meta = res["meta"]
    gt = data.boxes(meta["seq"])
    if meta.get("fps_stream"):
        # a paced run answers on a third of the frames; decomposing only those would describe a
        # tracker nobody consumes. `held` is the box in the consumer's hand, which is what every
        # paced number in this campaign scores, and `perdidos` then means "nothing to hold yet".
        h = held(res["rows"], meta["fps_stream"], len(gt))
        box = {i: r.get("box") for i, r in (extrapolate(h) if foh else h).items()}
    else:
        box = {r["i"]: r.get("box") for r in res["rows"]}
    raw, cen, rsz, lost, n = [], [], [], 0, 0
    for i, g in enumerate(gt):
        if not g:
            continue          # GT absent: nothing to hit, excluded like everywhere else
        n += 1
        p = box.get(i)
        if p is None:
            lost += 1
            continue
        raw.append(iou(g, p)), cen.append(iou(g, recentre(p, g))), rsz.append(iou(g, resize(p, g)))
    m = lambda v: float(np.mean(v)) if v else 0.0  # noqa: E731
    # `iou` is the scored quantity (losses count 0, as in `aggregate.py`); the other three are
    # CONDITIONAL on the arm having answered, so each can reach 1.0 and the loss column carries the
    # rest. Mixing the two conventions is what made `person18` read as "both low" on the first pass.
    return {"seq": meta["seq"], "arm": meta["arm"], "n": n, "perdidos": lost / max(n, 1),
            "iou": m(raw) * (n - lost) / max(n, 1), "base": m(raw),
            "centrado": m(cen), "reescalado": m(rsz)}


def lag(res_path: Path) -> dict:
    """Is the translation deficit pure delay, or drift? Score the held box twice.

    Once against the GT of the frame being consumed (`GT(j)`, the honest number) and once against
    the GT of the frame the box actually looked at (`GT(i)`). A box that is simply late scores low
    on the first and high on the second; a box that wandered off scores low on both. `GT(i)` is the
    ceiling of any consumer-side delay compensation -- FOH, a Kalman, anything -- because nothing
    downstream can fix a box that was already wrong when it was computed.
    """
    res = json.loads(res_path.read_text())
    meta = res["meta"]
    gt = data.boxes(meta["seq"])
    assert meta.get("fps_stream"), "sin pausar no hay retardo que medir"
    now, then, gap = [], [], []
    for j, r in held(res["rows"], meta["fps_stream"], len(gt)).items():
        if not gt[j] or not r or not r.get("box"):
            continue
        now.append(iou(gt[j], r["box"]))
        if gt[r["i"]]:
            then.append(iou(gt[r["i"]], r["box"])), gap.append(j - r["i"])
    md = lambda v: float(np.median(v)) if v else 0.0  # noqa: E731
    return {"seq": meta["seq"], "arm": meta["arm"], "ahora": md(now), "entonces": md(then),
            "retardo": md(gap)}


def selfcheck() -> None:
    g = [100, 100, 200, 200]
    # pure translation: right size, half a side off. Centring recovers everything, resizing nothing.
    t = decompose_pair(g, [150, 100, 250, 200])
    assert t["centrado"] == 1.0 and abs(t["reescalado"] - t["iou"]) < 1e-9, t
    # pure scale: same centre, half the side. Resizing recovers everything, centring nothing.
    s = decompose_pair(g, [125, 125, 175, 175])
    assert s["reescalado"] == 1.0 and abs(s["centrado"] - s["iou"]) < 1e-9, s
    print("ok: traslacion y escala se separan")


def decompose_pair(g: list, p: list) -> dict:
    return {"iou": iou(g, p), "centrado": iou(g, recentre(p, g)), "reescalado": iou(g, resize(p, g))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", nargs="?")
    ap.add_argument("--arm", action="append", default=[], help="repeatable; default every arm")
    ap.add_argument("--sort", default="iou",
                    choices=["iou", "base", "centrado", "reescalado", "perdidos"])
    ap.add_argument("--foh", action="store_true",
                    help="coast the held box (first-order hold) before decomposing")
    ap.add_argument("--lag", action="store_true",
                    help="retardo contra deriva: la caja entregada contra GT(j) y contra GT(i)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selfcheck()
    assert args.run_dir, "hace falta un run_dir (o --selftest)"

    paths = [p for p in sorted(Path(args.run_dir).glob("*.json")) if p.stem != "manifest"]
    rows = [(lag if args.lag else decompose)(p, *(() if args.lag else (args.foh,))) for p in paths]
    rows = [r for r in rows if not args.arm or r["arm"] in args.arm]
    assert rows, "ningun resultado que casar"

    if args.lag:
        for arm in sorted({r["arm"] for r in rows}):
            sub = sorted((r for r in rows if r["arm"] == arm), key=lambda r: r["ahora"])
            print(f"\n{arm}   n={len(sub)} clips   (IoU mediana por clip de la caja entregada)")
            print(f"{'clip':14s}{'vs GT(j)':>10s}{'vs GT(i)':>10s}{'retardo':>9s}")
            for r in sub:
                print(f"{r['seq']:14s}{r['ahora']:10.3f}{r['entonces']:10.3f}{r['retardo']:9.0f}")
            print(f"{'MEDIANA':14s}" + "".join(
                f"{np.median([r[k] for r in sub]):10.3f}" for k in ("ahora", "entonces"))
                + f"{np.median([r['retardo'] for r in sub]):9.0f}")
        return

    for arm in sorted({r["arm"] for r in rows}):
        sub = sorted((r for r in rows if r["arm"] == arm), key=lambda r: r[args.sort])
        print(f"\n{arm}   n={len(sub)} clips")
        cols = ("iou", "perdidos", "base", "centrado", "reescalado")
        print(f"{'clip':14s}{'IoU':>8s}{'perdidos':>10s}" + "  | sobre respondidos: "
              f"{'IoU':>7s}{'centrado':>10s}{'reescalado':>12s}")
        for r in sub:
            print(f"{r['seq']:14s}{r['iou']:8.3f}{r['perdidos']:10.3f}{'':21s}"
                  f"{r['base']:7.3f}{r['centrado']:10.3f}{r['reescalado']:12.3f}")
        med = {k: np.median([r[k] for r in sub]) for k in cols}
        print(f"{'MEDIANA':14s}{med['iou']:8.3f}{med['perdidos']:10.3f}{'':21s}"
              f"{med['base']:7.3f}{med['centrado']:10.3f}{med['reescalado']:12.3f}")


if __name__ == "__main__":
    main()
