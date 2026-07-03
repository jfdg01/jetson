# Run `20260703T091953Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T09:19:53.400002+00:00
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
    "n_frames": 2896,
    "duration_s": 150.0,
    "achieved_hz": 19.3,
    "carry_fps": 18.4,
    "in_fov_frac": 0.4927,
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
        34.78,
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
        37.13,
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
        39.39,
        [
          288.0,
          0.0,
          409.6,
          28.8
        ],
        false,
        "size"
      ],
      [
        41.69,
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
        43.99,
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
        46.29,
        [
          288.0,
          0.0,
          409.6,
          120.0
        ],
        false,
        "motion"
      ],
      [
        48.6,
        [
          281.6,
          0.0,
          409.6,
          163.2
        ],
        false,
        "motion"
      ],
      [
        50.9,
        [
          198.4,
          0.0,
          435.2,
          196.8
        ],
        false,
        "size"
      ],
      [
        53.2,
        [
          204.8,
          0.0,
          492.8,
          225.6
        ],
        false,
        "size"
      ],
      [
        55.6,
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
        57.91,
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
        60.21,
        [
          262.4,
          0.0,
          390.4,
          321.6
        ],
        false,
        "motion"
      ],
      [
        62.51,
        [
          262.4,
          0.0,
          403.2,
          350.4
        ],
        false,
        "motion"
      ],
      [
        64.82,
        [
          256.0,
          0.0,
          416.0,
          379.2
        ],
        false,
        "motion"
      ],
      [
        67.12,
        [
          256.0,
          0.0,
          422.4,
          408.0
        ],
        false,
        "motion"
      ],
      [
        69.42,
        [
          256.0,
          0.0,
          416.0,
          446.4
        ],
        true,
        ""
      ],
      [
        79.55,
        [
          230.4,
          62.4,
          371.2,
          302.4
        ],
        false,
        "motion"
      ],
      [
        81.85,
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
        84.15,
        [
          230.4,
          9.6,
          371.2,
          254.4
        ],
        false,
        "motion"
      ],
      [
        86.46,
        [
          236.8,
          14.4,
          371.2,
          254.4
        ],
        false,
        "motion"
      ],
      [
        88.76,
        [
          230.4,
          9.6,
          371.2,
          254.4
        ],
        false,
        "motion"
      ],
      [
        91.06,
        [
          230.4,
          9.6,
          371.2,
          254.4
        ],
        false,
        "motion"
      ],
      [
        93.37,
        [
          230.4,
          9.6,
          371.2,
          254.4
        ],
        false,
        "motion"
      ],
      [
        95.67,
        [
          230.4,
          9.6,
          371.2,
          254.4
        ],
        false,
        "motion"
      ],
      [
        97.97,
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
        100.27,
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
        102.58,
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
        104.88,
        [
          236.8,
          9.6,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        107.18,
        [
          243.2,
          9.6,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        109.49,
        [
          243.2,
          9.6,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        111.79,
        [
          236.8,
          9.6,
          364.8,
          259.2
        ],
        false,
        "motion"
      ],
      [
        114.09,
        [
          243.2,
          9.6,
          358.4,
          254.4
        ],
        false,
        "motion"
      ],
      [
        116.39,
        [
          236.8,
          9.6,
          364.8,
          259.2
        ],
        false,
        "motion"
      ],
      [
        118.7,
        [
          236.8,
          9.6,
          364.8,
          254.4
        ],
        false,
        "motion"
      ],
      [
        121.0,
        [
          243.2,
          9.6,
          358.4,
          254.4
        ],
        false,
        "motion"
      ],
      [
        123.3,
        [
          243.2,
          9.6,
          364.8,
          259.2
        ],
        false,
        "motion"
      ],
      [
        125.6,
        [
          236.8,
          9.6,
          364.8,
          259.2
        ],
        false,
        "motion"
      ],
      [
        127.91,
        [
          230.4,
          9.6,
          364.8,
          259.2
        ],
        false,
        "motion"
      ],
      [
        130.31,
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
        132.71,
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
        135.12,
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
        137.52,
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
        139.92,
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
        142.32,
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
        144.73,
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
        147.13,
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
        149.53,
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
      37.0
    ],
    "carry_px_err_mean": 8.2,
    "carry_frames": 502,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 4.48,
      "frac_box_closer_distractor": 0.159,
      "n_boxed_twin_frames": 502,
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
