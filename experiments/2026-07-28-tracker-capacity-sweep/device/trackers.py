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

import collections
import math
import os
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


def upscales(name: str, w: int, h: int) -> bool:
    """Would this arm have to invent pixels on a `w`x`h` clip?

    A clip that does not carry the resolution cannot be measured at it: SAM2 would be scored on
    interpolation, and two arms whose sizes both exceed the source stop being two treatments. The
    driver skips those jobs rather than writing a number that reads like the others.

    That reasoning holds for a FRAME and not for a SEARCH REGION, which is why the rule no longer
    applies to `search_factor` arms. A search region is a window sized by the target and resampled to
    the model input by definition -- every tracker in the lineage we compare against does exactly
    that, and at a 28 px target a factor-5 window is 140 px going into a 640 input. Gating on
    "the window is smaller than the input" would forbid the design the literature calls optimal.
    Whether that upsampling helps is the question `search-window` asks; it is not a validity check.

    Two rules remain. A FIXED crop is square and `crop_window` caps it at `min(w, h)`, so anything
    above that is pure upsampling on both axes. A full frame is squashed to `image_size` square
    regardless of aspect, so no single axis answers it -- 1280x720 into 768 upsamples vertically
    while downsampling horizontally, and still ends up with fewer pixels than it started with. Pixel
    budget is the honest comparison there.
    """
    m = REGISTRY[name]
    n = m.get("image_size")
    if n is None:
        return False  # opencv arms are handed the frame as it comes
    if m.get("search_factor"):
        return False
    return n > min(w, h) if m["family"] == "sam2crop" else n * n > w * h


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
        # `object_score_logits`, SAM2's own occlusion head: a TRAINED answer to "is the object in
        # this frame", not a by-product of localisation. It is the one arm family here that has a
        # real presence signal rather than a surrogate.
        self.conf = None

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
        self.conf = getattr(self.carry, "last_score", None)
        return (list(box) if box else None), mask_contours(mask)


def crop_window(center, size: int, w: int, h: int) -> tuple[int, int, int]:
    """`size`x`size` window centred on `center`, slid (not shrunk) to stay inside the frame.

    The FIXED-size geometry, kept because every committed result was measured with it and it is the
    control in `search-window`. Sliding is our own invention, not the literature's -- see
    `search_window` for what the trackers we compare against actually do.

    Same geometry as `analysis/render_overlay.py:crop_box` -- five lines, deliberately duplicated
    rather than shared, because host and device do not import from each other.
    """
    s = min(size, w, h)
    x = int(round(min(max(center[0] - s / 2, 0), w - s)))
    y = int(round(min(max(center[1] - s / 2, 0), h - s)))
    return x, y, s


def search_window(box, factor: float) -> tuple[int, int, int]:
    """Target-scaled square search region: side `factor * sqrt(area)`, centred on `box`.

    Byte-for-byte the arithmetic of `sample_target` in the STARK/OSTrack/AsymTrack lineage
    (`lib/train/data/processing_utils.py:30-39`), `ceil` included, so `sam2_f*` and `asym_b` ask for
    the same window given the same box and only the model differs. The universal convention since
    SiamFC 2016; OSTrack's ablation puts factor 4 -> 6 at +6.1 AUC and 7 in regression.

    Deliberately NOT clamped to the frame: clamping or sliding changes the target/context ratio,
    which is the one quantity the factor exists to hold constant. What falls outside is padded by
    `crop_pad`.
    """
    x1, y1, x2, y2 = box
    w, h = max(x2 - x1, 1.0), max(y2 - y1, 1.0)
    s = max(int(math.ceil(math.sqrt(w * h) * factor)), 1)
    return int(round(x1 + w / 2 - s / 2)), int(round(y1 + h / 2 - s / 2)), s


def crop_pad(frame: np.ndarray, win: tuple[int, int, int], value=0) -> np.ndarray:
    """Slice `win` out of `frame`, padding whatever hangs off the border.

    `value=0` (black) because that is what AsymTrack does -- `cv.copyMakeBorder(..., BORDER_CONSTANT)`
    with no `value` at `processing_utils.py:53`. SiamFC's older convention is the per-channel image
    mean, and the field never converged; matching the arm we compare against matters more than
    picking the prettier one, since a border-fill difference would enter the comparison disguised as
    a model difference. Left as a knob so the mean can be measured later rather than argued about.
    """
    x, y, s = win
    h, w = frame.shape[:2]
    out = np.full((s, s, frame.shape[2]), value, frame.dtype)
    sx, sy = max(x, 0), max(y, 0)
    ex, ey = min(x + s, w), min(y + s, h)
    if ex > sx and ey > sy:
        out[sy - y:ey - y, sx - x:ex - x] = frame[sy:ey, sx:ex]
    return out


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

    Two optional recovery heuristics, off by default so the plain arm stays the control. They are
    independent flags on purpose: each ships as its own arm, so a win can be attributed.

    `coast=N`  On a lost frame, keep sliding the window along the target's recent velocity instead
        of freezing it. Targets the observed `car12` failure, where one loss pins the window and the
        arm never sees the target again (450/499 frames lost). Velocity is the MEDIAN per-frame
        centre step over the last N hits, so one bad box cannot launch the window across the frame,
        and only consecutive pairs count -- a step across a gap is a teleport, not a speed.
        It moves the WINDOW and emits no box: an extrapolated box during a real occlusion is a
        guaranteed false positive, and `aggregate.py` counts those.

    `edge=True`  If the target was last seen within one target-size of the REAL frame border and is
        then lost, drop to the full frame until it comes back. Near the frame edge a loss usually
        means the target left the shot, and the crop window is then looking at the one place it
        cannot be. Full frame is the same predictor fed an unsliced image, i.e. the `sam2_t<N>`
        behaviour, so no second model is loaded.
        Named risk: the memory bank is full of crop-framed features and the framing jump is abrupt.
        That is the thing being measured.
    """

    def __init__(self, checkpoint: str, size: int, coast: int = 0, edge: bool = False,
                 factor: float = 0.0, pad: bool = False, floor: bool = False):
        self.size = size
        self.factor = factor
        self.floor = floor
        self._s0 = None  # frame-0 window side, the lower bound when `floor`
        self.pad = pad
        self.inner = Sam2Arm(checkpoint, size)
        self.coast, self.edge = coast, edge
        self.win = None   # (x, y, s) in full-frame coords; None means the full frame was fed
        self.last = None  # this frame's box, None if lost
        self.seen = None  # last box actually found, which is what `edge` interrogates
        self.anchor = None  # window centre; unlike `last` it survives a loss, and `coast` moves it
        self.hist = collections.deque(maxlen=max(coast, 2))  # (frame_index, centre) of hits
        self.i = 0
        self.coasted = 0.0
        self.full = False

    @property
    def conf(self):
        """The inner arm's score, unmodified. Cropping changes what SAM2 sees, not how it scores."""
        return self.inner.conf

    def _shift(self, box, dx, dy):
        return None if box is None else [box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy]

    def _crop(self, frame, center):
        """Slice the window for this frame. `self.win` is always what the model was actually fed."""
        h, w = frame.shape[:2]
        if self.factor:
            # window sized by the last box we FOUND and centred on `center`, which on a lost frame
            # is the coasted anchor rather than that box's own centre. Holding the size across a
            # loss is deliberate: a lost frame carries no evidence that the target got smaller.
            bw = self.seen[2] - self.seen[0]
            bh = self.seen[3] - self.seen[1]
            self.win = search_window(
                [center[0] - bw / 2, center[1] - bh / 2, center[0] + bw / 2, center[1] + bh / 2],
                self.factor)
            if self.floor:
                # The window is sized by the box the arm itself produced, so a shrinking box shrinks
                # the window, which removes context, which shrinks the box: positive feedback with
                # no bottom. Measured on `f5-30`: car9 went 647 px to 52 px and stayed on a gantry
                # sign 200 px from the car for the last 1000 frames. This floors the side at its
                # frame-0 value, which asks exactly one question -- is `f5`'s deficit the collapse?
                # It forbids a legitimately receding target from shrinking its window, and that is
                # affordable only because `c640` shows an over-large window costs nothing here.
                if self._s0 is None:
                    self._s0 = self.win[2]
                elif self.win[2] < self._s0:
                    cx = self.win[0] + self.win[2] / 2
                    cy = self.win[1] + self.win[2] / 2
                    self.win = (round(cx - self._s0 / 2), round(cy - self._s0 / 2), self._s0)
            return crop_pad(frame, self.win)
        if self.pad:
            # Fixed size like the plain crop arms, but the window stays CENTRED on the target and
            # what hangs off the frame is filled instead of slid back in. Splits the two things
            # `sam2_c640` vs `sam2_f5` changes at once. Not an edge case here: a 640 window fits
            # inside a 720-tall frame only when the centre sits in an 80 px band, so `crop_window`
            # is sliding vertically on nearly every frame of UAV123.
            s = self.size
            self.win = (round(center[0] - s / 2), round(center[1] - s / 2), s)
            return crop_pad(frame, self.win)
        x, y, s = crop_window(center, self.size, w, h)
        self.win = (x, y, s)
        return frame[y:y + s, x:x + s]

    def _hit(self, box):
        self.seen = box
        self.anchor = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        self.hist.append((self.i, self.anchor))
        self.coasted = 0.0
        self.full = False  # re-acquired: back to the crop

    def _velocity(self) -> tuple[float, float]:
        c = list(self.hist)
        d = [(c[k + 1][1][0] - c[k][1][0], c[k + 1][1][1] - c[k][1][1])
             for k in range(len(c) - 1) if c[k + 1][0] - c[k][0] == 1]
        if not d:
            return 0.0, 0.0
        return float(np.median([p[0] for p in d])), float(np.median([p[1] for p in d]))

    def _at_edge(self, w: int, h: int) -> bool:
        b = self.seen
        if b is None:
            return False
        m = max(b[2] - b[0], b[3] - b[1])  # one target-size of margin, so nothing needs tuning
        return b[0] < m or b[1] < m or b[2] > w - m or b[3] > h - m

    def init(self, frame, box):
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        self.seen = box  # `_crop` sizes a factor window from it, and frame 0 is the only GT we get
        sub = self._crop(frame, (cx, cy))
        x, y, _ = self.win
        b, cnts = self.inner.init(sub, [box[0] - x, box[1] - y, box[2] - x, box[3] - y])
        self.last = self._shift(b, x, y)
        if self.last is not None:
            self._hit(self.last)
        return self.last, _shift_contours(cnts, x, y)

    def step(self, frame):
        h, w = frame.shape[:2]
        self.i += 1
        if self.last is not None:  # re-centre on where the target was last seen
            self._hit(self.last)
        else:
            if self.edge and self._at_edge(w, h):
                self.full = True
            if self.coast:
                vx, vy = self._velocity()
                d = float(np.hypot(vx, vy))
                # coast until the window has travelled its own width, then stop: past that the
                # extrapolation is older than any evidence, and a runaway window never walks back.
                ceiling = self.win[2] if (self.factor and self.win) else self.size
                if d and self.coasted + d <= ceiling:
                    self.anchor = (self.anchor[0] + vx, self.anchor[1] + vy)
                    self.coasted += d
        if self.full:
            self.win, sub, x, y = None, frame, 0, 0
        else:
            sub = self._crop(frame, self.anchor)  # a lost frame otherwise keeps the same window
            x, y, _ = self.win
        b, cnts = self.inner.step(sub)
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


def _object_score(output_dict, idx):
    """SAM2's `object_score_logits` for frame `idx`, or None if it is not there.

    Same quantity `Sam2Arm.conf` records, pulled out of the inference state instead, because both
    vendored wrappers (DAM4SAM, SAMURAI) return only masks from their step. `propagate_in_video`
    consolidates into `output_dict` keyed by frame index; a tracked frame lands under
    `non_cond_frame_outputs`, frame 0 under `cond_frame_outputs`. One helper for both families so
    the two presence scores are literally the same number on the same scale.

    Returns None rather than raising: a missing score is a measurement gap, and killing a 4-hour
    sweep over one is worse than a NaN in a column.
    """
    try:
        out = (output_dict["non_cond_frame_outputs"].get(idx)
               or output_dict["cond_frame_outputs"].get(idx))
        return float(out["object_score_logits"].reshape(-1)[0])
    except Exception:
        return None


DAM4SAM_DIR = Path(os.environ.get("DAM4SAM_DIR", "/home/jfdg/trackers/DAM4SAM"))


class Dam4SamArm:
    """DAM4SAM: SAM2.1 plus a distractor-resolving memory (Videnovic et al., CVPR 2025 / IJCV 2026).

    Training-free -- same tiny checkpoint as `sam2_*`, different memory policy: on a frame where the
    chosen mask is confident and stable but an ALTERNATIVE mask disagrees with it, that frame is
    pushed into a second memory bank (DRM) so the model keeps a record of what the distractor looks
    like. That is exactly the failure `asym_lt` could not fix by heuristic (`car7` 0.740 -> 0.003).

    Full frame, no crop, by author's decision: measure the published tracker as published first, and
    only then ask whether our window geometry helps it. Input is fixed at 1024 inside the wrapper
    (`self.input_image_size`), so the `upscales` gate applies and the five 720x480 clips are skipped
    -- the same rule that produced the common-25 set the other arms are compared on.

    Not pip-installed: the repo vendors its own modified `sam2` fork, which would collide with the
    `sam2 1.1.0` in the main venv. It gets its own interpreter (`.venv-dam4sam`) and is reached by
    path, the way `AsymArm` reaches AsymTrack.
    """

    def __init__(self, name: str = "sam21pp-T", size: int = 1024):
        self.name, self.size = name, size
        self.tr = None
        self.torch = None
        # Same quantity as `Sam2Arm.conf` -- SAM2.1's trained occlusion head -- pulled out of the
        # inference state instead of off StreamCarry, because the DAM4SAM wrapper's `track()`
        # returns only `pred_mask`. Extracted exactly as `stream_carry.py:142` does it, so the two
        # families' presence scores are the same number on the same scale and comparable.
        self.conf = None

    def _amp(self):
        return self.torch.autocast("cuda", dtype=self.torch.bfloat16)

    @staticmethod
    def _pil(frame):
        from PIL import Image
        return Image.fromarray(frame[:, :, ::-1].copy())  # rig is BGR, wrapper wants a PIL RGB

    def init(self, frame, box):
        import sys

        import torch

        if str(DAM4SAM_DIR) not in sys.path:
            sys.path.insert(0, str(DAM4SAM_DIR))
        from dam4sam_tracker import DAM4SAMTracker

        self.torch = torch
        if self.size != 1024:
            # The wrapper hard-codes 1024 and builds the predictor with no hydra override, so both
            # ends have to move together: `input_image_size` is what `_prepare_image` resizes to,
            # `model.image_size` is what sets `sam_image_embedding_size`. Change one and SAM2 dies on
            # `assert backbone_features.size(2) == self.sam_image_embedding_size`.
            import dam4sam_tracker as _dt
            _build = _dt.build_sam2_video_predictor
            _dt.build_sam2_video_predictor = lambda cfg, ck=None, **kw: _build(
                cfg, ck, hydra_overrides_extra=[f"++model.image_size={self.size}"], **kw)
            try:
                self.tr = DAM4SAMTracker(self.name)
            finally:
                _dt.build_sam2_video_predictor = _build
            self.tr.input_image_size = self.size
            assert self.tr.predictor.image_size == self.size
        else:
            self.tr = DAM4SAMTracker(self.name)
        x1, y1, x2, y2 = box
        with self._amp():
            # `initialize` takes a MASK; passing bbox=None-mask makes it prompt SAM2 with the box
            # first (`estimate_mask_from_box`), which is the published bbox-init path. xywh there.
            m = self.tr.initialize(self._pil(frame), None,
                                   bbox=[x1, y1, x2 - x1, y2 - y1])["pred_mask"]
        return _box_of(m), mask_contours(m)

    def _score(self):
        return _object_score(self.tr.inference_state["output_dict"], self.tr.frame_index)

    def step(self, frame):
        with self._amp():
            m = self.tr.track(self._pil(frame))["pred_mask"]
        self.conf = self._score()
        return _box_of(m), mask_contours(m)


SAMURAI_DIR = Path(os.environ.get("SAMURAI_DIR", "/home/jfdg/trackers/samurai"))


class SamuraiArm:
    """SAMURAI: SAM2.1 with motion-aware memory selection (Yang et al., arXiv 2411.11922).

    Also training-free and also the same tiny checkpoint: a Kalman filter over the box predicts where
    the target should be, that prediction re-weights SAM2's multimask choice (`kf_score`), and frames
    only enter memory while the track is "stable". Kalman state lives on the MODEL (`self.kf_mean`,
    `self.stable_frames` in `sam2_base.py`), not in the inference state, which is what makes the
    streaming surgery below safe.

    Published usage is OFFLINE: `init_state(video_path)` calls `load_video_frames`, which decodes and
    resizes the WHOLE clip up front. At 1024 that is ~12.6 MB/frame; `bird1_3` alone is 865 frames,
    ~10.9 GB. Infeasible on an 8 GB Jetson, and it would also measure a batch pipeline instead of the
    per-frame latency the rig exists to measure. So the state is built by hand -- everything
    `init_state` does except `load_video_frames` -- with `images` as a DICT holding only the current
    frame, and `num_frames` advanced one frame at a time. `_get_image_feature` indexes `images` by
    frame index, so a dict is a drop-in; `propagate_in_video(start_frame_idx=i,
    max_frame_num_to_track=0)` then runs exactly one frame. Same trick DAM4SAM ships as
    `init_state_tw`.

    Own venv (`.venv-samurai`) and reached by path, same reason as `Dam4SamArm`: vendored `sam2` fork.
    """

    MEAN = (0.485, 0.456, 0.406)
    STD = (0.229, 0.224, 0.225)

    def __init__(self, size: int = 1024, ckpt: str = "sam2.1_hiera_tiny.pt"):
        self.size, self.ckpt = size, ckpt
        self.predictor = None
        self.state = None
        self.torch = None
        self.i = 0
        self.conf = None  # see `_object_score`

    def _amp(self):
        # fp16 here, not bf16: the published demo runs fp16 and the Kalman gating reads the mask
        # scores, so the numerics of the score head are part of the method.
        return self.torch.autocast("cuda", dtype=self.torch.float16)

    def _prep(self, frame):
        """BGR uint8 HxWx3 -> normalized CHW tensor on GPU, matching `_load_img_as_tensor`."""
        import cv2
        torch = self.torch
        img = cv2.resize(frame[:, :, ::-1], (self.size, self.size), interpolation=cv2.INTER_LINEAR)
        t = torch.from_numpy(np.ascontiguousarray(img)).permute(2, 0, 1).float() / 255.0
        t -= torch.tensor(self.MEAN)[:, None, None]
        t /= torch.tensor(self.STD)[:, None, None]
        return t.to("cuda")

    def init(self, frame, box):
        import sys

        import torch

        pkg = str(SAMURAI_DIR / "sam2")
        if pkg not in sys.path:
            sys.path.insert(0, pkg)
        from sam2.build_sam import build_sam2_video_predictor

        self.torch = torch
        h, w = frame.shape[:2]
        over = [f"++model.image_size={self.size}"] if self.size != 1024 else []
        self.predictor = build_sam2_video_predictor(
            "configs/samurai/sam2.1_hiera_t.yaml", str(SAMURAI_DIR / "checkpoints" / self.ckpt),
            device="cuda:0", hydra_overrides_extra=over)
        assert self.predictor.image_size == self.size
        dev = torch.device("cuda")
        self.i = 0
        self.state = {
            "images": {0: self._prep(frame)}, "num_frames": 1,
            "offload_video_to_cpu": False, "offload_state_to_cpu": False,
            "video_height": h, "video_width": w, "device": dev, "storage_device": dev,
            "point_inputs_per_obj": {}, "mask_inputs_per_obj": {}, "cached_features": {},
            "constants": {}, "obj_id_to_idx": collections.OrderedDict(),
            "obj_idx_to_id": collections.OrderedDict(),
            "obj_ids": [],
            "output_dict": {"cond_frame_outputs": {}, "non_cond_frame_outputs": {}},
            "output_dict_per_obj": {}, "temp_output_dict_per_obj": {},
            "consolidated_frame_inds": {"cond_frame_outputs": set(), "non_cond_frame_outputs": set()},
            "tracking_has_started": False, "frames_already_tracked": {},
        }
        with torch.inference_mode(), self._amp():
            _, _, masks = self.predictor.add_new_points_or_box(
                self.state, box=list(box), frame_idx=0, obj_id=0)
        m = (masks[0, 0] > 0).cpu().numpy()
        return _box_of(m), mask_contours(m)

    def step(self, frame):
        torch = self.torch
        self.i += 1
        self.state["images"].pop(self.i - 1, None)  # only the current frame is ever needed
        self.state["images"][self.i] = self._prep(frame)
        self.state["num_frames"] = self.i + 1
        with torch.inference_mode(), self._amp():
            _, _, masks = next(self.predictor.propagate_in_video(
                self.state, start_frame_idx=self.i, max_frame_num_to_track=0))
        m = (masks[0, 0] > 0).cpu().numpy()
        self.conf = _object_score(self.state["output_dict"], self.i)
        return _box_of(m), mask_contours(m)


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


# Outside `code/`, deliberately: `jetson.py sync` pushes `device/` with `rsync --delete`, so a
# 100 MB checkout parked under `code/` is erased by the next sync. It cost us one clone already.
ASYM_DIR = Path(os.environ.get("ASYMTRACK_DIR", "/home/jfdg/tracker-sweep/ext/AsymTrack"))


class AsymArm:
    """AsymTrack (Zhu et al., MIT) driven through its own `lib/test/tracker/AsymTrack.py`.

    Box-only: the head is `CORNER` with `PREDICT_MASK: false`, so `contours` is always None, and
    the tracker never abstains -- it emits a box every frame with no confidence output.

    Their parameter loader builds the checkpoint path out of `env_settings()`, which wants two
    local.py files filled in with someone else's dataset paths. We build `TrackerParams` here
    instead: same fields, read from the same yaml, no environment to keep in sync.
    """

    def __init__(self, cfg_name: str = "base", epoch: int = 500):
        self.cfg_name, self.epoch = cfg_name, epoch
        self.t = None
        self.win = None
        self.conf = None
        self.conf_cos = None
        self._maps = None
        self._z = None  # frame-0 template patch, for the cosine verifier

    def _params(self):
        from lib.config.AsymTrack.config import cfg, update_config_from_file
        from lib.test.utils import TrackerParams

        update_config_from_file(str(ASYM_DIR / f"experiments/AsymTrack/{self.cfg_name}.yaml"))
        ck = ASYM_DIR / f"output/checkpoints/AsymTrack/{self.cfg_name}/AsymTrack_ep{self.epoch:04d}.pth.tar"
        if not ck.exists():
            raise SystemExit(f"missing AsymTrack checkpoint {ck}")
        p = TrackerParams()
        p.cfg = cfg
        p.yaml_name = self.cfg_name
        p.template_factor, p.template_size = cfg.TEST.TEMPLATE_FACTOR, cfg.TEST.TEMPLATE_SIZE
        p.search_factor, p.search_size = cfg.TEST.SEARCH_FACTOR, cfg.TEST.SEARCH_SIZE
        p.checkpoint, p.debug, p.save_all_boxes = str(ck), 0, False
        cfg.TEST.EPOCH = self.epoch
        cfg.TEST_MODE = True
        return p

    def init(self, frame, box):
        if str(ASYM_DIR) not in sys.path:
            sys.path.insert(0, str(ASYM_DIR))
        from lib.test.tracker.AsymTrack import AsymTrack

        p = self._params()
        self.t = AsymTrack(p, "uav")
        self._tap_score_map()
        x1, y1, x2, y2 = box
        self._record_win([x1, y1, x2 - x1, y2 - y1], p)
        self.t.initialize(frame[:, :, ::-1], {"init_bbox": [x1, y1, x2 - x1, y2 - y1]})
        self._z = self._patch(frame[:, :, ::-1], [x1, y1, x2 - x1, y2 - y1])
        return [int(v) for v in (x1, y1, x2, y2)], None

    def _patch(self, rgb, xywh):
        """The template crop `initialize` takes, as a zero-mean unit-norm vector."""
        from lib.test.tracker.vittrack_utils import sample_target
        p = self.t.params
        a, _ = sample_target(rgb, list(xywh), p.template_factor, output_sz=p.template_size)
        v = a.astype(np.float32).ravel()
        v -= v.mean()
        n = float(np.linalg.norm(v))
        return v / n if n else v

    def _cosine(self, rgb) -> float | None:
        """SECOND presence surrogate, independent of the head: normalised cross-correlation between
        the frame-0 template patch and the same crop taken around the box just predicted.

        Pre-registered because `presence_auc` for the corner peak came out at 0.711, inside the
        0.65-0.75 grey band, where the plan says build a second verifier and compare rather than
        trust the first one. It is the pre-deep-learning verifier (NCC), and that is the point: it
        fails on different things than the corner softmax does -- illumination and pose break it,
        while a confident lock onto a distractor, which is what fools the corner peak, does not.

        Zero-mean before normalising, so a global brightness shift does not by itself look like a
        different object. No network: one crop and a dot product, ~0.3 ms.
        """
        if self._z is None:
            return None
        return float(self._z @ self._patch(rgb, self.t.state))

    def _record_win(self, xywh, p=None):
        """The square search crop `sample_target` will take next, in frame coordinates.

        Through the shared `search_window`, which is `sample_target`'s arithmetic verbatim. It used
        to round the side where the original ceils, so the window we drew could sit a pixel off the
        window the model actually cropped -- small, but the overlay is the instrument that verifies
        every geometry claim in this experiment, and an instrument that is approximately right is
        not one you can assert against.
        """
        p = p or self.t.params
        x, y, w, h = xywh
        self.win = search_window([x, y, x + w, y + h], float(p.search_factor))

    def _tap_score_map(self) -> None:
        """Keep the corner logit maps the head already computes, for `_corner_peak`.

        `forward_box_head` calls `box_head(opt_feat)` without `return_dist`, so the distributions
        are dropped. Asking for them in a SECOND head pass cost +4.7 ms p50 on bird1_3 (44.8 vs the
        40.1 that same sequence ran at in `asym-repro`) -- `get_score_map` is 8 convs over a 24x24
        grid, not free. Wrapping the method reuses the maps the first pass already produced and
        lands back on 40.1 exactly, with an identical presence_auc, so the tap is equivalent and
        the score costs nothing.

        A monkeypatch and not a forward hook because `get_score_map` is a method, not a submodule,
        so there is nothing to hook. Bound to the instance, so a second AsymArm in the same process
        would get its own.
        """
        head = self.t.network.box_head
        orig = head.get_score_map

        def tapped(x):
            out = orig(x)
            self._maps = out
            return out

        head.get_score_map = tapped

    def _corner_peak(self) -> float | None:
        """SURROGATE presence score: the peak of the corner softmax.

        AsymTrack has no presence output -- CORNER head, L1+GIoU only, no classification branch --
        so this is the sharpest signal available without adding a network.

        Geometric mean of the two corner peaks: both corners must be sharp for the box to be
        trustworthy, and the geometric mean punishes one flat corner the way `min` does without
        being blind to the other one.

        What it actually measures is certainty about WHERE the corner is, and we are borrowing it
        as certainty about WHETHER the target is there. Whether those correlate is what
        `presence_auc` tests; until that number exists this is a labelled guess.
        """
        import torch
        if self._maps is None:
            return None
        tl, br = self._maps
        # softmax over the flattened grid, exactly `soft_argmax`'s, but we only want its peak
        peak = [float(torch.softmax(m.reshape(1, -1), dim=1).max()) for m in (tl, br)]
        return float(np.sqrt(peak[0] * peak[1]))

    def step(self, frame):
        self._record_win(self.t.state)  # window used for THIS frame: centred on the previous box
        rgb = frame[:, :, ::-1]
        out = self.t.track(rgb)
        self.conf = self._corner_peak()
        self.conf_cos = self._cosine(rgb)
        x, y, w, h = out["target_bbox"]
        return [int(x), int(y), int(x + w), int(y + h)], None


class AsymLtArm:
    """AsymTrack plus the long-term wrapper neither tracker in this sweep has.

    Measured on `raw/full-sweep-30`: no arm re-attaches. Full frame at max resolution (`t1024`)
    recovers 3 of 13 losses, crop (`c704`) 5 of 13. SAM2's memory bank propagates forward through
    whatever window it is handed; it never searches elsewhere. AsymTrack's `clip_box(..., margin=10)`
    forces a box every frame, so it never registers being lost at all -- it answered in all 2683
    UAV123 frames where the ground truth says the target is absent.

    So re-detection is a WRAPPER, which is LTMU's explicit thesis: keep your short-term tracker,
    put a state machine around it. Five pieces, no new network:

      1. local tracker -- `AsymArm` unchanged, one window, ~29-40 ms;
      2. verifier -- `conf`, the corner-softmax peak (a surrogate; `presence_auc` is what says
         whether it is usable);
      3. state machine with hysteresis -- `tracking` -> `lost` after `k` frames under `tau_lo`,
         back only on a candidate at or above `tau_hi`. Two thresholds because one oscillates;
      4. re-detector -- the SAME AsymTrack over several windows. In `lost` it evaluates `probes`
         raster positions per frame at the last known target scale on top of the local one, and
         takes the argmax of `conf`. The sweep is AMORTISED rather than done in one burst: at the
         5 Hz this thesis actually runs at there are ~170 ms spare per frame after AsymTrack's 29,
         which is ~5 extra windows, and the whole frame is covered in ~8 frames (~1.6 s). No
         latency spike, no dropped control cycle. GlobalTrack's trained re-detector is the
         literature answer and is out of reach here -- Faster-RCNN + ResNet-50, ~6 FPS on a 1080Ti.
         That the edge forces the cheap version is a result, not an embarrassment;
      5. template -- frame 0, frozen. `AsymTrack.initialize` assigns `self.template` once and no
         line reassigns it, so this is free. Deliberately never touched while lost: that is exactly
         where a running template memorises the distractor.

    Emits a box only while `tracking`, `None` while `lost`. That is the point -- `asym_b` scores
    badly on MaxGM because it answers 2683 times where there is nothing to answer.

    Known ceiling: the raster grid steps by a full window with no overlap, so a target straddling
    two cells is seen at the edge of both. Overlapping the grid doubles the sweep time; worth it
    only if re-detection turns out to miss targets it passed over.
    """

    def __init__(self, tau_lo: float, tau_hi: float, k: int = 3, probes: int = 5):
        self.inner = AsymArm("base")
        self.tau_lo, self.tau_hi, self.k, self.probes = tau_lo, tau_hi, k, probes
        self.lost = False
        self.low = 0        # consecutive frames under tau_lo
        self.cursor = 0     # position in the raster sweep, so it resumes instead of restarting
        self.size = None    # (w, h) of the last CONFIRMED box; a loss carries no evidence of scale
        self.win = None
        self.conf = None

    def init(self, frame, box):
        b, _ = self.inner.init(frame, box)
        self.size = (box[2] - box[0], box[3] - box[1])
        self.win, self.conf = self.inner.win, self.inner.conf
        self.conf_cos = self.inner.conf_cos
        return b, None

    def _grid(self, w: int, h: int):
        """Raster positions at the current target scale: one window side apart, so a full pass
        covers the frame exactly once."""
        side = search_window([0, 0, self.size[0], self.size[1]],
                             float(self.inner.t.params.search_factor))[2]
        step = max(int(side), 1)
        return [(x, y) for y in range(step // 2, h + step, step)
                for x in range(step // 2, w + step, step)]

    def _probe(self, frame, cx, cy):
        """One forward pass with the search window moved to (cx, cy). `track` both reads and writes
        `self.state`, so the caller is responsible for restoring it."""
        tw, th = self.size
        self.inner.t.state = [cx - tw / 2, cy - th / 2, tw, th]
        self.inner._record_win(self.inner.t.state)
        out = self.inner.t.track(frame[:, :, ::-1])
        return self.inner._corner_peak(), list(out["target_bbox"]), self.inner.win

    def step(self, frame):
        h, w = frame.shape[:2]
        if not self.lost:
            b, _ = self.inner.step(frame)
            self.win, self.conf = self.inner.win, self.inner.conf
            self.conf_cos = self.inner.conf_cos
            self.low = self.low + 1 if (self.conf is not None and self.conf < self.tau_lo) else 0
            if self.low >= self.k:
                self.lost, self.low = True, 0
                return None, None  # the k frames before this one were already emitted: hysteresis
            if not self.low:
                # Only a frame the verifier is happy with updates the target scale. Updating on
                # every frame instead fed the k low-confidence frames before a loss -- exactly where
                # the box has already blown up -- into the scale the sweep rasters at: seen on the
                # car12 overlay, a car being tracked with a 154 px window produced 508 px probe
                # windows, so the grid was 4 cells and every probe was at the wrong scale.
                self.size = (b[2] - b[0], b[3] - b[1])
            return b, None

        keep = list(self.inner.t.state)  # where we were when we lost it; restored unless we re-find
        g = self._grid(w, h)
        # the local window stays in the running: the target most often walks back into it
        cands = [(keep[0] + keep[2] / 2, keep[1] + keep[3] / 2)]
        cands += [g[(self.cursor + j) % len(g)] for j in range(self.probes)]
        self.cursor = (self.cursor + self.probes) % len(g)

        best = (-1.0, None, None)
        for cx, cy in cands:
            s, box, win = self._probe(frame, cx, cy)
            if s is not None and s > best[0]:
                best = (s, box, win)

        self.conf, self.win = (best[0] if best[1] else None), best[2]
        if best[1] is not None and best[0] >= self.tau_hi:
            self.lost = False
            self.inner.t.state = best[1]
            x, y, bw, bh = best[1]
            self.size = (bw, bh)
            return [int(x), int(y), int(x + bw), int(y + bh)], None
        self.inner.t.state = keep  # nothing convincing: do not let the probes drag the anchor
        return None, None


class Dam4SamLtArm:
    """DAM4SAM plus the abstention half of the long-term state machine. No re-detector, on purpose.

    `AsymLtArm` needs five pieces because AsymTrack looks through ONE search window: once the target
    leaves it, nothing will ever bring it back, so a raster sweep has to go looking. DAM4SAM runs on
    the FULL FRAME. It already evaluates every pixel every frame -- there is nowhere to search that
    it is not already looking. The re-detector, which is the expensive and fragile piece, is
    structurally unnecessary here.

    That leaves exactly what `asym_b` and every DAM4SAM arm measured so far lack: the decision not to
    answer. Same hysteresis as `AsymLtArm` (`tracking` -> `lost` after `k` frames under `tau_lo`,
    back on one frame at or above `tau_hi`), driven by the trained occlusion head instead of a
    corner-peak surrogate.

    `inner.step` is called on EVERY frame including while lost, and its result is thrown away. That
    is not waste, it is the mechanism: SAM2's memory has to keep advancing or there is nothing to
    come back with, and DRM has to keep watching the distractor. So the arm costs the same 204 ms as
    `dam4sam_t640` -- abstention here is free, which is not true of the AsymTrack version.

    Known ceiling: while lost, the memory keeps ingesting frames of whatever the model is looking at,
    which is the distractor. DRM is the reason to expect that to survive, and it is the assumption
    under test. If the arm re-attaches to distractors, the fix is suppressing the memory write while
    lost -- which the vendored wrapper does not expose, so it would mean patching `track()`.
    """

    def __init__(self, tau_lo: float, tau_hi: float, size: int = 640, k: int = 3):
        self.inner = Dam4SamArm(size=size)
        self.tau_lo, self.tau_hi, self.k = tau_lo, tau_hi, k
        self.lost = False
        self.low = 0  # consecutive frames under tau_lo
        self.conf = None

    def init(self, frame, box):
        b, c = self.inner.init(frame, box)
        self.conf = self.inner.conf
        return b, c

    def step(self, frame):
        b, c = self.inner.step(frame)
        self.conf = self.inner.conf
        if self.conf is None:
            return b, c  # no score this frame: fall through to the plain arm rather than guess
        if self.lost:
            if self.conf >= self.tau_hi:
                self.lost = False
                return b, c
            return None, None
        self.low = self.low + 1 if self.conf < self.tau_lo else 0
        if self.low >= self.k:
            self.lost, self.low = True, 0
            return None, None  # the k frames before this one were already emitted: hysteresis
        return b, c


arm("asym_b", family="asymtrack", ckpt="base", search_factor=4.0, image_size=None,
    venv_python="/home/jfdg/tracker-sweep/.venv-asym/bin/python")(lambda: AsymArm("base"))

# Thresholds are the literal output of `analysis/presence.py raw/asym-conf --thresholds`, fitted on
# the 17 even-indexed gap sequences and evaluated on the 16 odd-indexed ones. They are not tuned
# against this arm's score; if they were, the number would mean nothing.
arm("asym_lt", family="asymtrack", ckpt="base", search_factor=4.0, image_size=None, heur="lt",
    venv_python="/home/jfdg/tracker-sweep/.venv-asym/bin/python")(
    lambda: AsymLtArm(tau_lo=0.3920, tau_hi=0.7293)
)


# `image_size=None` so the `upscales` gate does not apply, same as the AsymTrack arms. 1024 is not
# a knob we chose from a ladder: it is the wrapper's hard-coded input (`self.input_image_size`), and
# at 1024 the gate rejects EVERY UAV123 clip (1024^2 > 1280x720), which would veto the published
# tracker outright instead of measuring it. The gate exists to keep our own resolution ladder
# honest, not to forbid a fixed-input model.
for _sz in (512, 640, 768, 960, 1024):
    arm(f"dam4sam_t{_sz}", family="dam4sam", ckpt="sam21pp-T", image_size=None,
        venv_python="/home/jfdg/tracker-sweep/.venv-dam4sam/bin/python")(
        lambda sz=_sz: Dam4SamArm(size=sz)
    )

arm("dam4sam_t", family="dam4sam", ckpt="sam21pp-T", image_size=None,
    venv_python="/home/jfdg/tracker-sweep/.venv-dam4sam/bin/python")(lambda: Dam4SamArm())

# Same treatment for SAMURAI, and for the same reason: fixed-input published tracker, `image_size`
# is a hydra override we drive, not a rung on our ladder.
for _sz in (512, 640, 768, 960, 1024):
    arm(f"samurai_t{_sz}", family="samurai", ckpt="sam2.1_hiera_tiny", image_size=None,
        venv_python="/home/jfdg/tracker-sweep/.venv-samurai/bin/python")(
        lambda sz=_sz: SamuraiArm(size=sz)
    )


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

# Recovery heuristics, one per arm and only on 640 -- the best crop arm, so `sam2_c640` is the
# control and a difference is attributable to the one flag that changed. Combining them is only
# worth an arm once each is shown to earn its keep alone.
arm("sam2_c640_coast", family="sam2crop", ckpt="tiny", image_size=640, crop=640, heur="coast7")(
    lambda: Sam2CropArm("facebook/sam2.1-hiera-tiny", 640, coast=7)
)
arm("sam2_c640_edge", family="sam2crop", ckpt="tiny", image_size=640, crop=640, heur="edge")(
    lambda: Sam2CropArm("facebook/sam2.1-hiera-tiny", 640, edge=True)
)

# Same 640 window, centred and zero-padded instead of slid back inside the frame. The middle rung
# of `c640` (slides) -> `c640_pad` (pads) -> `f5` (pads, sized by the target): each step changes one
# thing, so a difference is attributable.
arm("sam2_c640_pad", family="sam2crop", ckpt="tiny", image_size=640, crop=640, heur="pad")(
    lambda: Sam2CropArm("facebook/sam2.1-hiera-tiny", 640, pad=True)
)

# Search-factor arms: same model, same 640 input, same compute as `sam2_c640` -- only the window
# geometry changes, from a fixed 640 square to `factor * sqrt(area)` around the target. Factor 5 is
# the primary (LoRAT at 378 input); 6 is OSTrack's ablation optimum and brackets it from above, so a
# monotone result is distinguishable from a peak. The point is the target/stride-16 ratio: at a 28 px
# target, `c640` puts 1.75 memory-attention cells on the target and factor 5 puts 8.
for _f in (5.0, 6.0):
    arm(f"sam2_f{int(_f)}", family="sam2crop", ckpt="tiny", image_size=640, crop=640,
        search_factor=_f)(
        lambda f=_f: Sam2CropArm("facebook/sam2.1-hiera-tiny", 640, factor=f)
    )

# Same as `sam2_f5` with one change: the window side never drops below its frame-0 value. Isolates
# the scale-collapse failure mode from the target-scaled geometry itself.
arm("sam2_f5_floor", family="sam2crop", ckpt="tiny", image_size=640, crop=640, search_factor=5.0,
    heur="floor")(
    lambda: Sam2CropArm("facebook/sam2.1-hiera-tiny", 640, factor=5.0, floor=True)
)

for _n in ["TrackerNano", "TrackerVit", "TrackerDaSiamRPN", "TrackerGOTURN", "TrackerMIL", "TrackerCSRT"]:
    arm(_n.replace("Tracker", "cv_").lower(), family="opencv")(lambda n=_n: CvArm(n))


def build(name: str):
    if name not in REGISTRY:
        raise SystemExit(f"unknown arm {name!r}; have: {', '.join(sorted(REGISTRY))}")
    return REGISTRY[name]["factory"]()


def _check_dam_lt() -> None:
    """Abstention state machine only -- no network, no probes, scripted confidences.

    Same three things as `_check_lt` minus re-detection: a single dip must not trigger a loss, no box
    comes out while lost, and a score between the thresholds must not bring it back. Plus one that is
    specific to this arm: `inner.step` has to be called on EVERY frame including while lost, because
    suppressing the memory update is exactly the bug this design cannot afford.
    """
    import types

    class FakeDam:
        def __init__(self, confs):
            self.confs, self.conf, self.calls = list(confs), None, 0

        def init(self, frame, box):
            self.conf = 9.0
            return list(box), None

        def step(self, frame):
            self.calls += 1
            self.conf = self.confs.pop(0) if self.confs else 0.0
            return [10, 10, 30, 30], None

    #        dip  recover  ---- three under tau_lo ----  between  under tau_hi
    script = [0.0, 5.0, -2.0, -2.0, -2.0, 3.0, 6.0]
    a = Dam4SamLtArm(tau_lo=1.0, tau_hi=8.0, k=3)
    a.inner = FakeDam(script)
    a.init(None, [10, 10, 30, 30])
    out = [a.step(None)[0] for _ in range(len(script))]
    assert out[0] is not None and out[1] is not None, "one dip below tau_lo is not a loss"
    assert out[2] is not None and out[3] is not None, "hysteresis: the k frames still emit"
    assert out[4] is None, "k consecutive frames under tau_lo must declare lost"
    assert out[5] is None, "a score between the thresholds must not re-attach"
    assert out[6] is None, "6.0 < tau_hi 8.0: still lost"
    assert a.inner.calls == len(script), (a.inner.calls, "memory must advance while lost")
    a.inner.confs = [9.0]
    assert a.step(None)[0] is not None and not a.lost, "at or above tau_hi comes back"
    print("dam4sam lt state machine ok")


def _check_lt() -> None:
    """The long-term state machine, driven by a scripted confidence and no network.

    The three things worth breaking: it must not declare lost on a single dip, it must stop emitting
    boxes once it does, and it must not come back on a score between the two thresholds. The probe
    positions are checked too, because a sweep that keeps re-testing the same cell would still pass
    every state assertion while never finding anything.
    """
    import types

    class FakeAsym:
        def __init__(self, confs):
            self.confs, self.win, self.conf, self.cur = list(confs), None, None, 0.0
            self.conf_cos = None
            self.probed = []
            self.t = types.SimpleNamespace(state=[100, 100, 20, 20], track=self._track,
                                           params=types.SimpleNamespace(search_factor=4.0))

        def _next(self):
            return self.confs.pop(0) if self.confs else 0.0

        def init(self, frame, box):
            self.conf = 0.9
            return list(box), None

        def step(self, frame):
            self.conf = self._next()
            if self.conf < 0.3:
                self.t.state = [100, 100, 400, 400]  # a box coming apart, as it does before a loss
            x, y, w, h = self.t.state
            return [x, y, x + w, y + h], None

        def _record_win(self, xywh):
            x, y, w, h = xywh
            self.win = search_window([x, y, x + w, y + h], 4.0)

        def _track(self, img):
            self.probed.append((round(self.t.state[0]), round(self.t.state[1])))
            self.cur = self._next()
            return {"target_bbox": list(self.t.state)}

        def _corner_peak(self):
            return self.cur

    frame = np.zeros((720, 1280, 3), np.uint8)
    lt = AsymLtArm(tau_lo=0.3, tau_hi=0.7, k=3, probes=2)
    #                tracking       -> lost      lost frames, 3 probes each (local + 2 raster)
    lt.inner = FakeAsym([0.9, 0.1, 0.1, 0.1] + [0.1, 0.1, 0.1] + [0.1, 0.5, 0.1] + [0.1, 0.9, 0.1])
    lt.init(frame, [100, 100, 120, 120])

    assert lt.step(frame)[0] is not None and not lt.lost          # 0.9, plainly fine
    assert lt.step(frame)[0] is not None and not lt.lost          # 0.1 once is not a loss
    assert lt.step(frame)[0] is not None and not lt.lost          # twice still is not
    assert lt.step(frame)[0] is None and lt.lost                  # k=3 reached
    # the sweep scale is the last GOOD frame's box, not the exploding one that preceded the loss:
    # the fake blows its box up to 400x400 on every sub-tau_lo frame
    assert lt.size == (20, 20), lt.size
    assert lt.step(frame)[0] is None and lt.lost                  # all probes cold
    assert lt.step(frame)[0] is None and lt.lost                  # 0.5 sits between the thresholds
    assert lt.step(frame)[0] is not None and not lt.lost          # 0.9 clears tau_hi

    # the sweep advances: the raster cells probed across the three lost frames are all distinct,
    # and the local anchor is re-tested every one of them
    raster = [p for i, p in enumerate(lt.inner.probed) if i % 3]
    assert len(set(raster)) == len(raster) == 6, lt.inner.probed
    local = [p for i, p in enumerate(lt.inner.probed) if i % 3 == 0]
    assert len(set(local)) == 1, local
    print("long-term state machine ok")


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

    # pad arm: window stays centred where `crop_window` would have slid it, and the round trip
    # still lands on the original box even though the window hangs off the frame
    p = Sam2CropArm("x", 512, pad=True)
    p.inner = FakeInner()
    corner = [0, 0, 40, 30]
    b, _ = p.init(frame, corner)
    assert b == corner, b
    assert p.win == (-236, -241, 512), p.win  # centred on (20, 15), NOT slid to (0, 0)
    assert crop_window((20, 15), 512, 1280, 720) == (0, 0, 512)  # what the sliding arm does instead

    # floor: a shrinking box shrinks the window, until it does not. The fake returns whatever box it
    # was handed, so feeding a 10x smaller one is exactly the collapse `f5` shows on car9.
    class Shrink(FakeInner):
        def step(self, sub):
            x1, y1, x2, y2 = self.last_in
            self.last_in = [x1, y1, x1 + (x2 - x1) / 4, y1 + (y2 - y1) / 4]
            return list(self.last_in), []

    for floor, want in [(False, 18), (True, 283)]:
        f = Sam2CropArm("x", 512, factor=5.0, floor=floor)
        f.inner = Shrink()
        f.init(frame, [600, 340, 680, 380])
        for _ in range(3):
            f.step(frame)
        assert f.win[2] == want, (floor, f.win)
    assert 283 == search_window([600, 340, 680, 380], 5.0)[2]  # the floor IS the frame-0 side

    _check_lt()
    _check_dam_lt()

    class Scripted:  # boxes in CROP coords, None = lost; drives the recovery heuristics
        def __init__(self, script): self.script = list(script)
        def init(self, sub, box): return list(box), []
        def step(self, sub):
            b = self.script.pop(0) if self.script else None
            return (list(b) if b else None), []

    # A box sitting 12 px right of the crop centre every frame IS +12 px/frame of real motion: the
    # window re-centres on it, so next frame it has to move another 12 to look the same again.
    RIGHT = [[256, 236, 280, 276]]  # centre (268, 256) in a 512 crop whose centre is (256, 256)

    # 5 hits then lost. Step 6 is the first frame the arm answers None, and its window is still the
    # one the last hit set -- coasting only starts on step 7, so that is where the two arms split.
    for coast, want in [(7, [12, 24]), (0, [0, 0])]:  # coast=0 is the control: window freezes
        a = Sam2CropArm("x", 512, coast=coast)
        a.inner = Scripted(RIGHT * 5 + [None] * 6)
        a.init(frame, [600, 340, 624, 380])
        for _ in range(4):
            a.step(frame)
        assert a.win[0] == 392, a.win[0]  # 356 + 3 hits x 12
        for _ in range(2):
            a.step(frame)
        assert a.last is None and a.win[0] == 416, (a.last, a.win[0])
        for w in want:
            a.step(frame)
            assert a.win[0] == 416 + w, (coast, a.win[0], w)

    # edge: last seen hard against the right border, then lost -> full frame (win None). The latch
    # lands one frame after the loss, because the crop is chosen before the model runs.
    a = Sam2CropArm("x", 512, edge=True)
    a.inner = Scripted([[500, 236, 512, 276], None, None])
    a.init(frame, [1250, 340, 1279, 380])
    a.step(frame)
    assert a._at_edge(1280, 720), a.seen
    a.step(frame)
    assert a.last is None and a.win is not None, (a.last, a.win)
    a.step(frame)
    assert a.win is None and a.full, (a.win, a.full)

    a = Sam2CropArm("x", 512, edge=True)  # lost mid-frame is not an edge loss, stay cropped
    a.inner = Scripted([[244, 236, 268, 276], None, None])
    a.init(frame, [600, 340, 624, 380])
    for _ in range(3):
        a.step(frame)
    assert a.win is not None and not a.full, (a.win, a.full)
    print("crop geometry ok; coast + edge ok")


if __name__ == "__main__":
    import sys as _sys
    if "--self-check" in _sys.argv:
        _check()
    else:
        print(len(REGISTRY), "arms:", ", ".join(sorted(REGISTRY)))
