# Run `20260617T173532Z-audit-refcoco-validation` — audit

- **Created (UTC):** 2026-06-17T17:35:33.002353+00:00
- **git SHA:** `1e4ac58e2776e63457c0b4e863b9cec6a5c0df66`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `43e3fa4577ff90e5c701c03a206398875c7e04babd0238ec92caa1f4f6ed0635`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "dataset": "refcoco",
  "split": "validation",
  "max_samples": 2000
}
```

## Results

```json
{
  "source": "refcoco",
  "split": "validation",
  "n_records": 2000,
  "n_real_boxes": 2000,
  "boxes_per_caption": {
    "1": 2000
  },
  "boxes_per_caption_mean": 1.0,
  "n_well_posed": 2000,
  "well_posed_fraction": 1.0,
  "obj_size_px_percentiles": {
    "p5": 132.86,
    "p10": 143.41,
    "p25": 167.88,
    "p50": 207.71,
    "p75": 270.56,
    "p90": 346.74,
    "p95": 395.33
  },
  "obj_size_px_after_resize": {
    "p5": 106.87,
    "p10": 116.09,
    "p25": 136.39,
    "p50": 171.97,
    "p75": 224.43,
    "p90": 281.6,
    "p95": 327.23
  },
  "image_size": 512
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
