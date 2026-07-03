# Run `20260703T160426Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T16:04:26.911522+00:00
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
    "n_frames": 2958,
    "duration_s": 150.0,
    "achieved_hz": 19.7,
    "carry_fps": 20.7,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 23,
    "n_rejected_acquires": 8,
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
          249.6,
          96.0,
          390.4,
          340.8
        ],
        true,
        ""
      ],
      [
        34.81,
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
        37.16,
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
          313.6,
          0.0,
          409.6,
          28.8
        ],
        false,
        "size"
      ],
      [
        41.72,
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
        44.02,
        [
          204.8,
          0.0,
          492.8,
          100.8
        ],
        false,
        "size"
      ],
      [
        46.33,
        [
          204.8,
          0.0,
          320.0,
          120.0
        ],
        false,
        "gate"
      ],
      [
        48.63,
        [
          211.2,
          0.0,
          499.2,
          168.0
        ],
        false,
        "size"
      ],
      [
        50.93,
        [
          198.4,
          0.0,
          422.4,
          182.4
        ],
        false,
        "gate"
      ],
      [
        53.29,
        [
          0.0,
          192.0,
          64.0,
          480.0
        ],
        false,
        "gate"
      ],
      [
        55.69,
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
        57.99,
        [
          262.4,
          0.0,
          409.6,
          297.6
        ],
        false,
        "gate"
      ],
      [
        60.3,
        [
          268.8,
          0.0,
          422.4,
          321.6
        ],
        false,
        "gate"
      ],
      [
        62.6,
        [
          268.8,
          0.0,
          416.0,
          345.6
        ],
        false,
        "gate"
      ],
      [
        64.9,
        [
          262.4,
          0.0,
          416.0,
          369.6
        ],
        false,
        "gate"
      ],
      [
        67.21,
        [
          262.4,
          0.0,
          422.4,
          403.2
        ],
        false,
        "gate"
      ],
      [
        69.51,
        [
          262.4,
          0.0,
          428.8,
          441.6
        ],
        false,
        "gate"
      ],
      [
        71.86,
        [
          256.0,
          235.2,
          396.8,
          470.4
        ],
        false,
        "gate"
      ],
      [
        74.27,
        [
          256.0,
          264.0,
          396.8,
          480.0
        ],
        false,
        "gate"
      ],
      [
        76.67,
        [
          256.0,
          297.6,
          396.8,
          480.0
        ],
        false,
        "gate"
      ],
      [
        79.07,
        [
          262.4,
          331.2,
          390.4,
          480.0
        ],
        false,
        "gate"
      ],
      [
        81.38,
        [
          294.4,
          0.0,
          422.4,
          211.2
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      48.93
    ],
    "carry_px_err_mean": 13.8,
    "carry_frames": 1826,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 1826,
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
