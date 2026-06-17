"""Config-driven LoRA training loop with in-loop eval (Phase 3).

One loop for all v2 runs, driven entirely by `TrainConfig`. Uses `grounding.data`
for samples, `grounding.resolution` for the input transform, and
`grounding.eval.harness` for the per-epoch contract metrics — so training-time and
eval-time scoring are identical. Gate (standing target): aerial IoU@0.25 ≥ 20%,
center_std non-degenerate, parse_rate ≥ 90%.

Filled in at Phase 3 startup.
"""

from __future__ import annotations

from grounding.train.config import TrainConfig


def train(config: TrainConfig) -> str:
    """Run a full LoRA fine-tune; return the merged-checkpoint output path."""
    raise NotImplementedError("filled in at Phase 3 startup")


def evaluate_only(checkpoint: str, config: TrainConfig):
    """Re-evaluate a merged checkpoint with the same harness used in-loop."""
    raise NotImplementedError("filled in at Phase 3 startup")
