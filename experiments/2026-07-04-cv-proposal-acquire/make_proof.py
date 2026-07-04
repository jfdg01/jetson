"""E22 proof figure -- the Phase-0 gate FAILED (2/6), so there is no Jetson matrix
and no run overlays. The thesis evidence for this NEGATIVE result is the CPU prior's
own stages: for three representative clips at t=0 this montages
  [cur frame + GT box (red) + proposed centroid (yellow)] | [motion mask] |
  [colour mask] | [combined]
so the reader SEES why the prior is insufficient on this footage:
  - car9 (white, large): HIT -- motion+colour both fire on the target.
  - car3 (red, tiny):    MISS -- target is ~4 px wide at width 320; both masks empty
                         in the GT box, camera-comp cancels its sub-pixel t=0 motion.
  - car7 (silver):       MISS -- the silver HSV mask floods the whole bright scene
                         (sky/road glare), centroid lands "center" not GT "top center".

    .venv-ft/bin/python experiments/2026-07-04-cv-proposal-acquire/make_proof.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
E20 = REPO / "experiments" / "2026-07-04-prompt-scoped-acquire"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(E18))
sys.path.insert(0, str(E20))

import proposals                                                     # noqa: E402
import scope                                                         # noqa: E402
from replay_source import load_uav123_gt                            # noqa: E402

DATA = E18 / "data" / "UAV123"
PANEL_W = 360
ROWS = [("car9", "HIT motion+colour"), ("car3", "MISS tiny target"),
        ("car7", "MISS silver floods scene")]


def _fit(img, w=PANEL_W):
    h = round(img.shape[0] * w / img.shape[1])
    return cv2.resize(img, (w, h))


def _label(img, text):
    cv2.rectangle(img, (0, 0), (img.shape[1], 22), (0, 0, 0), -1)
    cv2.putText(img, text, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (255, 255, 255), 1)
    return img


def row(clip, tag):
    paths = sorted((DATA / "data_seq" / "UAV123" / clip).glob("*.jpg"))
    gt = load_uav123_gt(DATA / "anno" / "UAV123" / f"{clip}.txt")
    cur = cv2.imread(str(paths[0]))
    prev = cv2.imread(str(paths[15]))
    h0, w0 = cur.shape[:2]
    kw = proposals.CLIP_KW[clip]
    hint, source = proposals.propose(prev, cur, kw)
    gt_hint = scope.hint_for(gt[0], w0, h0)

    pw, cw = proposals._work(prev), proposals._work(cur)
    mm = proposals._motion_mask(pw, cw)
    cm = proposals._color_mask(cw, kw)

    frame = cur.copy()
    g = [int(v) for v in gt[0]]
    cv2.rectangle(frame, (g[0], g[1]), (g[2], g[3]), (0, 0, 220), 3)
    p1 = _label(_fit(frame), f"{clip} {kw} GT={gt_hint}")
    p2 = _label(_fit(cv2.cvtColor(mm, cv2.COLOR_GRAY2BGR)), "motion mask (cam-comp)")
    p3 = _label(_fit(cv2.cvtColor(cm, cv2.COLOR_GRAY2BGR)), "colour mask")
    comb = mm.copy()
    if mm.any() and cm.any():
        comb = cv2.bitwise_and(mm, cm)
    elif not mm.any():
        comb = cm
    p4 = _label(_fit(cv2.cvtColor(comb, cv2.COLOR_GRAY2BGR)),
                f"combined -> {hint} [{tag}]")
    hh = min(p.shape[0] for p in (p1, p2, p3, p4))
    return np.hstack([p[:hh] for p in (p1, p2, p3, p4)])


def main():
    (HERE / "proof").mkdir(exist_ok=True)
    rows = [row(c, t) for c, t in ROWS]
    ww = min(r.shape[1] for r in rows)
    montage = np.vstack([r[:, :ww] for r in rows])
    out = HERE / "proof" / "phase0_prior_stages.png"
    cv2.imwrite(str(out), montage)
    print("wrote", out, montage.shape)


if __name__ == "__main__":
    main()
