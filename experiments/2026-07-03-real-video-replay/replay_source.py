"""E18 wall-clock replay source + UAV123 GT loader + scorer.

The one load-bearing realism rule: frames DROP during inference. latest()
returns whatever frame the wall clock says is current; anything the pipeline
missed while the VLM was thinking is gone, exactly like a live camera. A
replay that pauses the video while the model runs would flatter every number.

Scoring is at NATIVE fps against GT, not at pipeline rate: the held box is
whatever a downstream controller would consume at each video frame, so
staleness costs IoU. That is the honest metric.

    .venv-ft/bin/python experiments/2026-07-03-real-video-replay/replay_source.py  # selfcheck
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np


class WallClockVideo:
    """Real-time replay over a UAV123-style frames dir or a video file.

    latest() -> (frame_idx, BGR frame) for the frame the wall clock is on
    NOW, or None when the clip has ended. Repeated calls during one inference
    gap skip the frames in between -- that IS the point.

    `now` is injectable for the deterministic selfcheck only; real runs use
    time.monotonic.
    """

    def __init__(self, src: str | Path, fps: float = 30.0, now=time.monotonic):
        src = Path(src)
        self.fps, self._now = float(fps), now
        if src.is_dir():
            self._paths = sorted(src.glob("*.jpg"))
            self.n, self._cap = len(self._paths), None
        else:
            self._cap = cv2.VideoCapture(str(src))
            self.fps = self._cap.get(cv2.CAP_PROP_FPS) or self.fps
            self.n = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        assert self.n > 0, f"no frames in {src}"
        self._t0: float | None = None

    def start(self) -> None:
        self._t0 = self._now()

    def t(self) -> float:
        """Seconds since start() -- the timestamp to record with each event."""
        assert self._t0 is not None, "call start() first"
        return self._now() - self._t0

    def latest(self):
        if self._t0 is None:
            self.start()
        i = int((self._now() - self._t0) * self.fps)
        if i >= self.n:
            return None
        if self._cap is not None:
            # ponytail: per-grab seek; fine for short clips, stream-decode if it drags
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, frame = self._cap.read()
            assert ok, f"decode failed at frame {i}"
            return i, frame
        return i, cv2.imread(str(self._paths[i]))


def load_uav123_gt(anno: str | Path) -> list[tuple[float, float, float, float] | None]:
    """UAV123 anno .txt: one 'x,y,w,h' per frame (1-based, MATLAB heritage),
    NaN rows = target absent/fully occluded. Returns per-frame 0-based
    (x1, y1, x2, y2), or None where absent."""
    out: list[tuple | None] = []
    for line in Path(anno).read_text().strip().splitlines():
        vals = [float(v) for v in line.replace("\t", ",").split(",")]
        if any(v != v for v in vals) or vals[2] <= 0 or vals[3] <= 0:  # NaN or degenerate
            out.append(None)
        else:
            x, y, w, h = vals
            out.append((x - 1.0, y - 1.0, x - 1.0 + w, y - 1.0 + h))
    return out


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def score_run(events, gt, fps, lock_iou: float = 0.25) -> dict:
    """events: [(t_rel_s, box|None)] -- every held-box CHANGE the pipeline
    emitted (box=None means declared lost), t relative to replay start.
    gt: per-frame boxes from load_uav123_gt. Scored at native fps: frame i
    consumes the last event with t <= i/fps.

    Returns: t_lock (first non-None event, s), genuine_lock (that box hits
    GT at IoU>=lock_iou on its frame), coverage (frac of GT-valid frames
    after lock with IoU>=lock_iou), mean_iou (same domain), n_scored.
    """
    ev = sorted(events, key=lambda e: e[0])
    first = next(((t, b) for t, b in ev if b is not None), None)
    if first is None:
        return {"t_lock": None, "genuine_lock": False, "coverage": 0.0,
                "mean_iou": 0.0, "n_scored": 0}
    t_lock, lock_box = first
    i_lock = min(int(t_lock * fps), len(gt) - 1)
    genuine = gt[i_lock] is not None and iou(lock_box, gt[i_lock]) >= lock_iou
    ious, j, held = [], 0, None
    for i in range(len(gt)):
        t = i / fps
        while j < len(ev) and ev[j][0] <= t:
            held = ev[j][1]
            j += 1
        if t < t_lock or gt[i] is None:
            continue
        ious.append(iou(held, gt[i]) if held is not None else 0.0)
    cov = sum(v >= lock_iou for v in ious) / len(ious) if ious else 0.0
    return {"t_lock": round(t_lock, 2), "genuine_lock": bool(genuine),
            "coverage": round(cov, 4),
            "mean_iou": round(float(np.mean(ious)), 4) if ious else 0.0,
            "n_scored": len(ious)}


def selfcheck() -> None:
    import tempfile

    # -- WallClockVideo drops frames under a fake clock --------------------
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(30):
            cv2.imwrite(f"{tmp}/{i:06d}.jpg",
                        np.full((8, 8, 3), i * 8, dtype=np.uint8))
        ticks = iter([0.0, 0.0, 0.5, 0.966, 1.1])  # start, then 4 grabs
        v = WallClockVideo(tmp, fps=30.0, now=lambda: next(ticks))
        v.start()
        assert v.latest()[0] == 0
        assert v.latest()[0] == 15      # 0.5 s later: frames 1-14 dropped
        assert v.latest()[0] == 28
        assert v.latest() is None       # past end
    # -- GT loader: NaN row -> None, 1-based -> 0-based --------------------
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "seq.txt"
        p.write_text("11,21,30,40\nNaN,NaN,NaN,NaN\n1,1,10,10\n")
        gt = load_uav123_gt(p)
        assert gt[0] == (10.0, 20.0, 40.0, 60.0) and gt[1] is None
        assert gt[2] == (0.0, 0.0, 10.0, 10.0)
    # -- scorer ------------------------------------------------------------
    gt = [(0.0, 0.0, 10.0, 10.0)] * 30 + [None] * 10 + [(0.0, 0.0, 10.0, 10.0)] * 20
    fps = 10.0
    # perfect lock at t=0.5, lost (None) during the GT gap, relocks after
    ev = [(0.5, (0.0, 0.0, 10.0, 10.0)), (3.0, None), (4.2, (0.0, 0.0, 10.0, 10.0))]
    s = score_run(ev, gt, fps)
    assert s["genuine_lock"] and s["t_lock"] == 0.5
    assert s["n_scored"] == 45          # 25 pre-gap (i=5..29) + 20 post-gap
    # frames i=40,41: GT is back but relock lands t=4.2 -> honestly scored 0
    assert s["coverage"] == round(43 / 45, 4) and s["mean_iou"] == round(43 / 45, 4)
    # wrong lock: box misses GT entirely
    s = score_run([(0.5, (50.0, 50.0, 60.0, 60.0))], gt, fps)
    assert not s["genuine_lock"] and s["coverage"] == 0.0
    # never locked
    s = score_run([(3.0, None)], gt, fps)
    assert s["t_lock"] is None and s["n_scored"] == 0
    print("replay_source selfcheck OK")


if __name__ == "__main__":
    selfcheck()
