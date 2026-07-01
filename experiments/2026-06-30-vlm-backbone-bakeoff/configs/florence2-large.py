"""Arm D - Florence-2-large. Detection-native seq2seq speed-ceiling candidate.

Florence-2 does NOT fit the shared `AutoModelForImageTextToText` LoRA loop: it is
encoder-decoder, has no chat template, loads via `AutoModelForCausalLM(trust_remote_code
=True)`, and speaks native `<loc_N>` tokens (see `florence_loc.py`). It therefore runs
through a SEPARATE driver (`run_florence.py`), not `run_arm.py`. This config only carries
the knobs that driver reads; `target_modules` here documents the intended LoRA surface
(BART-style decoder attention + FFN; the DaViT vision tower stays frozen), but the driver
owns the enc-dec specifics.

Resolution: Florence-2-large is trained at a fixed 768 tile; image_size=768 feeds one
native tile. lr is the swept knob, same {1e-4,2e-4,4e-4} as the other arms.
"""

from grounding.train.config import TrainConfig, LoRAConfig

config = TrainConfig(
    model_id="microsoft/Florence-2-large",
    image_size=768,
    resolution_strategy="resize768",
    output_dir="experiments/2026-06-30-vlm-backbone-bakeoff/runs/florence2-large",
    lora=LoRAConfig(target_modules=[
        "q_proj", "k_proj", "v_proj", "out_proj",  # BART decoder attention
        "fc1", "fc2",                                # BART decoder FFN
    ]),
)
