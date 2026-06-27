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

from grounding.contract import MODEL_ID, SEED


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
    # spine chosen by Phase 0c (Qwen2-VL-2B, see grounding.contract.MODEL_ID)
    model_id: str = MODEL_ID
    init_from: Optional[str] = None         # warm-start checkpoint (curriculum)
    # data (Phase 1) + resolution (Phase 2)
    train_split: str = "refdrone:train"
    val_split: str = "refdrone:val"
    # Phase-1 lever: expand the budget to the largest-box-per-caption referent
    # (4101 well-posed -> ~12339 samples). Off by default; flip if the well-posed
    # run misses the gate. See results/2026-06-16-phase1-dataset-audit.
    largest_box_aug: bool = False
    # Phase-2 lever: input long-edge resize. Set to the resolution chosen by the
    # Phase-2 ladder; both the collate transform and the in-loop eval use it.
    image_size: int = 1024                   # Phase-2 chosen (elbow; clears 20% gate zero-shot)
    resolution_strategy: str = "resize1024"  # descriptive tag; see grounding.resolution
    # optimisation — lr=2e-4 is the validated Stage-3 RefCOCO PASS value.
    epochs: int = 3
    lr: float = 2e-4
    batch_size: int = 2
    grad_accum: int = 8
    precision: str = "bf16"
    seed: int = SEED
    eval_n: int = 200
    save_every: int = 0                      # mid-epoch adapter save (0 = epoch-end only)
    output_dir: str = "./experiments/runs/v2"
    lora: LoRAConfig = field(default_factory=LoRAConfig)
