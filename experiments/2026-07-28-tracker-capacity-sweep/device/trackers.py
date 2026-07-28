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

for _n in ["TrackerNano", "TrackerVit", "TrackerDaSiamRPN", "TrackerGOTURN", "TrackerMIL", "TrackerCSRT"]:
    arm(_n.replace("Tracker", "cv_").lower(), family="opencv")(lambda n=_n: CvArm(n))


def build(name: str):
    if name not in REGISTRY:
        raise SystemExit(f"unknown arm {name!r}; have: {', '.join(sorted(REGISTRY))}")
    return REGISTRY[name]["factory"]()


if __name__ == "__main__":
    print(len(REGISTRY), "arms:", ", ".join(sorted(REGISTRY)))
