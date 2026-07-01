# Run `20260701T230302Z` — follow-demo

- **Created (UTC):** 2026-07-01T23:03:03.003949+00:00
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
  "backend": "oracle",
  "ssh_host": "jetson",
  "fps": 25.0,
  "out": "/tmp/claude-1000/-home-gara-jetson/b0b3bca2-23f9-4ec3-b7a6-6a0656758fa0/scratchpad/smoke-retarget.mp4",
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
  "backend": "oracle",
  "events": [
    {
      "event": "ACQUIRE",
      "frame": 1,
      "wall_s": 0.05,
      "box": [
        312.000512,
        84.99978,
        365.00070400000004,
        132.99984
      ],
      "iou_vs_gt": 1.0
    },
    {
      "event": "RETARGET",
      "frame": 220,
      "wall_s": 0.05,
      "box": [
        24.000512,
        165.99978,
        125.000704,
        223.99956
      ],
      "caption": "The parked taxi",
      "iou_vs_gt": 1.0
    }
  ],
  "carry_fps": 16.1,
  "mean_iou_vs_gt": 0.828,
  "iou_at_25": 1.0,
  "pred_absent_frac": 0.0,
  "out": "/tmp/claude-1000/-home-gara-jetson/b0b3bca2-23f9-4ec3-b7a6-6a0656758fa0/scratchpad/smoke-retarget.mp4"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
