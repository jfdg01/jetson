"""RefDrone (well-posed) → canonical schema adapter (Phase 1).

The aerial target domain. Part I established the *well-posed subset* (one caption
→ one box; multi-box and empty/negative captions dropped) as the only tractable
supervision — that filter lives here and its effect is reported by `audit.py`.
The largest-box-augmentation lever (Stage 4 next-step #1) is a constructor flag.

Filled in at Phase 1 startup.
"""

from __future__ import annotations

from typing import List

from grounding.data.schema import GroundingSample


def load_refdrone(split: str, *, largest_box_aug: bool = False) -> List[GroundingSample]:
    """Return RefDrone `split` as canonical single-box samples.

    largest_box_aug: if True, keep multi-box captions but supervise the single
    largest box (the pre-registered Stage-4 data-scaling lever).
    """
    raise NotImplementedError("filled in at Phase 1 startup")
