"""HF → GGUF export with fidelity disambiguation (Phase 4a).

Converts a merged HF checkpoint to GGUF and, by DEFAULT, runs the Phase-0 parity
harness on F16 and Q8_0 before declaring success — so the Part-I confound (a −23pp
runtime/preprocessing loss that was mistaken for, and stacked on top of, a −7pp
quant loss) is surfaced as a gate, never discovered after deployment. The mmproj
is reused unchanged.

Filled in at Phase 4 startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ExportResult:
    gguf_path: str
    mmproj_path: str
    quant: str          # "F16" | "Q8_0"
    iou_gate_pass_rate: float
    drop_vs_hf_pp: float  # fidelity loss vs the HF reference


def export(checkpoint: str, *, quants: List[str] = ["F16", "Q8_0"],
           run_fidelity_gate: bool = True) -> List[ExportResult]:
    """Export to GGUF at each quant; gate each against the HF reference."""
    raise NotImplementedError("filled in at Phase 4 startup")
