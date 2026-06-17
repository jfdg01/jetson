"""Dataset audit gate (Phase 1).

Computes box-per-caption and object-size distributions and decides well-posedness
*before* any GPU run. Had this existed in Part I, the Stage 2 ill-posed RefDrone
target (many boxes per caption → marginal-mean collapse) would have been caught
for free. The gate result is baked onto the dataset as `AuditStats`.

Filled in at Phase 1 startup.
"""

from __future__ import annotations

from typing import Sequence

from grounding.data.schema import AuditStats, GroundingSample


def audit(samples: Sequence[GroundingSample]) -> AuditStats:
    """Compute the distribution summary for a set of raw (pre-filter) samples."""
    raise NotImplementedError("filled in at Phase 1 startup")


def assert_well_posed(stats: AuditStats, *, min_well_posed_fraction: float = 0.95) -> None:
    """Phase-1 gate: raise if the split is not predominantly one-box-per-caption."""
    raise NotImplementedError("filled in at Phase 1 startup")
