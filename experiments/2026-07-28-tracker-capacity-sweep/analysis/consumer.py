#!/usr/bin/env python3
"""How much of the delay ceiling a better CONSUMER can take, at zero device cost.

Nota 23 §3 measured the ceiling: the delivered box scores 0.485 against the frame being consumed and
0.811 against the frame it looked at, so ~0.33 of mIoU is pure delay and nothing else. `aggregate.
extrapolate` (FOH, velocity from the last two answers) cashes part of it. This asks what the rest is
worth by trying consumer-side rules that cost no model and no device time:

    zoh     freeze the last answer                       (the published baseline)
    foh     coast at the last two answers' velocity      (nota 19)
    fohk    coast at the velocity averaged over k gaps   (less jitter, more lag)
    fohs    foh, plus the box size coasted the same way  (scale, not just centre)
    techo   the same box scored against GT(i)            (nothing downstream beats this)

Every rule is strictly causal: only answers that had already landed. `techo` is not a rule, it is
the bound -- it uses GT and is unimplementable.

    analysis/consumer.py raw/paced-sweep-30 --arm sam2_c512
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data  # noqa: E402
from aggregate import extrapolate, held  # noqa: E402
from render_overlay import iou  # noqa: E402


def coast(h: dict, k: int = 2, scale: bool = False) -> dict:
    """FOH generalised: velocity averaged over the last `k` answer gaps, optionally on size too.

    `k=2, scale=False` is `aggregate.extrapolate` -- the check below pins that. A longer `k` trades
    jitter for lag: an average over three gaps still lags the newest gap by one and a half of them.
    """
    out, ans = {}, []
    for j in sorted(h):
        r = h[j]
        if r and r.get("box") and (not ans or r is not ans[-1]):
            ans.append(r)
        if not r or not r.get("box"):
            out[j] = r
            continue
        b, hist = list(r["box"]), ans[-k:]
        if len(hist) >= 2 and hist[-1]["i"] > hist[0]["i"]:
            a, z = hist[0], hist[-1]
            di = z["i"] - a["i"]
            t = (j - r["i"]) / di
            d = [(z["box"][c] - a["box"][c]) for c in range(4)]
            vx, vy = (d[0] + d[2]) / 2, (d[1] + d[3]) / 2
            b = [b[0] + vx * t, b[1] + vy * t, b[2] + vx * t, b[3] + vy * t]
            if scale:  # grow/shrink at the observed rate, around the coasted centre
                gw, gh = (d[2] - d[0]) * t, (d[3] - d[1]) * t
                b = [b[0] - gw / 2, b[1] - gh / 2, b[2] + gw / 2, b[3] + gh / 2]
        out[j] = r | {"box": b}
    return out


RULES = {
    "zoh": lambda h: h,
    "foh": extrapolate,
    "foh3": lambda h: coast(h, 3),
    "foh5": lambda h: coast(h, 5),
    "fohs": lambda h: coast(h, 2, scale=True),
}


def score(boxes: dict, gt: list, at_own_frame: bool = False) -> float:
    """mIoU over GT-present frames; a frame with nothing held scores 0, as everywhere else."""
    v = []
    for j, g in enumerate(gt):
        if not g:
            continue
        r = boxes.get(j)
        if not r or not r.get("box"):
            v.append(0.0)
            continue
        ref = gt[r["i"]] if at_own_frame else g
        v.append(iou(ref, r["box"]) if ref else 0.0)
    return float(np.mean(v)) if v else 0.0


def selfcheck() -> None:
    rows = [{"i": 0, "t": 0.0, "box": [0, 0, 10, 10]}, {"i": 3, "t": 0.1, "box": [3, 0, 13, 10]}]
    h = held(rows, 30.0, 8)
    a = {j: r.get("box") for j, r in extrapolate(h).items()}
    b = {j: r.get("box") for j, r in coast(h, 2).items()}
    assert a == b, (a, b)  # k=2 without scale IS aggregate.extrapolate
    s = coast(h, 2, scale=True)
    assert s[7]["box"][2] - s[7]["box"][0] == 10, s[7]  # constant size in, constant size out
    print("ok: coast(k=2) == extrapolate, y la escala no inventa crecimiento")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", nargs="?")
    ap.add_argument("--arm", default="sam2_c512")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selfcheck()
    assert args.run_dir, "hace falta un run_dir (o --selftest)"

    per: dict[str, dict[str, float]] = {r: {} for r in list(RULES) + ["techo"]}
    for p in sorted(Path(args.run_dir).glob(f"{args.arm}__*.json")):
        res = json.loads(p.read_text())
        gt = data.boxes(res["meta"]["seq"])
        h = held(res["rows"], res["meta"]["fps_stream"], len(gt))
        for name, rule in RULES.items():
            per[name][res["meta"]["seq"]] = score(rule(h), gt)
        per["techo"][res["meta"]["seq"]] = score(h, gt, at_own_frame=True)
    seqs = sorted(per["zoh"])
    assert seqs, f"ningun resultado de {args.arm} en {args.run_dir}"

    base = np.array([per["zoh"][s] for s in seqs])
    ceil = np.array([per["techo"][s] for s in seqs])
    print(f"{args.arm}, n={len(seqs)} clips, {args.run_dir}")
    print(f"{'regla':8s}{'mIoU medio':>12s}{'d vs zoh':>10s}{'gana':>8s}{'p':>10s}{'% del techo':>13s}")
    for name in list(RULES) + ["techo"]:
        v = np.array([per[name][s] for s in seqs])
        d = v - base
        p = float(wilcoxon(d).pvalue) if np.any(d) else 1.0
        gap = float(np.mean(ceil - base))
        print(f"{name:8s}{v.mean():12.3f}{d.mean():+10.3f}{int((d > 0).sum()):4d}/{len(d):<3d}"
              f"{p:10.1e}{(d.mean() / gap * 100 if gap else 0):12.0f}%")
    print("  el techo usa GT(i): no es una regla, es la cota. Nadie lo alcanza en vuelo.")


if __name__ == "__main__":
    main()
