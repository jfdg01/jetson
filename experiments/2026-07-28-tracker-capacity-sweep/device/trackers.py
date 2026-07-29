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

    The two families need different tests. A crop is square and `crop_window` already caps it at
    `min(w, h)`, so anything above that is pure upsampling on both axes. A full frame is squashed to
    `image_size` square regardless of aspect, so no single axis answers it -- 1280x720 into 768
    upsamples vertically while downsampling horizontally, and still ends up with fewer pixels than
    it started with. Pixel budget is the honest comparison there.
    """
    m = REGISTRY[name]
    n = m.get("image_size")
    if n is None:
        return False  # opencv arms are handed the frame as it comes
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

    def __init__(self, checkpoint: str, size: int, coast: int = 0, edge: bool = False):
        self.size = size
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

    def _shift(self, box, dx, dy):
        return None if box is None else [box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy]

    def _crop(self, frame, center):
        h, w = frame.shape[:2]
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
                if d and self.coasted + d <= self.size:
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
        x1, y1, x2, y2 = box
        self._record_win([x1, y1, x2 - x1, y2 - y1], p)
        self.t.initialize(frame[:, :, ::-1], {"init_bbox": [x1, y1, x2 - x1, y2 - y1]})
        return [int(v) for v in (x1, y1, x2, y2)], None

    def _record_win(self, xywh, p=None):
        """The square search crop `sample_target` will take next, in frame coordinates."""
        p = p or self.t.params
        x, y, w, h = xywh
        side = float(p.search_factor) * (max(w * h, 1.0) ** 0.5)
        self.win = (int(round(x + w / 2 - side / 2)), int(round(y + h / 2 - side / 2)), int(round(side)))

    def step(self, frame):
        self._record_win(self.t.state)  # window used for THIS frame: centred on the previous box
        out = self.t.track(frame[:, :, ::-1])
        x, y, w, h = out["target_bbox"]
        return [int(x), int(y), int(x + w), int(y + h)], None


arm("asym_b", family="asymtrack", ckpt="base", search_factor=4.0, image_size=None,
    venv_python="/home/jfdg/tracker-sweep/.venv-asym/bin/python")(lambda: AsymArm("base"))


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
