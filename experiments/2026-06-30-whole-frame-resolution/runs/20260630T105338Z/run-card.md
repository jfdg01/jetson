# Run `20260630T105338Z` — eval

- **Created (UTC):** 2026-06-30T10:53:38.674352+00:00
- **git SHA:** `48c9cc147e462dd83b85ff43ff792bcd0b5a81c9`  ⚠️ DIRTY TREE
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
  "resolution_max_side": 1920,
  "power_mode": "15W",
  "note": "whole-frame sweep, full well-posed val, Orin 15W Q8_0"
}
```

## Results

```json
{
  "max_side": 1920,
  "n": 439,
  "parse_pct": 100.0,
  "iou25_pct": 65.1,
  "mean_iou": 0.514,
  "med_box_px_fed": 68.0,
  "med_fed_mpx": 1.04,
  "med_prompt_n": 1383,
  "med_prompt_ms": 7938,
  "med_predicted_n": 12,
  "med_predicted_ms": 550,
  "med_wall_ms": 8689,
  "med_transfer_ms": 204
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
