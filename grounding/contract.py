"""The shared grounding contract — the single source of truth for v2.

Everything in the grounding pipeline (probe, train, export, Jetson deploy) imports
its prompt, parser, and metric from *here* so they can never drift apart again. In
Part I these were copy-pasted across five scripts (`run_stage2/3/4_finetune.py`,
`run_grounding_probe.py`, `run_phase_c.py`) and silently diverged; v2 forbids that by
construction.

Definitions below are lifted **verbatim** from the validated Part-I trainer
`experiments/legacy/run_stage3_finetune.py` (the run that produced the G2-PASS
RefCOCO checkpoint). Do not retype `GROUNDING_PROMPT` — keep it byte-identical so the
fine-tuned model sees exactly the prompt it was trained on.

This module is **stdlib-only on purpose** (`re`, `statistics`): the contract must be
importable by every backend (HF / GGUF / Jetson) without pulling in torch.
"""

from __future__ import annotations

import re
import statistics as st
from typing import List, Optional, Sequence

# ── constants ───────────────────────────────────────────────────────────────────
IMAGE_SIZE     = 512      # resize long edge before model (coords are normalized, so safe)
COORD_SCALE    = 1000     # normalized coordinate range [0, COORD_SCALE]
SEED           = 42
MAX_NEW_TOKENS = 64       # response cap for grounding eval calls

# The v2 spine, selected by the numbers in Phase 0c (RefCOCO base-vs-base parity:
# Qwen2-VL-2B 15% IoU@0.25 / center_std 162 healthy vs SmolVLM-500M 0% / 61 collapsed,
# and an ~8× smaller HF→GGUF deployment-fidelity gap). Qwen2-VL's native dynamic
# resolution is the built-in lever for binding constraint #2 (the tiny-object ceiling).
# Also used as the base-processor fallback when a merged checkpoint's own processor
# won't load. (Part-I incumbent was HuggingFaceTB/SmolVLM-500M-Instruct.)
MODEL_ID       = "Qwen/Qwen2-VL-2B-Instruct"

# UNIFIED prompt — must match every consumer (probe, train, export, Phase C) verbatim.
# Lifted byte-identical from experiments/legacy/run_stage3_finetune.py.
GROUNDING_PROMPT = (
    'Locate "{target}". Return the bounding box as JSON '
    '{{"bbox": [x1, y1, x2, y2]}} with integer coordinates normalized from 0 to 1000.'
)

# Standing primary gate for aerial grounding (Phase 3). Kept here so the trainer and
# the eval harness agree on the threshold.
IOU_GATE_THRESHOLD = 0.25   # IoU@0.25 ≥ 20% of samples = PASS (see DECISIONS Part II)


# ── coordinate helpers ───────────────────────────────────────────────────────────

def normalize_bbox(bbox_xyxy: Sequence[float], img_w: float, img_h: float,
                   scale: int = COORD_SCALE) -> List[int]:
    """[x1,y1,x2,y2] in pixels → integer coords normalized to [0, scale]."""
    x1, y1, x2, y2 = bbox_xyxy
    nx1 = round(x1 / img_w * scale)
    ny1 = round(y1 / img_h * scale)
    nx2 = round(x2 / img_w * scale)
    ny2 = round(y2 / img_h * scale)
    clamp = lambda v: max(0, min(scale, v))
    return [clamp(nx1), clamp(ny1), clamp(nx2), clamp(ny2)]


# ── output parsing ───────────────────────────────────────────────────────────────

def parse_bbox(text: str) -> Optional[List[int]]:
    """Extract [x1,y1,x2,y2] from model output; return None if unparseable."""
    m = re.search(r'\{[^{}]*"bbox"\s*:\s*\[([^\]]+)\][^{}]*\}', text)
    if m:
        try:
            vals = [float(v.strip()) for v in m.group(1).split(",")]
            if len(vals) == 4:
                return [int(v) for v in vals]
        except ValueError:
            pass
    return None


# ── metrics ──────────────────────────────────────────────────────────────────────

def iou(a: Sequence[float], b: Sequence[float]) -> float:
    """Intersection-over-union of two [x1,y1,x2,y2] boxes (same coordinate space)."""
    ix1 = max(a[0], b[0]); iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2]); iy2 = min(a[3], b[3])
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (a[2]-a[0]) * (a[3]-a[1])
    area_b = (b[2]-b[0]) * (b[3]-b[1])
    return inter / (area_a + area_b - inter)


def center_std(bboxes: Sequence[Sequence[float]]) -> float:
    """Mode-collapse sentinel: mean of the per-axis std of predicted box centers.

    A healthy, input-dependent model spreads its predictions across the image
    (center_std ~211 on Stage 3/4 RefCOCO/RefDrone); a collapsed model emits a near
    constant box and drives this toward zero. Pass the list of *parsed* predicted
    boxes (skip None / unparseable). Returns 0.0 for <2 boxes.
    """
    boxes = [b for b in bboxes if b is not None]
    if len(boxes) < 2:
        return 0.0
    cx = [(b[0] + b[2]) / 2 for b in boxes]
    cy = [(b[1] + b[3]) / 2 for b in boxes]
    return (st.pstdev(cx) + st.pstdev(cy)) / 2
