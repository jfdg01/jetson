# Run `20260625T222753Z` — train

- **Created (UTC):** 2026-06-25T22:27:53.629716+00:00
- **git SHA:** `0b936f5197cc3b4a5c52edaf01e596ad387ebd43`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `c85c39dfe299fff25dd94b8a84ffa4ae2a65a3a79146e6efd38c8b51d02f9ad7`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "model_id": "Qwen/Qwen2-VL-2B-Instruct",
  "init_from": null,
  "train_split": "refdrone:train",
  "val_split": "refdrone:val",
  "largest_box_aug": false,
  "image_size": 1024,
  "resolution_strategy": "resize1024",
  "epochs": 3,
  "lr": 0.0002,
  "batch_size": 2,
  "grad_accum": 8,
  "precision": "bf16",
  "seed": 42,
  "eval_n": 200,
  "save_every": 0,
  "output_dir": "./runs/v2/phase3-terse-1024",
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
      "parse_rate": 0.62,
      "iou_gate_pass_rate": 0.4,
      "mean_iou": 0.48382679268449813,
      "center_std": 239.18850183960404
    },
    {
      "epoch": 2,
      "backend": "hf",
      "n": 200,
      "parse_rate": 0.835,
      "iou_gate_pass_rate": 0.56,
      "mean_iou": 0.5178879190180756,
      "center_std": 237.28378544226857
    },
    {
      "epoch": 3,
      "backend": "hf",
      "n": 200,
      "parse_rate": 0.91,
      "iou_gate_pass_rate": 0.605,
      "mean_iou": 0.5048984738238266,
      "center_std": 234.06670132351798
    }
  ],
  "final": {
    "epoch": 3,
    "backend": "hf",
    "n": 200,
    "parse_rate": 0.91,
    "iou_gate_pass_rate": 0.605,
    "mean_iou": 0.5048984738238266,
    "center_std": 234.06670132351798
  },
  "train_n": 4101,
  "val_n": 439,
  "epochs": 3,
  "effective_batch": 16
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
