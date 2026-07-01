# Run `20260701T094830Z` — export

- **Created (UTC):** 2026-07-01T09:48:30.494083+00:00
- **git SHA:** `6d9d3a23f6748eea86039213fd5d77ec94a581fb`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `c85c39dfe299fff25dd94b8a84ffa4ae2a65a3a79146e6efd38c8b51d02f9ad7`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "phase": "4a",
  "kind": "gguf-export",
  "checkpoint": "experiments/2026-06-30-vlm-backbone-bakeoff/runs/qwen2.5-vl-3b/lr0.0002",
  "convert_script": "/tmp/llama.cpp-57fe1f0/convert_hf_to_gguf.py",
  "mmproj": "experiments/2026-06-30-vlm-backbone-bakeoff/runs/qwen2.5-vl-3b/lr0.0002/gguf/mmproj-lr0.0002-f16.gguf",
  "quants": [
    "F16",
    "Q8_0"
  ],
  "outputs": {
    "F16": "experiments/2026-06-30-vlm-backbone-bakeoff/runs/qwen2.5-vl-3b/lr0.0002/gguf/lr0.0002-f16.gguf",
    "Q8_0": "experiments/2026-06-30-vlm-backbone-bakeoff/runs/qwen2.5-vl-3b/lr0.0002/gguf/lr0.0002-q8_0.gguf"
  }
}
```

## Results

```json
{
  "F16": {
    "gguf_path": "experiments/2026-06-30-vlm-backbone-bakeoff/runs/qwen2.5-vl-3b/lr0.0002/gguf/lr0.0002-f16.gguf",
    "iou_gate_pass_rate": NaN,
    "drop_vs_hf_pp": NaN
  },
  "Q8_0": {
    "gguf_path": "experiments/2026-06-30-vlm-backbone-bakeoff/runs/qwen2.5-vl-3b/lr0.0002/gguf/lr0.0002-q8_0.gguf",
    "iou_gate_pass_rate": NaN,
    "drop_vs_hf_pp": NaN
  }
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
