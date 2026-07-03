# Run `20260703T173735Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T17:37:35.889175+00:00
- **git SHA:** `5be880ccfc2073ad8ccb8563c6c5f3a493084b5a`  ⚠️ DIRTY TREE
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
  "reground_gate": "none",
  "vmax": 2.5,
  "acquire_delay": 0.0,
  "app_tau": 12.0,
  "decoy_shade": 215,
  "decoy2_m": null,
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
    "n_frames": 2955,
    "duration_s": 150.0,
    "achieved_hz": 19.7,
    "carry_fps": 20.6,
    "in_fov_frac": 0.4477,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 45,
    "n_rejected_acquires": 39,
    "n_reground_gate_rejects": 0,
    "app_template": null,
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
        34.75,
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
          417.6
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
        41.76,
        [
          211.2,
          0.0,
          416.0,
          67.2
        ],
        false,
        "size"
      ],
      [
        44.07,
        [
          288.0,
          0.0,
          409.6,
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
          499.2,
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
          499.2,
          168.0
        ],
        false,
        "size"
      ],
      [
        50.98,
        [
          204.8,
          0.0,
          492.8,
          196.8
        ],
        false,
        "size"
      ],
      [
        53.38,
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
        55.68,
        [
          288.0,
          0.0,
          416.0,
          264.0
        ],
        true,
        ""
      ],
      [
        65.39,
        [
          236.8,
          0.0,
          377.6,
          283.2
        ],
        true,
        ""
      ],
      [
        71.01,
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
        73.41,
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
        75.81,
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
        78.22,
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
        80.62,
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
        83.02,
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
        85.33,
        [
          249.6,
          0.0,
          403.2,
          235.2
        ],
        true,
        ""
      ],
      [
        90.99,
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
        93.4,
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
        95.8,
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
        98.2,
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
        100.61,
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
        103.01,
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
        105.41,
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
        107.82,
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
        110.22,
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
        112.62,
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
        115.03,
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
        117.33,
        [
          249.6,
          0.0,
          396.8,
          244.8
        ],
        true,
        ""
      ],
      [
        122.99,
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
        125.4,
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
        127.8,
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
        130.2,
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
        132.61,
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
        135.01,
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
        137.41,
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
        139.82,
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
        142.22,
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
        144.62,
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
        147.03,
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
        149.43,
        [
          0.0,
          196.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ]
    ],
    "n_regrounds": 5,
    "relock_walls_s": [
      23.29,
      2.31,
      16.72,
      28.74
    ],
    "carry_px_err_mean": 13.6,
    "carry_frames": 556,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 51.96,
      "frac_box_closer_distractor": 0.032,
      "n_boxed_twin_frames": 556,
      "final_d_true_m": 26.71,
      "final_d_dist_m": 1.98,
      "final_d_dist2_m": null,
      "closest_at_end": "distractor",
      "relock_on": [
        "distractor",
        "distractor",
        "distractor",
        "distractor"
      ]
    }
  },
  "gate_speed_ms": 0.25,
  "gate": "FAIL"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
