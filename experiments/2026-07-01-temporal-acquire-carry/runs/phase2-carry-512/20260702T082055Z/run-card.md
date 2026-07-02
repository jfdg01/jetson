# Run `20260702T082055Z` — sam2-zeroshot-carry

- **Created (UTC):** 2026-07-02T08:20:55.399394+00:00
- **git SHA:** `c565578139fd0865023190cf951b2e39337485e8`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `8766f2dbfc806e5f6938dbd1715e228180ac778a04f4f2bacc03abda422c2b7a`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39
- **dataset:** `/home/gara/jetson/data/AerialMind` (sha256 `None`)

## Config

```json
{
  "model": "facebook/sam2.1-hiera-tiny",
  "image_size": 512,
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
  "image_size": 512,
  "cap": 300,
  "n_tracks": 186,
  "mean_iou": 0.5061577189965167,
  "iou_at_25": 0.7374051051604356,
  "iou_at_50": 0.610819177144582,
  "id_consistency": 0.8228774808236454,
  "pred_absent_frac": 0.04500840177580154,
  "occlusion_recovery": 0.2857142857142857,
  "n_gap_events": 70,
  "mean_fps": 24.45575268817204,
  "total_wall_min": 35.2
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
