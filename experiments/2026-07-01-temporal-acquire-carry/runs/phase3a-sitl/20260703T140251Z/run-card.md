# Run `20260703T140251Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T14:02:51.283113+00:00
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
    "in_fov_frac": 0.0294,
    "first_lock_s": null,
    "n_acquire_attempts": 31,
    "n_rejected_acquires": 30,
    "n_reground_gate_rejects": 0,
    "acquire_log": [
      [
        5.31,
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
        7.66,
        [
          294.4,
          249.6,
          320.0,
          360.0
        ],
        false,
        "size"
      ],
      [
        10.01,
        [
          294.4,
          288.0,
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
          76.8,
          339.2,
          201.6
        ],
        false,
        "size"
      ],
      [
        14.72,
        [
          288.0,
          326.4,
          307.2,
          451.2
        ],
        false,
        "size"
      ],
      [
        17.12,
        [
          281.6,
          360.0,
          307.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        19.53,
        [
          288.0,
          393.6,
          307.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        21.88,
        [
          294.4,
          192.0,
          332.8,
          312.0
        ],
        false,
        "size"
      ],
      [
        24.23,
        [
          300.8,
          216.0,
          320.0,
          297.6
        ],
        false,
        "size"
      ],
      [
        26.59,
        [
          294.4,
          240.0,
          326.4,
          355.2
        ],
        false,
        "size"
      ],
      [
        28.94,
        [
          288.0,
          264.0,
          313.6,
          379.2
        ],
        false,
        "size"
      ],
      [
        31.29,
        [
          313.6,
          62.4,
          339.2,
          182.4
        ],
        false,
        "size"
      ],
      [
        33.65,
        [
          294.4,
          307.2,
          313.6,
          422.4
        ],
        false,
        "size"
      ],
      [
        36.0,
        [
          281.6,
          336.0,
          307.2,
          456.0
        ],
        false,
        "size"
      ],
      [
        38.4,
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
        40.76,
        [
          300.8,
          163.2,
          326.4,
          283.2
        ],
        false,
        "size"
      ],
      [
        43.06,
        [
          313.6,
          0.0,
          332.8,
          76.8
        ],
        false,
        "size"
      ],
      [
        45.41,
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
        47.82,
        [
          288.0,
          460.8,
          294.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        50.17,
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
        52.52,
        [
          288.0,
          292.8,
          307.2,
          398.4
        ],
        false,
        "size"
      ],
      [
        54.88,
        [
          275.2,
          312.0,
          300.8,
          432.0
        ],
        false,
        "size"
      ],
      [
        57.23,
        [
          281.6,
          331.2,
          300.8,
          451.2
        ],
        false,
        "size"
      ],
      [
        59.53,
        [
          25.6,
          465.6,
          160.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        61.69,
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
        63.89,
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
        66.09,
        [
          38.4,
          33.6,
          64.0,
          57.6
        ],
        false,
        "size"
      ],
      [
        68.4,
        [
          313.6,
          0.0,
          332.8,
          57.6
        ],
        false,
        "size"
      ],
      [
        70.75,
        [
          275.2,
          408.0,
          288.0,
          460.8
        ],
        false,
        "size"
      ],
      [
        73.1,
        [
          288.0,
          216.0,
          307.2,
          326.4
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
