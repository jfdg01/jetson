#!/usr/bin/env python3
"""Predicting the target's position: on the model's INPUT, on the consumer's OUTPUT, or nowhere.

Under `--fps` the arm skips the frames it could not keep up with, so its last box is one whole
drop interval old. The same velocity estimate can be spent in two places:

    input   `sam2_c512_lead` centres the crop where the target is predicted to be (costs device
            time, and a wrong guess is written into SAM2's memory bank)
    output  `aggregate.py --foh` coasts the held box between answers (costs nothing, reversible
            frame by frame, changes no pixel the model sees)

Both, neither, or one: this prints the 2x2 and the paired test on the common clips.

The third column is the memory-poisoning check. If a mis-framed crop corrupts the memory bank the
damage ACCUMULATES, so the deficit grows from the first third of a clip to the last. If `lead`
simply frames worse, the deficit is flat. Same clips, same frames, so the thirds are comparable.

    analysis/lead.py raw/paced-sweep-30 raw/paced-lead-30
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
from aggregate import extrapolate, held, score_one  # noqa: E402
from render_overlay import iou  # noqa: E402


def thirds(path: Path, foh: bool) -> list[float]:
    """Mean IoU over the first, middle and last third of the clip's scored frames."""
    res = json.loads(path.read_text())
    gt = data.boxes(res["meta"]["seq"])
    rows = held(res["rows"], res["meta"]["fps_stream"], len(gt))
    if foh:
        rows = extrapolate(rows)
    ious = [0.0 if rows.get(i, {}).get("box") is None else iou(g, rows[i]["box"])
            for i, g in enumerate(gt) if g is not None]
    return [float(np.mean(c)) for c in np.array_split(np.array(ious), 3)]


def load(d: str, foh: bool, arm: str | None = None) -> dict:
    """seq -> (scored row, path). Keyed by seq, so a run dir with several arms needs `arm`."""
    out = {}
    for p in sorted(Path(d).glob("*.json")):
        if p.stem == "manifest":
            continue
        r = score_one(p, foh)
        if arm is None or r["arm"] == arm:
            out[r["seq"]] = (r, p)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("control", help="run dir holding the plain arm (paced)")
    ap.add_argument("lead", help="run dir holding the lead arm (paced)")
    ap.add_argument("--arm", default="sam2_c512", help="which arm in `control` is the control")
    args = ap.parse_args()

    print(f"{'':22s}{'ZOH':>18s}{'FOH':>18s}")
    print(f"{'brazo':22s}{'mIoU':>8s}{'@0.5':>10s}{'mIoU':>8s}{'@0.5':>10s}")
    cells = {}
    for tag, d in (("control", args.control), ("lead", args.lead)):
        line = ""
        for foh in (False, True):
            rows = [r for r, _ in load(d, foh, args.arm if tag == "control" else None).values()]
            cells[(tag, foh)] = {r["seq"]: r["mean_iou"] for r in rows}
            line += f"{np.median([r['mean_iou'] for r in rows]):8.3f}{np.median([r['iou@0.5'] for r in rows]):10.3f}"
        name = rows[0]["arm"]
        print(f"{name:22s}{line}   n={len(rows)}")

    print(f"\npareado, lead menos control\n{'salida':8s}{'n':>4s}{'d mediana':>11s}{'gana':>9s}{'p':>10s}")
    for foh in (False, True):
        a, b = cells[("lead", foh)], cells[("control", foh)]
        common = sorted(set(a) & set(b))
        d = np.array([a[s] - b[s] for s in common])
        p = wilcoxon(d).pvalue if np.any(d) else 1.0
        print(f"{'FOH' if foh else 'ZOH':8s}{len(d):4d}{np.median(d):+11.3f}"
              f"{(d > 0).sum():5d}/{len(d):<3d}{p:10.1e}")

    # memory poisoning: does the deficit grow along the clip?
    ctl = {s: p for s, (_, p) in load(args.control, False, args.arm).items()}
    led = {s: p for s, (_, p) in load(args.lead, False).items()}
    common = sorted(set(ctl) & set(led))
    dt = np.array([np.array(thirds(led[s], False)) - np.array(thirds(ctl[s], False))
                   for s in common])
    print(f"\ndeficit de `lead` por tercio del clip, ZOH, n={len(common)}")
    print(f"{'':8s}{'1o':>9s}{'2o':>9s}{'3o':>9s}")
    print(f"{'mediana':8s}" + "".join(f"{v:+9.3f}" for v in np.median(dt, 0)))
    print(f"{'media':8s}" + "".join(f"{v:+9.3f}" for v in dt.mean(0)))
    slope = dt[:, 2] - dt[:, 0]
    p = wilcoxon(slope).pvalue if np.any(slope) else 1.0
    print(f"3o menos 1o: mediana {np.median(slope):+.3f}, p={p:.1e} "
          f"-- negativo y significativo = el deficit CRECE, compatible con memoria envenenada")


if __name__ == "__main__":
    main()
