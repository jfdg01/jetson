# Run `20260703T151523Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T15:15:23.968617+00:00
- **git SHA:** `69691e9eaef23ad2cd1ed128149936cec9e045b5`  ⚠️ DIRTY TREE
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
  "retarget_t": null,
  "loss_gate": "motion",
  "score_tau": 0.0,
  "dr": "pursuit",
  "acquire_hold": "motion",
  "reground_gate": "appearance",
  "vmax": 2.5,
  "acquire_delay": 0.0,
  "app_tau": 12.0,
  "decoy_shade": 245,
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
    "n_frames": 1456,
    "duration_s": 75.0,
    "achieved_hz": 19.4,
    "carry_fps": 20.4,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 6,
    "n_rejected_acquires": 4,
    "n_reground_gate_rejects": 0,
    "app_template": [
      245.0,
      245.0,
      245.0
    ],
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
          76.8,
          390.4,
          326.4
        ],
        true,
        ""
      ],
      [
        35.08,
        [
          300.8,
          316.8,
          320.0,
          398.4
        ],
        false,
        "size"
      ],
      [
        37.43,
        [
          294.4,
          384.0,
          313.6,
          465.6
        ],
        false,
        "size"
      ],
      [
        39.73,
        [
          294.4,
          0.0,
          416.0,
          67.2
        ],
        false,
        "size"
      ],
      [
        42.04,
        [
          294.4,
          0.0,
          422.4,
          134.4
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      9.32
    ],
    "carry_px_err_mean": 25.4,
    "carry_frames": 1116,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 0.5,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
