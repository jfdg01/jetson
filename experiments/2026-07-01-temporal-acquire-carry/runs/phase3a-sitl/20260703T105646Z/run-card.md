# Run `20260703T105646Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T10:56:46.163898+00:00
- **git SHA:** `795975c39a68fe4e38a6cfb1f0023841632ae49e`  ⚠️ DIRTY TREE
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
  "acquire_hold": "motion",
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
    "n_frames": 1498,
    "duration_s": 75.0,
    "achieved_hz": 20.0,
    "carry_fps": null,
    "in_fov_frac": 0.0521,
    "first_lock_s": null,
    "n_acquire_attempts": 32,
    "n_rejected_acquires": 31,
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
        4.61,
        [
          288.0,
          0.0,
          396.8,
          72.0
        ],
        false,
        "size"
      ],
      [
        6.96,
        [
          294.4,
          100.8,
          339.2,
          230.4
        ],
        false,
        "size"
      ],
      [
        9.31,
        [
          300.8,
          153.6,
          332.8,
          268.8
        ],
        false,
        "size"
      ],
      [
        11.67,
        [
          307.2,
          148.8,
          339.2,
          268.8
        ],
        false,
        "size"
      ],
      [
        14.02,
        [
          307.2,
          144.0,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        16.37,
        [
          307.2,
          144.0,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        18.73,
        [
          307.2,
          139.2,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        21.08,
        [
          307.2,
          139.2,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        23.43,
        [
          307.2,
          144.0,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        25.79,
        [
          307.2,
          139.2,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        28.14,
        [
          307.2,
          144.0,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        30.49,
        [
          307.2,
          144.0,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        32.85,
        [
          307.2,
          144.0,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        35.2,
        [
          307.2,
          139.2,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        37.55,
        [
          307.2,
          139.2,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        39.91,
        [
          307.2,
          144.0,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        42.26,
        [
          307.2,
          144.0,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        44.61,
        [
          307.2,
          139.2,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        46.97,
        [
          307.2,
          144.0,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        49.32,
        [
          307.2,
          139.2,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        51.67,
        [
          307.2,
          139.2,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        54.02,
        [
          307.2,
          139.2,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        56.38,
        [
          307.2,
          144.0,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        58.73,
        [
          307.2,
          144.0,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        61.08,
        [
          307.2,
          139.2,
          339.2,
          264.0
        ],
        false,
        "size"
      ],
      [
        63.44,
        [
          307.2,
          139.2,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        65.79,
        [
          307.2,
          144.0,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        68.14,
        [
          307.2,
          144.0,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        70.5,
        [
          307.2,
          139.2,
          332.8,
          264.0
        ],
        false,
        "size"
      ],
      [
        72.85,
        [
          307.2,
          139.2,
          332.8,
          264.0
        ],
        false,
        "size"
      ]
    ],
    "n_regrounds": 0,
    "relock_walls_s": [],
    "carry_px_err_mean": null,
    "carry_frames": 0,
    "recovered_after_occlusion": false
  },
  "gate_speed_ms": 3.0,
  "gate": "FAIL"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
