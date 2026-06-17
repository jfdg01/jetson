"""Canonical sample schema + audit-stats dataclass (Phase 1).

The whole v2 pipeline speaks ONE sample shape: an image, a caption (the grounding
target), and a single bounding box already normalized to 0–`COORD_SCALE`. Every
adapter (`refcoco.py`, `refdrone.py`) emits this; the trainer and eval harness
consume only this. Baking the audit statistics into the dataset object means a
mis-posed target (the Stage 2 failure) is visible *before* a GPU is ever touched.

Filled in at Phase 1 startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence


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

    n_samples: int
    boxes_per_caption: dict          # histogram {n_boxes: count}
    obj_size_px_percentiles: dict    # {p10, p50, p90, ...} of sqrt(area) in px
    obj_size_px_after_resize: dict   # same, after IMAGE_SIZE long-edge resize
    well_posed_fraction: float       # share that survives the one-box filter


def load_split(name: str, split: str) -> List[GroundingSample]:
    """Load a named dataset split as canonical `GroundingSample`s."""
    raise NotImplementedError("filled in at Phase 1 startup")
