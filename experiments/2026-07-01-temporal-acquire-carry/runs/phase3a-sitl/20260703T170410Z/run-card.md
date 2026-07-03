# Run `20260703T170410Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T17:04:10.845657+00:00
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
  "reground_gate": "none",
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
    "n_frames": 2944,
    "duration_s": 150.0,
    "achieved_hz": 19.6,
    "carry_fps": 20.7,
    "in_fov_frac": 0.4497,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 40,
    "n_rejected_acquires": 31,
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
          345.6
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
          294.4,
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
          211.2,
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
          416.0,
          67.2
        ],
        false,
        "size"
      ],
      [
        43.94,
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
        46.24,
        [
          211.2,
          0.0,
          320.0,
          120.0
        ],
        true,
        ""
      ],
      [
        57.81,
        [
          256.0,
          0.0,
          384.0,
          288.0
        ],
        true,
        ""
      ],
      [
        63.35,
        [
          249.6,
          0.0,
          384.0,
          254.4
        ],
        true,
        ""
      ],
      [
        69.04,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        71.44,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        73.85,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        76.25,
        [
          0.0,
          235.2,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        78.65,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        81.06,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        83.46,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        85.86,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        88.17,
        [
          268.8,
          14.4,
          390.4,
          249.6
        ],
        true,
        ""
      ],
      [
        93.73,
        [
          249.6,
          9.6,
          384.0,
          244.8
        ],
        true,
        ""
      ],
      [
        99.4,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        101.81,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        104.21,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        106.62,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        109.02,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        111.42,
        [
          0.0,
          225.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        113.83,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        116.13,
        [
          262.4,
          14.4,
          384.0,
          249.6
        ],
        true,
        ""
      ],
      [
        121.8,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        124.2,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        126.51,
        [
          249.6,
          14.4,
          384.0,
          244.8
        ],
        true,
        ""
      ],
      [
        132.09,
        [
          19.2,
          230.4,
          633.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        134.49,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        136.9,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        139.3,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        141.7,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        144.11,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        146.51,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        148.91,
        [
          0.0,
          230.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ]
    ],
    "n_regrounds": 8,
    "relock_walls_s": [
      13.87,
      2.3,
      2.3,
      21.53,
      2.3,
      19.13,
      7.11
    ],
    "carry_px_err_mean": 24.3,
    "carry_frames": 597,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 68.7,
      "frac_box_closer_distractor": 0.134,
      "n_boxed_twin_frames": 597,
      "final_d_true_m": 26.61,
      "final_d_dist_m": 1.87,
      "final_d_dist2_m": null,
      "closest_at_end": "distractor",
      "relock_on": [
        "true",
        "distractor",
        "distractor",
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
