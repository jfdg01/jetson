# Run `20260703T171536Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T17:15:36.913336+00:00
- **git SHA:** `59c1d1a3bd2af0c5791695b7cd9708e4c547602c`  ⚠️ DIRTY TREE
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
  "speed": 0.25,
  "duration_s": 150.0,
  "hz": 20,
  "image_size": 1024,
  "sam2": "facebook/sam2.1-hiera-tiny",
  "validate": "sizeprior-0.5-2.0",
  "deadreckon": true,
  "twin": "decoy",
  "retarget_t": null,
  "loss_gate": "motion",
  "score_tau": 0.0,
  "dr": "pursuit",
  "acquire_hold": "motion",
  "reground_gate": "mask",
  "vmax": 2.5,
  "acquire_delay": 0.0,
  "app_tau": 12.0,
  "decoy_shade": 215,
  "decoy2_m": null,
  "occ2": [
    82.0,
    10.0
  ],
  "catchup_replay": true,
  "carry": "host-3090"
}
```

## Results

```json
{
  "trial": {
    "speed_ms": 0.25,
    "image_size": 1024,
    "n_frames": 2955,
    "duration_s": 150.0,
    "achieved_hz": 19.7,
    "carry_fps": 20.7,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 28,
    "n_rejected_acquires": 17,
    "n_reground_gate_rejects": 8,
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
          249.6,
          96.0,
          390.4,
          345.6
        ],
        true,
        ""
      ],
      [
        34.8,
        [
          294.4,
          273.6,
          313.6,
          384.0
        ],
        false,
        "size"
      ],
      [
        37.15,
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
        39.4,
        [
          320.0,
          0.0,
          409.6,
          28.8
        ],
        false,
        "size"
      ],
      [
        41.71,
        [
          281.6,
          0.0,
          403.2,
          67.2
        ],
        false,
        "size"
      ],
      [
        44.01,
        [
          268.8,
          0.0,
          403.2,
          100.8
        ],
        false,
        "size"
      ],
      [
        46.31,
        [
          192.0,
          0.0,
          486.4,
          124.8
        ],
        false,
        "size"
      ],
      [
        48.62,
        [
          192.0,
          0.0,
          486.4,
          172.8
        ],
        false,
        "size"
      ],
      [
        51.02,
        [
          0.0,
          148.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        53.32,
        [
          249.6,
          0.0,
          396.8,
          230.4
        ],
        false,
        "gate"
      ],
      [
        55.63,
        [
          249.6,
          0.0,
          396.8,
          264.0
        ],
        false,
        "gate"
      ],
      [
        57.94,
        [
          256.0,
          0.0,
          396.8,
          292.8
        ],
        false,
        "gate"
      ],
      [
        60.24,
        [
          243.2,
          0.0,
          396.8,
          326.4
        ],
        false,
        "gate"
      ],
      [
        62.54,
        [
          243.2,
          0.0,
          390.4,
          355.2
        ],
        false,
        "gate"
      ],
      [
        64.85,
        [
          243.2,
          0.0,
          390.4,
          388.8
        ],
        false,
        "gate"
      ],
      [
        67.15,
        [
          236.8,
          0.0,
          396.8,
          412.8
        ],
        false,
        "gate"
      ],
      [
        69.45,
        [
          230.4,
          4.8,
          396.8,
          446.4
        ],
        false,
        "gate"
      ],
      [
        71.76,
        [
          256.0,
          33.6,
          390.4,
          225.6
        ],
        true,
        ""
      ],
      [
        86.81,
        [
          230.4,
          465.6,
          294.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        89.16,
        [
          288.0,
          350.4,
          313.6,
          475.2
        ],
        false,
        "size"
      ],
      [
        91.51,
        [
          288.0,
          384.0,
          313.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        93.87,
        [
          294.4,
          417.6,
          313.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        96.02,
        [
          32.0,
          0.0,
          38.4,
          14.4
        ],
        false,
        "size"
      ],
      [
        98.32,
        [
          300.8,
          14.4,
          409.6,
          48.0
        ],
        false,
        "size"
      ],
      [
        100.63,
        [
          300.8,
          4.8,
          409.6,
          76.8
        ],
        false,
        "size"
      ],
      [
        102.93,
        [
          294.4,
          9.6,
          409.6,
          110.4
        ],
        false,
        "size"
      ],
      [
        105.23,
        [
          300.8,
          14.4,
          409.6,
          148.8
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 2,
    "relock_walls_s": [
      39.33,
      20.83
    ],
    "carry_px_err_mean": 14.3,
    "carry_frames": 1539,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 1539,
      "final_d_true_m": 0.53,
      "final_d_dist_m": 24.22,
      "final_d_dist2_m": null,
      "closest_at_end": "true",
      "relock_on": [
        "true",
        "true"
      ]
    }
  },
  "gate_speed_ms": 0.25,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
