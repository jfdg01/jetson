"""Arm B — Qwen2.5-VL-3B-Instruct. Bake-off vs the deployed Qwen2-VL-2B incumbent.

Same vision-arch family as the incumbent (~837 vision tokens at 1024 long-edge,
well under max_seq_len 1280 -> no truncation), so batch/grad-accum mirror the
incumbent (batch 2 / grad_accum 8). One forced deviation: gradient_checkpointing
is ON. At 3B the batch-2 *backward* pass OOM'd by 72 MiB on the 3090's 24 GB
(a forward-only dry-run missed it); checkpointing recomputes activations in the
backward and frees several GB, fitting comfortably at batch 2. Logged confound vs
the 2B incumbent (which trained without it). lr is the swept knob {1e-4,2e-4,4e-4}.
"""

from grounding.train.config import TrainConfig

config = TrainConfig(
    model_id="Qwen/Qwen2.5-VL-3B-Instruct",
    image_size=1024,
    resolution_strategy="resize1024",
    gradient_checkpointing=True,   # 3B batch-2 backward OOMs without it (72 MiB short)
    output_dir="experiments/2026-06-30-vlm-backbone-bakeoff/runs/qwen2.5-vl-3b",
)
