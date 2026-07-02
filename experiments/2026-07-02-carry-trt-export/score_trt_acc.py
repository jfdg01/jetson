"""E1 step 5 host scorer: IoU@0.25 vs AerialMind GT for eager vs fp16-TRT carry (M0205 tid 20).

Reads raw/boxes_trt.json (per-clip-index mask boxes dumped on the Jetson; clip idx i = M0205
frame START+i) and scores both runs against GT on the labeled frames. Gate: fp16 IoU@0.25
within 1 pp of eager (the parent's OP=768 number is 0.830 over 186 tracks; here we check the
single window doesn't regress under fp16).

  .venv-ft/bin/python score_trt_acc.py --seq M0205 --tid 20 --start 395
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "2026-07-01-temporal-acquire-carry"))
from aerialmind import load_sequences  # noqa: E402


def iou(a, b):
    if a is None or b is None:
        return 0.0
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def score(pred_by_idx, gt_by_frame, start):
    ious = []
    for frame, gt in sorted(gt_by_frame.items()):
        idx = str(frame - start)
        if idx in pred_by_idx:
            ious.append(iou(pred_by_idx[idx], gt))
    at25 = sum(v >= 0.25 for v in ious) / len(ious)
    mean = sum(ious) / len(ious)
    return at25, mean, len(ious)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boxes", default=str(HERE / "raw/boxes_trt.json"))
    ap.add_argument("--seq", required=True)
    ap.add_argument("--tid", type=int, required=True)
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--cap", type=int, default=100)
    a = ap.parse_args()

    data = json.load(open(a.boxes))
    seq = next(s for s in load_sequences() if s.name == a.seq)
    track = seq.tracks()[a.tid]
    gt = {n: b for n, b in track.boxes.items() if a.start <= n < a.start + a.cap}

    for run in ("eager", "trt"):
        at25, mean, n = score(data[run], gt, a.start)
        print(f"{run:6s}  IoU@0.25={at25:.4f}  meanIoU={mean:.4f}  labeled_frames={n}")

    e25 = score(data["eager"], gt, a.start)[0]
    t25 = score(data["trt"], gt, a.start)[0]
    d = abs(t25 - e25)
    print(f"delta IoU@0.25 = {d*100:.2f} pp (gate: within 1 pp)")
    assert d <= 0.01 + 1e-9, f"fp16 accuracy proxy FAIL: delta {d*100:.2f} pp"
    print("fp16 accuracy proxy PASS")


if __name__ == "__main__":
    main()
