# Run `20260703T083553Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T08:35:53.038459+00:00
- **git SHA:** `2344f6ab6c1d39dd49dc8f2ddb93a7034d56168b`  ⚠️ DIRTY TREE
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
  "duration_s": 75.0,
  "hz": 20,
  "image_size": 1024,
  "sam2": "facebook/sam2.1-hiera-tiny",
  "validate": "sizeprior-0.5-2.0",
  "deadreckon": true,
  "twin": "decoy",
  "loss_gate": "motion",
  "score_tau": 0.0,
  "dr": "pursuit",
  "acquire_hold": "motion",
  "reground_gate": "motion",
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
    "n_frames": 1455,
    "achieved_hz": 19.4,
    "carry_fps": 20.1,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 18,
    "n_rejected_acquires": 8,
    "n_reground_gate_rejects": 8,
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
        34.77,
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
        37.12,
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
        39.38,
        [
          217.6,
          0.0,
          409.6,
          28.8
        ],
        false,
        "size"
      ],
      [
        41.68,
        [
          288.0,
          0.0,
          403.2,
          62.4
        ],
        false,
        "size"
      ],
      [
        43.98,
        [
          281.6,
          0.0,
          403.2,
          96.0
        ],
        false,
        "size"
      ],
      [
        46.28,
        [
          288.0,
          0.0,
          409.6,
          124.8
        ],
        false,
        "motion"
      ],
      [
        48.59,
        [
          204.8,
          0.0,
          422.4,
          163.2
        ],
        false,
        "motion"
      ],
      [
        50.89,
        [
          204.8,
          0.0,
          416.0,
          196.8
        ],
        false,
        "motion"
      ],
      [
        53.19,
        [
          198.4,
          0.0,
          492.8,
          225.6
        ],
        false,
        "size"
      ],
      [
        55.5,
        [
          192.0,
          0.0,
          492.8,
          259.2
        ],
        false,
        "size"
      ],
      [
        57.8,
        [
          268.8,
          0.0,
          396.8,
          288.0
        ],
        false,
        "motion"
      ],
      [
        60.1,
        [
          268.8,
          0.0,
          390.4,
          321.6
        ],
        false,
        "motion"
      ],
      [
        62.4,
        [
          262.4,
          0.0,
          409.6,
          345.6
        ],
        false,
        "motion"
      ],
      [
        64.71,
        [
          256.0,
          0.0,
          409.6,
          374.4
        ],
        false,
        "motion"
      ],
      [
        67.01,
        [
          256.0,
          0.0,
          416.0,
          408.0
        ],
        false,
        "motion"
      ],
      [
        69.31,
        [
          249.6,
          0.0,
          422.4,
          441.6
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      36.91
    ],
    "carry_px_err_mean": 8.3,
    "carry_frames": 542,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 4.24,
      "frac_box_closer_distractor": 0.153,
      "n_boxed_twin_frames": 542,
      "final_d_true_m": 4.32,
      "final_d_dist_m": 1.68,
      "closest_at_end": "distractor",
      "relock_on": [
        "distractor"
      ]
    }
  },
  "gate_speed_ms": 0.25,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
