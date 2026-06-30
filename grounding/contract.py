"""The shared grounding contract — the single source of truth for v2.

Everything in the grounding pipeline (probe, train, export, Jetson deploy) imports
its prompt, parser, and metric from *here* so they can never drift apart again. In
Part I these were copy-pasted across five scripts (`run_stage2/3/4_finetune.py`,
`run_grounding_probe.py`, `run_phase_c.py`) and silently diverged; v2 forbids that by
construction.

Definitions below are lifted **verbatim** from the validated Part-I trainer
`runners/legacy/run_stage3_finetune.py` (the run that produced the G2-PASS
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
# COORD_SCALE 1000 → 100 (2026-06-26 iter-2): Qwen2-VL tokenizes digit-level, so coord
# *precision* is the dominant decode-token cost (12 digit-tokens at 0–1000 → 8 at 0–100).
# Measured quantization cost: 0% of RefDrone-val boxes (incl. tiny aerial, n=93) drop below
# the 0.25 IoU gate under 0–100 rounding. The dominant token lever, orthogonal to brackets.
COORD_SCALE    = 100      # normalized coordinate range [0, COORD_SCALE]
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
# TERSE format (2026-06-26 iter-2): four space-separated integers at 0–100 precision.
# Iter-1 (bracketless @0–1000) saved only ~3 decode tokens on the Orin: the model reverted
# to its pretrained bracketed-list prior ([x, y, x, y]) and only shed the {"bbox": …}
# wrapper. Iter-2 attacks the dominant cost — digit count (coords now 2-digit) — and keeps
# pushing the bracketless format. See experiments/2026-06-25-terse-output-retrain/.
GROUNDING_PROMPT = (
    'Locate "{target}". Return the bounding box as four space-separated integers '
    'x1 y1 x2 y2, normalized from 0 to 100.'
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
    """Extract [x1,y1,x2,y2] from terse model output; return None if unparseable.

    Terse format = four space-separated integers ("123 456 234 567"). Require *exactly*
    four integers: with no brackets to anchor on, a dropped/extra coordinate would
    otherwise be silent corruption — exactly-4 turns it into an honest parse-fail.
    """
    nums = re.findall(r"-?\d+", text)
    if len(nums) != 4:
        return None
    return [int(n) for n in nums]


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


# ── temporal metric primitives (Part III — object permanence) ─────────────────────
#
# The single-frame metrics above (iou / center_std) answer "where is it in THIS frame".
# Part III scores a *stream*: keep a lock on a moving target across time. These
# primitives are the §6 charter suite (experiments/2026-06-18-part3-charter §6) lifted into
# the one contract so anchor/tracker/eval can never disagree on what "success" means.
#
# Data model — a clip of N frames, each described by parallel per-frame lists:
#   pred[i]    : predicted/tracked box [x1,y1,x2,y2], or None when the tracker has no lock
#   gt[i]      : the target's oracle GT box, or None when the target is not visible
#   visible[i] : bool, target present in frame i (gt is not None ⟺ visible, by convention)
#   locked_id[i]: identity label the tracker is locked onto (any hashable), or None
# Scored ranges differ on purpose (see the T1 writeup): SOT success/precision are over
# *visible* frames (tracking quality while the target exists); oracle-coverage is over
# *all* frames (the closed-loop framing measure carried from Phase C).

# Default precision radius: a centre within 20 px of the oracle counts as "on target".
# 20 px ≈ a small fraction of the 640-wide SITL frame; tune per-clip via the argument.
PRECISION_THRESHOLD_PX = 20.0

# Success-plot threshold sweep (OTB convention: 0.00 → 1.00 step 0.05). The AUC over
# this sweep is the standard single-number SOT success score.
SUCCESS_AUC_THRESHOLDS = tuple(i / 20 for i in range(21))


def center_error(a: Sequence[float], b: Sequence[float]) -> float:
    """Euclidean distance between the centres of two [x1,y1,x2,y2] boxes (px)."""
    acx, acy = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    bcx, bcy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    return ((acx - bcx) ** 2 + (acy - bcy) ** 2) ** 0.5


def sot_success(pred: Sequence[Optional[Sequence[float]]],
                gt: Sequence[Optional[Sequence[float]]],
                threshold: float = IOU_GATE_THRESHOLD) -> float:
    """Fraction of *visible* frames with IoU(pred, gt) ≥ threshold.

    A frame is scored only when gt is not None (target visible). A None prediction on
    a visible frame counts as a miss (IoU 0). Returns 0.0 if no frame is visible.
    """
    scored = [(p, g) for p, g in zip(pred, gt) if g is not None]
    if not scored:
        return 0.0
    hits = sum(1 for p, g in scored if p is not None and iou(p, g) >= threshold)
    return hits / len(scored)


def sot_success_auc(pred: Sequence[Optional[Sequence[float]]],
                    gt: Sequence[Optional[Sequence[float]]],
                    thresholds: Sequence[float] = SUCCESS_AUC_THRESHOLDS) -> float:
    """Mean SOT success over an IoU-threshold sweep — the success-plot AUC."""
    if not thresholds:
        return 0.0
    return sum(sot_success(pred, gt, t) for t in thresholds) / len(thresholds)


def sot_precision(pred: Sequence[Optional[Sequence[float]]],
                  gt: Sequence[Optional[Sequence[float]]],
                  threshold_px: float = PRECISION_THRESHOLD_PX) -> float:
    """Fraction of *visible* frames with centre error ≤ threshold_px.

    Scored over frames where gt is not None; a None prediction counts as a miss.
    Returns 0.0 if no frame is visible.
    """
    scored = [(p, g) for p, g in zip(pred, gt) if g is not None]
    if not scored:
        return 0.0
    hits = sum(1 for p, g in scored
               if p is not None and center_error(p, g) <= threshold_px)
    return hits / len(scored)


def count_id_switches(locked_id: Sequence[object]) -> int:
    """Times the locked identity jumps between consecutive *locked* frames.

    None entries (no lock) are skipped, so a switch is only counted when the tracker
    holds a lock, drops nothing, and the identity differs from the previous lock. This
    is the direct constraint-#2 (object-permanence) failure signal: a memoryless
    tracker that re-locks the wrong object after an occlusion scores ≥1 here.
    """
    switches = 0
    last = None
    for cur in locked_id:
        if cur is None:
            continue
        if last is not None and cur != last:
            switches += 1
        last = cur
    return switches


def identity_purity(locked_id: Sequence[object], target_id: object) -> float:
    """Fraction of *locked* frames where the lock is on the true target.

    Complements count_id_switches: a tracker that steadily locks the WRONG object
    scores 0 switches but ~0 purity; the two numbers together describe the failure.
    Returns 0.0 if the tracker never holds a lock.
    """
    locked = [c for c in locked_id if c is not None]
    if not locked:
        return 0.0
    return sum(1 for c in locked if c == target_id) / len(locked)


def reacquisition_frames(visible: Sequence[bool],
                         correct: Sequence[bool]) -> List[Optional[int]]:
    """Frames from each target reappearance to the first correct re-lock.

    A reappearance is a visibility transition absent→present (and frame 0 if it starts
    visible — the initial acquisition). For each, returns the number of frames until
    the first frame where the target is both visible and correctly locked
    (`correct[i]` True). Returns None for that event if the target leaves the frame
    again before being re-locked (a failed re-acquisition). One list entry per event;
    an empty list means the target never appeared.
    """
    n = len(visible)
    events: List[Optional[int]] = []
    for i in range(n):
        is_reappear = visible[i] and (i == 0 or not visible[i - 1])
        if not is_reappear:
            continue
        delta: Optional[int] = None
        for j in range(i, n):
            if not visible[j]:
                break          # left again before any correct re-lock
            if correct[j]:
                delta = j - i
                break
        events.append(delta)
    return events


def oracle_coverage(pred: Sequence[Optional[Sequence[float]]],
                    gt: Sequence[Optional[Sequence[float]]],
                    threshold: float = IOU_GATE_THRESHOLD) -> float:
    """Fraction of *all* clip frames where the tracked box matches oracle GT ≥ threshold.

    Distinct from sot_success on purpose: the denominator is the whole clip length, so
    this penalises every frame the drone fails to frame the target — including genuine
    out-of-frame windows. This is the Phase-C closed-loop ground-truth metric (which
    read ~0% on a moving target). Returns 0.0 for an empty clip.
    """
    if not gt:
        return 0.0
    covered = sum(1 for p, g in zip(pred, gt)
                  if g is not None and p is not None and iou(p, g) >= threshold)
    return covered / len(gt)


def following_error(pred: Sequence[Optional[Sequence[float]]],
                    gt: Sequence[Optional[Sequence[float]]]) -> Optional[float]:
    """Mean centre offset (px) of the tracked box vs oracle, over co-present frames.

    Only frames where both pred and gt exist are averaged (you cannot measure framing
    error when there is no box). Returns None if no frame has both — the closed-loop
    framing-quality number for T3/T4.
    """
    errs = [center_error(p, g) for p, g in zip(pred, gt)
            if p is not None and g is not None]
    if not errs:
        return None
    return sum(errs) / len(errs)


def track_loss_events(visible: Sequence[bool], correct: Sequence[bool],
                      timeout: int) -> int:
    """Count runs where the target is visible but un-tracked for ≥ `timeout` frames.

    A track-loss event is a maximal run of consecutive frames in which the target is
    visible yet `correct` is False, whose length is ≥ timeout (the LOST_TIMEOUT
    exceedance from the follow stack). Brief, recoverable gaps shorter than the timeout
    are not counted. `timeout` must be ≥ 1.
    """
    if timeout < 1:
        raise ValueError("timeout must be >= 1")
    events = 0
    run = 0
    for vis, ok in zip(visible, correct):
        if vis and not ok:
            run += 1
            if run == timeout:        # crossed the threshold exactly once per run
                events += 1
        else:
            run = 0
    return events
