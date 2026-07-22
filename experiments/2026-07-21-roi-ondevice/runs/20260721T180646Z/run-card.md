# Run `20260721T180646Z` — eval

- **Created (UTC):** 2026-07-21T18:06:46.682559+00:00
- **git SHA:** `95228e21de1b85b3beb192b56fbf643edf08e2a6`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `4f32a323cde99d3ff579e9302196948573e04c60d97f64e175cf39ef0a512464`
- **python / platform:** 3.12.10 / Linux-7.0.0-28-generic-x86_64-with-glibc2.39

## Config

```json
{
  "experiment": "r14-roi-ondevice",
  "backend": "jetson",
  "dataset": "refdrone",
  "split": "val",
  "device": "jetson-orin-nano-8gb",
  "dtype": "q8_0",
  "power_mode": "15W+jetson_clocks",
  "model": "/home/jfdg/grounding/phase3-terse100eos-1024-q8_0.gguf",
  "mmproj": "/home/jfdg/grounding/mmproj-phase3-terse100eos-1024-f16.gguf",
  "max_side": 1024
}
```

## Results

```json
{
  "arm": "full-frame@1024",
  "k": 277,
  "n": 439,
  "iou_gate_pass_rate": 0.6309794988610479,
  "parse_rate": 1.0,
  "mean_iou": 0.47674662086288583,
  "center_std": 21.888046983888387,
  "prefill_ms_median": 3680,
  "decode_ms_median": 536,
  "wall_ms_median": 4319,
  "transfer_ms_median": 103,
  "prompt_tokens_median": 837,
  "fed_mpx_median": 0.6,
  "wall_s": 1881.4
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
