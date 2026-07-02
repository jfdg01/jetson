# Run `20260702T084032Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-02T08:40:32.201865+00:00
- **git SHA:** `c565578139fd0865023190cf951b2e39337485e8`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `8766f2dbfc806e5f6938dbd1715e228180ac778a04f4f2bacc03abda422c2b7a`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "caption": "the white car",
  "loss_s": 3.0,
  "occ": [
    30.0,
    5.0
  ],
  "speed": 0.25,
  "duration_s": 75.0,
  "hz": 20,
  "image_size": 1024,
  "sam2": "facebook/sam2.1-hiera-tiny",
  "validate": "sizeprior-0.5-2.0",
  "deadreckon": true
}
```

## Results

```json
{
  "trial": {
    "speed_ms": 0.25,
    "image_size": 1024,
    "n_frames": 1086,
    "achieved_hz": 14.5,
    "carry_fps": 13.6,
    "in_fov_frac": 1.0,
    "first_lock_s": 2.65,
    "n_acquire_attempts": 7,
    "n_rejected_acquires": 5,
    "n_regrounds": 1,
    "relock_walls_s": [
      13.9
    ],
    "carry_px_err_mean": 16.2,
    "carry_frames": 721,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 0.25,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
