"""E14 precondition smoke: the facts the mk-decoy legs assume, checked with
real SAM2 inits before any SITL time is spent.

1. Decoy-capture (unchanged from E13): does the deployed VLM (Qwen2-VL-2B
   Q8_0, greedy) still box a 215-shaded decoy as "the white car" when it is
   the ONLY car in frame? If not, there is no wrong-lock left to fix and the
   matrix is NOT-MEASURABLE at this shade. (E13 measured 10/10.)
2. Mask-descriptor separability, with the REAL latch: StreamCarry init on the
   oracle box, mask_descriptor over its frame-0 mask. All true-car dists from
   the pose-0 template <= APP_TAU, all decoy dists > APP_TAU.
3. Blend-latch rejection -- the exact E13 killer: on the bridge-emergence
   geometry (215 decoy parked 2 m past the north edge, true car nose emerged
   e in {0.5, 1.0, 1.5, 2.0} m -- the window where E13's crop gate ACCEPTED),
   a SAM2 init on the two-car blend box (visible true strip + full decoy)
   must be REJECTED by the mask gate (dist > APP_TAU vs the 245 template).
   Plus the relock win path: a true-strip-only box at e=3.0 must be ACCEPTED.

E13's two-car VLM preference check is not repeated: same VLM, same greedy
decoding, same frames -> E13's measurement (pref_true 4/10, descriptive)
stands.

Renders the same 10 distinct copter poses as E13/E9 (greedy decoding is
deterministic per frame, so pose variation is the only way to get independent
draws), alt 10 m. SAM2 runs on the host GPU; the Jetson boots for the VLM
draws only.

    .venv-ft/bin/python experiments/2026-07-03-mask-identity/e14_mask_smoke.py

PASS iff decoy_hits_of_10 >= 7 AND max(true_dists) <= APP_TAU AND
min(decoy_dists) > APP_TAU AND all 4 blend probes REJECT AND the true-strip
probe ACCEPTs. Writes runs/mask-smoke/results.json.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
TAC = HERE.parent / "2026-07-01-temporal-acquire-carry"
sys.path.insert(0, str(TAC))
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[1] / "runners"))

from follow_demo import vlm_acquire  # noqa: E402
from phase3_sitl import mask_descriptor  # noqa: E402
from sitl_cam import NadirCam, world_to_px  # noqa: E402
from stream_carry import StreamCarry  # noqa: E402

from sitl.oracle_bbox import (  # noqa: E402
    FOCAL_PX, IMG_H, IMG_W, TARGET_LEN_M, TARGET_WID_M)

CAPTION = "the white car"
CAR = (0.5, 0.0, 0.0)              # target position for every pose frame
FAR = (60.0, 0.0, 0.0)             # true car parked far outside the FOV
DECOY_SHADE = (215, 215, 215)      # keep in sync with the run matrix
APP_TAU = 12.0                     # keep in sync with phase3_sitl --app-tau
SMOKE_MIN = 7
POSES = [((0.1 * k - 0.5, 0.15 * k - 0.7, -10.0), 0.06 * k - 0.3)
         for k in range(10)]       # same distinct-pose trick as e13/e9
HL, HW = TARGET_LEN_M / 2, TARGET_WID_M / 2
BRIDGE = (10.0, 20.0)              # bridge N-extent for the emergence probes
DECOY_N = BRIDGE[1] + 2.0 + HL     # rear 2 m past the north edge (E3 geometry)
EMERGENCE = (0.5, 1.0, 1.5, 2.0)   # E13 accepted its blend boxes in this window


def oracle_box(target, cop, yaw):
    """Exact axis-aligned car rect from known geometry (yaw <= 0.3 rad; the
    latch absorbs the rotation slack -- SAM2 segments the car, not the box)."""
    u, v = world_to_px(target[:2], cop, yaw)[0]
    s = FOCAL_PX / -cop[2]
    return (u - s, v - 2 * s, u + s, v + 2 * s)  # 2 x 4 m body


def rect_px(cop, n0, n1, e0, e1):
    (u0, v0), (u1, v1) = world_to_px([(n1, e0), (n0, e1)], cop, 0.0)
    return (min(u0, u1), min(v0, v1), max(u0, u1), max(v0, v1))


def main() -> None:
    import torch
    from sam2.sam2_video_predictor import SAM2VideoPredictor

    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend

    predictor = SAM2VideoPredictor.from_pretrained("facebook/sam2.1-hiera-tiny")
    rgb = lambda f: np.ascontiguousarray(f[:, :, ::-1])  # noqa: E731

    def latch_median(frame_bgr, box):
        sc = StreamCarry(predictor, rgb(frame_bgr), box)
        d = mask_descriptor(frame_bgr, sc.init_mask)
        del sc
        return d

    cam = NadirCam()  # no bridge, pose frames
    raw = HERE / "raw" / "mask-smoke"
    raw.mkdir(parents=True, exist_ok=True)

    print("booting Jetson q8_0 server...", flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=1024)
    template = None
    true_dists, decoy_dists = [], []
    decoy_hits = 0
    draws, blends = [], []
    try:
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            for i, (cop, yaw) in enumerate(POSES):
                # (a) true-only frame: latch + descriptor, pose-0 = template
                ft = cam.render(cop, yaw, CAR)
                dt = latch_median(ft, oracle_box(CAR, cop, yaw))
                if template is None:
                    template = dt
                true_dists.append(round(float(abs(dt - template).max()), 1))

                # (b) decoy-only frame: latch descriptor + VLM decoy-capture
                fd = cam.render(cop, yaw, FAR, distractor_ned=CAR,
                                distractor_color=DECOY_SHADE)
                dd = latch_median(fd, oracle_box(CAR, cop, yaw))
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
                draws.append({"pose": i, "decoy_only_box": box and list(box),
                              "decoy_hit": hit,
                              "d_decoy_px": round(d, 1) if d is not None else None,
                              "wall_s": round(wall, 2)})
                print(f"pose{i}: decoy_hit={hit} d={d} "
                      f"true_dist={true_dists[-1]} decoy_dist={decoy_dists[-1]}",
                      flush=True)

            # (c) blend-latch probes on the E13 emergence geometry
            cam_b = NadirCam(bridge_n=BRIDGE)
            cop_b = (DECOY_N - 2.0, 0.0, -10.0)
            for e in EMERGENCE:
                true_n = BRIDGE[1] - HL + e  # center; nose = north edge + e
                f = cam_b.render(cop_b, 0.0, (true_n, 0.0, 0.0),
                                 distractor_ned=(DECOY_N, 0.0, 0.0),
                                 distractor_color=DECOY_SHADE)
                cv2.imwrite(str(raw / f"blend-e{e}.png"), f)
                bb = rect_px(cop_b, BRIDGE[1], DECOY_N + HL, -HW, HW)
                d = latch_median(f, bb)
                dist = float(abs(d - template).max()) if d is not None else None
                rejected = d is None or dist > APP_TAU
                blends.append({"emergence_m": e, "kind": "blend",
                               "median": d is not None and
                               [round(float(x), 1) for x in d],
                               "dist": dist and round(dist, 1),
                               "gate_rejects": rejected})
                print(f"blend e={e}: median={blends[-1]['median']} "
                      f"dist={blends[-1]['dist']} rejects={rejected}", flush=True)
            # (d) relock win path: true-strip box at e=3.0 must be ACCEPTED
            f = cam_b.render(cop_b, 0.0, (BRIDGE[1] - HL + 3.0, 0.0, 0.0),
                             distractor_ned=(DECOY_N, 0.0, 0.0),
                             distractor_color=DECOY_SHADE)
            cv2.imwrite(str(raw / "truestrip-e3.png"), f)
            d = latch_median(f, rect_px(cop_b, BRIDGE[1], BRIDGE[1] + 3.0, -HW, HW))
            strip_dist = float(abs(d - template).max()) if d is not None else None
            strip_accepts = d is not None and strip_dist <= APP_TAU
            blends.append({"emergence_m": 3.0, "kind": "true-strip",
                           "median": d is not None and
                           [round(float(x), 1) for x in d],
                           "dist": strip_dist and round(strip_dist, 1),
                           "gate_rejects": not strip_accepts})
            print(f"true-strip e=3.0: dist={blends[-1]['dist']} "
                  f"accepts={strip_accepts}", flush=True)
    finally:
        be.close()

    ok = (decoy_hits >= SMOKE_MIN and max(true_dists) <= APP_TAU
          and min(decoy_dists) > APP_TAU
          and all(b["gate_rejects"] for b in blends if b["kind"] == "blend")
          and strip_accepts)
    out = HERE / "runs" / "mask-smoke"
    out.mkdir(parents=True, exist_ok=True)
    summary = {"pass": ok, "decoy_hits_of_10": decoy_hits,
               "template_bgr": [round(float(x), 1) for x in template],
               "true_dists": true_dists, "decoy_dists": decoy_dists,
               "blend_probes": blends, "app_tau": APP_TAU,
               "decoy_shade": DECOY_SHADE[0], "draws": draws}
    (out / "results.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in
                      ("pass", "decoy_hits_of_10", "true_dists",
                       "decoy_dists")}, indent=2))
    print("blend_probes:", json.dumps(blends, indent=2))


if __name__ == "__main__":
    main()
