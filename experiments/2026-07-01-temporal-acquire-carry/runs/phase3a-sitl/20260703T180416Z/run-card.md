# Run `20260703T180416Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T18:04:16.728206+00:00
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
  "reground_gate": "mask",
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
    "n_frames": 2949,
    "duration_s": 150.0,
    "achieved_hz": 19.7,
    "carry_fps": 20.5,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 26,
    "n_rejected_acquires": 11,
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
          345.6
        ],
        true,
        ""
      ],
      [
        34.79,
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
        37.14,
        [
          288.0,
          307.2,
          307.2,
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
        41.7,
        [
          281.6,
          0.0,
          403.2,
          72.0
        ],
        false,
        "size"
      ],
      [
        44.0,
        [
          281.6,
          0.0,
          403.2,
          100.8
        ],
        false,
        "size"
      ],
      [
        46.3,
        [
          268.8,
          0.0,
          409.6,
          124.8
        ],
        false,
        "gate"
      ],
      [
        48.61,
        [
          275.2,
          0.0,
          396.8,
          163.2
        ],
        false,
        "gate"
      ],
      [
        51.01,
        [
          0.0,
          144.0,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        53.36,
        [
          19.2,
          192.0,
          633.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        55.67,
        [
          256.0,
          0.0,
          403.2,
          254.4
        ],
        false,
        "gate"
      ],
      [
        57.97,
        [
          256.0,
          0.0,
          409.6,
          292.8
        ],
        false,
        "gate"
      ],
      [
        60.27,
        [
          256.0,
          0.0,
          403.2,
          326.4
        ],
        false,
        "gate"
      ],
      [
        62.58,
        [
          249.6,
          0.0,
          396.8,
          340.8
        ],
        false,
        "gate"
      ],
      [
        64.88,
        [
          243.2,
          0.0,
          396.8,
          384.0
        ],
        false,
        "gate"
      ],
      [
        67.18,
        [
          243.2,
          0.0,
          403.2,
          412.8
        ],
        false,
        "gate"
      ],
      [
        69.49,
        [
          243.2,
          0.0,
          396.8,
          446.4
        ],
        false,
        "gate"
      ],
      [
        71.89,
        [
          236.8,
          240.0,
          377.6,
          480.0
        ],
        false,
        "gate"
      ],
      [
        74.3,
        [
          230.4,
          273.6,
          371.2,
          480.0
        ],
        false,
        "gate"
      ],
      [
        76.7,
        [
          230.4,
          302.4,
          371.2,
          480.0
        ],
        false,
        "gate"
      ],
      [
        79.11,
        [
          230.4,
          336.0,
          364.8,
          480.0
        ],
        false,
        "gate"
      ],
      [
        81.51,
        [
          236.8,
          374.4,
          358.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        83.91,
        [
          236.8,
          408.0,
          358.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        86.32,
        [
          236.8,
          436.8,
          358.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        88.62,
        [
          268.8,
          0.0,
          403.2,
          216.0
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      56.19
    ],
    "carry_px_err_mean": 13.7,
    "carry_frames": 1672,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 1672,
      "final_d_true_m": 0.2,
      "final_d_dist_m": 24.54,
      "final_d_dist2_m": null,
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
