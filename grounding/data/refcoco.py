"""RefCOCO → canonical schema adapter (Phase 1).

RefCOCO is the in-domain/warm-start corpus (Stage 3 produced the G2-PASS
checkpoint from it). Converts COCO xywh → xyxy → normalized 0–`COORD_SCALE` via
`grounding.contract.normalize_bbox`.

Filled in at Phase 1 startup.
"""

from __future__ import annotations

from typing import List

from grounding.data.schema import GroundingSample


def load_refcoco(split: str) -> List[GroundingSample]:
    """Return RefCOCO `split` as canonical single-box samples."""
    raise NotImplementedError("filled in at Phase 1 startup")
