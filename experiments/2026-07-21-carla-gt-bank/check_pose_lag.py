#!/usr/bin/env python3
"""Is the GT projected from the camera pose of THIS frame, or the previous one?

    .venv-ft/bin/python experiments/2026-07-21-carla-gt-bank/check_pose_lag.py

A one-frame-stale camera pose is the defect that costs the most and shows the
least: every box stays plausible, tight, and wrong, and no log mentions it. It is
the same class as the P5.13 zero-order-hold and the Phase C sky camera.

`capture_clip` projects GT from `cams[0][0].get_transform()` read *after*
`world.tick()`, on the assumption that this returns the pose the server just
rendered from rather than the one from before the tick. This script tests that
assumption offline, with no server, from the bank's own output.

The trick is the `track_gain == 0.0` clips: their commanded camera path is a
closed form in the frame index alone (start + bounded drift along a fixed
heading), independent of where any vehicle drove. So the pose commanded at frame
i and at frame i-1 are both computable, and the logged pose can be scored against
each. Whichever it matches is the answer.

Fast-tracking clips then bound the damage of the residual question this cannot
settle -- whether the *render* lagged the actor transform -- by converting one
camera step into pixels at that clip's altitude.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runners"))
from carla_gt_bank import W, FOV                      # noqa: E402

BANK = Path(__file__).resolve().parent / "runs" / "bank"


def clips():
    """Manifest-first, so a clip still being captured is skipped rather than
    half-read: the manifest is written last."""
    for man in sorted(BANK.glob("clip*/manifest.json")):
        gt = man.parent / "gt.jsonl"
        if gt.exists():
            yield json.loads(man.read_text()), gt


def rows_of(gt):
    return [json.loads(line) for line in gt.read_text().splitlines()]


def lag_test(m, rows):
    """Score the logged pose against commanded(i) and commanded(i-1)."""
    n0, e0 = m["cam_start"]
    hdg = math.radians(m["heading"])
    n = len(rows)

    def cmd(i):
        drift = m["drift_m"] * (i / max(1, n - 1))
        return n0 + drift * math.cos(hdg), e0 + drift * math.sin(hdg)

    cur = lag = 0.0
    for r in rows[1:]:
        i = r["i"]
        p = (r["cam"][0], r["cam"][1])
        cur += math.dist(p, cmd(i))
        lag += math.dist(p, cmd(i - 1))
    k = n - 1
    return cur / k, lag / k, math.dist(cmd(1), cmd(0))


def px_per_m(alt):
    return (W / 2) / math.tan(math.radians(FOV) / 2) / alt


def main():
    fixed = [(m, r) for m, r in ((m, rows_of(g)) for m, g in clips())
             if m["track_gain"] == 0.0 and m["drift_m"] > 0]
    if not fixed:
        print("no track_gain=0 drift>0 clip captured yet -- cannot test", file=sys.stderr)
        return 1

    print("== is the logged pose current, or one frame stale? ==")
    verdicts = []
    for m, rows in fixed:
        cur, lag, step = lag_test(m, rows)
        ok = cur < lag / 2          # unambiguous, not merely closer
        verdicts.append(ok)
        print(f"{m['clip']}  step {step * 100:5.2f} cm   "
              f"current {cur * 100:6.4f} cm   stale {lag * 100:6.4f} cm   "
              f"-> {'CURRENT' if ok else 'STALE/AMBIGUOUS'}")

    print("\n== bound if the render lagged the actor pose by one tick ==")
    worst = 0.0
    for m, g in clips():
        rows = rows_of(g)
        steps = sorted(math.dist(rows[i]["cam"][:2], rows[i - 1]["cam"][:2])
                       for i in range(1, len(rows)))
        p95 = steps[int(0.95 * len(steps))] * px_per_m(m["alt"])
        worst = max(worst, p95)
        print(f"{m['clip']}  alt {m['alt']:5.0f}  gain {m['track_gain']:4.1f}  "
              f"p95 one-tick offset {p95:5.2f} px")
    print(f"\nworst-case bound across the bank: {worst:.2f} px")

    ok = all(verdicts)
    print(f"\nVERDICT: {'PASS' if ok else 'FAIL'} -- "
          f"GT is projected from the current frame's camera pose"
          if ok else "\nVERDICT: FAIL -- pose may be one frame stale")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
