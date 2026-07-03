# Run `20260703T084334Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T08:43:34.374419+00:00
- **git SHA:** `2344f6ab6c1d39dd49dc8f2ddb93a7034d56168b`  ⚠️ DIRTY TREE
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
  "twin": null,
  "loss_gate": "motion",
  "score_tau": 0.0,
  "dr": "pursuit",
  "acquire_hold": "motion",
  "reground_gate": "motion",
  "catchup_replay": true,
  "carry": "host-3090"
}
```

## Results

```json
{
  "trial": {
    "speed_ms": 0.5,
    "image_size": 1024,
    "n_frames": 1470,
    "achieved_hz": 19.6,
    "carry_fps": 20.8,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 6,
    "n_rejected_acquires": 4,
    "n_reground_gate_rejects": 0,
    "acquire_log": [
      [
        2.35,
        [
          288.0,
          355.2,
          307.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        4.71,
        [
          256.0,
          81.6,
          390.4,
          331.2
        ],
        true,
        ""
      ],
      [
        35.1,
        [
          294.4,
          307.2,
          313.6,
          393.6
        ],
        false,
        "size"
      ],
      [
        37.46,
        [
          288.0,
          384.0,
          307.2,
          465.6
        ],
        false,
        "size"
      ],
      [
        39.76,
        [
          288.0,
          0.0,
          403.2,
          67.2
        ],
        false,
        "size"
      ],
      [
        42.06,
        [
          281.6,
          0.0,
          409.6,
          129.6
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      9.32
    ],
    "carry_px_err_mean": 25.7,
    "carry_frames": 1129,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 0.5,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
