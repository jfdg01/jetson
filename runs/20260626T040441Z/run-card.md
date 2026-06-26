# Run `20260626T040441Z` — eval

- **Created (UTC):** 2026-06-26T04:04:41.435873+00:00
- **git SHA:** `d806ed10e5a93b8951889cafeb39bae0ddcea03c`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `c85c39dfe299fff25dd94b8a84ffa4ae2a65a3a79146e6efd38c8b51d02f9ad7`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "backend": "jetson",
  "dataset": "refdrone",
  "model": "/home/jfdg/grounding/phase3-terse100eos-1024-q8_0.gguf",
  "split": "val",
  "n": 0,
  "max_side": 1024,
  "device": "cuda",
  "dtype": "bfloat16",
  "note": "",
  "mmproj": "/home/jfdg/grounding/mmproj-phase3-terse100eos-1024-f16.gguf",
  "ngl": 0
}
```

## Results

```json
{
  "backend": "jetson",
  "n": 439,
  "parse_rate": 1.0,
  "iou_gate_pass_rate": 0.6309794988610479,
  "mean_iou": 0.47674662086288583,
  "center_std": 21.888046983888387
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
