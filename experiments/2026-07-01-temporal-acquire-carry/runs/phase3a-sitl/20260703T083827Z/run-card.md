# Run `20260703T083827Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T08:38:27.012780+00:00
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
    "n_frames": 1472,
    "achieved_hz": 19.6,
    "carry_fps": 21.0,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 18,
    "n_rejected_acquires": 9,
    "n_reground_gate_rejects": 7,
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
        37.07,
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
        39.42,
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
        41.73,
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
        44.03,
        [
          204.8,
          0.0,
          486.4,
          96.0
        ],
        false,
        "size"
      ],
      [
        46.33,
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
        48.64,
        [
          294.4,
          0.0,
          409.6,
          168.0
        ],
        false,
        "motion"
      ],
      [
        50.94,
        [
          288.0,
          0.0,
          409.6,
          196.8
        ],
        false,
        "motion"
      ],
      [
        53.24,
        [
          275.2,
          0.0,
          409.6,
          225.6
        ],
        false,
        "motion"
      ],
      [
        55.65,
        [
          0.0,
          216.0,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        57.95,
        [
          268.8,
          0.0,
          409.6,
          292.8
        ],
        false,
        "motion"
      ],
      [
        60.25,
        [
          192.0,
          0.0,
          505.6,
          326.4
        ],
        false,
        "size"
      ],
      [
        62.55,
        [
          268.8,
          0.0,
          409.6,
          350.4
        ],
        false,
        "motion"
      ],
      [
        64.86,
        [
          268.8,
          0.0,
          422.4,
          384.0
        ],
        false,
        "motion"
      ],
      [
        67.16,
        [
          262.4,
          0.0,
          428.8,
          412.8
        ],
        false,
        "motion"
      ],
      [
        69.46,
        [
          262.4,
          0.0,
          428.8,
          446.4
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      37.1
    ],
    "carry_px_err_mean": 8.7,
    "carry_frames": 556,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 4.18,
      "frac_box_closer_distractor": 0.151,
      "n_boxed_twin_frames": 556,
      "final_d_true_m": 4.05,
      "final_d_dist_m": 1.94,
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
