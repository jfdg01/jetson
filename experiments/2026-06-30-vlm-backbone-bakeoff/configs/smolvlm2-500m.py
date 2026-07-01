"""Arm E — SmolVLM2-500M-Video-Instruct. Speed-floor anchor vs the Qwen2-VL-2B incumbent.

No harness deviation: SmolVLMProcessor HAS a chat template, so the shared chat-template
path (same as the Qwen incumbent / arm B) applies unchanged. Text backbone is Llama, so
the default LoRA targets (q/k/v/o_proj, gate/up/down_proj) match and the SigLIP vision
tower stays frozen by construction.

Resolution: pre-registration said "384-tile"; the actual SmolVLM2-500M checkpoint's
image processor uses a 512 native tile (max_image_size.longest_edge=512), so image_size
=512 feeds one native tile (few vision tokens -> the intended speed floor). Logged
correction; token count / fit to be confirmed by the dry-run before the sweep launches.
gradient_checkpointing left OFF (500M fits batch 2 comfortably); revisit if the dry-run
OOMs (it won't at this scale). lr is the swept knob.
"""

from grounding.train.config import TrainConfig

config = TrainConfig(
    model_id="HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
    image_size=512,
    resolution_strategy="resize512",
    output_dir="experiments/2026-06-30-vlm-backbone-bakeoff/runs/smolvlm2-500m",
)
