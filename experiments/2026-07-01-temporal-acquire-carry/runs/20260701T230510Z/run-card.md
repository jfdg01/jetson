# Run `20260701T230510Z` — follow-demo

- **Created (UTC):** 2026-07-01T23:05:10.227511+00:00
- **git SHA:** `54ea23b58b1929bd204dcf0fd8b9d11aa585d7ba`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `8766f2dbfc806e5f6938dbd1715e228180ac778a04f4f2bacc03abda422c2b7a`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "seq": "M0205",
  "caption": "Black car invading other lanes",
  "start": 1,
  "n_frames": 440,
  "gt_tid": 22,
  "loss_n": 75,
  "retarget": "220:4:The parked taxi",
  "backend": "jetson",
  "ssh_host": "jetson",
  "fps": 25.0,
  "out": "/home/gara/jetson/experiments/2026-07-01-temporal-acquire-carry/raw/demo-retarget.mp4",
  "selfcheck": false,
  "model": "facebook/sam2.1-hiera-tiny"
}
```

## Results

```json
{
  "seq": "M0205",
  "caption": "Black car invading other lanes",
  "frames": [
    1,
    440
  ],
  "backend": "jetson",
  "events": [
    {
      "event": "ACQUIRE",
      "frame": 1,
      "wall_s": 4.5,
      "box": [
        737.28,
        307.79999999999995,
        901.12,
        432.0
      ],
      "iou_vs_gt": 0.0
    },
    {
      "event": "RETARGET",
      "frame": 220,
      "wall_s": 4.08,
      "box": [
        450.56,
        351.0,
        593.92,
        464.4
      ],
      "caption": "The parked taxi",
      "iou_vs_gt": 0.0
    }
  ],
  "carry_fps": 15.4,
  "mean_iou_vs_gt": 0.0,
  "iou_at_25": 0.0,
  "pred_absent_frac": 0.161,
  "out": "/home/gara/jetson/experiments/2026-07-01-temporal-acquire-carry/raw/demo-retarget.mp4"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
