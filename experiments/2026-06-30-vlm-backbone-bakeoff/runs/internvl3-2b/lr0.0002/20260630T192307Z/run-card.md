# Run `20260630T192307Z` — train

- **Created (UTC):** 2026-06-30T19:23:07.840348+00:00
- **git SHA:** `6d9d3a23f6748eea86039213fd5d77ec94a581fb`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `c85c39dfe299fff25dd94b8a84ffa4ae2a65a3a79146e6efd38c8b51d02f9ad7`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "model_id": "OpenGVLab/InternVL3-2B-hf",
  "init_from": null,
  "train_split": "refdrone:train",
  "val_split": "refdrone:val",
  "largest_box_aug": false,
  "image_size": 1024,
  "resolution_strategy": "resize1024+internvl-tile448",
  "epochs": 3,
  "lr": 0.0002,
  "batch_size": 1,
  "grad_accum": 16,
  "max_seq_len": 4096,
  "gradient_checkpointing": true,
  "precision": "bf16",
  "seed": 42,
  "eval_n": 200,
  "save_every": 0,
  "output_dir": "experiments/2026-06-30-vlm-backbone-bakeoff/runs/internvl3-2b/lr0.0002",
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
      "iou_gate_pass_rate": 0.275,
      "mean_iou": 0.1599209242062152,
      "center_std": 24.54863850759571
    },
    {
      "epoch": 2,
      "backend": "hf",
      "n": 200,
      "parse_rate": 1.0,
      "iou_gate_pass_rate": 0.365,
      "mean_iou": 0.2392733455881883,
      "center_std": 21.646319723622078
    },
    {
      "epoch": 3,
      "backend": "hf",
      "n": 200,
      "parse_rate": 1.0,
      "iou_gate_pass_rate": 0.42,
      "mean_iou": 0.2618859976703615,
      "center_std": 22.53025256090754
    }
  ],
  "final": {
    "epoch": 3,
    "backend": "hf",
    "n": 200,
    "parse_rate": 1.0,
    "iou_gate_pass_rate": 0.42,
    "mean_iou": 0.2618859976703615,
    "center_std": 22.53025256090754
  },
  "train_n": 4101,
  "val_n": 439,
  "epochs": 3,
  "effective_batch": 16
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
