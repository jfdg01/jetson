# Run `20260703T084100Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T08:41:00.688521+00:00
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
    "n_frames": 1476,
    "achieved_hz": 19.7,
    "carry_fps": 20.9,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 18,
    "n_rejected_acquires": 10,
    "n_reground_gate_rejects": 6,
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
        34.72,
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
        37.08,
        [
          300.8,
          307.2,
          320.0,
          417.6
        ],
        false,
        "size"
      ],
      [
        39.33,
        [
          345.6,
          0.0,
          416.0,
          28.8
        ],
        false,
        "size"
      ],
      [
        41.63,
        [
          294.4,
          0.0,
          409.6,
          67.2
        ],
        false,
        "size"
      ],
      [
        43.94,
        [
          211.2,
          0.0,
          422.4,
          96.0
        ],
        false,
        "size"
      ],
      [
        46.24,
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
        48.54,
        [
          288.0,
          0.0,
          409.6,
          163.2
        ],
        false,
        "motion"
      ],
      [
        50.95,
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
        53.35,
        [
          0.0,
          172.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        55.65,
        [
          281.6,
          0.0,
          422.4,
          259.2
        ],
        false,
        "motion"
      ],
      [
        57.96,
        [
          281.6,
          0.0,
          422.4,
          292.8
        ],
        false,
        "motion"
      ],
      [
        60.26,
        [
          281.6,
          0.0,
          428.8,
          326.4
        ],
        false,
        "motion"
      ],
      [
        62.56,
        [
          281.6,
          0.0,
          428.8,
          350.4
        ],
        false,
        "motion"
      ],
      [
        64.87,
        [
          275.2,
          0.0,
          422.4,
          388.8
        ],
        false,
        "motion"
      ],
      [
        67.17,
        [
          192.0,
          0.0,
          505.6,
          417.6
        ],
        false,
        "size"
      ],
      [
        69.47,
        [
          268.8,
          0.0,
          422.4,
          446.4
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      37.12
    ],
    "carry_px_err_mean": 9.3,
    "carry_frames": 558,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 4.12,
      "frac_box_closer_distractor": 0.149,
      "n_boxed_twin_frames": 558,
      "final_d_true_m": 4.07,
      "final_d_dist_m": 1.93,
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
