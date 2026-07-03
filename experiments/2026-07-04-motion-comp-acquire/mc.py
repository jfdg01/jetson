"""E19 motion-compensated acquire — the flow-arm core.

E18 measured the binder: the ~4.85 s blocking VLM acquire returns a box that
was correct for the frame the model SAW, but the target has moved ~146 frames
by arrival. mc_shift re-finds the submit-frame crop in the arrival frame
(whole-frame NCC template match, ~ms) and shifts the box there before carry
init. Appearance change over ~5 s is the known ceiling; the refusal threshold
keeps a bad match from being worse than staleness.

    .venv-ft/bin/python experiments/2026-07-04-motion-comp-acquire/mc.py  # selfcheck
"""

from __future__ import annotations

import cv2
import numpy as np

MIN_SCORE = 0.5  # pre-registered refusal threshold: below this, keep the stale box


def mc_shift(submit_bgr: np.ndarray, box, arrival_bgr: np.ndarray,
             min_score: float = MIN_SCORE):
    """Template-match the submit-frame box crop in the arrival frame.

    Returns (box', ncc_score, applied). applied=False (box unchanged) when the
    crop is degenerate or the best match scores under min_score — a stale box
    is recoverable by carry (E18 showed cov 0.90-0.99 despite it); a
    teleported wrong match is not.
    """
    x1, y1 = max(int(round(box[0])), 0), max(int(round(box[1])), 0)
    x2, y2 = int(round(box[2])), int(round(box[3]))
    tpl = submit_bgr[y1:y2, x1:x2]
    if tpl.shape[0] < 4 or tpl.shape[1] < 4:
        return tuple(box), 0.0, False
    res = cv2.matchTemplate(arrival_bgr, tpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, (mx, my) = cv2.minMaxLoc(res)
    score = float(np.nan_to_num(score))
    if score < min_score:
        return tuple(box), score, False
    w, h = box[2] - box[0], box[3] - box[1]
    return (float(mx), float(my), float(mx) + w, float(my) + h), score, True


def selfcheck() -> None:
    rng = np.random.default_rng(0)
    patch = rng.integers(0, 255, (24, 32, 3), dtype=np.uint8)
    bg = rng.integers(100, 140, (200, 300, 3), dtype=np.uint8)
    submit, arrival = bg.copy(), bg.copy()
    submit[20:44, 20:52] = patch            # target at (20,20) when the VLM saw it
    arrival[60:84, 130:162] = patch         # moved to (130,60) by box arrival
    box = (20.0, 20.0, 52.0, 44.0)          # the (correct-but-stale) VLM box
    shifted, score, applied = mc_shift(submit, box, arrival)
    assert applied and score > 0.9, (score, applied)
    assert shifted == (130.0, 60.0, 162.0, 84.0), shifted
    # refusal: target absent from arrival frame -> keep the stale box
    _, score2, applied2 = mc_shift(submit, box, bg)
    assert not applied2 and score2 < MIN_SCORE, (score2, applied2)
    # refusal: degenerate sliver box
    _, _, applied3 = mc_shift(submit, (5.0, 5.0, 7.0, 40.0), arrival)
    assert not applied3
    print("mc selfcheck OK")


if __name__ == "__main__":
    selfcheck()
