# Run `20260703T160038Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T16:00:38.231504+00:00
- **git SHA:** `c6b4a879cc8fa808e353866c947307e5f5abe62a`  ⚠️ DIRTY TREE
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
    "n_frames": 2949,
    "duration_s": 150.0,
    "achieved_hz": 19.7,
    "carry_fps": 20.5,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 25,
    "n_rejected_acquires": 10,
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
          256.0,
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
          379.2
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
          412.8
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
          409.6,
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
          81.6
        ],
        false,
        "size"
      ],
      [
        46.3,
        [
          198.4,
          0.0,
          409.6,
          120.0
        ],
        false,
        "gate"
      ],
      [
        48.6,
        [
          281.6,
          0.0,
          403.2,
          153.6
        ],
        false,
        "gate"
      ],
      [
        50.9,
        [
          198.4,
          0.0,
          486.4,
          187.2
        ],
        false,
        "size"
      ],
      [
        53.31,
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
        55.71,
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
        58.01,
        [
          268.8,
          0.0,
          396.8,
          278.4
        ],
        false,
        "gate"
      ],
      [
        60.37,
        [
          262.4,
          72.0,
          403.2,
          312.0
        ],
        false,
        "gate"
      ],
      [
        62.67,
        [
          256.0,
          0.0,
          396.8,
          340.8
        ],
        false,
        "gate"
      ],
      [
        64.97,
        [
          256.0,
          0.0,
          403.2,
          369.6
        ],
        false,
        "gate"
      ],
      [
        67.28,
        [
          256.0,
          0.0,
          416.0,
          398.4
        ],
        false,
        "gate"
      ],
      [
        69.58,
        [
          256.0,
          0.0,
          416.0,
          436.8
        ],
        false,
        "gate"
      ],
      [
        71.93,
        [
          249.6,
          230.4,
          396.8,
          470.4
        ],
        false,
        "gate"
      ],
      [
        74.34,
        [
          243.2,
          264.0,
          390.4,
          480.0
        ],
        false,
        "gate"
      ],
      [
        76.74,
        [
          243.2,
          292.8,
          377.6,
          480.0
        ],
        false,
        "gate"
      ],
      [
        79.14,
        [
          249.6,
          326.4,
          377.6,
          480.0
        ],
        false,
        "gate"
      ],
      [
        81.55,
        [
          256.0,
          355.2,
          377.6,
          480.0
        ],
        false,
        "gate"
      ],
      [
        83.95,
        [
          256.0,
          388.8,
          377.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        86.25,
        [
          288.0,
          0.0,
          409.6,
          196.8
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      53.84
    ],
    "carry_px_err_mean": 13.9,
    "carry_frames": 1719,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 1719,
      "final_d_true_m": 0.21,
      "final_d_dist_m": 24.53,
      "closest_at_end": "true",
      "relock_on": [
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
