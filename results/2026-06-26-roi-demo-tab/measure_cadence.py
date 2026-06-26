"""Measure the real on-Orin anchor wall for the deployed terse+ROI system, to set the
demo's anchor cadence (`grounding/deploy/video.py:ANCHOR_PERIOD_S`) from data instead of
the stale T0/T4 JSON-anchor 2.26 s.

Times the exact paths the GUI/video loop blocks on (`video._anchor_box`):
  - cold acquire  = full-frame @ deploy max_side (1024), terse decode
  - ROI re-anchor = 512 crop around the prior box, terse decode (the prefill lever)

Wall-clock of `backend.generate()` (incl. ssh + image transfer) — that is what the demo
actually waits on per anchor. 15 W, clocks default. Run under .venv-ft on the host:

    .venv-ft/bin/python results/2026-06-26-roi-demo-tab/measure_cadence.py
"""
import statistics
import time

from PIL import Image

from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
from grounding.deploy.video import _REMOTE_MODELS, _REMOTE_MMPROJ, _anchor_box
from grounding.eval.backends import JetsonBackend

# 5 committed example images + a referring phrase keyed off the filename (box quality is
# irrelevant to timing; we only need a parseable anchor to seed the ROI crop).
CASES = [
    ("examples/images/white-car.jpg", "the white car"),
    ("examples/images/red-car.jpg", "the red car"),
    ("examples/images/blue-car.jpg", "the blue car"),
    ("examples/images/black-car-right.jpg", "the black car"),
    ("examples/images/small-bus.jpg", "the bus"),
]
REPS = 2  # per image per mode → median over 10 samples


def _timed(backend, img, caption, prior, use_roi):
    t0 = time.perf_counter()
    box = _anchor_box(backend, img, caption, prior, use_roi)
    return (time.perf_counter() - t0) * 1000.0, box


def main():
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=1024)
    acquire, reanchor = [], []
    try:
        for path, cap in CASES:
            img = Image.open(path).convert("RGB")
            seed = _anchor_box(be, img, cap, None, False)  # warm + a prior for ROI
            print(f"{path}  seed box={seed}", flush=True)
            for _ in range(REPS):
                ms, _ = _timed(be, img, cap, None, False)
                acquire.append(ms)
                print(f"  full-frame acquire  {ms:7.0f} ms", flush=True)
                ms, _ = _timed(be, img, cap, seed, True)
                reanchor.append(ms)
                print(f"  ROI re-anchor       {ms:7.0f} ms", flush=True)
    finally:
        be.close()

    def report(name, xs):
        print(f"\n{name}: median {statistics.median(xs):.0f} ms "
              f"(min {min(xs):.0f}, max {max(xs):.0f}, n={len(xs)})")
    report("full-frame acquire", acquire)
    report("ROI re-anchor", reanchor)


if __name__ == "__main__":
    main()
