# Run `20260701T235912Z` — sam2-zeroshot-carry

- **Created (UTC):** 2026-07-01T23:59:12.249505+00:00
- **git SHA:** `ab6d6d702bf59666ebf9d3a9ad3394adc37c2209`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `8766f2dbfc806e5f6938dbd1715e228180ac778a04f4f2bacc03abda422c2b7a`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39
- **dataset:** `/home/gara/jetson/data/AerialMind` (sha256 `None`)

## Config

```json
{
  "model": "facebook/sam2.1-hiera-tiny",
  "cap": 300,
  "smoke": false,
  "gap_min_frames": 3,
  "recovery_window": 5
}
```

## Results

```json
{
  "model": "facebook/sam2.1-hiera-tiny",
  "cap": 300,
  "n_tracks": 186,
  "mean_iou": 0.6017846700119674,
  "iou_at_25": 0.8492374782585477,
  "iou_at_50": 0.7504116142754472,
  "id_consistency": 0.8914200866963142,
  "pred_absent_frac": 0.03457480856447933,
  "occlusion_recovery": 0.32857142857142857,
  "n_gap_events": 70,
  "mean_fps": 14.352043010752686,
  "total_wall_min": 58.4
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
