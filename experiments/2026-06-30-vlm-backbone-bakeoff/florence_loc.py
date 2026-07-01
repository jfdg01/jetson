"""Arm D (Florence-2) contract bridge: our [0,100] bbox <-> Florence `<loc_N>` tokens.

Florence-2 is detection-*native*: it emits `phrase<loc_x1><loc_y1><loc_x2><loc_y2>`
where each loc bin is a resolution-independent fraction of the image (floor-quantized
to 1000 bins). Decision (README "Open decisions"): score arm D in its NATIVE loc format
and convert to the shared `contract.iou` space, rather than force the foreign terse-int
target on it — the RQ is "which backbone locates best per Jetson-second", and format is
each architecture's native interface, so we evaluate every arm at its strength and compare
on the format-agnostic IoU@0.25. Given up: target-format is no longer a held-constant across
arms (D=loc tokens, A/B/C/E=terse ints).

Because loc bins are fractions, we work entirely in the [0,100] contract space by using
image_size=(100,100) for both render and parse — Florence's native output then lands
directly on `GroundingSample.bbox` (already [0,100] over the original image). The Jetson
export path (TensorRT/ONNX) is a separate, still-unscoped concern.

Run the self-check:  python experiments/2026-06-30-vlm-backbone-bakeoff/florence_loc.py
"""
from __future__ import annotations

TASK = "<CAPTION_TO_PHRASE_GROUNDING>"
_BINS = 1000
_SIZE = 100.0  # contract space: bbox coords are [0,100] over the original image


def render_target(caption: str, bbox) -> str:
    """GT (caption, [0,100] bbox) -> Florence grounding answer string.

    Floor-quantize each coord to a loc bin exactly as `post_process_generation`
    inverts it (verified round-trip in the self-check below).
    """
    def q(c: float) -> int:
        return max(0, min(_BINS - 1, int(c / _SIZE * _BINS)))
    x1, y1, x2, y2 = bbox
    return f"{caption}<loc_{q(x1)}><loc_{q(y1)}><loc_{q(x2)}><loc_{q(y2)}>"


def parse_bbox(processor, text: str):
    """Florence generation text -> first [0,100] bbox, or None if none parsed.

    Uses the processor's own `post_process_generation` (don't reimplement the bin
    math) with image_size=(100,100) so the returned coords are already contract-space.
    """
    out = processor.post_process_generation(text, task=TASK, image_size=(int(_SIZE), int(_SIZE)))
    boxes = out.get(TASK, {}).get("bboxes") or []
    if not boxes:
        return None
    x1, y1, x2, y2 = boxes[0]
    return (x1, y1, x2, y2)


def _selfcheck():
    # ponytail: the one runnable check — the coord round-trip is the only piece
    # testable without a GPU, and the trickiest to get right (bin quantization).
    from transformers import AutoProcessor

    proc = AutoProcessor.from_pretrained("microsoft/Florence-2-large", trust_remote_code=True)
    for gt in [(10.0, 20.0, 40.0, 60.0), (0.0, 0.0, 100.0, 100.0), (55.5, 12.3, 88.8, 99.1)]:
        s = render_target("car", gt)
        got = parse_bbox(proc, s)
        assert got is not None, f"parse returned None for {s!r}"
        err = max(abs(a - b) for a, b in zip(gt, got))
        # one loc bin at size=100 is 0.1 contract units; allow one bin of slack.
        assert err <= 0.15, f"round-trip drift {err:.3f} for gt={gt} -> {s!r} -> {got}"
        print(f"ok  gt={gt}  ->  {s}  ->  {tuple(round(v, 2) for v in got)}  (err={err:.3f})")
    print("florence_loc round-trip OK")


if __name__ == "__main__":
    _selfcheck()
