"""Tracker registry. One uniform API so adding an arm is a function, not a script.

    init(frame_bgr, box_xyxy) -> None
    step(frame_bgr)           -> (box_xyxy | None, contours | None)

Everything streams frame-at-a-time. This is not a style choice: SAM2's batch path
(`init_state` over a directory) preloads the whole clip onto the GPU -- 535 frames at 1024 is
~6.7 GB -- and on 8 GB shared it dies with
`NVML_SUCCESS == r INTERNAL ASSERT FAILED at CUDACachingAllocator.cpp:1131`.
Streaming is also the path the rest of the project deploys, so the sweep measures what flies.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

REGISTRY: dict[str, dict] = {}


def arm(name: str, **meta):
    def deco(fn):
        REGISTRY[name] = {"factory": fn, **meta}
        return fn
    return deco


def mask_contours(mask: np.ndarray) -> list[list[list[int]]]:
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [c.reshape(-1, 2).tolist() for c in cnts]


class Sam2Arm:
    """SAM2 video predictor driven one frame at a time via the vendored StreamCarry.

    StreamCarry reuses the batch path's own `_run_single_frame_inference`, so the output is the
    same computation as `propagate_in_video` minus the preloading; its parity gate is per-frame
    IoU >= 0.99 stream-vs-batch.
    """

    def __init__(self, checkpoint: str, image_size: int):
        self.checkpoint, self.image_size = checkpoint, image_size
        self.carry = None
        self.torch = None

    def _amp(self):
        # StreamCarry is `@torch.inference_mode()` but does NOT autocast internally; all six
        # validated call sites in the project supply bf16 autocast. Without it the model runs
        # fp32 -- slower, and not the precision the rest of the project deploys and measures.
        return self.torch.autocast("cuda", dtype=self.torch.bfloat16)

    def init(self, frame, box):
        import torch
        from sam2.sam2_video_predictor import SAM2VideoPredictor

        from stream_carry import StreamCarry

        self.torch = torch
        # image_size must be set AT CONSTRUCTION via the hydra override, the way the rest of the
        # project does it. Assigning predictor.image_size afterwards leaves
        # sam_image_embedding_size and the prompt encoder at the checkpoint default, and any size
        # other than 1024 then dies on
        # `assert backbone_features.size(2) == self.sam_image_embedding_size`.
        predictor = SAM2VideoPredictor.from_pretrained(
            self.checkpoint, device="cuda",
            hydra_overrides_extra=[f"++model.image_size={self.image_size}"],
        )
        assert predictor.image_size == self.image_size
        torch.backends.cudnn.benchmark = False
        # StreamCarry wants RGB (it goes through PIL); the rig passes BGR everywhere.
        with self._amp():
            self.carry = StreamCarry(predictor, frame[:, :, ::-1].copy(), box)
        m = self.carry.init_mask
        return _box_of(m), mask_contours(m)

    def step(self, frame):
        with self._amp():
            mask, box = self.carry.step(frame[:, :, ::-1].copy())
        return (list(box) if box else None), mask_contours(mask)


def crop_window(center, size: int, w: int, h: int) -> tuple[int, int, int]:
    """`size`x`size` window centred on `center`, slid (not shrunk) to stay inside the frame.

    Same geometry as `analysis/render_overlay.py:crop_box` -- five lines, deliberately duplicated
    rather than shared, because host and device do not import from each other.
    """
    s = min(size, w, h)
    x = int(round(min(max(center[0] - s / 2, 0), w - s)))
    y = int(round(min(max(center[1] - s / 2, 0), h - s)))
    return x, y, s


class Sam2CropArm:
    """SAM2 fed only an NxN crop around the target, at native pixels (image_size == N).

    Same compute as the full-frame arm at the same `image_size`, but the frame is not downscaled,
    so the target keeps its original pixel size and loses context instead. This is the variable the
    resolution sweep confounds: `sam2_t512` shrinks a 26x16 truck to ~10x6, `sam2_c512` leaves it
    at 26x16 inside a 512 window.

    The window follows the arm's OWN last prediction, never GT -- GT past frame 0 does not exist on
    this device. A lost frame holds the last window rather than resetting to centre, which is the
    only chance the target has of walking back into view.

    Known ceiling: SAM2's memory bank sees a reference frame that translates every step, and
    nothing here tells it so. If the crop arms underperform, that is the first suspect.
    """

    def __init__(self, checkpoint: str, size: int):
        self.size = size
        self.inner = Sam2Arm(checkpoint, size)
        self.win = None  # (x, y, s) in full-frame coords
        self.last = None  # last full-frame box, the thing the window chases

    def _shift(self, box, dx, dy):
        return None if box is None else [box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy]

    def _crop(self, frame, center):
        h, w = frame.shape[:2]
        x, y, s = crop_window(center, self.size, w, h)
        self.win = (x, y, s)
        return frame[y:y + s, x:x + s]

    def init(self, frame, box):
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        sub = self._crop(frame, (cx, cy))
        x, y, _ = self.win
        b, cnts = self.inner.init(sub, [box[0] - x, box[1] - y, box[2] - x, box[3] - y])
        self.last = self._shift(b, x, y)
        return self.last, _shift_contours(cnts, x, y)

    def step(self, frame):
        if self.last is not None:  # re-centre on where the target was last seen
            cx, cy = (self.last[0] + self.last[2]) / 2, (self.last[1] + self.last[3]) / 2
            self._crop(frame, (cx, cy))
        x, y, s = self.win  # a lost frame keeps the previous window
        b, cnts = self.inner.step(frame[y:y + s, x:x + s])
        self.last = self._shift(b, x, y)
        return self.last, _shift_contours(cnts, x, y)


def _shift_contours(cnts, dx, dy):
    if not cnts:
        return cnts
    return [[[p[0] + dx, p[1] + dy] for p in c] for c in cnts]


def _box_of(mask):
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


class CvArm:
    """OpenCV built-in trackers. Box-only: no mask, so `contours` is None."""

    def __init__(self, ctor_name: str):
        self.ctor_name = ctor_name
        self.t = None

    def init(self, frame, box):
        ctor = getattr(cv2, self.ctor_name)
        self.t = ctor.create() if hasattr(ctor, "create") else ctor()
        x1, y1, x2, y2 = box
        self.t.init(frame, (int(x1), int(y1), int(x2 - x1), int(y2 - y1)))
        return [int(v) for v in (x1, y1, x2, y2)], None

    def step(self, frame):
        ok, r = self.t.update(frame)
        if not ok:
            return None, None
        x, y, w, h = r
        return [int(x), int(y), int(x + w), int(y + h)], None


for _ck, _short in [("tiny", "t"), ("small", "s"), ("base-plus", "bp"), ("large", "l")]:
    for _sz in (512, 640, 768, 1024):
        arm(f"sam2_{_short}{_sz}", family="sam2", ckpt=_ck, image_size=_sz)(
            lambda ck=_ck, sz=_sz: Sam2Arm(f"facebook/sam2.1-hiera-{ck}", sz)
        )

# Crop arms only for tiny, and only up to 704. UAV123 clips are 1280x720, so a window above 720 is
# capped by frame height -- but 720 itself is not a legal Hiera input: the window pos-embed tiles at
# image_size/4 in blocks of 8, so image_size must be a multiple of 32 and 720 dies with
# `The size of tensor a (180) must match the size of tensor b (176)`. 704 is the largest that fits.
for _sz in (512, 640, 704):
    arm(f"sam2_c{_sz}", family="sam2crop", ckpt="tiny", image_size=_sz, crop=_sz)(
        lambda sz=_sz: Sam2CropArm("facebook/sam2.1-hiera-tiny", sz)
    )

for _n in ["TrackerNano", "TrackerVit", "TrackerDaSiamRPN", "TrackerGOTURN", "TrackerMIL", "TrackerCSRT"]:
    arm(_n.replace("Tracker", "cv_").lower(), family="opencv")(lambda n=_n: CvArm(n))


def build(name: str):
    if name not in REGISTRY:
        raise SystemExit(f"unknown arm {name!r}; have: {', '.join(sorted(REGISTRY))}")
    return REGISTRY[name]["factory"]()


def _check() -> None:
    """Crop geometry and the crop->full-frame coordinate round trip, without touching a GPU."""
    assert crop_window((640, 360), 512, 1280, 720) == (384, 104, 512)
    assert crop_window((10, 10), 512, 1280, 720) == (0, 0, 512)  # slid off the corner
    assert crop_window((1270, 710), 512, 1280, 720) == (768, 208, 512)
    assert crop_window((640, 360), 1024, 1280, 720) == (280, 0, 720)  # capped by frame height

    class FakeInner:  # returns the box it was given, so any coordinate slip shows up as an offset
        def __init__(self): self.last_in = None
        def init(self, sub, box): self.last_in = box; return list(box), [[[box[0], box[1]]]]
        def step(self, sub): return list(self.last_in), [[[self.last_in[0], self.last_in[1]]]]

    a = Sam2CropArm("x", 512)
    a.inner = FakeInner()
    frame = np.zeros((720, 1280, 3), np.uint8)
    box = [600, 340, 680, 380]
    b, cnts = a.init(frame, box)
    assert b == box, b  # crop then un-crop is the identity
    assert cnts == [[[600, 340]]], cnts
    assert a.win == (384, 104, 512), a.win
    b, _ = a.step(frame)
    assert b == box, b  # window re-centres on the same target, so the box does not move
    print("crop geometry ok")


if __name__ == "__main__":
    import sys as _sys
    if "--self-check" in _sys.argv:
        _check()
    else:
        print(len(REGISTRY), "arms:", ", ".join(sorted(REGISTRY)))
