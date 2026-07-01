# Run `20260701T214139Z` — train

- **Created (UTC):** 2026-07-01T21:41:39.463588+00:00
- **git SHA:** `6d9d3a23f6748eea86039213fd5d77ec94a581fb`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `fef59a3713a47182a9219abfa5c10bc85694e2a766a1d4d94eef30580058db80`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "model_id": "HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
  "init_from": null,
  "train_split": "refdrone:train",
  "val_split": "refdrone:val",
  "largest_box_aug": false,
  "image_size": 512,
  "resolution_strategy": "resize512",
  "epochs": 3,
  "lr": 0.0001,
  "batch_size": 2,
  "grad_accum": 8,
  "max_seq_len": 1280,
  "gradient_checkpointing": false,
  "precision": "bf16",
  "seed": 42,
  "eval_n": 200,
  "save_every": 0,
  "output_dir": "experiments/2026-06-30-vlm-backbone-bakeoff/runs/smolvlm2-500m/lr0.0001",
  "lora": {
    "r": 16,
    "alpha": 32,
    "dropout": 0.05,
    "bias": "none",
    "target_modules": [
      "q_proj",
      "k_proj",
      "v_proj",
      "o_proj",
      "gate_proj",
      "up_proj",
      "down_proj"
    ],
    "freeze_vision": true
  }
}
```

## Results

```json
{
  "eval_history": [
    {
      "epoch": 1,
      "backend": "hf",
      "n": 200,
      "parse_rate": 1.0,
      "iou_gate_pass_rate": 0.05,
      "mean_iou": 0.021614102242456825,
      "center_std": 12.658626720374901
    },
    {
      "epoch": 2,
      "backend": "hf",
      "n": 200,
      "parse_rate": 1.0,
      "iou_gate_pass_rate": 0.05,
      "mean_iou": 0.03470163560553733,
      "center_std": 18.59097650835242
    },
    {
      "epoch": 3,
      "backend": "hf",
      "n": 200,
      "parse_rate": 1.0,
      "iou_gate_pass_rate": 0.055,
      "mean_iou": 0.03792351644212021,
      "center_std": 18.531101607290186
    }
  ],
  "final": {
    "epoch": 3,
    "backend": "hf",
    "n": 200,
    "parse_rate": 1.0,
    "iou_gate_pass_rate": 0.055,
    "mean_iou": 0.03792351644212021,
    "center_std": 18.531101607290186
  },
  "train_n": 4101,
  "val_n": 439,
  "epochs": 3,
  "effective_batch": 16
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
