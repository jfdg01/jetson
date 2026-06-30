# Run `20260630T082509Z` — eval

- **Created (UTC):** 2026-06-30T08:25:09.419980+00:00
- **git SHA:** `4d0a015feecf8d45b63baaaf5b63a34886d628db`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `c85c39dfe299fff25dd94b8a84ffa4ae2a65a3a79146e6efd38c8b51d02f9ad7`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "phase": "whole-frame",
  "experiment": "resolution-sweep",
  "backend": "jetson",
  "quant": "q8_0",
  "dataset": "refdrone",
  "split": "val",
  "n": 439,
  "resolution_max_side": 512,
  "power_mode": "15W",
  "note": "whole-frame sweep, full well-posed val, Orin 15W Q8_0"
}
```

## Results

```json
{
  "max_side": 512,
  "n": 439,
  "parse_pct": 100.0,
  "iou25_pct": 31.4,
  "mean_iou": 0.187,
  "med_box_px_fed": 28.8,
  "med_fed_mpx": 0.15,
  "med_prompt_n": 241,
  "med_prompt_ms": 816,
  "med_predicted_n": 12,
  "med_predicted_ms": 543,
  "med_wall_ms": 1424,
  "med_transfer_ms": 64
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
