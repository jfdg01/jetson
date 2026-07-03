# Run `20260703T150512Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T15:05:12.905301+00:00
- **git SHA:** `69691e9eaef23ad2cd1ed128149936cec9e045b5`  ⚠️ DIRTY TREE
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
  "reground_gate": "appearance",
  "vmax": 2.5,
  "acquire_delay": 0.0,
  "app_tau": 12.0,
  "decoy_shade": 215,
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
    "n_frames": 2964,
    "duration_s": 150.0,
    "achieved_hz": 19.8,
    "carry_fps": 20.4,
    "in_fov_frac": 0.5027,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 50,
    "n_rejected_acquires": 21,
    "n_reground_gate_rejects": 26,
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
          345.6
        ],
        true,
        ""
      ],
      [
        34.74,
        [
          294.4,
          268.8,
          313.6,
          379.2
        ],
        false,
        "size"
      ],
      [
        37.09,
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
        39.44,
        [
          153.6,
          316.8,
          454.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        41.75,
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
        44.05,
        [
          211.2,
          0.0,
          416.0,
          96.0
        ],
        false,
        "size"
      ],
      [
        46.35,
        [
          204.8,
          0.0,
          499.2,
          120.0
        ],
        false,
        "size"
      ],
      [
        48.66,
        [
          204.8,
          0.0,
          499.2,
          163.2
        ],
        false,
        "size"
      ],
      [
        51.01,
        [
          0.0,
          144.0,
          633.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        53.36,
        [
          0.0,
          230.4,
          64.0,
          480.0
        ],
        false,
        "gate"
      ],
      [
        55.67,
        [
          281.6,
          0.0,
          416.0,
          259.2
        ],
        false,
        "gate"
      ],
      [
        57.97,
        [
          204.8,
          0.0,
          499.2,
          297.6
        ],
        false,
        "size"
      ],
      [
        60.27,
        [
          275.2,
          0.0,
          428.8,
          326.4
        ],
        false,
        "gate"
      ],
      [
        62.58,
        [
          192.0,
          0.0,
          505.6,
          355.2
        ],
        false,
        "size"
      ],
      [
        64.88,
        [
          198.4,
          0.0,
          505.6,
          379.2
        ],
        false,
        "size"
      ],
      [
        67.18,
        [
          268.8,
          0.0,
          428.8,
          408.0
        ],
        false,
        "gate"
      ],
      [
        69.49,
        [
          268.8,
          0.0,
          428.8,
          441.6
        ],
        true,
        ""
      ],
      [
        79.31,
        [
          236.8,
          62.4,
          377.6,
          302.4
        ],
        false,
        "gate"
      ],
      [
        81.61,
        [
          236.8,
          14.4,
          377.6,
          259.2
        ],
        false,
        "gate"
      ],
      [
        84.02,
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
        86.42,
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
        88.82,
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
        91.13,
        [
          236.8,
          14.4,
          377.6,
          254.4
        ],
        false,
        "gate"
      ],
      [
        93.43,
        [
          236.8,
          14.4,
          377.6,
          254.4
        ],
        false,
        "gate"
      ],
      [
        95.73,
        [
          243.2,
          9.6,
          377.6,
          254.4
        ],
        false,
        "gate"
      ],
      [
        98.04,
        [
          243.2,
          9.6,
          377.6,
          254.4
        ],
        false,
        "gate"
      ],
      [
        100.34,
        [
          243.2,
          9.6,
          377.6,
          249.6
        ],
        false,
        "gate"
      ],
      [
        102.64,
        [
          243.2,
          9.6,
          377.6,
          249.6
        ],
        false,
        "gate"
      ],
      [
        104.95,
        [
          243.2,
          9.6,
          377.6,
          249.6
        ],
        false,
        "gate"
      ],
      [
        107.25,
        [
          243.2,
          9.6,
          377.6,
          249.6
        ],
        false,
        "gate"
      ],
      [
        109.55,
        [
          243.2,
          9.6,
          384.0,
          254.4
        ],
        false,
        "gate"
      ],
      [
        111.86,
        [
          243.2,
          14.4,
          377.6,
          249.6
        ],
        false,
        "gate"
      ],
      [
        114.26,
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
        116.56,
        [
          249.6,
          14.4,
          390.4,
          254.4
        ],
        false,
        "gate"
      ],
      [
        118.97,
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
        121.37,
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
        123.67,
        [
          243.2,
          14.4,
          390.4,
          249.6
        ],
        false,
        "gate"
      ],
      [
        126.08,
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
        128.38,
        [
          249.6,
          14.4,
          384.0,
          259.2
        ],
        false,
        "gate"
      ],
      [
        130.68,
        [
          249.6,
          14.4,
          384.0,
          254.4
        ],
        false,
        "gate"
      ],
      [
        132.99,
        [
          249.6,
          14.4,
          390.4,
          254.4
        ],
        false,
        "gate"
      ],
      [
        135.29,
        [
          256.0,
          14.4,
          390.4,
          254.4
        ],
        false,
        "gate"
      ],
      [
        137.59,
        [
          249.6,
          14.4,
          390.4,
          254.4
        ],
        false,
        "gate"
      ],
      [
        139.9,
        [
          249.6,
          14.4,
          390.4,
          254.4
        ],
        false,
        "gate"
      ],
      [
        142.3,
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
        144.6,
        [
          249.6,
          14.4,
          396.8,
          254.4
        ],
        false,
        "gate"
      ],
      [
        147.01,
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
        149.31,
        [
          249.6,
          14.4,
          396.8,
          254.4
        ],
        false,
        "gate"
      ]
    ],
    "n_regrounds": 2,
    "relock_walls_s": [
      37.11
    ],
    "carry_px_err_mean": 9.1,
    "carry_frames": 551,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 4.16,
      "frac_box_closer_distractor": 0.151,
      "n_boxed_twin_frames": 551,
      "final_d_true_m": 26.5,
      "final_d_dist_m": 1.76,
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
