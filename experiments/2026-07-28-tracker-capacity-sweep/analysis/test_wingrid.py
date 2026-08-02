#!/usr/bin/env python3
"""Self-check for the window-vs-input split (`Sam2CropArm(image_size=...)`).

Two things could silently be no-ops: the arm could feed the model a window of the wrong side, or
the `upscales` gate could start vetoing jobs it used to allow. Both are checked without loading
SAM2 -- the inner arm is stubbed and only its recorded `image_size` and the crop shape matter.

    analysis/test_wingrid.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "device"))
import trackers  # noqa: E402


class Stub:
    """Records what it was constructed with and what it was fed."""

    def __init__(self, checkpoint, image_size):
        self.image_size, self.conf, self.fed = image_size, 1.0, []

    def init(self, sub, box):
        self.fed.append(sub.shape[:2])
        return box, []

    def step(self, sub):
        self.fed.append(sub.shape[:2])
        return [10, 10, 30, 30], []


def main() -> None:
    trackers.Sam2Arm, real = Stub, trackers.Sam2Arm
    frame = np.zeros((720, 1280, 3), np.uint8)
    for win, inp in [(640, 512), (512, 640), (512, 0)]:
        a = trackers.Sam2CropArm("ck", win, image_size=inp)
        a.init(frame, [600, 300, 640, 340])
        a.step(frame)
        assert a.inner.image_size == (inp or win), (win, inp, a.inner.image_size)
        assert a.inner.fed == [(win, win)] * 2, (win, inp, a.inner.fed)
        assert a.win[2] == win
    trackers.Sam2Arm = real

    # the gate moved from `image_size` to `crop`; every arm written before the split has them equal,
    # so no existing veto may change. 720x480 is the `uav*` shape that vetoes the 640+ arms.
    for name, m in trackers.REGISTRY.items():
        if (m["family"] == "sam2crop" and m.get("crop") == m.get("image_size")
                and not m.get("search_factor")):
            assert trackers.upscales(name, 720, 480) == (m["image_size"] > 480), name
    assert trackers.upscales("sam2_w640_i512", 720, 480) is True    # 640 window > 480, as `c640`
    assert trackers.upscales("sam2_w512_i640", 720, 480) is True    # 512 > 480 too, as `c512`
    assert trackers.upscales("sam2_w512_i640", 1280, 720) is False  # fits: the 640 input is free
    assert trackers.upscales("sam2_w640_i512", 1280, 720) is False
    print("ok: ventana y entrada desacopladas, la puerta `upscales` sin cambios")


if __name__ == "__main__":
    main()
