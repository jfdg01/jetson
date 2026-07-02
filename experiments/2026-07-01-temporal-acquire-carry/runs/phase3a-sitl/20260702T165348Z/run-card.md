# Run `20260702T165348Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-02T16:53:48.103285+00:00
- **git SHA:** `eade34c018e17e2fac62a0fba7d6dfb280477585`  ⚠️ DIRTY TREE
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
  "speed": 0.5,
  "duration_s": 75.0,
  "hz": 20,
  "image_size": 1024,
  "sam2": "facebook/sam2.1-hiera-tiny",
  "validate": "sizeprior-0.5-2.0",
  "deadreckon": true,
  "carry": "host-3090"
}
```

## Results

```json
{
  "trial": {
    "speed_ms": 0.5,
    "image_size": 1024,
    "n_frames": 1460,
    "achieved_hz": 19.5,
    "carry_fps": 20.3,
    "in_fov_frac": 0.4842,
    "first_lock_s": 5.01,
    "n_acquire_attempts": 2,
    "n_rejected_acquires": 1,
    "n_regrounds": 0,
    "relock_walls_s": [],
    "carry_px_err_mean": 10.7,
    "carry_frames": 1359,
    "recovered_after_occlusion": false
  },
  "gate_speed_ms": 0.5,
  "gate": "FAIL"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
