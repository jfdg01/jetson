# Run `20260617T191739Z` — eval

- **Created (UTC):** 2026-06-17T19:17:39.259180+00:00
- **git SHA:** `ae7405fd626870b10ab33f49aa5f7633b15f67d6`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `43e3fa4577ff90e5c701c03a206398875c7e04babd0238ec92caa1f4f6ed0635`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "phase": "2",
  "backend": "hf",
  "model": "Qwen/Qwen2-VL-2B-Instruct",
  "dataset": "refdrone",
  "split": "val",
  "n": 439,
  "resolution_max_side": 1024,
  "device": "cuda",
  "dtype": "bfloat16",
  "note": ""
}
```

## Results

```json
{
  "backend": "hf",
  "n": 439,
  "parse_rate": 0.9179954441913439,
  "iou_gate_pass_rate": 0.30296127562642367,
  "mean_iou": 0.20189011395153666,
  "center_std": 191.9859678045687
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
