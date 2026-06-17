"""Jetson deployment + Phase C hook (Phase 4b).

Serves the exported GGUF on the Jetson (via `ssh jetson`, llama.cpp) and verifies
the deployed IoU lands within the Phase-0-characterised fidelity budget of the HF
number — closing the loop the design opened. Also exposes the natural-language
command hook (Part-I Phase C) against the live model.

Filled in at Phase 4 startup.
"""

from __future__ import annotations

from grounding.eval.backends import JetsonBackend


def deploy(gguf_path: str, mmproj_path: str) -> JetsonBackend:
    """Push the model to the Jetson and return a ready JetsonBackend handle."""
    raise NotImplementedError("filled in at Phase 4 startup")


def verify_deployment(backend: JetsonBackend, *, hf_iou_gate: float,
                      fidelity_budget_pp: float) -> bool:
    """Gate: deployed IoU within `fidelity_budget_pp` of the HF reference."""
    raise NotImplementedError("filled in at Phase 4 startup")
