"""P5.4 DESIGN-TIME pilot (Fable, pre-registration provenance — NOT the matrix).

Motivation: the first smoke test of vanilla ReCLIP IPS (crop + blur sigma=100)
on the easiest real scene (car9:300, silver vs black) mis-selected the *silver
target* for "the black car" at primary prob 0.963 — CLIP is size/quality-biased
toward the larger, sharper crop (37x54 px vs 23x19 px). UAV123 aerial crops are
16-100 px, far below the RefCOCO object sizes ReCLIP was validated on, so the
scoring variant must be picked BEFORE pre-registering the verdict.

This pilot scores 4 variants on the deterministic cand_at_prompt boxes recorded
in the P5.3 runs (idle_catchup_multi is non-realtime and deterministic, so these
are exactly the boxes the P5.4 matrix will produce) for 3 of the 5 frozen
scenes x both captions = 6 selection outcomes per variant:

  A ips      : ReCLIP crop + blur(sigma=100) sum            (baseline)
  B crop     : crop-only
  C ctx      : square context window (2.5x box side, min 64 px) LANCZOS-
               upscaled to 336 — equalises object scale across candidates
  D circle   : red ellipse (the Shtedritski et al. ICCV 2023 visual prompt)
               drawn on the FULL frame — shared image scale, kept context
  E circlectx: red ellipse drawn, then the C context window around it

Selection = argmax over candidates of the variant's image-text logit
(ViT-L/14, template "a photo of {caption}"); ViT-B/32 recorded too.
The pilot picks the PRIMARY variant for the P5.4 verdict (see README:
"Design-time pilot" section discloses this and the bias it introduces).

    .venv-ft/bin/python experiments/2026-07-14-crop-select/pilot_variants.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from select_p54 import (  # noqa: E402
    ClipScorer, clamp_box, ctx_window, isolate_blur, isolate_crop, red_circle,
)

P53_RUNS = REPO / "experiments" / "2026-07-14-multi-candidate-select" / "runs"
DATA = (REPO / "experiments" / "2026-07-03-real-video-replay" / "data"
        / "UAV123" / "data_seq" / "UAV123")

PILOT = [  # (clip, f0, target_caption, distractor_caption)
    ("car9", 300, "the silver car", "the black car"),
    ("car10", 240, "the white car", "the black car"),
    ("car3", 200, "the red car", "the white car"),
]


def variant_images(frame, cbox):
    """name -> list of BGR images whose logits are SUMMED for that variant."""
    blurred = cv2.GaussianBlur(frame, (0, 0), 100.0)
    circ = red_circle(frame, cbox)
    return {
        "ips": [isolate_crop(frame, cbox),
                isolate_blur(frame, cbox, blurred=blurred)],
        "crop": [isolate_crop(frame, cbox)],
        "ctx": [ctx_window(frame, cbox)],
        "circle": [circ],
        "circlectx": [ctx_window(circ, cbox)],
    }


def main() -> None:
    sc = ClipScorer()
    tally = {}   # (variant, model) -> [correct, total]
    for clip, f0, cap_t, cap_d in PILOT:
        r = json.loads((P53_RUNS / f"WSEL_{clip}_{f0}" / "results.json")
                       .read_text())
        cand = {k: tuple(v) for k, v in r["meta"]["cand_at_prompt"].items()}
        prompt = r["meta"]["prompt_frame"]
        frame = cv2.imread(str(DATA / clip / f"{prompt + 1:06d}.jpg"))
        cboxes = {k: clamp_box(b, frame.shape) for k, b in cand.items()}
        imgs = {k: variant_images(frame, cb) for k, cb in cboxes.items()}
        for caption, want in ((cap_t, "target"), (cap_d, "distractor")):
            text = f"a photo of {caption}"
            for var in next(iter(imgs.values())):
                for tag in sc.models:
                    fn = sc._embed_fn(tag)
                    scores = {k: sum(fn([cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
                                         for im in imgs[k][var]], text))
                              for k in cboxes}
                    pick = max(scores, key=scores.get)
                    key = (var, tag)
                    c, t = tally.get(key, (0, 0))
                    tally[key] = (c + (pick == want), t + 1)
                    print(f"{clip}:{f0} [{var}/{tag}] '{caption}' -> {pick} "
                          f"({'OK' if pick == want else 'X'}) "
                          f"{ {k: round(v, 2) for k, v in scores.items()} }")
    print("\n=== pilot tally (correct/6) ===")
    for (var, tag), (c, t) in sorted(tally.items()):
        print(f"{var:10s} {tag:10s} {c}/{t}")


if __name__ == "__main__":
    main()
