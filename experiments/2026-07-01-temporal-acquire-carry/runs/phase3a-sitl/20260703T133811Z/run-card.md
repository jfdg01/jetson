# Run `20260703T133811Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T13:38:11.832674+00:00
- **git SHA:** `3b22c68682192d4e831d1cff7515291bb0cd52ab`  ⚠️ DIRTY TREE
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
  "speed": 3.5,
  "duration_s": 75.0,
  "hz": 20,
  "image_size": 1024,
  "sam2": "facebook/sam2.1-hiera-tiny",
  "validate": "sizeprior-0.5-2.0",
  "deadreckon": true,
  "twin": null,
  "retarget_t": null,
  "loss_gate": "motion",
  "score_tau": 0.0,
  "dr": "pursuit",
  "acquire_hold": "chase",
  "reground_gate": "none",
  "vmax": 5.0,
  "catchup_replay": true,
  "carry": "host-3090"
}
```

## Results

```json
{
  "trial": {
    "speed_ms": 3.5,
    "image_size": 1024,
    "n_frames": 1461,
    "duration_s": 75.0,
    "achieved_hz": 19.5,
    "carry_fps": 20.5,
    "in_fov_frac": 0.9617,
    "first_lock_s": 2.3,
    "n_acquire_attempts": 4,
    "n_rejected_acquires": 2,
    "n_reground_gate_rejects": 0,
    "acquire_log": [
      [
        2.3,
        [
          243.2,
          76.8,
          396.8,
          340.8
        ],
        true,
        ""
      ],
      [
        35.15,
        [
          44.8,
          43.2,
          57.6,
          48.0
        ],
        false,
        "size"
      ],
      [
        37.45,
        [
          300.8,
          0.0,
          422.4,
          48.0
        ],
        false,
        "size"
      ],
      [
        39.76,
        [
          288.0,
          0.0,
          435.2,
          244.8
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      6.82
    ],
    "carry_px_err_mean": 174.6,
    "carry_frames": 1173,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 3.5,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
