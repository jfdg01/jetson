# Run `20260617T223958Z` — export

- **Created (UTC):** 2026-06-17T22:39:58.639360+00:00
- **git SHA:** `bf35575678b485132553876d102bbdcefdc6539d`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `43e3fa4577ff90e5c701c03a206398875c7e04babd0238ec92caa1f4f6ed0635`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "phase": "4a",
  "kind": "gguf-export",
  "checkpoint": "runs/v2/phase3-refdrone-1024",
  "convert_script": "/tmp/llama.cpp-57fe1f0/convert_hf_to_gguf.py",
  "mmproj": "runs/v2/phase3-refdrone-1024/gguf/mmproj-phase3-refdrone-1024-f16.gguf",
  "quants": [
    "F16",
    "Q8_0"
  ],
  "outputs": {
    "F16": "runs/v2/phase3-refdrone-1024/gguf/phase3-refdrone-1024-f16.gguf",
    "Q8_0": "runs/v2/phase3-refdrone-1024/gguf/phase3-refdrone-1024-q8_0.gguf"
  }
}
```

## Results

```json
{
  "F16": {
    "gguf_path": "runs/v2/phase3-refdrone-1024/gguf/phase3-refdrone-1024-f16.gguf",
    "iou_gate_pass_rate": NaN,
    "drop_vs_hf_pp": NaN
  },
  "Q8_0": {
    "gguf_path": "runs/v2/phase3-refdrone-1024/gguf/phase3-refdrone-1024-q8_0.gguf",
    "iou_gate_pass_rate": NaN,
    "drop_vs_hf_pp": NaN
  }
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
