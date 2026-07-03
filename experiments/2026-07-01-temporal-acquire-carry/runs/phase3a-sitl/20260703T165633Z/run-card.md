# Run `20260703T165633Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T16:56:33.471800+00:00
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
  "decoy2_m": 7.0,
  "occ2": null,
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
    "n_acquire_attempts": 28,
    "n_rejected_acquires": 12,
    "n_reground_gate_rejects": 13,
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
          340.8
        ],
        true,
        ""
      ],
      [
        34.76,
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
        37.11,
        [
          294.4,
          307.2,
          313.6,
          412.8
        ],
        false,
        "size"
      ],
      [
        39.46,
        [
          147.2,
          321.6,
          454.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        41.77,
        [
          288.0,
          0.0,
          409.6,
          67.2
        ],
        false,
        "size"
      ],
      [
        44.07,
        [
          204.8,
          0.0,
          492.8,
          100.8
        ],
        false,
        "size"
      ],
      [
        46.37,
        [
          204.8,
          0.0,
          492.8,
          124.8
        ],
        false,
        "size"
      ],
      [
        48.67,
        [
          204.8,
          0.0,
          422.4,
          163.2
        ],
        false,
        "gate"
      ],
      [
        51.03,
        [
          0.0,
          456.0,
          160.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        53.43,
        [
          0.0,
          192.0,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        55.73,
        [
          198.4,
          0.0,
          416.0,
          259.2
        ],
        false,
        "gate"
      ],
      [
        58.04,
        [
          192.0,
          0.0,
          416.0,
          292.8
        ],
        false,
        "gate"
      ],
      [
        60.34,
        [
          268.8,
          0.0,
          416.0,
          321.6
        ],
        false,
        "gate"
      ],
      [
        62.64,
        [
          268.8,
          0.0,
          403.2,
          345.6
        ],
        false,
        "gate"
      ],
      [
        64.95,
        [
          268.8,
          0.0,
          422.4,
          374.4
        ],
        false,
        "gate"
      ],
      [
        67.25,
        [
          262.4,
          0.0,
          422.4,
          412.8
        ],
        false,
        "gate"
      ],
      [
        69.55,
        [
          256.0,
          0.0,
          428.8,
          441.6
        ],
        false,
        "gate"
      ],
      [
        71.96,
        [
          256.0,
          235.2,
          396.8,
          480.0
        ],
        false,
        "gate"
      ],
      [
        74.31,
        [
          294.4,
          91.2,
          416.0,
          216.0
        ],
        true,
        ""
      ],
      [
        84.33,
        [
          288.0,
          67.2,
          384.0,
          124.8
        ],
        false,
        "size"
      ],
      [
        86.68,
        [
          294.4,
          321.6,
          320.0,
          441.6
        ],
        false,
        "size"
      ],
      [
        89.09,
        [
          294.4,
          350.4,
          313.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        91.39,
        [
          256.0,
          0.0,
          416.0,
          384.0
        ],
        false,
        "gate"
      ],
      [
        93.69,
        [
          256.0,
          0.0,
          416.0,
          412.8
        ],
        false,
        "gate"
      ],
      [
        96.0,
        [
          249.6,
          0.0,
          422.4,
          446.4
        ],
        false,
        "gate"
      ],
      [
        98.41,
        [
          256.0,
          235.2,
          390.4,
          480.0
        ],
        false,
        "gate"
      ],
      [
        100.71,
        [
          281.6,
          0.0,
          422.4,
          240.0
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 2,
    "relock_walls_s": [
      41.91,
      18.73
    ],
    "carry_px_err_mean": 14.9,
    "carry_frames": 1516,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 1516,
      "final_d_true_m": 0.21,
      "final_d_dist_m": 24.54,
      "final_d_dist2_m": 17.54,
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
