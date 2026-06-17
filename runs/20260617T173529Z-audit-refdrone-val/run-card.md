# Run `20260617T173529Z-audit-refdrone-val` — audit

- **Created (UTC):** 2026-06-17T17:35:29.986827+00:00
- **git SHA:** `1e4ac58e2776e63457c0b4e863b9cec6a5c0df66`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `43e3fa4577ff90e5c701c03a206398875c7e04babd0238ec92caa1f4f6ed0635`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "dataset": "refdrone",
  "split": "val",
  "max_samples": 0
}
```

## Results

```json
{
  "source": "refdrone",
  "split": "val",
  "n_records": 1421,
  "n_real_boxes": 4734,
  "boxes_per_caption": {
    "1": 439,
    "2": 320,
    "3": 237,
    "4": 124,
    "5": 103,
    "6": 57,
    "7": 41,
    "8": 21,
    "9": 25,
    "10": 18,
    "11": 7,
    "12": 7,
    "13": 1,
    "14": 2,
    "15": 3,
    "16": 3,
    "17": 2,
    "18": 1,
    "19": 1,
    "22": 1,
    "24": 1,
    "29": 1,
    "32": 1,
    "33": 1,
    "39": 1,
    "51": 1,
    "65": 1,
    "70": 1
  },
  "boxes_per_caption_mean": 3.3315,
  "n_well_posed": 439,
  "well_posed_fraction": 0.3089,
  "obj_size_px_percentiles": {
    "p5": 13.96,
    "p10": 16.16,
    "p25": 23.33,
    "p50": 36.74,
    "p75": 61.02,
    "p90": 93.99,
    "p95": 118.05
  },
  "obj_size_px_after_resize": {
    "p5": 5.51,
    "p10": 6.52,
    "p25": 9.35,
    "p50": 14.58,
    "p75": 23.82,
    "p90": 35.91,
    "p95": 44.72
  },
  "image_size": 512
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
