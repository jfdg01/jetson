"""Canonical sample schema + audit-stats dataclass (Phase 1).

The whole v2 pipeline speaks ONE sample shape: an image, a caption (the grounding
target), and a single bounding box already normalized to 0–`COORD_SCALE`. Every
adapter (`refcoco.py`, `refdrone.py`) emits this; the trainer and eval harness
consume only this. Baking the audit statistics into the dataset object means a
mis-posed target (the Stage 2 failure) is visible *before* a GPU is ever touched.

`RawRecord` is the *pre-filter* view (a caption + ALL its boxes); `audit.py`
consumes it to compute the box-per-caption distribution that the canonical
`GroundingSample` (one box by construction) has already collapsed away.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence


@dataclass(frozen=True)
class RawRecord:
    """One referring expression BEFORE the well-posed filter.

    A caption together with ALL of its *real* (non-empty) boxes in pixel XYXY. The
    box-per-caption distribution — the Stage-2 ill-posedness sentinel — is only
    visible at this pre-filter granularity, so the audit consumes `RawRecord`s, not
    the already-collapsed-to-one-box `GroundingSample`s.
    """

    caption: str
    boxes_xyxy: List[List[float]]  # all real boxes, pixel XYXY
    img_w: int
    img_h: int
    source: str  # "refcoco" | "refdrone" | ...


@dataclass(frozen=True)
class GroundingSample:
    """One well-posed grounding example in the canonical convention.

    bbox is [x1, y1, x2, y2] integers normalized to [0, COORD_SCALE] (see
    `grounding.contract.normalize_bbox`).
    """

    image_path: str
    caption: str
    bbox: List[int]
    # original pixel size, retained for object-size audit + resolution strategy
    img_w: int
    img_h: int
    source: str  # "refcoco" | "refdrone" | ...


@dataclass(frozen=True)
class AuditStats:
    """Distribution summary produced by `audit.py`; baked onto a dataset split."""

    source: str
    split: str
    n_records: int                   # raw referring expressions (pre-filter)
    n_real_boxes: int                # total non-empty boxes across all records
    boxes_per_caption: Dict[str, int]    # histogram {n_boxes(str): count}
    boxes_per_caption_mean: float        # the Part-I "3.80" sentinel
    n_well_posed: int                # records kept by the one-box filter
    well_posed_fraction: float       # share that survives the one-box filter
    obj_size_px_percentiles: Dict[str, float]      # {p5,p10,...} of sqrt(area) px
    obj_size_px_after_resize: Dict[str, float]     # same, after IMAGE_SIZE resize
    image_size: int                  # the long-edge resize the audit assumed


def load_split(name: str, split: str) -> List[GroundingSample]:
    """Load a named dataset split as canonical `GroundingSample`s."""
    raise NotImplementedError("filled in at Phase 1 startup")
