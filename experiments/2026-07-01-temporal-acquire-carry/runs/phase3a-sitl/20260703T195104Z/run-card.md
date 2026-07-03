# Run `20260703T195104Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T19:51:04.494368+00:00
- **git SHA:** `727025427f55acb95d5a413ec4fad9e8d612384b`  ⚠️ DIRTY TREE
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
  "speed": 3.0,
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
  "reground_hold": "chase",
  "reground_gate": "mask",
  "vmax": 4.0,
  "acquire_delay": 3.0,
  "app_tau": 12.0,
  "decoy_shade": 245,
  "decoy2_m": null,
  "occ2": null,
  "catchup_replay": true,
  "carry": "host-3090"
}
```

## Results

```json
{
  "trial": {
    "speed_ms": 3.0,
    "image_size": 1024,
    "n_frames": 1455,
    "duration_s": 75.0,
    "achieved_hz": 19.4,
    "carry_fps": 20.4,
    "in_fov_frac": 1.0,
    "first_lock_s": 9.86,
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
        5.26,
        [
          288.0,
          0.0,
          403.2,
          43.2
        ],
        false,
        "size"
      ],
      [
        7.56,
        [
          281.6,
          0.0,
          396.8,
          72.0
        ],
        false,
        "size"
      ],
      [
        9.86,
        [
          268.8,
          0.0,
          403.2,
          172.8
        ],
        true,
        ""
      ],
      [
        35.29,
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
        37.59,
        [
          300.8,
          0.0,
          435.2,
          62.4
        ],
        false,
        "size"
      ],
      [
        39.9,
        [
          275.2,
          28.8,
          416.0,
          278.4
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      6.95
    ],
    "carry_px_err_mean": 146.8,
    "carry_frames": 1061,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 3.0,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
