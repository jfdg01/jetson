"""Resolution strategies (Phase 2) — confronting the tiny-object ceiling head-on.

Aerial targets are 5–30 px and shrink to 2–11 px after the 512 long-edge resize
through a frozen SigLIP encoder — a hard cap on achievable IoU that Part I never
addressed explicitly. v2 makes the input transform a pre-registered, measurable
variable: each strategy is a callable (image, bbox) → (transformed image, mapped
bbox), evaluated on the Phase-0 harness *without training* before one is chosen.

Filled in at Phase 2 startup.
"""

from __future__ import annotations

from typing import List, Protocol, Sequence, Tuple


class ResolutionStrategy(Protocol):
    """Transform an image (and remap its box) prior to the model."""

    name: str

    def apply(self, image_path: str, bbox: Sequence[int]) -> Tuple[object, List[int]]:
        """Return (transformed image, remapped 0–1000 bbox)."""
        ...


def resize512(image_path: str, bbox: Sequence[int]) -> Tuple[object, List[int]]:
    """Baseline: long-edge resize to IMAGE_SIZE (the Part-I behaviour)."""
    raise NotImplementedError("filled in at Phase 2 startup")


def tile(image_path: str, bbox: Sequence[int]) -> Tuple[object, List[int]]:
    """Tile/crop the image so small objects keep more pixels through the encoder."""
    raise NotImplementedError("filled in at Phase 2 startup")


def upscale(image_path: str, bbox: Sequence[int]) -> Tuple[object, List[int]]:
    """Feed a higher-resolution input than 512 (encoder budget permitting)."""
    raise NotImplementedError("filled in at Phase 2 startup")
