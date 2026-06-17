"""Backend-fidelity parity report (Phase 0) — the −23pp probe.

Runs the *same* checkpoint and the *same* eval set through HF, GGUF (F16 and Q8_0),
and the Jetson, then diffs the contract metrics to attribute the drop to
preprocessing/runtime vs quantization. This is the de-risk-before-GPU instrument:
Phase 0 self-checks it against the known Part-I gap on `smolvlm_ft3`, then uses it
to pick the v2 spine (SmolVLM-500M vs a grounding-native candidate) BY THE NUMBERS.

Filled in at Phase 0 startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from grounding.data.schema import GroundingSample
from grounding.eval.harness import EvalReport


@dataclass(frozen=True)
class ParityReport:
    """Side-by-side fidelity across backends for one checkpoint."""

    checkpoint: str
    per_backend: List[EvalReport]
    runtime_gap_pp: float  # HF → GGUF-F16 drop (preprocessing/runtime)
    quant_gap_pp: float    # GGUF-F16 → Q8_0 drop (quantization)


def run_parity(checkpoint: str, samples: Sequence[GroundingSample]) -> ParityReport:
    """Evaluate one checkpoint across all available backends and attribute the gap."""
    raise NotImplementedError("filled in at Phase 0 startup")
