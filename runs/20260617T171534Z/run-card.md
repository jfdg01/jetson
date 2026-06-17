# Run `20260617T171534Z` — eval

- **Created (UTC):** 2026-06-17T17:15:34.704502+00:00
- **git SHA:** `86be5ccb60989e775bab2086b05081cd807910d4`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `43e3fa4577ff90e5c701c03a206398875c7e04babd0238ec92caa1f4f6ed0635`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "phase": "0",
  "backend": "gguf",
  "model": "./qwen2vl-2b_f16.gguf",
  "split": "validation",
  "n": 100,
  "device": "cuda",
  "dtype": "bfloat16",
  "note": "Phase-0c.2 spine: Qwen2-VL-2B BASE GGUF F16 vs HF, runtime fidelity gap (CPU llama-server, pinned 57fe1f0)",
  "mmproj": "./mmproj-qwen2vl-2b-f16.gguf",
  "ngl": 0
}
```

## Results

```json
{
  "backend": "gguf",
  "n": 100,
  "parse_rate": 0.18,
  "iou_gate_pass_rate": 0.13,
  "mean_iou": 0.5479189151303365,
  "center_std": 198.65111180432262
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
