# Run `20260701T230357Z` — follow-demo

- **Created (UTC):** 2026-07-01T23:03:57.410125+00:00
- **git SHA:** `54ea23b58b1929bd204dcf0fd8b9d11aa585d7ba`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `8766f2dbfc806e5f6938dbd1715e228180ac778a04f4f2bacc03abda422c2b7a`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "seq": "M0205",
  "caption": "Commercial truck",
  "start": 395,
  "n_frames": 320,
  "gt_tid": 25,
  "loss_n": 75,
  "retarget": null,
  "backend": "jetson",
  "ssh_host": "jetson",
  "fps": 25.0,
  "out": "/home/gara/jetson/experiments/2026-07-01-temporal-acquire-carry/raw/demo-occlusion.mp4",
  "selfcheck": false,
  "model": "facebook/sam2.1-hiera-tiny"
}
```

## Results

```json
{
  "seq": "M0205",
  "caption": "Commercial truck",
  "frames": [
    395,
    646
  ],
  "backend": "jetson",
  "events": [
    {
      "event": "ACQUIRE",
      "frame": 395,
      "wall_s": 4.58,
      "box": [
        686.08,
        345.6,
        1024.0,
        540.0
      ],
      "iou_vs_gt": 0.947
    }
  ],
  "carry_fps": 18.3,
  "mean_iou_vs_gt": 0.886,
  "iou_at_25": 1.0,
  "pred_absent_frac": 0.0,
  "out": "/home/gara/jetson/experiments/2026-07-01-temporal-acquire-carry/raw/demo-occlusion.mp4"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
