"""Single training config (Phase 3) — replaces the per-stage script forks.

One dataclass captures everything that varied across Stages 2/3/4 (model, data
mix, lr/epochs, resolution strategy, LoRA hyperparameters). A run is fully
described by an instance of this, so the trainer is a single loop and experiments
differ only by config — no more diverging forks.

Filled in at Phase 3 startup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from grounding.contract import IMAGE_SIZE, SEED


@dataclass
class LoRAConfig:
    r: int = 16
    alpha: int = 32
    dropout: float = 0.05
    bias: str = "none"
    # text-backbone attention + MLP; vision encoder frozen by default
    target_modules: List[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ])
    freeze_vision: bool = True


@dataclass
class TrainConfig:
    # spine chosen by Phase 0
    model_id: str = "HuggingFaceTB/SmolVLM-500M-Instruct"
    init_from: Optional[str] = None         # warm-start checkpoint (curriculum)
    # data (Phase 1) + resolution (Phase 2)
    train_split: str = "refdrone:train"
    val_split: str = "refdrone:val"
    largest_box_aug: bool = False
    image_size: int = IMAGE_SIZE
    resolution_strategy: str = "resize512"  # see grounding.resolution
    # optimisation
    epochs: int = 3
    lr: float = 1e-4
    batch_size: int = 2
    grad_accum: int = 8
    precision: str = "bf16"
    seed: int = SEED
    eval_n: int = 200
    save_every: int = 500
    output_dir: str = "./runs/v2"
    lora: LoRAConfig = field(default_factory=LoRAConfig)
