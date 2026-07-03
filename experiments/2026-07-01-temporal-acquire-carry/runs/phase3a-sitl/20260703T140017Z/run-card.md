# Run `20260703T140017Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T14:00:17.454254+00:00
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
  "acquire_delay": 3.0,
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
    "n_frames": 1498,
    "duration_s": 75.0,
    "achieved_hz": 20.0,
    "carry_fps": null,
    "in_fov_frac": 0.03,
    "first_lock_s": null,
    "n_acquire_attempts": 31,
    "n_rejected_acquires": 30,
    "n_reground_gate_rejects": 0,
    "acquire_log": [
      [
        5.31,
        [
          307.2,
          144.0,
          339.2,
          268.8
        ],
        false,
        "size"
      ],
      [
        7.66,
        [
          294.4,
          249.6,
          320.0,
          369.6
        ],
        false,
        "size"
      ],
      [
        10.01,
        [
          294.4,
          292.8,
          313.6,
          408.0
        ],
        false,
        "size"
      ],
      [
        12.37,
        [
          294.4,
          307.2,
          313.6,
          427.2
        ],
        false,
        "size"
      ],
      [
        14.72,
        [
          294.4,
          105.6,
          339.2,
          235.2
        ],
        false,
        "size"
      ],
      [
        17.12,
        [
          281.6,
          364.8,
          307.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        19.53,
        [
          281.6,
          398.4,
          300.8,
          480.0
        ],
        false,
        "size"
      ],
      [
        21.88,
        [
          307.2,
          206.4,
          326.4,
          321.6
        ],
        false,
        "size"
      ],
      [
        24.23,
        [
          300.8,
          225.6,
          326.4,
          336.0
        ],
        false,
        "size"
      ],
      [
        26.59,
        [
          294.4,
          254.4,
          320.0,
          360.0
        ],
        false,
        "size"
      ],
      [
        28.94,
        [
          294.4,
          273.6,
          313.6,
          388.8
        ],
        false,
        "size"
      ],
      [
        31.29,
        [
          288.0,
          302.4,
          307.2,
          417.6
        ],
        false,
        "size"
      ],
      [
        33.65,
        [
          294.4,
          326.4,
          313.6,
          441.6
        ],
        false,
        "size"
      ],
      [
        36.0,
        [
          288.0,
          345.6,
          307.2,
          470.4
        ],
        false,
        "size"
      ],
      [
        38.4,
        [
          281.6,
          374.4,
          307.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        40.76,
        [
          300.8,
          182.4,
          320.0,
          297.6
        ],
        false,
        "size"
      ],
      [
        43.11,
        [
          294.4,
          211.2,
          326.4,
          326.4
        ],
        false,
        "size"
      ],
      [
        45.46,
        [
          294.4,
          230.4,
          326.4,
          336.0
        ],
        false,
        "size"
      ],
      [
        47.82,
        [
          288.0,
          259.2,
          307.2,
          374.4
        ],
        false,
        "size"
      ],
      [
        50.17,
        [
          288.0,
          278.4,
          307.2,
          393.6
        ],
        false,
        "size"
      ],
      [
        52.52,
        [
          288.0,
          307.2,
          307.2,
          417.6
        ],
        false,
        "size"
      ],
      [
        54.88,
        [
          281.6,
          336.0,
          300.8,
          456.0
        ],
        false,
        "size"
      ],
      [
        57.23,
        [
          275.2,
          350.4,
          294.4,
          475.2
        ],
        false,
        "size"
      ],
      [
        59.43,
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
        61.64,
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
        63.79,
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
        66.04,
        [
          454.4,
          0.0,
          640.0,
          24.0
        ],
        false,
        "size"
      ],
      [
        68.35,
        [
          300.8,
          0.0,
          339.2,
          240.0
        ],
        false,
        "size"
      ],
      [
        70.7,
        [
          294.4,
          211.2,
          320.0,
          331.2
        ],
        false,
        "size"
      ],
      [
        73.05,
        [
          288.0,
          235.2,
          313.6,
          350.4
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
  "gate_speed_ms": 3.5,
  "gate": "FAIL"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
