"""Arm C — PaliGemma2-3B (pt-448). Bake-off vs the deployed Qwen2-VL-2B incumbent.

Forced harness deviation (pre-registered, logged confound): PaliGemma has NO chat
template. The trainer/eval detect this (`chat_template is None`) and switch to the
native path -- plain prompt, target passed as `suffix=` so the processor builds the
masked `labels` itself (prefix+image -100, suffix supervised, <eos> appended), and
plain-prompt generation at eval. Text backbone is Gemma2, whose module names match
the shared LoRA targets (q/k/v/o/gate/up/down_proj) -- vision tower untouched.

Fixed 448x448 square input: the processor squishes to square regardless, but coords
are normalized [0,100] to the ORIGINAL image (scale-invariant), so the squish adds
no coordinate confound. image_size=448 feeds the native resolution; ~1042 tokens per
sample, well under max_seq_len 1280. gradient_checkpointing ON as a 3B safety margin
on the 3090's 24 GB (arm B's 3B backward OOM'd without it). lr is the swept knob.

Gated model: launcher exports HF_TOKEN from .hugging-face-token.
"""

from grounding.train.config import TrainConfig

config = TrainConfig(
    model_id="google/paligemma2-3b-pt-448",
    image_size=448,
    resolution_strategy="resize448",
    gradient_checkpointing=True,   # 3B safety margin on 24 GB
    output_dir="experiments/2026-06-30-vlm-backbone-bakeoff/runs/paligemma2-3b",
)
