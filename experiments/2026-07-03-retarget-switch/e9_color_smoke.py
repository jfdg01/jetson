"""E9 precondition smoke: can the deployed VLM (Qwen2-VL-2B Q8_0, greedy) tell
"the white car" from "the blue car" on the synthetic nadir frames at all?

Renders 10 DISTINCT copter poses (greedy decoding is deterministic per frame,
so pose variation is the only way to get independent draws), each with the
white rover fixed at (0.5, 0, 0) and the blue escort at (-2.0, 3.0, 0) --
the exact E9 escort offset -- no bridge, alt 10 m. For each pose, one draw per
caption. Hit = returned box center is closer to the correct car's projected
center than to the wrong car's AND within 80 px of it.

    .venv-ft/bin/python experiments/2026-07-03-retarget-switch/e9_color_smoke.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
TAC = HERE.parent / "2026-07-01-temporal-acquire-carry"
sys.path.insert(0, str(TAC))
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[1] / "runners"))

from follow_demo import vlm_acquire  # noqa: E402
from sitl_cam import NadirCam, world_to_px  # noqa: E402

from sitl.oracle_bbox import IMG_H, IMG_W  # noqa: E402

ROVER = (0.5, 0.0, 0.0)
ESCORT = (-2.0, 3.0, 0.0)          # E9 lane offset: 2.5 m behind, +3 m east
ESCORT_COLOR = (230, 90, 40)       # keep in sync with phase3_sitl.ESCORT_COLOR
# 10 distinct poses: small copter offsets + yaws, both cars stay in frame
POSES = [((0.1 * k - 0.5, 0.15 * k - 0.7, -10.0), 0.06 * k - 0.3)
         for k in range(10)]


def main() -> None:
    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend

    cam = NadirCam()  # no bridge
    raw = HERE / "raw" / "color-smoke"
    raw.mkdir(parents=True, exist_ok=True)

    print("booting Jetson q8_0 server...", flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=1024)
    try:
        results = {"the white car": [], "the blue car": []}
        for i, (cop, yaw) in enumerate(POSES):
            frame = cam.render(cop, yaw, ROVER, distractor_ned=ESCORT,
                               distractor_color=ESCORT_COLOR)
            fp = raw / f"pose{i}.png"
            cv2.imwrite(str(fp), frame)
            centers = {"the white car": world_to_px(ROVER[:2], cop, yaw)[0],
                       "the blue car": world_to_px(ESCORT[:2], cop, yaw)[0]}
            for cap in results:
                right = centers[cap]
                wrong = centers["the blue car" if cap == "the white car"
                                else "the white car"]
                box, wall = vlm_acquire(be, str(fp), cap, IMG_W, IMG_H)
                hit, d = False, None
                if box is not None:
                    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                    d = math.hypot(cx - right[0], cy - right[1])
                    dw = math.hypot(cx - wrong[0], cy - wrong[1])
                    hit = d < dw and d < 80.0
                results[cap].append({"pose": i, "box": box, "hit": hit,
                                     "d_right_px": round(d, 1) if d is not None else None,
                                     "wall_s": round(wall, 2)})
                print(f"pose{i} {cap!r}: hit={hit} d={d}", flush=True)
    finally:
        be.close()

    summary = {c: sum(r["hit"] for r in rs) for c, rs in results.items()}
    out = HERE / "runs" / "color-smoke"
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(
        {"hits_of_10": summary, "draws": results}, indent=2))
    print(json.dumps({"hits_of_10": summary}, indent=2))


if __name__ == "__main__":
    main()
