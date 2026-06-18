# Run `20260618T001147Z` — eval

- **Created (UTC):** 2026-06-18T00:11:47.582583+00:00
- **git SHA:** `bf35575678b485132553876d102bbdcefdc6539d`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `43e3fa4577ff90e5c701c03a206398875c7e04babd0238ec92caa1f4f6ed0635`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "backend": "jetson",
  "dataset": "refdrone",
  "model": "/home/jfdg/grounding/phase3-refdrone-1024-q8_0.gguf",
  "split": "val",
  "n": 0,
  "max_side": 1024,
  "device": "cuda",
  "dtype": "bfloat16",
  "note": "phase4 jetson Q8_0 deploy gate (15W, clocks locked, single-slot no-cache)",
  "mmproj": "/home/jfdg/grounding/mmproj-phase3-refdrone-1024-f16.gguf",
  "ngl": 0
}
```

## Results

```json
{
  "backend": "jetson",
  "n": 439,
  "parse_rate": 1.0,
  "iou_gate_pass_rate": 0.6264236902050114,
  "mean_iou": 0.46839149469763913,
  "center_std": 217.40809818624683
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
