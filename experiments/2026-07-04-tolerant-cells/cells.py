"""E23 tolerant-cell sizing -- the overlapping-cell crop grammar + fuzzy operator.

E20's crop grammar (`scope.py`) quantises the operator's phrase to a rigid 3x3 grid
of exact thirds + a fixed 0.10 pad. That grid is too cagey: a target at 34% of frame
width classes "center" (0.34 > 1/3) yet a real operator would say "left". E23 replaces
E20's `third + fixed pad` with ONE knob -- a half-width HW. Cells are centered windows
on each axis at centers {1/6, 3/6, 5/6}; a cell spans [center - HW, center + HW]
(fraction of axis), clamped to the frame.

HW = 1/6 + 0.10 = 0.2667 EXACTLY reproduces E20's padded cells (a third's half-width
1/6 plus E20's 0.10 pad), so E23 is a clean superset -- the selfcheck asserts byte
equality against `scope.crop_rect` for all 9 cells. For HW > 1/6 the cells OVERLAP: a
boundary target lands inside more than one cell, so an operator naming either neighbour
still crops it.

`hint_for` (the true cell = centroid's nearest third) is UNCHANGED and imported from
E20's `scope.py` -- it is the ground-truth cell. `map_back` is likewise imported. What
E23 adds: (a) the HW-parameterised crop size, and (b) a fuzzy-operator model
(`plausible_hints` / `worst_hint`) that enumerates the coarse spatial terms a casual
operator might plausibly use for a target near a cell edge.

    .venv-ft/bin/python experiments/2026-07-04-tolerant-cells/cells.py  # selfcheck
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E20 = REPO / "experiments" / "2026-07-04-prompt-scoped-acquire"
sys.path.insert(0, str(E20))

import scope  # noqa: E402  -- import E20's audited grammar (do not copy)
from scope import hint_for, map_back  # noqa: E402,F401  re-export the true cell + map-back

PAD_FRAC = 0.10                 # E20's fixed pad (kept only to define HW_E20)
HW_E20 = 1 / 3 / 2 + PAD_FRAC   # = 1/6 + 0.10 = 0.2667: reproduces E20's padded cells
MAX_SIDE = 1024                 # deployed acquire cap; used only for the area proxy

# per-axis cell centers (the three thirds' midpoints)
COL_CENTER = {"left": 1 / 6, "center": 3 / 6, "right": 5 / 6}
ROW_CENTER = {"top": 1 / 6, "middle": 3 / 6, "bottom": 5 / 6}


def _cell_of(hint: str):
    """Hint string -> (row, col). 'center' == ('middle', 'center')."""
    if hint == "center":
        return "middle", "center"
    row, col = hint.split(" ", 1)
    return row, col


def _name(row: str, col: str) -> str:
    return "center" if (row, col) == ("middle", "center") else f"{row} {col}"


def crop_rect(hint: str, w: int, h: int, hw: float = HW_E20):
    """Named cell -> centered HW-window, clamped, as an int pixel rect (x0,y0,x1,y1).

    At hw = HW_E20 this is byte-identical to `scope.crop_rect(hint, w, h)` for all 9
    grid cells (asserted in selfcheck). The arithmetic mirrors scope's: each axis is
    center +/- hw, scaled and int-truncated, then clamped to the frame.
    """
    row, col = _cell_of(hint)
    cx, cy = COL_CENTER[col], ROW_CENTER[row]
    return (max(int((cx - hw) * w), 0), max(int((cy - hw) * h), 0),
            min(int((cx + hw) * w), w), min(int((cy + hw) * h), h))


def regions(hw: float = HW_E20):
    """The 9 grid cells as clamped fractional rects (x0,y0,x1,y1) in [0,1] for a HW."""
    out = {}
    for row in ROW_CENTER:
        for col in COL_CENTER:
            cx, cy = COL_CENTER[col], ROW_CENTER[row]
            out[_name(row, col)] = (max(cx - hw, 0.0), max(cy - hw, 0.0),
                                    min(cx + hw, 1.0), min(cy + hw, 1.0))
    return out


def contains(rect, box) -> bool:
    """Does an int pixel crop rect fully contain a GT box (x0,y0,x1,y1)?"""
    return (rect[0] <= box[0] and rect[1] <= box[1]
            and rect[2] >= box[2] and rect[3] >= box[3])


def capped_area(cw: int, ch: int, max_side: int = MAX_SIDE) -> float:
    """Effective pixel count fed to the VLM after the max_side cap (latency proxy).

    Crops smaller than the cap are sent native (E20 D7); a crop whose long side
    exceeds max_side is downscaled preserving aspect, exactly like the full frame.
    """
    s = min(1.0, max_side / max(cw, ch))
    return (cw * s) * (ch * s)


def crop_area_frac(hint: str, w: int, h: int, hw: float, max_side: int = MAX_SIDE) -> float:
    """Crop's capped pixel area as a fraction of the capped full frame (latency proxy)."""
    x0, y0, x1, y1 = crop_rect(hint, w, h, hw)
    return capped_area(x1 - x0, y1 - y0, max_side) / capped_area(w, h, max_side)


def _centroid_frac(box, w: int, h: int):
    return (box[0] + box[2]) / 2 / w, (box[1] + box[3]) / 2 / h


def plausible_hints(box, w: int, h: int, tau: float = 0.10):
    """Fuzzy operator: every coarse (row,col) phrasing a casual operator might use for
    the target's frame-0 centroid, per the frozen tau model:

      col: left if cx < 1/3 + tau; right if cx > 2/3 - tau;
           center if 1/3 - tau < cx < 2/3 + tau.
      row: top  if cy < 1/3 + tau; bottom if cy > 2/3 - tau;
           middle if 1/3 - tau < cy < 2/3 + tau.

    A centroid in an overlap band yields >= 2 plausible terms on that axis. Returns the
    cartesian product as hint strings (>= 1 always -- the true cell is always plausible).
    """
    cx, cy = _centroid_frac(box, w, h)
    cols = [c for c, ok in (("left", cx < 1 / 3 + tau),
                            ("center", 1 / 3 - tau < cx < 2 / 3 + tau),
                            ("right", cx > 2 / 3 - tau)) if ok]
    rows = [r for r, ok in (("top", cy < 1 / 3 + tau),
                            ("middle", 1 / 3 - tau < cy < 2 / 3 + tau),
                            ("bottom", cy > 2 / 3 - tau)) if ok]
    return [_name(r, c) for r in rows for c in cols]


def plausible_cols(box, w: int, h: int, tau: float = 0.10):
    """The plausible column terms only (for the selfcheck / reporting)."""
    cx, _ = _centroid_frac(box, w, h)
    return {c for c, ok in (("left", cx < 1 / 3 + tau),
                            ("center", 1 / 3 - tau < cx < 2 / 3 + tau),
                            ("right", cx > 2 / 3 - tau)) if ok}


def worst_hint(box, w: int, h: int, tau: float = 0.10) -> str:
    """The most edge-ward plausible phrasing -- the hardest cell for a crop to contain.

    Containment is per-axis independent, so the worst cell pairs the plausible column
    whose center is FARTHEST from the target centroid with the plausible row likewise.
    That pushes the target closest to (or past) the crop's boundary on both axes.
    """
    cx, cy = _centroid_frac(box, w, h)
    cols = [c for c, ok in (("left", cx < 1 / 3 + tau),
                            ("center", 1 / 3 - tau < cx < 2 / 3 + tau),
                            ("right", cx > 2 / 3 - tau)) if ok]
    rows = [r for r, ok in (("top", cy < 1 / 3 + tau),
                            ("middle", 1 / 3 - tau < cy < 2 / 3 + tau),
                            ("bottom", cy > 2 / 3 - tau)) if ok]
    worst_col = max(cols, key=lambda c: abs(cx - COL_CENTER[c]))
    worst_row = max(rows, key=lambda r: abs(cy - ROW_CENTER[r]))
    return _name(worst_row, worst_col)


# frame-0 UAV123 GT (x,y,bw,bh, 1-based) for the six E23/E20 clips
GT0 = {"car3": (403, 503, 16, 41), "car7": (538, 48, 40, 44),
       "car9": (440, 439, 99, 169), "car10": (636, 278, 46, 38),
       "car14": (423, 250, 43, 68), "car18": (246, 278, 131, 59)}


def gt0_box(clip: str):
    x, y, bw, bh = GT0[clip]
    return (x - 1.0, y - 1.0, x - 1.0 + bw, y - 1.0 + bh)  # 1-based -> 0-based x0y0x1y1


def selfcheck() -> None:
    w, h = 1280, 720

    # (a) HW_E20 reproduces E20's padded cells byte-for-byte, all 9 grid cells --------
    for hint in scope.REGIONS:
        if "half" in hint:
            continue                                   # E23 grammar is the 3x3 grid
        assert crop_rect(hint, w, h, HW_E20) == scope.crop_rect(hint, w, h), \
            (hint, crop_rect(hint, w, h, HW_E20), scope.crop_rect(hint, w, h))

    # (b) car14's plausible cols == {left, center} at tau=0.10 (the 34% example) ------
    b14 = gt0_box("car14")
    assert plausible_cols(b14, w, h, 0.10) == {"left", "center"}, \
        plausible_cols(b14, w, h, 0.10)
    assert hint_for(b14, w, h) == "center", hint_for(b14, w, h)   # true cell unchanged
    assert worst_hint(b14, w, h, 0.10) == "top left", worst_hint(b14, w, h, 0.10)

    # (c) the knob does something: car14's worst_hint crop contains the box at HW=0.44
    #     but NOT at HW=0.2667 (bigger cells absorb the fuzz) -----------------------
    wh = worst_hint(b14, w, h, 0.10)
    assert contains(crop_rect(wh, w, h, 0.44), b14), (wh, crop_rect(wh, w, h, 0.44), b14)
    assert not contains(crop_rect(wh, w, h, HW_E20), b14), \
        (wh, crop_rect(wh, w, h, HW_E20), b14)

    # map_back round-trips (re-exported from scope) ----------------------------------
    r = crop_rect("bottom left", w, h, HW_E20)
    assert map_back((10.0, 20.0, 30.0, 40.0), r) == (10 + r[0], 20 + r[1],
                                                     30 + r[0], 40 + r[1])
    assert map_back(None, r) is None

    # every cell is a valid clamped rect for the whole HW sweep -----------------------
    for hw in (HW_E20, 0.32, 0.38, 0.44, 0.50):
        for hint in regions(hw):
            x0, y0, x1, y1 = crop_rect(hint, w, h, hw)
            assert 0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h, (hw, hint)

    # plausible set always includes the true cell ------------------------------------
    for clip in GT0:
        b = gt0_box(clip)
        assert hint_for(b, w, h) in plausible_hints(b, w, h, 0.10), clip
        assert worst_hint(b, w, h, 0.10) in plausible_hints(b, w, h, 0.10), clip

    print("cells selfcheck OK")


if __name__ == "__main__":
    selfcheck()
