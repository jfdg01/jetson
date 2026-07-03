# Run `20260703T135743Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T13:57:43.700069+00:00
- **git SHA:** `dd39ffc4ab1095da00440bb938984468218cd9e9`  ⚠️ DIRTY TREE
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
  "reground_gate": "none",
  "vmax": 4.0,
  "acquire_delay": 3.0,
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
    "n_frames": 1467,
    "duration_s": 75.0,
    "achieved_hz": 19.6,
    "carry_fps": 20.5,
    "in_fov_frac": 1.0,
    "first_lock_s": 12.17,
    "n_acquire_attempts": 12,
    "n_rejected_acquires": 10,
    "n_reground_gate_rejects": 0,
    "acquire_log": [
      [
        5.21,
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
        7.51,
        [
          281.6,
          0.0,
          396.8,
          81.6
        ],
        false,
        "size"
      ],
      [
        9.86,
        [
          281.6,
          340.8,
          307.2,
          470.4
        ],
        false,
        "size"
      ],
      [
        12.17,
        [
          262.4,
          24.0,
          403.2,
          278.4
        ],
        true,
        ""
      ],
      [
        35.18,
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
        37.43,
        [
          300.8,
          0.0,
          422.4,
          43.2
        ],
        false,
        "size"
      ],
      [
        39.74,
        [
          192.0,
          0.0,
          518.4,
          436.8
        ],
        false,
        "size"
      ],
      [
        42.14,
        [
          332.8,
          451.2,
          345.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        44.54,
        [
          345.6,
          398.4,
          364.8,
          480.0
        ],
        false,
        "size"
      ],
      [
        46.95,
        [
          358.4,
          350.4,
          377.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        49.3,
        [
          217.6,
          0.0,
          563.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        51.6,
        [
          352.0,
          0.0,
          492.8,
          244.8
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      18.63
    ],
    "carry_px_err_mean": 145.2,
    "carry_frames": 791,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 3.0,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
