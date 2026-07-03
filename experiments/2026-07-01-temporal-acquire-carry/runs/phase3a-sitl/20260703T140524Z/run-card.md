# Run `20260703T140524Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T14:05:24.793662+00:00
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
          294.4,
          144.0,
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
          326.4,
          364.8
        ],
        false,
        "size"
      ],
      [
        10.01,
        [
          294.4,
          62.4,
          345.6,
          182.4
        ],
        false,
        "size"
      ],
      [
        12.37,
        [
          300.8,
          81.6,
          339.2,
          201.6
        ],
        false,
        "size"
      ],
      [
        14.72,
        [
          294.4,
          105.6,
          332.8,
          235.2
        ],
        false,
        "size"
      ],
      [
        17.12,
        [
          294.4,
          355.2,
          313.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        19.53,
        [
          275.2,
          398.4,
          294.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        21.88,
        [
          300.8,
          201.6,
          326.4,
          316.8
        ],
        false,
        "size"
      ],
      [
        24.23,
        [
          294.4,
          220.8,
          326.4,
          340.8
        ],
        false,
        "size"
      ],
      [
        26.59,
        [
          294.4,
          244.8,
          320.0,
          355.2
        ],
        false,
        "size"
      ],
      [
        28.94,
        [
          288.0,
          268.8,
          313.6,
          384.0
        ],
        false,
        "size"
      ],
      [
        31.29,
        [
          288.0,
          297.6,
          307.2,
          412.8
        ],
        false,
        "size"
      ],
      [
        33.65,
        [
          288.0,
          316.8,
          307.2,
          432.0
        ],
        false,
        "size"
      ],
      [
        36.0,
        [
          281.6,
          345.6,
          307.2,
          460.8
        ],
        false,
        "size"
      ],
      [
        38.4,
        [
          275.2,
          369.6,
          300.8,
          480.0
        ],
        false,
        "size"
      ],
      [
        40.76,
        [
          300.8,
          172.8,
          326.4,
          283.2
        ],
        false,
        "size"
      ],
      [
        43.11,
        [
          294.4,
          201.6,
          320.0,
          316.8
        ],
        false,
        "size"
      ],
      [
        45.46,
        [
          288.0,
          225.6,
          313.6,
          336.0
        ],
        false,
        "size"
      ],
      [
        47.76,
        [
          313.6,
          19.2,
          339.2,
          134.4
        ],
        false,
        "size"
      ],
      [
        50.12,
        [
          288.0,
          268.8,
          307.2,
          384.0
        ],
        false,
        "size"
      ],
      [
        52.47,
        [
          281.6,
          288.0,
          307.2,
          403.2
        ],
        false,
        "size"
      ],
      [
        54.82,
        [
          275.2,
          316.8,
          300.8,
          436.8
        ],
        false,
        "size"
      ],
      [
        57.18,
        [
          275.2,
          340.8,
          294.4,
          465.6
        ],
        false,
        "size"
      ],
      [
        59.38,
        [
          38.4,
          43.2,
          64.0,
          62.4
        ],
        false,
        "size"
      ],
      [
        61.58,
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
        63.74,
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
        65.99,
        [
          32.0,
          4.8,
          633.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        68.29,
        [
          307.2,
          0.0,
          339.2,
          216.0
        ],
        false,
        "size"
      ],
      [
        70.65,
        [
          268.8,
          408.0,
          288.0,
          465.6
        ],
        false,
        "size"
      ],
      [
        73.0,
        [
          275.2,
          220.8,
          300.8,
          336.0
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
