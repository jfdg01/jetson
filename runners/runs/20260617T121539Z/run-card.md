# Run `20260617T121539Z` — eval

- **Created (UTC):** 2026-06-17T12:15:39.608432+00:00
- **git SHA:** `32ec67a53532d5f481456bd39981a519a0ca1506`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `43e3fa4577ff90e5c701c03a206398875c7e04babd0238ec92caa1f4f6ed0635`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "phase": "0",
  "backend": "gguf",
  "model": "./smolvlm_ft3_f16.gguf",
  "split": "validation",
  "n": 100,
  "device": "cuda",
  "dtype": "bfloat16",
  "note": "Phase-0b parity: GGUF F16 vs HF bf16 on smolvlm_ft3, reproduce -23pp gap",
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
  "iou_gate_pass_rate": 0.69,
  "mean_iou": 0.3934580595488633,
  "center_std": 149.70017252565037
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
