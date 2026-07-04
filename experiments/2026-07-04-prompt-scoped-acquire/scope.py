"""E20 prompt-scoped acquire -- the crop-grammar core.

E18/E19 measured the binder: the ~4.85 s full-frame VLM acquire lands stale.
Prefill cost scales with image area (ROI campaign: M=2.0@512 crop = 2.7x
cheaper AND +22.6pp), but first acquire has no location prior. E20's prior is
the operator's own phrase: "the red car in the bottom left" -> crop the padded
bottom-left cell, acquire in the crop, map the box back to full-frame coords.

The phrase is consumed CLIENT-SIDE: the caption sent to the VLM stays the
frozen E18 caption ("the red car"); the spatial part only picks the crop.

    .venv-ft/bin/python experiments/2026-07-04-prompt-scoped-acquire/scope.py  # selfcheck
"""

from __future__ import annotations

PAD_FRAC = 0.10  # pre-registered: expand the named region by 10% of frame W/H
                 # each side so a boundary-straddling target stays inside

_COLS = {"left": (0, 1 / 3), "center": (1 / 3, 2 / 3), "right": (2 / 3, 1.0)}
_ROWS = {"top": (0, 1 / 3), "middle": (1 / 3, 2 / 3), "bottom": (2 / 3, 1.0)}

# 3x3 cell grammar ("center" = middle center) + halves. Halves exist for
# completeness but are not matrixed in E20: on 720p under the max_side=1024
# cap a half crop saves ~1.1x pixels -- no latency lever (see README D2).
REGIONS = {
    **{(f"{r} {c}" if not (r == "middle" and c == "center") else "center"):
       (cx0, ry0, cx1, ry1)
       for r, (ry0, ry1) in _ROWS.items() for c, (cx0, cx1) in _COLS.items()},
    "left half": (0, 0, 0.5, 1.0), "right half": (0.5, 0, 1.0, 1.0),
    "top half": (0, 0, 1.0, 0.5), "bottom half": (0, 0.5, 1.0, 1.0),
}


def crop_rect(hint: str, w: int, h: int, pad: float = PAD_FRAC):
    """Named region -> padded, clamped int pixel rect (x0, y0, x1, y1)."""
    fx0, fy0, fx1, fy1 = REGIONS[hint]
    px, py = pad * w, pad * h
    return (max(int(fx0 * w - px), 0), max(int(fy0 * h - py), 0),
            min(int(fx1 * w + px), w), min(int(fy1 * h + py), h))


def hint_for(box, w: int, h: int) -> str:
    """Honest operator phrase for a frame-0 GT box (x0, y0, x1, y1):
    the 3x3 cell containing its centroid. Simulates an operator who looks at
    the screen and says where the target is."""
    cx, cy = (box[0] + box[2]) / 2 / w, (box[1] + box[3]) / 2 / h
    col = "left" if cx < 1 / 3 else ("center" if cx < 2 / 3 else "right")
    row = "top" if cy < 1 / 3 else ("middle" if cy < 2 / 3 else "bottom")
    return "center" if (row, col) == ("middle", "center") else f"{row} {col}"


def map_back(box, rect):
    """Box in crop coords -> full-frame coords. None passes through."""
    if box is None:
        return None
    x0, y0 = rect[0], rect[1]
    return (box[0] + x0, box[1] + y0, box[2] + x0, box[3] + y0)


def selfcheck() -> None:
    w, h = 1280, 720
    # the six E20 clip hints, from frame-0 UAV123 GT (x,y,bw,bh 1-based)
    gt0 = {"car3": (403, 503, 16, 41), "car7": (538, 48, 40, 44),
           "car9": (440, 439, 99, 169), "car10": (636, 278, 46, 38),
           "car14": (423, 250, 43, 68), "car18": (246, 278, 131, 59)}
    want = {"car3": "bottom left", "car7": "top center", "car9": "bottom center",
            "car10": "center", "car14": "center", "car18": "middle left"}
    for clip, (x, y, bw, bh) in gt0.items():
        box = (x, y, x + bw, y + bh)
        hint = hint_for(box, w, h)
        assert hint == want[clip], (clip, hint)
        r = crop_rect(hint, w, h)
        assert r[0] <= box[0] and r[1] <= box[1] and r[2] >= box[2] \
            and r[3] >= box[3], (clip, hint, r, box)   # padded cell contains GT
        # latency lever: every padded cell is well under the 1024-cap full frame
        assert (r[2] - r[0]) * (r[3] - r[1]) < 0.55 * (1024 * 576), (clip, r)
    # map_back round-trips
    r = crop_rect("bottom left", w, h)
    b = map_back((10.0, 20.0, 30.0, 40.0), r)
    assert b == (10 + r[0], 20 + r[1], 30 + r[0], 40 + r[1]), b
    assert map_back(None, r) is None
    # clamping: corner cells never leave the frame
    for hint in REGIONS:
        x0, y0, x1, y1 = crop_rect(hint, w, h)
        assert 0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h, hint
    print("scope selfcheck OK")


if __name__ == "__main__":
    selfcheck()
