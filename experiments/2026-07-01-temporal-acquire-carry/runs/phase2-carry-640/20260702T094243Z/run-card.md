# Run `20260702T094243Z` — sam2-zeroshot-carry

- **Created (UTC):** 2026-07-02T09:42:43.165562+00:00
- **git SHA:** `7295a06d64a3e5a13513b16cce10d359a4d92d09`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `8766f2dbfc806e5f6938dbd1715e228180ac778a04f4f2bacc03abda422c2b7a`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39
- **dataset:** `/home/gara/jetson/data/AerialMind` (sha256 `None`)

## Config

```json
{
  "model": "facebook/sam2.1-hiera-tiny",
  "image_size": 640,
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
  "image_size": 640,
  "cap": 300,
  "n_tracks": 186,
  "mean_iou": 0.5513063230780029,
  "iou_at_25": 0.7870390479654928,
  "iou_at_50": 0.6801236056672003,
  "id_consistency": 0.8593226249215443,
  "pred_absent_frac": 0.04628573710088266,
  "occlusion_recovery": 0.3142857142857143,
  "n_gap_events": 70,
  "mean_fps": 22.92989247311828,
  "total_wall_min": 37.4
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
