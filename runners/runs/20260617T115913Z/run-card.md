# Run `20260617T115913Z` — eval

- **Created (UTC):** 2026-06-17T11:59:13.563600+00:00
- **git SHA:** `3a3352cb78970ca7b9f0a8d1c48d2af65b0bbe0f`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `43e3fa4577ff90e5c701c03a206398875c7e04babd0238ec92caa1f4f6ed0635`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "phase": "0",
  "backend": "hf",
  "model": "./smolvlm_ft3",
  "split": "validation",
  "n": 100,
  "device": "cuda",
  "dtype": "bfloat16",
  "note": "Phase-0 harness self-check: reproduce Part-I in-domain IoU on smolvlm_ft3"
}
```

## Results

```json
{
  "backend": "hf",
  "n": 100,
  "parse_rate": 1.0,
  "iou_gate_pass_rate": 0.85,
  "mean_iou": 0.5665358033459382,
  "center_std": 187.76222968193937
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
