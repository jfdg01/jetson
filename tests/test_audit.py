"""Phase-1 dataset-audit gate tests.

Locks the box-per-caption counting + well-posed-fraction logic and the gate
assertion. These run with no data on disk (synthetic RawRecords), so they are a
fast regression gate against the Stage-2 ill-posedness sentinel drifting.
"""

from __future__ import annotations

import math

import pytest

from grounding.contract import IMAGE_SIZE
from grounding.data.audit import _percentiles, assert_well_posed, audit
from grounding.data.schema import RawRecord


def _rec(n_boxes: int, *, box=(0.0, 0.0, 10.0, 10.0), img=(1000, 500)) -> RawRecord:
    return RawRecord(
        caption="x",
        boxes_xyxy=[list(box) for _ in range(n_boxes)],
        img_w=img[0],
        img_h=img[1],
        source="synthetic",
    )


def test_box_per_caption_histogram_and_mean():
    recs = [_rec(1), _rec(1), _rec(2), _rec(4)]
    st = audit(recs, split="t")
    assert st.n_records == 4
    assert st.n_real_boxes == 1 + 1 + 2 + 4
    assert st.boxes_per_caption == {"1": 2, "2": 1, "4": 1}
    assert st.boxes_per_caption_mean == pytest.approx(8 / 4)
    assert st.n_well_posed == 2
    assert st.well_posed_fraction == pytest.approx(0.5)


def test_object_size_pre_and_post_resize():
    # one record, one 10x10 box on a 1000-long-edge image → √area = 10 px.
    st = audit([_rec(1, box=(0, 0, 10, 10), img=(1000, 500))], split="t")
    assert st.obj_size_px_percentiles["p50"] == pytest.approx(10.0)
    # post-resize scale = IMAGE_SIZE / max(w,h) = 512/1000
    assert st.obj_size_px_after_resize["p50"] == pytest.approx(10.0 * IMAGE_SIZE / 1000)
    assert st.image_size == IMAGE_SIZE


def test_gate_passes_on_well_posed_and_fails_on_ill_posed():
    well = audit([_rec(1), _rec(1), _rec(1)], split="t")
    assert_well_posed(well)  # must not raise

    ill = audit([_rec(1), _rec(3), _rec(5)], split="t")
    with pytest.raises(AssertionError):
        assert_well_posed(ill)


def test_audit_rejects_empty():
    with pytest.raises(ValueError):
        audit([], split="t")


def test_percentiles_single_value():
    assert _percentiles([7.0])["p50"] == pytest.approx(7.0)
    assert _percentiles([]) == {}
