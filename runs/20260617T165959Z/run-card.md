# Run `20260617T165959Z` — eval

- **Created (UTC):** 2026-06-17T16:59:59.567323+00:00
- **git SHA:** `86be5ccb60989e775bab2086b05081cd807910d4`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `43e3fa4577ff90e5c701c03a206398875c7e04babd0238ec92caa1f4f6ed0635`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "phase": "0",
  "backend": "hf",
  "model": "HuggingFaceTB/SmolVLM-500M-Instruct",
  "split": "validation",
  "n": 100,
  "device": "cuda",
  "dtype": "bfloat16",
  "note": "Phase-0c.2 spine: SmolVLM-500M BASE zero-shot RefCOCO val seed-42 (HF bf16 reference)"
}
```

## Results

```json
{
  "backend": "hf",
  "n": 100,
  "parse_rate": 0.09,
  "iou_gate_pass_rate": 0.0,
  "mean_iou": 0.004033312975568462,
  "center_std": 61.293386924935014
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
