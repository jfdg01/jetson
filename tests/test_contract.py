"""Contract tests — the one thing in v2 that MUST NOT drift.

The whole v2 design rests on prompt/parser/metric being byte-stable and shared. These
tests lock the parser's tolerance to real model output, the metric maths, and (most
importantly) that GROUNDING_PROMPT stays byte-identical to the validated trainer.
Run: `python -m pytest tests/ -q` (or `make test`).
"""

from __future__ import annotations

import pytest

from grounding import contract as c


# ── GROUNDING_PROMPT: byte-stability ─────────────────────────────────────────────

def test_prompt_is_byte_identical_to_validated_string():
    # The exact validated string from the Stage-3 G2-PASS trainer. If this fails,
    # the contract drifted from what the fine-tuned weights were trained on.
    expected = (
        'Locate "{target}". Return the bounding box as JSON '
        '{{"bbox": [x1, y1, x2, y2]}} with integer coordinates normalized from 0 to 1000.'
    )
    assert c.GROUNDING_PROMPT == expected


def test_prompt_formats_target_and_leaves_literal_json_braces():
    out = c.GROUNDING_PROMPT.format(target="red car")
    assert 'Locate "red car".' in out
    assert '{"bbox": [x1, y1, x2, y2]}' in out  # doubled braces collapse to literals


# ── parse_bbox ───────────────────────────────────────────────────────────────────

def test_parse_clean_json():
    assert c.parse_bbox('{"bbox": [10, 20, 30, 40]}') == [10, 20, 30, 40]


def test_parse_with_surrounding_prose():
    txt = 'Sure! The object is at {"bbox": [1, 2, 3, 4]} in the image.'
    assert c.parse_bbox(txt) == [1, 2, 3, 4]


def test_parse_floats_are_truncated_to_int():
    assert c.parse_bbox('{"bbox": [10.9, 20.1, 30.5, 40.7]}') == [10, 20, 30, 40]


@pytest.mark.parametrize("bad", [
    "no bbox here",
    '{"bbox": [1, 2, 3]}',          # only three coords
    '{"bbox": []}',                  # empty
    '{"bbox": [a, b, c, d]}',        # non-numeric
    "",
])
def test_parse_unparseable_returns_none(bad):
    assert c.parse_bbox(bad) is None


# ── normalize_bbox ───────────────────────────────────────────────────────────────

def test_normalize_basic():
    # full-image box on a 100x200 image → [0,0,1000,1000]
    assert c.normalize_bbox([0, 0, 100, 200], 100, 200) == [0, 0, 1000, 1000]


def test_normalize_clamps_overflow():
    assert c.normalize_bbox([-10, -10, 200, 400], 100, 200) == [0, 0, 1000, 1000]


# ── iou ──────────────────────────────────────────────────────────────────────────

def test_iou_identical_is_one():
    assert c.iou([0, 0, 10, 10], [0, 0, 10, 10]) == pytest.approx(1.0)


def test_iou_disjoint_is_zero():
    assert c.iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0


def test_iou_half_overlap():
    # [0,0,10,10] vs [5,0,15,10]: inter=50, union=150 → 1/3
    assert c.iou([0, 0, 10, 10], [5, 0, 15, 10]) == pytest.approx(1 / 3)


# ── center_std (mode-collapse sentinel) ──────────────────────────────────────────

def test_center_std_zero_for_constant_boxes():
    # collapsed model: same box every time → sentinel ~0
    boxes = [[10, 10, 20, 20]] * 5
    assert c.center_std(boxes) == 0.0


def test_center_std_positive_for_spread_boxes():
    boxes = [[0, 0, 10, 10], [500, 500, 510, 510], [900, 900, 910, 910]]
    assert c.center_std(boxes) > 0.0


def test_center_std_ignores_none_and_handles_too_few():
    assert c.center_std([None, [1, 1, 2, 2]]) == 0.0   # <2 real boxes
    assert c.center_std([]) == 0.0
