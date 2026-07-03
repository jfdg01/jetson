# Run `20260703T083319Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T08:33:19.108145+00:00
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
  "reground_gate": "none",
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
    "n_frames": 1432,
    "achieved_hz": 19.1,
    "carry_fps": 20.0,
    "in_fov_frac": 0.9029,
    "first_lock_s": 7.16,
    "n_acquire_attempts": 17,
    "n_rejected_acquires": 12,
    "n_reground_gate_rejects": 0,
    "acquire_log": [
      [
        2.4,
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
        4.81,
        [
          281.6,
          403.2,
          300.8,
          480.0
        ],
        false,
        "size"
      ],
      [
        7.16,
        [
          249.6,
          100.8,
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
        39.52,
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
        41.83,
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
        44.13,
        [
          211.2,
          0.0,
          320.0,
          100.8
        ],
        false,
        "size"
      ],
      [
        46.43,
        [
          204.8,
          0.0,
          492.8,
          129.6
        ],
        false,
        "size"
      ],
      [
        48.73,
        [
          204.8,
          0.0,
          492.8,
          168.0
        ],
        false,
        "size"
      ],
      [
        51.09,
        null,
        false,
        ""
      ],
      [
        53.49,
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
        55.79,
        [
          281.6,
          0.0,
          416.0,
          264.0
        ],
        true,
        ""
      ],
      [
        65.57,
        [
          236.8,
          0.0,
          364.8,
          283.2
        ],
        true,
        ""
      ],
      [
        71.3,
        [
          0.0,
          196.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        73.7,
        [
          0.0,
          201.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ]
    ],
    "n_regrounds": 3,
    "relock_walls_s": [
      23.38,
      2.32
    ],
    "carry_px_err_mean": 13.8,
    "carry_frames": 479,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.81,
      "frac_box_closer_distractor": 0.038,
      "n_boxed_twin_frames": 479,
      "final_d_true_m": 7.91,
      "final_d_dist_m": 1.93,
      "closest_at_end": "distractor",
      "relock_on": [
        "distractor",
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
