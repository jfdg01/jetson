# Run `20260702T080332Z` — phase1-sitl-oracle

- **Created (UTC):** 2026-07-02T08:03:32.787258+00:00
- **git SHA:** `041caeb95eec8e36004c6b5745d781ecd80b29ca`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `8766f2dbfc806e5f6938dbd1715e228180ac778a04f4f2bacc03abda422c2b7a`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "lat_s": [
    4.1,
    4.6
  ],
  "p_parsefail": 0.007,
  "loss_n": 60,
  "occ": [
    30.0,
    5.0
  ],
  "speeds": [
    0.25,
    0.5,
    1.0
  ],
  "duration_s": 75.0,
  "hz": 20,
  "seed": 7
}
```

## Results

```json
{
  "trials": [
    {
      "speed_ms": 0.25,
      "n_frames": 1498,
      "in_fov_frac": 1.0,
      "first_lock_s": 4.31,
      "n_acquire_attempts": 2,
      "n_regrounds": 1,
      "relock_walls_s": [
        4.46
      ],
      "carry_px_err_mean": 16.1,
      "carry_frames": 1264,
      "recovered_after_occlusion": true
    },
    {
      "speed_ms": 0.5,
      "n_frames": 1498,
      "in_fov_frac": 1.0,
      "first_lock_s": 4.26,
      "n_acquire_attempts": 2,
      "n_regrounds": 1,
      "relock_walls_s": [
        4.21
      ],
      "carry_px_err_mean": 32.0,
      "carry_frames": 1270,
      "recovered_after_occlusion": true
    },
    {
      "speed_ms": 1.0,
      "n_frames": 1499,
      "in_fov_frac": 0.4817,
      "first_lock_s": 4.36,
      "n_acquire_attempts": 10,
      "n_regrounds": 1,
      "relock_walls_s": [],
      "carry_px_err_mean": 66.2,
      "carry_frames": 513,
      "recovered_after_occlusion": false
    }
  ],
  "gate_speed_ms": 0.25,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
