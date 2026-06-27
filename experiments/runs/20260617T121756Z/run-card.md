# Run `20260617T121756Z` — eval

- **Created (UTC):** 2026-06-17T12:17:56.230816+00:00
- **git SHA:** `32ec67a53532d5f481456bd39981a519a0ca1506`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `43e3fa4577ff90e5c701c03a206398875c7e04babd0238ec92caa1f4f6ed0635`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "phase": "0",
  "backend": "gguf",
  "model": "./smolvlm_ft3_q8_0.gguf",
  "split": "validation",
  "n": 100,
  "device": "cuda",
  "dtype": "bfloat16",
  "note": "Phase-0b parity: GGUF Q8_0 vs F16 on smolvlm_ft3, quant gap arm",
  "mmproj": "./mmproj-SmolVLM-500M-Instruct-f16.gguf",
  "ngl": 0
}
```

## Results

```json
{
  "backend": "gguf",
  "n": 100,
  "parse_rate": 1.0,
  "iou_gate_pass_rate": 0.67,
  "mean_iou": 0.3888639370400005,
  "center_std": 148.0144977219823
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
