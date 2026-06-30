# Run `20260626T014126Z` — train

- **Created (UTC):** 2026-06-26T01:41:26.655295+00:00
- **git SHA:** `599bde2f6cb23d7e595d5e48525110beae6a0f73`  ⚠️ DIRTY TREE
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
  "batch_size": 1,
  "grad_accum": 16,
  "precision": "bf16",
  "seed": 42,
  "eval_n": 200,
  "save_every": 0,
  "output_dir": "./runs/v2/phase3-terse100-1024",
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
      "parse_rate": 0.06,
      "iou_gate_pass_rate": 0.035,
      "mean_iou": 0.48470370950524294,
      "center_std": 79.56435555617291
    },
    {
      "epoch": 2,
      "backend": "hf",
      "n": 200,
      "parse_rate": 0.04,
      "iou_gate_pass_rate": 0.02,
      "mean_iou": 0.3347504617414666,
      "center_std": 92.17977798107378
    },
    {
      "epoch": 3,
      "backend": "hf",
      "n": 200,
      "parse_rate": 0.05,
      "iou_gate_pass_rate": 0.035,
      "mean_iou": 0.5570861522963327,
      "center_std": 85.66367741001534
    }
  ],
  "final": {
    "epoch": 3,
    "backend": "hf",
    "n": 200,
    "parse_rate": 0.05,
    "iou_gate_pass_rate": 0.035,
    "mean_iou": 0.5570861522963327,
    "center_std": 85.66367741001534
  },
  "train_n": 4101,
  "val_n": 439,
  "epochs": 3,
  "effective_batch": 16
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
