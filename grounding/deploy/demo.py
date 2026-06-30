"""Interactive single-image demo of the deployed aerial-grounding skill.

Boots the Phase-4 GGUF on the Jetson (Q8_0 by default), runs ONE (image, phrase)
through the exact same contract path the eval used (`GROUNDING_PROMPT` verbatim,
`parse_bbox`), draws the predicted box on the image, and saves an annotated PNG.

This is the "show me a box" entry point — the eval runner (`grounding.eval.run`)
scores the whole dataset; this visualises one query for a demo.

    source .venv-ft/bin/activate
    python -m grounding.deploy.demo \
        --image path/to/aerial.jpg \
        --caption "the white car near the building" \
        --out /tmp/demo.png

`--quant {q8_0,f16}` picks the deployed artifact (default q8_0, the 1.65 GB
deployment skill). The Jetson must be reachable via `ssh jetson` and hold the
GGUFs under /home/jfdg/grounding (they were pushed in Phase 4).
"""

from __future__ import annotations

import argparse
import sys

from PIL import Image, ImageDraw, ImageFont

from grounding.contract import parse_bbox, COORD_SCALE
from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
from grounding.eval.backends import JetsonBackend

# Phase-4 deployed artifact names on the device (see experiments/2026-06-18-phase4-*).
# terse iter-2b anchor (2026-06-26): bare 0–100 ints, Orin Q8_0 63.1% (> JSON 62.6%),
# decode −45%. Must match the terse GROUNDING_PROMPT in contract.py.
_REMOTE_MODELS = {
    "q8_0": "phase3-terse100eos-1024-q8_0.gguf",
    "f16": "phase3-terse100eos-1024-f16.gguf",
}
_REMOTE_MMPROJ = "mmproj-phase3-terse100eos-1024-f16.gguf"  # bit-equiv to base; serves both
_TRAIN_MAX_SIDE = 1024  # the resolution the Phase-3 checkpoint was trained/evaluated under

# Demo presets — real RefDrone val (image, caption) pairs spanning target sizes, so a
# live demo is one click instead of file-hunting. Images ship in the repo. Captions are
# the dataset's own referring expressions; not pre-scored — the demo shows the live box.
_VAL = "data/VisDrone2019-DET/images/val"
PRESETS = {
    "motorbike-small": (f"{_VAL}/0000242_04116_d_0000013.jpg",
                        "The white motorbike is near the right side of the road."),
    "bus-midlane":     (f"{_VAL}/0000199_01269_d_0000166.jpg",
                        "The white bus is traveling in the middle lane."),
    "bus-intersection": (f"{_VAL}/0000291_01001_d_0000873.jpg",
                        "The green bus is prominently located at the center of the intersection."),
    "pedestrians-red": (f"{_VAL}/0000330_01001_d_0000805.jpg",
                        "The pedestrians in red walk near the center median."),
    "car-large":       (f"{_VAL}/0000103_00502_d_0000027.jpg",
                        "The white car parks on the paved area."),
}


def _draw_box(image_path: str, box_norm: list[int], caption: str, out_path: str) -> None:
    """Draw a normalized [x1,y1,x2,y2] (0..COORD_SCALE) box onto the image and save."""
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    x1, y1, x2, y2 = (
        box_norm[0] / COORD_SCALE * w,
        box_norm[1] / COORD_SCALE * h,
        box_norm[2] / COORD_SCALE * w,
        box_norm[3] / COORD_SCALE * h,
    )
    draw = ImageDraw.Draw(img)
    line_w = max(2, round(min(w, h) / 200))
    draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 0), width=line_w)

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(14, round(min(w, h) / 40)))
    except OSError:
        font = ImageFont.load_default()
    label = caption if len(caption) <= 60 else caption[:57] + "..."
    ty = max(0, y1 - (line_w + 18))
    draw.rectangle([x1, ty, x1 + 9 * len(label), ty + 18], fill=(255, 0, 0))
    draw.text((x1 + 2, ty), label, fill=(255, 255, 255), font=font)
    img.save(out_path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preset", choices=list(PRESETS),
                    help="use a bundled RefDrone (image, caption) preset instead of --image/--caption")
    ap.add_argument("--image", help="local image path")
    ap.add_argument("--caption", help="referring phrase to ground")
    ap.add_argument("--out", default="/tmp/grounding-demo.png", help="annotated PNG output")
    ap.add_argument("--quant", choices=list(_REMOTE_MODELS), default="q8_0")
    ap.add_argument("--remote-dir", default=_DEFAULT_REMOTE_DIR)
    ap.add_argument("--ssh-host", default="jetson")
    ap.add_argument("--max-side", type=int, default=_TRAIN_MAX_SIDE)
    args = ap.parse_args(argv)

    if args.preset:
        args.image, args.caption = PRESETS[args.preset]
    if not args.image or not args.caption:
        ap.error("need --preset, or both --image and --caption")

    remote_model = f"{args.remote_dir}/{_REMOTE_MODELS[args.quant]}"
    remote_mmproj = f"{args.remote_dir}/{_REMOTE_MMPROJ}"

    print(f"[demo] booting Jetson {args.quant} server (this takes a few seconds)...",
          flush=True)
    with JetsonBackend(remote_model, remote_mmproj,
                       ssh_host=args.ssh_host, max_side=args.max_side) as be:
        raw = be.generate(args.image, args.caption)

    print(f"[demo] raw model output: {raw!r}", flush=True)
    box = parse_bbox(raw)
    if box is None:
        print("[demo] could not parse a bounding box from the output.", file=sys.stderr)
        return 1

    print(f"[demo] box (normalized 0..{COORD_SCALE}): {box}", flush=True)
    _draw_box(args.image, box, args.caption, args.out)
    print(f"[demo] annotated image -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
