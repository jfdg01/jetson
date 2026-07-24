#!/usr/bin/env python3
"""g6_gate.py -- the G6 grounding-over-CARLA capability gate (P6.2 prerequisite).

Question it answers
-------------------
Before any P6.x closed-loop number means anything, one thing has to be true: the
DEPLOYED grounding checkpoint (`phase3-terse100eos-1024-q8_0.gguf`, served on the
Jetson) must actually resolve the small nadir car it will be asked to follow. At the
P6.2 geometry -- CARLA `Town10HD_Opt`, 60 m AGL nadir, a ~17 px car -- that is not a
given: the model was trained/eval'd on UAV123, not sim renders, and a target this
small is where grounding fails silently. G6 is that gate. It is NOT the P6.2 verdict;
it only certifies the perception the whole flight matrix rests on.

What it does
------------
Reads ONE CARLA-captured PNG off disk (`--frame`) plus the known target pixel box
(`--box x0 y0 x1 y1`, produced by `run_p62_flight.actor_box` at capture time), runs
the deployed q8_0 grounding on the Jetson through `JetsonBackend` + `vlm_acquire`
(both reused verbatim, NOT reimplemented), and reports IoU@0.25 of the predicted box
vs the known box. PASS iff IoU >= 0.25. It does NOT boot CARLA -- it consumes a frame
another tool already rendered.

Machine of every number (R-2 discipline)
-----------------------------------------
- The predicted box + IoU: **Jetson Orin Nano 8 GB** (deployed q8_0 over SSH via
  `JetsonBackend`, 15 W + jetson_clocks, max_side=1024). The only on-device number.
- The IoU@0.25 PASS/FAIL classification: pure host logic (no device) -- `classify()`.
- The `--frame` render itself: RTX-3090 host (CARLA), captured earlier by the flight
  rig. Not produced here.

Reuse map
---------
- VLM grounding call: `experiments/2026-07-04-warm-start-acquire/replay_e24.py`
  `vlm_acquire` (imported inside `run_gate`, not at module top -- heavy path).
- Backend: `grounding.eval.backends.JetsonBackend` (imported inside `run_gate`).
- Remote model/mmproj paths: `grounding.deploy.{serve,video}` (the same symbols
  `replay_e24.run_matrix_clip` points the WARM/COLD acquire at).
- IoU geometry: `grounding.contract.iou` (stdlib-only module; None-safe wrapper here).

Run it for real (deferred -- needs the Jetson + a captured frame)
-----------------------------------------------------------------
    # frame + box come from a run_p62_flight capture (actor_box in the rows / overlay)
    .venv-ft/bin/python runners/g6_gate.py \
        --frame runs/p62_delivery/warm_seed03/overlay_00030.png \
        --box 312 236 329 251 --caption "the car" \
        --out runs/g6_gate/seed03

    # pure-logic check (no Jetson, no CARLA, no model):
    .venv-ft/bin/python runners/g6_gate.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from grounding.contract import iou as _contract_iou  # stdlib-only; safe at module top

THRESH = 0.25          # IoU@0.25 -- the P6.2 lock threshold (E18/P5 convention)
MAX_SIDE = 1024        # deployed full-frame acquire resolution (matches replay_e24)


def iou_safe(pred_box, gt_box) -> float:
    """IoU of two (x0,y0,x1,y1) boxes; 0.0 if either is None. Wraps the contract
    metric (which assumes both boxes exist) so a grounding miss scores 0, not a
    crash."""
    if pred_box is None or gt_box is None:
        return 0.0
    return float(_contract_iou(pred_box, gt_box))


def classify(pred_box, gt_box, thresh: float = THRESH):
    """The G6 decision, on already-obtained boxes -- the one piece of pure logic.

    Returns (passed, iou). PASS iff the deployed grounding's box overlaps the known
    target box at IoU >= `thresh`. A None prediction (parse-fail / no detection) is a
    FAIL at IoU 0.0, never an exception -- that is the exact case G6 exists to catch.
    """
    score = iou_safe(pred_box, gt_box)
    return (score >= thresh), score


def run_gate(frame_path: str, box, caption: str, *, ssh_host: str = "jetson",
             max_side: int = MAX_SIDE, out: str | None = None) -> dict:
    """Live G6: ground ONE captured frame on the Jetson and score vs `box`.

    Heavy imports (JetsonBackend, replay_e24.vlm_acquire, cv2) are pulled INSIDE
    this function so `--selftest` stays pure. Boots the deployed q8_0 server on the
    Jetson, runs one full-frame acquire, tears the server down, classifies.
    """
    import cv2  # noqa: PLC0415 -- guarded: selftest must not need cv2/model/SSH

    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend

    # vlm_acquire lives beside replay_e24; add its dir so the module (and its own
    # replay_source/warmstart imports) resolve, then reuse the symbol verbatim.
    e24_dir = REPO / "experiments" / "2026-07-04-warm-start-acquire"
    if str(e24_dir) not in sys.path:
        sys.path.insert(0, str(e24_dir))
    from replay_e24 import vlm_acquire  # noqa: PLC0415

    frame_path = str(frame_path)
    img = cv2.imread(frame_path)
    if img is None:
        raise FileNotFoundError(f"could not read frame: {frame_path}")
    h, w = img.shape[:2]

    print(f"[G6] booting Jetson q8_0 server (max_side={max_side})...", flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host=ssh_host, max_side=max_side)
    try:
        pred = vlm_acquire(be, frame_path, caption, w, h)   # ON-DEVICE (Orin) number
    finally:
        be.close()

    passed, score = classify(pred, box, THRESH)
    result = {
        "gate": "G6",
        "machine": "jetson-orin-nano-8gb (grounding) / rtx-3090 (render)",
        "frame": frame_path, "frame_wh": [w, h],
        "caption": caption, "max_side": max_side,
        "gt_box": [round(float(v), 1) for v in box],
        "pred_box": [round(float(v), 1) for v in pred] if pred else None,
        "iou": round(score, 4), "thresh": THRESH,
        "passed": bool(passed),
    }

    if out:
        out_dir = Path(out)
        out_dir.mkdir(parents=True, exist_ok=True)
        # look-at-it: draw GT (green) + predicted (green if PASS else red) and dump
        g = [int(v) for v in box]
        cv2.rectangle(img, (g[0], g[1]), (g[2], g[3]), (0, 255, 0), 1)
        if pred:
            p = [int(v) for v in pred]
            col = (0, 255, 0) if passed else (0, 0, 255)
            cv2.rectangle(img, (p[0], p[1]), (p[2], p[3]), col, 1)
        cv2.putText(img, f"G6 iou={score:.2f} {'PASS' if passed else 'FAIL'}",
                    (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        cv2.imwrite(str(out_dir / "g6_overlay.png"), img)
        (out_dir / "g6_result.json").write_text(json.dumps(result, indent=2))
        print(f"[G6] wrote {out_dir / 'g6_overlay.png'} -- OPEN IT before trusting the verdict")

    print(json.dumps(result, indent=2))
    print(f"[G6] {'PASS' if passed else 'FAIL'} "
          f"(iou={score:.3f} vs thresh {THRESH}); grounding measured on Jetson Orin.")
    return result


def selftest() -> None:
    """Pure-logic check of the IoU@0.25 PASS classifier on synthetic boxes.

    Never touches the Jetson, CARLA, a model, or cv2 (all guarded inside run_gate).
    Exercises the exact boundary at 0.25 and the None-prediction FAIL path -- the two
    things the gate hinges on.
    """
    a = (0.0, 0.0, 10.0, 10.0)

    # identical boxes -> IoU 1.0 -> PASS
    ok, s = classify(a, a)
    assert ok and abs(s - 1.0) < 1e-9, (ok, s)

    # partial overlap IoU = 50/150 = 0.333 -> PASS
    ok, s = classify((5.0, 0.0, 15.0, 10.0), a)
    assert ok and abs(s - (50.0 / 150.0)) < 1e-9, (ok, s)

    # box fully inside, area 25 in area 100 -> IoU exactly 0.25 -> PASS (>=)
    ok, s = classify((0.0, 0.0, 5.0, 5.0), a)
    assert ok and abs(s - 0.25) < 1e-9, ("boundary must pass", ok, s)

    # box fully inside, area 20 in area 100 -> IoU 0.20 -> FAIL (just below)
    ok, s = classify((0.0, 0.0, 4.0, 5.0), a)
    assert (not ok) and abs(s - 0.20) < 1e-9, ("just-below must fail", ok, s)

    # disjoint -> IoU 0 -> FAIL
    ok, s = classify((100.0, 100.0, 110.0, 110.0), a)
    assert (not ok) and s == 0.0, (ok, s)

    # the case G6 exists to catch: grounding returns nothing -> FAIL, not a crash
    ok, s = classify(None, a)
    assert (not ok) and s == 0.0, ("None prediction must FAIL at 0.0", ok, s)

    # None-safe both ways
    assert iou_safe(a, None) == 0.0 and iou_safe(None, None) == 0.0

    print("selftest OK")


def main() -> None:
    ap = argparse.ArgumentParser(description="G6 grounding-over-CARLA gate (on-device q8_0)")
    ap.add_argument("--selftest", action="store_true", help="pure-logic check; no Jetson/CARLA")
    ap.add_argument("--frame", help="CARLA-captured PNG frame to ground")
    ap.add_argument("--box", nargs=4, type=float, metavar=("X0", "Y0", "X1", "Y1"),
                    help="known target pixel box (from run_p62_flight.actor_box)")
    ap.add_argument("--caption", default="the car")
    ap.add_argument("--ssh-host", default="jetson")
    ap.add_argument("--max-side", type=int, default=MAX_SIDE)
    ap.add_argument("--out", help="output dir for g6_result.json + g6_overlay.png")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if not args.frame or not args.box:
        ap.error("need --frame and --box (or --selftest)")
    run_gate(args.frame, tuple(args.box), args.caption,
             ssh_host=args.ssh_host, max_side=args.max_side, out=args.out)


if __name__ == "__main__":
    main()
