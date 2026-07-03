# Run `20260703T084841Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T08:48:41.743378+00:00
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
  "speed": 1.5,
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
    "speed_ms": 1.5,
    "image_size": 1024,
    "n_frames": 1410,
    "achieved_hz": 18.8,
    "carry_fps": 19.4,
    "in_fov_frac": 1.0,
    "first_lock_s": 16.57,
    "n_acquire_attempts": 10,
    "n_rejected_acquires": 8,
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
          294.4,
          230.4,
          320.0,
          350.4
        ],
        false,
        "size"
      ],
      [
        7.11,
        [
          294.4,
          422.4,
          313.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        9.51,
        [
          294.4,
          388.8,
          320.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        11.92,
        [
          294.4,
          369.6,
          313.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        14.27,
        [
          294.4,
          340.8,
          313.6,
          470.4
        ],
        false,
        "size"
      ],
      [
        16.57,
        [
          268.8,
          0.0,
          396.8,
          216.0
        ],
        true,
        ""
      ],
      [
        35.13,
        [
          6.4,
          43.2,
          38.4,
          48.0
        ],
        false,
        "size"
      ],
      [
        37.38,
        [
          288.0,
          0.0,
          409.6,
          19.2
        ],
        false,
        "size"
      ],
      [
        39.69,
        [
          307.2,
          0.0,
          441.6,
          220.8
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      6.78
    ],
    "carry_px_err_mean": 76.0,
    "carry_frames": 883,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 1.5,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
