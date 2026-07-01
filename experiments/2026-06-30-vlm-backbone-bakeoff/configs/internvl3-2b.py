"""Arm A — InternVL3-2B. One TrainConfig; the only deltas from the Qwen2-VL-2B
baseline are the backbone id and per-arch resolution (logged confounds, see README).

- model_id `OpenGVLab/InternVL3-2B-hf`: the transformers-native checkpoint
  (registered as `internvl` under AutoModelForImageTextToText in tf 4.57), so it
  loads through the same generic harness as Qwen with no trust_remote_code.
- LLM is Qwen2-based, so the default LoRA target names (q/k/v/o_proj, gate/up/
  down_proj) match the language tower and naturally skip the InternViT vision
  tower (attn.qkv / mlp.fc1/fc2) -> freeze_vision holds by construction.
- image_size 1024 long-edge: same input budget as the Qwen baseline; InternVL's
  processor then dynamic-tiles at 448. Per-arm deviation, logged not controlled.

lr is swept by run_arm.py ({1e-4,2e-4,4e-4}); the value here is just the default.
"""

from grounding.train.config import TrainConfig

config = TrainConfig(
    model_id="OpenGVLab/InternVL3-2B-hf",
    image_size=1024,
    # InternVL dynamic-tiles @1024 -> measured 817..3385 tokens (median ~2100 over
    # 30 train samples, 2026-06-30); 1280 would truncate. 4096 covers the max + text.
    max_seq_len=4096,
    # ~2-3k-token sequences OOM at batch 2 on 24 GB; checkpointing + batch 1 /
    # grad-accum 16 fits and keeps the effective batch at 16 (matched to baseline).
    gradient_checkpointing=True,
    batch_size=1,
    grad_accum=16,
    resolution_strategy="resize1024+internvl-tile448",
    output_dir="experiments/2026-06-30-vlm-backbone-bakeoff/runs/internvl3-2b",
)
