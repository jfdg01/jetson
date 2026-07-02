"""E6 Stage 0 diagnostic (run at design time, before the SITL matrix): why is the
t=0 acquire rejected in ~half the high-speed trials (E5: 31/32 rejects, lock lottery)?

The SITL frame is a deterministic render (NadirCam) and the VLM decodes greedily
(temperature=0), so each frame has exactly ONE answer -- the E5 "acquire lottery"
must live in frame content (rover dash-phase / altitude jitter at t=0), not in
sampling. This bench re-renders the t=0 frame over a grid of rover positions
(full 4 m dash period, includes the observed ~0.5 m) and altitudes, runs the
deployed VLM (Jetson q8_0 over ssh, same JetsonBackend/vlm_acquire as
phase3_sitl), and logs per frame: the box, the size-prior ratios rw/rh, the
accept/reject verdict, and IoU vs the oracle car box.

    .venv-ft/bin/python experiments/2026-07-03-first-acquire/acquire_bench.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TA = ROOT / "experiments" / "2026-07-01-temporal-acquire-carry"
sys.path.insert(0, str(TA))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "runners"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from sitl_cam import NadirCam  # noqa: E402
from sitl.oracle_bbox import (  # noqa: E402
    FOCAL_PX, IMG_H, IMG_W, TARGET_LEN_M, TARGET_WID_M, project)
from follow_demo import vlm_acquire  # noqa: E402

CAPTION = "the white car"  # phase3_sitl.CAPTION
ALT = 8.8                  # pb.TAKEOFF_ALT_M; E5 CSVs hover at 8.8-8.9


def ratios(box, alt):
    """The phase3_sitl.validate size-prior ratios (accept iff both in [0.5, 2.0])."""
    rw = (box[2] - box[0]) / (FOCAL_PX * TARGET_WID_M / alt)
    rh = (box[3] - box[1]) / (FOCAL_PX * TARGET_LEN_M / alt)
    return rw, rh


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ar = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ar if ar > 0 else 0.0


def main() -> None:
    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend

    out_dir = HERE / "raw" / "stage0"
    out_dir.mkdir(parents=True, exist_ok=True)

    # rover_n sweep spans a full 4 m dash period (dashes: 2 m painted / 2 m gap);
    # the observed t=0 rover_n across E4/E5 runs is ~0.5. alt sweep covers the
    # takeoff-settle jitter seen in the CSVs (8.6-9.2).
    cases = [("phase", round(rn, 2), ALT) for rn in np.arange(0.0, 4.0, 0.25)]
    cases += [("alt", 0.5, a) for a in (8.6, 9.0, 9.2)]

    # bridge at its 1.0 m/s trial location (out of FOV at t=0; kept for fidelity)
    cam = NadirCam(bridge_n=(28.5, 37.5), road_e=0.0)

    print("[stage0] booting Jetson q8_0 server...", flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=1024)
    rows = []
    try:
        for kind, rn, alt in cases:
            frame = cam.render((0.0, 0.0, -alt), 0.0, (rn, 0.0, 0.0))
            name = f"{kind}_rn{rn:.2f}_alt{alt:.1f}"
            png = out_dir / f"{name}.png"
            cv2.imwrite(str(png), frame)
            box, wall = vlm_acquire(be, str(png), CAPTION, IMG_W, IMG_H)
            gt = project((0.0, 0.0, -alt), (rn, 0.0, 0.0), 0.0, 0.0, 0.0)
            gt_xyxy = (gt["cx"] - gt["w"] / 2, gt["cy"] - gt["h"] / 2,
                       gt["cx"] + gt["w"] / 2, gt["cy"] + gt["h"] / 2)
            row = {"case": name, "kind": kind, "rover_n": rn, "alt": alt,
                   "wall_s": round(wall, 2), "box": None, "rw": None, "rh": None,
                   "accept": False, "iou_gt": None}
            if box is not None:
                rw, rh = ratios(box, alt)
                row.update(box=[round(v, 1) for v in box],
                           rw=round(rw, 3), rh=round(rh, 3),
                           accept=0.5 <= rw <= 2.0 and 0.5 <= rh <= 2.0,
                           iou_gt=round(iou(box, gt_xyxy), 3))
            rows.append(row)
            print(f"  {name}: box={row['box']} rw={row['rw']} rh={row['rh']} "
                  f"accept={row['accept']} iou={row['iou_gt']} wall={row['wall_s']}s",
                  flush=True)
    finally:
        be.close()

    n_acc = sum(r["accept"] for r in rows)
    summary = {"n": len(rows), "n_accept": n_acc,
               "accept_rate": round(n_acc / len(rows), 3),
               "model": f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
               "caption": CAPTION, "max_side": 1024,
               "prior": "rw,rh in [0.5,2.0] @ render alt",
               "date": time.strftime("%Y-%m-%dT%H:%MZ")}
    (out_dir / "results.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
