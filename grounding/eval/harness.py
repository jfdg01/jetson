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
from typing import List, Optional, Sequence

from grounding import contract
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
             *, limit: int | None = None,
             progress_every: int = 0) -> EvalReport:
    """Run `backend` over `samples` and return the contract metrics.

    The single scoring path: backend.generate → `contract.parse_bbox` →
    `contract.iou` against the sample's normalized GT box. `iou_gate_pass_rate`
    and `mean_iou` follow the Part-I convention exactly — the gate fraction is over
    *all* n samples (an unparseable prediction counts as a miss), while mean_iou is
    averaged over the *parsed* predictions only. `center_std` (the mode-collapse
    sentinel) is computed over parsed boxes.
    """
    n = len(samples) if limit is None else min(limit, len(samples))

    parsed = 0
    gate_hits = 0
    total_iou = 0.0
    pred_boxes: List[List[int]] = []

    for i in range(n):
        s = samples[i]
        text = backend.generate(s.image_path, s.caption)
        box: Optional[List[int]] = contract.parse_bbox(text)
        if box is not None:
            parsed += 1
            pred_boxes.append(box)
            iou_val = contract.iou(box, s.bbox)
            total_iou += iou_val
            if iou_val >= contract.IOU_GATE_THRESHOLD:
                gate_hits += 1
        if progress_every and (i + 1) % progress_every == 0:
            print(f"  [{backend.name}] {i + 1}/{n}  "
                  f"parsed={parsed}  gate_hits={gate_hits}", flush=True)

    return EvalReport(
        backend=backend.name,
        n=n,
        parse_rate=parsed / n if n else 0.0,
        iou_gate_pass_rate=gate_hits / n if n else 0.0,
        mean_iou=total_iou / parsed if parsed else 0.0,
        center_std=contract.center_std(pred_boxes),
    )
