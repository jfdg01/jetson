"""Backend-agnostic inference interface (Phase 0).

The whole point of v2 is that the SAME grounding skill is measured identically
across runtimes, so the deployment-fidelity gap (HF bf16 85% → GGUF F16 62% →
Q8_0 55%) is a measured quantity, not a post-hoc surprise. Each backend takes an
image + a caption, applies the verbatim `grounding.contract.GROUNDING_PROMPT`,
and returns raw model text; scoring is done once, centrally, by `harness.py`.

Filled in at Phase 0 startup.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Backend(Protocol):
    """One inference runtime behind a uniform call."""

    name: str  # "hf" | "gguf" | "jetson"

    def generate(self, image_path: str, caption: str) -> str:
        """Run the model on one (image, caption) and return raw output text."""
        ...


class HFBackend:
    """HuggingFace transformers backend (bf16 reference; local RTX 3090)."""

    name = "hf"

    def __init__(self, model_path: str, *, device: str = "cuda", dtype: str = "bfloat16"):
        raise NotImplementedError("filled in at Phase 0 startup")

    def generate(self, image_path: str, caption: str) -> str:
        raise NotImplementedError("filled in at Phase 0 startup")


class GGUFBackend:
    """llama.cpp GGUF backend (F16 / Q8_0); exercises the Idefics3 preprocessing path."""

    name = "gguf"

    def __init__(self, model_path: str, mmproj_path: str, *, n_ctx: int = 4096):
        raise NotImplementedError("filled in at Phase 0 startup")

    def generate(self, image_path: str, caption: str) -> str:
        raise NotImplementedError("filled in at Phase 0 startup")


class JetsonBackend:
    """Remote llama.cpp on the Jetson over `ssh jetson` (deployment target)."""

    name = "jetson"

    def __init__(self, remote_model_path: str, remote_mmproj_path: str):
        raise NotImplementedError("filled in at Phase 0 startup")

    def generate(self, image_path: str, caption: str) -> str:
        raise NotImplementedError("filled in at Phase 0 startup")
