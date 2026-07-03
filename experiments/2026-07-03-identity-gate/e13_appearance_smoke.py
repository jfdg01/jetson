"""E13 precondition smoke: two facts the decoy legs assume, checked before any
SITL time is spent.

1. Decoy-capture: does the deployed VLM (Qwen2-VL-2B Q8_0, greedy) still box a
   215-shaded decoy as "the white car" when it is the ONLY car in frame? That
   is the E3-S2 wrong-lock situation (the wrong-lock decision happens while
   the true car is occluded), so if the shade change alone already stops the
   VLM boxing the decoy, there is no failure left for the gate to fix and the
   matrix is NOT-MEASURABLE at this shade.
2. Descriptor separability: on exact-geometry (oracle) crops, are all true-car
   descriptors within APP_TAU of the pose-0 template and all decoy descriptors
   beyond it? This is the gate's entire discriminative claim, measured with
   the box variable removed.

Also recorded (descriptive, NOT gated): on two-car frames (true + 215 decoy at
the E9 escort offset), which car does "the white car" land on? This informs the
win-path mechanism (proposal preference for the whiter car) but is not a
precondition -- the gate is designed to work even when the VLM prefers the
decoy.

Renders 10 DISTINCT copter poses (greedy decoding is deterministic per frame,
so pose variation is the only way to get independent draws), no bridge, alt
10 m, same pose set as the E9 color smoke.

    .venv-ft/bin/python experiments/2026-07-03-identity-gate/e13_appearance_smoke.py

PASS iff decoy_hits_of_10 >= 7 AND max(true_dists) <= APP_TAU AND
min(decoy_dists) > APP_TAU. Writes runs/appearance-smoke/results.json.
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
from phase3_sitl import appearance_descriptor  # noqa: E402
from sitl_cam import NadirCam, world_to_px  # noqa: E402

from sitl.oracle_bbox import FOCAL_PX, IMG_H, IMG_W  # noqa: E402

CAPTION = "the white car"
CAR = (0.5, 0.0, 0.0)              # target position for every frame variant
TWOCAR_DECOY = (-2.0, 3.0, 0.0)    # E9 escort offset, reused for the pref check
FAR = (60.0, 0.0, 0.0)             # true car parked far outside the FOV
DECOY_SHADE = (215, 215, 215)      # keep in sync with the run matrix
APP_TAU = 12.0                     # keep in sync with phase3_sitl --app-tau
SMOKE_MIN = 7
POSES = [((0.1 * k - 0.5, 0.15 * k - 0.7, -10.0), 0.06 * k - 0.3)
         for k in range(10)]       # same distinct-pose trick as e9_color_smoke


def oracle_box(target, cop, yaw):
    """Exact axis-aligned car rect from known geometry (yaw <= 0.3 rad, the
    rotation slack is absorbed by the descriptor's bright-quartile selection)."""
    u, v = world_to_px(target[:2], cop, yaw)[0]
    s = FOCAL_PX / -cop[2]
    return (u - s, v - 2 * s, u + s, v + 2 * s)  # 2 x 4 m body


def main() -> None:
    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend

    cam = NadirCam()  # no bridge
    raw = HERE / "raw" / "appearance-smoke"
    raw.mkdir(parents=True, exist_ok=True)

    print("booting Jetson q8_0 server...", flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=1024)
    template = None
    true_dists, decoy_dists = [], []
    decoy_hits, pref_true = 0, 0
    draws = []
    try:
        for i, (cop, yaw) in enumerate(POSES):
            # (a) true-only frame: descriptor separability reference
            ft = cam.render(cop, yaw, CAR)
            dt = appearance_descriptor(ft, oracle_box(CAR, cop, yaw))
            if template is None:
                template = dt  # pose-0 crop = the template analog
            true_dists.append(round(float(abs(dt - template).max()), 1))

            # (b) decoy-only frame: descriptor + VLM decoy-capture draw
            fd = cam.render(cop, yaw, FAR, distractor_ned=CAR,
                            distractor_color=DECOY_SHADE)
            dd = appearance_descriptor(fd, oracle_box(CAR, cop, yaw))
            decoy_dists.append(round(float(abs(dd - template).max()), 1))
            fp = raw / f"pose{i}-decoy.png"
            cv2.imwrite(str(fp), fd)
            box, wall = vlm_acquire(be, str(fp), CAPTION, IMG_W, IMG_H)
            c = world_to_px(CAR[:2], cop, yaw)[0]
            hit, d = False, None
            if box is not None:
                d = math.hypot((box[0] + box[2]) / 2 - c[0],
                               (box[1] + box[3]) / 2 - c[1])
                hit = d < 80.0
            decoy_hits += hit

            # (c) two-car frame: VLM preference (descriptive only)
            f2 = cam.render(cop, yaw, CAR, distractor_ned=TWOCAR_DECOY,
                            distractor_color=DECOY_SHADE)
            fp2 = raw / f"pose{i}-twocar.png"
            cv2.imwrite(str(fp2), f2)
            box2, wall2 = vlm_acquire(be, str(fp2), CAPTION, IMG_W, IMG_H)
            pref = None
            if box2 is not None:
                cx, cy = (box2[0] + box2[2]) / 2, (box2[1] + box2[3]) / 2
                cdk = world_to_px(TWOCAR_DECOY[:2], cop, yaw)[0]
                pref = ("true" if math.hypot(cx - c[0], cy - c[1])
                        < math.hypot(cx - cdk[0], cy - cdk[1]) else "decoy")
            pref_true += pref == "true"
            draws.append({"pose": i, "decoy_box": box2 and list(box2),
                          "decoy_only_box": box and list(box),
                          "decoy_hit": hit,
                          "d_decoy_px": round(d, 1) if d is not None else None,
                          "twocar_pref": pref,
                          "walls_s": [round(wall, 2), round(wall2, 2)]})
            print(f"pose{i}: decoy_hit={hit} d={d} "
                  f"true_dist={true_dists[-1]} decoy_dist={decoy_dists[-1]} "
                  f"twocar_pref={pref}", flush=True)
    finally:
        be.close()

    ok = (decoy_hits >= SMOKE_MIN and max(true_dists) <= APP_TAU
          and min(decoy_dists) > APP_TAU)
    out = HERE / "runs" / "appearance-smoke"
    out.mkdir(parents=True, exist_ok=True)
    summary = {"pass": ok, "decoy_hits_of_10": decoy_hits,
               "pref_true_of_10": pref_true,
               "template_bgr": [round(float(x), 1) for x in template],
               "true_dists": true_dists, "decoy_dists": decoy_dists,
               "app_tau": APP_TAU, "decoy_shade": DECOY_SHADE[0],
               "draws": draws}
    (out / "results.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in
                      ("pass", "decoy_hits_of_10", "pref_true_of_10",
                       "true_dists", "decoy_dists")}, indent=2))


if __name__ == "__main__":
    main()
