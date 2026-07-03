# Run `20260703T171148Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T17:11:48.219426+00:00
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
    "n_frames": 2939,
    "duration_s": 150.0,
    "achieved_hz": 19.6,
    "carry_fps": 20.4,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 31,
    "n_rejected_acquires": 18,
    "n_reground_gate_rejects": 10,
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
          96.0,
          390.4,
          340.8
        ],
        true,
        ""
      ],
      [
        34.74,
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
        37.1,
        [
          294.4,
          307.2,
          313.6,
          417.6
        ],
        false,
        "size"
      ],
      [
        39.35,
        [
          198.4,
          0.0,
          416.0,
          28.8
        ],
        false,
        "size"
      ],
      [
        41.65,
        [
          288.0,
          0.0,
          409.6,
          76.8
        ],
        false,
        "size"
      ],
      [
        43.96,
        [
          204.8,
          0.0,
          486.4,
          100.8
        ],
        false,
        "size"
      ],
      [
        46.26,
        [
          204.8,
          0.0,
          499.2,
          124.8
        ],
        false,
        "size"
      ],
      [
        48.56,
        [
          211.2,
          0.0,
          422.4,
          163.2
        ],
        false,
        "gate"
      ],
      [
        50.87,
        [
          0.0,
          144.0,
          64.0,
          475.2
        ],
        false,
        "gate"
      ],
      [
        53.27,
        [
          0.0,
          177.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        55.57,
        [
          204.8,
          0.0,
          422.4,
          259.2
        ],
        false,
        "gate"
      ],
      [
        57.88,
        [
          275.2,
          0.0,
          409.6,
          292.8
        ],
        false,
        "gate"
      ],
      [
        60.23,
        [
          262.4,
          72.0,
          396.8,
          326.4
        ],
        false,
        "gate"
      ],
      [
        62.53,
        [
          262.4,
          0.0,
          422.4,
          350.4
        ],
        false,
        "gate"
      ],
      [
        64.84,
        [
          268.8,
          0.0,
          422.4,
          388.8
        ],
        false,
        "gate"
      ],
      [
        67.14,
        [
          268.8,
          0.0,
          422.4,
          412.8
        ],
        false,
        "gate"
      ],
      [
        69.44,
        [
          262.4,
          0.0,
          428.8,
          451.2
        ],
        false,
        "gate"
      ],
      [
        71.85,
        [
          262.4,
          240.0,
          403.2,
          480.0
        ],
        false,
        "gate"
      ],
      [
        74.2,
        [
          294.4,
          67.2,
          422.4,
          225.6
        ],
        true,
        ""
      ],
      [
        86.82,
        [
          224.0,
          470.4,
          281.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        89.17,
        [
          281.6,
          350.4,
          300.8,
          475.2
        ],
        false,
        "size"
      ],
      [
        91.53,
        [
          275.2,
          384.0,
          300.8,
          480.0
        ],
        false,
        "size"
      ],
      [
        93.88,
        [
          275.2,
          417.6,
          300.8,
          480.0
        ],
        false,
        "size"
      ],
      [
        96.13,
        [
          288.0,
          0.0,
          403.2,
          24.0
        ],
        false,
        "size"
      ],
      [
        98.44,
        [
          275.2,
          0.0,
          390.4,
          52.8
        ],
        false,
        "size"
      ],
      [
        100.74,
        [
          281.6,
          19.2,
          390.4,
          86.4
        ],
        false,
        "size"
      ],
      [
        103.04,
        [
          275.2,
          0.0,
          390.4,
          115.2
        ],
        false,
        "size"
      ],
      [
        105.4,
        [
          0.0,
          100.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        107.8,
        [
          0.0,
          139.2,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        110.1,
        [
          249.6,
          0.0,
          396.8,
          220.8
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 2,
    "relock_walls_s": [
      41.82,
      25.69
    ],
    "carry_px_err_mean": 14.4,
    "carry_frames": 1377,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 1377,
      "final_d_true_m": 0.2,
      "final_d_dist_m": 24.54,
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
