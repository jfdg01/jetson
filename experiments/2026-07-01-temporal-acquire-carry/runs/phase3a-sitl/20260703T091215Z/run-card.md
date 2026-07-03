# Run `20260703T091215Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T09:12:15.428583+00:00
- **git SHA:** `50cf356ffd36c9ce3e3b387c32b05e1e23b8302a`  ⚠️ DIRTY TREE
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
    "n_frames": 2911,
    "duration_s": 150.0,
    "achieved_hz": 19.4,
    "carry_fps": 18.8,
    "in_fov_frac": 0.4954,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 50,
    "n_rejected_acquires": 18,
    "n_reground_gate_rejects": 29,
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
        34.87,
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
        37.22,
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
        39.47,
        [
          294.4,
          0.0,
          409.6,
          28.8
        ],
        false,
        "size"
      ],
      [
        41.78,
        [
          288.0,
          0.0,
          403.2,
          67.2
        ],
        false,
        "size"
      ],
      [
        44.08,
        [
          288.0,
          0.0,
          409.6,
          96.0
        ],
        false,
        "size"
      ],
      [
        46.38,
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
        48.68,
        [
          294.4,
          0.0,
          403.2,
          163.2
        ],
        false,
        "motion"
      ],
      [
        50.99,
        [
          288.0,
          0.0,
          403.2,
          196.8
        ],
        false,
        "motion"
      ],
      [
        53.39,
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
        55.69,
        [
          268.8,
          0.0,
          409.6,
          264.0
        ],
        false,
        "motion"
      ],
      [
        57.99,
        [
          268.8,
          0.0,
          390.4,
          292.8
        ],
        false,
        "motion"
      ],
      [
        60.3,
        [
          268.8,
          0.0,
          409.6,
          321.6
        ],
        false,
        "motion"
      ],
      [
        62.6,
        [
          262.4,
          0.0,
          416.0,
          350.4
        ],
        false,
        "motion"
      ],
      [
        64.9,
        [
          256.0,
          0.0,
          416.0,
          384.0
        ],
        false,
        "motion"
      ],
      [
        67.21,
        [
          249.6,
          0.0,
          416.0,
          412.8
        ],
        false,
        "motion"
      ],
      [
        69.51,
        [
          256.0,
          0.0,
          422.4,
          446.4
        ],
        true,
        ""
      ],
      [
        79.54,
        [
          230.4,
          72.0,
          371.2,
          312.0
        ],
        false,
        "motion"
      ],
      [
        81.84,
        [
          230.4,
          14.4,
          371.2,
          259.2
        ],
        false,
        "motion"
      ],
      [
        84.14,
        [
          230.4,
          14.4,
          371.2,
          259.2
        ],
        false,
        "motion"
      ],
      [
        86.55,
        [
          0.0,
          211.2,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        88.85,
        [
          230.4,
          14.4,
          371.2,
          259.2
        ],
        false,
        "motion"
      ],
      [
        91.15,
        [
          230.4,
          14.4,
          371.2,
          254.4
        ],
        false,
        "motion"
      ],
      [
        93.46,
        [
          230.4,
          14.4,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        95.76,
        [
          230.4,
          14.4,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        98.06,
        [
          230.4,
          14.4,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        100.36,
        [
          230.4,
          14.4,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        102.67,
        [
          230.4,
          14.4,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        104.97,
        [
          230.4,
          9.6,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        107.27,
        [
          230.4,
          9.6,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        109.57,
        [
          230.4,
          9.6,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        111.88,
        [
          230.4,
          14.4,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        114.18,
        [
          236.8,
          14.4,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        116.48,
        [
          230.4,
          14.4,
          364.8,
          259.2
        ],
        false,
        "motion"
      ],
      [
        118.79,
        [
          236.8,
          9.6,
          358.4,
          259.2
        ],
        false,
        "motion"
      ],
      [
        121.09,
        [
          230.4,
          9.6,
          358.4,
          259.2
        ],
        false,
        "motion"
      ],
      [
        123.49,
        [
          0.0,
          206.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        125.89,
        [
          0.0,
          211.2,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        128.3,
        [
          0.0,
          206.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        130.7,
        [
          0.0,
          211.2,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        133.0,
        [
          224.0,
          9.6,
          364.8,
          259.2
        ],
        false,
        "motion"
      ],
      [
        135.41,
        [
          0.0,
          211.2,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        137.71,
        [
          217.6,
          9.6,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        140.01,
        [
          224.0,
          9.6,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        142.41,
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
        144.82,
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
        147.22,
        [
          0.0,
          211.2,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        149.62,
        [
          0.0,
          211.2,
          640.0,
          480.0
        ],
        false,
        "size"
      ]
    ],
    "n_regrounds": 2,
    "relock_walls_s": [
      37.13
    ],
    "carry_px_err_mean": 8.3,
    "carry_frames": 513,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 4.37,
      "frac_box_closer_distractor": 0.156,
      "n_boxed_twin_frames": 513,
      "final_d_true_m": 26.51,
      "final_d_dist_m": 1.93,
      "closest_at_end": "distractor",
      "relock_on": [
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
