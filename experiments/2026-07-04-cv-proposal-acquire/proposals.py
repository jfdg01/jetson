"""E22 CV-proposal acquire -- the ~ms CPU location prior.

E20 cut the ~4.85 s full-frame VLM acquire to ~1.85 s by cropping the padded 3x3
cell the OPERATOR named (cell 3/6, PARTIAL [hint-fragile]). E21 tried to automate
that hint with a second, coarse VLM pass and lost both axes (NO [prior-wrong]: the
320px coarse vote is inaccurate AND its +0.97 s re-opens the staleness gap). E22's
surviving hypothesis: a ~zero-cost CPU prior -- camera-motion-compensated frame
differencing intersected with the caption colour -> a 3x3 cell vote -- preserves
E20's latency with no operator and no second VLM call.

    propose(prev_bgr, cur_bgr, color_kw) -> (hint | None, source | None)

All stages run at a working width of 320 (D5: thresholds FROZEN). UAV123 has a
MOVING camera, so raw frame differencing is swamped by global motion; step 1
estimates the global translation with phaseCorrelate and warps `prev` onto `cur`
before differencing (D3: translation-only; homography is the documented upgrade
path if Phase 0 shows rotation/zoom clips failing).

    .venv-ft/bin/python experiments/2026-07-04-cv-proposal-acquire/proposals.py  # selfcheck
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E20 = REPO / "experiments" / "2026-07-04-prompt-scoped-acquire"
sys.path.insert(0, str(E20))       # import E20's audited scope.py (D1) -- do not copy

import scope                                                          # noqa: E402

# --- FROZEN thresholds (D5) --------------------------------------------------
WORK_W = 320       # working width; all stages run here (D5)
MOTION_T = 25      # absdiff -> binary threshold
OPEN_K = 3         # morphological-open kernel (removes salt from the motion mask)
MIN_AREA = 30      # smallest connected component to accept (px, at width 320)

# caption keyword -> caption map (frozen); the prior only needs the keyword
CLIP_KW = {"car3": "red", "car10": "red", "car14": "red", "car18": "red",
           "car9": "white", "car7": "silver"}


def _work(frame_bgr: np.ndarray) -> np.ndarray:
    """Downscale to the frozen working width (INTER_AREA), aspect kept."""
    h, w = frame_bgr.shape[:2]
    s = WORK_W / w
    return cv2.resize(frame_bgr, (WORK_W, max(round(h * s), 1)),
                      interpolation=cv2.INTER_AREA)


def _color_mask(work_bgr: np.ndarray, kw: str) -> np.ndarray:
    """Frozen HSV colour mask for the caption keyword (uint8 0/255).
    red is a strong cue; white/silver are WEAK (sky, road glare)."""
    hsv = cv2.cvtColor(work_bgr, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    if kw == "red":
        m = ((H <= 10) | (H >= 170)) & (S >= 90) & (V >= 60)
    elif kw == "white":
        m = (S <= 40) & (V >= 170)
    elif kw == "silver":
        m = (S <= 40) & (V >= 90) & (V <= 170)
    else:
        raise ValueError(f"unknown colour keyword {kw!r}")
    return (m.astype(np.uint8)) * 255


def _motion_mask(prev_bgr: np.ndarray, cur_bgr: np.ndarray) -> np.ndarray:
    """Camera-motion-compensated frame-difference mask (uint8 0/255).
    phaseCorrelate estimates the global translation of `cur` w.r.t. `prev`;
    warp `prev` by it so only INDEPENDENT (target) motion survives absdiff."""
    pg = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    cg = cv2.cvtColor(cur_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = pg.shape
    han = cv2.createHanningWindow((w, h), cv2.CV_32F)
    (dx, dy), _ = cv2.phaseCorrelate(pg, cg, han)   # shift of cur relative to prev
    M = np.float32([[1, 0, dx], [0, 1, dy]])        # warp prev onto cur
    pg_a = cv2.warpAffine(pg, M, (w, h))
    diff = cv2.absdiff(pg_a, cg).astype(np.uint8)
    _, mm = cv2.threshold(diff, MOTION_T, 255, cv2.THRESH_BINARY)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (OPEN_K, OPEN_K))
    return cv2.morphologyEx(mm, cv2.MORPH_OPEN, k)


def propose(prev_bgr: np.ndarray, cur_bgr: np.ndarray, color_kw: str):
    """CPU location prior -> (hint | None, source | None).

    source in {"motion+color", "motion", "color"} when a hint is produced,
    else None. Stages (all at width 320): camera-comp motion mask AND caption
    colour mask (falling back to whichever is non-empty) -> largest connected
    component with area >= MIN_AREA -> centroid -> scope.hint_for.
    """
    pw = _work(prev_bgr)
    cw = _work(cur_bgr)
    wh, ww = cw.shape[:2]
    mm = _motion_mask(pw, cw)
    cm = _color_mask(cw, color_kw)
    m_has, c_has = int(mm.any()), int(cm.any())
    if m_has and c_has:
        combined, source = cv2.bitwise_and(mm, cm), "motion+color"
    elif m_has:
        combined, source = mm, "motion"
    elif c_has:
        combined, source = cm, "color"
    else:
        return None, None
    n, _, stats, cents = cv2.connectedComponentsWithStats(combined, connectivity=8)
    if n <= 1:
        return None, None
    areas = stats[1:, cv2.CC_STAT_AREA]
    k = int(np.argmax(areas)) + 1
    if stats[k, cv2.CC_STAT_AREA] < MIN_AREA:
        return None, None
    cx, cy = cents[k]
    hint = scope.hint_for((cx, cy, cx, cy), ww, wh)
    return hint, source


# --------------------------------------------------------------------------- #
def selfcheck() -> None:
    """Offline (no Jetson): (1) a translating BACKGROUND + an independently moving
    RED patch -> the patch's cell (motion+color isolates it from the camera pan);
    (2) an identical, neutral pair -> None (no motion, no colour) -> full-frame
    fallback."""
    W, H = 1280, 720
    rng = np.random.default_rng(0)

    # -- (1) translating background + a differently-moving red patch -----------
    # base texture (bright, so a dark-in-gray red target diffs cleanly) larger
    # than the frame so we can crop panned views; texture gives phaseCorrelate
    # features to lock onto.
    pan = 24
    base = rng.integers(120, 230, (H + 2 * pan, W + 2 * pan, 3), dtype=np.uint8)
    prev = base[pan:pan + H, pan:pan + W].copy()                 # camera at origin
    cur = base[pan + 10:pan + 10 + H, pan + 20:pan + 20 + W].copy()  # panned (+20,+10)
    # red square that does NOT follow the pan -> independent motion on screen.
    # centre it at (640, 540): cx=0.5 (center col), cy=0.75 (bottom row) -> "bottom center"
    cv2.rectangle(prev, (280, 280), (400, 400), (0, 0, 255), -1)  # prev red pos (decoy)
    cv2.rectangle(cur, (580, 480), (700, 600), (0, 0, 255), -1)   # cur red pos (target)
    hint, source = propose(prev, cur, "red")
    assert hint == "bottom center", (hint, source)
    assert source == "motion+color", source
    # ground truth from scope on the cur box centroid, sanity that the cell agrees
    assert scope.hint_for((610, 510, 670, 570), W, H) == "bottom center"

    # -- (2) identical neutral pair -> no motion, no colour -> None ------------
    flat = np.full((H, W, 3), 130, dtype=np.uint8)
    assert propose(flat.copy(), flat.copy(), "red") == (None, None)
    # also a static pair with texture but no red: colour empty, motion empty
    tex = rng.integers(60, 190, (H, W, 3), dtype=np.uint8)
    assert propose(tex.copy(), tex.copy(), "red") == (None, None)

    # -- timing: the prior must be ~ms (sanity, not a gate) --------------------
    t0 = time.monotonic()
    for _ in range(5):
        propose(prev, cur, "red")
    ms = (time.monotonic() - t0) / 5 * 1000
    assert ms < 100, f"prior too slow: {ms:.1f} ms"
    print(f"proposals selfcheck OK (prior ~{ms:.1f} ms at width {WORK_W})")


if __name__ == "__main__":
    selfcheck()
