"""Evaluation harness — run a backend over a dataset, score via contract (Phase 0).

The single scoring path for the whole project: feed `GroundingSample`s through any
`Backend`, parse with `contract.parse_bbox`, and report the contract metrics
(IoU@0.25 pass-rate, mean IoU, parse_rate, center_std). Because parsing and
metrics come from `grounding.contract`, every number in the thesis is comparable
across HF / GGUF / Jetson and across phases by construction.

Filled in at Phase 0 startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from grounding.data.schema import GroundingSample
from grounding.eval.backends import Backend


@dataclass(frozen=True)
class EvalReport:
    """Contract-derived metrics for one (backend, dataset) run."""

    backend: str
    n: int
    parse_rate: float
    iou_gate_pass_rate: float  # fraction with IoU ≥ contract.IOU_GATE_THRESHOLD
    mean_iou: float
    center_std: float


def evaluate(backend: Backend, samples: Sequence[GroundingSample],
             *, limit: int | None = None) -> EvalReport:
    """Run `backend` over `samples` and return the contract metrics."""
    raise NotImplementedError("filled in at Phase 0 startup")
