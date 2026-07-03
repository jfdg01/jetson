# Run `20260703T133304Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T13:33:04.460680+00:00
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
    "n_frames": 1471,
    "duration_s": 75.0,
    "achieved_hz": 19.6,
    "carry_fps": 20.6,
    "in_fov_frac": 1.0,
    "first_lock_s": 9.31,
    "n_acquire_attempts": 15,
    "n_rejected_acquires": 13,
    "n_reground_gate_rejects": 0,
    "acquire_log": [
      [
        2.3,
        [
          134.4,
          0.0,
          499.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        4.66,
        [
          294.4,
          264.0,
          313.6,
          379.2
        ],
        false,
        "size"
      ],
      [
        7.01,
        [
          294.4,
          211.2,
          326.4,
          331.2
        ],
        false,
        "size"
      ],
      [
        9.31,
        [
          275.2,
          0.0,
          396.8,
          158.4
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
        37.41,
        [
          390.4,
          0.0,
          492.8,
          28.8
        ],
        false,
        "size"
      ],
      [
        39.71,
        [
          211.2,
          0.0,
          518.4,
          427.2
        ],
        false,
        "size"
      ],
      [
        42.11,
        [
          339.2,
          441.6,
          345.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        44.52,
        [
          345.6,
          384.0,
          364.8,
          480.0
        ],
        false,
        "size"
      ],
      [
        46.87,
        [
          352.0,
          336.0,
          377.6,
          460.8
        ],
        false,
        "size"
      ],
      [
        49.22,
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
        51.58,
        [
          377.6,
          225.6,
          409.6,
          345.6
        ],
        false,
        "size"
      ],
      [
        53.98,
        [
          384.0,
          408.0,
          403.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        56.38,
        [
          396.8,
          360.0,
          422.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        58.69,
        [
          384.0,
          0.0,
          518.4,
          230.4
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      25.74
    ],
    "carry_px_err_mean": 148.5,
    "carry_frames": 710,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 3.0,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
